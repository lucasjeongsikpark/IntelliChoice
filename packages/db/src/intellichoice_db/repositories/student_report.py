
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.student_report import StudentReport


class StudentReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, report: StudentReport) -> StudentReport:
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_by_idempotency_key(
        self, student_id: str, *, audience: str, idempotency_key: str
    ) -> StudentReport | None:
        """AUD-X-04: the replay lookup. Read-then-act on its own, which is why
        `uq_student_reports_student_audience_key` exists.
        """
        stmt = select(StudentReport).where(
            StudentReport.student_external_id == student_id,
            StudentReport.audience == audience,
            StudentReport.idempotency_key == idempotency_key,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def create_if_first(self, report: StudentReport) -> StudentReport | None:
        """Insert, or return `None` when this (student, audience, key) already has a report -
        i.e. a concurrent request won the race after both read no row.

        Inside a SAVEPOINT for the same reason as `AssessmentRepository.record_attempt_if_
        first`: an `IntegrityError` on the outer transaction would poison every later statement
        in the request, and the caller still needs to read the winning row.
        """
        try:
            async with self._session.begin_nested():
                self._session.add(report)
                await self._session.flush()
        except IntegrityError as exc:
            if "uq_student_reports_student_audience_key" in str(exc.orig):
                return None
            raise
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
