from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.mastery import LearningGain, Mastery


class MasteryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_mastery(self, mastery: Mastery) -> Mastery:
        """Updates the existing (student, skill) row in place if one exists, otherwise
        inserts. Without this, repeated recomputation (pre-exam, then once per study
        attempt) would accumulate a new row every time instead of tracking current state.
        """
        existing = await self.get_mastery(mastery.student_external_id, mastery.skill_id)
        if existing is None:
            self._session.add(mastery)
            await self._session.flush()
            return mastery

        existing.raw_accuracy = mastery.raw_accuracy
        existing.weighted_score = mastery.weighted_score
        existing.accuracy_by_difficulty = mastery.accuracy_by_difficulty
        existing.highest_consistent_difficulty = mastery.highest_consistent_difficulty
        existing.estimated_theta = mastery.estimated_theta
        existing.theta_confidence_interval = mastery.theta_confidence_interval
        existing.mastery_probability = mastery.mastery_probability
        existing.recommended_difficulty = mastery.recommended_difficulty
        # `mastery.model_version` is only column-defaulted at INSERT time (SQLAlchemy
        # resolves mapped_column `default=` on flush of the object it was set on), so an
        # un-flushed transient `mastery` still reads None here unless the caller set it
        # explicitly - keep the existing row's value in that case rather than nulling it.
        if mastery.model_version is not None:
            existing.model_version = mastery.model_version
        await self._session.flush()
        return existing

    async def record_learning_gain(self, gain: LearningGain) -> LearningGain:
        self._session.add(gain)
        await self._session.flush()
        return gain

    async def get_mastery(self, student_id: str, skill_id: str) -> Mastery | None:
        stmt = select(Mastery).where(
            Mastery.student_external_id == student_id, Mastery.skill_id == skill_id
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def list_for_student(self, student_id: str) -> list[Mastery]:
        stmt = select(Mastery).where(Mastery.student_external_id == student_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_learning_gains_for_student(self, student_id: str) -> list[LearningGain]:
        """SPEC §5.14.3 parent dashboard - one row per completed pre->study->post cycle,
        newest first.
        """
        stmt = (
            select(LearningGain)
            .where(LearningGain.student_external_id == student_id)
            .order_by(LearningGain.computed_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_weak_skills(self, student_id: str, week_id: str) -> list[Mastery]:
        """SPEC §5.26.1 predefined method. `week_id` is accepted for signature parity with
        the spec; weekly mastery snapshots don't exist until S10, so this reads current
        mastery ordered weakest-first by weighted_score.
        """
        del week_id
        stmt = (
            select(Mastery)
            .where(Mastery.student_external_id == student_id)
            .order_by(Mastery.weighted_score.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
