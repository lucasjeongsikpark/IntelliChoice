"""`session_scope` is a unit of work, not a session dispenser (D-284 addendum / D-294).

The defect these pin: it used to yield a session and close it, committing nothing. A
caller that wrote without committing got a **no-op that reported success** - the D-284
addendum's one-off script printed `activated 26, retired 3` and rolled all of it back on
the way out, because `set_active_status` flushes and a flush is not a commit. Nothing
raised, nothing logged, and the count came from the script's own loop.

Both directions, because only one of them is the interesting half (D-221): a clean exit
must persist, and an exception must not. A test that only checked the first would pass on
an implementation that committed unconditionally, including on the way out of a failure.
"""

import asyncio
import uuid

import pytest
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.curriculum import Topic
from sqlalchemy import delete, select

from .conftest import postgres_skip_reason

pytestmark = pytest.mark.skipif(
    postgres_skip_reason() is not None, reason=postgres_skip_reason() or ""
)


def _throwaway_topic() -> Topic:
    return Topic(
        topic_id=f"session-scope-test-{uuid.uuid4()}",
        curriculum_version="test",
        name="session_scope round trip",
        grade_band="6-7",
    )


async def _exists(factory, topic_id: str) -> bool:
    """Read in a session of its own - the point is what another reader can see, and a
    session that wrote the row would report it from its own identity map either way.
    """
    async with session_scope(factory) as session:
        found = await session.execute(select(Topic).where(Topic.topic_id == topic_id))
        return found.scalars().first() is not None


def test_a_write_with_no_explicit_commit_is_still_persisted() -> None:
    async def run() -> None:
        engine = create_engine()
        factory = create_session_factory(engine)
        topic = _throwaway_topic()
        try:
            async with session_scope(factory) as session:
                session.add(topic)
                # Deliberately no `await session.commit()`. This is the exact shape of the
                # ad-hoc script that silently did nothing.
            assert await _exists(factory, topic.topic_id), (
                "a clean exit from session_scope must commit; without this the caller has "
                "no way to tell a successful write from a discarded one"
            )
        finally:
            async with session_scope(factory) as session:
                await session.execute(delete(Topic).where(Topic.topic_id == topic.topic_id))
            await engine.dispose()

    asyncio.run(run())


def test_an_exception_discards_the_write() -> None:
    """The negative control. Commit-on-exit is only safe if the failure path still rolls
    back - otherwise the fix would persist half-finished work, which is worse than the bug
    it replaced.
    """

    class Boom(RuntimeError):
        pass

    async def run() -> None:
        engine = create_engine()
        factory = create_session_factory(engine)
        topic = _throwaway_topic()
        try:
            with pytest.raises(Boom):
                async with session_scope(factory) as session:
                    session.add(topic)
                    # Flushed, so the row exists in the transaction - the D-284 shape.
                    await session.flush()
                    raise Boom("the caller failed after writing")
            assert not await _exists(factory, topic.topic_id)
        finally:
            async with session_scope(factory) as session:
                await session.execute(delete(Topic).where(Topic.topic_id == topic.topic_id))
            await engine.dispose()

    asyncio.run(run())
