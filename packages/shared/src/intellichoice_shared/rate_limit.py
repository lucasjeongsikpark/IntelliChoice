"""In-memory sliding-window rate limiter (SPEC §5.24.2 "IP and user rate limiting").
Single-process, in-memory - same posture as `session_events.ChatSessionEventBus` (D-032):
sufficient for each app's one-task/one-Uvicorn-worker staging footprint (`desired_count`
defaults to 1, D-084); a real multi-worker/multi-task deployment would need a shared
store (Redis) behind the same interface, not a rewrite of the caller. Originally
chat-api-only, scoped to the admin-escalation send (SPEC §5.24.2's specific anonymous-
abuse concern) - moved here in S33 (D-087) alongside a second, general-purpose use: a
global per-IP request cap on both apps, a stopgap against gross traffic/cost abuse until
a real WAF exists (SPEC §6.22 lists both separately; no AWS WAF this session - see
DECISIONS.md).
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from starlette import status


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


def install_global_rate_limit_middleware(
    app: FastAPI,
    *,
    max_per_window: int,
    window_s: float,
    exempt_paths: frozenset[str] = frozenset({"/healthz", "/metrics"}),
) -> None:
    """Keyed by client IP (`request.client.host`) - requires the ALB-facing Dockerfile
    CMD to pass Uvicorn `--proxy-headers --forwarded-allow-ips`, or every real request
    behind the ALB collapses onto the same key (the ALB's own address, not the caller's)
    - see the Dockerfile comment. `exempt_paths` defaults to health/metrics endpoints,
    which real infrastructure (ALB health checks, a Prometheus scraper) polls on its own
    fixed schedule and which carry no per-caller abuse risk.
    """
    limiter = InMemoryRateLimiter(max_per_window=max_per_window, window_s=window_s)

    @app.middleware("http")
    async def _rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in exempt_paths:
            return await call_next(request)
        key = request.client.host if request.client else "unknown"
        if not limiter.allow(key):
            return Response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(int(window_s))},
            )
        return await call_next(request)
