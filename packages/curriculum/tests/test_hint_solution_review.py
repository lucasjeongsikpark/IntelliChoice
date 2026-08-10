"""D-251: the hint & solution review instrument, before it is wired to any decision.

These pin the contract, not the quality of any verdict - the instrument's actual behaviour
is unmeasured until the falsification run in docs/HINT_SOLUTION_REVIEW.md §5, and no test
here should be read as evidence that it works.
"""

import asyncio

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.hint_solution_review import (
    SYSTEM_PROMPT,
    build_payload,
    out_of_range_defects,
    review_hints_and_solution,
)
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    BedrockTask,
    HintSolutionDefect,
    HintSolutionReviewResponse,
    LlmJudgeResponse,
    RubricDimensionScore,
    SolutionResponse,
    SolutionStep,
)
from pydantic import ValidationError


def _item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve for n: 4n = 52.",
        context_block=None,
        option_a="13",
        option_b="12",
        option_c="14",
        option_d="11",
        correct_option="a",
        equation="Eq(4*n, 52)",
        hint_ladder=[
            "What operation undoes multiplication?",
            "Both sides can be divided by the same number.",
            "Divide 52 by 4.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide both sides by 4",
                    expression="n = 52/4",
                ),
                SolutionStep(step_number=2, explanation="Simplify", expression="n = 13"),
            ],
            final_answer="13",
        ),
        estimated_time_seconds=60,
        proposed_difficulty=3,
        difficulty_rationale="One inverse operation, no negatives.",
    )
    base.update(overrides)
    return AuthoredGeneratedItemResponse(**base)  # type: ignore[arg-type]


def _gateway() -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=MockBedrockProvider(),
        model_registry={BedrockTask.HINT_SOLUTION_REVIEW: "anthropic.claude-haiku-4-5"},
    )


def test_a_blocking_verdict_without_a_defect_is_rejected() -> None:
    """The invariant that makes the verdict automatable: `repair` with nothing located gives
    a repair prompt no instruction to follow, and a reviewer nothing to read.
    """
    with pytest.raises(ValidationError):
        HintSolutionReviewResponse(
            verdict="repair", defects=[], uncertainty="low", reasoning="something is off"
        )
    with pytest.raises(ValidationError):
        HintSolutionReviewResponse(
            verdict="reject", defects=[], uncertainty="high", reasoning="bad"
        )
    # `pass` with no defects is the normal case and must stay legal.
    assert (
        HintSolutionReviewResponse(
            verdict="pass", defects=[], uncertainty="low", reasoning="fine"
        ).verdict
        == "pass"
    )


def test_the_response_carries_no_scalar_quality_score() -> None:
    """D-251's whole premise. If a numeric quality field ever appears on this model, the
    thing D-249 measured as noise has been reintroduced under a new name.
    """
    fields = HintSolutionReviewResponse.model_fields
    assert "verdict" in fields
    numeric = {
        name
        for name, field in fields.items()
        if field.annotation in (int, float, int | None, float | None)
    }
    assert numeric == set(), f"scalar score fields reintroduced: {numeric}"


def test_defect_indices_beyond_the_item_are_reported_as_unusable() -> None:
    """A hallucinated location must not reach a repair prompt as if it were real - repairing
    against a location that does not exist is how a correct item gets damaged.
    """
    item = _item()
    response = HintSolutionReviewResponse(
        verdict="repair",
        defects=[
            HintSolutionDefect(
                target="hint_ladder", index=7, problem="p", suggested_fix="f"
            ),
            HintSolutionDefect(
                target="canonical_solution", index=2, problem="p", suggested_fix="f"
            ),
            HintSolutionDefect(target="hint_ladder", index=None, problem="p", suggested_fix="f"),
        ],
        uncertainty="medium",
        reasoning="r",
    )
    problems = out_of_range_defects(response, item)
    assert problems == ["hint_ladder[7] does not exist (hint_ladder has 3 entries)"]


def test_payload_renders_the_question_a_student_is_served() -> None:
    """D-196: judging the stem alone is judging text nobody sees."""
    with_context = build_payload(
        _item(context_block="A rope is cut into 4 equal pieces."),
        skill_name="linear_one_step",
        grade_band="6-8",
    )
    assert with_context.rendered_question.startswith("A rope is cut into 4 equal pieces.")
    assert "Solve for n: 4n = 52." in with_context.rendered_question

    without_context = build_payload(_item(), skill_name="linear_one_step", grade_band="6-8")
    assert without_context.rendered_question == "Solve for n: 4n = 52."


def test_payload_carries_the_solution_steps_not_just_the_final_answer() -> None:
    payload = build_payload(_item(), skill_name="linear_one_step", grade_band="6-8")
    assert payload.solution_steps == [
        "1. Divide both sides by 4 [n = 52/4]",
        "2. Simplify [n = 13]",
    ]
    assert payload.solution_final_answer == "13"


def test_the_prompt_tells_the_reviewer_what_is_already_decided_deterministically() -> None:
    """D-223: if the prompt does not say these are handled, the reviewer spends output
    re-deriving them and reports a rule's job as a pedagogy defect.
    """
    assert "verbatim" in SYSTEM_PROMPT
    assert "matches the declared correct option" in SYSTEM_PROMPT
    assert "Do not re-check these" in SYSTEM_PROMPT


def test_the_prompt_forbids_judging_against_a_house_style() -> None:
    """Diversity is a constraint, not a preference. Without this clause the reviewer's
    implicit reference is the ladder it would have written itself.
    """
    assert "no house style and no reference item" in SYSTEM_PROMPT
    assert "Vary is not the same as wrong" in SYSTEM_PROMPT


def test_review_returns_a_pass_for_a_well_formed_item_under_the_mock() -> None:
    async def run() -> None:
        response = await review_hints_and_solution(
            _gateway(),
            _item(),
            skill_name="linear_one_step",
            grade_band="6-8",
            session_spend_cents=0.0,
        )
        assert response.verdict == "pass"
        assert response.defects == []

    asyncio.run(run())


def test_review_returns_a_located_repair_when_a_rung_repeats_its_predecessor() -> None:
    """Exercises the defect path end to end, including the model validator that would have
    rejected a defect-free `repair`.
    """

    async def run() -> None:
        response = await review_hints_and_solution(
            _gateway(),
            _item(hint_ladder=["Divide 52 by 4.", "Divide 52 by 4.", "What is 52/4?"]),
            skill_name="linear_one_step",
            grade_band="6-8",
            session_spend_cents=0.0,
        )
        assert response.verdict == "repair"
        assert [d.index for d in response.defects] == [2]
        assert response.defects[0].suggested_fix

    asyncio.run(run())


def test_rubric_dimension_score_is_bounded_to_the_scale_its_prompt_states() -> None:
    """Not this instrument, but the same defect class one file over: `run_llm_judge`'s
    prompt says 1-5 and its schema said nothing, which is how the question judge came to
    emit 8s and 9s against thresholds of 2 and 3.
    """
    assert LlmJudgeResponse(
        scores=[RubricDimensionScore(dimension="d", score=5)], overall_pass=True
    ).scores[0].score == 5
    with pytest.raises(ValidationError):
        RubricDimensionScore(dimension="d", score=9)
    with pytest.raises(ValidationError):
        RubricDimensionScore(dimension="d", score=0)
