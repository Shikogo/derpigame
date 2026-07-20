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


async def test_remaining_counts_down_while_armed():
    timer = TurnTimer()
    assert timer.remaining is None  # nothing armed yet
    timer.arm(10.0, lambda: _append([], "x"))
    first = timer.remaining
    assert 9.0 < first <= 10.0
    await asyncio.sleep(0.02)
    assert timer.remaining < first
    timer.cancel()
    assert timer.remaining is None


async def test_rearm_refills_remaining():
    timer = TurnTimer()
    timer.arm(1.0, lambda: _append([], "x"))
    await asyncio.sleep(0.02)
    timer.arm(10.0, lambda: _append([], "y"))
    assert timer.remaining > 9.0
    timer.cancel()


async def test_rearm_supersedes_the_previous_timer():
    fired: list[str] = []
    timer = TurnTimer()
    timer.arm(0.02, lambda: _append(fired, "first"))
    timer.arm(0.02, lambda: _append(fired, "second"))
    await asyncio.sleep(0.05)
    assert fired == ["second"]  # the first never fires
