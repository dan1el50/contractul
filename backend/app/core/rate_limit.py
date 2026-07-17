"""In-process rate limiting.

A defence against brute force and abuse that needs no external service. The
limiter is a Protocol so it can be swapped for a shared store the day a second
backend worker exists — nothing above this module changes when that happens.

**Scope, stated plainly.** This counter lives in one process's memory. With a
single Uvicorn worker — our deployment today — it is authoritative. Run N
workers and each keeps its own count, so the effective limit becomes N times
the configured one. That ceiling is documented, not silent: the fix is a
shared backend (Redis) behind this same Protocol, and it is the reason the
Protocol exists before we need it.

The algorithm is a sliding window log: every accepted hit records its instant,
and a request is allowed only if fewer than `limit` hits fall inside the
trailing `window`. Unlike a fixed window it has no boundary burst — you cannot
spend the whole budget at 11:59:59 and the whole budget again at 12:00:00.
"""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitResult:
    """The verdict for one attempt against a key."""

    allowed: bool
    #: Seconds until an attempt on this key would next be allowed. Zero when
    #: allowed. Meant for a Retry-After header, so the caller rounds up.
    retry_after: float


class RateLimiter(Protocol):
    """A counter keyed by an opaque string.

    The key carries all the identity a limiter needs — scope and client, joined
    by the caller. The limiter neither parses nor trusts it.
    """

    def hit(self, key: str, *, limit: int, window_seconds: float) -> RateLimitResult:
        """Record an attempt and report whether it is within the limit.

        A rejected attempt is *not* recorded: being refused must not push the
        next allowed moment further away, or a client hammering a blocked
        endpoint would never recover.
        """
        ...


class InMemoryRateLimiter:
    """A sliding-window limiter backed by a dict of timestamp deques.

    Thread-safety is by the event loop, not a lock: `hit` contains no `await`,
    so under asyncio it runs to completion before any other coroutine observes
    the dict. Moving this off a single event loop would require a real lock.
    """

    #: How often the idle-key sweep runs. Keys are only touched on access, so
    #: without it a process that saw a million distinct IPs would hold a million
    #: empty deques forever.
    _SWEEP_INTERVAL_SECONDS = 60.0

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        # Monotonic, not wall-clock: windows must not shift when the system
        # clock is stepped by NTP. The clock is injectable so tests can advance
        # time without sleeping.
        self._clock = clock
        self._buckets: dict[str, deque[float]] = {}
        # The largest window any caller has asked about. The sweep prunes every
        # key against it, which can never drop a timestamp a smaller-window key
        # still cares about.
        self._max_window = 0.0
        self._next_sweep = clock() + self._SWEEP_INTERVAL_SECONDS

    def hit(self, key: str, *, limit: int, window_seconds: float) -> RateLimitResult:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        now = self._clock()
        self._max_window = max(self._max_window, window_seconds)
        self._maybe_sweep(now)

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = self._buckets[key] = deque()

        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            # The oldest hit in the window is what has to age out before there
            # is room again.
            retry_after = (bucket[0] + window_seconds) - now
            return RateLimitResult(allowed=False, retry_after=max(retry_after, 0.0))

        bucket.append(now)
        return RateLimitResult(allowed=True, retry_after=0.0)

    def reset(self) -> None:
        """Forget every key. Used between tests; not part of the Protocol."""
        self._buckets.clear()
        self._max_window = 0.0
        self._next_sweep = self._clock() + self._SWEEP_INTERVAL_SECONDS

    def _maybe_sweep(self, now: float) -> None:
        if now < self._next_sweep:
            return
        self._next_sweep = now + self._SWEEP_INTERVAL_SECONDS

        # A key whose newest hit predates the horizon has nothing left inside
        # any window we serve, so the whole deque is dead weight.
        horizon = now - self._max_window
        dead = [key for key, bucket in self._buckets.items() if not bucket or bucket[-1] <= horizon]
        for key in dead:
            del self._buckets[key]
