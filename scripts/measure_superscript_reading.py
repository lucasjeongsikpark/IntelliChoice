"""The gate demands a notation it cannot read: superscript powers (D-297).

**The contradiction, in two checks introduced three days apart.** D-288 added
`check_math_notation_is_readable` because 64 shipped fields showed students SymPy; it tells
the generator to write "powers with superscripts like x²" and refuses `x**2` in any
student-facing field. The symbolic answer arm then parses an option with `_parse_side`, whose
substitution table (`_MATH_TEXT_SUBSTITUTIONS`) normalizes `−`, `–`, `—`, `×`, `÷` and `^`
(D-278) - **and not superscript digits**. So:

    _parse_side("x² - 5x + 4") -> ValueError: String "²" does not denote a Number

The generator is instructed to write `x²`, complies, and the verifier refuses to parse it.
Measured on the D-296 run: `alg2_rational_radical` 0 of 4, `alg2_exponential_log` 0 of 2,
`alg2_irrational` 0 of 2, every rejection of the form

    symbolic answer (x**3 - 8*x**2 + 19*x - 12)/(x - 3) does not match
    declared correct option 'c' ('x² − 5x + 4')

where the two sides are the same polynomial - `sympy.cancel` on the quotient returns the
option exactly.

**A correction to my own first diagnosis, kept because it was wrong in the interesting
direction.** I read that message as a missing `cancel` in the comparison, and the comparison
already does better than `cancel`: `simplify(expression - expected) == 0`. It never ran,
because the option never parsed. The uncancelled quotient in the message is a red herring -
it is just how the *derived* side prints.

**The proposal:** add superscript digits to the substitution table, `²` -> `**2`. Same
justification as D-278's `^`: it is the notation humans use, it means exactly one thing, and
the equation side and the option side should read it the same way.

**Both directions per D-221**, free because D-195 stores rejected candidate content:

- recall: how many rejected items' declared correct option now matches;
- **precision: how many items would gain a second matching option** - a distractor that also
  parses under the new reading is an ambiguous item, and admitting one is worse than the
  rejections this fixes.

Run: uv run python scripts/measure_superscript_reading.py
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from intellichoice_curriculum import authored_validation as av
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionValidationRun
from sqlalchemy import select

MISMATCH = "does not match"


def _matches_under(derivation: av.DerivedAnswer, text: str, *, with_superscripts: bool) -> bool:
    """`_option_matches`, with the superscript reading forced on or off.

    Calls the real gate on real stored text (the D-291 method) rather than reimplementing
    the rule, so this cannot drift from the behaviour it describes.

    Both arms stay meaningful after the fix shipped, because the reading is a *flag* on the
    real function rather than something this script patches in. An earlier version patched
    the substitution table instead, and once the fix shipped both arms became the same code
    and it reported that the change recovers nothing - a before/after measurement whose
    baseline had quietly become the treatment (D-293's expired premise, a second time).

    `if before: continue` in `main` mirrors the D-281 seam this reading actually lives in:
    it is consulted only when the first reading matched nothing, so an item the gate already
    accepts never reaches it.
    """
    try:
        return av._option_matches(derivation, text, expand_superscripts=with_superscripts)
    except Exception:
        return False


async def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            rows = list(
                (
                    await session.execute(
                        select(QuestionValidationRun).where(
                            QuestionValidationRun.outcome == "rejected"
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    candidates = [
        (r, (r.stage_results or {}).get("candidate_snapshot"))
        for r in rows
        if any("symbolic answer" in x and MISMATCH in x for x in (r.reasons or []))
    ]
    candidates = [(r, cs) for r, cs in candidates if cs]
    print(f"stored symbolic-mismatch rejections: {len(candidates)}")

    recovered = declined = unparseable = 0
    ambiguous: list[str] = []
    by_topic: collections.Counter[str] = collections.Counter()

    for _row, cs in candidates:
        equation = cs.get("equation") or ""
        derivation, error = av.route_answer(equation)
        if derivation is None or error is not None or derivation.model != "symbolic":
            unparseable += 1
            continue
        options = {k: cs.get(f"option_{k}") or "" for k in "abcd"}
        declared = cs.get("correct_option")
        def matched(on: bool, d: av.DerivedAnswer = derivation, o: dict = options) -> set[str]:
            return {k for k, t in o.items() if _matches_under(d, t, with_superscripts=on)}

        before, after = matched(False), matched(True)

        # The D-281 rule: a second reading may turn a rejection into a pass, never one pass
        # into a different pass. So only items matching nothing before are candidates.
        if before:
            continue
        if after == {declared}:
            recovered += 1
            by_topic[cs.get("topic_id") or "?"] += 1
        elif len(after) > 1:
            ambiguous.append(
                f"{cs.get('planned_template_id')}: options {sorted(after)} all match "
                f"(declared {declared!r})"
            )
        else:
            declined += 1

    print(f"\nrecall  - rejections the reading recovers:        {recovered}")
    print(f"        - by topic: {dict(by_topic.most_common())}")
    print(f"declined - still match nothing (a real defect):    {declined}")
    print(f"skipped  - equation does not route to `symbolic`:  {unparseable}")
    print(f"\nPRECISION - items that would gain a 2nd match:    {len(ambiguous)}")
    for line in ambiguous:
        print(f"  {line}")
    if not ambiguous:
        print("  none: no distractor becomes readable in a way that makes an item ambiguous")

    # The other precision direction: does the whole gate still reject a genuinely wrong key?
    print("\nnegative control - a wrong key must still fail:")
    for option, expect in (("x**2 - 5*x + 4", True), ("x² - 5x + 4", True), ("x² - 5x + 5", False)):
        derivation, _ = av.route_answer("(x**3 - 8*x**2 + 19*x - 12)/(x - 3)")
        assert derivation is not None
        got = _matches_under(derivation, option, with_superscripts=True)
        flag = "OK" if got is expect else "WRONG"
        print(f"  {option!r:<22} matches={got}  expected={expect}  [{flag}]")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
