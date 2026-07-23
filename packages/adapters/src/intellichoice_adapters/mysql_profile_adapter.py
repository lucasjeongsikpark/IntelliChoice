from datetime import UTC, datetime

from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def current_week_key(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _branch_from_row(row) -> BranchInfo:
    return BranchInfo(
        branch_external_id=row.external_id,
        name=row.name,
        manager_email=row.manager_email,
        address=row.address,
        latitude=row.latitude,
        longitude=row.longitude,
    )


class MySQLProfileAdapter:
    """Read-only adapter over the dev-fake MySQL (SPEC §5.4.1).

    Never writes. PostgreSQL must never replicate the PII this adapter reads
    (names, emails) — see SPEC §5.4.1 / §5.30.
    """

    def __init__(self, mysql_url: str, database_name: str = "intellichoice") -> None:
        url = make_url(mysql_url).set(database=database_name)
        self.engine: AsyncEngine = create_async_engine(url)

    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT external_id, display_name, grade, branch_external_id "
                        "FROM users WHERE external_id = :id AND role = 'student'"
                    ),
                    {"id": student_external_id},
                )
            ).first()
        if row is None:
            return None
        return StudentProfile(
            student_external_id=row.external_id,
            display_name=row.display_name,
            grade=row.grade,
            branch_external_id=row.branch_external_id,
        )

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT external_id, display_name "
                        "FROM users WHERE external_id = :id AND role = 'parent'"
                    ),
                    {"id": parent_external_id},
                )
            ).first()
        if row is None:
            return None
        children = await self.get_parent_children(parent_external_id)
        return ParentProfile(
            parent_external_id=row.external_id,
            display_name=row.display_name,
            children=children,
        )

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT child_external_id FROM parent_child_links "
                    "WHERE parent_external_id = :id"
                ),
                {"id": parent_external_id},
            )
            return [row.child_external_id for row in rows]

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT status FROM attendance "
                        "WHERE student_external_id = :id AND week_key = :week"
                    ),
                    {"id": student_external_id, "week": current_week_key()},
                )
            ).first()
        if row is None:
            return AttendanceStatus.UNKNOWN
        return AttendanceStatus(row.status)

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None:
        async with self.engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT external_id, name, manager_email, address, latitude, longitude "
                        "FROM branches WHERE external_id = :id"
                    ),
                    {"id": branch_external_id},
                )
            ).first()
        if row is None:
            return None
        return _branch_from_row(row)

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None:
        branch = await self.get_branch(branch_external_id)
        return branch.manager_email if branch else None

    async def list_branches(self) -> list[BranchInfo]:
        async with self.engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT external_id, name, manager_email, address, latitude, longitude "
                    "FROM branches"
                )
            )
            return [_branch_from_row(row) for row in rows]

    async def close(self) -> None:
        await self.engine.dispose()
