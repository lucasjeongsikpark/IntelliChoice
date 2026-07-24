from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.student_report import StudentReport


class StudentReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, report: StudentReport) -> StudentReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_spend_cents_since(self, student_external_id: str, since: datetime) -> float:
        """Sum of `cost_cents` for this student's reports at or after `since` - read by
        `report.generate_student_report`'s per-day cost ceiling before every Bedrock call.

        Mirrors `TutorChatMessageRepository.get_spend_cents_since` deliberately: report
        generation is the second surface (after chat) where one authenticated caller can
        trigger unlimited separate LLM calls, so it needs the same per-day ceiling rather
        than only the per-session budget, which a session-less endpoint cannot have. See
        AUD-L-02 in docs/AUDIT_FINDINGS.md for the finding this closes.
        """
        stmt = select(func.coalesce(func.sum(StudentReport.cost_cents), 0.0)).where(
            StudentReport.student_external_id == student_external_id,
            StudentReport.created_at >= since,
        )
        result = await self._session.execute(stmt)
        return float(result.scalar_one())

    async def list_for_student(
        self, student_id: str, *, audience: str | None = None
    ) -> list[StudentReport]:
        stmt = select(StudentReport).where(StudentReport.student_external_id == student_id)
        if audience is not None:
            stmt = stmt.where(StudentReport.audience == audience)
        stmt = stmt.order_by(StudentReport.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_for_student(
        self, student_id: str, *, audience: str
    ) -> StudentReport | None:
        stmt = (
            select(StudentReport)
            .where(
                StudentReport.student_external_id == student_id,
                StudentReport.audience == audience,
            )
            .order_by(StudentReport.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
