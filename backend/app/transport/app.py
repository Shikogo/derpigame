"""ASGI application wiring: Socket.IO + FastAPI on one event loop.

The composition root for the transport, and the one place settings are read. It
loads a ``Settings``, turns it into the plain values each layer already
understood — a taxonomy, a room factory, a client config — and assembles the
registry, emitter, ``GameService``, and handlers behind a ``socketio.ASGIApp``
that serves the websocket and delegates plain HTTP to a small FastAPI app.
Everything it builds is injectable, so tests can drive the pieces without a live
server or a config file.
"""

import logging
from contextlib import asynccontextmanager
from functools import partial
from pathlib import Path

import httpx
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings, load_settings
from app.domain.rating import DERPIBOORU_AXES, FURBOORU_AXES
from app.domain.room import Room
from app.domain.tag_taxonomy import DERPIBOORU_TAXONOMY, FURBOORU_TAXONOMY
from app.logging_config import configure_logging
from app.service.game_service import GameService
from app.service.image_source import ImageSource
from app.service.philomena import PhilomenaClient
from app.service.sources import SourceBundle
from app.service.tag_resolver import NullTagResolver, TagResolver
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import SocketHandlers
from app.transport.registry import RoomRegistry

logger = logging.getLogger(__name__)


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
    configure_logging(settings.logging.level)
    logger.info("derpigame starting (log level %s)", settings.logging.level)
    cors_origins = list(settings.server.cors_origins)

    sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=cors_origins)
    # One shared httpx client so every lookup reuses the connection pool instead of
    # paying a fresh TLS handshake; each PhilomenaClient keeps its own back-off
    # state (per-IP, per-booru) but shares that pool.
    booru_client = httpx.AsyncClient()
    sources = _build_sources(settings, booru_client, image_source, tag_resolver)
    service = GameService(
        emitter=SocketIOEmitter(sio),
        sources=sources,
        default_source=settings.room_defaults.source,
        turn_seconds=settings.room_defaults.turn_seconds,
        max_query_lookups=settings.limits.max_query_lookups,
        game_options=settings.game.model_dump(),
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


# Which structural taxonomy each source's tags are classified by. The config's
# per-source curation (ignored tags) is applied over these at startup.
_BASE_TAXONOMIES = {
    "derpibooru": DERPIBOORU_TAXONOMY,
    "furbooru": FURBOORU_TAXONOMY,
}

# Each source's rating scales, for cap validation and the lobby UI. Furbooru's
# darkness axis differs from Derpibooru's (no semi-grimdark).
_BASE_AXES = {
    "derpibooru": DERPIBOORU_AXES,
    "furbooru": FURBOORU_AXES,
}


def _build_sources(
    settings: Settings,
    client: httpx.AsyncClient,
    image_source: ImageSource | None,
    tag_resolver: TagResolver | None,
) -> dict[str, SourceBundle]:
    """The source registry handed to the service, keyed by the name a room picks.

    Production builds a ``PhilomenaClient`` per configured source, each paired
    with its taxonomy (the source's constant with config curation applied over
    it). A test that injects an ``image_source`` gets a single-source registry
    under the default source name and a no-op resolver, so overrides never reach
    the live network.
    """
    default = settings.room_defaults.source
    if image_source is not None:
        curation = getattr(settings.taxonomy, default)
        return {
            default: SourceBundle(
                image_source=image_source,
                tag_resolver=tag_resolver or NullTagResolver(),
                taxonomy=curation.apply_to(_BASE_TAXONOMIES[default]),
            )
        }
    bundles: dict[str, SourceBundle] = {}
    for key, config in settings.sources.all().items():
        booru = PhilomenaClient(config=config, rating_axes=_BASE_AXES[key], client=client)
        curation = getattr(settings.taxonomy, key)
        bundles[key] = SourceBundle(
            image_source=booru,
            tag_resolver=booru,  # one client search + resolve, so they share back-off
            taxonomy=curation.apply_to(_BASE_TAXONOMIES[key]),
        )
    return bundles


def _new_room(settings: Settings, name: str) -> Room:
    """A room opened with the configured defaults, before anyone reconfigures it."""
    return Room(name, **settings.room_defaults.model_dump())
