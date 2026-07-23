from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intellichoice_db.models.base import Base, new_uuid
from intellichoice_db.models.rag import EMBEDDING_DIM

# SPEC §5.8.2 question_template fields.


class QuestionTemplate(Base):
    __tablename__ = "question_templates"

    question_template_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    curriculum_version: Mapped[str] = mapped_column(String, nullable=False)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.topic_id"), nullable=False)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), nullable=False)
    grade_band: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_label: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_confidence: Mapped[float] = mapped_column(nullable=False, default=1.0)
    question_type: Mapped[str] = mapped_column(String, nullable=False, default="multiple_choice")
    parameter_schema: Mapped[dict] = mapped_column(JSON, nullable=False)
    generation_constraints: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    solution_function: Mapped[str] = mapped_column(String, nullable=False)
    correct_option_generator: Mapped[str] = mapped_column(String, nullable=False)
    distractor_generators: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    common_error_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    estimated_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    generator_model: Mapped[str] = mapped_column(String, nullable=False)
    review_model_versions: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    validation_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    active_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # S20 (SPEC §5.8.2-5.8.5, plan §7): authored-item fields, all nullable/defaulted so
    # the existing "shape" pipeline's rows are unaffected. `authoring_mode` picks which
    # column group a template actually uses - "shape" rows keep using
    # `parameter_schema`/`solution_function`/the generator registry; "authored" rows use
    # the fields below instead and always get exactly one static `QuestionVariant`.
    authoring_mode: Mapped[str] = mapped_column(String, nullable=False, default="shape")
    stem: Mapped[str | None] = mapped_column(String, nullable=True)
    context_block: Mapped[str | None] = mapped_column(String, nullable=True)
    answer_expression: Mapped[str | None] = mapped_column(String, nullable=True)
    hint_ladder: Mapped[list | None] = mapped_column(JSON, nullable=True)
    canonical_solution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stem_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(EMBEDDING_DIM), nullable=True
    )
    review_priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")

    variants: Mapped[list["QuestionVariant"]] = relationship(back_populates="template")


class QuestionVariant(Base):
    __tablename__ = "question_variants"

    question_variant_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    question_template_id: Mapped[str] = mapped_column(
        ForeignKey("question_templates.question_template_id"), nullable=False
    )
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    rendered_question: Mapped[str] = mapped_column(String, nullable=False)
    option_a: Mapped[str] = mapped_column(String, nullable=False)
    option_b: Mapped[str] = mapped_column(String, nullable=False)
    option_c: Mapped[str] = mapped_column(String, nullable=False)
    option_d: Mapped[str] = mapped_column(String, nullable=False)
    correct_option: Mapped[str] = mapped_column(String, nullable=False)
    parameter_values: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    template: Mapped[QuestionTemplate] = relationship(back_populates="variants")


class QuestionValidationRun(Base):
    """S20 (plan §7 step 4): one append-only audit row per `generate_authored_candidate`
    attempt, recording every stage's result whether the candidate ended up `pending` or
    `rejected` - see `ai_pipeline.generate_authored_candidate`. `question_template_id` is
    nullable: a candidate rejected before the final "persist" step (deterministic gate,
    solver disagreement, judge rejection) never gets a `QuestionTemplate` row at all
    (matching the existing "shape" pipeline's `generate_candidate`, D-026) but its
    rejection reasons must still be persisted here (ROADMAP S20's "rejected with
    persisted reasons" done-when criterion) - only a candidate that clears every stage
    gets both a template row and a validation-run row with `question_template_id` set.
    """

    __tablename__ = "question_validation_runs"

    question_validation_run_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=new_uuid
    )
    question_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("question_templates.question_template_id"), nullable=True
    )
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    stage_results: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    cost_cents: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
