from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.15.2 learning_events. Spec names the field "question_id"; stored here as
# question_variant_id (a real FK) since that's the only question-level identifier that exists.


class LearningEvent(Base):
    __tablename__ = "learning_events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.topic_id"), nullable=True)
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.skill_id"), nullable=True)
    question_variant_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=True
    )
    structured_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SemanticMemory(Base):
    """SPEC §5.15.3. No fact may exist without evidence_event_ids (enforced by the
    consolidation worker, `packages/memory`, not at the DB layer - S25/plan §9).

    `status` is one of `provisional` (fewer than the minimum-evidence threshold, never
    read by a tutor/chat payload), `active` (served), `contested` (an active fact that a
    later contradicting window demoted - not deleted, per plan §9's "one bad day
    shouldn't relabel a student"), or `superseded` (a second consecutive contradiction
    replaced it - `superseded_by_id` points at the fact that replaced it).
    `contradicts_event_count` tracks how many consolidation windows in a row have
    contradicted an `active` fact; it resets to 0 on a reconfirming window.
    """

    __tablename__ = "semantic_memory"

    semantic_memory_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String, nullable=False)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.topic_id"), nullable=True)
    skill_id: Mapped[str | None] = mapped_column(ForeignKey("skills.skill_id"), nullable=True)
    fact_text: Mapped[str] = mapped_column(String, nullable=False)
    structured_value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_event_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    memory_version: Mapped[int] = mapped_column(nullable=False, default=1)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # S25 (plan §9's contradiction-demotion rule).
    superseded_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("semantic_memory.semantic_memory_id", ondelete="SET NULL"), nullable=True
    )
    contradicts_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
