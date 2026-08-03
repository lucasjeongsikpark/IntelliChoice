"""Measure why generated parent reports fail `numeric_grounding.is_grounded` (D-162 §4).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    uv run python scripts/measure_report_grounding.py --runs 5 --payload staging

**Why this needs the real model, and why no test replaces it.**
`MockBedrockProvider._report_interpretation_json` builds its text out of the payload's own
fields, so its output round-trips `is_grounded` *by construction* - the entire local suite
is structurally incapable of observing a grounding failure. Only a real generation can, and
staging discards the offending text (the fallback replaces it before the row is persisted),
so the text has to be produced here to be read at all.

This script calls Bedrock and spends real money. It is bounded three ways: `--runs`
(default 5), the gateway's own `session_budget_cents` ceiling, and the same
`_MAX_OUTPUT_TOKENS` the service uses. At the deployed model's rate a run costs about
0.4 cents, so the default is roughly 2 cents per payload.

It is deliberately read-only with respect to everything else: no database, no report row,
no cost-reservation ledger. It exercises exactly the prompt -> model -> `is_grounded` seam
that fails, and nothing else.
"""

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_shared.bedrock import (
    BedrockTask,
    ReportInterpretationPayload,
    ReportInterpretationResponse,
)
from intellichoice_shared.mastery_policy import WEAK_SKILL_THRESHOLD
from intellichoice_shared.numeric_grounding import extract_numbers
from learning_api.services.dashboard import MASTERY_WINDOW_LABEL
from learning_api.services.report import (
    _MAX_OUTPUT_TOKENS,
    _SYSTEM_PROMPT,
    _WEAK_SKILL_WINDOW_LABEL,
)

# Imported from the service, not retyped: a retyped label would measure a prompt staging
# never saw. `_WEAK_SKILL_WINDOW_LABEL` is a template, formatted here exactly as
# `build_report_facts` formats it.
_MASTERY_WINDOW_LABEL = MASTERY_WINDOW_LABEL
_WEAK_SKILL_WINDOW_LABEL_TEXT = _WEAK_SKILL_WINDOW_LABEL.format(threshold=WEAK_SKILL_THRESHOLD)

# The deployed staging values (terraform.tfvars), not the config defaults - the point is to
# reproduce what staging did, so a mismatch here would measure a different model.
_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_AWS_REGION = "us-east-1"

# A hard ceiling on this script's own spend, independent of `--runs`. The gateway refuses
# the call that would cross it rather than truncating mid-run.
_SCRIPT_BUDGET_CENTS = 25.0


# --- the payloads under measurement -------------------------------------------------
#
# Two arms, because the open question is *whether the polluted aggregates matter at all*.
# D-162 §4's suspicion is that staging's load-test-inflated counts invite thousands
# separators; if the small, ordinary control fails too, the cause is something the data
# shape has nothing to do with, and the suspicion is a red herring.


def _staging_payload() -> ReportInterpretationPayload:
    """Staging's shape: load-test-polluted aggregates, four-digit counts."""
    return ReportInterpretationPayload(
        audience="parent",
        grade="7",
        date_range_label="2026-07-01 to 2026-07-31",
        mastery_window_label=_MASTERY_WINDOW_LABEL,
        weak_skill_window_label=_WEAK_SKILL_WINDOW_LABEL_TEXT,
        pre_raw_score=4.0,
        post_raw_score=7.0,
        raw_gain=3.0,
        overall_accuracy=0.6666666666666666,
        mastery_by_skill={
            "adding fractions": 0.8333333333333334,
            "subtracting fractions": 0.4166666666666667,
            "multiplying decimals": 0.625,
        },
        weak_skill_names=["subtracting fractions", "multiplying decimals"],
        hint_count=1284,
        solution_count=317,
        video_count=42,
        independent_correct_rate=0.7291666666666666,
        attempts_count=7371,
        time_spent_minutes=4.6,
        tutor_review_flagged=True,
        relevant_learning_facts=[
            "Works carefully but slowly on multi-step problems.",
            "Asks for a hint before attempting subtraction with unlike denominators.",
        ],
    )


def _control_payload() -> ReportInterpretationPayload:
    """An ordinary single-student month: small counts, no number a thousands separator
    could reach. If this arm fails too, the polluted-aggregate theory is refuted.
    """
    return ReportInterpretationPayload(
        audience="parent",
        grade="7",
        date_range_label="2026-07-01 to 2026-07-31",
        mastery_window_label=_MASTERY_WINDOW_LABEL,
        weak_skill_window_label=_WEAK_SKILL_WINDOW_LABEL_TEXT,
        pre_raw_score=4.0,
        post_raw_score=7.0,
        raw_gain=3.0,
        overall_accuracy=0.6666666666666666,
        mastery_by_skill={
            "adding fractions": 0.8333333333333334,
            "subtracting fractions": 0.4166666666666667,
            "multiplying decimals": 0.625,
        },
        weak_skill_names=["subtracting fractions", "multiplying decimals"],
        hint_count=6,
        solution_count=2,
        video_count=1,
        independent_correct_rate=0.75,
        attempts_count=26,
        time_spent_minutes=18.5,
        tutor_review_flagged=True,
        relevant_learning_facts=[
            "Works carefully but slowly on multi-step problems.",
            "Asks for a hint before attempting subtraction with unlike denominators.",
        ],
    )


def _integers_payload() -> ReportInterpretationPayload:
    """Third arm, isolating one variable: the control's numbers with every repeating
    decimal replaced by a clean value. Separates "the model reformats percentages" from
    "the model rounds a long decimal", which the other two arms confound.
    """
    return ReportInterpretationPayload(
        audience="parent",
        grade="7",
        date_range_label="2026-07-01 to 2026-07-31",
        mastery_window_label=_MASTERY_WINDOW_LABEL,
        weak_skill_window_label=_WEAK_SKILL_WINDOW_LABEL_TEXT,
        pre_raw_score=4.0,
        post_raw_score=7.0,
        raw_gain=3.0,
        overall_accuracy=0.75,
        mastery_by_skill={
            "adding fractions": 0.8,
            "subtracting fractions": 0.4,
            "multiplying decimals": 0.6,
        },
        weak_skill_names=["subtracting fractions", "multiplying decimals"],
        hint_count=6,
        solution_count=2,
        video_count=1,
        independent_correct_rate=0.75,
        attempts_count=26,
        time_spent_minutes=18.5,
        tutor_review_flagged=True,
        relevant_learning_facts=[
            "Works carefully but slowly on multi-step problems.",
            "Asks for a hint before attempting subtraction with unlike denominators.",
        ],
    )


# --- diagnosis ----------------------------------------------------------------------

_GROUPED_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")


def _evidence_numbers(evidence: dict) -> list[float]:
    from intellichoice_shared.numeric_grounding import _collect_evidence_numbers

    return _collect_evidence_numbers(evidence)


def _evidence_strings(evidence: object) -> list[str]:
    out: list[str] = []
    if isinstance(evidence, str):
        out.append(evidence)
    elif isinstance(evidence, dict):
        for item in evidence.values():
            out.extend(_evidence_strings(item))
    elif isinstance(evidence, (list, tuple)):
        for item in evidence:
            out.extend(_evidence_strings(item))
    return out


def _matches(extracted: float, value: float) -> bool:
    from intellichoice_shared.numeric_grounding import _matches as real_matches

    return real_matches(extracted, value)


@dataclass(frozen=True)
class Unmatched:
    number: float
    cause: str
    detail: str


def _classify(number: float, text: str, evidence: dict) -> Unmatched:
    """Name *why* a number failed, so the fix targets a measured cause rather than a
    guessed one. Ordered most-specific first; `unexplained` is the honest answer when no
    hypothesis fits, and is the only class that would justify calling the model wrong.
    """
    numbers = _evidence_numbers(evidence)
    strings = _evidence_strings(evidence)

    # (a) thousands separator: "7,371" tokenizes as 7 and 371.
    for grouped in _GROUPED_NUMBER_RE.findall(text):
        joined = float(grouped.replace(",", ""))
        parts = [float(p) for p in grouped.replace(".", ",").split(",") if p]
        if number in parts and any(_matches(joined, value) for value in numbers):
            return Unmatched(number, "thousands_separator", f"fragment of {grouped!r} = {joined}")

    # (b) percent scaling: the model wrote 67 for an evidence value of 0.6666. Report the
    # *closest* proportion, not the first one that matches - `is_grounded`'s
    # nearest-integer rule makes every value in (0.5, 1.5) collide, so a first-match
    # attribution names an arbitrary field and misreads as a wilder error than it is.
    proportions = [value for value in numbers if 0.0 <= value <= 1.0]
    if proportions:
        closest = min(proportions, key=lambda value: abs(number - value * 100.0))
        if abs(number - closest * 100.0) <= 0.5:
            return Unmatched(
                number, "percent_scaling", f"{number:g}% == evidence {closest:.4g} rendered"
            )

    # (c)/(d) the number is present in an evidence *string* - a window label or the date
    # range - which `_collect_evidence_numbers` never looks inside.
    rendered = f"{number:g}"
    for string in strings:
        if rendered in string:
            return Unmatched(number, "evidence_string", f"appears in {string[:70]!r}")

    # (e) a count the model derived from a list it was given (e.g. "2 skills").
    counts = {
        "weak_skill_names": len(evidence.get("weak_skill_names") or []),
        "mastery_by_skill": len(evidence.get("mastery_by_skill") or {}),
        "relevant_learning_facts": len(evidence.get("relevant_learning_facts") or []),
    }
    for field, count in counts.items():
        if count and _matches(number, float(count)):
            return Unmatched(number, "derived_count", f"len({field}) == {count}")

    return Unmatched(number, "unexplained", "no evidence value, scaling, or label matches")


@dataclass
class RunResult:
    grounded: bool
    cost_cents: float
    repaired: bool
    interpretation: str
    recommendations: str
    unmatched: list[Unmatched]


async def _one_run(gateway, payload: ReportInterpretationPayload, spent: float) -> RunResult:
    evidence = payload.model_dump()
    result = await gateway.generate_structured(
        task=BedrockTask.PARENT_REPORT,
        system_prompt=_SYSTEM_PROMPT,
        payload=payload,
        response_model=ReportInterpretationResponse,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=spent,
    )
    numbers = _evidence_numbers(evidence)
    unmatched: list[Unmatched] = []
    for text in (result.value.interpretation_text, result.value.recommendations_text):
        for extracted in extract_numbers(text):
            if not any(_matches(extracted, value) for value in numbers):
                unmatched.append(_classify(extracted, text, evidence))
    return RunResult(
        grounded=not unmatched,
        cost_cents=result.cost_cents,
        repaired=result.repaired,
        interpretation=result.value.interpretation_text,
        recommendations=result.value.recommendations_text,
        unmatched=unmatched,
    )


_PAYLOADS = {
    "staging": _staging_payload,
    "control": _control_payload,
    "integers": _integers_payload,
}


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5, help="generations per payload")
    parser.add_argument(
        "--payload",
        choices=[*_PAYLOADS, "all"],
        default="all",
        help="which arm to measure",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    gateway = ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=_AWS_REGION),
        model_registry={BedrockTask.PARENT_REPORT: _MODEL_ID},
        call_timeout_s=30.0,
        max_retries=2,
        circuit_failure_threshold=5,
        circuit_cooldown_s=30.0,
        session_budget_cents=_SCRIPT_BUDGET_CENTS,
    )

    names = list(_PAYLOADS) if args.payload == "all" else [args.payload]
    spent = 0.0
    summary: dict[str, dict] = {}

    for name in names:
        payload = _PAYLOADS[name]()
        runs: list[RunResult] = []
        print(f"\n{'=' * 78}\n{name.upper()} - {args.runs} generations\n{'=' * 78}")
        for index in range(args.runs):
            run = await _one_run(gateway, payload, spent)
            spent += run.cost_cents
            runs.append(run)
            verdict = "GROUNDED" if run.grounded else "UNGROUNDED"
            print(f"\n--- run {index + 1}: {verdict} ({run.cost_cents:.4f}c) ---")
            print(f"  interpretation : {run.interpretation}")
            print(f"  recommendations: {run.recommendations}")
            for item in run.unmatched:
                print(f"  ! {item.number:<10g} {item.cause:<20} {item.detail}")

        causes: dict[str, int] = {}
        for run in runs:
            for item in run.unmatched:
                causes[item.cause] = causes.get(item.cause, 0) + 1
        ungrounded = sum(1 for run in runs if not run.grounded)
        summary[name] = {
            "runs": len(runs),
            "ungrounded": ungrounded,
            "causes": causes,
            "cost_cents": round(sum(run.cost_cents for run in runs), 4),
        }
        print(f"\n  => {ungrounded}/{len(runs)} ungrounded; causes: {causes or 'none'}")

    print(f"\n{'=' * 78}\nTOTAL SPEND: {spent:.4f} cents\n{'=' * 78}")
    for name, stats in summary.items():
        print(f"  {name:<10} {stats['ungrounded']}/{stats['runs']} ungrounded  {stats['causes']}")
    if args.json:
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
