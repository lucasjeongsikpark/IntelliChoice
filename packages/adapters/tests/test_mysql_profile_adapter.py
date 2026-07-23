import asyncio

import pytest
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_adapters.seed.mysql_fixtures import (
    BRANCH_MAIN,
    BRANCH_NORTH,
    PARENT_ONE_CHILD,
    PARENT_TWO_CHILDREN,
    STUDENT_FIRST_CHILD,
    STUDENT_ONLY_CHILD,
    STUDENT_SECOND_CHILD,
    seed,
)
from intellichoice_shared.profiles import AttendanceStatus
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"
TEST_DATABASE = "intellichoice_test"


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


pytestmark = pytest.mark.skipif(
    not _mysql_available(), reason="MySQL is not reachable at localhost:3306 (run `make up`)"
)


@pytest.fixture(scope="module", autouse=True)
def seeded_mysql() -> None:
    asyncio.run(seed(MYSQL_URL, TEST_DATABASE))


def test_student_profile_and_branch() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        profile = await adapter.get_student_profile(STUDENT_ONLY_CHILD)
        assert profile is not None
        assert profile.student_external_id == STUDENT_ONLY_CHILD
        assert profile.branch_external_id == BRANCH_MAIN
        await adapter.close()

    asyncio.run(run())


def test_unknown_student_profile_is_none() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        profile = await adapter.get_student_profile("does-not-exist")
        assert profile is None
        await adapter.close()

    asyncio.run(run())


def test_parent_children_one_and_two_child_cases() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        one_child = await adapter.get_parent_children(PARENT_ONE_CHILD)
        two_children = await adapter.get_parent_children(PARENT_TWO_CHILDREN)
        assert one_child == [STUDENT_ONLY_CHILD]
        assert set(two_children) == {STUDENT_FIRST_CHILD, STUDENT_SECOND_CHILD}
        await adapter.close()

    asyncio.run(run())


def test_parent_profile_includes_children() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        profile = await adapter.get_parent_profile(PARENT_TWO_CHILDREN)
        assert profile is not None
        assert set(profile.children) == {STUDENT_FIRST_CHILD, STUDENT_SECOND_CHILD}
        await adapter.close()

    asyncio.run(run())


def test_attendance_present_absent_unknown() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        present = await adapter.get_current_week_attendance(STUDENT_ONLY_CHILD)
        absent = await adapter.get_current_week_attendance(STUDENT_FIRST_CHILD)
        unknown = await adapter.get_current_week_attendance(STUDENT_SECOND_CHILD)
        assert present == AttendanceStatus.PRESENT
        assert absent == AttendanceStatus.ABSENT
        assert unknown == AttendanceStatus.UNKNOWN
        await adapter.close()

    asyncio.run(run())


def test_branch_and_manager_email() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        branch = await adapter.get_branch(BRANCH_MAIN)
        assert branch is not None
        assert branch.manager_email
        assert branch.address
        assert branch.latitude != 0.0
        email = await adapter.get_branch_manager_email(BRANCH_MAIN)
        assert email == branch.manager_email
        await adapter.close()

    asyncio.run(run())


def test_list_branches_returns_every_seeded_branch() -> None:
    async def run() -> None:
        adapter = MySQLProfileAdapter(MYSQL_URL, TEST_DATABASE)
        branches = await adapter.list_branches()
        ids = {b.branch_external_id for b in branches}
        assert {BRANCH_MAIN, BRANCH_NORTH} <= ids
        await adapter.close()

    asyncio.run(run())
