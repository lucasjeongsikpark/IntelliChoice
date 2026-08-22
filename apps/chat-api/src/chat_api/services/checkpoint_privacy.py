"""AUD-C-03: purge LangGraph's internal resume-value bookkeeping after a
location-consent turn ends.

`LOCATION_CONSENT_NOTICE` promises verbatim that IntelliChoice "will not permanently
store your precise location" (SPEC §5.1.3), and `branch_locator_consent` keeps the
coordinates out of every checkpointed `QAState` field - but `AsyncPostgresSaver`
persists the raw `Command(resume=...)` payload in `checkpoint_writes` under the
`__resume__` channel for crash-safety while the interrupt is being resumed, and nothing
ever removed it (D-045 recorded this as "briefly"; measured, it was the unbounded
lifetime of the thread). Once the resumed turn has ended the resume value has served its
purpose, so deleting it keeps crash-safety for exactly the window it exists to cover.

Deleting by thread rather than by checkpoint id is deliberate: older checkpoints'
`__resume__` values are only reachable through checkpoint history/time travel, which
this app never uses, and a thread's earlier email/calendar resume values (a boolean, a
choice string) are equally finished business.

**Why the session *factory* rather than the request's session** (SEC-13-PURGE). The purge
has to hold on every way a resume turn can end, and two of those ways are failures:
`get_db_session` commits only on its normal path, so a delete issued on the request's
session while an exception is propagating is rolled back at dependency teardown - green to
any assertion made through that same session, and still in the database. The row it is
deleting is not symmetrical with it: `AsyncPostgresSaver.from_conn_string` opens its
connection with `autocommit=True`, so the coordinates were committed the moment the resume
was applied and they outlive the request's rollback. Its own short-lived unit of work is
what closes that gap, and it is the same reason `get_cost_ledger`,
`get_turn_cancellations` and `get_escalation_sends` each take the factory too.
"""

from intellichoice_db.engine import session_scope
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def purge_resume_writes(
    session_factory: async_sessionmaker[AsyncSession], thread_id: str
) -> None:
    async with session_scope(session_factory) as session:
        await session.execute(
            text(
                "DELETE FROM checkpoint_writes WHERE thread_id = :thread_id "
                "AND channel = '__resume__'"
            ),
            {"thread_id": thread_id},
        )
