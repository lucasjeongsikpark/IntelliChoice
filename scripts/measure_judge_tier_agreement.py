"""Does the judge reproduce the tier labels of items it already approved? (C1 Phase 3)

**The observation this exists to resolve.** In the Phase 3 serving-floor runs, **38 of 73
rejections (52%) were the judge disagreeing about difficulty, and every one pulled toward the
middle of the scale**:

    asked 1 -> judged 3   (3 items)
    asked 4 -> judged 2   (18 items)
    asked 5 -> judged 2   (6 items)
    asked 5 -> judged 3   (11 items)

Not one disagreement moved outward. Eighteen items designed against a topic's own tier-4
anchor landed at tier 2. Two readings fit that, and they have opposite consequences:

- **content**: these topics genuinely do not span five tiers - a grade-2 word problem has no
  difficulty 5 - and the serving floor's "every tier 1-5" is the thing that is wrong;
- **instrument**: the judge's scale is compressed and rates most things 2-3 regardless, in
  which case the floor is fine and the *rubric* needs work.

**The test.** Re-judge items **already in the bank at known tiers**, blind, exactly as the
pipeline judges a candidate. Their labels were set by this same judge agreeing with the
requested tier at generation time (a disagreement would have rejected or retiered them), so
this is a self-consistency check with a real prediction:

- if the judge reproduces d4/d5 labels on d4/d5 bank items, the scale discriminates and the
  new candidates were genuinely mis-tiered - the *content* reading;
- if it rates those same shipped items 2-3, the instrument is compressed, and the same
  rejections would fire against content the bank already serves - the *instrument* reading.

Hand-authored items are excluded: they never faced the judge, so they carry no prediction.

**Cost.** One judge call per sampled item, through the same gateway, task slot, timeout and
token ceiling as the pipeline, with an explicit `--run-budget-cents` checked between items.
Preflight is the default: it prints the sample and calls nothing.

Run:

    uv run python scripts/measure_judge_tier_agreement.py                     # free preflight
    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    CURRICULUM_BEDROCK_PROVIDER=bedrock CURRICULUM_BEDROCK_AWS_REGION=us-east-1 \
    CURRICULUM_BEDROCK_JUDGE_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \
    uv run python scripts/measure_judge_tier_agreement.py --run --run-budget-cents 60
"""

from __future__ import annotations

import argparse
import asyncio
import collections
import sys

from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_curriculum.ai_pipeline import (
    _AUTHORED_JUDGE_MAX_TOKENS,
    _AUTHORED_JUDGE_TIMEOUT_S,
    _call,
    judge_system_prompt,
)
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.content import load_curriculum
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import (
    BedrockTask,
    QuestionJudgePayload,
    QuestionJudgeResponse,
)

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway  # isort: skip

# The tiers the disagreements clustered at. The middle tier is sampled too, as a control:
# a compressed instrument agrees there and disagrees at the edges, while a broken one
# disagrees everywhere.
SAMPLED_TIERS = (1, 3, 4, 5)
PER_TIER = 4

# **The sample has to come from the topics that produced the disagreements**, or it tests
# nothing. The first version of this script took whatever sorted first and drew every d4/d5
# item from `algebra_*` and `calculus` - none of which is where the 18 "asked 4, judged 2"
# rejections happened. These five are the topics that both (a) refused new tier-4/5
# candidates in the Phase 3 runs and (b) already hold approved items at those tiers, which
# is the only population where the two readings actually predict different results.
PRIORITY_TOPICS = (
    "g4_word_problems",
    "trigonometry",
    "g68_word_problems",
    "g6_word_problems",
    "algebra_2",
)


def _sample() -> list[tuple[str, int, AuthoredTemplateDef]]:
    """(topic_id, difficulty, template) for generated items only, spread across topics."""
    bank = load_authored_bank()
    by_tier: dict[int, list[tuple[str, int, AuthoredTemplateDef]]] = collections.defaultdict(list)
    for topic_id, templates in sorted(bank.items()):
        for template in templates:
            if not str(template.generator_model).startswith("bedrock"):
                continue  # hand-authored and figure items never faced the judge
            if template.difficulty_label in SAMPLED_TIERS:
                tier = template.difficulty_label
                by_tier[tier].append((topic_id, tier, template))

    chosen: list[tuple[str, int, AuthoredTemplateDef]] = []
    for tier in SAMPLED_TIERS:
        # Priority topics first, then anything else - and one per topic before a second
        # from any topic, so the sample is not one topic's idea of a tier 5.
        rows = sorted(
            by_tier.get(tier, []),
            key=lambda row: (
                PRIORITY_TOPICS.index(row[0]) if row[0] in PRIORITY_TOPICS else len(PRIORITY_TOPICS)
            ),
        )
        seen: set[str] = set()
        spread = [row for row in rows if not (row[0] in seen or seen.add(row[0]))]
        chosen.extend(spread[:PER_TIER])
    return chosen


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Make the paid calls")
    parser.add_argument("--run-budget-cents", type=float, default=60.0)
    args = parser.parse_args()

    curriculum = load_curriculum()
    sample = _sample()
    print(f"sampled {len(sample)} generated bank items at tiers {SAMPLED_TIERS}:")
    for _topic_id, tier, template in sample:
        print(f"  d{tier} {template.question_template_id}")
    if not args.run:
        print("\npreflight only - no call made. Re-run with --run to judge them.")
        return 0

    settings = get_pipeline_settings()
    provider = (
        AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        if settings.bedrock_provider == "bedrock"
        else MockBedrockProvider()
    )
    gateway = ResilientBedrockGateway(
        provider=provider,
        model_registry={BedrockTask.QUESTION_JUDGE: settings.bedrock_judge_model_id},
        session_budget_cents=args.run_budget_cents,
        call_timeout_s=120.0,
    )
    spend = 0.0
    agreements: collections.Counter[str] = collections.Counter()
    matrix: collections.Counter[tuple[int, int]] = collections.Counter()

    for topic_id, tier, template in sample:
        if spend >= args.run_budget_cents:
            print(f"\nstopped early: budget {args.run_budget_cents}c reached")
            break
        topic = next(t for t in curriculum.topics if t.topic_id == topic_id)
        skill = curriculum.skill(template.skill_id)
        if skill is None:
            print(f"  d{tier} {template.question_template_id}: unknown skill, skipped")
            continue
        item = template.to_generated_item()
        payload = QuestionJudgePayload(
            rendered_question=template.rendered_question,
            option_a=item.option_a,
            option_b=item.option_b,
            option_c=item.option_c,
            option_d=item.option_d,
            correct_option=item.correct_option,
            hint_ladder=item.hint_ladder,
            canonical_solution=item.canonical_solution.final_answer,
            topic_name=topic.name,
            skill_name=skill.name,
            grade_band=topic.grade_band,
        )
        judge, cost, error = await _call(
            gateway,
            task=BedrockTask.QUESTION_JUDGE,
            system_prompt=judge_system_prompt(topic),
            payload=payload,
            response_model=QuestionJudgeResponse,
            session_spend_cents=spend,
            # The pipeline's own ceilings, not the 400-token default - judging is a
            # prose-first response and every one of the first 16 calls died on the
            # default mid-sentence, for 6.8 cents and no data.
            max_output_tokens=_AUTHORED_JUDGE_MAX_TOKENS,
            timeout_s=_AUTHORED_JUDGE_TIMEOUT_S,
        )
        spend += cost
        if error is not None or not isinstance(judge, QuestionJudgeResponse):
            print(f"  d{tier} {template.question_template_id}: call failed - {error}")
            agreements["call_failed"] += 1
            continue
        matrix[(tier, judge.reviewed_difficulty)] += 1
        verdict = "agrees" if judge.reviewed_difficulty == tier else "disagrees"
        agreements[verdict] += 1
        print(
            f"  d{tier} -> judged {judge.reviewed_difficulty}  [{verdict}] "
            f"{template.question_template_id}"
        )

    print(f"\nspend: {spend:.2f} cents")
    print(f"verdicts: {dict(agreements)}")
    print("\nbank tier -> judged tier:")
    for (asked, judged), count in sorted(matrix.items()):
        print(f"  d{asked} -> d{judged}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
