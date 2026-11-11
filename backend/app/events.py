"""Fanout: entregar cada evento a todos os admins, em qualquer uma das 4 instâncias.

Cada instância só conhece os próprios sockets. Por isso, quem recebe uma
posição a publica no canal "positions" do Redis, e TODAS as instâncias
escutam esse canal e repassam o evento aos admins conectados nelas.

    motorista ─▶ api_2 ─PUBLISH─▶ Redis ─▶ api_1, api_2, api_3, api_4 ─▶ seus admins
"""
import json
from typing import Any

import redis.asyncio as redis

from app.ws import ConnectionManager

CHANNEL = "positions"


async def publish_position(r: redis.Redis, data: dict[str, Any]) -> None:
    await r.publish(CHANNEL, json.dumps(data))


async def publish_removed(r: redis.Redis, driver_id: str) -> None:
    # Mesmo canal das posições, para que a ordem "posição, depois remoção" se mantenha.
    await r.publish(CHANNEL, json.dumps({"event": "removed", "driver_id": driver_id}))


async def fanout(r: redis.Redis, manager: ConnectionManager) -> None:
    """Roda para sempre em cada instância (iniciada no lifespan de main.py)."""
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue  # confirmações de subscribe etc.
        data = json.loads(message["data"])
        if data.get("event") == "removed":
            await manager.broadcast({"type": "driver_removed", "driver_id": data["driver_id"]})
        else:
            await manager.broadcast({"type": "position", **data})
