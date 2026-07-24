"""D-087: `InMemoryRateLimiter` (moved here from chat-api in S33, now shared) and the
new global per-IP FastAPI middleware built on top of it.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from intellichoice_shared.rate_limit import (
    InMemoryRateLimiter,
    install_global_rate_limit_middleware,
)


def test_limiter_allows_up_to_the_window_max() -> None:
    limiter = InMemoryRateLimiter(max_per_window=3, window_s=60.0)
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False


def test_limiter_tracks_keys_independently() -> None:
    limiter = InMemoryRateLimiter(max_per_window=1, window_s=60.0)
    assert limiter.allow("a") is True
    assert limiter.allow("b") is True
    assert limiter.allow("a") is False
    assert limiter.allow("b") is False


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
