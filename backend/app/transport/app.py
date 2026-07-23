"""ASGI application wiring: Socket.IO + FastAPI on one event loop.

The composition root for the transport, and the one place settings are read. It
loads a ``Settings``, turns it into the plain values each layer already
understood — a taxonomy, a room factory, a client config — and assembles the
registry, emitter, ``GameService``, and handlers behind a ``socketio.ASGIApp``
that serves the websocket and delegates plain HTTP to a small FastAPI app.
Everything it builds is injectable, so tests can drive the pieces without a live
server or a config file.
"""

from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

import httpx
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings
from app.domain.room import Room
from app.domain.tag_taxonomy import DERPIBOORU_TAXONOMY
from app.service.derpibooru import DerpibooruClient
from app.service.game_service import GameService
from app.service.image_source import ImageSource
from app.service.tag_resolver import NullTagResolver, TagResolver
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import SocketHandlers
from app.transport.registry import RoomRegistry


def create_app(
    *,
    settings: Settings | None = None,
    image_source: ImageSource | None = None,
    tag_resolver: TagResolver | None = None,
    static_dir: Path | str | None = None,
):
    """Build the ASGI app. ``settings`` defaults to ``config.toml`` + environment.

    The remaining arguments are test/dev seams: injecting an ``image_source``
    keeps the real network out of reach, and ``static_dir`` serves a built
    frontend from the same origin.
    """
    settings = settings or load_settings()
    cors_origins = list(settings.server.cors_origins)

    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
    # One DerpibooruClient for both image search and alias lookups so they share
    # the per-IP back-off, over one shared httpx client so every lookup reuses the
    # connection pool instead of paying a fresh TLS handshake. A test that injects
    # its own image_source gets a no-op resolver instead, so overrides never reach
    # the live network.
    booru_client = httpx.AsyncClient(timeout=settings.derpibooru.timeout)
    booru = DerpibooruClient(config=settings.derpibooru, client=booru_client)
    service = GameService(
        image_source or booru,
        SocketIOEmitter(sio),
        tag_resolver=tag_resolver or (NullTagResolver() if image_source else booru),
        turn_seconds=settings.room_defaults.turn_seconds,
        max_query_lookups=settings.limits.max_query_lookups,
        game_options={
            # Curation from config.toml replaces the taxonomy's own lists; the
            # constant keeps only what's structural about the source.
            "taxonomy": settings.taxonomy.apply_to(DERPIBOORU_TAXONOMY),
            **settings.game.model_dump(),
        },
    )
    registry = RoomRegistry(partial(_new_room, settings))
    handlers = SocketHandlers(sio, registry, service, limits=settings.limits)
    handlers.register()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        service.shutdown()  # cancel every pending turn timer on shutdown
        handlers.shutdown()  # and any reconnect grace timers
        await booru_client.aclose()  # release the shared HTTP connection pool

    api = FastAPI(lifespan=lifespan)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
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


def _new_room(settings: Settings, name: str) -> Room:
    """A room opened with the configured defaults, before anyone reconfigures it."""
    return Room(name, **settings.room_defaults.model_dump())
