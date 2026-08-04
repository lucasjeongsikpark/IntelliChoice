"""AUD-F-22: `GET /learning/parents/me/children` - the pre-session child resolution.

The endpoint exists so a parent's child can be resolved *before* any learning session
(D-175 §5's recorded decision): without it, the frontend only learned the link from the
in-session `child_selection` interrupt, which made `StartScreen`'s dashboard button
unreachable on the natural parent path.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import (
    PARENT_ONE_CHILD,
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
    not _mysql_available(),
    reason="MySQL not reachable (run `make up`)",
)


@pytest.fixture(scope="module", autouse=True)
def seeded_fixtures() -> None:
    asyncio.run(seed(MYSQL_URL))


def _headers(sub: str, role: Role) -> dict[str, str]:
    token = issuer.issue(sub=sub, role=role, audience=Audience.LEARNING)
    return {"Authorization": f"Bearer {token}"}


def test_parent_with_two_children_gets_both_with_display_data() -> None:
    with TestClient(app) as client:
        resp = client.get(
            "/learning/parents/me/children", headers=_headers(PARENT_TWO_CHILDREN, Role.PARENT)
        )
    assert resp.status_code == 200
    children = resp.json()
    assert [c["student_external_id"] for c in children] == [
        STUDENT_FIRST_CHILD,
        STUDENT_SECOND_CHILD,
    ]
    for child in children:
        # The selection card renders all three; an empty one would be a blank button.
        assert child["display_name"]
        assert child["grade"]
        assert child["branch_name"]


def test_parent_with_one_child_gets_exactly_that_child() -> None:
    with TestClient(app) as client:
        resp = client.get(
            "/learning/parents/me/children", headers=_headers(PARENT_ONE_CHILD, Role.PARENT)
        )
    assert resp.status_code == 200
    assert [c["student_external_id"] for c in resp.json()] == [STUDENT_ONLY_CHILD]


def test_student_role_is_refused() -> None:
    with TestClient(app) as client:
        resp = client.get(
            "/learning/parents/me/children", headers=_headers(STUDENT_UNLINKED, Role.STUDENT)
        )
    assert resp.status_code == 403


def test_branch_manager_role_is_refused() -> None:
    """Fails closed: no role falls through to a permissive branch (the
    AUD-C-01/AUD-X-01/AUD-X-05 pattern this codebase keeps re-finding)."""
    with TestClient(app) as client:
        resp = client.get(
            "/learning/parents/me/children", headers=_headers("bm-ext-1", Role.BRANCH_MANAGER)
        )
    assert resp.status_code == 403


def test_anonymous_is_refused() -> None:
    with TestClient(app) as client:
        resp = client.get("/learning/parents/me/children")
    assert resp.status_code in (401, 403)
