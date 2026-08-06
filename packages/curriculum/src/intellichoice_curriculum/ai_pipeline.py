"""SPEC §5.8.3 AI question-generation pipeline (S9), offline only - never called from a
runtime request path (CLAUDE.md non-negotiable #2, "no runtime NL2SQL" - by extension, no
runtime LLM authoring of graded content either).

```
Curriculum Topic -> Generator Agent -> Structured Question Template
  -> Solver Agent A -> Solver Agent B
  -> Difficulty Reviewer -> Ambiguity Reviewer -> Curriculum Alignment Reviewer
  -> Deterministic/Executable Validation -> Deduplication -> Activate or Quarantine
```

Design choices worth knowing before reading the code (see DECISIONS.md D-026):

- The Generator Agent picks a *shape key* from an explicit, difficulty-scoped allowlist
  (`DIFFICULTY_SHAPES`) - it never invents solving logic (D-015). Numeric parameter
  bounds are NOT requested from the model at all; `SHAPE_PARAMETER_BOUNDS` supplies them
  deterministically by shape, keeping magnitude a code-owned property (§5.8.4 lists
  "numerical magnitude" as one of several *deterministic complexity features*, not
  something an LLM should choose freely).
- Every model-proposed string (shape_key, correct_option_generator,
  distractor_generator_keys) is re-validated against the same registry the deterministic
  loader uses before it's trusted - a bad/hallucinated key rejects the candidate, it is
  never passed through to `generate_variant`.
- Solver A/B agreement is checked as *selected option letter*, not free-text answer
  matching - avoids formatting ambiguity, mirrors §5.8.4's "independent solver
  agreement" and this project's existing `generate_solution` answer-verification pattern
  (`learning_api/services/tutor.py`).
- A candidate that passes every automated check lands at `validation_status="pending"`,
  never auto-`"approved"` - see `QuestionRepository.activate_template` for why.
- Currently only `linear_equations` has registered shapes (D-003/D-015); calling this for
  any other topic_id raises `PipelineConfigError` rather than silently doing nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from intellichoice_db.models.questions import (
    VARIANT_ORIGIN_CANONICAL,
    QuestionTemplate,
    QuestionValidationRun,
    QuestionVariant,
)
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_shared.bedrock import (
    AlignmentReviewPayload,
    AlignmentReviewResponse,
    AmbiguityReviewPayload,
    AmbiguityReviewResponse,
    AuthoredGeneratedItemResponse,
    AuthoredGeneratorPayload,
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    DifficultyReviewPayload,
    DifficultyReviewResponse,
    GeneratedTemplateResponse,
    GeneratorPayload,
    QuestionJudgePayload,
    QuestionJudgeResponse,
    SolverPayload,
    SolverResponse,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_curriculum.content import CurriculumContent
from intellichoice_curriculum.generation import VariantGenerationError, generate_variant
from intellichoice_curriculum.templates.model import QuestionTemplateDef
from intellichoice_curriculum.templates.registry import (
    CORRECT_OPTION_GENERATORS,
    DISTRACTOR_GENERATORS,
)
from intellichoice_curriculum.validation import validate_variant

# topic_id -> difficulty_label -> skill_id. Deterministic, not LLM-chosen: this topic's
# skill ladder tracks difficulty 1:1 (matches the S4 hand-authored bank exactly - see
# curriculum/internal_math/skills.yaml's comment and templates/linear_equations.py).
TOPIC_DIFFICULTY_SKILLS: dict[str, dict[int, str]] = {
    "linear_equations": {
        1: "linear_one_step",
        2: "linear_two_step",
        3: "linear_neg_frac_coeff",
        4: "linear_both_sides",
        5: "linear_distribute",
    }
}

# topic_id -> skill_id -> the difficulty tiers that skill should carry content at.
#
# D-186: the authoring plan, and the reason it is a *second* map rather than an inversion
# of the one above. `TOPIC_DIFFICULTY_SKILLS` stays the **native** ladder - each skill's
# home tier, the default when no skill is named, and still 1:1. This map says which tiers
# each skill should additionally be authored at, and it is deliberately not uniform:
#
#   - The three middle skills carry their native tier ±1. `mastery_bootstrap` anchors
#     `recommended_difficulty` on the modal assessed tier ±1 and clamps to 1-5, so T±1 is
#     the entire range a skill can ever be recommended at - a fourth tier could not be
#     selected by any student.
#   - The ladder ends (`linear_one_step` at 1, `linear_distribute` at 5) stay single-tier.
#     The clamp means tier 1's neighbour below and tier 5's neighbour above do not exist,
#     and the user's call was multi-tier "for the middle skills".
#
# **Authored mode only.** The shape pipeline picks from `DIFFICULTY_SHAPES`, which is keyed
# by tier alone, so a skill generated at an off-native tier would be handed another skill's
# math forms (`linear_two_step` at tier 3 would get `frac_coeff`/`neg_coeff`). Authored mode
# has no shape allowlist - it generates a real stem from the skill and tier - which is why
# multi-tier lives there and `run_pipeline` is untouched.
TOPIC_SKILL_DIFFICULTIES: dict[str, dict[str, list[int]]] = {
    "linear_equations": {
        "linear_one_step": [1],
        "linear_two_step": [1, 2, 3],
        "linear_neg_frac_coeff": [2, 3, 4],
        "linear_both_sides": [3, 4, 5],
        "linear_distribute": [5],
    }
}

# topic_id -> difficulty_label -> shape keys the Generator Agent may choose among.
DIFFICULTY_SHAPES: dict[str, dict[int, list[str]]] = {
    "linear_equations": {
        1: ["one_step_add", "one_step_sub", "one_step_mul"],
        2: ["two_step", "two_step_sub_b"],
        3: ["frac_coeff", "neg_coeff"],
        4: ["both_sides", "both_sides_alt"],
        5: ["distribute_simple", "distribute_combine"],
    }
}


def _bounds(min_: int, max_: int, exclude: list[int] | None = None) -> dict:
    spec: dict = {"min": min_, "max": max_}
    if exclude:
        spec["exclude"] = exclude
    return spec


# Deterministic per-shape parameter bounds (see module docstring) - one safe default per
# shape, grade-appropriate magnitude, guaranteed by construction to avoid the zero
# coefficients each shape's `solve` divides by.
SHAPE_PARAMETER_BOUNDS: dict[str, dict] = {
    "one_step_add": {"b": _bounds(1, 20), "x": _bounds(1, 20, [0])},
    "one_step_sub": {"b": _bounds(1, 20), "x": _bounds(1, 20, [0])},
    "one_step_mul": {"a": _bounds(2, 12, [0, 1]), "x": _bounds(1, 20, [0])},
    "two_step": {"a": _bounds(2, 12, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "two_step_sub_b": {"a": _bounds(2, 12, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "frac_coeff": {
        "d": _bounds(2, 6, [0, 1]),
        "b": _bounds(1, 20),
        "x_over_d": _bounds(-9, 9, [0]),
    },
    "neg_coeff": {"a": _bounds(2, 6, [0]), "b": _bounds(1, 20), "x": _bounds(-9, 9, [0])},
    "both_sides": {
        "a": _bounds(2, 10, [0]),
        "d": _bounds(2, 10, [0]),
        "b": _bounds(1, 20),
        "x": _bounds(-9, 9, [0]),
    },
    "both_sides_alt": {
        "a": _bounds(2, 10, [0]),
        "d": _bounds(2, 10, [0]),
        "b": _bounds(1, 20),
        "x": _bounds(-9, 9, [0]),
    },
    "distribute_simple": {
        "a": _bounds(2, 10, [0, 1]),
        "b": _bounds(1, 15),
        "x": _bounds(-9, 9, [0]),
    },
    "distribute_combine": {
        "a": _bounds(2, 8, [0]),
        "d": _bounds(-8, 8, [0]),
        "b": _bounds(1, 15),
        "x": _bounds(-9, 9, [0]),
    },
}

_REQUIRED_DISTRACTOR_COUNT = 3  # 4 options total: 1 correct + 3 distractors.

_GENERATOR_SYSTEM_PROMPT = (
    "You are a math question generator for a K-12 curriculum. Given a topic, skill, "
    "grade band, and target difficulty, choose ONE equation shape and metadata from the "
    "allowed lists provided. Never propose a shape, generator, or distractor key that "
    "isn't in the allowed lists."
)
_SOLVER_SYSTEM_PROMPT = (
    "You are an independent math solver. Solve the given question and select the "
    "letter of the one option that matches your answer."
)
_DIFFICULTY_SYSTEM_PROMPT = (
    "You are an independent difficulty reviewer for a K-12 math question bank. Rate the "
    "question's difficulty from 1 (easiest) to 5 (hardest), independent of the proposed "
    "label."
)
_AMBIGUITY_SYSTEM_PROMPT = (
    "You are reviewing a multiple-choice math question for ambiguity - wording that "
    "could reasonably support more than one option, or that is unclear to a K-12 "
    "student."
)
_ALIGNMENT_SYSTEM_PROMPT = (
    "You are reviewing whether a math question is correctly aligned to its stated "
    "topic and skill for a K-12 curriculum."
)

_MAX_TOKENS = 400

# S20 authored mode's responses are far larger than S9's shape-mode ones, and the single
# shared ceiling above made authored generation *impossible* rather than merely tight -
# silently, because nothing exercised it under a real model until now. Measured against
# real Bedrock (Haiku 4.5, 2026-08-05): a complete `AuthoredGeneratedItemResponse` runs
# 631 output tokens at tier 1 and 954 at tier 5, so 400 truncated every candidate at the
# generator stage, before the deterministic gate ever ran. Sized with headroom above the
# measured worst case rather than at it - the ceiling is a runaway guard, not a budget,
# since output tokens bill by actual use.
_AUTHORED_ITEM_MAX_TOKENS = 1600
# Solver and judge responses are a few small fields plus a free-text `reasoning` (the
# generator's ran ~660 characters at tier 5, i.e. well inside 400 on its own). Not observed
# truncating, but a judge truncated by this ceiling discards a candidate that has already
# paid for four calls, so they get modest headroom for the same reason.
_AUTHORED_REVIEW_MAX_TOKENS = 800

# --- S20 authored generation mode (plan §7) -----------------------------------------

_AUTHORED_GENERATOR_SYSTEM_PROMPT = (
    "You are an expert K-12 math item writer. Given a topic, skill, grade band, and "
    "target difficulty, write ONE original multiple-choice question: a clear stem, an "
    "optional short context block (a scenario or table) if it helps, four distinct "
    "options with exactly one correct, a SymPy-parseable answer_expression when the "
    "answer is a computable value, a 3-level hint ladder that progressively guides "
    "without ever stating the final answer, a worked canonical solution whose final "
    "answer matches the correct option exactly, and a misconception tag per distractor. "
    "Follow the style of the exemplars provided. Never leak the answer in the stem or "
    "any hint. "
    # The deterministic gate re-solves `answer_expression` and compares it to the
    # options' own text, so an option that does not parse as a value cannot be confirmed
    # correct. The first real run lost six of eleven candidates to exactly this - correct
    # answers written as "x = 7" or with a typographic minus - so the format is stated
    # rather than left implied. `_normalize_math_text` now also repairs both cases at the
    # parse site; asking here as well keeps the item text itself clean, since the stored
    # option text is what students and downstream text checks actually see.
    "When answer_expression is given, write each option as a bare value with no variable "
    "and no equals sign ('7', not 'x = 7'), and use the ASCII hyphen '-' for negatives, "
    "never a typographic minus."
)
_JUDGE_SYSTEM_PROMPT = (
    "You are an independent judge reviewing one authored K-12 math question for "
    "difficulty fit, ambiguity, curriculum alignment, age-appropriateness, and the "
    "quality of its hint ladder. Be strict: a genuinely ambiguous, misaligned, or "
    "unsafe question must be flagged. "
    # Left unstated until 2026-08-05, when the first real run showed the judge inventing a
    # 1-10 scale and scoring 8-9 on every item - which sits above both thresholds below,
    # so the hint-quality gate silently never fired. The schema now bounds the field too;
    # this states the same contract in the place the model is most likely to follow it.
    "Score hint_quality_score on a scale of 1 to 5, where 1 is a ladder that misleads or "
    "gives the answer away, 3 is usable but shallow, and 5 is a genuinely progressive "
    "ladder that guides without revealing. Do not use any other scale."
)

# Small, fixed set of hand-written few-shot exemplars (this project has no pre-authored
# hint/solution content to draw from - hints are otherwise only ever LLM-generated at
# request time, §5.11.4) describing the expected stem/hint-ladder/solution style. Not
# topic-specific by design so the same list works across every authored difficulty.
_AUTHORED_FEW_SHOT_EXEMPLARS: list[str] = [
    (
        "stem: 'A rectangle is 3 times as long as it is wide. If the width is 5 cm, "
        "what is the perimeter?' | hint_ladder: ['Perimeter adds up all four sides - "
        "what shape does a rectangle have?', 'Find the length first using the "
        "width-times-3 relationship.', 'Add width + length + width + length.'] | "
        "canonical_solution final_answer: '40 cm'"
    ),
    (
        "stem: 'Solve for x: 3x - 4 = 11.' | hint_ladder: ['What operation would undo "
        "subtracting 4?', 'Add 4 to both sides first, then look at what multiplies x.', "
        "'Isolate x by dividing both sides by its coefficient.'] | canonical_solution "
        "final_answer: '5'"
    ),
]

# Cosine-*distance* ceiling for the SPEC §5.8.5 authored near-duplicate check (0 =
# identical, 2 = opposite) - a placeholder pending real-embedding calibration, same
# "never exercised against real AWS" caveat as D-025/D-035/D-046: `MockBedrockProvider`'s
# hash-based vectors are high-dimensional and effectively random for unrelated text, so
# only a near-exact-text stem collides this tightly in tests.
NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD = 0.05

# SPEC §5.8.5/plan §7 judge thresholds: a genuinely low hint-quality score rejects; a
# borderline one (or a 1-off difficulty disagreement) doesn't reject but does route the
# candidate to human review first (`review_priority="high"`) rather than the ordinary
# queue. `hint_quality_score` is judged on a 1 (poor) - 5 (excellent) scale.
_HINT_QUALITY_REJECT_BELOW = 2
_HINT_QUALITY_BORDERLINE_AT = 3


class PipelineConfigError(Exception):
    """The pipeline was asked to generate for a topic/difficulty it has no registered
    shapes or skill for - a configuration gap, not a per-candidate rejection.
    """


@dataclass
class PipelineOutcome:
    status: Literal["pending", "rejected"]
    reasons: list[str] = field(default_factory=list)
    question_template_id: str | None = None
    question_variant_id: str | None = None
    cost_cents: float = 0.0


async def _call(
    gateway: BedrockGateway,
    *,
    task: BedrockTask,
    system_prompt: str,
    payload: BaseModel,
    response_model: type[BaseModel],
    session_spend_cents: float,
    max_output_tokens: int = _MAX_TOKENS,
) -> tuple[BaseModel | None, float, str | None]:
    """Thin wrapper: returns (value, cost_cents, error) instead of raising, so the
    pipeline can record *why* a candidate was rejected instead of crashing the batch run
    (SPEC §5.29-style failure handling, applied to an offline pipeline instead of a
    request path).

    `max_output_tokens` is per call site rather than per `BedrockTask` on purpose: the
    authored solvers deliberately reuse the shape pipeline's `QUESTION_GENERATION` and
    `QUESTION_REVIEW` task slots so they resolve to two different models, so the task
    alone cannot say how large a response to expect. The default keeps every shape-mode
    call at the value it has always used.
    """
    try:
        result = await gateway.generate_structured(
            task=task,
            system_prompt=system_prompt,
            payload=payload,
            response_model=response_model,
            max_output_tokens=max_output_tokens,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        return None, exc.cost_cents, str(exc)
    return result.value, result.cost_cents, None


async def generate_candidate(
    *,
    session: AsyncSession,
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    topic_id: str,
    difficulty_label: int,
    seed: int,
    session_spend_cents: float,
) -> PipelineOutcome:
    """Runs one candidate template through the full pipeline and persists the result
    (as `pending` or `rejected` - see module docstring). Returns the outcome plus the
    real cost incurred, so a caller running many candidates can track cumulative spend
    across calls (the gateway itself only guards a single call against the budget it's
    told about - see `ResilientBedrockGateway.generate_structured`).
    """
    difficulty_shapes = DIFFICULTY_SHAPES.get(topic_id, {}).get(difficulty_label)
    skill_id = TOPIC_DIFFICULTY_SKILLS.get(topic_id, {}).get(difficulty_label)
    if not difficulty_shapes or skill_id is None:
        raise PipelineConfigError(
            f"no registered shapes/skill for topic_id={topic_id!r} "
            f"difficulty_label={difficulty_label!r}"
        )
    topic = next((t for t in curriculum.topics if t.topic_id == topic_id), None)
    skill = next((s for s in curriculum.skills if s.skill_id == skill_id), None)
    if topic is None or skill is None:
        raise PipelineConfigError(f"topic/skill not in curriculum taxonomy: {topic_id}/{skill_id}")

    spend = session_spend_cents
    total_cost = 0.0

    def _spend(cost: float) -> None:
        nonlocal spend, total_cost
        spend += cost
        total_cost += cost

    # --- 1. Generator Agent -----------------------------------------------------
    gen_payload = GeneratorPayload(
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
        difficulty_label=difficulty_label,
        allowed_shape_keys=difficulty_shapes,
        allowed_correct_option_generators=list(CORRECT_OPTION_GENERATORS),
        allowed_distractor_generator_keys=list(DISTRACTOR_GENERATORS),
    )
    proposal, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_GENERATOR_SYSTEM_PROMPT,
        payload=gen_payload,
        response_model=GeneratedTemplateResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None or proposal is None:
        return PipelineOutcome(
            status="rejected", reasons=[f"generator call failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(proposal, GeneratedTemplateResponse)

    reasons: list[str] = []
    if proposal.shape_key not in difficulty_shapes:
        reasons.append(
            f"generator proposed unregistered/off-difficulty shape {proposal.shape_key!r}"
        )
    if proposal.correct_option_generator not in CORRECT_OPTION_GENERATORS:
        reasons.append(
            f"generator proposed unregistered correct_option_generator "
            f"{proposal.correct_option_generator!r}"
        )
    distractor_keys = proposal.distractor_generator_keys
    if len(distractor_keys) != _REQUIRED_DISTRACTOR_COUNT or any(
        key not in DISTRACTOR_GENERATORS for key in distractor_keys
    ):
        reasons.append(
            f"generator proposed invalid distractor_generator_keys {distractor_keys!r} "
            f"(need exactly {_REQUIRED_DISTRACTOR_COUNT} registered keys)"
        )
    if reasons:
        return PipelineOutcome(status="rejected", reasons=reasons, cost_cents=total_cost)

    parameter_schema = SHAPE_PARAMETER_BOUNDS[proposal.shape_key]
    template_def = QuestionTemplateDef(
        topic_id=topic_id,
        skill_id=skill_id,
        grade_band=topic.grade_band,
        difficulty_label=difficulty_label,
        question_type="multiple_choice",
        parameter_schema=parameter_schema,
        solution_function=proposal.shape_key,
        correct_option_generator=proposal.correct_option_generator,
        distractor_generators=distractor_keys,
        common_error_tags=proposal.common_error_tags,
        estimated_time_seconds=proposal.estimated_time_seconds,
        generator_model="bedrock-question-generation",
        review_model_versions={},
    )

    # --- 2. Deterministic variant generation + §5.8.5 executable validation -----
    try:
        variant = generate_variant(
            shape_key=proposal.shape_key,
            parameter_schema=parameter_schema,
            correct_option_generator=proposal.correct_option_generator,
            distractor_generator_keys=distractor_keys,
            seed=seed,
        )
    except VariantGenerationError as exc:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"variant generation failed: {exc}"],
            cost_cents=total_cost,
        )

    if await QuestionRepository(session).rendered_question_exists(variant.rendered_question):
        return PipelineOutcome(
            status="rejected", reasons=["duplicate rendered_question"], cost_cents=total_cost
        )

    validation = validate_variant(template_def, variant, curriculum)
    if not validation.passed:
        return PipelineOutcome(
            status="rejected", reasons=validation.failures, cost_cents=total_cost
        )

    # --- 3. Independent Solver Agents A and B ------------------------------------
    solver_payload = SolverPayload(
        rendered_question=variant.rendered_question,
        option_a=variant.option_a,
        option_b=variant.option_b,
        option_c=variant.option_c,
        option_d=variant.option_d,
    )
    solver_a, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"solver A call failed: {error}"], cost_cents=total_cost
        )
    solver_b, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"solver B call failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(solver_a, SolverResponse) and isinstance(solver_b, SolverResponse)

    if not (solver_a.selected_option == solver_b.selected_option == variant.correct_option):
        return PipelineOutcome(
            status="rejected",
            reasons=[
                "independent solver disagreement: "
                f"solver_a={solver_a.selected_option!r} solver_b={solver_b.selected_option!r} "
                f"deterministic={variant.correct_option!r}"
            ],
            cost_cents=total_cost,
        )

    # --- 4. Difficulty / Ambiguity / Curriculum-Alignment reviewers -------------
    difficulty_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_DIFFICULTY_SYSTEM_PROMPT,
        payload=DifficultyReviewPayload(
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
            skill_name=skill.name,
            proposed_difficulty=difficulty_label,
        ),
        response_model=DifficultyReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"difficulty review failed: {error}"],
            cost_cents=total_cost,
        )
    assert isinstance(difficulty_review, DifficultyReviewResponse)
    if abs(difficulty_review.difficulty_label - difficulty_label) > 1:
        return PipelineOutcome(
            status="rejected",
            reasons=[
                f"difficulty reviewer rated {difficulty_review.difficulty_label}, too far "
                f"from proposed {difficulty_label}"
            ],
            cost_cents=total_cost,
        )

    ambiguity_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_AMBIGUITY_SYSTEM_PROMPT,
        payload=AmbiguityReviewPayload(
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
        ),
        response_model=AmbiguityReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"ambiguity review failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(ambiguity_review, AmbiguityReviewResponse)
    if ambiguity_review.is_ambiguous:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"ambiguity reviewer flagged the question: {ambiguity_review.reasoning}"],
            cost_cents=total_cost,
        )

    alignment_review, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_ALIGNMENT_SYSTEM_PROMPT,
        payload=AlignmentReviewPayload(
            rendered_question=variant.rendered_question,
            topic_name=topic.name,
            skill_name=skill.name,
        ),
        response_model=AlignmentReviewResponse,
        session_spend_cents=spend,
    )
    _spend(cost)
    if error is not None:
        return PipelineOutcome(
            status="rejected", reasons=[f"alignment review failed: {error}"], cost_cents=total_cost
        )
    assert isinstance(alignment_review, AlignmentReviewResponse)
    if not alignment_review.is_aligned:
        return PipelineOutcome(
            status="rejected",
            reasons=[f"alignment reviewer flagged the question: {alignment_review.reasoning}"],
            cost_cents=total_cost,
        )

    # --- 5. Persist as pending (never auto-approved - see module docstring) -----
    repo = QuestionRepository(session)
    template_id = f"ai-{topic_id}-d{difficulty_label}-{seed}"
    template = await repo.create_template(
        QuestionTemplate(
            question_template_id=template_id,
            curriculum_version=curriculum.curriculum_version,
            topic_id=topic_id,
            skill_id=skill_id,
            grade_band=topic.grade_band,
            difficulty_label=difficulty_label,
            difficulty_confidence=1.0
            if difficulty_review.difficulty_label == difficulty_label
            else 0.5,
            question_type="multiple_choice",
            parameter_schema=parameter_schema,
            solution_function=proposal.shape_key,
            correct_option_generator=proposal.correct_option_generator,
            distractor_generators=distractor_keys,
            common_error_tags=proposal.common_error_tags,
            estimated_time_seconds=proposal.estimated_time_seconds,
            generator_model="bedrock-question-generation",
            review_model_versions={
                "difficulty": "bedrock-question-review",
                "ambiguity": "bedrock-question-review",
                "alignment": "bedrock-question-review",
            },
            validation_status="pending",
            active_status="active",
        )
    )
    persisted_variant = await repo.create_variant(
        QuestionVariant(
            # The newly authored template's defining rendering (D-106).
            origin=VARIANT_ORIGIN_CANONICAL,
            question_template_id=template.question_template_id,
            random_seed=variant.random_seed,
            rendered_question=variant.rendered_question,
            option_a=variant.option_a,
            option_b=variant.option_b,
            option_c=variant.option_c,
            option_d=variant.option_d,
            correct_option=variant.correct_option,
            parameter_values=variant.parameter_values,
        )
    )

    return PipelineOutcome(
        status="pending",
        question_template_id=template.question_template_id,
        question_variant_id=persisted_variant.question_variant_id,
        cost_cents=total_cost,
    )


async def generate_authored_candidate(
    *,
    session: AsyncSession,
    gateway: BedrockGateway,
    curriculum: CurriculumContent,
    topic_id: str,
    difficulty_label: int,
    seed: int,
    session_spend_cents: float,
    version: int = 1,
    skill_id: str | None = None,
) -> PipelineOutcome:
    """Runs one candidate through the S20 *authored* pipeline (plan §7): a real
    hand-quality stem/hint-ladder/solution instead of a parameterized shape (see this
    module's docstring for the two modes' relationship). Reuses the same
    `TOPIC_DIFFICULTY_SKILLS` topic/skill map the shape pipeline above uses (same scope
    limit - other topics raise `PipelineConfigError`, D-003/D-016). `version` lets
    `review_cli.py`'s edit-and-rerun action persist a new template that supersedes an
    existing one (plan §7 "Versioning/audit").

    Every rejection - even one before a `QuestionTemplate` row exists - is persisted as
    its own `question_validation_runs` row (`question_template_id=None` in that case;
    see the model's own docstring for why), satisfying ROADMAP S20's "rejected with
    persisted reasons" done-when criterion.
    """
    # D-186: an explicit `skill_id` is how a skill gets authored at an off-native tier.
    # Deriving from the tier is still the default and still correct for the 1:1 ladder, but
    # it *cannot* express multi-tier - once two skills share a tier the derivation has no
    # way to know which was meant, so the caller has to say. Validated against the authoring
    # plan rather than accepted verbatim: an unplanned (skill, tier) pair is a config error,
    # not a licence to generate content nothing will ever select.
    if skill_id is None:
        skill_id = TOPIC_DIFFICULTY_SKILLS.get(topic_id, {}).get(difficulty_label)
        if skill_id is None:
            raise PipelineConfigError(
                f"no registered skill for topic_id={topic_id!r} "
                f"difficulty_label={difficulty_label!r}"
            )
    else:
        planned = TOPIC_SKILL_DIFFICULTIES.get(topic_id, {}).get(skill_id)
        if planned is None:
            raise PipelineConfigError(
                f"no registered skill for topic_id={topic_id!r} skill_id={skill_id!r}"
            )
        if difficulty_label not in planned:
            raise PipelineConfigError(
                f"skill_id={skill_id!r} is not planned at difficulty_label="
                f"{difficulty_label!r} (planned: {planned})"
            )
    topic = next((t for t in curriculum.topics if t.topic_id == topic_id), None)
    skill = next((s for s in curriculum.skills if s.skill_id == skill_id), None)
    if topic is None or skill is None:
        raise PipelineConfigError(f"topic/skill not in curriculum taxonomy: {topic_id}/{skill_id}")

    spend = session_spend_cents
    total_cost = 0.0

    def _spend(cost: float) -> None:
        nonlocal spend, total_cost
        spend += cost
        total_cost += cost

    repo = QuestionRepository(session)

    async def _reject(reasons: list[str], stage_results: dict) -> PipelineOutcome:
        await repo.create_validation_run(
            QuestionValidationRun(
                question_template_id=None,
                outcome="rejected",
                stage_results=stage_results,
                reasons=reasons,
                cost_cents=total_cost,
            )
        )
        return PipelineOutcome(status="rejected", reasons=reasons, cost_cents=total_cost)

    # --- 1. Authored Generator Agent --------------------------------------------
    gen_payload = AuthoredGeneratorPayload(
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
        difficulty_label=difficulty_label,
        exemplars=_AUTHORED_FEW_SHOT_EXEMPLARS,
    )
    item, cost, error = await _call(
        gateway,
        task=BedrockTask.AUTHORED_QUESTION_GENERATION,
        system_prompt=_AUTHORED_GENERATOR_SYSTEM_PROMPT,
        payload=gen_payload,
        response_model=AuthoredGeneratedItemResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_ITEM_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None or item is None:
        return await _reject([f"authored generator call failed: {error}"], {})
    assert isinstance(item, AuthoredGeneratedItemResponse)

    rendered_question = (
        f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem
    )

    # --- 2. Deterministic gate (schema/markdown safety, SymPy solve, exactly-one- --
    # --- correct, leakage, hint-ladder monotonicity, hint/solution/answer          -
    # --- agreement, wordlist/readability - see authored_validation.py) ------------
    gate = validate_authored_item(difficulty_label, item)
    stage_results: dict = {
        "deterministic_gate": {"passed": gate.passed, "failures": gate.failures}
    }
    if not gate.passed:
        return await _reject(gate.failures, stage_results)

    if await repo.rendered_question_exists(rendered_question):
        stage_results["deduplication"] = {"passed": False, "reason": "exact text duplicate"}
        return await _reject(["duplicate rendered_question (exact text match)"], stage_results)

    # --- 3. Near-duplicate check: embed the stem, cosine-compare against every ---
    # --- other authored template's stem in this topic -----------------------------
    try:
        embed_result = await gateway.create_embedding(
            texts=[item.stem], session_spend_cents=spend
        )
    except BedrockGatewayError as exc:
        stage_results["deduplication"] = {"passed": False, "error": str(exc)}
        return await _reject([f"stem embedding call failed: {exc}"], stage_results)
    _spend(embed_result.cost_cents)
    stem_embedding = embed_result.vectors[0]
    if await repo.stem_near_duplicate_exists(
        topic_id, stem_embedding, threshold=NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD
    ):
        stage_results["deduplication"] = {
            "passed": False,
            "reason": "near-duplicate stem embedding",
        }
        return await _reject(
            ["near-duplicate stem (embedding cosine distance below threshold)"], stage_results
        )
    stage_results["deduplication"] = {"passed": True}

    # --- 4. Independent Solver Agents A and B, routed through two already- -------
    # --- distinct task/model slots so they resolve to different models -----------
    solver_payload = SolverPayload(
        rendered_question=item.stem,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
    )
    solver_a, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_GENERATION,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"solver A call failed: {error}"], stage_results)
    solver_b, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_REVIEW,
        system_prompt=_SOLVER_SYSTEM_PROMPT,
        payload=solver_payload,
        response_model=SolverResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"solver B call failed: {error}"], stage_results)
    assert isinstance(solver_a, SolverResponse) and isinstance(solver_b, SolverResponse)
    stage_results["solver_a"] = {"selected_option": solver_a.selected_option}
    stage_results["solver_b"] = {"selected_option": solver_b.selected_option}

    if not (solver_a.selected_option == solver_b.selected_option == item.correct_option):
        reasons = [
            "independent solver disagreement: "
            f"solver_a={solver_a.selected_option!r} solver_b={solver_b.selected_option!r} "
            f"declared={item.correct_option!r}"
        ]
        return await _reject(reasons, stage_results)

    # --- 5. Judge: difficulty fit, ambiguity, alignment, age-appropriateness, ----
    # --- hint quality, all from one independent model call -----------------------
    judge_payload = QuestionJudgePayload(
        rendered_question=item.stem,
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
        hint_ladder=item.hint_ladder,
        canonical_solution=item.canonical_solution.final_answer,
        topic_name=topic.name,
        skill_name=skill.name,
        grade_band=topic.grade_band,
        proposed_difficulty=difficulty_label,
    )
    judge, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_JUDGE,
        system_prompt=_JUDGE_SYSTEM_PROMPT,
        payload=judge_payload,
        response_model=QuestionJudgeResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
    )
    _spend(cost)
    if error is not None:
        return await _reject([f"judge call failed: {error}"], stage_results)
    assert isinstance(judge, QuestionJudgeResponse)
    stage_results["judge"] = judge.model_dump()

    judge_reasons: list[str] = []
    if judge.is_ambiguous:
        judge_reasons.append(f"judge flagged ambiguity: {judge.reasoning}")
    if not judge.is_aligned:
        judge_reasons.append(f"judge flagged misalignment: {judge.reasoning}")
    if not judge.is_age_appropriate:
        judge_reasons.append(f"judge flagged age-inappropriate content: {judge.reasoning}")
    if abs(judge.difficulty_label - difficulty_label) > 1:
        judge_reasons.append(
            f"judge rated difficulty {judge.difficulty_label}, too far from proposed "
            f"{difficulty_label}"
        )
    if judge.hint_quality_score < _HINT_QUALITY_REJECT_BELOW:
        judge_reasons.append(f"judge rated hint quality {judge.hint_quality_score}, too low")
    if judge_reasons:
        return await _reject(judge_reasons, stage_results)

    review_priority = "normal"
    if (
        judge.hint_quality_score <= _HINT_QUALITY_BORDERLINE_AT
        or abs(judge.difficulty_label - difficulty_label) == 1
    ):
        review_priority = "high"

    # --- 6. Persist as pending (never auto-approved - see module docstring) -----
    template_id = f"authored-{topic_id}-d{difficulty_label}-{seed}"
    template = await repo.create_template(
        QuestionTemplate(
            question_template_id=template_id,
            curriculum_version=curriculum.curriculum_version,
            topic_id=topic_id,
            skill_id=skill_id,
            grade_band=topic.grade_band,
            difficulty_label=difficulty_label,
            difficulty_confidence=1.0 if judge.difficulty_label == difficulty_label else 0.5,
            question_type="multiple_choice",
            parameter_schema={},
            solution_function="authored",
            correct_option_generator="authored",
            distractor_generators=[],
            common_error_tags=item.misconception_tags,
            estimated_time_seconds=item.estimated_time_seconds,
            generator_model="bedrock-authored-question-generation",
            review_model_versions={
                "solver_a": "bedrock-question-generation",
                "solver_b": "bedrock-question-review",
                "judge": "bedrock-question-judge",
            },
            validation_status="pending",
            active_status="active",
            authoring_mode="authored",
            stem=item.stem,
            context_block=item.context_block,
            answer_expression=item.answer_expression,
            hint_ladder=item.hint_ladder,
            canonical_solution=item.canonical_solution.model_dump(),
            stem_embedding=stem_embedding,
            review_priority=review_priority,
            version=version,
        )
    )
    persisted_variant = await repo.create_variant(
        QuestionVariant(
            # The newly authored template's defining rendering (D-106), declared
            # explicitly rather than left to the column default, which is "runtime".
            # It used to be true that such a template "never gains runtime ones"; D-189
            # made it servable, so it now gains one row per showing and this flag is what
            # separates the reviewed content from an arbitrary student's rendering.
            origin=VARIANT_ORIGIN_CANONICAL,
            question_template_id=template.question_template_id,
            random_seed=seed,
            rendered_question=rendered_question,
            option_a=item.option_a,
            option_b=item.option_b,
            option_c=item.option_c,
            option_d=item.option_d,
            correct_option=item.correct_option,
            parameter_values={},
        )
    )
    await repo.create_validation_run(
        QuestionValidationRun(
            question_template_id=template.question_template_id,
            outcome="pending",
            stage_results=stage_results,
            reasons=[],
            cost_cents=total_cost,
        )
    )

    return PipelineOutcome(
        status="pending",
        question_template_id=template.question_template_id,
        question_variant_id=persisted_variant.question_variant_id,
        cost_cents=total_cost,
    )
