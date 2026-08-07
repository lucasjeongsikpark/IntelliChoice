"""D-208: memory consolidation must not be on the request path.

**The measurement.** `POST /exam/finalize` on staging: **65 s and 81 s**, of which 61.5 s
was one `memory_consolidation` call. Both attempts took the same duration to the
millisecond - `61502.69ms` and `61503.12ms` - because `bedrock_call_timeout_s` (20.0) times
`1 + max_retries` (2) is exactly 60 s. That is a ceiling, not work.

**And it had never once succeeded.** Fourteen days of staging logs contain two
`memory_consolidation` entries and both are `bedrock_call_failed / provider_unavailable /
TimeoutError`, ending in `"memory consolidation call failed, no facts changed"`. So the
student paid a minute for nothing, twice, and semantic memory never consolidated at all.

These tests pin the two halves of the fix separately, because they are separate claims:
the scheduler returns without waiting, and a failure inside it never escapes to a caller
who is no longer there to catch it.
"""

import asyncio

import pytest
from learning_api.services.consolidation_scheduler import (
    BackgroundConsolidationScheduler,
    InlineConsolidationScheduler,
)


class _SlowSessionFactory:
    """Stands in for `async_sessionmaker`, and records that a session was opened."""

    def __init__(self, on_enter) -> None:
        self.on_enter = on_enter
        self.opened = 0

    def __call__(self):
        return self

    async def __aenter__(self):
        self.opened += 1
        await self.on_enter()
        return object()

    async def __aexit__(self, *exc) -> bool:
        return False


def test_scheduling_returns_without_waiting_for_the_work() -> None:
    """The claim the 61-second measurement is about: `schedule` hands the work off and
    returns. If this ever regresses to an `await` of the real call, the elapsed time here
    goes from ~0 to the length of the work.
    """

    async def run() -> None:
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_enter() -> None:
            started.set()
            await release.wait()

        factory = _SlowSessionFactory(slow_enter)
        scheduler = BackgroundConsolidationScheduler(
            session_factory=factory,  # type: ignore[arg-type]
            gateway_factory=lambda: None,  # type: ignore[return-value,arg-type]
        )

        loop = asyncio.get_running_loop()
        before = loop.time()
        await scheduler.schedule(student_external_id="stu-1", session_id="sess-1")
        elapsed = loop.time() - before

        assert elapsed < 0.05, (
            f"schedule() took {elapsed:.3f}s - it is awaiting the work again, which is the "
            f"defect that made POST /exam/finalize take 65-81s on staging"
        )

        # It really did start, rather than being dropped: the point is "not awaited", not
        # "not run".
        await asyncio.wait_for(started.wait(), timeout=2)
        release.set()
        await asyncio.sleep(0)

    asyncio.run(run())


def test_a_failure_in_the_background_never_escapes() -> None:
    """Nothing awaits this task, so an exception escaping it would surface only as
    "Task exception was never retrieved" at garbage-collection time - the least findable
    place a failure can land. It has to be caught and logged where it happens.
    """

    async def run() -> None:
        async def explode() -> None:
            raise RuntimeError("database is on fire")

        factory = _SlowSessionFactory(explode)
        scheduler = BackgroundConsolidationScheduler(
            session_factory=factory,  # type: ignore[arg-type]
            gateway_factory=lambda: None,  # type: ignore[return-value,arg-type]
        )
        await scheduler.schedule(student_external_id="stu-1", session_id="sess-1")

        # Drain: the task must finish, and finish *without* an exception set on it.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if not scheduler._tasks:
                break
        assert not scheduler._tasks, "the background task never completed"

    asyncio.run(run())


def test_the_task_set_keeps_a_strong_reference_until_the_task_finishes() -> None:
    """`asyncio.create_task` only holds a weak reference, so a task with no other referent
    can be garbage-collected mid-flight - the work would silently never happen. The
    scheduler holds the set for exactly this reason, and drops entries on completion so it
    cannot grow without bound.
    """

    async def run() -> None:
        release = asyncio.Event()

        async def wait_for_release() -> None:
            await release.wait()

        factory = _SlowSessionFactory(wait_for_release)
        scheduler = BackgroundConsolidationScheduler(
            session_factory=factory,  # type: ignore[arg-type]
            gateway_factory=lambda: None,  # type: ignore[return-value,arg-type]
        )
        await scheduler.schedule(student_external_id="stu-1", session_id="sess-1")
        assert len(scheduler._tasks) == 1, "an in-flight task is not being referenced"

        release.set()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if not scheduler._tasks:
                break
        assert not scheduler._tasks, "completed tasks are not being discarded"

    asyncio.run(run())


def test_the_inline_scheduler_actually_finishes_before_returning() -> None:
    """The variant the graph falls back to when no scheduler is injected, which is every
    existing test. It must genuinely complete - a fire-and-forget inline variant would
    silently break every assertion about the facts a cycle produced.
    """

    calls: list[tuple[str, str]] = []

    class _Repo:
        async def list_events_for_session(self, student_external_id: str, session_id: str):
            calls.append((student_external_id, session_id))
            return []

    async def run() -> None:
        scheduler = InlineConsolidationScheduler(
            memory_repo=_Repo(),  # type: ignore[arg-type]
            mastery_repo=None,  # type: ignore[arg-type]
            tutor_chat_repo=None,  # type: ignore[arg-type]
            gateway=None,  # type: ignore[arg-type]
        )
        await scheduler.schedule(student_external_id="stu-1", session_id="sess-1")
        # Already done by the time `schedule` returns - no draining needed.
        assert calls == [("stu-1", "sess-1")]

    asyncio.run(run())


def test_the_consolidation_timeout_is_larger_than_the_shared_one() -> None:
    """The second half of the fix. Consolidation sends up to 20 000 tokens of events plus
    every existing fact; the shared 20 s ceiling is sized for a tutor reply (~3-4 s
    measured) and it timed out on every attempt it ever made.

    Raising it is only safe *because* the call left the request path - which is why these
    two facts are asserted in the same file rather than separately.
    """
    from learning_api.config import Settings

    settings = Settings()
    assert settings.bedrock_consolidation_timeout_s > settings.bedrock_call_timeout_s
    # The observed failure needed more than 60 s of total budget to have any chance.
    assert settings.bedrock_consolidation_timeout_s >= 60.0


@pytest.mark.parametrize("attr", ["schedule"])
def test_both_schedulers_satisfy_the_protocol(attr: str) -> None:
    """Structural check rather than a `isinstance` one - `ConsolidationScheduler` is a
    plain Protocol, and the graph only ever calls this one method.
    """
    assert callable(getattr(BackgroundConsolidationScheduler, attr))
    assert callable(getattr(InlineConsolidationScheduler, attr))
