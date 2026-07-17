"""The in-memory rate limiter, in isolation.

No database, no HTTP, no real time — the clock is injected so a "5-minute
window" test runs in microseconds and never flakes on a slow machine.
"""

import pytest

from app.core.rate_limit import InMemoryRateLimiter


class FakeClock:
    """A clock the test advances by hand."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_up_to_the_limit_then_blocks() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    for _ in range(3):
        assert limiter.hit("k", limit=3, window_seconds=60).allowed is True

    assert limiter.hit("k", limit=3, window_seconds=60).allowed is False


def test_a_blocked_attempt_is_not_counted() -> None:
    """Being refused must not push the recovery time further out.

    If rejected hits were recorded, a client hammering a blocked key would
    keep resetting its own window and never be let back in.
    """
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    assert limiter.hit("k", limit=1, window_seconds=60).allowed is True
    # Two refusals 30s apart. The window still clears 60s after the ONE
    # accepted hit, not 60s after the last refusal.
    assert limiter.hit("k", limit=1, window_seconds=60).allowed is False
    clock.advance(30)
    assert limiter.hit("k", limit=1, window_seconds=60).allowed is False
    clock.advance(31)  # 61s past the accepted hit
    assert limiter.hit("k", limit=1, window_seconds=60).allowed is True


def test_the_window_slides() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    assert limiter.hit("k", limit=2, window_seconds=60).allowed is True
    clock.advance(30)
    assert limiter.hit("k", limit=2, window_seconds=60).allowed is True
    assert limiter.hit("k", limit=2, window_seconds=60).allowed is False

    # 31s later the first hit (now 61s old) has aged out; one slot frees up,
    # but the second hit (31s old) is still inside the window.
    clock.advance(31)
    assert limiter.hit("k", limit=2, window_seconds=60).allowed is True
    assert limiter.hit("k", limit=2, window_seconds=60).allowed is False


def test_no_boundary_burst() -> None:
    """Slots come back one at a time, not all at once.

    A fixed window resets its whole count at a boundary, so a client can spend
    the full budget just before it and again just after — a 2x burst. A sliding
    window expires each hit exactly one window after *its own* time, so budget
    spread across the window is returned staggered, never in a lump.
    """
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    # Five hits, one every 10s, filling a budget of 5 over a 60s window.
    for _ in range(5):
        assert limiter.hit("k", limit=5, window_seconds=60).allowed is True
        clock.advance(10)

    # Now at t+50, budget is full and the next is refused.
    assert limiter.hit("k", limit=5, window_seconds=60).allowed is False

    # At t+60 only the first hit (60s old) has aged out — exactly one slot, not
    # five. Take it, and the sixth is refused again.
    clock.advance(10)
    assert limiter.hit("k", limit=5, window_seconds=60).allowed is True
    assert limiter.hit("k", limit=5, window_seconds=60).allowed is False


def test_keys_are_independent() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    assert limiter.hit("a", limit=1, window_seconds=60).allowed is True
    assert limiter.hit("a", limit=1, window_seconds=60).allowed is False
    # A different key has its own untouched budget.
    assert limiter.hit("b", limit=1, window_seconds=60).allowed is True


def test_retry_after_reports_when_the_oldest_hit_expires() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    limiter.hit("k", limit=1, window_seconds=60)
    clock.advance(20)
    result = limiter.hit("k", limit=1, window_seconds=60)

    assert result.allowed is False
    # The one hit is 20s old; 40s remain until the 60s window clears it.
    assert result.retry_after == pytest.approx(40.0)


def test_retry_after_is_zero_when_allowed() -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock())
    assert limiter.hit("k", limit=2, window_seconds=60).retry_after == 0.0


def test_reset_forgets_every_key() -> None:
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    limiter.hit("k", limit=1, window_seconds=60)
    assert limiter.hit("k", limit=1, window_seconds=60).allowed is False

    limiter.reset()
    assert limiter.hit("k", limit=1, window_seconds=60).allowed is True


def test_idle_keys_are_swept() -> None:
    """Memory does not grow without bound for keys that never return."""
    clock = FakeClock()
    limiter = InMemoryRateLimiter(clock=clock)

    limiter.hit("gone", limit=1, window_seconds=60)
    assert "gone" in limiter._buckets

    # Past the window and past the sweep interval, a hit on a different key
    # triggers the sweep, which drops the stale one.
    clock.advance(120)
    limiter.hit("other", limit=1, window_seconds=60)

    assert "gone" not in limiter._buckets
    assert "other" in limiter._buckets


@pytest.mark.parametrize(
    ("limit", "window"),
    [(0, 60), (-1, 60), (1, 0), (1, -5)],
)
def test_rejects_nonsensical_configuration(limit: int, window: float) -> None:
    limiter = InMemoryRateLimiter(clock=FakeClock())
    with pytest.raises(ValueError):
        limiter.hit("k", limit=limit, window_seconds=window)
