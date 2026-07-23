from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.student_report import StudentReport


class StudentReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, report: StudentReport) -> StudentReport:
        self._session.add(report)
        await self._session.flush()
        return report

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
