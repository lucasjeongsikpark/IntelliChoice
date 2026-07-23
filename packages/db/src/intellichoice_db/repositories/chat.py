"""SPEC §18-C3: `chat_suggestions` is small, hand-authored reference data (unlike
`OrgBranch`/`OrgTeamMember`/`OrgEvent`, it's never scraped) - upsert-by-id, mirroring
those repositories' idempotent-seed shape without the inactive-marking bookkeeping
(there's no "disappeared from the source page" concept for hand-authored prompts).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.chat import ChatSuggestion


class ChatSuggestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, suggestion_id: str) -> ChatSuggestion | None:
        return await self._session.get(ChatSuggestion, suggestion_id)

    async def upsert(self, suggestion: ChatSuggestion) -> ChatSuggestion:
        existing = await self.get(suggestion.id)
        if existing is None:
            self._session.add(suggestion)
            await self._session.flush()
            return suggestion

        existing.role_audience = suggestion.role_audience
        existing.category = suggestion.category
        existing.prompt_text = suggestion.prompt_text
        existing.sort_order = suggestion.sort_order
        existing.active = suggestion.active
        await self._session.flush()
        return existing

    async def list_active(self) -> list[ChatSuggestion]:
        stmt = (
            select(ChatSuggestion)
            .where(ChatSuggestion.active.is_(True))
            .order_by(ChatSuggestion.sort_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
