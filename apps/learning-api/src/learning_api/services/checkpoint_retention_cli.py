"""Deletes checkpoints whose durable memory has been consolidated (U7, D-333).

Run with: `uv run python -m learning_api.services.checkpoint_retention_cli`

**Dry-run unless `CHECKPOINT_RETENTION_APPLY=true`.** A job whose failure mode is silently deleting
a K-12 student's learning history does not get to delete by default on its first deployment. The
dry-run reports exactly what it would do and touches nothing.

**The rule this implements, in the user's words:** *keep chat and abandoned/pending checkpoints on
an inactivity retention window; before deleting any eligible checkpoint, run long-term memory
consolidation first; only delete the checkpoint after consolidation succeeds, and retain/retry it
if consolidation fails. A successful no-op when there is nothing worth remembering counts as
successful consolidation.*

Three windows, three policies, deliberately not one:

| thread kind | window | why |
|---|---|---|
| completed learning | 30 days | SPEC's own number for completed checkpoints |
| abandoned/pending learning | 90 days inactivity | a half-finished exam a student may return to |
| chat | 180 days inactivity | no resumable work, but no durable record either - see below |

**What the measurement said about the shape of this job** (D-331): completed sessions are 1.7% of
checkpoint bytes, abandoned sessions 77%, chat 19%. The 30-day window is the one SPEC names and the
one that matters least by volume, which is why all three are here rather than only the first.

**Chat consolidation is a structural no-op today, and that is recorded rather than hidden.**
`consolidate_student_session` reads `learning_events`, and chat-api writes none - it persists only
`interrupt_approvals`, `mcp_tool_calls`, `rate_limit_events` and (since D-345) `cost_reservations`.
So the call returns a zero-cost success for every chat thread. That is not a wiring gap to be
fixed: `semantic_memory`'s twelve fact types are all about learning (`weak_skill`,
`misconception`, `hint_dependence`, ...) and "when does Saturday class start?" maps to none of
them. The gate is written so that it becomes *real* automatically if chat ever does emit events,
rather than being special-cased into always passing.

**Two corrections to that inventory (D-343), neither of which changes the policy.** The list above
used to name only the first two tables. And **none of the four is deleted when a chat thread is
pruned here** - `interrupt_approvals` rows in particular outlive their thread and keep a
`session_id` pointing at nothing. Accepted rather than overlooked: an approval record is the audit
trail of a human decision to send an email, which is exactly the thing that should survive the
conversation that produced it. But it does mean "a chat Q&A leaves no durable record" is true of
the *conversation*, not of the account of what was approved.

Neither counter table is wired here either, for different reasons. `rate_limit_events` prunes its
own expired rows inside the transaction that writes them and stores an HMAC rather than the caller
key, so it needs nothing. `cost_reservations` does **not** self-prune - its ceiling query is
windowed, so old rows stop counting but keep sitting there. At chat's volume that is a few rows a
day and not worth a job; if it ever is, `retention_purge_cli` is where it goes.

**Cost.** `consolidate_student_session` is a paid Bedrock call. `finalize_exam` has been making it
since S25, so most completed sessions are already consolidated and must not be re-paid for -
`_ensure_consolidated` checks the recorded flag, then looks for consolidation *evidence*, and only
then reaches for the gateway. A per-run spend ceiling and a thread limit bound the worst case, and
both are checked before each call rather than after.

**`create_engine()` is called bare** - the ops-task D-092 fallback, guarded by
`packages/db/tests/test_standalone_clis_use_the_env_fallback.py`.
"""

import asyncio
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.learning_session import LearningSession
from intellichoice_db.repositories.learning_session import LearningSessionRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import LIVE_STATUSES, MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_memory.consolidate_cli import _build_gateway as build_consolidation_gateway
from intellichoice_memory.consolidation import consolidate_student_session
from intellichoice_memory.settings import get_consolidation_settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

COMPLETED_RETENTION_DAYS = 30
ABANDONED_RETENTION_DAYS = 90
CHAT_RETENTION_DAYS = 180

# Bounds on one run. Both exist because this job's cost and its blast radius both scale with the
# backlog, and a first run against a long-unpruned database is exactly when that matters.
MAX_THREADS_PER_RUN = int(os.environ.get("CHECKPOINT_RETENTION_MAX_THREADS", "500"))
MAX_SPEND_CENTS = float(os.environ.get("CHECKPOINT_RETENTION_MAX_SPEND_CENTS", "100"))

_CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


def apply_enabled() -> bool:
    """Deletion is opt-in per run. Anything other than an explicit `true` is a dry run."""
    return os.environ.get("CHECKPOINT_RETENTION_APPLY", "").strip().lower() == "true"


@dataclass
class RetentionCounts:
    eligible: int = 0
    consolidated_now: int = 0
    already_consolidated: int = 0
    deleted: int = 0
    retained_consolidation_failed: int = 0
    skipped_budget: int = 0
    spend_cents: float = 0.0
    reasons: dict[str, int] = field(default_factory=dict)

    def note(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


class _ConsolidationEvidenceSource(Protocol):
    """Exactly the two reads `_has_consolidation_evidence` needs.

    Narrower than `MemoryRepository` on purpose: the evidence check is pure decision logic, and
    typing it against the concrete repository would force its tests to construct a database session
    to answer a question that involves no database at all.
    """

    async def list_events_for_session(
        self, student_external_id: str, session_id: str, /
    ) -> Sequence[Any]: ...

    async def list_facts_for_student(
        self, student_external_id: str, /, *, statuses: Sequence[str]
    ) -> Sequence[Any]: ...


async def _has_consolidation_evidence(
    memory_repo: _ConsolidationEvidenceSource, student_external_id: str, session_id: str
) -> bool:
    """Did consolidation already run for this session, judged by what it left behind?

    A live `semantic_memory` fact citing one of this session's events is proof that the pipeline
    ran and succeeded over them. Used only when `memory_consolidated_at` is NULL, which for a
    completed session usually means "consolidated by `finalize_exam` before that column existed"
    rather than "never consolidated" - and paying Bedrock again to rediscover that would be a cost
    bug, not caution.
    """
    events = await memory_repo.list_events_for_session(student_external_id, session_id)
    if not events:
        # Nothing to consolidate. The user's rule names this case explicitly: a successful no-op
        # counts as successful consolidation.
        return True
    event_ids = {event.event_id for event in events}
    facts = await memory_repo.list_facts_for_student(student_external_id, statuses=LIVE_STATUSES)
    return any(event_ids.intersection(fact.evidence_event_ids or []) for fact in facts)


async def _delete_checkpoint(session: AsyncSession, thread_id: str) -> None:
    """Three deletes and the bookkeeping, in the caller's single transaction.

    One transaction per thread: a partial delete leaves a checkpoint LangGraph can load but not
    resume, which is worse than either extreme. The `checkpoint_deleted_at` write rides in the same
    transaction so a crash cannot leave the rows gone and the summary still claiming they exist.
    """
    for table in _CHECKPOINT_TABLES:
        await session.execute(text(f"DELETE FROM {table} WHERE thread_id = :t"), {"t": thread_id})


async def _ensure_consolidated(
    *,
    session: AsyncSession,
    summary: LearningSession,
    gateway: ResilientBedrockGateway,
    counts: RetentionCounts,
) -> bool:
    """The gate. Returns True only if long-term memory for this session is durable.

    Order is deliberate and is what keeps the rule affordable: recorded flag, then evidence, then
    the paid call. Never the paid call first.
    """
    if summary.memory_consolidated_at is not None:
        counts.already_consolidated += 1
        return True

    memory_repo = MemoryRepository(session)
    student = summary.student_external_id
    if student is None:
        # A thread that never resolved a student produced no learning events and can have no
        # memory. Nothing to consolidate, so the no-op rule applies.
        counts.already_consolidated += 1
        await LearningSessionRepository(session).mark_consolidated(
            summary.learning_session_id, datetime.now(UTC)
        )
        return True

    if await _has_consolidation_evidence(memory_repo, student, summary.learning_session_id):
        counts.already_consolidated += 1
        await LearningSessionRepository(session).mark_consolidated(
            summary.learning_session_id, datetime.now(UTC)
        )
        return True

    if counts.spend_cents >= MAX_SPEND_CENTS:
        counts.skipped_budget += 1
        counts.note("spend_ceiling_reached")
        return False

    try:
        result = await consolidate_student_session(
            memory_repo=memory_repo,
            mastery_repo=MasteryRepository(session),
            tutor_chat_repo=TutorChatMessageRepository(session),
            gateway=gateway,
            student_external_id=student,
            session_id=summary.learning_session_id,
            session_spend_cents=counts.spend_cents,
        )
    except Exception as exc:  # noqa: BLE001 - any failure must retain, never delete
        # "Retain and retry on failure" is the whole point of catching broadly here. A narrower
        # except would let an unanticipated error escape and abort the run, which is a worse
        # outcome than skipping one thread: the remaining eligible threads would go unprocessed.
        counts.retained_consolidation_failed += 1
        counts.note(f"consolidation_failed:{type(exc).__name__}")
        logger.warning(
            "checkpoint_retention_consolidation_failed",
            extra={
                "learning_session_id": summary.learning_session_id,
                "error_type": type(exc).__name__,
            },
        )
        return False

    counts.consolidated_now += 1
    counts.spend_cents += result.cost_cents
    await LearningSessionRepository(session).mark_consolidated(
        summary.learning_session_id, datetime.now(UTC)
    )
    return True


async def _process_learning_threads(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    gateway: ResilientBedrockGateway,
    now: datetime,
    counts: RetentionCounts,
    apply: bool,
) -> None:
    windows = (
        (True, COMPLETED_RETENTION_DAYS),
        (False, ABANDONED_RETENTION_DAYS),
    )
    for completed, days in windows:
        cutoff = now - timedelta(days=days)
        async with session_scope(session_factory) as session:
            eligible = await LearningSessionRepository(session).list_eligible(
                phase=None,
                completed=completed,
                cutoff=cutoff,
                limit=max(0, MAX_THREADS_PER_RUN - counts.eligible),
            )
        counts.eligible += len(eligible)

        for summary in eligible:
            # One transaction per thread: consolidation bookkeeping, the deletes, and the
            # `checkpoint_deleted_at` write either all land or none do.
            async with session_scope(session_factory) as session:
                fresh = await LearningSessionRepository(session).get(summary.learning_session_id)
                if fresh is None or fresh.checkpoint_deleted_at is not None:
                    continue
                if not await _ensure_consolidated(
                    session=session, summary=fresh, gateway=gateway, counts=counts
                ):
                    await session.commit()
                    continue
                if not apply:
                    counts.note("would_delete")
                    await session.commit()
                    continue
                await _delete_checkpoint(session, fresh.learning_session_id)
                await LearningSessionRepository(session).mark_checkpoint_deleted(
                    fresh.learning_session_id, datetime.now(UTC)
                )
                await session.commit()
                counts.deleted += 1


async def _chat_thread_ids(
    session_factory: async_sessionmaker[AsyncSession], cutoff: datetime, limit: int
) -> list[str]:
    """Chat threads past the window - and "chat" has to be established, not assumed.

    **Two conditions, because one of them is not enough.** The obvious rule is "has checkpoints but
    no `learning_sessions` row". That is wrong in the dangerous direction: a *learning* thread the
    reconciler has not projected yet also has no row, so if the reconciler had never run, every
    learning thread past 180 days would be deleted here - under the chat policy, bypassing the
    consolidation gate entirely. The gate would still be in the code and would simply never be
    reached.

    So a thread additionally has to carry no `phase` in any of its checkpoints. `phase` is on every
    `LearningState` and on no `QAState`, which makes its absence across the whole thread a
    statement about what the thread *is* rather than about what has been done to it. It is the same
    positive-classification rule the reconciler uses, applied from the other side.
    """
    if limit <= 0:
        return []
    async with session_scope(session_factory) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT c.thread_id FROM checkpoints c "
                    "WHERE NOT EXISTS (SELECT 1 FROM learning_sessions l "
                    "                  WHERE l.learning_session_id = c.thread_id) "
                    "  AND NOT EXISTS (SELECT 1 FROM checkpoints p "
                    "                  WHERE p.thread_id = c.thread_id "
                    "                    AND p.checkpoint->'channel_values' ? 'phase') "
                    "GROUP BY c.thread_id "
                    "HAVING MAX((c.checkpoint->>'ts')::timestamptz) < :cutoff "
                    "ORDER BY MAX((c.checkpoint->>'ts')::timestamptz) "
                    "LIMIT :lim"
                ),
                {"cutoff": cutoff, "lim": limit},
            )
        ).all()
    return [row[0] for row in rows]


async def _process_chat_threads(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    now: datetime,
    counts: RetentionCounts,
    apply: bool,
) -> None:
    """Chat threads carry no bookkeeping row, deliberately.

    Building one would mean retaining a record of chat sessions purely to support their deletion,
    which is the opposite of what the retention decision asked for. Statelessness also gives
    "retain and retry on failure" for free: a thread that fails is simply still there next run.
    """
    cutoff = now - timedelta(days=CHAT_RETENTION_DAYS)
    thread_ids = await _chat_thread_ids(
        session_factory, cutoff, max(0, MAX_THREADS_PER_RUN - counts.eligible)
    )
    counts.eligible += len(thread_ids)

    for thread_id in thread_ids:
        # Consolidation for a chat thread finds no `learning_events` and returns a zero-cost
        # success - the no-op case the rule names. See the module docstring for why that is
        # structural rather than a gap.
        counts.already_consolidated += 1
        if not apply:
            counts.note("would_delete_chat")
            continue
        async with session_scope(session_factory) as session:
            await _delete_checkpoint(session, thread_id)
            await session.commit()
        counts.deleted += 1


async def run(*, apply: bool | None = None) -> RetentionCounts:
    apply_deletes = apply_enabled() if apply is None else apply
    counts = RetentionCounts()
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        now = datetime.now(UTC)
        # The same gateway `memory-consolidate` builds, from the same settings, because this job
        # makes the same `MEMORY_CONSOLIDATION` call. Reusing it rather than reaching into
        # `learning_api.main` keeps this a standalone CLI - importing the FastAPI app here would
        # pull in the D-092 prefixed-settings path the ops task does not have.
        gateway = build_consolidation_gateway(get_consolidation_settings())

        await _process_learning_threads(
            session_factory=session_factory,
            gateway=gateway,
            now=now,
            counts=counts,
            apply=apply_deletes,
        )
        await _process_chat_threads(
            session_factory=session_factory, now=now, counts=counts, apply=apply_deletes
        )
        return counts
    finally:
        await engine.dispose()


def main() -> None:
    counts = asyncio.run(run())
    mode = "APPLY" if apply_enabled() else "DRY-RUN (set CHECKPOINT_RETENTION_APPLY=true to delete)"
    print(
        f"[{mode}] eligible={counts.eligible} deleted={counts.deleted} "
        f"already_consolidated={counts.already_consolidated} "
        f"consolidated_now={counts.consolidated_now} "
        f"retained_consolidation_failed={counts.retained_consolidation_failed} "
        f"skipped_budget={counts.skipped_budget} "
        f"spend_cents={counts.spend_cents:.4f} reasons={counts.reasons}"
    )


if __name__ == "__main__":
    main()
