from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# Phase 8 (SPEC §6.9) completion criterion: "No external action can execute before
# approval." This is that audit record. Only external-id references, never the email
# recipient/subject/body itself - Postgres stores that a decision was made, not the PII
# the decision was about (D-020).


class InterruptApproval(Base):
    __tablename__ = "interrupt_approvals"

    approval_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    # Renamed from `learning_session_id` in S14: chat-api now writes rows here too
    # (admin-escalation email approval, calendar action), so the column is generic
    # across both apps' checkpointed session ids; `source_app` disambiguates which.
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_app: Mapped[str] = mapped_column(String, nullable=False)  # "learning" | "chat"
    interrupt_type: Mapped[str] = mapped_column(String, nullable=False)
    # No CHECK constraint (plain String) - learning-api still only ever writes
    # "approved"/"cancelled"; chat-api's calendar_action records the literal 3-way
    # choice ("google"/"ics"/"cancel") since there's no reason to lossily compress it.
    decision: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable in S14: chat-api allows anonymous callers (SPEC §5.19.1) to trigger
    # admin-escalation/calendar actions, so there's no external id to record for them -
    # learning-api requires auth on every endpoint and always supplies one.
    decided_by_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
