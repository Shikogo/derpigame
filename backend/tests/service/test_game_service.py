"""Orchestration: fetch → mutate domain → emit → time, routed through one path."""

import asyncio

import pytest

from app.domain.room import Room
from app.domain.user import User
from app.service.emitter import EventEmitter
from app.service.errors import NotYourTurn
from app.service.game_service import GameService
from app.service.image_source import Image, ImageSource, ImageSourceError, StaticImageSource


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


def make_room(*names: str, query: list[str] | None = None) -> Room:
    room = Room("lobby", query=query or [])
    for name in names:
        user = User(uuid=name, name=name)
        user.ready = True
        room.add_user(user)
    return room


def make_service(tags: list[str], emitter: EventEmitter, **kwargs) -> GameService:
    image = Image(id="1", tags=tags, thumb_url="t", full_url="f")
    return GameService(StaticImageSource([image]), emitter, **kwargs)


# --- starting a game ---------------------------------------------------------


async def test_start_game_announces_opening_and_arms_a_timer():
    emitter = RecordingEmitter()
    service = make_service(["solo", "twilight"], emitter)
    room = make_room("alice", "bob")

    await service.start_game(room, first_index=0)

    assert emitter.types() == ["game_started", "turn_started"]
    assert room.game is not None
    assert "lobby" in service._timers  # armed for the first turn
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
