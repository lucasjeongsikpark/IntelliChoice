"""D-087: `InMemoryRateLimiter` (moved here from chat-api in S33, now shared) and the
global per-IP FastAPI middleware built on top of it. AUD-C-27 made `allow` async so a
shared-store implementation fits the same seam, and added `hash_caller_key`.
"""

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_shared.rate_limit import (
    InMemoryRateLimiter,
    hash_caller_key,
    install_global_rate_limit_middleware,
)


def test_limiter_allows_up_to_the_window_max() -> None:
    async def run() -> None:
        limiter = InMemoryRateLimiter(max_per_window=3, window_s=60.0)
        assert await limiter.allow("k") is True
        assert await limiter.allow("k") is True
        assert await limiter.allow("k") is True
        assert await limiter.allow("k") is False

    asyncio.run(run())


def test_limiter_tracks_keys_independently() -> None:
    async def run() -> None:
        limiter = InMemoryRateLimiter(max_per_window=1, window_s=60.0)
        assert await limiter.allow("a") is True
        assert await limiter.allow("b") is True
        assert await limiter.allow("a") is False
        assert await limiter.allow("b") is False

    asyncio.run(run())


def test_two_in_memory_limiters_do_not_share_a_quota() -> None:
    """AUD-C-27's defect, pinned rather than fixed here - this class is per-process on
    purpose and the global per-IP cap still uses it. The test exists so the property is
    stated somewhere: two instances (i.e. two ECS tasks) each grant the full cap, which is
    why anything whose ceiling is a promise uses the Postgres implementation instead. The
    matching positive assertion is
    `packages/db/tests/test_rate_limit_repository.py::test_the_cap_is_shared_across_repository_instances`.
    """

    async def run() -> None:
        first = InMemoryRateLimiter(max_per_window=1, window_s=60.0)
        second = InMemoryRateLimiter(max_per_window=1, window_s=60.0)
        assert await first.allow("same-caller") is True
        assert await first.allow("same-caller") is False
        # A second process has never heard of this caller.
        assert await second.allow("same-caller") is True

    asyncio.run(run())


def test_hash_caller_key_is_stable_secret_dependent_and_never_the_key() -> None:
    """The three properties the storage promise rests on: the same caller counts against
    the same row, a different caller does not, and the stored value does not contain the
    IP it was derived from.
    """
    ip = "203.0.113.7"
    digest = hash_caller_key(ip, secret="s3cret")

    assert digest == hash_caller_key(ip, secret="s3cret")
    assert digest != hash_caller_key("203.0.113.8", secret="s3cret")
    # Rotating the secret changes the key, which resets counters - documented, bounded.
    assert digest != hash_caller_key(ip, secret="other")
    assert ip not in digest
    # Domain separation: a rate-limit hash must not be derivable as a plain HMAC of the
    # key, or it could collide with another use of the same secret.
    import hashlib
    import hmac

    assert digest != hmac.new(b"s3cret", ip.encode(), hashlib.sha256).hexdigest()


def _build_app(*, max_per_window: int, window_s: float = 60.0) -> FastAPI:
    app = FastAPI()

    @app.get("/thing")
    async def thing() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/healthz")
    async def healthz() -> dict[str, bool]:
        return {"ok": True}

    install_global_rate_limit_middleware(app, max_per_window=max_per_window, window_s=window_s)
    return app


def test_middleware_returns_429_after_the_cap_and_sets_retry_after() -> None:
    client = TestClient(_build_app(max_per_window=2))
    assert client.get("/thing").status_code == 200
    assert client.get("/thing").status_code == 200
    resp = client.get("/thing")
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "60"


def test_middleware_exempts_healthz_from_the_cap() -> None:
    client = TestClient(_build_app(max_per_window=1))
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").status_code == 200
    # The one non-exempt route still enforces the cap independently.
    assert client.get("/thing").status_code == 200
    assert client.get("/thing").status_code == 429
