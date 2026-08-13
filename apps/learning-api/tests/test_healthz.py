from datetime import UTC, datetime

from fastapi import status
from fastapi.testclient import TestClient
from intellichoice_shared.bedrock import BedrockGatewayError
from learning_api.main import app

TEST_ROUTE = "/_test/gateway-error"


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


def test_an_unhandled_gateway_error_becomes_a_503_with_a_student_safe_detail() -> None:
    """learning-api had no exception handler at all, which is the same structural gap
    AUD-C-07 recorded for chat-api - and this app has far more Bedrock call sites.

    Two consequences, both invisible from inside the app: uvicorn's default 500 prints a
    traceback *outside* `JsonLogFormatter`, so the line carries no `trace_id` and cannot be
    joined to its X-Ray span or LangSmith run; and the response is raised outside
    `CORSMiddleware`, so a browser sees an opaque `net::ERR_FAILED` rather than a status.

    Registered on the real `app` and torn down after, so this asserts the shipped wiring
    rather than a copy of it - the same shape as chat-api's test of the same handler.

    Asserts the *register* too, not only the status: this text reaches a K-12 student, so it
    must not leak `str(exc)` and must say the thing that is actually true and useful (the work
    is saved, because answers commit per submission and the session resumes from the
    checkpoint).
    """

    @app.get(TEST_ROUTE)
    async def _boom() -> None:
        raise BedrockGatewayError("titan is out", cost_cents=0.0)

    try:
        response = TestClient(app, raise_server_exceptions=False).get(TEST_ROUTE)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        detail = response.json()["detail"]
        assert "titan is out" not in detail
        assert "Your work is saved" in detail
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", None) != TEST_ROUTE
        ]
