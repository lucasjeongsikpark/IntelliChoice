from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intellichoice_db.models.base import Base, new_uuid

# SPEC §5.11.1 base study plan.


class StudySession(Base):
    __tablename__ = "study_sessions"

    study_session_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.topic_id"), nullable=False)
    target_skill_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    starting_difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    base_problem_count: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    maximum_attempts_per_skill: Mapped[int] = mapped_column(Integer, nullable=False)
    intervention_policy: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="in_progress")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attempts: Mapped[list["StudyAttempt"]] = relationship(back_populates="study_session")
    items: Mapped[list["StudyItem"]] = relationship(back_populates="study_session")


class StudyItem(Base):
    """One served study question (SPEC §5.11.1-§5.11.7). Created incrementally, not as a
    fixed batch: one base item per target skill (`is_remediation=False`) plus dynamically
    generated retry/prerequisite remediation items (`is_remediation=True`) as the retry
    ladder escalates. `target_skill_id` is the base skill this item's line is remediating
    (== `skill_id` for base items; the *prerequisite* skill's question keeps the base
    `target_skill_id` so its attempts count toward the same skill line). The current
    pending question is the item lacking a matching `StudyAttempt`.
    """

    __tablename__ = "study_items"

    study_item_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    study_session_id: Mapped[str] = mapped_column(
        ForeignKey("study_sessions.study_session_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    target_skill_id: Mapped[str] = mapped_column(String, nullable=False)
    skill_id: Mapped[str] = mapped_column(String, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    is_remediation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    study_session: Mapped[StudySession] = relationship(back_populates="items")


class StudyAttempt(Base):
    """Study-phase attempts, unlike assessment_attempts, carry hint/video/solution and
    retry-ladder context (SPEC §5.11.3-§5.11.7). `outcome_label` is one of the six §5.11.7
    final outcomes (`independent_correct`, `correct_after_hint/video/solution`,
    `answer_revealed`, `unresolved`) or the interim `incorrect`; only `independent_correct`
    counts toward independent mastery (§5.11.5, §5.10.3). `tutor_review_flagged` marks a
    skill line the student never resolved after the full ladder (§5.11.7 4th attempt).
    """

    __tablename__ = "study_attempts"

    # D-216: one attempt per served item, as the StudyItem docstring above already
    # promises ("the current pending question is the item lacking a matching
    # StudyAttempt"). Safe as a (session, variant) pair because every serving - including
    # a D-210 re-serve of a seen rendering - mints a fresh variant row. The exam-side
    # precedent is `uq_assessment_attempts_session_variant` (AUD-L-10).
    __table_args__ = (
        UniqueConstraint(
            "study_session_id",
            "question_variant_id",
            name="uq_study_attempts_session_variant",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    study_session_id: Mapped[str] = mapped_column(
        ForeignKey("study_sessions.study_session_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    selected_option: Mapped[str] = mapped_column(String, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hint_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    video_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    solution_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome_label: Mapped[str | None] = mapped_column(String, nullable=True)
    tutor_review_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    responded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    study_session: Mapped[StudySession] = relationship(back_populates="attempts")


class Mastery(Base):
    """Bootstrap mastery model (SPEC §5.10.1). Enterprise IRT/Bayesian fields (§5.10.2) are
    nullable until that model exists.
    """

    __tablename__ = "mastery"

    mastery_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.skill_id"), nullable=False)
    raw_accuracy: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False)
    accuracy_by_difficulty: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    highest_consistent_difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_confidence_interval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mastery_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False, default="bootstrap-v1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningGain(Base):
    """SPEC §5.13.3 learning-gain metrics.

    `study_session_id`/`topic_id` (S11) link a completed pre->study->post cycle back to
    its study session and topic - nullable because no FK/grouping id ties the three
    phases together otherwise (the `LearningSession` table that once did this was
    retired in S6; domain tables are the record now). `services/history.py` is the one
    reader: it uses `study_session_id` to pull hint/solution/video counts and the
    tutor-review flag for the SPEC §5.14.3 parent dashboard, since a completed
    `LearningGain` row is the closest thing to a "finished learning session" record.
    """

    __tablename__ = "learning_gain"

    learning_gain_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    student_external_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    pre_assessment_session_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_sessions.assessment_session_id"), nullable=False
    )
    post_assessment_session_id: Mapped[str] = mapped_column(
        ForeignKey("assessment_sessions.assessment_session_id"), nullable=False
    )
    study_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("study_sessions.study_session_id"), nullable=True
    )
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.topic_id"), nullable=True)
    pre_raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    post_raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    raw_gain: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_gain: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_gain: Mapped[float | None] = mapped_column(Float, nullable=True)
    normalized_gain_status: Mapped[str | None] = mapped_column(String, nullable=True)
    skill_level_gain: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    difficulty_transition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    independent_correct_rate: Mapped[float] = mapped_column(Float, nullable=False)
    hint_dependency: Mapped[float] = mapped_column(Float, nullable=False)
    solution_dependency: Mapped[float] = mapped_column(Float, nullable=False)
    unresolved_skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    response_time_change_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
