"""The asyncio turn timer: fires once, cancels cleanly, re-arm supersedes."""

import asyncio

from app.service.turn_timer import TurnTimer


async def _append(sink: list, value: str) -> None:
    sink.append(value)


async def test_arm_fires_callback_after_delay():
    fired: list[str] = []
    timer = TurnTimer()
    timer.arm(0.01, lambda: _append(fired, "x"))
    await asyncio.sleep(0.03)
    assert fired == ["x"]


async def test_cancel_prevents_firing():
    fired: list[str] = []
    timer = TurnTimer()
    timer.arm(0.02, lambda: _append(fired, "x"))
    timer.cancel()
    await asyncio.sleep(0.04)
    assert fired == []


async def test_rearm_supersedes_the_previous_timer():
    fired: list[str] = []
    timer = TurnTimer()
    timer.arm(0.02, lambda: _append(fired, "first"))
    timer.arm(0.02, lambda: _append(fired, "second"))
    await asyncio.sleep(0.05)
    assert fired == ["second"]  # the first never fires
