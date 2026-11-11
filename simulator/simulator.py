"""Simulador de motoristas: entrypoint, estado e comandos.

- Cada bot é uma task asyncio (driver.py) que envia posições pela conexão
  WebSocket compartilhada (telemetry.py).
- O painel Simulação do admin manda comandos que a API repassa pelo canal
  Redis "sim:cmd". Este processo escuta o canal, aplica o comando e grava o
  estado em "sim:state", que o painel lê para mostrar o efeito.

WS_URL e REDIS_URL usam nomes de serviço do docker-compose ("nginx", "redis"):
o DNS interno do Compose resolve esses nomes para o container certo.
"""
import asyncio
import itertools
import json
import logging
import os
from dataclasses import dataclass, field
from random import randint

import redis.asyncio as redis

from cities import CITIES
from driver import ROUTES, Driver, run_driver
from telemetry import TelemetryLink

WS_URL = os.getenv("WS_URL", "ws://nginx/ws")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
NUM_DRIVERS = int(os.getenv("NUM_DRIVERS", "5"))
TICK_SECONDS = float(os.getenv("TICK_SECONDS", "1"))

CHANNEL = "sim:cmd"
STATE_KEY = "sim:state"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("simulator")


@dataclass
class Simulation:
    """Estado da simulação: os comandos o alteram e os bots o leem a cada tick."""

    link: TelemetryLink
    tick_seconds: float = TICK_SECONDS
    rate_multiplier: float = 1.0
    running_event: asyncio.Event = field(default_factory=asyncio.Event)
    tasks: dict[str, asyncio.Task] = field(default_factory=dict)  # driver_id -> task do bot
    ids: itertools.count = field(default_factory=itertools.count)

    def __post_init__(self) -> None:
        self.running_event.set()  # começa rodando

    def _launch(self, city_id: str, offset: int) -> str:
        driver_id = f"driver_{next(self.ids):03d}"
        self.tasks[driver_id] = asyncio.create_task(run_driver(self.link, Driver(driver_id, city_id, offset), self))
        return driver_id

    def seed(self, count: int) -> None:
        """Distribui `count` bots pelas cidades, em rodízio, espaçados na rota."""
        city_ids = list(CITIES)
        for i in range(count):
            self._launch(city_ids[i % len(city_ids)], offset=i * 7)

    def spawn(self, city_id: str, count: int) -> None:
        for _ in range(count):
            self._launch(city_id, offset=randint(0, len(ROUTES[city_id]) - 1))

    def despawn(self, driver_id: str) -> None:
        task = self.tasks.pop(driver_id, None)
        if task:
            task.cancel()  # a task termina no próximo `await` dela

    def reset(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()
        self.rate_multiplier = 1.0
        self.running_event.set()
        self.seed(NUM_DRIVERS)

    def apply(self, cmd: dict) -> None:
        match cmd.get("type"):
            case "start":
                self.running_event.set()
            case "pause":
                self.running_event.clear()
            case "reset":
                self.reset()
            case "spawn":
                self.spawn(cmd["city"], int(cmd["count"]))
            case "despawn":
                self.despawn(cmd["driver_id"])
            case "set_rate":
                self.rate_multiplier = float(cmd["multiplier"])
            case other:
                log.warning("comando desconhecido: %s", other)

    def snapshot(self) -> dict[str, str]:
        # Hash do Redis só guarda strings.
        return {
            "status": "running" if self.running_event.is_set() else "paused",
            "driver_count": str(len(self.tasks)),
            "rate_multiplier": str(self.rate_multiplier),
        }


async def listen_commands(r: redis.Redis, sim: Simulation) -> None:
    pubsub = r.pubsub()
    await pubsub.subscribe(CHANNEL)
    await r.hset(STATE_KEY, mapping=sim.snapshot())
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            sim.apply(json.loads(message["data"]))
        except Exception:
            # Um comando ruim não pode derrubar o simulador.
            log.exception("comando inválido: %r", message["data"])
            continue
        await r.hset(STATE_KEY, mapping=sim.snapshot())


async def main() -> None:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    link = TelemetryLink(WS_URL)
    link_task = asyncio.create_task(link.run())
    sim = Simulation(link)
    sim.seed(NUM_DRIVERS)
    log.info("%d bots, tick=%.1fs -> %s", NUM_DRIVERS, TICK_SECONDS, WS_URL)
    try:
        await listen_commands(r, sim)  # roda para sempre
    finally:
        link_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
