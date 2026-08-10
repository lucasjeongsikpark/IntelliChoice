"""Run the §4 review loop over authored bank items the audit flags (D-262).

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    CURRICULUM_BEDROCK_PROVIDER=bedrock CURRICULUM_BEDROCK_AWS_REGION=us-east-1 \
    uv run --package intellichoice-curriculum python scripts/repair_authored_solutions.py \
      --limit 8 --run-budget-cents 100 --dump out.json

**It never writes to the bank.** The output is a dump of proposed repairs and a before/after
audit count. Content served to minors does not change because a script produced a diff; applying
one is a separate, human decision made against that dump.

**The population is `audit_solution_step_completeness`'s unambiguous set** — items whose last
solution step shows unevaluated arithmetic or an unsolved unknown (D-257: 44 of 130). That audit
is also the *outcome* measure, which is the point: the panel accepting an item that still fails
it would mean the reviewers approved a repair that did not repair, and that is a worse finding
than a low acceptance rate.

Roster is D-261's and is not a default anywhere: reviewers B and C must differ from each other
and from the repairer, or the panel is one opinion billed twice and the repairer is grading its
own work.
"""

import argparse
import asyncio
import json
import pathlib
import sys
from collections import Counter

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.authored_bank import load_authored_bank
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.review_loop import run_review_loop
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockTask,
    HintSolutionDefect,
)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from audit_solution_step_completeness import (  # noqa: E402
    _UNAMBIGUOUS,
    classify,
    last_step_text,
)

_DEFAULT_REVIEWERS = (
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    "openai.gpt-oss-120b-1:0",
)
_DEFAULT_REPAIRER = "qwen.qwen3-32b-v1:0"


def _gateway(model_id: str, budget_cents: float) -> ResilientBedrockGateway:
    settings = get_pipeline_settings()
    provider = (
        AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        if settings.bedrock_provider == "bedrock"
        else MockBedrockProvider()
    )
    return ResilientBedrockGateway(
        provider=provider,
        model_registry={
            BedrockTask.HINT_SOLUTION_REVIEW: model_id,
            BedrockTask.HINT_SOLUTION_REPAIR: model_id,
        },
        session_budget_cents=budget_cents,
        call_timeout_s=120.0,
    )


def _flagged_items() -> list:
    """Bank items the audit flags unambiguously, **round-robin across skills**.

    Sorting by id alone put all eight pilot items in `fraction_operations`, because that is
    what comes first alphabetically - and the defect classes are not evenly spread (D-257:
    `place_value_compare` is 14 of 15, and its `[128 plus something makes 182]` shape is a
    different repair problem from an unevaluated fraction). A pilot that sees one topic
    cannot say anything about the others, and would report a converged loop while the hardest
    class was never attempted.
    """
    by_skill: dict[str, list] = {}
    for items in load_authored_bank().values():
        for item in items:
            steps = item.canonical_solution["steps"]
            verdict = classify(
                last_step_text(steps[-1]), str(item.canonical_solution["final_answer"])
            )
            if verdict in _UNAMBIGUOUS:
                by_skill.setdefault(item.skill_id, []).append(item)
    for group in by_skill.values():
        group.sort(key=lambda i: i.question_template_id)
    ordered: list = []
    for depth in range(max(len(g) for g in by_skill.values())):
        for skill in sorted(by_skill):
            if depth < len(by_skill[skill]):
                ordered.append(by_skill[skill][depth])
    return ordered


def _still_flagged(outcome) -> bool:
    """Does the *repaired* item still fail the audit? R2, and the disqualifying metric."""
    last = outcome.item.canonical_solution.steps[-1]
    # Both fields (D-262). Scoring `expression` alone made a working repair - one that put the
    # computation in the prose - read as the panel approving something it had not fixed.
    return (
        classify(
            last_step_text({"explanation": last.explanation, "expression": last.expression}),
            str(outcome.item.canonical_solution.final_answer),
        )
        in _UNAMBIGUOUS
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=8, help="items to attempt (D-204: pilot)")
    parser.add_argument("--run-budget-cents", type=float, default=100.0)
    parser.add_argument("--per-item-cents", type=float, default=15.0)
    parser.add_argument("--reviewer", action="append", metavar="MODEL_ID")
    parser.add_argument("--repairer", default=_DEFAULT_REPAIRER)
    parser.add_argument("--dump", default=None, metavar="PATH")
    parser.add_argument(
        "--contribute-audit-defect",
        action="store_true",
        help=(
            "let the audit open a repair on round 1 for items it flags (D-263). It can "
            "never reject: from round 2 the panel alone decides, and the reviewers are "
            "never told what the audit found"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    reviewers = tuple(args.reviewer) if args.reviewer else _DEFAULT_REVIEWERS
    if len(set(reviewers)) < 2 or args.repairer in reviewers:
        print(
            "reviewers must differ from each other and from the repairer (D-261): a shared "
            "model makes the panel one opinion billed twice, and a repairer that reviews "
            "grades its own work",
            file=sys.stderr,
        )
        return 2

    flagged = _flagged_items()
    chosen = flagged[: args.limit]
    print(f"audit flags {len(flagged)} items; attempting {len(chosen)}")
    print(f"reviewers: {', '.join(reviewers)}\nrepairer:  {args.repairer}")
    for item in chosen:
        last = item.canonical_solution["steps"][-1]["expression"]
        final = item.canonical_solution["final_answer"]
        print(f"  {item.question_template_id:<44} [{last}] -> [{final}]")
    if args.dry_run:
        print("--dry-run: no provider built, nothing spent")
        return 0

    skills = {s.skill_id: s.name for s in load_curriculum().skills}
    gateways: dict[str, BedrockGateway] = {
        name: _gateway(name, args.run_budget_cents) for name in reviewers
    }
    repairer = _gateway(args.repairer, args.run_budget_cents)

    records, spend = [], 0.0
    for item in chosen:
        if spend >= args.run_budget_cents:
            print(f"! run budget of {args.run_budget_cents}c reached - stopping")
            break
        generated = item.to_generated_item()
        contributed = (
            [
                HintSolutionDefect(
                    target="canonical_solution",
                    index=len(generated.canonical_solution.steps),
                    problem=(
                        "the final solution step describes an operation without showing its "
                        "result, so the worked solution never states the answer a student is "
                        "meant to arrive at"
                    ),
                    suggested_fix=(
                        "complete the last step so it shows the result of the operation it "
                        "describes"
                    ),
                )
            ]
            if args.contribute_audit_defect
            else None
        )
        outcome = await run_review_loop(
            reviewers=gateways,
            repairer=repairer,
            item=generated,
            skill_name=skills[item.skill_id],
            grade_band=item.grade_band,
            per_item_budget_cents=args.per_item_cents,
            session_spend_cents=spend,
            first_round_defects=contributed,
        )
        spend += outcome.spend_cents
        still = _still_flagged(outcome)
        print(
            f"  {item.question_template_id:<44} {outcome.status:<9} "
            f"{outcome.stopped_because:<26} rounds={len(outcome.rounds)} "
            f"audit={'STILL FLAGGED' if still else 'clear'} spend={spend:.1f}c"
        )
        records.append(
            {
                "question_template_id": item.question_template_id,
                "skill_id": item.skill_id,
                "outcome": outcome.as_evidence(),
                "still_flagged_by_audit": still,
                "before_last_step": str(item.canonical_solution["steps"][-1]["expression"]),
                "after_last_step": str(outcome.item.canonical_solution.steps[-1].expression),
                "before_hint_ladder": list(item.hint_ladder),
                "after_hint_ladder": list(outcome.item.hint_ladder),
                "after_solution_steps": [
                    {
                        "step_number": s.step_number,
                        "explanation": s.explanation,
                        "expression": s.expression,
                    }
                    for s in outcome.item.canonical_solution.steps
                ],
            }
        )

    accepted = [r for r in records if r["outcome"]["status"] == "accepted"]
    cleared = [r for r in accepted if not r["still_flagged_by_audit"]]
    collateral = [r for r in records if any(x["collateral_edits"] for x in r["outcome"]["rounds"])]
    # D-262: "accepted but still flagged" has two causes with *opposite* fixes, and the
    # criterion this replaces conflated them - it read every such item as the panel laundering
    # a defect into an approval, when in that run every one was an item the panel simply never
    # blocked. Reporting them apart is the whole correction.
    never = [
        r for r in accepted if r["still_flagged_by_audit"] and len(r["outcome"]["rounds"]) == 1
    ]
    laundered = [
        r for r in accepted if r["still_flagged_by_audit"] and len(r["outcome"]["rounds"]) > 1
    ]
    print(f"\nR1 accepted:            {len(accepted)} of {len(records)}")
    print(f"R2 accepted AND clear:  {len(cleared)} of {len(records)}")
    print(f"   ...passed on sight (recall failure)  : {len(never)}")
    print(f"   ...repaired but still flagged        : {len(laundered)}")
    if laundered:
        print("  >>> SERIOUS: the panel accepted a repair that did not fix what it named.")
        print("      That launders a defect into an approval. Different failure from a miss,")
        print("      and the only one that makes the loop worse than not running it.")
    if never:
        print("  >>> RECALL FAILURE: the panel never blocked these. The repair machinery was")
        print("      never asked. Fix the detector, not the loop (D-262).")
    reasons = Counter(r["outcome"]["stopped_because"] for r in records)
    print(f"R3 stop reasons:        {dict(reasons)}")
    print(f"R4 rounds:              {[len(r['outcome']['rounds']) for r in records]}")
    print(f"R6 collateral rejects:  {len(collateral)} of {len(records)}")
    print(f"\nspend: {spend:.1f} cents")
    print("\nNothing was written to the bank. Read the dump before applying anything.")

    if args.dump:
        with open(args.dump, "w") as fh:
            json.dump({"records": records, "spend_cents": spend}, fh, indent=2)
        print(f"proposed repairs -> {args.dump}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
