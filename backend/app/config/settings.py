"""Centralized deployment settings, loaded from ``config.toml`` and the environment.

Config is *injected*, never imported by the code it configures: the composition
root (``app.transport.app.create_app``) loads a ``Settings`` and hands each layer
plain values it already understood. That's why ruff bans ``app.config`` from the
domain — a ``Game`` takes an elimination threshold, it doesn't look one up.

Two sources, by intent:

- ``config.toml`` (checked in) holds curation and tuning — the ignored-tag list,
  room defaults, game rules. Things a human edits and wants reviewed in a diff.
- The environment holds secrets and per-deployment values (API key, CORS
  origins). Any field can be overridden with ``DERPIGAME_<SECTION>__<FIELD>``,
  e.g. ``DERPIGAME_DERPIBOORU__API_KEY`` or ``DERPIGAME_SERVER__CORS_ORIGINS``.

Precedence, highest first: constructor arguments, environment, ``.env``,
``config.toml``, then the defaults below. Every section forbids unknown keys, so
a typo in ``config.toml`` fails at startup instead of silently doing nothing.
"""

from dataclasses import replace
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from app.domain.tag_taxonomy import TagTaxonomy

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_FILE = BACKEND_ROOT / "config.toml"


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerSettings(_Section):
    """HTTP/websocket surface."""

    # "*" is fine for local play but must be narrowed to the real frontend origin
    # before deployment — it governs the websocket handshake as well as CORS.
    cors_origins: list[str] = ["*"]


class TaxonomySettings(_Section):
    """Tag curation: what the game refuses to treat as a guessable tag.

    These *replace* the taxonomy's own lists rather than adding to them, so the
    file is the whole truth and you can remove an entry by deleting the line.
    Namespaces and rating tags aren't here: those are structural facts about a
    booru, not preferences, and live with the taxonomy in the domain.
    """

    ignored_tags: frozenset[str] = frozenset()
    ignored_prefixes: tuple[str, ...] = ()

    def apply_to(self, base: TagTaxonomy) -> TagTaxonomy:
        """The taxonomy ``base`` with this file's curation swapped in."""
        return replace(
            base,
            ignored_tags=self.ignored_tags,
            ignored_prefixes=self.ignored_prefixes,
        )


class RoomDefaults(_Section):
    """What a freshly created room starts with, before anyone configures it."""

    nsfw: bool = False
    query: list[str] = []
    turn_seconds: float = Field(default=60.0, gt=0)
    # Search bounds. TOML has no null, so these can't be switched *off* from the
    # file — a room turns them off at runtime instead, via configure_room.
    min_tag_count: int = Field(default=15, ge=0)
    min_score: int = Field(default=10, ge=0)
    # Axis key -> level name, both from the image source's own vocabulary. An
    # unknown axis or level caps nothing (see RatingAxis.excluded), so a stale
    # entry here degrades to "no cap" rather than a wrong one.
    rating_caps: dict[str, str] = {}


class GameRules(_Section):
    """Domain knobs handed to each ``Game``."""

    elimination_threshold: int = Field(default=3, ge=1)
    near_miss_threshold: float = Field(default=0.85, gt=0.0, le=1.0)


class DerpibooruSettings(_Section):
    """Provider client: credentials, filters, and the mandatory back-off timings.

    The back-off durations implement Derpibooru's API rules and are configurable
    only so they can be shortened in tests — raising them is safe, lowering them
    in production is not.
    """

    api_key: str | None = None
    timeout: float = Field(default=10.0, gt=0)
    user_agent: str = "derpigame/0.1 (https://github.com/Shikogo/derpigame)"
    # Sent explicitly so we never inherit the anonymous site default (a legacy
    # filter that surfaces AI-generated content). Sfw rooms get the system
    # "Default" filter, a hard server-side gate on everything above suggestive.
    # Nsfw rooms get a public custom filter that blocks AI art but permits every
    # rating tag, so the room's own caps — not the filter — decide how far a game
    # goes.
    #
    # A filter Derpibooru won't serve is *silently* replaced with the anonymous
    # default rather than refused, so a private or invalid id degrades quietly.
    # Verify a new id by checking that a search returns different totals.
    default_filter_id: str = "100073"
    nsfw_filter_id: str = "232619"
    # Back-off durations (seconds) per Derpibooru's API rules.
    challenge_backoff: float = Field(default=5.0, gt=0)  # 501 anti-bot: silence >=5s
    block_backoff: float = Field(default=900.0, gt=0)  # 500 IP block: >=15min
    failure_backoff_base: float = Field(default=1.0, gt=0)  # other failures: exponential...
    failure_backoff_max: float = Field(default=60.0, gt=0)  # ...capped here

    @model_validator(mode="after")
    def _check_backoff_range(self):
        if self.failure_backoff_max < self.failure_backoff_base:
            raise ValueError("failure_backoff_max must be >= failure_backoff_base")
        return self


class LimitsSettings(_Section):
    """Bounds on what a client may ask for. Abuse control, not gameplay tuning."""

    max_query_terms: int = Field(default=24, ge=1)
    min_turn_seconds: float = Field(default=10.0, gt=0)
    max_turn_seconds: float = Field(default=300.0, gt=0)
    # Alias lookups spent resolving a room's query on its first round; also
    # bounds what an oversized query can cost the shared rate limit.
    max_query_lookups: int = Field(default=8, ge=0)
    # How long a drained room is kept so a reload or flaky connection can reclaim it.
    reconnect_grace_seconds: float = Field(default=30.0, ge=0)

    @model_validator(mode="after")
    def _check_turn_range(self):
        if self.max_turn_seconds < self.min_turn_seconds:
            raise ValueError("max_turn_seconds must be >= min_turn_seconds")
        return self


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DERPIGAME_",
        env_nested_delimiter="__",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        frozen=True,
        toml_file=DEFAULT_CONFIG_FILE,
    )

    server: ServerSettings = ServerSettings()
    taxonomy: TaxonomySettings = TaxonomySettings()
    room_defaults: RoomDefaults = RoomDefaults()
    game: GameRules = GameRules()
    derpibooru: DerpibooruSettings = DerpibooruSettings()
    limits: LimitsSettings = LimitsSettings()

    @model_validator(mode="after")
    def _check_default_turn_is_allowed(self):
        """A default a client couldn't choose is a trap — catch it at startup."""
        turn = self.room_defaults.turn_seconds
        if not (self.limits.min_turn_seconds <= turn <= self.limits.max_turn_seconds):
            raise ValueError(
                f"room_defaults.turn_seconds ({turn}) is outside the allowed range "
                f"{self.limits.min_turn_seconds}–{self.limits.max_turn_seconds}"
            )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Explicit arguments beat the environment, which beats the file. The TOML
        # source goes last so it fills in whatever nobody else supplied.
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            TomlConfigSettingsSource(settings_cls),
        )


def load_settings(config_file: Path | str | None = None, **overrides) -> Settings:
    """Build a ``Settings``, optionally from a specific ``config.toml``.

    A missing file is not an error — every field has a working default, so tests
    and a fresh checkout run without one. ``overrides`` take precedence over both
    the file and the environment, which is how tests pin a value.
    """
    if config_file is None:
        return Settings(**overrides)
    # The TOML path is read off model_config by the source, and pydantic-settings
    # only accepts an ``_env_file``-style override for env files — so pointing at
    # a different file means a subclass carrying a different config.
    config = SettingsConfigDict(**{**Settings.model_config, "toml_file": Path(config_file)})
    variant = type("FileSettings", (Settings,), {"model_config": config})
    return variant(**overrides)
