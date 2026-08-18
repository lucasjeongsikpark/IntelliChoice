"""Do the pipeline's run summaries and `question_validation_runs.cost_cents` agree? (D-294)

**The observation this exists to resolve.** C1 carried an undiagnosed carry-over: the
pipeline's own run summaries totalled **1278c** for one session's runs while
`question_validation_runs.cost_cents` summed to **884c** over the same window, with
candidate counts nearly matching (368 vs 378). Cost accounting is CLAUDE.md rule 7, so a
31% gap in it is a real defect and not a rounding story.

**The cause, found by reconciling one slot rather than by re-querying the window.** The
equation-design call is made by `generate_authored_candidate` **once per slot, before**
`_attempt_authored_candidate` - which is the function that writes the rows. So the design
cost reached `RunSummary` through the caller's running total and reached no row at all.
The only rows that ever carried it were the pure design *failures*, which return before
the inner function exists.

That makes `cost_cents` mean two different things on two kinds of row, which is worse than
a uniform undercount: no single multiplier corrects it. D-294 fixed the write path and
`test_a_slots_rows_account_for_every_cent_the_slot_reports` pins the invariant.

**What this script is for now.** Two jobs, both read-only and free:

1. **Quantify the historical gap** from rows written before the fix, so the 31% is
   explained arithmetically instead of asserted. A design attempt's real cost is
   recoverable because design-failure rows record spend *and* attempt count.
2. **Re-check the invariant against real runs** after the fix, by reporting how many
   accepted rows carry a design record. Every post-fix accepted row should.

Run (read-only, no model calls):

    uv run python scripts/measure_spend_reconciliation.py
    uv run python scripts/measure_spend_reconciliation.py --since 2026-08-11
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from datetime import UTC, datetime

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionValidationRun
from sqlalchemy import select


def _design(row: QuestionValidationRun) -> dict:
    return (row.stage_results or {}).get("equation_design") or {}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default=None, help="ISO date; default is every row")
    args = parser.parse_args()

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            stmt = select(QuestionValidationRun)
            if args.since:
                # Parsed rather than passed through: asyncpg binds a bare string as
                # VARCHAR and Postgres has no `timestamptz >= varchar` operator, so the
                # filter fails loudly instead of silently matching everything.
                since = datetime.fromisoformat(args.since).replace(tzinfo=UTC)
                stmt = stmt.where(QuestionValidationRun.created_at >= since)
            rows = list((await session.execute(stmt)).scalars().all())
    finally:
        await engine.dispose()

    if not rows:
        print("no question_validation_runs rows in range")
        return 0

    # A design *failure* row is the clean isolate for what a design attempt costs: nothing
    # else ran on that path, and the failure list is one entry per attempt.
    per_attempt: list[float] = []
    for row in rows:
        design = _design(row)
        attempts = design.get("attempts") or []
        if design.get("passed") is False and attempts and row.cost_cents > 0:
            per_attempt.append(float(row.cost_cents) / len(attempts))

    accepted = [r for r in rows if r.question_template_id is not None]
    # Post-fix rows record the design they paid for; pre-fix rows carry the money silently.
    accepted_with_design = [r for r in accepted if _design(r).get("passed") is True]
    accepted_without = [r for r in accepted if not _design(r)]

    print(f"rows in range:              {len(rows)}")
    print(f"  accepted (has template):  {len(accepted)}")
    print(f"    recording their design: {len(accepted_with_design)}  (D-294 and later)")
    print(f"    silent about design:    {len(accepted_without)}  (written before D-294)")
    print(f"  design-failure isolates:  {len(per_attempt)}")
    print(f"sum(cost_cents):            {sum(float(r.cost_cents) for r in rows):.2f}c")

    if not per_attempt:
        print("\nno design-failure rows: cannot price a design attempt from this range")
        return 0

    median_design = statistics.median(per_attempt)
    print(
        f"\ncost per design attempt:    median {median_design:.4f}c "
        f"(min {min(per_attempt):.4f}, max {max(per_attempt):.4f}, n={len(per_attempt)})"
    )

    if accepted_without:
        avg = statistics.mean(float(r.cost_cents) for r in accepted_without)
        true = avg + median_design
        print(f"\npre-D-294 accepted rows:    avg {avg:.4f}c recorded")
        print(f"  true cost if designed once: {true:.4f}c")
        print(f"  those rows understate their slots by {median_design / true * 100:.1f}%")
        print("  ^ compare against the 31% the C1 carry-over reported")

    if accepted_with_design:
        recorded = [float(_design(r)["cost_cents"]) for r in accepted_with_design]
        print(
            f"\npost-D-294 accepted rows:   {len(recorded)} record a design cost, "
            f"median {statistics.median(recorded):.4f}c"
        )
        missing = [r for r in accepted_with_design if not _design(r).get("cost_cents")]
        if missing:
            print(f"  WARNING: {len(missing)} claim a passed design with no cost recorded")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
