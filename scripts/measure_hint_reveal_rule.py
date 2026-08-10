"""Measure whether the §5.8.5 judge answers `hint_reveals_answer` consistently (D-245).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    CURRICULUM_BEDROCK_PROVIDER=bedrock CURRICULUM_BEDROCK_AWS_REGION=us-east-1 \
    CURRICULUM_BEDROCK_JUDGE_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
    uv run --package intellichoice-curriculum python scripts/measure_hint_reveal_rule.py \
      --repeat 4 --run-budget-cents 80

**What this is for.** D-243 closed the generator's parsing problem and left its dominant
loss at the judge: two of three judge rejections were `hint_reveals_answer` on hints that
**stated the setup equation**. Before treating that as a generator defect, three things were
established for free and they point the other way.

The rubric defines reveal as *"states it, or reduces the problem to reading it off"*, and
solving `4n = 52` is neither. The **same judge in the same run decided both ways** on the
identical pattern - it rejected `4n = 52` in one candidate and explicitly excused
`5(w+3) + 10 = 50` in another (*"does not state the answer (w = 5)"*). And **8 of the 130
hand-authored, human-reviewed bank items state the setup equation in a hint** and were all
accepted.

So the hypothesis under test is not "the generator writes bad hints". It is **"the rubric
does not say where stating-the-equation falls, so the judge answers inconsistently"** - and
those 8 reviewed items are the population that settles it, because whatever the judge says
about them is a statement about the rubric rather than about a generated candidate.

**Why not `audit_authored_bank.py --judge`.** It has no way to target specific items, so it
would bill an entire topic to answer a question about eight of them - and its report is
built around tier disagreement, which is not what is in dispute here.

**n=4, and the reason is paid for.** D-237 measured this judge answering 6 and 13 out of 16
on identical inputs, and D-238 paid to match an n=4 baseline rather than conclude from an
asymmetry. A per-item split is the *finding* here, not noise to be averaged away, so every
item's four answers are printed individually.

**The prompt is imported, never restated** - `judge_inputs` assembles exactly what the
shipped pipeline sends, which is also what the D-236 fingerprint hashes. Condition B splices
one candidate clause onto that same string, so the only difference between the conditions is
the clause under test.

**Result (D-245, 42 cents).** The inconsistency is real and the proposed fix does not fix
it. Under the shipped rubric **3 of 8 human-reviewed bank items answered both ways** across
four identical calls, and **4 of 8 were flagged at least once** - so a gate that rejects on
one judge call discards roughly half of content a human already approved. The candidate
clause made it **worse** (4 of 8 split) while moving the tier reading on none, which is the
one thing it was required not to disturb.

Re-run this before changing anything about `hint_reveals_answer`. It is cheap, it is
non-destructive, and the last two readings of this rule from a single run were both wrong.

Bedrock use: one `QUESTION_JUDGE` call per item per repeat per condition. Nothing is
written anywhere - no database, no verdict file.
"""

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.adjudications import judge_inputs
from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockTask,
    QuestionJudgeResponse,
)

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway  # isort: skip

# Matches a hint that writes an equation out - `8b = 144`, `36 - 3x = 12 + x`. Deliberately
# loose: it selects the *population to measure*, and a false positive here costs one extra
# judged item while a false negative silently shrinks the sample. It is not a gate and
# nothing ships based on it.
_EQUATION_IN_HINT = re.compile(r"[0-9a-zA-Z)]\s*=\s*[0-9a-zA-Z(-]")

# The clause under test. **It was measured and it FAILED - do not ship it, and do not
# assume a variant of it will work without measuring that too.**
#
# Kept here rather than in `ai_pipeline` precisely because it did not earn its place:
# shipping a prompt change and then measuring it is how a rubric acquires a rule nobody
# checked, and this one lapses live verdicts when it lands (D-236/D-237).
#
# n=4 per condition, 8 hand-authored bank items: splits went **3/8 -> 4/8**, the flag rate
# stayed at 4/8, and the one item that had been unanimous became split. More instruction
# produced *less* consistency.
#
# The reason is in the judge's own words. On `208100` it observed, correctly, that "for a
# 1-step equation, formulating the equation is the main cognitive task; once stated, only
# division remains" - which is the exact opposite of what this clause asserts. The clause
# says a solving skill leaves the work intact when the equation is written out; at tier 1
# that is simply false, and telling the judge otherwise asked it to excuse something that
# really is the task. See D-245.
_CANDIDATE_CLAUSE = (
    "Judge `hint_reveals_answer` against the SKILL this item is filed under, named above. "
    "A hint reveals the answer only if it removes the work that skill names. For a skill "
    "about solving an equation, writing the equation out does NOT reveal the answer - the "
    "student still has to solve it, which is the entire skill; that is a legitimate final "
    "rung of a hint ladder. For a skill about translating a scenario into an equation, "
    "writing the equation out DOES reveal it, because the translation was the work. "
)


@dataclass
class ItemResult:
    question_template_id: str
    skill_id: str
    reveals: list[bool] = field(default_factory=list)
    hint_quality: list[int] = field(default_factory=list)
    reviewed: list[int] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def split(self) -> bool:
        """Answered both ways across identical calls. The finding, not the noise."""
        return len(set(self.reveals)) > 1

    @property
    def flagged_any(self) -> bool:
        return any(self.reveals)


def leaking_variant(item):
    """The same item with its final hint stating the answer outright (D-246).

    **The negative control D-245 was missing.** That run measured the rule only on content a
    human had approved, so it could show the gate is too *strict* and say nothing about
    whether it has any signal at all - and a gate cannot be loosened on evidence drawn only
    from the population it was too strict on (D-221).

    The mutation appends one sentence to the last rung, leaving the item otherwise
    byte-identical, so any change in the verdict is attributable to that sentence alone.

    **This is the easy end and the write-up must say so.** The judge's *unique* contribution
    over the deterministic `answer_text_leaked` check would be catching leaks that never
    print the answer string - and that class cannot be built here without presupposing the
    verdict under test, because `208100`'s shipped hint 3 is already "Divide 144 by 8" and
    the judge excused it in 3 of 4 calls.
    """
    answer_text = getattr(item, f"option_{item.correct_option}")
    ladder = list(item.hint_ladder)
    ladder[-1] = f"{ladder[-1].rstrip()} The answer is {answer_text}."
    return item.model_copy(update={"hint_ladder": ladder})


def _population() -> list:
    """Bank items whose hint ladder writes an equation out.

    Hand-authored and human-reviewed, which is what makes them load-bearing: whatever the
    judge says about these is a statement about the rubric, because the content has already
    been through the deterministic gate and a human.
    """
    return [
        item
        for items in load_authored_bank().values()
        for item in items
        if any(_EQUATION_IN_HINT.search(h) for h in item.hint_ladder)
    ]


def _build_gateway() -> ResilientBedrockGateway:
    settings = get_pipeline_settings()
    provider = (
        AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        if settings.bedrock_provider == "bedrock"
        else MockBedrockProvider()
    )
    return ResilientBedrockGateway(
        provider=provider,
        model_registry={BedrockTask.QUESTION_JUDGE: settings.bedrock_judge_model_id},
        session_budget_cents=settings.bedrock_run_budget_cents,
        call_timeout_s=120.0,
    )


async def _judge_once(gateway, item, *, clause: str, spend: float) -> tuple[dict, float]:
    payload, _anchors, system_prompt = judge_inputs(item)
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.QUESTION_JUDGE,
            system_prompt=system_prompt + clause,
            payload=payload,
            response_model=QuestionJudgeResponse,
            max_output_tokens=4000,
            session_spend_cents=spend,
        )
    except BedrockGatewayError as exc:
        return {"error": str(exc)}, spend + exc.cost_cents
    r = result.value
    return (
        {
            "reveals": r.hint_reveals_answer,
            "reason": r.hint_reveals_answer_reason,
            "hint_quality": r.hint_quality_score,
            "reviewed": r.reviewed_difficulty,
        },
        spend + result.cost_cents,
    )


async def _condition(gateway, items, *, clause: str, repeat: int, budget: float, spend: float):
    results = {
        i.question_template_id: ItemResult(i.question_template_id, i.skill_id)
        for i in items
    }
    reasons: list[tuple[str, bool, str]] = []
    for run in range(repeat):
        for item in items:
            if spend >= budget:
                print(f"  ! budget of {budget} cents reached - stopping this condition early")
                return results, reasons, spend
            record, spend = await _judge_once(gateway, item, clause=clause, spend=spend)
            r = results[item.question_template_id]
            if "error" in record:
                r.errors.append(record["error"])
                print(f"  run {run + 1} {item.question_template_id}: E")
                continue
            r.reveals.append(record["reveals"])
            r.hint_quality.append(record["hint_quality"])
            r.reviewed.append(record["reviewed"])
            reasons.append((item.question_template_id, record["reveals"], record["reason"]))
            print(
                f"  run {run + 1} {item.question_template_id}: "
                f"reveals={record['reveals']} quality={record['hint_quality']} "
                f"tier={record['reviewed']}"
            )
    return results, reasons, spend


def _report(name: str, results: dict[str, ItemResult]) -> dict:
    split = [r for r in results.values() if r.split]
    flagged = [r for r in results.values() if r.flagged_any]
    unanimous_true = [r for r in results.values() if r.reveals and all(r.reveals)]
    print(f"\n--- {name} " + "-" * (60 - len(name)))
    for r in results.values():
        marks = "".join("T" if v else "." for v in r.reveals) or "-"
        flag = "  <- SPLIT" if r.split else ""
        print(f"  {r.question_template_id:<42} {r.skill_id:<24} {marks}{flag}")
    print(f"  items: {len(results)}   split: {len(split)}   flagged at least once: {len(flagged)}")
    print(f"  unanimously 'reveals': {len(unanimous_true)}")
    return {
        "items": len(results),
        "split": len(split),
        "flagged_any": len(flagged),
        "unanimous_true": len(unanimous_true),
        "split_ids": [r.question_template_id for r in split],
        "per_item": {
            r.question_template_id: {
                "skill_id": r.skill_id,
                "reveals": r.reveals,
                "hint_quality": r.hint_quality,
                "reviewed": r.reviewed,
                "errors": r.errors,
            }
            for r in results.values()
        },
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=4, help="runs per condition (D-237: not 2)")
    parser.add_argument("--run-budget-cents", type=float, default=80.0)
    parser.add_argument("--dump", default=None, metavar="PATH", help="write the raw records")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="condition A only - the pre-registered stopping point if P1 fails",
    )
    parser.add_argument(
        "--control-only",
        action="store_true",
        help=(
            "D-246: judge the LEAKING variants under the shipped rubric and nothing else. "
            "This is the negative control - the true-positive rate the D-245 run could not "
            "measure, because every item in it was content a human had approved"
        ),
    )
    args = parser.parse_args()

    items = _population()
    if not items:
        print("no bank items write an equation into a hint - nothing to measure")
        return 1
    settings = get_pipeline_settings()
    print(f"provider: {settings.bedrock_provider}   judge: {settings.bedrock_judge_model_id}")
    print(
        f"population: {len(items)} items   repeat: {args.repeat}   "
        f"budget: {args.run_budget_cents}c"
    )
    print(f"skills: {dict(Counter(i.skill_id for i in items))}\n")

    gateway, spend = _build_gateway(), 0.0

    if args.control_only:
        print("=== control: leaking variants, shipped rubric (D-246) ===")
        leaking = [leaking_variant(i) for i in items]
        c_results, c_reasons, spend = await _condition(
            gateway,
            leaking,
            clause="",
            repeat=args.repeat,
            budget=args.run_budget_cents,
            spend=spend,
        )
        c = _report("control: hints that state the answer", c_results)
        calls = sum(len(r.reveals) for r in c_results.values())
        caught = sum(sum(r.reveals) for r in c_results.values())
        unanimous = sum(
            1 for r in c_results.values() if r.reveals and all(r.reveals)
        )
        rate = caught / calls if calls else 0.0
        print(f"\n  true-positive rate: {caught}/{calls} = {rate:.0%}")
        print(f"  caught unanimously: {unanimous} of {len(c_results)} items")
        print(f"\nspend: {spend:.2f} cents")
        if args.dump:
            with open(args.dump, "w") as fh:
                json.dump(
                    {
                        "control": c,
                        "true_positive_rate": rate,
                        "calls": calls,
                        "caught": caught,
                        "unanimous": unanimous,
                        "reasons": c_reasons,
                        "spend_cents": spend,
                    },
                    fh,
                    indent=2,
                )
            print(f"wrote {args.dump}")
        return 0

    print("=== condition A: the shipped rubric ===")
    a_results, a_reasons, spend = await _condition(
        gateway, items, clause="", repeat=args.repeat, budget=args.run_budget_cents, spend=spend
    )
    a = _report("A: shipped rubric", a_results)

    b = None
    if not args.baseline_only:
        print("\n=== condition B: + the skill-aware clause ===")
        b_results, b_reasons, spend = await _condition(
            gateway,
            items,
            clause=_CANDIDATE_CLAUSE,
            repeat=args.repeat,
            budget=args.run_budget_cents,
            spend=spend,
        )
        b = _report("B: + skill-aware clause", b_results)
        # M4: a clause about hints must not move the tier reading. Checked here rather than
        # left to the eye, because D-238 spent a whole session on tier calibration.
        moved = [
            i
            for i in a_results
            if a_results[i].reviewed
            and b_results[i].reviewed
            and round(sum(a_results[i].reviewed) / len(a_results[i].reviewed))
            != round(sum(b_results[i].reviewed) / len(b_results[i].reviewed))
        ]
        print(f"\n  tier reading moved on {len(moved)} of {len(a_results)} items: {moved}")

    print(f"\nspend: {spend:.2f} cents")
    if args.dump:
        with open(args.dump, "w") as fh:
            json.dump(
                {"A": a, "B": b, "a_reasons": a_reasons, "spend_cents": spend}, fh, indent=2
            )
        print(f"wrote {args.dump}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
