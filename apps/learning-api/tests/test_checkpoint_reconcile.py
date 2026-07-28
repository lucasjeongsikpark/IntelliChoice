"""S42 (AUD-X-07): a session that lost its domain transaction heals instead of 500ing.

The checkpoint commits inside `graph.ainvoke`, on the saver's own psycopg pool. The domain
rows commit at FastAPI dependency teardown, *after* the route returns. Anything that raises
in between keeps the checkpoint and discards the rows.

The failure is induced the same way S38 reproduced it: make `_publish_snapshot` raise. It
is a real statement sitting in that exact window - the route has invoked the graph and has
not yet returned - so this is the genuine seam rather than a contrived one. What a real
deployment does instead is stop the task there, which ECS does on every deploy.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_shared.auth import Audience, Role
from learning_api.main import app
from learning_api.routers import sessions as sessions_router
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


def _headers() -> dict[str, str]:
    token = issuer.issue(sub=STUDENT_UNLINKED, role=Role.STUDENT, audience=Audience.LEARNING)
    return {"Authorization": f"Bearer {token}"}


def _correct_option(variant_id: str) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                row = await conn.execute(
                    text(
                        "SELECT correct_option FROM question_variants "
                        "WHERE question_variant_id = :v"
                    ),
                    {"v": variant_id},
                )
                return str(row.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _checkpoint_phase(learning_session_id: str) -> dict:
    async def fetch() -> dict:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        return snapshot.values

    return asyncio.run(fetch())


def _study_session_exists(study_session_id: str) -> bool:
    async def fetch() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                row = await conn.execute(
                    text(
                        "SELECT count(*) FROM study_sessions WHERE study_session_id = :s"
                    ),
                    {"s": study_session_id},
                )
                return int(row.scalar_one()) > 0
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def test_a_finalize_lost_between_the_two_commits_recovers_instead_of_dead_ending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The S38 reproduction, end to end, now with the recovery asserted.

    Before this fix: `POST /resume` returned 200 with `phase=study` and served a study
    question, answering it 500'd, every retry 500'd, and `GET /exam/overview` refused with
    "not in an exam phase" - the session was a dead end that still rendered a question, and
    only operator DB surgery could clear it.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = client.post("/learning/sessions", headers=headers).json()[
            "learning_session_id"
        ]
        client.post(
            f"/learning/sessions/{session_id}/student",
            headers=headers,
            json={"student_id": STUDENT_UNLINKED},
        )
        items = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        ).json()["items"]

        for index, item in enumerate(items):
            variant_id = item["question_variant_id"]
            resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"x07-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": _correct_option(variant_id),
                    "response_time_ms": 1500,
                },
            )
            assert resp.status_code == 200

        # Crash in the window: the graph has committed `phase=study` and a
        # `study_session_id`, the domain rows have not committed yet.
        def _boom(events, response) -> None:
            raise RuntimeError("induced failure between the checkpoint and domain commits")

        monkeypatch.setattr(sessions_router, "_publish_snapshot", _boom)
        with pytest.raises(RuntimeError):
            client.post(f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={})
        monkeypatch.undo()

        # The divergence is real: the checkpoint is ahead of the database.
        diverged = _checkpoint_phase(session_id)
        assert diverged["phase"] == "study"
        assert diverged["study_session_id"] is not None
        assert not _study_session_exists(diverged["study_session_id"])

        # Recovery. Resume rolls the checkpoint back to the phase the database supports
        # rather than serving a study question against a study session that never existed.
        resume = client.post(f"/learning/sessions/{session_id}/resume", headers=headers)
        assert resume.status_code == 200
        assert resume.json()["phase"] == "pre_exam"

        healed = _checkpoint_phase(session_id)
        assert healed["phase"] == "pre_exam"
        assert healed["study_session_id"] is None

        # And the student can finish: the exam was never finalized, so finalizing again
        # is the ordinary path, not a repair.
        overview = client.get(f"/learning/sessions/{session_id}/exam/overview", headers=headers)
        assert overview.status_code == 200

        finalize = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize.status_code == 200
        assert finalize.json()["phase"] == "study"
        study_session_id = _checkpoint_phase(session_id)["study_session_id"]
        assert study_session_id is not None
        assert _study_session_exists(study_session_id)
