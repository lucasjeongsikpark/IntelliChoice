"""Would a canonical-form tie-break recover the equal-valued-option rejections? (A4 sizing)

**The class this measures.** `check_sympy_independent_solve` derives the answer from the item's
own equation and refuses the item when **more than one option matches** that value. For most
skills that is exactly right - two options a student cannot tell apart must never both be on
screen. For a skill whose question asks for a *form* rather than a *value* it is wrong, and the
item it refuses is a good one:

    Reduce 12/18 to lowest terms.       12/18   6/9   2/3   4/6     <- all four equal 2/3
    Simplify √80.                       8√10    4√5   √16+√5  2√20  <- 4√5 and 2√20 both equal

A student reading either question has exactly one correct choice. The value test cannot see
that, because the distinguishing information is in **how the option is written**, and both
`sympify('4/6')` and `sqrt(80)` normalise it away before the comparison happens. So a
canonical-form check has to read the option **text**, which is also why it is safe: it is a
presentation rule sitting beside the value rule, not a weakening of it.

**Why this script exists before the code.** D-306 sized the recoverable share at "16 of 44" from
one reading of the rejections, and that estimate is mine rather than measured. A4 relaxes
duplicate detection, so the sizing decides whether the relaxation is worth its risk. Read-only
and free - D-195 stores candidate content with every rejection.

**What it reports.** Per skill, of the rejections whose reason is an equal-valued option:

- **recoverable** - narrowing the matching options to those in canonical form leaves **exactly
  one**, and it is the option the item declares correct
- **declared form is not canonical** - the item names the *unreduced* option as the answer; the
  rejection is correct and must stay
- **still ambiguous** - two or more matching options are canonical, or none is; no tie-break
- **no longer reproduces** - the current gate does not reach this failure any more (D-297/D-298
  admitted readings the run predated)

Both predicates are applied to every row regardless of skill, so the census says *which* form
each skill needs rather than assuming it. The shipped check is declared per skill.

    uv run python scripts/measure_canonical_form.py
    uv run python scripts/measure_canonical_form.py --show 8
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.authored_validation import (
    ANSWER_FORMS,
    matching_options,
    route_answer,
)
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionValidationRun
from sqlalchemy import select

_EQUAL_VALUE_REASON = "more than one option matches"

# Imported from the gate rather than reimplemented here. `matching_options`' own docstring
# records the cost of the alternative: that reading sequence was inline in the gate and
# duplicated in a census, and the duplicate expired **three times** as new readings were
# admitted, each time leaving the census asserting a rule the gate had moved past. A census
# that disagrees with the gate measures nothing.
_FORMS = ANSWER_FORMS


def _options(snapshot: dict) -> dict[str, str]:
    return {k: snapshot.get(f"option_{k}") or "" for k in "abcd"}


def _verdict(snapshot: dict) -> tuple[str, str]:
    """Classify one stored rejection. Returns (verdict, detail)."""
    equation = snapshot.get("equation") or ""
    correct = snapshot.get("correct_option") or ""
    options = _options(snapshot)

    derivation, error = route_answer(equation)
    if derivation is None:
        return "no longer reproduces", f"equation no longer solves: {error}"

    matches, derivation = matching_options(derivation, options, equation)
    if len(matches) <= 1:
        return "no longer reproduces", f"the current gate matches {matches}"

    # Every form is tried before any verdict is returned. Returning on the first form that
    # resolves to *one* option would report "declared form is not canonical" for an item that
    # a second form resolves correctly - the same first-reading-wins mistake D-281 guards
    # against, in a census instead of a gate.
    resolved: list[tuple[str, str]] = []
    for form, predicate in _FORMS.items():
        canonical = [label for label in matches if predicate(options[label]) is True]
        if len(canonical) == 1:
            resolved.append((form, canonical[0]))

    for form, label in resolved:
        if label == correct:
            beaten = [options[m] for m in matches if m != correct]
            return f"recoverable ({form})", f"{options[correct]!r} over {beaten}"
    if resolved:
        form, label = resolved[0]
        return (
            "declared form is not canonical",
            f"declares {options[correct]!r}; the {form} option is {options[label]!r}",
        )

    readable = {
        form: [options[m] for m in matches if p(options[m]) is True] for form, p in _FORMS.items()
    }
    return "still ambiguous", f"matches {[options[m] for m in matches]}, canonical {readable}"


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--show", type=int, default=4, help="Examples per skill per verdict")
    args = parser.parse_args()

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            rows = (await session.execute(select(QuestionValidationRun))).scalars().all()
    finally:
        await engine.dispose()

    rejections = [
        row
        for row in rows
        if row.outcome != "accepted"
        and any(_EQUAL_VALUE_REASON in str(r) for r in (row.reasons or []))
    ]
    # **A filter that belongs here does not exist, and saying so is the point.** A slot whose
    # later repair attempt was accepted already produced content, so recovering its earlier
    # rejection would add nothing - and I wrote that filter, ran it, and it excluded 0 of 59.
    # The reason is structural: D-195 stores `candidate_snapshot` *with a rejection*, so
    # `accepted` rows carry none and no (skill, seed) can ever match one. Measured:
    # 606 rows hold a snapshot, **0** of them accepted. A filter that cannot match is not a
    # safeguard, so it is gone and the residual uncertainty is stated instead - the bank
    # counts below are what bound it from the other side.
    print(f"validation runs on record: {len(rows)}")
    print(f"equal-valued-option rejections: {len(rejections)}\n")

    per_skill: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    examples: dict[tuple[str, str], list[str]] = collections.defaultdict(list)
    totals: collections.Counter = collections.Counter()
    # A slot's repair attempts each write their own row (D-198), so `1/3 cup` / `1/3 cups` /
    # `1/3 cup` is one slot re-rolled three times, not three recoverable items. Counting
    # attempts sizes how much rejection VOLUME the check absorbs; counting slots sizes how
    # much distinct CONTENT it recovers, and only the second is depth.
    slots: dict[tuple[str, object], str] = {}

    for row in rejections:
        snapshot = (row.stage_results or {}).get("candidate_snapshot") or {}
        if not snapshot:
            per_skill["(no snapshot)"]["no snapshot stored"] += 1
            totals["no snapshot stored"] += 1
            continue
        skill = snapshot.get("skill_id") or "(unknown)"
        verdict, detail = _verdict(snapshot)
        per_skill[skill][verdict] += 1
        totals[verdict] += 1
        examples[(skill, verdict)].append(detail)
        key = (skill, snapshot.get("seed"))
        if key not in slots or verdict.startswith("recoverable"):
            slots[key] = verdict

    verdicts = sorted(totals, key=lambda v: (not v.startswith("recoverable"), v))
    print("by skill:")
    width = max(len(s) for s in per_skill) + 2
    print(f"  {'skill':<{width}}{'n':>4}  " + "  ".join(f"{v:<34}" for v in verdicts))
    for skill in sorted(per_skill, key=lambda s: -sum(per_skill[s].values())):
        counts = per_skill[skill]
        cells = "  ".join(f"{counts.get(v, 0):<34}" for v in verdicts)
        print(f"  {skill:<{width}}{sum(counts.values()):>4}  {cells}")

    print(
        f"\n  {'TOTAL':<{width}}{sum(totals.values()):>4}  "
        + "  ".join(f"{totals.get(v, 0):<34}" for v in verdicts)
    )

    recoverable = sum(n for v, n in totals.items() if v.startswith("recoverable"))
    slot_counts = collections.Counter(slots.values())
    slot_recoverable = sum(n for v, n in slot_counts.items() if v.startswith("recoverable"))
    recoverable_slots = collections.Counter(
        skill for (skill, _seed), verdict in slots.items() if verdict.startswith("recoverable")
    )
    print(
        f"\nthe A4 sizing, in the two units that can be measured:\n"
        f"  rejection attempts absorbed: {recoverable} of {sum(totals.values())} "
        f"({recoverable / max(1, sum(totals.values())) * 100:.0f}%)  <- review/spend volume\n"
        f"  distinct slots recovered:    {slot_recoverable} of {len(slots)} "
        f"({slot_recoverable / max(1, len(slots)) * 100:.0f}%)  <- the content number"
    )

    bank = collections.Counter(
        template.skill_id for templates in load_authored_bank().values() for template in templates
    )
    print("\nwhat each affected skill holds today, which is what makes the number mean something:")
    print(f"  {'skill':<26}{'in bank':>9}{'slots A4 recovers':>20}")
    for skill, n in recoverable_slots.most_common():
        flag = "   <- UNSTOCKED: no item has ever passed" if bank.get(skill, 0) == 0 else ""
        print(f"  {skill:<26}{bank.get(skill, 0):>9}{n:>20}{flag}")

    for (skill, verdict), details in sorted(examples.items()):
        print(f"\n{skill} - {verdict} ({len(details)}):")
        for detail in details[: args.show]:
            print(f"    {detail}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
