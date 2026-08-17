"""D-217: the study-transition narrative deferred off the answer's critical path.

`_study_narrative_marker` is the pure decision (which narrative, ids only); the background
scheduler generates it against its own session and publishes a full snapshot over the SSE
bus. The inline (mock-provider) path is exercised by `test_learning_flow.py` /
`test_stage_narrative.py` - those stay green, which is the proof that deferral is opt-in
and did not change the default behaviour.
"""

import asyncio
from types import SimpleNamespace

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED, seed
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.stage_transition import StageTransition
from intellichoice_shared.bedrock import BedrockTask
from learning_api.graph.nodes import _study_narrative_marker
from learning_api.graph.state import LearningState
from learning_api.routers.sessions import build_deferred_narrative_snapshot
from learning_api.services import flow
from learning_api.services.session_events import SessionEventBus
from learning_api.services.stage_narrative_scheduler import (
    BackgroundStudyNarrativeScheduler,
    help_is_on_screen,
)
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
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def test_study_narrative_marker_is_ids_only_and_carries_no_pii() -> None:
    state = LearningState(session_id="s", study_session_id="ss-1")
    step = _study_narrative_marker(
        state,
        flow.AnswerResult(
            is_correct=True,
            phase="study",
            items=None,
            learning_gain=None,
            target_skill_id="linear_one_step",
            new_target_skill_id="linear_two_step",
        ),
    )
    assert step == {
        "stage": "study_step",
        "completed_skill_id": "linear_one_step",
        "target_skill_id": "linear_two_step",
    }

    outro = _study_narrative_marker(
        state,
        flow.AnswerResult(is_correct=True, phase="post_exam", items=[], learning_gain=None),
    )
    assert outro == {"stage": "study_outro", "study_session_id": "ss-1"}

    # A plain incorrect study answer (pauses for intervention) fires no narrative.
    none = _study_narrative_marker(
        state,
        flow.AnswerResult(is_correct=False, phase="study", items=None, learning_gain=None),
    )
    assert none is None


def test_background_scheduler_generates_and_publishes_a_full_snapshot() -> None:
    """The deferred path end to end: a `study_step` marker produces a `stage_transitions`
    row and a published snapshot that still carries the current question (the client
    replaces its whole snapshot per SSE frame, so a partial one would blank the screen).
    """
    learning_session_id = "d217-narr-sched-session"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    # The committed checkpoint the background task reads back after generating. A fake
    # graph is enough - the scheduler only calls `aget_state`.
    committed_state = {
        "phase": "study",
        "last_is_correct": True,
        "last_items": [
            {
                "question_variant_id": "v-next",
                "assessment_item_id": "i-next",
                "rendered_question": "Solve for x: x + 2 = 9",
                "display_order": 0,
                "option_a": "7",
                "option_b": "6",
                "option_c": "8",
                "option_d": "5",
            }
        ],
    }
    fake_graph = SimpleNamespace(
        aget_state=lambda config: _resolved(SimpleNamespace(values=committed_state))
    )

    def _gateway() -> ResilientBedrockGateway:
        mock = MockBedrockProvider()
        return ResilientBedrockGateway(
            provider=mock,
            embedding_provider=mock,
            model_registry={BedrockTask.STAGE_NARRATIVE: "us.anthropic.claude-haiku-4-5"},
        )

    async def run() -> dict:
        engine = create_engine()
        profile_adapter = MySQLProfileAdapter(MYSQL_URL)
        try:
            scheduler = BackgroundStudyNarrativeScheduler(
                session_factory=create_session_factory(engine),
                gateway_factory=_gateway,
                graph_getter=lambda: fake_graph,  # type: ignore[arg-type, return-value]
                events=events,
                profile_adapter=profile_adapter,
                snapshot_builder=build_deferred_narrative_snapshot,
            )
            await scheduler.schedule(
                learning_session_id=learning_session_id,
                student_external_id=STUDENT_UNLINKED,
                marker={
                    "stage": "study_step",
                    "completed_skill_id": "linear_one_step",
                    "target_skill_id": "linear_two_step",
                },
            )
            # Await the one detached task the scheduler is tracking.
            await asyncio.gather(*scheduler._tasks)
            return queue.get_nowait()
        finally:
            await profile_adapter.close()
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                await session.execute(
                    delete(StageTransition).where(
                        StageTransition.learning_session_id == learning_session_id
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    try:
        published = asyncio.run(run())
    finally:
        asyncio.run(cleanup())

    # A narrative was generated and published, and the snapshot still carries the next
    # question (a partial snapshot would blank the client).
    assert published["event"] == "session_update"
    assert published["phase"] == "study"
    assert published["stage_narrative"]
    assert published["items"][0]["question_variant_id"] == "v-next"


def _resolved(value: object):
    async def _coro():
        return value

    return _coro()


def test_the_publish_is_skipped_while_the_student_is_reading_a_video() -> None:
    """D-358: the terminal rungs close the pause, and the old guard only saw the pause.

    Measured on staging before the fix: `POST /respond` returned 200 with a real video, and
    a deferred `study_step` frame ~1.5s later replaced the client's whole snapshot without
    `intervention`, erasing the video the student had just asked for. Roughly one run in
    two. `hint_ladder_awaiting_choice` is **false** here - that is the whole point, and the
    reason the D-272 guard could not fire.
    """
    values = {
        "phase": "study",
        "hint_ladder_awaiting_choice": False,
        "last_intervention": {"type": "video", "video_title": "Solving two-step equations"},
        "last_intervention_attempt_id": "attempt-7",
        "last_study_attempt_id": "attempt-7",
    }
    assert help_is_on_screen(values), (
        "a video the student is looking at was not recognised as help on screen, so the "
        "deferred narrative frame would publish over it and blank the panel (D-358)"
    )


def test_a_stale_intervention_does_not_suppress_the_narrative() -> None:
    """The falsification, and the one that matters more than the test above.

    Skipping whenever `last_intervention` is set would be trivially "safe" and would
    silently disable deferred narratives for the rest of the session, because that channel
    is never cleared - `submit_answer` moves `last_study_attempt_id` on and leaves the help
    behind. A guard that always fires is not a guard.
    """
    values = {
        "phase": "study",
        "hint_ladder_awaiting_choice": False,
        # The help from a question the student has since answered and moved past.
        "last_intervention": {"type": "video", "video_title": "An earlier question's video"},
        "last_intervention_attempt_id": "attempt-7",
        "last_study_attempt_id": "attempt-8",
    }
    assert not help_is_on_screen(values), (
        "a stale intervention from a previous question suppressed the narrative - the "
        "pairing with the current attempt is what stops this guard swallowing everything"
    )


def test_an_open_ladder_still_suppresses_the_narrative() -> None:
    """D-272's original case, kept: hints 1-2 leave the graph paused and the panel up."""
    assert help_is_on_screen({"hint_ladder_awaiting_choice": True})


def test_a_turn_with_no_help_publishes_normally() -> None:
    """The common path - a correct answer, nothing on screen to protect."""
    assert not help_is_on_screen(
        {"phase": "study", "hint_ladder_awaiting_choice": False, "last_intervention": None}
    )


@pytest.mark.skipif(not _mysql_available(), reason="MySQL dev fake not running")
def test_help_arriving_after_the_guard_still_suppresses_the_publish() -> None:
    """D-369: the guard asked the right question at the wrong moment.

    Every test above checks `help_is_on_screen` as a **predicate**. None of them checks
    **when** it is evaluated, and that is where the remaining failures lived: the scheduler
    read the checkpoint once, then opened a session and queried the study rows to build the
    snapshot, and only then published. A student clicking "Watch a video" in that gap
    commits their choice *after* the read, so the values the guard inspected cannot contain
    it — no pairing signal can detect a write that has not happened yet.

    Measured on staging against the deployed D-358 fix: 1 failure in 5 repeats, with the
    `POST /respond` bodies byte-identical in substance between the passing and failing runs
    (200, `intervention.type="video"`, a real URL). The server was right every time.

    This models the gap directly: `aget_state` returns "nothing on screen" the first time
    and "a video the student is reading" the second. Nothing may be published.

    **Falsified by deleting the re-check** in `_run` — with only the first guard, this test
    publishes a frame and goes red.
    """
    learning_session_id = "d369-late-help-session"
    events = SessionEventBus()
    queue = events.subscribe(learning_session_id)

    before = {
        "phase": "study",
        "hint_ladder_awaiting_choice": False,
        "last_intervention": None,
        "last_study_attempt_id": "attempt-3",
        "last_items": [
            {
                "question_variant_id": "v-next",
                "assessment_item_id": "i-next",
                "rendered_question": "Solve for x: x + 2 = 9",
                "display_order": 0,
                "option_a": "7",
                "option_b": "6",
                "option_c": "8",
                "option_d": "5",
            }
        ],
    }
    # The same attempt, now with a video attached: the student chose it while the snapshot
    # was being built. `hint_ladder_awaiting_choice` stays False because a video *closes*
    # the pause - the D-358 case, arriving one step later.
    after = {
        **before,
        "last_intervention": {"type": "video"},
        "last_intervention_attempt_id": "attempt-3",
    }

    reads: list[str] = []

    def _aget_state(config: object):
        reads.append("read")
        return _resolved(SimpleNamespace(values=before if len(reads) == 1 else after))

    fake_graph = SimpleNamespace(aget_state=_aget_state)

    def _gateway() -> ResilientBedrockGateway:
        mock = MockBedrockProvider()
        return ResilientBedrockGateway(
            provider=mock,
            embedding_provider=mock,
            model_registry={BedrockTask.STAGE_NARRATIVE: "us.anthropic.claude-haiku-4-5"},
        )

    async def run() -> None:
        engine = create_engine()
        profile_adapter = MySQLProfileAdapter(MYSQL_URL)
        try:
            scheduler = BackgroundStudyNarrativeScheduler(
                session_factory=create_session_factory(engine),
                gateway_factory=_gateway,
                graph_getter=lambda: fake_graph,  # type: ignore[arg-type, return-value]
                events=events,
                profile_adapter=profile_adapter,
                snapshot_builder=build_deferred_narrative_snapshot,
            )
            await scheduler.schedule(
                learning_session_id=learning_session_id,
                student_external_id=STUDENT_UNLINKED,
                marker={
                    "stage": "study_step",
                    "completed_skill_id": "linear_one_step",
                    "target_skill_id": "linear_two_step",
                },
            )
            await asyncio.gather(*scheduler._tasks)
        finally:
            await profile_adapter.close()
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            factory = create_session_factory(engine)
            async with session_scope(factory) as session:
                await session.execute(
                    delete(StageTransition).where(
                        StageTransition.learning_session_id == learning_session_id
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
    finally:
        asyncio.run(cleanup())

    # The checkpoint must be read a second time at all - if it is not, the guard is being
    # asked once and this test would pass for the wrong reason.
    assert len(reads) == 2, (
        f"the scheduler read the checkpoint {len(reads)} time(s); the publish-time re-check "
        "is what closes the window between the guard and the frame (D-369)"
    )
    assert queue.empty(), (
        "a deferred narrative frame was published over a video the student had just asked "
        "for - the choice committed after the guard read the checkpoint, which is D-356's "
        "mechanism surviving D-358's fix (D-369)"
    )
