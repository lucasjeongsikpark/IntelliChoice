"""Where does a bank item's difficulty label actually come from? (D-301)

**The question this answers, which three decisions assumed instead.** D-292 and D-296 both
reasoned from "a bank item's difficulty label is the judge's own rating, because a
disagreement at generation time would have rejected or re-tiered it". D-300 measured that on
16 items and found it false for 10 of them: a gap of exactly 1 is `flagged`
(`_DIFFICULTY_FLAG_AT = 1`), and **flagged keeps the tier the slot asked for**, not the
judge's. Only `accepted` and `retiered` produce a label the judge would endorse.

So "the judge does not reproduce its own labels" was partly "the judge is being scored against
a label it never assigned". This script puts a number on that over the whole serving bank
instead of a 16-item sample - free, read-only, no model calls.

**Why the whole bank and not the probe's sample.** `measure_judge_tier_agreement.py` draws
deliberately from the topics that *produced* the tier-4/5 disagreements, because that is the
only population where the competing explanations predict different results. That makes it the
right sample for the agreement question and the *wrong* one for "how much of the bank is
mislabelled" - it over-represents disagreement by construction. Measured here at 27% stored
above the judge's reading, against 8 of 16 in that sample.

Run:

    uv run python scripts/measure_tier_label_provenance.py
    uv run python scripts/measure_tier_label_provenance.py --by-topic
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.questions import QuestionTemplate, QuestionValidationRun
from sqlalchemy import select


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by-topic", action="store_true", help="Break the skew down per topic")
    args = parser.parse_args()

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            serving = {
                t.question_template_id: (t.topic_id, t.difficulty_label)
                for t in (
                    await session.execute(
                        select(QuestionTemplate)
                        .where(QuestionTemplate.validation_status == "approved")
                        .where(QuestionTemplate.active_status == "active")
                    )
                )
                .scalars()
                .all()
            }
            runs = list(
                (
                    await session.execute(
                        select(QuestionValidationRun).where(
                            QuestionValidationRun.question_template_id.isnot(None)
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    provenance: collections.Counter[str] = collections.Counter()
    skew: collections.Counter[int] = collections.Counter()
    per_topic: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    covered = 0

    for run in runs:
        entry = serving.get(run.question_template_id or "")
        if entry is None:
            continue
        evidence = (run.stage_results or {}).get("difficulty") or {}
        if not evidence:
            continue
        topic_id, stored = entry
        covered += 1
        provenance[str(evidence.get("decision"))] += 1
        judged = evidence.get("judge_reviewed_difficulty")
        if judged is not None:
            skew[int(judged) - int(stored)] += 1
            per_topic[topic_id][int(judged) - int(stored)] += 1

    print(f"serving items: {len(serving)}; with authoring difficulty evidence: {covered}")
    print(
        "\n(items without evidence are hand-authored, figure-authored, or predate the "
        "difficulty stage -\nthey never faced the judge, so they carry no claim either way)"
    )

    print("\nhow the stored tier was decided:")
    for decision, n in provenance.most_common():
        note = {
            "accepted": "judge agreed with the slot",
            "flagged": "judge named a DIFFERENT tier; the slot's was kept",
            "retiered": "judge's tier was stored",
        }.get(decision, "")
        print(f"  {decision:<10} {n:>5}   {note}")

    total = sum(skew.values())
    print("\njudge's rating minus the stored tier:")
    for delta in sorted(skew):
        label = (
            "judge says EASIER than the label"
            if delta < 0
            else ("agrees" if delta == 0 else "judge says HARDER than the label")
        )
        print(f"  {delta:+d}: {skew[delta]:>5}  ({skew[delta] / total * 100:>4.0f}%)  {label}")

    above = sum(n for d, n in skew.items() if d < 0)
    below = sum(n for d, n in skew.items() if d > 0)
    print(
        f"\nstored ABOVE the judge's reading: {above} ({above / total * 100:.0f}%)"
        f"\nstored BELOW the judge's reading: {below} ({below / total * 100:.0f}%)"
        f"\nnet skew: {(above - below) / total * 100:+.0f} percentage points toward "
        f"over-labelling"
    )
    print(
        "\nThis is NOT a defect count. D-301's decision is that `difficulty_label` means "
        '"the tier the\nplan asked for", which is what the study planner plays in order. '
        "The number matters because\nit bounds how much of any tier-4/5 shortage is a "
        "labelling artefact rather than missing content."
    )

    if args.by_topic:
        print("\nper topic (n, % stored above the judge's reading):")
        rows = []
        for topic_id, counts in per_topic.items():
            n = sum(counts.values())
            over = sum(v for d, v in counts.items() if d < 0)
            rows.append((over / n, n, over, topic_id))
        for share, n, over, topic_id in sorted(rows, reverse=True):
            print(f"  {topic_id:<26} {n:>4} items  {over:>3} above  ({share * 100:>3.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
