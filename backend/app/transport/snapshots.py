"""Compose the ``room_state`` lobby snapshot from a domain ``Room``.

Membership, readiness, and config aren't game rules, so the domain emits no
events for them; the transport builds this whole-snapshot view and rebroadcasts
it on any lobby change. Game state travels separately as ``game_events``.
"""

from app.domain.room import Room


def room_state(room: Room) -> dict:
    return {
        "room": room.name,
        "query": list(room.query),
        "nsfw": room.nsfw,
        "in_progress": room.active,
        "users": [
            {"uuid": user.uuid, "name": user.name, "ready": user.ready}
            for user in room.users.values()
        ],
    }
