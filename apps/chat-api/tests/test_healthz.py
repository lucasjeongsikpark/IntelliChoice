from datetime import UTC, datetime

from chat_api.main import app
from fastapi.testclient import TestClient


def test_healthz_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "dev"


def test_healthz_carries_build_identity() -> None:
    """AUD-F-16 - see the matching test in apps/learning-api/tests/test_healthz.py."""
    response = TestClient(app).get("/healthz")
    body = response.json()

    assert body["build_sha"] == "unknown"
    started_at = datetime.fromisoformat(body["started_at"])
    assert started_at.tzinfo is not None
    assert started_at <= datetime.now(UTC)
    assert body["uptime_seconds"] >= 0
