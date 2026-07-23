"""S17 test-debt cleanup (ROADMAP "wrap `apps/learning-api/tests/*` HTTP-committed tests
in rollback/teardown", S12/S14's carry-over): `with TestClient(app) as client:` tests
drive the real app, whose `get_db_session` dependency commits per request against the
real engine built in `main.py`'s lifespan - unlike `packages/db`/`packages/curriculum`/
`packages/knowledge`'s `rollback_session` fixture, so rows land for real in the shared
dev Postgres under the MySQL-fixture student ids.

A single shared-connection rollback transaction was tried first and rejected: many tests
verify state via a *second*, independent connection (`asyncio.run(fetch())` helpers like
`_correct_options`), and Postgres's own transaction isolation makes an uncommitted write
on one connection invisible to another - exactly the "rollback" property that would break
those assertions. Threading one shared connection through every such helper across 4
files was a much larger, riskier change than the actual problem calls for.

Instead: a `teardown`, matching the ROADMAP wording's other option and exactly automating
the dependency-ordered `DELETE` sweep S9/S12/S14 already ran by hand each time pollution
was noticed (see docs/PROGRESS.md). Runs before *and* after every test in this directory
(before, to self-heal any pollution already sitting in the shared dev Postgres from a
prior run; after, to leave nothing behind) - cheap and correct even for tests that never
touch Postgres, since every `DELETE ... WHERE student_external_id = ...` simply matches
zero rows.
"""

import asyncio
from collections.abc import Iterator

import pytest
from intellichoice_adapters.seed.mysql_fixtures import (
    STUDENT_FIRST_CHILD,
    STUDENT_ONLY_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
)
from intellichoice_db.engine import create_engine
from sqlalchemy import text

_FIXTURE_STUDENT_IDS = (
    STUDENT_ONLY_CHILD,
    STUDENT_FIRST_CHILD,
    STUDENT_SECOND_CHILD,
    STUDENT_UNLINKED,
)

# Children before parents (FK order); the two subqueried tables have no
# student_external_id column of their own, only a session FK.
_DELETE_STATEMENTS = (
    "DELETE FROM problem_reports WHERE student_external_id = ANY(:ids)",
    "DELETE FROM learning_gain WHERE student_external_id = ANY(:ids)",
    # S21: hint_events FKs to study_attempts, so it must clear first.
    "DELETE FROM hint_events WHERE student_external_id = ANY(:ids)",
    # S24: tutor_chat_messages has no FK to study_attempts (question_variant_id is
    # nullable, and question_variants themselves are never deleted by this sweep), so
    # it has no ordering constraint relative to the rows below - grouped here only
    # because it's conceptually another per-attempt assistance-audit table.
    "DELETE FROM tutor_chat_messages WHERE student_external_id = ANY(:ids)",
    # S26: stage_transitions has no FK to any other table this sweep touches (plain
    # student_external_id/learning_session_id columns) - same "independent audit table"
    # posture as tutor_chat_messages above.
    "DELETE FROM stage_transitions WHERE student_external_id = ANY(:ids)",
    "DELETE FROM study_attempts WHERE student_external_id = ANY(:ids)",
    "DELETE FROM study_items WHERE study_session_id IN "
    "(SELECT study_session_id FROM study_sessions WHERE student_external_id = ANY(:ids))",
    "DELETE FROM study_sessions WHERE student_external_id = ANY(:ids)",
    "DELETE FROM assessment_attempts WHERE student_external_id = ANY(:ids)",
    # S22: assessment_item_state FKs to assessment_items, so it must clear first.
    "DELETE FROM assessment_item_state WHERE assessment_item_id IN "
    "(SELECT assessment_item_id FROM assessment_items WHERE assessment_session_id IN "
    "(SELECT assessment_session_id FROM assessment_sessions "
    "WHERE student_external_id = ANY(:ids)))",
    "DELETE FROM assessment_items WHERE assessment_session_id IN "
    "(SELECT assessment_session_id FROM assessment_sessions WHERE student_external_id = ANY(:ids))",
    "DELETE FROM assessment_sessions WHERE student_external_id = ANY(:ids)",
    "DELETE FROM mastery WHERE student_external_id = ANY(:ids)",
    "DELETE FROM blocked_sessions WHERE student_external_id = ANY(:ids)",
    "DELETE FROM learning_events WHERE student_external_id = ANY(:ids)",
    "DELETE FROM semantic_memory WHERE student_external_id = ANY(:ids)",
)


async def _sweep() -> None:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            for statement in _DELETE_STATEMENTS:
                await conn.execute(text(statement), {"ids": list(_FIXTURE_STUDENT_IDS)})
            await conn.commit()
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _clean_fixture_student_rows() -> Iterator[None]:
    asyncio.run(_sweep())
    yield
    asyncio.run(_sweep())
