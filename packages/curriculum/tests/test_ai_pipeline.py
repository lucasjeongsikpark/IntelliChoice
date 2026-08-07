"""SPEC §5.8.3 AI question-generation pipeline tests.

Uses a `_ScriptedGateway` test double rather than `MockBedrockProvider`: the mock's
solver always returns option "a", which won't match a variant's shuffled correct option,
so it can't exercise the real solver-agreement gate. `_ScriptedGateway.solver` actually
solves the rendered equation by substitution (an honest "independent solver"), and each
stage is overridable so the reject-path tests can inject a disagreeing solver or a
flagging reviewer.

Every test runs against the real Compose Postgres via the same rollback-session pattern
as test_loader.py (D-013), since the pipeline's dedup check and persistence both need a
real session. Skips cleanly when Postgres is unreachable (D-008).
"""

import asyncio
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

import pytest
from intellichoice_curriculum import ai_pipeline
from intellichoice_curriculum.ai_pipeline import PipelineConfigError, generate_candidate
from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.engine import create_engine
from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    VARIANT_ORIGIN_RUNTIME,
    QuestionTemplate,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AlignmentReviewResponse,
    AmbiguityReviewResponse,
    BedrockGenerationResult,
    DifficultyReviewResponse,
    EmbeddingResult,
    GeneratedTemplateResponse,
    GeneratorPayload,
    SolverPayload,
    SolverResponse,
)
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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


# --- honest substitution solver ------------------------------------------------
def _evaluate_equation(rendered_question: str, x_value: int) -> tuple[float, float]:
    """Parses 'Solve for x: LHS = RHS' and evaluates both sides for a candidate x.
    Handles the implicit multiplication in every registered linear_equations shape
    ('5x' -> '5*x', '3(x' -> '3*(x').
    """
    _, _, body = rendered_question.partition(":")
    lhs_str, _, rhs_str = body.partition("=")

    def _prep(side: str) -> str:
        side = re.sub(r"(\d)x", r"\1*x", side)
        side = re.sub(r"(\d)\(", r"\1*(", side)
        return side.replace("x", f"({x_value})")

    lhs = eval(_prep(lhs_str), {"__builtins__": {}}, {})  # noqa: S307 - test-only, sanitized
    rhs = eval(_prep(rhs_str), {"__builtins__": {}}, {})  # noqa: S307
    return float(lhs), float(rhs)


def _solve_option(payload: SolverPayload) -> str:
    options = {
        "a": payload.option_a,
        "b": payload.option_b,
        "c": payload.option_c,
        "d": payload.option_d,
    }
    for letter, text_value in options.items():
        lhs, rhs = _evaluate_equation(payload.rendered_question, int(text_value))
        if abs(lhs - rhs) < 1e-9:
            return letter
    raise AssertionError("no option satisfied the equation - variant generation bug")


def _default_generator(payload: GeneratorPayload) -> GeneratedTemplateResponse:
    return GeneratedTemplateResponse(
        shape_key=payload.allowed_shape_keys[0],
        correct_option_generator=payload.allowed_correct_option_generators[0],
        distractor_generator_keys=payload.allowed_distractor_generator_keys[:3],
        common_error_tags=["test_tag"],
        estimated_time_seconds=40,
    )


class _ScriptedGateway:
    """Per-stage-overridable test gateway. Defaults produce a valid, passing candidate."""

    def __init__(
        self,
        *,
        generator: Callable[[GeneratorPayload], GeneratedTemplateResponse] | None = None,
        solver: Callable[[SolverPayload], str] | None = None,
        difficulty: int | None = None,
        is_ambiguous: bool = False,
        is_aligned: bool = True,
    ) -> None:
        self._generator = generator or _default_generator
        self._solver = solver or _solve_option
        self._difficulty = difficulty
        self._is_ambiguous = is_ambiguous
        self._is_aligned = is_aligned

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
        if name == "GeneratedTemplateResponse":
            assert isinstance(payload, GeneratorPayload)
            value: BaseModel = self._generator(payload)
        elif name == "SolverResponse":
            assert isinstance(payload, SolverPayload)
            value = SolverResponse(
                reasoning="scripted solver",
                selected_option=self._solver(payload),  # type: ignore[arg-type]
            )
        elif name == "DifficultyReviewResponse":
            from intellichoice_shared.bedrock import DifficultyReviewPayload

            assert isinstance(payload, DifficultyReviewPayload)
            proposed = payload.proposed_difficulty
            value = DifficultyReviewResponse(
                difficulty_label=self._difficulty if self._difficulty is not None else proposed
            )
        elif name == "AmbiguityReviewResponse":
            value = AmbiguityReviewResponse(is_ambiguous=self._is_ambiguous)
        elif name == "AlignmentReviewResponse":
            value = AlignmentReviewResponse(is_aligned=self._is_aligned)
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
        raise NotImplementedError("this fake never embeds - the AI pipeline only generates")


def test_passing_candidate_lands_pending_then_activates_to_active() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=987654,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending"
            assert outcome.cost_cents > 0  # six real calls were accounted for
            assert outcome.question_template_id is not None

            repo = QuestionRepository(session)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            # Never auto-approved: passing every check yields "pending", not "approved".
            assert template.validation_status == "pending"
            assert template.active_status == "active"

            # A pending template is NOT yet deliverable (get_active_questions filters
            # validation_status == "approved").
            active_before = await repo.get_active_questions("linear_equations", difficulty=2)
            active_ids_before = {t.question_template_id for t in active_before}
            assert outcome.question_template_id not in active_ids_before

            # Explicit activation is the only path to "approved".
            await repo.activate_template(outcome.question_template_id)
            template = await repo.get_template(outcome.question_template_id)
            assert template is not None
            assert template.validation_status == "approved"
            # D-210: approved is no longer the same as servable. This template comes from
            # the S9 *shape* pipeline, and the serving path now returns authored word
            # problems only - so what activation still guarantees is the status above, and
            # what it deliberately no longer guarantees is an appearance here.
            #
            # Asserted in both directions rather than deleted: silently dropping the second
            # half would hide that the shape pipeline's output is now unservable, which is a
            # consequence of the decision that someone reading this test should meet.
            active_after = await repo.get_active_questions("linear_equations", difficulty=2)
            assert outcome.question_template_id not in {
                t.question_template_id for t in active_after
            }
            assert all(t.authoring_mode == "authored" for t in active_after)

    asyncio.run(run())


def test_solver_disagreement_rejects_without_persisting() -> None:
    async def run() -> None:
        curriculum = load_curriculum()

        def _wrong_solver(payload: SolverPayload) -> str:
            correct = _solve_option(payload)
            return "a" if correct != "a" else "b"

        # A large, distinctive seed (not a small round number like the original
        # 424242) so the generated rendered_question doesn't coincidentally collide
        # with one of the 50 hand-authored seed-bank templates from S4's
        # curriculum-load - a collision makes the dedup check reject the candidate for
        # "duplicate rendered_question" before it ever reaches the solver-agreement
        # check this test means to exercise (see docs/PROGRESS.md's known-red-test note).
        seed = 700666
        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(solver=_wrong_solver),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=3,
                seed=seed,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("solver disagreement" in r for r in outcome.reasons)
            assert outcome.question_template_id is None
            repo = QuestionRepository(session)
            assert await repo.get_template(f"ai-linear_equations-d3-{seed}") is None

    asyncio.run(run())


# The reviewer-flag tests use difficulty 4 (the `both_sides` shape's parameter space is
# vast) with large distinctive seeds, so the deterministic dedup check - which runs
# *before* the reviewers - can't coincidentally reject the candidate first by colliding
# with a sample variant `make curriculum-load` may have persisted into this dev DB.
def test_ambiguity_reviewer_flag_rejects() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(is_ambiguous=True),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=4,
                seed=700111,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("ambiguity" in r for r in outcome.reasons)
            repo = QuestionRepository(session)
            assert await repo.get_template("ai-linear_equations-d4-700111") is None

    asyncio.run(run())


def test_alignment_reviewer_flag_rejects() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(is_aligned=False),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=4,
                seed=700222,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("alignment" in r for r in outcome.reasons)

    asyncio.run(run())


def test_difficulty_reviewer_far_off_rejects() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(difficulty=1),  # proposed 4, reviewer says 1
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=4,
                seed=700333,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("difficulty reviewer" in r for r in outcome.reasons)

    asyncio.run(run())


def test_generator_proposing_unregistered_shape_rejects() -> None:
    async def run() -> None:
        curriculum = load_curriculum()

        def _bad_generator(payload: GeneratorPayload) -> GeneratedTemplateResponse:
            # A hallucinated shape key the registry has never heard of (D-015 boundary):
            # the model can never make the pipeline execute unknown solve logic.
            return GeneratedTemplateResponse(
                shape_key="quadratic_formula_from_the_model",
                correct_option_generator=payload.allowed_correct_option_generators[0],
                distractor_generator_keys=payload.allowed_distractor_generator_keys[:3],
                common_error_tags=[],
                estimated_time_seconds=40,
            )

        async with _rollback_session() as session:
            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(generator=_bad_generator),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=1,
                seed=444,
                session_spend_cents=0.0,
            )
            assert outcome.status == "rejected"
            assert any("unregistered/off-difficulty shape" in r for r in outcome.reasons)

    asyncio.run(run())


def test_duplicate_rendered_question_rejects() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            # First candidate passes and is persisted (pending).
            first = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=555000,
                session_spend_cents=0.0,
            )
            assert first.status == "pending"

            # Same seed reproduces the identical rendered_question -> dedup rejects it.
            second = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=555000,
                session_spend_cents=0.0,
            )
            assert second.status == "rejected"
            assert any("duplicate" in r for r in second.reasons)

    asyncio.run(run())


def test_runtime_variant_with_identical_text_does_not_block_the_pipeline() -> None:
    """S40 regression (D-106), the negative arm of the test above.

    A *runtime* variant carrying the identical `rendered_question` must not reject the
    candidate, where a canonical one must. Before this fix `rendered_question_exists`
    compared against every row in `question_variants`, which includes the instance the
    exam builder mints for every question ever served - so the pipeline's verdict on a
    candidate drifted with how much the app had been used. That produced four false
    "duplicate rendered_question" rejections across S17, S22, S31 and S40, each one
    masking the check the failing test actually meant to exercise, and each one "fixed"
    by deleting the offending row.

    The two arms have to be read together: scoping the check too far would silently
    disable deduplication altogether, and only `test_duplicate_rendered_question_rejects`
    would notice.
    """

    async def run() -> None:
        curriculum = load_curriculum()
        seed = 771337

        # Pass 1: discover what this seed renders, then throw the whole thing away.
        async with _rollback_session() as session:
            probe = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=seed,
                session_spend_cents=0.0,
            )
            assert probe.status == "pending", probe.reasons
            assert probe.question_variant_id is not None
            variant = await QuestionRepository(session).get_variant(probe.question_variant_id)
            assert variant is not None
            rendered = variant.rendered_question
            # The pipeline's own write must be canonical, or the arm above is vacuous.
            assert variant.origin == VARIANT_ORIGIN_CANONICAL

        # Pass 2: same seed, but the text now already exists as a runtime instance of a
        # different, already-approved template - exactly the shape that kept recurring.
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            host = (await repo.get_active_questions("linear_equations", difficulty=2))[0]
            await repo.create_variant(
                QuestionVariant(
                    origin=VARIANT_ORIGIN_RUNTIME,
                    question_template_id=host.question_template_id,
                    random_seed=1,
                    rendered_question=rendered,
                    option_a="1",
                    option_b="2",
                    option_c="3",
                    option_d="4",
                    correct_option="a",
                    parameter_values={},
                )
            )
            assert not await repo.rendered_question_exists(rendered)

            outcome = await generate_candidate(
                session=session,
                gateway=_ScriptedGateway(),
                curriculum=curriculum,
                topic_id="linear_equations",
                difficulty_label=2,
                seed=seed,
                session_spend_cents=0.0,
            )
            assert outcome.status == "pending", outcome.reasons
            assert not any("duplicate" in r for r in outcome.reasons)

    asyncio.run(run())


def test_activate_template_refuses_a_non_pending_template() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            repo = QuestionRepository(session)
            # A template already rejected by the pipeline can never be activated.
            rejected = QuestionTemplate(
                question_template_id="test-rejected-tpl",
                curriculum_version="2026.1",
                topic_id="linear_equations",
                skill_id="linear_one_step",
                grade_band="6-7",
                difficulty_label=1,
                parameter_schema={"b": {"min": 1, "max": 9}, "x": {"min": 1, "max": 9}},
                solution_function="one_step_add",
                correct_option_generator="format_integer",
                distractor_generators=["distractor_off_by_one"],
                estimated_time_seconds=25,
                generator_model="test",
                validation_status="rejected",
                active_status="active",
            )
            await repo.create_template(rejected)
            with pytest.raises(ValueError, match="only a pending template"):
                await repo.activate_template("test-rejected-tpl")

    asyncio.run(run())


def test_unconfigured_topic_raises_pipeline_config_error() -> None:
    async def run() -> None:
        curriculum = load_curriculum()
        async with _rollback_session() as session:
            with pytest.raises(PipelineConfigError):
                await generate_candidate(
                    session=session,
                    gateway=_ScriptedGateway(),
                    curriculum=curriculum,
                    topic_id="fraction_operations",  # no registered shapes yet
                    difficulty_label=1,
                    seed=1,
                    session_spend_cents=0.0,
                )

    asyncio.run(run())


def test_module_exposes_shapes_for_every_registered_difficulty() -> None:
    # A light guard that DIFFICULTY_SHAPES/TOPIC_DIFFICULTY_SKILLS stay in sync.
    for difficulty in range(1, 6):
        assert ai_pipeline.DIFFICULTY_SHAPES["linear_equations"][difficulty]
        assert ai_pipeline.TOPIC_DIFFICULTY_SKILLS["linear_equations"][difficulty]
