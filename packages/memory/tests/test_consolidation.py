"""S25 memory consolidation (SPEC §5.15.4, plan §9) - real Postgres via the same
rollback-session pattern `packages/youtube/tests/test_catalog_sync.py` uses (D-013),
skipping cleanly when Postgres is unreachable (D-008). A scripted fake `BedrockGateway`
(same pattern `apps/learning-api/tests/test_tutor_service.py::_FakeGateway` uses) stands
in for the real resilience wrapper, so these tests focus purely on the deterministic
validation/upsert logic - evidence verification, provisional/active promotion,
contradiction demotion/supersession, and PII/enum screens.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest
from intellichoice_db.engine import create_engine
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.memory import LearningEvent
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_memory.consolidation import (
    consolidate_student_session,
    consolidate_student_window,
)
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    MemoryFactCandidate,
    MemoryFactUpdate,
    MemoryUpdateResponse,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM semantic_memory LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)

STUDENT_ID = "memory-test-student-1"


class _FakeGateway:
    """Returns each queued `MemoryUpdateResponse`/`BedrockGatewayError` in order, one
    per `generate_structured` call - lets a test script a multi-round consolidation
    sequence (e.g. contradiction -> second contradiction -> supersede).
    """

    def __init__(self, outcomes: list[MemoryUpdateResponse | BedrockGatewayError]) -> None:
        self._outcomes = list(outcomes)

    async def generate_structured(self, *, task: BedrockTask, **kwargs) -> BedrockGenerationResult:
        del task, kwargs
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BedrockGatewayError):
            raise outcome
        return BedrockGenerationResult(
            value=outcome,
            input_tokens=10,
            output_tokens=10,
            cost_cents=0.5,
            model_id="test-model",
            repaired=False,
        )

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


@dataclass
class Seed:
    topic_id: str
    skill_id: str


async def _seed_topic_skill(session: AsyncSession) -> Seed:
    curriculum = CurriculumRepository(session)
    topic = await curriculum.create_topic(
        Topic(curriculum_version="v1", name="Linear Equations", grade_band="6-8")
    )
    skill = await curriculum.create_skill(
        Skill(topic_id=topic.topic_id, name="linear_one_step")
    )
    return Seed(topic_id=topic.topic_id, skill_id=skill.skill_id)


async def _add_event(
    memory_repo: MemoryRepository,
    *,
    skill_id: str,
    session_id: str,
    event_type: str = "study_outcome",
    payload: dict | None = None,
    occurred_at: datetime | None = None,
) -> LearningEvent:
    return await memory_repo.record_event(
        LearningEvent(
            student_external_id=STUDENT_ID,
            session_id=session_id,
            event_type=event_type,
            skill_id=skill_id,
            structured_payload=payload
            or {"outcome_label": "unresolved", "target_skill_id": skill_id},
        )
    )


def _weak_skill_candidate(skill_id: str, event_ids: list[str]) -> MemoryFactCandidate:
    return MemoryFactCandidate(
        fact_type="weak_skill",
        skill_id=skill_id,
        fact_text="May need extra support with this skill.",
        polarity="negative",
        confidence=0.6,
        supporting_event_ids=event_ids,
    )


def _weak_skill_response(skill_id: str, event_ids: list[str]) -> MemoryUpdateResponse:
    return MemoryUpdateResponse(facts_to_add=[_weak_skill_candidate(skill_id, event_ids)])


async def _sole_active_fact(memory_repo: MemoryRepository):
    facts = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
    return facts[0]


def test_candidate_dropped_when_no_evidence_ids_resolve() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway(
                [
                    MemoryUpdateResponse(
                        facts_to_add=[
                            _weak_skill_candidate(seed.skill_id, ["not-a-real-event-id"])
                        ]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0
            facts = await memory_repo.list_facts_for_student(
                STUDENT_ID, statuses=("active", "provisional")
            )
            assert facts == []

    asyncio.run(run())


def test_new_fact_below_minimum_evidence_is_provisional() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway(
                [
                    MemoryUpdateResponse(
                        facts_to_add=[
                            _weak_skill_candidate(seed.skill_id, [event.event_id])
                        ]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 1
            active = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert active == []
            provisional = await memory_repo.list_facts_for_student(
                STUDENT_ID, statuses=("provisional",)
            )
            assert len(provisional) == 1

    asyncio.run(run())


def test_new_fact_active_with_enough_events_across_enough_sessions() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]

            gateway = _FakeGateway(
                [
                    MemoryUpdateResponse(
                        facts_to_add=[
                            _weak_skill_candidate(
                                seed.skill_id, [e.event_id for e in events]
                            )
                        ]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=events[0].occurred_at - timedelta(minutes=1),
                window_end=events[-1].occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 1
            active = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert len(active) == 1
            assert set(active[0].evidence_event_ids) == {e.event_id for e in events}

    asyncio.run(run())


def test_out_of_enum_fact_type_is_dropped() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            candidate = _weak_skill_candidate(seed.skill_id, [event.event_id])
            candidate.fact_type = "diagnosed_learning_disability"  # not in the closed enum
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[candidate])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0

    asyncio.run(run())


def test_fact_text_containing_pii_pattern_is_dropped() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            candidate = _weak_skill_candidate(seed.skill_id, [event.event_id])
            candidate.fact_text = "Contact the student at student@example.com for follow-up."
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[candidate])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0

    asyncio.run(run())


def test_contradiction_demotes_then_supersedes_on_second_contradiction() -> None:
    """Plan §9: an opposite-polarity conflict demotes the existing fact to `contested`
    rather than overwriting it; only a *second* consecutive contradiction supersedes.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            event_ids = [e.event_id for e in events]
            window_start = events[0].occurred_at - timedelta(minutes=1)
            window_end = events[-1].occurred_at + timedelta(minutes=1)

            # Round 1: establishes an active weak_skill (negative) fact.
            gateway = _FakeGateway([_weak_skill_response(seed.skill_id, event_ids)])
            await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            original = await _sole_active_fact(memory_repo)
            assert original.status == "active"
            assert original.contradicts_event_count == 0

            strength_candidate = MemoryFactCandidate(
                fact_type="weak_skill",
                skill_id=seed.skill_id,
                fact_text="Now solves this skill independently.",
                polarity="positive",
                confidence=0.6,
                supporting_event_ids=event_ids,
            )

            # Round 2: opposite-polarity candidate -> demote to contested.
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[strength_candidate])])
            result_2 = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            assert result_2.contested == 1
            refreshed = await memory_repo.get_fact(original.semantic_memory_id)
            assert refreshed is not None
            assert refreshed.status == "contested"
            assert refreshed.contradicts_event_count == 1
            assert refreshed.superseded_by_id is None

            # Round 3: a *second* opposite-polarity candidate -> supersede.
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[strength_candidate])])
            result_3 = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            assert result_3.contested == 1
            twice_refreshed = await memory_repo.get_fact(original.semantic_memory_id)
            assert twice_refreshed is not None
            assert twice_refreshed.status == "superseded"
            assert twice_refreshed.superseded_by_id is not None

    asyncio.run(run())


def test_rerun_with_same_candidate_reconfirms_instead_of_duplicating() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            event_ids = [e.event_id for e in events]
            window_start = events[0].occurred_at - timedelta(minutes=1)
            window_end = events[-1].occurred_at + timedelta(minutes=1)

            for _ in range(2):
                gateway = _FakeGateway(
                    [
                        MemoryUpdateResponse(
                            facts_to_add=[_weak_skill_candidate(seed.skill_id, event_ids)]
                        )
                    ]
                )
                await consolidate_student_window(
                    memory_repo=memory_repo,
                    tutor_chat_repo=tutor_chat_repo,
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=window_start,
                    window_end=window_end,
                    session_spend_cents=0.0,
                )

            facts = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert len(facts) == 1

    asyncio.run(run())


def test_facts_to_update_reconfirms_named_existing_fact() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            event_ids = [e.event_id for e in events]
            window_start = events[0].occurred_at - timedelta(minutes=1)
            window_end = events[-1].occurred_at + timedelta(minutes=1)

            gateway = _FakeGateway([_weak_skill_response(seed.skill_id, event_ids)])
            await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            existing = await _sole_active_fact(memory_repo)

            new_event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s2")
            update = MemoryFactUpdate(
                semantic_memory_id=existing.semantic_memory_id,
                fact_text="Still needs extra support with this skill.",
                confidence=0.75,
                supporting_event_ids=[new_event.event_id],
            )
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_update=[update])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=new_event.occurred_at - timedelta(minutes=1),
                window_end=new_event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.updated == 1
            refreshed = await memory_repo.get_fact(existing.semantic_memory_id)
            assert refreshed is not None
            assert refreshed.fact_text == "Still needs extra support with this skill."
            assert new_event.event_id in refreshed.evidence_event_ids

    asyncio.run(run())


def test_consolidate_student_session_only_considers_that_session_id() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            in_session = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id="target-session")
                for _ in range(3)
            ]
            # A different session's events must never be sent as evidence candidates.
            await _add_event(memory_repo, skill_id=seed.skill_id, session_id="other-session")

            event_ids = [e.event_id for e in in_session]
            gateway = _FakeGateway([_weak_skill_response(seed.skill_id, event_ids)])
            result = await consolidate_student_session(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                session_id="target-session",
                session_spend_cents=0.0,
            )
            assert result.added == 1

    asyncio.run(run())


def test_gateway_failure_changes_no_facts() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([BedrockGatewayError("simulated failure")])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0
            facts = await memory_repo.list_facts_for_student(
                STUDENT_ID, statuses=("active", "provisional")
            )
            assert facts == []

    asyncio.run(run())
