"""In-memory sliding-window rate limiter (SPEC §5.24.2 "IP and user rate limiting").
Single-process, in-memory - same posture as `session_events.ChatSessionEventBus` (D-032):
sufficient for this app's one-Uvicorn-worker dev/test footprint; a real multi-worker
deployment would need a shared store (Redis) behind the same interface, not a rewrite of
the caller. Scoped to the admin-escalation send only, not every chat message - that's the
specific SPEC §5.24.2 anonymous-abuse concern, not general traffic shaping.
"""

import time


class InMemoryRateLimiter:
    def __init__(self, *, max_per_window: int, window_s: float) -> None:
        self._max_per_window = max_per_window
        self._window_s = window_s
        self._calls_by_key: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_s
        calls = [t for t in self._calls_by_key.get(key, []) if t > cutoff]
        if len(calls) >= self._max_per_window:
            self._calls_by_key[key] = calls
            return False
        calls.append(now)
        self._calls_by_key[key] = calls
        return True
