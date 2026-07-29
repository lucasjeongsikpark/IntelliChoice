from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.memory import LearningEvent, SemanticMemory

# Statuses a consolidation run/read path should ever consider "live" - excludes
# "superseded" (kept only for audit, per plan §9's "readable for audit, never served").
LIVE_STATUSES = ("provisional", "active", "contested")


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_event(self, event: LearningEvent) -> LearningEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_students_with_events_in_window(
        self, start: datetime, end: datetime
    ) -> list[str]:
        """Drives the weekly batch CLI (`consolidate_cli.py`): only students with at
        least one event in the window need a consolidation call at all.
        """
        stmt = (
            select(LearningEvent.student_external_id)
            .where(LearningEvent.occurred_at >= start, LearningEvent.occurred_at < end)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_events_for_session(
        self, student_external_id: str, session_id: str
    ) -> list[LearningEvent]:
        """Backs `consolidation.consolidate_student_session` (plan §9 trigger (a)):
        every event this one learning-session thread produced, regardless of when.
        """
        stmt = (
            select(LearningEvent)
            .where(
                LearningEvent.student_external_id == student_external_id,
                LearningEvent.session_id == session_id,
            )
            .order_by(LearningEvent.occurred_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_events_in_window(
        self, student_external_id: str, start: datetime, end: datetime
    ) -> list[LearningEvent]:
        stmt = (
            select(LearningEvent)
            .where(
                LearningEvent.student_external_id == student_external_id,
                LearningEvent.occurred_at >= start,
                LearningEvent.occurred_at < end,
            )
            .order_by(LearningEvent.occurred_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_events_by_ids(self, event_ids: Sequence[str]) -> list[LearningEvent]:
        if not event_ids:
            return []
        stmt = select(LearningEvent).where(LearningEvent.event_id.in_(event_ids))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def add_fact(self, fact: SemanticMemory) -> SemanticMemory:
        """Inserts a brand-new fact row - never call this for a fact the caller already
        has a `semantic_memory_id` for (use `update_fact`/`reconfirm_fact` instead).
        """
        self._session.add(fact)
        await self._session.flush()
        return fact

    async def get_fact(self, semantic_memory_id: str) -> SemanticMemory | None:
        return await self._session.get(SemanticMemory, semantic_memory_id)

    async def find_live_fact(
        self, student_external_id: str, fact_type: str, skill_id: str | None
    ) -> SemanticMemory | None:
        """The one live (provisional/active/contested) fact for this (student, fact_type,
        skill) combination, if any - `fact_type`+`skill_id` is the natural key a
        consolidation run reconfirms or contradicts against (plan §9).
        """
        stmt = select(SemanticMemory).where(
            SemanticMemory.student_external_id == student_external_id,
            SemanticMemory.fact_type == fact_type,
            SemanticMemory.skill_id == skill_id,
            SemanticMemory.status.in_(LIVE_STATUSES),
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_facts_for_student(
        self, student_id: str, *, statuses: Sequence[str] = ("active",)
    ) -> list[SemanticMemory]:
        stmt = select(SemanticMemory).where(
            SemanticMemory.student_external_id == student_id,
            SemanticMemory.status.in_(statuses),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def top_fact_for_skill(
        self, student_id: str, skill_id: str, *, now: datetime | None = None
    ) -> SemanticMemory | None:
        """Read path (`tutor.py`/`tutor_chat.py`'s `relevant_learning_fact`): the
        highest-confidence `active`, non-expired fact for this skill, or `None`.
        `provisional`/`contested`/`superseded` facts are never returned here - only a
        fact that cleared the minimum-evidence bar and hasn't been demoted is trusted
        enough to reach a Bedrock payload.
        """
        as_of = now or datetime.now(UTC)
        stmt = (
            select(SemanticMemory)
            .where(
                SemanticMemory.student_external_id == student_id,
                SemanticMemory.skill_id == skill_id,
                SemanticMemory.status == "active",
            )
            .order_by(SemanticMemory.confidence.desc())
        )
        result = await self._session.execute(stmt)
        for fact in result.scalars().all():
            if fact.expires_at is None or fact.expires_at > as_of:
                return fact
        return None

    async def reconfirm_fact(
        self,
        semantic_memory_id: str,
        *,
        fact_text: str,
        confidence: float,
        evidence_event_ids: list[str],
    ) -> SemanticMemory | None:
        """A `facts_to_update` (or same-polarity `facts_to_add`) application: merges new
        evidence into an existing fact, refreshes `last_confirmed_at`, and clears any
        contradiction streak (a reconfirming window is the opposite of a contradicting
        one). A reconfirmed `contested` fact returns to `active` - being contradicted
        once doesn't permanently demote a fact that a later window reconfirms;
        `provisional` is left alone here since promotion has its own evidence-bar check
        (`promote_if_eligible`), meant to be called right after this.
        """
        fact = await self.get_fact(semantic_memory_id)
        if fact is None:
            return None
        fact.fact_text = fact_text
        fact.confidence = confidence
        fact.evidence_event_ids = sorted(set(fact.evidence_event_ids) | set(evidence_event_ids))
        fact.last_confirmed_at = datetime.now(UTC)
        fact.contradicts_event_count = 0
        fact.memory_version += 1
        if fact.status == "contested":
            fact.status = "active"
        await self._session.flush()
        return fact

    async def promote_if_eligible(self, semantic_memory_id: str) -> SemanticMemory | None:
        fact = await self.get_fact(semantic_memory_id)
        if fact is None:
            return None
        if fact.status == "provisional":
            fact.status = "active"
            await self._session.flush()
        return fact

    async def demote_to_contested(self, semantic_memory_id: str) -> SemanticMemory | None:
        """Plan §9: a contradicting window demotes rather than replaces - the fact stays
        readable, just `contested` instead of `active`, and its streak increments.
        """
        fact = await self.get_fact(semantic_memory_id)
        if fact is None:
            return None
        fact.status = "contested"
        fact.contradicts_event_count += 1
        await self._session.flush()
        return fact

    async def supersede_fact(
        self, semantic_memory_id: str, *, superseded_by: SemanticMemory
    ) -> SemanticMemory | None:
        """A second consecutive contradiction: the old fact is retired (`superseded`,
        never deleted - audit trail) in favor of the new one already added via
        `add_fact`.
        """
        fact = await self.get_fact(semantic_memory_id)
        if fact is None:
            return None
        fact.status = "superseded"
        fact.superseded_by_id = superseded_by.semantic_memory_id
        await self._session.flush()
        return fact

    async def expire_fact(self, semantic_memory_id: str, *, now: datetime | None = None) -> None:
        fact = await self.get_fact(semantic_memory_id)
        if fact is None:
            return
        fact.expires_at = now or datetime.now(UTC)
        await self._session.flush()

    async def purge_facts_older_than(self, cutoff: datetime) -> int:
        """AUD-L-04's retention boundary: deletes every fact whose `last_confirmed_at`
        is older than `cutoff`, regardless of student or status. Returns the number of
        rows removed.

        Keyed on `last_confirmed_at`, not `first_observed_at`: a fact the weekly
        consolidation keeps reconfirming has fresh evidence inside the window and stays;
        a fact nothing has confirmed in the window - including `superseded` audit rows,
        which nothing ever reconfirms - ages out. This bounds how long a name that
        slipped through `contains_pii_pattern` into `fact_text` can live, which is the
        promise D-072 made about the *source* text and S25 silently unmade for the
        derived text. Plan §9's "superseded, never deleted" yields to that here: the
        audit trail is retained for the window, not forever.

        `superseded_by_id` is a self-FK with `ondelete="SET NULL"`, so deleting an old
        fact a survivor points at cannot fail the delete.
        """
        result = cast(
            CursorResult,
            await self._session.execute(
                delete(SemanticMemory).where(SemanticMemory.last_confirmed_at < cutoff)
            ),
        )
        return result.rowcount or 0
