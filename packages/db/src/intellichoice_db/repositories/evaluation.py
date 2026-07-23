from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.evaluation import EvaluationResult


class EvaluationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_result(self, result: EvaluationResult) -> EvaluationResult:
        self._session.add(result)
        await self._session.flush()
        return result

    async def list_results(self, suite_name: str) -> list[EvaluationResult]:
        stmt = select(EvaluationResult).where(EvaluationResult.suite_name == suite_name)
        query_result = await self._session.execute(stmt)
        return list(query_result.scalars().all())
