from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.hints import HintEvent


class HintEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: HintEvent) -> HintEvent:
        self._session.add(event)
        await self._session.flush()
        return event

    async def get_events_for_attempt(self, study_attempt_id: str) -> list[HintEvent]:
        """Ordered by level - the within-question ladder's history so far, used to
        build `HintPersonalizationPayload.previous_hint_summaries` for the next level.
        """
        stmt = (
            select(HintEvent)
            .where(HintEvent.study_attempt_id == study_attempt_id)
            .order_by(HintEvent.hint_level)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
