import asyncio

import pytest
from fastapi.testclient import TestClient
from learning_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not _mysql_available(), reason="MySQL is not reachable at localhost:3306 (run `make up`)"
)


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
