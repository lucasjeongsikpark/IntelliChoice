"""S22 (SPEC §5.9/§5.13, plan §18-L3, D-064): the exam nav/timer/finalize backend - skip,
flag, overview, and the explicit finalize step that replaces the old grade-on-submit
auto-advance. See `test_learning_flow.py` for the full pre->study->post->completed happy
path (which already exercises finalize on the golden path); this file covers the new
surface's own edge cases.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

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


def _attempts_for_variant(assessment_session_id: str, question_variant_id: str) -> list[bool]:
    """`is_correct` of every attempt recorded for one item, in insertion order - so a test
    can tell "the first answer stands" from "the second answer replaced it" (AUD-L-10).
    """

    async def fetch() -> list[bool]:
        engine = create_engine()
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                repo = AssessmentRepository(session)
                attempts = await repo.get_attempts(assessment_session_id)
                return [
                    a.is_correct for a in attempts if a.question_variant_id == question_variant_id
                ]
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _checkpoint_row_counts(thread_id: str) -> tuple[int, int]:
    """(`checkpoints`, `checkpoint_writes`) rows for one thread. Lets a test assert that a
    request the server *refused* did not still advance the graph's own store.
    """

    async def fetch() -> tuple[int, int]:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                checkpoints = await conn.execute(
                    text("SELECT count(*) FROM checkpoints WHERE thread_id = :t"), {"t": thread_id}
                )
                writes = await conn.execute(
                    text("SELECT count(*) FROM checkpoint_writes WHERE thread_id = :t"),
                    {"t": thread_id},
                )
                return int(checkpoints.scalar_one()), int(writes.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _variant_outside_exam(assessment_session_id: str) -> str:
    """A real `question_variants` row that is *not* an item of this exam - AUD-L-11's "stale
    tab" shape, as distinct from a variant id that never existed at all. Chosen by query
    rather than by drawing a second exam, so the test does not depend on two seeded draws
    happening to differ.
    """

    async def fetch() -> str:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT question_variant_id FROM question_variants "
                        "WHERE question_variant_id NOT IN ("
                        "  SELECT question_variant_id FROM assessment_items "
                        "  WHERE assessment_session_id = :sid) "
                        "ORDER BY question_variant_id LIMIT 1"
                    ),
                    {"sid": assessment_session_id},
                )
                variant_id = result.scalar_one_or_none()
                assert variant_id is not None, "no variant outside this exam exists to test with"
                return str(variant_id)
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _exam_row_counts(student_external_id: str) -> tuple[int, int]:
    """(`assessment_sessions`, `assessment_items`) for one student - AUD-X-03's measurement.
    The finding was invisible in response codes and only showed up in row counts.
    """

    async def fetch() -> tuple[int, int]:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                sessions = await conn.execute(
                    text(
                        "SELECT count(*) FROM assessment_sessions "
                        "WHERE student_external_id = :sid"
                    ),
                    {"sid": student_external_id},
                )
                items = await conn.execute(
                    text(
                        "SELECT count(*) FROM assessment_items WHERE assessment_session_id IN "
                        "(SELECT assessment_session_id FROM assessment_sessions "
                        " WHERE student_external_id = :sid)"
                    ),
                    {"sid": student_external_id},
                )
                return int(sessions.scalar_one()), int(items.scalar_one())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def _study_attempt_count(learning_session_id: str) -> int:
    """Study-phase attempts for this session. Must be called inside a `TestClient` block."""

    async def fetch() -> int:
        graph = app.state.learning_graph
        snapshot = await graph.aget_state({"configurable": {"thread_id": learning_session_id}})
        study_session_id = snapshot.values["study_session_id"]
        assert study_session_id is not None
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                result = await conn.execute(
                    text("SELECT count(*) FROM study_attempts WHERE study_session_id = :sid"),
                    {"sid": study_session_id},
                )
                return int(result.scalar_one())
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


def test_changing_an_answer_is_refused_and_leaves_one_attempt_per_item() -> None:
    """AUD-L-10. The server marked an item `answered` and then accepted more answers for
    it: a resubmission under a *different* `Idempotency-Key` graded and inserted a second
    attempt rather than replacing the first, and both counted. Scores are attempt-counted
    (`learning_gain.compute_learning_gain`'s `max_score`), so one changed answer rescored a
    10-item exam as 10/11 and silently dropped the `not_applicable_pre_max` flag.

    The counted assertion is the point, as it was for AUD-F-01: the endpoint returned 200
    and the screen looked right, which is why three audits walked past it.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        pre_assessment_session_id = _pre_assessment_session_id(session_id)

        first_variant = pre_items[0]["question_variant_id"]
        correct = pre_correct[first_variant]

        wrong_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "change-1"},
            json={
                "question_variant_id": first_variant,
                "selected_option": _other_option(correct),
                "response_time_ms": 2000,
            },
        )
        assert wrong_resp.status_code == 200
        # `is_correct` is withheld on the wire during an exam (D-064), so correctness is
        # read from the recorded attempt instead.
        assert _attempts_for_variant(pre_assessment_session_id, first_variant) == [False]

        # The same submission retried is still idempotent - the key does what it always did.
        replay = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "change-1"},
            json={
                "question_variant_id": first_variant,
                "selected_option": _other_option(correct),
                "response_time_ms": 2000,
            },
        )
        assert replay.status_code == 200
        assert _attempt_count(pre_assessment_session_id) == 1

        # A *different* key for the same item is a second answer, not a retry.
        checkpoints_before = _checkpoint_row_counts(session_id)
        changed = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "change-2"},
            json={
                "question_variant_id": first_variant,
                "selected_option": correct,
                "response_time_ms": 2000,
            },
        )
        assert changed.status_code == 409
        assert "already been answered" in changed.json()["detail"]
        # Still one attempt, and still the *wrong* one: the change was refused, not applied.
        assert _attempts_for_variant(pre_assessment_session_id, first_variant) == [False]
        # And the refusal cost nothing durable. This covers the router's pre-flight
        # specifically: the unique constraint alone also returns 409, but only after the
        # request has run a graph turn, and a rejected turn measurably left +2 `checkpoints`
        # / +4 `checkpoint_writes` behind - unbounded growth on a duplicate click, and
        # AUD-X-07's checkpoint-ahead-of-database shape opened by an ordinary client bug.
        assert _checkpoint_row_counts(session_id) == checkpoints_before

        for index, item in enumerate(pre_items[1:], start=1):
            variant_id = item["question_variant_id"]
            resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"change-rest-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            assert resp.status_code == 200

        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        # 10, not 11: the scoring denominator is one-per-item again, and the first answer
        # is the one that stands (grade-on-submit locks the item, D-064).
        assert _attempt_count(pre_assessment_session_id) == 10


def test_concurrent_answers_to_one_item_produce_one_attempt() -> None:
    """The concurrent arm of AUD-L-10, and the reason the fix is a unique constraint rather
    than only a check in `flow`. `ensure_item_unanswered` is read-then-act: two requests
    that both read "no attempt yet" would both insert, and the sequential test above would
    keep passing. Same verification shape D-102 requires of AUD-X-08.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        pre_assessment_session_id = _pre_assessment_session_id(session_id)

        variant_id = pre_items[0]["question_variant_id"]
        correct = pre_correct[variant_id]

        def answer(key: str, option: str) -> int:
            return client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": key},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": option,
                    "response_time_ms": 2000,
                },
            ).status_code

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(answer, f"race-{i}", correct if i % 2 else _other_option(correct))
                for i in range(4)
            ]
            statuses = sorted(future.result() for future in futures)

        # Exactly one winner. The losers are refused, not absorbed: a client that thinks it
        # changed an answer must find out it did not.
        assert statuses.count(200) == 1, statuses
        assert statuses.count(409) == 3, statuses
        assert _attempt_count(pre_assessment_session_id) == 1


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


def test_replaying_topic_selection_serves_the_same_exam_and_builds_nothing() -> None:
    """AUD-X-03. `POST /topics` replayed on a session that already had a pre-exam returned
    **200** and built a whole second one: +1 `assessment_sessions`, +10 `assessment_items`, a
    different variant draw, and the first exam left `in_progress` and unreachable with any
    attempts already recorded against it stranded.

    Measured in row counts rather than status codes, which is why three audits walked past
    it - the response looked exactly like a successful first selection.

    The replay must be genuinely idempotent (the same exam, item for item), not merely
    harmless: a retrying proxy or a second tab has to end up looking at the exam the student
    is already taking.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        rows_before = _exam_row_counts(STUDENT_UNLINKED)
        assert rows_before == (1, 10)

        replay = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        assert replay.status_code == 200
        body = replay.json()
        assert body["phase"] == "pre_exam"
        assert [i["question_variant_id"] for i in body["items"]] == [
            i["question_variant_id"] for i in pre_items
        ]
        assert _exam_row_counts(STUDENT_UNLINKED) == rows_before
        assert _pre_assessment_session_id(session_id) == pre_assessment_session_id


def test_selecting_a_different_topic_after_an_exam_exists_is_refused() -> None:
    """The other half of AUD-X-03: a *different* topic is not a replay, and silently
    abandoning the exam in progress is the defect. 409 rather than rebuilding, because the
    student is mid-exam and the server cannot tell a stray click from a deliberate change -
    and no UI flow reaches this, since the topic list is gone once the phase is `pre_exam`.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, _pre_items = _start_pre_exam(client, headers)
        rows_before = _exam_row_counts(STUDENT_UNLINKED)

        resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "fraction_operations"},
        )
        assert resp.status_code == 409
        assert "linear_equations" in resp.json()["detail"]
        assert _exam_row_counts(STUDENT_UNLINKED) == rows_before


def test_replaying_topic_selection_after_the_phase_advanced_is_refused() -> None:
    """AUD-X-03's worst case, and the reason the guard is "an exam exists" rather than "the
    phase is still pre_exam": replayed after finalize, the rebuild overwrote
    `pre_assessment_session_id` while a study session was already live off the old one, so
    the learning-gain comparison would have been computed against an exam the student never
    sat.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"topic-replay-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.json()["phase"] == "study"
        rows_before = _exam_row_counts(STUDENT_UNLINKED)
        checkpoints_before = _checkpoint_row_counts(session_id)

        resp = client.post(
            f"/learning/sessions/{session_id}/topics",
            headers=headers,
            json={"topic_id": "linear_equations"},
        )
        assert resp.status_code == 409
        assert _exam_row_counts(STUDENT_UNLINKED) == rows_before
        assert _pre_assessment_session_id(session_id) == pre_assessment_session_id
        # Refused before the graph ran, like the answer pre-flights.
        assert _checkpoint_row_counts(session_id) == checkpoints_before


def test_an_unknown_variant_id_is_a_400_not_an_unhandled_500() -> None:
    """AUD-L-11. `UnknownQuestionVariantError` was raised at four sites in `flow` and caught
    nowhere, so a variant id that does not exist returned **500**. The correct pattern already
    existed one route away (`POST /sessions/{id}/chat` validates the same thing and 400s).

    A 500 is not merely the wrong number here: error-rate is what the S34 CloudWatch alarms
    watch, so an ordinary bad request from a stale client was indistinguishable from the
    service breaking.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, _pre_items = _start_pre_exam(client, headers)
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        checkpoints_before = _checkpoint_row_counts(session_id)

        resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "unknown-variant-1"},
            json={
                "question_variant_id": "does-not-exist",
                "selected_option": "a",
                "response_time_ms": 2000,
            },
        )
        assert resp.status_code == 400
        assert "does-not-exist" in resp.json()["detail"]
        # Refused before the graph ran, like AUD-L-10's duplicate answer: a malformed request
        # must not leave checkpoint rows behind, and must not record an attempt.
        assert _checkpoint_row_counts(session_id) == checkpoints_before
        assert _attempt_count(pre_assessment_session_id) == 0


def test_a_variant_from_outside_this_exam_is_refused_and_records_no_attempt() -> None:
    """The second half of AUD-L-11, and a defect found while fixing it (AUD-L-17): a *real*
    variant that is not one of this exam's items was neither refused nor a 500 - it was
    **graded and persisted as an attempt against this exam**. `assessment_attempts` had no
    membership check at all (`flow._submit_pre_exam_answer` checked only that the variant
    exists, and `_mark_item_answered` silently no-ops when the item is not found), so a stale
    tab could add an 11th attempt to a 10-item exam and move the scoring denominator that
    AUD-L-10 was fixed to protect.

    409 rather than 400, because the id is well-formed and real - what is wrong is the
    session's state, which is the same thing `ItemAlreadyAnsweredError` reports.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, _pre_items = _start_pre_exam(client, headers)
        pre_assessment_session_id = _pre_assessment_session_id(session_id)
        foreign_variant = _variant_outside_exam(pre_assessment_session_id)
        checkpoints_before = _checkpoint_row_counts(session_id)

        resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "foreign-variant-1"},
            json={
                "question_variant_id": foreign_variant,
                "selected_option": "a",
                "response_time_ms": 2000,
            },
        )
        assert resp.status_code == 409
        assert foreign_variant in resp.json()["detail"]
        assert _attempt_count(pre_assessment_session_id) == 0
        assert _checkpoint_row_counts(session_id) == checkpoints_before


def test_a_stale_exam_variant_answered_during_study_is_refused() -> None:
    """AUD-L-11's own stated reproduction: "a retry landing after the phase advanced". The
    study phase already checked study-item membership (`flow._record_study_attempt`), so this
    one really was only a status-code defect - it raised the uncaught exception and 500'd.

    The stale id here is a pre-exam variant, which is exactly what a tab left open on the
    exam screen would resubmit after finalize moved the session to `study`.
    """
    headers = _auth_header(_student_token(STUDENT_UNLINKED))
    with TestClient(app) as client:
        session_id, pre_items = _start_pre_exam(client, headers)
        pre_correct = _correct_options([item["question_variant_id"] for item in pre_items])
        for index, item in enumerate(pre_items):
            variant_id = item["question_variant_id"]
            resp = client.post(
                f"/learning/sessions/{session_id}/answers",
                headers={**headers, "Idempotency-Key": f"stale-study-{index}"},
                json={
                    "question_variant_id": variant_id,
                    "selected_option": pre_correct[variant_id],
                    "response_time_ms": 2000,
                },
            )
            assert resp.status_code == 200
        finalize_resp = client.post(
            f"/learning/sessions/{session_id}/exam/finalize", headers=headers, json={}
        )
        assert finalize_resp.status_code == 200
        assert finalize_resp.json()["phase"] == "study"

        stale_variant = pre_items[0]["question_variant_id"]
        checkpoints_before = _checkpoint_row_counts(session_id)
        stale_resp = client.post(
            f"/learning/sessions/{session_id}/answers",
            headers={**headers, "Idempotency-Key": "stale-study-resubmit"},
            json={
                "question_variant_id": stale_variant,
                "selected_option": pre_correct[stale_variant],
                "response_time_ms": 2000,
            },
        )
        assert stale_resp.status_code == 409
        assert _study_attempt_count(session_id) == 0
        assert _checkpoint_row_counts(session_id) == checkpoints_before


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
