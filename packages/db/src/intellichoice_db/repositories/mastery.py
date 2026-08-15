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
        """One row per (pre, post) cycle - returning the existing row if the cycle already has one.

        **D-336: this used to be a bare `add`, and a cycle finalized twice produced two rows.**
        Measured on staging: `pre=f422de5d…` has two rows with the *same* post session and
        byte-identical numbers (`raw_gain=-1.0`, `normalized_gain=-0.125`), written **46 seconds
        apart**. `POST /exam/finalize` carries no `Idempotency-Key` - only `/answers` does - so a
        retry, a double submit or a reconnect recomputes the cycle and inserts again.

        **The harm is parent-visible, and was verified against the deployed API rather than
        inferred.** `services/history.py` builds one completed-session summary *per gain row*, so
        `GET /learning/students/{id}/sessions` returned **10 entries for 9 real cycles** - a parent
        seeing their child's `linear_equations` session listed twice, with identical scores.

        Returning the existing row rather than raising: a second finalize of an already-finalized
        cycle is a *retry*, not an error, and the caller wants the cycle's gain either way. The
        recomputed values are discarded rather than written over the stored ones - they are
        computed from the same attempts, so they agree, and preferring the first keeps
        `computed_at` meaning "when this cycle was finalized".

        **Not a race-proof guarantee.** Two truly concurrent finalizes could both miss the check
        and insert. Closing that needs a unique constraint on
        `(pre_assessment_session_id, post_assessment_session_id)`, which cannot be added while the
        existing duplicate row is in the table - a deletion, and therefore the user's call. The
        observed failure was 46 seconds apart, which this covers.
        """
        existing = await self.get_learning_gain_for_cycle(
            gain.pre_assessment_session_id, gain.post_assessment_session_id
        )
        if existing is not None:
            return existing
        self._session.add(gain)
        await self._session.flush()
        return gain

    async def get_learning_gain_for_cycle(
        self, pre_assessment_session_id: str, post_assessment_session_id: str
    ) -> LearningGain | None:
        """The pair is the cycle's identity: one pre form, one post form built against it."""
        stmt = select(LearningGain).where(
            LearningGain.pre_assessment_session_id == pre_assessment_session_id,
            LearningGain.post_assessment_session_id == post_assessment_session_id,
        )
        return (await self._session.execute(stmt)).scalars().first()

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
