"""Socket.IO handlers driven directly against a recording server double.

No live server: a ``FakeServer`` stands in for the AsyncServer surface the
handlers touch (sessions, room membership, emit), and a real ``GameService``
backed by a ``StaticImageSource`` runs underneath. Handler coroutines are called
straight, and their ack return values and recorded emits are asserted.
"""

import asyncio

import pytest

from app.config import LimitsSettings
from app.domain.rating import DERPIBOORU_AXES
from app.service.game_service import GameService
from app.service.image_source import Image, StaticImageSource
from app.service.sources import SourceBundle
from app.service.tag_resolver import NullTagResolver
from app.transport.emitter import SocketIOEmitter
from app.transport.handlers import SocketHandlers
from app.transport.registry import RoomRegistry

MAX_QUERY_TERMS = LimitsSettings().max_query_terms


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
        # A targeted emit uses to=<sid>; record it in the room slot for assertions.
        self.emits.append((event, data, room if room is not None else kwargs.get("to")))

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
    handlers_made = []

    def _make(
        tags=("solo", "twilight"),
        turn_seconds=30.0,
        reconnect_grace=30.0,
        unload_grace=30.0,
        rating_axes=(),
        sources=None,
    ):
        server = FakeServer()
        registry = RoomRegistry()
        image = Image(id="1", tags=list(tags), thumb_url="t", full_url="f")
        if sources is not None:
            service = GameService(SocketIOEmitter(server), sources, turn_seconds=turn_seconds)
        else:
            service = GameService.single_source(
                StaticImageSource([image], rating_axes=rating_axes),
                SocketIOEmitter(server),
                turn_seconds=turn_seconds,
            )
        handlers = SocketHandlers(
            server,
            registry,
            service,
            reconnect_grace=reconnect_grace,
            unload_grace=unload_grace,
        )
        services.append(service)
        handlers_made.append(handlers)
        return handlers, server, registry, service

    yield _make
    for handlers in handlers_made:
        handlers.shutdown()
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


async def test_return_to_lobby_clears_only_the_caller_and_broadcasts(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})
    registry.get(code).mark_viewing_results()  # as a finished round leaves them

    ack = await handlers.return_to_lobby("sa")

    assert ack == {"ok": True}
    viewing = {u["name"]: u["viewing_results"] for u in server.last_state()["users"]}
    assert viewing == {"Alice": False, "Bob": True}


async def test_configure_room_updates_query_and_nsfw_before_a_game(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.configure_room("sa", {"query": "cute, pony", "nsfw": True})

    assert ack == {"ok": True}
    room = registry.get(code)
    assert room.query == ["cute", "pony"] and room.nsfw is True
    assert server.last_state()["query"] == ["cute", "pony"]


async def test_configure_room_truncates_an_oversized_query(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    flood = ",".join(f"tag{i}" for i in range(200))
    await handlers.configure_room("sa", {"query": flood})

    assert registry.get(code).query == [f"tag{i}" for i in range(MAX_QUERY_TERMS)]


async def test_configure_room_sets_turn_seconds_and_broadcasts_it(make):
    handlers, server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.configure_room("sa", {"turn_seconds": 45})

    assert ack == {"ok": True}
    assert registry.get(code).turn_seconds == 45.0
    assert server.last_state()["turn_seconds"] == 45.0


async def test_configure_room_clamps_out_of_range_turn_seconds(make):
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"turn_seconds": 5})  # below the floor
    assert registry.get(code).turn_seconds == 10.0
    await handlers.configure_room("sa", {"turn_seconds": 9999})  # above the ceiling
    assert registry.get(code).turn_seconds == 300.0


async def test_configured_turn_seconds_flows_into_game_started(make):
    handlers, server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")
    await handlers.configure_room("sa", {"turn_seconds": 60})
    await handlers.set_ready("sa", {"ready": True})

    await handlers.start_game("sa")

    started = next(p for p in server.emits_of("game_events")[-1] if p["type"] == "game_started")
    assert started["turn_seconds"] == 60.0


async def test_configure_room_sets_the_search_bounds_and_broadcasts_them(make):
    handlers, server, registry, _service = make(rating_axes=DERPIBOORU_AXES)
    code = await _create(handlers, "sa", "ua", "Alice")

    ack = await handlers.configure_room(
        "sa",
        {
            "min_tag_count": 25,
            "min_score": 100,
            "rating_caps": {"rating": "safe", "darkness": "none"},
        },
    )

    assert ack == {"ok": True}
    room = registry.get(code)
    assert (room.min_tag_count, room.min_score) == (25, 100)
    assert room.rating_caps == {"rating": "safe", "darkness": "none"}
    assert server.last_state()["min_score"] == 100


async def test_configure_room_turns_a_bound_off_with_null(make):
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"min_tag_count": None, "min_score": None})

    room = registry.get(code)
    assert room.min_tag_count is None and room.min_score is None


async def test_configure_room_keeps_a_zero_score_bound(make):
    """0 is a real threshold (it excludes downvoted images), not an off switch."""
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"min_score": 0})

    assert registry.get(code).min_score == 0


async def test_configure_room_floors_a_negative_tag_count(make):
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"min_tag_count": -5})

    assert registry.get(code).min_tag_count == 0


async def test_configure_room_drops_caps_the_source_does_not_recognize(make):
    """An unknown axis or level means no cap, never a silently wrong one."""
    handlers, _server, registry, _service = make(rating_axes=DERPIBOORU_AXES)
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room(
        "sa", {"rating_caps": {"rating": "sfw-ish", "loudness": "none", "darkness": "grimdark"}}
    )

    assert registry.get(code).rating_caps == {"darkness": "grimdark"}


async def test_room_state_advertises_the_source_rating_axes(make):
    handlers, server, _registry, _service = make(rating_axes=DERPIBOORU_AXES)
    await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"nsfw": True})

    axes = server.last_state()["rating_axes"]
    assert [a["key"] for a in axes] == ["rating", "darkness"]
    assert axes[1]["levels"] == ["none", "semi-grimdark", "grimdark", "grotesque"]


def _two_sources():
    """Two distinct sources: one with rating axes, one without."""
    image = Image(id="1", tags=["solo"], thumb_url="t", full_url="f")
    return {
        "derpibooru": SourceBundle(
            StaticImageSource([image], rating_axes=DERPIBOORU_AXES), NullTagResolver()
        ),
        "furbooru": SourceBundle(StaticImageSource([image], rating_axes=()), NullTagResolver()),
    }


async def test_configure_room_switches_to_a_known_source_and_ignores_unknown(make):
    handlers, server, registry, _service = make(sources=_two_sources())
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"source": "furbooru"})
    assert registry.get(code).source == "furbooru"
    assert server.last_state()["source"] == "furbooru"
    # The furbooru stand-in carries no rating axes, so the caps UI empties out.
    assert server.last_state()["rating_axes"] == []

    await handlers.configure_room("sa", {"source": "nonesuch"})
    assert registry.get(code).source == "furbooru"  # unknown selection left the room alone


async def test_room_state_advertises_the_available_sources(make):
    handlers, server, _registry, _service = make(sources=_two_sources())
    await _create(handlers, "sa", "ua", "Alice")

    await handlers.configure_room("sa", {"nsfw": True})

    sources = server.last_state()["sources"]
    assert [s["key"] for s in sources] == ["derpibooru", "furbooru"]
    assert [s["label"] for s in sources] == ["Derpibooru", "Furbooru"]


async def test_configure_room_is_rejected_during_a_game(make):
    handlers, _server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")

    ack = await handlers.configure_room("sa", {"query": "cute"})

    assert ack == {"ok": False, "error": "game_in_progress"}


# --- starting a game ---------------------------------------------------------


async def test_start_requires_the_caller_to_be_ready(make):
    # Bug #1: legacy crashed with a NameError here; now it's a clean ack.
    handlers, _server, _registry, _service = make()
    await _create(handlers, "sa", "ua", "Alice")  # not ready

    ack = await handlers.start_game("sa")

    assert ack == {"ok": False, "error": "not_ready"}


async def test_spectator_cannot_start_but_a_ready_player_can(make):
    handlers, _server, registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})
    await handlers.set_ready("sb", {"ready": True})  # only Bob readies up

    # Alice is a spectator (not ready) — she can't start, even though Bob is.
    assert await handlers.start_game("sa") == {"ok": False, "error": "not_ready"}
    assert not registry.get(code).active

    # Bob, who's ready, can.
    assert await handlers.start_game("sb") == {"ok": True}
    assert registry.get(code).active


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


# --- stopping and leaving ----------------------------------------------------


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


async def test_win_counts_surface_in_the_snapshot_after_a_win(make):
    handlers, server, _registry, _service = make(tags=("solo",))  # single goal tag
    await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")
    await handlers.submit_guess("sa", {"guess": "solo"})  # clears the goal → win

    # a natural game-over doesn't rebroadcast; the next lobby action carries it
    await handlers.set_ready("sa", {"ready": False})
    assert server.last_state()["win_counts"] == [{"uuid": "ua", "name": "Alice", "wins": 1}]


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


async def test_disconnect_keeps_the_room_briefly_then_tears_it_down(make):
    handlers, _server, registry, _service = make(reconnect_grace=0.02)
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.disconnect("sa")
    assert registry.get(code) is not None  # held for a reconnect window

    await asyncio.sleep(0.05)
    assert registry.get(code) is None  # torn down once the window lapses


async def test_reconnect_within_grace_reclaims_the_room(make):
    handlers, _server, registry, _service = make(reconnect_grace=0.05)
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.disconnect("sa")  # e.g. a page reload drops the socket
    await handlers.join_room("sa2", {"room": code, "uuid": "ua", "name": "Alice"})
    await asyncio.sleep(0.08)  # window lapses, but the reconnect cancelled it

    assert registry.get(code) is not None
    assert "ua" in registry.get(code).users


async def test_stale_disconnect_after_a_reconnect_is_ignored(make):
    handlers, _server, registry, _service = make(reconnect_grace=0.02)
    code = await _create(handlers, "sa", "ua", "Alice")
    # A new socket for the same identity takes over before the old one closes.
    await handlers.join_room("sa2", {"room": code, "uuid": "ua", "name": "Alice"})

    await handlers.disconnect("sa")  # stale close from the superseded socket
    await asyncio.sleep(0.05)

    assert registry.get(code) is not None
    assert "ua" in registry.get(code).users


async def test_unload_signal_clears_fast_while_a_bare_drop_holds_the_seat(make):
    # A signalled page unload (tab close/refresh) clears on the short window; a
    # bare drop with no signal holds the seat for the longer reconnect grace.
    handlers, _server, registry, _service = make(unload_grace=0.02, reconnect_grace=5.0)
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})

    await handlers.leaving("sa")  # Alice's page signals it is unloading...
    await handlers.disconnect("sa")  # ...then the socket closes
    await handlers.disconnect("sb")  # Bob just drops — no signal
    await asyncio.sleep(0.05)

    room = registry.get(code)
    assert room is not None and "ua" not in room.users  # unload cleared fast
    assert "ub" in room.users  # bare drop still holds the seat


async def test_a_reclaim_clears_the_unload_mark(make):
    # A refresh signals unload then reconnects; the reclaim must clear the mark so
    # a later ordinary drop still gets the full grace.
    handlers, _server, registry, _service = make(unload_grace=0.02, reconnect_grace=5.0)
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.leaving("sa")
    await handlers.join_room("sa2", {"room": code, "uuid": "ua", "name": "Alice"})
    await handlers.disconnect("sa2")  # a fresh, unsignalled drop
    await asyncio.sleep(0.05)

    assert registry.get(code) is not None  # held on the long grace, not cleared fast


async def test_joining_a_live_round_gets_a_game_snapshot(make):
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")
    await handlers.set_ready("sa", {"ready": True})
    await handlers.start_game("sa")

    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})

    snapshots = [
        (data, target)
        for name, data, target in server.emits
        if name == "game_events" and data and data[0]["type"] == "game_snapshot"
    ]
    assert len(snapshots) == 1
    data, target = snapshots[0]
    assert target == "sb"  # to the joining socket only, not a room broadcast
    assert data[0]["active_player"]["name"] == "Alice"


async def test_lobby_join_gets_no_snapshot(make):
    handlers, server, _registry, _service = make()
    code = await _create(handlers, "sa", "ua", "Alice")

    await handlers.join_room("sb", {"room": code, "uuid": "ub", "name": "Bob"})

    assert "game_snapshot" not in server.game_event_types()


# --- acting before joining ---------------------------------------------------


@pytest.mark.parametrize(
    "action",
    ["set_ready", "return_to_lobby", "configure_room", "start_game", "submit_guess", "stop_game"],
)
async def test_actions_before_joining_are_rejected(make, action):
    handlers, _server, _registry, _service = make()

    ack = await getattr(handlers, action)("ghost", {})

    assert ack == {"ok": False, "error": "not_in_room"}
