from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.9.1-§5.9.3: pre/post-exam sessions are the same shape, distinguished by session_type.
# The question set is fixed once created (§5.9.2) - no row is ever regenerated, only appended to
# via assessment_items.


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    assessment_session_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    session_type: Mapped[str] = mapped_column(String, nullable=False)  # pre_exam | post_exam
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # D-218: when the exam was first actually *on screen*, which is not when the row was
    # created. The row is assembled one graph turn before the student can reach a question -
    # the stage-transition overlay is modal - so `started_at` bills reading time against the
    # time limit. Null for rows created before D-218 and for any client that never reports
    # it; `flow.exam_clock_start` falls back to `started_at` in that case.
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # S22 (SPEC §5.9/§5.13, AssessmentPolicy): informational only, not backfilled for rows
    # created before this session - only discoverable via items before now.
    topic_id: Mapped[str | None] = mapped_column(
        ForeignKey("topics.topic_id"), nullable=True
    )
    # JSON snapshot of the AssessmentPolicy applied at creation time (learning_api.services.
    # exam_policy) - stored so a later change to the policy constants can't retroactively
    # alter an already-in-progress exam's rules.
    policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    time_limit_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Set once by `flow.finalize_exam` - a fresh, non-null value is the authoritative
    # "already finalized" check (read straight from this row, not from checkpointed
    # `LearningState`), so a retried `/exam/finalize` call can be served idempotently.
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["AssessmentItem"]] = relationship(back_populates="session")


class AssessmentItem(Base):
    __tablename__ = "assessment_items"

    assessment_item_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    assessment_session_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_sessions.assessment_session_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)

    session: Mapped[AssessmentSession] = relationship(back_populates="items")


class AssessmentItemState(Base):
    """S22 (SPEC §5.9/§5.13, plan §18-L3): per-item navigation state for the exam nav bar -
    unseen/answered/skipped/flagged, one row per `AssessmentItem`, created alongside it in
    `assessment_builder.py`. Grading itself still lives on `AssessmentAttempt` (grade-on-
    submit was kept, D-064) - this table is purely navigation/timing bookkeeping, never a
    second source of truth for correctness.
    """

    __tablename__ = "assessment_item_state"

    assessment_item_state_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=new_uuid
    )
    assessment_item_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_items.assessment_item_id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="unseen")
    first_viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Populated by the S23 frontend autosave tick via `AssessmentRepository.add_item_time`.
    time_spent_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AssessmentAttempt(Base):
    """Deterministic pre/post-exam grading record (SPEC §5.9.3). No LLM involved."""

    __tablename__ = "assessment_attempts"
    # One attempt per item per exam (AUD-L-10). `idempotency_key` used to be part of this
    # key, which meant a resubmission under a *new* key inserted a second graded attempt -
    # and scoring counts attempts (`learning_gain.compute_learning_gain`'s `max_score`), so
    # a changed answer rescored a 10-item exam as 10/11. The key deduplicates retries; it
    # was never meant to license a second answer.
    __table_args__ = (
        UniqueConstraint(
            "assessment_session_id",
            "question_variant_id",
            name="uq_assessment_attempts_session_variant",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    assessment_session_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_sessions.assessment_session_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    # Nullable since S22: a `flow.finalize_exam` call synthesizes an incorrect attempt for
    # any item skipped through to the end, with no real selected option to record.
    selected_option: Mapped[str | None] = mapped_column(String, nullable=True)
    correct_option: Mapped[str] = mapped_column(String, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)


class BlockedSession(Base):
    """Why a learning session was blocked (SPEC §5.6.5). No score/penalty is ever recorded here."""

    __tablename__ = "blocked_sessions"

    blocked_session_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    week_id: Mapped[str] = mapped_column(String, nullable=False)
    blocked_reason: Mapped[str] = mapped_column(String, nullable=False)
    blocked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
