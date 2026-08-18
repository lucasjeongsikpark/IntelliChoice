"""Did the dispersion guard, not the tier disagreement, discard 117 paid candidates? (D-295)

**The observation.** `judge_difficulty` treats `slot_gap >= 2` as *re-tier the item to the
judge's tier* when the run's histogram shows the judge discriminating, and as *reject* only
when it does not (`_DIFFICULTY_RETIER_AT`, `may_retier`). Across every recorded candidate:

    accepted 329 | flagged 325 | retiered 87 | rejected 117

The bottom two rows are the same disagreement at the same tiers - d4 ×28 / d5 ×41 retiered
against d4 ×64 / d5 ×40 rejected. So 117 candidates that had already passed the generator,
both solvers and every judge flag were discarded by the *guard*, not by the gap. D-239 built
the re-tier precisely to stop that happening.

**The hypothesis this was written to test, and the measurement that killed it.** The first
reading was that a batch deliberately targeting tiers 4-5 gets mostly-2 answers from a
judge that drifts downward (D-292), looking exactly like a collapsed instrument, so
`_JUDGE_COLLAPSE_SHARE` fires. **Measured: false.** The runs whose histograms collapse are
*small* (n=5-7), not tier-homogeneous - their dominant requested tier is 33-60%, no higher
than runs that re-tier freely.

**What is actually happening is a warm-up cost, and it is structural.**
`_MIN_JUDGE_OBSERVATIONS = 5` means the guard blocks **100% of candidates at positions 1-4
of every run** and ~1-2% at position 11 and beyond - stable across both grouping
thresholds:

    position in run:   1     2     3     4     5     6    7-10   11+
    blocked:         100%  100%  100%  100%   35%   31%   13%   0.6%     (600s grouping)

So the cost driver is **the number of runs, not the tier mix**: every `run_plan` invocation
pays about four un-retierable candidates before its own evidence exists. Phase 3's depth
pass ran many small per-topic batches, and each one paid that toll. The tier-4/5
concentration in the rejections follows rather than causes it - those are the slots where
the judge's downward drift produces a gap of 2 most often, so they take the warm-up hit.

That makes the remedy operational before it is a code change: **fewer, larger runs**, which
is not a workaround but the design used as intended - D-231 scoped the histogram to a run
precisely so a stale instrument could not authorise today's moves.

**Why this is a reconstruction, and the cost of that.** `question_validation_runs` carries
**no run identifier**, so runs cannot be recovered from the table - they are inferred by
clustering `created_at`. The threshold is not chosen by taste: the replay recomputes each
candidate's decision from the real `JudgeDispersion` and the real `judge_difficulty`, and
the sweep reports which threshold reproduces the *recorded* decisions. A grouping that
cannot reproduce them is wrong, and the script says so rather than reporting a number.

Free and read-only - no model calls.

Run:

    uv run python scripts/measure_retier_guard.py
    uv run python scripts/measure_retier_guard.py --gap-seconds 600 --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from intellichoice_curriculum.ai_pipeline import JudgeDispersion, judge_difficulty
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionValidationRun
from sqlalchemy import select

# Swept rather than picked. Measured inter-candidate gaps: median 41s, p90 113s, then a
# thin tail (55 gaps in 2-10m, 12 in 10m-1h, 9 over 1h), so the plausible boundary sits
# somewhere in that tail and the replay is what decides where.
GAP_CANDIDATES = (120, 300, 600, 1800, 3600)


def _evidence(row: QuestionValidationRun) -> dict:
    return (row.stage_results or {}).get("difficulty") or {}


def _replay(rows: list[QuestionValidationRun], gap_seconds: float) -> dict:
    """Recompute every candidate's difficulty decision, run by inferred run.

    Uses the production `JudgeDispersion` and `judge_difficulty` rather than a local copy
    of the rule, so this measurement cannot drift away from the behaviour it describes.
    """
    runs = _group(rows, gap_seconds)

    agree = disagree = 0
    # A rejection the guard caused: the gap was re-tierable and only `may_retier` said no.
    guard_caused = 0
    blocked_by_run: collections.Counter[int] = collections.Counter()
    mismatches: list[str] = []

    for run in runs:
        dispersion = JudgeDispersion()
        for row in run:
            ev = _evidence(row)
            recorded = ev.get("decision")
            try:
                reviewed = int(ev["judge_reviewed_difficulty"])
                requested = int(ev["requested_difficulty"])
                proposed = int(ev["generator_proposed_difficulty"])
            except (KeyError, TypeError, ValueError):
                # Pre-D-194 rows predate these fields. Skipped rather than defaulted: a
                # replay that invented a tier would report agreement it did not measure.
                continue
            if recorded is None:
                continue
            # The candidate joins the histogram before the gate reads it (ai_pipeline
            # states this explicitly), so observe first.
            dispersion.observe(reviewed)
            may_retier = dispersion.permits_retier()
            verdict = judge_difficulty(
                proposed=proposed,
                proposed_rationale="",
                reviewed=reviewed,
                reviewed_rationale="",
                requested=requested,
                may_retier=may_retier,
            )
            if verdict.decision == recorded:
                agree += 1
            else:
                disagree += 1
                if len(mismatches) < 10:
                    mismatches.append(
                        f"{row.question_validation_run_id}: recorded {recorded}, "
                        f"replayed {verdict.decision} "
                        f"(d{requested}->d{reviewed}, may_retier={may_retier})"
                    )
            if recorded == "rejected" and verdict.slot_gap >= 2 and not may_retier:
                guard_caused += 1
                blocked_by_run[len(run)] += 1

    return {
        "runs": len(runs),
        "agree": agree,
        "disagree": disagree,
        "guard_caused": guard_caused,
        "mismatches": mismatches,
        "run_sizes": sorted((len(r) for r in runs), reverse=True),
    }


def _group(
    rows: list[QuestionValidationRun], gap_seconds: float
) -> list[list[QuestionValidationRun]]:
    runs: list[list[QuestionValidationRun]] = []
    for row in rows:
        if runs and (row.created_at - runs[-1][-1].created_at).total_seconds() <= gap_seconds:
            runs[-1].append(row)
        else:
            runs.append([row])
    return runs


def _warm_up_cost(rows: list[QuestionValidationRun], gap_seconds: float) -> None:
    """Where in a run does the guard actually block? This is the finding.

    Separates the two candidate explanations, which predict different shapes: a *collapse*
    effect would block wherever the judge happens to be constant, spread through a run; a
    *warm-up* effect blocks the opening positions of every run and then stops. It is the
    second, and the shape is stable whichever grouping threshold is used - which is why
    this conclusion survives the reconstruction's ~90% fidelity while the exact
    guard-caused count does not.
    """
    runs = _group(rows, gap_seconds)
    blocked: collections.Counter[object] = collections.Counter()
    total: collections.Counter[object] = collections.Counter()
    for run in runs:
        dispersion = JudgeDispersion()
        for i, row in enumerate(run, start=1):
            try:
                reviewed = int(_evidence(row)["judge_reviewed_difficulty"])
            except (KeyError, TypeError, ValueError):
                continue
            dispersion.observe(reviewed)
            bucket: object = i if i <= 6 else ("7-10" if i <= 10 else "11+")
            total[bucket] += 1
            if not dispersion.permits_retier():
                blocked[bucket] += 1

    print(f"\nwhere the guard blocks, over {len(runs)} inferred runs:")
    print("  position in run   blocked / candidates")
    for bucket in [1, 2, 3, 4, 5, 6, "7-10", "11+"]:
        if total[bucket]:
            share = blocked[bucket] / total[bucket] * 100
            print(
                f"  {str(bucket):>13}   {blocked[bucket]:>4} / {total[bucket]:<5} ({share:>5.1f}%)"
            )
    print(
        f"\n  structural floor: {4 * len(runs)} candidate-slots cannot be re-tiered no matter "
        f"what,\n  because _MIN_JUDGE_OBSERVATIONS is 5 and every run starts with an empty "
        f"histogram.\n  That is a per-run toll: fewer, larger runs pay it once."
    )

    # The falsified reading, kept because a hypothesis that was measured and dropped is
    # worth more than one that was never written down.
    print("\n  and the reading this does NOT support - collapsed runs are small, not")
    print("  tier-homogeneous:")
    print("    run   n   dominant requested tier   judged-tier share")
    for i, run in enumerate(runs):
        # Below _MIN_JUDGE_OBSERVATIONS a run could never re-tier regardless, so its
        # histogram says nothing about collapse.
        if len(run) < 5:
            continue
        judged = collections.Counter(_evidence(r).get("judge_reviewed_difficulty") for r in run)
        if not judged or max(judged.values()) / len(run) < 0.8:
            continue
        requested = collections.Counter(_evidence(r).get("requested_difficulty") for r in run)
        print(
            f"    {i:>3}  {len(run):>3}   d{max(requested, key=lambda k: requested[k])} at "
            f"{max(requested.values()) / len(run):>4.0%}              "
            f"{max(judged.values()) / len(run):>4.0%}"
        )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gap-seconds", type=float, default=None, help="skip the sweep")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            rows = list(
                (
                    await session.execute(
                        select(QuestionValidationRun).order_by(QuestionValidationRun.created_at)
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    scored = [r for r in rows if _evidence(r).get("decision")]
    print(f"candidates carrying a difficulty decision: {len(scored)}")
    recorded = collections.Counter(_evidence(r)["decision"] for r in scored)
    print(f"recorded decisions: {dict(recorded.most_common())}")

    thresholds = [args.gap_seconds] if args.gap_seconds else list(GAP_CANDIDATES)
    print("\nreplaying the real guard over runs inferred at each threshold:")
    print("  gap(s)  runs  reproduces  disagrees  guard-caused rejections")
    best = None
    for gap in thresholds:
        out = _replay(scored, float(gap))
        total = out["agree"] + out["disagree"]
        rate = out["agree"] / total * 100 if total else 0.0
        print(
            f"  {gap:>6.0f}  {out['runs']:>4}  {rate:>9.1f}%  {out['disagree']:>9}"
            f"  {out['guard_caused']:>22}"
        )
        if best is None or out["agree"] > best[1]["agree"]:
            best = (gap, out)

    assert best is not None
    gap, out = best
    total = out["agree"] + out["disagree"]
    rate = out["agree"] / total * 100 if total else 0.0
    print(f"\nbest threshold: {gap:.0f}s, reproducing {rate:.1f}% of recorded decisions")
    if rate < 90:
        print(
            "  ^ BELOW 90%: the run reconstruction does not explain the recorded decisions,\n"
            "    so nothing below should be read as evidence. The table has no run id; that\n"
            "    is the thing to fix before asking this question again."
        )
    else:
        print(
            f"  {out['guard_caused']} of {recorded['rejected']} rejections were caused by the\n"
            f"  guard: the gap was re-tierable and only `may_retier` refused."
        )
    if args.verbose and out["mismatches"]:
        print("\nfirst mismatches:")
        for line in out["mismatches"]:
            print(f"  {line}")

    _warm_up_cost(scored, float(gap))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
