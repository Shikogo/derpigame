"""Socket.IO event handlers — the only place transport meets game actions.

Each handler resolves the caller's room from the socket session, calls
``GameService`` (game actions) or mutates the ``Room`` directly (lobby actions),
returns an ack dict to that one caller, and broadcasts ``room_state`` /
``game_events`` to the room as needed. No game logic lives here: the handlers
parse, dispatch, and translate — nothing more.
"""

import asyncio

from app.domain.user import User
from app.service.errors import GameActionError, NotYourTurn
from app.service.game_service import GameService
from app.transport.registry import RoomRegistry
from app.transport.room_codes import new_code
from app.transport.snapshots import room_state

_ALLOCATE_ATTEMPTS = 10  # fresh code draws before giving up (collisions are rare)
_RECONNECT_GRACE_SECONDS = 30.0  # keep a drained room this long for a reload/reconnect


def _ok(**extra) -> dict:
    return {"ok": True, **extra}


def _err(error: str, **extra) -> dict:
    return {"ok": False, "error": error, **extra}


def _parse_query(raw) -> list[str]:
    """Normalize a query payload (list, or newline/comma-separated string) to tags."""
    parts = raw.replace("\n", ",").split(",") if isinstance(raw, str) else list(raw)
    return [tag for tag in (str(part).strip() for part in parts) if tag]


MIN_TURN_SECONDS = 10.0
MAX_TURN_SECONDS = 300.0


def _parse_turn_seconds(raw) -> float | None:
    """Clamp a turn-length setting to whole seconds in range; None if unparseable."""
    try:
        return float(max(MIN_TURN_SECONDS, min(MAX_TURN_SECONDS, round(float(raw)))))
    except (TypeError, ValueError):
        return None


class SocketHandlers:
    def __init__(
        self,
        sio,
        registry: RoomRegistry,
        service: GameService,
        *,
        reconnect_grace: float = _RECONNECT_GRACE_SECONDS,
    ):
        self._sio = sio
        self._registry = registry
        self._service = service
        self._reconnect_grace = reconnect_grace
        self._owner: dict[str, str] = {}  # uuid -> the sid that currently holds it
        self._grace: dict[str, asyncio.Task] = {}  # uuid -> pending teardown

    def register(self) -> None:
        for event in (
            "connect", "disconnect", "create_room", "join_room", "set_ready",
            "configure_room", "start_game", "submit_guess", "stop_game",
            "leave_room", "chat",
        ):
            self._sio.on(event, getattr(self, event))

    # --- connection lifecycle -------------------------------------------------

    async def connect(self, sid, environ, auth=None):
        return None  # no auth yet (Phase 2); identity arrives with create/join

    async def disconnect(self, sid, *args):
        session = await self._session(sid)
        room_name, uuid = session.get("room"), session.get("uuid")
        if not room_name or not uuid:
            return
        if self._owner.get(uuid) != sid:
            return  # a newer socket already took over this identity; stale close
        self._schedule_teardown(sid, room_name, uuid)

    def shutdown(self) -> None:
        """Cancel pending reconnect grace timers (app shutdown / test cleanup)."""
        for task in self._grace.values():
            task.cancel()
        self._grace.clear()

    # --- room membership ------------------------------------------------------

    async def create_room(self, sid, data=None):
        data = data or {}
        name = str(data.get("name", "")).strip()
        uuid = str(data.get("uuid", "")).strip()
        if not name or not uuid:
            return _err("bad_request")

        room = self._allocate_room()
        if room is None:
            return _err("room_unavailable")
        if "nsfw" in data:
            room.nsfw = bool(data["nsfw"])
        if "query" in data:
            room.query = _parse_query(data["query"])

        return await self._join(sid, room, name, uuid)

    async def join_room(self, sid, data=None):
        data = data or {}
        code = str(data.get("room", "")).strip().lower()
        name = str(data.get("name", "")).strip()
        uuid = str(data.get("uuid", "")).strip()
        if not code or not name or not uuid:
            return _err("bad_request")

        room = self._registry.get(code)
        if room is None:
            return _err("room_not_found")
        return await self._join(sid, room, name, uuid)

    async def leave_room(self, sid, data=None):
        session = await self._session(sid)
        room_name = session.get("room")
        uuid = session.get("uuid")
        if room_name:
            await self._sio.leave_room(sid, room_name)
        await self._sio.save_session(sid, {})
        if uuid:  # an explicit leave is intentional — no reconnect grace
            self._cancel_grace(uuid)
            if self._owner.get(uuid) == sid:
                self._owner.pop(uuid, None)
        await self._remove_member(room_name, uuid)
        return _ok()

    async def set_ready(self, sid, data=None):
        resolved = await self._resolve(sid)
        if resolved is None:
            return _err("not_in_room")
        room, user = resolved
        user.ready = bool((data or {}).get("ready", False))
        await self._broadcast_state(room)
        return _ok()

    async def configure_room(self, sid, data=None):
        resolved = await self._resolve(sid)
        if resolved is None:
            return _err("not_in_room")
        room, _user = resolved
        if room.active:
            return _err("game_in_progress")
        data = data or {}
        if "query" in data:
            room.query = _parse_query(data["query"])
        if "nsfw" in data:
            room.nsfw = bool(data["nsfw"])
        if "turn_seconds" in data:
            seconds = _parse_turn_seconds(data["turn_seconds"])
            if seconds is not None:
                room.turn_seconds = seconds
        await self._broadcast_state(room)
        return _ok()

    # --- game actions ---------------------------------------------------------

    async def start_game(self, sid, data=None):
        resolved = await self._resolve(sid)
        if resolved is None:
            return _err("not_in_room")
        room, user = resolved
        if room.active:
            return _err("game_in_progress")
        if not user.ready:
            # Only a ready player may start; spectators just watch. A ready
            # caller also guarantees the round has at least one player.
            return _err("not_ready")
        await self._service.start_game(room)
        await self._broadcast_state(room)
        return _ok()

    async def submit_guess(self, sid, data=None):
        resolved = await self._resolve(sid)
        if resolved is None:
            return _err("not_in_room")
        room, user = resolved
        guess = str((data or {}).get("guess", ""))
        try:
            await self._service.submit_guess(room, user.uuid, guess)
        except NotYourTurn as exc:
            active = exc.active_player
            return _err(
                "not_your_turn",
                active_player={"uuid": active.uuid, "name": active.name},
            )
        except GameActionError as exc:
            return _err(str(exc))
        return _ok()

    async def stop_game(self, sid, data=None):
        resolved = await self._resolve(sid)
        if resolved is None:
            return _err("not_in_room")
        room, _user = resolved
        await self._service.stop_game(room)
        await self._broadcast_state(room)
        return _ok()

    async def chat(self, sid, data=None):
        session = await self._session(sid)
        room_name = session.get("room")
        if not room_name:
            return _err("not_in_room")
        text = str((data or {}).get("text", "")).strip()
        if not text:
            return _err("empty")
        await self._sio.emit(
            "chat", {"name": session.get("name"), "text": text}, room=room_name
        )
        return _ok()

    # --- helpers --------------------------------------------------------------

    async def _join(self, sid, room, name: str, uuid: str) -> dict:
        """Add or re-attach a user to a room, then broadcast and ack the roster.

        Any previous room is left only once this join is known to succeed, so a
        rejected join never strands the caller between rooms.
        """
        taken = any(
            user.uuid != uuid and user.name.casefold() == name.casefold()
            for user in room.users.values()
        )
        if taken:
            return _err("name_taken")

        await self._leave_if_switching(sid, room.name)
        user = room.get_user(uuid)
        if user is None:
            user = User(uuid, name)
            room.add_user(user)
        else:
            user.name = name
        user.ready = False

        await self._sio.save_session(
            sid, {"uuid": uuid, "room": room.name, "name": name}
        )
        await self._sio.enter_room(sid, room.name)
        self._owner[uuid] = sid
        self._cancel_grace(uuid)  # a reconnect cancels any pending teardown
        await self._broadcast_state(room)
        # Rejoin/late-join into a live round: hand this socket the game snapshot
        # so it renders the round in progress instead of a lobby-only view.
        snapshot = self._service.game_snapshot(room)
        if snapshot is not None:
            await self._sio.emit("game_events", [snapshot], to=sid)
        return _ok(room_state=self._state(room))

    def _allocate_room(self):
        for _ in range(_ALLOCATE_ATTEMPTS):
            room = self._registry.create(new_code())
            if room is not None:
                return room
        return None

    async def _session(self, sid) -> dict:
        try:
            return await self._sio.get_session(sid) or {}
        except KeyError:
            return {}

    async def _resolve(self, sid):
        """Return ``(room, user)`` for a joined socket, or ``None`` if unknown."""
        session = await self._session(sid)
        room_name, uuid = session.get("room"), session.get("uuid")
        if not room_name or not uuid:
            return None
        room = self._registry.get(room_name)
        if room is None:
            return None
        user = room.get_user(uuid)
        return (room, user) if user is not None else None

    def _state(self, room) -> dict:
        """The room snapshot plus service-owned extras: round history and win tally."""
        return {
            **room_state(room),
            "turn_seconds": self._service.turn_seconds_for(room),
            "history": self._service.room_history(room.name),
            "win_counts": self._service.room_win_counts(room.name),
        }

    async def _broadcast_state(self, room) -> None:
        await self._sio.emit("room_state", self._state(room), room=room.name)

    async def _leave_if_switching(self, sid, new_room: str) -> None:
        session = await self._session(sid)
        old_room = session.get("room")
        if old_room and old_room != new_room:
            await self._sio.leave_room(sid, old_room)
            await self._remove_member(old_room, session.get("uuid"))

    async def _remove_member(self, room_name, uuid) -> None:
        """Drop a user from a room; tear the room down once it's empty."""
        if not room_name or not uuid:
            return
        room = self._registry.get(room_name)
        if room is None:
            return
        room.remove_user(uuid)
        if room.users:
            await self._broadcast_state(room)
        else:
            self._service.cancel_room(room_name)
            self._registry.remove(room_name)

    def _schedule_teardown(self, sid: str, room_name: str, uuid: str) -> None:
        """After a disconnect, keep the room briefly so a reload can reclaim it."""
        self._cancel_grace(uuid)
        self._grace[uuid] = asyncio.create_task(
            self._drop_after_grace(sid, room_name, uuid)
        )

    def _cancel_grace(self, uuid: str) -> None:
        task = self._grace.pop(uuid, None)
        if task is not None:
            task.cancel()

    async def _drop_after_grace(self, sid: str, room_name: str, uuid: str) -> None:
        try:
            await asyncio.sleep(self._reconnect_grace)
        except asyncio.CancelledError:
            return  # reconnected within the window; keep the membership
        self._grace.pop(uuid, None)
        if self._owner.get(uuid) == sid:  # nobody reclaimed this identity
            self._owner.pop(uuid, None)
            await self._remove_member(room_name, uuid)
