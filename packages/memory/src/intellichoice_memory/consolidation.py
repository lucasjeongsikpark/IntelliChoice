"""S25 memory consolidation (SPEC §5.15.4, plan §9): deterministic pre-aggregation ->
one `MEMORY_CONSOLIDATION` call -> deterministic validation (fail closed) -> upsert.

Two public entrypoints share the same core (`_consolidate_events`):
`consolidate_student_session` (`learning_api.graph.nodes.finalize_exam`, right after a
post-exam completes - plan §9 trigger (a), "session-scoped consolidation of that
cycle") and `consolidate_student_window` (`consolidate_cli.py`'s weekly batch over
every student with activity in a rolling window - trigger (b), SPEC §5.15.4's Sunday
job; manual `make memory-consolidate` in dev, same "schedule later" posture
`youtube-sync`/`webcontent-sync` already established).

Idempotent per (student, window): re-running against an unchanged set of events can
only reconfirm facts already derived from them (the `events` list sent to the model is
entirely sourced from `learning_events`), never invent a new fact_type/skill
combination with no supporting event.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from intellichoice_db.models.memory import LearningEvent, SemanticMemory
from intellichoice_db.repositories.memory import LIVE_STATUSES, MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    MemoryConsolidationPayload,
    MemoryEventSummary,
    MemoryExistingFact,
    MemoryUpdateResponse,
)
from intellichoice_shared.pii_redaction import contains_pii_pattern

from intellichoice_memory.events import CHAT_TURN, render_event_summary

logger = logging.getLogger(__name__)

# Plan §9's closed fact-type enum - anything else a model proposes is dropped, not
# stored (same "hallucinated key rejects the candidate" posture as D-026).
FACT_TYPES = frozenset(
    {
        "strength",
        "weak_skill",
        "misconception",
        "explanation_preference",
        "scaffolding_level",
        "vocabulary_difficulty",
        "guessing_pattern",
        "hint_dependence",
        "improvement",
        "effective_intervention",
        "open_question",
        "next_skill_recommendation",
    }
)

# Plan §9: "a new stable fact needs >=3 supporting events across >=2 sessions; below
# that it's stored as status=provisional (never read by the tutor payload)."
MIN_EVIDENCE_EVENTS = 3
MIN_EVIDENCE_SESSIONS = 2

# S43: was a flat 1200 over a response whose two largest lists are one item per *existing
# fact* - see `MemoryUpdateResponse.max_output_tokens_for` for the measurement and for why
# this shape, unlike a RAG answer's, really does scale with its input.

_SYSTEM_PROMPT = (
    "You are a memory consolidation assistant for a K-12 math tutoring system. Given a "
    "student's recent learning events and their existing durable facts, propose updates "
    "to their long-term memory. Only propose a fact when the events genuinely support "
    "it - do not speculate. Never infer personality, medical, or psychological traits. "
    "Only cite event_id values that appear in the events you were given. Use only the "
    "allowed fact types."
)


@dataclass(frozen=True)
class ConsolidationResult:
    added: int
    updated: int
    contested: int
    expired: int
    cost_cents: float


def _meets_stability_bar(event_ids: list[str], events_by_id: dict[str, LearningEvent]) -> bool:
    matched = [events_by_id[eid] for eid in event_ids if eid in events_by_id]
    unique_sessions = {e.session_id for e in matched}
    return len(matched) >= MIN_EVIDENCE_EVENTS and len(unique_sessions) >= MIN_EVIDENCE_SESSIONS


def _verify_evidence(
    candidate_ids: list[str],
    events_by_id: dict[str, LearningEvent],
    *,
    student_external_id: str,
) -> list[str]:
    """Re-derives trust the same way `chat_api.services.qa._verify_citations` does for
    RAG citations (D-038): a model-cited id is only trusted once code confirms it's a
    real event belonging to this student inside the window this call was built from.
    `events_by_id` is already scoped to exactly that (student, window) by its caller,
    so this is a defense-in-depth re-check of that invariant, not a second query.
    """
    verified = []
    for eid in candidate_ids:
        event = events_by_id.get(eid)
        if event is None or event.student_external_id != student_external_id:
            continue
        verified.append(eid)
    return verified


async def consolidate_student_window(
    *,
    memory_repo: MemoryRepository,
    tutor_chat_repo: TutorChatMessageRepository,
    gateway: BedrockGateway,
    student_external_id: str,
    window_start: datetime,
    window_end: datetime,
    session_spend_cents: float,
) -> ConsolidationResult:
    """Trigger (b): SPEC §5.15.4's weekly batch - every event in `[window_start,
    window_end)`, regardless of which learning-session thread produced it.
    """
    events = await memory_repo.list_events_in_window(student_external_id, window_start, window_end)
    return await _consolidate_events(
        memory_repo=memory_repo,
        tutor_chat_repo=tutor_chat_repo,
        gateway=gateway,
        student_external_id=student_external_id,
        events=events,
        chat_window_start=window_start,
        chat_window_end=window_end,
        session_spend_cents=session_spend_cents,
    )


async def consolidate_student_session(
    *,
    memory_repo: MemoryRepository,
    tutor_chat_repo: TutorChatMessageRepository,
    gateway: BedrockGateway,
    student_external_id: str,
    session_id: str,
    session_spend_cents: float,
) -> ConsolidationResult:
    """Trigger (a): plan §9's "session-scoped consolidation of that cycle" - every
    event this learning-session thread produced (pre-exam through post-exam), called
    right after `finalize_exam` completes a post-exam.
    """
    events = await memory_repo.list_events_for_session(student_external_id, session_id)
    if not events:
        return ConsolidationResult(added=0, updated=0, contested=0, expired=0, cost_cents=0.0)
    occurred_ats = [event.occurred_at for event in events]
    return await _consolidate_events(
        memory_repo=memory_repo,
        tutor_chat_repo=tutor_chat_repo,
        gateway=gateway,
        student_external_id=student_external_id,
        events=events,
        chat_window_start=min(occurred_ats),
        chat_window_end=max(occurred_ats) + timedelta(minutes=1),
        session_spend_cents=session_spend_cents,
    )


async def _consolidate_events(
    *,
    memory_repo: MemoryRepository,
    tutor_chat_repo: TutorChatMessageRepository,
    gateway: BedrockGateway,
    student_external_id: str,
    events: list[LearningEvent],
    chat_window_start: datetime,
    chat_window_end: datetime,
    session_spend_cents: float,
) -> ConsolidationResult:
    if not events:
        return ConsolidationResult(added=0, updated=0, contested=0, expired=0, cost_cents=0.0)
    events_by_id = {e.event_id: e for e in events}

    chat_messages = await tutor_chat_repo.list_for_student_in_window(
        student_external_id, chat_window_start, chat_window_end
    )
    chat_text_by_message_id = {m.message_id: m.redacted_student_message for m in chat_messages}

    def _chat_text_for(event: LearningEvent) -> str | None:
        if event.event_type != CHAT_TURN:
            return None
        message_id = event.structured_payload.get("tutor_chat_message_id")
        if not isinstance(message_id, str):
            return None
        return chat_text_by_message_id.get(message_id)

    event_summaries = [
        MemoryEventSummary(
            event_id=event.event_id,
            event_type=event.event_type,
            topic_id=event.topic_id,
            skill_id=event.skill_id,
            summary=render_event_summary(
                event.event_type, event.structured_payload, chat_text=_chat_text_for(event)
            ),
        )
        for event in events
    ]

    existing_facts = await memory_repo.list_facts_for_student(
        student_external_id, statuses=LIVE_STATUSES
    )
    existing_payload = [
        MemoryExistingFact(
            semantic_memory_id=fact.semantic_memory_id,
            fact_type=fact.fact_type,
            skill_id=fact.skill_id,
            fact_text=fact.fact_text,
            status=fact.status,
            confidence=fact.confidence,
        )
        for fact in existing_facts
    ]

    payload = MemoryConsolidationPayload(
        events=event_summaries,
        existing_facts=existing_payload,
        allowed_fact_types=sorted(FACT_TYPES),
    )

    max_output_tokens = MemoryUpdateResponse.max_output_tokens_for(len(existing_payload))
    if len(existing_payload) > MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS:
        # The derived budget is above the gateway's hard ceiling, so it will be clamped
        # and this student's consolidation *can* truncate. Bounding the payload is the
        # real fix and is a behaviour decision (which facts to drop) - logged rather than
        # guessed, so it arrives with a count attached. AUD-X-11's lesson: a failure mode
        # that logs nothing is a failure mode nobody finds.
        logger.warning(
            "memory_consolidation_payload_oversized",
            extra={
                # A count, not an id: the decision this informs is "should the payload be
                # bounded", which needs the distribution, not who. Every other `extra=` in
                # the codebase is counts and reasons; this keeps that floor.
                "existing_fact_count": len(existing_payload),
                "max_safe_existing_facts": MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS,
                "derived_max_output_tokens": max_output_tokens,
            },
        )

    try:
        result = await gateway.generate_structured(
            task=BedrockTask.MEMORY_CONSOLIDATION,
            system_prompt=_SYSTEM_PROMPT,
            payload=payload,
            response_model=MemoryUpdateResponse,
            max_output_tokens=max_output_tokens,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("memory consolidation call failed, no facts changed: %s", exc)
        return ConsolidationResult(
            added=0, updated=0, contested=0, expired=0, cost_cents=exc.cost_cents
        )

    update = result.value
    added = updated = contested = expired = 0

    for candidate in update.facts_to_add:
        if candidate.fact_type not in FACT_TYPES:
            continue
        if contains_pii_pattern(candidate.fact_text):
            continue
        verified_ids = _verify_evidence(
            candidate.supporting_event_ids, events_by_id, student_external_id=student_external_id
        )
        if not verified_ids:
            continue

        status = "active" if _meets_stability_bar(verified_ids, events_by_id) else "provisional"
        existing_live = await memory_repo.find_live_fact(
            student_external_id, candidate.fact_type, candidate.skill_id
        )

        if existing_live is None:
            await memory_repo.add_fact(
                SemanticMemory(
                    student_external_id=student_external_id,
                    fact_type=candidate.fact_type,
                    topic_id=candidate.topic_id,
                    skill_id=candidate.skill_id,
                    fact_text=candidate.fact_text,
                    structured_value={**candidate.structured_value, "polarity": candidate.polarity},
                    confidence=candidate.confidence,
                    evidence_event_ids=verified_ids,
                    status=status,
                )
            )
            added += 1
            continue

        if existing_live.structured_value.get("polarity", "positive") == candidate.polarity:
            # Same-direction duplicate proposal - treat as reconfirmation, not a new
            # row. Reconfirming a `contested` fact returns it to `active` (D-074).
            await memory_repo.reconfirm_fact(
                existing_live.semantic_memory_id,
                fact_text=candidate.fact_text,
                confidence=candidate.confidence,
                evidence_event_ids=verified_ids,
            )
            await memory_repo.promote_if_eligible(existing_live.semantic_memory_id)
            updated += 1
            continue

        # Plan §9: opposite-polarity conflict demotes rather than replaces - the first
        # contradiction only demotes the existing fact (no new row yet: "one bad day
        # shouldn't relabel a student"). Only when the existing fact is *already*
        # `contested` (a second consecutive contradiction) does a new fact get created
        # and supersede it.
        if existing_live.status != "contested":
            await memory_repo.demote_to_contested(existing_live.semantic_memory_id)
            contested += 1
            continue

        new_fact = await memory_repo.add_fact(
            SemanticMemory(
                student_external_id=student_external_id,
                fact_type=candidate.fact_type,
                topic_id=candidate.topic_id,
                skill_id=candidate.skill_id,
                fact_text=candidate.fact_text,
                structured_value={**candidate.structured_value, "polarity": candidate.polarity},
                confidence=candidate.confidence,
                evidence_event_ids=verified_ids,
                status=status,
            )
        )
        added += 1
        await memory_repo.supersede_fact(existing_live.semantic_memory_id, superseded_by=new_fact)
        contested += 1

    for fact_update in update.facts_to_update:
        existing_fact = await memory_repo.get_fact(fact_update.semantic_memory_id)
        if existing_fact is None or existing_fact.student_external_id != student_external_id:
            continue
        if contains_pii_pattern(fact_update.fact_text):
            continue
        verified_ids = _verify_evidence(
            fact_update.supporting_event_ids, events_by_id, student_external_id=student_external_id
        )
        if not verified_ids:
            continue
        await memory_repo.reconfirm_fact(
            fact_update.semantic_memory_id,
            fact_text=fact_update.fact_text,
            confidence=fact_update.confidence,
            evidence_event_ids=verified_ids,
        )
        await memory_repo.promote_if_eligible(fact_update.semantic_memory_id)
        updated += 1

    for fact_id in update.facts_to_expire:
        existing_fact = await memory_repo.get_fact(fact_id)
        if existing_fact is None or existing_fact.student_external_id != student_external_id:
            continue
        await memory_repo.expire_fact(fact_id)
        expired += 1

    return ConsolidationResult(
        added=added,
        updated=updated,
        contested=contested,
        expired=expired,
        cost_cents=result.cost_cents,
    )
