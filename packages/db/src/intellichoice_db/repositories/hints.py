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

    async def set_personalized(
        self, hint_event_id: str, *, personalized_hint_text: str, was_personalized: bool
    ) -> HintEvent | None:
        """D-272: fill in the personalized text on a row that was written canonically.

        The two-stage hint serves the authored rung immediately and personalizes in the
        background, so the audit row exists from the first moment (D-026's "every attempt
        gets a row") and is completed a beat later. `None` if the row is gone, which the
        caller treats as "nothing to update" - a background task must not raise.
        """
        event = await self._session.get(HintEvent, hint_event_id)
        if event is None:
            return None
        event.personalized_hint_text = personalized_hint_text
        event.was_personalized = was_personalized
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
