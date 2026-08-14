"""Projects LangGraph checkpoints into durable `learning_sessions` rows (U7, D-331).

Run with: `uv run python -m learning_api.services.session_consolidation_cli`

**This is the "extract → store separately" half of the user's design, and it ships before the
"delete" half deliberately.** D-331 measured that the deletion job as scoped would reclaim 1.7% of
checkpoint bytes and *zero* bytes today, while the five fields in `LearningSession`'s docstring are
recorded nowhere every day this does not run. Extraction has value on its own; deletion does not
have value without it.

**Why a reconciler and not a write on the request path.** `routers/sessions.py` has eight
`graph.ainvoke` call sites. Threading a summary write through all eight would add a write to every
turn a student waits on, and would rot the first time a ninth is added without one. A reconciler
reads the same state after the fact, adds nothing to the hot path, and cannot be partially wired.
The summary lags by up to a scheduling interval, which does not matter: nothing deletes a
checkpoint for at least 30 days.

**State is read through `AsyncPostgresSaver.aget_tuple`, never by querying the checkpoint tables.**
`checkpoints.checkpoint->'channel_values'` looks like the full state and is not - it is partial per
superstep (measured: most rows carry 13-24 of the 31 fields, and some carry one), with the larger
channels living in `checkpoint_blobs` under a versioning scheme. Reconstructing that in SQL means
reimplementing LangGraph's storage format and re-breaking it at every upgrade. The saver already
does it correctly.

**Thread kind is classified positively, never by a missing field** (D-331 §3). `checkpoints` is
shared with chat-api: `QAState` and `LearningState` write to the same tables keyed by `thread_id`
(measured on dev: 31,416 learning-only threads, 12,638 chat-only, 0 overlap). A rule like "skip
threads with no `phase`" would silently reclassify a learning thread the moment a future state
change made `phase` optional. This requires `session_id` *and* `phase`, both of which `QAState`
lacks (`QAState` has `session_id` but never `phase`), and skips anything else without pretending to
understand it.

**`create_engine()` is called bare, and that is load-bearing** - this runs in the ops task, whose
environment supplies the *unprefixed* five-component DSN vars that `create_engine`'s D-092 fallback
understands, not the `LEARNING_`-prefixed settings the FastAPI app reads. See
`packages/db/tests/test_standalone_clis_use_the_env_fallback.py`, which includes this file, and
`tutor_chat_purge_cli`'s docstring for the incident history.
"""

import asyncio
from datetime import datetime
from typing import Any

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.learning_session import LearningSession
from intellichoice_db.repositories.learning_session import LearningSessionRepository
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Every field projected straight across from graph state. `phase` is handled separately because it
# is the one column that is NOT NULL, and `bedrock_spend_cents` because it needs a numeric default.
_DIRECT_FIELDS = (
    "student_external_id",
    "parent_external_id",
    "user_external_id",
    "user_role",
    "week_id",
    "topic_id",
    "attendance_status",
    "attendance_resolution",
    "pre_assessment_session_id",
    "study_session_id",
    "post_assessment_session_id",
    "blocked_session_id",
)


def checkpoint_dsn_from(engine: AsyncEngine) -> str:
    """A psycopg DSN for the same database the bare engine resolved.

    Derived from the engine rather than from `Settings.checkpoint_database_url`, which reads
    `LEARNING_`-prefixed env vars this process does not have. Deriving it keeps one source of truth
    for where the database *is*, and keeps `create_engine()` bare so the D-092 guard test passes.

    The rendered string contains the password, so it is returned for immediate use and must never
    be logged or printed.
    """
    url = engine.url.render_as_string(hide_password=False).replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    if engine.url.host not in ("localhost", "127.0.0.1"):
        url += "?sslmode=require"
    return url


def summary_from_state(
    learning_session_id: str, state: dict[str, Any], last_activity_at: datetime
) -> LearningSession | None:
    """Project one thread's reconstructed graph state into a summary row.

    Returns `None` for anything that is not a learning thread - see the module docstring on why
    that test is positive rather than "has no `phase`".
    """
    if not state.get("session_id") or not state.get("phase"):
        return None

    summary = LearningSession(
        learning_session_id=learning_session_id,
        phase=str(state["phase"]),
        # `or 0.0` rather than a `.get` default: a checkpoint written before this field existed can
        # carry an explicit `None`, which a plain default would pass through into a NOT NULL column.
        bedrock_spend_cents=float(state.get("bedrock_spend_cents") or 0.0),
        last_activity_at=last_activity_at,
    )
    for field in _DIRECT_FIELDS:
        value = state.get(field)
        setattr(summary, field, str(value) if value is not None else None)
    return summary


async def consolidate() -> dict[str, int]:
    """Upsert a summary for every learning thread whose checkpoint has advanced since the last run.

    Returns counts for the caller to print: threads seen, summaries written, threads skipped as
    not-learning, and threads already current.
    """
    engine = create_engine()
    counts = {"threads": 0, "written": 0, "skipped_not_learning": 0, "unchanged": 0}
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            known = await LearningSessionRepository(session).known_activity()

        # One pass over the checkpoint index to find each thread's newest write. Cheap next to
        # `aget_tuple`, and it is what makes the run incremental.
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT thread_id, MAX((checkpoint->>'ts')::timestamptz) "
                        "FROM checkpoints GROUP BY thread_id"
                    )
                )
            ).all()

        stale = [(tid, ts) for tid, ts in rows if known.get(tid) != ts]
        counts["threads"] = len(rows)
        counts["unchanged"] = len(rows) - len(stale)

        async with AsyncPostgresSaver.from_conn_string(checkpoint_dsn_from(engine)) as saver:
            for thread_id, last_activity_at in stale:
                tuple_ = await saver.aget_tuple({"configurable": {"thread_id": thread_id}})
                if tuple_ is None:
                    continue
                summary = summary_from_state(
                    thread_id, dict(tuple_.checkpoint["channel_values"]), last_activity_at
                )
                if summary is None:
                    counts["skipped_not_learning"] += 1
                    continue
                # One transaction per thread. A single malformed checkpoint then costs its own row
                # rather than the whole run's - the same reasoning that keeps FKs off this table.
                async with session_scope(session_factory) as session:
                    await LearningSessionRepository(session).upsert(summary)
                    await session.commit()
                counts["written"] += 1
        return counts
    finally:
        await engine.dispose()


def main() -> None:
    counts = asyncio.run(consolidate())
    print(
        f"consolidated {counts['written']} learning session(s) from {counts['threads']} thread(s); "
        f"{counts['unchanged']} already current, "
        f"{counts['skipped_not_learning']} not learning threads"
    )


if __name__ == "__main__":
    main()
