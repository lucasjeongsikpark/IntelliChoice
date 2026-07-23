from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.questions import (
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)

_ACTIVATABLE_VALIDATION_STATUS = "pending"


class QuestionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_template(self, template: QuestionTemplate) -> QuestionTemplate:
        self._session.add(template)
        await self._session.flush()
        return template

    async def create_variant(self, variant: QuestionVariant) -> QuestionVariant:
        self._session.add(variant)
        await self._session.flush()
        return variant

    async def get_template(self, question_template_id: str) -> QuestionTemplate | None:
        return await self._session.get(QuestionTemplate, question_template_id)

    async def get_variant(self, question_variant_id: str) -> QuestionVariant | None:
        return await self._session.get(QuestionVariant, question_variant_id)

    async def get_active_questions(self, topic_id: str, difficulty: int) -> list[QuestionTemplate]:
        """SPEC §5.26.1 predefined method. Runtime question selection reads only active,
        approved templates for a topic/difficulty pair - never ad-hoc SQL from a request.
        """
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.topic_id == topic_id,
            QuestionTemplate.difficulty_label == difficulty,
            QuestionTemplate.active_status == "active",
            QuestionTemplate.validation_status == "approved",
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_questions_for_skill(self, skill_id: str) -> list[QuestionTemplate]:
        """Same active/approved filter as `get_active_questions`, scoped by skill instead
        of topic+difficulty - used by the §5.11.2 study-plan selector.
        """
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.skill_id == skill_id,
            QuestionTemplate.active_status == "active",
            QuestionTemplate.validation_status == "approved",
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def rendered_question_exists(self, rendered_question: str) -> bool:
        """SPEC §5.8.3 "Deduplication" step - checked against every variant ever
        persisted (not just the current pipeline run's in-memory set), so a re-run of the
        generation pipeline can't reintroduce a question a previous run already produced.
        """
        stmt = select(QuestionVariant.question_variant_id).where(
            QuestionVariant.rendered_question == rendered_question
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def activate_template(self, question_template_id: str) -> QuestionTemplate:
        """SPEC §5.8.3 "Activate" step. Only promotes a template already sitting at
        `validation_status="pending"` - i.e. one the pipeline already determined passed
        every automated check (SPEC §5.8.5) - to `"approved"`/`active_status="active"`.
        A template the pipeline set to `"rejected"` can never reach this method through
        normal pipeline flow, so this is a status flip, not a re-check (D-026).
        """
        template = await self._session.get(QuestionTemplate, question_template_id)
        if template is None:
            raise ValueError(f"unknown question_template_id {question_template_id!r}")
        if template.validation_status != _ACTIVATABLE_VALIDATION_STATUS:
            raise ValueError(
                f"template {question_template_id!r} has validation_status="
                f"{template.validation_status!r}, not {_ACTIVATABLE_VALIDATION_STATUS!r} "
                "- only a pending template (one that passed every automated check) can "
                "be activated"
            )
        template.validation_status = "approved"
        template.active_status = "active"
        await self._session.flush()
        return template

    async def set_active_status(self, question_template_id: str, active_status: str) -> None:
        """Flips `active_status` only - e.g. SPEC §5.8.7's report-triggered quarantine.
        Never touches `validation_status`, which is the pipeline's own lifecycle.
        """
        template = await self._session.get(QuestionTemplate, question_template_id)
        if template is None:
            raise ValueError(f"unknown question_template_id {question_template_id!r}")
        template.active_status = active_status
        await self._session.flush()

    async def reject_template(self, question_template_id: str) -> QuestionTemplate:
        """S20 human-review "reject" action (plan §7 step 5) - same guard as
        `activate_template`: only a `pending` template (one the pipeline already passed)
        can be explicitly rejected by a reviewer.
        """
        template = await self._session.get(QuestionTemplate, question_template_id)
        if template is None:
            raise ValueError(f"unknown question_template_id {question_template_id!r}")
        if template.validation_status != _ACTIVATABLE_VALIDATION_STATUS:
            raise ValueError(
                f"template {question_template_id!r} has validation_status="
                f"{template.validation_status!r}, not {_ACTIVATABLE_VALIDATION_STATUS!r}"
            )
        template.validation_status = "rejected"
        await self._session.flush()
        return template

    async def supersede_template(self, question_template_id: str) -> QuestionTemplate:
        """S20 human-review "edit-and-rerun" action (plan §7 "Versioning/audit"): marks
        a `pending` template `superseded` - the prior row is kept, never deleted, for
        audit history - and returns it so the caller can read its `version` (the rerun's
        new template gets `version + 1`, set by the caller when it invokes
        `generate_authored_candidate` again).
        """
        template = await self._session.get(QuestionTemplate, question_template_id)
        if template is None:
            raise ValueError(f"unknown question_template_id {question_template_id!r}")
        if template.validation_status != _ACTIVATABLE_VALIDATION_STATUS:
            raise ValueError(
                f"template {question_template_id!r} has validation_status="
                f"{template.validation_status!r}, not {_ACTIVATABLE_VALIDATION_STATUS!r}"
            )
        template.validation_status = "superseded"
        await self._session.flush()
        return template

    async def create_validation_run(self, run: QuestionValidationRun) -> QuestionValidationRun:
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_latest_validation_run(
        self, question_template_id: str
    ) -> QuestionValidationRun | None:
        stmt = (
            select(QuestionValidationRun)
            .where(QuestionValidationRun.question_template_id == question_template_id)
            .order_by(QuestionValidationRun.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_variant_for_template(
        self, question_template_id: str
    ) -> QuestionVariant | None:
        """Authored templates always get exactly one static variant (plan §7) - this is
        the lookup `review_cli.py` uses to render it, without relying on lazy-loading
        `QuestionTemplate.variants` across an async session.
        """
        stmt = (
            select(QuestionVariant)
            .where(QuestionVariant.question_template_id == question_template_id)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_pending_authored_by_priority(
        self, topic_id: str | None = None
    ) -> list[QuestionTemplate]:
        """S20 `review_cli.py`: pending authored templates, `review_priority="high"`
        surfaced first (plan §7 step 5's "lists pending sorted by review_priority"),
        newest first within each tier.
        """
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.validation_status == "pending",
            QuestionTemplate.authoring_mode == "authored",
        )
        if topic_id is not None:
            stmt = stmt.where(QuestionTemplate.topic_id == topic_id)
        stmt = stmt.order_by(
            (QuestionTemplate.review_priority == "high").desc(),
            QuestionTemplate.created_at.desc(),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def stem_near_duplicate_exists(
        self, topic_id: str, embedding: list[float], *, threshold: float
    ) -> bool:
        """SPEC §5.8.5 "no duplicate question" for authored items - unlike the shape
        pipeline's exact-text `rendered_question_exists` check, this compares meaning:
        cosine *distance* (0 = identical, 2 = opposite) between the candidate's stem
        embedding and every other authored template's stem in the same topic. Mirrors
        `RagRepository.semantic_search_chunk_ids`'s pgvector query shape.
        """
        stmt = (
            select(QuestionTemplate.question_template_id)
            .where(
                QuestionTemplate.topic_id == topic_id,
                QuestionTemplate.authoring_mode == "authored",
                QuestionTemplate.stem_embedding.is_not(None),
                QuestionTemplate.stem_embedding.cosine_distance(embedding) < threshold,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None
