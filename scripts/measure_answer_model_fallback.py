"""How many rejected candidates were rejected for being right? (D-281 measurement)

The 6-8/9-12 re-run rejected 168 candidates, and 60 of them carry one message:

    symbolic answer -2*t**2 + 10*t - 12 derived from the equation does not match
    declared correct option 'd' ('2 seconds and 3 seconds')

That item is correct. The stem asks "at what two times is the balloon at ground level",
`-2t^2 + 10t - 12 = 0` has roots 2 and 3, and option d says "2 seconds and 3 seconds".
What failed is the *routing*: the Generator wrote the expression `-2*t**2 + 10*t - 12`
rather than the equation `Eq(-2*t**2 + 10*t - 12, 0)`, and `route_answer` reads a bare
polynomial as the `symbolic` model - "the answer IS this expression" - so it compared a
polynomial against the string "2 seconds and 3 seconds".

`route_answer` infers the model from the equation's form on purpose (D-252: a declared
model is a second field that can disagree with the first). That principle is not in
question here. The problem is narrower: **a bare polynomial with free symbols is
genuinely ambiguous** - "simplify this" and "solve this = 0" have the same form - and the
router resolves the ambiguity by fiat rather than by evidence.

The proposal measured here: when the symbolic reading matches *no* option, try reading the
same expression as `Eq(expr, 0)`. Accept only if that second reading matches **exactly
one** option. The item's own options are the tiebreak, and they are data the gate already
trusts - nothing is asked of a model, and an item whose answer is still ambiguous under
both readings stays rejected.

This script decides nothing. It re-gates the stored candidates (D-195 keeps their content,
so this is free - no Bedrock call, no spend) and reports both directions, per D-221:
recall (how many correct items the fallback recovers) *and* precision (whether it lets
anything through that should stay out).

Run: uv run python scripts/measure_answer_model_fallback.py [--hours N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from dataclasses import dataclass, field

import sympy
from intellichoice_curriculum.authored_validation import (
    DerivedAnswer,
    _option_matches,
    _options,
    route_answer,
    validate_authored_item,
)
from intellichoice_curriculum.content import load_curriculum
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"

MISMATCH = "derived from the equation does not match"


# ---------------------------------------------------------------------------------------
# The proposal, implemented here rather than in the gate - measure before changing.
# ---------------------------------------------------------------------------------------


def solve_reading(equation: str) -> DerivedAnswer | None:
    """The same expression read as `expr = 0`, or None if that is not a legal reading."""
    derivation, _ = route_answer(f"Eq({equation}, 0)")
    return derivation


def boundary_reading(payload: object, *, whole_numbers: bool) -> DerivedAnswer | None:
    """The extreme value of a solution set - what "the smallest number of days" means.

    `12 + 6*m >= 54` solves to `Interval(7, oo)`, and the question asks for 7. The set and
    its boundary are different answers to different questions, and only one of them is a
    number a student writes.

    The open/closed distinction is the whole risk here and is why this is not a plain
    `.left`: `m >= 7` admits 7, but `m > 7` does not - its smallest *whole* value is 8, and
    for a continuous quantity there is no smallest value at all. So an open boundary yields
    an answer only when the skill's answer family says the quantity is counted (D-274).
    Getting this wrong in the lenient direction would accept an off-by-one, which is
    precisely the distractor these items carry.
    """
    if not isinstance(payload, sympy.Interval):
        return None
    for endpoint, is_open, step in (
        (payload.left, payload.left_open, 1),
        (payload.right, payload.right_open, -1),
    ):
        if endpoint in (sympy.oo, -sympy.oo) or not endpoint.is_number:
            continue
        if not is_open:
            return DerivedAnswer("value", (endpoint,))
        if whole_numbers and endpoint.is_integer:
            return DerivedAnswer("value", (endpoint + step,))
        return None
    return None


def fallback_verdict(
    item: AuthoredGeneratedItemResponse, *, whole_numbers: bool = True
) -> tuple[str, str]:
    """`(verdict, detail)` for one item under the proposed fallback.

    Verdicts: `recovered` (the second reading matches exactly the declared option),
    `still_ambiguous` (matches several), `still_wrong` (matches none, or matches a
    different option - the declared answer really is wrong), `not_applicable`.
    """
    if not item.equation:
        return "not_applicable", "no equation"
    derivation, error = route_answer(item.equation)
    if derivation is None:
        return "not_applicable", error or "unroutable"
    if derivation.model not in ("symbolic", "interval"):
        return "not_applicable", f"model is {derivation.model}, no second reading defined"

    options = _options(item)
    if any(_option_matches(derivation, t) for t in options.values()):
        return "not_applicable", f"{derivation.model} reading already matches an option"

    if derivation.model == "interval":
        second = boundary_reading(derivation.payload, whole_numbers=whole_numbers)
        if second is None:
            return "still_wrong", f"{derivation.payload} has no well-defined extreme value"
    else:
        second = solve_reading(item.equation)
    if second is None:
        return "still_wrong", "expression is not solvable as expr = 0"

    matches = [label for label, t in options.items() if _option_matches(second, t)]
    if not matches:
        return "still_wrong", f"solve reading {second.payload} matches no option"
    if len(matches) > 1:
        return "still_ambiguous", f"solve reading matches {matches}"
    if matches[0] != item.correct_option:
        return (
            "still_wrong",
            f"solve reading matches option {matches[0]!r}, but {item.correct_option!r} "
            f"is declared correct - the declared answer is wrong",
        )
    return "recovered", f"{second.model} {second.payload} == option {matches[0]!r}"


# ---------------------------------------------------------------------------------------


@dataclass
class Report:
    considered: int = 0
    verdicts: Counter[str] = field(default_factory=Counter)
    recovered_examples: list[str] = field(default_factory=list)
    wrong_examples: list[str] = field(default_factory=list)
    control_flips: list[str] = field(default_factory=list)


def _counts_in_whole_numbers(skill_id: str | None) -> bool:
    """Does this skill's answer family count in whole numbers? Fail closed if unknown.

    `False` is the conservative answer: it makes `boundary_reading` decline to guess on an
    open boundary rather than assume the quantity is countable.
    """
    if not skill_id:
        return False
    try:
        return load_curriculum().skill(skill_id).family.whole_numbers_only
    except Exception:
        return False


def _item_from(snapshot: dict) -> AuthoredGeneratedItemResponse | None:
    fields = set(AuthoredGeneratedItemResponse.model_fields)
    try:
        return AuthoredGeneratedItemResponse.model_validate(
            {k: v for k, v in snapshot.items() if k in fields}
        )
    except Exception:
        return None


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=6, help="look-back window (default 6)")
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

        if outcome == "rejected" and MISMATCH in (reasons_raw or ""):
            report.considered += 1
            verdict, detail = fallback_verdict(
                item, whole_numbers=_counts_in_whole_numbers(snapshot.get("skill_id"))
            )
            report.verdicts[verdict] += 1
            line = f"  [{snapshot.get('skill_id','?')}] {item.equation}  ->  {detail}"
            if verdict == "recovered" and len(report.recovered_examples) < 8:
                report.recovered_examples.append(f"{line}\n      stem: {item.stem[:110]}")
            if verdict == "still_wrong" and len(report.wrong_examples) < 6:
                report.wrong_examples.append(line)

        # Negative control (D-246, both directions): an item the gate ACCEPTED must not
        # change verdict under the fallback.
        #
        # **This control is vacuous and the count below is not evidence.** Only *rejected*
        # runs store a `candidate_snapshot` - 158 accepted runs in the measured window
        # carried none - so there is nothing here to re-gate and the loop reports 0
        # because it examined 0. Left in place, and labelled, because deleting it would
        # leave the next reader to rediscover that the accepted side is unobservable from
        # this table. The precision claim rests on the structural argument (the second
        # reading runs only when the first matched nothing, so an accepted item never
        # reaches it) and on the distractor tests in `test_second_reading.py`, not on this.
        elif outcome != "rejected":
            gate = validate_authored_item(
                snapshot.get("requested_difficulty") or item.proposed_difficulty, item
            )
            if gate.passed and fallback_verdict(item)[0] != "not_applicable":
                report.control_flips.append(f"  {item.equation}")

    print(
        f"\nRe-gated {len(rows)} stored runs from the last {args.hours}h "
        f"(free, no model call).\n"
    )
    print(f"Candidates rejected for an answer mismatch: {report.considered}")
    for verdict, n in report.verdicts.most_common():
        share = f"{100 * n / report.considered:.0f}%" if report.considered else "-"
        print(f"  {verdict:<16} {n:>4}  {share}")

    print("\nRECOVERED - correct items the current gate rejects:")
    for line in report.recovered_examples:
        print(line)

    print("\nSTILL REJECTED - the fallback does not rescue these:")
    for line in report.wrong_examples:
        print(line)

    print(
        f"\nNegative control: {len(report.control_flips)} accepted items would change "
        f"verdict -- VACUOUS, see the comment above: accepted runs store no snapshot, so "
        f"this examined nothing. Not evidence."
    )
    for line in report.control_flips:
        print(line)

    await engine.dispose()


if __name__ == "__main__":
    sympy.init_printing(use_unicode=False)
    asyncio.run(main())
