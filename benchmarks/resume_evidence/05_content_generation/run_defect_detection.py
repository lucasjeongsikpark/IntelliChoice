"""E5.2 - run every detector over the labeled defect corpus and score precision/recall/F1.

    # free arm: the deterministic detectors only, no provider, no spend
    uv run python benchmarks/resume_evidence/05_content_generation/run_defect_detection.py \
      --arm free

    # paid arm: adds the real blind solver panel and the real embedding dedup check
    eval "$(aws configure export-credentials --profile <profile> --format env)"
    CURRICULUM_BENCH_REAL_BEDROCK=1 CURRICULUM_BEDROCK_PROVIDER=bedrock \
      uv run python .../run_defect_detection.py --arm real --budget-cents 200

    # re-score an existing results file without calling anything
    uv run python .../run_defect_detection.py --score-only

## What is being scored

`build_defect_corpus.py` produces 102 labeled defects over six classes plus 102 unmutated
clean controls drawn from the same bank. This runs the pipeline's own detectors over every
one of them and reports, per class and per detector, TP / FP / FN / TN with precision, recall
and F1 - and, first-class rather than as a footnote, the **false-positive rate on the clean
controls** (D-221: a detector is only as good as the direction it is not being asked to
prove).

Six detector columns. The first four are free and run in every arm:

- `deterministic_gate` - `validate_authored_item`, the whole §5.8.5 suite, exactly as
  `loader._gate` calls it.
- `sympy_rederivation` - `check_sympy_independent_solve` alone, reported separately because
  D-276 is the strongest single result in this subsystem (gate off -> five wrong answer keys
  passed both blind solvers *and* the judge) and it deserves its own row rather than being
  folded into the suite that surrounds it.
- `exact_text_dedup` - the cheap check the pipeline runs first: is this exact rendered
  question already in the reference set. Included because it is what near-duplicate detection
  is a *backstop for*, and a backstop's value is the gap between the two.
- `arithmetic_identity` - `arithmetic_identity`, D-273's "same calculation, different story"
  check. Present in the codebase, deliberately **not wired into the pipeline** (see
  `ai_pipeline` §2b), so this is the first measurement of what wiring it would buy.

Two paid columns:

- `dedup_embedding` - the production near-duplicate check: embed the stem, cosine-compare
  against every reference item **in the same topic**, flag below
  `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD`. Same threshold, same scoping, same embedding
  model as `stem_near_duplicate_exists`. Costs ~0.03 c for the whole corpus.
- `solver_panel` - Solver A + Solver B through the two distinct task slots, verdicts through
  `solver_objections`. Two calls per item; this is the entire cost of the experiment.

And one combined column, `combined_pipeline` = gate OR dedup OR solvers: the three machine
stages of `run_authored_candidate` that this corpus can exercise, unioned the way the pipeline
actually unions them (fail-closed, any stage rejects).

## The accounting rule this file exists to keep (D-230)

A solver call that **fails** is not a catch. `audit_authored_bank.py` shipped one run where it
was: `ItemVerdict.agrees` is false for an objection and for an error alike, so a Solver B that
failed every call scored a perfect negative control. Here, an item whose solver call failed is
excluded from the `solver_panel` and `combined_pipeline` denominators entirely and counted in
its own column, so no metric in the output can be inflated by a broken panel.

The same discipline is extended to two neighbours of a call failure that are not call failures
either: a **budget stop** (the run hit its ceiling) and a **circuit stop** (the gateway's
breaker opened) end the run rather than scoring an item.

## Budget

Hard ceiling, abort rather than truncate silently: before every item the harness prices the
two calls it is about to make with the gateway's own `worst_case_cost_cents` and stops if that
would cross the ceiling. Every completed item is appended to the results JSONL immediately, so
a stopped run keeps everything it paid for and `--resume` continues from there. The gateway's
own `session_budget_cents` is set to the same ceiling as a backstop; if it ever fires first,
the error is classified as a budget stop and not as a call failure.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import pathlib
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.ai_pipeline import (
    _AUTHORED_SOLVER_MAX_TOKENS,
    _SOLVER_SYSTEM_PROMPT,
    NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD,
    _call,
    solver_objections,
)
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef
from intellichoice_curriculum.authored_validation import (
    AuthoredValidationResult,
    arithmetic_identity,
    check_sympy_independent_solve,
    validate_authored_item,
)
from intellichoice_curriculum.pipeline_cli import underlying_model
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import BedrockTask, SolverPayload, SolverResponse

HARNESS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HARNESS_DIR))
from build_defect_corpus import DEFECT_CLASSES, load_corpus  # noqa: E402

FREE_DETECTORS = (
    "deterministic_gate",
    "sympy_rederivation",
    "exact_text_dedup",
    "arithmetic_identity",
)
PAID_DETECTORS = ("dedup_embedding", "solver_panel")
DETECTORS = (*FREE_DETECTORS, *PAID_DETECTORS, "combined_pipeline")

# The three machine stages `run_authored_candidate` runs that this corpus can exercise. The
# judge stage is deliberately absent: its +/-1-tier noise is documented (D-238/D-239) and
# difficulty is not a defect class here.
COMBINED_PARTS = ("deterministic_gate", "dedup_embedding", "solver_panel")

_EMBED_BATCH = 16
# Consecutive item-level solver failures after which the run stops. The gateway's own breaker
# opens at 5 consecutive provider failures, so a run that keeps going past this is producing
# `circuit_open` rows rather than measurements.
_MAX_CONSECUTIVE_FAILURES = 5
# Kept back from the ceiling so the harness's guard, not the gateway's, is what ends the run -
# a gateway budget refusal arrives as an error string and would have to be un-counted again.
_BUDGET_RESERVE_CENTS = 2.0


@dataclass
class ItemVerdicts:
    corpus_id: str
    label: str
    defect_class: str | None
    clean_block: str | None
    severity_tier: str | None
    topic_id: str
    source_item_id: str
    flags: dict[str, bool | None] = field(default_factory=dict)
    gate_failures: list[str] = field(default_factory=list)
    sympy_failures: list[str] = field(default_factory=list)
    nearest_distance: float | None = None
    nearest_reference_id: str | None = None
    identity_collision_with: str | None = None
    exact_match_with: str | None = None
    solver_a: dict | None = None
    solver_b: dict | None = None
    solver_objections: list[str] = field(default_factory=list)
    solver_status: str = "not_run"  # not_run | scored | call_failure | budget_stop | circuit_stop
    solver_error: str | None = None
    solver_cost_cents: float = 0.0

    def as_json(self) -> dict:
        return {
            "record": "item",
            "corpus_id": self.corpus_id,
            "label": self.label,
            "defect_class": self.defect_class,
            "clean_block": self.clean_block,
            "severity_tier": self.severity_tier,
            "topic_id": self.topic_id,
            "source_item_id": self.source_item_id,
            "flags": self.flags,
            "gate_failures": self.gate_failures,
            "sympy_failures": self.sympy_failures,
            "nearest_distance": self.nearest_distance,
            "nearest_reference_id": self.nearest_reference_id,
            "identity_collision_with": self.identity_collision_with,
            "exact_match_with": self.exact_match_with,
            "solver_a": self.solver_a,
            "solver_b": self.solver_b,
            "solver_objections": self.solver_objections,
            "solver_status": self.solver_status,
            "solver_error": self.solver_error,
            "solver_cost_cents": round(self.solver_cost_cents, 5),
        }


# --- free detectors -------------------------------------------------------------------------


def _gate_result(item: AuthoredTemplateDef, answer_form: str) -> AuthoredValidationResult:
    return validate_authored_item(
        item.difficulty_label,
        item.to_generated_item(),
        figure=item.figure_spec,
        figure_reading=item.figure_reading,
        answer_form=answer_form,
    )


def _sympy_only(item: AuthoredTemplateDef, answer_form: str) -> AuthoredValidationResult:
    """`check_sympy_independent_solve` on its own, so the D-276 column is that check and
    nothing else - not "the gate, mostly because of SymPy".
    """
    result = AuthoredValidationResult()
    if item.figure_reading is None:
        check_sympy_independent_solve(item.to_generated_item(), result, answer_form)
    return result


def run_free_detectors(records: list[dict]) -> dict[str, ItemVerdicts]:
    """Everything that costs nothing, over the whole corpus.

    The reference set for both dedup columns is the **clean controls**, scoped to the same
    topic, because that is what `stem_near_duplicate_exists` compares a candidate against: the
    already-approved items of the candidate's own topic. A candidate is never compared with
    itself.
    """
    items = {r["corpus_id"]: AuthoredTemplateDef.model_validate(r["item"]) for r in records}
    reference = [r for r in records if r["label"] == "clean"]

    by_topic_text: dict[str, dict[str, str]] = defaultdict(dict)
    by_topic_identity: dict[str, dict[str, tuple]] = defaultdict(dict)
    for record in reference:
        item = items[record["corpus_id"]]
        by_topic_text[item.topic_id][record["corpus_id"]] = item.rendered_for_model()
        identity = arithmetic_identity(item.answer_expression or "")
        if identity is not None:
            by_topic_identity[item.topic_id][record["corpus_id"]] = identity

    verdicts: dict[str, ItemVerdicts] = {}
    for record in records:
        corpus_id = record["corpus_id"]
        item = items[corpus_id]
        answer_form = record["answer_form"]
        gate = _gate_result(item, answer_form)
        sympy = _sympy_only(item, answer_form)

        rendered = item.rendered_for_model()
        exact_match = next(
            (
                other
                for other, text in by_topic_text[item.topic_id].items()
                if other != corpus_id and text == rendered
            ),
            None,
        )
        identity = arithmetic_identity(item.answer_expression or "")
        identity_match = None
        if identity is not None:
            identity_match = next(
                (
                    other
                    for other, other_identity in by_topic_identity[item.topic_id].items()
                    if other != corpus_id and other_identity == identity
                ),
                None,
            )

        verdicts[corpus_id] = ItemVerdicts(
            corpus_id=corpus_id,
            label=record["label"],
            defect_class=record["defect_class"],
            clean_block=record["clean_block"],
            severity_tier=record.get("mutation", {}).get("severity_tier"),
            topic_id=item.topic_id,
            source_item_id=record["source_item_id"],
            flags={
                "deterministic_gate": not gate.passed,
                "sympy_rederivation": not sympy.passed,
                "exact_text_dedup": exact_match is not None,
                "arithmetic_identity": identity_match is not None,
                "dedup_embedding": None,
                "solver_panel": None,
                "combined_pipeline": None,
            },
            gate_failures=gate.failures,
            sympy_failures=sympy.failures,
            exact_match_with=exact_match,
            identity_collision_with=identity_match,
        )
    return verdicts


# --- paid detectors ---------------------------------------------------------------------------


def build_gateway(*, arm: str, budget_cents: float) -> ResilientBedrockGateway:
    settings = get_pipeline_settings()
    if arm == "real":
        from intellichoice_adapters.bedrock.bedrock_runtime_provider import (
            AnthropicBedrockProvider,
        )
        from intellichoice_adapters.bedrock.titan_embedding_provider import (
            TitanEmbeddingProvider,
        )

        provider: Any = AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        embedding_provider: Any = TitanEmbeddingProvider(aws_region=settings.bedrock_aws_region)
    else:
        mock = MockBedrockProvider()
        provider = mock
        embedding_provider = mock
    return ResilientBedrockGateway(
        provider=provider,
        embedding_provider=embedding_provider,
        model_registry={
            BedrockTask.QUESTION_GENERATION: settings.bedrock_generation_model_id,
            BedrockTask.QUESTION_REVIEW: settings.bedrock_review_model_id,
            BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id,
        },
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=budget_cents,
    )


_PROBE_PAYLOAD = SolverPayload(
    rendered_question="What is 1 + 1?",
    option_a="1",
    option_b="2",
    option_c="3",
    option_d="4",
)
_PROBE_SYSTEM_PROMPT = (
    "Invocability probe. Answer with the shortest possible reasoning and the correct option."
)


async def probe_solver_slot(gateway, task: BedrockTask, spend: float) -> tuple[bool, str, float]:
    """D-273's rule, applied before this run spends anything: **AVAILABLE is not invocable.**

    The recorded 2026-08-11 invocability stratum expired by its own terms, and a model can be
    listed, enabled, and still return `AccessDenied` for this principal. Both slots are probed,
    not one - Solver A and Solver B are different models and either can be the one that is
    unreachable today.

    This is the smallest *legal* call, not literally one token: the gateway only speaks
    structured output, so a probe has to be a schema-valid `SolverResponse`. Payload is a
    one-line arithmetic question and the ceiling is 200 output tokens, which prices at a small
    fraction of a cent on either model.
    """
    response, cost, error = await _call(
        gateway,
        task=task,
        system_prompt=_PROBE_SYSTEM_PROMPT,
        payload=_PROBE_PAYLOAD,
        response_model=SolverResponse,
        session_spend_cents=spend,
        max_output_tokens=200,
    )
    if error is not None or not isinstance(response, SolverResponse):
        return False, error or "no response", cost
    return True, f"selected {response.selected_option!r}", cost


async def embed_corpus(
    gateway, records: list[dict], verdicts: dict[str, ItemVerdicts], spend: float
) -> tuple[float, str | None]:
    """Embed every corpus stem once and score the near-duplicate column in memory.

    `item.stem` - not `rendered_for_model()` - because that is the text
    `ai_pipeline` passes to `create_embedding` before calling `stem_near_duplicate_exists`.
    Production compares a candidate against the approved items **of its own topic**, and so
    does this; a cross-topic comparison would invent false positives the pipeline cannot have.
    """
    items = {r["corpus_id"]: AuthoredTemplateDef.model_validate(r["item"]) for r in records}
    order = [r["corpus_id"] for r in records]
    vectors: dict[str, list[float]] = {}
    for start in range(0, len(order), _EMBED_BATCH):
        chunk = order[start : start + _EMBED_BATCH]
        try:
            result = await gateway.create_embedding(
                texts=[items[cid].stem for cid in chunk], session_spend_cents=spend
            )
        except Exception as exc:  # noqa: BLE001 - any failure here means "no dedup column"
            return spend, f"{type(exc).__name__}: {exc}"
        spend += result.cost_cents
        for cid, vector in zip(chunk, result.vectors, strict=True):
            vectors[cid] = vector

    reference_by_topic: dict[str, list[str]] = defaultdict(list)
    for record in records:
        if record["label"] == "clean":
            reference_by_topic[items[record["corpus_id"]].topic_id].append(record["corpus_id"])

    for corpus_id in order:
        topic = items[corpus_id].topic_id
        nearest_id: str | None = None
        nearest = None
        for other in reference_by_topic[topic]:
            if other == corpus_id:
                continue
            distance = cosine_distance(vectors[corpus_id], vectors[other])
            if nearest is None or distance < nearest:
                nearest, nearest_id = distance, other
        verdict = verdicts[corpus_id]
        verdict.nearest_distance = None if nearest is None else round(nearest, 6)
        verdict.nearest_reference_id = nearest_id
        verdict.flags["dedup_embedding"] = (
            nearest is not None and nearest < NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD
        )
    return spend, None


def cosine_distance(a: list[float], b: list[float]) -> float:
    """pgvector's `cosine_distance`: 1 - cosine similarity, 0 = identical.

    Written out rather than assumed from normalized vectors, so the number this harness
    compares against `NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD` is the same quantity the SQL
    operator produces.
    """
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


def _classify_error(error: str) -> str:
    lowered = error.lower()
    if "budget" in lowered:
        return "budget_stop"
    if "circuit" in lowered:
        return "circuit_stop"
    return "call_failure"


async def run_solver_panel(
    gateway, item: AuthoredTemplateDef, verdict: ItemVerdicts, spend: float
) -> float:
    """Two blind solver calls, scored through the pipeline's own `solver_objections`.

    The payload is `SolverPayload(rendered_for_model(), option_a..d)` - built the way
    `ai_pipeline` builds it, including D-196's `rendered_for_model()` rather than the bare
    stem, because a payload that differs from production's measures a different question.
    """
    payload = SolverPayload(
        rendered_question=item.rendered_for_model(),
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
    )
    responses: list[SolverResponse] = []
    for name, task in (("A", BedrockTask.QUESTION_GENERATION), ("B", BedrockTask.QUESTION_REVIEW)):
        response, cost, error = await _call(
            gateway,
            task=task,
            system_prompt=_SOLVER_SYSTEM_PROMPT,
            payload=payload,
            response_model=SolverResponse,
            session_spend_cents=spend,
            max_output_tokens=_AUTHORED_SOLVER_MAX_TOKENS,
        )
        spend += cost
        verdict.solver_cost_cents += cost
        if error is not None or not isinstance(response, SolverResponse):
            verdict.solver_status = _classify_error(error or "")
            verdict.solver_error = f"solver {name}: {error}"
            verdict.flags["solver_panel"] = None
            return spend
        responses.append(response)

    verdict.solver_a = responses[0].model_dump()
    verdict.solver_b = responses[1].model_dump()
    verdict.solver_objections = solver_objections(
        responses[0], responses[1], declared=item.correct_option
    )
    verdict.solver_status = "scored"
    verdict.flags["solver_panel"] = bool(verdict.solver_objections)
    return spend


def finalise_combined(verdict: ItemVerdicts) -> None:
    """`combined_pipeline` is None whenever any of its parts is None.

    A union that treated an unmeasured part as "did not flag" would report the pipeline as
    weaker than it is on a free arm and, worse, would let a run whose solver calls all failed
    still publish a combined recall.
    """
    parts = [verdict.flags.get(name) for name in COMBINED_PARTS]
    verdict.flags["combined_pipeline"] = None if any(p is None for p in parts) else any(parts)


# --- scoring ----------------------------------------------------------------------------------


@dataclass
class Cell:
    detector: str
    scope: str
    n_defects: int = 0
    n_clean: int = 0
    tp: int = 0
    fn: int = 0
    fp: int = 0
    tn: int = 0
    unscored_defects: int = 0
    unscored_clean: int = 0

    @property
    def precision(self) -> float | None:
        return None if (self.tp + self.fp) == 0 else self.tp / (self.tp + self.fp)

    @property
    def recall(self) -> float | None:
        return None if (self.tp + self.fn) == 0 else self.tp / (self.tp + self.fn)

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)

    @property
    def clean_fp_rate(self) -> float | None:
        scored = self.fp + self.tn
        return None if scored == 0 else self.fp / scored

    def as_row(self) -> dict:
        def pct(value: float | None) -> str:
            return "" if value is None else f"{value:.4f}"

        return {
            "detector": self.detector,
            "scope": self.scope,
            "n_defects": self.n_defects,
            "n_clean": self.n_clean,
            "tp": self.tp,
            "fn": self.fn,
            "fp": self.fp,
            "tn": self.tn,
            "unscored_defects": self.unscored_defects,
            "unscored_clean": self.unscored_clean,
            "recall_n_over_N": f"{self.tp}/{self.tp + self.fn}",
            "clean_fp_n_over_N": f"{self.fp}/{self.fp + self.tn}",
            "precision": pct(self.precision),
            "recall": pct(self.recall),
            "f1": pct(self.f1),
            "clean_fp_rate": pct(self.clean_fp_rate),
        }


def score(verdicts: list[ItemVerdicts]) -> list[Cell]:
    """Per detector: one cell per defect class, one per near-duplicate severity, one pooled.

    **Precision needs a matched negative set, and this is where it comes from.** A per-class
    precision computed against the whole clean set would give six classes the same
    denominator; a per-class precision with no clean items at all is undefined. The corpus
    therefore blocks the 102 controls into six groups of 17, one per class, and a class's false
    positives are its own block's. The pooled row uses all 102 against all 102 and is the
    number to quote when one number is wanted.

    An item the detector could not judge (`flag is None` - a failed solver call, a detector
    that did not run in this arm) is counted in `unscored_*` and appears in **no** numerator or
    denominator. That is D-230, mechanised: a panel that fails everywhere scores nothing rather
    than scoring perfectly.
    """
    cells: list[Cell] = []
    defects = [v for v in verdicts if v.label == "defect"]
    clean = [v for v in verdicts if v.label == "clean"]

    for detector in DETECTORS:
        for defect_class in DEFECT_CLASSES:
            cell = Cell(detector=detector, scope=defect_class)
            _fill(cell, [v for v in defects if v.defect_class == defect_class], is_defect=True)
            _fill(cell, [v for v in clean if v.clean_block == defect_class], is_defect=False)
            cells.append(cell)

        tiers = sorted({v.severity_tier for v in defects if v.severity_tier})
        for tier in tiers:
            cell = Cell(detector=detector, scope=f"near_duplicate:{tier}")
            _fill(cell, [v for v in defects if v.severity_tier == tier], is_defect=True)
            _fill(cell, [v for v in clean if v.clean_block == "near_duplicate"], is_defect=False)
            cells.append(cell)

        pooled = Cell(detector=detector, scope="ALL")
        _fill(pooled, defects, is_defect=True)
        _fill(pooled, clean, is_defect=False)
        cells.append(pooled)
    return cells


def _fill(cell: Cell, rows: list[ItemVerdicts], *, is_defect: bool) -> None:
    for row in rows:
        flag = row.flags.get(cell.detector)
        if is_defect:
            cell.n_defects += 1
            if flag is None:
                cell.unscored_defects += 1
            elif flag:
                cell.tp += 1
            else:
                cell.fn += 1
        else:
            cell.n_clean += 1
            if flag is None:
                cell.unscored_clean += 1
            elif flag:
                cell.fp += 1
            else:
                cell.tn += 1


# --- artifacts ----------------------------------------------------------------------------------


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):  # pragma: no cover
        return "unknown"


def write_metrics(path: pathlib.Path, cells: list[Cell]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [cell.as_row() for cell in cells]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_results(path: pathlib.Path) -> tuple[dict, dict[str, dict]]:
    if not path.exists():
        return {}, {}
    header: dict = {}
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("record") == "header":
                header = record
            else:
                rows[record["corpus_id"]] = record
    return header, rows


def verdicts_from_rows(rows: dict[str, dict]) -> list[ItemVerdicts]:
    restored: list[ItemVerdicts] = []
    for row in rows.values():
        verdict = ItemVerdicts(
            corpus_id=row["corpus_id"],
            label=row["label"],
            defect_class=row["defect_class"],
            clean_block=row["clean_block"],
            severity_tier=row.get("severity_tier"),
            topic_id=row["topic_id"],
            source_item_id=row["source_item_id"],
            flags=row["flags"],
            gate_failures=row.get("gate_failures", []),
            sympy_failures=row.get("sympy_failures", []),
            nearest_distance=row.get("nearest_distance"),
            nearest_reference_id=row.get("nearest_reference_id"),
            identity_collision_with=row.get("identity_collision_with"),
            exact_match_with=row.get("exact_match_with"),
            solver_a=row.get("solver_a"),
            solver_b=row.get("solver_b"),
            solver_objections=row.get("solver_objections", []),
            solver_status=row.get("solver_status", "not_run"),
            solver_error=row.get("solver_error"),
            solver_cost_cents=row.get("solver_cost_cents", 0.0),
        )
        restored.append(verdict)
    return restored


def format_metrics(cells: list[Cell]) -> str:
    lines = [
        f"{'detector':<20} {'scope':<34} {'recall':>12} {'clean FP':>12} "
        f"{'prec':>7} {'F1':>7} {'unscored':>9}"
    ]
    for cell in cells:
        if cell.n_defects == 0 and cell.n_clean == 0:
            continue
        precision = "-" if cell.precision is None else f"{cell.precision:.3f}"
        f1 = "-" if cell.f1 is None else f"{cell.f1:.3f}"
        lines.append(
            f"{cell.detector:<20} {cell.scope:<34} "
            f"{cell.tp:>4}/{cell.tp + cell.fn:<7} {cell.fp:>4}/{cell.fp + cell.tn:<7} "
            f"{precision:>7} {f1:>7} "
            f"{cell.unscored_defects + cell.unscored_clean:>9}"
        )
    return "\n".join(lines)


# --- the run ---------------------------------------------------------------------------------


def interleaved(records: list[dict]) -> list[dict]:
    """Round-robin over the six classes and the clean set.

    A run that is stopped by its budget must leave a *balanced* sample behind, not seventeen
    complete `wrong_numeric_answer` rows and nothing else. Deterministic and independent of the
    corpus file's order.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[record["defect_class"] or "clean"].append(record)
    keys = sorted(groups)
    ordered: list[dict] = []
    for index in range(max(len(g) for g in groups.values())):
        for key in keys:
            if index < len(groups[key]):
                ordered.append(groups[key][index])
    return ordered


async def run(args: argparse.Namespace) -> int:
    corpus_path = pathlib.Path(args.corpus)
    results_path = pathlib.Path(args.results)
    corpus_header, records = load_corpus(corpus_path)
    if not records:
        raise SystemExit(f"no corpus items in {corpus_path}")

    if args.score_only:
        _, rows = load_results(results_path)
        if not rows:
            raise SystemExit(f"no results to score in {results_path}")
        verdicts = verdicts_from_rows(rows)
        cells = score(verdicts)
        write_metrics(pathlib.Path(args.metrics), cells)
        print(format_metrics(cells))
        print(f"\nmetrics written to {args.metrics}")
        return 0

    settings = get_pipeline_settings()
    if args.arm == "real":
        if os.environ.get("CURRICULUM_BENCH_REAL_BEDROCK") != "1":
            raise SystemExit(
                "--arm real needs CURRICULUM_BENCH_REAL_BEDROCK=1 - this arm spends money and "
                "must never start by accident (or under pytest)"
            )
        if settings.bedrock_provider != "bedrock":
            raise SystemExit(
                f"--arm real needs CURRICULUM_BEDROCK_PROVIDER=bedrock, got "
                f"{settings.bedrock_provider!r} - a 'real' run against the mock would report the "
                f"mock's constant answer as a quality result (AUD-C-05)"
            )
        if underlying_model(settings.bedrock_generation_model_id) == underlying_model(
            settings.bedrock_review_model_id
        ):
            raise SystemExit(
                "REFUSED: Solver A and Solver B resolve to the same model, so their agreement "
                "would be one opinion counted twice"
            )

    verdicts = run_free_detectors(records)
    print(f"free detectors: {len(verdicts)} items scored, 0.00 cents")

    spend = 0.0
    probes: list[dict] = []
    embedding_error: str | None = None
    stopped: str | None = None
    consecutive_failures = 0

    if args.arm == "free":
        for verdict in verdicts.values():
            finalise_combined(verdict)
    else:
        gateway = build_gateway(arm=args.arm, budget_cents=args.budget_cents)
        for name, task in (
            ("solver_a", BedrockTask.QUESTION_GENERATION),
            ("solver_b", BedrockTask.QUESTION_REVIEW),
        ):
            ok, detail, cost = await probe_solver_slot(gateway, task, spend)
            spend += cost
            model_id = (
                settings.bedrock_generation_model_id
                if name == "solver_a"
                else settings.bedrock_review_model_id
            )
            probes.append({"slot": name, "model_id": model_id, "ok": ok, "detail": detail})
            print(f"invocability probe {name} ({model_id}): {'OK' if ok else 'FAILED'} - {detail}")
            if not ok:
                raise SystemExit(
                    f"{name} is not invocable on this account today; nothing further was called. "
                    f"D-273: availability is a dated measurement, not a property."
                )

        spend, embedding_error = await embed_corpus(gateway, records, verdicts, spend)
        if embedding_error is not None:
            print(f"embedding stage FAILED - dedup column unscored: {embedding_error}")
        print(f"after probes + embeddings: {spend:.3f} cents")

        items = {r["corpus_id"]: AuthoredTemplateDef.model_validate(r["item"]) for r in records}
        _, existing = load_results(results_path)
        todo = [
            r for r in interleaved(records) if r["corpus_id"] not in existing or not args.resume
        ]
        if args.limit:
            todo = todo[: args.limit]

        results_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if (args.resume and results_path.exists()) else "w"
        with results_path.open(mode, encoding="utf-8") as handle:
            if mode == "w":
                handle.write(json.dumps(_header(args, corpus_header, settings, probes)) + "\n")
                handle.flush()
            for index, record in enumerate(todo, start=1):
                corpus_id = record["corpus_id"]
                item = items[corpus_id]
                reserve = gateway.worst_case_cost_cents(
                    BedrockTask.QUESTION_GENERATION, _AUTHORED_SOLVER_MAX_TOKENS
                ) + gateway.worst_case_cost_cents(
                    BedrockTask.QUESTION_REVIEW, _AUTHORED_SOLVER_MAX_TOKENS
                )
                if spend + reserve > args.budget_cents - _BUDGET_RESERVE_CENTS:
                    stopped = (
                        f"budget: stopped before item {index}/{len(todo)} - spent "
                        f"{spend:.2f} c, next item's worst case {reserve:.2f} c, ceiling "
                        f"{args.budget_cents:.0f} c"
                    )
                    print(f"\n{stopped}")
                    break
                verdict = verdicts[corpus_id]
                spend = await run_solver_panel(gateway, item, verdict, spend)
                if verdict.solver_status in ("budget_stop", "circuit_stop"):
                    stopped = f"{verdict.solver_status}: {verdict.solver_error}"
                    print(f"\n{stopped}")
                    break
                if verdict.solver_status == "call_failure":
                    consecutive_failures += 1
                else:
                    consecutive_failures = 0
                finalise_combined(verdict)
                handle.write(json.dumps(verdict.as_json()) + "\n")
                handle.flush()
                mark = {
                    "scored": "!" if verdict.flags["solver_panel"] else ".",
                    "call_failure": "E",
                }.get(verdict.solver_status, "?")
                print(mark, end="", flush=True)
                if index % 60 == 0:
                    print(f"  {index}/{len(todo)}  {spend:.1f}c", flush=True)
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    stopped = (
                        f"{consecutive_failures} consecutive solver call failures - the gateway's "
                        f"breaker is at or near its threshold; further rows would be circuit "
                        f"noise, not measurements"
                    )
                    print(f"\n{stopped}")
                    break
        print()

    if args.arm == "free":
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with results_path.open("w", encoding="utf-8") as handle:
            handle.write(json.dumps(_header(args, corpus_header, settings, probes)) + "\n")
            for verdict in verdicts.values():
                handle.write(json.dumps(verdict.as_json()) + "\n")

    _, rows = load_results(results_path)
    scored = verdicts_from_rows(rows)
    cells = score(scored)
    write_metrics(pathlib.Path(args.metrics), cells)

    print(format_metrics(cells))
    statuses = defaultdict(int)
    for verdict in scored:
        statuses[verdict.solver_status] += 1
    print(f"\nsolver statuses: {dict(sorted(statuses.items()))}")
    print(f"items with a completed row: {len(scored)}/{len(records)}")
    print(f"TOTAL SPEND: {spend:.2f} cents (ceiling {args.budget_cents:.0f})")
    if stopped:
        print(f"RUN STOPPED EARLY - {stopped}")
    if embedding_error:
        print(f"dedup column unscored - {embedding_error}")
    print(f"results: {results_path}\nmetrics: {args.metrics}")
    return 0


def _header(args, corpus_header: dict, settings, probes: list[dict]) -> dict:
    return {
        "record": "header",
        "experiment": "E5.2",
        "artifact": "detection_results",
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": git_sha(),
        "arm": args.arm,
        "environment": {
            "free": "local, deterministic detectors only - no provider",
            "mock": "mock-model eval - MockBedrockProvider; NOT a quality result (AUD-C-05)",
            "real": "real-model evaluation (solver panel) + deterministic gate, local",
        }[args.arm],
        "corpus_git_sha": corpus_header.get("git_sha"),
        "corpus_seed": corpus_header.get("corpus_seed"),
        "budget_cents": args.budget_cents,
        "bedrock_provider": settings.bedrock_provider,
        "solver_a_model_id": settings.bedrock_generation_model_id,
        "solver_b_model_id": settings.bedrock_review_model_id,
        "embedding_model_id": settings.bedrock_embedding_model_id,
        "solver_max_output_tokens": _AUTHORED_SOLVER_MAX_TOKENS,
        "near_duplicate_cosine_threshold": NEAR_DUPLICATE_COSINE_DISTANCE_THRESHOLD,
        "invocability_probes": probes,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    base = "docs/resume_evidence/05_content_generation"
    parser.add_argument("--corpus", default=f"{base}/defect_corpus.jsonl")
    parser.add_argument("--results", default=f"{base}/detection_results.jsonl")
    parser.add_argument("--metrics", default=f"{base}/detection_metrics.csv")
    parser.add_argument(
        "--arm",
        choices=("free", "mock", "real"),
        default="free",
        help="free: deterministic detectors only. mock: wiring smoke test, never a quality "
        "result. real: the paid solver panel and real embeddings",
    )
    parser.add_argument(
        "--budget-cents",
        type=float,
        default=200.0,
        help="hard ceiling for this run; the harness stops before the call that would cross it",
    )
    parser.add_argument("--limit", type=int, default=0, help="score at most N items (calibration)")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="append to an existing results file, skipping its rows",
    )
    parser.add_argument(
        "--score-only", action="store_true", help="re-score an existing results file, call nothing"
    )
    return parser


def main() -> int:
    return asyncio.run(run(build_parser().parse_args()))


if __name__ == "__main__":
    sys.exit(main())
