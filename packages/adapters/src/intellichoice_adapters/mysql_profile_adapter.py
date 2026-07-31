from datetime import datetime

from intellichoice_shared.org_time import OrgTimeConfig, resolve_org_time
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def current_week_key(now: datetime | None = None, *, config: OrgTimeConfig | None = None) -> str:
    """The attendance week key, in the organization's local calendar (SPEC §5.6.2).

    This used to read the ISO week straight off UTC, which quietly put a Sunday-evening
    session into the *following* week — Sunday 19:00 Central is Monday 00:00 UTC, and ISO
    weeks start on Monday. The convention now comes from `intellichoice_shared.org_time`,
    which is a placeholder with an env switch until the org confirms it: see that module,
    and Message A in docs/S42_ORG_ASKS.md.

    Read fresh rather than cached so an env change takes effect on redeploy without a
    process-lifetime cache to reason about; this is called once per attendance check, not
    per request.
    """
    return (config or resolve_org_time()).week_key(now)


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
