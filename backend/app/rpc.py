"""Pedido/resposta sobre o WebSocket (o substituto das rotas REST).

O cliente manda  {"type": "request", "id": "7", "op": "analytics.summary", "payload": {}}
e recebe          {"type": "response", "id": "7", "ok": true, "data": {...}}

Cada op é uma função registrada com @op. `roles` diz quem pode chamá-la, e o
padrão é só admin: uma op nova nasce fechada (negar por padrão).
"""
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import redis.asyncio as redis
from pydantic import ValidationError

from app import analytics, jobs, store
from app.cache import cached
from app.cities import CITIES
from app.db import async_session
from app.schemas import sim_command_adapter

# "guest" = socket que ainda não fez `join`.
Caller = Literal["admin", "driver", "guest"]
Handler = Callable[[redis.Redis, dict[str, Any]], Awaitable[Any]]


class RpcError(Exception):
    """Erro que vira {"ok": false, "error": {"code", "message"}} na resposta."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


_OPS: dict[str, tuple[Handler, tuple[Caller, ...]]] = {}


def op(name: str, roles: tuple[Caller, ...] = ("admin",)):
    def register(fn: Handler) -> Handler:
        _OPS[name] = (fn, roles)
        return fn
    return register


async def call(r: redis.Redis, name: str, payload: dict[str, Any], role: Caller) -> Any:
    if name not in _OPS:
        raise RpcError("unknown_op", f"op desconhecida: {name}")
    handler, roles = _OPS[name]
    if role not in roles:
        if role == "guest":
            raise RpcError("join_required", f"envie `join` antes de chamar {name}")
        raise RpcError("forbidden", f"role={role} não pode chamar {name}")
    return await handler(r, payload)


def first_error(exc: ValidationError) -> str:
    """Primeiro erro de validação do pydantic, em uma linha legível."""
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"])
    return f"{loc}: {err['msg']}" if loc else err["msg"]


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise RpcError("invalid_payload", f"{key} é obrigatório")
    return value.strip()


# --- Cidades (pública: a tela de entrada do motorista usa antes do join) -----

@op("cities.list", roles=("admin", "driver", "guest"))
async def cities_list(r: redis.Redis, payload: dict[str, Any]) -> list[dict]:
    return [
        {"city_id": city_id, "name": info["name"], "center": {"lat": info["center"][0], "lon": info["center"][1]}}
        for city_id, info in CITIES.items()
    ]


# --- Frota --------------------------------------------------------------------

@op("drivers.nearby")
async def drivers_nearby(r: redis.Redis, payload: dict[str, Any]) -> list[dict]:
    try:
        lat, lon, radius = (float(payload[k]) for k in ("lat", "lon", "radius_km"))
    except (KeyError, TypeError, ValueError):
        raise RpcError("invalid_payload", "lat, lon e radius_km numéricos são obrigatórios")
    return await store.get_nearby(r, lat, lon, radius)


@op("drivers.history")
async def drivers_history(r: redis.Redis, payload: dict[str, Any]) -> list[dict]:
    driver_id = _require_str(payload, "driver_id")
    try:
        since = (
            datetime.fromisoformat(payload["since"])
            if payload.get("since")
            else datetime.now(timezone.utc) - timedelta(hours=1)
        )
    except (TypeError, ValueError):
        raise RpcError("invalid_payload", "since deve ser uma data ISO-8601")
    # Sessão aberta por chamada, não por socket: um socket vive horas e o pool só tem 10 conexões.
    async with async_session() as session:
        return await analytics.driver_history(session, driver_id, since)


# --- Simulação ----------------------------------------------------------------

@op("simulation.state")
async def simulation_state(r: redis.Redis, payload: dict[str, Any]) -> dict:
    return await r.hgetall("sim:state") or {"status": "unknown"}


@op("simulation.command")
async def simulation_command(r: redis.Redis, payload: dict[str, Any]) -> dict:
    try:
        cmd = sim_command_adapter.validate_python(payload)
    except ValidationError as exc:
        raise RpcError("invalid_payload", first_error(exc))
    # A API só repassa o comando ao simulador pelo Redis. Pub/sub não confirma
    # entrega, então a resposta é "aceito", não "executado": o efeito aparece em simulation.state.
    await r.publish("sim:cmd", cmd.model_dump_json())
    return {"accepted": True}


# --- Analytics (com cache de 5 s, ver cache.py) -------------------------------

@op("analytics.summary")
async def analytics_summary(r: redis.Redis, payload: dict[str, Any]) -> Any:
    async with async_session() as session:
        return await cached(r, "analytics:summary", 5, lambda: analytics.summary(session))


@op("analytics.by_city")
async def analytics_by_city(r: redis.Redis, payload: dict[str, Any]) -> Any:
    async with async_session() as session:
        return await cached(r, "analytics:by_city", 5, lambda: analytics.by_city(session))


@op("analytics.timeseries")
async def analytics_timeseries(r: redis.Redis, payload: dict[str, Any]) -> Any:
    metric = _require_str(payload, "metric")
    bucket = str(payload.get("bucket", "5m"))
    try:
        async with async_session() as session:
            return await cached(
                r, f"analytics:timeseries:{metric}:{bucket}", 5,
                lambda: analytics.timeseries(session, metric, bucket),
            )
    except ValueError as exc:
        raise RpcError("invalid_payload", str(exc))


# --- Jobs ---------------------------------------------------------------------

@op("jobs.list")
async def jobs_list(r: redis.Redis, payload: dict[str, Any]) -> list[dict]:
    async with async_session() as session:
        return await jobs.list_jobs(session)


@op("jobs.run")
async def jobs_run(r: redis.Redis, payload: dict[str, Any]) -> dict:
    name = _require_str(payload, "name")
    if name not in jobs.JOBS:
        raise RpcError("not_found", f"job desconhecido: {name}")
    async with async_session() as session:
        return await jobs.run_job(session, r, name)
