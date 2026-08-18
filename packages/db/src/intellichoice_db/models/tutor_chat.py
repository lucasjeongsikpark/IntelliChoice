from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.12/§5.30.1 (D-072), ROADMAP S24 contextual learning chat.


class TutorChatMessage(Base):
    """One full chat turn - the student's own message (redacted before storage, same as
    before it ever crosses the Bedrock wire) and the tutor's reply, stored together
    since a turn is atomic (one dispatch call, one reply). `student_external_id` only -
    no name, matching every other Postgres table (SPEC §5.30). `question_variant_id` is
    nullable: `off_topic` turns and turns before the student has started a question have
    no associated question. 90-day retention (plan §15) - see
    `TutorChatMessageRepository.purge_older_than`.
    """

    __tablename__ = "tutor_chat_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    learning_session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    question_variant_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=True
    )
    intent: Mapped[str] = mapped_column(String, nullable=False)
    redacted_student_message: Mapped[str] = mapped_column(String, nullable=False)
    reply_text: Mapped[str] = mapped_column(String, nullable=False)
    cost_cents: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # SPEC §5.12.2 "route self-harm/abuse signals through a separately approved safety
    # policy" - True marks a fixed-response turn queued for human review, never an
    # LLM-improvised reply (see `learning_api.services.tutor_chat.screen_for_safety_concern`).
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
