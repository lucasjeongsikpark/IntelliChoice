from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.10.3/§5.13.3, ROADMAP S26 personalized stage narratives (plan §18-L7).


class StageTransition(Base):
    """One generated (or template-fallback) narrative for one stage moment in a
    learning session. `student_external_id`/`learning_session_id` only - no name,
    matching every other Postgres table (SPEC §5.30). `related_skill_id` is nullable:
    only `study_step` (a skill-transition narrative) ever sets it - the other four
    stages fire at most once per session, matching the read-side idempotency check
    (`StageTransitionRepository.get_for_session_stage`) that runs before ever calling
    Bedrock again for the same (session, stage[, skill]). `evidence` is the exact
    deterministic JSON built before the Bedrock call - `narrative_text` is re-verified
    against it (`intellichoice_shared.numeric_grounding.is_grounded`) before this row is
    ever written; `generated=False` marks a narrative that used the deterministic
    template fallback instead (gateway failure or a failed grounding check), never a
    silently-accepted ungrounded model output.
    """

    __tablename__ = "stage_transitions"

    stage_transition_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    learning_session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    related_skill_id: Mapped[str | None] = mapped_column(String, nullable=True)
    narrative_text: Mapped[str] = mapped_column(String, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cost_cents: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
