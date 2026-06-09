"""Per-IP fixed-window rate limiter (architecture.md §7, qa.md §9).

Two buckets per IP: questions (30/hour) and ingests (10/hour). The window is a
wall-clock hour; counters live in memory and reset on instance restart (acceptable
at MVP, single Replit instance). The limiter exposes remaining quota on every
response and raises on a hit; the UI warns as the limit approaches rather than the
backend blocking early.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

QUESTIONS = "questions"
INGESTS = "ingests"
_LIMITS = {QUESTIONS: 30, INGESTS: 10}
_WINDOW_SECONDS = 3600
PROXIMITY_THRESHOLD = 5  # UI warns when remaining <= this (qa.md §9)


class RateLimitExceeded(Exception):
    """Raised when a bucket is over its limit for the current window."""

    def __init__(self, bucket: str, window_reset: str):
        self.bucket = bucket
        self.window_reset = window_reset
        super().__init__(
            f"Rate limit reached for {bucket}. Try again after {window_reset}."
        )


def _window_start(now: float) -> int:
    return int(now) // _WINDOW_SECONDS * _WINDOW_SECONDS


def _window_reset_iso(window_start: int) -> str:
    reset = datetime.fromtimestamp(window_start + _WINDOW_SECONDS, tz=timezone.utc)
    return reset.isoformat()


class FixedWindowLimiter:
    def __init__(self):
        self._counts: dict[tuple[str, str, int], int] = {}
        self._lock = threading.Lock()

    def _count(self, ip: str, bucket: str, window: int) -> int:
        return self._counts.get((ip, bucket, window), 0)

    def consume(self, ip: str, bucket: str, now: float | None = None) -> None:
        """Consume one unit from the bucket; raise if it would exceed the limit.

        Checks before consuming so a hit does no work and incurs no bill.
        """
        now = time.time() if now is None else now
        window = _window_start(now)
        limit = _LIMITS[bucket]
        with self._lock:
            current = self._count(ip, bucket, window)
            if current >= limit:
                raise RateLimitExceeded(bucket, _window_reset_iso(window))
            self._counts[(ip, bucket, window)] = current + 1

    def quota(self, ip: str, now: float | None = None) -> dict:
        """Remaining counts for both buckets plus the window reset time."""
        now = time.time() if now is None else now
        window = _window_start(now)
        with self._lock:
            q_used = self._count(ip, QUESTIONS, window)
            i_used = self._count(ip, INGESTS, window)
        return {
            "questions_remaining": max(0, _LIMITS[QUESTIONS] - q_used),
            "ingests_remaining": max(0, _LIMITS[INGESTS] - i_used),
            "window_reset": _window_reset_iso(window),
        }


# Module-level singleton, shared by the ask and ingest routes (qa.md §9).
limiter = FixedWindowLimiter()
