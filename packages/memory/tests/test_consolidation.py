"""S25 memory consolidation (SPEC §5.15.4, plan §9) - real Postgres via the same
rollback-session pattern `packages/youtube/tests/test_catalog_sync.py` uses (D-013),
skipping cleanly when Postgres is unreachable (D-008). A scripted fake `BedrockGateway`
(same pattern `apps/learning-api/tests/test_tutor_service.py::_FakeGateway` uses) stands
in for the real resilience wrapper, so these tests focus purely on the deterministic
validation/upsert logic - evidence verification, provisional/active promotion,
contradiction demotion/supersession, and PII/enum screens.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.provider import RawGeneration
from intellichoice_db.engine import create_engine
from intellichoice_db.models.curriculum import Skill, Topic
from intellichoice_db.models.mastery import Mastery
from intellichoice_db.models.memory import LearningEvent, SemanticMemory
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_memory.consolidation import (
    _ABILITY_FACT_TYPES,
    _MAX_CALLS_PER_STUDENT,
    _MAX_EVENT_CHARS_PER_CALL,
    _MAX_EVENT_TOKENS_PER_CALL,
    _SYSTEM_PROMPT,
    ConsolidationResult,
    _batch_summaries,
    _summary_chars,
    consolidate_student_session,
    consolidate_student_window,
)
from intellichoice_memory.settings import MemoryConsolidationSettings
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    CostBudgetExceededError,
    MemoryEventSummary,
    MemoryFactCandidate,
    MemoryFactUpdate,
    MemoryUpdateResponse,
    OutputTruncatedError,
)
from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD
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
        # S43: the output budget each call was given, so a test can assert the cap is
        # derived from the input rather than fixed. Discarding it is how a dead cap
        # survives (AUD-X-09).
        self.max_output_tokens_seen: list[int | None] = []
        # UD-15: the `existing_facts` ids each call was shown, so a test can tell a fact
        # the model never saw from one it saw and ignored.
        self.existing_fact_ids_seen: list[list[str]] = []

    async def generate_structured(self, *, task: BedrockTask, **kwargs) -> BedrockGenerationResult:
        del task
        self.max_output_tokens_seen.append(kwargs.get("max_output_tokens"))
        payload = kwargs.get("payload")
        if payload is not None:
            self.existing_fact_ids_seen.append(
                [fact.semantic_memory_id for fact in payload.existing_facts]
            )
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
    skill = await curriculum.create_skill(Skill(topic_id=topic.topic_id, name="linear_one_step"))
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
    event = LearningEvent(
        student_external_id=STUDENT_ID,
        session_id=session_id,
        event_type=event_type,
        skill_id=skill_id,
        structured_payload=payload or {"outcome_label": "unresolved", "target_skill_id": skill_id},
    )
    if occurred_at is not None:
        event.occurred_at = occurred_at
    return await memory_repo.record_event(event)


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
                        facts_to_add=[_weak_skill_candidate(seed.skill_id, ["not-a-real-event-id"])]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
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


def test_reconfirmation_does_not_promote_below_the_accumulated_evidence_bar() -> None:
    """AUD-F-35: plan §9's ">=3 supporting events across >=2 sessions" bar was enforced
    at creation and bypassed on the next reconfirmation - a fact created off one event
    became tutor-readable the second time the model proposed it, at two events. The bar
    must hold over the fact's ACCUMULATED evidence at promotion time.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event_1 = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")
            event_2 = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s2")
            window_start = event_1.occurred_at - timedelta(minutes=1)
            window_end = event_2.occurred_at + timedelta(minutes=1)

            # Run 1 creates the fact off one event (provisional); run 2's same-polarity
            # duplicate proposal reconfirms it with a second event from a second session.
            # Accumulated evidence is then 2 events / 2 sessions - still below the bar.
            for event in (event_1, event_2):
                gateway = _FakeGateway([_weak_skill_response(seed.skill_id, [event.event_id])])
                await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=tutor_chat_repo,
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=window_start,
                    window_end=window_end,
                    session_spend_cents=0.0,
                )

            active = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert active == []
            provisional = await memory_repo.list_facts_for_student(
                STUDENT_ID, statuses=("provisional",)
            )
            assert len(provisional) == 1
            assert len(provisional[0].evidence_event_ids) == 2

    asyncio.run(run())


def test_reconfirmation_promotes_once_accumulated_evidence_meets_the_bar() -> None:
    """The counterpart: a fact whose accumulated evidence reaches 3 events across 2
    sessions IS promoted on reconfirmation - the AUD-F-35 fix must not fail closed so
    hard that legitimately re-evidenced facts stay provisional forever.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event_1 = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")
            event_2 = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")
            event_3 = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s2")
            window_start = event_1.occurred_at - timedelta(minutes=1)
            window_end = event_3.occurred_at + timedelta(minutes=1)

            gateway = _FakeGateway(
                [
                    _weak_skill_response(seed.skill_id, [event_1.event_id, event_2.event_id]),
                    _weak_skill_response(seed.skill_id, [event_3.event_id]),
                ]
            )
            for _ in range(2):
                await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=tutor_chat_repo,
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=window_start,
                    window_end=window_end,
                    session_spend_cents=0.0,
                )

            active = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert len(active) == 1
            assert len(active[0].evidence_event_ids) == 3

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
                        facts_to_add=[_weak_skill_candidate(seed.skill_id, [event.event_id])]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
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
                            _weak_skill_candidate(seed.skill_id, [e.event_id for e in events])
                        ]
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0

    asyncio.run(run())


# --- AUD-L-13 (D-156): a fact must agree with the mastery score in the same database ---
#
# Consolidation verified a candidate's evidence provenance and its cross-session
# repetition, and never once compared the *claim* to `mastery.weighted_score` for the same
# skill - which is one query away, in the same transaction. S36's audit found
# `aud-student-regressing` holding an accepted `strength` fact for a skill measured at
# 0.000, and all 20 facts across four journeys were `strength` with zero `weak_skill`
# facts, including for the student who went 8->4. Repetition is not consistency: the
# promotion bar would have let that fact reach a parent after a second session.


def _strength_candidate(skill_id: str, event_ids: list[str]) -> MemoryFactCandidate:
    return MemoryFactCandidate(
        fact_type="strength",
        skill_id=skill_id,
        fact_text="Shows independent strength in this skill.",
        polarity="positive",
        confidence=0.8,
        supporting_event_ids=event_ids,
    )


async def _set_mastery(session: AsyncSession, skill_id: str, weighted_score: float) -> None:
    await MasteryRepository(session).upsert_mastery(
        Mastery(
            student_external_id=STUDENT_ID,
            skill_id=skill_id,
            raw_accuracy=weighted_score,
            weighted_score=weighted_score,
        )
    )


async def _consolidate_one(
    session: AsyncSession, candidate: MemoryFactCandidate, events: list[LearningEvent]
):
    return await consolidate_student_window(
        memory_repo=MemoryRepository(session),
        mastery_repo=MasteryRepository(session),
        tutor_chat_repo=TutorChatMessageRepository(session),
        gateway=_FakeGateway([MemoryUpdateResponse(facts_to_add=[candidate])]),
        student_external_id=STUDENT_ID,
        window_start=events[0].occurred_at - timedelta(minutes=1),
        window_end=events[-1].occurred_at + timedelta(minutes=1),
        session_spend_cents=0.0,
    )


def test_strength_fact_is_refused_when_measured_mastery_says_weak() -> None:
    """The AUD-L-13 reproduction, exactly: a well-evidenced, repetition-passing `strength`
    candidate for a skill the same database measures at 0.0.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            await _set_mastery(session, seed.skill_id, 0.0)

            result = await _consolidate_one(
                session, _strength_candidate(seed.skill_id, [e.event_id for e in events]), events
            )

            assert result.added == 0
            assert result.mastery_conflicts == 1
            # Not stored at any status - `provisional` is a real bound today but the
            # promotion criterion is repetition, so a second session would promote it.
            assert await memory_repo.list_facts_for_student(STUDENT_ID) == []

    asyncio.run(run())


def test_weak_skill_fact_is_refused_when_measured_mastery_says_proficient() -> None:
    """The other direction. Same defect: a claim about a child's ability contradicting the
    measurement sitting beside it.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            await _set_mastery(session, seed.skill_id, 1.0)

            result = await _consolidate_one(
                session, _weak_skill_candidate(seed.skill_id, [e.event_id for e in events]), events
            )

            assert result.added == 0
            assert result.mastery_conflicts == 1

    asyncio.run(run())


def test_a_consistent_fact_is_still_accepted() -> None:
    """The floor must not become "no ability facts at all" - the positive control."""

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            await _set_mastery(session, seed.skill_id, 0.95)

            result = await _consolidate_one(
                session, _strength_candidate(seed.skill_id, [e.event_id for e in events]), events
            )

            assert result.added == 1
            assert result.mastery_conflicts == 0
            assert (await _sole_active_fact(memory_repo)).fact_type == "strength"

    asyncio.run(run())


def test_a_skill_with_no_mastery_row_is_not_blocked() -> None:
    """No measurement means nothing to contradict, so the floor abstains rather than
    refusing. This is the deliberate hole in it: a never-assessed skill is exactly the
    case where the model's read of the events is the only evidence there is. It is safe
    because a skill with no mastery row has never been examined or studied, so there is
    no measurement for the fact to be wrong *about* - unlike AUD-L-13's reproduction,
    where a contradicting number existed and went unread.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]

            result = await _consolidate_one(
                session, _strength_candidate(seed.skill_id, [e.event_id for e in events]), events
            )

            assert result.added == 1
            assert result.mastery_conflicts == 0

    asyncio.run(run())


def test_the_floor_only_screens_ability_claims() -> None:
    """`misconception`, `hint_dependence` and the rest are claims about *how* a student
    works, not about a measured score, so mastery cannot contradict them. Screening them
    on `weighted_score` would silence the fact types that carry the most teaching value
    for a struggling student - the opposite of what AUD-L-13 asks for.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            await _set_mastery(session, seed.skill_id, 0.0)

            candidate = _strength_candidate(seed.skill_id, [e.event_id for e in events])
            candidate.fact_type = "hint_dependence"
            candidate.fact_text = "Reaches for a hint before attempting the first step."

            result = await _consolidate_one(session, candidate, events)

            assert result.added == 1
            assert result.mastery_conflicts == 0

    asyncio.run(run())


def test_the_floor_treats_the_threshold_itself_as_proficient() -> None:
    """Pins the boundary rather than leaving it to whichever comparison operator got
    typed. "Weak" is strictly below the cut everywhere else in the codebase
    (`topic_resolver`, `learning_gain`), and this floor reads the same shared constant so
    the three cannot drift - a second copy of the number is how one subsystem calls a
    skill weak while another calls it proficient, which is AUD-L-13's defect class one
    layer over.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            # Exactly at the cut: "weak" is strictly below it, so this is proficient and a
            # `strength` fact is consistent. Pins the boundary rather than leaving it to
            # whichever comparison operator got typed.
            await _set_mastery(session, seed.skill_id, WEAK_SKILL_THRESHOLD)

            result = await _consolidate_one(
                session, _strength_candidate(seed.skill_id, [e.event_id for e in events]), events
            )

            assert result.added == 1
            assert result.mastery_conflicts == 0

    asyncio.run(run())


def test_contradiction_demotes_then_supersedes_on_second_contradiction() -> None:
    """Plan §9: an opposite-polarity conflict demotes the existing fact to `contested`
    rather than overwriting it; only a *second* consecutive contradiction supersedes.

    Scripted on `hint_dependence`, a fact type whose polarity the model chooses. It used
    to script a `weak_skill` fact flipping to "positive", which D-460 #2's fix now
    normalises away: for the two ability types polarity is derived from the fact type, so
    a `weak_skill` candidate can never contradict a `weak_skill` fact - a regression after
    a strength is a *new* `weak_skill` fact, and the read path's recency ordering decides
    what is served (`test_a_later_regression_is_served_over_an_older_strength`).
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

            def hint_dependence(polarity: str, text: str) -> MemoryFactCandidate:
                return MemoryFactCandidate(
                    fact_type="hint_dependence",
                    skill_id=seed.skill_id,
                    fact_text=text,
                    polarity=polarity,  # type: ignore[arg-type]
                    confidence=0.6,
                    supporting_event_ids=event_ids,
                )

            # Round 1: establishes an active hint_dependence (negative) fact.
            gateway = _FakeGateway(
                [
                    MemoryUpdateResponse(
                        facts_to_add=[
                            hint_dependence("negative", "Relies on the full hint ladder.")
                        ]
                    )
                ]
            )
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
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

            strength_candidate = hint_dependence(
                "positive", "Now works through this skill without hints."
            )

            # Round 2: opposite-polarity candidate -> demote to contested.
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[strength_candidate])])
            result_2 = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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


def test_ability_fact_polarity_is_derived_from_the_fact_type_not_the_model() -> None:
    """E4 §4.3 / D-460 finding #2 (`MEMORY-POLARITY-DEFAULT`): the real model left
    `polarity` at its schema default on 98/120 `weak_skill` facts, so the contradiction
    protocol - which keys on polarity - almost never fired. For the two ability types the
    direction is not the model's to choose: `strength` IS positive and `weak_skill` IS
    negative (`_ABILITY_FACT_TYPES`, the same table the mastery floor already reads), so
    code sets it and the model's value is ignored. Deterministic core (CLAUDE.md rule 2).
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

            def defaulted_weak_skill() -> MemoryFactCandidate:
                # What the real model actually emits ~82% of the time: a weakness in the
                # text, `polarity` untouched at the "positive" default.
                return MemoryFactCandidate(
                    fact_type="weak_skill",
                    skill_id=seed.skill_id,
                    fact_text="May need extra support with this skill.",
                    confidence=0.6,
                    supporting_event_ids=event_ids,
                )

            assert defaulted_weak_skill().polarity == "positive"

            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[defaulted_weak_skill()])])
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            fact = await _sole_active_fact(memory_repo)
            assert fact.fact_type == "weak_skill"
            assert fact.structured_value["polarity"] == "negative"

            # A second defaulted weak_skill candidate is the SAME direction, so it must
            # reconfirm - not read as an opposite-polarity contradiction of itself.
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[defaulted_weak_skill()])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=window_start,
                window_end=window_end,
                session_spend_cents=0.0,
            )
            assert result.updated == 1
            assert result.contested == 0
            refreshed = await memory_repo.get_fact(fact.semantic_memory_id)
            assert refreshed is not None
            assert refreshed.status == "active"
            assert refreshed.structured_value["polarity"] == "negative"

    asyncio.run(run())


def test_polarity_is_explained_to_the_model_in_prompt_and_schema() -> None:
    """The other half of finding #2: neither the system prompt nor the schema told the model
    what `polarity` was for. Ability types are now code-derived (above); for every other
    fact type the model still chooses, so both the prompt and the field description must
    say what the field means. Descriptions travel to the model - the gateway sends
    `model_json_schema()` as the tool's `inputSchema`.
    """
    assert "polarity" in _SYSTEM_PROMPT
    description = MemoryFactCandidate.model_json_schema()["properties"]["polarity"].get(
        "description", ""
    )
    assert "negative" in description
    assert set(_ABILITY_FACT_TYPES) == {"strength", "weak_skill"}


def test_a_later_regression_is_served_over_an_older_strength() -> None:
    """E4 §3.4 end to end through the write path (`polarity_flip`, 985/985 served the stale
    fact): an active `strength` established first, then an evidenced `weak_skill` on the
    same skill a window later. The tutor read path must hand back the regression - the
    most recently confirmed fact - not the older, higher-confidence strength.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            base = datetime.now(UTC) - timedelta(days=14)
            success_events = [
                await _add_event(
                    memory_repo,
                    skill_id=seed.skill_id,
                    session_id=f"early-s{i % 2}",
                    payload={"outcome_label": "correct", "target_skill_id": seed.skill_id},
                    occurred_at=base + timedelta(hours=i),
                )
                for i in range(3)
            ]
            strength = MemoryFactCandidate(
                fact_type="strength",
                skill_id=seed.skill_id,
                fact_text="Solves this skill independently.",
                polarity="positive",
                confidence=0.7,
                supporting_event_ids=[e.event_id for e in success_events],
            )
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[strength])])
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=success_events[0].occurred_at - timedelta(minutes=1),
                window_end=success_events[-1].occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            served_before = await memory_repo.top_fact_for_skill(STUDENT_ID, seed.skill_id)
            assert served_before is not None and served_before.fact_type == "strength"

            regression_events = [
                await _add_event(
                    memory_repo,
                    skill_id=seed.skill_id,
                    session_id=f"late-s{i % 2}",
                    occurred_at=base + timedelta(days=7, hours=i),
                )
                for i in range(4)
            ]
            weak = MemoryFactCandidate(
                fact_type="weak_skill",
                skill_id=seed.skill_id,
                fact_text="Recent attempts on this skill went unresolved.",
                polarity="negative",
                confidence=0.6,
                supporting_event_ids=[e.event_id for e in regression_events],
            )
            gateway = _FakeGateway([MemoryUpdateResponse(facts_to_add=[weak])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=regression_events[0].occurred_at - timedelta(minutes=1),
                window_end=regression_events[-1].occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 1

            active = await memory_repo.list_facts_for_student(STUDENT_ID, statuses=("active",))
            assert {f.fact_type for f in active} == {"strength", "weak_skill"}
            served_after = await memory_repo.top_fact_for_skill(STUDENT_ID, seed.skill_id)
            assert served_after is not None
            assert served_after.fact_type == "weak_skill"

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
                    mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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
                mastery_repo=MasteryRepository(session),
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


# --- S43: the output cap, derived rather than fixed (D-115 carry-over (ii)) ----------


def test_consolidation_output_budget_scales_with_existing_fact_count() -> None:
    """The two largest lists in `MemoryUpdateResponse` are one item per existing fact.

    Measured against the serialized schema: 261 tokens at 1 live fact, 1733 at 10, 2712
    at 20 - so the old flat 1200 was under the real need from roughly 5 facts on. This is
    the same shape as the reranker (AUD-X-09), which sat truncating in production for a
    week, and deliberately *not* the shape of a RAG answer, whose length follows the
    question rather than the input (D-115 §10's correction).
    """
    budget_for = MemoryUpdateResponse.max_output_tokens_for
    assert budget_for(20) > budget_for(5)
    assert budget_for(0) > 0

    # Every count up to the safe bound clears both the measured need and the flat 1200
    # this replaced - the regression D-115 §10 shipped and had to correct was a derived
    # cap that came out *below* the constant it replaced at the low end.
    measured_need = {1: 261, 5: 1249, 10: 1733, 20: 2712}
    for facts, need in measured_need.items():
        budget = budget_for(facts)
        assert budget >= need, f"{facts} facts need ~{need} tokens, budget is {budget}"
        assert budget >= 1200, f"{facts} facts got {budget}, below the flat cap it replaced"

    # ...and the safe bound is honest: at it the budget still fits the gateway's ceiling,
    # past it it does not, which is exactly what the caller warns about.
    safe = MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS
    assert budget_for(safe) <= 4000
    assert budget_for(safe + 1) > 4000


def test_the_output_budget_admits_the_e4_worst_case_new_fact_slate() -> None:
    """D-460/R1: the base must hold a real window's worth of NEW facts.

    E4 measured a window of ~100 events across ~14 skills offering ~14 new-fact candidates
    at ~149 output tokens each - about 2,086 tokens - against a base of 1,280. The call
    stopped on `max_tokens` 29 times out of 30, at ZERO existing facts, which is the regime
    the old formula was most confident about. This asserts the regime the old one failed:
    the budget at no existing facts, where the per-fact term contributes nothing.
    """
    budget_for = MemoryUpdateResponse.max_output_tokens_for

    e4_candidates = 14
    tokens_per_new_fact = 149
    e4_worst_case = e4_candidates * tokens_per_new_fact  # 2,086
    assert budget_for(0) >= e4_worst_case, (
        f"a {e4_candidates}-candidate window needs ~{e4_worst_case} tokens; "
        f"the base is {budget_for(0)} - this is the E4 truncation, unfixed"
    )

    # ...and it fits under the gateway's hard ceiling with room for existing facts too, so
    # the fix does not just move the truncation to the first student who has any history.
    assert budget_for(0) < 4000
    assert MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS >= 10

    # No count loses budget relative to what it had before the raise (the D-115 10 floor
    # argument, which set the old base and still binds).
    for facts in (0, 1, 5, 10, 20):
        assert budget_for(facts) >= 1280 + 128 * facts


def test_consolidation_sends_a_fact_count_derived_budget() -> None:
    """A derived cap that never reaches the gateway is decoration - assert the wire."""

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

            budget_for = MemoryUpdateResponse.max_output_tokens_for

            # First pass: no existing facts, and it stores one.
            gateway = _FakeGateway([_weak_skill_response(seed.skill_id, event_ids)])
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=events[0].occurred_at - timedelta(minutes=1),
                window_end=events[-1].occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert gateway.max_output_tokens_seen == [budget_for(0)]

            # Second pass over the same student now has one live fact to reconfirm, so the
            # budget must be larger. A fixed cap makes these two numbers equal.
            gateway2 = _FakeGateway([MemoryUpdateResponse()])
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway2,
                student_external_id=STUDENT_ID,
                window_start=events[0].occurred_at - timedelta(minutes=1),
                window_end=events[-1].occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert gateway2.max_output_tokens_seen == [budget_for(1)]
            # The point of the two passes: a fixed cap makes these two numbers equal.
            assert budget_for(1) > budget_for(0)

    asyncio.run(run())


# --- UD-15: the payload is bounded to the most recently confirmed facts ------------------
#
# D-467 made `MAX_SAFE_EXISTING_FACTS` honest (11) and D-471 measured what happens past it: a
# ~26-fact student derives a 5,888-token budget, the gateway clamps it to 4,000, and 8/8 calls
# truncated. The user's decision (UD-15) is to send only the N most recently confirmed facts;
# older ones are still reconciled at apply time (`find_live_fact` reads the database, not the
# payload) and age out through retention. These tests pin the three halves of that: what is
# sent, what the store does with a fact that was not sent, and what gets logged.

_BOUND = MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS
_CONSOLIDATION_LOGGER = "intellichoice_memory.consolidation"


async def _seed_live_facts(
    session: AsyncSession,
    seed: Seed,
    count: int,
    *,
    fact_type: str = "weak_skill",
    polarity: str = "negative",
    tie_at: int | None = None,
) -> list[SemanticMemory]:
    """`count` active facts on `count` distinct skills, fact `i` confirmed `i` hours after a
    fixed base - so index `count - 1` is the most recent. Returned in index order.

    **Inserted out of recency order on purpose** (evens, then odds). `list_facts_for_student`
    has no `ORDER BY`, so a payload that merely followed insertion/heap order would pass a
    test that seeded oldest-first; this order is neither recency nor its reverse.

    `tie_at`: fact `tie_at` gets fact `tie_at + 1`'s timestamp and a higher confidence, so
    the pair straddling the cut is decided by the confidence tiebreak alone.
    """
    curriculum = CurriculumRepository(session)
    memory_repo = MemoryRepository(session)
    base = datetime(2026, 9, 1, tzinfo=UTC)
    skills = [seed.skill_id] + [
        (
            await curriculum.create_skill(Skill(topic_id=seed.topic_id, name=f"bounded_skill_{i}"))
        ).skill_id
        for i in range(1, count)
    ]
    facts: dict[int, SemanticMemory] = {}
    for i in [*range(0, count, 2), *range(1, count, 2)]:
        confirmed_at = base + timedelta(hours=i + 1 if i == tie_at else i)
        facts[i] = await memory_repo.add_fact(
            SemanticMemory(
                student_external_id=STUDENT_ID,
                fact_type=fact_type,
                topic_id=seed.topic_id,
                skill_id=skills[i],
                fact_text="May need extra support with this skill.",
                structured_value={"polarity": polarity},
                confidence=0.9 if i == tie_at else 0.6,
                evidence_event_ids=[f"seed-{i}"],
                status="active",
                first_observed_at=confirmed_at,
                last_confirmed_at=confirmed_at,
            )
        )
    return [facts[i] for i in range(count)]


class _RecordingMockProvider:
    """The real `MockBedrockProvider`, with the wire recorded: what the gateway actually
    handed the provider (the serialized payload and the clamped budget), not what the caller
    asked for. The mock ignores `max_output_tokens`, so a 5,888-token ask would "succeed"
    here too - the recorded budget is how this double tells the two apart.
    """

    def __init__(self) -> None:
        self._inner = MockBedrockProvider()
        self.payloads: list[dict] = []
        self.max_output_tokens_seen: list[int] = []

    async def raw_generate(self, **kwargs) -> RawGeneration:
        self.payloads.append(json.loads(kwargs["user_message"]))
        self.max_output_tokens_seen.append(kwargs["max_output_tokens"])
        return await self._inner.raw_generate(**kwargs)


def _bounded_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == "memory_consolidation_payload_bounded"]


def _bounded_counts(record: logging.LogRecord) -> tuple[int, int, int]:
    """(existing, sent, dropped) - read through `vars` because `extra=` fields are set on the
    record dynamically and are not attributes `LogRecord` declares."""
    fields = vars(record)
    return (
        fields["existing_fact_count"],
        fields["sent_fact_count"],
        fields["dropped_fact_count"],
    )


def test_a_26_fact_student_is_sent_only_the_11_most_recently_confirmed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Required behaviour 1, through the real gateway and the real mock provider: D-471's
    cohort size, bounded to `MAX_SAFE_EXISTING_FACTS`, newest first, ties by confidence."""

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            # Facts 14 and 15 share a timestamp; 14 has the higher confidence, so it - not
            # 15 - is the 11th fact sent. Without the tiebreak the cut is arbitrary.
            facts = await _seed_live_facts(session, seed, 26, tie_at=14)
            expected = [f.semantic_memory_id for f in reversed(facts[16:])] + [
                facts[14].semantic_memory_id
            ]
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            provider = _RecordingMockProvider()
            gateway = ResilientBedrockGateway(
                provider=provider,
                model_registry={BedrockTask.MEMORY_CONSOLIDATION: "anthropic.claude-test"},
                max_retries=0,
            )
            with caplog.at_level(logging.INFO, logger=_CONSOLIDATION_LOGGER):
                result = await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=TutorChatMessageRepository(session),
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=event.occurred_at - timedelta(minutes=1),
                    window_end=event.occurred_at + timedelta(minutes=1),
                    session_spend_cents=0.0,
                )

            assert len(provider.payloads) == 1
            sent = [f["semantic_memory_id"] for f in provider.payloads[0]["existing_facts"]]
            assert sent == expected
            assert provider.max_output_tokens_seen == [
                MemoryUpdateResponse.max_output_tokens_for(_BOUND)
            ]
            assert MemoryUpdateResponse.max_output_tokens_for(_BOUND) < 4000
            assert result.calls_attempted == 1
            assert result.calls_failed == 0

            (record,) = _bounded_records(caplog)
            assert _bounded_counts(record) == (26, _BOUND, 26 - _BOUND)

    asyncio.run(run())


def test_at_or_below_the_bound_the_payload_is_unchanged_and_nothing_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Required behaviour 2: exactly `MAX_SAFE_EXISTING_FACTS` live facts - every one sent,
    the budget derived from all of them, and no bounded event (nothing was dropped)."""

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            facts = await _seed_live_facts(session, seed, _BOUND)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([MemoryUpdateResponse()])
            with caplog.at_level(logging.INFO, logger=_CONSOLIDATION_LOGGER):
                await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=TutorChatMessageRepository(session),
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=event.occurred_at - timedelta(minutes=1),
                    window_end=event.occurred_at + timedelta(minutes=1),
                    session_spend_cents=0.0,
                )

            (seen,) = gateway.existing_fact_ids_seen
            assert sorted(seen) == sorted(f.semantic_memory_id for f in facts)
            assert gateway.max_output_tokens_seen == [
                MemoryUpdateResponse.max_output_tokens_for(_BOUND)
            ]
            assert _bounded_records(caplog) == []

    asyncio.run(run())


def test_a_fact_left_out_of_the_bounded_payload_is_still_reconciled_not_duplicated() -> None:
    """Required behaviour 3. The oldest fact is not sent, the model (never having seen it)
    proposes the same skill as a NEW fact - first agreeing, then contradicting - and apply
    time still finds the live row in the database: reconfirmed, then demoted, never a second
    live row. This is why bounding the payload cannot create duplicates."""

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            # `hint_dependence`: model-chosen polarity, so the same fact type can contradict.
            facts = await _seed_live_facts(
                session, seed, _BOUND + 1, fact_type="hint_dependence", polarity="negative"
            )
            oldest = facts[0]
            events = [
                await _add_event(memory_repo, skill_id=seed.skill_id, session_id=f"s{i % 2}")
                for i in range(3)
            ]
            event_ids = [e.event_id for e in events]

            def candidate(polarity: Literal["positive", "negative"]) -> MemoryUpdateResponse:
                return MemoryUpdateResponse(
                    facts_to_add=[
                        MemoryFactCandidate(
                            fact_type="hint_dependence",
                            skill_id=seed.skill_id,
                            fact_text="Often asks for a hint on this skill.",
                            polarity=polarity,
                            confidence=0.7,
                            supporting_event_ids=event_ids,
                        )
                    ]
                )

            async def consolidate(
                response: MemoryUpdateResponse,
            ) -> tuple[_FakeGateway, ConsolidationResult]:
                gateway = _FakeGateway([response])
                result = await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=TutorChatMessageRepository(session),
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=events[0].occurred_at - timedelta(minutes=1),
                    window_end=events[-1].occurred_at + timedelta(minutes=1),
                    session_spend_cents=0.0,
                )
                return gateway, result

            async def rows_for_skill() -> list[SemanticMemory]:
                every = await memory_repo.list_facts_for_student(
                    STUDENT_ID, statuses=("active", "provisional", "contested", "superseded")
                )
                return [f for f in every if f.skill_id == seed.skill_id]

            # Same direction: the unseen fact is reconfirmed in place.
            gateway, result = await consolidate(candidate("negative"))
            assert oldest.semantic_memory_id not in gateway.existing_fact_ids_seen[0]
            assert (result.added, result.updated) == (0, 1)
            (row,) = await rows_for_skill()
            assert row.semantic_memory_id == oldest.semantic_memory_id
            assert row.confidence == 0.7

            # The reconfirmation made it the NEWEST fact, so it is now sent and the next-
            # oldest is the one dropped - recency is re-read per call, not frozen.
            await session.refresh(row)
            gateway, result = await consolidate(candidate("positive"))
            assert oldest.semantic_memory_id in gateway.existing_fact_ids_seen[0]
            assert facts[1].semantic_memory_id not in gateway.existing_fact_ids_seen[0]
            # Opposite direction against a live fact: demoted, not added alongside.
            assert (result.added, result.contested) == (0, 1)
            (row,) = await rows_for_skill()
            assert row.status == "contested"

    asyncio.run(run())


def test_dropping_facts_logs_one_counts_only_info_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Required behaviour 4, at the boundary: 12 live facts drops exactly one. The event is
    INFO (a bounded payload is the designed path now, not a fault), carries counts only, and
    the old oversize WARNING - a condition that can no longer occur - is gone. AUD-X-11: a
    bound that logs nothing is a decision nobody can audit."""

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            await _seed_live_facts(session, seed, _BOUND + 1)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([MemoryUpdateResponse()])
            with caplog.at_level(logging.INFO, logger=_CONSOLIDATION_LOGGER):
                await consolidate_student_window(
                    memory_repo=memory_repo,
                    mastery_repo=MasteryRepository(session),
                    tutor_chat_repo=TutorChatMessageRepository(session),
                    gateway=gateway,
                    student_external_id=STUDENT_ID,
                    window_start=event.occurred_at - timedelta(minutes=1),
                    window_end=event.occurred_at + timedelta(minutes=1),
                    session_spend_cents=0.0,
                )

            (record,) = _bounded_records(caplog)
            assert record.levelno == logging.INFO
            assert _bounded_counts(record) == (_BOUND + 1, _BOUND, 1)
            # Counts only: no student id, fact id or fact text anywhere on the record.
            # `message`/`asctime` are added by the capture handler's formatter, not the caller.
            standard = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}
            extras = {k: v for k, v in vars(record).items() if k not in standard}
            assert set(extras) == {"existing_fact_count", "sent_fact_count", "dropped_fact_count"}
            assert all(isinstance(v, int) for v in extras.values())

            # ...and nothing at WARNING or above: the oversize warning this replaced is gone.
            assert [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING] == []
            assert gateway.max_output_tokens_seen == [
                MemoryUpdateResponse.max_output_tokens_for(_BOUND)
            ]

    asyncio.run(run())


def test_the_model_is_told_the_existing_fact_list_is_bounded() -> None:
    """D4: under the mock this is inert, but the real model must not read an unlisted fact
    as an absent one. The D-472 polarity wording stays intact alongside it."""
    assert "most recently confirmed" in _SYSTEM_PROMPT
    assert "not listed" in _SYSTEM_PROMPT
    assert "Polarity is how the system detects" in _SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# AUD-F-34 / D-141: input-bounded batching, and the silent-failure fix.
#
# The pure batching tests do not touch Postgres and are deliberately not written
# through `consolidate_student_window`: `_batch_summaries` is where the arithmetic
# lives, and driving it through a database plus a fake gateway would test the
# plumbing while leaving the boundary conditions unexercised. The behavioural
# tests below it *do* go through the real entrypoint.
# ---------------------------------------------------------------------------


def _summary(event_id: str, chars: int) -> MemoryEventSummary:
    return MemoryEventSummary(event_id=event_id, event_type="study_outcome", summary="x" * chars)


# **The sizes below are absolute, not derived from the constants under test, and that is the
# whole point.** The first version of these tests computed its inputs as fractions of
# `_MAX_EVENT_CHARS_PER_CALL` - so when the bound was raised to 100,000,000 tokens as a control,
# the inputs grew with it and all of them still passed. A test that scales with the thing it
# pins cannot fail. Controls were then re-run against both constants and these do fail:
# removing the input bound collapses the split/truncate assertions, and removing the call cap
# collapses the drop assertion.
_ASSUMED_CHARS_PER_CALL = 60_000  # 20,000 tokens x 3 chars/token
_ASSUMED_CALL_CAP = 4
# Big enough that two cannot share one call (2 x 40,000 > 60,000), small enough that one can.
_BIG = 40_000


def test_the_batching_constants_are_what_these_tests_assume() -> None:
    """The single place to update when the bound is tuned on purpose - and a loud, obvious
    failure when it is tuned by accident. Every absolute number below depends on these two.
    """
    assert _MAX_EVENT_CHARS_PER_CALL == _ASSUMED_CHARS_PER_CALL
    assert _MAX_CALLS_PER_STUDENT == _ASSUMED_CALL_CAP


def test_small_event_set_still_makes_exactly_one_call() -> None:
    """The regression guard for the fix itself: batching must not turn the ordinary case into
    several paid calls. Every other test in this file covers one call implicitly; this says so.
    """
    batches, dropped = _batch_summaries([_summary(f"e{i}", 100) for i in range(50)])
    assert len(batches) == 1
    assert dropped == 0
    assert [s.event_id for s in batches[0]] == [f"e{i}" for i in range(50)]


def test_events_are_split_when_they_exceed_the_per_call_budget() -> None:
    """Three 40,000-char events cannot share a 60,000-char call, so this is 3 batches.
    Unbounded, it would be 1 - which is what the control confirmed.
    """
    batches, dropped = _batch_summaries([_summary(f"e{i}", _BIG) for i in range(3)])
    assert [len(b) for b in batches] == [1, 1, 1]
    assert dropped == 0
    for batch in batches:
        assert sum(_summary_chars(s) for s in batch) <= _ASSUMED_CHARS_PER_CALL


def test_batches_stay_chronological_and_never_reorder() -> None:
    """Order is load-bearing: a later batch sees the facts an earlier one wrote, so reordering
    silently changes which of two conflicting facts wins a contradiction.
    """
    summaries = [_summary(f"e{i:02d}", _BIG) for i in range(4)]
    batches, _ = _batch_summaries(summaries)
    assert len(batches) > 1, "test needs more than one batch to be meaningful"
    flattened = [s.event_id for batch in batches for s in batch]
    assert flattened == ["e00", "e01", "e02", "e03"]


def test_over_the_call_cap_the_oldest_events_are_dropped_and_counted() -> None:
    """Seven un-shareable events against a cap of 4: the three OLDEST go. Recency is what a
    memory system wants, and the dropped count is asserted because a silent cap is the failure
    mode being fixed. Without the cap this is 7 batches and 0 dropped.
    """
    summaries = [_summary(f"e{i:02d}", _BIG) for i in range(7)]
    batches, dropped = _batch_summaries(summaries)
    assert len(batches) == 4
    assert dropped == 3
    kept = [s.event_id for batch in batches for s in batch]
    assert kept == ["e03", "e04", "e05", "e06"]
    assert "e00" not in kept


def test_a_single_event_larger_than_the_budget_is_truncated_not_dropped() -> None:
    """Without this the batcher either loops forever or emits a batch guaranteed to fail.
    Truncation is marked; dropping would make evidence vanish silently. Unbounded, the summary
    comes back at its original 1,000,000 chars and the length assertion fails.
    """
    batches, dropped = _batch_summaries([_summary("huge", 1_000_000)])
    assert dropped == 0
    assert len(batches) == 1 and len(batches[0]) == 1
    only = batches[0][0]
    assert only.event_id == "huge"
    assert only.summary.endswith("…[truncated]")
    assert len(only.summary) < 1_000_000
    assert _summary_chars(only) <= _ASSUMED_CHARS_PER_CALL


def test_no_events_means_no_batches_and_no_calls() -> None:
    assert _batch_summaries([]) == ([], 0)


def test_every_call_failing_is_reported_rather_than_swallowed() -> None:
    """AUD-F-34's core: this exact shape used to return zeros that the CLI printed as a
    completed run, and exit 0. The counts now travel with the result.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([BedrockGatewayError("prompt is too long")])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0
            assert result.calls_attempted == 1
            assert result.calls_failed == 1
            # The condition the CLI turns into a non-zero exit code.
            assert result.calls_failed == result.calls_attempted

    asyncio.run(run())


def test_a_truncated_consolidation_is_a_failed_call_not_an_empty_update() -> None:
    """E4/D-460's silent-success path, at the layer that reports it.

    Truncation on this task does not arrive as malformed JSON. Converse returns the partial
    `toolUse` input, which for a model cut off before its first key is `{}` - and `{}` is a
    *valid* `MemoryUpdateResponse`, because all three of its lists default to empty. So the
    real run reported `added=0, calls_failed=0, exit 0` for 10 of 10 students whose calls had
    all truncated: identical, from the outside, to ten students with nothing to consolidate.

    The gateway now fails closed on the stop reason, and `OutputTruncatedError` is a
    `BedrockGatewayError` - so it lands in the branch AUD-F-34 built and the count travels
    with the result. This test pins the whole path, not just the base class: a future
    refactor that catches `StructuredOutputError` separately, or that "recovers" a truncated
    response into an empty update, fails here.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway(
                [
                    OutputTruncatedError(
                        "model hit max_output_tokens=1280 before completing the "
                        "MemoryUpdateResponse response",
                        cost_cents=0.4,
                    )
                ]
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.added == 0
            assert result.calls_attempted == 1
            # The whole point: a truncated call is a FAILED call, never a quiet zero.
            assert result.calls_failed == 1
            assert result.calls_failed == result.calls_attempted  # the CLI's exit-1 condition
            assert result.cost_cents > 0  # the truncated call still cost money

    asyncio.run(run())


class _TruncatingProvider:
    """A `BedrockProvider` that reproduces real Bedrock on `max_tokens` for this task.

    Not a fake gateway: the point of this double is to exercise the REAL
    `ResilientBedrockGateway` underneath `consolidate_student_window`, because the defect
    lived in the gateway's validate-then-check-truncation ordering and a fake gateway
    cannot show it. `text="{}"` is what Converse hands back - the partial `toolUse` input
    of a model cut off before its first key.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def raw_generate(self, **kwargs) -> RawGeneration:
        del kwargs
        self.calls += 1
        return RawGeneration(
            text="{}",
            input_tokens=500,
            output_tokens=1280,
            truncated=True,
            stop_reason="max_tokens",
        )


def test_a_truncated_call_through_the_real_gateway_is_never_a_silent_zero() -> None:
    """The end-to-end reproduction of E4/D-460, through the real gateway.

    Everything above this test doubles the gateway; this one doubles only the *provider*,
    so the path under test is the one that actually shipped: provider returns `{}` with
    `stopReason=max_tokens` -> gateway -> `consolidate_student_window` -> the result the CLI
    reads. Before the fix this returned `added=0, calls_failed=0` and the CLI exited 0.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            provider = _TruncatingProvider()
            gateway = ResilientBedrockGateway(
                provider=provider,
                model_registry={BedrockTask.MEMORY_CONSOLIDATION: "anthropic.claude-test"},
                max_retries=0,
            )
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert provider.calls == 1  # D-115: no repair retry under the same ceiling
            assert result.added == 0
            assert result.calls_attempted == 1
            assert result.calls_failed == 1  # was 0 - the whole defect
            assert result.calls_failed == result.calls_attempted  # the CLI's exit-1 condition

            # And nothing was written: a truncated response must not mutate the store.
            written = await memory_repo.list_facts_for_student(
                STUDENT_ID, statuses=("active", "provisional", "contested", "superseded")
            )
            assert written == []

    asyncio.run(run())


def test_a_successful_call_reports_no_failures() -> None:
    """The negative arm. Without it, a result object that always reported failures would
    pass the test above and exit non-zero on every healthy run.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([_weak_skill_response(seed.skill_id, [event.event_id])])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.calls_attempted == 1
            assert result.calls_failed == 0
            assert result.budget_stopped is False

    asyncio.run(run())


def test_budget_exhaustion_is_not_counted_as_a_failed_call() -> None:
    """`CostBudgetExceededError` is the run budget working. Counting it as a failure would
    make a correctly-bounded run exit non-zero and page someone every week.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            seed = await _seed_topic_skill(session)
            memory_repo = MemoryRepository(session)
            tutor_chat_repo = TutorChatMessageRepository(session)
            event = await _add_event(memory_repo, skill_id=seed.skill_id, session_id="s1")

            gateway = _FakeGateway([CostBudgetExceededError("budget would be exceeded")])
            result = await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=MasteryRepository(session),
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=STUDENT_ID,
                window_start=event.occurred_at - timedelta(minutes=1),
                window_end=event.occurred_at + timedelta(minutes=1),
                session_spend_cents=0.0,
            )
            assert result.calls_failed == 0
            assert result.calls_attempted == 0
            assert result.budget_stopped is True

    asyncio.run(run())


def test_the_consolidation_call_timeout_leaves_room_for_the_largest_output_budget() -> None:
    """D-141 §6: this job times out on *output* generation, not input, and the output budget
    scales with a student's existing fact count. 20 s (every interactive surface's value, and
    this job's original) does not finish a 2176-token structured response; a student at the
    `MAX_SAFE_EXISTING_FACTS` ceiling asks for nearly 4000.

    Pinned as a test rather than left as a comment because the failure it prevents is invisible:
    a timeout here costs 3 attempts, two timeouts trip the circuit breaker at 5, and the run
    ends having printed a summary. Also asserts the input bound still exists - raising the
    timeout is only safe because the work is bounded on the other axis.
    """
    settings = MemoryConsolidationSettings()
    assert settings.bedrock_call_timeout_s >= 60.0, (
        "a background job's timeout must fit the largest output budget it can ask for; "
        f"max_output_tokens_for(MAX_SAFE_EXISTING_FACTS) is "
        f"{MemoryUpdateResponse.max_output_tokens_for(MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS)}"
    )
    # The other half of the pair: the timeout may only be generous because the input is capped.
    assert _MAX_EVENT_TOKENS_PER_CALL <= 40_000
    assert _MAX_CALLS_PER_STUDENT <= 8
