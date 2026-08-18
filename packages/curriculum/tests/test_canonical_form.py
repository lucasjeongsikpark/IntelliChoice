"""The canonical-form tie-break (D-308), scored in both directions and negatively controlled.

**The class it exists for.** `check_sympy_independent_solve` refuses an item when more than one
option matches the value derived from its equation. For a skill whose question asks for a
*value* that is exactly right - two options a student cannot tell apart must never both be on
screen. For a skill whose question asks for a *form* it refuses the skill's best item:

    Reduce 12/18 to lowest terms.   12/18   6/9   **2/3**   4/6     - all four equal 2/3
    Simplify √80.                   8√10   **4√5**   √16+√5   2√20   - two of them equal 4√5

Measured before any of this was written (`scripts/measure_canonical_form.py`, free, from the
rejections D-195 stores): **59 of 74** distinct slots of this class are that item, and
`g6_fraction_reduce` held **0 items in the bank** because every candidate it ever produced died
here. D-306 had already measured the repair path against it at 0 of 4, twice.

**Why the relaxation is safe, and what these tests are for.** The tie-break is scoped by
`SkillDef.answer_form`, declared per skill, never inferred from the stem. The two hazards are
opposite and both are tested:

- *recall* - the item the value test wrongly refused is now accepted (§1)
- *precision* - and this is the one that matters, because A4 relaxes duplicate detection: the
  same item under the default `"any"` is **still refused** (§2). Without that test, "scoped by
  skill" would be an assertion about code I wrote rather than a measured property.

The negative controls in §3 are the cases where the form does *not* settle it and the rejection
must stand - two canonical options, none, or the declared answer being the unreduced one.

Free: pure SymPy and string reading, no model call, no database.
"""

import pytest
from intellichoice_curriculum.authored_validation import (
    _is_lowest_terms,
    _is_simplest_radical,
    canonical_option,
    validate_authored_item,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import (
    AuthoredGeneratedItemResponse,
    SolutionResponse,
    SolutionStep,
)


def _reduce_item(**overrides) -> AuthoredGeneratedItemResponse:
    """A real `g6_fraction_reduce` shape: the answer beside two unreduced equivalents."""
    base = dict(
        stem="Reduce the fraction 12/18 to its lowest terms.",
        option_a="12/18",
        option_b="6/9",
        option_c="2/3",
        option_d="5/6",
        correct_option="c",
        hint_ladder=[
            "Look for a number that divides both the top and the bottom.",
            "Both 12 and 18 can be divided by 6.",
            "Divide the top and the bottom by the same number.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Divide the top and the bottom by their common factor.",
                    expression="12/18 = 2/3",
                    common_mistake=None,
                )
            ],
            final_answer="2/3",
        ),
        estimated_time_seconds=45,
        misconception_tags=["stopped_halfway"],
        proposed_difficulty=1,
        difficulty_rationale="one common factor divides both parts",
        required_prerequisites=["dividing whole numbers"],
        equation="Eq(x, Rational(12, 18))",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def _radical_item(**overrides) -> AuthoredGeneratedItemResponse:
    """A real `alg2_irrational` shape: the answer beside an unsimplified equivalent."""
    base = dict(
        stem="Write the square root of 80 in its simplest radical form.",
        option_a="8√10",
        option_b="4√5",
        option_c="2√20",
        option_d="5√3",
        correct_option="b",
        hint_ladder=[
            "Look for a perfect square that divides 80.",
            "80 is 16 times 5, and 16 is a perfect square.",
            "Take the square root of the perfect square out of the radical.",
        ],
        canonical_solution=SolutionResponse(
            steps=[
                SolutionStep(
                    step_number=1,
                    explanation="Split the radical at the perfect square factor.",
                    expression="sqrt(80) = sqrt(16*5)",
                    common_mistake=None,
                )
            ],
            final_answer="4√5",
        ),
        estimated_time_seconds=60,
        misconception_tags=["stopped_halfway_through_simplification"],
        proposed_difficulty=2,
        difficulty_rationale="a single factorisation step out of the radical",
        required_prerequisites=["perfect squares"],
        equation="Eq(x, sqrt(80))",
    )
    return AuthoredGeneratedItemResponse(**{**base, **overrides})


def _failures(item, answer_form: str) -> list[str]:
    return validate_authored_item(1, item, answer_form=answer_form).failures


# --------------------------------------------------------------------------------------
# 1. Recall: the item the value test wrongly refused
# --------------------------------------------------------------------------------------


def test_a_lowest_terms_item_is_accepted_when_the_skill_asks_for_that_form():
    item = _reduce_item()
    result = validate_authored_item(1, item, answer_form="lowest_terms")
    assert result.passed, _failures(item, "lowest_terms")


def test_a_simplest_radical_item_is_accepted_when_the_skill_asks_for_that_form():
    item = _radical_item()
    result = validate_authored_item(2, item, answer_form="simplest_radical")
    assert result.passed, _failures(item, "simplest_radical")


# --------------------------------------------------------------------------------------
# 2. Precision: the same items are still refused everywhere else.
#    This is the half that keeps the relaxation scoped, and it fails against a universal
#    tie-break - the shape D-274 and D-304 both got wrong in the other direction.
# --------------------------------------------------------------------------------------


def test_the_same_item_is_still_refused_under_the_default_form():
    failures = _failures(_reduce_item(), "any")
    assert any("more than one option matches" in f for f in failures), failures


def test_the_same_radical_item_is_still_refused_under_the_default_form():
    failures = _failures(_radical_item(), "any")
    assert any("more than one option matches" in f for f in failures), failures


def test_a_fraction_tie_is_not_broken_by_the_radical_form_or_the_reverse():
    """Each form reads its own notation and nothing else, so declaring one does not quietly
    admit the other's ties."""
    assert any(
        "more than one option matches" in f for f in _failures(_reduce_item(), "simplest_radical")
    )
    assert any(
        "more than one option matches" in f for f in _failures(_radical_item(), "lowest_terms")
    )


# --------------------------------------------------------------------------------------
# 3. The negative controls: the form is declared and still does not settle it
# --------------------------------------------------------------------------------------


def test_declaring_the_unreduced_option_as_the_answer_is_still_refused():
    """The tie-break picks the canonical option, it does not bless whichever one is declared.
    An item naming `12/18` as the answer to "reduce 12/18" is a bad item under any form."""
    failures = _failures(_reduce_item(correct_option="a"), "lowest_terms")
    assert failures, "an item declaring the unreduced form correct must not pass"


def test_two_options_in_lowest_terms_do_not_break_the_tie():
    """`2/3` beside `-2/-3`: both are written in lowest terms and both equal the answer, so
    there is no canonical option and the rejection stands.

    **This test found a real hole in the predicate rather than confirming one.** The first
    version of `_WRITTEN_FRACTION` had no sign, so `-2/-3` matched nothing, returned None,
    was excluded from the tie-break - and the item **passed** with two indistinguishable
    options on screen. The lowest-terms form of a rational is unique, which is what makes the
    tie-break reliable; it is only ambiguous when the same value is *written* two canonical
    ways, and a sign is the way that happens.
    """
    item = _reduce_item(option_a="-2/-3", option_b="5/7")
    failures = _failures(item, "lowest_terms")
    assert any("more than one option matches" in f for f in failures), failures


def test_no_option_in_lowest_terms_does_not_break_the_tie():
    item = _reduce_item(option_c="4/6", option_d="8/12", correct_option="c")
    failures = _failures(item, "lowest_terms")
    assert failures, "with no reduced option there is nothing to prefer"


def test_a_whole_number_option_is_not_evidence_of_a_reduced_form():
    """`1` beside `4/4` is one of the real stored rejections. The reduced form of `4/4` *is*
    `1`, and this rule cannot say so - so it must not guess, and the item stays refused."""
    item = _reduce_item(
        stem="Reduce the fraction 4/4 to its lowest terms.",
        equation="Eq(x, Rational(4, 4))",
        option_a="1",
        option_b="4/4",
        option_c="2/2",
        option_d="3/4",
        correct_option="a",
    )
    assert _failures(item, "lowest_terms"), "a bare whole number must not win a tie-break"


def test_the_failure_message_names_the_declared_form():
    """D-283: a message that names the symptom without the rule sends the next reader to the
    wrong lever. When a form is declared and did not settle it, the message says so."""
    item = _reduce_item(option_a="-2/-3", option_b="5/7")
    failures = _failures(item, "lowest_terms")
    assert any("lowest_terms" in f for f in failures), failures


# --------------------------------------------------------------------------------------
# 4. The predicates, pinned. Every case here was validated against the real bank and the
#    real rejections before the gate consulted them - the D-303 lesson, where three
#    successive rulers were wrong and each would have shipped a false finding.
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2/3", True),
        ("3/4", True),
        ("-2/3", True),
        # Signed on both parts. Read as "no fraction" before the precision test caught it,
        # which let an ambiguous item through - see the docstring on that test.
        ("-2/-3", True),
        ("-4/-6", False),
        ("2/3 cups", True),
        ("1 1/2", True),
        ("4/6", False),
        ("12/18", False),
        ("6/9", False),
        ("8/12", False),
        ("24/36", False),
        ("2/4 of a pie", False),
        # None, not False: no fraction is written, so there is nothing to call reduced.
        ("7", None),
        ("0.75", None),
        ("2 batches", None),
    ],
)
def test_lowest_terms_predicate(text: str, expected: bool | None):
    assert _is_lowest_terms(text) is expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4√5", True),
        ("8√10", True),
        ("6√2", True),
        ("sqrt(2)", True),
        ("3√7 inches", True),
        ("√1", True),
        ("2√20", False),
        ("√80", False),
        ("√12", False),
        ("√45", False),
        ("sqrt(50)", False),
        ("√16 + √5", False),
        ("5", None),
        ("2/3", None),
    ],
)
def test_simplest_radical_predicate(text: str, expected: bool | None):
    assert _is_simplest_radical(text) is expected


def test_an_undeclared_form_never_produces_a_canonical_option():
    """The fail-closed default, asserted rather than assumed: `"any"` and an unknown name
    both yield None, which means the rejection stands."""
    options = {"a": "12/18", "b": "6/9", "c": "2/3", "d": "5/6"}
    assert canonical_option("any", options, ["a", "b", "c"]) is None
    assert canonical_option("not_a_form", options, ["a", "b", "c"]) is None
    assert canonical_option("lowest_terms", options, ["a", "b", "c"]) == "c"


# --------------------------------------------------------------------------------------
# 5. Where the declaration is allowed to be. Pinned as a set so adding a skill to it is a
#    deliberate edit that shows up in a diff, the same discipline the coverage matrix uses.
# --------------------------------------------------------------------------------------


def test_only_skills_whose_question_asks_for_a_form_declare_one():
    """`stat_probability`'s answers are conventionally reduced, but its question asks for a
    probability, not for a form - so a student choosing `2/6` there is not wrong on the
    question as written and the equal-valued option really is a defect. It stays at "any"."""
    curriculum = load_curriculum()
    declared = {
        skill.skill_id: skill.answer_form
        for skill in curriculum.skills
        if skill.answer_form != "any"
    }
    assert declared == {
        "g6_fraction_reduce": "lowest_terms",
        "alg2_irrational": "simplest_radical",
    }


def test_the_pipeline_and_the_loader_resolve_the_form_through_one_function():
    """Two gates that disagree about what a valid item is are worse than either alone
    (`ai_pipeline`'s own comment at the gate call). An unknown or absent skill resolves to
    the fail-closed default rather than raising."""
    curriculum = load_curriculum()
    assert curriculum.answer_form("g6_fraction_reduce") == "lowest_terms"
    assert curriculum.answer_form("alg2_irrational") == "simplest_radical"
    assert curriculum.answer_form("g6_fraction_mul_div") == "any"
    assert curriculum.answer_form("no_such_skill") == "any"
    assert curriculum.answer_form(None) == "any"
