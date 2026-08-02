from datetime import UTC, datetime

from chat_api.graph.nodes import SERVICE_UNAVAILABLE_MESSAGE
from chat_api.main import app
from fastapi import status
from fastapi.testclient import TestClient
from intellichoice_shared.bedrock import BedrockGatewayError

TEST_ROUTE = "/_test/gateway-error"


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


def test_a_bedrock_gateway_error_becomes_a_503_not_a_500() -> None:
    """AUD-C-07's backstop. The finding's real fix is in the graph, but the reason an
    unguarded gateway call could 500 at all is that chat-api registered no exception
    handler - so the next gateway call anyone adds inherits the same defect, and the
    browser sees an opaque `net::ERR_FAILED` instead of a status (AUD-F-16's CORS half).

    Registered on the real `app`, torn down after, so this asserts the shipped wiring
    rather than a copy of it.
    """

    @app.get(TEST_ROUTE)
    async def _boom() -> None:
        raise BedrockGatewayError("titan is out", cost_cents=0.0)

    try:
        response = TestClient(app, raise_server_exceptions=False).get(TEST_ROUTE)
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["detail"] == SERVICE_UNAVAILABLE_MESSAGE
    finally:
        app.router.routes = [
            route for route in app.router.routes if getattr(route, "path", None) != TEST_ROUTE
        ]
