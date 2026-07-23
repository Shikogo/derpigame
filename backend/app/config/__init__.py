"""Deployment settings. See ``settings.py`` for how the sources are layered."""

from app.config.settings import (
    DEFAULT_CONFIG_FILE,
    GameRules,
    LimitsSettings,
    LoggingSettings,
    PhilomenaSourceSettings,
    RoomDefaults,
    ServerSettings,
    Settings,
    SourceCuration,
    SourcesSettings,
    TaxonomySettings,
    load_settings,
)

__all__ = [
    "DEFAULT_CONFIG_FILE",
    "GameRules",
    "LimitsSettings",
    "LoggingSettings",
    "PhilomenaSourceSettings",
    "RoomDefaults",
    "ServerSettings",
    "Settings",
    "SourceCuration",
    "SourcesSettings",
    "TaxonomySettings",
    "load_settings",
]
