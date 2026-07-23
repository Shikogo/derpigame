"""Settings loading: source precedence, validation, and taxonomy curation.

These drive ``load_settings`` against temporary TOML files rather than the
shipped ``config.toml``, except where a test deliberately pins the real file.
"""

from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.config import DEFAULT_CONFIG_FILE, Settings, TaxonomySettings, load_settings
from app.domain.tag_taxonomy import DERPIBOORU_TAXONOMY


def write_config(tmp_path, body: str):
    path = tmp_path / "config.toml"
    path.write_text(body)
    return path


# --- sources & precedence -----------------------------------------------------


def test_a_missing_file_falls_back_to_defaults(tmp_path):
    # A fresh checkout or a test run shouldn't need a config file to boot.
    settings = load_settings(tmp_path / "absent.toml")

    assert settings.game.elimination_threshold == 3
    assert settings.limits.max_query_terms == 24
    assert settings.taxonomy.ignored_tags == ()


def test_file_values_win_over_defaults(tmp_path):
    path = write_config(tmp_path, "[game]\nelimination_threshold = 5\n")

    assert load_settings(path).game.elimination_threshold == 5


def test_environment_wins_over_the_file(tmp_path, monkeypatch):
    path = write_config(tmp_path, "[room_defaults]\nturn_seconds = 45.0\n")
    monkeypatch.setenv("DERPIGAME_ROOM_DEFAULTS__TURN_SECONDS", "90")

    assert load_settings(path).room_defaults.turn_seconds == 90.0


def test_explicit_overrides_win_over_the_environment(tmp_path, monkeypatch):
    path = write_config(tmp_path, "[game]\nelimination_threshold = 5\n")
    monkeypatch.setenv("DERPIGAME_GAME__ELIMINATION_THRESHOLD", "7")

    settings = load_settings(path, game={"elimination_threshold": 9})

    assert settings.game.elimination_threshold == 9


def test_a_secret_can_come_from_the_environment_alone(monkeypatch):
    # The API key is deliberately absent from config.toml — it belongs in the env.
    monkeypatch.setenv("DERPIGAME_DERPIBOORU__API_KEY", "s3cret")

    assert load_settings().derpibooru.api_key == "s3cret"


def test_log_level_defaults_to_info_and_normalizes_case(tmp_path, monkeypatch):
    assert load_settings(tmp_path / "absent.toml").logging.level == "INFO"  # default

    monkeypatch.setenv("DERPIGAME_LOGGING__LEVEL", "debug")
    assert load_settings().logging.level == "DEBUG"  # accepted case-insensitively


def test_a_custom_file_still_returns_a_settings(tmp_path):
    assert isinstance(load_settings(write_config(tmp_path, "")), Settings)


# --- rejecting bad config -----------------------------------------------------


def test_an_unknown_key_is_a_startup_error(tmp_path):
    # A silently-ignored typo would look exactly like a setting that doesn't work.
    path = write_config(tmp_path, '[taxonomy]\nignoredtags = ["oops"]\n')

    with pytest.raises(ValidationError, match="ignoredtags"):
        load_settings(path)


def test_an_unknown_section_is_a_startup_error(tmp_path):
    with pytest.raises(ValidationError, match="taxonmy"):
        load_settings(write_config(tmp_path, "[taxonmy]\n"))


def test_an_inverted_turn_range_is_rejected():
    with pytest.raises(ValidationError, match="max_turn_seconds"):
        load_settings(limits={"min_turn_seconds": 100.0, "max_turn_seconds": 10.0})


def test_a_default_turn_length_outside_the_allowed_range_is_rejected():
    # A default no client could choose would be silently clamped away.
    with pytest.raises(ValidationError, match="outside the allowed range"):
        load_settings(room_defaults={"turn_seconds": 5.0})


def test_an_out_of_range_near_miss_threshold_is_rejected():
    with pytest.raises(ValidationError, match="near_miss_threshold"):
        load_settings(game={"near_miss_threshold": 1.5})


def test_an_inverted_failure_backoff_range_is_rejected():
    with pytest.raises(ValidationError, match="failure_backoff_max"):
        load_settings(derpibooru={"failure_backoff_base": 30.0, "failure_backoff_max": 5.0})


def test_an_unknown_log_level_is_rejected():
    with pytest.raises(ValidationError, match="unknown log level"):
        load_settings(logging={"level": "chatty"})


# --- taxonomy curation --------------------------------------------------------


def test_configured_curation_replaces_rather_than_extends():
    # The file is the whole truth: deleting a line there must make that tag
    # guessable again, which a union would quietly prevent.
    base = replace(DERPIBOORU_TAXONOMY, ignored_tags=("from-the-constant",))

    curated = TaxonomySettings(ignored_tags=("from-config",)).apply_to(base)

    assert curated.ignored_tags == ("from-config",)
    assert not curated.is_droppable("from-the-constant")
    assert curated.is_droppable("from-config")


def test_curation_leaves_the_structural_parts_of_a_taxonomy_alone():
    curated = TaxonomySettings(ignored_tags=("x",)).apply_to(DERPIBOORU_TAXONOMY)

    assert curated.namespaces == DERPIBOORU_TAXONOMY.namespaces
    assert curated.rating_tags == DERPIBOORU_TAXONOMY.rating_tags
    assert curated.goal_bucket == DERPIBOORU_TAXONOMY.goal_bucket


def test_a_glob_pattern_drops_a_whole_namespace(tmp_path):
    path = write_config(tmp_path, '[taxonomy]\nignored_tags = ["spoiler:*"]\n')

    curated = load_settings(path).taxonomy.apply_to(DERPIBOORU_TAXONOMY)

    assert curated.is_droppable("spoiler:the-ending")
    assert not curated.is_droppable("solo")


# --- the shipped file ---------------------------------------------------------


def test_the_shipped_config_file_is_valid_and_carries_the_curation():
    # Pins the real config.toml: it's the source of truth for the ignored-tag
    # list now, so a broken or emptied one should fail here rather than in play.
    settings = load_settings(DEFAULT_CONFIG_FILE)
    curated = settings.taxonomy.apply_to(DERPIBOORU_TAXONOMY)

    assert curated.is_droppable("source needed")  # housekeeping, not on the image
    assert curated.is_droppable("battle in the comments")  # a glob-matched family
    assert curated.is_droppable("spoiler:the-ending")  # a dropped namespace
    assert curated.is_droppable("commissioner:someone")  # a credit, not guessable
    assert curated.is_droppable("editor:someone")
    assert not curated.is_droppable("solo")  # a real, guessable tag
    assert settings.room_defaults.min_tag_count > 0
