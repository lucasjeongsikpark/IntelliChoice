"""U7 falsification check #1: deleting a consolidated session's checkpoint loses nothing.

**This is the test that earns the deletion.** Everything else in U7 argues that a completed
session's durable record lives outside its checkpoint. This runs a real session to completion,
deletes its checkpoint rows the way the retention job will, and then asks the database what a
student's next session would see. If mastery, learning gain, memory facts or the session summary
were only ever in the checkpoint, this fails.

**Why the read-only evidence was not enough.** D-331 checked that 9 of 9 completed staging sessions
*had* durable rows. That is a necessary condition, not a sufficient one: it cannot catch a row that
exists but is only reachable *through* the checkpoint, and it cannot catch a delete that takes more
than it should. The only honest form of "the checkpoint is redundant" is to remove it and look.

**The negative control matters as much as the assertion.** A test that deleted nothing would pass
every assertion here trivially, so each test asserts `_checkpoint_rows(...) > 0` before deleting and
`== 0` after. Without that pair this file would be the project's recurring failure mode again - a
criterion that cannot fail.

**And the session is driven to `completed`, not merely to `finalize`.** The first version stopped
after the pre-exam's finalize, which leaves the session in `study`: no `learning_gain` row, and not
the state the 30-day policy selects on. Both tests passed anyway. It was caught by querying
`learning_sessions.phase` after the run - measurement, not re-reading, exactly as every other
instance of this in the project.
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
from sqlalchemy import text

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

issuer = FakeTokenIssuer()


def _mysql_available() -> bool:
    async def check() -> bool:
        from sqlalchemy.ext.asyncio import create_async_engine

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
                await conn.execute(text("SELECT 1 FROM learning_sessions LIMIT 1"))
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
    return _scalar(
        "SELECT correct_option FROM question_variants WHERE question_variant_id = :v",
        {"v": variant_id},
    )


def _scalar(sql: str, params: dict) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                return str((await conn.execute(text(sql), params)).scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _count(sql: str, params: dict) -> int:
    return int(_scalar(sql, params))


def _checkpoint_rows(thread_id: str) -> int:
    """All three tables, because a partial delete is the failure this must be able to see."""
    return _count(
        "SELECT (SELECT COUNT(*) FROM checkpoints WHERE thread_id = :t)"
        "     + (SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = :t)"
        "     + (SELECT COUNT(*) FROM checkpoint_blobs WHERE thread_id = :t)",
        {"t": thread_id},
    )


def _delete_checkpoint(thread_id: str) -> None:
    """Exactly what the retention job will do: three deletes, one transaction, nothing else."""

    async def run() -> None:
        engine = create_engine()
        try:
            async with engine.begin() as conn:
                for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
                    await conn.execute(
                        text(f"DELETE FROM {table} WHERE thread_id = :t"), {"t": thread_id}
                    )
        finally:
            await engine.dispose()

    asyncio.run(run())


def _consolidate_summary(thread_id: str) -> None:
    """Run the extraction half for this one thread, as the retention job will before deleting."""

    async def run() -> None:
        from intellichoice_db.repositories.learning_session import LearningSessionRepository
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from learning_api.services.session_consolidation_cli import (
            checkpoint_dsn_from,
            summary_from_state,
        )

        engine = create_engine()
        try:
            # Read `ts` on this connection rather than via `_scalar`, which calls `asyncio.run`
            # and cannot be reached from inside a running loop.
            async with engine.connect() as conn:
                last_ts = (
                    await conn.execute(
                        text(
                            "SELECT MAX((checkpoint->>'ts')::timestamptz) FROM checkpoints "
                            "WHERE thread_id = :t"
                        ),
                        {"t": thread_id},
                    )
                ).scalar_one()

            async with AsyncPostgresSaver.from_conn_string(checkpoint_dsn_from(engine)) as saver:
                tuple_ = await saver.aget_tuple({"configurable": {"thread_id": thread_id}})
            assert tuple_ is not None

            summary = summary_from_state(
                thread_id, dict(tuple_.checkpoint["channel_values"]), last_ts
            )
            assert summary is not None, "a completed learning session must project a summary"
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await LearningSessionRepository(session).upsert(summary)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _run_a_full_session(client: TestClient, headers: dict[str, str]) -> str:
    """Pre-exam → study → post-exam → `completed`, answering everything correctly.

    **Driven all the way to `completed` deliberately.** The first version of this helper stopped
    after the pre-exam's `finalize`, which leaves the session in `study` — so it never produced a
    `learning_gain` row and never reached the state the 30-day policy actually selects on. Both
    tests passed anyway, which is precisely the failure this project keeps finding: a green
    assertion about a state the run never entered. Caught by querying `learning_sessions.phase`
    after the run rather than by re-reading the helper.
    """
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
    client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": STUDENT_UNLINKED},
    )
    body = client.post(
        f"/learning/sessions/{session_id}/topics",
        headers=headers,
        json={"topic_id": "linear_equations"},
    ).json()

    for index, item in enumerate(body["items"]):
        variant_id = item["question_variant_id"]
        resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"pre-{session_id[:8]}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 1500,
            },
        )
        assert resp.status_code == 200

    body = client.post(
        f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
    ).json()
    assert body["phase"] == "study"

    # The study loop serves one item at a time and ends by flipping the phase to post_exam.
    # Bounded rather than `while True`: a routing regression should fail this test, not hang CI.
    for step in range(60):
        if body["phase"] != "study":
            break
        items = body["items"]
        assert items and len(items) == 1
        variant_id = items[0]["question_variant_id"]
        body = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"study-{session_id[:8]}-{step}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 2500,
            },
        ).json()
    assert body["phase"] == "post_exam", f"study loop did not finish: {body['phase']}"

    for index, item in enumerate(body["items"]):
        variant_id = item["question_variant_id"]
        body = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"post-{session_id[:8]}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 2000,
            },
        ).json()

    body = client.post(
        f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
    ).json()
    assert body["phase"] == "completed", f"session did not complete: {body['phase']}"
    assert body["learning_gain"] is not None
    return session_id


def test_a_consolidated_sessions_durable_record_survives_its_checkpoint_being_deleted() -> None:
    """The restore test proper.

    Runs a real session, consolidates it, deletes the checkpoint, and asserts every durable
    artefact is still readable afterwards - including the summary row, which is the only place
    the five orphan fields exist.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = _run_a_full_session(client, headers)

    _consolidate_summary(session_id)

    before = {
        "attempts": _count(
            "SELECT COUNT(*) FROM assessment_attempts a JOIN assessment_sessions s "
            "ON s.assessment_session_id = a.assessment_session_id "
            "WHERE a.student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "mastery": _count(
            "SELECT COUNT(*) FROM mastery WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "events": _count(
            "SELECT COUNT(*) FROM learning_events WHERE session_id = :t", {"t": session_id}
        ),
        "summary": _count(
            "SELECT COUNT(*) FROM learning_sessions WHERE learning_session_id = :t",
            {"t": session_id},
        ),
        "gain": _count(
            "SELECT COUNT(*) FROM learning_gain WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "facts": _count(
            "SELECT COUNT(*) FROM semantic_memory WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
    }
    assert before["summary"] == 1, "the summary must exist before the checkpoint is deleted"
    assert before["attempts"] > 0, "the session must have produced attempts to be worth testing"
    assert before["gain"] > 0, "a completed session must have produced a learning_gain row"
    assert before["mastery"] > 0, "a completed session must have produced mastery rows"

    assert _checkpoint_rows(session_id) > 0, "nothing to delete - the session never checkpointed"
    _delete_checkpoint(session_id)

    # The negative control: the delete really happened, so the assertions below mean something.
    assert _checkpoint_rows(session_id) == 0

    after = {
        "attempts": _count(
            "SELECT COUNT(*) FROM assessment_attempts a JOIN assessment_sessions s "
            "ON s.assessment_session_id = a.assessment_session_id "
            "WHERE a.student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "mastery": _count(
            "SELECT COUNT(*) FROM mastery WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "events": _count(
            "SELECT COUNT(*) FROM learning_events WHERE session_id = :t", {"t": session_id}
        ),
        "summary": _count(
            "SELECT COUNT(*) FROM learning_sessions WHERE learning_session_id = :t",
            {"t": session_id},
        ),
        "gain": _count(
            "SELECT COUNT(*) FROM learning_gain WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
        "facts": _count(
            "SELECT COUNT(*) FROM semantic_memory WHERE student_external_id = :s",
            {"s": STUDENT_UNLINKED},
        ),
    }
    assert after == before, (
        f"deleting the checkpoint changed the durable record: {before} -> {after}"
    )


def test_the_orphan_fields_are_still_readable_after_the_checkpoint_is_gone() -> None:
    """The five fields with no other home are the whole reason `learning_sessions` exists, so
    they get their own assertion rather than riding on a row count.

    `week_id` is the sharpest of them: before this table it existed *only* inside the checkpoint
    for any session that was not blocked, so a delete would have destroyed the only record of
    which attendance week a student's session belonged to.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = _run_a_full_session(client, headers)

    _consolidate_summary(session_id)
    _delete_checkpoint(session_id)
    assert _checkpoint_rows(session_id) == 0

    row = _scalar(
        "SELECT concat_ws('|', phase, coalesce(week_id, '-'), "
        "coalesce(pre_assessment_session_id, '-'), coalesce(post_assessment_session_id, '-'), "
        "coalesce(student_external_id, '-')) "
        "FROM learning_sessions WHERE learning_session_id = :t",
        {"t": session_id},
    )
    phase, week_id, pre_id, _post_id, student = row.split("|")

    # `completed` exactly: this is the state the 30-day policy selects on, so a test that
    # accepted `study` would be asserting about a session the retention job would never touch.
    assert phase == "completed", phase
    assert week_id != "-", "week_id was lost - it exists nowhere else for a non-blocked session"
    assert pre_id != "-", "the pre-assessment linkage was lost"
    assert student == STUDENT_UNLINKED
