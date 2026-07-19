"""ASGI application wiring: Socket.IO + FastAPI on one event loop.

The composition root for the transport. It assembles the registry, emitter,
``GameService``, and handlers behind a ``socketio.ASGIApp`` that serves the
websocket and delegates plain HTTP to a small FastAPI app. Everything it builds
is injectable, so tests can drive the pieces without a live server.
"""

from contextlib import asynccontextmanager
from pathlib import Path

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.service.derpibooru import DerpibooruClient
from app.service.game_service import DEFAULT_TURN_SECONDS, GameService
from app.service.image_source import ImageSource
from app.service.tag_resolver import NullTagResolver, TagResolver
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import _RECONNECT_GRACE_SECONDS, SocketHandlers
from app.transport.registry import RoomRegistry


def create_app(
    *,
    image_source: ImageSource | None = None,
    tag_resolver: TagResolver | None = None,
    turn_seconds: float = DEFAULT_TURN_SECONDS,
    reconnect_grace: float = _RECONNECT_GRACE_SECONDS,
    cors_origins: list[str] | str = "*",
    static_dir: Path | str | None = None,
):
    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
    # One client for both image search and alias lookups so they share the
    # per-IP back-off. A test that injects its own image_source gets a no-op
    # resolver instead, so overrides never reach the live network.
    booru = DerpibooruClient()
    service = GameService(
        image_source or booru,
        SocketIOEmitter(sio),
        tag_resolver=tag_resolver or (NullTagResolver() if image_source else booru),
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

    # Optionally serve a built frontend from the same origin, so one URL (and one
    # tunnel) fronts both the SPA and the websocket. Mounted last so /health and
    # the Socket.IO paths keep priority; html=True serves index.html at /.
    if static_dir is not None:
        api.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")

    return socketio.ASGIApp(sio, other_asgi_app=api)
