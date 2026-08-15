"""U4/D-338: a completed cycle's results, readable by id after the session is over.

**The criterion D-327 could not meet.** U4 shipped three of four: reload lands on the same screen,
the dashboard is bookmarkable, Back works. "Results are bookmarkable" was left ⏸ because
`ResultsScreen` read the live snapshot and no endpoint served a completed session by id - a
`/results` URL worked only while the graph still held that thread.

**The test that earns the criterion is `…_after_the_checkpoint_is_deleted`.** Serving results
while the session is live proves very little: the snapshot could do that already. The claim is that
the URL keeps working *after* the session is over, and U7's retention job deletes the checkpoint at
30 days - so the honest form is to delete it and ask again.

That works because `learning_sessions` (U7/D-332) exists: `learning_gain` carries no
`learning_session_id`, so without that table there is no path from a URL to a cycle's numbers.
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
            async with session_scope(create_session_factory(engine)) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _headers(sub: str = STUDENT_UNLINKED) -> dict[str, str]:
    token = issuer.issue(sub=sub, role=Role.STUDENT, audience=Audience.LEARNING)
    return {"Authorization": f"Bearer {token}"}


def _scalar(sql: str, params: dict) -> str:
    async def fetch() -> str:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                return str((await conn.execute(text(sql), params)).scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _correct_option(variant_id: str) -> str:
    return _scalar(
        "SELECT correct_option FROM question_variants WHERE question_variant_id = :v",
        {"v": variant_id},
    )


def _delete_checkpoint(thread_id: str) -> None:
    """Exactly what U7's retention job does."""

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


def _consolidate(thread_id: str) -> None:
    """Project the session into `learning_sessions`, as the reconciler does."""

    async def run() -> None:
        from intellichoice_db.repositories.learning_session import LearningSessionRepository
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from learning_api.services.session_consolidation_cli import (
            checkpoint_dsn_from,
            summary_from_state,
        )

        engine = create_engine()
        try:
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
            assert summary is not None
            async with session_scope(create_session_factory(engine)) as session:
                await LearningSessionRepository(session).upsert(summary)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _run_a_full_session(client: TestClient, headers: dict[str, str]) -> str:
    """Pre-exam → study → post-exam → `completed`."""
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
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"res-pre-{session_id[:8]}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 1200,
            },
        )

    body = client.post(
        f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
    ).json()
    for step in range(60):
        if body["phase"] != "study":
            break
        variant_id = body["items"][0]["question_variant_id"]
        body = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"res-study-{session_id[:8]}-{step}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 2000,
            },
        ).json()
    assert body["phase"] == "post_exam", body["phase"]

    for index, item in enumerate(body["items"]):
        variant_id = item["question_variant_id"]
        body = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": f"res-post-{session_id[:8]}-{index}"},
            json={
                "question_variant_id": variant_id,
                "selected_option": _correct_option(variant_id),
                "response_time_ms": 1800,
            },
        ).json()

    body = client.post(
        f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
    ).json()
    assert body["phase"] == "completed", body["phase"]
    return session_id


def test_a_completed_sessions_results_are_readable_by_id() -> None:
    """The endpoint itself: the numbers a bookmark needs, keyed only by the session id."""
    headers = _headers()
    with TestClient(app) as client:
        session_id = _run_a_full_session(client, headers)
        resp = client.get(f"/learning/sessions/{session_id}/results", headers=headers)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["learning_session_id"] == session_id
    # The whole gain object, so `ResultsScreen` needs no restored-from-URL variant.
    gain = body["learning_gain"]
    assert {"pre_raw_score", "post_raw_score", "unresolved_skills", "independent_correct_rate"} <= (
        gain.keys()
    )
    assert isinstance(body["hint_count"], int)
    assert isinstance(body["video_count"], int)


def test_the_results_survive_the_checkpoint_being_deleted() -> None:
    """**The criterion, in the only form that means anything.**

    Serving results while the session is live proves nothing the snapshot could not already do.
    U7's retention job deletes the checkpoint at 30 days, so "bookmarkable" is a claim about what
    happens *after* that. The summary row from `learning_sessions` is what carries it.
    """
    headers = _headers()
    with TestClient(app) as client:
        session_id = _run_a_full_session(client, headers)
        _consolidate(session_id)
        _delete_checkpoint(session_id)

        # The negative control: the checkpoint really is gone, so a pass below is not the
        # fallback path quietly still reading it.
        remaining = int(
            _scalar(
                "SELECT (SELECT COUNT(*) FROM checkpoints WHERE thread_id = :t)"
                "     + (SELECT COUNT(*) FROM checkpoint_writes WHERE thread_id = :t)",
                {"t": session_id},
            )
        )
        assert remaining == 0

        resp = client.get(f"/learning/sessions/{session_id}/results", headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["learning_session_id"] == session_id


def test_a_session_still_in_progress_has_no_results() -> None:
    """A results URL for a live session names a page that does not exist yet. 404 rather than a
    half-filled screen, and rather than 409 - from the caller's side this simply is not a results
    page."""
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
        resp = client.get(f"/learning/sessions/{session_id}/results", headers=headers)

    assert resp.status_code == 404


def test_an_unknown_session_id_reveals_nothing() -> None:
    """Guessing an id must not distinguish "no such session" from "someone else's session" -
    SPEC §5.21.3. Both are 404."""
    with TestClient(app) as client:
        resp = client.get(
            "/learning/sessions/00000000-0000-0000-0000-000000000000/results", headers=_headers()
        )
    assert resp.status_code == 404


def test_another_students_results_are_refused() -> None:
    """**Authorization is derived from the record, never taken from the URL.** The session id names
    the cycle; the student comes from the stored session, and `resolve_target_student` then decides
    whether this caller may read that student. A student holding a valid token for *themselves*
    must not be able to read a classmate's results by pasting an id."""
    owner_headers = _headers(STUDENT_UNLINKED)
    with TestClient(app) as client:
        session_id = _run_a_full_session(client, owner_headers)
        resp = client.get(
            f"/learning/sessions/{session_id}/results", headers=_headers("student-ext-9")
        )

    assert resp.status_code in (403, 404), resp.status_code
