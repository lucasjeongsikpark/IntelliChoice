from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid


class EvaluationResult(Base):
    """Backs the S19 evaluation platform (SPEC §5.31); no exact column list is given in
    the spec sections this session reads, so this is a minimal generic shape."""

    __tablename__ = "evaluation_results"

    evaluation_result_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    suite_name: Mapped[str] = mapped_column(String, nullable=False)
    case_id: Mapped[str] = mapped_column(String, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
