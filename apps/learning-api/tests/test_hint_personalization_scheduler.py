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

**Every test here also pins the outcome counter** (D-329's detection gap). The delivery branch
is only half the question: the other half is whether an operator can *tell* which branch
production is taking. Each run must move exactly one label of
`learning_hint_personalization_outcomes_total` and no other, so a path that silently stops
publishing shows up as a different label moving rather than as nothing at all - which is what
"ran dead in production without raising" looked like.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import get_args

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.hints import HintEvent
from intellichoice_db.models.mastery import StudyAttempt, StudySession
from intellichoice_observability.metrics import (
    HINT_PERSONALIZATION_OUTCOMES,
    PREINITIALISED_LABEL_VALUES,
)
from intellichoice_shared.bedrock import BedrockTask
from learning_api.routers.sessions import build_personalized_hint_snapshot
from learning_api.services.hint_personalization_scheduler import (
    BackgroundHintPersonalizationScheduler,
    _Outcome,
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


def _gateway_missing_the_hint_model() -> ResilientBedrockGateway:
    """D-329's actual production configuration: the registry entry absent.

    `generate_structured` raises `ValueError` for an unregistered task - not a
    `BedrockGatewayError` - so `tutor.generate_personalized_hint` does not catch it and the
    scheduler's own `except` does. That is the 117-failures-in-48-hours path, and the one
    outcome that is *also* visible as a log line.
    """
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(provider=mock, embedding_provider=mock, model_registry={})


def _gateway_with_no_budget_left() -> ResilientBedrockGateway:
    """A configured model whose call the session budget refuses.

    `CostBudgetExceededError` is a `BedrockGatewayError`, so this is the *quiet* half: the
    tutor falls back to the canonical rung, returns `was_personalized=False`, and the
    scheduler returns without publishing and without raising. Nothing before this change
    counted it - a budget or config regression that made every call fall back was
    indistinguishable from a week when nobody asked for a hint.
    """
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={BedrockTask.HINT_PERSONALIZATION: "us.anthropic.claude-haiku-4-5"},
        session_budget_cents=0.0,
    )


_OUTCOMES: tuple[str, ...] = get_args(_Outcome)


def _outcome_counts() -> dict[str, float]:
    """Every label of the outcome counter, read the `test_session_event_relay.py` way."""
    return {
        outcome: HINT_PERSONALIZATION_OUTCOMES.labels(outcome=outcome)._value.get()
        for outcome in _OUTCOMES
    }


def _moved(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    """Which labels changed, and by how much.

    The whole dict rather than one label, because "exactly one outcome per run" is the
    property: an assertion on `published` alone would still pass if the run had also counted
    a drop.
    """
    return {name: after[name] - before[name] for name in after if after[name] != before[name]}


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
            await session.execute(delete(HintEvent).where(HintEvent.study_attempt_id == attempt_id))
            await session.execute(delete(StudyAttempt).where(StudyAttempt.attempt_id == attempt_id))
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


_UNSET = object()


async def _run_scheduler(
    *,
    learning_session_id: str,
    marker: dict,
    checkpoint_attempt_id: str | None,
    events,
    intervention: object = _UNSET,
    intervention_attempt_id: object = _UNSET,
    late_intervention: object = _UNSET,
    gateway_factory=_gateway,
) -> list[dict]:
    """Drive one scheduler task to completion against a fake graph. Returns the values read.

    `checkpoint_attempt_id` is what the checkpoint claims the student is currently on. Passing
    the marker's own attempt means "still here"; anything else means "moved on".

    **`intervention` and `intervention_attempt_id` default to "the hint this marker describes,
    still on screen"** (D-373), which is what every pre-existing test in this file assumed
    implicitly and got for free when the guard read one field. They are parameters now because
    the guard reads four, and the three that were added are the ones D-356 turns on.

    `gateway_factory` is the working gateway unless a test is exercising an outcome that
    needs a broken one - the two above are the failure and fallback configurations.

    `late_intervention` models the D-369 window: when set, the **second** `aget_state` — the
    one immediately before the publish — returns it instead. That is the only way to exercise a
    student who switches help while the snapshot is being built.
    """

    def _resolved(value: object):
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        future.set_result(value)
        return future

    default_intervention = {"type": "hint", "hint_level": marker["level"]}
    first = intervention if intervention is not _UNSET else default_intervention
    paired = (
        intervention_attempt_id if intervention_attempt_id is not _UNSET else checkpoint_attempt_id
    )

    def _values(current_intervention: object) -> dict:
        return {
            "phase": "study",
            "last_study_attempt_id": checkpoint_attempt_id,
            "last_intervention": current_intervention,
            "last_intervention_attempt_id": paired,
            "last_items": [],
        }

    reads: list[dict] = []

    def _aget_state(config: object):
        is_second = len(reads) == 1
        current = late_intervention if (is_second and late_intervention is not _UNSET) else first
        values = _values(current)
        reads.append(values)
        return _resolved(SimpleNamespace(values=values))

    fake_graph = SimpleNamespace(aget_state=_aget_state)

    engine = create_engine()
    profile_adapter = MySQLProfileAdapter(MYSQL_URL)
    try:
        scheduler = BackgroundHintPersonalizationScheduler(
            session_factory=create_session_factory(engine),
            gateway_factory=gateway_factory,
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
        return reads
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

    before = _outcome_counts()
    event, (was_personalized, stored_text, canonical_col), canonical = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"published": 1}, (
        "the delivery path must count itself: `published` staying flat while hint usage moves "
        "is the shape that says personalization is running dead (D-329)"
    )

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

    before = _outcome_counts()
    nothing_published, (was_personalized, stored_text, canonical_col) = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"dropped_stale": 1}

    assert nothing_published, "a hint for a question the student has left must not be published"
    assert was_personalized is True, (
        "the rewrite still completed - dropping is about the screen, not about the record"
    )
    assert stored_text != canonical_col


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_a_student_watching_a_video_does_not_have_it_replaced_by_hint_text() -> None:
    """**D-373: D-356's defect, in the publisher that never got D-358's fix.**

    The old guard compared `last_study_attempt_id` to the marker's attempt — and
    `intervention_choice` does **not** advance that channel, only `submit_answer` does. So a
    student who clicked "Watch a video" while this task sat in its ~2.3 s Bedrock call was
    still on the same attempt, the guard passed, and the frame replaced their video with hint
    text.

    **Not recoverable, which is why this is P1 rather than a repaint.** A video closes the
    pause, nothing republishes, and `_initial_snapshot` gates `intervention` on
    `hint_ladder_awaiting_choice` — false at every terminal rung — so a refresh shows no help
    at all. The student spent their one intervention on nothing.

    Falsified by reverting `_hint_is_still_on_screen` to the single attempt-id comparison:
    this publishes and goes red.
    """
    learning_session_id = f"d373-video-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[bool, tuple[bool, str, str]]:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d373-video"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                # Same attempt throughout - the student never answered, they switched help.
                checkpoint_attempt_id=attempt_id,
                intervention={"type": "video", "video_title": "Solving two-step equations"},
                events=events,
            )
            return queue.empty(), await _stored_hint(hint_event_id)
        finally:
            await _cleanup(study_session_id, attempt_id)

    before = _outcome_counts()
    nothing_published, (was_personalized, stored_text, canonical_col) = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"dropped_stale": 1}

    assert nothing_published, (
        "hint text was published over a video the student had just chosen - D-356's symptom, "
        "and unrecoverable because the pause is closed and a refresh restores no help (D-373)"
    )
    # Same posture as the moved-on case: dropping is about the screen, not the record.
    assert was_personalized is True
    assert stored_text != canonical_col


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_a_student_who_advanced_to_the_next_rung_is_not_shown_the_previous_one() -> None:
    """The same attempt and still a hint — but hint 2, while this task personalized hint 1.

    Publishing would walk the ladder *backwards* on screen, which reads as the product losing
    the student's place. The level comparison is what rules it out, and it is the one condition
    of the four that is not about D-356.
    """
    learning_session_id = f"d373-rung-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> bool:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d373-rung"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                checkpoint_attempt_id=attempt_id,
                intervention={"type": "hint", "hint_level": 2},
                events=events,
            )
            return queue.empty()
        finally:
            await _cleanup(study_session_id, attempt_id)

    before = _outcome_counts()
    assert asyncio.run(run()), "hint 1 was published over hint 2 - the ladder went backwards"
    assert _moved(before, _outcome_counts()) == {"dropped_stale": 1}


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_help_that_changes_while_the_snapshot_is_built_still_suppresses_the_publish() -> None:
    """**D-369's window, ported here (D-373).**

    The guard is evaluated once and the snapshot build after it opens a session and queries
    the study rows. A student switching to a video *in that gap* commits after the read, so
    the values the guard inspected cannot contain it — no predicate can detect a write that
    has not happened yet. The fix is a second read immediately before the synchronous publish.

    Falsified by deleting that re-read: the first read says "hint on screen", nothing looks
    again, and this publishes.
    """
    learning_session_id = f"d373-late-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[bool, int]:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d373-late"
        )
        try:
            reads = await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                checkpoint_attempt_id=attempt_id,
                # First read: the hint is on screen. Second read: they chose a video.
                late_intervention={"type": "video", "video_title": "Two-step equations"},
                events=events,
            )
            return queue.empty(), len(reads)
        finally:
            await _cleanup(study_session_id, attempt_id)

    before = _outcome_counts()
    nothing_published, read_count = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"dropped_late": 1}

    assert read_count == 2, (
        f"the scheduler read the checkpoint {read_count} time(s); the publish-time re-check is "
        "what closes the window between the guard and the frame (D-369/D-373)"
    )
    assert nothing_published, (
        "the student switched to a video while the snapshot was being built and the hint was "
        "published over it anyway"
    )


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_a_run_that_falls_back_to_the_canonical_rung_says_so() -> None:
    """**The outcome D-329's fix left invisible, and the one that matters most.**

    A gateway error inside `tutor.generate_personalized_hint` returns the canonical rung with
    `was_personalized=False`, and the scheduler returns without publishing - correctly, since
    the student already has that exact text on screen. Nothing raises, nothing logs at ERROR,
    and before this counter nothing counted it. A config or budget regression that made *every*
    call take this path therefore produced no signal at all: hint usage kept moving, the
    personalized rewrite never arrived, and every dashboard looked healthy.

    Driven through the session budget rather than a patched function: `CostBudgetExceededError`
    is a real `BedrockGatewayError` that a real session can hit (SPEC §5.25.1), so this
    exercises the same fallback the production path would.
    """
    learning_session_id = f"d329-fallback-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[bool, tuple[bool, str, str]]:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d329-fallback"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                checkpoint_attempt_id=attempt_id,
                events=events,
                gateway_factory=_gateway_with_no_budget_left,
            )
            return queue.empty(), await _stored_hint(hint_event_id)
        finally:
            await _cleanup(study_session_id, attempt_id)

    before = _outcome_counts()
    nothing_published, (was_personalized, stored_text, canonical_col) = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"fallback_canonical": 1}

    assert nothing_published, "the canonical text is already on screen - republishing it is noise"
    assert was_personalized is False
    assert stored_text == canonical_col, "the fallback must be the canonical rung verbatim"


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_a_marker_whose_attempt_no_longer_exists_counts_as_a_missing_precondition() -> None:
    """The early returns, which end *before* the paid call.

    Separated from the drops for that reason: a run that ends here spent nothing and owed the
    student nothing, so a rise in this label is a data-integrity question (a marker outliving
    its row), not a delivery one.
    """
    learning_session_id = f"d329-precondition-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> bool:
        await _run_scheduler(
            learning_session_id=learning_session_id,
            marker={
                "attempt_id": "attempt-that-was-never-written",
                "hint_event_id": "hint-that-was-never-written",
                "level": 1,
            },
            checkpoint_attempt_id="attempt-that-was-never-written",
            events=events,
        )
        return queue.empty()

    before = _outcome_counts()
    nothing_published = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"precondition_missing": 1}
    assert nothing_published


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_the_swallowed_failure_counts_and_keeps_its_log_line_byte_identical(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """**D-329 itself, reproduced**: the registry entry missing, the call raising, the
    exception swallowed because nothing awaits a detached task.

    Two assertions, because the two signals are read by different things. The counter is new.
    The log line is not: the deployed metric filter behind the `BackgroundTaskFailures` alarm
    matches `{ $.event = "background_*_failed" }`, so this message is load-bearing for an alarm
    that is already live. Pinned as the exact string rather than as "an error was logged",
    because a rename that left the convention is the failure this would otherwise miss.
    """
    learning_session_id = f"d329-failed-{uuid.uuid4().hex[:8]}"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    async def run() -> tuple[bool, tuple[bool, str, str]]:
        study_session_id, attempt_id, hint_event_id, _canonical = await _seed_a_hinted_attempt(
            "d329-failed"
        )
        try:
            await _run_scheduler(
                learning_session_id=learning_session_id,
                marker={"attempt_id": attempt_id, "hint_event_id": hint_event_id, "level": 1},
                checkpoint_attempt_id=attempt_id,
                events=events,
                gateway_factory=_gateway_missing_the_hint_model,
            )
            return queue.empty(), await _stored_hint(hint_event_id)
        finally:
            await _cleanup(study_session_id, attempt_id)

    before = _outcome_counts()
    with caplog.at_level(logging.ERROR):
        nothing_published, (was_personalized, stored_text, canonical_col) = asyncio.run(run())
    assert _moved(before, _outcome_counts()) == {"failed": 1}

    messages = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert "background_hint_personalization_failed" in messages, messages
    assert nothing_published
    # The student is not harmed by this: the canonical rung was served synchronously and the
    # row still holds it. That is exactly why the failure was invisible for 48 hours.
    assert was_personalized is False
    assert stored_text == canonical_col


def test_the_outcome_vocabulary_is_the_pre_initialised_one() -> None:
    """The two halves of the contract have to name the same six strings.

    `_Outcome` is what `_personalize` may return; `PREINITIALISED_LABEL_VALUES` is what exists
    as a series at import. An outcome added to one and not the other is either an unalarmable
    metric that appears only on its first occurrence (COST-22) or a pre-initialised series
    nothing can ever increment.
    """
    declared = {
        tuple(sorted(values["outcome"]))
        for metric, values in PREINITIALISED_LABEL_VALUES
        if metric is HINT_PERSONALIZATION_OUTCOMES
    }
    assert declared == {tuple(sorted(_OUTCOMES))}
