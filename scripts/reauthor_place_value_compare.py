"""Re-author `place_value_compare` so its items exercise comparison (D-273, C1 Phase R).

**The defect.** All 15 items in this skill asked *"how many more?"* - subtraction word
problems filed under *"Compare and order multi-digit numbers by place value"*. Not one asked
a student to compare. Measured across the whole bank, every other skill is 0/N on that
pattern; this one was 15/15. It is the third instance of the D-238 shape (`div_remainder`
items that all stated the remainder in the stem), and the first where the cause is known.

**The cause was not the gate.** That was the working hypothesis and it was wrong.
`Eq(x, Max(34, 43))` derives 43 and passes the §5.8.5 gate today, unchanged - measured before
writing any router code. So a comparison question was always expressible, and these 15 were
reshaped into arithmetic by an author who did not reach for that form. The repair is
authoring, not code.

**What changes and what does not.** Every item keeps its id, seed, tier, grade band and
estimated time, so the bank's shape and the difficulty ladder D-238 fixed are untouched;
`version` goes to 2 and the stem, options, equation, hints and solution are replaced. The
tiers follow `place_value`'s own anchors (topics.yaml), which is why the four groups differ
in *what decides the comparison* rather than merely in digit count - D-238's finding was that
a bare digit-count clause is real work for `compare` and none at all for `identify`.

Run it, then re-gate and canonicalise through the normal route:

    .venv/bin/python scripts/reauthor_place_value_compare.py
    make curriculum-load && make question-export
"""

import pathlib
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
BANK = ROOT / "curriculum" / "internal_math" / "authored" / "place_value.yaml"

_COMPARISON_STEM = "Which of these numbers is the largest?"

# (template_id, options, correct, what makes this tier this tier)
#
# Options are always four numbers drawn so the *rubric's* discriminator decides the answer:
# at tier 2 the ones digit misleads, at tier 3 the hundreds are shared so the tens decide, at
# tier 4 the leading digits are shared, at tier 5 the first difference sits outside the
# leading two places. A set whose answer has both the largest tens *and* the largest ones
# digit would let a student win by reading one column, which is the trap D-238 found.
_COMPARISONS: list[tuple[str, list[int], int, str]] = [
    # d2 - two-digit, and the largest ones digit belongs to a smaller number
    ("authored-place_value-d1-200104", [34, 43, 38, 29], 43, "tens decide; 38 baits the ones"),
    ("authored-place_value-d2-200203", [58, 85, 59, 49], 85, "tens decide; 59 baits the ones"),
    ("authored-place_value-d2-200205", [67, 76, 69, 59], 76, "tens decide; 69 baits the ones"),
    # d3 - three-digit, hundreds shared, so the tens decide
    ("authored-place_value-d3-200302", [348, 384, 359, 371], 384, "all 3xx; tens decide"),
    ("authored-place_value-d3-200304", [128, 182, 149, 167], 182, "all 1xx; tens decide"),
    ("authored-place_value-d3-200305", [703, 730, 719, 725], 730, "all 7xx; tens decide"),
    ("authored-place_value-d4-200403", [415, 451, 429, 437], 451, "all 4xx; tens decide"),
    # d4 - four digits, leading digits shared, first difference is not the leading place
    ("authored-place_value-d4-200402", [2610, 2160, 2601, 2016], 2610, "all 2xxx; hundreds"),
    ("authored-place_value-d4-200405", [1089, 1098, 1079, 1092], 1098, "all 10xx; tens"),
    ("authored-place_value-d5-200503", [4507, 4570, 4519, 4552], 4570, "all 45xx; tens"),
    # d5 - five digits, first difference outside the leading two places
    ("authored-place_value-d5-200502", [12340, 12430, 12403, 12034], 12430, "all 12xxx"),
    ("authored-place_value-d5-200506", [24105, 24150, 24015, 24051], 24150, "all 24xxx"),
]

# d5 BUILD - the student arranges the digits before anything can be compared, so choosing the
# arrangement is itself the work (the tier-5 anchor's second clause).
_BUILDS: list[tuple[str, list[int], list[int], int]] = [
    ("authored-place_value-d5-200504", [8, 3, 6], [863, 836, 683, 386], 863),
    ("authored-place_value-d5-200507", [5, 2, 9], [952, 925, 592, 295], 952),
    ("authored-place_value-d5-200508", [7, 3, 1], [731, 713, 371, 137], 731),
]


def _permutations_of(digits: list[int]) -> list[int]:
    """Every three-digit number the digits can form - the honest model of "the largest
    number he can make", so SymPy picks the maximum rather than the author asserting it.
    """
    from itertools import permutations

    return sorted({int("".join(str(d) for d in p)) for p in permutations(digits)})


def _place_name(numbers: list[int], answer: int) -> str:
    """Which column actually decides this set. Used in the hints, so they describe the work
    rather than restating the answer.
    """
    width = len(str(answer))
    for index in range(width):
        column = {str(n).rjust(width, "0")[index] for n in numbers}
        if len(column) > 1:
            return ["ones", "tens", "hundreds", "thousands", "ten thousands"][width - index - 1]
    return "ones"


def _comparison_item(existing: dict[str, Any], numbers: list[int], answer: int) -> dict[str, Any]:
    place = _place_name(numbers, answer)
    item = dict(existing)
    item["version"] = 2
    item["stem"] = _COMPARISON_STEM
    item["rendered_question"] = _COMPARISON_STEM
    item["context_block"] = None
    item["answer_expression"] = f"Eq(x, Max({', '.join(str(n) for n in numbers)}))"
    item["common_error_tags"] = [
        "Compared the ones digits instead of the highest differing place",
        "Read the numbers left to right without lining up the places",
        "Chose the number with the most digits showing rather than the largest value",
    ]
    # **The third hint used to say the first differing column decides it, and in 7 of these
    # 15 items it does not** - two numbers tie there and the student is left choosing
    # between them. Found by the §5.8.5 judge on `200502` (12340/12430/12403/12034, where
    # 12430 and 12403 both carry 4 in the hundreds), then measured across the set. The
    # deterministic gate passed all 15, because it checks that the answer is right and not
    # that the hint is sufficient to reach it - which is exactly the class of defect the
    # human review skipped for this wave exists to catch.
    item["hint_ladder"] = [
        "Line the numbers up so their place-value columns sit under each other.",
        "Start at the leftmost column and move right until the digits stop matching.",
        f"The first column where they differ is the {place} column. Keep the numbers with "
        f"the largest digit there, and if two of them tie, compare the next column to the "
        f"right.",
    ]
    item["canonical_solution"] = {
        "steps": [
            {
                "step_number": 1,
                "explanation": "Write the numbers with their place-value columns lined up.",
                "expression": ", ".join(str(n) for n in numbers),
                "common_mistake": "Comparing digits that sit in different places",
            },
            {
                "step_number": 2,
                "explanation": (
                    "Move left to right and find the first column where the digits differ."
                ),
                "expression": f"the {place} column is the first one that differs",
                "common_mistake": "Jumping straight to the ones digit",
            },
            {
                "step_number": 3,
                "explanation": (
                    "Keep the numbers with the largest digit in that column. If two of them "
                    "tie, compare the next column to the right until one is larger."
                ),
                "expression": f"largest = {answer}",
                "common_mistake": (
                    "Stopping at the first differing column when two numbers tie there"
                ),
            },
        ],
        "final_answer": str(answer),
    }
    for label, value in zip("abcd", numbers, strict=True):
        item[f"option_{label}"] = str(value)
    item["correct_option"] = "abcd"[numbers.index(answer)]
    return item


def _build_item(
    existing: dict[str, Any], digits: list[int], options: list[int], answer: int
) -> dict[str, Any]:
    spelled = ", ".join(str(d) for d in digits[:-1]) + f" and {digits[-1]}"
    stem = (
        f"Leo has three digit cards: {spelled}. He puts all three cards in a row to make "
        f"the largest three-digit number he can. What number does he make?"
    )
    item = dict(existing)
    item["version"] = 2
    item["stem"] = stem
    item["rendered_question"] = stem
    item["context_block"] = None
    everything = _permutations_of(digits)
    item["answer_expression"] = f"Eq(x, Max({', '.join(str(n) for n in everything)}))"
    item["common_error_tags"] = [
        "Placed the digits in the order they were given",
        "Put the largest digit in the ones place instead of the hundreds place",
        "Made the smallest number instead of the largest",
    ]
    item["hint_ladder"] = [
        "The hundreds place is worth the most, so decide which card goes there first.",
        "To make a number as large as possible, the largest digit belongs in the largest place.",
        "Place the cards in order from largest to smallest, left to right.",
    ]
    item["canonical_solution"] = {
        "steps": [
            {
                "step_number": 1,
                "explanation": "Sort the digit cards from largest to smallest.",
                "expression": " > ".join(str(d) for d in sorted(digits, reverse=True)),
                "common_mistake": "Keeping the cards in the order they were handed over",
            },
            {
                "step_number": 2,
                "explanation": (
                    "The hundreds place is worth the most, so it takes the largest digit; "
                    "the tens place takes the next one."
                ),
                "expression": (
                    f"hundreds = {sorted(digits, reverse=True)[0]}, "
                    f"tens = {sorted(digits, reverse=True)[1]}, "
                    f"ones = {sorted(digits, reverse=True)[2]}"
                ),
                "common_mistake": "Giving the largest digit to the ones place",
            },
            {
                "step_number": 3,
                "explanation": "Read the cards left to right to get the number.",
                "expression": f"largest = {answer}",
                "common_mistake": None,
            },
        ],
        "final_answer": str(answer),
    }
    for label, value in zip("abcd", options, strict=True):
        item[f"option_{label}"] = str(value)
    item["correct_option"] = "abcd"[options.index(answer)]
    return item


def main() -> None:
    bank = yaml.safe_load(BANK.open())
    by_id = {t["question_template_id"]: t for t in bank["templates"]}

    rewritten = 0
    for template_id, numbers, answer, _why in _COMPARISONS:
        by_id[template_id].update(_comparison_item(by_id[template_id], numbers, answer))
        rewritten += 1
    for template_id, digits, options, answer in _BUILDS:
        by_id[template_id].update(_build_item(by_id[template_id], digits, options, answer))
        rewritten += 1

    with BANK.open("w") as fh:
        yaml.dump(bank, fh, sort_keys=False, allow_unicode=True, width=110)
    print(f"rewrote {rewritten} place_value_compare items in {BANK.relative_to(ROOT)}")
    print("next: make curriculum-load && make question-export")


if __name__ == "__main__":
    main()
