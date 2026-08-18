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


async def _authoring_ratings(template_ids: list[str]) -> dict[str, tuple[int | None, str]]:
    """What the judge said about these items *when they were authored*, and how the stored
    tier was decided (D-300).

    Read because scoring only against the stored tier is what made this measurement
    mislead twice. A gap of exactly 1 is `flagged`, and flagged keeps the **slot's** tier -
    so for those items the stored label is not a judge rating at all, and "the judge does
    not reproduce it" is not evidence about the judge.
    """
    from intellichoice_db.engine import create_engine, create_session_factory, session_scope
    from intellichoice_db.models.questions import QuestionValidationRun
    from sqlalchemy import select

    engine = create_engine()
    try:
        async with session_scope(create_session_factory(engine)) as session:
            rows = (
                (
                    await session.execute(
                        select(QuestionValidationRun).where(
                            QuestionValidationRun.question_template_id.in_(template_ids)
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()
    out: dict[str, tuple[int | None, str]] = {}
    for row in rows:
        evidence = (row.stage_results or {}).get("difficulty") or {}
        if evidence and row.question_template_id:
            out[row.question_template_id] = (
                evidence.get("judge_reviewed_difficulty"),
                str(evidence.get("decision")),
            )
    return out


# The tiers the disagreements clustered at. The middle tier is sampled too, as a control:
# a compressed instrument agrees there and disagrees at the edges, while a broken one
# disagrees everywhere.
SAMPLED_TIERS = (1, 3, 4, 5)
PER_TIER = 4

# **Pinned by id, and that is the point (D-300).** D-292 reported 19% exact / 88% within one
# tier and did *not* record which 16 items it drew. The sample is computed from the bank, the
# bank has grown 658 -> 912 since, and re-running the old selector today already returns a
# different set - two of these are items this session generated. So D-292's numbers cannot be
# a baseline for any rubric change: a before/after on a moving sample measures the sample.
#
# The tiers and the topic priority below are why these particular items: the topics that both
# produced the tier-4/5 disagreements *and* already hold approved items at those tiers, which
# is the only population where "the content is mis-tiered" and "the instrument is compressed"
# predict different results. Tier 3 is the control - a compressed instrument agrees in the
# middle and disagrees at the edges, a broken one disagrees everywhere.
#
# Changing this list is allowed and re-baselining is then MANDATORY: the comparison is only
# meaningful between two runs over the same items.
PINNED_SAMPLE: tuple[tuple[int, str], ...] = (
    (1, "authored-g4_word_problems-d1-1506100"),
    (1, "authored-trigonometry-d5-1285500"),
    (1, "authored-g68_word_problems-d1-1225100"),
    (1, "authored-g6_word_problems-d1-1125100"),
    (3, "authored-g4_word_problems-d3-96300"),
    (3, "authored-trigonometry-d3-1285302"),
    (3, "authored-g68_word_problems-d3-1225301"),
    (3, "authored-g6_word_problems-d3-1126300"),
    (4, "authored-g4_word_problems-d4-977400"),
    (4, "authored-trigonometry-d4-1285402"),
    (4, "authored-g68_word_problems-d4-36400"),
    (4, "authored-g6_word_problems-d4-1127401"),
    (5, "authored-g4_word_problems-d5-37500"),
    (5, "authored-trigonometry-d5-35500"),
    (5, "authored-g68_word_problems-d5-1506501"),
    (5, "authored-algebra_2-d5-101500"),
)

# The topics that produced the disagreements. Kept because `--fresh-sample` still uses it,
# and because it records WHY the pinned ids are these ones. The first version of this script
# drew alphabetically and got every d4/d5 item from `algebra_*` and `calculus` - none of which
# is where the "asked 4, judged 2" rejections happened. A sample that cannot see the
# phenomenon reports that the phenomenon is absent.
PRIORITY_TOPICS = (
    "g4_word_problems",
    "trigonometry",
    "g68_word_problems",
    "g6_word_problems",
    "algebra_2",
)


def _pinned() -> list[tuple[str, int, AuthoredTemplateDef]]:
    """The pinned items, resolved from the bank. Missing ids are a hard error.

    Failing loudly matters more than degrading gracefully: silently dropping an item that has
    been retired would shrink the denominator and move the agreement rate for a reason that
    has nothing to do with the rubric.
    """
    bank = load_authored_bank()
    by_id = {
        template.question_template_id: (topic_id, template)
        for topic_id, templates in bank.items()
        for template in templates
    }
    chosen: list[tuple[str, int, AuthoredTemplateDef]] = []
    missing: list[str] = []
    for tier, template_id in PINNED_SAMPLE:
        found = by_id.get(template_id)
        if found is None:
            missing.append(template_id)
            continue
        topic_id, template = found
        if template.difficulty_label != tier:
            missing.append(f"{template_id} (now d{template.difficulty_label}, pinned as d{tier})")
            continue
        chosen.append((topic_id, tier, template))
    if missing:
        raise SystemExit(
            "pinned sample no longer matches the bank:\n  "
            + "\n  ".join(missing)
            + "\n\nRe-pin PINNED_SAMPLE and take a FRESH baseline - a before/after "
            "comparison across different items measures the items, not the rubric."
        )
    return chosen


def _fresh_sample() -> list[tuple[str, int, AuthoredTemplateDef]]:
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
    parser.add_argument(
        "--fresh-sample",
        action="store_true",
        help="Re-select from the bank instead of using PINNED_SAMPLE. Invalidates any "
        "before/after comparison - take a new baseline if you use this",
    )
    parser.add_argument(
        "--label", default="run", help="Tag for this run's output, e.g. 'baseline' or 'reanchored'"
    )
    args = parser.parse_args()

    curriculum = load_curriculum()
    sample = _fresh_sample() if args.fresh_sample else _pinned()
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
    reasonings: list[tuple[int, int, str, str]] = []

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
        # D-300: the aggregate says the instrument is compressed; only the rationale says
        # WHAT it is keying on, which is the difference between re-wording an anchor and
        # re-wording the shared scale instruction. D-292 measured the drift and could not act
        # on it because this was never captured.
        reasonings.append(
            (
                tier,
                judge.reviewed_difficulty,
                template.question_template_id,
                judge.difficulty_reasoning,
            )
        )

    print(f"\nspend: {spend:.2f} cents")
    print(f"verdicts: {dict(agreements)}")
    print("\nbank tier -> judged tier:")
    for (asked, judged), count in sorted(matrix.items()):
        print(f"  d{asked} -> d{judged}: {count}")

    exact = agreements["agrees"]
    scored = exact + agreements["disagrees"]
    within_one = sum(n for (a, b), n in matrix.items() if abs(a - b) <= 1)
    if scored:
        print(
            f"\n[{args.label}] vs the bank's STORED tier: exact {exact}/{scored} "
            f"({exact / scored * 100:.0f}%), within one {within_one}/{scored} "
            f"({within_one / scored * 100:.0f}%)"
        )
        drift = sum((b - a) * n for (a, b), n in matrix.items()) / scored
        print(
            f"[{args.label}] mean signed drift {drift:+.2f} tiers "
            f"(negative = judged easier than the bank says)"
        )

        # D-300: the number that actually measures the instrument. Reported beside the one
        # above rather than instead of it, because the two answer different questions and
        # quoting only the first is what sent D-292 and D-296 after the wrong lever.
        first = await _authoring_ratings([t.question_template_id for _, _, t in sample])
        comparable: list[tuple[int, int]] = []
        for _tier, new, tid, _why in reasonings:
            original = first.get(tid, (None, ""))[0]
            if original is not None:
                comparable.append((int(original), new))
        if comparable:
            same = sum(1 for a, b in comparable if a == b)
            near = sum(1 for a, b in comparable if abs(a - b) <= 1)
            n = len(comparable)
            print(
                f"[{args.label}] vs THE JUDGE'S OWN first rating: exact {same}/{n} "
                f"({same / n * 100:.0f}%), within one {near}/{n} ({near / n * 100:.0f}%)"
            )
            provenance = collections.Counter(
                first[tid][1] for _t, _n, tid, _w in reasonings if tid in first
            )
            print(
                f"[{args.label}] how these items got their stored tier: "
                f"{dict(provenance.most_common())}"
            )
            print("           `flagged` keeps the SLOT's tier, so for those items the stored")
            print("           label was never a judge rating - see D-300 and")
            print("           scripts/measure_tier_label_provenance.py for the bank-wide share.")

    print("\nwhat the judge said it was keying on:")
    for tier, judged, template_id, reasoning in reasonings:
        mark = "  " if tier == judged else "->"
        print(f"{mark} d{tier} judged {judged}  {template_id}")
        print(f"     {reasoning.strip()[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
