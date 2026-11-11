"""O endpoint WebSocket /ws: recebe cada mensagem, valida, autoriza e executa.

Ciclo de vida de um socket:

    conectado (guest) ── join ──▶ admin   pode mandar: subscribe, request
                                  driver  pode mandar: position, request
                                  sim     pode mandar: sim_position

Autorização em duas camadas:
  1. ALLOWED (aqui): que TIPOS de mensagem cada papel pode mandar.
  2. @op(roles=...) (rpc.py): que OPS cada papel pode chamar dentro de um `request`.

Um erro nunca fecha o socket: o cliente recebe uma mensagem de erro e continua conectado.
"""
import json
import logging
from typing import Any

import redis.asyncio as redis
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app import rpc, store
from app.db import async_session
from app.ingest import ingest_position
from app.schemas import (
    JoinMessage,
    PositionMessage,
    RequestMessage,
    SimPositionMessage,
    SubscribeMessage,
    TelemetryInput,
    client_message_adapter,
)
from app.settings import settings
from app.ws import BBox, ConnectionManager

logger = logging.getLogger(__name__)

ALLOWED = {
    "admin": (SubscribeMessage, RequestMessage),
    "driver": (PositionMessage, RequestMessage),
    "sim": (SimPositionMessage,),  # o simulador só publica; não lê dados nem assina a frota
}


async def serve(ws: WebSocket, manager: ConnectionManager, r: redis.Redis, instance: str) -> None:
    await ws.accept()
    # Primeira mensagem: qual instância atendeu (aparece na barra de status das telas).
    await ws.send_json({"type": "handshake", "instance": instance})
    try:
        while True:
            # O servidor processa as mensagens de um socket uma por vez, em ordem.
            frame = await ws.receive()
            if frame["type"] == "websocket.disconnect":
                break
            if frame.get("text") is None:
                await _error(ws, "invalid_message", "apenas frames de texto (JSON)")
                continue
            await _handle(ws, manager, r, frame["text"])
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


async def _handle(ws: WebSocket, manager: ConnectionManager, r: redis.Redis, text: str) -> None:
    try:
        msg = client_message_adapter.validate_json(text)
    except ValidationError as exc:
        await _invalid(ws, text, rpc.first_error(exc))
        return

    conn = manager.get(ws)

    if conn is None:  # guest: só pode entrar ou chamar ops públicas
        if isinstance(msg, JoinMessage):
            await _join(ws, manager, r, msg)
        elif isinstance(msg, RequestMessage):
            await _request(ws, r, "guest", msg)
        else:
            await _reply_error(ws, msg, "join_required", "envie `join` antes de qualquer outra mensagem")
        return

    if isinstance(msg, JoinMessage):
        await _error(ws, "already_joined", f"este socket já entrou como {conn.role}")
    elif not isinstance(msg, ALLOWED[conn.role]):
        await _reply_error(ws, msg, "not_allowed", f"`{msg.type}` não é permitido para role={conn.role}")
    elif isinstance(msg, SubscribeMessage):
        try:
            manager.set_bbox(ws, BBox.parse(msg.bbox))
        except ValueError:
            await _error(ws, "invalid_message", "bbox deve ser 'west,south,east,north' numérico")
    elif isinstance(msg, RequestMessage):
        await _request(ws, r, conn.role, msg)
    elif isinstance(msg, PositionMessage):
        # O driver_id vem do join, nunca da mensagem: um motorista não publica como outro.
        await _ingest(ws, r, _telemetry(conn.driver_id, msg, "app"))
    elif isinstance(msg, SimPositionMessage):
        await _ingest(ws, r, _telemetry(msg.driver_id, msg, "sim"))


def _telemetry(driver_id: str, msg: PositionMessage | SimPositionMessage, source: str) -> TelemetryInput:
    fields: dict[str, Any] = {"driver_id": driver_id, "latitude": msg.lat, "longitude": msg.lon, "source": source}
    if msg.ts is not None:
        fields["timestamp"] = msg.ts
    return TelemetryInput(**fields)


async def _join(ws: WebSocket, manager: ConnectionManager, r: redis.Redis, msg: JoinMessage) -> None:
    if msg.role == "admin":
        # Registra ANTES de ler o snapshot, para não perder eventos (ver finish_sync).
        manager.join(ws, "admin", syncing=True)
        snapshot = list((await store.get_all(r)).values())
        await manager.finish_sync(ws, snapshot)

    elif msg.role == "sim":
        manager.join(ws, "sim")
        await ws.send_json({"type": "joined", "role": "sim"})

    else:  # driver: o join já traz a posição inicial ("entrar no mapa")
        data = TelemetryInput(driver_id=msg.driver_id, latitude=msg.lat, longitude=msg.lon, source="app")
        if not await _ingest(ws, r, data):
            return  # falhou: o socket continua guest e o cliente pode tentar de novo
        manager.join(ws, "driver", msg.driver_id)
        # O servidor manda os limites do filtro de movimento: uma fonte só de verdade.
        await ws.send_json({
            "type": "joined",
            "role": "driver",
            "driver_id": msg.driver_id,
            "config": {"min_move_m": settings.min_move_m, "heartbeat_ms": int(settings.heartbeat_s * 1000)},
        })


async def _ingest(ws: WebSocket, r: redis.Redis, data: TelemetryInput) -> bool:
    try:
        # Sessão por mensagem, não por socket (o pool do banco é pequeno, ver db.py).
        async with async_session() as session:
            await ingest_position(r, session, data)
        return True
    except Exception:
        logger.exception("falha ao gravar posição de %s", data.driver_id)
        await _error(ws, "internal", "falha ao gravar a posição")
        return False


async def _request(ws: WebSocket, r: redis.Redis, role: rpc.Caller, msg: RequestMessage) -> None:
    try:
        data = await rpc.call(r, msg.op, msg.payload, role)
        await ws.send_json({"type": "response", "id": msg.id, "ok": True, "data": data})
    except rpc.RpcError as exc:
        await ws.send_json(_failure(msg.id, exc.code, exc.message))
    except Exception:
        logger.exception("op %s falhou", msg.op)
        await ws.send_json(_failure(msg.id, "internal", "erro interno"))


# --- Respostas de erro ----------------------------------------------------------

def _failure(request_id: str, code: str, message: str) -> dict[str, Any]:
    return {"type": "response", "id": request_id, "ok": False, "error": {"code": code, "message": message}}


async def _error(ws: WebSocket, code: str, message: str) -> None:
    await ws.send_json({"type": "error", "code": code, "message": message})


async def _reply_error(ws: WebSocket, msg: Any, code: str, message: str) -> None:
    # Se era um `request`, o erro vai como `response` com o mesmo id; senão o
    # cliente ficaria esperando a resposta até o timeout.
    if isinstance(msg, RequestMessage):
        await ws.send_json(_failure(msg.id, code, message))
    else:
        await _error(ws, code, message)


async def _invalid(ws: WebSocket, text: str, message: str) -> None:
    # Mesmo para mensagem inválida: se dá para ver que era um request com id, responde ao id.
    try:
        raw = json.loads(text)
    except ValueError:
        raw = None
    if isinstance(raw, dict) and raw.get("type") == "request" and isinstance(raw.get("id"), str):
        await ws.send_json(_failure(raw["id"], "invalid_message", message))
    else:
        await _error(ws, "invalid_message", message)
