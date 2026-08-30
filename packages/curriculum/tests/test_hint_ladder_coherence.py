"""R3a - the deterministic hint/stem coherence check, both directions (D-221).

**The hole it closes, measured.** E5.2 built 102 labeled defects over six classes against 102
clean controls drawn from the same approved bank and ran every detector the pipeline has over
all 204. One class scored **0/17 on every detector**: `mismatched_hint_ladder`, three rungs
lifted wholesale from a different item and chosen so they share no numeral with the question
they are attached to. It was 17 of the pipeline's 28 total misses, and the reason was
structural rather than a tuning problem - `hint_ladder_monotonicity_violations` is verbatim
containment between rungs, `check_no_answer_leakage` asks whether a rung states *this* item's
answer, and `SolverPayload` never carries a hint at all. Nothing in the pipeline compared a
hint with its stem.

**What is asserted here, and why in this shape.** `HINT_SOLUTION_REVIEW.md` §1 records two
hint scorers that failed, both of them because they graded how *good* a hint is. This check
grades nothing. It asks a closed question with a yes/no answer - does this ladder name a
number that occurs in the question it is attached to? - so the tests below are the two
directions of that question and not a quality judgement:

- the catch direction, pinned to the frozen E5.2 corpus at the number it actually measures
  (12 of 17), with the five misses named rather than averaged away;
- the false-positive direction, which is the one that decides where the check may live: it
  runs over all 102 clean controls **and the entire 958-item approved bank**, because a gate
  check that fails an approved item breaks `make curriculum-load` in every environment. Both
  are zero, which is why the check sits in the shared gate rather than on the generation path
  only.

The unit cases in between are the bank patterns that a naive version of this rule *did* reject
while it was being designed - place-value coaching, money cents, superscripts, thousands
separators and figure items - each one a measured false positive, kept as a fixture so a later
simplification of `_grounded_numerals` reintroduces them loudly.

Free: no model call, no database, no network.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.authored_validation import (
    hint_ladder_is_ungrounded,
    validate_authored_item,
)
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse

ROOT = pathlib.Path(__file__).resolve().parents[3]
CORPUS_PATH = ROOT / "docs" / "resume_evidence" / "05_content_generation" / "defect_corpus.jsonl"

# The five grafted ladders that pass, named rather than counted. Each one shares at least one
# numeral with its host question by coincidence of the donor's arithmetic, which is exactly
# the limit a disjointness rule has and the reason 12/17 is reported rather than 17/17.
KNOWN_MISSES = {
    "e52-mismatched_hint_ladder-003",
    "e52-mismatched_hint_ladder-011",
    "e52-mismatched_hint_ladder-013",
    "e52-mismatched_hint_ladder-015",
    "e52-mismatched_hint_ladder-016",
}


def _corpus() -> list[dict]:
    records = []
    with CORPUS_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("record") != "header":
                records.append(record)
    return records


def _flagged(record: dict) -> bool:
    item = AuthoredTemplateDef.model_validate(record["item"])
    return bool(hint_ladder_is_ungrounded(item.to_generated_item(), item.figure_spec))


# --- the catch direction, on the frozen corpus -------------------------------------------------


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_the_grafted_ladders_are_caught_at_the_measured_rate() -> None:
    """0/17 before, 12/17 after, on the same corpus and the same denominator.

    Pinned as an equality rather than a floor on purpose: a later change that moves this
    number in *either* direction has changed what the post-fix report says, and the report is
    the artifact this number exists to support.
    """
    defects = [r for r in _corpus() if r["defect_class"] == "mismatched_hint_ladder"]
    assert len(defects) == 17
    caught = {r["corpus_id"] for r in defects if _flagged(r)}
    missed = {r["corpus_id"] for r in defects} - caught
    assert len(caught) == 12
    assert missed == KNOWN_MISSES


def test_a_ladder_from_another_item_is_rejected_by_the_whole_gate() -> None:
    """Through `validate_authored_item`, not the predicate - the gate is what the loader and
    the pipeline both call, and a check that is written but not wired catches nothing (the
    exact state D-273's `arithmetic_identity` sat in for four waves).
    """
    item = _item()
    item.hint_ladder = [
        "What operation tells you how many groups of $8.75 fit into $52.50?",
        "You need to divide the total saved by the amount saved each week.",
        "Write 52.50 / 8.75 and calculate the quotient.",
    ]
    result = validate_authored_item(1, item)
    assert not result.passed
    assert any("the ladder is not about this item" in f for f in result.failures)
    assert any("52.50" in f for f in result.failures)


# --- the false-positive direction --------------------------------------------------------------


@pytest.mark.skipif(not CORPUS_PATH.exists(), reason="corpus artifact not built")
def test_no_clean_control_and_no_other_defect_class_is_flagged() -> None:
    """D-221: the direction the check is not being asked to prove. 102 unmutated bank items
    and the 85 defects of the other five classes, none of which this check is about.
    """
    records = _corpus()
    clean = [r for r in records if r["label"] == "clean"]
    others = [
        r
        for r in records
        if r["label"] == "defect" and r["defect_class"] != "mismatched_hint_ladder"
    ]
    assert len(clean) == 102
    assert [r["corpus_id"] for r in clean if _flagged(r)] == []
    assert [r["corpus_id"] for r in others if _flagged(r)] == []


def test_the_whole_approved_bank_passes_the_check() -> None:
    """The condition that decides where this check is allowed to live.

    `loader.py` re-gates **every** bank item on load, in every environment including
    production, and aborts the run on a failure. So a hint check that fails even one approved
    item would break `make curriculum-load` and CI, and would have had to be scoped to the
    generation path only. It fails none of the 958, which is why it is in the shared gate.

    Scanning the whole bank rather than three sampled items is deliberate: three items prove
    the check runs, and only the whole bank proves it does not break serving.
    """
    bank = [item for items in load_authored_bank().values() for item in items]
    assert len(bank) >= 900, "the bank shrank - re-read this assertion before relaxing it"
    flagged = [
        item.question_template_id
        for item in bank
        if hint_ladder_is_ungrounded(item.to_generated_item(), item.figure_spec)
    ]
    assert flagged == []


# --- the measured false-positive families, kept as fixtures ------------------------------------


def _item(**overrides: object) -> AuthoredGeneratedItemResponse:
    """A minimal gate-clean authored item, as `AuthoredGeneratedItemResponse`."""
    base = AuthoredTemplateDef(
        question_template_id="fixture",
        topic_id="g1_addition",
        skill_id="g1_add_within_10",
        grade_band="1-2",
        difficulty_label=1,
        estimated_time_seconds=45,
        generator_model="fixture",
        stem="Liam has 4 apples in a basket. He picks 5 more apples. How many apples now?",
        context_block="",
        answer_expression="Eq(x, 4 + 5)",
        hint_ladder=[
            "Start with the apples Liam already has.",
            "Count on from 4: how many more does he pick?",
            "Write 4 + 5 and find the sum.",
        ],
        canonical_solution={
            "steps": [
                {
                    "step_number": 1,
                    "explanation": "Liam starts with 4 apples.",
                    "expression": "4",
                    "common_mistake": None,
                }
            ],
            "final_answer": "9 apples",
        },
        random_seed=1001,
        rendered_question="Liam has 4 apples in a basket. He picks 5 more apples.",
        option_a="9 apples",
        option_b="4 apples",
        option_c="5 apples",
        option_d="11 apples",
        correct_option="a",
    ).to_generated_item()
    for name, value in overrides.items():
        setattr(base, name, value)
    return base


@pytest.mark.parametrize(
    ("stem", "equation", "hints", "why"),
    [
        (
            "Maria has 32 stickers and her friend gives her 24 more stickers. How many now?",
            "Eq(x, 32 + 24)",
            [
                "Maria starts with some stickers and receives more. What operation combines them?",
                "Write an addition sentence using the two numbers of stickers.",
                "Add the ones place first: 2 + 4. Then add the tens place: 30 + 20.",
            ],
            "place-value coaching names the digits and the tens, not the numbers themselves "
            "(authored-g2_addition-d2-7201)",
        ),
        (
            "A cyclist had $21.50 and spent $9.35 on a water bottle. How much is left?",
            "Eq(x, 21.50 - 9.35)",
            [
                "Start with the amount the cyclist had at the beginning.",
                "Subtract the cost of the water bottle from the starting amount.",
                "Remember to regroup when subtracting cents: 50 cents minus 35 cents.",
            ],
            "money hints name the cents, which are the decimal part "
            "(authored-measurement-d2-959202)",
        ),
        (
            "Three cities reported populations of 45,832, 67,419 and 52,106. Which is largest?",
            "Eq(x, Max(45832, 67419, 52106))",
            [
                "Look at the leftmost digit of each population number.",
                "The ten-thousands digits are 4, 6, and 5. Which of those is greatest?",
                "The number starting with the greatest digit is the largest number.",
            ],
            "a thousands separator must not split one number into two, and the hint names "
            "digits (the ten `number_sense` compare/round items)",
        ),
        (
            "A tournament has 2³ groups and each group contains 3² players. How many players?",
            "Eq(x, 2**3 * 3**2)",
            [
                "Start by evaluating each exponent separately.",
                "The number of groups is 2³ = 8, and each group has 3² = 9 players.",
                "Multiply the groups by the players in each group to find the total.",
            ],
            "a superscript exponent is a number the stem states (authored-pre_algebra-d3-1166300)",
        ),
    ],
)
def test_a_legitimate_ladder_that_names_derived_numbers_passes(stem, equation, hints, why) -> None:
    item = _item(stem=stem, equation=equation, hint_ladder=hints)
    assert hint_ladder_is_ungrounded(item) == set(), why


def test_a_ladder_that_names_no_number_is_not_judged() -> None:
    """127 of the 958 approved items are in this state, so it is the common case and not an
    edge one. The check is a floor on coherence and has nothing to say about a ladder with no
    numerals in it; claiming a verdict there would be inventing one.
    """
    item = _item(
        hint_ladder=[
            "Think about combining two groups of objects.",
            "Count on from the first group.",
            "Add the two amounts together.",
        ]
    )
    assert hint_ladder_is_ungrounded(item) == set()


def test_a_figure_item_is_grounded_by_its_figure() -> None:
    """A figure item states its numbers in the picture, not in the sentence.

    Without the figure in the grounded set the ten `telling_time` items are all disjoint from
    their own questions, which is the largest single false-positive family this rule had.
    """
    from intellichoice_shared.figures import ClockFigure

    figure = ClockFigure(hour=3, minute=30)
    item = _item(
        stem="What time does this clock show?",
        equation=None,
        option_a="3:30",
        option_b="6:15",
        option_c="9:30",
        option_d="12:30",
        correct_option="a",
        hint_ladder=[
            "The short hand tells you the hour. Which number has it just passed?",
            "The short hand has passed 3, so the hour is 3.",
            "The long hand counts minutes in fives. Count round from the 12.",
        ],
    )
    assert hint_ladder_is_ungrounded(item, figure) == set()
