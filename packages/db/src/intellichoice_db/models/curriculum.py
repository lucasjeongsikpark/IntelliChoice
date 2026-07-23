from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from intellichoice_db.models.base import Base, new_uuid


class Topic(Base):
    __tablename__ = "topics"

    topic_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    curriculum_version: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    grade_band: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skills: Mapped[list["Skill"]] = relationship(back_populates="topic")


class Skill(Base):
    __tablename__ = "skills"

    skill_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    topic_id: Mapped[str] = mapped_column(ForeignKey("topics.topic_id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    topic: Mapped[Topic] = relationship(back_populates="skills")
