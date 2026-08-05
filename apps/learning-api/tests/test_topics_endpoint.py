"""D-187: `GET /learning/sessions/{id}/topics` against the real seeded bank and the real
seeded profiles.

Kept out of `test_learning_flow.py` on purpose: that module's HTTP runs commit rows for the
student they use, and its footprint is already a recurring source of count drift in
`packages/db/tests/test_repositories.py` (S12/S21). These three tests bind a student and
read; they build no exam and answer nothing.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import (
    PARENT_TWO_CHILDREN,
    STUDENT_ONLY_CHILD,
    STUDENT_UNLINKED,
    seed,
)
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
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


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not (_mysql_available() and _postgres_available()),
    reason="MySQL/PostgreSQL not reachable or not migrated (run `make up && make db-upgrade`)",
)


@pytest.fixture(scope="module", autouse=True)
def seeded_fixtures() -> None:
    asyncio.run(seed(MYSQL_URL))

    async def load() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _bound_session(client: TestClient, headers: dict[str, str], student_id: str) -> str:
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
    student_resp = client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": student_id},
    )
    assert student_resp.status_code == 200
    return session_id


def test_the_topic_list_reflects_the_bank_and_never_recommends_an_empty_topic() -> None:
    """`STUDENT_UNLINKED` is grade 4, whose §5.7.3 band (4-5) names `fraction_operations` -
    a topic with **zero** templates (D-185's count). The grade map alone would have offered
    it; conjoining it with the bank is what stops that.
    """
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = _bound_session(client, headers, STUDENT_UNLINKED)
        response = client.get(f"/learning/sessions/{session_id}/topics", headers=headers)

    assert response.status_code == 200
    topics = {t["topic_id"]: t for t in response.json()["topics"]}

    assert topics["linear_equations"]["available"] is True
    assert topics["fraction_operations"]["available"] is False
    assert topics["place_value"]["available"] is False
    assert topics["fraction_operations"]["recommended_for_grade"] is False
    for topic in topics.values():
        assert not (topic["recommended_for_grade"] and not topic["available"])
    # Every topic is still listed - "your grade has no stocked topic" must not read as
    # "there is nothing to study".
    assert len(topics) == 3


def test_a_parent_cannot_read_the_topic_list_of_a_child_it_is_not_linked_to() -> None:
    """Authorization is the sibling POST's, not a weaker read-only variant: the list names
    what a student may study, so it is resolved through `resolve_target_student` too.
    """
    student_token = issuer.issue(
        sub=STUDENT_ONLY_CHILD, role=Role.STUDENT, audience=Audience.LEARNING
    )
    with TestClient(app) as client:
        session_id = _bound_session(client, _auth_header(student_token), STUDENT_ONLY_CHILD)
        other_parent = issuer.issue(
            sub=PARENT_TWO_CHILDREN, role=Role.PARENT, audience=Audience.LEARNING
        )
        response = client.get(
            f"/learning/sessions/{session_id}/topics", headers=_auth_header(other_parent)
        )

    assert response.status_code == 403


def test_the_topic_list_refuses_a_session_that_has_not_run_a_turn() -> None:
    """404, not 409, and the distinction is the pre-existing one: `POST /learning/sessions`
    writes no checkpoint, so `_get_state_values` cannot find the thread at all - the
    "select a student before a topic" 409 both topic routes carry is a precondition on a
    session that *has* state, which this one does not yet. Pinned because it is the first
    thing a client hits if it fetches the picker before binding a student.
    """
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    headers = _auth_header(token)

    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        response = client.get(f"/learning/sessions/{session_id}/topics", headers=headers)

    assert response.status_code == 404
