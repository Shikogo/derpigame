"""A single pending timeout for the active turn, on the asyncio event loop.

This is the piece that structurally removes the legacy timer race. Legacy ran
the turn timer on a background thread while guesses arrived on another, so a
guess and a timeout could both advance the same turn. Here everything runs on
one event loop: guesses and timeouts are serialized by the loop, no locks.

Arming replaces any previous timer. A *superseded* timer — one whose sleep
already elapsed, but a guess advanced the turn before its callback got to run —
is suppressed by a generation check, so a stale timeout can never fire against
the wrong turn.
"""

import asyncio
from collections.abc import Awaitable, Callable


class TurnTimer:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._generation = 0
        self._deadline: float | None = None

    def arm(self, delay: float, callback: Callable[[], Awaitable[None]]) -> None:
        """Fire ``callback`` after ``delay`` seconds, cancelling any prior timer."""
        self._cancel_task()
        self._generation += 1
        generation = self._generation
        self._deadline = asyncio.get_running_loop().time() + delay
        self._task = asyncio.create_task(self._run(delay, callback, generation))

    @property
    def remaining(self) -> float | None:
        """Seconds left on the armed turn, or ``None`` when no timer is pending."""
        if self._deadline is None:
            return None
        return max(0.0, self._deadline - asyncio.get_running_loop().time())

    def cancel(self) -> None:
        """Stop the pending timer; a fire already in flight is invalidated too."""
        self._cancel_task()
        self._generation += 1
        self._deadline = None

    def _cancel_task(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(
        self, delay: float, callback: Callable[[], Awaitable[None]], generation: int
    ) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            return
        self._task = None
        if generation != self._generation:
            return  # a newer turn superseded this timer while it was pending
        await callback()
