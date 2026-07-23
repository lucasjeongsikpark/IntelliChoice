from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.curriculum import Skill, Topic


class CurriculumRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_topic(self, topic: Topic) -> Topic:
        self._session.add(topic)
        await self._session.flush()
        return topic

    async def create_skill(self, skill: Skill) -> Skill:
        self._session.add(skill)
        await self._session.flush()
        return skill

    async def get_topic(self, topic_id: str) -> Topic | None:
        return await self._session.get(Topic, topic_id)

    async def get_skill(self, skill_id: str) -> Skill | None:
        return await self._session.get(Skill, skill_id)
