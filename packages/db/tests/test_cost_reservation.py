"""S42 (AUD-X-08): the spend ledger that makes the per-day cost ceilings atomic.

Unlike the other repository tests here, these cannot use `rollback_session` - the whole
point of `CostReservationRepository` is that it commits on its own connection so an
in-flight reservation is visible to concurrent callers. So each test cleans up after
itself by subject id instead.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.models.cost_reservation import SCOPE_STUDENT_REPORT, SCOPE_TUTOR_CHAT
from intellichoice_db.repositories.cost_reservation import (
    CeilingReachedError,
    CostReservationRepository,
)
from sqlalchemy import text

from .conftest import postgres_skip_reason

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

SUBJECT = "cost-ledger-test-subject"
OTHER_SUBJECT = "cost-ledger-test-other"


async def _cleanup() -> None:
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM cost_reservations WHERE subject_external_id = ANY(:ids)"),
                {"ids": [SUBJECT, OTHER_SUBJECT]},
            )
    finally:
        await engine.dispose()


async def _backdate(reservation_id: str, age: timedelta) -> None:
    engine = create_engine()
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("UPDATE cost_reservations SET created_at = :at WHERE reservation_id = :id"),
                {"at": datetime.now(UTC) - age, "id": reservation_id},
            )
    finally:
        await engine.dispose()


def _run(coro_factory) -> None:
    async def wrapped() -> None:
        engine = create_engine()
        try:
            repo = CostReservationRepository(create_session_factory(engine))
            await _cleanup()
            try:
                await coro_factory(repo)
            finally:
                await _cleanup()
        finally:
            await engine.dispose()

    asyncio.run(wrapped())


def test_a_reservation_counts_against_the_ceiling_before_it_settles() -> None:
    """The property the whole table exists for: an unsettled reservation is already
    charged. Before AUD-X-08's fix the equivalent read saw only committed spend rows, so
    an in-flight call counted as zero.
    """

    async def body(repo: CostReservationRepository) -> None:
        first = await repo.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=SUBJECT,
            estimate_cents=0.5,
            ceiling_cents=1.0,
        )
        # Nothing settled yet, and the estimate is already visible.
        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT, subject_external_id=SUBJECT
        ) == pytest.approx(0.5)

        second = await repo.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=SUBJECT,
            estimate_cents=0.5,
            ceiling_cents=1.0,
        )
        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT, subject_external_id=SUBJECT
        ) == pytest.approx(1.0)

        with pytest.raises(CeilingReachedError):
            await repo.reserve(
                scope=SCOPE_STUDENT_REPORT,
                subject_external_id=SUBJECT,
                estimate_cents=0.5,
                ceiling_cents=1.0,
            )

        # Settling for less than the estimate returns the difference to the ceiling.
        await repo.settle(first.reservation_id, 0.1)
        await repo.settle(second.reservation_id, 0.1)
        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT, subject_external_id=SUBJECT
        ) == pytest.approx(0.2)

    _run(body)


def test_concurrent_reservations_cannot_exceed_the_ceiling() -> None:
    """The arm D-102 requires. A read-then-act check passes the sequential test above and
    still lets ten simultaneous callers through; the advisory lock in `reserve` is what
    makes this one pass, and dropping it is visible here and nowhere else.
    """

    async def body(repo: CostReservationRepository) -> None:
        async def attempt() -> bool:
            try:
                await repo.reserve(
                    scope=SCOPE_STUDENT_REPORT,
                    subject_external_id=SUBJECT,
                    estimate_cents=1.0,
                    ceiling_cents=3.0,
                )
                return True
            except CeilingReachedError:
                return False

        results = await asyncio.gather(*(attempt() for _ in range(10)))

        # The ceiling is 3.0 and each reservation is 1.0, so at most 3 can be granted.
        assert sum(results) == 3, results
        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT, subject_external_id=SUBJECT
        ) == pytest.approx(3.0)

    _run(body)


def test_spend_is_scoped_by_surface_subject_and_window() -> None:
    """A ceiling that another surface's spend, another student's spend, or last week's
    spend can trip would deny legitimate use - the same three axes AUD-L-02's original
    test pinned, now on the ledger.
    """

    async def body(repo: CostReservationRepository) -> None:
        mine = await repo.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=SUBJECT,
            estimate_cents=1.0,
            ceiling_cents=100.0,
        )
        await repo.settle(mine.reservation_id, 1.0)
        other_surface = await repo.reserve(
            scope=SCOPE_TUTOR_CHAT,
            subject_external_id=SUBJECT,
            estimate_cents=2.0,
            ceiling_cents=100.0,
        )
        await repo.settle(other_surface.reservation_id, 2.0)
        other_subject = await repo.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=OTHER_SUBJECT,
            estimate_cents=4.0,
            ceiling_cents=100.0,
        )
        await repo.settle(other_subject.reservation_id, 4.0)
        stale = await repo.reserve(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=SUBJECT,
            estimate_cents=8.0,
            ceiling_cents=100.0,
        )
        await repo.settle(stale.reservation_id, 8.0)
        await _backdate(stale.reservation_id, timedelta(days=7))

        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT, subject_external_id=SUBJECT
        ) == pytest.approx(1.0)
        # A wider window does pick the old one up, which is what proves it was excluded
        # by the window rather than simply missing.
        assert await repo.spend_cents_since(
            scope=SCOPE_STUDENT_REPORT,
            subject_external_id=SUBJECT,
            window=timedelta(days=30),
        ) == pytest.approx(9.0)

    _run(body)


def test_an_unsettled_reservation_stays_charged_at_its_estimate() -> None:
    """A process that dies mid-call leaves its reservation unsettled. That must keep
    counting - failing closed on spend is the safe direction, and the alternative is a
    crash loop that spends without limit.
    """

    async def body(repo: CostReservationRepository) -> None:
        await repo.reserve(
            scope=SCOPE_TUTOR_CHAT,
            subject_external_id=SUBJECT,
            estimate_cents=0.5,
            ceiling_cents=100.0,
        )
        assert await repo.spend_cents_since(
            scope=SCOPE_TUTOR_CHAT, subject_external_id=SUBJECT
        ) == pytest.approx(0.5)

    _run(body)
