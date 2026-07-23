"""S17 (plan §2.3/§8): natural-key upsert + inactive-marking for the real org content
scraped by `packages/webcontent`, mirroring `YoutubeRepository`'s S15 pattern - a
re-sync of unchanged content is a no-op, a changed page updates the row in place, and a
record that disappears from the source page is marked "inactive", never deleted.
"""

from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.org import OrgBranch, OrgEvent, OrgTeamMember


class OrgBranchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_branch(self, branch_external_id: str) -> OrgBranch | None:
        return await self._session.get(OrgBranch, branch_external_id)

    async def upsert_branch(self, branch: OrgBranch) -> OrgBranch:
        existing = await self.get_branch(branch.branch_external_id)
        if existing is None:
            self._session.add(branch)
            await self._session.flush()
            return branch

        if existing.content_hash != branch.content_hash:
            existing.name = branch.name
            existing.address = branch.address
            existing.phone = branch.phone
            existing.email = branch.email
            existing.hours = branch.hours
            existing.latitude = branch.latitude
            existing.longitude = branch.longitude
            existing.source_url = branch.source_url
            existing.content_hash = branch.content_hash
        existing.status = "active"
        await self._session.flush()
        return existing

    async def mark_inactive_except(self, seen_branch_ids: list[str]) -> int:
        stmt = update(OrgBranch).where(OrgBranch.status != "inactive")
        if seen_branch_ids:
            stmt = stmt.where(OrgBranch.branch_external_id.notin_(seen_branch_ids))
        stmt = stmt.values(status="inactive")
        result = cast(CursorResult, await self._session.execute(stmt))
        await self._session.flush()
        return result.rowcount or 0

    async def list_branches(self, *, status: str = "active") -> list[OrgBranch]:
        stmt = select(OrgBranch).where(OrgBranch.status == status).order_by(OrgBranch.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class OrgTeamMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_member(self, team_member_id: str) -> OrgTeamMember | None:
        return await self._session.get(OrgTeamMember, team_member_id)

    async def upsert_member(self, member: OrgTeamMember) -> OrgTeamMember:
        existing = await self.get_member(member.team_member_id)
        if existing is None:
            self._session.add(member)
            await self._session.flush()
            return member

        if existing.content_hash != member.content_hash:
            existing.name = member.name
            existing.role_title = member.role_title
            existing.category = member.category
            existing.biography = member.biography
            existing.branch_external_id = member.branch_external_id
            existing.audience = member.audience
            existing.source_url = member.source_url
            existing.content_hash = member.content_hash
        existing.status = "active"
        await self._session.flush()
        return existing

    async def mark_inactive_except(self, seen_member_ids: list[str]) -> int:
        stmt = update(OrgTeamMember).where(OrgTeamMember.status != "inactive")
        if seen_member_ids:
            stmt = stmt.where(OrgTeamMember.team_member_id.notin_(seen_member_ids))
        stmt = stmt.values(status="inactive")
        result = cast(CursorResult, await self._session.execute(stmt))
        await self._session.flush()
        return result.rowcount or 0

    async def list_members(self, *, status: str = "active") -> list[OrgTeamMember]:
        stmt = select(OrgTeamMember).where(OrgTeamMember.status == status)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


class OrgEventRepository:
    """No `mark_inactive_except` - see `OrgEvent`'s own docstring for why events don't
    need the branches/team-members "disappeared from source" bookkeeping.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_event(self, event_external_id: str) -> OrgEvent | None:
        return await self._session.get(OrgEvent, event_external_id)

    async def upsert_event(self, event: OrgEvent) -> OrgEvent:
        """Deliberately never overwrites `status` on an update (unlike every other
        field) - a re-sync that only fixes a typo/time shouldn't silently clear a
        `"canceled"`/`"changed"` designation a human previously set (the source scrape
        has no signal for those states today, so they can only ever be set by a human
        reviewer editing the row directly).
        """
        existing = await self.get_event(event.event_external_id)
        if existing is None:
            self._session.add(event)
            await self._session.flush()
            return event

        if existing.content_hash != event.content_hash:
            existing.title = event.title
            existing.description = event.description
            existing.starts_at = event.starts_at
            existing.ends_at = event.ends_at
            existing.timezone = event.timezone
            existing.location = event.location
            existing.registration_url = event.registration_url
            existing.recurrence_rule = event.recurrence_rule
            existing.source_url = event.source_url
            existing.content_hash = event.content_hash
        return existing

    async def list_events(self, *, audiences: list[str]) -> list[OrgEvent]:
        """Every event this repository knows about, restricted to the caller's
        resolved audiences - the classification of upcoming/completed/canceled/changed
        happens deterministically in `chat_api.services.calendar_events`, not here.
        """
        stmt = (
            select(OrgEvent)
            .where(OrgEvent.audience.in_(audiences))
            .order_by(OrgEvent.starts_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
