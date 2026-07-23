from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.stage_transition import StageTransition


class StageTransitionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, transition: StageTransition) -> StageTransition:
        self._session.add(transition)
        await self._session.flush()
        return transition

    async def get_for_session_stage(
        self, learning_session_id: str, stage: str, *, related_skill_id: str | None = None
    ) -> StageTransition | None:
        """Idempotency check `services.stage_narrative` runs before ever calling
        Bedrock: a row already existing for this (session, stage[, skill]) means the
        narrative was already generated - the caller returns the stored text instead of
        firing a second call (bounds `pre_intro`'s own out-of-graph spend to exactly one
        call per session, and keeps a `study_step` skill transition from re-firing if a
        client reconnects mid-transition).
        """
        stmt = select(StageTransition).where(
            StageTransition.learning_session_id == learning_session_id,
            StageTransition.stage == stage,
            StageTransition.related_skill_id == related_skill_id,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_session(self, learning_session_id: str) -> list[StageTransition]:
        stmt = (
            select(StageTransition)
            .where(StageTransition.learning_session_id == learning_session_id)
            .order_by(StageTransition.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
