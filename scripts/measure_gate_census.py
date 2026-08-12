"""Re-gate the entire shipped bank, and report per-check failures.

Run with:

    uv run python scripts/measure_gate_census.py
    uv run python scripts/measure_gate_census.py --check no_answer_leakage --show 20

**Why this exists.** ROADMAP C1 Phase 3's auto-approval criteria include "zero leaked-answer
and meta-text defects reaching `pending`". Four waves were auto-approved, so `pending` and
`approved` are the same population and that criterion is a property of the shipped bank. The
only honest way to state it is to run the checks over all of it.

**Free, and it writes nothing** - no database connection, no model call. It reads the bank
files, which are the artifact (D-190), and calls the same deterministic §5.8.5 gate the loader
calls on every insert and update.

**What the number means, precisely.** This measures the bank against *today's* gate, not against
the gate each item shipped under. Those differ - `check_math_notation_is_readable` (D-288) did
not exist when the 6-12 wave shipped, and 64 fields were rewritten to satisfy it after the fact.
So a clean census here says "nothing in the bank violates the rules we now hold", which is the
right claim for a go/no-go on *future* auto-approval, and is **not** the claim "no defect ever
reached pending". D-288 is the counter-example to that stronger claim and it is already recorded.

**`make curriculum-load` is not a substitute** and the difference has bitten before: the loader
gates on insert and update only, so a run reporting "N unchanged" verified nothing (the D-280
correction). This walks every item unconditionally.
"""

from __future__ import annotations

import argparse
import collections
import re
import sys

from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.authored_validation import (
    AuthoredValidationResult,
    check_no_answer_leakage,
    check_no_meta_commentary,
    validate_authored_item,
)

# The gate reports failures as prose, so attribution is by pattern. Ordered: the first match
# wins, so put the specific before the general.
_BUCKETS: list[tuple[str, str]] = [
    (r"leak|states the answer|reveals", "answer leakage"),
    (r"meta|as an ai|this question|the exam", "meta commentary"),
    (r"notation|`\*`|multiplication sign", "math notation"),
    (r"does not match declared|independent solve|sympy", "answer disagrees with key"),
    (r"option", "options"),
    (r"hint", "hint ladder"),
    (r"readab|words|sentence", "readability"),
    (r"figure|reading", "figure"),
    (r"difficulty|rubric", "difficulty rubric"),
    (r"markdown|schema", "schema/markdown"),
]


def _bucket(failure: str) -> str:
    lowered = failure.lower()
    for pattern, name in _BUCKETS:
        if re.search(pattern, lowered):
            return name
    return "other"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        choices=["all", "no_answer_leakage", "no_meta_commentary"],
        default="all",
        help="Run the whole gate (default) or one criterion check on its own",
    )
    parser.add_argument("--show", type=int, default=10, help="Failure examples to print")
    args = parser.parse_args()

    bank = load_authored_bank()
    total = sum(len(items) for items in bank.values())
    failing_items = 0
    buckets: collections.Counter[str] = collections.Counter()
    examples: list[str] = []
    per_topic: collections.Counter[str] = collections.Counter()

    for topic_id, templates in sorted(bank.items()):
        for template in templates:
            item = template.to_generated_item()
            if args.check == "all":
                result = validate_authored_item(
                    template.difficulty_label,
                    item,
                    figure=template.figure_spec,
                    figure_reading=template.figure_reading,
                )
            else:
                result = AuthoredValidationResult()
                check = (
                    check_no_answer_leakage
                    if args.check == "no_answer_leakage"
                    else check_no_meta_commentary
                )
                check(item, result)
            if result.passed:
                continue
            failing_items += 1
            per_topic[topic_id] += 1
            for failure in result.failures:
                buckets[_bucket(failure)] += 1
                if len(examples) < args.show:
                    examples.append(f"  [{template.question_template_id}] {failure}")

    print(f"bank items re-gated: {total} across {len(bank)} topics")
    print(f"check: {args.check}")
    print(f"items failing: {failing_items} ({failing_items / total:.1%})")
    if buckets:
        print("\nfailures by kind:")
        for name, count in buckets.most_common():
            print(f"  {name:26} {count}")
        print("\nby topic:")
        for topic_id, count in per_topic.most_common():
            print(f"  {topic_id:28} {count}")
        print("\nexamples:")
        print("\n".join(examples))
    return 1 if failing_items else 0


if __name__ == "__main__":
    sys.exit(main())
