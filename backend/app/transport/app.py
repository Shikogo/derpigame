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

from app.service.game_service import DEFAULT_TURN_SECONDS, GameService
from app.service.image_source import Image, ImageSource, StaticImageSource
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import SocketHandlers
from app.transport.registry import RoomRegistry

# A single offline sample so the app runs before a real provider exists; the
# Derpibooru/e621 ImageSource drops in here later (Phase 2/3).
_SAMPLE_IMAGE = Image(
    id="sample",
    tags=["solo", "pony", "twilight sparkle", "artist:unknown"],
    thumb_url="https://derpicdn.net/img/view/sample.png",
    full_url="https://derpicdn.net/img/view/sample.png",
)


def create_app(
    *,
    image_source: ImageSource | None = None,
    turn_seconds: float = DEFAULT_TURN_SECONDS,
    cors_origins: list[str] | str = "*",
):
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
    service = GameService(
        image_source or StaticImageSource([_SAMPLE_IMAGE]),
        SocketIOEmitter(sio),
        turn_seconds=turn_seconds,
    )
    SocketHandlers(sio, RoomRegistry(), service).register()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service.shutdown()  # cancel every pending turn timer on shutdown

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
