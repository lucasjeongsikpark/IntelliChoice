"""Is `multi_root` rejecting correct items the way `interval` was? (C1 Phase 3 measurement)

**The observation.** The Phase 3 serving-floor batch opened with `algebra_1` difficulty 1 and
took 0 of 3, every rejection identical in shape:

    multi_root answer frozenset({-8, 8}) derived from the equation does not match
    declared correct option 'b' ('8 metres')

A square of area 64 m² has a side of 8 metres. `Eq(x**2, 64)` has roots ±8, and the gate
compared the *set* against the *value* a student writes - which is precisely D-281's interval
defect (`Interval(7, oo)` vs "7 months") in a second answer model. `alg1_square_roots` had
never produced an accepted item at tier 1, and the historical rejections say the same: four
more, same message.

**The proposal, and why it is narrower than "take the positive root".** Only when the first
reading matched nothing (the D-281 rule - this can turn a rejection into a pass, never one
pass into a different one), and only when:

1. exactly one root is positive, and
2. **no option matches any of the non-positive roots.**

Rule 2 is the one that protects precision, and it is not decoration. An abstract item -
"solve x² = 64" with options 8, -8, 16, 4 - offers the negative root as a distractor, which
is exactly the case where "8" alone is a *wrong* key and the set reading is right. A
measurement item never offers "-8 metres" as a choice, because a length cannot be negative.
So the item's own options carry the domain constraint, and the gate reads it off data it
already trusts rather than parsing the stem for units or asking a model.

This script decides nothing. It re-gates the stored candidates - free, because D-195 keeps a
rejected candidate's content - and reports **both directions** per D-221: what the rule
recovers, and what it would wrongly let through.

Run: uv run python scripts/measure_multi_root_reading.py [--hours N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from dataclasses import dataclass, field

from intellichoice_curriculum.authored_validation import (
    DerivedAnswer,
    _option_matches,
    _options,
    route_answer,
    validate_authored_item,
)
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"

MISMATCH = "derived from the equation does not match"


@dataclass
class Report:
    considered: int = 0
    verdicts: Counter[str] = field(default_factory=Counter)
    recovered: list[str] = field(default_factory=list)
    declined: list[str] = field(default_factory=list)
    control_flips: list[str] = field(default_factory=list)


def _item_from(snapshot: dict) -> AuthoredGeneratedItemResponse | None:
    fields = set(AuthoredGeneratedItemResponse.model_fields)
    try:
        return AuthoredGeneratedItemResponse.model_validate(
            {k: v for k, v in snapshot.items() if k in fields}
        )
    except Exception:
        return None


def positive_root_reading(
    derivation: DerivedAnswer, options: dict[str, str]
) -> tuple[DerivedAnswer | None, str]:
    """The candidate second reading, with the reason when it declines.

    Returns `(reading, detail)`. `reading` is None whenever the rule refuses, and `detail`
    always says why - a measurement that only reports its successes cannot be checked.
    """
    if derivation.model != "multi_root" or not isinstance(derivation.payload, frozenset):
        return None, "not multi_root"
    roots = list(derivation.payload)
    if not all(getattr(root, "is_number", False) for root in roots):
        return None, "a root is not a number"
    positive = [root for root in roots if root.is_positive]
    if len(positive) != 1:
        return None, f"{len(positive)} positive roots, not exactly one"
    others = [root for root in roots if not root.is_positive]
    offered = [
        label
        for label, textual in options.items()
        if any(_option_matches(DerivedAnswer("value", (other,)), textual) for other in others)
    ]
    if offered:
        return None, f"a non-positive root is offered as option(s) {offered}"
    return DerivedAnswer("value", (positive[0],)), f"positive root {positive[0]}"


def verdict_for(item: AuthoredGeneratedItemResponse) -> tuple[str, str]:
    derivation, _ = route_answer(item.equation or "")
    if derivation is None:
        return "unroutable", "route_answer returned nothing"
    options = _options(item)
    first = [label for label, textual in options.items() if _option_matches(derivation, textual)]
    if first:
        return "not_applicable", "the first reading already matched"
    reading, detail = positive_root_reading(derivation, options)
    if reading is None:
        return "declined", detail
    second = [label for label, textual in options.items() if _option_matches(reading, textual)]
    if len(second) != 1:
        return "still_ambiguous", f"{detail}; matched {len(second)} options"
    if second[0] != item.correct_option:
        return "would_be_wrong", f"{detail}; matches {second[0]}, key is {item.correct_option}"
    return "recovered", detail


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=200, help="look-back window (default 200)")
    args = parser.parse_args()

    engine = create_async_engine(os.environ.get("LEARNING_DATABASE_URL", DEFAULT_URL))
    report = Report()

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT outcome, stage_results::text, reasons::text "
                    "FROM question_validation_runs "
                    "WHERE created_at > now() - make_interval(hours => :h)"
                ),
                {"h": args.hours},
            )
        ).all()

    for outcome, stage_raw, reasons_raw in rows:
        snapshot = (json.loads(stage_raw) or {}).get("candidate_snapshot")
        if not snapshot:
            continue
        item = _item_from(snapshot)
        if item is None:
            continue

        if outcome == "rejected" and MISMATCH in (reasons_raw or "") and "multi_root" in (
            reasons_raw or ""
        ):
            report.considered += 1
            verdict, detail = verdict_for(item)
            report.verdicts[verdict] += 1
            line = f"  [{snapshot.get('skill_id', '?')}] {item.equation}  ->  {detail}"
            if verdict == "recovered" and len(report.recovered) < 10:
                report.recovered.append(f"{line}\n      stem: {item.stem[:110]}")
            elif verdict != "recovered" and len(report.declined) < 10:
                report.declined.append(f"  [{verdict}] {line}")

        # Both directions (D-221). An item the gate ACCEPTED must not change verdict.
        #
        # **This control is vacuous on the accepted side and the count is not evidence** -
        # only rejected runs store a snapshot (the D-281 correction, kept here rather than
        # rediscovered). What it *can* still catch is a rejected-for-another-reason item
        # that this rule would now wave through, which is why the loop re-gates rather than
        # filtering on the message alone.
        elif outcome == "rejected":
            gate = validate_authored_item(
                snapshot.get("requested_difficulty") or item.proposed_difficulty, item
            )
            if not gate.passed and verdict_for(item)[0] == "recovered":
                report.control_flips.append(f"  {item.equation}: {gate.failures[:1]}")

    print(f"multi_root mismatch rejections considered: {report.considered}")
    for verdict, count in report.verdicts.most_common():
        print(f"  {verdict:18} {count}")
    if report.recovered:
        print("\nrecovered:")
        print("\n".join(report.recovered))
    if report.declined:
        print("\ndeclined (the precision side - these stay rejected):")
        print("\n".join(report.declined))
    print(
        "\nitems rejected for OTHER reasons this rule would wave through: "
        f"{len(report.control_flips)}"
    )
    for line in report.control_flips[:10]:
        print(line)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
