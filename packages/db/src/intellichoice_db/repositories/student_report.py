
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.student_report import StudentReport


class StudentReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, report: StudentReport) -> StudentReport:
        self._session.add(report)
        await self._session.flush()
        return report

    # `get_spend_cents_since` was removed in S42 (AUD-X-08), for the same reason as its
    # `TutorChatMessageRepository` twin: it read spend from rows that commit at request
    # teardown, so ten concurrent reports each read zero and each generated. AUD-L-02's
    # ceiling itself still stands - it just reads `cost_reservations` now, where an
    # in-flight call is already counted.

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

    async def purge_older_than(self, cutoff: datetime) -> int:
        """AUD-L-04 item 2's retention boundary: deletes every report snapshot older
        than `cutoff`, regardless of student or audience. Returns the number of rows
        removed.

        The window here is a year, not 90 days (D-114): reports are the parent-visible
        record of a student's progress and `list_for_student` serves them as history,
        so a quarter-length window would delete reports a parent reasonably expects to
        re-open. `verified_facts` embeds semantic-memory `fact_text`, which is why
        reports get a bound at all.
        """
        result = cast(
            CursorResult,
            await self._session.execute(
                delete(StudentReport).where(StudentReport.created_at < cutoff)
            ),
        )
        return result.rowcount or 0
