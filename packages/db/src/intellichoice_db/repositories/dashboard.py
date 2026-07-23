"""SPEC §5.14.2-§5.14.4, ROADMAP S28 (plan §12, §18-L9): read-only aggregate queries for
the progress dashboard and student report. Every query is scoped to one
`student_external_id` and takes an optional `[start, end)` window applied in SQL (never
fetched unfiltered and trimmed in Python) - the caller passes `None` for either bound to
leave that side open. No LLM anywhere on this path (CLAUDE.md non-negotiable #2 - the
dashboard is deterministic).

`question_variant_id` is the join key from `StudyAttempt`/`AssessmentAttempt` back to
`StudyItem`/`AssessmentItem` - `study_plan._serve_new_item` mints a fresh variant per
served item, so the join is 1:1, not a fan-out.
"""

from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.assessment import (
    AssessmentAttempt,
    AssessmentItem,
    AssessmentItemState,
    AssessmentSession,
)
from intellichoice_db.models.mastery import LearningGain, StudyAttempt, StudyItem


def _apply_range(
    stmt: Select, column, start: datetime | None, end: datetime | None
) -> Select:
    if start is not None:
        stmt = stmt.where(column >= start)
    if end is not None:
        stmt = stmt.where(column < end)
    return stmt


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_learning_gains_in_range(
        self, student_id: str, *, start: datetime | None, end: datetime | None
    ) -> list[LearningGain]:
        stmt = select(LearningGain).where(LearningGain.student_external_id == student_id)
        stmt = _apply_range(stmt, LearningGain.computed_at, start, end)
        stmt = stmt.order_by(LearningGain.computed_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_study_attempts_with_items_in_range(
        self, student_id: str, *, start: datetime | None, end: datetime | None
    ) -> list[tuple[StudyAttempt, StudyItem]]:
        stmt = (
            select(StudyAttempt, StudyItem)
            .join(StudyItem, StudyItem.question_variant_id == StudyAttempt.question_variant_id)
            .where(StudyAttempt.student_external_id == student_id)
        )
        stmt = _apply_range(stmt, StudyAttempt.responded_at, start, end)
        stmt = stmt.order_by(StudyAttempt.responded_at)
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def list_assessment_attempts_in_range(
        self, student_id: str, *, start: datetime | None, end: datetime | None
    ) -> list[tuple[AssessmentAttempt, AssessmentSession]]:
        stmt = (
            select(AssessmentAttempt, AssessmentSession)
            .join(
                AssessmentSession,
                AssessmentSession.assessment_session_id == AssessmentAttempt.assessment_session_id,
            )
            .where(AssessmentAttempt.student_external_id == student_id)
        )
        stmt = _apply_range(stmt, AssessmentAttempt.submitted_at, start, end)
        stmt = stmt.order_by(AssessmentAttempt.submitted_at)
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def total_assessment_time_ms_in_range(
        self, student_id: str, *, start: datetime | None, end: datetime | None
    ) -> int:
        """Sum of `AssessmentItemState.time_spent_ms` (S23's autosave tick) for this
        student's exam items - the only populated per-question timing source in this
        schema (study-phase attempts carry no response-time column).
        """
        stmt = (
            select(func.coalesce(func.sum(AssessmentItemState.time_spent_ms), 0))
            .select_from(AssessmentItemState)
            .join(
                AssessmentItem,
                AssessmentItem.assessment_item_id == AssessmentItemState.assessment_item_id,
            )
            .join(
                AssessmentSession,
                AssessmentSession.assessment_session_id == AssessmentItem.assessment_session_id,
            )
            .where(AssessmentSession.student_external_id == student_id)
        )
        stmt = _apply_range(stmt, AssessmentItemState.updated_at, start, end)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())
