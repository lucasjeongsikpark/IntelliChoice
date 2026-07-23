from chat_api.main import app
from fastapi.testclient import TestClient


def test_healthz_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "dev"}
