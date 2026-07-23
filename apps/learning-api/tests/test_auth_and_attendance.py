import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import (
    PARENT_TWO_CHILDREN,
    STUDENT_FIRST_CHILD,
    STUDENT_ONLY_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()


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


@pytest.fixture(scope="module", autouse=True)
def seeded_mysql() -> None:
    asyncio.run(seed(MYSQL_URL))


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_student_can_access_own_attendance() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 200
    assert response.json()["status"] == "present"


def test_student_cannot_access_another_students_attendance() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_FIRST_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 403


def test_parent_can_access_linked_child() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_FIRST_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 200
    assert response.json()["status"] == "absent"


def test_parent_cannot_access_unlinked_student() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_UNLINKED}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 403


def test_unknown_attendance_is_not_treated_as_present() -> None:
    token = issuer.issue(sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_SECOND_CHILD}/attendance", headers=_auth_header(token)
        )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "unknown"
    assert body["message"]


def test_tutor_and_branch_manager_roles_resolve() -> None:
    for role in (Role.TUTOR, Role.BRANCH_MANAGER):
        token = issuer.issue(sub=f"{role.value}-ext-1", role=role, audience=Audience.LEARNING)
        with TestClient(app) as client:
            response = client.get(
                f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
            )
        assert response.status_code == 200


def test_wrong_audience_token_is_rejected() -> None:
    token = issuer.issue(sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.CHAT)
    with TestClient(app) as client:
        response = client.get(
            f"/students/{STUDENT_ONLY_CHILD}/attendance", headers=_auth_header(token)
        )

    assert response.status_code == 401
