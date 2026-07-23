"""Fixture data for the dev-fake MySQL (SPEC §5.4.1 tables).

2 parents (1-child and 2-child cases) + 1 unlinked student = 4 students total,
2 branches, and attendance covering present / absent / unknown (no row).
"""

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from intellichoice_adapters.mysql_profile_adapter import current_week_key

PARENT_ONE_CHILD = "parent-ext-1"
PARENT_TWO_CHILDREN = "parent-ext-2"

STUDENT_ONLY_CHILD = "student-ext-1"  # child of PARENT_ONE_CHILD, attendance: present
STUDENT_FIRST_CHILD = "student-ext-2"  # child of PARENT_TWO_CHILDREN, attendance: absent
STUDENT_SECOND_CHILD = "student-ext-3"  # child of PARENT_TWO_CHILDREN, attendance: unknown (no row)
STUDENT_UNLINKED = "student-ext-4"  # no parent link, attendance: present

BRANCH_MAIN = "branch-ext-1"
BRANCH_NORTH = "branch-ext-2"

_USERS = [
    {
        "external_id": PARENT_ONE_CHILD,
        "role": "parent",
        "display_name": "Priya One",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": PARENT_TWO_CHILDREN,
        "role": "parent",
        "display_name": "Paul Two",
        "grade": None,
        "branch_external_id": None,
    },
    {
        "external_id": STUDENT_ONLY_CHILD,
        "role": "student",
        "display_name": "Ava Only",
        "grade": "3",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_FIRST_CHILD,
        "role": "student",
        "display_name": "Ben First",
        "grade": "5",
        "branch_external_id": BRANCH_MAIN,
    },
    {
        "external_id": STUDENT_SECOND_CHILD,
        "role": "student",
        "display_name": "Cleo Second",
        "grade": "2",
        "branch_external_id": BRANCH_NORTH,
    },
    {
        "external_id": STUDENT_UNLINKED,
        "role": "student",
        "display_name": "Drew Unlinked",
        "grade": "4",
        "branch_external_id": BRANCH_NORTH,
    },
]

_PARENT_CHILD_LINKS = [
    {"parent_external_id": PARENT_ONE_CHILD, "child_external_ids": [STUDENT_ONLY_CHILD]},
    {
        "parent_external_id": PARENT_TWO_CHILDREN,
        "child_external_ids": [STUDENT_FIRST_CHILD, STUDENT_SECOND_CHILD],
    },
]

_BRANCHES = [
    {
        "external_id": BRANCH_MAIN,
        "name": "Main Branch",
        "manager_email": "manager.main@example.test",
        # Matches knowledge-content/documents/public/branch-directory (SPEC §5.22).
        "address": "100 Learning Way, Springfield",
        "latitude": 39.7817,
        "longitude": -89.6501,
    },
    {
        "external_id": BRANCH_NORTH,
        "name": "North Branch",
        "manager_email": "manager.north@example.test",
        "address": "45 Oakridge Ave, Springfield",
        "latitude": 39.8500,
        "longitude": -89.6900,
    },
]

_ATTENDANCE = [
    {
        "student_external_id": STUDENT_ONLY_CHILD,
        "week_key": current_week_key(),
        "status": "present",
    },
    {
        "student_external_id": STUDENT_FIRST_CHILD,
        "week_key": current_week_key(),
        "status": "absent",
    },
    # STUDENT_SECOND_CHILD intentionally has no attendance row -> unknown.
    {
        "student_external_id": STUDENT_UNLINKED,
        "week_key": current_week_key(),
        "status": "present",
    },
]


async def seed(mysql_url: str, database_name: str = "intellichoice") -> None:
    """Idempotently upsert fixture data. Safe to re-run."""
    url = make_url(mysql_url).set(database=database_name)
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            for user in _USERS:
                await conn.execute(
                    text(
                        "INSERT INTO users (external_id, role, display_name, grade, "
                        "branch_external_id) VALUES (:external_id, :role, :display_name, "
                        ":grade, :branch_external_id) ON DUPLICATE KEY UPDATE "
                        "role = VALUES(role), display_name = VALUES(display_name), "
                        "grade = VALUES(grade), branch_external_id = VALUES(branch_external_id)"
                    ),
                    user,
                )

            for link in _PARENT_CHILD_LINKS:
                await conn.execute(
                    text("DELETE FROM parent_child_links WHERE parent_external_id = :id"),
                    {"id": link["parent_external_id"]},
                )
                for child_id in link["child_external_ids"]:
                    await conn.execute(
                        text(
                            "INSERT INTO parent_child_links (parent_external_id, "
                            "child_external_id) VALUES (:parent_id, :child_id)"
                        ),
                        {"parent_id": link["parent_external_id"], "child_id": child_id},
                    )

            for branch in _BRANCHES:
                await conn.execute(
                    text(
                        "INSERT INTO branches (external_id, name, manager_email, address, "
                        "latitude, longitude) VALUES (:external_id, :name, :manager_email, "
                        ":address, :latitude, :longitude) ON DUPLICATE KEY UPDATE "
                        "name = VALUES(name), manager_email = VALUES(manager_email), "
                        "address = VALUES(address), latitude = VALUES(latitude), "
                        "longitude = VALUES(longitude)"
                    ),
                    branch,
                )

            # Clear only this week's attendance for our fixture students, then insert current
            # state (a missing row is meaningful here, so we don't upsert absence-of-a-record).
            fixture_student_ids = [u["external_id"] for u in _USERS]
            week = current_week_key()
            if fixture_student_ids:
                placeholders = ", ".join(f":sid{i}" for i in range(len(fixture_student_ids)))
                params = {f"sid{i}": sid for i, sid in enumerate(fixture_student_ids)}
                params["week"] = week
                await conn.execute(
                    text(
                        f"DELETE FROM attendance WHERE student_external_id IN "
                        f"({placeholders}) AND week_key = :week"
                    ),
                    params,
                )
            for record in _ATTENDANCE:
                await conn.execute(
                    text(
                        "INSERT INTO attendance (student_external_id, week_key, status) "
                        "VALUES (:student_external_id, :week_key, :status)"
                    ),
                    record,
                )
    finally:
        await engine.dispose()
