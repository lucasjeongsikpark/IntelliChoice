"""Structured records the extractors produce - the shape written to
`knowledge-content/structured/*.yaml` and consumed by the loaders in `org_load.py`.
"""

from pydantic import BaseModel


class BranchRecord(BaseModel):
    branch_external_id: str
    name: str
    address: str | None
    hours_raw: str | None
    online_only: bool
    detail_url: str
    content_hash: str


class TeamMemberRecord(BaseModel):
    team_member_id: str
    name: str
    role_title: str
    category: str
    biography: str
    content_hash: str


class AboutSection(BaseModel):
    heading: str | None
    level: int
    paragraphs: list[str]


class EventRecord(BaseModel):
    event_external_id: str
    title: str
    description: str
    starts_at: str
    ends_at: str
    timezone: str
    location: str | None
    registration_url: str | None
    recurrence_rule: str | None
    source_url: str
    content_hash: str
