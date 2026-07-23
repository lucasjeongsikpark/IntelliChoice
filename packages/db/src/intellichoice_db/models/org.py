from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base


class OrgBranch(Base):
    """SPEC §5.20/plan §2.3 - the real tutoring-branch directory, scraped from the
    org's own public `/branches/` page (`packages/webcontent`) rather than hand-
    authored. `branch_external_id` is the natural-key primary key (D-016's pattern);
    a re-sync of an unchanged page is a no-op via `content_hash`, and a branch that
    disappears from the page flips `status` to "inactive" rather than being deleted
    (S15 `YoutubeVideo.active_status`'s convention).
    """

    __tablename__ = "org_branches"

    branch_external_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    hours: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")


class OrgEvent(Base):
    """SPEC §5.23/plan §2.4 (S18) - real events from the org's Tribe Events Calendar
    REST API, replacing S12's placeholder `academic-calendar` document's per-turn LLM
    date extraction with a queryable structured table. `status` holds the org's own
    declared scheduling override (`"canceled"`/`"changed"`) when known, or a neutral
    `"scheduled"` default otherwise - `upcoming` vs `completed` is deliberately *not*
    trusted from this column (it would go stale between syncs); `chat_api.services.
    calendar_events.classify_event` always recomputes that pair against the current
    time, so a past event is never described as upcoming regardless of when this row
    was last synced. No `mark_inactive_except`-style bookkeeping exists for events
    (unlike `OrgBranch`/`OrgTeamMember`) - a real event does not "go inactive" the way a
    closed branch or departed staff member does, it simply becomes `completed`; the org's
    own event history has never had one disappear from the source once published.
    """

    __tablename__ = "org_events"

    event_external_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    audience: Mapped[str] = mapped_column(String, nullable=False, default="public")
    branch_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    registration_url: Mapped[str | None] = mapped_column(String, nullable=True)
    recurrence_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="scheduled")
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OrgTeamMember(Base):
    """SPEC §5.20/plan §2.3 - staff/volunteer-leadership bios from the org's own
    public `/pages/our-team/` page. `name`/`biography` are content the org itself
    chose to publish about its leadership on its public website, not student/user PII
    - an explicit, documented exemption in `test_schema_purity.py` covers this (D-050,
    plan §19 decision #2, confirmed with the user at S17 start).
    """

    __tablename__ = "org_team_members"

    team_member_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role_title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    biography: Mapped[str] = mapped_column(String, nullable=False)
    branch_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    audience: Mapped[str] = mapped_column(String, nullable=False, default="public")
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
