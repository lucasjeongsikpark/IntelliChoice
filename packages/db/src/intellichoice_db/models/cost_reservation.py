"""Atomic spend reservations for the per-day paid-API ceilings (AUD-X-08).

Every per-day ceiling in this codebase was read-then-act: read the spend, then spend. Two
windows, not one - concurrent callers all read the same pre-call value, and because the row
carrying the cost is committed by the FastAPI dependency teardown *after* the response
(AUD-X-07's ordering), even a staggered caller that starts after an earlier call finished
its model request still read a stale total. Measured: 10 concurrent reports produced 10
generated reports and 10x the ceiling, while the sequential control degraded correctly.

This table is the serialization point. A caller reserves its worst-case cost *before* the
model call, in its own immediately-committed transaction, and settles the real cost after.
An in-flight reservation is therefore visible to every other caller, which the spending
row itself was not.

No PII: `subject_external_id` is the same external reference every other table uses
(SPEC §5.30), and `scope` is a fixed enum of surface names.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# Ceiling surfaces. Kept as strings rather than a Postgres enum so adding a surface is a
# code change, not a migration - the same posture `assessment_sessions.session_type` takes.
SCOPE_STUDENT_REPORT = "student_report"
SCOPE_TUTOR_CHAT = "tutor_chat"
# D-345: chat-api's per-*day* ceiling, and the one scope here whose subject is not a person.
# Its subject is the constant `SUBJECT_CHAT_API`, because the thing being bounded is the
# app's daily bill rather than one caller's share of it - a chat caller may be anonymous,
# and the only identifier an anonymous caller has is an IP, which must not be stored here
# (see `rate_limit_events`, which HMACs its key for exactly this reason).
SCOPE_CHAT_TURN = "chat_turn"
SUBJECT_CHAT_API = "chat-api"


class CostReservation(Base):
    __tablename__ = "cost_reservations"
    __table_args__ = (
        # The ceiling query is always (scope, subject, created_at >= window start).
        Index(
            "ix_cost_reservations_scope_subject_created",
            "scope",
            "subject_external_id",
            "created_at",
        ),
    )

    reservation_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    scope: Mapped[str] = mapped_column(String, nullable=False)
    subject_external_id: Mapped[str] = mapped_column(String, nullable=False)
    # What the caller committed to before making the call - the gateway's own worst-case
    # estimate for that request. Counted against the ceiling while the call is in flight.
    reserved_cents: Mapped[float] = mapped_column(Float, nullable=False)
    # The real cost, written after the call returns. NULL means still in flight (or that
    # the process died mid-call, in which case the reservation stays charged at its
    # estimate - failing closed, which for a spend ceiling is the safe direction).
    actual_cents: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
