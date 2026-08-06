"""S20 authored generation pipeline + review CLI tests (SPEC §5.8.2-5.8.5, plan §7).

Uses a `_ScriptedAuthoredGateway` test double, same reasoning as `test_ai_pipeline.py`'s
own `_ScriptedGateway`: `MockBedrockProvider`'s stub responses are deterministic
placeholders, not a real solver/judge, so exercising rejection paths (solver
disagreement, judge flags, near-duplicate) needs a gateway whose behavior a test can
script per-stage.

Every test runs against the real Compose Postgres via the same rollback-session pattern
as `test_ai_pipeline.py`/`test_loader.py` (D-013). Skips cleanly when Postgres is
unreachable (D-008).
"""

import asyncio
import hashlib
import random
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from intellichoice_curriculum import ai_pipeline, pipeline_cli, review_cli
from intellichoice_curriculum.ai_pipeline import (
    TOPIC_SKILL_DIFFICULTIES,
    PipelineConfigError,
    generate_authored_candidate,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.engine import create_engine
from intellichoice_db.models.questions import QuestionTemplate, QuestionValidationRun
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockGenerationResult,
    BedrockTask,
    EmbeddingResult,
    QuestionJudgePayload,
    QuestionJudgeResponse,
    SolutionResponse,
    SolutionStep,
    SolverPayload,
    SolverResponse,
)
from pydantic import BaseModel, ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

_EMBEDDING_DIM = 1024


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM question_templates LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


def _hash_vector(text_value: str) -> list[float]:
    """Same reasoning as `mock_provider._deterministic_vector`: reproducible, and
    unrelated text produces near-orthogonal vectors in this many dimensions, so distinct
    stems don't accidentally collide as near-duplicates in tests that don't mean to
    exercise that path.
    """
    seed = int.from_bytes(hashlib.sha256(text_value.encode("utf-8")).digest()[:8], "big")
    rng = random.Random(seed)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(_EMBEDDING_DIM)]
    norm = sum(v * v for v in raw) ** 0.5
    return [v / norm for v in raw]


def _good_item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve: what is 2 + 2?",
        option_a="4",
        option_b="5",
        option_c="6",
        option_d="3",
        correct_option="a",
        equation="Eq(x, 2 + 2)",
        hint_ladder=[
            "Think about combining two small groups of objects.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="Add the numbers.", expression="2 + 2")
            ],
            final_answer="4",
        ),
        misconception_tags=["off_by_one"],
        estimated_time_seconds=30,
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


class _ScriptedAuthoredGateway:
    """Per-stage-overridable test gateway for the authored pipeline. Defaults produce a
    valid, passing candidate whose solvers agree with the generator's own declared
    answer (mirrors `_ScriptedGateway`'s "defaults pass" convention).
    """

    def __init__(
        self,
        *,
        item: AuthoredGeneratedItemResponse | None = None,
        item_factory: Callable[[AuthoredGeneratorPayload], AuthoredGeneratedItemResponse]
        | None = None,
        solver_a_option: str | None = None,
        solver_b_option: str | None = None,
        judge: QuestionJudgeResponse | None = None,
        embedding_vector: list[float] | None = None,
    ) -> None:
        self._item = item
        self._item_factory = item_factory
        self._solver_a_option = solver_a_option
        self._solver_b_option = solver_b_option
        self._judge = judge
        self._embedding_vector = embedding_vector
        self._last_item: AuthoredGeneratedItemResponse | None = None
        # response_model name -> the ceiling that stage was called with. Recorded rather
        # than asserted here so one test can state the whole per-stage sizing (see
        # `test_authored_stages_get_ceilings_above_the_measured_response_size`).
        self.ceilings: dict[str, int] = {}

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: object,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        name = response_model.__name__
        self.ceilings[name] = max_output_tokens
        if name == "AuthoredGeneratedItemResponse":
            assert isinstance(payload, AuthoredGeneratorPayload)
            if self._item_factory is not None:
                value: BaseModel = self._item_factory(payload)
            else:
                value = self._item or _good_item()
            self._last_item = value  # type: ignore[assignment]
        elif name == "SolverResponse":
            assert isinstance(payload, SolverPayload)
            assert self._last_item is not None
            # Read the options *as presented*, which is what a real solver does and what
            # the pipeline now requires: options are shuffled after generation (D-191), so
            # the generated item's own `correct_option` letter no longer names the same
            # option the solver is shown. Answering from the pre-shuffle letter made this
            # double disagree with itself.
            generated = {
                "a": self._last_item.option_a,
                "b": self._last_item.option_b,
                "c": self._last_item.option_c,
                "d": self._last_item.option_d,
            }
            correct_text = generated[self._last_item.correct_option]
            presented = {
                "a": payload.option_a,
                "b": payload.option_b,
                "c": payload.option_c,
                "d": payload.option_d,
            }
            as_presented = next(
                (label for label, text in presented.items() if text == correct_text),
                self._last_item.correct_option,
            )
            if task == BedrockTask.QUESTION_GENERATION:
                selected = self._solver_a_option or as_presented
            else:
                selected = self._solver_b_option or as_presented
            value = SolverResponse(selected_option=selected)  # type: ignore[arg-type]
        elif name == "QuestionJudgeResponse":
            assert isinstance(payload, QuestionJudgePayload)
            value = self._judge or QuestionJudgeResponse(
                difficulty_label=payload.proposed_difficulty,
                is_ambiguous=False,
                is_aligned=True,
                is_age_appropriate=True,
                hint_quality_score=5,
            )
        else:
            raise AssertionError(f"unexpected response_model {name}")
        return BedrockGenerationResult(
            value=value,  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
            cost_cents=0.01,
            model_id="test",
            repaired=False,
        )

    async def create_embedding(
        self, *, texts: list[str], session_spend_cents: float
    ) -> EmbeddingResult:
        vectors = [self._embedding_vector or _hash_vector(t) for t in texts]
        return EmbeddingResult(
            vectors=vectors, model_id="test", dimensions=len(vectors[0]), cost_cents=0.001
        )


async def _latest_validation_run(session: AsyncSession) -> QuestionValidationRun:
    result = await session.execute(
        select(QuestionValidationRun).order_by(QuestionValidationRun.created_at.desc()).limit(1)
    )
    run = result.scalars().first()
    assert run is not None
    return run


def test_passing_candidate_lands_pending_then_activates_to_active() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=918273,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            assert outcome.cost_cents > 0
            assert outcome.question_template_id is not None
            assert outcome.question_variant_id is not None

            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            assert template.authoring_mode == "authored"
            # Never auto-approved: passing every check yields "pending", not "approved".
            assert template.validation_status == "pending"
            assert template.stem_embedding is not None

            variant = await repo.get_variant_for_template(outcome.question_template_id)
            assert variant is not None
            assert variant.correct_option == "a"

            # A pending template is NOT yet deliverable.
            active_before = await repo.get_active_questions("linear_equations", difficulty=2)
            active_ids_before = {t.question_template_id for t in active_before}
            assert outcome.question_template_id not in active_ids_before

            # Explicit activation is the only path to "approved" (D-026, unchanged).
            await repo.activate_template(outcome.question_template_id)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            assert template.validation_status == "approved"

            # Appears via the exact, unchanged runtime selection queries.
            active_after = await repo.get_active_questions("linear_equations", difficulty=2)
            assert outcome.question_template_id in {t.question_template_id for t in active_after}
            for_skill = await repo.get_active_questions_for_skill(template.skill_id)
            assert outcome.question_template_id in {t.question_template_id for t in for_skill}

    asyncio.run(run())


def test_authored_stages_get_ceilings_above_the_measured_response_size() -> None:
    """The whole first real-Bedrock authoring run failed on this, silently and completely.

    Every authored call shared `_MAX_TOKENS = 400` with S9's shape mode, whose responses
    are a fraction of the size. Measured against real Bedrock (Haiku 4.5, 2026-08-05), a
    complete `AuthoredGeneratedItemResponse` runs 631 output tokens at tier 1 and 954 at
    tier 5, so the generator hit the ceiling before emitting a usable item on 11 of 11
    candidates - and the gateway correctly refuses to retry under an unchanged ceiling, so
    no amount of re-running would have produced content.

    The assertion is against the *measured* worst case rather than the constant's current
    value: the point is that the ceiling stays above what a real model actually emits, not
    that it equals any particular number. Solver and judge share the item's call path and
    are the stages where a truncation throws away a candidate that has already paid for
    four calls, so they are pinned above shape mode's default too.
    """
    measured_worst_case_output_tokens = 954

    async def run() -> None:
        curriculum = load_curriculum()
        gateway = _ScriptedAuthoredGateway()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=918274,
                session_spend_cents=0.0,
            )
            # A passing candidate is what visits every stage - a rejection would leave
            # later stages unrecorded and quietly weaken this test.
            assert outcome.status == "pending"

        assert gateway.ceilings["AuthoredGeneratedItemResponse"] > measured_worst_case_output_tokens
        assert gateway.ceilings["SolverResponse"] > ai_pipeline._MAX_TOKENS
        assert gateway.ceilings["QuestionJudgeResponse"] > ai_pipeline._MAX_TOKENS

    asyncio.run(run())


def test_authored_seeds_are_distinct_within_a_run_and_across_a_seed_offset() -> None:
    """A duplicate seed is a duplicate template id, and that is a batch-level failure.

    `pipeline_cli.main` commits once after the whole run, so a single primary-key
    collision discards every candidate in it - including the ones that passed and were
    paid for. Two ways to collide: within one run (two skills sharing a tier, D-186's
    multi-tier plan), or across runs (the seed is a pure function of (skill, tier, index),
    so a second run at the same settings re-proposes the first run's ids). The first is
    covered by the skill term; the second is why `--seed-offset` exists.
    """
    plan = TOPIC_SKILL_DIFFICULTIES["linear_equations"]
    candidates_per_pair = 2

    def seeds_for(seed_offset: int) -> list[int]:
        return [
            pipeline_cli.authored_seed(
                skill_index=skill_index,
                difficulty_label=difficulty_label,
                index=i,
                seed_offset=seed_offset,
            )
            for skill_index, (_, difficulty_labels) in enumerate(sorted(plan.items()))
            for difficulty_label in sorted(difficulty_labels)
            for i in range(candidates_per_pair)
        ]

    first_run = seeds_for(pipeline_cli.DEFAULT_SEED_OFFSET)
    assert len(set(first_run)) == len(first_run)

    # The default offset is the collision this flag exists to prevent - a re-run without
    # one must be identical, or the flag would be solving a problem that isn't there.
    assert seeds_for(pipeline_cli.DEFAULT_SEED_OFFSET) == first_run

    # An offset clear of one run's span gives a following run an id range of its own.
    second_run = seeds_for(100_000)
    assert not set(second_run) & set(first_run)


def test_judge_hint_quality_score_is_bounded_to_the_scale_its_thresholds_assume() -> None:
    """An unbounded score is what made the hint-quality gate unreachable in practice.

    `_HINT_QUALITY_REJECT_BELOW` and `_HINT_QUALITY_BORDERLINE_AT` are 2 and 3 on a
    documented 1-5 scale. The first real-Bedrock run (2026-08-05) had the judge score 8-9
    on every candidate against a scale it invented, so neither threshold could fire and
    eight items passed a check that never ran. The bound is asserted against the
    thresholds rather than against the literal numbers, so a future retune of either
    cannot leave the scale and the gate disagreeing again.
    """
    with pytest.raises(ValidationError):
        QuestionJudgeResponse(
            difficulty_label=3,
            is_ambiguous=False,
            is_aligned=True,
            is_age_appropriate=True,
            hint_quality_score=9,
        )

    schema = QuestionJudgeResponse.model_json_schema()["properties"]["hint_quality_score"]
    # The model only complies if it is told, and the tool schema is how it is told - the
    # gateway sends `model_json_schema()` as the tool's inputSchema.
    assert schema["minimum"] <= ai_pipeline._HINT_QUALITY_REJECT_BELOW
    assert schema["maximum"] > ai_pipeline._HINT_QUALITY_BORDERLINE_AT


def test_approving_an_authored_template_now_succeeds_but_still_needs_something_to_serve() -> None:
    """D-188 refused every authored approval; D-189 built serving, so the bar moved.

    The original refusal was measured, not theoretical: approving five authored templates
    failed 34 tests with `VariantGenerationError: unknown shape 'authored'`, because every
    served question went through `generate_variant(shape_key=template.solution_function)`.
    Serving now reads the canonical variant instead, so a normally-produced authored
    template is approvable - and the guard narrows to the case that is still unservable,
    a template with neither a shape nor a canonical variant to fall back on.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=918275,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            assert outcome.question_template_id is not None

            await review_cli.approve(session, outcome.question_template_id)
            approved = await repo.get_template(outcome.question_template_id)
            assert approved is not None
            assert approved.validation_status == "approved"

            # Same content, no canonical variant behind it - nothing to render and
            # nothing to serve, so the guard still fires and fires before the flip.
            orphan = await repo.create_template(
                QuestionTemplate(
                    question_template_id="authored-orphan-no-variant",
                    curriculum_version=approved.curriculum_version,
                    topic_id=approved.topic_id,
                    skill_id=approved.skill_id,
                    grade_band=approved.grade_band,
                    difficulty_label=approved.difficulty_label,
                    question_type="multiple_choice",
                    parameter_schema={},
                    solution_function="authored",
                    correct_option_generator="authored",
                    distractor_generators=[],
                    common_error_tags=[],
                    estimated_time_seconds=30,
                    generator_model="test",
                    review_model_versions={},
                    stem="Solve: an authored template with no variant behind it.",
                    hint_ladder=["a", "b", "c"],
                    canonical_solution={"steps": [], "final_answer": "4"},
                    authoring_mode="authored",
                    validation_status="pending",
                    active_status="active",
                )
            )
            with pytest.raises(review_cli.UnservableTemplateError):
                await review_cli.approve(session, orphan.question_template_id)
            still_pending = await repo.get_template(orphan.question_template_id)
            assert still_pending is not None
            assert still_pending.validation_status == "pending"

    asyncio.run(run())


def test_option_shuffling_moves_the_correct_answer_without_changing_it() -> None:
    """Six of six correct answers landed on option `b` in the first scenario run.

    "Always answer b" would have scored 100%. Nothing caught it, and nothing could: the
    bias is a property of the *set*, so no check that looks at one item can see it, and
    the two solvers and the judge each look at one item. Fixed deterministically because
    "vary the correct position" is an instruction a model follows unreliably.
    """
    item = _good_item()
    correct_text = {"a": item.option_a, "b": item.option_b, "c": item.option_c}[
        item.correct_option
    ]

    # The same seed rebuilds the same item - the whole pipeline is seed-reproducible.
    assert ai_pipeline.shuffle_options(item, seed=7) == ai_pipeline.shuffle_options(item, seed=7)

    positions = set()
    for seed in range(40):
        shuffled = ai_pipeline.shuffle_options(item, seed=seed)
        options = {
            "a": shuffled.option_a,
            "b": shuffled.option_b,
            "c": shuffled.option_c,
            "d": shuffled.option_d,
        }
        # The declared correct option still names the same answer text.
        assert options[shuffled.correct_option] == correct_text
        # And the four options are the same four, only reordered.
        assert sorted(options.values()) == sorted(
            [item.option_a, item.option_b, item.option_c, item.option_d]
        )
        positions.add(shuffled.correct_option)
    assert positions == {"a", "b", "c", "d"}, positions


def test_unregistered_topic_raises_pipeline_config_error() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            with pytest.raises(PipelineConfigError):
                await generate_authored_candidate(
                    session=session,
                    gateway=_ScriptedAuthoredGateway(),
                    curriculum=curriculum,
                    topic_id="fraction_operations",
                    difficulty_label=1,
                    seed=1,
                    session_spend_cents=0.0,
                )

    asyncio.run(run())


# --- Golden bad-item fixtures (ROADMAP S20 "Done when") ----------------------------


def test_two_correct_options_rejected_with_persisted_reasons() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(item_factory=lambda _: _good_item(option_b="4"))
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1001,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert outcome.question_template_id is None
            assert any("unique" in r or "exactly one option" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            assert run_row.outcome == "rejected"
            assert run_row.question_template_id is None
            assert run_row.reasons == outcome.reasons

    asyncio.run(run())


def test_leaked_answer_rejected_with_persisted_reasons() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            leaked_item = _good_item(
                hint_ladder=[
                    "The answer is 4, but think about why.",
                    "Try counting up from 2 by 2 more.",
                    "Add the two numbers together directly.",
                ]
            )
            gateway = _ScriptedAuthoredGateway(item=leaked_item)
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1002,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("leak" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            assert run_row.outcome == "rejected"
            assert run_row.question_template_id is None

    asyncio.run(run())


def test_disagreeing_solver_rejected_with_persisted_reasons() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(stem="Solve: disagreement fixture, what is 2 + 2?"),
                solver_b_option="b",
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1003,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("solver disagreement" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            assert run_row.outcome == "rejected"
            assert run_row.stage_results["solver_a"]["selected_option"] == "a"
            assert run_row.stage_results["solver_b"]["selected_option"] == "b"

    asyncio.run(run())


def test_off_grade_wording_rejected_with_persisted_reasons() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            item = _good_item(stem="This is a dumb question: what is 2 + 2?")
            gateway = _ScriptedAuthoredGateway(item=item)
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1004,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("disallowed wording" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            assert run_row.outcome == "rejected"
            assert run_row.question_template_id is None

    asyncio.run(run())


def test_near_duplicate_rejected_with_persisted_reasons() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        fixed_vector = [0.1] * _EMBEDDING_DIM
        async with _rollback_session() as session:
            first = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: what is 2 + 2, the first time?"),
                    embedding_vector=fixed_vector,
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1005,
                session_spend_cents=0.0,
            )
            assert first.status == "pending"

            second = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: compute 2 + 2, phrased differently."),
                    embedding_vector=fixed_vector,
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1006,
                session_spend_cents=0.0,
            )
            assert second.status == "rejected"
            assert any("near-duplicate" in r for r in second.reasons)

            # Postgres `now()` is frozen per-transaction, so ordering by `created_at`
            # can't disambiguate two rows created in the same rollback-session
            # transaction (both calls above share one) - match on content instead.
            result = await session.execute(
                select(QuestionValidationRun).where(QuestionValidationRun.outcome == "rejected")
            )
            rejected_runs = result.scalars().all()
            assert any(
                run.question_template_id is None and "near-duplicate" in " ".join(run.reasons)
                for run in rejected_runs
            )

    asyncio.run(run())


def test_judge_flags_reject_and_borderline_score_sets_high_priority() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            ambiguous_judge = QuestionJudgeResponse(
                difficulty_label=1,
                is_ambiguous=True,
                is_aligned=True,
                is_age_appropriate=True,
                hint_quality_score=5,
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: judge-ambiguous fixture, what is 2 + 2?"),
                    judge=ambiguous_judge,
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1007,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("ambiguity" in r for r in outcome.reasons)

        async with _rollback_session() as session:
            borderline_judge = QuestionJudgeResponse(
                difficulty_label=1,
                is_ambiguous=False,
                is_aligned=True,
                is_age_appropriate=True,
                hint_quality_score=3,
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: judge-borderline fixture, what is 2 + 2?"),
                    judge=borderline_judge,
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1008,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)  # type: ignore[arg-type]
            assert template is not None
            assert template.review_priority == "high"

    asyncio.run(run())


# --- review_cli.py --------------------------------------------------------------


def test_review_cli_render_item_includes_pipeline_evidence() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: render fixture, what is 2 + 2?")
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1101,
                session_spend_cents=0.0,
            )
            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)  # type: ignore[arg-type]
            variant = await repo.get_variant_for_template(outcome.question_template_id)  # type: ignore[arg-type]
            validation_run = await repo.get_latest_validation_run(outcome.question_template_id)  # type: ignore[arg-type]
            assert template is not None

            rendered = review_cli.render_item(template, variant, validation_run)
            assert template.stem is not None
            assert template.stem in rendered
            assert "* a)" in rendered
            assert "pipeline evidence" in rendered

    asyncio.run(run())


def test_review_cli_approve_reject_and_rerun() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)

            approve_outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: approve fixture, what is 2 + 2?")
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1102,
                session_spend_cents=0.0,
            )
            assert approve_outcome.status == "pending"
            # Activated through the repository rather than `review_cli.approve`, which now
            # refuses authored templates outright because the runtime cannot render them
            # (see `test_approving_an_unservable_authored_template_is_refused`). What this
            # test is about is the pending -> approved transition and the "only pending can
            # move" invariants below, which are the repository's to enforce.
            await repo.activate_template(approve_outcome.question_template_id)  # type: ignore[arg-type]
            approved = await repo.get_template(approve_outcome.question_template_id)  # type: ignore[arg-type]
            assert approved is not None
            assert approved.validation_status == "approved"

            reject_outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: reject fixture, what is 2 + 2?")
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1103,
                session_spend_cents=0.0,
            )
            assert reject_outcome.status == "pending"
            await review_cli.reject(session, reject_outcome.question_template_id)  # type: ignore[arg-type]
            rejected = await repo.get_template(reject_outcome.question_template_id)  # type: ignore[arg-type]
            assert rejected is not None
            assert rejected.validation_status == "rejected"

            # Both guards refuse a non-pending template (D-026's "only pending can
            # move" invariant, extended to the reviewer's own actions).
            with pytest.raises(ValueError):
                await repo.activate_template(reject_outcome.question_template_id)  # type: ignore[arg-type]
            with pytest.raises(ValueError):
                await repo.reject_template(approve_outcome.question_template_id)  # type: ignore[arg-type]

    asyncio.run(run())


def test_review_cli_edit_and_rerun_supersedes_and_bumps_version() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: rerun-original fixture, what is 2 + 2?")
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1104,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            original_id = outcome.question_template_id
            assert original_id is not None

            gateway = _ScriptedAuthoredGateway(
                item=_good_item(stem="Solve: rerun-replacement fixture, what is 2 + 2?")
            )
            message = await review_cli.edit_and_rerun(session, gateway, original_id)
            assert "superseded" in message

            original = await repo.get_template(original_id)
            assert original is not None
            assert original.validation_status == "superseded"

            new_template_id = message.rsplit(" ", 1)[-1]
            new_template = await repo.get_template(new_template_id)
            assert new_template is not None
            assert new_template.version == original.version + 1
            assert new_template.validation_status == "pending"

    asyncio.run(run())


# --- D-186: multi-tier-per-skill authoring ------------------------------------------
#
# The middle skills carry their native tier ±1 so that D-169's rule 2 has something to
# choose between. Until content exists at those tiers the *selector* stays inert - these
# tests are about the pipeline being able to produce it, which is the part that was
# structurally impossible before: the skill was derived *from* the difficulty, so no
# number of runs could ever yield two tiers for one skill.


def test_the_two_skill_maps_agree_on_every_native_tier() -> None:
    """The native ladder and the authoring plan are separate maps, so they can drift.

    `TOPIC_DIFFICULTY_SKILLS` (tier -> skill) is still the default when no skill is named;
    `TOPIC_SKILL_DIFFICULTIES` (skill -> tiers) says where content should exist. A skill
    whose native tier fell out of its planned list would be generatable by derivation and
    rejected when named explicitly - the two paths would disagree about the same slot.
    """
    for topic_id, difficulty_skills in ai_pipeline.TOPIC_DIFFICULTY_SKILLS.items():
        planned = ai_pipeline.TOPIC_SKILL_DIFFICULTIES[topic_id]
        for native_tier, skill_id in difficulty_skills.items():
            assert skill_id in planned, f"{skill_id} has no authoring plan"
            assert native_tier in planned[skill_id], (
                f"{skill_id}'s native tier {native_tier} is missing from its planned tiers"
            )
        # And nothing is planned for a skill the taxonomy does not place in this topic.
        assert set(planned) == set(difficulty_skills.values())


def test_the_plan_keeps_every_tier_inside_what_a_student_can_be_recommended() -> None:
    """`mastery_bootstrap` anchors `recommended_difficulty` at the modal assessed tier ±1
    and clamps to 1-5, so a skill authored further than one tier from its native home
    could never be selected - content nothing can serve is worse than no content.
    """
    for topic_id, difficulty_skills in ai_pipeline.TOPIC_DIFFICULTY_SKILLS.items():
        native_of = {skill: tier for tier, skill in difficulty_skills.items()}
        for skill_id, tiers in ai_pipeline.TOPIC_SKILL_DIFFICULTIES[topic_id].items():
            for tier in tiers:
                assert 1 <= tier <= 5
                assert abs(tier - native_of[skill_id]) <= 1, (
                    f"{skill_id} planned at {tier}, unreachable from native "
                    f"{native_of[skill_id]}"
                )


def test_a_middle_skill_generates_at_a_tier_that_is_not_its_native_one() -> None:
    """The point of the whole change: `linear_two_step` is native to tier 2, and this
    authors it at tier 3 - a (skill, tier) pair the derived-from-difficulty path could
    not express, because tier 3 derives to `linear_neg_frac_coeff`.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=3,
                seed=771001,
                session_spend_cents=0.0,
                skill_id="linear_two_step",
            )
            assert outcome.status == "pending"
            assert outcome.question_template_id is not None

            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            # Both halves matter: the tier the reviewer asked for, and the skill that
            # would have been silently overwritten by the old derivation.
            assert template.difficulty_label == 3
            assert template.skill_id == "linear_two_step"
            assert template.skill_id != ai_pipeline.TOPIC_DIFFICULTY_SKILLS["linear_equations"][3]

    asyncio.run(run())


def test_omitting_the_skill_still_derives_it_from_the_tier() -> None:
    """The 1:1 default is unchanged - every existing caller passes no `skill_id`."""

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=3,
                seed=771002,
                session_spend_cents=0.0,
            )
            assert outcome.question_template_id is not None
            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            assert template.skill_id == "linear_neg_frac_coeff"

    asyncio.run(run())


def test_an_unplanned_skill_tier_pair_is_a_config_error_rather_than_content() -> None:
    """`linear_one_step` is planned at tier 1 only. Asking for it at 4 is a mistake, and
    generating it anyway would spend money on an item no student could ever be served -
    the recommendation range cannot reach it.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            with pytest.raises(PipelineConfigError, match="not planned at difficulty_label"):
                await generate_authored_candidate(
                    session=session,
                    gateway=_ScriptedAuthoredGateway(),
                    curriculum=curriculum,
                    topic_id="linear_equations",
                    difficulty_label=4,
                    seed=771003,
                    session_spend_cents=0.0,
                    skill_id="linear_one_step",
                )

    asyncio.run(run())


def test_an_unknown_skill_is_a_config_error() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            with pytest.raises(PipelineConfigError, match="no registered skill"):
                await generate_authored_candidate(
                    session=session,
                    gateway=_ScriptedAuthoredGateway(),
                    curriculum=curriculum,
                    topic_id="linear_equations",
                    difficulty_label=2,
                    seed=771004,
                    session_spend_cents=0.0,
                    skill_id="fraction_add_sub_like",
                )

    asyncio.run(run())
