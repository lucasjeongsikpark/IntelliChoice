"""Does the last step of each worked solution actually state the answer? (D-257)

    uv run --package intellichoice-curriculum python scripts/audit_solution_step_completeness.py

**Free and deterministic.** No model, no database, no network. Reads the authored bank YAML and
reports, so it can be run before and after a repair pass and the two numbers compared.

**Found by the reviewers, not by a rule.** D-254 and D-256 blocked items whose final solution step
described an operation and displayed its *input*: `"Divide the top and bottom by 6"` shown as
`[6/12]` against a final answer of `1/2`. Six such blocks were read by hand and all six were real.
This script exists because that pattern is checkable for free across the whole bank, and 44 items
have it - **twice what the reviewers flagged**, which is the opposite of the D-249 failure mode
where a signal fired indiscriminately.

**This is NOT a gate and must not become one.** HINT_SOLUTION_REVIEW.md §3 admits deterministic
checks only for *exact invariants*, and this is not one: `[18 = 18 ✓]` is a legitimate
verification step that ends a correct solution without restating the answer, and a grade-1 item
answering `[4 groups of ten]` for `40` is a judgement call rather than an error. The classes below
keep those separate instead of averaging them into one number that would be wrong in both
directions.
"""

import pathlib
import re
from collections import Counter

import yaml

_BANK = pathlib.Path(__file__).resolve().parents[1] / "curriculum" / "internal_math" / "authored"

# The numeric or fractional head of a final answer, so `6 minutes` matches a step ending `t = 6`.
# Without this the check reports 72 items and 12 of them differ only by a unit word - a false
# positive rate high enough to make the real finding unreadable.
_LEADING_VALUE = re.compile(r"\s*(-?[\d,]+\s*/\s*[\d,]+|-?[\d,]+(?:\.\d+)?)")
_UNEVALUATED = re.compile(r"[\d)]\s*[-+x*/]\s*[\d(]")

_UNAMBIGUOUS = ("unevaluated arithmetic", "unsolved unknown stated")


def _squash(text: str) -> str:
    return re.sub(r"[\s,]", "", str(text))


def classify(last_expression: str, final_answer: str) -> str | None:
    """`None` when the step states the answer. Otherwise the class of what it states instead."""
    last, final = _squash(last_expression), _squash(final_answer)
    head = _LEADING_VALUE.match(str(final_answer))
    if final in last or (head and _squash(head.group(1)) in last):
        return None
    if "?" in last_expression or "something" in last_expression:
        return "unsolved unknown stated"
    if _UNEVALUATED.search(last_expression):
        return "unevaluated arithmetic"
    if re.search(r"\d", last_expression):
        # Mixed on purpose: a substitution check (`[18 = 18 ✓]`) and a place-value item
        # answering in words (`[4 groups of ten]`) both land here, and they are not the same
        # thing. Separating them needs a reading, which is the reviewers' job, not a regex's.
        return "numeric, but not the answer"
    return "answer in words only"


def main() -> int:
    by_class: Counter[str] = Counter()
    by_skill: Counter[str] = Counter()
    skill_totals: Counter[str] = Counter()
    unambiguous: list[tuple[str, str, str, str]] = []
    total = 0

    for path in sorted(_BANK.glob("*.yaml")):
        for item in yaml.safe_load(path.read_text())["templates"]:
            total += 1
            skill_totals[item["skill_id"]] += 1
            last = item["canonical_solution"]["steps"][-1]["expression"]
            final = item["canonical_solution"]["final_answer"]
            verdict = classify(str(last), str(final))
            if verdict is None:
                continue
            by_class[verdict] += 1
            if verdict in _UNAMBIGUOUS:
                by_skill[item["skill_id"]] += 1
                unambiguous.append(
                    (item["question_template_id"], item["skill_id"], str(last), str(final))
                )

    print(f"bank items: {total}\n")
    print("last solution step does not state the answer:")
    for name, count in by_class.most_common():
        mark = "  <- unambiguous" if name in _UNAMBIGUOUS else ""
        print(f"  {count:>3}  {name}{mark}")
    print(f"\n  {len(unambiguous)} of {total} ({len(unambiguous) / total:.1%}) unambiguous")
    print(f"  {sum(by_class.values())} of {total} "
          f"({sum(by_class.values()) / total:.1%}) at the outer bound\n")

    print(f"{'skill':<28}{'unambiguous':>12}{'total':>7}  rate")
    for skill in sorted(by_skill, key=lambda s: -(by_skill[s] / skill_totals[s])):
        print(f"{skill:<28}{by_skill[skill]:>12}{skill_totals[skill]:>7}  "
              f"{by_skill[skill] / skill_totals[skill]:>5.0%}")

    print("\nitems:")
    for tid, _skill, last, final in unambiguous:
        print(f"  {tid:<44} [{last}] -> [{final}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
