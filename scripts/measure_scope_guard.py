"""Measure SPEC §5.19.2's Scope Guard + Intent Router in isolation, in both directions.

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/measure_scope_guard.py --repeat 2

**Why this exists, and why it is not the D-220 sweep.** D-220 measured the access hint by
driving the whole pipeline against staging: 38 questions, ~48 cents, ~20 minutes. It found
that 4 of those 38 never reached retrieval at all - the scope guard classified a
tutor-procedure question the prompt explicitly lists as in scope as out of scope - but it
could not iterate on that finding, because every re-measurement cost another 48 cents and
paid for retrieval, reranking and synthesis to re-answer a question that was rejected in the
first call. The scope guard is *one* Haiku call with a ~250-word prompt. Measured on its own
it is roughly two orders of magnitude cheaper, which is what makes repeat runs affordable -
and D-220's other finding was that single runs of this system are samples, not constants.

**The prompt is imported, never copied** (`SCOPE_AND_INTENT_SYSTEM_PROMPT`), as are the
payload and response models. A measurement script that restates the thing it measures is
measuring its own transcription; that is exactly the trap AUD-C-25 caught in the probe
harness, where a hand-written rule diverged from the shipped one.

**Three classes, with deliberately opposite expectations.** Scoring only the questions that
*should* get in, and calling a prompt better when more of them do, rewards a guard that
admits everything - and the guard exists to refuse early and cheaply. So every run scores
both directions and prints them side by side:

  gated       (probe_eval.yaml)       in-scope organizational questions whose answer happens
                                      to live in a role-gated document. Must be `in_scope`,
                                      and `document_qa`, or they never reach retrieval and
                                      the access probe is never consulted. This is the class
                                      D-220 found failing.
  in_scope    (qa_coverage_eval.yaml) `grounded`, `paraphrase` and `no_answer` - ordinary
                                      public organizational questions, including ones nothing
                                      answers. Must be `in_scope`. These are what the prompt
                                      was tuned against (AUD-F-19, D-111), so they are the
                                      regression class.
  off_topic   (qa_coverage_eval.yaml) `out_of_scope` - genuinely unrelated. Must stay
                                      `out_of_scope`. **These are the controls.** A change
                                      that recovers gated questions by losing these has not
                                      improved the guard, it has removed it.

`no_source`'s nonsense markers ("zqxveval6 handbook") are excluded, not scored: a real model
correctly refuses them as off-topic, so they would measure the marker design rather than the
guard (the same reason `include_mock_only=False` drops them from the real-Bedrock eval).

**`--repeat` samples; it does not average away a real change.** Per-case flips are printed
separately from the rates, because a case that answers differently on two identical calls is
a fact about the classifier and not noise to be smoothed. D-175's rule: sample size is chosen
before the run, not after seeing the result.

Bedrock use: exactly one `SCOPE_AND_INTENT` call per case per repeat, nothing written
anywhere, no database. Spend accumulates into `session_spend_cents` so `--budget-cents`
actually binds (the bug AUD-C-22 found in the probe harness, where every call passed 0.0 and
the ceiling could never be reached).
"""

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml
from chat_api.graph.nodes import SCOPE_AND_INTENT_SYSTEM_PROMPT
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    ScopeAndIntentPayload,
    ScopeAndIntentResponse,
)

# The three classes, and what each one's *correct* answer is. `expected_in_scope` is the
# whole scoring rule for `in_scope` and `off_topic`; `gated` additionally has to route to
# `document_qa`, because in_scope + clarification (or + admin_contact) still never reaches
# retrieval - which is the failure D-220 actually saw.
COVERAGE_IN_SCOPE = ("grounded", "paraphrase", "no_answer")
COVERAGE_OFF_TOPIC = ("out_of_scope",)
# Only `document_qa` reaches `retrieve`. The other three intents are real destinations, so
# they are reported rather than silently folded into "wrong".
RETRIEVAL_INTENT = "document_qa"

# A fourth class, and the only one written here rather than loaded from a fixture, because
# neither fixture contains a single question whose *intent* is the point: `probe_eval.yaml`
# is corpus-derived (every case is a document question) and `qa_coverage_eval.yaml` scores
# refusal and grounding. Without these, a prompt edit that narrows `branch_locator` or
# `admin_contact` scores as a clean improvement in the table above while having silently
# deleted a workflow - D-221 came within one clause of exactly that, since "a city named in
# the question is not the user's location" moved the only `branch_locator` case in the whole
# sweep to `document_qa` and there was nothing left to notice it with.
#
# Deliberately tiny and deliberately obvious: this is a smoke test for three routes, not a
# measurement of routing quality. Anything subtle enough to argue about belongs in a fixture.
INTENT_PROBES = (
    ("intent-locator-1", "Which IntelliChoice branch is closest to me?", "branch_locator"),
    ("intent-locator-2", "What branches do you have near me?", "branch_locator"),
    ("intent-calendar-1", "Add the next tutoring session to my calendar", "calendar"),
    ("intent-calendar-2", "What events are coming up?", "calendar"),
    ("intent-admin-1", "Please send a message to an administrator", "admin_contact"),
    (
        "intent-admin-2",
        "Can you put me in touch with someone at the Dallas branch?",
        "admin_contact",
    ),
)


@dataclass
class _Case:
    case_id: str
    klass: str
    query: str
    expected_in_scope: bool
    # Only the `intent_probe` class sets this; every other class scores scope, and reports
    # intent as a distribution rather than pinning one right answer per case.
    expected_intent: str | None = None


@dataclass
class _Outcome:
    case_id: str
    klass: str
    query: str
    expected_in_scope: bool
    in_scope: bool | None
    intent: str | None
    reasoning: str
    error: str | None = None
    expected_intent: str | None = None

    @property
    def scope_correct(self) -> bool:
        return self.in_scope is not None and self.in_scope == self.expected_in_scope

    @property
    def reaches_retrieval(self) -> bool:
        return bool(self.in_scope) and self.intent == RETRIEVAL_INTENT

    @property
    def routed_correctly(self) -> bool:
        """`intent_probe` only. The other classes have no single right intent."""
        return bool(self.in_scope) and self.intent == self.expected_intent


@dataclass
class _Spend:
    """Cumulative real spend, threaded into every call so the session budget binds."""

    cents: float = 0.0

    def add(self, amount: float) -> float:
        self.cents += amount
        return self.cents


def _load_cases(probe_fixture: Path, coverage_fixture: Path, query_field: str) -> list[_Case]:
    cases: list[_Case] = []
    probe = yaml.safe_load(probe_fixture.read_text())["cases"]
    for case in probe:
        if case.get("category") != "gated":
            continue
        # AUD-C-21: `human_query` is the blind rewrite - how a person asks. Cases where the
        # generator's call failed have no `human_query`; fall back rather than drop, since
        # scope classification (unlike the probe's distance measurement) is not comparing a
        # question against the chunk it came from.
        query = case.get(query_field) or case["query"]
        cases.append(_Case(case["id"], "gated", query, expected_in_scope=True))

    coverage = yaml.safe_load(coverage_fixture.read_text())["cases"]
    for case in coverage:
        category = case.get("category")
        if case.get("mock_only"):
            continue
        if category in COVERAGE_IN_SCOPE:
            cases.append(_Case(case["id"], "in_scope", case["query"], expected_in_scope=True))
        elif category in COVERAGE_OFF_TOPIC:
            cases.append(_Case(case["id"], "off_topic", case["query"], expected_in_scope=False))

    cases.extend(
        _Case(case_id, "intent_probe", query, expected_in_scope=True, expected_intent=intent)
        for case_id, query, intent in INTENT_PROBES
    )
    return cases


def _gateway(region: str, model: str, budget_cents: float) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        model_registry={BedrockTask.SCOPE_AND_INTENT: model},
        session_budget_cents=budget_cents,
    )


async def _gather_limited[T](
    factories: Sequence[Callable[[], Awaitable[T]]], limit: int
) -> list[T]:
    """Bounded concurrency - the gateway retries and breaks its own circuit, so a wide
    fan-out turns a measurement run into a throttling experiment.
    """
    semaphore = asyncio.Semaphore(limit)

    async def _run(factory: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await factory()

    return list(await asyncio.gather(*(_run(f) for f in factories)))


async def _classify(gateway: BedrockGateway, case: _Case, spend: _Spend) -> _Outcome:
    """The shipped call, argument for argument - same task, prompt, payload and response
    model as `chat_api.graph.nodes.scope_guard`, including `max_output_tokens=512`.
    """
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.SCOPE_AND_INTENT,
            system_prompt=SCOPE_AND_INTENT_SYSTEM_PROMPT,
            payload=ScopeAndIntentPayload(standalone_query=case.query),
            response_model=ScopeAndIntentResponse,
            max_output_tokens=512,
            session_spend_cents=spend.cents,
        )
    except BedrockGatewayError as exc:
        # A failed call is recorded as a failed call, never scored as a misclassification -
        # `scope_guard` itself returns `scope=None` here rather than claiming a verdict, and
        # a table that counted an outage as an out-of-scope decision would be the same false
        # statement moved into a spreadsheet.
        spend.add(exc.cost_cents)
        return _Outcome(
            case.case_id,
            case.klass,
            case.query,
            case.expected_in_scope,
            None,
            None,
            "",
            str(exc),
            case.expected_intent,
        )
    spend.add(result.cost_cents)
    return _Outcome(
        case.case_id,
        case.klass,
        case.query,
        case.expected_in_scope,
        result.value.in_scope,
        result.value.intent,
        result.value.reasoning,
        None,
        case.expected_intent,
    )


def _report(outcomes: list[list[_Outcome]], spend: _Spend, repeat: int) -> None:
    print(f"\n{repeat} repeat(s), {len(outcomes[0])} cases, {spend.cents:.2f} cents\n")
    print(f"{'class':<12} {'n':>4} {'scope ok':>10} {'reaches retrieval':>19}")
    print("-" * 48)
    flat = [o for run in outcomes for o in run]
    for klass in ("gated", "in_scope", "off_topic", "intent_probe"):
        rows = [o for o in flat if o.klass == klass]
        if not rows:
            continue
        ok = sum(1 for o in rows if o.scope_correct)
        # Only meaningful for the classes expected in scope; an off-topic question that
        # reaches retrieval is a control loss already counted in the `scope ok` column.
        # `intent_probe` reports its own routing instead - reaching retrieval is the
        # *failure* there, since each of its cases belongs to another workflow.
        if klass == "off_topic":
            third = "-"
        elif klass == "intent_probe":
            third = f"routed {sum(1 for o in rows if o.routed_correctly)}/{len(rows)}"
        else:
            third = f"{sum(1 for o in rows if o.reaches_retrieval):>4}/{len(rows)}"
        print(f"{klass:<12} {len(rows):>4} {ok:>5}/{len(rows):<4} {third:>19}")

    errors = [o for o in flat if o.error]
    if errors:
        print(f"\n{len(errors)} call(s) failed and were not scored:")
        for outcome in errors[:10]:
            print(f"  {outcome.case_id}: {outcome.error}")

    print("\nintent distribution, in-scope classes:")
    for klass in ("gated", "in_scope"):
        counts = Counter(o.intent for o in flat if o.klass == klass and o.in_scope)
        if counts:
            print(f"  {klass:<10} " + ", ".join(f"{k}={v}" for k, v in counts.most_common()))

    print("\nfailures (any repeat):")
    seen: set[str] = set()
    for outcome in flat:
        if outcome.error:
            continue
        if outcome.klass == "off_topic":
            passed = outcome.scope_correct
        elif outcome.klass == "intent_probe":
            passed = outcome.routed_correctly
        else:
            passed = outcome.scope_correct and outcome.reaches_retrieval
        if passed or outcome.case_id in seen:
            continue
        seen.add(outcome.case_id)
        verdict = "in_scope" if outcome.in_scope else "out_of_scope"
        print(f"  [{outcome.klass}] {outcome.case_id}: {verdict}/{outcome.intent}")
        print(f"      {outcome.query}")
    if not seen:
        print("  none")

    if repeat > 1:
        print("\nflips across repeats (same question, different verdict):")
        flipped = False
        for case_id in {o.case_id for o in flat}:
            verdicts = {
                (o.in_scope, o.intent) for run in outcomes for o in run if o.case_id == case_id
            }
            if len(verdicts) > 1:
                flipped = True
                rendered = ", ".join(
                    f"{'in' if s else 'out'}/{i}"
                    for s, i in sorted(verdicts, key=lambda v: (bool(v[0]), str(v[1])))
                )
                print(f"  {case_id}: {rendered}")
        if not flipped:
            print("  none - every case answered identically on every repeat")


async def _run(args: argparse.Namespace) -> int:
    cases = _load_cases(Path(args.probe_fixture), Path(args.coverage_fixture), args.query_field)
    if args.dry_run:
        for case in cases:
            print(f"[{case.klass}] {case.case_id}: {case.query}")
        print(f"\n{len(cases)} cases x {args.repeat} repeat(s)")
        return 0

    spend = _Spend()
    gateway = _gateway(args.region, args.model, args.budget_cents)
    runs: list[list[_Outcome]] = []
    for _ in range(args.repeat):
        runs.append(
            await _gather_limited(
                [lambda c=case: _classify(gateway, c, spend) for case in cases],
                args.concurrency,
            )
        )
    _report(runs, spend, args.repeat)
    if args.dump:
        Path(args.dump).write_text(json.dumps([[asdict(o) for o in run] for run in runs], indent=2))
        print(f"\nmeasurements written to {args.dump}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-fixture", default="apps/chat-api/tests/fixtures/probe_eval.yaml")
    parser.add_argument(
        "--coverage-fixture", default="apps/chat-api/tests/fixtures/qa_coverage_eval.yaml"
    )
    parser.add_argument(
        "--query-field",
        default="human_query",
        choices=["query", "human_query"],
        help="AUD-C-21: `human_query` is the blind rewrite that models how a person asks, "
        "and is what D-220 measured. `query` is the chunk-derived phrasing.",
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument(
        "--repeat",
        type=int,
        default=2,
        help="Runs every case this many times. D-220: one run of this system is a sample.",
    )
    parser.add_argument(
        "--budget-cents",
        type=float,
        default=50.0,
        help="Hard session ceiling, enforced by threading cumulative spend into every call. "
        "A full 76-case run at 2 repeats measured well under a cent per repeat.",
    )
    parser.add_argument("--dump", help="Write this run's raw outcomes to a JSON file.")
    parser.add_argument(
        "--dry-run", action="store_true", help="List the cases without calling Bedrock."
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
