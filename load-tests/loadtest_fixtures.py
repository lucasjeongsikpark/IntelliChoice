"""Bulk-seed/cleanup synthetic MySQL students for load testing (S34).

SPEC §6.23's ">1,000 students / >100 concurrent learning sessions" targets need many
*distinct* students - `mysql_fixtures.py`'s 4-student set is deliberately small (SPEC
§5.4.1 fixture set, reused by every functional test in this repo) and reusing it across
many concurrent k6 VUs would serialize on a handful of students' own mastery/attendance
rows instead of exercising genuine per-student concurrency. This inserts `--count`
disposable `loadtest-student-N` rows (present attendance, unlinked, reusing the existing
`branch-ext-2` fixture branch as their FK target so no new branch is needed) directly into
the local dev MySQL, and removes them again afterward - never touches the committed
fixture set, never run against anything but a local docker-compose MySQL.

Run with: uv run python load-tests/loadtest_fixtures.py --count 150
Clean up: uv run python load-tests/loadtest_fixtures.py --cleanup
"""

import argparse
import asyncio

from intellichoice_shared.org_time import current_week_key
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"
BRANCH_EXTERNAL_ID = "branch-ext-2"  # BRANCH_NORTH, already seeded by mysql_fixtures.seed()
STUDENT_PREFIX = "loadtest-student-"


def student_id(n: int) -> str:
    return f"{STUDENT_PREFIX}{n}"


async def seed_load_students(mysql_url: str, count: int) -> None:
    url = make_url(mysql_url).set(database="intellichoice")
    engine = create_async_engine(url)
    week = current_week_key()
    try:
        async with engine.begin() as conn:
            for i in range(1, count + 1):
                sid = student_id(i)
                await conn.execute(
                    text(
                        "INSERT INTO users (external_id, role, display_name, grade, "
                        "branch_external_id) VALUES (:external_id, 'student', "
                        ":display_name, '5', :branch_external_id) "
                        "ON DUPLICATE KEY UPDATE role = VALUES(role)"
                    ),
                    {
                        "external_id": sid,
                        "display_name": f"Load Test Student {i}",
                        "branch_external_id": BRANCH_EXTERNAL_ID,
                    },
                )
                await conn.execute(
                    text(
                        "DELETE FROM attendance WHERE student_external_id = :sid "
                        "AND week_key = :week"
                    ),
                    {"sid": sid, "week": week},
                )
                await conn.execute(
                    text(
                        "INSERT INTO attendance (student_external_id, week_key, status) "
                        "VALUES (:sid, :week, 'present')"
                    ),
                    {"sid": sid, "week": week},
                )
        print(f"Seeded {count} load-test students ({student_id(1)}..{student_id(count)}).")
    finally:
        await engine.dispose()


async def cleanup_load_students(mysql_url: str) -> None:
    url = make_url(mysql_url).set(database="intellichoice")
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("DELETE FROM attendance WHERE student_external_id LIKE :prefix"),
                {"prefix": f"{STUDENT_PREFIX}%"},
            )
            attendance_deleted = result.rowcount
            result = await conn.execute(
                text("DELETE FROM users WHERE external_id LIKE :prefix"),
                {"prefix": f"{STUDENT_PREFIX}%"},
            )
            users_deleted = result.rowcount
        print(f"Removed {users_deleted} load-test users, {attendance_deleted} attendance rows.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=150, help="Number of students to seed")
    parser.add_argument(
        "--cleanup", action="store_true", help="Remove all loadtest-student-* rows instead"
    )
    parser.add_argument("--mysql-url", default=DEFAULT_MYSQL_URL)
    args = parser.parse_args()

    if args.cleanup:
        asyncio.run(cleanup_load_students(args.mysql_url))
    else:
        asyncio.run(seed_load_students(args.mysql_url, args.count))


if __name__ == "__main__":
    main()
