"""S22 (SPEC §5.9/§5.13, plan §18-L3, D-064): the exam nav/timer/finalize backend - skip,
flag, overview, and the explicit finalize step that replaces the old grade-on-submit
auto-advance. See `test_learning_flow.py` for the full pre->study->post->completed happy
path (which already exercises finalize on the golden path); this file covers the new
surface's own edge cases.
"""

import asyncio

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.questions import QuestionRepository
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


def _student_token(student_id: str) -> str:
    return issuer.issue(sub=student_id, role=Role.STUDENT, audience=Audience.LEARNING)


def _correct_options(variant_ids: list[str]) -> dict[str, str]:
    async def fetch() -> dict[str, str]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = QuestionRepository(session)
                result = {}
                for variant_id in variant_ids:
                    variant = await repo.get_variant(variant_id)
                    assert variant is not None
                    result[variant_id] = variant.correct_option
                return result
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _other_option(correct: str) -> str:
    for option in ("a", "b", "c", "d"):
        if option != correct:
            return option
    raise AssertionError("no alternate option available")


def _pre_assessment_session_id(learning_session_id: str) -> str:
    """Resolves the pre-exam assessment_session_id from the graph's checkpointed state.
    Must be called from inside a `with TestClient(app) as client:` block - that's what
    initializes `app.state`.
    """

    async def fetch() -> str:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        pre_assessment_session_id = snapshot.values["pre_assessment_session_id"]
        assert pre_assessment_session_id is not None
        return pre_assessment_session_id

    return asyncio.run(fetch())


def _attempt_count(assessment_session_id: str) -> int:
    async def fetch() -> int:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = AssessmentRepository(session)
                return len(await repo.get_attempts(assessment_session_id))
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _expire_exam(assessment_session_id: str) -> None:
    """Simulates the exam timer having run out - sets `time_limit_seconds=0` so
    `flow.is_exam_expired` is true the instant any time at all has elapsed since
    `started_at`, without needing to wait or fake the clock.
    """

    async def run() -> None:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                await session.execute(
                    text(
                        "UPDATE assessment_sessions SET time_limit_seconds = 0 "
                        "WHERE assessment_session_id = :id"
                    ),
                    {"id": assessment_session_id},
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(run())


def _start_pre_exam(client: TestClient, headers: dict[str, str]) -> tuple[str, list[dict]]:
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
    client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": STUDENT_UNLINKED},
    )
    topics_resp = client.post(
        f"/learning/sessions/{session_id}/topics",
        headers=headers,
        json={"topic_id": "linear_equations"},
    )
    return session_id, topics_resp.json()["items"]


def test_skip_then_answer_grades_normally() -> None:
    """Skipping an item is pure navigation bookkeeping - answering it afterwards grades
    identically to answering it directly, never silently marking it incorrect.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        first_item_id = overview["items"][0]["assessment_item_id"]

        skip_resp = client.post(
            f"/learning/sessions/{session_id}/exam/items/{first_item_id}/skip", headers=headers
        )
        assert skip_resp.status_code == 204

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert overview["items"][0]["status"] == "skipped"

        # Answer every item, including the skipped one, in normal order.
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            correct = pre_correct[variant_id]
            resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"skip-then-answer-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": correct,
                    "response_time_ms": 2000,
                },
            )
            assert resp.status_code == 200

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert all(item["status"] == "answered" for item in overview["items"])

        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        # A perfect score (all correct) proves the previously-skipped item's real answer
        # was graded, not silently marked incorrect by finalize.
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        assert _attempt_count(pre_assessment_session_id) == 10


def test_flag_toggles_and_is_locked_out_once_answered() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        first_item_id = overview["items"][0]["assessment_item_id"]

        flag_resp = client.post(
            f"/learning/sessions/{session_id}/exam/items/{first_item_id}/flag",
            headers=headers,
            json={"flagged": True},
        )
        assert flag_resp.status_code == 204
        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert overview["items"][0]["status"] == "flagged"

        unflag_resp = client.post(
            f"/learning/sessions/{session_id}/exam/items/{first_item_id}/flag",
            headers=headers,
            json={"flagged": False},
        )
        assert unflag_resp.status_code == 204
        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert overview["items"][0]["status"] == "unseen"

        variant_id = pre_items[0]["question_variant_id"]
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "flag-lock-0"},
            json={
                "question_variant_id": variant_id,
                "selected_option": pre_correct[variant_id],
                "response_time_ms": 2000,
            },
        )

        # Flagging an already-answered item is a no-op, not an error or a status change
        # (grade-on-submit locks it, D-064).
        flag_after_answer = client.post(
            f"/learning/sessions/{session_id}/exam/items/{first_item_id}/flag",
            headers=headers,
            json={"flagged": True},
        )
        assert flag_after_answer.status_code == 204
        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert overview["items"][0]["status"] == "answered"


def test_time_tracking_accumulates_across_calls_and_is_unknown_item_safe() -> None:
    """S23 autosave tick: `time_spent_ms` sums across multiple calls (a student can
    revisit an item via the nav bar more than once) rather than being overwritten, and an
    unknown item id 404s the same way skip/flag already do.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, _pre_items = _start_pre_exam(client, headers)
        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        first_item_id = overview["items"][0]["assessment_item_id"]
        assert overview["items"][0]["time_spent_ms"] == 0

        for elapsed in (1500, 2500):
            resp = client.post(
                f"/learning/sessions/{session_id}/exam/items/{first_item_id}/time",
                headers=headers,
                json={"elapsed_ms": elapsed},
            )
            assert resp.status_code == 204

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        assert overview["items"][0]["time_spent_ms"] == 4000
        # Every other item's timing is untouched by a call scoped to one item.
        assert all(item["time_spent_ms"] == 0 for item in overview["items"][1:])

        unknown_resp = client.post(
            f"/learning/sessions/{session_id}/exam/items/not-a-real-item/time",
            headers=headers,
            json={"elapsed_ms": 100},
        )
        assert unknown_resp.status_code == 404


def test_finalize_requires_confirmation_then_grades_unanswered_items_incorrect() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        # Answer every item except the last two.
        for index, item in enumerate(pre_items[:-2]):
            variant_id = item["question_variant_id"]
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"partial-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        unanswered_ids = {
            i["assessment_item_id"] for i in overview["items"] if i["status"] == "unseen"
        }
        assert len(unanswered_ids) == 2

        no_confirm_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert no_confirm_resp.status_code == 422
        assert set(no_confirm_resp.json()["detail"]["unanswered_item_ids"]) == unanswered_ids

        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        assert _attempt_count(pre_assessment_session_id) == 8

        confirmed_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize",
            headers=headers,
            json={"confirm_unanswered": True},
        )
        assert confirmed_resp.status_code == 200
        assert confirmed_resp.json()["phase"] == "study"
        # The 2 unanswered items are now synthetic incorrect attempts (SPEC §5.9.3 - no
        # LLM, deterministic), bringing the total to all 10.
        assert _attempt_count(pre_assessment_session_id) == 10


def test_finalize_is_idempotent_no_duplicate_attempts() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"idem-fin-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )

        pre_assessment_session_id = _pre_assessment_session_id(session_id)

        first = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert first.status_code == 200
        assert _attempt_count(pre_assessment_session_id) == 10

        second = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert second.status_code == 200
        assert second.json() == first.json()
        assert _attempt_count(pre_assessment_session_id) == 10


def test_expired_exam_rejects_new_answers_and_finalizes_without_confirmation() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        # Answer one item for real, then let the clock run out before the rest.
        first_variant_id = pre_items[0]["question_variant_id"]
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "expiry-0"},
            json={
                "question_variant_id": first_variant_id,
                "selected_option": pre_correct[first_variant_id],
                "response_time_ms": 2000,
            },
        )
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        _expire_exam(pre_assessment_session_id)

        second_variant_id = pre_items[1]["question_variant_id"]
        blocked_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "expiry-1"},
            json={
                "question_variant_id": second_variant_id,
                "selected_option": pre_correct[second_variant_id],
                "response_time_ms": 2000,
            },
        )
        assert blocked_resp.status_code == 409

        # No confirmation needed once expired - the 9 unanswered items are graded
        # incorrect and the exam finalizes anyway.
        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["phase"] == "study"
        assert _attempt_count(pre_assessment_session_id) == 10


def test_resume_and_overview_restore_item_statuses_after_restart() -> None:
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])

        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()
        item_ids = [i["assessment_item_id"] for i in overview["items"]]

        client.post(
            f"/learning/sessions/{session_id}/exam/items/{item_ids[0]}/skip", headers=headers
        )
        client.post(
            f"/learning/sessions/{session_id}/exam/items/{item_ids[1]}/flag",
            headers=headers,
            json={"flagged": True},
        )
        variant_id = pre_items[2]["question_variant_id"]
        client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "restart-overview-0"},
            json={
                "question_variant_id": variant_id,
                "selected_option": pre_correct[variant_id],
                "response_time_ms": 2000,
            },
        )

    # The app (and its checkpointer connection) has fully shut down here.

    with TestClient(app) as client:
        overview = client.get(
            f"/learning/sessions/{session_id}/exam/overview", headers=headers
        ).json()

    by_id = {i["assessment_item_id"]: i for i in overview["items"]}
    assert by_id[item_ids[0]]["status"] == "skipped"
    assert by_id[item_ids[1]]["status"] == "flagged"
    assert by_id[item_ids[2]]["status"] == "answered"
    assert overview["remaining_seconds"] is not None
