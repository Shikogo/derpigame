"""Orchestration: fetch → mutate domain → emit → time, routed through one path."""

import asyncio
import json
import logging

import pytest

from app.config import LimitsSettings
from app.domain.rating import DERPIBOORU_AXES
from app.domain.room import Room
from app.domain.tag_taxonomy import DERPIBOORU_TAXONOMY, FURBOORU_TAXONOMY
from app.domain.user import User
from app.service.emitter import EventEmitter
from app.service.errors import GameActionError, NotYourTurn
from app.service.game_service import GameService
from app.service.image_source import (
    Image,
    ImageSource,
    ImageSourceError,
    SearchOptions,
    StaticImageSource,
)
from app.service.sources import SourceBundle
from app.service.tag_resolver import NullTagResolver, TagResolver


class RecordingEmitter(EventEmitter):
    def __init__(self):
        self.batches: list[tuple[str, list[dict]]] = []

    async def emit(self, room_name: str, payloads: list[dict]) -> None:
        self.batches.append((room_name, payloads))

    @property
    def payloads(self) -> list[dict]:
        return [payload for _, batch in self.batches for payload in batch]

    def types(self) -> list[str]:
        return [payload["type"] for payload in self.payloads]


class BrokenImageSource(ImageSource):
    async def random_image(self, query, *, options):
        raise ImageSourceError("provider is down")


class GatedImageSource(ImageSource):
    """Blocks each fetch until released, so overlapping starts can be forced."""

    def __init__(self, image: Image):
        self._image = image
        self.calls = 0
        self.gate = asyncio.Event()

    async def random_image(self, query, *, options):
        self.calls += 1
        await self.gate.wait()
        return self._image


class RecordingImageSource(ImageSource):
    """Captures the options it was handed, so the room→provider chain is testable."""

    def __init__(self, image: Image):
        self._image = image
        self.options: SearchOptions | None = None

    async def random_image(self, query, *, options):
        self.options = options
        return self._image


class RecordingResolver(TagResolver):
    """Resolves from a fixed alias map and records every tag it's asked about."""

    def __init__(self, aliases: dict[str, str] | None = None):
        self._aliases = aliases or {}
        self.calls: list[str] = []

    async def canonicalize(self, tag: str) -> str:
        self.calls.append(tag)
        return self._aliases.get(tag.lower(), tag)


def make_room(*names: str, query: list[str] | None = None) -> Room:
    room = Room("lobby", query=query or [])
    for name in names:
        user = User(uuid=name, name=name)
        user.ready = True
        room.add_user(user)
    return room


def ready_up(room: Room) -> None:
    """Re-ready everyone — a round end clears readiness, so a new round needs it."""
    for user in room.users.values():
        user.ready = True


def make_service(tags: list[str], emitter: EventEmitter, **kwargs) -> GameService:
    image = Image(id="1", tags=tags, thumb_url="t", full_url="f")
    return GameService.single_source(StaticImageSource([image]), emitter, **kwargs)


def rich_image() -> Image:
    """An image carrying every attribution field, incl. an artist tag."""
    return Image(
        id="7",
        tags=["solo", "artist:foo"],
        thumb_url="thumb",
        full_url="full",
        page_url="https://derpibooru.org/images/7",
        source_url="https://example.com/original",
    )


# --- starting a game ---------------------------------------------------------


async def test_start_game_announces_opening_and_arms_a_timer():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)

    assert emitter.types() == ["image_started", "game_started", "turn_started"]
    assert room.game is not None
    assert "lobby" in service._timers  # armed for the first turn
    service.shutdown()


async def test_game_started_carries_the_service_turn_duration():
    emitter = RecordingEmitter()
    service = make_service(["solo"], emitter, turn_seconds=45.0)
    room = make_room("alice")

    await service.start_game(room, first_index=0)

    started = next(p for p in emitter.payloads if p["type"] == "game_started")
    assert started["turn_seconds"] == 45.0  # the client's clock matches the server
    service.shutdown()


async def test_room_turn_seconds_override_beats_the_deployment_default():
    emitter = RecordingEmitter()
    service = make_service(["solo"], emitter, turn_seconds=30.0)
    room = make_room("alice")
    room.turn_seconds = 90.0

    await service.start_game(room, first_index=0)

    started = next(p for p in emitter.payloads if p["type"] == "game_started")
    assert started["turn_seconds"] == 90.0
    service.shutdown()


async def test_start_game_is_ignored_when_one_is_already_running():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)
    before = len(emitter.batches)
    await service.start_game(room, first_index=0)  # already active

    assert len(emitter.batches) == before
    service.shutdown()


async def test_concurrent_starts_open_only_one_game():
    # Two players hitting "start" at once must not each open a round: the fetch
    # is an await point, so the second start has to bail on the first's reservation
    # rather than pass a still-clear `room.active` guard and fetch a rival image.
    emitter = RecordingEmitter()
    image = Image(id="1", tags=["solo", "twilight"], thumb_url="t", full_url="f")
    source = GatedImageSource(image)
    service = GameService.single_source(source, emitter)
    room = make_room("alice", "bob")

    first = asyncio.create_task(service.start_game(room, first_index=0))
    second = asyncio.create_task(service.start_game(room, first_index=0))
    await asyncio.sleep(0)  # let both reach the start_game guard
    source.gate.set()  # release the fetch(es)
    await asyncio.gather(first, second)

    assert source.calls == 1  # the loser bailed before ever fetching
    assert emitter.types() == ["image_started", "game_started", "turn_started"]
    assert room.name not in service._starting  # reservation cleared
    service.shutdown()


async def test_room_search_settings_reach_the_image_source():
    emitter = RecordingEmitter()
    source = RecordingImageSource(Image(id="1", tags=["solo"], thumb_url="", full_url=""))
    service = GameService.single_source(source, emitter)
    room = make_room("alice")
    room.nsfw = True
    room.min_tag_count = 20
    room.min_score = 5
    room.rating_caps = {"rating": "questionable"}

    await service.start_game(room)

    assert source.options == SearchOptions(
        nsfw=True,
        min_tag_count=20,
        min_score=5,
        rating_caps={"rating": "questionable"},
    )
    service.shutdown()


async def test_rating_axes_come_from_the_rooms_source():
    """A source with no rating vocabulary reports none, rather than guessing."""
    service = GameService.single_source(StaticImageSource([]), RecordingEmitter())

    assert service.rating_axes_for(make_room("alice")) == []


async def test_no_matching_image_emits_no_image():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([]), emitter)
    room = make_room("alice", query=["cute"])

    await service.start_game(room)

    assert emitter.types() == ["no_image"]
    assert emitter.payloads[0]["query"] == ["cute"]
    assert room.game is None


async def test_image_source_failure_emits_image_error(caplog):
    emitter = RecordingEmitter()
    service = GameService.single_source(BrokenImageSource(), emitter)
    room = make_room("alice")

    with caplog.at_level(logging.WARNING, logger="app.service.game_service"):
        await service.start_game(room)

    assert emitter.types() == ["image_error"]
    assert room.game is None
    assert any("Image fetch failed" in m for m in caplog.messages)  # not silently swallowed


# --- guessing ----------------------------------------------------------------


async def test_active_player_guess_is_applied():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "solo")

    assert "correct_guess" in emitter.types()
    assert room.game.active_player.name == "bob"  # turn advanced
    service.shutdown()


async def test_guess_out_of_turn_is_rejected_and_changes_nothing():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    with pytest.raises(NotYourTurn) as excinfo:
        await service.submit_guess(room, "bob", "solo")  # it's alice's turn

    assert excinfo.value.active_player.name == "alice"  # transport can ack this back
    assert emitter.batches == []  # nothing broadcast to the room
    assert room.game.active_player.name == "alice"  # turn unchanged
    assert "solo" in room.game.tag_buckets["tags"].tags  # tag untouched
    service.shutdown()


async def test_blank_guess_is_ignored_without_penalty():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "   ")

    assert emitter.batches == []  # no strike, no turn change
    assert room.game.active_player.name == "alice"
    assert room.game.active_player.wrong_guesses == 0
    service.shutdown()


async def test_surrounding_whitespace_is_stripped_from_a_guess():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "  SOLO  ")

    assert "correct_guess" in emitter.types()
    service.shutdown()


async def test_winning_guess_ends_game_and_drops_the_timer():
    emitter = RecordingEmitter()
    service = make_service(["solo"], emitter)  # one regular tag
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "solo")

    assert "game_over" in emitter.types()
    assert room.game.is_over
    assert "lobby" not in service._timers  # timer released


async def test_game_over_unreadies_everyone():
    emitter = RecordingEmitter()
    service = make_service(["solo"], emitter)  # one regular tag -> instant win
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "solo")

    assert room.ready_users() == []  # a new round needs a fresh ready-up


async def test_stop_game_unreadies_everyone():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.stop_game(room, "alice")

    assert room.ready_users() == []


async def test_stop_game_refuses_anyone_who_is_not_a_current_player():
    # A spectator or an eliminated player can't kill the round for everyone left.
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    with pytest.raises(GameActionError):
        await service.stop_game(room, "stranger")

    assert room.game is not None  # the round is still running
    assert emitter.batches == []  # nothing broadcast
    service.shutdown()


# --- alias resolution --------------------------------------------------------


async def test_alias_guess_is_accepted_as_the_canonical_tag():
    emitter = RecordingEmitter()
    resolver = RecordingResolver({"bm": "big macintosh"})
    service = make_service(["big macintosh", "twilight"], emitter, tag_resolver=resolver)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "bm")

    correct = next(p for p in emitter.payloads if p["type"] == "correct_guess")
    assert correct["guess"] == "big macintosh"  # canonical shown, not the alias
    # The alias survives the lookup, so the client can show bm → big macintosh.
    assert correct["as_typed"] == "bm"
    assert resolver.calls == ["bm"]  # unrecognized, so it was resolved
    service.shutdown()


async def test_a_guess_needing_no_resolution_carries_no_as_typed():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "solo")

    correct = next(p for p in emitter.payloads if p["type"] == "correct_guess")
    # Omitted rather than null, so the common case adds nothing to the wire.
    assert "as_typed" not in correct
    service.shutdown()


async def test_a_directly_known_guess_skips_the_resolver():
    emitter = RecordingEmitter()
    resolver = RecordingResolver()
    service = make_service(["solo", "twilight"], emitter, tag_resolver=resolver)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "solo")  # a tag already on the image

    assert "correct_guess" in emitter.types()
    assert resolver.calls == []  # recognized: no lookup
    service.shutdown()


async def test_an_unrecognized_non_alias_resolves_to_itself_and_is_wrong():
    emitter = RecordingEmitter()
    resolver = RecordingResolver()  # knows no aliases
    service = make_service(["solo", "twilight"], emitter, tag_resolver=resolver)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.submit_guess(room, "alice", "xyzzy")

    assert "wrong_guess" in emitter.types()
    assert resolver.calls == ["xyzzy"]  # tried, found nothing, treated literally
    service.shutdown()


# --- timeouts ----------------------------------------------------------------


async def test_handle_timeout_counts_as_wrong_and_advances():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.handle_timeout(room)

    assert "timeout" in emitter.types()
    assert room.game.active_player.name == "bob"
    service.shutdown()


async def test_timer_is_rearmed_even_when_emit_fails(caplog):
    class FailingEmitter(EventEmitter):
        async def emit(self, room_name, payloads):
            raise RuntimeError("socket died")

    service = make_service(["solo", "twilight"], FailingEmitter())
    room = make_room("alice", "bob")

    # emit blows up, but the turn must still get a timer to advance it
    with (
        caplog.at_level(logging.ERROR, logger="app.service.game_service"),
        pytest.raises(RuntimeError),
    ):
        await service.start_game(room, first_index=0)

    assert "lobby" in service._timers
    # the failure is recorded with a traceback, not silently swallowed by the finally
    emit_errors = [r for r in caplog.records if "Failed to emit" in r.getMessage()]
    assert emit_errors and emit_errors[0].exc_info is not None
    service.shutdown()


async def test_armed_timer_fires_a_timeout_on_its_own():
    # Proves the wiring: arming eventually calls handle_timeout without any
    # further input.
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter, turn_seconds=0.02)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)
    for _ in range(50):
        await asyncio.sleep(0.005)
        if "timeout" in emitter.types():
            break
    service.shutdown()  # stop before the re-armed timer fires again

    assert "timeout" in emitter.types()


# --- image payloads ----------------------------------------------------------


async def test_start_game_leads_with_image_started_and_hides_answers():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)

    started = emitter.payloads[0]  # picture arrives before the game/turn events
    assert started["type"] == "image_started"
    assert (started["id"], started["thumb_url"], started["full_url"]) == ("7", "thumb", "full")
    # pins the round to its booru, so end-of-round links survive a source switch
    assert started["source"] == room.source
    # answer-revealing fields must never leak mid-game
    for leaky in ("tags", "artists", "source_url", "page_url"):
        assert leaky not in started
    service.shutdown()


async def test_game_over_reveals_attribution():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # clears the goal bucket → win

    assert "game_over" in emitter.types()
    reveal = emitter.payloads[-1]  # trails the batch
    assert reveal["type"] == "image_revealed"
    assert reveal["artists"] == ["foo"]  # "artist:" stripped
    assert reveal["source_url"] == "https://example.com/original"
    assert reveal["page_url"] == "https://derpibooru.org/images/7"


async def test_stop_game_reveals_attribution_with_the_abort():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.stop_game(room, "alice")

    assert emitter.types() == ["game_aborted", "image_revealed"]
    assert emitter.payloads[-1]["artists"] == ["foo"]
    assert room.game is None  # back to the lobby


async def test_stop_game_reveals_the_unguessed_tags_it_is_discarding():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.stop_game(room, "alice")

    aborted = emitter.payloads[0]
    assert aborted["type"] == "game_aborted"
    assert aborted["unguessed"] == {"tags": ["solo"], "artists": ["artist:foo"]}


async def test_cancel_room_drops_the_image_without_revealing():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    service.cancel_room(room.name)

    assert emitter.batches == []  # empty room: nobody to reveal to
    assert room.name not in service._current_image


# --- round history -----------------------------------------------------------


async def test_game_over_records_a_won_round_in_history():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # clears the goal bucket → win

    history = service.room_history(room.name)
    assert len(history) == 1
    record = history[0]
    assert record["page_url"] == "https://derpibooru.org/images/7"
    assert record["artists"] == ["foo"]
    assert record["win"] is True
    assert record["aborted"] is False
    assert record["nsfw"] is False  # room defaults to SFW
    assert [w["uuid"] for w in record["winners"]] == ["alice"]
    assert [s["uuid"] for s in record["standings"]] == ["alice"]


async def test_round_history_captures_nsfw_at_play_time():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")
    room.nsfw = True

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win

    room.nsfw = False  # room flipped to SFW after the round was played
    (record,) = service.room_history(room.name)
    assert record["nsfw"] is True  # the played round stays flagged, thumbnail gated


async def test_aborted_round_is_recorded_with_the_link_but_no_result():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.stop_game(room, "alice")

    (record,) = service.room_history(room.name)
    assert record["aborted"] is True
    assert record["win"] is False
    assert record["winners"] == []
    assert record["standings"] == []
    assert record["page_url"] == "https://derpibooru.org/images/7"  # still traceable


async def test_history_accumulates_across_rounds():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image(), rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")
    ready_up(room)  # the finished round un-readied everyone
    await service.start_game(room, first_index=0)
    await service.stop_game(room, "alice")

    history = service.room_history(room.name)
    assert [r["aborted"] for r in history] == [False, True]


async def test_cancel_room_drops_history():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")
    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")

    service.cancel_room(room.name)

    assert service.room_history(room.name) == []


# --- win counts (server-authoritative tally) ---------------------------------


async def test_win_counts_come_from_played_rounds():
    emitter = RecordingEmitter()
    service = GameService.single_source(StaticImageSource([rich_image(), rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win #1
    ready_up(room)  # the finished round un-readied everyone
    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win #2

    assert service.room_win_counts(room.name) == [{"uuid": "alice", "name": "alice", "wins": 2}]


def test_win_counts_tally_by_uuid_sorted_with_latest_name():
    service = GameService.single_source(StaticImageSource([]), RecordingEmitter())
    service._history["lobby"] = [
        {"winners": [{"uuid": "a", "name": "Alice"}]},
        {"winners": [{"uuid": "b", "name": "Bob"}, {"uuid": "a", "name": "Alicia"}]},
        {"winners": []},  # aborted / lost round contributes nothing
    ]

    assert service.room_win_counts("lobby") == [
        {"uuid": "a", "name": "Alicia", "wins": 2},  # most wins first, name updated
        {"uuid": "b", "name": "Bob", "wins": 1},
    ]


def test_win_counts_are_empty_for_an_unplayed_room():
    service = GameService.single_source(StaticImageSource([]), RecordingEmitter())
    assert service.room_win_counts("lobby") == []


# --- game snapshot (mid-game (re)join) ---------------------------------------


async def test_game_snapshot_describes_the_live_round_without_leaking_answers():
    service = make_service(["solo", "twilight"], RecordingEmitter(), turn_seconds=45.0)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    snap = service.game_snapshot(room)

    assert snap["type"] == "game_snapshot"
    assert snap["image"] == {"id": "1", "thumb_url": "t", "full_url": "f"}
    assert {p["name"] for p in snap["players"]} == {"alice", "bob"}
    assert snap["active_player"]["name"] == "alice"
    assert snap["tag_count"] == 2
    assert snap["goal_remaining"] == 2
    assert snap["eliminated"] == []
    assert snap["turn_seconds"] == 45.0  # the snapshot carries the room's turn length
    # A rejoining client needs the strike denominator as much as a fresh one.
    assert snap["elimination_threshold"] == 3
    # the unguessed goal tags must never appear anywhere in the payload
    assert "twilight" not in json.dumps(snap)
    assert "solo" not in json.dumps(snap)
    service.shutdown()


async def test_game_snapshot_carries_the_rounds_feed_for_replay():
    service = make_service(["solo", "twilight"], RecordingEmitter())
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "solo")  # correct, turn passes to bob
    await service.submit_guess(room, "bob", "nope")  # wrong

    feed = service.game_snapshot(room)["feed"]
    assert [entry["type"] for entry in feed] == ["correct_guess", "wrong_guess"]
    assert [entry["guess"] for entry in feed] == ["solo", "nope"]
    # turn_started/game_started aren't feed rows — the snapshot's own fields cover them
    assert not {"game_started", "turn_started"} & {entry["type"] for entry in feed}
    service.shutdown()


async def test_a_new_round_starts_from_an_empty_feed():
    service = make_service(["solo", "twilight"], RecordingEmitter())
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "nope")

    await service.stop_game(room, "alice")
    ready_up(room)
    await service.start_game(room, first_index=0)

    assert service.game_snapshot(room)["feed"] == []
    service.shutdown()


async def test_game_snapshot_reports_what_is_left_of_the_active_turn():
    service = make_service(["solo", "twilight"], RecordingEmitter(), turn_seconds=45.0)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await asyncio.sleep(0.05)

    snap = service.game_snapshot(room)
    # a rejoin mid-turn resumes the clock rather than restarting it at 45
    assert 0 < snap["turn_remaining"] < 45.0
    assert snap["turn_seconds"] == 45.0
    service.shutdown()


async def test_game_snapshot_tracks_progress_but_keeps_the_original_total():
    service = make_service(["solo", "twilight"], RecordingEmitter())
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "solo")  # one goal tag found

    snap = service.game_snapshot(room)
    assert snap["goal_remaining"] == 1
    assert snap["tag_count"] == 2  # original total, reconstructed
    service.shutdown()


async def test_an_aliased_query_term_still_frees_its_canonical_tag():
    resolver = RecordingResolver({"ts": "twilight sparkle"})
    service = make_service(["twilight sparkle", "solo"], RecordingEmitter(), tag_resolver=resolver)
    room = make_room("alice", query=["ts"])
    await service.start_game(room, first_index=0)

    assert room.game.freebie_tags == ["twilight sparkle"]
    assert room.game.tag_buckets["tags"].tags == ["solo"]
    service.shutdown()


async def test_a_query_term_already_on_the_image_costs_no_lookup():
    resolver = RecordingResolver()
    service = make_service(["mare", "solo"], RecordingEmitter(), tag_resolver=resolver)
    room = make_room("alice", query=["mare", "cute"])
    await service.start_game(room, first_index=0)

    assert resolver.calls == ["cute"]  # "mare" is on the image, so already canonical
    service.shutdown()


async def test_only_plain_query_terms_cost_an_alias_lookup():
    resolver = RecordingResolver()
    service = make_service(["solo"], RecordingEmitter(), tag_resolver=resolver)
    room = make_room("alice", query=["mare", "artist:foo", "-anthro", "score.gte:100", "a || b"])
    await service.start_game(room, first_index=0)

    assert resolver.calls == ["mare", "artist:foo"]
    service.shutdown()


async def test_query_alias_lookups_are_capped_per_round():
    resolver = RecordingResolver()
    service = make_service(["solo"], RecordingEmitter(), tag_resolver=resolver)
    room = make_room("alice", query=[f"tag{i}" for i in range(20)])
    await service.start_game(room, first_index=0)

    assert len(resolver.calls) == LimitsSettings().max_query_lookups
    service.shutdown()


async def test_game_snapshot_carries_the_freebies_a_rejoin_missed():
    service = make_service(["solo", "twilight", "mare"], RecordingEmitter())
    room = make_room("alice", query=["mare", "score.gte:100"])
    await service.start_game(room, first_index=0)

    assert service.game_snapshot(room)["freebie_tags"] == ["mare"]
    service.shutdown()


async def test_game_snapshot_is_none_without_a_running_game():
    service = make_service(["solo"], RecordingEmitter())
    room = make_room("alice")
    assert service.game_snapshot(room) is None  # no game yet

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # single goal tag -> win
    assert room.game.is_over
    assert service.game_snapshot(room) is None  # finished round reveals, not snapshots
    service.shutdown()


# --- multiple sources --------------------------------------------------------


def two_source_service(emitter: EventEmitter, **resolvers) -> GameService:
    """A service wired with two distinct sources, one image and taxonomy each."""
    derpi = StaticImageSource(
        [Image(id="d", tags=["solo"], thumb_url="", full_url="")], rating_axes=DERPIBOORU_AXES
    )
    furry = StaticImageSource(
        [Image(id="f", tags=["solo"], thumb_url="", full_url="")], rating_axes=()
    )
    sources = {
        "derpibooru": SourceBundle(
            derpi, resolvers.get("derpibooru", NullTagResolver()), DERPIBOORU_TAXONOMY
        ),
        "furbooru": SourceBundle(
            furry, resolvers.get("furbooru", NullTagResolver()), FURBOORU_TAXONOMY
        ),
    }
    return GameService(emitter, sources, default_source="derpibooru")


async def test_the_rooms_source_picks_its_bundle_image_and_taxonomy():
    service = two_source_service(RecordingEmitter())
    room = make_room("alice")
    room.source = "furbooru"

    await service.start_game(room, first_index=0)

    assert service._current_image[room.name].id == "f"  # furbooru's provider served it
    assert room.game.taxonomy is FURBOORU_TAXONOMY  # and its taxonomy classified the tags
    service.shutdown()


async def test_the_round_payloads_carry_the_rooms_source():
    """Both ways into a round name its booru, so links outlive a later switch."""
    emitter = RecordingEmitter()
    service = two_source_service(emitter)
    room = make_room("alice")
    room.source = "furbooru"  # not the default

    await service.start_game(room, first_index=0)

    assert emitter.payloads[0]["source"] == "furbooru"  # image_started opens the round
    assert service.game_snapshot(room)["source"] == "furbooru"  # a rejoin agrees
    service.shutdown()


async def test_an_unknown_room_source_falls_back_to_the_default_bundle():
    service = two_source_service(RecordingEmitter())
    room = make_room("alice")
    room.source = "e621"  # not configured

    await service.start_game(room, first_index=0)

    assert service._current_image[room.name].id == "d"  # the default (derpibooru)
    service.shutdown()


async def test_rating_axes_follow_the_rooms_source():
    # derpibooru carries the Philomena axes; the furbooru stand-in carries none.
    service = two_source_service(RecordingEmitter())
    room = make_room("alice")

    assert [a["key"] for a in service.rating_axes_for(room)] == ["rating", "darkness"]
    room.source = "furbooru"
    assert service.rating_axes_for(room) == []


async def test_a_guess_is_resolved_by_the_rooms_own_source():
    derpi_resolver = RecordingResolver()
    furry_resolver = RecordingResolver({"bm": "big macintosh"})
    service = two_source_service(
        RecordingEmitter(), derpibooru=derpi_resolver, furbooru=furry_resolver
    )
    room = make_room("alice")
    room.source = "furbooru"
    await service.start_game(room, first_index=0)

    await service.submit_guess(room, "alice", "bm")  # unrecognized → hits the resolver

    assert furry_resolver.calls == ["bm"]  # the room's source resolved it
    assert derpi_resolver.calls == []  # the other source stayed untouched
    service.shutdown()
