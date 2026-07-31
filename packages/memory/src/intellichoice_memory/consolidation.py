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
    CostBudgetExceededError,
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


# AUD-F-34 (D-141): the payload had no *input* bound at all. The gateway bounds output tokens
# and per-run spend; nothing bounded how much went in, so one week of a load-tested student's
# tutor chat built a 215,355-token prompt against Haiku 4.5's 200,000-token context and every
# call failed - while the process exited 0.
#
# 120k rather than something nearer the 200k ceiling, because this bounds only the *events*
# half of the payload: `existing_facts`, the system prompt, the JSON schema and the derived
# output budget share the same window, and the size below is a character heuristic rather than
# a real tokenizer.
_MAX_EVENT_TOKENS_PER_CALL = 120_000
# Pessimistic on purpose. English prose runs ~4 chars/token; JSON with short keys and uuid-ish
# ids is denser, and *under*-estimating is precisely the failure this constant exists to
# prevent - so the estimate is allowed to be wrong only in the direction that costs a call.
_CHARS_PER_TOKEN = 3.0
_MAX_EVENT_CHARS_PER_CALL = int(_MAX_EVENT_TOKENS_PER_CALL * _CHARS_PER_TOKEN)
# Bounds paid calls per student per run deterministically. Without it the number of model calls
# is a function of chat volume, which is the same unbounded shape that produced AUD-F-34 one
# layer up: a fix that turns "one failing call" into "N succeeding calls" has to say what N is.
_MAX_CALLS_PER_STUDENT = 4


@dataclass(frozen=True)
class ConsolidationResult:
    added: int
    updated: int
    contested: int
    expired: int
    cost_cents: float
    # AUD-F-34's reporting half. `calls_attempted == calls_failed` with a non-zero count is the
    # exact condition that used to print "Consolidation run complete" and exit 0, so the caller
    # needs to be able to see it rather than infer it from `added == 0` - which is also what a
    # student with nothing to consolidate looks like.
    calls_attempted: int = 0
    calls_failed: int = 0
    # Events dropped because the student exceeded `_MAX_CALLS_PER_STUDENT`. Reported so the
    # cap's cost is visible; a silent cap is the thing D-105 §4's mock-provider lesson is about.
    events_dropped: int = 0
    # True when the run budget stopped this student early. Distinct from `calls_failed` because
    # it is designed behaviour, not a fault, and must not make the process exit non-zero.
    budget_stopped: bool = False


@dataclass
class _RunningTotals:
    """Mutable accumulator across one student's batches.

    A plain dataclass rather than threading six return values through the batch loop: the
    counts are genuinely accumulated across calls, and `ConsolidationResult` stays frozen so
    callers cannot be handed something that mutates under them.
    """

    added: int = 0
    updated: int = 0
    contested: int = 0
    expired: int = 0
    cost_cents: float = 0.0
    calls_attempted: int = 0
    calls_failed: int = 0
    events_dropped: int = 0
    budget_stopped: bool = False

    def as_result(self) -> ConsolidationResult:
        return ConsolidationResult(
            added=self.added,
            updated=self.updated,
            contested=self.contested,
            expired=self.expired,
            cost_cents=self.cost_cents,
            calls_attempted=self.calls_attempted,
            calls_failed=self.calls_failed,
            events_dropped=self.events_dropped,
            budget_stopped=self.budget_stopped,
        )


async def _maybe_promote(
    memory_repo: MemoryRepository, semantic_memory_id: str, created_this_run: set[str]
) -> None:
    """Promote a reconfirmed fact, unless this run is the thing that created it.

    **This guard exists to avoid amplifying AUD-F-35, not to fix it.** `promote_if_eligible`
    promotes any `provisional` fact unconditionally, despite its name and despite
    `reconfirm_fact`'s docstring stating that "promotion has its own evidence-bar check" - so
    plan §9's ">=3 supporting events across >=2 sessions" bar is applied when a fact is created
    and bypassed the next time it is reconfirmed. That is a pre-existing defect and fixing it
    changes what the tutor reads, which is a product decision (filed, not taken).

    What batching would otherwise add is a *new* path into it: before this change one student
    got one call per run, so a fact could not be created and reconfirmed inside the same run.
    Now it can, several times over. Excluding this run's own creations keeps multi-batch
    students behaving exactly as single-batch ones do today - the bug is neither fixed nor
    made worse, which is the most a fix for a different finding should do.
    """
    if semantic_memory_id in created_this_run:
        return
    await memory_repo.promote_if_eligible(semantic_memory_id)


def _summary_chars(summary: MemoryEventSummary) -> int:
    """What one event summary costs in the serialised payload, counted rather than guessed.

    `model_dump_json` is what the gateway actually sends (`payload.model_dump_json()`), so
    measuring the same serialisation is the only estimate that cannot drift from it - a
    hand-rolled `len(summary.summary)` would miss the ids, keys and quoting, which for short
    summaries is most of the bytes.
    """
    return len(summary.model_dump_json())


def _truncate_summary(summary: MemoryEventSummary, budget_chars: int) -> MemoryEventSummary:
    """Shrink one pathologically large event summary to fit a call on its own.

    A single event bigger than the whole per-call budget cannot be packed anywhere, so
    without this the batcher either loops forever or emits a batch guaranteed to fail. The
    choice made here is to **truncate the text and mark it**, not to drop the event: an event
    dropped silently is evidence that vanishes, while a marked truncation is still evidence
    and is visible to anyone reading the payload or this log line.
    """
    overhead = _summary_chars(summary) - len(summary.summary)
    keep = max(0, budget_chars - overhead - len(_TRUNCATION_MARKER))
    logger.warning(
        "memory_consolidation_event_truncated",
        extra={
            # A length and an id, never the text: this log line would otherwise be a copy of
            # a student's chat message, which is the one thing that must not reach the logs
            # (SPEC §5.30). The id is an internal event id, not a student identifier.
            "event_id": summary.event_id,
            "original_chars": len(summary.summary),
            "kept_chars": keep,
        },
    )
    return summary.model_copy(update={"summary": summary.summary[:keep] + _TRUNCATION_MARKER})


_TRUNCATION_MARKER = " …[truncated]"


def _batch_summaries(
    summaries: list[MemoryEventSummary],
) -> tuple[list[list[MemoryEventSummary]], int]:
    """Pack chronologically ordered summaries into calls that fit the input budget.

    Returns `(batches, dropped_event_count)`.

    **Chronological order is load-bearing rather than cosmetic.** `existing_facts` is re-read
    before each call, so a later batch sees the facts an earlier one wrote - which reproduces
    what running this job weekly all along would have produced, and lets a contradiction
    inside one week demote a fact the same way a contradiction between weeks does. Any other
    order silently changes which of two conflicting facts wins.

    **Over the call cap the OLDEST batches are dropped**, because recency is what a memory
    system wants and because dropping the newest would make the job blind to what just
    happened. `list_events_in_window` already orders by `occurred_at`, and this relies on it.
    """
    batches: list[list[MemoryEventSummary]] = []
    current: list[MemoryEventSummary] = []
    current_chars = 0

    for summary in summaries:
        chars = _summary_chars(summary)
        if chars > _MAX_EVENT_CHARS_PER_CALL:
            summary = _truncate_summary(summary, _MAX_EVENT_CHARS_PER_CALL)
            chars = _summary_chars(summary)
        if current and current_chars + chars > _MAX_EVENT_CHARS_PER_CALL:
            batches.append(current)
            current, current_chars = [], 0
        current.append(summary)
        current_chars += chars

    if current:
        batches.append(current)

    dropped = 0
    if len(batches) > _MAX_CALLS_PER_STUDENT:
        surplus = batches[: len(batches) - _MAX_CALLS_PER_STUDENT]
        dropped = sum(len(batch) for batch in surplus)
        batches = batches[len(batches) - _MAX_CALLS_PER_STUDENT :]
    return batches, dropped


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

    batches, events_dropped = _batch_summaries(event_summaries)
    if events_dropped:
        logger.warning(
            "memory_consolidation_events_dropped",
            extra={
                # Counts and a reason, no student id - the same floor as
                # `memory_consolidation_payload_oversized` below.
                "events_dropped": events_dropped,
                "events_total": len(event_summaries),
                "max_calls_per_student": _MAX_CALLS_PER_STUDENT,
            },
        )

    totals = _RunningTotals(events_dropped=events_dropped)
    spend_so_far = session_spend_cents
    # Facts created earlier in *this* run. They are excluded from promotion below - see
    # `_apply_update`'s note on AUD-F-35.
    created_this_run: set[str] = set()

    for batch in batches:
        batch_events_by_id = {
            event_id: events_by_id[event_id]
            for event_id in (summary.event_id for summary in batch)
            if event_id in events_by_id
        }
        stopped = await _consolidate_one_batch(
            memory_repo=memory_repo,
            gateway=gateway,
            student_external_id=student_external_id,
            batch=batch,
            events_by_id=batch_events_by_id,
            session_spend_cents=spend_so_far,
            totals=totals,
            created_this_run=created_this_run,
        )
        spend_so_far = session_spend_cents + totals.cost_cents
        if stopped:
            break

    return totals.as_result()


async def _consolidate_one_batch(
    *,
    memory_repo: MemoryRepository,
    gateway: BedrockGateway,
    student_external_id: str,
    batch: list[MemoryEventSummary],
    events_by_id: dict[str, LearningEvent],
    session_spend_cents: float,
    totals: "_RunningTotals",
    created_this_run: set[str],
) -> bool:
    """One model call over one batch, applied. Returns True when the run should stop.

    `existing_facts` is re-read here rather than once per student, which is what makes a
    later batch see an earlier batch's writes (the repository flushes on every mutation, so
    they are visible inside the open transaction before the CLI's single commit).
    """
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
        events=batch,
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

    totals.calls_attempted += 1
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.MEMORY_CONSOLIDATION,
            system_prompt=_SYSTEM_PROMPT,
            payload=payload,
            response_model=MemoryUpdateResponse,
            max_output_tokens=max_output_tokens,
            session_spend_cents=session_spend_cents,
        )
    except CostBudgetExceededError as exc:
        # Designed behaviour, not a fault: the run budget is doing its job. Not counted as a
        # failed call, because doing so would make a correctly-bounded run exit non-zero and
        # page someone every week - the opposite of AUD-F-34's fix.
        totals.calls_attempted -= 1
        totals.cost_cents += exc.cost_cents
        totals.budget_stopped = True
        return True
    except BedrockGatewayError as exc:
        # AUD-F-34: this branch used to be the whole story - log a warning, return zeros, and
        # let the caller print a success summary. It still swallows the error per batch (one
        # bad batch should not lose the others), but the count now travels with the result so
        # the process can exit non-zero when *every* call failed.
        logger.warning("memory consolidation call failed, no facts changed: %s", exc)
        totals.calls_failed += 1
        totals.cost_cents += exc.cost_cents
        return False

    update = result.value
    totals.cost_cents += result.cost_cents
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
            created = await memory_repo.add_fact(
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
            created_this_run.add(created.semantic_memory_id)
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
            await _maybe_promote(
                memory_repo, existing_live.semantic_memory_id, created_this_run
            )
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
        await _maybe_promote(memory_repo, fact_update.semantic_memory_id, created_this_run)
        updated += 1

    for fact_id in update.facts_to_expire:
        existing_fact = await memory_repo.get_fact(fact_id)
        if existing_fact is None or existing_fact.student_external_id != student_external_id:
            continue
        await memory_repo.expire_fact(fact_id)
        expired += 1

    totals.added += added
    totals.updated += updated
    totals.contested += contested
    totals.expired += expired
    return False
