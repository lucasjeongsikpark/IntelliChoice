"""AUD-C-03: purge LangGraph's internal resume-value bookkeeping after a
location-consent turn completes.

`LOCATION_CONSENT_NOTICE` promises verbatim that IntelliChoice "will not permanently
store your precise location" (SPEC §5.1.3), and `branch_locator_consent` keeps the
coordinates out of every checkpointed `QAState` field - but `AsyncPostgresSaver`
persists the raw `Command(resume=...)` payload in `checkpoint_writes` under the
`__resume__` channel for crash-safety while the interrupt is being resumed, and nothing
ever removed it (D-045 recorded this as "briefly"; measured, it was the unbounded
lifetime of the thread). Once the resumed `ainvoke` has returned, the post-node
checkpoint is written and the resume value has served its purpose, so deleting it
keeps crash-safety for exactly the window it exists to cover.

Deleting by thread rather than by checkpoint id is deliberate: older checkpoints'
`__resume__` values are only reachable through checkpoint history/time travel, which
this app never uses, and a thread's earlier email/calendar resume values (a boolean, a
choice string) are equally finished business.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def purge_resume_writes(db: AsyncSession, thread_id: str) -> None:
    await db.execute(
        text(
            "DELETE FROM checkpoint_writes WHERE thread_id = :thread_id AND channel = '__resume__'"
        ),
        {"thread_id": thread_id},
    )
