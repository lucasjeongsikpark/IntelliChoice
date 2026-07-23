"""Pure unit tests for `authored_validation.py`'s deterministic §5.8.5 checks - no
Postgres needed, unlike `test_authored_pipeline.py`'s end-to-end tests.
"""

from intellichoice_curriculum.authored_validation import validate_authored_item
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _good_item(**overrides: object) -> AuthoredGeneratedItemResponse:
    base: dict[str, object] = dict(
        stem="Solve: what is 2 + 2?",
        option_a="4",
        option_b="5",
        option_c="6",
        option_d="3",
        correct_option="a",
        answer_expression="2 + 2",
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


def test_valid_item_passes_every_check() -> None:
    result = validate_authored_item(1, _good_item())
    assert result.passed
    assert result.failures == []


def test_two_correct_options_rejected() -> None:
    item = _good_item(option_b="4")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("unique" in f or "exactly one option" in f for f in result.failures)


def test_sympy_disagreement_with_declared_answer_rejected() -> None:
    item = _good_item(answer_expression="2 + 2", correct_option="b")  # option_b == "5"
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_leaked_answer_in_hint_rejected() -> None:
    item = _good_item(
        hint_ladder=[
            "The answer is 4, but think about why.",
            "Try counting up from 2 by 2 more.",
            "Add the two numbers together directly.",
        ]
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("leak" in f for f in result.failures)


def test_hint_ladder_monotonicity_violation_rejected() -> None:
    item = _good_item(
        hint_ladder=[
            "Try counting up from 2. Add the two numbers together directly.",
            "Try counting up from 2.",
            "Add the two numbers together directly.",
        ]
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("already reveals" in f for f in result.failures)


def test_hint_solution_answer_disagreement_rejected() -> None:
    item = _good_item(
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="e", expression="e")],
            final_answer="5",
        )
    )
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("final_answer" in f for f in result.failures)


def test_disallowed_wording_rejected() -> None:
    item = _good_item(stem="This is a dumb question: what is 2 + 2?")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("disallowed wording" in f for f in result.failures)


def test_off_grade_readability_rejected() -> None:
    long_sentence = " ".join(["word"] * 40) + "?"
    item = _good_item(stem=long_sentence)
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("readability" in f for f in result.failures)


def test_html_or_link_rejected() -> None:
    item = _good_item(stem="Solve: what is 2 + 2? <script>alert(1)</script>")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("HTML or a link" in f for f in result.failures)


def test_wrong_hint_ladder_length_rejected() -> None:
    item = _good_item(hint_ladder=["only one hint"])
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("hint_ladder has" in f for f in result.failures)


def test_out_of_range_difficulty_rejected() -> None:
    result = validate_authored_item(9, _good_item())
    assert not result.passed
    assert any("difficulty_label" in f for f in result.failures)
