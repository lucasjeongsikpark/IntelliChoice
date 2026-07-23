from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid


class ProblemReport(Base):
    """SPEC §5.8.7. Uniqueness is scoped to the template, not the variant, so repeat
    reports from the same student against different variants of the same template still
    count once toward the five-distinct-user quarantine threshold.
    """

    __tablename__ = "problem_reports"
    __table_args__ = (UniqueConstraint("question_template_id", "student_external_id"),)

    problem_report_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    question_template_id: Mapped[str] = mapped_column(
        ForeignKey("question_templates.question_template_id"), nullable=False
    )
    question_variant_id: Mapped[str] = mapped_column(
        ForeignKey("question_variants.question_variant_id"), nullable=False
    )
    student_external_id: Mapped[str] = mapped_column(String, nullable=False)
    report_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
