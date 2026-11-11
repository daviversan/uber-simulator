"""Estado ATUAL da frota no Redis (o histórico fica no Postgres).

Duas estruturas, sempre atualizadas juntas:
- drivers:last (hash):  driver_id -> JSON da última posição. Leitura O(1) por motorista.
- drivers:geo  (geo):   índice espacial para "quem está a até X km daqui?".
"""
import json
from typing import Any

import redis.asyncio as redis

LAST_KEY = "drivers:last"
GEO_KEY = "drivers:geo"


async def save_position(r: redis.Redis, driver_id: str, data: dict[str, Any]) -> None:
    await r.hset(LAST_KEY, driver_id, json.dumps(data))
    await r.geoadd(GEO_KEY, (data["longitude"], data["latitude"], driver_id))


async def get_one(r: redis.Redis, driver_id: str) -> dict[str, Any] | None:
    raw = await r.hget(LAST_KEY, driver_id)
    return json.loads(raw) if raw is not None else None


async def get_all(r: redis.Redis) -> dict[str, Any]:
    raw = await r.hgetall(LAST_KEY)
    return {driver_id: json.loads(payload) for driver_id, payload in raw.items()}


async def get_nearby(r: redis.Redis, lat: float, lon: float, radius_km: float) -> list[dict[str, Any]]:
    driver_ids = await r.geosearch(GEO_KEY, longitude=lon, latitude=lat, radius=radius_km, unit="km")
    if not driver_ids:
        return []
    payloads = await r.hmget(LAST_KEY, driver_ids)
    return [json.loads(p) for p in payloads if p is not None]


async def remove(r: redis.Redis, driver_id: str) -> None:
    """Tira o motorista do estado atual. O histórico no Postgres continua intacto."""
    await r.hdel(LAST_KEY, driver_id)
    await r.zrem(GEO_KEY, driver_id)
