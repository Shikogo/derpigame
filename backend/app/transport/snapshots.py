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
        "source": room.source,
        "min_tag_count": room.min_tag_count,
        "min_score": room.min_score,
        "rating_caps": dict(room.rating_caps),
        "in_progress": room.active,
        "users": [
            {
                "uuid": user.uuid,
                "name": user.name,
                "ready": user.ready,
                "viewing_results": user.viewing_results,
            }
            for user in room.users.values()
        ],
    }
