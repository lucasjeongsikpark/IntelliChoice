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
    item = _good_item(equation="Eq(x, 2 + 2)", correct_option="b")  # option_b == "5"
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_correct_answer_written_as_an_equation_is_accepted() -> None:
    """Both of these are what a real model actually wrote, and both were rejected.

    The first real-Bedrock authoring run (2026-08-05) lost six of eleven candidates to
    option formatting rather than to wrong math: `sympy.sympify` accepts neither `'x = 7'`
    nor a typographic minus, so the independent-solve gate reported a mismatch for items
    whose answers were right. The value each option denotes is unchanged by either
    repair - that is what makes accepting them safe.
    """
    restated = _good_item(
        equation="Eq(x, 3 + 4)",
        option_a="x = 7",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Add.", expression="3 + 4")],
            final_answer="7",
        ),
    )
    result = validate_authored_item(1, restated)
    assert result.passed, result.failures

    typographic_minus = _good_item(
        stem="Solve for x: 2x + 7 = 1",
        equation="Eq(2*x + 7, 1)",
        option_a="−3",
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(step_number=1, explanation="Subtract 7.", expression="2x = -6")
            ],
            final_answer="−3",
        ),
    )
    result = validate_authored_item(1, typographic_minus)
    assert result.passed, result.failures


def test_a_word_problem_answer_with_a_unit_is_verified_rather_than_exempt() -> None:
    """The gate penalised word problems, which is where units naturally appear.

    Not by rejecting prose - a scenario stem always passed - but by rejecting the answer
    text a scenario implies. `sympify('12 minutes')` fails, so the correct option matched
    nothing and the item was rejected for a mismatch its math did not have. Same family as
    `'x = 7'` and the typographic minus, unnoticed until the questions stopped being bare
    equations (D-191).

    The second half is the part that matters: stripping a unit must not stop the value
    being checked, or this would trade a false rejection for a false acceptance.
    """
    with_unit = _good_item(
        stem="A tank fills at 4 litres each minute. How long to add 12 litres?",
        equation="Eq(4*x, 12)",
        option_a="3 minutes",
        option_b="4 minutes",
        option_c="12 minutes",
        option_d="48 minutes",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Divide.", expression="12 / 4")],
            final_answer="3 minutes",
        ),
    )
    result = validate_authored_item(1, with_unit)
    assert result.passed, result.failures

    # Same units, wrong declared answer: still caught, so the unit did not become a
    # loophole that makes any option match.
    wrong = _good_item(
        stem="A tank fills at 4 litres each minute. How long to add 12 litres?",
        equation="Eq(4*x, 12)",
        option_a="3 minutes",
        option_b="4 minutes",
        option_c="12 minutes",
        option_d="48 minutes",
        correct_option="b",
        canonical_solution=SolutionResponse(
            steps=[SolutionStep(step_number=1, explanation="Divide.", expression="12 / 4")],
            final_answer="4 minutes",
        ),
    )
    result = validate_authored_item(1, wrong)
    assert not result.passed
    assert any("does not match declared correct option" in f for f in result.failures)


def test_an_algebraic_answer_is_not_mistaken_for_a_united_value() -> None:
    """`'2x'` must not be read as `2` by the unit stripper - the reason it only runs
    after a direct parse has already failed, and only on suffixes of two letters or more.
    """
    from intellichoice_curriculum.authored_validation import _sympify

    assert _sympify("2x") is None
    assert str(_sympify("x")) == "x"
    assert _sympify("12 minutes") == 12
    assert _sympify("40 cm") == 40


def test_typographic_minus_distractor_is_no_longer_exempt_from_the_duplicate_check() -> None:
    """The gate was quieter, not just noisier, before the parse-site normalization.

    An option that failed to parse was skipped by `check_sympy_independent_solve`'s "no
    distractor also matches" arm entirely, so a distractor equal to the correct answer
    would pass unnoticed as long as it was written with a character SymPy rejects. The
    2026-08-05 run produced an item with exactly such a distractor ('−3'), which is how
    this was noticed.
    """
    item = _good_item(equation="Eq(x, 2 + 2)", option_b="−4", option_c="4")
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("more than one option matches" in f for f in result.failures)


def test_banned_wording_matches_words_not_substrings() -> None:
    """Substring matching rejected correct, harmless questions - and the words it hit are
    ones a math item is likely to contain.

    Measured on the first scenario run (D-191): a question about rolling a **die** was
    rejected. `'skill'` contains `'kill'` and `'studies'` contains `'die'`, so the check
    was a trap that got more likely to spring the more natural the language became. `die`
    is off the list entirely - it is the singular of dice, not a word about death.
    """
    for harmless in [
        "Roll a die and record the number that lands face up.",
        "This skill needs practice before the next unit.",
        "Ana studies for 40 minutes each evening.",
        "Choose the medium jar rather than the small one.",
    ]:
        item = _good_item(stem=harmless)
        result = validate_authored_item(1, item)
        assert not any("disallowed wording" in f for f in result.failures), harmless

    for banned in ["The plants died after a week.", "That answer is stupid."]:
        item = _good_item(stem=banned)
        result = validate_authored_item(1, item)
        assert any("disallowed wording" in f for f in result.failures), banned


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
