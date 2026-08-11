"""Which approved bank items nobody actually read (D-273, 2026-08-11).

`review_cli --approve-all-unreviewed` suspends D-026 on the user's explicit instruction, so
the bank now contains items whose approval was mechanical. That is only defensible while the
set stays *recoverable* - an unreviewed item that cannot be told apart from a reviewed one is
just an unreviewed item.

This reproduces the set from the database at any time, so it can be read, re-reviewed, or
reverted in bulk. Free and read-only: no model call, no writes.

    .venv/bin/python scripts/list_unreviewed_bank_items.py
    .venv/bin/python scripts/list_unreviewed_bank_items.py --topic g1_addition --full

**How the set is identified, and its one real limit.** An item auto-approved this way keeps
`review_priority='high'` *and* has no `reviewed_at`-style human mark, because there is no such
column - approval writes `active_status` and nothing records who did it. So the marker here is
provenance, not proof: `generator_model` starts with `bedrock-` (the pipeline wrote it) and
`review_priority='high'`. A human who reviewed and approved a high-priority pipeline item
would be indistinguishable. That is a real gap and the honest statement of it is: this lists
items that were *probably* not read, and it is exact only while no human review has run.
"""

import argparse
import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DEFAULT_URL = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"

QUERY = """
SELECT question_template_id, topic_id, skill_id, difficulty_label, review_priority,
       stem, option_a, option_b, option_c, option_d, correct_option, answer_expression
FROM question_templates
WHERE active_status = 'active'
  AND generator_model LIKE 'bedrock-%'
  AND review_priority = 'high'
  {topic_filter}
ORDER BY topic_id, skill_id, difficulty_label, question_template_id
"""


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--full", action="store_true", help="Print stems and options too")
    args = parser.parse_args()

    engine = create_async_engine(os.environ.get("DATABASE_URL", DEFAULT_URL))
    try:
        async with engine.connect() as connection:
            sql = QUERY.format(topic_filter="AND topic_id = :topic" if args.topic else "")
            result = await connection.execute(
                text(sql), {"topic": args.topic} if args.topic else {}
            )
            rows = result.fetchall()
    finally:
        await engine.dispose()

    print(f"{len(rows)} active item(s) that were probably approved without a human read\n")
    for row in rows:
        print(f"{row.question_template_id}  [{row.skill_id} d{row.difficulty_label}]")
        if args.full:
            print(f"    {row.stem}")
            for label in "abcd":
                mark = "*" if label == row.correct_option else " "
                print(f"      {mark} {label}) {getattr(row, f'option_{label}')}")
            print(f"      eq: {row.answer_expression}")
            print()
    if rows:
        print(
            "\nD-026 is suspended for these. Reverting is a bulk "
            "`UPDATE question_templates SET active_status='pending'` over these ids."
        )


if __name__ == "__main__":
    asyncio.run(main())
