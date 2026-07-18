"""ASGI application wiring: Socket.IO + FastAPI on one event loop.

The composition root for the transport. It assembles the registry, emitter,
``GameService``, and handlers behind a ``socketio.ASGIApp`` that serves the
websocket and delegates plain HTTP to a small FastAPI app. Everything it builds
is injectable, so tests can drive the pieces without a live server.
"""

from contextlib import asynccontextmanager

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.service.derpibooru import DerpibooruImageSource
from app.service.game_service import DEFAULT_TURN_SECONDS, GameService
from app.service.image_source import ImageSource
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import _RECONNECT_GRACE_SECONDS, SocketHandlers
from app.transport.registry import RoomRegistry


def create_app(
    *,
    image_source: ImageSource | None = None,
    turn_seconds: float = DEFAULT_TURN_SECONDS,
    reconnect_grace: float = _RECONNECT_GRACE_SECONDS,
    cors_origins: list[str] | str = "*",
):
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
    service = GameService(
        image_source or DerpibooruImageSource(),
        SocketIOEmitter(sio),
        turn_seconds=turn_seconds,
    )
    handlers = SocketHandlers(sio, RoomRegistry(), service, reconnect_grace=reconnect_grace)
    handlers.register()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service.shutdown()  # cancel every pending turn timer on shutdown
        handlers.shutdown()  # and any reconnect grace timers

    api = FastAPI(lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if isinstance(cors_origins, list) else [cors_origins],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    return socketio.ASGIApp(sio, other_asgi_app=api)
