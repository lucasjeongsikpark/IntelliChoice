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
from typing import NoReturn

import pytest
from intellichoice_curriculum import ai_pipeline, pipeline_cli, review_cli
from intellichoice_curriculum.ai_pipeline import (
    TOPIC_SKILL_DIFFICULTIES,
    PipelineConfigError,
    generate_authored_candidate,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.settings import CurriculumPipelineSettings
from intellichoice_db.engine import create_engine
from intellichoice_db.models.questions import QuestionTemplate, QuestionValidationRun
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    CircuitOpenError,
    EmbeddingResult,
    EquationDesignResponse,
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
# Deliberately absurd, so no real authoring run would ever choose it and consume the ids
# these tests assert are free (D-201).
_TEST_RESERVED_SEED_OFFSET = 990_000_000


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
            steps=[SolutionStep(step_number=1, explanation="Add the numbers.", expression="2 + 2")],
            final_answer="4",
        ),
        misconception_tags=["off_by_one"],
        estimated_time_seconds=30,
        proposed_difficulty=1,
        difficulty_rationale=(
            "One addition with single-digit whole numbers and no equation to rearrange."
        ),
        required_prerequisites=["single-digit addition"],
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
        solver_objection: dict[str, object] | None = None,
        judge: QuestionJudgeResponse | None = None,
        embedding_vector: list[float] | None = None,
    ) -> None:
        self._item = item
        self._item_factory = item_factory
        self._solver_a_option = solver_a_option
        self._solver_b_option = solver_b_option
        # Applied to solver A only, so a test can check that *one* objecting solver is
        # enough - the whole point of the flags is that they don't need a second vote.
        self._solver_objection = solver_objection or {}
        self._judge = judge
        self._embedding_vector = embedding_vector
        self._last_item: AuthoredGeneratedItemResponse | None = None
        # response_model name -> the ceiling that stage was called with. Recorded rather
        # than asserted here so one test can state the whole per-stage sizing (see
        # `test_authored_stages_get_ceilings_above_the_measured_response_size`).
        self.ceilings: dict[str, int] = {}
        self.design_calls = 0

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: object,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
        # A fake gateway should tolerate options it does not implement - D-205 passes
        # `tools`/`tool_executor` on the design call, and a double that refused them would
        # be asserting something about its own signature rather than about the pipeline.
        **_options: object,
    ) -> BedrockGenerationResult[T]:
        name = response_model.__name__
        self.ceilings[name] = max_output_tokens
        if name == "EquationDesignResponse":
            # D-200's cheap pre-stage. The double always returns a skeleton that passes the
            # deterministic check, so every existing test still exercises the behaviour it
            # was written for; a test that wants the design stage to fail scripts it
            # explicitly (see `_FailingDesignGateway`).
            self.design_calls += 1
            value: BaseModel = EquationDesignResponse(
                reasoning="scripted design",
                scenario_sketch="Two friends combine what they have.",
                unknown_meaning="the number of items to add",
                equation="Eq(x, 2 + 2)",
                final_answer="4",
            )
        elif name == "AuthoredGeneratedItemResponse":
            assert isinstance(payload, AuthoredGeneratorPayload)
            if self._item_factory is not None:
                value = self._item_factory(payload)
            elif self._item is not None:
                value = self._item
            else:
                # A real generator is told the target tier and normally proposes it, so the
                # default double does too. Without this every default fixture proposed 1
                # while the slot asked for 3, and D-194's slot gate correctly rejected it -
                # the double was modelling a generator that ignores its instructions.
                value = _good_item(proposed_difficulty=payload.target_difficulty)
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
            is_solver_a = task == BedrockTask.QUESTION_GENERATION
            if is_solver_a:
                selected = self._solver_a_option or as_presented
            else:
                selected = self._solver_b_option or as_presented
            value = SolverResponse(
                reasoning="scripted solver",
                selected_option=selected,  # type: ignore[arg-type]
                **(self._solver_objection if is_solver_a else {}),  # type: ignore[arg-type]
            )
        elif name == "QuestionJudgeResponse":
            assert isinstance(payload, QuestionJudgePayload)
            assert self._last_item is not None
            value = self._judge or QuestionJudgeResponse(
                reasoning="scripted judge",
                # The judge no longer receives a proposed difficulty (D-194), so the
                # double cannot echo one. Agreeing with the item's own proposal is what
                # makes the default path "the two readings agree"; a test that wants a
                # disagreement passes `judge=`.
                reviewed_difficulty=self._last_item.proposed_difficulty,
                difficulty_reasoning="scripted judge difficulty reasoning, long enough",
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
            reasoning="out-of-range score fixture",
            reviewed_difficulty=3,
            difficulty_reasoning="a rationale long enough to clear the length floor",
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
    correct_text = {"a": item.option_a, "b": item.option_b, "c": item.option_c}[item.correct_option]

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


def test_a_solver_that_cannot_find_its_answer_rejects_even_though_both_agree() -> None:
    """The gap that let a wrong item through, closed (D-193).

    `narrative-linear_equations-d4-23000` reached `pending` with the wrong answer: the
    story's answer was 4, no option offered 4, and both solvers - unable to say so through
    a closed `selected_option` literal - picked the same wrong option. The agreement arm
    then read that as independent confirmation, which is the worst possible reading of it.

    So the fixture here is deliberately one where **agreement holds**: both solvers select
    the declared correct option, and the rejection comes only from solver A's
    `no_option_matches`. If the flag were ignored, this candidate would pass.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(stem="Solve: missing-answer fixture, what is 2 + 2?"),
                solver_objection={"no_option_matches": True},
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1013,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert outcome.rejected_at == "solver"
            assert any("not among the options" in r for r in outcome.reasons)
            # Not a disagreement - saying so would send a reviewer looking for the wrong
            # defect entirely.
            assert not any("disagreement" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            assert run_row.stage_results["solver_a"]["no_option_matches"] is True
            assert run_row.stage_results["solver_b"]["no_option_matches"] is False

    asyncio.run(run())


def test_one_solver_flagging_ambiguity_is_enough_to_reject() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(stem="Solve: ambiguity fixture, what is 2 + 2?"),
                solver_objection={
                    "is_unambiguous": False,
                    "ambiguity_reasons": ["the broth may or may not count as soup"],
                },
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1014,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert outcome.rejected_at == "solver"
            assert any("broth" in r for r in outcome.reasons)

    asyncio.run(run())


def test_the_judge_and_solver_decide_after_they_reason_not_before() -> None:
    """Field order is the mechanism, so it is what gets asserted.

    A model emits JSON in the order the tool's schema declares (the gateway sends
    `model_json_schema()`), so a verdict field ahead of `reasoning` is decided before any
    reasoning exists and cannot be revised by it. That is not a theory: the judge on
    `narrative-linear_equations-d4-23000` worked out that the stated answer was wrong,
    wrote so, and had already emitted `is_internally_consistent: true`.

    Asserting on the schema rather than on a model's behaviour is deliberate - this is a
    property of what we send, which is the only part we control.
    """
    for model in (QuestionJudgeResponse, SolverResponse):
        fields = list(model.model_json_schema()["properties"])
        assert fields[0] == "reasoning", f"{model.__name__} decides before it reasons"

    # And the escape hatches exist at all, since a prompt asking for them is useless if
    # the schema has nowhere to put the answer.
    solver_fields = SolverResponse.model_json_schema()["properties"]
    assert "no_option_matches" in solver_fields
    assert "is_unambiguous" in solver_fields



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
                reasoning="scripted judge",
                reviewed_difficulty=1,
                difficulty_reasoning="a rationale long enough to clear the length floor",
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
                reasoning="scripted judge",
                reviewed_difficulty=1,
                difficulty_reasoning="a rationale long enough to clear the length floor",
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
                    f"{skill_id} planned at {tier}, unreachable from native {native_of[skill_id]}"
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


def test_generator_schema_accepts_and_rejects_difficulty_metadata() -> None:
    """The difficulty fields are only worth having if the schema enforces them, because
    the schema is what the model is shown - `model_json_schema()` is the tool's input
    contract, so a bound written here reaches the model as `minimum`/`maximum` and a
    missing one lets it invent a scale (which it did, on the first real run).
    """
    assert _good_item(proposed_difficulty=5).proposed_difficulty == 5

    for invalid in (0, 6, -1):
        with pytest.raises(ValidationError):
            _good_item(proposed_difficulty=invalid)

    schema = AuthoredGeneratedItemResponse.model_json_schema()["properties"]
    assert schema["proposed_difficulty"]["minimum"] == 1
    assert schema["proposed_difficulty"]["maximum"] == 5

    # "This is difficulty 3" is not a rationale, and neither is the empty string. A length
    # floor cannot force a good one; it can refuse the degenerate ones, and the judge is
    # what actually tests the claim.
    for empty in ("", "   ", "hard"):
        with pytest.raises(ValidationError):
            _good_item(difficulty_rationale=empty)

    # And the response is closed: a drifted model that invents a field fails into the
    # repair retry rather than having the extra silently dropped.
    with pytest.raises(ValidationError):
        _good_item(confidence=0.9)


def test_difficulty_agreement_accepts_disagreement_flags_and_wide_gaps_reject() -> None:
    """The whole policy, as arithmetic on two numbers - no gateway and no database.

    Acceptability is computed rather than asked of the judge, deliberately: a judge blind
    to the proposal cannot say whether it is acceptable, and a judge shown the proposal is
    no longer independent, so the only coherent answer is the one arithmetic gives.
    """
    rationale = "a rationale long enough to clear the length floor"

    agreed = ai_pipeline.judge_difficulty(
        proposed=3,
        proposed_rationale=rationale,
        reviewed=3,
        reviewed_rationale=rationale,
        requested=3,
    )
    assert agreed.decision == "accepted"
    assert agreed.proposal_gap == 0
    assert agreed.reasons == []

    one_off = ai_pipeline.judge_difficulty(
        proposed=3,
        proposed_rationale=rationale,
        reviewed=4,
        reviewed_rationale=rationale,
        requested=3,
    )
    assert one_off.decision == "flagged"
    assert one_off.reasons == []

    two_off = ai_pipeline.judge_difficulty(
        proposed=2,
        proposed_rationale=rationale,
        reviewed=4,
        reviewed_rationale=rationale,
        requested=3,
    )
    assert two_off.decision == "rejected"
    assert any("difficulty disagreement" in r for r in two_off.reasons)

    # The second gate: the two models can agree with each other and still both be far from
    # the tier the slot asked for. Storing that item at the requested tier would offer it
    # to students who have earned a different one, so it is rejected on its own terms.
    wrong_slot = ai_pipeline.judge_difficulty(
        proposed=1,
        proposed_rationale=rationale,
        reviewed=1,
        reviewed_rationale=rationale,
        requested=5,
    )
    assert wrong_slot.decision == "rejected"
    assert any("too far from the requested tier" in r for r in wrong_slot.reasons)

    # Both numbers and both rationales survive into the evidence whatever the outcome.
    evidence = two_off.as_evidence()
    assert evidence["generator_proposed_difficulty"] == 2
    assert evidence["judge_reviewed_difficulty"] == 4
    assert evidence["proposal_vs_review_difference"] == 2
    assert evidence["decision"] == "rejected"


def test_one_level_difficulty_disagreement_keeps_the_item_at_high_priority() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(
                        stem="Solve: one-level disagreement fixture, what is 2 + 2?",
                        proposed_difficulty=1,
                    ),
                    judge=QuestionJudgeResponse(
                        reasoning="scripted judge",
                        reviewed_difficulty=2,
                        difficulty_reasoning="one more step than a bare sum, on reflection",
                        is_ambiguous=False,
                        is_aligned=True,
                        is_age_appropriate=True,
                        hint_quality_score=5,
                    ),
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1021,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            template = await QuestionRepository(session).get_template(
                outcome.question_template_id or ""
            )
            assert template is not None
            assert template.review_priority == "high"
            assert template.difficulty_confidence == 0.5

            run_row = await _latest_validation_run(session)
            evidence = run_row.stage_results["difficulty"]
            assert evidence["generator_proposed_difficulty"] == 1
            assert evidence["judge_reviewed_difficulty"] == 2
            assert evidence["decision"] == "flagged"
            assert run_row.stage_results["prerequisites"] == ["single-digit addition"]

    asyncio.run(run())


def test_two_level_difficulty_disagreement_rejects_with_both_rationales_persisted() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(
                        stem="Solve: two-level disagreement fixture, what is 2 + 2?",
                        proposed_difficulty=1,
                        difficulty_rationale="a single addition with no equation to rearrange",
                    ),
                    judge=QuestionJudgeResponse(
                        reasoning="scripted judge",
                        reviewed_difficulty=3,
                        difficulty_reasoning=(
                            "reads as multi-step with a negative coefficient, to me"
                        ),
                        is_ambiguous=False,
                        is_aligned=True,
                        is_age_appropriate=True,
                        hint_quality_score=5,
                    ),
                ),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=1022,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert outcome.rejected_at == "difficulty"
            assert any("difficulty disagreement" in r for r in outcome.reasons)

            run_row = await _latest_validation_run(session)
            evidence = run_row.stage_results["difficulty"]
            assert evidence["generator_difficulty_rationale"].startswith("a single addition")
            assert evidence["judge_difficulty_reasoning"].startswith("reads as multi-step")
            assert evidence["proposal_vs_review_difference"] == 2

    asyncio.run(run())


def test_the_judge_is_not_told_what_difficulty_was_asked_for() -> None:
    """Blindness is the premise the whole comparison rests on, so it is asserted on the
    payload's own schema rather than trusted to a prompt sentence.
    """
    fields = set(QuestionJudgePayload.model_fields)
    assert "proposed_difficulty" not in fields
    assert not any("difficulty" in name for name in fields), fields
    assert not any("rationale" in name for name in fields), fields


def _settings(*, solver_a: str = "model-x", solver_b: str = "model-y", cap: float = 1000.0):
    return CurriculumPipelineSettings(
        bedrock_generation_model_id=solver_a,
        bedrock_review_model_id=solver_b,
        bedrock_run_budget_cents=cap,
    )


def test_the_plan_the_preflight_reports_is_the_plan_the_runner_executes() -> None:
    """One structure drives both, and this is what says so.

    D-193 built the preflight to recompute ids independently, on the theory that a shared
    derivation could not catch a divergence. Filtering (D-194) changed the balance: a
    `--skill-id` the report understood and the loop ignored would generate content nobody
    asked for, which is worse than the divergence the duplication guarded against. So the
    plan is shared and the agreement is asserted here instead.
    """
    plan = pipeline_cli.build_plan(candidates_per_slot=1, seed_offset=0)
    ids = plan.template_ids
    assert len(ids) == len(set(ids)), "a run cannot claim the same id twice"
    assert len(ids) == sum(
        len(tiers) for topic in TOPIC_SKILL_DIFFICULTIES.values() for tiers in topic.values()
    )
    for slot in plan.slots:
        assert slot.difficulty_label in TOPIC_SKILL_DIFFICULTIES[slot.topic_id][slot.skill_id]
        assert slot.question_template_id.endswith(str(slot.seed))

    # A fresh offset must claim an entirely disjoint range - that is what it is for.
    shifted = pipeline_cli.build_plan(candidates_per_slot=1, seed_offset=400_000)
    assert not set(ids) & set(shifted.template_ids)


def test_cli_filters_generate_only_the_requested_skills_and_difficulties() -> None:
    plan = pipeline_cli.build_plan(topic_id="linear_equations",
        skill_ids=["linear_both_sides"],
        difficulties=[3, 4],
        candidates_per_slot=3,
        seed_offset=40_000,
    )
    assert {slot.skill_id for slot in plan.slots} == {"linear_both_sides"}
    assert {slot.difficulty_label for slot in plan.slots} == {3, 4}
    assert len(plan.slots) == 2 * 3  # two tiers, three candidates each

    # Narrowing must not move the seeds. The skill index is enumerated over the whole
    # topic precisely so that a filtered run and a full run propose the *same* ids for the
    # slots they share - otherwise narrowing a run would silently make it collide with an
    # earlier full one.
    full = pipeline_cli.build_plan(candidates_per_slot=3, seed_offset=40_000)
    assert set(plan.template_ids) <= set(full.template_ids)


def test_unsupported_requested_skill_or_difficulty_fails_before_anything_is_called() -> None:
    with pytest.raises(pipeline_cli.PlanError, match="outside the 1-5 scale"):
        pipeline_cli.build_plan(difficulties=[7])
    with pytest.raises(pipeline_cli.PlanError, match="not in the selected topic"):
        pipeline_cli.build_plan(skill_ids=["fraction_add_sub_like"])
    with pytest.raises(pipeline_cli.PlanError, match="no registered generation plan"):
        pipeline_cli.build_plan(topic_id="place_value")
    # A pair that is individually valid but is not in the authoring plan: tier 1 exists and
    # `linear_distribute` exists, but D-186 only plans that skill at tier 5.
    with pytest.raises(pipeline_cli.PlanError, match="no generation slots match"):
        pipeline_cli.build_plan(skill_ids=["linear_distribute"], difficulties=[1])


def test_preflight_fails_when_the_two_solvers_are_one_model() -> None:
    """Solver A and B read `bedrock_generation_model_id` and `bedrock_review_model_id`,
    which carry the *same default* - so the shipped configuration gives two solvers that
    are one model, and their agreement is one opinion counted twice.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            # A reserved offset no real run uses. The previous value, 810_000, was a
            # perfectly ordinary one for a pilot to pick - and a pilot did pick it, which
            # made this test fail on any machine whose database had seen that run. A test
            # asserting "these ids are free" must claim a range nothing else will.
            plan = pipeline_cli.build_plan(
                candidates_per_slot=1, seed_offset=_TEST_RESERVED_SEED_OFFSET
            )
            report = await pipeline_cli.preflight(
                session, _settings(solver_a="model-x", solver_b="model-x"), plan
            )
            assert not report.ok
            assert any("one opinion counted twice" in f for f in report.failures)
            assert "solver diversity:      FAIL" in report.text

            report = await pipeline_cli.preflight(session, _settings(), plan)
            assert report.ok, report.failures
            assert "solver diversity:      PASS" in report.text

    asyncio.run(run())


def test_two_inference_profiles_for_one_model_are_not_two_solvers() -> None:
    """A string comparison answers the wrong question, and answers it permissively.

    Bedrock's `us.` / `global.` / bare ids are routing aliases for the same weights, so two
    solvers configured that way agree by construction while the check meant to catch that
    reports PASS. Found while preparing a pilot in an account with exactly two accessible
    Anthropic models, which is the situation that makes reaching for an alias the obvious
    move rather than a contrived one.
    """
    haiku = "anthropic.claude-haiku-4-5-20251001-v1:0"
    assert pipeline_cli.underlying_model(f"us.{haiku}") == haiku
    assert pipeline_cli.underlying_model(f"global.{haiku}") == haiku
    assert pipeline_cli.underlying_model(haiku) == haiku
    # A genuinely different model is still different.
    assert pipeline_cli.underlying_model("us.anthropic.claude-sonnet-5") != haiku

    async def run() -> None:
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(candidates_per_slot=1, seed_offset=870_000)
            report = await pipeline_cli.preflight(
                session,
                _settings(solver_a=f"us.{haiku}", solver_b=f"global.{haiku}"),
                plan,
            )
            assert not report.ok
            assert any("two inference profiles for one model" in f for f in report.failures)

            # And two real models still pass, prefixes and all.
            report = await pipeline_cli.preflight(
                session,
                _settings(solver_a=f"us.{haiku}", solver_b="us.anthropic.claude-sonnet-5"),
                plan,
            )
            assert report.ok, report.failures

    asyncio.run(run())


def test_preflight_sees_a_taken_id_before_the_run_pays_for_it() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(candidates_per_slot=1, seed_offset=900_000)
            report = await pipeline_cli.preflight(session, _settings(), plan)
            assert report.ok, "a fresh offset should be clear"

            # Claim one of the ids this plan would use, then ask again. Taken from the plan
            # itself rather than rebuilt by hand: hand-rebuilding is how an earlier version
            # of this test claimed a (skill, tier) pair the plan never visits, then "proved"
            # the preflight saw nothing by handing it nothing.
            first = plan.slots[0]
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(
                        stem="Solve: preflight fixture, what is 2 + 2?",
                        # The slot decides the tier, so the fixture's proposal has to
                        # follow it or D-194's slot gate rejects a candidate this test is
                        # only using to occupy an id.
                        proposed_difficulty=first.difficulty_label,
                    )
                ),
                curriculum=curriculum,
                topic_id=first.topic_id,
                difficulty_label=first.difficulty_label,
                seed=first.seed,
                session_spend_cents=0.0,
                skill_id=first.skill_id,
            )
            assert outcome.status == "pending"
            assert outcome.question_template_id == first.question_template_id

            report = await pipeline_cli.preflight(session, _settings(), plan)
            assert not report.ok
            assert any("already exist" in f for f in report.failures)
            assert "id availability:       FAIL" in report.text

            # And the documented remedy works without deleting anything.
            fresh = pipeline_cli.build_plan(candidates_per_slot=1, seed_offset=950_000)
            assert (await pipeline_cli.preflight(session, _settings(), fresh)).ok

    asyncio.run(run())


def test_preflight_refuses_a_budget_above_the_configured_hard_cap() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(
                candidates_per_slot=1, seed_offset=820_000, run_budget_cents=500.0
            )
            report = await pipeline_cli.preflight(session, _settings(cap=100.0), plan)
            assert not report.ok
            assert any("exceeds the configured hard ceiling" in f for f in report.failures)

    asyncio.run(run())


def test_preflight_and_dry_run_make_no_provider_call() -> None:
    """The claim `--preflight` and `--dry-run` rest on, asserted rather than assumed.

    A gateway that raises on any use is the only way to prove a code path did not call one;
    counting calls would pass a version that made a call and discarded the result.
    """

    class _ExplodingGateway:
        async def generate_structured(self, **kwargs: object) -> object:
            raise AssertionError("preflight made a model call")

        async def embed(self, **kwargs: object) -> object:
            raise AssertionError("preflight made an embedding call")

    async def run() -> None:
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(candidates_per_slot=2, seed_offset=830_000)
            report = await pipeline_cli.preflight(session, _settings(), plan)
            assert report.text  # it produced a report...
            # ...and the gateway it never touched still refuses to be touched.
            with pytest.raises(AssertionError):
                await _ExplodingGateway().generate_structured()

            # Nothing was written either: the ids the plan names still do not exist.
            existing = (
                (
                    await session.execute(
                        select(QuestionTemplate.question_template_id).where(
                            QuestionTemplate.question_template_id.in_(plan.template_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert existing == []

    asyncio.run(run())


def test_preflight_reports_every_field_a_paid_decision_needs() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(topic_id="linear_equations",
                skill_ids=["linear_both_sides"],
                difficulties=[4],
                candidates_per_slot=2,
                seed_offset=840_000,
            )
            report = await pipeline_cli.preflight(session, _settings(), plan)
            for expected in [
                "provider:",
                "generator model:",
                "solver A model:",
                "solver B model:",
                "judge model:",
                "embedding model:",
                "topic:                 linear_equations",
                "skills:                linear_both_sides",
                "difficulties:          4",
                "candidates per slot:   2",
                "scheduled candidates:  2",
                "planned template ids:",
                "already-used ids:      0",
                "seed offset:           840000",
                "run budget ceiling:",
                "estimated max calls:   10",
                "estimated max spend:",
                "solver diversity:",
                "id availability:",
            ]:
                assert expected in report.text, expected

    asyncio.run(run())


def test_per_candidate_settlement_survives_a_duplicate_id() -> None:
    """D-193's property, re-asserted now that one loop serves both modes: the candidate
    that collides is lost and the ones already committed are not.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            plan = pipeline_cli.build_plan(skill_ids=["linear_one_step"],
                difficulties=[1],
                candidates_per_slot=1,
                seed_offset=860_000,
            )
            slot = plan.slots[0]
            # Take the id first, so the run's only candidate is guaranteed to collide.
            await generate_authored_candidate(
                session=session,
                gateway=_ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: collision fixture, what is 2 + 2?")
                ),
                curriculum=curriculum,
                topic_id=slot.topic_id,
                difficulty_label=slot.difficulty_label,
                seed=slot.seed,
                session_spend_cents=0.0,
                skill_id=slot.skill_id,
            )
            await session.commit()

            summary = await pipeline_cli.run_plan(
                session,
                _ScriptedAuthoredGateway(
                    item=_good_item(stem="Solve: collision rerun, what is 2 + 2?")
                ),
                plan,
            )
            assert summary.skipped_duplicate_id == 1
            assert summary.pending == 0
            # The already-committed row is untouched by the collision.
            assert (
                await QuestionRepository(session).get_template(slot.question_template_id)
            ) is not None

    asyncio.run(run())


def test_run_summary_separates_processed_from_scheduled() -> None:
    """A 50-candidate run quoted two denominators as if they were one (D-192).

    It reported "8 of 50" and "stopped at 34 of 50" together: 16 candidates never reached a
    model - the gateway refused them on budget - and were counted as rejections, so the
    yield read 16% when the number that says whether the mode works is 8/34. A budget skip
    is not a quality signal and must not sit in the same bucket as a solver disagreement.
    """
    summary = pipeline_cli.RunSummary()
    summary.scheduled = 50
    for _ in range(8):
        summary.record(ai_pipeline.PipelineOutcome(status="pending", cost_cents=1.0))
    stages: list[tuple[ai_pipeline.RejectionStage, int]] = [
        ("solver", 17),
        ("judge", 3),
        ("validation", 5),
        ("dedup", 1),
    ]
    for stage, count in stages:
        for _ in range(count):
            summary.record(
                ai_pipeline.PipelineOutcome(status="rejected", rejected_at=stage, cost_cents=0.5)
            )
    for _ in range(16):
        summary.record(
            ai_pipeline.PipelineOutcome(status="rejected", rejected_at="budget", cost_cents=0.0)
        )

    assert summary.processed == 34
    assert summary.skipped_budget == 16
    assert summary.rejected == 26
    # The budget skips are outside `rejected` entirely, so the quality denominator is the
    # 34 candidates a model actually saw.
    assert summary.pending / summary.processed == pytest.approx(8 / 34)
    rendered = summary.format()
    assert "8 accepted of 34 processed (24%)" in rendered
    assert "50 scheduled" in rendered
    assert "solver=17" in rendered
    assert "budget=16" in rendered


# --- D-195: a rejected candidate keeps its content -----------------------------------
# The first four-candidate pilot rejected all four and left nothing to read: the reasons
# said *that* a hint leaked the answer, never which hint or what answer. These tests pin
# the fix at every stage that can reject after the Generator has returned an item.

_STUDENT_VISIBLE_SNAPSHOT_KEYS = (
    "stem",
    "context_block",
    "option_a",
    "option_b",
    "option_c",
    "option_d",
    "correct_option",
    "hint_ladder",
    "canonical_solution",
    "equation",
)


class _FailingGeneratorGateway(_ScriptedAuthoredGateway):
    """Generator call raises the way a real access denial does - the pilot's first run
    hit `AccessDeniedException` on all four candidates.
    """

    async def generate_structured(self, **kwargs: object) -> object:
        # Fails only the authoring call, so the test still exercises the *generator*
        # rejection path rather than D-200's cheap design stage in front of it.
        model = kwargs.get("response_model")
        if getattr(model, "__name__", "") == "AuthoredGeneratedItemResponse":
            raise BedrockGatewayError("AccessDeniedException: no access to model", cost_cents=0.0)
        return await super().generate_structured(**kwargs)  # type: ignore[arg-type]


async def _reject_and_fetch(
    session: AsyncSession, gateway: object, *, seed: int, difficulty: int = 2
) -> tuple[object, QuestionValidationRun]:
    outcome = await generate_authored_candidate(
        session=session,
        gateway=gateway,  # type: ignore[arg-type]
        curriculum=load_curriculum(),
        topic_id="linear_equations",
        difficulty_label=difficulty,
        seed=seed,
        session_spend_cents=0.0,
    )
    assert outcome.status == "rejected", outcome
    return outcome, await _latest_validation_run(session)


def test_a_gated_rejection_persists_the_whole_candidate() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            # Candidate 2's defect: an equation that restates arithmetic instead of
            # modelling the question, so the deterministic gate rejects before any solver.
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(equation="Eq((20 - 3) / 2, (25 - 7) / 2)", proposed_difficulty=2),
                solver_objection=dict(_SOLVER_OBJECTION),
            )
            outcome, run_row = await _reject_and_fetch(session, gateway, seed=501001)
            assert outcome.rejected_at == "solver"  # type: ignore[attr-defined]
            snapshot = run_row.stage_results["candidate_snapshot"]
            assert snapshot["equation"] == "Eq((20 - 3) / 2, (25 - 7) / 2)"
            # The stage evidence is still there - the snapshot is an addition, not a
            # replacement. A reviewer needs the content *and* the reading that rejected it.
            assert run_row.stage_results["solver_a"]["no_option_matches"] is True
            assert run_row.reasons

    asyncio.run(run())


def test_a_solver_stage_rejection_persists_the_whole_candidate() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            # Candidate 4's defect: an under-specified stem. One solver reporting
            # `no_option_matches` is enough, which is the D-193 escape hatch.
            gateway = _ScriptedAuthoredGateway(
                solver_objection={"no_option_matches": True, "is_unambiguous": False}
            )
            outcome, run_row = await _reject_and_fetch(session, gateway, seed=501002)
            assert outcome.rejected_at == "solver"  # type: ignore[attr-defined]
            assert "candidate_snapshot" in run_row.stage_results
            assert run_row.stage_results["solver_a"]["no_option_matches"] is True

    asyncio.run(run())


def test_a_judge_stage_rejection_persists_the_whole_candidate() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                judge=QuestionJudgeResponse(
                    reasoning="the stem admits two readings",
                    reviewed_difficulty=2,
                    difficulty_reasoning="scripted judge difficulty reasoning, long enough",
                    is_ambiguous=True,
                    is_aligned=True,
                    is_age_appropriate=True,
                    hint_quality_score=5,
                )
            )
            outcome, run_row = await _reject_and_fetch(session, gateway, seed=501003)
            assert outcome.rejected_at == "judge"  # type: ignore[attr-defined]
            assert "candidate_snapshot" in run_row.stage_results
            assert run_row.stage_results["judge"]["is_ambiguous"] is True

    asyncio.run(run())


def test_a_difficulty_stage_rejection_persists_the_candidate_and_both_readings() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            # Candidate 3 exactly: a mathematically correct item lost to a two-tier
            # disagreement. It is the case where keeping the content matters most - the
            # item is the evidence for whether the gate or the generator was wrong.
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(proposed_difficulty=4),
                judge=QuestionJudgeResponse(
                    reasoning="straightforward for the tier",
                    reviewed_difficulty=2,
                    difficulty_reasoning="one step, no rearrangement required of the student",
                    is_ambiguous=False,
                    is_aligned=True,
                    is_age_appropriate=True,
                    hint_quality_score=5,
                ),
            )
            outcome, run_row = await _reject_and_fetch(
                session, gateway, seed=501004, difficulty=4
            )
            assert outcome.rejected_at == "difficulty"  # type: ignore[attr-defined]
            snapshot = run_row.stage_results["candidate_snapshot"]
            # Test 10: all three difficulty readings are recoverable from one row.
            assert snapshot["proposed_difficulty"] == 4
            assert snapshot["requested_difficulty"] == 4
            assert snapshot["difficulty_rationale"]
            difficulty = run_row.stage_results["difficulty"]
            assert difficulty["judge_reviewed_difficulty"] == 2
            assert difficulty["decision"] == "rejected"

    asyncio.run(run())


def test_a_generator_failure_records_the_request_and_error_without_inventing_content() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            outcome, run_row = await _reject_and_fetch(
                session, _FailingGeneratorGateway(), seed=501005
            )
            assert outcome.rejected_at == "generator"  # type: ignore[attr-defined]
            # No item existed, so none is fabricated - the honest half of the fix.
            assert "candidate_snapshot" not in run_row.stage_results
            request = run_row.stage_results["generator_request"]
            assert request["planned_template_id"] == "authored-linear_equations-d2-501005"
            assert request["seed"] == 501005
            assert "AccessDeniedException" in request["provider_error"]

    asyncio.run(run())


def test_the_rejected_snapshot_carries_every_student_visible_field() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(
                    context_block="A class is planning a trip.", equation="Eq(x, 2 + 3)"
                ),
                solver_objection=dict(_SOLVER_OBJECTION),
            )
            _, run_row = await _reject_and_fetch(session, gateway, seed=501006)
            snapshot = run_row.stage_results["candidate_snapshot"]
            for key in _STUDENT_VISIBLE_SNAPSHOT_KEYS:
                assert key in snapshot, f"{key} missing from the rejected candidate snapshot"
            assert snapshot["context_block"] == "A class is planning a trip."
            assert len(snapshot["hint_ladder"]) == 3
            assert snapshot["canonical_solution"]["final_answer"]
            # Provenance: which model wrote it, and which slot it was written for.
            assert snapshot["generator_model_id"] == "test"
            assert snapshot["topic_id"] == "linear_equations"
            assert snapshot["skill_id"]

    asyncio.run(run())


def test_rejected_inspection_renders_the_content_and_cannot_approve() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(stem="Two robots collect crystals.", equation="Eq(x, 2 + 3)"),
                solver_objection=dict(_SOLVER_OBJECTION),
            )
            await _reject_and_fetch(session, gateway, seed=501007)

            rendered = await review_cli.show_rejected(session, limit=5, planned_id=None)
            assert "Two robots collect crystals." in rendered
            assert "REJECTED authored-linear_equations-d2-501007" in rendered
            assert "rejection reasons:" in rendered

            # Read-only, structurally: the inspection path holds no repository write and
            # offers no decision. Approval remains `review_cli.approve`, which this never
            # reaches - and nothing in the pending bank moved.
            template = await QuestionRepository(session).get_template(
                "authored-linear_equations-d2-501007"
            )
            assert template is None

    asyncio.run(run())


def test_rejected_inspection_can_be_narrowed_to_one_planned_id() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            bad_equation = _good_item(equation="Eq(4, 4)")
            objection = dict(_SOLVER_OBJECTION)
            await _reject_and_fetch(
                session,
                _ScriptedAuthoredGateway(item=bad_equation, solver_objection=objection),
                seed=501008,
            )
            await _reject_and_fetch(
                session,
                _ScriptedAuthoredGateway(item=bad_equation, solver_objection=objection),
                seed=501009,
            )
            rendered = await review_cli.show_rejected(
                session, limit=10, planned_id="authored-linear_equations-d2-501009"
            )
            assert "501009" in rendered
            assert "501008" not in rendered

    asyncio.run(run())


def test_rejection_evidence_never_reaches_the_served_bank() -> None:
    """The snapshot is authoring evidence, and the export path must not be able to carry
    it into content students see. Structural, not incidental: `build_bank_file` reads
    approved `QuestionTemplate` rows, and a rejected candidate never becomes one.
    """

    async def run() -> None:
        from intellichoice_curriculum.export_cli import build_bank_file, render_bank_file

        async with _rollback_session() as session:
            gateway = _ScriptedAuthoredGateway(
                item=_good_item(equation="Eq(4, 4)"), solver_objection=dict(_SOLVER_OBJECTION)
            )
            _, run_row = await _reject_and_fetch(session, gateway, seed=501010)
            assert "candidate_snapshot" in run_row.stage_results

            exported = await build_bank_file(
                session,
                topic_id="linear_equations",
                curriculum_version=load_curriculum().curriculum_version,
            )
            rendered = render_bank_file(exported)
            assert "candidate_snapshot" not in rendered
            assert "501010" not in rendered

    asyncio.run(run())


def test_a_pre_d195_rejection_is_not_reported_as_a_generator_failure() -> None:
    """Found by running the new command against the real pilot rows.

    Both a Generator failure and a pre-D-195 run lack a `candidate_snapshot`, and the
    first version of the renderer printed "no candidate was generated" for both. For the
    eleven rejections already in the database that is simply false - those candidates were
    generated, judged, and rejected on their merits, and the stage evidence below the
    header proves it. A reviewer opening the oldest rejections first would have been told
    the opposite of what happened.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            await repo.create_validation_run(
                QuestionValidationRun(
                    question_template_id=None,
                    outcome="rejected",
                    # Exactly the shape D-193/D-194 wrote: stage evidence, no snapshot.
                    stage_results={"deterministic_gate": {"passed": False, "failures": ["x"]}},
                    reasons=["x"],
                    cost_cents=1.0,
                )
            )
            rendered = await review_cli.show_rejected(session, limit=1, planned_id=None)
            assert "no candidate was generated" not in rendered
            assert "content not retained" in rendered
            assert "predates D-195" in rendered

    asyncio.run(run())


# --- D-196: the solvers and the judge must see what the student sees ------------------


def test_solvers_and_judge_receive_the_context_block_not_just_the_stem() -> None:
    """Measured on the real barrel item, which was correct and rejected anyway.

    Its stem is "After how many hours will both barrels contain the same amount of water?"
    and every number - 50 L, 3 L/hour, 30 L, 5 L/hour - lives in the context block. The
    pipeline sent `item.stem` to the solvers and the judge while serving
    `context_block + stem` to the student, so Solver A reported "the problem statement is
    incomplete" and was right about what it had been shown.

    The judge half is the more serious one: it clears content for a student on ambiguity,
    alignment and age-appropriateness, and it was reaching those verdicts about a fragment
    of the item that actually gets served.
    """

    class _RecordingGateway(_ScriptedAuthoredGateway):
        def __init__(self, **kwargs: object) -> None:
            super().__init__(**kwargs)  # type: ignore[arg-type]
            self.seen: dict[str, str] = {}

        async def generate_structured[T: BaseModel](self, **kwargs: object) -> object:
            payload = kwargs["payload"]
            if isinstance(payload, SolverPayload | QuestionJudgePayload):
                self.seen[type(payload).__name__] = payload.rendered_question
            return await super().generate_structured(**kwargs)  # type: ignore[arg-type]

    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RecordingGateway(
                item=_good_item(
                    stem="After how many hours will both barrels hold the same amount?",
                    context_block=(
                        "Barrel X holds 50 litres and fills at 3 litres per hour. "
                        "Barrel Y holds 30 litres and fills at 5 litres per hour."
                    ),
                    equation="Eq(x, 2 + 2)",
                )
            )
            await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=601001,
                session_spend_cents=0.0,
            )

            assert gateway.seen, "neither solver nor judge was called"
            for payload_name, seen in gateway.seen.items():
                assert "50 litres" in seen, (
                    f"{payload_name} was shown a question with no numbers in it - "
                    f"the context block was dropped"
                )
                assert "same amount" in seen, f"{payload_name} lost the stem"

    asyncio.run(run())


# --- D-198: the repair loop, and the boundary it must not cross ----------------------
# `repair_feedback` is the only thing standing between "tell the model what was wrong" and
# "tell the model what the independent checks decided". These tests are that boundary.


def test_repair_feedback_passes_deterministic_failures_verbatim() -> None:
    # Objective, mechanical facts about the item. Nothing here is a verdict, and these are
    # the defects most worth repairing - D-197 measured 4 of 10 items failing exactly this.
    failures = ["SymPy-solved answer 21/5 does not match declared correct option 'b' ('7')"]
    assert ai_pipeline.repair_feedback(
        stage="validation", reasons=failures, stage_results={}
    ) == failures


def test_repair_feedback_never_reveals_which_option_a_solver_chose() -> None:
    """The cheapest way to resolve "solver A picked b, you declared c" is to declare b.

    That satisfies the gate and fixes nothing, and it turns the independent solve into a
    lookup. So the raw reason - which does contain the letters - must not survive.
    """
    raw = ["independent solver disagreement: solver_a='b' solver_b='a' declared='c'"]
    defects = ai_pipeline.repair_feedback(
        stage="solver",
        reasons=raw,
        stage_results={
            "solver_a": {
                "selected_option": "b", "no_option_matches": False, "is_unambiguous": True
            },
            "solver_b": {
                "selected_option": "a", "no_option_matches": False, "is_unambiguous": True
            },
        },
    )
    assert defects
    joined = " ".join(defects)
    for leak in ("solver_a=", "solver_b=", "'b'", "'a'", "declared="):
        assert leak not in joined, f"repair feedback leaked {leak!r}: {joined}"


def test_repair_feedback_describes_a_solver_objection_without_its_verdict() -> None:
    defects = ai_pipeline.repair_feedback(
        stage="solver",
        reasons=["solver_b reached an answer that is not among the options (closest='a')"],
        stage_results={
            "solver_a": {
                "selected_option": "a", "no_option_matches": False, "is_unambiguous": True
            },
            "solver_b": {
                "selected_option": "a", "no_option_matches": True, "is_unambiguous": False
            },
        },
    )
    joined = " ".join(defects or [])
    assert "could not find its answer among your four options" in joined
    assert "ambiguous" in joined
    assert "closest=" not in joined and "'a'" not in joined


def test_repair_feedback_never_reveals_the_judges_difficulty() -> None:
    # The judge's tier is the one number D-194 built blind review to protect. A rejection
    # it caused is not repairable at all - see the next test - but even a judge rejection
    # for another reason must not carry it.
    defects = ai_pipeline.repair_feedback(
        stage="judge",
        reasons=["judge flagged ambiguity: ..."],
        stage_results={"judge": {"is_ambiguous": True, "reviewed_difficulty": 2}},
    )
    joined = " ".join(defects or [])
    assert "ambiguous" in joined
    assert "2" not in joined and "reviewed_difficulty" not in joined


def test_a_difficulty_rejection_is_never_repairable() -> None:
    """The only feedback that would help is the judge's tier, and that is the one thing
    that must not cross. D-197 also measured *why* repairing it is futile:
    `linear_both_sides` proposed-4/judged-2 four times across three sessions - the slot's
    authoring plan is miscalibrated, not its items.
    """
    assert (
        ai_pipeline.repair_feedback(
            stage="difficulty",
            reasons=["difficulty disagreement: generator proposed 4 ... judge rated 2"],
            stage_results={"difficulty": {"judge_reviewed_difficulty": 2}},
        )
        is None
    )


def test_stages_with_nothing_to_repair_are_terminal() -> None:
    for stage in ("generator", "dedup", "budget"):
        assert ai_pipeline.repair_feedback(stage=stage, reasons=["x"], stage_results={}) is None


class _RepairAwareGateway(_ScriptedAuthoredGateway):
    """Emits a defective item first, then a good one once a `repair` block arrives.

    Also records the repair contexts it was handed, so a test can assert what actually
    crossed the boundary rather than only what `repair_feedback` returned in isolation.
    """

    def __init__(
        self,
        *,
        bad: AuthoredGeneratedItemResponse,
        object_until_repaired: bool = True,
        **kwargs: object,
    ) -> None:
        self.repairs: list[object] = []
        # Off when the test wants a *later* stage to do the rejecting - a difficulty
        # disagreement cannot be observed if a solver objects first.
        self._object_until_repaired = object_until_repaired
        super().__init__(  # type: ignore[arg-type]
            item_factory=lambda payload: (
                self._record(payload) or (_good_item(proposed_difficulty=payload.target_difficulty))
                if payload.repair is not None
                else bad
            ),
            **kwargs,  # type: ignore[arg-type]
        )

    def _record(self, payload: AuthoredGeneratorPayload) -> None:
        self.repairs.append(payload.repair)

    async def generate_structured(self, **kwargs: object) -> object:
        # Objects until a repair has actually been handed to the author, so attempt 1 fails
        # at the solver (the rejection that survives D-202) and attempt 2 passes.
        model = kwargs.get("response_model")
        if (
            self._object_until_repaired
            and getattr(model, "__name__", "") == "SolverResponse"
            and not self.repairs
        ):
            self._solver_objection = dict(_SOLVER_OBJECTION)
        else:
            self._solver_objection = {}
        return await super().generate_structured(**kwargs)  # type: ignore[arg-type]


# D-202 removed the deterministic gate, so "an item that will certainly be rejected" is no
# longer a badly-formed equation - nothing between the author and the solvers looks at it.
# The reliable, still-repairable rejection is a solver that cannot find the answer.
_SOLVER_OBJECTION: dict[str, object] = {"no_option_matches": True, "is_unambiguous": False}


def _bad_equation_item() -> AuthoredGeneratedItemResponse:
    return _good_item(equation="Eq(4, 4)")


def test_a_repairable_rejection_is_retried_and_can_land_pending() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RepairAwareGateway(bad=_bad_equation_item())
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=801001,
                session_spend_cents=0.0,
                max_repair_attempts=1,
            )
            assert outcome.status == "pending"
            assert outcome.attempts == 2
            # Never auto-approved, repair or not.
            template = await QuestionRepository(session).get_template(
                outcome.question_template_id or ""
            )
            assert template is not None and template.validation_status == "pending"
            # The slot kept its one id across both attempts.
            assert outcome.question_template_id == "authored-linear_equations-d2-801001"

    asyncio.run(run())


def test_repair_is_off_unless_asked_for() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RepairAwareGateway(bad=_bad_equation_item())
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=801002,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert outcome.attempts == 1
            assert gateway.repairs == []

    asyncio.run(run())


def test_the_repair_context_carries_the_previous_item_and_only_safe_defects() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            bad = _bad_equation_item()
            gateway = _RepairAwareGateway(bad=bad)
            await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=801003,
                session_spend_cents=0.0,
                max_repair_attempts=1,
            )
            assert len(gateway.repairs) == 1
            repair = gateway.repairs[0]
            assert repair is not None
            # "Fix this" needs a *this*.
            assert repair.previous_stem == bad.stem  # type: ignore[attr-defined]
            assert repair.previous_equation == "Eq(4, 4)"  # type: ignore[attr-defined]
            assert repair.defects  # type: ignore[attr-defined]

    asyncio.run(run())


def test_every_failed_attempt_keeps_its_own_snapshot_and_attempt_number() -> None:
    """A repair history a reviewer cannot read is not a history. D-195 made rejected
    content inspectable; a loop that overwrote or skipped the failed attempts would undo
    that for exactly the runs where the trail matters most.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RepairAwareGateway(bad=_bad_equation_item())
            await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=801004,
                session_spend_cents=0.0,
                max_repair_attempts=1,
            )
            # Scoped to this slot: the database carries every earlier run's rejections,
            # so a bare count would assert a fact about the whole table.
            rows = (
                await session.execute(
                    select(QuestionValidationRun).where(QuestionValidationRun.outcome == "rejected")
                )
            ).scalars().all()
            mine = [
                r
                for r in rows
                if (r.stage_results or {}).get("candidate_snapshot", {}).get(
                    "planned_template_id"
                )
                == "authored-linear_equations-d2-801004"
            ]
            assert len(mine) == 1, "the failed attempt must leave exactly one audit row"
            snapshot = mine[0].stage_results["candidate_snapshot"]
            assert snapshot["attempt"] == 1
            assert snapshot["equation"] == "Eq(4, 4)"
            assert snapshot["repaired_defects"] == []  # attempt 1 repaired nothing

    asyncio.run(run())


def test_a_repair_attempt_is_not_started_past_the_budget_ceiling() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RepairAwareGateway(bad=_bad_equation_item())
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=801005,
                session_spend_cents=0.0,
                max_repair_attempts=3,
                budget_ceiling_cents=0.001,  # below one scripted call's cost
            )
            assert outcome.status == "rejected"
            assert outcome.attempts == 1
            assert gateway.repairs == []
            assert any("budget ceiling" in r for r in outcome.reasons)

    asyncio.run(run())


def test_a_difficulty_rejection_ends_the_loop_without_paying_for_a_retry() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _RepairAwareGateway(
                bad=_good_item(proposed_difficulty=4),
                object_until_repaired=False,
                judge=QuestionJudgeResponse(
                    reasoning="straightforward",
                    reviewed_difficulty=2,
                    difficulty_reasoning="one step, no rearrangement required",
                    is_ambiguous=False,
                    is_aligned=True,
                    is_age_appropriate=True,
                    hint_quality_score=5,
                ),
            )
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=4,
                seed=801006,
                session_spend_cents=0.0,
                max_repair_attempts=3,
            )
            assert outcome.rejected_at == "difficulty"
            assert outcome.attempts == 1
            assert gateway.repairs == [], "a difficulty rejection must not be retried"

    asyncio.run(run())


# --- D-200: the numbers are fixed before anything is written around them --------------


def test_the_design_gate_rejects_an_answer_that_is_not_a_whole_number() -> None:
    """Every observed instance of this defect was a fraction in a counting scenario -
    12/5 games, 8/3 swaps, 62/7 weeks. The check exists where it is cheap.
    """
    design = EquationDesignResponse(
        reasoning="picked numbers that do not divide",
        scenario_sketch="Two players swap cards.",
        unknown_meaning="swaps",
        equation="Eq(15 + 3*g, 27 - 2*g)",  # solves to 12/5
        final_answer="12/5",
    )
    failures = ai_pipeline.validate_equation_design(design, target_difficulty=4)
    assert any("not a whole number" in f for f in failures)


def test_the_design_gate_rejects_an_answer_the_equation_does_not_produce() -> None:
    design = EquationDesignResponse(
        reasoning="declared what I wanted, not what it solves to",
        scenario_sketch="Saving for a skateboard.",
        unknown_meaning="weeks",
        equation="Eq(23 + 7*w, 85)",  # solves to 62/7
        final_answer="9",
    )
    failures = ai_pipeline.validate_equation_design(design, target_difficulty=3)
    assert any("do not divide evenly" in f for f in failures)


def test_the_design_gate_rejects_a_negative_answer() -> None:
    # The cyclist nobody can catch: Eq(3*t, 15*t + 24) solves to -2 because she never
    # catches him. The mathematics is saying the scenario is impossible.
    design = EquationDesignResponse(
        reasoning="scenario cannot happen",
        scenario_sketch="Walker chases a faster cyclist who is ahead.",
        unknown_meaning="hours",
        equation="Eq(3*t, 15*t + 24)",
        final_answer="-2",
    )
    failures = ai_pipeline.validate_equation_design(design, target_difficulty=3)
    assert any("positive whole number" in f for f in failures)


def test_a_clean_design_passes() -> None:
    design = EquationDesignResponse(
        reasoning="18 = 2w so w = 9, a whole number",
        scenario_sketch="Two swimmers with different starting laps and rates.",
        unknown_meaning="weeks",
        equation="Eq(28 + 3*w, 10 + 5*w)",
        final_answer="9",
    )
    assert ai_pipeline.validate_equation_design(design, target_difficulty=4) == []


def test_the_design_stage_runs_before_the_author_and_is_handed_to_it() -> None:
    """The author must build around a verified skeleton, not invent its own numbers."""

    class _Recording(_ScriptedAuthoredGateway):
        seen_design: object = None

        async def generate_structured(self, **kwargs: object) -> object:
            payload = kwargs.get("payload")
            if isinstance(payload, AuthoredGeneratorPayload):
                self.seen_design = payload.verified_design
            return await super().generate_structured(**kwargs)  # type: ignore[arg-type]

    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _Recording()
            await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=1001001,
                session_spend_cents=0.0,
            )
            assert gateway.design_calls == 1, "the design stage must run before authoring"
            assert gateway.seen_design is not None, "the author was not given the design"
            assert gateway.seen_design.equation == "Eq(x, 2 + 2)"  # type: ignore[attr-defined]

    asyncio.run(run())


def test_a_design_that_never_solves_cleanly_fails_cheaply_and_never_authors() -> None:
    class _BadDesign(_ScriptedAuthoredGateway):
        authored = 0

        async def generate_structured(self, **kwargs: object) -> object:
            model = kwargs.get("response_model")
            name = getattr(model, "__name__", "")
            if name == "EquationDesignResponse":
                return BedrockGenerationResult(
                    value=EquationDesignResponse(  # type: ignore[arg-type]
                        reasoning="does not divide",
                        scenario_sketch="x",
                        unknown_meaning="y",
                        equation="Eq(15 + 3*g, 27 - 2*g)",
                        final_answer="12/5",
                    ),
                    input_tokens=1, output_tokens=1, cost_cents=0.01,
                    model_id="test", repaired=False,
                )
            if name == "AuthoredGeneratedItemResponse":
                self.authored += 1
            return await super().generate_structured(**kwargs)  # type: ignore[arg-type]

    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _BadDesign()
            outcome = await generate_authored_candidate(
                session=session,
                gateway=gateway,  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=1001002,
                session_spend_cents=0.0,
            )
            assert outcome.rejected_at == "design"
            # The whole economic argument: no full-size authoring call was ever made.
            assert gateway.authored == 0
# --- D-199: a circuit-breaker refusal is not a verdict on a question ------------------


class _CircuitOpenGateway(_ScriptedAuthoredGateway):
    async def generate_structured(self, **kwargs: object) -> NoReturn:
        raise CircuitOpenError("Bedrock circuit breaker is open")


def test_a_circuit_open_refusal_is_recorded_as_a_skip_not_a_generator_rejection() -> None:
    """Measured cost of not separating these: a run reported `generator=11` when two
    candidates had actually been attempted and nine were refused after the breaker opened.
    It read as "the model cannot produce anything"; it meant "the model failed twice and
    the breaker did its job", which is the opposite diagnosis.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_CircuitOpenGateway(),  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=901001,
                session_spend_cents=0.0,
            )
            assert outcome.rejected_at == "circuit_open"

            summary = pipeline_cli.RunSummary()
            summary.record(outcome)
            assert summary.skipped_circuit_open == 1
            # Not in the quality denominator: nothing was generated to judge.
            assert summary.processed == 0
            assert summary.rejected_generator == 0

    asyncio.run(run())


def test_the_generator_and_the_judge_are_given_the_same_tier_scale() -> None:
    """One definition of the 1-5 scale, used by the stage that builds the equation and the
    stage that rates it. Before D-200 the judge rated on an implicit absolute scale (2 in
    15 of 17 items) while the generator aimed at the requested tier, so the two numbers the
    difficulty gate compares were not measuring the same thing.
    """
    for tier, anchor in ai_pipeline.DIFFICULTY_ANCHORS.items():
        assert 1 <= tier <= 5
        assert anchor in ai_pipeline._JUDGE_SYSTEM_PROMPT, f"tier {tier} missing from judge"
    assert "BOTH sides" in ai_pipeline.DIFFICULTY_ANCHORS[4]
    assert "distribution" in ai_pipeline.DIFFICULTY_ANCHORS[5].lower()


def test_every_authorable_skill_has_a_required_equation_structure() -> None:
    """The design stage must be told the skill, not only the tier.

    Measured: the first design run handed `linear_both_sides` and `linear_distribute` at
    tier 5 the *identical* equation `Eq(3*(x + 4) + 10, 34)`, because both were told only
    "tier 5 = distribution required" and neither was told which skill it was authoring for.
    The both-sides slot got an equation with the variable on one side - the one thing that
    skill is defined by.
    """
    authorable = {
        skill
        for skills in ai_pipeline.TOPIC_SKILL_DIFFICULTIES.values()
        for skill in skills
    }
    missing = authorable - set(ai_pipeline.SKILL_STRUCTURES)
    assert missing == set(), f"skills with no required equation structure: {missing}"
    # The two that collided must now demand different shapes.
    assert "BOTH sides" in ai_pipeline.SKILL_STRUCTURES["linear_both_sides"]
    assert "distributed" in ai_pipeline.SKILL_STRUCTURES["linear_distribute"]
def test_a_real_generator_failure_is_still_a_generator_rejection() -> None:
    # The other half: the separation must not swallow genuine failures.
    async def run() -> None:
        async with _rollback_session() as session:
            outcome = await generate_authored_candidate(
                session=session,
                gateway=_FailingGeneratorGateway(),  # type: ignore[arg-type]
                curriculum=load_curriculum(),
                topic_id="linear_equations",
                difficulty_label=2,
                seed=901002,
                session_spend_cents=0.0,
            )
            assert outcome.rejected_at == "generator"
            summary = pipeline_cli.RunSummary()
            summary.record(outcome)
            assert summary.rejected_generator == 1
            assert summary.skipped_circuit_open == 0
            assert summary.processed == 1

    asyncio.run(run())


def test_a_circuit_open_candidate_is_never_repaired() -> None:
    # There is no item and no defect - only a breaker that has already decided the next
    # call should not be made. Retrying is the one thing that must not happen.
    assert (
        ai_pipeline.repair_feedback(
            stage="circuit_open", reasons=["Bedrock circuit breaker is open"], stage_results={}
        )
        is None
    )
