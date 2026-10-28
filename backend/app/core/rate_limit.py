"""In-memory sliding-window rate limiter.

Single-process only: limits reset on restart and are not shared between workers. That fits
the lab deployment (one API process); see the threat model's residual risks.
"""

import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowLimiter:
    def __init__(
        self, max_events: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events.setdefault(key, deque())
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        return events

    def allow(self, key: str) -> bool:
        """Record an event for ``key``; False if the limit for the window is exceeded."""
        with self._lock:
            now = self._clock()
            events = self._prune(key, now)
            if len(events) >= self.max_events:
                return False
            events.append(now)
            return True

    def retry_after(self, key: str) -> int:
        with self._lock:
            now = self._clock()
            events = self._prune(key, now)
            if len(events) < self.max_events:
                return 0
            return max(1, int(self.window_seconds - (now - events[0])) + 1)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)
