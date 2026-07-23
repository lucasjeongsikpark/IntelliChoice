from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.11.4, ROADMAP S21 personalized hint ladder.


class HintEvent(Base):
    """One hint level served within a single study attempt's within-question ladder
    (`assistance_level_by_variant`, `learning_api.graph.nodes.intervention_choice`).
    `student_external_id` only - no name, matching every other Postgres table (SPEC
    §5.30). `was_personalized=False` marks a canonical-verbatim fallback (gateway
    failure, or a failed leak/monotonicity check on the personalized text) - never a
    row with bad content.
    """

    __tablename__ = "hint_events"

    hint_event_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    study_attempt_id: Mapped[str] = mapped_column(
        ForeignKey("study_attempts.attempt_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    hint_level: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_hint_text: Mapped[str] = mapped_column(String, nullable=False)
    personalized_hint_text: Mapped[str] = mapped_column(String, nullable=False)
    misconception_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    was_personalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
