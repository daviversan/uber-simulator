"""O único caminho de escrita de uma posição, usado pelo app do motorista e pelo simulador."""
from datetime import datetime, timezone

import redis.asyncio as redis
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import store
from app.events import publish_position
from app.geo import haversine_m
from app.models import Driver, Position
from app.schemas import TelemetryInput
from app.settings import settings


async def ingest_position(r: redis.Redis, session: AsyncSession, data: TelemetryInput) -> None:
    """Grava a posição no Redis (estado atual), avisa os admins (pub/sub) e grava
    no Postgres (histórico).

    Se o motorista andou menos que min_move_m desde a última posição gravada, a
    mensagem é só um heartbeat (prova de vida): renova o horário, mas não
    publica nada nem cria linha nova no histórico. O servidor aplica essa regra
    sozinho, então vale para qualquer cliente.
    """
    payload = data.model_dump(mode="json")
    prev = await store.get_one(r, data.driver_id)
    moved = prev is None or (
        haversine_m(prev["latitude"], prev["longitude"], data.latitude, data.longitude)
        >= settings.min_move_m
    )

    if moved:
        await store.save_position(r, data.driver_id, payload)
        await publish_position(r, payload)
    else:
        # Mantém as coordenadas antigas e só atualiza o horário. Se gravássemos as
        # novas, a próxima comparação partiria delas, e um deslocamento lento
        # (ex.: 4 m por mensagem) nunca somaria os 10 m.
        await store.save_position(r, data.driver_id, {**prev, "timestamp": payload["timestamp"]})

    # Upsert: cria o motorista na primeira vez; nas seguintes, só atualiza last_seen.
    now = datetime.now(timezone.utc)
    await session.execute(
        pg_insert(Driver)
        .values(driver_id=data.driver_id, first_seen=now, last_seen=now)
        .on_conflict_do_update(index_elements=[Driver.driver_id], set_={"last_seen": now})
    )
    if moved:
        await session.execute(
            Position.__table__.insert().values(
                driver_id=data.driver_id,
                latitude=data.latitude,
                longitude=data.longitude,
                recorded_at=data.timestamp,
            )
        )
    await session.commit()
