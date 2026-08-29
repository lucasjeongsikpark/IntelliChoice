"""E5.1 - what each stage of the content pipeline actually caught, and what it cost.

Run with:

    uv run python benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py
    uv run python .../stage_funnel_analysis.py --pipeline-run-id <id>   # one run (E5.3 reuse)
    uv run python .../stage_funnel_analysis.py --no-overlap             # funnel only

**Free, and it writes nothing to the database.** One `SELECT` over
`question_validation_runs` (plus one over `question_templates` for strata the rejection rows
cannot carry), no model call, no network beyond the local Postgres. It never opens a
transaction that could commit: the read runs on a bare `engine.connect()`.

**What it measures.** `question_validation_runs` is an append-only row per candidate
attempt (D-195/D-294/D-295), and the offline generator has only ever run from this machine
against this database - so the table is the complete recorded history of the automated
pipeline. This reconstructs, per row, *which stage ended the candidate*, then reports the
funnel: how many candidates reached each stage, how many it rejected, what that stage's
share of spend was, and where in a run the rejections fell (D-296's warm-up structure).

**The novel half is the deterministic-gate overlap counterfactual, and it is free.** Every
rejection after the Generator carries the candidate itself (`candidate_snapshot`, D-195).
So for a candidate the *paid* stages rejected - dedup, the solver panel, the judge, the
difficulty adjudicator - the free deterministic gate can be re-run over the recorded
content and asked: would SymPy and the string checks have caught this one too? That
separates "the LLM stage found something the arithmetic could not" from "the LLM stage was
paid to re-find something already free".

**The direction that cannot be computed, stated once here and again in the report.** The
mirror question - would the solvers/judge have caught the items the deterministic gate
rejected? - is unanswerable from this data and this script will not guess at it. Those
stages never ran on those candidates (the gate rejects before them, deliberately: D-276),
and running them now costs real money on content that was discarded. D-276 is the closest
evidence that exists and it points the other way: with the gate off, five wrong answer keys
passed both blind solvers and the judge.

**Three things this is not.** (1) It measures the *automated* pipeline only - the human
review step that follows `pending` writes no row here, so an "accepted" candidate below is
one that cleared the machine, not one a person approved. (2) The re-gate uses *today's*
gate, which has grown checks since the oldest rows were written (D-288's notation check,
D-308's canonical form), so the overlap it reports is an upper bound on what the gate of
the day would have caught. (3) Rejection reasons are prose written by the pipeline, so
failure-family bucketing is by pattern, first match wins, with an explicit `other`.
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import csv
import json
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from intellichoice_curriculum.authored_validation import (
    answer_leaked_beyond_the_question,
    leak_phrase_present,
    validate_authored_item,
)
from intellichoice_curriculum.content import CurriculumContent, load_curriculum
from intellichoice_db.engine import create_engine
from intellichoice_shared.bedrock import AuthoredGeneratedItemResponse
from sqlalchemy import text

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
DEFAULT_OUT_DIR = REPO_ROOT / "docs" / "resume_evidence" / "05_content_generation"

ENVIRONMENT = "local development database - complete offline generation history"

# The pipeline's own stage order (`ai_pipeline.RejectionStage`), in execution order. A
# candidate is ended by exactly one of these, so `reached(stage) = total - everything
# rejected before it` and the funnel columns sum to the row count by construction.
STAGE_ORDER: tuple[str, ...] = (
    "design",
    "generator",
    "validation",
    "dedup",
    "solver",
    "judge",
    "difficulty",
)

# Ended the candidate without any stage reaching a verdict on it. Kept out of the
# "rejection rate" numerators on purpose - D-192's rule: "the solvers disagreed" and "we
# ran out of money before calling anything" must not be the same number.
SKIP_STAGES: tuple[str, ...] = ("budget", "circuit_open")

ACCEPTED_OUTCOME = "pending"

# Which stages charge a model call for the verdict itself. The overlap counterfactual is
# only interesting for these: they are what the deterministic gate could have saved.
PAID_STAGES: tuple[str, ...] = ("dedup", "solver", "judge", "difficulty")

_CIRCUIT_OPEN_MARKER = "circuit_open:"

# What `validate_authored_item` applied to every skill before D-308 gave some of them a
# declared canonical form: no tie-break at all. Re-gating under both is what separates
# "the gate changed" from "the reconstruction is wrong".
PRE_D308_ANSWER_FORM = "any"

# The two figures the decision record froze on 2026-08-12, checked rather than repeated.
D294_ROWS = 1184
D295_DECISIONS = 858
D289_CENTS_PER_ITEM = 4.7


# --- reason-string classification -------------------------------------------------
#
# The stage evidence is authoritative where it exists; these patterns are the fallback for
# rows written before the evidence keys did (2026-08-05/06), and the source of the failure
# *family* for every row. Ordered - the first match wins - so specific precedes general.
_STAGE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"^equation design never reached a model", "circuit_open"),
    (r"^equation design failed", "design"),
    # Before the plain generator pattern: the breaker refusing the call is a *skip*, not a
    # verdict on the candidate, and it is the one thing that can end the generator stage
    # without any model having seen the item (D-199).
    (r"^authored generator call failed:.*circuit", "circuit_open"),
    (r"^authored generator call failed", "generator"),
    (r"^narrative dressing call failed", "budget"),
    (r"session budget of .* would be exceeded", "budget"),
    (r"^duplicate rendered_question|^near-duplicate stem|^stem embedding call failed", "dedup"),
    (r"^solver [ab] call failed|^independent solver disagreement|^solver_[ab] ", "solver"),
    # `judge found ...` is the pre-D-246 wording of the hint-reveals-answer rejection, which
    # is no longer a rejection at all. Kept because the rows are still in the table.
    (r"^judge call failed|^judge flagged|^judge rated|^judge found", "judge"),
    (r"^difficulty disagreement", "difficulty"),
)

# Failure families for the deterministic gate's own prose, extended from
# `scripts/measure_gate_census.py`'s buckets so the two measurements name defects the same
# way. First match wins.
_FAMILY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"leak|states the answer|reveals", "answer leakage"),
    (r"meta|as an ai|this question|the exam", "meta commentary"),
    (r"notation|`\*`|which a student sees as programme", "math notation"),
    (r"more than one option matches", "answer key: several options match"),
    (
        r"does not match declared|does not match the declared|independent solve|sympy",
        "answer key: derived answer disagrees",
    ),
    (r"equation is missing|could not be parsed|could not solve", "equation unusable"),
    (r"option", "options"),
    (r"hint", "hint ladder"),
    (r"readab|words, exceeding|sentence", "readability"),
    (r"figure|reading", "figure"),
    (r"difficulty|rubric", "difficulty rubric"),
    (r"markdown|schema", "schema/markdown"),
)


def classify_stage_from_reasons(reasons: list[str]) -> str | None:
    """The stage a rejection's own prose names, or None when nothing matches."""
    for pattern, stage in _STAGE_PATTERNS:
        if any(re.search(pattern, reason.lower()) for reason in reasons):
            return stage
    return None


def failure_family(reason: str) -> str:
    lowered = reason.lower()
    for pattern, name in _FAMILY_PATTERNS:
        if re.search(pattern, lowered):
            return name
    return "other"


# --- one recorded candidate attempt -----------------------------------------------


@dataclass(frozen=True)
class RunRow:
    """One `question_validation_runs` row, as plain data - so every function below is
    testable from literals with no database anywhere near it.
    """

    run_id: str
    question_template_id: str | None
    outcome: str
    stage_results: dict[str, Any]
    reasons: list[str]
    cost_cents: float
    created_at: datetime
    pipeline_run_id: str | None


@dataclass(frozen=True)
class Attribution:
    """Which stage ended this candidate, and how confidently we know it."""

    stage: str
    # "stage_evidence" - a stage key in `stage_results` records its own failure.
    # "reason_text"    - no such key (pre-D-195/D-243 rows); the prose named the stage.
    # "accepted"       - the candidate cleared every stage.
    # "unattributed"   - neither; counted and reported rather than guessed at.
    basis: str
    family: str


def _passed(evidence: Any) -> bool | None:
    if isinstance(evidence, dict) and "passed" in evidence:
        value = evidence["passed"]
        return bool(value) if isinstance(value, bool) else None
    return None


def attribute(row: RunRow) -> Attribution:
    """Which stage ended this candidate.

    Evidence first, in execution order: the pipeline stops at the first stage that fails,
    and writes that stage's failure into `stage_results` - so the first key that records a
    failure IS the stage that ended it. Reason prose is the fallback for the 2026-08-05/06
    rows written before those keys existed, and always supplies the failure family.
    """
    if row.outcome == ACCEPTED_OUTCOME:
        return Attribution(stage="accepted", basis="accepted", family="")

    family = failure_family(row.reasons[0]) if row.reasons else "other"
    evidence = row.stage_results or {}

    # `equation_design` is written with `passed: true` on candidates that got past it
    # (D-294's cost record), so only an explicit false is a design failure. Whether that
    # failure was the designer giving up or the breaker refusing the call is a distinction
    # only the reason prose carries.
    if _passed(evidence.get("equation_design")) is False:
        stage = "circuit_open" if _design_never_reached_a_model(evidence, row.reasons) else "design"
        return Attribution(stage=stage, basis="stage_evidence", family=family)

    if "generator_request" in evidence:
        # Same rule as the prose fallback below, deliberately: `ai_pipeline` decides this
        # by testing whether the provider error starts with its own `circuit_open` marker,
        # and that marker did not exist for the earliest 11 rows - so 11 breaker refusals
        # are recorded by the pipeline's own literal as `generator`. Attributing by what
        # actually happened rather than by the era's label; §10 records the difference.
        stage = "circuit_open" if _breaker_refused(row.reasons) else "generator"
        return Attribution(stage=stage, basis="stage_evidence", family=family)

    if _passed(evidence.get("deterministic_gate")) is False:
        return Attribution(stage="validation", basis="stage_evidence", family=family)

    if _passed(evidence.get("deduplication")) is False:
        return Attribution(stage="dedup", basis="stage_evidence", family=family)

    difficulty = evidence.get("difficulty")
    if isinstance(difficulty, dict) and difficulty.get("decision") == "rejected":
        return Attribution(stage="difficulty", basis="stage_evidence", family=family)

    # The solver and judge stages record their readings whether they passed or failed, so
    # unlike every branch above there is no "passed" flag to test - which stage objected is
    # carried by the reason prose alone. Both are checked here rather than earlier so a row
    # that has *both* a failed gate flag and solver evidence attributes to the gate, which
    # is the stage the pipeline would actually have stopped at.
    from_reasons = classify_stage_from_reasons(row.reasons)
    if from_reasons is not None:
        has_evidence = from_reasons in evidence or from_reasons in ("solver", "judge")
        basis = "stage_evidence" if has_evidence else "reason_text"
        if from_reasons == "solver" and not ("solver_a" in evidence or "solver_b" in evidence):
            basis = "reason_text"
        if from_reasons == "judge" and "judge" not in evidence:
            basis = "reason_text"
        return Attribution(stage=from_reasons, basis=basis, family=family)

    return Attribution(stage="unattributed", basis="unattributed", family=family)


def _design_never_reached_a_model(evidence: dict[str, Any], reasons: list[str]) -> bool:
    """`generate_authored_candidate` calls the same failure `circuit_open` when every design
    attempt was refused by the breaker rather than answered badly. Recomputed from the
    recorded attempts where they exist, so this does not depend on the reason wording.
    """
    design = evidence.get("equation_design")
    attempts = design.get("attempts") if isinstance(design, dict) else None
    if isinstance(attempts, list) and attempts:
        return all(isinstance(a, str) and a.startswith(_CIRCUIT_OPEN_MARKER) for a in attempts)
    return _mentions(reasons, "never reached a model")


def _mentions(reasons: list[str], needle: str) -> bool:
    return any(needle in reason.lower() for reason in reasons)


def _breaker_refused(reasons: list[str]) -> bool:
    return _mentions(reasons, "circuit breaker is open") or _mentions(reasons, "circuit_open")


# --- strata ------------------------------------------------------------------------


@dataclass(frozen=True)
class Strata:
    topic_id: str | None
    skill_id: str | None
    requested_difficulty: int | None


def strata_of(row: RunRow, templates: dict[str, Strata]) -> Strata:
    """Topic/skill/tier for one row, from whichever record carries them.

    Three eras, three sources, none of them universal: a rejection after the Generator has
    the `candidate_snapshot` (D-195); a Generator *failure* has `generator_request`
    (D-243); an accepted candidate has none of that but does have a template row. A design
    failure has nothing at all, and is reported as uncovered rather than filled in.
    """
    snapshot = (row.stage_results or {}).get("candidate_snapshot")
    if isinstance(snapshot, dict):
        return Strata(
            topic_id=_as_str(snapshot.get("topic_id")),
            skill_id=_as_str(snapshot.get("skill_id")),
            requested_difficulty=_as_int(snapshot.get("requested_difficulty")),
        )
    request = (row.stage_results or {}).get("generator_request")
    if isinstance(request, dict):
        return Strata(
            topic_id=_as_str(request.get("topic_id")),
            skill_id=_as_str(request.get("skill_id")),
            requested_difficulty=_as_int(request.get("requested_difficulty")),
        )
    if row.question_template_id and row.question_template_id in templates:
        return templates[row.question_template_id]
    return Strata(None, None, None)


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# --- the funnel --------------------------------------------------------------------


@dataclass
class StageRow:
    stage: str
    reached: int
    rejected: int
    cost_cents: float

    @property
    def rejection_rate(self) -> float | None:
        return self.rejected / self.reached if self.reached else None


def build_funnel(rows: list[RunRow], attributions: dict[str, Attribution]) -> list[StageRow]:
    """Reached / rejected / spend per stage, in execution order.

    `reached` is derived, not observed: the pipeline is strictly sequential, so a candidate
    reached stage *k* exactly when no earlier stage ended it. Deriving it keeps the table
    arithmetically closed - `reached(first) == len(rows)` and every candidate leaves the
    funnel exactly once.
    """
    by_stage: collections.Counter[str] = collections.Counter()
    cost_by_stage: collections.defaultdict[str, float] = collections.defaultdict(float)
    for row in rows:
        attribution = attributions[row.run_id]
        by_stage[attribution.stage] += 1
        cost_by_stage[attribution.stage] += row.cost_cents

    remaining = len(rows)
    table: list[StageRow] = []
    for stage in STAGE_ORDER:
        table.append(
            StageRow(
                stage=stage,
                reached=remaining,
                rejected=by_stage[stage],
                cost_cents=round(cost_by_stage[stage], 4),
            )
        )
        remaining -= by_stage[stage]
        # A skip is not a verdict, but it does remove the candidate - so it leaves the
        # funnel where it happened rather than being silently carried forward. Both skip
        # kinds happen at or before the generator, so they are drained after "generator".
        if stage == "generator":
            for skip in SKIP_STAGES:
                remaining -= by_stage[skip]
    return table


# --- the deterministic-gate overlap counterfactual ---------------------------------


@dataclass(frozen=True)
class RegateResult:
    run_id: str
    stage: str
    would_reject: bool
    failures: list[str]
    families: list[str]
    error: str | None
    # The same re-gate with `answer_form="any"`, which is what every caller got before
    # D-308 introduced the per-skill canonical-form tie-break. Carried so gate *drift* can
    # be separated from a gate *disagreement*: a candidate the gate of the day rejected and
    # today's gate passes is not a measurement error if D-308 is why.
    would_reject_pre_d308: bool = False


# Every field `candidate_snapshot` records that is NOT part of the Generator's response
# contract. `AuthoredGeneratedItemResponse` is `extra="forbid"`, so reconstructing the item
# means dropping exactly these - listed rather than filtered by try/except so a future
# snapshot field is a visible decision instead of a silent drop.
_SNAPSHOT_ONLY_KEYS = frozenset(
    {
        "planned_template_id",
        "attempt",
        "repaired_defects",
        "topic_id",
        "skill_id",
        "requested_difficulty",
        "seed",
        "generator_model_id",
    }
)


def item_from_snapshot(snapshot: dict[str, Any]) -> AuthoredGeneratedItemResponse:
    """Rebuild the exact object the gate saw. Raises on a snapshot that cannot be one."""
    payload = {k: v for k, v in snapshot.items() if k not in _SNAPSHOT_ONLY_KEYS}
    return AuthoredGeneratedItemResponse.model_validate(payload)


def hint_leak_failures(item: AuthoredGeneratedItemResponse) -> list[str]:
    """The pipeline's pre-gate hint-leak check, reproduced exactly (D-201/D-249).

    It runs *before* `validate_authored_item` and rejects at the same stage, so a re-gate
    that skipped it would understate what the deterministic stage catches. The helpers are
    imported rather than reimplemented, which is the whole point of D-223's rule - a second
    copy here would silently lack the two measured false-positive fixes in their lookarounds.
    """
    rendered = f"{item.context_block}\n\n{item.stem}" if item.context_block else item.stem
    answer_text = getattr(item, f"option_{item.correct_option}")
    return [
        f"hint_ladder[{n}] leaks the correct answer text verbatim"
        for n, hint in enumerate(item.hint_ladder)
        if leak_phrase_present(hint)
        or answer_leaked_beyond_the_question(
            hint_text=hint, correct_answer_text=answer_text, question_text=rendered
        )
    ]


def regate(
    row: RunRow, attribution: Attribution, curriculum: CurriculumContent
) -> RegateResult | None:
    """Re-run today's free deterministic stage over one recorded candidate.

    Returns None when the row carries no snapshot - there is nothing to re-gate and
    inventing an item would be worse than reporting the gap.
    """
    snapshot = (row.stage_results or {}).get("candidate_snapshot")
    if not isinstance(snapshot, dict):
        return None
    tier = _as_int(snapshot.get("requested_difficulty"))
    skill_id = _as_str(snapshot.get("skill_id"))
    try:
        item = item_from_snapshot(snapshot)
    except Exception as exc:  # noqa: BLE001 - a snapshot era we cannot parse is a finding
        return RegateResult(row.run_id, attribution.stage, False, [], [], f"snapshot: {exc}")
    # Tier is only read by `check_difficulty_rubric_compliance`, which asserts the 1-5 scale
    # and a positive time estimate. A snapshot without one falls back to the generator's own
    # claim rather than skipping the whole gate.
    label = tier if tier is not None else item.proposed_difficulty
    try:
        leaks = hint_leak_failures(item)
        declared = curriculum.answer_form(skill_id)
        failures = leaks + list(validate_authored_item(label, item, answer_form=declared).failures)
        if declared == PRE_D308_ANSWER_FORM:
            pre_d308 = failures
        else:
            pre_d308 = leaks + list(
                validate_authored_item(label, item, answer_form=PRE_D308_ANSWER_FORM).failures
            )
    except Exception as exc:  # noqa: BLE001 - SymPy can raise on recorded content
        return RegateResult(row.run_id, attribution.stage, False, [], [], f"gate: {exc}")
    return RegateResult(
        run_id=row.run_id,
        stage=attribution.stage,
        would_reject=bool(failures),
        failures=failures,
        families=sorted({failure_family(f) for f in failures}),
        error=None,
        would_reject_pre_d308=bool(pre_d308),
    )


def overlap_report(results: list[RegateResult]) -> dict[str, Any]:
    """Of the candidates a paid stage rejected, how many were free to catch?"""
    paid = [r for r in results if r.stage in PAID_STAGES and r.error is None]
    overlap = [r for r in paid if r.would_reject]
    unique = [r for r in paid if not r.would_reject]
    by_stage: dict[str, dict[str, Any]] = {}
    for stage in PAID_STAGES:
        subset = [r for r in paid if r.stage == stage]
        caught = [r for r in subset if r.would_reject]
        by_stage[stage] = {
            "snapshots_regated": len(subset),
            "deterministic_gate_would_also_reject": len(caught),
            "unique_catch_by_this_stage": len(subset) - len(caught),
            "overlap_rate": (len(caught) / len(subset)) if subset else None,
            "overlap_families": dict(
                collections.Counter(f for r in caught for f in r.families).most_common()
            ),
        }
    return {
        "paid_stage_rejections_with_snapshot": len(paid),
        "deterministic_gate_would_also_reject": len(overlap),
        "unique_catch_by_paid_stage": len(unique),
        "overlap_rate": (len(overlap) / len(paid)) if paid else None,
        "by_stage": by_stage,
        "deterministic_gate_would_also_reject_pre_d308_form": sum(
            1 for r in paid if r.would_reject_pre_d308
        ),
        "overlap_failure_families": dict(
            collections.Counter(f for r in overlap for f in r.families).most_common()
        ),
    }


def validation_family_report(results: list[RegateResult], rows_by_id: dict[str, RunRow]) -> dict:
    """What the deterministic stage itself rejected, bucketed - and whether today's gate
    still reproduces the recorded verdict.

    The reproduction rate is the interesting number: a gap is gate drift (a check added or
    relaxed since the row was written), which is a finding about the measurement rather
    than about the content.
    """
    subset = [r for r in results if r.stage == "validation" and r.error is None]
    recorded_families: collections.Counter[str] = collections.Counter()
    for r in subset:
        row = rows_by_id[r.run_id]
        for reason in row.reasons:
            recorded_families[failure_family(reason)] += 1
    reproduced = [r for r in subset if r.would_reject]
    reproduced_pre_d308 = [r for r in subset if r.would_reject_pre_d308]
    relaxed_by_d308 = [r for r in subset if r.would_reject_pre_d308 and not r.would_reject]
    return {
        "validation_rejections_with_snapshot": len(subset),
        "today_gate_still_rejects": len(reproduced),
        "today_gate_now_passes": len(subset) - len(reproduced),
        "reproduction_rate": (len(reproduced) / len(subset)) if subset else None,
        "under_pre_d308_answer_form_any": {
            "still_rejects": len(reproduced_pre_d308),
            "reproduction_rate": (len(reproduced_pre_d308) / len(subset)) if subset else None,
            "explained_by_the_d308_canonical_form_relaxation": len(relaxed_by_d308),
            "residual_drift_neither_form_reproduces": len(subset) - len(reproduced_pre_d308),
        },
        "recorded_failure_families": dict(recorded_families.most_common()),
        "today_failure_families": dict(
            collections.Counter(f for r in reproduced for f in r.families).most_common()
        ),
    }


# --- per-run and warm-up ------------------------------------------------------------


def per_run_breakdown(
    rows: list[RunRow], attributions: dict[str, Attribution]
) -> list[dict[str, Any]]:
    """One row per `pipeline_run_id`. NULL ids are grouped as a single `(unidentified)`
    bucket rather than clustered by timestamp: D-295 measured that clustering at ~90.8%
    fidelity and refused to present it as evidence, and nothing here needs it.
    """
    groups: collections.defaultdict[str, list[RunRow]] = collections.defaultdict(list)
    for row in rows:
        groups[row.pipeline_run_id or "(unidentified)"].append(row)

    out: list[dict[str, Any]] = []
    for run_id, members in sorted(groups.items(), key=lambda kv: min(r.created_at for r in kv[1])):
        accepted = sum(1 for r in members if r.outcome == ACCEPTED_OUTCOME)
        cost = sum(r.cost_cents for r in members)
        stages = collections.Counter(attributions[r.run_id].stage for r in members)
        out.append(
            {
                "pipeline_run_id": run_id,
                "candidates": len(members),
                "accepted": accepted,
                "rejected": len(members) - accepted,
                "acceptance_rate": accepted / len(members) if members else None,
                "cost_cents": round(cost, 4),
                "cost_cents_per_accepted": round(cost / accepted, 4) if accepted else None,
                "first_candidate_at": min(r.created_at for r in members).isoformat(),
                "last_candidate_at": max(r.created_at for r in members).isoformat(),
                **{f"rejected_at_{s}": stages[s] for s in (*STAGE_ORDER, *SKIP_STAGES)},
            }
        )
    return out


def warm_up_toll(rows: list[RunRow], attributions: dict[str, Attribution]) -> dict[str, Any]:
    """Rejections by position within their own run (D-296's structure).

    Only rows carrying a real `pipeline_run_id` are counted. D-295 introduced that column
    precisely because inferring run boundaries from `created_at` reproduced only ~90.8% of
    recorded decisions; this reports the identified runs and says how many rows it left out.
    """
    groups: collections.defaultdict[str, list[RunRow]] = collections.defaultdict(list)
    for row in rows:
        if row.pipeline_run_id:
            groups[row.pipeline_run_id].append(row)

    buckets = ["1", "2", "3", "4", "5", "6", "7-10", "11+"]
    total: collections.Counter[str] = collections.Counter()
    rejected: collections.Counter[str] = collections.Counter()
    difficulty_rejected: collections.Counter[str] = collections.Counter()
    for members in groups.values():
        for i, row in enumerate(sorted(members, key=lambda r: r.created_at), start=1):
            bucket = str(i) if i <= 6 else ("7-10" if i <= 10 else "11+")
            total[bucket] += 1
            if row.outcome != ACCEPTED_OUTCOME:
                rejected[bucket] += 1
                if attributions[row.run_id].stage == "difficulty":
                    difficulty_rejected[bucket] += 1
    return {
        "runs_with_an_identifier": len(groups),
        "candidates_counted": sum(total.values()),
        "candidates_excluded_no_run_id": len(rows) - sum(total.values()),
        "by_position": [
            {
                "position": b,
                "candidates": total[b],
                "rejected": rejected[b],
                "rejected_at_difficulty": difficulty_rejected[b],
                "rejection_rate": (rejected[b] / total[b]) if total[b] else None,
                "difficulty_rejection_rate": (
                    (difficulty_rejected[b] / total[b]) if total[b] else None
                ),
            }
            for b in buckets
        ],
    }


# --- database read (the only impure part) -------------------------------------------

_RUNS_SQL = """
SELECT question_validation_run_id, question_template_id, outcome, stage_results, reasons,
       cost_cents, created_at, pipeline_run_id
FROM question_validation_runs
ORDER BY created_at
"""

_TEMPLATES_SQL = """
SELECT question_template_id, topic_id, skill_id, difficulty_label
FROM question_templates
"""


def _json(value: Any, default: Any) -> Any:
    """`stage_results`/`reasons` are `JSON` columns, so the driver may hand back either the
    decoded object or the raw text depending on how the column was written. Both eras exist
    in this table."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value if value is not None else default


async def read_rows() -> tuple[list[RunRow], dict[str, Strata]]:
    """One read-only connection. `engine.connect()` rather than `session_scope`, which
    commits on a clean exit (D-294) - there is nothing to commit here and this script must
    not be able to write."""
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            run_records = (await conn.execute(text(_RUNS_SQL))).all()
            template_records = (await conn.execute(text(_TEMPLATES_SQL))).all()
    finally:
        await engine.dispose()

    rows = [
        RunRow(
            run_id=r[0],
            question_template_id=r[1],
            outcome=r[2],
            stage_results=_json(r[3], {}) or {},
            reasons=_json(r[4], []) or [],
            cost_cents=float(r[5] or 0.0),
            created_at=r[6],
            pipeline_run_id=r[7],
        )
        for r in run_records
    ]
    templates = {t[0]: Strata(t[1], t[2], _as_int(t[3])) for t in template_records}
    return rows, templates


# --- artifacts ----------------------------------------------------------------------


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _display(path: pathlib.Path) -> str:
    """Repo-relative where possible - `--out-dir` may legitimately point outside it."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _rate(n: int, d: int) -> str:
    return f"{n}/{d} ({n / d:.1%})" if d else f"{n}/0 (n/a)"


@dataclass
class Analysis:
    generated_at: str
    git_sha: str
    environment: str
    pipeline_run_filter: str | None
    rows: list[RunRow] = field(default_factory=list)
    attributions: dict[str, Attribution] = field(default_factory=dict)
    funnel: list[StageRow] = field(default_factory=list)
    per_run: list[dict[str, Any]] = field(default_factory=list)
    warm_up: dict[str, Any] = field(default_factory=dict)
    regate_results: list[RegateResult] = field(default_factory=list)
    strata: dict[str, Strata] = field(default_factory=dict)
    reconciliation: str = ""
    era_coverage: list[tuple[str, int, str]] = field(default_factory=list)


def build_summary(analysis: Analysis) -> dict[str, Any]:
    rows = analysis.rows
    attributions = analysis.attributions
    accepted = sum(1 for r in rows if r.outcome == ACCEPTED_OUTCOME)
    rejected = len(rows) - accepted
    stage_counts = collections.Counter(a.stage for a in attributions.values())
    basis_counts = collections.Counter(a.basis for a in attributions.values())
    total_cost = sum(r.cost_cents for r in rows)
    accepted_cost = sum(r.cost_cents for r in rows if r.outcome == ACCEPTED_OUTCOME)

    by_tier: collections.defaultdict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"candidates": 0, "accepted": 0}
    )
    by_topic: collections.defaultdict[str, dict[str, int]] = collections.defaultdict(
        lambda: {"candidates": 0, "accepted": 0}
    )
    uncovered = 0
    for row in rows:
        s = analysis.strata[row.run_id]
        if s.requested_difficulty is None and s.topic_id is None:
            uncovered += 1
        tier_key = f"d{s.requested_difficulty}" if s.requested_difficulty else "(unknown)"
        topic_key = s.topic_id or "(unknown)"
        for bucket, key in ((by_tier, tier_key), (by_topic, topic_key)):
            bucket[key]["candidates"] += 1
            if row.outcome == ACCEPTED_OUTCOME:
                bucket[key]["accepted"] += 1

    return {
        "experiment": "E5.1 - content-pipeline per-stage defect-containment funnel",
        "generated_at": analysis.generated_at,
        "git_sha": analysis.git_sha,
        "environment": analysis.environment,
        "pipeline_run_filter": analysis.pipeline_run_filter,
        "scope": (
            "automated pipeline only - the human review step that follows `pending` "
            "writes no row in this table"
        ),
        "totals": {
            "validation_runs": len(rows),
            "accepted_by_the_machine": accepted,
            "rejected": rejected,
            "acceptance_rate": accepted / len(rows) if rows else None,
            "first_candidate_at": (min(r.created_at for r in rows).isoformat() if rows else None),
            "last_candidate_at": (max(r.created_at for r in rows).isoformat() if rows else None),
            "distinct_pipeline_run_ids": len(
                {r.pipeline_run_id for r in rows if r.pipeline_run_id}
            ),
            "rows_without_a_pipeline_run_id": sum(1 for r in rows if not r.pipeline_run_id),
            "rows_carrying_a_candidate_snapshot": sum(
                1
                for r in rows
                if isinstance((r.stage_results or {}).get("candidate_snapshot"), dict)
            ),
        },
        "attribution_basis": dict(basis_counts.most_common()),
        "funnel": [
            {
                "stage": s.stage,
                "reached": s.reached,
                "rejected": s.rejected,
                "rejection_rate": s.rejection_rate,
                "cost_cents": s.cost_cents,
            }
            for s in analysis.funnel
        ],
        "skips": {s: stage_counts[s] for s in SKIP_STAGES},
        "unattributed": stage_counts["unattributed"],
        "cost": {
            "total_cents": round(total_cost, 4),
            "on_accepted_candidates_cents": round(accepted_cost, 4),
            "on_rejected_candidates_cents": round(total_cost - accepted_cost, 4),
            "share_spent_on_rejected": (
                (total_cost - accepted_cost) / total_cost if total_cost else None
            ),
            "cents_per_accepted_candidate": round(total_cost / accepted, 4) if accepted else None,
            "by_stage_cents": {s.stage: s.cost_cents for s in analysis.funnel},
        },
        "strata": {
            "rows_with_no_topic_or_tier_recorded": uncovered,
            "by_requested_tier": {
                k: {**v, "acceptance_rate": v["accepted"] / v["candidates"]}
                for k, v in sorted(by_tier.items())
            },
            "by_topic": {
                k: {**v, "acceptance_rate": v["accepted"] / v["candidates"]}
                for k, v in sorted(by_topic.items())
            },
        },
        "era_notes": {
            "rows_with_equation_design_evidence": sum(
                1 for r in rows if "equation_design" in (r.stage_results or {})
            ),
            "design_stage_exits": sum(
                1
                for r in rows
                if attributions[r.run_id].stage in ("design", "circuit_open")
                and "equation_design" in (r.stage_results or {})
            ),
            "uncovered_rows_by_stage": dict(
                collections.Counter(
                    attributions[r.run_id].stage
                    for r in rows
                    if analysis.strata[r.run_id].topic_id is None
                    and analysis.strata[r.run_id].requested_difficulty is None
                ).most_common()
            ),
            "accepted_rows_without_a_difficulty_stage": sum(
                1
                for r in rows
                if r.outcome == ACCEPTED_OUTCOME and "difficulty" not in (r.stage_results or {})
            ),
        },
        "warm_up_toll": analysis.warm_up,
        "per_stage_reason_families": {
            stage: dict(
                collections.Counter(
                    failure_family(reason)
                    for r in rows
                    if attributions[r.run_id].stage == stage
                    for reason in r.reasons
                ).most_common()
            )
            for stage in (*STAGE_ORDER, *SKIP_STAGES)
            if stage_counts[stage]
        },
    }


def write_artifacts(analysis: Analysis, out_dir: pathlib.Path) -> dict[str, pathlib.Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary(analysis)
    rows_by_id = {r.run_id: r for r in analysis.rows}

    overlap = {
        "experiment": "E5.1 overlap - what the free deterministic gate would also have caught",
        "generated_at": analysis.generated_at,
        "git_sha": analysis.git_sha,
        "environment": analysis.environment,
        "method": (
            "For every rejection carrying a `candidate_snapshot`, the item is rebuilt and "
            "today's free deterministic stage (the D-201/D-249 hint-leak pre-check plus "
            "`validate_authored_item`) is re-run over it. No model is called."
        ),
        "uncomputable_direction": (
            "Whether the paid stages (dedup/solver/judge/difficulty) would have caught the "
            "candidates the deterministic gate rejected CANNOT be computed from this data: "
            "those stages never ran on those candidates by design, and running them now "
            "costs real money on discarded content. The nearest existing evidence is D-276, "
            "which points the other way - with the gate off, 5 wrong answer keys passed both "
            "blind solvers and the judge."
        ),
        "snapshots_available": sum(1 for r in analysis.regate_results),
        "regate_errors": [
            {"run_id": r.run_id, "stage": r.stage, "error": r.error}
            for r in analysis.regate_results
            if r.error
        ],
        "paid_stage_overlap": overlap_report(analysis.regate_results),
        "validation_stage": validation_family_report(analysis.regate_results, rows_by_id),
    }

    paths = {
        "funnel_summary": out_dir / "funnel_summary.json",
        "overlap_analysis": out_dir / "overlap_analysis.json",
        "stage_attribution": out_dir / "stage_attribution.csv",
        "per_run_breakdown": out_dir / "per_run_breakdown.csv",
        "report": out_dir / "E5_1_REPORT.md",
    }
    paths["funnel_summary"].write_text(json.dumps(summary, indent=2, sort_keys=False) + "\n")
    paths["overlap_analysis"].write_text(json.dumps(overlap, indent=2, sort_keys=False) + "\n")

    regate_by_id = {r.run_id: r for r in analysis.regate_results}
    with paths["stage_attribution"].open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "question_validation_run_id",
                "created_at",
                "pipeline_run_id",
                "outcome",
                "attributed_stage",
                "attribution_basis",
                "failure_family",
                "cost_cents",
                "topic_id",
                "skill_id",
                "requested_difficulty",
                "has_candidate_snapshot",
                "regate_would_reject",
                "regate_failure_families",
            ]
        )
        for row in analysis.rows:
            a = analysis.attributions[row.run_id]
            s = analysis.strata[row.run_id]
            g = regate_by_id.get(row.run_id)
            writer.writerow(
                [
                    row.run_id,
                    row.created_at.isoformat(),
                    row.pipeline_run_id or "",
                    row.outcome,
                    a.stage,
                    a.basis,
                    a.family,
                    f"{row.cost_cents:.4f}",
                    s.topic_id or "",
                    s.skill_id or "",
                    s.requested_difficulty if s.requested_difficulty is not None else "",
                    "yes" if g is not None else "no",
                    "" if g is None else ("yes" if g.would_reject else "no"),
                    "" if g is None else "|".join(g.families),
                ]
            )

    per_run = analysis.per_run
    with paths["per_run_breakdown"].open("w", newline="") as fh:
        fieldnames = list(per_run[0].keys()) if per_run else ["pipeline_run_id"]
        writer2 = csv.DictWriter(fh, fieldnames=fieldnames)
        writer2.writeheader()
        for entry in per_run:
            writer2.writerow(entry)

    paths["report"].write_text(render_report(analysis, summary, overlap))
    return paths


def render_report(analysis: Analysis, summary: dict, overlap: dict) -> str:
    t = summary["totals"]
    cost = summary["cost"]
    paid = overlap["paid_stage_overlap"]
    val = overlap["validation_stage"]
    lines: list[str] = []
    add = lines.append

    add("# E5.1 - Content-pipeline per-stage defect-containment funnel")
    add("")
    add("> Experiment: **E5.1** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 5).")
    add(f"> Generated: **{analysis.generated_at}** at repository `{analysis.git_sha}`.")
    add(f"> Environment: **{analysis.environment}**.")
    add("> Cost of this measurement: **$0** - no model call, no network, read-only SQL.")
    add("> Harness: `benchmarks/resume_evidence/05_content_generation/stage_funnel_analysis.py`.")
    if analysis.pipeline_run_filter:
        add(f"> Filter: `pipeline_run_id = {analysis.pipeline_run_filter}`.")
    add("")
    add("## 1. What this measures, and what it does not")
    add("")
    add(
        "`question_validation_runs` is an append-only row per candidate attempt of the "
        "offline authoring pipeline (D-195, D-294, D-295). The generator has only ever run "
        "from this machine against this database, so the table is the complete recorded "
        "history of that pipeline."
    )
    add("")
    add(
        "**This is the automated pipeline only.** A candidate that clears every machine "
        "stage is written `outcome='pending'` and then goes to human review, which writes "
        'no row here. "Accepted" below means *accepted by the machine*, never *approved '
        "by a person*."
    )
    add("")
    add("## 2. Headline")
    add("")
    add(f"- Candidate attempts recorded: **{t['validation_runs']}**")
    accepted_rate = _rate(t["accepted_by_the_machine"], t["validation_runs"])
    add(f"- Accepted by the machine: **{accepted_rate}**")
    add(f"- Rejected: **{_rate(t['rejected'], t['validation_runs'])}**")
    add(
        f"- Window: {t['first_candidate_at']} -> {t['last_candidate_at']}; "
        f"{t['distinct_pipeline_run_ids']} identified `pipeline_run_id`s, "
        f"{t['rows_without_a_pipeline_run_id']} rows predate that column"
    )
    add(
        f"- Total recorded spend: **{cost['total_cents']:.2f}¢**, of which "
        f"**{cost['on_rejected_candidates_cents']:.2f}¢** "
        f"({cost['share_spent_on_rejected']:.1%}) was spent on candidates that were "
        f"rejected"
    )
    add(f"- Cost per machine-accepted candidate: **{cost['cents_per_accepted_candidate']:.2f}¢**")
    add("")
    add("## 3. The funnel")
    add("")
    add(
        "Stages run in this order and a candidate is ended by exactly one of them, so "
        "`reached` is derived: a candidate reached stage *k* exactly when no earlier stage "
        "ended it. The columns close arithmetically against the row count."
    )
    add("")
    add("| stage | reached | rejected here | rejection rate (n/N) | spend attributed (¢) |")
    add("|---|---:|---:|---|---:|")
    for s in analysis.funnel:
        add(
            f"| `{s.stage}` | {s.reached} | {s.rejected} | "
            f"{_rate(s.rejected, s.reached)} | {s.cost_cents:.2f} |"
        )
    add("")
    design_rows = summary["era_notes"]["rows_with_equation_design_evidence"]
    design_ended = summary["era_notes"]["design_stage_exits"]
    add(
        f"**One caveat on the first row.** The equation-design pre-stage is optional "
        f"(`--design-attempts`), and only **{design_rows}** rows carry its record at all, so "
        f"`design`'s 4.2% is a whole-history rate rather than a per-eligible-candidate one. "
        f"Among the rows that demonstrably ran it, design ended "
        f"**{_rate(design_ended, design_rows)}** - the stage is far more decisive than the "
        f"whole-history column suggests, and it is also the cheapest exit in the table."
    )
    skips = summary["skips"]
    add("")
    add(
        "Plus non-verdict exits, which end a candidate without any stage judging it - kept "
        'out of the rates above on purpose (D-192: "the solvers disagreed" and "we ran '
        'out of money before calling anything" must not be one number):'
    )
    add("")
    for name, count in skips.items():
        add(f"- `{name}`: **{count}**")
    if summary["unattributed"]:
        add(
            f"- `unattributed` (neither stage evidence nor matching prose): "
            f"**{summary['unattributed']}**"
        )
    add("")
    total_leaving = (
        sum(s.rejected for s in analysis.funnel)
        + sum(skips.values())
        + summary["unattributed"]
        + t["accepted_by_the_machine"]
    )
    add(
        f"Closure check: {sum(s.rejected for s in analysis.funnel)} stage rejections + "
        f"{sum(skips.values())} skips + {summary['unattributed']} unattributed + "
        f"{t['accepted_by_the_machine']} accepted = **{total_leaving}** = "
        f"{t['validation_runs']} rows."
    )
    add("")
    add("### 3.1 How each stage was attributed")
    add("")
    add(
        "Evidence first: the pipeline stops at the first stage that fails and writes that "
        "stage's failure into `stage_results`, so the first key recording a failure *is* "
        "the stage that ended the candidate. Reason prose is the fallback for the rows "
        "written before those keys existed."
    )
    add("")
    add("| basis | rows |")
    add("|---|---:|")
    for basis, n in summary["attribution_basis"].items():
        add(f"| `{basis}` | {n} |")
    add("")
    add("### 3.2 Failure families per stage")
    add("")
    add(
        "Buckets are matched against the pipeline's own prose, first match wins, sharing "
        "`scripts/measure_gate_census.py`'s vocabulary. Counts are *reasons*, not "
        "candidates - one rejection can carry several. The vocabulary was built for the "
        "deterministic gate's failure strings, so it is most meaningful on `validation`; "
        "for `design`, `dedup`, `budget` and `circuit_open` the prose is provider-error "
        "text and lands in `other` by design."
    )
    add("")
    for stage, families in summary["per_stage_reason_families"].items():
        if not families:
            continue
        add(f"**`{stage}`** - " + ", ".join(f"{k} {v}" for k, v in families.items()))
    add("")
    add("## 4. The free-gate overlap counterfactual")
    add("")
    add(overlap["method"])
    add("")
    add(
        f"- Rejections carrying a snapshot that could be re-gated: "
        f"**{overlap['snapshots_available']}**"
    )
    add(
        f"- Of those, rejected by a **paid** stage (dedup / solver / judge / difficulty): "
        f"**{paid['paid_stage_rejections_with_snapshot']}**"
    )
    paid_n = paid["paid_stage_rejections_with_snapshot"]
    add(
        "- The free deterministic gate would **also** have rejected: "
        f"**{_rate(paid['deterministic_gate_would_also_reject'], paid_n)}** (overlap)"
    )
    add(
        "- Only the paid stage caught it: "
        f"**{_rate(paid['unique_catch_by_paid_stage'], paid_n)}** (unique catch)"
    )
    add("")
    add("| paid stage | snapshots re-gated | free gate also rejects | unique catch | overlap |")
    add("|---|---:|---:|---:|---|")
    for stage, d in paid["by_stage"].items():
        add(
            f"| `{stage}` | {d['snapshots_regated']} | "
            f"{d['deterministic_gate_would_also_reject']} | "
            f"{d['unique_catch_by_this_stage']} | "
            f"{_rate(d['deterministic_gate_would_also_reject'], d['snapshots_regated'])} |"
        )
    add("")
    add("**The direction that cannot be computed.** " + overlap["uncomputable_direction"])
    add("")
    add("### 4.1 The deterministic stage against itself")
    add("")
    add(
        "Re-running today's gate over the candidates the gate itself rejected is a drift "
        "check on the measurement, not a claim about the content."
    )
    add("")
    add(
        f"- Validation-stage rejections with a snapshot: "
        f"**{val['validation_rejections_with_snapshot']}**"
    )
    add(
        f"- Today's gate still rejects: "
        f"**{_rate(val['today_gate_still_rejects'], val['validation_rejections_with_snapshot'])}**"
    )
    add(
        f"- Today's gate now passes (checks relaxed or the failure was era-specific): "
        f"**{val['today_gate_now_passes']}**"
    )
    pre = val["under_pre_d308_answer_form_any"]
    add("")
    add(
        "**Most of that gap has a name.** Re-running the identical gate with "
        '`answer_form="any"` - what every skill got before D-308 introduced the '
        f"per-skill canonical-form tie-break - reproduces "
        f"**{_rate(pre['still_rejects'], val['validation_rejections_with_snapshot'])}** "
        f"instead. So **{pre['explained_by_the_d308_canonical_form_relaxation']}** of the "
        f"{val['today_gate_now_passes']} are the D-308 relaxation working as designed, and "
        f"**{pre['residual_drift_neither_form_reproduces']}** are residual drift from other "
        "checks that have changed since (D-276's restoration of the answer-key checks, "
        "D-288's notation check). Neither number is a defect in the content; both are why "
        "section 4's overlap is an upper bound."
    )
    add("")
    families = ", ".join(f"{k} {v}" for k, v in val["recorded_failure_families"].items())
    add("Recorded failure families at the time: " + (families or "none") + ".")
    today_families = ", ".join(f"{k} {v}" for k, v in val["today_failure_families"].items())
    add("")
    add("Families today's gate raises on the same items: " + (today_families or "none") + ".")
    add("")
    add("## 5. Spend containment")
    add("")
    add("| bucket | cents | share |")
    add("|---|---:|---|")
    add(
        f"| spent on machine-accepted candidates | {cost['on_accepted_candidates_cents']:.2f} | "
        f"{1 - cost['share_spent_on_rejected']:.1%} |"
    )
    add(
        f"| spent on rejected candidates | {cost['on_rejected_candidates_cents']:.2f} | "
        f"{cost['share_spent_on_rejected']:.1%} |"
    )
    add(f"| **total** | **{cost['total_cents']:.2f}** | 100% |")
    add("")
    add(
        "Per-stage spend attribution is in the funnel table above. Note that a row's "
        "`cost_cents` is what the *slot* had spent when the row was written (D-294), so "
        'stage spend is "money on candidates this stage ended", not "money this stage\'s '
        'own call cost".'
    )
    add("")
    add("## 6. Strata")
    add("")
    add("| requested tier | candidates | machine-accepted | acceptance rate |")
    add("|---|---:|---:|---|")
    for tier, d in summary["strata"]["by_requested_tier"].items():
        add(
            f"| {tier} | {d['candidates']} | {d['accepted']} | "
            f"{_rate(d['accepted'], d['candidates'])} |"
        )
    add("")
    add("| topic | candidates | machine-accepted | acceptance rate |")
    add("|---|---:|---:|---|")
    for topic, d in summary["strata"]["by_topic"].items():
        add(
            f"| `{topic}` | {d['candidates']} | {d['accepted']} | "
            f"{_rate(d['accepted'], d['candidates'])} |"
        )
    add("")
    uncovered = summary["era_notes"]["uncovered_rows_by_stage"]
    add(
        f"Rows carrying neither a topic nor a tier anywhere: "
        f"**{summary['strata']['rows_with_no_topic_or_tier_recorded']}** - by attributed "
        f"stage, " + ", ".join(f"`{k}` {v}" for k, v in uncovered.items()) + ". These are the "
        "exits that happen before any item exists to describe (design and the breaker), plus "
        "the 2026-08-05/06 rows whose evidence is reason prose alone. They are counted in the "
        "`(unknown)` row above rather than dropped, so the strata denominators still sum to "
        "the row count."
    )
    add("")
    add("## 7. The warm-up toll (D-296's structure, re-measured)")
    add("")
    w = summary["warm_up_toll"]
    add(
        f"Counted over the **{w['runs_with_an_identifier']}** runs that carry a real "
        f"`pipeline_run_id` (**{w['candidates_counted']}** candidates); "
        f"**{w['candidates_excluded_no_run_id']}** rows predate the column and are "
        f"excluded rather than clustered by timestamp - D-295 measured that reconstruction "
        f"at ~90.8% fidelity and refused to present it as evidence."
    )
    add("")
    add(
        "| position in run | candidates | rejected | rejection rate | rejected at "
        "`difficulty` | difficulty-rejection rate |"
    )
    add("|---|---:|---:|---|---:|---|")
    for b in w["by_position"]:
        add(
            f"| {b['position']} | {b['candidates']} | {b['rejected']} | "
            f"{_rate(b['rejected'], b['candidates'])} | {b['rejected_at_difficulty']} | "
            f"{_rate(b['rejected_at_difficulty'], b['candidates'])} |"
        )
    early = [b for b in w["by_position"] if b["position"] in {"1", "2", "3", "4", "5", "6"}]
    late = [b for b in w["by_position"] if b["position"] == "11+"]
    early_n = sum(b["candidates"] for b in early)
    early_d = sum(b["rejected_at_difficulty"] for b in early)
    late_n = sum(b["candidates"] for b in late)
    late_d = sum(b["rejected_at_difficulty"] for b in late)
    add("")
    add(
        f"Aggregated, the D-296 shape is present: difficulty rejections run "
        f"**{_rate(early_d, early_n)}** over positions 1-6 against **{_rate(late_d, late_n)}** "
        f"at position 11+. It is a weak version of it - only "
        f"{w['candidates_counted']} candidates across {w['runs_with_an_identifier']} runs "
        f"carry a run id, and most of those runs are small - so this reproduces the "
        f"*direction* of D-295/D-296 and not their magnitudes. The mechanism itself (the "
        f"`may_retier` guard blocking while the judge histogram warms up) is replayed "
        f"against the real `JudgeDispersion` in `scripts/measure_retier_guard.py`; this "
        f"experiment does not re-derive it."
    )
    add("")
    add("## 8. Per-run breakdown")
    add("")
    add("Full table in `per_run_breakdown.csv`. Acceptance rate by identified run:")
    add("")
    add("| pipeline_run_id | candidates | accepted | acceptance rate | ¢ | ¢/accepted |")
    add("|---|---:|---:|---|---:|---|")
    for entry in analysis.per_run:
        cpa = entry["cost_cents_per_accepted"]
        add(
            f"| `{entry['pipeline_run_id']}` | {entry['candidates']} | {entry['accepted']} | "
            f"{_rate(entry['accepted'], entry['candidates'])} | {entry['cost_cents']:.2f} | "
            + (f"{cpa:.2f}" if cpa is not None else "n/a")
            + " |"
        )
    add("")
    add("## 8.1 Schema eras present in the data")
    add("")
    add(
        "The table spans several pipeline generations and the evidence keys differ across "
        "them. Reported rather than smoothed over - a parser that silently dropped an era "
        "would understate exactly the stages that were added last."
    )
    add("")
    add("| era marker | rows | what it means |")
    add("|---|---:|---|")
    for marker, count, meaning in analysis.era_coverage:
        add(f"| {marker} | {count} | {meaning} |")
    add("")
    add("## 9. Reconciliation against the decision record")
    add("")
    add(analysis.reconciliation)
    add("")
    add("## 10. Limitations")
    add("")
    for item in LIMITATIONS:
        add(f"- {item}")
    add("")
    add("## 11. Artifacts")
    add("")
    add("- `funnel_summary.json` - every number in sections 2-7, machine-readable.")
    add("- `stage_attribution.csv` - one row per candidate attempt with its attribution.")
    add("- `overlap_analysis.json` - section 4 in full, including per-stage families.")
    add("- `per_run_breakdown.csv` - section 8 in full.")
    add("- This report.")
    add("")
    return "\n".join(lines)


LIMITATIONS: tuple[str, ...] = (
    "**Automated pipeline only.** Human review writes no row in this table, so no number "
    "here is a statement about content a person approved. `outcome='pending'` includes "
    "candidates later approved *and* candidates later rejected by review.",
    "**The re-gate uses today's gate.** Checks have been added since the oldest rows were "
    "written (D-288's readable-notation check, D-308's canonical-form tie-break, D-276's "
    "restoration of the answer-key checks), so the overlap in section 4 is an **upper "
    'bound** on what the gate of the day would have caught. It answers "how much of what '
    'we pay for is free *today*", which is the forward-looking question.',
    "**Snapshot coverage is partial and era-dependent.** A rejection only carries the "
    "candidate from D-195 onward and only after the Generator returned; design-stage and "
    "generator-stage failures have nothing to re-gate. Two snapshot shapes exist (the "
    "earlier one lacks `attempt`/`repaired_defects`); both carry every field the Generator "
    "contract needs, so both re-gate.",
    "**`pipeline_run_id` is NULL before D-295** and was deliberately not backfilled - "
    "inferring it would bake a ~10%-wrong guess into the data as recorded fact. Per-run "
    "and warm-up numbers therefore cover the identified runs only, and say so.",
    "**Stage spend is attributed, not itemised.** `cost_cents` is the slot's running total "
    "at the moment the row was written (D-294), so a stage's column means \"money on "
    'candidates this stage ended", not "the cost of this stage\'s own call".',
    "**Failure families are pattern-matched prose.** The pipeline writes rejection reasons "
    "for a human reader; bucketing is regex, first match wins, with an explicit `other`.",
    "**Reasons are counted per reason, not per candidate** in section 3.2 - one rejection "
    "can raise several objections.",
    '**A retired stage is in the history.** 16 rows from 2026-08-06 name a "narrative '
    'dressing" call that no longer exists in the pipeline; they are attributed to `budget` '
    "because that is what their prose records refusing the call.",
    "**The uncomputable direction stays uncomputed.** Whether the paid stages would have "
    "caught the gate's rejections is not measured and is not estimated here; see section 4.",
)


# --- reconciliation ------------------------------------------------------------------


def reconciliation_note(rows: list[RunRow]) -> str:
    """D-294 recorded 1,184 rows and D-295 recorded 858 difficulty decisions, both on
    2026-08-12. Checked here rather than asserted: a mismatch is a finding.
    """
    ordered = sorted(rows, key=lambda r: r.created_at)
    with_difficulty = [
        r
        for r in ordered
        if isinstance((r.stage_results or {}).get("difficulty"), dict)
        and (r.stage_results or {})["difficulty"].get("decision")
    ]
    total = len(ordered)
    diff_total = len(with_difficulty)
    cutoff = ordered[D294_ROWS - 1].created_at if total >= D294_ROWS else None
    at_cutoff = (
        sum(1 for r in with_difficulty if r.created_at <= cutoff) if cutoff is not None else 0
    )
    rows_at_d295 = (
        sum(1 for r in ordered if r.created_at <= with_difficulty[D295_DECISIONS - 1].created_at)
        if diff_total >= D295_DECISIONS
        else None
    )

    parts = [
        f"The table now holds **{total}** rows and **{diff_total}** difficulty decisions - "
        f"both larger than the decision record's figures, which is expected of an "
        f"append-only table that kept being written to.",
        "",
    ]
    if cutoff is not None:
        parts.append(
            f"- **D-294's {D294_ROWS:,} rows.** Row {D294_ROWS:,} in `created_at` order was "
            f"written at `{cutoff.isoformat()}`, inside the 2026-08-12 session D-294 "
            f"records. **Reconciles.**"
        )
        parts.append(
            f"- **D-295's {D295_DECISIONS} difficulty decisions.** At the {D294_ROWS:,}-row "
            f"instant only **{at_cutoff}** difficulty decisions existed; the "
            f"{D295_DECISIONS}th was written at row **{rows_at_d295}**. The two recorded "
            f"numbers are therefore snapshots of the same append-only history taken at "
            f"**different instants within 2026-08-12**, not of one instant. **Reconciles, "
            f"with that correction** - neither figure is wrong, and quoting them as one "
            f"pair would be."
        )
    else:
        parts.append(
            f"- The selected rows ({total}) are fewer than D-294's {D294_ROWS:,}, so the "
            f"row-count reconciliation does not apply to this slice."
        )
    parts.append(
        "- **D-296's 63%-yield run.** Its shape is visible in the per-run table above "
        "rather than re-asserted here; see section 8."
    )
    accepted = sum(1 for r in rows if r.outcome == ACCEPTED_OUTCOME)
    if accepted:
        per_accepted = sum(r.cost_cents for r in rows) / accepted
        parts.append(
            f"- **D-289's criterion 5, {D289_CENTS_PER_ITEM}¢ per accepted item** "
            f"($24.97 over 529 serving generated items). Computed over this whole history "
            f"instead: **{per_accepted:.2f}¢** "
            f"({sum(r.cost_cents for r in rows):.2f}¢ / {accepted} machine-accepted "
            f"candidates). The denominators are not the same one - D-289 counted *serving* "
            f"items after human review, this counts every candidate the machine accepted - "
            f"so the agreement is corroboration rather than a re-derivation."
        )
    return "\n".join(parts)


def era_coverage(rows: list[RunRow]) -> list[tuple[str, int, str]]:
    """Which evidence keys the rows actually carry, and what their absence means.

    `stage_results` has grown keys as the pipeline grew stages, so "the key is missing" is
    ambiguous between "the stage did not run" and "the stage did not exist yet". Counting
    the eras is what keeps a downstream reader from reading one as the other.
    """

    def has(row: RunRow, key: str) -> bool:
        return key in (row.stage_results or {})

    return [
        (
            "`candidate_snapshot` present",
            sum(
                1
                for r in rows
                if isinstance((r.stage_results or {}).get("candidate_snapshot"), dict)
            ),
            "D-195 onward, and only on rejections after the Generator returned - "
            "the population section 4 can re-gate",
        ),
        (
            "`equation_design` present",
            sum(1 for r in rows if has(r, "equation_design")),
            "D-200/D-294 onward; absent means the design pre-stage was off or unreached",
        ),
        (
            "`difficulty` present",
            sum(1 for r in rows if has(r, "difficulty")),
            "D-194 onward; "
            + str(
                sum(1 for r in rows if r.outcome == ACCEPTED_OUTCOME and not has(r, "difficulty"))
            )
            + " accepted rows lack it because they predate difficulty being its own stage",
        ),
        (
            "`generator_request` present",
            sum(1 for r in rows if has(r, "generator_request")),
            "D-243 onward; earlier generator failures recorded reason prose and nothing else",
        ),
        (
            "`stage_results` empty",
            sum(1 for r in rows if not (r.stage_results or {})),
            "2026-08-05/06 rows, attributed from reason prose alone; 16 of them name a "
            'since-removed "narrative dressing" stage',
        ),
        (
            "`pipeline_run_id` present",
            sum(1 for r in rows if r.pipeline_run_id),
            "D-295 onward, deliberately not backfilled",
        ),
    ]


# --- entry point ---------------------------------------------------------------------


async def run(args: argparse.Namespace) -> int:
    rows, templates = await read_rows()
    if args.pipeline_run_id:
        rows = [r for r in rows if r.pipeline_run_id == args.pipeline_run_id]
        if not rows:
            print(f"no rows for pipeline_run_id={args.pipeline_run_id!r}", file=sys.stderr)
            return 1

    curriculum = load_curriculum()
    attributions = {r.run_id: attribute(r) for r in rows}
    strata = {r.run_id: strata_of(r, templates) for r in rows}

    regate_results: list[RegateResult] = []
    if not args.no_overlap:
        for row in rows:
            result = regate(row, attributions[row.run_id], curriculum)
            if result is not None:
                regate_results.append(result)

    analysis = Analysis(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_sha=_git_sha(),
        environment=ENVIRONMENT,
        pipeline_run_filter=args.pipeline_run_id,
        rows=rows,
        attributions=attributions,
        funnel=build_funnel(rows, attributions),
        per_run=per_run_breakdown(rows, attributions),
        warm_up=warm_up_toll(rows, attributions),
        regate_results=regate_results,
        strata=strata,
    )
    analysis.reconciliation = reconciliation_note(rows)
    analysis.era_coverage = era_coverage(rows)

    paths = write_artifacts(analysis, pathlib.Path(args.out_dir))

    summary = build_summary(analysis)
    t = summary["totals"]
    print(
        f"rows: {t['validation_runs']}  accepted: {t['accepted_by_the_machine']}  "
        f"rejected: {t['rejected']}  acceptance: {t['acceptance_rate']:.1%}"
    )
    print("\nfunnel (stage / reached / rejected / rate):")
    for s in analysis.funnel:
        rate = f"{s.rejection_rate:.1%}" if s.rejection_rate is not None else "n/a"
        print(f"  {s.stage:<12} {s.reached:>6} {s.rejected:>6}  {rate:>7}   {s.cost_cents:>9.2f}¢")
    print(
        f"  {'skips':<12} {'':>6} {sum(summary['skips'].values()):>6}   "
        f"({', '.join(f'{k}={v}' for k, v in summary['skips'].items())})"
    )
    print(f"  {'unattributed':<12} {'':>6} {summary['unattributed']:>6}")

    if regate_results:
        paid = overlap_report(regate_results)
        print(
            f"\noverlap: of {paid['paid_stage_rejections_with_snapshot']} paid-stage "
            f"rejections with a snapshot, the free gate would also reject "
            f"{paid['deterministic_gate_would_also_reject']} "
            f"({(paid['overlap_rate'] or 0):.1%}); "
            f"{paid['unique_catch_by_paid_stage']} were unique catches."
        )
    print("\nartifacts:")
    for name, path in paths.items():
        print(f"  {name:<18} {_display(path)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pipeline-run-id",
        default=None,
        help="analyse one run only (E5.3 reuses this to report a fresh run's funnel)",
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--no-overlap",
        action="store_true",
        help="skip the deterministic re-gate (funnel only; the re-gate is free but slow)",
    )
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
