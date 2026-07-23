from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.reports import ProblemReport


class ReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_report(self, report: ProblemReport) -> ProblemReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_report(
        self, question_template_id: str, student_external_id: str
    ) -> ProblemReport | None:
        """Backs the SPEC §5.8.7 "multiple reports from the same user count once" rule -
        checked before insert so a repeat report is an idempotent no-op rather than a
        unique-constraint IntegrityError that would poison the request's transaction.
        """
        stmt = select(ProblemReport).where(
            ProblemReport.question_template_id == question_template_id,
            ProblemReport.student_external_id == student_external_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_distinct_reporters(self, question_template_id: str) -> int:
        """Backs the SPEC §5.8.7 five-distinct-user quarantine rule."""
        stmt = select(func.count(func.distinct(ProblemReport.student_external_id))).where(
            ProblemReport.question_template_id == question_template_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def list_by_student(self, student_external_id: str) -> list[ProblemReport]:
        """SPEC §5.14.3 parent dashboard - reports this student has filed, newest first."""
        stmt = (
            select(ProblemReport)
            .where(ProblemReport.student_external_id == student_external_id)
            .order_by(ProblemReport.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
