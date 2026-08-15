"""D-336: finalizing a cycle twice must not give the parent two identical sessions.

**Found in staging data, not in code review.** `learning_gain` held two rows for
`pre=f422de5d…` with the *same* post session and byte-identical numbers, written 46 seconds apart.
`POST /exam/finalize` carries no `Idempotency-Key` - only `/answers` does - so a retry, a double
submit or a reconnect recomputes the cycle and inserts again.

**The harm was verified against the deployed API rather than reasoned about.**
`GET /learning/students/student-ext-1/sessions` returned **10 completed entries for 9 real cycles**,
because `services/history.py` builds one summary per gain row. A parent saw their child's
`linear_equations` session listed twice with identical scores.

The repository docstring had claimed *"one row per completed pre->study->post cycle"* since it was
written. Nothing enforced it and nothing checked it.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from intellichoice_db.models.assessment import AssessmentSession
from intellichoice_db.models.mastery import LearningGain
from intellichoice_db.repositories.mastery import MasteryRepository

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

STUDENT = "learning-gain-idempotency-test-student"
PRE = "lgi-pre-1"
POST = "lgi-post-1"


async def _seed_sessions(session, *ids: str) -> None:
    """`learning_gain` has real FKs to `assessment_sessions`, so the cycle's forms must exist
    before its gain can. Seeded rather than driven through the API: this test is about the
    repository's write rule, not about the flow that reaches it."""
    for assessment_session_id in ids:
        session.add(
            AssessmentSession(
                assessment_session_id=assessment_session_id,
                student_external_id=STUDENT,
                session_type="pre" if "pre" in assessment_session_id else "post",
                status="completed",
                started_at=datetime(2026, 8, 7, 1, 0, tzinfo=UTC),
            )
        )
    await session.flush()


def _gain(**overrides: object) -> LearningGain:
    fields: dict[str, object] = {
        "student_external_id": STUDENT,
        "pre_assessment_session_id": PRE,
        "post_assessment_session_id": POST,
        "study_session_id": None,
        "topic_id": "linear_equations",
        "pre_raw_score": 8.0,
        "post_raw_score": 7.0,
        "raw_gain": -1.0,
        "weighted_gain": -1.0,
        "normalized_gain": -0.125,
        "normalized_gain_status": "computed",
        "skill_level_gain": {},
        "difficulty_transition": {},
        "independent_correct_rate": 0.5,
        "hint_dependency": 0.0,
        "solution_dependency": 0.0,
        "unresolved_skills": [],
        "response_time_change_ms": 0,
        "computed_at": datetime(2026, 8, 7, 1, 40, tzinfo=UTC),
        **overrides,
    }
    return LearningGain(**fields)


def test_finalizing_the_same_cycle_twice_records_one_row() -> None:
    """**The regression test.** The exact staging shape: same pre, same post, same numbers, a
    second write moments later.

    Asserted on the count for *this cycle* rather than on the table, because the table legitimately
    holds other students' rows and a test that only held against an empty table would be the
    mistake this session has already made once.
    """

    async def run() -> tuple[int, str]:
        async with rollback_session() as session:
            await _seed_sessions(session, PRE, POST)
            repo = MasteryRepository(session)
            first = await repo.record_learning_gain(_gain())
            await repo.record_learning_gain(
                _gain(computed_at=datetime(2026, 8, 7, 1, 41, tzinfo=UTC))
            )

            rows = [
                g
                for g in await repo.list_learning_gains_for_student(STUDENT)
                if g.pre_assessment_session_id == PRE
            ]
            return len(rows), first.learning_gain_id

    count, first_id = asyncio.run(run())
    assert count == 1, "a re-finalized cycle must not appear twice in the parent's history"
    assert first_id


def test_the_second_write_returns_the_first_row_rather_than_raising() -> None:
    """A second finalize is a *retry*, not an error - the caller still wants the cycle's gain, and
    raising would turn a harmless double submit into a 500 on a screen the student is waiting on."""

    async def run() -> tuple[str, str]:
        async with rollback_session() as session:
            await _seed_sessions(session, PRE, POST)
            repo = MasteryRepository(session)
            first = await repo.record_learning_gain(_gain())
            second = await repo.record_learning_gain(_gain(post_raw_score=999.0))
            return first.learning_gain_id, second.learning_gain_id

    first_id, second_id = asyncio.run(run())
    assert first_id == second_id


def test_the_stored_values_are_not_overwritten_by_the_retry() -> None:
    """The recomputation reads the same attempts, so it agrees - but preferring the stored row
    keeps `computed_at` meaning "when this cycle was finalized" rather than "when someone last
    retried". The 999.0 here is impossible in practice and is only there to prove which row won.
    """

    async def run() -> float:
        async with rollback_session() as session:
            await _seed_sessions(session, PRE, POST)
            repo = MasteryRepository(session)
            await repo.record_learning_gain(_gain())
            await repo.record_learning_gain(_gain(post_raw_score=999.0))
            stored = await repo.get_learning_gain_for_cycle(PRE, POST)
            assert stored is not None
            return stored.post_raw_score

    assert asyncio.run(run()) == 7.0


def test_a_different_post_form_against_the_same_pre_is_a_different_cycle() -> None:
    """The negative arm, and the reason the key is the *pair*.

    Keying on `pre_assessment_session_id` alone would silently discard a genuine second cycle - a
    student who studied again and took a new post-exam against the same pre would have their second
    result dropped, which is worse than the duplicate this fixes.
    """

    async def run() -> int:
        async with rollback_session() as session:
            await _seed_sessions(session, PRE, POST, "lgi-post-2")
            repo = MasteryRepository(session)
            await repo.record_learning_gain(_gain())
            await repo.record_learning_gain(_gain(post_assessment_session_id="lgi-post-2"))
            rows = [
                g
                for g in await repo.list_learning_gains_for_student(STUDENT)
                if g.pre_assessment_session_id == PRE
            ]
            return len(rows)

    assert asyncio.run(run()) == 2
