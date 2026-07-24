from chat_api.main import app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine


def test_readyz_reports_ready_when_both_databases_are_reachable() -> None:
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "postgres": True, "mysql": True}


def test_readyz_returns_503_when_postgres_is_unreachable() -> None:
    with TestClient(app) as client:
        app.state.db_engine = create_async_engine(
            "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/nonexistent",
            connect_args={"timeout": 1},
        )
        response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["postgres"] is False
