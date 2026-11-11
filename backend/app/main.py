"""Ponto de entrada da API (uvicorn app.main:app).

HTTP serve só as páginas, os arquivos estáticos e o /health. Todo o resto
(telemetria, consultas, comandos) passa pelo WebSocket /ws: ver ws_handler.py.
"""
import asyncio
import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import ws_handler
from app.events import fanout
from app.settings import settings
from app.ws import ConnectionManager

INSTANCE = os.getenv("HOSTNAME", "local")  # no Docker, HOSTNAME = id do container


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda uma vez ao subir: abre o Redis e inicia a task que repassa os
    # eventos do Redis aos sockets desta instância (fanout).
    app.state.redis = redis.from_url(settings.redis_url, decode_responses=True)
    app.state.manager = ConnectionManager()
    task = asyncio.create_task(fanout(app.state.redis, app.state.manager))
    yield
    # Roda ao desligar.
    task.cancel()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("app/static/index.html")


@app.get("/admin", include_in_schema=False)
async def admin_app():
    return FileResponse("app/static/admin/index.html")


@app.get("/driver", include_in_schema=False)
async def driver_app():
    return FileResponse("app/static/driver/index.html")


@app.get("/health")
async def health():
    # Usado pelo healthcheck do Docker. `instance` mostra qual réplica respondeu.
    return {"status": "ok", "instance": INSTANCE}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_handler.serve(ws, app.state.manager, app.state.redis, INSTANCE)
