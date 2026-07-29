from datetime import UTC, datetime

from fastapi.testclient import TestClient
from learning_api.main import app


def test_healthz_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "dev"


def test_healthz_carries_build_identity() -> None:
    """AUD-F-16: a run has to be able to say what version answered it.

    The e2e harness reads exactly these fields to decide whether a reused `uvicorn`
    process predates the checkout it is supposed to be testing. Asserted here rather
    than only in the harness because the harness cannot fail informatively on a field
    that silently disappears - it would report "stale server" for a shape change.
    """
    response = TestClient(app).get("/healthz")
    body = response.json()

    # "unknown" outside a built image; a real SHA is injected by the Dockerfile's ARG.
    assert body["build_sha"] == "unknown"
    # Parses as an aware timestamp, in the past, and not absurdly so.
    started_at = datetime.fromisoformat(body["started_at"])
    assert started_at.tzinfo is not None
    assert started_at <= datetime.now(UTC)
    assert body["uptime_seconds"] >= 0
