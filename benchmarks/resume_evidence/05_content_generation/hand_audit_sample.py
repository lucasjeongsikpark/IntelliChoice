"""E5.3 - draw the 30-item hand-audit sample and print it as a worksheet.

    uv run python benchmarks/resume_evidence/05_content_generation/hand_audit_sample.py \
        --scores docs/resume_evidence/05_content_generation/e5_3/raw_arm_scores.jsonl \
        --out-dir docs/resume_evidence/05_content_generation/e5_3 --seed 20260829

**Why a script rather than a hand-picked sample.** D-285's hand audit is the method being
mirrored, and its one methodological weakness was that the sampler and the reader were the
same judgement. Here the draw is seeded, stratified and written down *before* anything is
read, so the sample cannot drift toward the interesting items. The seed and the drawn ids
go in the JSON artifact; re-running with the same seed and the same scores file reproduces
the identical 30.

**The strata.** 15 machine-rejected and 15 machine-accepted - the two arms' difference is
the thing being audited, so an unstratified draw from a run that rejects most candidates
would produce almost no accepted items to read. Within each arm the draw is proportional
across requested difficulty, because tier is the axis the judge and the difficulty
adjudicator act on.

Free: reads one JSONL file, no database, no model.
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import random
from typing import Any

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "05_content_generation" / "e5_3"


def stratified_sample(
    rows: list[dict[str, Any]], size: int, rng: random.Random
) -> list[dict[str, Any]]:
    """Proportional over `requested_difficulty`, deterministic given `rng`.

    Largest-remainder allocation, so the quotas sum to `size` exactly rather than to
    `size - len(strata)` after truncation. A stratum smaller than its quota gives its
    shortfall back to the pool, which is then filled from the remaining rows - a small
    tier must not silently shrink the sample.
    """
    if size >= len(rows):
        return sorted(rows, key=lambda r: r["run_id"])
    buckets: dict[Any, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        buckets[row.get("requested_difficulty")].append(row)
    for bucket in buckets.values():
        bucket.sort(key=lambda r: r["run_id"])

    exact = {key: len(bucket) * size / len(rows) for key, bucket in buckets.items()}
    quota = {key: min(int(value), len(buckets[key])) for key, value in exact.items()}
    remainder = sorted(buckets, key=lambda key: (-(exact[key] - int(exact[key])), str(key)))
    while sum(quota.values()) < size:
        progressed = False
        for key in remainder:
            if sum(quota.values()) >= size:
                break
            if quota[key] < len(buckets[key]):
                quota[key] += 1
                progressed = True
        if not progressed:  # every stratum exhausted
            break

    drawn: list[dict[str, Any]] = []
    for key in sorted(buckets, key=str):
        drawn.extend(rng.sample(buckets[key], quota[key]))
    return sorted(drawn, key=lambda r: (r.get("requested_difficulty"), r["run_id"]))


def worksheet(rows: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for n, row in enumerate(rows, start=1):
        arm = "machine-ACCEPTED" if row["machine_accepted"] else "machine-REJECTED"
        lines.append(
            f"### {n}. `{row['run_id'][:8]}` — {arm} — {row['topic_id']} / "
            f"{row['skill_id']} / d{row['requested_difficulty']}"
        )
        lines.append("")
        if row.get("context_block"):
            lines.append(f"> {row['context_block']}")
            lines.append("")
        lines.append(f"**Stem.** {row['stem']}")
        lines.append("")
        options = row["options"]
        for letter in ("a", "b", "c", "d"):
            mark = " ← key" if letter == row["correct_option"] else ""
            lines.append(f"- **{letter})** {options[letter]}{mark}")
        lines.append("")
        lines.append(
            f"**Equation.** `{row.get('equation')}`  **Final answer.** {row['final_answer']}"
        )
        lines.append("")
        for i, hint in enumerate(row["hint_ladder"], start=1):
            lines.append(f"{i}. {hint}")
        lines.append("")
        if row["defect_families"]:
            lines.append(f"**Deterministic scorer.** {', '.join(row['defect_families'])}")
        else:
            lines.append("**Deterministic scorer.** clean")
        if row["pipeline_reasons"]:
            lines.append(f"**Pipeline said.** {row['pipeline_reasons'][0]}")
        lines.append("")
        lines.append("**Audit verdict.** _(to fill in)_")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", default=str(DEFAULT_DIR / "raw_arm_scores.jsonl"))
    parser.add_argument("--out-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--seed", type=int, default=20260829)
    parser.add_argument("--per-arm", type=int, default=15)
    args = parser.parse_args()

    rows = [json.loads(line) for line in pathlib.Path(args.scores).read_text().splitlines() if line]
    accepted = [r for r in rows if r["machine_accepted"]]
    rejected = [r for r in rows if not r["machine_accepted"]]

    rng = random.Random(args.seed)
    sample_rejected = stratified_sample(rejected, args.per_arm, rng)
    sample_accepted = stratified_sample(accepted, args.per_arm, rng)
    drawn = sample_rejected + sample_accepted

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "hand_audit_sample.json").write_text(
        json.dumps(
            {
                "experiment": "E5.3",
                "seed": args.seed,
                "scores_file": str(pathlib.Path(args.scores).name),
                "population": {"rejected": len(rejected), "accepted": len(accepted)},
                "drawn": {
                    "machine_rejected": [r["run_id"] for r in sample_rejected],
                    "machine_accepted": [r["run_id"] for r in sample_accepted],
                },
                "stratification": "proportional over requested_difficulty within each arm",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "hand_audit_worksheet.md").write_text(
        f"# E5.3 hand-audit worksheet (seed {args.seed})\n\n"
        f"{len(sample_rejected)} machine-rejected + {len(sample_accepted)} machine-accepted, "
        "drawn before reading.\n\n" + worksheet(drawn),
        encoding="utf-8",
    )
    print(
        f"drew {len(drawn)} items ({len(sample_rejected)} rejected + {len(sample_accepted)} "
        f"accepted) with seed {args.seed}\nwrote {out_dir}/hand_audit_sample.json and "
        f"{out_dir}/hand_audit_worksheet.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
