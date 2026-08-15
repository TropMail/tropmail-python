"""Client-side token bucket that paces requests to the server's advertised budget."""

from __future__ import annotations

import asyncio
import threading
import time


class TokenBucket:
    """Paces requests to at most ``rate`` per second.

    The bucket stays inert until the first ``X-RateLimit-Limit`` header is observed,
    so the very first request is never delayed. Once the tier budget is known,
    callers are spaced out just enough to avoid tripping the server's 1-second
    sliding window.
    """

    def __init__(self) -> None:
        self._rate: float | None = None
        self._tokens = 0.0
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    @property
    def rate(self) -> float | None:
        return self._rate

    def observe_limit(self, limit: int) -> None:
        """Size the bucket from a server-advertised per-second limit."""
        if limit <= 0:
            return
        with self._lock:
            if self._rate == float(limit):
                return
            self._rate = float(limit)
            self._tokens = float(limit)
            self._updated = time.monotonic()

    def _reserve(self) -> float:
        """Consume a token, returning how long the caller must wait first."""
        with self._lock:
            rate = self._rate
            if rate is None:
                return 0.0
            now = time.monotonic()
            self._tokens = min(rate, self._tokens + (now - self._updated) * rate)
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return 0.0
            deficit = 1.0 - self._tokens
            self._tokens = 0.0
            return deficit / rate

    def acquire(self) -> None:
        delay = self._reserve()
        if delay > 0:
            time.sleep(delay)

    async def acquire_async(self) -> None:
        delay = self._reserve()
        if delay > 0:
            await asyncio.sleep(delay)
