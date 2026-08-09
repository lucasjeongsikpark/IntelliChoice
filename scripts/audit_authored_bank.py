"""Run the two-solver panel over the *already-approved* authored bank (D-211's open risk).

Run with:

    uv run python scripts/audit_authored_bank.py                     # preflight, calls nothing
    uv run python scripts/audit_authored_bank.py --run               # the paid pass
    uv run python scripts/audit_authored_bank.py --run --topic-id place_value

**Why this exists.** Every one of the bank's approved items passed the deterministic §5.8.5 gate,
and none passed a solver panel. That gap is not incidental: `check_sympy_independent_solve` verifies
*equation → answer* and its own docstring says what it cannot do — "it verifies equation -> answer,
never situation -> equation. A model that equates two robots' *rates* instead of their *totals* gets
a faithfully-solved wrong answer." The pipeline answers that with two independent solvers who read
the scenario blind and must land on the same option. Items authored by the *pipeline* got that;
the 80 hand-authored ones (D-222/D-223/D-225/D-228) did not, and they are now the majority of the
bank.

**This changes nothing.** It reads the bank files, calls the two solver slots, and prints a report.
No database write, no file write, no approval or retirement. What it produces is a list for a human
to act on, because "two models disagreed with the author" is evidence, not a verdict — an item can
be correct and still be solved wrongly by a model, which is exactly why the pipeline records solver
objections rather than deleting on them.

**Cost.** Two calls per item, routed through the same two distinct task slots the pipeline uses
(`QUESTION_GENERATION` and `QUESTION_REVIEW`) so Solver A and Solver B resolve to different models —
their agreement is worthless if they are one model asked twice. Spend is accumulated and checked
against `--run-budget-cents` *between* items, and every call carries the gateway's timeout, bounded
retry and max-token ceiling. Preflight is the default and calls nothing, per this repo's convention
that a paid run is never the thing that happens when you forget an argument.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass, field

from intellichoice_curriculum.adjudications import (
    LAPSE_REASON,
    JudgedItem,
    fingerprint,
    judge_inputs,
    load_adjudications,
    partition_findings,
)
from intellichoice_curriculum.ai_pipeline import (
    _AUTHORED_JUDGE_MAX_TOKENS,
    _AUTHORED_JUDGE_TIMEOUT_S,
    _AUTHORED_SOLVER_MAX_TOKENS,
    _SOLVER_SYSTEM_PROMPT,
    _call,
    solver_objections,
)
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.pipeline_cli import _build_gateway, underlying_model
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import (
    BedrockTask,
    QuestionJudgeResponse,
    SolverPayload,
    SolverResponse,
)

# The pipeline's own thresholds, reused rather than restated so this audit cannot drift into
# judging the bank by a standard the pipeline would not apply (`ai_pipeline.judge_difficulty`
# rejects at 2; the hint-quality gate flags at or below 3).
_DIFFICULTY_REJECT_GAP = 2
_HINT_QUALITY_FLOOR = 3

_CALLS_PER_ITEM = 2


@dataclass
class ItemVerdict:
    question_template_id: str
    topic_id: str
    declared: str
    solver_a: str | None = None
    solver_b: str | None = None
    objections: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def agrees(self) -> bool:
        return not self.objections and self.error is None


async def _audit_item(
    gateway, item: AuthoredTemplateDef, spend: float
) -> tuple[ItemVerdict, float]:
    verdict = ItemVerdict(
        question_template_id=item.question_template_id,
        topic_id=item.topic_id,
        declared=item.correct_option,
    )
    payload = SolverPayload(
        rendered_question=item.rendered_for_model(),
        option_a=item.option_a,
        option_b=item.option_b,
        option_c=item.option_c,
        option_d=item.option_d,
    )
    solvers: list[SolverResponse] = []
    for name, task in (
        ("A", BedrockTask.QUESTION_GENERATION),
        ("B", BedrockTask.QUESTION_REVIEW),
    ):
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
        if error is not None or not isinstance(response, SolverResponse):
            verdict.error = f"solver {name} call failed: {error}"
            return verdict, spend
        solvers.append(response)

    verdict.solver_a = solvers[0].selected_option
    verdict.solver_b = solvers[1].selected_option
    verdict.objections = solver_objections(solvers[0], solvers[1], declared=item.correct_option)
    return verdict, spend


async def _judge_item(
    gateway, item: AuthoredTemplateDef, spend: float
) -> tuple[dict, float]:
    """One blind judge call. The judge never sees the declared tier (D-194), which is what
    makes the comparison below worth making at all.
    """
    payload, anchors, system_prompt = judge_inputs(item)
    response, cost, error = await _call(
        gateway,
        task=BedrockTask.QUESTION_JUDGE,
        system_prompt=system_prompt,
        payload=payload,
        response_model=QuestionJudgeResponse,
        session_spend_cents=spend,
        max_output_tokens=_AUTHORED_JUDGE_MAX_TOKENS,
        timeout_s=_AUTHORED_JUDGE_TIMEOUT_S,
    )
    spend += cost
    if error is not None or not isinstance(response, QuestionJudgeResponse):
        return {"id": item.question_template_id, "error": error or "no response"}, spend

    flags = []
    gap = abs(response.reviewed_difficulty - item.difficulty_label)
    if gap >= _DIFFICULTY_REJECT_GAP:
        flags.append(
            f"difficulty: declared {item.difficulty_label}, judge {response.reviewed_difficulty}"
        )
    if response.is_ambiguous:
        flags.append("ambiguous")
    if not response.is_aligned:
        flags.append("not aligned to its skill")
    if not response.is_age_appropriate:
        flags.append("not age appropriate")
    if not response.is_internally_consistent:
        flags.append("internally inconsistent")
    if response.hint_quality_score <= _HINT_QUALITY_FLOOR:
        flags.append(f"hint quality {response.hint_quality_score}")
    return {
        "id": item.question_template_id,
        "declared": item.difficulty_label,
        "reviewed": response.reviewed_difficulty,
        "gap": gap,
        "hint_quality": response.hint_quality_score,
        "flags": flags,
        "reasoning": response.difficulty_reasoning,
        "content_fingerprint": fingerprint(payload, anchors),
        "instrument_fingerprint": fingerprint(payload, anchors, system_prompt),
    }, spend


async def _judge(items: list[AuthoredTemplateDef], budget_cents: float) -> int:
    settings = get_pipeline_settings()
    gateway = _build_gateway(settings)
    spend = 0.0
    results: list[dict] = []

    for item in items:
        if spend >= budget_cents:
            print(f"\nrun budget of {budget_cents:.0f} cents reached")
            break
        result, spend = await _judge_item(gateway, item, spend)
        results.append(result)
        print("E" if result.get("error") else ("!" if result["flags"] else "."), end="", flush=True)
    print()

    scored = [r for r in results if not r.get("error")]
    errored = [r for r in results if r.get("error")]
    flagged = [r for r in scored if r["flags"]]

    print(f"\njudged {len(scored)} items ({len(errored)} call failures), {spend:.2f} cents")
    print(f"  clean:                 {len(scored) - len(flagged)}")
    print(f"  flagged:               {len(flagged)}")

    # The control. A judge that answers the same tier every time produces small gaps on any
    # bank centred near that tier, and would read as excellent calibration. So the spread of
    # its *own* ratings is reported next to the agreement figure, always.
    spread: dict[int, int] = {}
    exact = 0
    for r in scored:
        spread[r["reviewed"]] = spread.get(r["reviewed"], 0) + 1
        exact += 1 if r["gap"] == 0 else 0
    print(f"  exact tier agreement:  {exact}/{len(scored)}")
    print(f"  judge's own tiers:     {dict(sorted(spread.items()))}")
    # Dispersion, not distinctness. The first version of this check fired only when the
    # judge returned *one* tier for everything, and on the first real run it returned
    # {2: 20, 5: 1} - two distinct values, so it passed, while still being a constant for
    # every practical purpose. A control that a near-degenerate distribution walks through
    # is not a control.
    if scored:
        dominant = max(spread.values())
        if dominant / len(scored) >= 0.8:
            tier = max(spread, key=lambda k: spread[k])
            print(
                f"  CONTROL FAILED: the judge answered {tier} for {dominant} of "
                f"{len(scored)} items, so the agreement figure above measures the judge's "
                f"constant rather than this bank's calibration."
            )

    # D-236: split the flagged list by what a human has already decided about it. Without
    # this, every re-run reports D-235's twelve known-wrong judgements again, in the same
    # words, indistinguishable from twelve new ones - and the fastest thing a reader learns
    # is that the flagged list is mostly noise.
    verdicts = load_adjudications()
    findings = partition_findings(
        [
            JudgedItem(
                question_template_id=r["id"],
                declared_difficulty=r["declared"],
                reviewed_difficulty=r["reviewed"],
                flagged=bool(r["flags"]),
                content_fingerprint=r["content_fingerprint"],
                instrument_fingerprint=r["instrument_fingerprint"],
            )
            for r in scored
        ],
        verdicts,
    )
    by_id = {r["id"]: r for r in scored}
    print(f"    new:                 {len(findings.new)}")
    print(f"    already adjudicated: {len(findings.known)}")
    print(f"    verdict lapsed:      {len(findings.lapsed)}")
    print(f"  adjudications on file: {len(verdicts)}")

    def show(rows: list[JudgedItem], heading: str) -> None:
        if not rows:
            return
        print(f"\n--- {heading}")
        for item in rows:
            r = by_id[item.question_template_id]
            print(f"\n  {r['id']}  (declared {r['declared']}, judge {r['reviewed']})")
            for flag in r["flags"]:
                print(f"    - {flag}")
            reason = LAPSE_REASON.get(findings.status[item.question_template_id])
            if reason:
                v = verdicts[item.question_template_id]
                print(f"    ! verdict from {v.decided_in} no longer applies: {reason}")
            print(f"    {r['reasoning'][:160]}")

    show(findings.new, f"NEW - {len(findings.new)} finding(s) nobody has ruled on")
    show(findings.lapsed, f"LAPSED - {len(findings.lapsed)} verdict(s) that no longer apply")
    show(findings.known, f"already adjudicated - {len(findings.known)} repeat(s), not news")
    # An `upheld` item the judge now agrees with. Nothing is wrong with it, so it is in no
    # flagged bucket - but the instrument moved, which is the whole question the tier-5 work
    # is asking, and a suppression quietly becoming unnecessary is how that would be missed.
    for item in findings.moot:
        r = by_id[item.question_template_id]
        v = verdicts[item.question_template_id]
        print(
            f"\n  {r['id']}: {v.decided_in} recorded the judge as wrong (it said "
            f"{v.judge_difficulty}); it now agrees at {r['reviewed']}. The verdict is spent."
        )
    for r in errored:
        print(f"\n  {r['id']}  call failed: {r['error']}")
    return 0


def _plan(
    topic_id: str | None,
    difficulties: list[int] | None = None,
    per_cell: int | None = None,
) -> list[AuthoredTemplateDef]:
    banks = load_authored_bank()
    if topic_id is not None:
        if topic_id not in banks:
            raise SystemExit(
                f"no authored bank file for topic {topic_id!r} (have: {sorted(banks)})"
            )
        banks = {topic_id: banks[topic_id]}

    selected: list[AuthoredTemplateDef] = []
    for templates in banks.values():
        if difficulties is None:
            selected.extend(templates)
            continue
        # Stratified by (topic, tier) so a before/after runs on the same cells rather than
        # on whatever the file order happens to put first. `--difficulty 1 --difficulty 5`
        # is the sharp version of the calibration question: a rubric that cannot separate
        # the easiest tier from the hardest *within one topic* is not calibrating anything.
        for tier in difficulties:
            in_tier = [t for t in templates if t.difficulty_label == tier]
            selected.extend(in_tier[:per_cell] if per_cell else in_tier)
    return selected


def _preflight(
    items: list[AuthoredTemplateDef], budget_cents: float, *, judge: bool = False
) -> int:
    settings = get_pipeline_settings()
    solver_a = settings.bedrock_generation_model_id
    solver_b = settings.bedrock_review_model_id
    by_topic: dict[str, int] = {}
    for item in items:
        by_topic[item.topic_id] = by_topic.get(item.topic_id, 0) + 1

    print("audit preflight - nothing was called and nothing was written")
    print(f"  provider:            {settings.bedrock_provider}")
    print(f"  solver A model:      {solver_a}")
    print(f"  solver B model:      {solver_b}")
    for topic, count in sorted(by_topic.items()):
        print(f"  {topic:<24} {count} items")
    print(f"  items:               {len(items)}")
    per_item = 1 if judge else _CALLS_PER_ITEM
    print(f"  max calls:           {len(items) * per_item} ({per_item} per item)")
    print(f"  run budget ceiling:  {budget_cents:.0f} cents")

    if not judge and underlying_model(solver_a) == underlying_model(solver_b):
        print(
            "\nREFUSED: Solver A and Solver B resolve to the same model, so their agreement "
            "would be one opinion counted twice."
        )
        return 1
    return 0


async def _self_test(items: list[AuthoredTemplateDef], budget_cents: float) -> int:
    """Score the audit in the direction it is *not* trying to prove (D-221's rule).

    Every item's declared answer is moved to a different option, so every one of them is now
    wrong by construction. A panel that is working objects to all of them. A panel that has
    silently stopped firing - a prompt that no longer parses, a payload built from the wrong
    field (D-196), a response model whose `selected_option` is always None - agrees with all
    of them, and would have scored a clean 127/127 on the real bank for the same reason.
    """
    settings = get_pipeline_settings()
    gateway = _build_gateway(settings)
    spend = 0.0
    caught = 0
    missed = 0
    errored = 0

    for item in items:
        if spend >= budget_cents:
            print(f"\nrun budget of {budget_cents:.0f} cents reached")
            break
        wrong = next(o for o in ("a", "b", "c", "d") if o != item.correct_option)
        corrupted = item.model_copy(update={"correct_option": wrong})
        verdict, spend = await _audit_item(gateway, corrupted, spend)
        # A failed call is NOT a catch, and conflating the two is a real defect this script
        # shipped with for one run: `agrees` is False for both an objection and an error, so
        # a Solver B that failed every single call scored a perfect negative control. Caught
        # while smoke-testing a cross-vendor Solver B, which failed exactly that way.
        if verdict.error is not None:
            errored += 1
            mark = "E"
        elif verdict.objections:
            caught += 1
            mark = "!"
        else:
            missed += 1
            mark = "."
        print(mark, end="", flush=True)
    print()

    scored = caught + missed
    print(f"\nnegative control: {caught}/{scored} deliberately-wrong items caught "
          f"({errored} call failures, not scored), {spend:.2f} cents")
    if errored:
        print(
            f"{errored} call(s) failed. A failure is not evidence either way - a panel whose "
            f"calls all fail catches nothing and must not read as catching everything."
        )
    if missed:
        print(
            f"{missed} corrupted item(s) were NOT caught. The audit's agreement figure is "
            f"worth only as much as this number."
        )
    return 0


async def _run(items: list[AuthoredTemplateDef], budget_cents: float) -> int:
    settings = get_pipeline_settings()
    gateway = _build_gateway(settings)
    spend = 0.0
    verdicts: list[ItemVerdict] = []

    for index, item in enumerate(items, start=1):
        if spend >= budget_cents:
            print(f"run budget of {budget_cents:.0f} cents reached after {index - 1} items")
            break
        verdict, spend = await _audit_item(gateway, item, spend)
        verdicts.append(verdict)
        mark = "." if verdict.agrees else "!"
        print(mark, end="", flush=True)
    print()

    flagged = [v for v in verdicts if not v.agrees]
    print(f"\naudited {len(verdicts)} of {len(items)} items, spent {spend:.2f} cents")
    print(f"both solvers agreed with the author on {len(verdicts) - len(flagged)}")
    for verdict in flagged:
        detail = verdict.error or "; ".join(verdict.objections)
        print(f"\n  {verdict.question_template_id}")
        print(f"    declared={verdict.declared} solver_a={verdict.solver_a} "
              f"solver_b={verdict.solver_b}")
        print(f"    {detail}")
    if flagged:
        print(
            f"\n{len(flagged)} item(s) to review by hand. A disagreement is evidence, not a "
            f"verdict - read the item before changing anything."
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="actually call the models; without it this is a preflight that calls nothing",
    )
    parser.add_argument(
        "--topic-id", default=None, help="audit one topic instead of the whole bank"
    )
    parser.add_argument(
        "--difficulty",
        type=int,
        action="append",
        default=None,
        help="restrict to these tiers; repeat the flag. Use with --per-cell to stratify",
    )
    parser.add_argument(
        "--per-cell",
        type=int,
        default=None,
        help="at most N items per (topic, tier) cell, so a before/after runs on the same set",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help=(
            "run the blind judge instead of the solver panel: difficulty calibration, "
            "ambiguity, alignment, age-appropriateness, consistency and hint quality"
        ),
    )
    parser.add_argument(
        "--self-test",
        type=int,
        default=0,
        metavar="N",
        help=(
            "negative control: re-run the first N items with the declared answer moved to a "
            "wrong option, and report how many the panel catches. A 127/127 pass means "
            "nothing without this - a check that never fires scores identically"
        ),
    )
    parser.add_argument(
        "--run-budget-cents",
        type=float,
        default=None,
        help="hard spend ceiling for this run (default: the configured pipeline ceiling)",
    )
    args = parser.parse_args()

    budget = (
        args.run_budget_cents
        if args.run_budget_cents is not None
        else get_pipeline_settings().bedrock_run_budget_cents
    )
    items = _plan(args.topic_id, args.difficulty, args.per_cell)

    if args.self_test:
        items = items[: args.self_test]
    status = _preflight(items, budget, judge=args.judge)
    if status != 0 or not args.run:
        if status == 0:
            print("\npreflight only. Re-run with --run to spend.")
        return status
    if args.self_test:
        return asyncio.run(_self_test(items, budget))
    if args.judge:
        return asyncio.run(_judge(items, budget))
    return asyncio.run(_run(items, budget))


if __name__ == "__main__":
    sys.exit(main())
