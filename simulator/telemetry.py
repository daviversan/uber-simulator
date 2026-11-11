"""Conexão WebSocket do simulador com a API.

Um socket para o processo inteiro, não um por bot: entra com role "sim" e
manda `sim_position` com o driver_id de cada bot.
"""
import asyncio
import json
import logging
import random

import websockets

log = logging.getLogger("simulator")

BACKOFF_MIN_S = 1.0
BACKOFF_MAX_S = 30.0


class TelemetryLink:
    def __init__(self, url: str) -> None:
        self.url = url
        self._ws = None  # None = desconectado

    async def run(self) -> None:
        """Mantém a conexão de pé para sempre.

        Se cair, tenta de novo com backoff exponencial (1, 2, 4... até 30 s) e
        jitter (um fator aleatório). Sem o jitter, vários clientes que caíram
        juntos voltariam todos no mesmo instante e derrubariam a API de novo.
        """
        backoff = BACKOFF_MIN_S
        while True:
            try:
                async with websockets.connect(self.url, open_timeout=5) as ws:
                    await self._join(ws)
                    self._ws = ws
                    backoff = BACKOFF_MIN_S
                    log.info("conectado em %s", self.url)
                    async for raw in ws:  # só esperamos mensagens de erro
                        msg = json.loads(raw)
                        if msg.get("type") == "error":
                            log.warning("API recusou: %s", msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("API fora do ar (%s); nova tentativa em ~%.0fs", exc, backoff)
            finally:
                self._ws = None
            await asyncio.sleep(backoff * random.uniform(0.5, 1.0))
            backoff = min(backoff * 2, BACKOFF_MAX_S)

    @staticmethod
    async def _join(ws) -> None:
        handshake = json.loads(await asyncio.wait_for(ws.recv(), 5))
        if handshake.get("type") != "handshake":
            raise RuntimeError(f"esperava handshake, veio {handshake!r}")
        await ws.send(json.dumps({"type": "join", "role": "sim"}))
        joined = json.loads(await asyncio.wait_for(ws.recv(), 5))
        if joined.get("type") != "joined":
            raise RuntimeError(f"join recusado: {joined!r}")

    async def send_position(self, driver_id: str, lat: float, lon: float) -> None:
        # Desconectado, a posição é DESCARTADA, não enfileirada: uma posição velha
        # não serve para nada, e uma fila acumulada viraria uma rajada na volta.
        if self._ws is None:
            return
        try:
            await self._ws.send(json.dumps({"type": "sim_position", "driver_id": driver_id, "lat": lat, "lon": lon}))
        except websockets.ConnectionClosed:
            pass
