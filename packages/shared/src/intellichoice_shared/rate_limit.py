"""Sliding-window rate limiters (SPEC §5.24.2 "IP and user rate limiting").

Two limiters, and after AUD-C-27 they no longer share a storage posture, because they
never shared a *purpose*:

- the **admin-escalation cap** (5/hour/caller) is a security control on an anonymous
  caller's ability to reach a human, so its number has to mean what it says. It runs on
  a shared store - see `chat_api.services.escalation_rate_limit`, which implements
  `RateLimiter` over Postgres.
- the **global per-IP request cap** (`install_global_rate_limit_middleware`, 6000/min)
  is a deliberately generous stopgap against gross traffic/cost abuse until a real WAF
  exists (SPEC §6.22; AWS WAF is dispositioned to S50 A7). It stays in-process and
  per-task on purpose: a database round-trip on *every* request would cost more than the
  imprecision it removes.

**⚠️ `InMemoryRateLimiter` counts per process, and a process is one ECS task.** Uvicorn
runs a single worker in both Dockerfiles, so the effective ceiling is
`max_per_window × running task count` for any caller whose requests the ALB spreads
across tasks - there is no target-group stickiness. This used to be documented as
"sufficient for each app's one-task footprint (`desired_count` defaults to 1, D-084)",
which stopped being true when autoscaling landed: `autoscaling_min_capacity` is 2 for
learning-api and 1 for chat-api, with `max_capacity` 3. AUD-C-27 measured the
consequence on the deployed escalation cap - **8 drafts accepted from one IP against a
configured 5** - which is why that limiter moved and this docstring changed. Anything
whose number is a promise rather than a bound must not use this class.
"""

import hashlib
import hmac
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

from fastapi import FastAPI, Request, Response
from starlette import status


class RateLimiter(Protocol):
    """`allow` is async so a shared-store implementation fits the same seam as the
    in-memory one (D-002's interface-plus-fake pattern). Callers await it; whether that
    await touches a database is the implementation's business.
    """

    async def allow(self, key: str) -> bool: ...


def hash_caller_key(key: str, *, secret: str) -> str:
    """Derive the storage key for a rate-limit counter. **Never store `key` itself.**

    A rate-limit key is a caller external id or, for an anonymous caller, a client IP.
    An IP is identifying, and SPEC §5.30 keeps identifying values out of Postgres, which
    holds only `*_external_id` references. Before AUD-C-27 no client IP was persisted
    anywhere; this keeps that true by storing an HMAC instead of the value.

    HMAC rather than a bare `sha256`: an unsalted digest of an IPv4 address is reversible
    by exhausting 2^32 candidates, so it would be obfuscation rather than protection. The
    secret is the app's own signing secret with a domain-separation prefix, so no new
    secret and no Terraform change is needed, and a rate-limit hash can never collide
    with a token signature. Rotating that secret resets the counters, which for a 1-hour
    window is an acceptable, bounded effect.
    """
    return hmac.new(
        secret.encode(), b"rate-limit-caller-key-v1|" + key.encode(), hashlib.sha256
    ).hexdigest()


class InMemoryRateLimiter:
    """Per-process sliding window. Read the module docstring's warning before using it
    for anything whose ceiling is a promise - it is the dev fake for `RateLimiter` and
    the real implementation of the global per-IP cap, and those are different claims.
    """

    def __init__(self, *, max_per_window: int, window_s: float) -> None:
        self._max_per_window = max_per_window
        self._window_s = window_s
        self._calls_by_key: dict[str, list[float]] = {}

    async def allow(self, key: str) -> bool:
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

    Per-task by design (AUD-C-27) - see the module docstring. The real ceiling a single
    source IP sees is `max_per_window × running tasks`, and 6000 was chosen as "roughly 3x
    a measured legitimate burst" rather than as a precise abuse threshold, so the
    multiplier makes it more generous without making it wrong. The precise control is the
    WAF (S50 A7). The escalation cap could not accept that trade and moved to a shared
    store.
    """
    limiter = InMemoryRateLimiter(max_per_window=max_per_window, window_s=window_s)

    @app.middleware("http")
    async def _rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in exempt_paths:
            return await call_next(request)
        key = request.client.host if request.client else "unknown"
        if not await limiter.allow(key):
            return Response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(int(window_s))},
            )
        return await call_next(request)
