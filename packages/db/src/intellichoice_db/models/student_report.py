from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.14.2-§5.14.4, ROADMAP S28 (plan §18-L9, §12).


class StudentReport(Base):
    """One generated (or facts-only fallback) report snapshot for one student, scoped to
    a single audience view. `list_for_student` returns history, newest first.

    **Idempotency-keyed since D-159 (AUD-X-04).** This class used to say it deliberately was
    not, because "report generation is an explicit on-demand action, so every call persists a
    new row" - which is right about deliberate re-generation and wrong about a replay: two
    clicks produced two rows and two paid Bedrock calls. The key scopes uniqueness to
    (student, audience, key) so a *replay* is absorbed while a genuinely new request, under a
    new key, still writes history. It does not cap how often a report may be generated.

    `audience` is one of `student`/`parent`/`tutor`/`branch_manager` (SPEC §5.14.2-
    §5.14.4) - always resolved server-side from the caller's role, never a client-
    supplied value (CLAUDE.md non-negotiable #3). `verified_facts` is the exact
    deterministic evidence JSON assembled before the Bedrock call (dashboard aggregates +
    semantic-memory facts, already audience-filtered) - `interpretation_text`/
    `recommendations_text` are re-verified against it
    (`intellichoice_shared.numeric_grounding.is_grounded`) before this row is ever
    written. `generated=False` marks a facts-only fallback (gateway failure or a failed
    grounding check on either text) - both texts are then a deterministic template built
    only from `verified_facts`, never a silently-accepted ungrounded model output (same
    convention as `StageTransition.generated`).
    """

    __tablename__ = "student_reports"
    __table_args__ = (
        UniqueConstraint(
            "student_external_id",
            "audience",
            "idempotency_key",
            name="uq_student_reports_student_audience_key",
        ),
    )

    student_report_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    audience: Mapped[str] = mapped_column(String, nullable=False)
    verified_facts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    interpretation_text: Mapped[str] = mapped_column(String, nullable=False)
    recommendations_text: Mapped[str] = mapped_column(String, nullable=False)
    generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cost_cents: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # AUD-X-04. `NOT NULL` rather than nullable-for-legacy: the migration backfills existing
    # rows with `legacy-<student_report_id>`, which is unique by construction, so the column
    # states the same rule for every row instead of leaving a permanent "may be missing" case
    # for the next reader (and for the unique constraint) to reason about.
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
