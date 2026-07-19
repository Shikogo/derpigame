"""Orchestration: fetch → mutate domain → emit → time, routed through one path."""

import asyncio
import json

import pytest

from app.domain.room import Room
from app.domain.user import User
from app.service.emitter import EventEmitter
from app.service.errors import NotYourTurn
from app.service.game_service import GameService
from app.service.image_source import Image, ImageSource, ImageSourceError, StaticImageSource
from app.service.tag_resolver import TagResolver


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
    async def random_image(self, query, *, nsfw):
        raise ImageSourceError("provider is down")


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
    return GameService(StaticImageSource([image]), emitter, **kwargs)


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


async def test_no_matching_image_emits_no_image():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([]), emitter)
    room = make_room("alice", query=["cute"])

    await service.start_game(room)

    assert emitter.types() == ["no_image"]
    assert emitter.payloads[0]["query"] == ["cute"]
    assert room.game is None


async def test_image_source_failure_emits_image_error():
    emitter = RecordingEmitter()
    service = GameService(BrokenImageSource(), emitter)
    room = make_room("alice")

    await service.start_game(room)

    assert emitter.types() == ["image_error"]
    assert room.game is None


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

    await service.stop_game(room)

    assert room.ready_users() == []


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
    assert resolver.calls == ["bm"]  # unrecognized, so it was resolved
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


async def test_timer_is_rearmed_even_when_emit_fails():
    class FailingEmitter(EventEmitter):
        async def emit(self, room_name, payloads):
            raise RuntimeError("socket died")

    service = make_service(["solo", "twilight"], FailingEmitter())
    room = make_room("alice", "bob")

    # emit blows up, but the turn must still get a timer to advance it
    with pytest.raises(RuntimeError):
        await service.start_game(room, first_index=0)

    assert "lobby" in service._timers
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
    service = GameService(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)

    started = emitter.payloads[0]  # picture arrives before the game/turn events
    assert started["type"] == "image_started"
    assert (started["id"], started["thumb_url"], started["full_url"]) == ("7", "thumb", "full")
    # answer-revealing fields must never leak mid-game
    for leaky in ("tags", "artists", "source_url", "page_url"):
        assert leaky not in started
    service.shutdown()


async def test_game_over_reveals_attribution():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([rich_image()]), emitter)
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
    service = GameService(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)
    emitter.batches.clear()

    await service.stop_game(room)

    assert emitter.types() == ["game_aborted", "image_revealed"]
    assert emitter.payloads[-1]["artists"] == ["foo"]
    assert room.game is None  # back to the lobby


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
    service = GameService(StaticImageSource([rich_image()]), emitter)
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
    service = GameService(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")
    room.nsfw = True

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win

    room.nsfw = False  # room flipped to SFW after the round was played
    (record,) = service.room_history(room.name)
    assert record["nsfw"] is True  # the played round stays flagged, thumbnail gated


async def test_aborted_round_is_recorded_with_the_link_but_no_result():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice", "bob")
    await service.start_game(room, first_index=0)

    await service.stop_game(room)

    (record,) = service.room_history(room.name)
    assert record["aborted"] is True
    assert record["win"] is False
    assert record["winners"] == []
    assert record["standings"] == []
    assert record["page_url"] == "https://derpibooru.org/images/7"  # still traceable


async def test_history_accumulates_across_rounds():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([rich_image(), rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")
    ready_up(room)  # the finished round un-readied everyone
    await service.start_game(room, first_index=0)
    await service.stop_game(room)

    history = service.room_history(room.name)
    assert [r["aborted"] for r in history] == [False, True]


async def test_cancel_room_drops_history():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([rich_image()]), emitter)
    room = make_room("alice")
    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")

    service.cancel_room(room.name)

    assert service.room_history(room.name) == []


# --- win counts (server-authoritative tally) ---------------------------------


async def test_win_counts_come_from_played_rounds():
    emitter = RecordingEmitter()
    service = GameService(StaticImageSource([rich_image(), rich_image()]), emitter)
    room = make_room("alice")

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win #1
    ready_up(room)  # the finished round un-readied everyone
    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # win #2

    assert service.room_win_counts(room.name) == [{"uuid": "alice", "name": "alice", "wins": 2}]


def test_win_counts_tally_by_uuid_sorted_with_latest_name():
    service = GameService(StaticImageSource([]), RecordingEmitter())
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
    service = GameService(StaticImageSource([]), RecordingEmitter())
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
    # the unguessed goal tags must never appear anywhere in the payload
    assert "twilight" not in json.dumps(snap)
    assert "solo" not in json.dumps(snap)
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


async def test_game_snapshot_is_none_without_a_running_game():
    service = make_service(["solo"], RecordingEmitter())
    room = make_room("alice")
    assert service.game_snapshot(room) is None  # no game yet

    await service.start_game(room, first_index=0)
    await service.submit_guess(room, "alice", "solo")  # single goal tag -> win
    assert room.game.is_over
    assert service.game_snapshot(room) is None  # finished round reveals, not snapshots
    service.shutdown()
