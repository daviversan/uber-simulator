"""Consultas sobre o histórico (tabela positions), usadas pelo painel Analytics.

Cada função recebe uma sessão aberta e devolve dados prontos para virar JSON.
O cache fica em quem chama (rpc.py).
"""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cities import CITIES, nearest_city
from app.models import Position

ACTIVE_WINDOW = timedelta(minutes=5)


async def summary(session: AsyncSession) -> dict:
    """Quantos motoristas diferentes mandaram posição nos últimos 5 minutos."""
    since = datetime.now(timezone.utc) - ACTIVE_WINDOW
    query = select(func.count(func.distinct(Position.driver_id))).where(Position.recorded_at >= since)
    return {"active_drivers": (await session.execute(query)).scalar_one()}


async def by_city(session: AsyncSession) -> list[dict]:
    """Motoristas por cidade. Não há coluna "cidade": calcula-se a posição média
    de cada motorista no SQL e se classifica em Python pela cidade mais próxima."""
    query = select(
        func.avg(Position.latitude), func.avg(Position.longitude)
    ).group_by(Position.driver_id)

    counts = {city_id: 0 for city_id in CITIES}
    for lat, lon in (await session.execute(query)).all():
        counts[nearest_city(lat, lon)] += 1

    return [
        {"city_id": city_id, "city_name": info["name"], "driver_count": counts[city_id]}
        for city_id, info in CITIES.items()
    ]


_BUCKET_RE = re.compile(r"^(\d+)([smh])$")
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600}
_METRICS = {
    "points": func.count(),
    "active_drivers": func.count(func.distinct(Position.driver_id)),
}


async def timeseries(session: AsyncSession, metric: str, bucket: str) -> list[dict]:
    """Série temporal em janelas de `bucket` (ex.: "30s", "5m").

    Para agrupar em janelas de N segundos: floor(epoch / N) * N leva cada
    instante ao início da sua janela. Lança ValueError se metric/bucket forem inválidos.
    """
    match = _BUCKET_RE.match(bucket)
    if metric not in _METRICS or not match:
        raise ValueError(f"use metric em {list(_METRICS)} e bucket como '30s', '5m' ou '1h'")
    seconds = int(match[1]) * _UNIT_SECONDS[match[2]]

    epoch = func.extract("epoch", Position.recorded_at)
    bucket_start = func.floor(epoch / seconds) * seconds
    query = select(bucket_start, _METRICS[metric]).group_by(bucket_start).order_by(bucket_start)

    return [
        {"timestamp": datetime.fromtimestamp(float(start), tz=timezone.utc).isoformat(), "value": int(value)}
        for start, value in (await session.execute(query)).all()
    ]


async def driver_history(session: AsyncSession, driver_id: str, since: datetime) -> list[dict]:
    """Trilha de um motorista desde `since`, da mais antiga para a mais recente."""
    query = (
        select(Position.latitude, Position.longitude, Position.recorded_at)
        .where(Position.driver_id == driver_id, Position.recorded_at >= since)
        .order_by(Position.recorded_at)
    )
    return [
        {"latitude": lat, "longitude": lon, "recorded_at": recorded_at.isoformat()}
        for lat, lon, recorded_at in (await session.execute(query)).all()
    ]
