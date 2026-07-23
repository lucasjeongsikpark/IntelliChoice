from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.interrupts import InterruptApproval


class InterruptApprovalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, approval: InterruptApproval) -> InterruptApproval:
        self._session.add(approval)
        await self._session.flush()
        return approval
