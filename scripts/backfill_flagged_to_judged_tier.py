"""Re-tier the items a `flagged` verdict parked at the slot's difficulty (D-302).

`judge_difficulty` now stores the judge's reading on `flagged` as well as on `retiered`, so
new content is labelled by the only independent reading of it. This brings the **existing**
bank to the same rule: 327 serving items were labelled by the slot over a recorded judge
disagreement (D-301), and leaving them would mean the bank's tiers meant one thing before a
date and another after it.

**Preconditions this relies on, both measured rather than assumed:**

- The judge's rating is on the item's own `question_validation_runs` row, stored since D-194,
  so nothing here is inferred - it is a column read.
- Moving them empties the top tiers (204 down against 104 up). That is only safe because
  `EXAM_QUESTION_COUNT` replaced the per-tier serving floor in the same decision: measured,
  openable topics go 26 -> 12 under the old rule and 33 -> 33 under the new one.

**Writes through an explicit commit**, because D-284's addendum found that `session_scope`
used to discard uncommitted work while reporting success. It now commits on a clean exit, but
an ad-hoc migration should say so rather than rely on it.

Dry run by default - it prints every move and writes nothing.

    uv run python scripts/backfill_flagged_to_judged_tier.py            # dry run
    uv run python scripts/backfill_flagged_to_judged_tier.py --apply
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
    parser.add_argument("--apply", action="store_true", help="Actually write the new tiers")
    args = parser.parse_args()

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            templates = {
                t.question_template_id: t
                for t in (await session.execute(select(QuestionTemplate))).scalars().all()
            }
            runs = (
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

            moves: list[tuple[str, int, int]] = []
            for run in runs:
                template = templates.get(run.question_template_id or "")
                if template is None:
                    continue
                evidence = (run.stage_results or {}).get("difficulty") or {}
                if evidence.get("decision") != "flagged":
                    continue
                judged = evidence.get("judge_reviewed_difficulty")
                if judged is None or int(judged) == template.difficulty_label:
                    continue
                moves.append(
                    (template.question_template_id, template.difficulty_label, int(judged))
                )

            delta = collections.Counter(new - old for _tid, old, new in moves)
            by_topic: collections.Counter[str] = collections.Counter()
            for tid, _old, _new in moves:
                by_topic[templates[tid].topic_id] += 1

            print(f"flagged items whose stored tier differs from the judge's: {len(moves)}")
            print(f"  by delta: {dict(sorted(delta.items()))}")
            print("  by topic:")
            for topic_id, n in by_topic.most_common():
                print(f"    {topic_id:<28} {n}")

            if not args.apply:
                print("\ndry run - nothing written. Re-run with --apply.")
                return 0

            for tid, _old, new in moves:
                templates[tid].difficulty_label = new
            # Explicit, not inherited: an ad-hoc migration should name its own commit.
            await session.commit()
            print(f"\napplied: {len(moves)} templates re-tiered and committed")
            print("Run `make question-export` next so the bank files match the database.")
    finally:
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
