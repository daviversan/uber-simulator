"""Registro dos sockets conectados NESTA instância e entrega de eventos aos admins."""
from dataclasses import dataclass, field
from typing import Literal

from fastapi import WebSocket

Role = Literal["admin", "driver", "sim"]


@dataclass
class BBox:
    """Área visível do mapa do admin, no formato do Leaflet: "west,south,east,north"."""

    west: float
    south: float
    east: float
    north: float

    @classmethod
    def parse(cls, raw: str) -> "BBox":
        west, south, east, north = (float(v) for v in raw.split(","))
        return cls(west, south, east, north)

    def contains(self, lat: float, lon: float) -> bool:
        if not (self.south <= lat <= self.north):
            return False
        if self.west <= self.east:
            return self.west <= lon <= self.east
        # west > east: a área cruza a linha de 180° (ex.: do Japão até o Havaí).
        return lon >= self.west or lon <= self.east


@dataclass
class Connection:
    """O que o servidor sabe sobre um socket depois do `join`."""

    role: Role
    driver_id: str | None = None
    bbox: BBox | None = None  # None = ainda não informou a área visível: recebe tudo
    # Enquanto o snapshot inicial não foi enviado, os eventos novos esperam em `pending`.
    syncing: bool = False
    pending: list[dict] = field(default_factory=list)


class ConnectionManager:
    def __init__(self) -> None:
        # Só entram aqui sockets que já fizeram `join`.
        self.active: dict[WebSocket, Connection] = {}

    def join(self, ws: WebSocket, role: Role, driver_id: str | None = None, *, syncing: bool = False) -> None:
        self.active[ws] = Connection(role=role, driver_id=driver_id, syncing=syncing)

    def get(self, ws: WebSocket) -> Connection | None:
        return self.active.get(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self.active.pop(ws, None)

    def set_bbox(self, ws: WebSocket, bbox: BBox) -> None:
        self.active[ws].bbox = bbox

    async def finish_sync(self, ws: WebSocket, snapshot: list[dict]) -> None:
        """Envia o snapshot e, logo depois, os eventos que chegaram enquanto ele era lido.

        Quem chama registra o socket com syncing=True ANTES de ler o snapshot.
        Assim nenhum evento se perde no meio: no pior caso um evento chega
        duplicado (já estava no snapshot), e reaplicá-lo no cliente é inofensivo.
        """
        conn = self.active[ws]
        await ws.send_json({"type": "snapshot", "drivers": snapshot})
        while conn.pending:
            await ws.send_json(conn.pending.pop(0))
        conn.syncing = False

    async def broadcast(self, message: dict) -> None:
        """Envia um evento a todos os admins desta instância. Motoristas não recebem a frota."""
        dead = []
        for ws, conn in list(self.active.items()):
            if conn.role != "admin":
                continue
            # Posições fora da área visível do admin não são enviadas. Remoções
            # (sem coordenadas) vão para todos.
            if "latitude" in message and conn.bbox and not conn.bbox.contains(message["latitude"], message["longitude"]):
                continue
            if conn.syncing:
                conn.pending.append(message)
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)  # o cliente caiu sem avisar
        for ws in dead:
            self.disconnect(ws)
