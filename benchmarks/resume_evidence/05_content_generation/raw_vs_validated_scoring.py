"""E5.3 - what would have shipped raw, and what the pipeline actually let through.

    uv run python benchmarks/resume_evidence/05_content_generation/raw_vs_validated_scoring.py \
        --pipeline-run-id <id> --out-dir docs/resume_evidence/05_content_generation/e5_3

**Free, deterministic, and it writes nothing to the database.** Two read-only `SELECT`s on a
bare `engine.connect()` (never `session_scope`, which commits on a clean exit, D-294). No
model call: the ground truth is SymPy re-derivation and the same string/structure checks
`authored_validation` owns, which is the whole reason this arm can be scored at all.

**The two arms, defined precisely.**

- **Raw arm** - every candidate the Generator actually returned as a schema-valid
  `AuthoredGeneratedItemResponse`, scored as if it had shipped with no gate, no solver panel
  and no judge. That is the controlled version of D-276's accidental ablation.
- **Validated arm** - the subset of those same candidates the pipeline machine-accepted.
  "Accepted" here means *cleared the machine*, never *approved by a person*: human review
  writes no row in this table, and nothing this experiment produces is approved, exported or
  counted toward any coverage target.

**Where each arm's items come from.** A rejection after the Generator carries the item in
`stage_results.candidate_snapshot` (D-195). An acceptance does not - the item is persisted
instead, as a `question_templates` row plus its canonical `question_variants` row - so an
accepted candidate is rebuilt from those two rows. Four generator fields are not persisted
anywhere (`difficulty_rationale`, `required_prerequisites`, `reasoning`, and the generator's
own `proposed_difficulty`); three of them are recovered from the row's own difficulty and
prerequisite evidence, and none of the four is read by any deterministic check, so the
reconstruction is exact for everything being measured. `_RECONSTRUCTION_PLACEHOLDERS` names
what was substituted rather than hiding it.

**A generator *call failure* is not a raw-arm candidate.** No item exists, so there is
nothing to score; those rows carry `generator_request` instead of a snapshot and are counted
and reported separately (D-230's rule: a call that never returned is not a quality signal).

**What the deterministic scorer cannot see**, stated here and again in the report: prose
quality, scenario plausibility, ambiguity, and whether a distractor is tempting. Those are
what the hand audit is for, and its numbers are the honest bound on this script's blindness.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import json
import pathlib
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from intellichoice_curriculum import authored_validation as av
from intellichoice_curriculum.authored_validation import AuthoredValidationResult
from intellichoice_curriculum.content import CurriculumContent, load_curriculum
from intellichoice_db.engine import create_engine
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from sqlalchemy import text

# Siblings/neighbours imported rather than reimplemented (D-223's rule): a second copy of
# either would silently lack the fixes the original has taken.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "scripts"))
from measure_bank_duplicates import content_words, jaccard, skeleton  # noqa: E402
from stage_funnel_analysis import (  # noqa: E402
    failure_family,
    hint_leak_failures,
    item_from_snapshot,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "05_content_generation" / "e5_3"

ENVIRONMENT = "real-model generation (D-447 roster), isolated local benchmark database"

# Substituted when rebuilding an accepted candidate, because the column does not exist.
# Listed so the substitution is a visible decision. None of these is read by any check in
# `validate_authored_item` - `estimated_time_seconds` is the only generator-claim field the
# deterministic gate reads, and that one IS persisted.
_RECONSTRUCTION_PLACEHOLDERS = ("reasoning",)

# One named check per defect family, each run in isolation so a family's n/N comes from the
# real instrument rather than from regex-bucketing a prose reason. The order is
# `validate_authored_item`'s own.
CHECKS: tuple[
    tuple[str, Callable[[AuthoredGeneratedItemResponse, AuthoredValidationResult, int, str], None]],
    ...,
] = (
    ("schema/markdown safety", lambda i, r, d, f: av.check_schema_and_markdown_safety(i, r)),
    ("duplicate options", lambda i, r, d, f: av.check_unique_options(i, r)),
    (
        "answer key: derived answer disagrees",
        lambda i, r, d, f: av.check_sympy_independent_solve(i, r, f),
    ),
    (
        "answer key: not exactly one correct option",
        lambda i, r, d, f: av.check_exactly_one_correct_answer(i, r),
    ),
    ("answer leakage", lambda i, r, d, f: av.check_no_answer_leakage(i, r)),
    ("hint ladder monotonicity", lambda i, r, d, f: av.check_hint_ladder_monotonicity(i, r)),
    (
        "hint/solution/answer disagreement",
        lambda i, r, d, f: av.check_hint_solution_answer_agreement(i, r),
    ),
    ("difficulty rubric", lambda i, r, d, f: av.check_difficulty_rubric_compliance(d, i, r)),
    ("age-appropriate wording", lambda i, r, d, f: av.check_age_appropriate_wording(i, r)),
    ("math notation readability", lambda i, r, d, f: av.check_math_notation_is_readable(i, r)),
    ("meta commentary", lambda i, r, d, f: av.check_no_meta_commentary(i, r)),
)


# --- plain data, so every function below is testable from literals --------------------


@dataclass(frozen=True)
class Candidate:
    """One generator-returned candidate of the run, with the arm it belongs to."""

    run_id: str
    source: str  # "snapshot" (a rejection) | "persisted" (a machine acceptance)
    accepted: bool
    topic_id: str
    skill_id: str
    requested_difficulty: int
    stored_difficulty: int | None
    question_template_id: str | None
    cost_cents: float
    created_at: datetime
    position: int  # 1-based order within the run - the warm-up toll is positional
    pipeline_reasons: list[str]
    item: AuthoredGeneratedItemResponse
    placeholders: tuple[str, ...] = ()


@dataclass(frozen=True)
class Score:
    run_id: str
    accepted: bool
    topic_id: str
    skill_id: str
    requested_difficulty: int
    position: int
    families: tuple[str, ...]
    failures: tuple[str, ...]
    error: str | None = None

    @property
    def defective(self) -> bool:
        return bool(self.families)


@dataclass
class ArmSummary:
    name: str
    n: int = 0
    scored: int = 0
    errors: int = 0
    defective: int = 0
    by_family: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "arm": self.name,
            "candidates": self.n,
            "scored": self.scored,
            "scoring_errors": self.errors,
            "defective": self.defective,
            "invalid_content_rate": (self.defective / self.scored) if self.scored else None,
            "by_family": dict(sorted(self.by_family.items(), key=lambda kv: -kv[1])),
        }


# --- scoring (pure) ------------------------------------------------------------------


def score_candidate(candidate: Candidate, curriculum: CurriculumContent) -> Score:
    """Every deterministic check, each in its own result object so the failing family is
    the check that failed rather than a pattern match on its prose."""
    answer_form = curriculum.answer_form(candidate.skill_id)
    families: list[str] = []
    failures: list[str] = []
    try:
        leaks = hint_leak_failures(candidate.item)
        if leaks:
            families.append("answer leakage")
            failures.extend(leaks)
        for name, check in CHECKS:
            result = AuthoredValidationResult()
            check(candidate.item, result, candidate.requested_difficulty, answer_form)
            if result.failures:
                if name not in families:
                    families.append(name)
                failures.extend(result.failures)
    except Exception as exc:  # noqa: BLE001 - SymPy can raise on real generated content
        return Score(
            candidate.run_id,
            candidate.accepted,
            candidate.topic_id,
            candidate.skill_id,
            candidate.requested_difficulty,
            candidate.position,
            (),
            (),
            error=f"{type(exc).__name__}: {exc}",
        )
    return Score(
        candidate.run_id,
        candidate.accepted,
        candidate.topic_id,
        candidate.skill_id,
        candidate.requested_difficulty,
        candidate.position,
        tuple(families),
        tuple(failures),
    )


def duplicate_groups(
    candidates: list[Candidate], threshold: float
) -> tuple[dict[str, list[list[str]]], dict[str, set[str]]]:
    """Within-run repetition, by the two signals `measure_bank_duplicates` separates.

    Signal 1 (`skeleton`) has no knob: same sentence, different numbers. Signal 2 (Jaccard
    over content words) catches rewordings the skeleton misses and is reported separately
    so the headline number stays the one with no threshold in it.
    """
    rendered = {
        c.run_id: (f"{c.item.context_block} {c.item.stem}" if c.item.context_block else c.item.stem)
        for c in candidates
    }
    by_skeleton: dict[str, list[str]] = collections.defaultdict(list)
    for run_id, stem in rendered.items():
        by_skeleton[skeleton(stem)].append(run_id)
    skeleton_groups = [sorted(ids) for ids in by_skeleton.values() if len(ids) > 1]

    words = {run_id: content_words(stem) for run_id, stem in rendered.items()}
    ids = sorted(rendered)
    near: list[list[str]] = []
    seen: set[tuple[str, str]] = set()
    for n, a in enumerate(ids):
        for b in ids[n + 1 :]:
            if (a, b) in seen:
                continue
            if jaccard(words[a], words[b]) >= threshold:
                near.append([a, b])
                seen.add((a, b))
    flagged = {
        "skeleton": {run_id for group in skeleton_groups for run_id in group},
        "near_duplicate": {run_id for pair in near for run_id in pair},
    }
    return {"skeleton_collisions": skeleton_groups, "near_duplicate_pairs": near}, flagged


def summarise(name: str, scores: list[Score]) -> ArmSummary:
    summary = ArmSummary(name=name, n=len(scores))
    families: collections.Counter[str] = collections.Counter()
    for score in scores:
        if score.error:
            summary.errors += 1
            continue
        summary.scored += 1
        if score.defective:
            summary.defective += 1
        families.update(score.families)
    summary.by_family = dict(families)
    return summary


# --- database read (the only impure part) --------------------------------------------

_RUNS_SQL = """
SELECT question_validation_run_id, question_template_id, outcome, stage_results, reasons,
       cost_cents, created_at
FROM question_validation_runs
WHERE pipeline_run_id = :run_id
ORDER BY created_at
"""

_TEMPLATE_SQL = """
SELECT t.question_template_id, t.topic_id, t.skill_id, t.difficulty_label, t.stem,
       t.context_block, t.answer_expression, t.hint_ladder, t.canonical_solution,
       t.common_error_tags, t.estimated_time_seconds,
       v.option_a, v.option_b, v.option_c, v.option_d, v.correct_option
FROM question_templates t
JOIN question_variants v ON v.question_template_id = t.question_template_id
                        AND v.origin = 'canonical'
WHERE t.question_template_id = ANY(:ids)
"""


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def item_from_persisted(
    row: Any, difficulty: dict[str, Any], prerequisites: Any
) -> AuthoredGeneratedItemResponse:
    """Rebuild a machine-accepted candidate from what the pipeline persisted.

    `difficulty_rationale` has a 20-character floor in the response contract; the recorded
    rationale is used when the row carries one, and the explicit marker below when it does
    not - never a silent empty string, which would change what the contract validates.
    """
    rationale = str(difficulty.get("generator_difficulty_rationale") or "")
    if len(rationale) < 20:
        rationale = "[not persisted: rationale unavailable for this row]"
    return AuthoredGeneratedItemResponse.model_validate(
        {
            "stem": row.stem,
            "context_block": row.context_block,
            "option_a": row.option_a,
            "option_b": row.option_b,
            "option_c": row.option_c,
            "option_d": row.option_d,
            "correct_option": row.correct_option,
            "equation": row.answer_expression,
            "hint_ladder": _json(row.hint_ladder, []),
            "canonical_solution": _json(row.canonical_solution, {}),
            "misconception_tags": _json(row.common_error_tags, []),
            "estimated_time_seconds": row.estimated_time_seconds,
            "proposed_difficulty": (
                _as_int(difficulty.get("generator_proposed_difficulty")) or row.difficulty_label
            ),
            "difficulty_rationale": rationale,
            "required_prerequisites": list(_json(prerequisites, []) or []),
            "reasoning": "",
        }
    )


async def read_candidates(run_id: str) -> tuple[list[Candidate], dict[str, Any]]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            rows = (await conn.execute(text(_RUNS_SQL), {"run_id": run_id})).all()
            accepted_ids = [r[1] for r in rows if r[2] == "pending" and r[1]]
            templates = {}
            if accepted_ids:
                records = (await conn.execute(text(_TEMPLATE_SQL), {"ids": accepted_ids})).all()
                templates = {r.question_template_id: r for r in records}
    finally:
        await engine.dispose()

    candidates: list[Candidate] = []
    generator_call_failures = 0
    unreconstructable: list[dict[str, str]] = []
    for position, r in enumerate(rows, start=1):
        stage_results = _json(r[3], {}) or {}
        reasons = _json(r[4], []) or []
        accepted = r[2] == "pending"
        difficulty = stage_results.get("difficulty") or {}
        if accepted:
            record = templates.get(r[1])
            if record is None:
                unreconstructable.append({"run_id": str(r[0]), "why": "no canonical variant row"})
                continue
            try:
                item = item_from_persisted(record, difficulty, stage_results.get("prerequisites"))
            except Exception as exc:  # noqa: BLE001 - a shape we cannot rebuild is a finding
                unreconstructable.append({"run_id": str(r[0]), "why": f"persisted: {exc}"})
                continue
            requested = _as_int(difficulty.get("requested_difficulty")) or record.difficulty_label
            candidates.append(
                Candidate(
                    run_id=str(r[0]),
                    source="persisted",
                    accepted=True,
                    topic_id=record.topic_id,
                    skill_id=record.skill_id,
                    requested_difficulty=requested,
                    stored_difficulty=record.difficulty_label,
                    question_template_id=record.question_template_id,
                    cost_cents=float(r[5] or 0.0),
                    created_at=r[6],
                    position=position,
                    pipeline_reasons=list(reasons),
                    item=item,
                    placeholders=_RECONSTRUCTION_PLACEHOLDERS,
                )
            )
            continue
        snapshot = stage_results.get("candidate_snapshot")
        if not isinstance(snapshot, dict):
            # No item was ever returned: a generator call failure, a circuit-open skip, or
            # a design-stage rejection. Counted, never scored (D-230).
            generator_call_failures += 1
            continue
        try:
            item = item_from_snapshot(snapshot)
        except Exception as exc:  # noqa: BLE001
            unreconstructable.append({"run_id": str(r[0]), "why": f"snapshot: {exc}"})
            continue
        candidates.append(
            Candidate(
                run_id=str(r[0]),
                source="snapshot",
                accepted=False,
                topic_id=str(snapshot.get("topic_id") or ""),
                skill_id=str(snapshot.get("skill_id") or ""),
                requested_difficulty=(
                    _as_int(snapshot.get("requested_difficulty")) or item.proposed_difficulty
                ),
                stored_difficulty=None,
                question_template_id=None,
                cost_cents=float(r[5] or 0.0),
                created_at=r[6],
                position=position,
                pipeline_reasons=list(reasons),
                item=item,
            )
        )
    totals = {
        "validation_run_rows": len(rows),
        "generator_returned_no_item": generator_call_failures,
        "unreconstructable": unreconstructable,
        "machine_accepted_rows": sum(1 for r in rows if r[2] == "pending"),
        "rejected_rows": sum(1 for r in rows if r[2] == "rejected"),
        "total_cost_cents": round(sum(float(r[5] or 0.0) for r in rows), 4),
        "first_candidate_at": rows[0][6].isoformat() if rows else None,
        "last_candidate_at": rows[-1][6].isoformat() if rows else None,
    }
    return candidates, totals


# --- artifacts -----------------------------------------------------------------------


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def write_jsonl(path: pathlib.Path, candidates: list[Candidate], scores: dict[str, Score]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            score = scores[candidate.run_id]
            handle.write(
                json.dumps(
                    {
                        "run_id": candidate.run_id,
                        "source": candidate.source,
                        "machine_accepted": candidate.accepted,
                        "position": candidate.position,
                        "topic_id": candidate.topic_id,
                        "skill_id": candidate.skill_id,
                        "requested_difficulty": candidate.requested_difficulty,
                        "stored_difficulty": candidate.stored_difficulty,
                        "question_template_id": candidate.question_template_id,
                        "cost_cents": candidate.cost_cents,
                        "defect_families": list(score.families),
                        "failures": list(score.failures),
                        "scoring_error": score.error,
                        "pipeline_reasons": candidate.pipeline_reasons,
                        "pipeline_reason_families": sorted(
                            {failure_family(r) for r in candidate.pipeline_reasons}
                        ),
                        "stem": candidate.item.stem,
                        "context_block": candidate.item.context_block,
                        "equation": candidate.item.equation,
                        "correct_option": candidate.item.correct_option,
                        "options": {
                            "a": candidate.item.option_a,
                            "b": candidate.item.option_b,
                            "c": candidate.item.option_c,
                            "d": candidate.item.option_d,
                        },
                        "hint_ladder": list(candidate.item.hint_ladder),
                        "final_answer": candidate.item.canonical_solution.final_answer,
                        "reconstruction_placeholders": list(candidate.placeholders),
                    }
                )
                + "\n"
            )


def write_family_csv(path: pathlib.Path, raw: ArmSummary, validated: ArmSummary) -> None:
    families = sorted(set(raw.by_family) | set(validated.by_family))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "defect_family",
                "raw_n",
                "raw_denominator",
                "raw_rate",
                "validated_n",
                "validated_denominator",
                "validated_rate",
            ]
        )
        for family in families:
            raw_n = raw.by_family.get(family, 0)
            val_n = validated.by_family.get(family, 0)
            writer.writerow(
                [
                    family,
                    raw_n,
                    raw.scored,
                    f"{raw_n / raw.scored:.4f}" if raw.scored else "",
                    val_n,
                    validated.scored,
                    f"{val_n / validated.scored:.4f}" if validated.scored else "",
                ]
            )


async def run(args: argparse.Namespace) -> int:
    candidates, totals = await read_candidates(args.pipeline_run_id)
    if not candidates:
        print(
            f"no scoreable candidates for pipeline_run_id={args.pipeline_run_id!r}", file=sys.stderr
        )
        return 1
    curriculum = load_curriculum()
    scores = {c.run_id: score_candidate(c, curriculum) for c in candidates}

    dup_report, dup_flagged = duplicate_groups(candidates, args.duplicate_threshold)
    # Duplication is a property of a *set*, not of one item, so it is added to a
    # candidate's families after the per-item checks rather than inside them.
    for run_id in dup_flagged["skeleton"]:
        score = scores[run_id]
        if "duplicate scenario (skeleton collision)" not in score.families:
            scores[run_id] = Score(
                score.run_id,
                score.accepted,
                score.topic_id,
                score.skill_id,
                score.requested_difficulty,
                score.position,
                (*score.families, "duplicate scenario (skeleton collision)"),
                (*score.failures, "stem skeleton collides with another candidate in this run"),
                score.error,
            )

    raw_scores = [scores[c.run_id] for c in candidates]
    validated_scores = [scores[c.run_id] for c in candidates if c.accepted]
    raw = summarise("raw generation (every schema-valid generator output)", raw_scores)
    validated = summarise("validated pipeline output (machine-accepted)", validated_scores)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / "raw_arm_scores.jsonl", candidates, scores)
    write_jsonl(
        out_dir / "validated_arm_scores.jsonl", [c for c in candidates if c.accepted], scores
    )
    write_family_csv(out_dir / "defect_families.csv", raw, validated)

    elapsed_minutes = None
    if totals["first_candidate_at"] and totals["last_candidate_at"]:
        start = datetime.fromisoformat(totals["first_candidate_at"])
        end = datetime.fromisoformat(totals["last_candidate_at"])
        elapsed_minutes = (end - start).total_seconds() / 60.0

    accepted_n = sum(1 for c in candidates if c.accepted)
    summary = {
        "experiment": "E5.3",
        "measured_at": datetime.now(UTC).isoformat(),
        "git_sha": _git_sha(),
        "environment": ENVIRONMENT,
        "pipeline_run_id": args.pipeline_run_id,
        "duplicate_threshold": args.duplicate_threshold,
        "run_totals": totals,
        "raw_arm": raw.as_dict(),
        "validated_arm": validated.as_dict(),
        "acceptance": {
            "machine_accepted": accepted_n,
            "generator_returned_items": len(candidates),
            "acceptance_rate_of_returned_items": (
                accepted_n / len(candidates) if candidates else None
            ),
            "acceptance_rate_of_all_attempts": (
                accepted_n / totals["validation_run_rows"]
                if totals["validation_run_rows"]
                else None
            ),
        },
        "economics": {
            "total_cost_cents": totals["total_cost_cents"],
            "cost_cents_per_attempt": (
                totals["total_cost_cents"] / totals["validation_run_rows"]
                if totals["validation_run_rows"]
                else None
            ),
            "cost_cents_per_machine_accepted": (
                totals["total_cost_cents"] / accepted_n if accepted_n else None
            ),
            "elapsed_minutes": elapsed_minutes,
            "candidates_per_minute": (
                totals["validation_run_rows"] / elapsed_minutes if elapsed_minutes else None
            ),
        },
        "duplicates": {
            "skeleton_collision_groups": len(dup_report["skeleton_collisions"]),
            "candidates_in_a_skeleton_collision": len(dup_flagged["skeleton"]),
            "near_duplicate_pairs": len(dup_report["near_duplicate_pairs"]),
            "candidates_in_a_near_duplicate_pair": len(dup_flagged["near_duplicate"]),
            "accepted_candidates_in_a_skeleton_collision": sum(
                1 for c in candidates if c.accepted and c.run_id in dup_flagged["skeleton"]
            ),
            "detail": dup_report,
        },
        "reconstruction_placeholders": list(_RECONSTRUCTION_PLACEHOLDERS),
    }
    (out_dir / "scoring_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    print(
        json.dumps({k: v for k, v in summary.items() if k != "duplicates"}, indent=2, default=str)
    )
    print(
        f"\nwrote {out_dir}/raw_arm_scores.jsonl, validated_arm_scores.jsonl, "
        f"defect_families.csv, scoring_summary.json"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-run-id", required=True)
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--duplicate-threshold",
        type=float,
        default=0.75,
        help="Jaccard floor for the second, thresholded duplicate signal (default: 0.75, "
        "the value scripts/measure_bank_duplicates.py uses)",
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
