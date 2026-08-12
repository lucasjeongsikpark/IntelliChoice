import re
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)

_ACTIVATABLE_VALIDATION_STATUS = "pending"

# D-210: what the serving path is allowed to hand a student.
#
# The user's decision, and the reason for it: a "shape" template renders a bare equation
# ("Solve for x: -4x + 3 = -33"), while an authored template is a real-world word problem
# with a scenario, a hint ladder and a verified worked solution. Serving both meant a
# student met two visibly different kinds of question inside one exam, and the bare form
# is the weaker one pedagogically - it tests the arithmetic without ever asking them to
# build the equation from a situation.
#
# A hard filter, applied in **one** place, deliberately. The four read methods below all
# feed question selection, and a filter applied to three of them is a bug that only shows
# up on whichever path was missed.
#
# The cost, stated because it is real: a topic whose bank has no authored items becomes
# unservable. That is the intended outcome rather than a side effect - D-187 already makes
# topic availability a question the bank answers, so those topics correctly stop being
# offered instead of silently serving weaker content. Today `linear_equations` is the only
# generation-capable topic and its authored tiers are {1:13, 2:9, 3:12, 4:7, 5:7}.
#
# Reversing this is deleting one clause from `_servable()`.
SERVABLE_AUTHORING_MODE = "authored"


def _servable() -> tuple:
    """The filter every serving-path read shares: active, approved, and authored."""
    return (
        QuestionTemplate.active_status == "active",
        QuestionTemplate.validation_status == "approved",
        QuestionTemplate.authoring_mode == SERVABLE_AUTHORING_MODE,
    )


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

    async def create_variants(self, variants: Sequence[QuestionVariant]) -> list[QuestionVariant]:
        """One flush for the whole batch - SQLAlchemy emits a single `executemany` INSERT
        rather than one round-trip per row (AUD-F-31). Callers that need the generated
        primary keys can read them after this returns; the flush assigns them.
        """
        self._session.add_all(variants)
        await self._session.flush()
        return list(variants)

    async def get_template(self, question_template_id: str) -> QuestionTemplate | None:
        return await self._session.get(QuestionTemplate, question_template_id)

    async def get_variant(self, question_variant_id: str) -> QuestionVariant | None:
        return await self._session.get(QuestionVariant, question_variant_id)

    async def get_templates(
        self, question_template_ids: Sequence[str]
    ) -> dict[str, QuestionTemplate]:
        """The batch form of `get_template`, keyed by id (AUD-F-31)."""
        if not question_template_ids:
            return {}
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.question_template_id.in_(list(question_template_ids))
        )
        result = await self._session.execute(stmt)
        return {t.question_template_id: t for t in result.scalars().all()}

    async def get_variants(
        self, question_variant_ids: Sequence[str]
    ) -> dict[str, QuestionVariant]:
        """The batch form of `get_variant`, keyed by id (AUD-F-31).

        `get_variant` is `Session.get`, which *can* answer from the identity map - but the
        Session holds only weak references to persistent objects, so a caller that reads
        variants back after the function that created them has returned finds the map
        already collected and pays a round-trip per variant anyway. That was 10 of the 47
        statements in the `select_topic` path.
        """
        if not question_variant_ids:
            return {}
        stmt = select(QuestionVariant).where(
            QuestionVariant.question_variant_id.in_(list(question_variant_ids))
        )
        result = await self._session.execute(stmt)
        return {variant.question_variant_id: variant for variant in result.scalars().all()}

    async def get_active_questions(self, topic_id: str, difficulty: int) -> list[QuestionTemplate]:
        """SPEC §5.26.1 predefined method. Runtime question selection reads only active,
        approved templates for a topic/difficulty pair - never ad-hoc SQL from a request.

        Ordered by primary key so the list a seeded RNG samples from is stable. Without
        an `ORDER BY`, "the same seed builds the same exam" (CLAUDE.md non-negotiable #2)
        rested on Postgres returning rows in whatever order it liked.
        """
        stmt = (
            select(QuestionTemplate)
            .where(
                QuestionTemplate.topic_id == topic_id,
                QuestionTemplate.difficulty_label == difficulty,
                *_servable(),
            )
            .order_by(QuestionTemplate.question_template_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_questions_by_difficulty(
        self, topic_id: str, difficulties: Sequence[int]
    ) -> dict[int, list[QuestionTemplate]]:
        """The batch form of `get_active_questions` (AUD-F-31): one query for every
        difficulty an exam needs, grouped in Python.

        Same filters and the same `ORDER BY` as the single-difficulty method, so the list
        handed to `rng.sample()` per difficulty is byte-for-byte the one the unbatched
        path produced. That equality is the point - the row order decides *which*
        templates a seed picks, so a batched read with a different order would silently
        change exam content.
        """
        grouped: dict[int, list[QuestionTemplate]] = {d: [] for d in difficulties}
        if not difficulties:
            return grouped
        stmt = (
            select(QuestionTemplate)
            .where(
                QuestionTemplate.topic_id == topic_id,
                QuestionTemplate.difficulty_label.in_(list(difficulties)),
                *_servable(),
            )
            .order_by(QuestionTemplate.difficulty_label, QuestionTemplate.question_template_id)
        )
        result = await self._session.execute(stmt)
        for template in result.scalars().all():
            grouped[template.difficulty_label].append(template)
        return grouped

    async def count_active_questions_by_topic(self) -> dict[str, dict[int, int]]:
        """`{topic_id: {difficulty_label: count}}` over active+approved templates, in one
        query for the whole bank (D-187).

        Exists so "can this topic be offered?" can be answered without reading the
        templates themselves: the topic list is rendered before any exam is built, and
        pulling every row of every topic to take five lengths would be a table scan's worth
        of ORM objects for five integers.

        Same `active`/`approved` filter as `get_active_questions` above, deliberately - a
        count that used a looser filter would advertise a topic the exam builder then
        refuses to build (the failure D-187 exists to prevent). Difficulties absent from a
        topic are absent from its inner dict, so callers must read them with a default
        rather than assume every tier is present.
        """
        stmt = (
            select(
                QuestionTemplate.topic_id,
                QuestionTemplate.difficulty_label,
                func.count(QuestionTemplate.question_template_id),
            )
            .where(
                *_servable(),
            )
            .group_by(QuestionTemplate.topic_id, QuestionTemplate.difficulty_label)
        )
        result = await self._session.execute(stmt)
        counts: dict[str, dict[int, int]] = {}
        for topic_id, difficulty_label, count in result.all():
            counts.setdefault(topic_id, {})[difficulty_label] = count
        return counts

    async def get_active_questions_for_skill(self, skill_id: str) -> list[QuestionTemplate]:
        """Same active/approved filter as `get_active_questions`, scoped by skill instead
        of topic+difficulty - used by the §5.11.2 study-plan selector.
        """
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.skill_id == skill_id,
            *_servable(),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_authored_templates(self) -> list[QuestionTemplate]:
        """Every authored template in the bank, whatever its status (D-210).

        Used by the loader to retire ones the bank file no longer lists. Deliberately
        unfiltered: a retired row must still be *found* here, or a re-added template could
        never be reactivated and a second retirement pass would keep counting it.
        """
        stmt = select(QuestionTemplate).where(
            QuestionTemplate.authoring_mode == SERVABLE_AUTHORING_MODE
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def rendered_question_exists(self, rendered_question: str) -> bool:
        """SPEC §5.8.3 "Deduplication" step - checked against every *canonical* variant
        ever persisted (not just the current pipeline run's in-memory set), so a re-run of
        the generation pipeline can't reintroduce a question a previous run already
        produced.

        S40 (D-106) scoped this to `VARIANT_ORIGIN_CANONICAL`. It previously compared
        against every row in the table, which silently included the runtime instances the
        exam and study builders mint per serving - re-renderings of already-approved
        templates at fresh seeds, one row per question shown to any student, ever. That
        made a *content* question ("is this a new question?") depend on a *usage* fact
        ("how much has the app been run?"), and the dedup population grew without bound:
        60,906 rows against 50 templates when this was fixed, 93.5% of them referenced by
        nothing at all.

        The failure it produced was not a missed duplicate but a false positive, and it
        recurred four times. `test_solver_disagreement_rejects_without_persisting` picks a
        deliberate seed so its candidate reaches the solver-agreement check; each time
        traffic happened to mint a runtime variant rendering that same text, the candidate
        was rejected for "duplicate rendered_question" first and the test failed. S17, S22
        and S31 each fixed it by deleting the one offending row, which is why it came
        back. Scoped this way the population is bounded by the template count and cannot
        grow with use.
        """
        stmt = select(QuestionVariant.question_variant_id).where(
            QuestionVariant.rendered_question == rendered_question,
            QuestionVariant.origin == VARIANT_ORIGIN_CANONICAL,
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def stem_skeleton_exists_in_another_topic(
        self, *, topic_id: str, rendered_question: str
    ) -> str | None:
        """The same sentence with different numbers, already used by a **different** topic
        (D-286). Returns the offending template id, or None.

        **The gap this closes, measured.** `rendered_question_exists` above is global but
        needs an *exact* match, and the near-duplicate embedding check is scoped to one
        `topic_id`. Between them sits the case that actually occurred three times:

            g1_addition        "Liam has 9 stickers in his album. His friend gives him 6 more..."
            g2_word_problems   "Liam has 9 stickers in his album. His friend gives him 6 more..."

        Different numbers, so not an exact match; different topics, so the embedding check
        never compared them. A student meeting Liam and his stickers in two grades notices.

        **Why different topics only, and not everywhere.** Within one topic a repeated
        skeleton is usually *correct*: `place_value_compare` asks "Which of these numbers is
        the largest?" twelve times and there is no other way to phrase it - the question
        lives in the options. Applying this globally would reject eleven of those twelve.
        Across topics there is no such case: a topic is the unit of curriculum content, and
        two topics sharing a story verbatim is duplication whatever the grades involved.

        **Why not widen the embedding check instead.** Grade-1 and grade-2 addition problems
        are *supposed* to resemble each other - that is the curriculum spiral - so a global
        cosine threshold would reject correct content by design. Normalising the digits is
        the narrower instrument: it fires only on the same sentence, never on the same idea.
        """
        skeleton = func.regexp_replace(
            func.lower(QuestionVariant.rendered_question), r"[0-9]+(\.[0-9]+)?", "#", "g"
        )
        target = re.sub(r"[0-9]+(\.[0-9]+)?", "#", rendered_question.lower())
        stmt = (
            select(QuestionTemplate.question_template_id)
            .join(
                QuestionVariant,
                QuestionVariant.question_template_id == QuestionTemplate.question_template_id,
            )
            .where(
                QuestionVariant.origin == VARIANT_ORIGIN_CANONICAL,
                QuestionTemplate.topic_id != topic_id,
                skeleton == target,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()

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

    async def list_rejected_validation_runs(
        self, *, limit: int = 20
    ) -> list[QuestionValidationRun]:
        """Rejected runs, newest first - the read side of D-195's rejection evidence.

        No filter argument: a rejected run has `question_template_id=None` by construction
        (see the model's docstring), and the topic/skill/planned-id it *does* carry live
        inside the `stage_results` JSON, where filtering would need a JSON-path predicate
        with different syntax on SQLite and Postgres. Callers filter in Python instead -
        a review batch is a handful of candidates, not a table scan worth optimising.
        """
        stmt = (
            select(QuestionValidationRun)
            .where(QuestionValidationRun.outcome == "rejected")
            .order_by(QuestionValidationRun.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_variant_for_template(
        self, question_template_id: str
    ) -> QuestionVariant | None:
        """The authored template's one *canonical* variant (plan §7) - the lookup
        `review_cli.py` uses to render it for review, without relying on lazy-loading
        `QuestionTemplate.variants` across an async session.

        The `origin` filter is load-bearing as of D-189. This used to take any row with
        `limit(1)`, which was correct only while authored templates were never served:
        serving one mints a `VARIANT_ORIGIN_RUNTIME` row per student per showing, and an
        unfiltered `limit(1)` would then start returning an arbitrary *serving* instead of
        the reviewed content - silently, and more often the more the item is used.
        """
        stmt = (
            select(QuestionVariant)
            .where(QuestionVariant.question_template_id == question_template_id)
            .where(QuestionVariant.origin == VARIANT_ORIGIN_CANONICAL)
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_canonical_variants(
        self, question_template_ids: Sequence[str]
    ) -> dict[str, QuestionVariant]:
        """The batch form of `get_variant_for_template`, keyed by *template* id.

        Exists for the serving path (D-189): a statically-rendered template carries its
        content on its canonical variant rather than in a shape function, so building an
        exam that contains one has to read it. Batched for the same reason as
        `get_templates`/`get_variants` (AUD-F-31) - the per-item form would reintroduce
        the N+1 that the `select_topic` path was measured and fixed for.
        """
        if not question_template_ids:
            return {}
        stmt = (
            select(QuestionVariant)
            .where(QuestionVariant.question_template_id.in_(list(question_template_ids)))
            .where(QuestionVariant.origin == VARIANT_ORIGIN_CANONICAL)
        )
        result = await self._session.execute(stmt)
        return {v.question_template_id: v for v in result.scalars().all()}

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
