"""Outbound channel for delivering events to the players in a room.

The orchestration service depends only on this interface, never on socketio, so
it stays testable with a recording double. The transport layer provides the real
implementation that pushes payloads over the websocket.
"""

from abc import ABC, abstractmethod


class EventEmitter(ABC):
    @abstractmethod
    async def emit(self, room_name: str, payloads: list[dict]) -> None:
        """Deliver already-serialized event payloads to everyone in a room.

        Payloads are sent in order; the transport decides message framing.
        """
