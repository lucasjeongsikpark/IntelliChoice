"""Which approved bank items nobody actually read (D-273, corrected D-276).

`review_cli --approve-all-unreviewed` suspends D-026 on the user's explicit instruction, so
the bank contains items whose approval was mechanical. That is only defensible while the set
stays *recoverable* - an unreviewed item that cannot be told apart from a reviewed one is
just an unreviewed item.

This reproduces the set from the database at any time, so it can be read, re-reviewed, or
reverted in bulk. Free and read-only: no model call, no writes.

    .venv/bin/python scripts/list_unreviewed_bank_items.py
    .venv/bin/python scripts/list_unreviewed_bank_items.py --topic decimals --full

**Two corrections, both found by running it after the 3-5 wave was auto-approved (D-276).**
The safety property this script *is* was asserted in `approve_all_pending`'s docstring and
then relied on in conversation, while the script itself had never been executed:

1. **It crashed.** It selected `option_a..option_d` from `question_templates`, where those
   columns do not exist - options live on `question_variants`. The same mistake D-273 hit
   once already and fixed at a different call site.
2. **Its filter did not select the set it claims to.** It required
   `review_priority = 'high'`, on the belief that auto-approved items keep that value.
   Measured after the 3-5 wave: **37 of 38** `decimals` rows are `normal`. `review_priority`
   is assigned at generation from judge signals; it says nothing about who approved what, so
   filtering on it hid 97% of exactly the items this exists to surface.

**How the set is identified, and why it OVER-REPORTS.** There is no `approved_by` column -
approval writes status and nothing records who did it. So the marker is provenance:
`generator_model` starts with `bedrock-` and the item is approved.

That is *not* the same as "nobody read it", and the difference is large. Running this after
the 3-5 wave returns **305 items**, of which only 160 are the auto-approved ones: the
remaining 145 are `linear_equations` and the K-2 topics, and earlier sessions reviewed items
one by one (`make question-review`, ROADMAP Phase 1). So this is an **upper bound** on the
unreviewed set, not the set.

A first draft of this docstring claimed it was exact "while no human review has ever approved
a pipeline item". That was wrong on the repository's own record, and is corrected here rather
than quietly narrowed, because a recoverability guarantee nobody rechecked is the kind that is
believed for months. Narrow by `--topic` to reach the set an individual wave auto-approved;
the real fix is an `approved_by` column, not a cleverer query.
"""

import argparse
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"

# The variant carries the rendered question and the options; the template carries provenance
# and status. `DISTINCT ON` keeps one row per template - a template may have several variants
# and this is a review listing, not a variant audit.
QUERY = """
SELECT DISTINCT ON (t.question_template_id)
       t.question_template_id, t.topic_id, t.skill_id, t.difficulty_label,
       t.review_priority, t.validation_status, t.answer_expression,
       v.rendered_question, v.option_a, v.option_b, v.option_c, v.option_d, v.correct_option
FROM question_templates AS t
LEFT JOIN question_variants AS v
       ON v.question_template_id = t.question_template_id
WHERE t.validation_status = 'approved'
  AND t.generator_model LIKE 'bedrock-%'
  {topic_filter}
ORDER BY t.question_template_id, t.topic_id, t.skill_id, t.difficulty_label
"""


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--full", action="store_true", help="Print stems and options too")
    args = parser.parse_args()

    engine = create_async_engine(os.environ.get("DATABASE_URL", DEFAULT_URL))
    try:
        async with engine.connect() as connection:
            sql = QUERY.format(topic_filter="AND t.topic_id = :topic" if args.topic else "")
            result = await connection.execute(
                text(sql), {"topic": args.topic} if args.topic else {}
            )
            rows = result.fetchall()
    finally:
        await engine.dispose()

    print(f"{len(rows)} approved item(s) with no record of a human having read them\n")
    by_topic: dict[str, int] = {}
    for row in rows:
        by_topic[row.topic_id] = by_topic.get(row.topic_id, 0) + 1
    for topic, count in sorted(by_topic.items()):
        print(f"  {topic:30s} {count:4d}")
    print()

    if args.full:
        for row in sorted(rows, key=lambda r: (r.topic_id, r.skill_id, r.difficulty_label)):
            print(f"{row.question_template_id}  [{row.skill_id} d{row.difficulty_label}]")
            print(f"    {row.rendered_question}")
            for label in "abcd":
                mark = "*" if label == row.correct_option else " "
                print(f"      {mark} {label}) {getattr(row, f'option_{label}')}")
            print(f"      eq: {row.answer_expression}")
            print()

    if rows:
        print(
            "D-026 is suspended for these. Reverting is a bulk\n"
            "  UPDATE question_templates SET validation_status='pending'\n"
            "over these ids - `validation_status`, not `active_status`: the review CLI's\n"
            "approve/reject guard reads the former, so setting the latter would leave every\n"
            "one of these un-re-reviewable."
        )


if __name__ == "__main__":
    asyncio.run(main())
