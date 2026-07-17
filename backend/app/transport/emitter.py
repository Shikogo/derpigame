"""The real ``EventEmitter``: pushes serialized game events over Socket.IO.

Room-wide game state travels on the ``game_events`` channel, one batched list of
typed payloads per action. This is the only line that turns the service's
outbound abstraction into an actual socket emit.
"""

from app.service.emitter import EventEmitter


class SocketIOEmitter(EventEmitter):
    def __init__(self, sio):
        self._sio = sio

    async def emit(self, room_name: str, payloads: list[dict]) -> None:
        await self._sio.emit("game_events", payloads, room=room_name)
