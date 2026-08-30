"""R3 - re-score E5.2's frozen corpus after the two gate fixes, for $0.

    uv run python benchmarks/resume_evidence/05_content_generation/run_postfix_detection.py

## What this is, and what it deliberately is not

E5.2's `run_defect_detection.py` is the instrument; this is a thin driver over it, not a
second one. It imports that module's detectors, its `Cell`/`score`/`write_metrics` and its
corpus loader, so every number below is produced by the same code that produced the
before-numbers. Nothing here re-mutates, re-samples or extends the corpus: **the denominators
are frozen** at 102 labeled defects and 102 clean controls, and a re-measurement that moved
them would not be a re-measurement.

## Why a driver was needed at all

Two of E5.2's six detector columns are paid - `dedup_embedding` (real Titan embeddings) and
`solver_panel` (two Bedrock calls per item, the entire cost of that experiment). Neither is
touched by R3's fixes, and re-buying them to restate them would be spending money to learn
nothing. So:

- the four **free** columns are recomputed from scratch against the current code, which is
  what carries R3a's new gate check and is the only thing that moved;
- the two **paid** columns are carried over verbatim, per corpus id, from the committed
  `detection_results.jsonl`, and the header records that they are carried rather than
  measured;
- an item whose paid columns are absent from that file keeps `None` and is excluded from
  those denominators exactly as D-230 requires.

## The one definition that changes, and why it has to

`combined_pipeline` in E5.2 was `deterministic_gate OR dedup_embedding OR solver_panel` - the
three machine stages `run_authored_candidate` ran at that time. R3b wires `arithmetic_identity`
into the dedup stage, so the dedup stage is now `dedup_embedding OR arithmetic_identity` and
the union has four parts. Reporting the post-fix pipeline with the pre-fix union would hide
the fix being measured. Both unions are therefore emitted: `combined_pipeline` is the pipeline
as it now stands, and `combined_pipeline_prefix` recomputes E5.2's three-part union from the
same rows, so the before/after difference in the report is attributable and not definitional.

Free by construction: no gateway is built, no provider is imported, no network call is made,
and `--arm` does not exist here.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import UTC, datetime

HARNESS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))

from build_defect_corpus import load_corpus  # noqa: E402
from intellichoice_curriculum.authored_bank import load_authored_bank  # noqa: E402
from intellichoice_curriculum.authored_validation import (  # noqa: E402
    arithmetic_identity,
    hint_ladder_is_ungrounded,
)
from run_defect_detection import (  # noqa: E402
    Cell,
    ItemVerdicts,
    format_metrics,
    git_sha,
    load_results,
    run_free_detectors,
    score,
    verdicts_from_rows,
    write_metrics,
)

BASE = pathlib.Path("docs/resume_evidence/05_content_generation")
CARRIED = ("dedup_embedding", "solver_panel")
# The pipeline's machine stages as they stand after R3b. `arithmetic_identity` is here
# because it is now wired into the dedup stage, which is the whole of R3b.
POSTFIX_PARTS = ("deterministic_gate", "dedup_embedding", "arithmetic_identity", "solver_panel")
# E5.2's union, recomputed over the same rows so the two are comparable.
PREFIX_PARTS = ("deterministic_gate", "dedup_embedding", "solver_panel")


def _union(verdict: ItemVerdicts, parts: tuple[str, ...]) -> bool | None:
    """D-230, unchanged: a union with an unmeasured part is unmeasured, never `False`."""
    flags = [verdict.flags.get(name) for name in parts]
    return None if any(flag is None for flag in flags) else any(flags)


def _prefix_cells(rows: dict[str, dict]) -> list[Cell]:
    """The before-table, re-derived from the committed results rather than transcribed."""
    return score(verdicts_from_rows(rows))


def scan_the_approved_bank(path: pathlib.Path) -> dict:
    """Both new checks over all 958 committed bank items, which is a landing gate, not a metric.

    **Why the hint check is scanned here and not only on the corpus.** `loader.py` re-gates
    every bank item on load, in every environment including production, and aborts the run on
    a failure. A new gate check that failed even one approved item would break
    `make curriculum-load` and CI, so "zero failures on the whole bank" is the condition that
    decides whether the check may live in the shared gate at all rather than on the
    generation path only.

    **Why the fingerprint scan is diagnostic and not a gate.** The dedup stage is not part of
    the loader re-gate - `loader._gate` calls `validate_authored_item` and nothing else - so
    the fingerprint cannot fail an existing bank item however many collisions it finds. What
    it finds is a *content* finding about already-approved material, reported and never acted
    on here: E5.2 §7.4 hand-read six such pairs on its 102-item sample and every one was real,
    and whether the bank should be deduplicated is a user decision nobody has made.

    Scoped to the topic, exactly as the wired check is - two topics legitimately teaching the
    same arithmetic is the curriculum spiral, not a duplicate.
    """
    bank = [item for items in load_authored_bank().values() for item in items]
    hint_failures = [
        {
            "question_template_id": item.question_template_id,
            "topic_id": item.topic_id,
            "ungrounded_numerals": sorted(
                hint_ladder_is_ungrounded(item.to_generated_item(), item.figure_spec)
            ),
        }
        for item in bank
        if hint_ladder_is_ungrounded(item.to_generated_item(), item.figure_spec)
    ]
    by_identity: dict[tuple, list[str]] = {}
    silent = 0
    for item in bank:
        identity = arithmetic_identity(item.answer_expression or "")
        if identity is None:
            silent += 1
            continue
        by_identity.setdefault((item.topic_id, identity), []).append(item.question_template_id)
    groups = sorted(
        (
            {
                "topic_id": topic_id,
                "numbers": list(identity[0]),
                "operators": list(identity[1]),
                "question_template_ids": sorted(ids),
            }
            for (topic_id, identity), ids in by_identity.items()
            if len(ids) > 1
        ),
        key=lambda g: (g["topic_id"], g["numbers"]),
    )
    scan = {
        "record": "bank_scan",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": git_sha(),
        "items_scanned": len(bank),
        "hint_coherence_failures": hint_failures,
        "items_with_no_hint_numeral": sum(
            1
            for item in bank
            if not any(char.isdigit() for rung in item.hint_ladder for char in rung)
        ),
        "identity_groups": groups,
        "identity_group_count": len(groups),
        "items_in_an_identity_group": sum(len(g["question_template_ids"]) for g in groups),
        "items_with_no_parseable_equation": silent,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(scan, indent=2) + "\n", encoding="utf-8")
    print("\n=== approved-bank scan ===")
    print(f"items scanned:                {scan['items_scanned']}")
    print(f"hint-coherence failures:      {len(hint_failures)}  <- must be 0 to ship in the gate")
    print(f"  (ladders naming no numeral: {scan['items_with_no_hint_numeral']} - not judged)")
    print(f"same-topic identity groups:   {scan['identity_group_count']}")
    print(f"  items in one:               {scan['items_in_an_identity_group']}")
    print(f"  (no parseable equation:     {scan['items_with_no_parseable_equation']} - skipped)")
    print(f"scan written to {path}")
    return scan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(BASE / "defect_corpus.jsonl"))
    parser.add_argument("--before", default=str(BASE / "detection_results.jsonl"))
    out = BASE / "post_remediation"
    parser.add_argument("--results", default=str(out / "detection_results_postfix.jsonl"))
    parser.add_argument("--metrics", default=str(out / "detection_metrics_postfix.csv"))
    parser.add_argument("--before-metrics", default=str(out / "detection_metrics_prefix.csv"))
    parser.add_argument("--bank-scan", default=str(out / "bank_scan.json"))
    args = parser.parse_args()

    corpus_header, records = load_corpus(pathlib.Path(args.corpus))
    if not records:
        raise SystemExit(f"no corpus items in {args.corpus}")
    before_header, before_rows = load_results(pathlib.Path(args.before))
    if not before_rows:
        raise SystemExit(f"no before-results in {args.before} - nothing to carry or compare")

    print("=== BEFORE (re-scored from the committed E5.2 results, no code involved) ===")
    prefix_cells = _prefix_cells(before_rows)
    write_metrics(pathlib.Path(args.before_metrics), prefix_cells)
    print(format_metrics(prefix_cells))

    verdicts = run_free_detectors(records)
    carried = 0
    for corpus_id, verdict in verdicts.items():
        row = before_rows.get(corpus_id)
        if row is None:
            continue
        for name in CARRIED:
            verdict.flags[name] = row["flags"].get(name)
        verdict.solver_status = row.get("solver_status", "not_run")
        verdict.solver_objections = row.get("solver_objections", [])
        verdict.nearest_distance = row.get("nearest_distance")
        verdict.nearest_reference_id = row.get("nearest_reference_id")
        carried += 1
    print(f"\nfree detectors recomputed: {len(verdicts)} items, 0.00 cents")
    print(f"paid columns carried from {args.before}: {carried} items")

    for verdict in verdicts.values():
        verdict.flags["combined_pipeline"] = _union(verdict, POSTFIX_PARTS)

    results_path = pathlib.Path(args.results)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with results_path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "record": "header",
                    "experiment": "R3 post-remediation",
                    "artifact": "detection_results_postfix",
                    "generated_at": datetime.now(UTC).isoformat(),
                    "git_sha": git_sha(),
                    "corpus_git_sha": corpus_header.get("git_sha"),
                    "corpus_seed": corpus_header.get("corpus_seed"),
                    "free_columns": "recomputed against the post-R3 code",
                    "paid_columns": f"carried verbatim from {args.before}, not re-measured",
                    "paid_columns_source_sha": before_header.get("git_sha"),
                    "combined_pipeline_parts": list(POSTFIX_PARTS),
                    "spend_cents": 0.0,
                }
            )
            + "\n"
        )
        for verdict in verdicts.values():
            handle.write(json.dumps(verdict.as_json()) + "\n")

    cells = score(list(verdicts.values()))
    write_metrics(pathlib.Path(args.metrics), cells)
    print("\n=== AFTER (free columns recomputed, paid columns carried) ===")
    print(format_metrics(cells))

    for verdict in verdicts.values():
        verdict.flags["combined_pipeline"] = _union(verdict, PREFIX_PARTS)
    control = [c for c in score(list(verdicts.values())) if c.scope == "ALL"]
    print("\n=== control: the post-fix rows under E5.2's three-part union ===")
    print(format_metrics(control))
    scan_the_approved_bank(pathlib.Path(args.bank_scan))
    print(f"\nresults: {results_path}\nmetrics: {args.metrics}")
    print(f"before-metrics: {args.before_metrics}")
    print("TOTAL SPEND: 0.00 cents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
