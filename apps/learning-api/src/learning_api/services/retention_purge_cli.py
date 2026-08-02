"""CLI entrypoint for the AUD-L-04 retention purges (D-114).

Run with: uv run python -m learning_api.services.retention_purge_cli

One CLI, three tables, one EventBridge schedule (`intellichoice-staging-retention-purge`,
daily) - the disposition's "done once rather than three times". `tutor_chat_purge_cli`
stays separate: it predates this, has its own schedule already inside its unattended
gate-criterion week, and merging them would touch a job that must not be touched.

Windows (D-114):

- `semantic_memory`: 90 days on `last_confirmed_at`. This restores the boundary D-072
  reasoned about when it accepted that name detection in free text is unreliable - that
  acceptance was premised on the text living in a 90-day-purged table, and S25's
  consolidation quietly derived permanent text from it. Keyed on `last_confirmed_at` so
  a fact the weekly consolidation keeps reconfirming stays; the daily schedule runs
  after Sunday's consolidation in the staggered UTC evening block, so a reconfirming
  window always lands before the purge that would otherwise catch its fact.
- `stage_transitions`: 90 days on `created_at` - narrative text derived from the same
  tutoring data, same window as its source.
- `student_reports`: 365 days on `created_at` - parent-visible history served by
  `list_for_student`; a 90-day window would delete reports a parent expects to re-open
  (the trade-off is D-114's).

**`create_engine()` is called bare, and that is load-bearing** - this module runs inside
the ops task, whose environment supplies the *unprefixed* five-component DSN vars that
`create_engine`'s D-092 fallback understands, not the `LEARNING_`-prefixed settings the
FastAPI app reads. See `tutor_chat_purge_cli`'s docstring for the incident history
(AUD-F-15: the 90-day promise had never once run against the deployed database) and
`packages/db/tests/test_standalone_clis_use_the_env_fallback.py` for the guard, which
includes this file.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_db.repositories.student_report import StudentReportRepository

SEMANTIC_MEMORY_RETENTION_DAYS = 90
STAGE_TRANSITION_RETENTION_DAYS = 90
STUDENT_REPORT_RETENTION_DAYS = 365
# D-153: `learning_events` was the one table with no retention promise and no bound - the
# gap D-141 §5 filed after it grew to 13,865 rows on staging from load-test exhaust alone.
# 365 days, deliberately the same window as `student_reports`, so the product makes ONE
# promise a parent or manager can hold in their head: "a school year of learning history".
#
# The floor is not a matter of taste. Events are the evidence base `semantic_memory.
# evidence_event_ids` points at, and `promote_if_eligible` resolves that list back to real
# rows, so this window must stay >= SEMANTIC_MEMORY_RETENTION_DAYS + the consolidation
# window (90 + 7 = 97). `test_learning_event_retention_clears_the_semantic_memory_floor`
# asserts exactly that, so lowering either constant without thinking fails the suite.
#
# Sizing at the planning cohort (~1,000 students across a week, user 2026-08-02): roughly
# 60 events per student per week => ~3M rows and a few hundred MB at steady state, which is
# unremarkable for this RDS instance. The point of the window is the promise, not the disk.
LEARNING_EVENT_RETENTION_DAYS = 365


async def purge() -> dict[str, int]:
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            now = datetime.now(UTC)
            deleted = {
                "semantic_memory": await MemoryRepository(session).purge_facts_older_than(
                    now - timedelta(days=SEMANTIC_MEMORY_RETENTION_DAYS)
                ),
                "stage_transitions": await StageTransitionRepository(session).purge_older_than(
                    now - timedelta(days=STAGE_TRANSITION_RETENTION_DAYS)
                ),
                "student_reports": await StudentReportRepository(session).purge_older_than(
                    now - timedelta(days=STUDENT_REPORT_RETENTION_DAYS)
                ),
                "learning_events": await MemoryRepository(session).purge_events_older_than(
                    now - timedelta(days=LEARNING_EVENT_RETENTION_DAYS)
                ),
            }
            await session.commit()
            return deleted
    finally:
        await engine.dispose()


def main() -> None:
    deleted = asyncio.run(purge())
    print(
        f"purged {deleted['semantic_memory']} semantic_memory row(s) older than "
        f"{SEMANTIC_MEMORY_RETENTION_DAYS} days, "
        f"{deleted['stage_transitions']} stage_transitions row(s) older than "
        f"{STAGE_TRANSITION_RETENTION_DAYS} days, "
        f"{deleted['student_reports']} student_reports row(s) older than "
        f"{STUDENT_REPORT_RETENTION_DAYS} days, "
        f"{deleted['learning_events']} learning_events row(s) older than "
        f"{LEARNING_EVENT_RETENTION_DAYS} days"
    )


if __name__ == "__main__":
    main()
