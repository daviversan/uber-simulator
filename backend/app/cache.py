"""Cache-aside no Redis: procura no cache; se não achar, calcula e guarda por `ttl` segundos.

Usado pelas consultas de analytics. Com N abas do admin pedindo os mesmos
números a cada 5 s, o Postgres roda a consulta uma vez por TTL, não uma vez
por aba. Como o cache fica no Redis, as 4 instâncias da API o compartilham.
"""
import json
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as redis


async def cached(r: redis.Redis, key: str, ttl: int, fn: Callable[[], Awaitable[Any]]) -> Any:
    hit = await r.get(key)
    if hit is not None:
        return json.loads(hit)

    value = await fn()
    await r.setex(key, ttl, json.dumps(value))
    return value
