"""Socket.IO handlers driven directly against a recording server double.

No live server: a ``FakeServer`` stands in for the AsyncServer surface the
handlers touch (sessions, room membership, emit), and a real ``GameService``
backed by a ``StaticImageSource`` runs underneath. Handler coroutines are called
straight, and their ack return values and recorded emits are asserted.
"""

import pytest

from app.service.game_service import GameService
from app.service.image_source import Image, StaticImageSource
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import SocketHandlers
from app.transport.registry import RoomRegistry


class FakeServer:
    """Records the AsyncServer surface the handlers use — sessions, rooms, emit."""

    def __init__(self):
        self.sessions: dict[str, dict] = {}
        self.member_rooms: dict[str, set] = {}
        self.emits: list[tuple] = []  # (event, data, room)

    async def save_session(self, sid, data):
        self.sessions[sid] = data

    async def get_session(self, sid):
        return self.sessions.get(sid, {})

    async def enter_room(self, sid, room):
        self.member_rooms.setdefault(room, set()).add(sid)

    async def leave_room(self, sid, room):
        self.member_rooms.get(room, set()).discard(sid)

    async def emit(self, event, data=None, room=None, **kwargs):
        self.emits.append((event, data, room))

    def on(self, event, handler):  # parity with register(); unused here
        pass

    # --- assertion helpers ---
    def emits_of(self, event):
        return [data for name, data, _room in self.emits if name == event]

    def last_state(self):
        states = self.emits_of("room_state")
        return states[-1] if states else None

    def game_event_types(self):
        return [p["type"] for batch in self.emits_of("game_events") for p in batch]


@pytest.fixture
def make():
    """Factory for a wired (handlers, server, registry, service); auto-shuts timers."""
    services = []

    def _make(tags=("solo", "twilight"), turn_seconds=30.0):
        server = FakeServer()
        registry = RoomRegistry()
        image = Image(id="1", tags=list(tags), thumb_url="t", full_url="f")
        service = GameService(
            StaticImageSource([image]), SocketIOEmitter(server), turn_seconds=turn_seconds
        )
        services.append(service)
        return SocketHandlers(server, registry, service), server, registry, service

    yield _make
    for service in services:
        service.shutdown()


async def _create(handlers, sid, uuid, name, **extra):
    """Mint a room via create_room and return its code."""
    ack = await handlers.create_room(sid, {"uuid": uuid, "name": name, **extra})
    assert ack["ok"], ack
    return ack["room_state"]["room"]


# --- creating & joining ------------------------------------------------------


async def test_create_room_mints_a_code_and_joins_the_creator(make):
    handlers, server, registry, _service = make()

    ack = await handlers.create_room("sa", {"uuid": "ua", "name": "Alice"})

    code = ack["room_state"]["room"]
    assert ack["ok"] and code.count("-") == 2
    assert registry.get(code) is not None
    assert server.sessions["sa"] == {"uuid": "ua", "room": code, "name": "Alice"}
    assert "sa" in server.member_rooms[code]  # joined the socketio room
    assert server.last_state()["users"][0]["name"] == "Alice"


async def test_join_unknown_room_is_rejected(make):
    handlers, _server, _registry, _service = make()

    ack = await handlers.join_room("sb", {"room": "no-such-fox", "uuid": "ub", "name": "Bob"})

    assert ack == {"ok": False, "error": "room_not_found"}


async def test_second_player_joins_by_code(make):
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})

    assert ack["ok"]
    assert [u["name"] for u in server.last_state()["users"]] == ["Alice", "Bob"]


async def test_join_is_case_insensitive_on_the_code(make):
    handlers, _server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.join_room("sb", {"room": code.upper(), "uuid": "ub", "name": "Bob"})

    assert ack["ok"]


async def test_duplicate_name_is_rejected(make):
    # Bug #2: legacy compared a string to User objects, so this never fired.
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "alice"})

    assert ack == {"ok": False, "error": "name_taken"}
    assert len(server.last_state()["users"]) == 1  # Bob not added


async def test_reconnect_same_uuid_updates_name_without_duplicating(make):
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.join_room("sa", {"room": code, "uuid": "ua", "name": "Al"})

    assert ack["ok"]
    users = server.last_state()["users"]
    assert len(users) == 1 and users[0]["name"] == "Al"


async def test_rejected_switch_keeps_you_in_your_current_room(make):
    # A failed join must not strand the caller: leaving the old room happens only
    # after the new join is known to succeed.
    handlers, server, registry, _service = make()
    a_code = await _create(handlers, "sa", "ua", "Alice")
    b_code = await _create(handlers, "sb", "ub", "Bob")

    ack = await handlers.join_room("sb", {"room": a_code, "uuid": "ub", "name": "Alice"})

    assert ack == {"ok": False, "error": "name_taken"}
    assert "ub" in registry.get(b_code).users  # still in his own room
    assert server.sessions["sb"]["room"] == b_code


async def test_creating_again_leaves_the_previous_room(make):
    handlers, _server, registry, _service = make()
    first = await _create(handlers, "sa", "ua", "Alice")

    second = await _create(handlers, "sa", "ua", "Alice")

    assert second != first
    assert registry.get(first) is None  # emptied and torn down
    assert "ua" in registry.get(second).users


# --- readiness & config ------------------------------------------------------


async def test_set_ready_toggles_and_broadcasts(make):
    handlers, server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.set_ready("sa", {"ready": True})

    assert ack == {"ok": True}
    assert server.last_state()["users"][0]["ready"] is True


async def test_configure_room_updates_query_and_nsfw_before_a_game(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.configure_room("sa", {"query": "cute, pony", "nsfw": True})

    assert ack == {"ok": True}
    room = registry.get(code)
    assert room.query == ["cute", "pony"] and room.nsfw is True
    assert server.last_state()["query"] == ["cute", "pony"]


async def test_configure_room_is_rejected_during_a_game(make):
    handlers, _server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")

    ack = await handlers.configure_room("sa", {"query": "cute"})

    assert ack == {"ok": False, "error": "game_in_progress"}


# --- starting a game ---------------------------------------------------------


async def test_start_requires_a_ready_player(make):
    # Bug #1: legacy crashed with a NameError here; now it's a clean ack.
    handlers, _server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")  # nobody ready

    ack = await handlers.start_game("sa")

    assert ack == {"ok": False, "error": "no_players_ready"}


async def test_start_happy_path_emits_game_events(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})

    ack = await handlers.start_game("sa")

    assert ack == {"ok": True}
    assert server.game_event_types()[:3] == ["image_started", "game_started", "turn_started"]
    assert registry.get(code).active
    assert server.last_state()["in_progress"] is True


async def test_start_when_already_active_is_rejected(make):
    handlers, _server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")

    ack = await handlers.start_game("sa")

    assert ack == {"ok": False, "error": "game_in_progress"}


# --- guessing ----------------------------------------------------------------


async def _start_two_player_game(handlers):
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})
    await handlers.set_ready("sa", {"ready": True})
    await handlers.set_ready("sb", {"ready": True})
    await handlers.start_game("sa")
    return code


async def test_guess_out_of_turn_acks_not_your_turn(make):
    handlers, _server, registry, _service = make()
    code = await _start_two_player_game(handlers)
    active = registry.get(code).game.active_player
    off_turn_sid = "sb" if active.uuid == "ua" else "sa"

    ack = await handlers.submit_guess(off_turn_sid, {"guess": "solo"})

    assert ack["ok"] is False and ack["error"] == "not_your_turn"
    assert ack["active_player"] == {"uuid": active.uuid, "name": active.name}


async def test_active_player_guess_is_applied(make):
    handlers, server, registry, _service = make()
    code = await _start_two_player_game(handlers)
    active = registry.get(code).game.active_player
    active_sid = "sa" if active.uuid == "ua" else "sb"

    ack = await handlers.submit_guess(active_sid, {"guess": "solo"})

    assert ack == {"ok": True}
    assert "correct_guess" in server.game_event_types()


# --- stopping, leaving, chat -------------------------------------------------


async def test_stop_game_aborts_and_returns_to_lobby(make):
    handlers, server, registry, service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")

    ack = await handlers.stop_game("sa")

    assert ack == {"ok": True}
    assert "game_aborted" in server.game_event_types()
    assert registry.get(code).active is False
    assert code not in service._timers  # timer released
    assert server.last_state()["in_progress"] is False


async def test_room_snapshot_carries_round_history(make):
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    assert server.last_state()["history"] == []  # nothing played yet

    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")
    await handlers.stop_game("sa")  # aborts, records the round, rebroadcasts state

    history = server.last_state()["history"]
    assert len(history) == 1 and history[0]["aborted"] is True
    # the join ack snapshot is composed the same way
    rejoin = await handlers.join_room("sa", {"room": code, "uuid": "ua", "name": "Alice"})
    assert rejoin["room_state"]["history"] == history


async def test_leave_room_removes_user_and_keeps_a_non_empty_room(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})

    ack = await handlers.leave_room("sb")

    assert ack == {"ok": True}
    assert registry.get(code) is not None
    assert [u["name"] for u in server.last_state()["users"]] == ["Alice"]
    assert server.sessions["sb"] == {}  # session cleared
    assert "sb" not in server.member_rooms[code]


async def test_last_player_leaving_tears_down_the_room_and_timer(make):
    handlers, _server, registry, service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")  # arms a timer

    await handlers.leave_room("sa")

    assert registry.get(code) is None
    assert code not in service._timers  # orphaned timer cancelled


async def test_disconnect_is_treated_as_leaving(make):
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.disconnect("sa")

    assert registry.get(code) is None


async def test_chat_broadcasts_and_never_touches_the_game(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")
    before = server.game_event_types()

    ack = await handlers.chat("sa", {"text": "hi all"})

    assert ack == {"ok": True}
    assert ("chat", {"name": "Alice", "text": "hi all"}, code) in server.emits
    assert server.game_event_types() == before  # no game state moved


# --- acting before joining ---------------------------------------------------


@pytest.mark.parametrize("action", ["set_ready", "configure_room", "start_game", "submit_guess", "stop_game"])
async def test_actions_before_joining_are_rejected(make, action):
    handlers, _server, _registry, _service = make()

    ack = await getattr(handlers, action)("ghost", {})

    assert ack == {"ok": False, "error": "not_in_room"}
