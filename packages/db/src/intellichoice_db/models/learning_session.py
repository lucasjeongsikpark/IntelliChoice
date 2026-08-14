"""The durable summary of a learning session (U7, D-331).

**Why this table exists, and why it did not before.** A learning session has never had a row of its
own. Its identity and lifecycle lived entirely in the LangGraph checkpoint, and every durable table
that references it - `stage_transitions.learning_session_id`, `tutor_chat_messages
.learning_session_id`, `learning_events.session_id` - holds a bare string pointing at nothing but
that checkpoint. That was invisible while nothing deleted checkpoints. U7 proposes to delete them,
which turns an invisible gap into data loss.

**The five fields this table exists to save.** D-331 enumerated all 31 `LearningState` fields
against the durable schema. Twenty-six were either already durable or transient by design. These
five had no home anywhere:

- `week_id` - only `blocked_sessions.week_id` exists, so a *non-blocked* session's attendance week
  is recorded nowhere. "Did this student do their weekly session?" is a product question and
  `learning_gain` carries only `computed_at`.
- `parent_external_id` - who drove the session, parent or student. Audit-shaped and absent.
- `bedrock_spend_cents` - per-call costs land in `cost_reservations` and
  `stage_transitions.cost_cents` (90-day), but the per-session total is nowhere.
- `attendance_status` - the input to the §5.4.4 gate decision.
- `attendance_resolution` - SPEC §5.6.5 names it; `blocked_sessions` stores `blocked_reason` but
  never how the block was resolved.

`phase` is a sixth, half-case: the sub-sessions carry their own `status`, but the *learning
session's* own lifecycle state exists only in the checkpoint.

**No foreign keys, deliberately.** `pre_assessment_session_id` and friends are plain strings even
though the target rows exist, because this table is written by a reconciler reading arbitrary
checkpoint state. A FK violation would abort a whole consolidation run over one inconsistent
thread, which is the opposite of what a durability backstop should do. This also matches the
existing precedent: `stage_transitions.learning_session_id` is itself a bare indexed string.

**No PII** (SPEC §5.30): external ids, curriculum ids, enum-ish strings, timestamps and a float.
`packages/db/tests/test_schema_purity.py` enforces the column-name half of that.

**No retention window of its own, and that is the point.** Three of the tables U7 was originally
going to treat as "durable homes" are themselves purged - `stage_transitions` and `semantic_memory`
at 90 days, `learning_events` at 365 (`retention_purge_cli.py`, D-114/D-153). A summary that
expires sooner than the thing it summarizes would only move the deletion date.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    # The LangGraph `thread_id`. Not generated here: this row is a projection of a checkpoint that
    # already has an identity, and inventing a second one would break every existing reference.
    learning_session_id: Mapped[str] = mapped_column(String, primary_key=True)

    # Nullable because a thread exists from its first turn, before `resolve_student` has run - an
    # abandoned "who is this?" session is exactly the kind of thread that otherwise accumulates
    # forever unexplained.
    student_external_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    parent_external_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    user_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    user_role: Mapped[str | None] = mapped_column(String, nullable=True)

    week_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    topic_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    phase: Mapped[str] = mapped_column(String, nullable=False, index=True)

    attendance_status: Mapped[str | None] = mapped_column(String, nullable=True)
    attendance_resolution: Mapped[str | None] = mapped_column(String, nullable=True)

    pre_assessment_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    study_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    post_assessment_session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    blocked_session_id: Mapped[str | None] = mapped_column(String, nullable=True)

    bedrock_spend_cents: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # `last_activity_at` is the checkpoint's own newest `ts`, **not** the time this row was
    # written. The future deletion job reads its age floor from this column, so it has to mean
    # "when the student last touched the session" rather than "when the reconciler last ran" -
    # otherwise every consolidation pass would reset the clock and nothing would ever age out.
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # When the checkpoint's rows were actually removed, or NULL while they still exist. Lets a
    # reader tell "this session was consolidated and its scaffolding is gone" from "not yet
    # reached", and makes the deletion job's second run a no-op it can prove rather than assume.
    checkpoint_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consolidated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
