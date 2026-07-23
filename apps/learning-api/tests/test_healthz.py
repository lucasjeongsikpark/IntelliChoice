from fastapi.testclient import TestClient
from learning_api.main import app


def test_healthz_ok() -> None:
    client = TestClient(app)
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "environment": "dev"}
