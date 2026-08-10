"""Try to disqualify the D-251 hint & solution review instrument (D-254).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    CURRICULUM_BEDROCK_PROVIDER=bedrock CURRICULUM_BEDROCK_AWS_REGION=us-east-1 \
    CURRICULUM_BEDROCK_JUDGE_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
    uv run --package intellichoice-curriculum python scripts/measure_hint_solution_review.py \
      --run-budget-cents 150

`--dry-run` prints the exact population and call count without building a provider, and the
whole script runs end to end for free under `CURRICULUM_BEDROCK_PROVIDER=mock` (D-238's
precedent: a paid instrument nobody can exercise for free gets exercised rarely and wrongly).

**This is not a correctness measurement and cannot be one.** There is no golden label set here
by explicit decision - a mutation corpus and a human-labelled benchmark were both rejected
(D-251). Each check below is an attempt to *disqualify* the instrument. Surviving them means
"not yet falsified", which is why HINT_SOLUTION_REVIEW.md's check 3 - sampling `PASS` in
production - runs permanently rather than as a gate. False acceptance is invisible to both
checks in this file, and no result printed here should be read as evidence against it.

**Check 1 - reproducibility.** 8 items x 4 readings. A *per-item* claim ("does this item's
verdict flip"), so repetition is the design: D-237 measured this project's judge answering 6 and
13 out of 16 on identical inputs, and never n=2 for a per-item claim.

**Check 2 - approved-bank false rejection.** 50 items x 1 reading. An *aggregate rate* claim
("how often does it block content a human approved"), so breadth is the design and n=1 per item
is right - the sample size lives across items, not within them.

**Check 1's items are a subset of check 2's, deliberately.** Check 2 estimates a rate from
single readings, which is only interpretable if per-item verdicts are stable. Check 1 is check
2's error bar, not a separate experiment.

**The population is the shipped bank** - hand-authored, passed the deterministic §5.8.5 gate,
human-reviewed, live on staging. That is what makes a block load-bearing: D-249 disqualified
`hint_quality_score <= 3` because it fired on 46% of exactly this content, indistinguishably
from the pending queue's 45%. An instrument that blocks approved content at a similar rate is
describing itself, not the item.

**The payload is built by the pipeline's own `build_payload`**, not a variant assembled here.
The instrument is measured as it would run.

Nothing is written anywhere - no database, no verdict file. `--dump` writes the raw records so a
run can be re-analysed without buying it twice.
"""

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from dataclasses import dataclass, field

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.hint_solution_review import (
    build_payload,
    out_of_range_defects,
)
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockTask,
    HintSolutionReviewResponse,
)

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway  # isort: skip

from intellichoice_curriculum.hint_solution_review import SYSTEM_PROMPT  # isort: skip

# The two verdicts that stop an item. `repair` and `reject` differ in recoverability and are
# reported separately below, but on the axis that decides whether a human is needed they are
# the same answer, and that axis is what check 1 measures a flip on.
_BLOCKING = ("repair", "reject")

_MAX_OUTPUT_TOKENS = 1500


@dataclass
class ItemResult:
    question_template_id: str
    skill_id: str
    difficulty_label: int
    verdicts: list[str] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    # The *content*, not just a count. D-195 is the entry that says a pilot which rejects
    # everything and keeps nothing leaves nothing to review - and this script shipped its
    # first run recording counts only, so its five blocked items could not be read without
    # re-buying them. A measurement whose findings are unreadable is a measurement of a
    # number rather than of the thing.
    defects: list[list[dict]] = field(default_factory=list)
    reasonings: list[str] = field(default_factory=list)
    bad_indices: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def blocking_flags(self) -> list[bool]:
        return [v in _BLOCKING for v in self.verdicts]

    @property
    def split(self) -> bool:
        """Both blocked and passed across identical readings - the finding, not noise."""
        flags = self.blocking_flags
        return len(set(flags)) > 1


def _population(
    seed: int, sample: int
) -> tuple[list[AuthoredTemplateDef], list[AuthoredTemplateDef]]:
    """(check-2 sample, check-1 subset), drawn once from one seeded shuffle.

    Sorted by id before shuffling so the draw depends on the seed and not on filesystem
    ordering - a population that quietly changes between runs would make a repeat
    measurement incomparable to this one, which is the whole point of recording the seed.
    """
    everything = sorted(
        (item for items in load_authored_bank().values() for item in items),
        key=lambda i: i.question_template_id,
    )
    rng = random.Random(seed)
    rng.shuffle(everything)
    broad = everything[:sample]
    return broad, broad[:8]


def _build_gateway(budget_cents: float) -> ResilientBedrockGateway:
    settings = get_pipeline_settings()
    provider = (
        AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        if settings.bedrock_provider == "bedrock"
        else MockBedrockProvider()
    )
    return ResilientBedrockGateway(
        provider=provider,
        # No dedicated setting for this task yet, on purpose: it has no pipeline caller, and
        # adding a settings field for a task that may be disqualified by this very run would
        # be building the wiring before the result. The judge's model is the honest default -
        # it is the model the pipeline would most plausibly give this job.
        model_registry={BedrockTask.HINT_SOLUTION_REVIEW: settings.bedrock_judge_model_id},
        session_budget_cents=budget_cents,
        call_timeout_s=120.0,
    )


async def _review_once(
    gateway, item: AuthoredTemplateDef, *, names: dict, spend: float
) -> tuple[dict, float]:
    generated = item.to_generated_item()
    payload = build_payload(
        generated,
        skill_name=names["skills"][item.skill_id],
        grade_band=item.grade_band,
    )
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.HINT_SOLUTION_REVIEW,
            system_prompt=SYSTEM_PROMPT,
            payload=payload,
            response_model=HintSolutionReviewResponse,
            max_output_tokens=_MAX_OUTPUT_TOKENS,
            session_spend_cents=spend,
        )
    except BedrockGatewayError as exc:
        return {"error": str(exc)}, spend + exc.cost_cents
    response = result.value
    return (
        {
            "verdict": response.verdict,
            "uncertainty": response.uncertainty,
            "defects": [d.model_dump() for d in response.defects],
            # A hallucinated location must be counted, not silently tolerated: repairing
            # against an index the item does not have is how a correct item gets damaged.
            "bad_indices": out_of_range_defects(response, generated),
            "reasoning": response.reasoning,
        },
        spend + result.cost_cents,
    )


async def _read(
    gateway, items, *, repeat: int, budget: float, spend: float, label: str
) -> tuple[dict[str, ItemResult], float]:
    results = {
        i.question_template_id: ItemResult(
            i.question_template_id, i.skill_id, i.difficulty_label
        )
        for i in items
    }
    names = {"skills": {s.skill_id: s.name for s in load_curriculum().skills}}
    for run in range(repeat):
        for item in items:
            if spend >= budget:
                print(f"  ! budget of {budget}c reached - stopping {label} early")
                return results, spend
            record, spend = await _review_once(gateway, item, names=names, spend=spend)
            r = results[item.question_template_id]
            if "error" in record:
                r.errors.append(record["error"])
                print(f"  {label} run {run + 1} {item.question_template_id}: ERROR")
                continue
            r.verdicts.append(record["verdict"])
            r.uncertainties.append(record["uncertainty"])
            r.defects.append(record["defects"])
            r.reasonings.append(record["reasoning"])
            r.bad_indices.extend(record["bad_indices"])
            print(
                f"  {label} run {run + 1} {item.question_template_id}: "
                f"{record['verdict']:<6} unc={record['uncertainty']:<6} "
                f"defects={len(record['defects'])} spend={spend:.1f}c"
            )
    return results, spend


def _report_check_1(results: dict[str, ItemResult]) -> dict:
    print("\n--- Check 1: reproducibility (per-item, 4 readings) " + "-" * 20)
    split = [r for r in results.values() if r.split]
    for r in results.values():
        marks = "".join("B" if b else "." for b in r.blocking_flags) or "-"
        print(
            f"  {r.question_template_id:<42} d{r.difficulty_label} {marks}"
            f"{'  <- SPLIT' if r.split else ''}"
        )
    print(f"  items: {len(results)}   M1 split: {len(split)}")
    print(f"  verdicts seen: {dict(Counter(v for r in results.values() for v in r.verdicts))}")
    # Pre-registered: >= 3 of 8 is D-245's exact number, which that session called a
    # coin-flip gate and downgraded rather than shipped.
    print(f"  >>> {'DISQUALIFIED' if len(split) >= 3 else 'not falsified'} by M1 (>= 3 splits)")
    return {
        "m1_split": len(split),
        "split_ids": [r.question_template_id for r in split],
        "per_item": {
            r.question_template_id: {
                "skill_id": r.skill_id,
                "difficulty_label": r.difficulty_label,
                "verdicts": r.verdicts,
                "uncertainties": r.uncertainties,
                "defects": r.defects,
                "reasonings": r.reasonings,
                "bad_indices": r.bad_indices,
                "errors": r.errors,
            }
            for r in results.values()
        },
    }


def _report_check_2(results: dict[str, ItemResult]) -> dict:
    print("\n--- Check 2: false rejection on approved content (1 reading) " + "-" * 10)
    read = [r for r in results.values() if r.verdicts]
    verdicts = Counter(r.verdicts[0] for r in read)
    blocking = [r for r in read if r.verdicts[0] in _BLOCKING]
    rejects = [r for r in read if r.verdicts[0] == "reject"]
    bad = [r for r in blocking if r.bad_indices]
    total = len(read) or 1
    m2, m2r = len(blocking) / total, len(rejects) / total
    m3 = len(bad) / (len(blocking) or 1)
    for r in blocking:
        print(f"  BLOCKED {r.question_template_id:<42} {r.verdicts[0]:<6} d{r.difficulty_label}")
    print(f"  items read: {len(read)}   verdicts: {dict(verdicts)}")
    print(f"  M2  blocking rate: {m2:.1%}   M2r reject rate: {m2r:.1%}")
    print(f"  M3  blocking responses with an out-of-range defect index: {len(bad)} ({m3:.1%})")
    print(f"  M4  uncertainty: {dict(Counter(r.uncertainties[0] for r in read))}")
    # Pre-registered thresholds. 30% rather than D-249's 46% on purpose: matching that figure
    # would let this instrument be *as bad as* the thing it replaces and still pass.
    verdict_lines = [
        ("M2 >= 30%", m2 >= 0.30),
        ("M2r >= 10%", m2r >= 0.10),
        ("M3 > 5% of blocking", len(bad) > 0 and m3 > 0.05),
    ]
    for name, failed in verdict_lines:
        print(f"  >>> {'DISQUALIFIED' if failed else 'not falsified'} by {name}")
    # D-254 measured this at 48/50 `low` and D-255 acted on it: the decision flow no longer
    # routes second readings on uncertainty, because both reviewers now read every item. The
    # field is kept as an observability signal, so what matters here is no longer "is it
    # constant" but "has its baseline moved" - ~96% `low` is the reference.
    if len(set(r.uncertainties[0] for r in read)) < 2:
        print("  >>> `uncertainty` is constant in this sample. It routes nothing (D-255), so")
        print("      this is an observability note, not a disqualifier - but a reviewer whose")
        print("      self-report never varies is reporting a constant, not a judgement.")
    return {
        "m2_blocking_rate": m2,
        "m2r_reject_rate": m2r,
        "m3_bad_index_share_of_blocking": m3,
        "verdicts": dict(verdicts),
        "uncertainty": dict(Counter(r.uncertainties[0] for r in read)),
        "blocked_ids": [r.question_template_id for r in blocking],
        "per_item": {
            r.question_template_id: {
                "skill_id": r.skill_id,
                "difficulty_label": r.difficulty_label,
                "verdict": r.verdicts[0] if r.verdicts else None,
                "uncertainty": r.uncertainties[0] if r.uncertainties else None,
                "defects": r.defects[0] if r.defects else None,
                "reasoning": r.reasonings[0] if r.reasonings else None,
                "bad_indices": r.bad_indices,
                "errors": r.errors,
            }
            for r in results.values()
        },
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=4, help="check-1 readings (D-237: not 2)")
    parser.add_argument("--sample", type=int, default=50, help="check-2 item count")
    parser.add_argument("--seed", type=int, default=20260810, help="population draw seed")
    parser.add_argument("--run-budget-cents", type=float, default=150.0)
    parser.add_argument("--dump", default=None, metavar="PATH")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the population and call count; build no provider and spend nothing",
    )
    args = parser.parse_args()

    broad, narrow = _population(args.seed, args.sample)
    if not broad:
        print("no authored bank items found - nothing to measure", file=sys.stderr)
        return 1
    calls = len(narrow) * args.repeat + len(broad)
    print(f"seed {args.seed}: check 1 = {len(narrow)} items x {args.repeat}, "
          f"check 2 = {len(broad)} items x 1  ->  {calls} calls")
    print(f"check 1 items: {', '.join(i.question_template_id for i in narrow)}")
    if args.dry_run:
        print("--dry-run: no provider built, nothing spent")
        return 0

    gateway = _build_gateway(args.run_budget_cents)
    spend = 0.0
    # Check 1 first: if verdicts flip on identical input, check 2's single readings are
    # already known to be unreliable and the run can be stopped by reading the output.
    narrow_results, spend = await _read(
        gateway, narrow, repeat=args.repeat, budget=args.run_budget_cents, spend=spend,
        label="c1",
    )
    broad_results, spend = await _read(
        gateway, broad, repeat=1, budget=args.run_budget_cents, spend=spend, label="c2",
    )
    report = {
        "seed": args.seed,
        "check_1": _report_check_1(narrow_results),
        "check_2": _report_check_2(broad_results),
        "spend_cents": spend,
    }
    print(f"\nspend: {spend:.1f} cents")
    print(
        "\nSurviving these checks is not validation. It means not-yet-falsified: false\n"
        "acceptance is invisible to both, and HINT_SOLUTION_REVIEW.md check 3 exists for it."
    )
    if args.dump:
        with open(args.dump, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"raw records -> {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
