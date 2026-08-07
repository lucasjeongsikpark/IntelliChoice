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
from learning_api.routers.sessions import build_deferred_narrative_snapshot
from learning_api.services import flow
from learning_api.services.session_events import SessionEventBus
from learning_api.services.stage_narrative_scheduler import (
    BackgroundStudyNarrativeScheduler,
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
    step = _study_narrative_marker(
        SimpleNamespace(study_session_id="ss-1"),
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
        SimpleNamespace(study_session_id="ss-1"),
        flow.AnswerResult(
            is_correct=True, phase="post_exam", items=[{"x": 1}], learning_gain=None
        ),
    )
    assert outro == {"stage": "study_outro", "study_session_id": "ss-1"}

    # A plain incorrect study answer (pauses for intervention) fires no narrative.
    none = _study_narrative_marker(
        SimpleNamespace(study_session_id="ss-1"),
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
                graph_getter=lambda: fake_graph,
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
