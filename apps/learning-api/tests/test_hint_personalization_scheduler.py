"""D-272/D-329/D-334: does a personalized hint ever reach the student's screen?

**This file exists because the answer was "nobody knows".** D-329 fixed the gateway registry so
personalization stopped raising, and that fix was verified server-side: no failures, `bedrock_call`
fires, `hint_events.was_personalized` flips to true. What was never verified is the half that the
student actually experiences - the SSE publish that repaints the hint panel.

Measured on staging 2026-08-14 before this file existed: **2 of 2** personalized hints were
generated and then dropped, `bedrock_call` at 21:34:28.826 and
`hint_personalization_dropped_stale` at 21:34:28.836, ten milliseconds apart. The e2e walk answers
faster than the rewrite returns, so every walk that has ever run took the drop path. The delivery
path had no coverage at all - this scheduler was the only one of the three without a test file.

**What the staleness guard is for, and why it is not the bug.** A student can answer again while a
rewrite is in flight; publishing then would put a hint for a finished question beside the one they
are looking at (the D-215 §4 defect this codebase has already had once). Dropping is correct. The
open question was only ever whether the *non*-stale path works, and no test asked.

The two tests below are the two branches, asserted for opposite outcomes so neither can pass by
doing nothing.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.hints import HintEvent
from intellichoice_db.models.mastery import StudyAttempt, StudySession
from intellichoice_shared.bedrock import BedrockTask
from learning_api.routers.sessions import build_personalized_hint_snapshot
from learning_api.services.hint_personalization_scheduler import (
    BackgroundHintPersonalizationScheduler,
)
from learning_api.services.session_events import SessionEventBus
from sqlalchemy import delete, text
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
            async with session_scope(create_session_factory(engine)) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        # The registry entry D-329 was missing. Its absence here would reproduce that bug
        # exactly: the call raises, the scheduler swallows it, and the student keeps the
        # canonical rung - which is why `test_background_gateway_registry.py` guards the
        # production wiring separately.
        model_registry={BedrockTask.HINT_PERSONALIZATION: "us.anthropic.claude-haiku-4-5"},
    )


async def _seed_a_hinted_attempt(prefix: str) -> tuple[str, str, str, str]:
    """A study attempt that has just been served its first canonical hint.

    Returns `(study_session_id, attempt_id, hint_event_id, canonical_text)`. Rows are seeded
    rather than driven through the API because the scheduler is reached from a marker, not from a
    request - driving a session would exercise the route and leave the branch under test to luck.
    """
    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            row = (
                await session.execute(
                    text(
                        "SELECT v.question_variant_id, t.hint_ladder, t.skill_id, t.topic_id "
                        "FROM question_variants v "
                        "JOIN question_templates t "
                        "  ON t.question_template_id = v.question_template_id "
                        "WHERE t.hint_ladder IS NOT NULL "
                        "  AND jsonb_array_length(t.hint_ladder::jsonb) >= 2 "
                        "LIMIT 1"
                    )
                )
            ).one()
            variant_id, ladder, skill_id, topic_id = row
            canonical = ladder[0]

            study_session_id = f"{prefix}-study-{uuid.uuid4().hex[:8]}"
            attempt_id = f"{prefix}-attempt-{uuid.uuid4().hex[:8]}"
            hint_event_id = f"{prefix}-hint-{uuid.uuid4().hex[:8]}"

            session.add(
                StudySession(
                    study_session_id=study_session_id,
                    student_external_id=STUDENT_UNLINKED,
                    topic_id=topic_id,
                    target_skill_ids=[skill_id],
                    starting_difficulty=2,
                    base_problem_count=5,
                    maximum_attempts_per_skill=3,
                    intervention_policy={},
                    status="in_progress",
                    started_at=datetime.now(UTC),
                )
            )
            # Flushed between adds: `hint_events` -> `study_attempts` -> `study_sessions` is a
            # two-hop FK chain and the unit of work does not order these three by itself.
            await session.flush()
            session.add(
                StudyAttempt(
                    attempt_id=attempt_id,
                    student_external_id=STUDENT_UNLINKED,
                    study_session_id=study_session_id,
                    question_variant_id=variant_id,
                    selected_option="b",
                    is_correct=False,
                    hint_used=True,
                    video_used=False,
                    solution_used=False,
                    retry_count=0,
                    tutor_review_flagged=False,
                    responded_at=datetime.now(UTC),
                )
            )
            await session.flush()
            session.add(
                HintEvent(
                    hint_event_id=hint_event_id,
                    student_external_id=STUDENT_UNLINKED,
                    study_attempt_id=attempt_id,
                    question_variant_id=variant_id,
                    hint_level=1,
                    # Exactly what `_hint_round` writes before deferring: canonical text in both
                    # columns, `was_personalized=False`.
                    canonical_hint_text=canonical,
                    personalized_hint_text=canonical,
                    was_personalized=False,
                )
            )
            await session.commit()
        return study_session_id, attempt_id, hint_event_id, canonical
    finally:
        await engine.dispose()


async def _cleanup(study_session_id: str, attempt_id: str) -> None:
    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            await session.execute(
                delete(HintEvent).where(HintEvent.study_attempt_id == attempt_id)
            )
            await session.execute(
                delete(StudyAttempt).where(StudyAttempt.attempt_id == attempt_id)
            )
            await session.execute(
                delete(StudySession).where(StudySession.study_session_id == study_session_id)
            )
            await session.commit()
    finally:
        await engine.dispose()


async def _stored_hint(hint_event_id: str) -> tuple[bool, str, str]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT was_personalized, personalized_hint_text, canonical_hint_text "
                        "FROM hint_events WHERE hint_event_id = :h"
                    ),
                    {"h": hint_event_id},
                )
            ).one()
        return bool(row[0]), str(row[1]), str(row[2])
    finally:
        await engine.dispose()


async def _run_scheduler(
    *, learning_session_id: str, marker: dict, checkpoint_attempt_id: str | None, events
) -> None:
    """Drive one scheduler task to completion against a fake graph.

    `checkpoint_attempt_id` is what the checkpoint claims the student is currently on - the single
    value the staleness guard reads. Passing the marker's own attempt means "still here"; anything
    else means "moved on".
    """

    def _resolved(value: object):
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        future.set_result(value)
        return future

    fake_graph = SimpleNamespace(
        aget_state=lambda config: _resolved(
            SimpleNamespace(
                values={
                    "phase": "study",
                    "last_study_attempt_id": checkpoint_attempt_id,
                    "last_items": [],
                }
            )
        )
    )

    engine = create_engine()
    profile_adapter = MySQLProfileAdapter(MYSQL_URL)
    try:
        scheduler = BackgroundHintPersonalizationScheduler(
            session_factory=create_session_factory(engine),
            gateway_factory=_gateway,
            graph_getter=lambda: fake_graph,  # type: ignore[arg-type, return-value]
            events=events,
            profile_adapter=profile_adapter,
            # The exact builder `main.py` wires this scheduler with. Using the narrative one
            # here raised a TypeError the scheduler swallowed, which is how a test can end up
            # asserting against a task that never reached its publish.
            snapshot_builder=build_personalized_hint_snapshot,
        )
        await scheduler.schedule(learning_session_id=learning_session_id, marker=marker)
        await asyncio.gather(*scheduler._tasks)
    finally:
        await profile_adapter.close()
        await engine.dispose()


def test_a_student_still_on_the_question_receives_the_personalized_hint() -> None:
    """**The test this file was written for.**

    Everything about D-329 was verified up to the database row. This asserts the last hop: with the
    student still on the same attempt, the scheduler publishes an SSE event, and the hint text in
    it is the *personalized* one rather than the canonical rung the student already has on screen.

    A published event carrying the canonical text would be indistinguishable from success in every
    log and every counter, and would repaint the panel with what was already there - so the
    assertion is on the text differing, not on an event merely arriving.
    """
    learning_session_id = f"d334-live-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[dict, tuple[bool, str, str], str]:
        study_session_id, attempt_id, hint_event_id, canonical = await _seed_a_hinted_attempt(
            "d334-live"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                checkpoint_attempt_id=attempt_id,
                events=events,
            )
            return queue.get_nowait(), await _stored_hint(hint_event_id), canonical
        finally:
            await _cleanup(study_session_id, attempt_id)

    event, (was_personalized, stored_text, canonical_col), canonical = asyncio.run(run())

    assert was_personalized is True, "the row must record that personalization happened"
    assert stored_text != canonical_col, "the stored hint is still the canonical rung"

    # The published frame is a whole snapshot; the hint rides in `intervention`.
    intervention = event.get("intervention") or {}
    assert intervention.get("type") == "hint"
    assert intervention.get("hint_text") == stored_text
    assert intervention.get("hint_text") != canonical, (
        "the student was shown the canonical rung they already had - a repaint for nothing"
    )
    assert intervention.get("hint_level") == 1


def test_a_student_who_moved_on_is_not_shown_a_hint_for_the_previous_question() -> None:
    """The other branch, and the reason the guard exists (D-215 §4).

    The row still completes - the work is not thrown away, it is simply not put on screen - so this
    asserts *both*: nothing published, and the personalization durably recorded. A test that only
    asserted "nothing published" would also pass if the scheduler had crashed on its first line.
    """
    learning_session_id = f"d334-stale-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[bool, tuple[bool, str, str]]:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d334-stale"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                # The student has answered again; the checkpoint names a different attempt.
                checkpoint_attempt_id="some-later-attempt",
                events=events,
            )
            return queue.empty(), await _stored_hint(hint_event_id)
        finally:
            await _cleanup(study_session_id, attempt_id)

    nothing_published, (was_personalized, stored_text, canonical_col) = asyncio.run(run())

    assert nothing_published, "a hint for a question the student has left must not be published"
    assert was_personalized is True, (
        "the rewrite still completed - dropping is about the screen, not about the record"
    )
    assert stored_text != canonical_col
