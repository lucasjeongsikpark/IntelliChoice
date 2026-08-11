from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.mastery import StudyAttempt, StudyItem, StudySession


class StudyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_study_session(self, study_session: StudySession) -> StudySession:
        self._session.add(study_session)
        await self._session.flush()
        return study_session

    async def add_item(self, item: StudyItem) -> StudyItem:
        self._session.add(item)
        await self._session.flush()
        return item

    async def record_attempt(self, attempt: StudyAttempt) -> StudyAttempt:
        """Plain insert, for test seeding. The answer path goes through
        `record_attempt_if_first`, which enforces one attempt per (session, variant).
        """
        self._session.add(attempt)
        await self._session.flush()
        return attempt

    async def record_attempt_if_first(self, attempt: StudyAttempt) -> StudyAttempt | None:
        """Insert, or return `None` if this item already has an attempt (D-216 - the study
        counterpart of `AssessmentRepository.record_attempt_if_first`, AUD-L-10). Every
        study serving mints a fresh variant row, so one attempt per (session, variant) is
        the model's own invariant ("the current pending question is the item lacking a
        matching StudyAttempt"); a second answer from a stale tab would re-label a resolved
        skill line and skew the gain's dependency denominators.

        The insert runs inside a SAVEPOINT so losing the race leaves the surrounding
        request transaction usable.
        """
        try:
            async with self._session.begin_nested():
                self._session.add(attempt)
                await self._session.flush()
        except IntegrityError as exc:
            if "uq_study_attempts_session_variant" in str(exc.orig):
                return None
            raise
        return attempt

    async def update_intervention_choice(
        self,
        attempt_id: str,
        *,
        hint_used: bool = False,
        video_used: bool = False,
        solution_used: bool = False,
    ) -> StudyAttempt:
        """Applies the SPEC §5.11.3 hint/solution/video choice to an already-recorded
        attempt, once the graph's `interrupt()` for that choice has resumed. Each flag is
        OR'd into whatever the attempt already has (S21: a within-question hint ladder can
        call this more than once per attempt as the round loops - e.g. hint then solution -
        and a later round must never silently clear an earlier round's flag, or
        `study_outcomes.correct_label`'s support-history precedence would misclassify an
        abandoned-without-solution case). `solution_used` is tracked distinctly (not just
        "neither hint nor video") so a later correct answer can be labeled
        `correct_after_solution` (SPEC §5.11.5).
        """
        attempt = await self._session.get(StudyAttempt, attempt_id)
        assert attempt is not None
        attempt.hint_used = attempt.hint_used or hint_used
        attempt.video_used = attempt.video_used or video_used
        attempt.solution_used = attempt.solution_used or solution_used
        await self._session.flush()
        return attempt

    async def set_outcome(
        self,
        attempt_id: str,
        *,
        outcome_label: str,
        tutor_review_flagged: bool = False,
    ) -> StudyAttempt:
        """Finalizes an attempt's §5.11.7 outcome label (and, for an unresolved skill line,
        its tutor-review flag). Set once the retry ladder knows whether the attempt resolved
        the skill.
        """
        attempt = await self._session.get(StudyAttempt, attempt_id)
        assert attempt is not None
        attempt.outcome_label = outcome_label
        attempt.tutor_review_flagged = tutor_review_flagged
        await self._session.flush()
        return attempt

    async def get_study_session(self, study_session_id: str) -> StudySession | None:
        return await self._session.get(StudySession, study_session_id)

    async def get_attempt(self, attempt_id: str) -> StudyAttempt | None:
        """One attempt by id. D-272: the router needs the attempt named by
        `LearningState.last_study_attempt_id` to say which question the current hint or
        solution is about - that binding is what stops the UI pairing one problem's help
        with a different problem's stem.
        """
        return await self._session.get(StudyAttempt, attempt_id)

    async def get_items(self, study_session_id: str) -> list[StudyItem]:
        stmt = (
            select(StudyItem)
            .where(StudyItem.study_session_id == study_session_id)
            .order_by(StudyItem.display_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_attempts(self, study_session_id: str) -> list[StudyAttempt]:
        stmt = select(StudyAttempt).where(StudyAttempt.study_session_id == study_session_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_attempt_for_variant(
        self, student_external_id: str, question_variant_id: str
    ) -> StudyAttempt | None:
        """S24: `tutor_chat` looks up "what did the student just try" for the question
        it's chatting about by this, not by `LearningState.last_study_attempt_id` -
        unlike `intervention_choice`, `tutor_chat` is a fresh top-level graph entry
        (no `interrupt()`/resume), so it never has that transient state field to read.
        """
        stmt = (
            select(StudyAttempt)
            .where(
                StudyAttempt.student_external_id == student_external_id,
                StudyAttempt.question_variant_id == question_variant_id,
            )
            .order_by(desc(StudyAttempt.responded_at))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()
