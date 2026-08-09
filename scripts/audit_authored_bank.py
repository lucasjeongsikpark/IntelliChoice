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

from intellichoice_curriculum.ai_pipeline import (
    _AUTHORED_REVIEW_MAX_TOKENS,
    _SOLVER_SYSTEM_PROMPT,
    _call,
    solver_objections,
)
from intellichoice_curriculum.authored_bank import AuthoredTemplateDef, load_authored_bank
from intellichoice_curriculum.pipeline_cli import _build_gateway, underlying_model
from intellichoice_curriculum.settings import get_pipeline_settings
from intellichoice_shared.bedrock import BedrockTask, SolverPayload, SolverResponse

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


def _rendered(item: AuthoredTemplateDef) -> str:
    """What the student is actually shown - context block first (D-196).

    Passing the stem alone is the bug D-196 measured: an item whose numbers live in the
    context block and whose question lives in the stem becomes an unanswerable fragment,
    and the solver correctly reports that the problem is incomplete. The item is fine; the
    payload was not.
    """
    context = (item.context_block or "").strip()
    return f"{context}\n{item.stem}".strip() if context else item.stem


async def _audit_item(
    gateway, item: AuthoredTemplateDef, spend: float
) -> tuple[ItemVerdict, float]:
    verdict = ItemVerdict(
        question_template_id=item.question_template_id,
        topic_id=item.topic_id,
        declared=item.correct_option,
    )
    payload = SolverPayload(
        rendered_question=_rendered(item),
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
            max_output_tokens=_AUTHORED_REVIEW_MAX_TOKENS,
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


def _plan(topic_id: str | None) -> list[AuthoredTemplateDef]:
    banks = load_authored_bank()
    if topic_id is not None:
        if topic_id not in banks:
            raise SystemExit(
                f"no authored bank file for topic {topic_id!r} (have: {sorted(banks)})"
            )
        banks = {topic_id: banks[topic_id]}
    return [item for templates in banks.values() for item in templates]


def _preflight(items: list[AuthoredTemplateDef], budget_cents: float) -> int:
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
    print(f"  max calls:           {len(items) * _CALLS_PER_ITEM} ({_CALLS_PER_ITEM} per item)")
    print(f"  run budget ceiling:  {budget_cents:.0f} cents")

    if underlying_model(solver_a) == underlying_model(solver_b):
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

    for item in items:
        if spend >= budget_cents:
            print(f"\nrun budget of {budget_cents:.0f} cents reached")
            break
        wrong = next(o for o in ("a", "b", "c", "d") if o != item.correct_option)
        corrupted = item.model_copy(update={"correct_option": wrong})
        verdict, spend = await _audit_item(gateway, corrupted, spend)
        caught += 0 if verdict.agrees else 1
        print("!" if not verdict.agrees else ".", end="", flush=True)
    print()

    total = len(items)
    print(f"\nnegative control: {caught}/{total} deliberately-wrong items caught, "
          f"{spend:.2f} cents")
    if caught < total:
        print(
            f"{total - caught} corrupted item(s) were NOT caught. The audit's agreement "
            f"figure is worth only as much as this number."
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
    items = _plan(args.topic_id)

    if args.self_test:
        items = items[: args.self_test]
    status = _preflight(items, budget)
    if status != 0 or not args.run:
        if status == 0:
            print("\npreflight only. Re-run with --run to spend.")
        return status
    if args.self_test:
        return asyncio.run(_self_test(items, budget))
    return asyncio.run(_run(items, budget))


if __name__ == "__main__":
    sys.exit(main())
