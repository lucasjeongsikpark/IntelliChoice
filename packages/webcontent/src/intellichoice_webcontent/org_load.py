"""`make org-load`: upserts `org_branches`/`org_team_members`/`org_events` from the
structured YAML `sync_cli.py` already wrote (and a human already reviewed) -
natural-key + content_hash idempotency (D-016's pattern, mirrors `YoutubeRepository`'s
S15 upsert/inactive-mark shape). Never fetches the network itself; a missing structured
file is a hard error, not an empty no-op, so a typo'd path can't silently wipe the
directory to "all inactive." `load_events` has no inactive-marking step (S18) - see
`OrgEvent`'s own docstring for why.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from intellichoice_db.models.org import OrgBranch, OrgEvent, OrgTeamMember
from intellichoice_db.repositories.org import (
    OrgBranchRepository,
    OrgEventRepository,
    OrgTeamMemberRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession

_REPO_ROOT = Path(__file__).resolve().parents[4]
_STRUCTURED_DIR = _REPO_ROOT / "knowledge-content" / "structured"


class OrgLoadError(Exception):
    """A structured YAML file was missing or malformed - never treated as "no records"."""


@dataclass
class OrgLoadSummary:
    branches_created: int = 0
    branches_updated: int = 0
    branches_unchanged: int = 0
    branches_marked_inactive: int = 0
    members_created: int = 0
    members_updated: int = 0
    members_unchanged: int = 0
    members_marked_inactive: int = 0
    events_created: int = 0
    events_updated: int = 0
    events_unchanged: int = 0


def _load_structured(name: str) -> dict:
    path = _STRUCTURED_DIR / f"{name}.yaml"
    if not path.exists():
        raise OrgLoadError(f"missing structured file: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data.get("records"), list):
        raise OrgLoadError(f"{path} has no 'records' list")
    return data


async def load_branches(session: AsyncSession) -> tuple[int, int, int, int]:
    repo = OrgBranchRepository(session)
    seen_ids: list[str] = []
    created = updated = unchanged = 0
    for rec in _load_structured("branches")["records"]:
        existing = await repo.get_branch(rec["branch_external_id"])
        was_new = existing is None
        was_unchanged = existing is not None and existing.content_hash == rec["content_hash"]
        await repo.upsert_branch(
            OrgBranch(
                branch_external_id=rec["branch_external_id"],
                name=rec["name"],
                address=rec["address"],
                hours={"raw_text": rec["hours_raw"]} if rec["hours_raw"] else {},
                source_url=rec["detail_url"],
                content_hash=rec["content_hash"],
            )
        )
        seen_ids.append(rec["branch_external_id"])
        if was_new:
            created += 1
        elif was_unchanged:
            unchanged += 1
        else:
            updated += 1
    marked_inactive = await repo.mark_inactive_except(seen_ids)
    return created, updated, unchanged, marked_inactive


async def load_team_members(session: AsyncSession) -> tuple[int, int, int, int]:
    repo = OrgTeamMemberRepository(session)
    seen_ids: list[str] = []
    created = updated = unchanged = 0
    data = _load_structured("team")
    source_url = data["source_url"]
    for rec in data["records"]:
        existing = await repo.get_member(rec["team_member_id"])
        was_new = existing is None
        was_unchanged = existing is not None and existing.content_hash == rec["content_hash"]
        await repo.upsert_member(
            OrgTeamMember(
                team_member_id=rec["team_member_id"],
                name=rec["name"],
                role_title=rec["role_title"],
                category=rec["category"],
                biography=rec["biography"],
                audience="public",
                source_url=source_url,
                content_hash=rec["content_hash"],
            )
        )
        seen_ids.append(rec["team_member_id"])
        if was_new:
            created += 1
        elif was_unchanged:
            unchanged += 1
        else:
            updated += 1
    marked_inactive = await repo.mark_inactive_except(seen_ids)
    return created, updated, unchanged, marked_inactive


async def load_events(session: AsyncSession) -> tuple[int, int, int]:
    repo = OrgEventRepository(session)
    created = updated = unchanged = 0
    data = _load_structured("events")
    source_url = data["source_url"]
    for rec in data["records"]:
        existing = await repo.get_event(rec["event_external_id"])
        was_new = existing is None
        was_unchanged = existing is not None and existing.content_hash == rec["content_hash"]
        tz = ZoneInfo(rec["timezone"])
        await repo.upsert_event(
            OrgEvent(
                event_external_id=rec["event_external_id"],
                title=rec["title"],
                description=rec["description"],
                starts_at=datetime.strptime(rec["starts_at"], "%Y-%m-%d %H:%M:%S").replace(
                    tzinfo=tz
                ),
                ends_at=datetime.strptime(rec["ends_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz),
                timezone=rec["timezone"],
                location=rec["location"],
                audience="public",
                registration_url=rec["registration_url"],
                recurrence_rule=rec["recurrence_rule"],
                status="scheduled",
                source_url=source_url,
                content_hash=rec["content_hash"],
            )
        )
        if was_new:
            created += 1
        elif was_unchanged:
            unchanged += 1
        else:
            updated += 1
    return created, updated, unchanged


async def run_org_load(session: AsyncSession) -> OrgLoadSummary:
    summary = OrgLoadSummary()
    (
        summary.branches_created,
        summary.branches_updated,
        summary.branches_unchanged,
        summary.branches_marked_inactive,
    ) = await load_branches(session)
    (
        summary.members_created,
        summary.members_updated,
        summary.members_unchanged,
        summary.members_marked_inactive,
    ) = await load_team_members(session)
    (
        summary.events_created,
        summary.events_updated,
        summary.events_unchanged,
    ) = await load_events(session)
    return summary
