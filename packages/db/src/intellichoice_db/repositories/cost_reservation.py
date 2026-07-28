"""Reserve-then-settle for the per-day paid-API ceilings (AUD-X-08).

Unlike every other repository here, this one holds a **session factory**, not a session.
That is the whole point: a reservation has to be visible to concurrent callers *before*
the model call returns, and the request's own session does not commit until FastAPI's
dependency teardown, after the response. A reservation written on the request session
would be invisible to exactly the callers it needs to stop.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from intellichoice_db.models.cost_reservation import CostReservation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Reservation:
    """A granted reservation. `settle` it with the real cost once the call returns."""

    reservation_id: str
    reserved_cents: float


class CeilingReachedError(Exception):
    """The per-day ceiling for this (scope, subject) is already committed or in flight."""

    def __init__(self, scope: str, spend_cents: float, ceiling_cents: float) -> None:
        self.scope = scope
        self.spend_cents = spend_cents
        self.ceiling_cents = ceiling_cents
        super().__init__(
            f"{scope} per-day ceiling reached ({spend_cents:.4f} >= {ceiling_cents:.4f} cents)"
        )


class CostReservationRepository:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def reserve(
        self,
        *,
        scope: str,
        subject_external_id: str,
        estimate_cents: float,
        ceiling_cents: float,
        window: timedelta = timedelta(hours=24),
    ) -> Reservation:
        """Charge `estimate_cents` against the ceiling, or raise `CeilingReachedError`.

        Serialized by a transaction-scoped advisory lock on (scope, subject). The lock is
        necessary and an `INSERT ... SELECT` alone is not: under READ COMMITTED the
        subselect two concurrent inserts run does not see the other's uncommitted row, so
        both would pass the ceiling test. It is held only across two fast statements - a
        sum and an insert - and never across the model call, so it does not serialize the
        expensive part of the request.
        """
        async with self._session_factory() as session:
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"{scope}:{subject_external_id}"},
            )
            spend = await self._spend_cents(
                session, scope=scope, subject_external_id=subject_external_id, window=window
            )
            if spend >= ceiling_cents:
                # Commit rather than roll back: nothing was written, and this releases the
                # advisory lock immediately instead of holding it to teardown.
                await session.commit()
                raise CeilingReachedError(scope, spend, ceiling_cents)

            row = CostReservation(
                scope=scope,
                subject_external_id=subject_external_id,
                reserved_cents=estimate_cents,
            )
            session.add(row)
            await session.commit()
            return Reservation(reservation_id=row.reservation_id, reserved_cents=estimate_cents)

    async def settle(self, reservation_id: str, actual_cents: float) -> None:
        """Replace the estimate with the real cost. Best-effort by design: a reservation
        that is never settled stays charged at its estimate, which over-counts rather than
        under-counts, and a spend ceiling should fail in that direction.
        """
        async with self._session_factory() as session:
            row = await session.get(CostReservation, reservation_id)
            if row is None:
                logger.warning("cost reservation %s vanished before settlement", reservation_id)
                return
            row.actual_cents = actual_cents
            row.settled_at = datetime.now(UTC)
            await session.commit()

    async def spend_cents_since(
        self, *, scope: str, subject_external_id: str, window: timedelta = timedelta(hours=24)
    ) -> float:
        """Committed + in-flight spend for this (scope, subject). Read-only, no lock -
        for reporting and for passing the gateway its `session_spend_cents`.
        """
        async with self._session_factory() as session:
            return await self._spend_cents(
                session, scope=scope, subject_external_id=subject_external_id, window=window
            )

    @staticmethod
    async def _spend_cents(
        session, *, scope: str, subject_external_id: str, window: timedelta
    ) -> float:
        # `coalesce(actual, reserved)` is what closes the race: an in-flight call counts at
        # its estimate until it settles at its real cost.
        stmt = select(
            func.coalesce(
                func.sum(
                    func.coalesce(CostReservation.actual_cents, CostReservation.reserved_cents)
                ),
                0.0,
            )
        ).where(
            CostReservation.scope == scope,
            CostReservation.subject_external_id == subject_external_id,
            CostReservation.created_at >= datetime.now(UTC) - window,
        )
        result = await session.execute(stmt)
        return float(result.scalar_one())
