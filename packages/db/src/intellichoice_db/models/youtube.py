from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base
from intellichoice_db.models.rag import EMBEDDING_DIM


class YoutubeVideo(Base):
    """SPEC §5.18.2 stored metadata - the local catalog `youtube_catalog.search`
    queries at learning time (§5.18.3), never a live YouTube API call.
    `youtube_video_id` (the real YouTube id) is the natural-key primary key, same
    D-016 convention as `Topic`/`Skill`'s YAML ids - a re-sync of the same video is an
    update-in-place, never a duplicate row.
    """

    __tablename__ = "youtube_videos"

    youtube_video_id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[str] = mapped_column(String, nullable=False)
    channel_title: Mapped[str] = mapped_column(String, nullable=False)
    video_url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    playlist_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    duration: Mapped[str] = mapped_column(String, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    thumbnail_url: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="en")
    # Re-validated against the real curriculum registry before ever being written here
    # (SPEC §5.18's classification step, D-038-style "model proposes, code re-derives" -
    # see `intellichoice_youtube.classify`) - never the model's own invented labels.
    topic_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skill_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    grade_band: Mapped[str] = mapped_column(String, nullable=False)
    difficulty_min: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_max: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # "active" | "inactive" (SPEC §5.18.2 "Mark deleted or private videos as inactive") -
    # never deleted outright, so a re-sync's "removed video" handling is reversible if
    # the video reappears in a later fetch.
    active_status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    # S27 hardening columns (plan §18-L8) ----------------------------------------------
    # Deterministically derived from `skill_ids` via `CurriculumContent.prerequisite_for`
    # in `catalog_sync.py` - never an LLM output (project's "deterministic core" rule).
    prerequisite_skill_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    transcript_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    transcript_language: Mapped[str | None] = mapped_column(String, nullable=True)
    license: Mapped[str] = mapped_column(String, nullable=False, default="youtube")
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Independent of `active_status` (which tracks "still in the channel's uploads at
    # all"): a content/policy gate `search_catalog` also checks, defaulting to the one
    # value this session ever sets - a future human/automated review step could set it
    # to something else without touching liveness.
    suitability_status: Mapped[str] = mapped_column(String, nullable=False, default="approved")
    # Reset to 0 on a verification pass that finds the video available again -
    # "reversible", same posture as `active_status`.
    verification_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
