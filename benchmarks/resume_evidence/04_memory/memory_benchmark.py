"""E4.1 / E4.2 / E4.3 - the memory-consolidation benchmark.

Run with (from the repository root):

    export BENCH_DB=postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice_e4_bench

    # E4.1, Tier 1, $0 - mock provider, N = 1,000
    DATABASE_URL=$BENCH_DB uv run python \\
      benchmarks/resume_evidence/04_memory/memory_benchmark.py --arm mock --students 1000

    # the deterministic-transition lane (also Tier 1, $0, no provider at all)
    DATABASE_URL=... uv run python .../memory_benchmark.py --arm scripted

    # E4.2, Tier 2 - real Bedrock, N = 25, HARD ceiling 300 cents, opt-in
    eval "$(aws configure export-credentials --profile <profile> --format env)"
    MEMORY_BENCH_REAL_BEDROCK=1 AWS_REGION=us-east-1 \\
      MEMORY_BENCH_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0 \\
      DATABASE_URL=... uv run python .../memory_benchmark.py --arm real --students 25

`--arm real` is the only arm that costs money and it cannot start without
`MEMORY_BENCH_REAL_BEDROCK=1`, so nothing here can run in CI or under `pytest` by
accident. Every arm needs an **explicit** `DATABASE_URL` pointing at a benchmark database
(see `--database-url` below); the runner refuses to start against the dev database.

## The three arms, and the line between them

The measurement plan's own rule (and AUD-C-05's lesson) is that a mock-model result is
never a quality result: what a mock eval measures is the mock. That line is structural
here, not editorial.

- **`mock`** - `MockBedrockProvider`. Its consolidation stand-in derives facts from
  keywords in the code-rendered event summaries this generator itself produced, so its
  facts are correct by construction and say nothing about model quality. What it *does*
  measure honestly is everything provider-independent at a scale a paid arm cannot reach:
  exact input-token accounting, batching and call counts, `events_dropped`, the
  compression ratio, provenance coverage, and the deterministic promotion / mastery /
  evidence screens. Those are properties of `consolidation.py`, and they are what this arm
  reports.
- **`scripted`** - **no provider at all**. A fake gateway returns pre-built
  `MemoryUpdateResponse` values, so the deterministic transition machinery can be driven
  into states no provider reaches on its own (see the finding below) and the four screens
  can be given inputs a well-behaved model would never produce. This measures *code*,
  and is labelled as such everywhere.
- **`real`** - real Bedrock. The only arm any quality number may be quoted from.

## The finding that shaped the mock arm

`_memory_consolidation_json` pairs `weak_skill` with `polarity="negative"` and `strength`
with `polarity="positive"`, always. The contradiction protocol in `consolidation.py`
triggers on an **opposite-polarity candidate for an existing live fact with the same
`(fact_type, skill_id)`** - so under the mock, a student who succeeds and then fails does
not get their `strength` fact demoted; they get a second, coexisting `weak_skill` fact.
`contested` and `superseded` are therefore unreachable under the mock provider, and the
`scripted` arm exists because of it. The mock arm reports the `polarity_flip` scenario as
what actually happens (two live facts, and which one `top_fact_for_skill` serves), not as
a pass or a fail.

## Environment labels

- `mock` arm: **mock-model simulation, local** (local Postgres, `MockBedrockProvider`).
- `scripted` arm: **deterministic code measurement, local** (local Postgres, no provider).
- `real` arm: **real-model evaluation (Haiku 4.5), local data** (local Postgres, real
  Bedrock in `us-east-1`).

No arm touches staging, production, or `../IntelliChoice-web`.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import dataclasses
import importlib.util
import json
import os
import pathlib
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import DEFAULT_DATABASE_URL, create_engine, create_session_factory
from intellichoice_db.models.memory import SemanticMemory
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import LIVE_STATUSES, MemoryRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_memory.consolidation import (
    _MAX_CALLS_PER_STUDENT,
    _MAX_EVENT_TOKENS_PER_CALL,
    consolidate_student_window,
)
from intellichoice_memory.events import CHAT_TURN, render_event_summary
from intellichoice_shared.bedrock import (
    BedrockGenerationResult,
    BedrockTask,
    MemoryConsolidationPayload,
    MemoryEventSummary,
    MemoryExistingFact,
    MemoryFactCandidate,
    MemoryUpdateResponse,
    estimate_input_tokens,
)
from sqlalchemy import select, text

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "e4_synthetic_histories", HERE / "synthetic_histories.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gen = _load_generator()

# --- pricing, restated from the gateway's own table so a projection cannot drift --------
#
# `ResilientBedrockGateway._MODEL_RATES_PER_1K_CENTS` is module-private; these are the
# Haiku 4.5 entries from it (0.1 cents/1k input, 0.5 cents/1k output). The real arm never
# uses them - it reports the gateway's own `cost_cents`, which is what was actually
# billed-shaped. They exist only to price the mock arm's **projection** and E4.3's arm-B
# arithmetic, both of which are labelled as projections wherever they appear.
HAIKU_INPUT_CENTS_PER_1K = 0.1
HAIKU_OUTPUT_CENTS_PER_1K = 0.5
DEFAULT_REAL_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# `gateway._HARD_MAX_INPUT_TOKENS`. A payload above this is **refused, never truncated**,
# which is the structural half of E4.3: a raw history over this line cannot be sent at all.
HARD_MAX_INPUT_TOKENS = 32_000

# The system prompt consolidation actually sends, plus the inlined response schema, both
# of which the gateway counts toward the input ceiling. Measured once at import rather
# than guessed, because leaving them out would under-count exactly the payloads closest
# to the ceiling.
from intellichoice_memory.consolidation import _SYSTEM_PROMPT  # noqa: E402

_SCHEMA_JSON = json.dumps(MemoryUpdateResponse.model_json_schema(), separators=(",", ":"))
FIXED_OVERHEAD_TOKENS = estimate_input_tokens(_SYSTEM_PROMPT, _SCHEMA_JSON)

# --- E4.2 spend guards ------------------------------------------------------------------
#
# Three ceilings, smallest first, copied from the established pattern in
# `apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py`:
#
#  1. `PER_STUDENT_BUDGET_CENTS` - the gateway's own per-session budget, so one pathological
#     student cannot spend the run's whole allowance. Sized from the bound rather than from
#     a guess: `_MAX_CALLS_PER_STUDENT` (4) x `_MAX_EVENT_TOKENS_PER_CALL` (20,000) is 80k
#     input tokens = 8 cents, plus at most 4 x 4,000 output tokens = 8 cents, per window;
#     three windows is a worst case of ~48 cents. 25 is above what any standard student in
#     this corpus can reach (~5 cents) and below a third of the run ceiling.
#  2. `RUN_BUDGET_CENTS` - a HARD 300, checked after every window by summing the gateway's
#     own reported `cost_cents`. The run **aborts** rather than truncating, because a
#     partial run scored as if complete is a wrong measurement, and the abort is loud.
#     `MEMORY_BENCH_RUN_BUDGET_CENTS` can only *tighten* it: a value above the default is
#     ignored, because a run must never be able to raise its own spend limit from the
#     environment.
#  3. a pre-flight projection, refused before the first paid call if it exceeds the
#     remaining ceiling - so an over-large corpus fails for free rather than half way in.
PER_STUDENT_BUDGET_CENTS = 25.0
RUN_BUDGET_CENTS_HARD = 300.0
RUN_BUDGET_CENTS = min(
    float(os.getenv("MEMORY_BENCH_RUN_BUDGET_CENTS") or RUN_BUDGET_CENTS_HARD),
    RUN_BUDGET_CENTS_HARD,
)


class RunBudgetExceeded(RuntimeError):
    """Raised to abort the real arm. Never caught inside the per-student loop."""


# --- observation records ----------------------------------------------------------------


@dataclass
class WindowObservation:
    window: int
    raw_event_count: int
    # The EVENT half of the payload only (events + system prompt + schema). Kept separate
    # from `full_payload_tokens` because this is the number E4.3's arm-B arithmetic needs -
    # "what would it cost to send this history as context" - and because it is the only one
    # a re-score can reconstruct from persisted rows, so the two paths report the same
    # quantity rather than two subtly different ones.
    raw_payload_tokens: int
    # What the gateway actually priced and ceiling-checked for this call: the above plus
    # the student's existing live facts, which really are sent on every call.
    full_payload_tokens: int
    batches: int
    calls_attempted: int
    calls_failed: int
    events_dropped: int
    mastery_conflicts: int
    budget_stopped: bool
    calls_hit_output_ceiling: int
    cache_write_tokens: int
    conservative_cost_cents: float
    added: int
    updated: int
    contested: int
    expired: int
    cost_cents: float
    existing_facts_at_start: int
    over_input_ceiling: bool
    wall_s: float


@dataclass
class FactObservation:
    fact_type: str
    skill_id: str | None
    polarity: str
    status: str
    confidence: float
    evidence_event_ids: list[str]
    evidence_resolved: int
    evidence_total: int


@dataclass
class ScoredExpectation:
    scenario: str
    skill_id: str
    expected_fact_type: str | None
    expected_status: str | None
    expected_served: bool
    observed_status: str | None
    observed_fact_type: str | None
    observed_polarity: str | None
    served_fact_type: str | None
    served_polarity: str | None
    status_correct: bool
    served_correct: bool
    # Two deliberately laxer readings, reported beside the strict one rather than instead
    # of it. `status_correct` demands the exact planted `fact_type`, which is right for a
    # deterministic provider and too strict for a real model: a student who is failing a
    # skill can be described as `weak_skill`, `misconception` or `hint_dependence` and all
    # three are defensible. Scoring those as errors by fiat would report a vocabulary
    # difference as a quality failure. So:
    #   `any_live_fact_on_skill` - did the pipeline learn ANYTHING about the planted skill
    #     (a coverage question: did the planted signal survive at all?);
    #   `polarity_match_any` - does any live fact on that skill carry the planted polarity
    #     (a direction question: is what it learned pointing the right way?).
    any_live_fact_on_skill: bool
    polarity_match_any: bool


@dataclass
class StudentResult:
    student_external_id: str
    student_class: str
    windows: list[WindowObservation]
    facts: list[FactObservation]
    scored: list[ScoredExpectation]
    unplanted_extra_facts: int
    unsupported_facts: int
    total_raw_events: int
    total_raw_tokens: int
    live_fact_tokens: int
    served_fact_tokens: int
    compression_ratio: float | None
    total_cost_cents: float
    total_conservative_cost_cents: float
    total_calls: int
    total_calls_hit_output_ceiling: int
    total_failed_calls: int
    total_events_dropped: int
    cumulative_history_tokens: int
    cumulative_over_ceiling: bool

    def as_json(self) -> dict:
        return {
            "student_external_id": self.student_external_id,
            "student_class": self.student_class,
            "windows": [dataclasses.asdict(w) for w in self.windows],
            # `evidence_event_ids` is deliberately NOT serialised. It is ~28% of a
            # 1,000-student artifact and adds nothing a reader can use: every provenance
            # number in this program is derived from `evidence_resolved`/`evidence_total`,
            # which are kept, and the ids themselves are opaque uuids that resolve only
            # against a benchmark database that is truncated after the run.
            "facts": [
                {k: v for k, v in dataclasses.asdict(f).items() if k != "evidence_event_ids"}
                for f in self.facts
            ],
            "scored": [dataclasses.asdict(s) for s in self.scored],
            "unplanted_extra_facts": self.unplanted_extra_facts,
            "unsupported_facts": self.unsupported_facts,
            "total_raw_events": self.total_raw_events,
            "total_raw_tokens": self.total_raw_tokens,
            "live_fact_tokens": self.live_fact_tokens,
            "served_fact_tokens": self.served_fact_tokens,
            "compression_ratio": self.compression_ratio,
            "total_cost_cents": round(self.total_cost_cents, 6),
            "total_conservative_cost_cents": round(self.total_conservative_cost_cents, 6),
            "total_calls": self.total_calls,
            "total_calls_hit_output_ceiling": self.total_calls_hit_output_ceiling,
            "total_failed_calls": self.total_failed_calls,
            "total_events_dropped": self.total_events_dropped,
            "cumulative_history_tokens": self.cumulative_history_tokens,
            "cumulative_over_ceiling": self.cumulative_over_ceiling,
        }


# --- exact token accounting --------------------------------------------------------------


async def _event_summaries(
    memory_repo: MemoryRepository,
    tutor_chat_repo: TutorChatMessageRepository,
    student_external_id: str,
    start: datetime,
    end: datetime,
) -> list[MemoryEventSummary]:
    """Rebuild EXACTLY the `MemoryEventSummary` list `_consolidate_events` would build.

    Duplicating those ~15 lines rather than importing a private helper is deliberate: the
    thing being measured is the size of what the gateway is sent, and the only estimate
    that cannot drift from it is one produced from the same three inputs (the event rows,
    the chat-text join, `render_event_summary`). `test_memory_benchmark.py` asserts this
    function's output matches what a real consolidation call received.
    """
    events = await memory_repo.list_events_in_window(student_external_id, start, end)
    messages = await tutor_chat_repo.list_for_student_in_window(student_external_id, start, end)
    chat_text = {m.message_id: m.redacted_student_message for m in messages}

    def _text_for(event) -> str | None:
        if event.event_type != CHAT_TURN:
            return None
        message_id = event.structured_payload.get("tutor_chat_message_id")
        return chat_text.get(message_id) if isinstance(message_id, str) else None

    return [
        MemoryEventSummary(
            event_id=e.event_id,
            event_type=e.event_type,
            topic_id=e.topic_id,
            skill_id=e.skill_id,
            summary=render_event_summary(
                e.event_type, e.structured_payload, chat_text=_text_for(e)
            ),
        )
        for e in events
    ]


def payload_tokens(summaries: list[MemoryEventSummary], existing: list[MemoryExistingFact]) -> int:
    """What one consolidation call's input costs, counted the way the gateway counts it.

    `estimate_input_tokens` over the *serialised* payload plus the system prompt and the
    inlined schema - the same three parts `ResilientBedrockGateway._estimated_input_tokens`
    sums, so this number and the gateway's ceiling check are the same measurement.
    """
    payload = MemoryConsolidationPayload(
        events=summaries, existing_facts=existing, allowed_fact_types=[]
    )
    return estimate_input_tokens(payload.model_dump_json()) + FIXED_OVERHEAD_TOKENS


def fact_tokens(facts: list[SemanticMemory]) -> int:
    """The serialised size of a student's live memory, in the shape it is actually sent -
    `MemoryExistingFact`, which is what `_consolidate_one_batch` puts on the wire.
    """
    if not facts:
        return 0
    payload = [
        MemoryExistingFact(
            semantic_memory_id=f.semantic_memory_id,
            fact_type=f.fact_type,
            skill_id=f.skill_id,
            fact_text=f.fact_text,
            status=f.status,
            confidence=f.confidence,
        )
        for f in facts
    ]
    return estimate_input_tokens(json.dumps([p.model_dump() for p in payload]))


# --- scoring (pure) -----------------------------------------------------------------------


def score_expectations(
    planted: list[dict],
    live_facts_by_skill: dict[str, list[FactObservation]],
    served_by_skill: dict[str, FactObservation | None],
) -> list[ScoredExpectation]:
    """Score one student's planted facts against what actually ended up in memory.

    Pure: takes plain values, returns plain values, no database and no clock, so the
    scoring rules are unit-testable without Postgres. Two independent judgements per
    expectation, because they can and do disagree:

    - **`status_correct`** - the lifecycle state of the fact for this
      `(skill, expected_fact_type)`. `expected_status is None` means "nothing live for this
      skill at all", which is the correct outcome for both mastery-conflict scenarios.
    - **`served_correct`** - what `top_fact_for_skill` would hand a tutor payload. This is
      the operational question ("does the read path carry the right thing?") and it is the
      only sense in which this pipeline has a notion of memory *retrieval*: there is no
      candidate set and no ranking, so there is no recall@k to compute.
    """
    scored: list[ScoredExpectation] = []
    for expectation in planted:
        skill_id = expectation["skill_id"]
        expected_type = expectation["expected_fact_type"]
        expected_status = expectation["expected_status"]
        expected_served = expectation["expected_served"]
        candidates = live_facts_by_skill.get(skill_id, [])

        if expected_status is None:
            observed = candidates[0] if candidates else None
            status_correct = not candidates
        else:
            observed = next((f for f in candidates if f.fact_type == expected_type), None)
            status_correct = observed is not None and observed.status == expected_status

        served = served_by_skill.get(skill_id)
        if expected_served:
            served_correct = (
                served is not None and served.polarity == expectation["expected_polarity"]
            )
        else:
            served_correct = served is None

        scored.append(
            ScoredExpectation(
                scenario=expectation["scenario"],
                skill_id=skill_id,
                expected_fact_type=expected_type,
                expected_status=expected_status,
                expected_served=expected_served,
                observed_status=observed.status if observed else None,
                observed_fact_type=observed.fact_type if observed else None,
                observed_polarity=observed.polarity if observed else None,
                served_fact_type=served.fact_type if served else None,
                served_polarity=served.polarity if served else None,
                status_correct=status_correct,
                served_correct=served_correct,
                any_live_fact_on_skill=bool(candidates),
                polarity_match_any=any(
                    f.polarity == expectation["expected_polarity"] for f in candidates
                )
                if expectation["expected_polarity"]
                else not candidates,
            )
        )
    return scored


def percentiles(values: list[float]) -> dict[str, float | None]:
    """p10 / median / p90 with explicit `None` when there is nothing to summarise.

    `statistics.quantiles` needs at least two points; returning `None` rather than
    silently reusing the single value keeps a one-sample run from reading like a
    distribution.
    """
    if not values:
        return {"p10": None, "median": None, "p90": None, "n": 0}
    if len(values) == 1:
        return {"p10": None, "median": values[0], "p90": None, "n": 1}
    deciles = statistics.quantiles(values, n=10, method="inclusive")
    return {
        "p10": round(deciles[0], 4),
        "median": round(statistics.median(values), 4),
        "p90": round(deciles[8], 4),
        "n": len(values),
    }


# --- gateways ------------------------------------------------------------------------------


class ScriptedGateway:
    """Returns pre-built `MemoryUpdateResponse` values, one per `generate_structured` call.

    Same shape as `packages/memory/tests/test_consolidation.py::_FakeGateway`. It exists so
    the deterministic transition code can be driven into states no provider produces on its
    own - see the module docstring's finding about `(fact_type, skill_id)` keying.
    """

    def __init__(self, responses: list[MemoryUpdateResponse]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def generate_structured(self, *, task: BedrockTask, **kwargs) -> BedrockGenerationResult:
        del task
        self.calls += 1
        return BedrockGenerationResult(
            value=self._responses.pop(0),
            input_tokens=0,
            output_tokens=0,
            cost_cents=0.0,
            model_id="scripted-no-provider",
            repaired=False,
        )

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


# Published Anthropic prompt-cache multipliers on Bedrock, relative to the base input rate.
# Used ONLY by the conservative estimate below; nothing here changes what the gateway bills.
CACHE_WRITE_RATE_MULTIPLIER = 1.25
CACHE_READ_RATE_MULTIPLIER = 0.1


@dataclass
class CallRecord:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    stop_reason: str
    gateway_cost_cents: float
    conservative_cost_cents: float
    max_output_tokens: int

    @property
    def hit_output_ceiling(self) -> bool:
        return self.stop_reason == "max_tokens"


class MeteringGateway:
    """A pass-through wrapper that records what each call actually consumed.

    Two things the benchmark needs and `ConsolidationResult` cannot carry:

    1. **`stop_reason`.** A consolidation response that hits `max_output_tokens` comes back
       from Converse as an empty tool input (`{}`), and `MemoryUpdateResponse` validates it
       cleanly because every one of its three fields defaults to `[]`. So the gateway's
       `if truncated:` guard is never reached, the caller sees `added=0, calls_failed=0`,
       and a truncated consolidation is indistinguishable from a student who had nothing to
       consolidate. Counting `stop_reason == "max_tokens"` is the only way to see it from
       outside, and it is the single most important number the real arm produces.
    2. **Cache-write tokens.** With `cachePoint` blocks in play (D-203), a cold call reports
       almost all of its input under `cacheWriteInputTokens` and only a couple of dozen
       under `inputTokens` - and `ResilientBedrockGateway._cost_cents` prices
       `input_tokens` alone. The gateway's own comment says as much ("not yet billed off
       separately"), but the direction matters here: a spend ceiling enforced against a
       number that omits most of the input is not the ceiling it claims to be. This wrapper
       prices cache traffic at the published multipliers and the run guard uses whichever
       figure is larger, so the 300-cent cap holds against the pessimistic reading.

    It measures; it never changes a request, and product code is untouched.
    """

    def __init__(
        self,
        inner,
        *,
        input_rate: float,
        output_rate: float,
        output_token_floor: int | None = None,
    ) -> None:
        self._inner = inner
        self._input_rate = input_rate
        self._output_rate = output_rate
        # E4.2 arm B, and the ONLY thing this wrapper ever changes about a request.
        #
        # `max_output_tokens_for` derives the output budget from the number of EXISTING
        # facts, on the stated reasoning that new facts "do not scale with the input". A
        # student with events across fourteen skills is a counter-example: the model has
        # fourteen legitimate new-fact candidates and needs ~1,600 output tokens to emit
        # them, against a floor of 1,280 at zero existing facts. Arm A runs the shipped
        # budget and measures what happens; arm B raises it to the gateway's own hard
        # ceiling and measures what the same model does with room, on the same students.
        # Without arm B, "planted-fact recall = 0" is unattributable between the model and
        # the budget - and an unattributable number is not a measurement.
        #
        # **Arm B is not the shipped configuration** and every artifact it produces says so.
        #
        # **Post-D-460/R1 the gap this wrapper opens is much smaller, on purpose.** The
        # shipped floor is now 2,560 at zero existing facts, so arm B no longer separates
        # "truncated" from "had room" - it separates "2,560" from "4,000". The paragraph
        # above is kept verbatim because it is the reasoning the E4 artifacts were written
        # under, and rewriting it would make those artifacts unreadable against their own
        # harness. A post-fix run uses arm A (no floor); arm B remains available as the
        # same ablation against the new base.
        self._output_token_floor = output_token_floor
        self.calls: list[CallRecord] = []

    async def generate_structured(self, **kwargs):
        if self._output_token_floor is not None:
            kwargs["max_output_tokens"] = max(
                kwargs.get("max_output_tokens", 0), self._output_token_floor
            )
        result = await self._inner.generate_structured(**kwargs)
        conservative = (
            result.input_tokens / 1000 * self._input_rate
            + result.cache_write_tokens / 1000 * self._input_rate * CACHE_WRITE_RATE_MULTIPLIER
            + result.cache_read_tokens / 1000 * self._input_rate * CACHE_READ_RATE_MULTIPLIER
            + result.output_tokens / 1000 * self._output_rate
        )
        self.calls.append(
            CallRecord(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_write_tokens=result.cache_write_tokens,
                stop_reason=result.stop_reason,
                gateway_cost_cents=result.cost_cents,
                conservative_cost_cents=conservative,
                max_output_tokens=kwargs.get("max_output_tokens", 0),
            )
        )
        return result

    async def create_embedding(self, **kwargs):
        return await self._inner.create_embedding(**kwargs)

    def drain(self) -> list[CallRecord]:
        drained, self.calls = self.calls, []
        return drained


def build_mock_gateway() -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=MockBedrockProvider(),
        model_registry={BedrockTask.MEMORY_CONSOLIDATION: "anthropic.claude-haiku-4-5"},
        call_timeout_s=120.0,
        max_retries=2,
        circuit_failure_threshold=5,
        circuit_cooldown_s=30.0,
        session_budget_cents=1_000_000.0,
    )


def build_real_gateway(model_id: str, region: str) -> ResilientBedrockGateway:
    """The real lane's gateway, with the per-student ceiling as its session budget.

    `session_budget_cents=PER_STUDENT_BUDGET_CENTS` is guard #1: the gateway raises
    `CostBudgetExceededError` before a call that would cross it, and `consolidate_student_
    window` converts that into `budget_stopped=True` rather than a failure - so one
    pathological student stops early instead of spending the run's allowance. The per-run
    ceiling is enforced by the caller, because the gateway has no notion of a run.
    """
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider

    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        model_registry={BedrockTask.MEMORY_CONSOLIDATION: model_id},
        call_timeout_s=120.0,
        max_retries=2,
        circuit_failure_threshold=5,
        circuit_cooldown_s=30.0,
        session_budget_cents=PER_STUDENT_BUDGET_CENTS,
    )


# --- the per-student run --------------------------------------------------------------------


async def _score_student_from_database(
    memory_repo: MemoryRepository,
    plan,
    *,
    skill_ids: list[str],
    windows: list[WindowObservation],
    total_events: int,
    cumulative_tokens: int,
) -> StudentResult:
    """Everything E4 measures ABOUT a student, derived from persisted rows alone.

    Split out of `run_student` so the scoring half has no dependency on the
    consolidation half: the same code produces the numbers whether the facts were
    written seconds ago by this process or by a run that has since aborted on its
    spend ceiling. One implementation, so a re-scored result and a live one cannot
    disagree.
    """
    # --- read back what memory now holds -------------------------------------------------
    all_facts = await memory_repo.list_facts_for_student(
        plan.external_id, statuses=("provisional", "active", "contested", "superseded")
    )
    live_facts = [f for f in all_facts if f.status in LIVE_STATUSES]

    # Provenance is re-derived, not trusted: every cited event id is looked up again and
    # checked to belong to this student. `_verify_evidence` should have guaranteed it at
    # write time; measuring it independently is what turns "guaranteed by construction"
    # into a number.
    all_ids = sorted({eid for f in all_facts for eid in f.evidence_event_ids})
    resolved = await memory_repo.get_events_by_ids(all_ids)
    owned_ids = {e.event_id for e in resolved if e.student_external_id == plan.external_id}

    fact_observations: list[FactObservation] = []
    for fact in all_facts:
        ids = list(fact.evidence_event_ids)
        fact_observations.append(
            FactObservation(
                fact_type=fact.fact_type,
                skill_id=fact.skill_id,
                polarity=str(fact.structured_value.get("polarity", "positive")),
                status=fact.status,
                confidence=fact.confidence,
                evidence_event_ids=ids,
                evidence_resolved=sum(1 for i in ids if i in owned_ids),
                evidence_total=len(ids),
            )
        )

    live_by_skill: dict[str, list[FactObservation]] = {}
    for observation, fact in zip(fact_observations, all_facts, strict=True):
        if fact.status in LIVE_STATUSES and fact.skill_id:
            live_by_skill.setdefault(fact.skill_id, []).append(observation)

    planted_records = [
        {
            "scenario": p.scenario,
            "skill_id": skill_ids[p.skill_slot],
            "expected_fact_type": p.expected_fact_type,
            "expected_polarity": p.expected_polarity,
            "expected_status": p.expected_status,
            "expected_served": p.expected_served,
        }
        for p in plan.planted
    ]
    served_by_skill: dict[str, FactObservation | None] = {}
    for record in planted_records:
        top = await memory_repo.top_fact_for_skill(plan.external_id, record["skill_id"])
        served_by_skill[record["skill_id"]] = (
            FactObservation(
                fact_type=top.fact_type,
                skill_id=top.skill_id,
                polarity=str(top.structured_value.get("polarity", "positive")),
                status=top.status,
                confidence=top.confidence,
                evidence_event_ids=list(top.evidence_event_ids),
                evidence_resolved=0,
                evidence_total=len(top.evidence_event_ids),
            )
            if top is not None
            else None
        )

    scored = score_expectations(planted_records, live_by_skill, served_by_skill)
    planted_skills = {r["skill_id"] for r in planted_records}
    unplanted = sum(
        1
        for f in fact_observations
        if f.status in LIVE_STATUSES and f.skill_id not in planted_skills
    )
    unsupported = sum(1 for f in fact_observations if f.evidence_resolved == 0)

    live_tokens = fact_tokens(live_facts)
    served_tokens = fact_tokens([f for f in live_facts if f.status == "active"][:1])
    total_raw_tokens = sum(w.raw_payload_tokens for w in windows)

    return StudentResult(
        student_external_id=plan.external_id,
        student_class=plan.student_class,
        windows=windows,
        facts=fact_observations,
        scored=scored,
        unplanted_extra_facts=unplanted,
        unsupported_facts=unsupported,
        total_raw_events=total_events,
        total_raw_tokens=total_raw_tokens,
        live_fact_tokens=live_tokens,
        served_fact_tokens=served_tokens,
        compression_ratio=(total_raw_tokens / live_tokens) if live_tokens else None,
        total_cost_cents=sum(w.cost_cents for w in windows),
        total_conservative_cost_cents=sum(w.conservative_cost_cents for w in windows),
        total_calls=sum(w.calls_attempted for w in windows),
        total_calls_hit_output_ceiling=sum(w.calls_hit_output_ceiling for w in windows),
        total_failed_calls=sum(w.calls_failed for w in windows),
        total_events_dropped=sum(w.events_dropped for w in windows),
        cumulative_history_tokens=cumulative_tokens,
        cumulative_over_ceiling=cumulative_tokens > HARD_MAX_INPUT_TOKENS,
    )


async def run_student(
    session,
    plan,
    config,
    *,
    gateway,
    skill_ids: list[str],
    bounds: list[tuple[datetime, datetime]],
    run_spend_cents: float,
    run_conservative_cents: float,
    run_budget_cents: float | None,
) -> StudentResult:
    """Consolidate one student window by window, then read and score their memory.

    Windows run **in order** and each is a separate `consolidate_student_window` call, which
    is exactly what the deployed weekly job does (`consolidate_cli.py`). Doing it in one
    call over three weeks would be a different measurement: `existing_facts` is re-read per
    call, so the window boundary is what lets a later week reconfirm (and therefore promote)
    or contradict what an earlier week wrote.
    """
    memory_repo = MemoryRepository(session)
    mastery_repo = MasteryRepository(session)
    tutor_chat_repo = TutorChatMessageRepository(session)

    windows: list[WindowObservation] = []
    spend = run_spend_cents
    # Separate from `spend` on purpose. The gateway's `session_budget_cents` is guard #1 -
    # the PER-STUDENT ceiling - and it is only that if the running total handed to it
    # accumulates across this student's windows. Passing 0.0 each window (the obvious
    # thing) would silently turn a 25-cent per-student ceiling into a 25-cent per-WINDOW
    # ceiling, i.e. three times the intended bound with nothing in the output saying so.
    student_spend = 0.0
    conservative_spend = run_conservative_cents
    cumulative_tokens = 0
    total_raw_events = 0

    for index, (start, end) in enumerate(bounds):
        summaries = await _event_summaries(
            memory_repo, tutor_chat_repo, plan.external_id, start, end
        )
        existing = await memory_repo.list_facts_for_student(
            plan.external_id, statuses=LIVE_STATUSES
        )
        existing_payload = [
            MemoryExistingFact(
                semantic_memory_id=f.semantic_memory_id,
                fact_type=f.fact_type,
                skill_id=f.skill_id,
                fact_text=f.fact_text,
                status=f.status,
                confidence=f.confidence,
            )
            for f in existing
        ]
        raw_tokens = payload_tokens(summaries, [])
        full_tokens = payload_tokens(summaries, existing_payload)
        cumulative_tokens += raw_tokens
        total_raw_events += len(summaries)

        started = time.perf_counter()
        result = await consolidate_student_window(
            memory_repo=memory_repo,
            mastery_repo=mastery_repo,
            tutor_chat_repo=tutor_chat_repo,
            gateway=gateway,
            student_external_id=plan.external_id,
            window_start=start,
            window_end=end,
            session_spend_cents=student_spend,
        )
        elapsed = time.perf_counter() - started
        records = gateway.drain() if isinstance(gateway, MeteringGateway) else []
        conservative = sum(r.conservative_cost_cents for r in records)
        # The per-student ceiling handed to the gateway has to stay the gateway's OWN
        # number: it is what the gateway compares against internally, and feeding it a
        # different figure would make its `CostBudgetExceededError` fire against an
        # accounting it does not use. The conservative figure guards the RUN ceiling below,
        # which is this benchmark's to enforce.
        spend += result.cost_cents
        student_spend += result.cost_cents
        conservative_spend += conservative

        windows.append(
            WindowObservation(
                window=index,
                raw_event_count=len(summaries),
                raw_payload_tokens=raw_tokens,
                full_payload_tokens=full_tokens,
                # `calls_attempted` is the batch count the run actually made; a
                # budget-stopped student can have fewer calls than batches, and reporting
                # the attempted count keeps that visible rather than inferred.
                batches=result.calls_attempted,
                calls_attempted=result.calls_attempted,
                calls_failed=result.calls_failed,
                events_dropped=result.events_dropped,
                mastery_conflicts=result.mastery_conflicts,
                budget_stopped=result.budget_stopped,
                calls_hit_output_ceiling=sum(1 for r in records if r.hit_output_ceiling),
                cache_write_tokens=sum(r.cache_write_tokens for r in records),
                conservative_cost_cents=round(conservative, 6),
                added=result.added,
                updated=result.updated,
                contested=result.contested,
                expired=result.expired,
                cost_cents=result.cost_cents,
                existing_facts_at_start=len(existing_payload),
                over_input_ceiling=full_tokens > HARD_MAX_INPUT_TOKENS,
                wall_s=round(elapsed, 4),
            )
        )
        # Whichever accounting is higher stops the run. Enforcing only the gateway's own
        # figure would let a run whose input is billed as cache writes spend well past the
        # ceiling while every printed number said it was inside it.
        worst_case_spend = max(spend, conservative_spend)
        if run_budget_cents is not None and worst_case_spend > run_budget_cents:
            raise RunBudgetExceeded(
                f"run ceiling of {run_budget_cents:.1f} cents crossed at "
                f"{worst_case_spend:.2f} cents (gateway-reported {spend:.2f}, conservative "
                f"{conservative_spend:.2f}) while consolidating {plan.external_id} window "
                f"{index}. Aborting rather than truncating - a partial run scored as if "
                "complete is a wrong measurement."
            )

    return await _score_student_from_database(
        memory_repo,
        plan,
        skill_ids=skill_ids,
        windows=windows,
        total_events=total_raw_events,
        cumulative_tokens=cumulative_tokens,
    )


# --- aggregation ------------------------------------------------------------------------------


def aggregate(results: list[StudentResult], *, arm: str, config, model_id: str) -> dict:
    """Every headline number, each with its own numerator and denominator.

    No rate in here is ever emitted as a bare percentage: the plan's evidence rule is that
    a rate carries n and N, and the only way to hold that is to build the summary out of
    pairs rather than out of floats.
    """
    ratios = [r.compression_ratio for r in results if r.compression_ratio]
    per_scenario: dict[str, dict[str, int]] = {}
    for result in results:
        for scored in result.scored:
            bucket = per_scenario.setdefault(
                scored.scenario,
                {
                    "status_correct": 0,
                    "served_correct": 0,
                    "any_live_fact_on_skill": 0,
                    "polarity_match_any": 0,
                    "n": 0,
                },
            )
            bucket["n"] += 1
            bucket["status_correct"] += int(scored.status_correct)
            bucket["served_correct"] += int(scored.served_correct)
            bucket["any_live_fact_on_skill"] += int(scored.any_live_fact_on_skill)
            bucket["polarity_match_any"] += int(scored.polarity_match_any)

    total_facts = sum(len(r.facts) for r in results)
    facts_with_resolved_evidence = sum(
        1
        for r in results
        for f in r.facts
        if f.evidence_total and f.evidence_resolved == f.evidence_total
    )
    facts_with_any_evidence = sum(1 for r in results for f in r.facts if f.evidence_total)

    lifecycle: dict[str, int] = {}
    for result in results:
        for fact in result.facts:
            lifecycle[fact.status] = lifecycle.get(fact.status, 0) + 1

    windows_over_ceiling = sum(1 for r in results for w in r.windows if w.over_input_ceiling)
    total_windows = sum(len(r.windows) for r in results)
    students_over_ceiling = sum(1 for r in results if r.cumulative_over_ceiling)
    oversized_payload_windows = sum(
        1
        for r in results
        for w in r.windows
        if w.existing_facts_at_start > MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS
    )

    total_input_tokens = sum(w.raw_payload_tokens for r in results for w in r.windows)
    projected_input_cents = total_input_tokens / 1000 * HAIKU_INPUT_CENTS_PER_1K

    return {
        "arm": arm,
        "environment": {
            "mock": "mock-model simulation, local",
            "scripted": "deterministic code measurement, local (no provider)",
            "real": "real-model evaluation (Haiku 4.5), local data",
        }[arm],
        "model_id": model_id,
        "git_sha": _git_sha(),
        "generated_at": datetime.now(UTC).isoformat(),
        "config": config.as_dict(),
        "students": len(results),
        "students_by_class": _count_by(results, lambda r: r.student_class),
        "events": {
            "total": sum(r.total_raw_events for r in results),
            "dropped_over_call_cap": sum(r.total_events_dropped for r in results),
            "students_with_drops": sum(1 for r in results if r.total_events_dropped),
        },
        "calls": {
            "total": sum(r.total_calls for r in results),
            "failed": sum(r.total_failed_calls for r in results),
            "max_calls_per_student_per_window": _MAX_CALLS_PER_STUDENT,
            "max_event_tokens_per_call": _MAX_EVENT_TOKENS_PER_CALL,
            # The real arm's headline, and E4's finding (D-460): a call that stopped on
            # `max_tokens` returned an empty tool input, validated as an empty update, and
            # was reported as `added=0` with ZERO failures - so this count was the only
            # place a silently truncated consolidation was visible anywhere.
            #
            # Post-D-460/R1 the gateway fails closed on the stop reason, so a truncated call
            # now also appears in `calls.failed`. This count is kept, and is still the more
            # informative of the two: it separates "truncated" from every other failure
            # class, and on a healthy post-fix run it should be ~0 rather than merely
            # matching `failed`.
            "hit_output_ceiling": sum(r.total_calls_hit_output_ceiling for r in results),
            "students_with_a_truncated_call": sum(
                1 for r in results if r.total_calls_hit_output_ceiling
            ),
        },
        "compression_ratio": percentiles(ratios),
        "tokens": {
            "raw_history_input_tokens_total": total_input_tokens,
            "live_fact_tokens_total": sum(r.live_fact_tokens for r in results),
            "median_raw_tokens_per_window": percentiles(
                [float(w.raw_payload_tokens) for r in results for w in r.windows]
            )["median"],
            "median_live_fact_tokens_per_student": percentiles(
                [float(r.live_fact_tokens) for r in results]
            )["median"],
        },
        "lifecycle_distribution": lifecycle,
        "scenario_scores": per_scenario,
        "provenance": {
            "facts_total": total_facts,
            "facts_with_evidence_ids": facts_with_any_evidence,
            "facts_with_all_evidence_resolving_to_this_student": facts_with_resolved_evidence,
        },
        "students_budget_stopped": sum(
            1 for r in results if any(w.budget_stopped for w in r.windows)
        ),
        "unplanted_extra_live_facts": sum(r.unplanted_extra_facts for r in results),
        "facts_with_no_resolving_evidence": sum(r.unsupported_facts for r in results),
        "input_ceiling": {
            "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
            "windows_over_ceiling": windows_over_ceiling,
            "windows_total": total_windows,
            "students_whose_cumulative_history_exceeds_ceiling": students_over_ceiling,
            "windows_with_oversized_existing_fact_payload": oversized_payload_windows,
            "max_safe_existing_facts": MemoryUpdateResponse.MAX_SAFE_EXISTING_FACTS,
        },
        "cost": {
            "measured_cents_total": round(sum(r.total_cost_cents for r in results), 4),
            "measured_cents_per_student": (
                round(sum(r.total_cost_cents for r in results) / len(results), 4)
                if results
                else None
            ),
            "measured_is_real": arm == "real",
            "projected_input_cents_at_haiku_rates": round(projected_input_cents, 4),
            # Prices cache-write and cache-read traffic the gateway's own `_cost_cents`
            # does not. Reported beside the gateway figure rather than instead of it: the
            # gap between them IS the finding, and collapsing the two would hide it.
            "conservative_cents_total": round(
                sum(r.total_conservative_cost_cents for r in results), 4
            ),
            "cache_write_tokens_total": sum(
                w.cache_write_tokens for r in results for w in r.windows
            ),
        },
    }


def _count_by(results, key) -> dict[str, int]:
    out: dict[str, int] = {}
    for result in results:
        k = key(result)
        out[k] = out.get(k, 0) + 1
    return out


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=ROOT,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - a missing SHA must not fail a measurement run
        return "unknown"


# --- E4.3 --------------------------------------------------------------------------------------


def raw_vs_consolidated_table(results: list[StudentResult]) -> dict:
    """E4.3: the arm-B arithmetic, free and exact.

    Arm B is "send the student's raw event history as context instead of their consolidated
    memory". No model call is needed to price it: the token counts are measured from the
    same corpora with the same serialisation the gateway bills, and the per-request delta is
    those tokens at the published input rate.

    The structural half is the more important one. A payload above the gateway's
    `_HARD_MAX_INPUT_TOKENS` is **refused, not truncated** - so for those students arm B is
    not expensive, it is impossible, which is the property AUD-F-34 demonstrated live at
    215,355 tokens.
    """
    rows = []
    for result in results:
        raw = result.cumulative_history_tokens
        live = result.live_fact_tokens
        served = result.served_fact_tokens
        rows.append(
            {
                "student_external_id": result.student_external_id,
                "student_class": result.student_class,
                "events": result.total_raw_events,
                "raw_history_tokens": raw,
                "live_memory_tokens": live,
                "served_fact_tokens": served,
                "compression_ratio_vs_live_memory": round(raw / live, 3) if live else None,
                "compression_ratio_vs_served_fact": round(raw / served, 3) if served else None,
                "raw_exceeds_input_ceiling": raw > HARD_MAX_INPUT_TOKENS,
                "raw_input_cents_per_request": round(raw / 1000 * HAIKU_INPUT_CENTS_PER_1K, 5),
                "live_memory_input_cents_per_request": round(
                    live / 1000 * HAIKU_INPUT_CENTS_PER_1K, 5
                ),
            }
        )
    sendable = [r for r in rows if not r["raw_exceeds_input_ceiling"]]
    return {
        "rows": rows,
        "students": len(rows),
        "students_raw_over_ceiling": len(rows) - len(sendable),
        "hard_max_input_tokens": HARD_MAX_INPUT_TOKENS,
        "median_raw_tokens": percentiles([float(r["raw_history_tokens"]) for r in rows])["median"],
        "median_live_tokens": percentiles([float(r["live_memory_tokens"]) for r in rows])["median"],
        "median_compression_vs_live": percentiles(
            [
                r["compression_ratio_vs_live_memory"]
                for r in rows
                if r["compression_ratio_vs_live_memory"]
            ]
        )["median"],
        "median_compression_vs_served": percentiles(
            [
                r["compression_ratio_vs_served_fact"]
                for r in rows
                if r["compression_ratio_vs_served_fact"]
            ]
        )["median"],
        "projected_cents_per_request_raw_median": percentiles(
            [r["raw_input_cents_per_request"] for r in rows]
        )["median"],
        "projected_cents_per_request_live_median": percentiles(
            [r["live_memory_input_cents_per_request"] for r in rows]
        )["median"],
        "note": (
            "Arm B is priced, never called. Every token count is measured from the same "
            "serialisation the gateway sends; the cents columns are a PROJECTION at the "
            "published Haiku 4.5 input rate (0.1 cents/1k), not a billed number."
        ),
    }


# --- the scripted lane ---------------------------------------------------------------------------

SCRIPTED_FLIP_STUDENTS = 40
SCRIPTED_SCREEN_STUDENTS = 40

# Pattern-matching strings that are not anyone's data: `.invalid` is reserved by RFC 2606
# and 555-000-0000 is not an assignable North American number. They exist to prove the
# screen fires, and writing a real-looking address here would be the exact thing the screen
# is protecting against.
_PII_PROBE_TEXTS = (
    "Student can be reached at bench-probe@example.invalid for follow-up.",
    "See https://example.invalid/bench-notes for the full history.",
    "Guardian contact on file: 555-000-0000.",
)


def _candidate(
    fact_type: str,
    skill_id: str,
    polarity: str,
    event_ids: list[str],
    text_override: str | None = None,
) -> MemoryFactCandidate:
    return MemoryFactCandidate(
        fact_type=fact_type,
        skill_id=skill_id,
        fact_text=text_override or f"Scripted {polarity} claim about this skill.",
        polarity=polarity,  # type: ignore[arg-type]
        confidence=0.7,
        supporting_event_ids=event_ids,
    )


@dataclass
class ScriptedOutcome:
    lane: str
    check: str
    passed: bool
    detail: str


async def _seed_scripted_student(
    session, *, external_id: str, skill_id: str, topic_id: str, bounds, events_per_window
) -> dict[int, list[str]]:
    """A minimal history for the scripted lane: just enough real events for the scripted
    responses to cite, since `_verify_evidence` refuses a citation that does not resolve to
    a real event of this student inside the window the call was built from.
    """
    from datetime import timedelta

    from intellichoice_db.models.memory import LearningEvent

    memory_repo = MemoryRepository(session)
    ids: dict[int, list[str]] = {}
    for window, (start, _end) in enumerate(bounds):
        per_window = events_per_window[window]
        window_ids = []
        for i in range(per_window):
            row = await memory_repo.record_event(
                LearningEvent(
                    student_external_id=external_id,
                    session_id=f"{external_id}-w{window}-s{i % 2}",
                    event_type="study_outcome",
                    topic_id=topic_id,
                    skill_id=skill_id,
                    structured_payload={
                        "outcome_label": "unresolved",
                        "target_skill_id": skill_id,
                    },
                    occurred_at=start + timedelta(minutes=10 * (i + 1)),
                )
            )
            window_ids.append(row.event_id)
        ids[window] = window_ids
    return ids


async def run_scripted_lane(session, *, topic_id: str, skill_ids: list[str], bounds) -> dict:
    """The two provider-independent lanes: lifecycle transitions, and the four screens.

    **This measures `consolidation.py`, not a model.** Everything the gateway returns here
    is a value this file wrote, so nothing in the result says anything about model quality
    - it says whether the deterministic protocol does what plan §9 specifies when it is
    handed each input. That is worth measuring precisely because it is the half of the
    design that does not depend on the model getting better.
    """
    memory_repo = MemoryRepository(session)
    mastery_repo = MasteryRepository(session)
    tutor_chat_repo = TutorChatMessageRepository(session)
    outcomes: list[ScriptedOutcome] = []

    # --- lane 1: create -> contest -> supersede ------------------------------------------
    for n in range(SCRIPTED_FLIP_STUDENTS):
        external_id = f"bench-scripted-flip-{n:03d}"
        skill_id = skill_ids[n % len(skill_ids)]
        ids = await _seed_scripted_student(
            session,
            external_id=external_id,
            skill_id=skill_id,
            topic_id=topic_id,
            bounds=bounds,
            events_per_window={0: 3, 1: 2, 2: 2},
        )
        gateway = ScriptedGateway(
            [
                MemoryUpdateResponse(
                    facts_to_add=[_candidate("improvement", skill_id, "positive", ids[0])]
                ),
                MemoryUpdateResponse(
                    facts_to_add=[_candidate("improvement", skill_id, "negative", ids[1])]
                ),
                MemoryUpdateResponse(
                    facts_to_add=[_candidate("improvement", skill_id, "negative", ids[2])]
                ),
            ]
        )
        states: list[str] = []
        for window, (start, end) in enumerate(bounds):
            await consolidate_student_window(
                memory_repo=memory_repo,
                mastery_repo=mastery_repo,
                tutor_chat_repo=tutor_chat_repo,
                gateway=gateway,
                student_external_id=external_id,
                window_start=start,
                window_end=end,
                session_spend_cents=0.0,
            )
            facts = await memory_repo.list_facts_for_student(
                external_id, statuses=("provisional", "active", "contested", "superseded")
            )
            first = min(facts, key=lambda f: f.first_observed_at)
            states.append(first.status)
            del window

        facts = await memory_repo.list_facts_for_student(
            external_id, statuses=("provisional", "active", "contested", "superseded")
        )
        superseded = [f for f in facts if f.status == "superseded"]
        live_negative = [
            f
            for f in facts
            if f.status in LIVE_STATUSES and f.structured_value.get("polarity") == "negative"
        ]
        outcomes.append(
            ScriptedOutcome(
                lane="lifecycle",
                check="active_after_first_window",
                passed=states[0] == "active",
                detail=f"status after w0 = {states[0]}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="lifecycle",
                check="contested_after_first_contradiction",
                passed=states[1] == "contested",
                detail=f"status after w1 = {states[1]}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="lifecycle",
                check="superseded_after_second_contradiction",
                passed=states[2] == "superseded" and len(superseded) == 1,
                detail=f"status after w2 = {states[2]}, superseded rows = {len(superseded)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="lifecycle",
                check="replacement_fact_is_live_and_negative",
                passed=len(live_negative) == 1,
                detail=f"live negative facts = {len(live_negative)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="lifecycle",
                check="superseded_fact_points_at_replacement",
                passed=bool(superseded) and superseded[0].superseded_by_id is not None,
                detail=(
                    f"superseded_by_id = {superseded[0].superseded_by_id if superseded else 'n/a'}"
                ),
            )
        )

    # --- lane 2: the four screens ---------------------------------------------------------
    other_student = "bench-scripted-flip-000"
    other_ids = [
        row.event_id
        for row in (
            await MemoryRepository(session).list_events_in_window(
                other_student, bounds[0][0], bounds[0][1]
            )
        )
    ]
    for n in range(SCRIPTED_SCREEN_STUDENTS):
        external_id = f"bench-scripted-screen-{n:03d}"
        skill_id = skill_ids[n % len(skill_ids)]
        ids = await _seed_scripted_student(
            session,
            external_id=external_id,
            skill_id=skill_id,
            topic_id=topic_id,
            bounds=bounds[:1],
            events_per_window={0: 3},
        )
        control_skill = skill_ids[(n + 1) % len(skill_ids)]
        gateway = ScriptedGateway(
            [
                MemoryUpdateResponse(
                    facts_to_add=[
                        # 1. outside plan §9's closed enum
                        _candidate("mood_assessment", skill_id, "negative", ids[0]),
                        # 2. text that trips the PII denylist
                        _candidate(
                            "misconception",
                            skill_id,
                            "negative",
                            ids[0],
                            text_override=_PII_PROBE_TEXTS[n % len(_PII_PROBE_TEXTS)],
                        ),
                        # 3. a citation that resolves to nothing
                        _candidate(
                            "hint_dependence", skill_id, "negative", ["not-a-real-event-id"]
                        ),
                        # 4. a citation that resolves to ANOTHER student's real event
                        _candidate("guessing_pattern", skill_id, "negative", other_ids[:2]),
                        # 5. a well-formed control, so a lane that drops everything is
                        #    distinguishable from a lane whose screens work
                        _candidate("weak_skill", control_skill, "negative", ids[0]),
                    ]
                )
            ]
        )
        await consolidate_student_window(
            memory_repo=memory_repo,
            mastery_repo=mastery_repo,
            tutor_chat_repo=tutor_chat_repo,
            gateway=gateway,
            student_external_id=external_id,
            window_start=bounds[0][0],
            window_end=bounds[0][1],
            session_spend_cents=0.0,
        )
        facts = await memory_repo.list_facts_for_student(
            external_id, statuses=("provisional", "active", "contested", "superseded")
        )
        types = {f.fact_type for f in facts}
        outcomes.append(
            ScriptedOutcome(
                lane="screens",
                check="out_of_enum_fact_type_dropped",
                passed="mood_assessment" not in types,
                detail=f"stored types = {sorted(types)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="screens",
                check="pii_pattern_text_dropped",
                passed="misconception" not in types,
                detail=f"stored types = {sorted(types)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="screens",
                check="unresolvable_evidence_dropped",
                passed="hint_dependence" not in types,
                detail=f"stored types = {sorted(types)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="screens",
                check="cross_student_evidence_dropped",
                passed="guessing_pattern" not in types,
                detail=f"stored types = {sorted(types)}",
            )
        )
        outcomes.append(
            ScriptedOutcome(
                lane="screens",
                check="well_formed_control_accepted",
                passed="weak_skill" in types,
                detail=f"stored types = {sorted(types)}",
            )
        )

    by_check: dict[str, dict[str, int]] = {}
    for outcome in outcomes:
        bucket = by_check.setdefault(f"{outcome.lane}:{outcome.check}", {"passed": 0, "n": 0})
        bucket["n"] += 1
        bucket["passed"] += int(outcome.passed)
    failures = [dataclasses.asdict(o) for o in outcomes if not o.passed]
    return {
        "arm": "scripted",
        "environment": "deterministic code measurement, local (no provider)",
        "git_sha": _git_sha(),
        "generated_at": datetime.now(UTC).isoformat(),
        "flip_students": SCRIPTED_FLIP_STUDENTS,
        "screen_students": SCRIPTED_SCREEN_STUDENTS,
        "checks": by_check,
        "failures": failures[:20],
        "failure_count": len(failures),
    }


# --- database isolation --------------------------------------------------------------------

# Every table this benchmark writes. TRUNCATE rather than DELETE because the corpus is
# hundreds of thousands of rows and a benchmark that takes minutes to clean up is a
# benchmark nobody cleans up.
_BENCH_TABLES = (
    "semantic_memory",
    "learning_events",
    "tutor_chat_messages",
    "mastery",
    "skills",
    "topics",
)


def resolve_database_url(explicit: str | None) -> str:
    """Force the benchmark onto its own database, by name, before anything is written.

    The isolation mechanism is a **separate Postgres database on the same local instance**,
    selected by `DATABASE_URL` (which `intellichoice_db.engine.create_engine` already reads,
    so no product code changes and no second configuration path):

        docker compose exec postgres psql -U intellichoice -d postgres \\
          -c 'CREATE DATABASE intellichoice_e4_bench OWNER intellichoice;'
        cd packages/db && DATABASE_URL=<bench url> uv run alembic upgrade head

    A separate database rather than a schema: the migrations create extensions and are
    written against the default `search_path`, so a schema-scoped run would need alembic
    configuration this benchmark has no business changing.

    **The name must contain `bench`.** This is the guard, and it is deliberately crude: the
    dev database holds e2e and pytest rows, this benchmark TRUNCATEs six tables, and a
    misplaced env var would otherwise be indistinguishable from a correct run until the
    dev data was gone.
    """
    url = explicit or os.environ.get("DATABASE_URL") or ""
    if not url:
        raise SystemExit(
            "refusing to run: set DATABASE_URL (or --database-url) to a dedicated benchmark "
            f"database. The dev default ({DEFAULT_DATABASE_URL}) is never used by this file."
        )
    database = url.rsplit("/", 1)[-1].split("?")[0]
    if "bench" not in database:
        raise SystemExit(
            f"refusing to run against database {database!r}: this benchmark TRUNCATEs "
            f"{', '.join(_BENCH_TABLES)}, so its database name must contain 'bench'."
        )
    return url


async def reset_tables(session) -> None:
    await session.execute(
        text(f"TRUNCATE TABLE {', '.join(_BENCH_TABLES)} RESTART IDENTITY CASCADE")
    )


async def table_counts(session) -> dict[str, int]:
    counts = {}
    for table in _BENCH_TABLES:
        result = await session.execute(text(f"SELECT count(*) FROM {table}"))
        counts[table] = int(result.scalar_one())
    return counts


# --- the real arm's pre-flight ---------------------------------------------------------------


async def probe_model(gateway, model_id: str) -> tuple[bool, str, float]:
    """D-273's lesson, applied before any money is spent: **AVAILABLE is not invocable.**

    A model can be listed by `bedrock list-foundation-models`, be enabled in the account,
    and still fail every `InvokeModel` for this principal. The recorded 2026-08-11
    invocability stratum expired by its own rule, and `settings.py`'s default consolidation
    model is known not to be invocable by the staging task role - so a run that assumes and
    then discovers otherwise has burned its setup time for nothing.

    One structured call with the smallest legal payload (`max_output_tokens` at the schema's
    own floor), costing a fraction of a cent. Returns `(ok, detail, cost_cents)`.
    """
    payload = MemoryConsolidationPayload(
        events=[
            MemoryEventSummary(
                event_id="probe-0",
                event_type="study_outcome",
                summary="Probe event. Reply with an empty update.",
            )
        ],
        existing_facts=[],
        allowed_fact_types=["weak_skill"],
    )
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.MEMORY_CONSOLIDATION,
            system_prompt="Reply with empty lists. This is an invocability probe.",
            payload=payload,
            response_model=MemoryUpdateResponse,
            max_output_tokens=256,
            session_spend_cents=0.0,
        )
    except Exception as exc:  # noqa: BLE001 - any failure here means "do not spend"
        return False, f"{type(exc).__name__}: {exc}", 0.0
    return True, f"invoked {model_id} ok (repaired={result.repaired})", result.cost_cents


def project_worst_case_cents(results_so_far: list[StudentResult], plans, config) -> float:
    """Deliberately pessimistic, and used only to refuse a run before it starts.

    Prices every window at the FULL output cap rather than at an expected output length,
    because the number this feeds is a refusal, and a refusal that under-estimates is the
    one failure mode it must not have.
    """
    del results_so_far
    per_student_events = statistics.median([len(p.events) for p in plans] or [0]) / max(
        config.windows, 1
    )
    # ~280 chars per serialised event summary (measured on this corpus), chars/3 tokens.
    est_input = per_student_events * 280 / 3 + FIXED_OVERHEAD_TOKENS
    est_output = MemoryUpdateResponse.max_output_tokens_for(12)
    per_window = (
        est_input / 1000 * HAIKU_INPUT_CENTS_PER_1K + est_output / 1000 * HAIKU_OUTPUT_CENTS_PER_1K
    )
    return per_window * config.windows * len(plans)


# --- artifacts ----------------------------------------------------------------------------------


def write_jsonl(path: pathlib.Path, header: dict, results: list[StudentResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"record": "header", **header}) + "\n")
        for result in results:
            fh.write(json.dumps({"record": "student", **result.as_json()}) + "\n")


def write_metrics_csv(path: pathlib.Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["arm", "metric", "numerator", "denominator", "value", "unit", "note"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def summary_to_metric_rows(summary: dict) -> list[dict]:
    """Flatten one arm's summary into `(numerator, denominator, value)` triples.

    Every rate in the CSV therefore arrives with both of its parts, which is the plan's
    evidence rule expressed as a file format rather than as a promise.
    """
    arm = summary["arm"]
    rows: list[dict] = []

    def add(metric, numerator="", denominator="", value="", unit="", note=""):
        rows.append(
            {
                "arm": arm,
                "metric": metric,
                "numerator": numerator,
                "denominator": denominator,
                "value": value,
                "unit": unit,
                "note": note,
            }
        )

    add("students", value=summary["students"], unit="count")
    add("events_total", value=summary["events"]["total"], unit="count")
    add(
        "events_dropped_over_call_cap",
        numerator=summary["events"]["dropped_over_call_cap"],
        denominator=summary["events"]["total"],
        unit="events",
    )
    add(
        "students_with_dropped_events",
        numerator=summary["events"]["students_with_drops"],
        denominator=summary["students"],
        unit="students",
    )
    add(
        "model_calls_failed",
        numerator=summary["calls"]["failed"],
        denominator=summary["calls"]["total"],
        unit="calls",
    )
    for key in ("p10", "median", "p90"):
        add(
            f"compression_ratio_{key}",
            value=summary["compression_ratio"][key],
            denominator=summary["compression_ratio"]["n"],
            unit="raw_tokens/live_fact_tokens",
        )
    for scenario, bucket in sorted(summary["scenario_scores"].items()):
        add(
            f"scenario_status_correct:{scenario}",
            numerator=bucket["status_correct"],
            denominator=bucket["n"],
            unit="students",
        )
        add(
            f"scenario_served_correct:{scenario}",
            numerator=bucket["served_correct"],
            denominator=bucket["n"],
            unit="students",
        )
        add(
            f"scenario_any_fact_on_skill:{scenario}",
            numerator=bucket["any_live_fact_on_skill"],
            denominator=bucket["n"],
            unit="students",
            note="coverage: the pipeline learned SOMETHING about the planted skill",
        )
        add(
            f"scenario_polarity_match:{scenario}",
            numerator=bucket["polarity_match_any"],
            denominator=bucket["n"],
            unit="students",
            note="direction: a live fact on the planted skill carries the planted polarity",
        )
    add(
        "provenance_all_evidence_resolves",
        numerator=summary["provenance"]["facts_with_all_evidence_resolving_to_this_student"],
        denominator=summary["provenance"]["facts_total"],
        unit="facts",
    )
    add(
        "facts_with_no_resolving_evidence",
        numerator=summary["facts_with_no_resolving_evidence"],
        denominator=summary["provenance"]["facts_total"],
        unit="facts",
    )
    add("unplanted_extra_live_facts", value=summary["unplanted_extra_live_facts"], unit="facts")
    add(
        "students_stopped_by_per_student_ceiling",
        numerator=summary.get("students_budget_stopped", 0),
        denominator=summary["students"],
        unit="students",
    )
    for status, count in sorted(summary["lifecycle_distribution"].items()):
        add(
            f"lifecycle:{status}",
            numerator=count,
            denominator=summary["provenance"]["facts_total"],
            unit="facts",
        )
    ceiling = summary["input_ceiling"]
    add(
        "windows_over_32k_input_ceiling",
        numerator=ceiling["windows_over_ceiling"],
        denominator=ceiling["windows_total"],
        unit="windows",
    )
    add(
        "students_cumulative_history_over_ceiling",
        numerator=ceiling["students_whose_cumulative_history_exceeds_ceiling"],
        denominator=summary["students"],
        unit="students",
    )
    add(
        "windows_with_oversized_existing_fact_payload",
        numerator=ceiling["windows_with_oversized_existing_fact_payload"],
        denominator=ceiling["windows_total"],
        unit="windows",
        note=f"existing facts > MAX_SAFE_EXISTING_FACTS={ceiling['max_safe_existing_facts']}",
    )
    add(
        "calls_hit_output_ceiling",
        numerator=summary["calls"].get("hit_output_ceiling", 0),
        denominator=summary["calls"]["total"],
        unit="calls",
        note="stop_reason=max_tokens; the response validated as an EMPTY update",
    )
    add(
        "students_with_a_truncated_call",
        numerator=summary["calls"].get("students_with_a_truncated_call", 0),
        denominator=summary["students"],
        unit="students",
    )
    add(
        "cost_total_conservative",
        value=summary["cost"].get("conservative_cents_total"),
        unit="cents",
        note="includes cache-write/read tokens the gateway's own cost_cents omits",
    )
    add(
        "cost_per_student",
        value=summary["cost"]["measured_cents_per_student"],
        denominator=summary["students"],
        unit="cents",
        note="measured"
        if summary["cost"]["measured_is_real"]
        else "MOCK provider, not a real cost",
    )
    add(
        "cost_total",
        value=summary["cost"]["measured_cents_total"],
        unit="cents",
        note="measured"
        if summary["cost"]["measured_is_real"]
        else "MOCK provider, not a real cost",
    )
    return rows


# --- arms ----------------------------------------------------------------------------


async def _setup_corpus(session, config, plans, corpus_start, log):
    await reset_tables(session)
    topic_id, skill_ids = await gen.seed_catalog(session, config)
    bounds = gen.window_bounds(config, corpus_start)
    log(f"seeding {len(plans)} students ({sum(len(p.events) for p in plans)} events) ...")
    started = time.perf_counter()
    written = await gen.write_corpus(
        session,
        plans,
        config,
        corpus_start=corpus_start,
        topic_id=topic_id,
        skill_ids=skill_ids,
        log=log,
    )
    await session.commit()
    log(
        f"seeded in {time.perf_counter() - started:.1f}s: "
        f"{written.events_written} events, {written.chat_messages_written} chat messages, "
        f"{written.mastery_rows_written} mastery rows"
    )
    return topic_id, skill_ids, bounds


async def run_measured_arm(
    session,
    *,
    arm: str,
    config,
    plans,
    corpus_start,
    gateway,
    model_id: str,
    run_budget_cents: float | None,
    log,
) -> tuple[list[StudentResult], dict]:
    topic_id, skill_ids, bounds = await _setup_corpus(session, config, plans, corpus_start, log)
    del topic_id
    results: list[StudentResult] = []
    spend = 0.0
    conservative = 0.0
    started = time.perf_counter()
    aborted_reason: str | None = None
    for n, plan in enumerate(plans, start=1):
        try:
            result = await run_student(
                session,
                plan,
                config,
                gateway=gateway,
                skill_ids=skill_ids,
                bounds=bounds,
                run_spend_cents=spend,
                run_conservative_cents=conservative,
                run_budget_cents=run_budget_cents,
            )
        except RunBudgetExceeded as exc:
            # Abort-not-truncate, without throwing away what was already paid for.
            #
            # The rule the ceiling exists to protect is "a partial run must never be
            # SCORED AS IF COMPLETE" - not "a partial run must leave no trace". Re-raising
            # here (the first version of this loop) satisfied the rule by destroying
            # results the run had already bought, which cost this task a 22-student real
            # arm and taught the lesson directly. So: stop immediately, keep the students
            # that finished, stamp `aborted` on every artifact, and exit non-zero.
            aborted_reason = str(exc)
            log(f"ABORTED: {exc}")
            await session.commit()
            break
        spend += result.total_cost_cents
        conservative += result.total_conservative_cost_cents
        results.append(result)
        await session.commit()
        # Each student's rows are finished the moment their last window commits, and a
        # 1,000-student run would otherwise carry every event and fact it has ever touched
        # in one identity map. `StudentResult` is plain data, so nothing downstream needs
        # the ORM objects to stay attached.
        session.expunge_all()
        if n % max(1, len(plans) // 20) == 0 or n == len(plans):
            rate = n / max(time.perf_counter() - started, 1e-6)
            log(
                f"  consolidated {n}/{len(plans)} students ({rate:.1f}/s, spend "
                f"{spend:.2f} cents gateway / {conservative:.2f} cents conservative)"
            )
    summary = aggregate(results, arm=arm, config=config, model_id=model_id)
    summary["run_spend_cents"] = round(spend, 4)
    summary["run_spend_cents_conservative"] = round(conservative, 4)
    summary["run_budget_cents"] = run_budget_cents
    summary["aborted"] = aborted_reason is not None
    summary["aborted_reason"] = aborted_reason
    summary["students_requested"] = len(plans)
    floor = getattr(gateway, "_output_token_floor", None)
    summary["output_token_floor"] = floor
    summary["configuration"] = (
        "SHIPPED output budget (max_output_tokens_for)"
        if floor is None
        else f"ABLATION: max_output_tokens raised to at least {floor} - NOT the shipped "
        "configuration"
    )
    return results, summary


async def rescore_from_database(
    session, *, config, plans, corpus_start, log
) -> tuple[list[StudentResult], dict]:
    """Re-score an already-consolidated benchmark database with **no model calls at all**.

    Why this exists. `run_measured_arm` holds its per-student results in memory and writes
    them once at the end, so a run that aborts on the spend ceiling - which is the correct
    behaviour, and the behaviour E4.2 is required to have - loses every result it had
    already paid for. The facts themselves are not lost: each student commits as it
    finishes. So the scoring half can be re-run against the database for free, and the
    money already spent still produces evidence.

    What it cannot recover, it reports as absent rather than as zero. Per-call fields
    (`calls_attempted`, `cost_cents`, `stop_reason`, cache tokens) only ever existed in the
    gateway's replies; they are set to 0 here and every artifact this path writes carries
    `rescored_from_database: true` so no reader can mistake a 0 for a measurement. The
    lifecycle, provenance, scenario and compression numbers are all derived from persisted
    rows and are exactly what the original run would have reported.
    """
    from intellichoice_db.models.curriculum import Skill

    memory_repo = MemoryRepository(session)
    tutor_chat_repo = TutorChatMessageRepository(session)
    bounds = gen.window_bounds(config, corpus_start)

    rows = await session.execute(
        select(Skill).where(Skill.name.like(f"{gen.CATALOG_SKILL_PREFIX}-%")).order_by(Skill.name)
    )
    skill_ids = [row.skill_id for row in rows.scalars().all()]
    if len(skill_ids) != config.catalog_skills:
        raise SystemExit(
            f"expected {config.catalog_skills} benchmark skills in this database, found "
            f"{len(skill_ids)} - is this the database the run used?"
        )

    results: list[StudentResult] = []
    for plan in plans:
        windows: list[WindowObservation] = []
        cumulative = 0
        total_events = 0
        for index, (start, end) in enumerate(bounds):
            summaries = await _event_summaries(
                memory_repo, tutor_chat_repo, plan.external_id, start, end
            )
            raw_tokens = payload_tokens(summaries, [])
            cumulative += raw_tokens
            total_events += len(summaries)
            windows.append(
                WindowObservation(
                    window=index,
                    raw_event_count=len(summaries),
                    raw_payload_tokens=raw_tokens,
                    # A re-score has no record of what the existing-fact list looked like at
                    # each call, so the two are equal here. Stated rather than silently
                    # equated: it makes `over_input_ceiling` a slight UNDER-count on this
                    # path, never an over-count.
                    full_payload_tokens=raw_tokens,
                    batches=0,
                    calls_attempted=0,
                    calls_failed=0,
                    events_dropped=0,
                    mastery_conflicts=0,
                    budget_stopped=False,
                    calls_hit_output_ceiling=0,
                    cache_write_tokens=0,
                    conservative_cost_cents=0.0,
                    added=0,
                    updated=0,
                    contested=0,
                    expired=0,
                    cost_cents=0.0,
                    existing_facts_at_start=0,
                    over_input_ceiling=raw_tokens > HARD_MAX_INPUT_TOKENS,
                    wall_s=0.0,
                )
            )
        if not total_events:
            # This student was never seeded, so the run aborted before reaching them.
            # Scoring them would count "no facts" as a model failure; excluding them keeps
            # every denominator equal to the number of students actually consolidated.
            continue
        results.append(
            await _score_student_from_database(
                memory_repo,
                plan,
                skill_ids=skill_ids,
                windows=windows,
                total_events=total_events,
                cumulative_tokens=cumulative,
            )
        )
        log(f"  rescored {plan.external_id}")

    summary = aggregate(
        results, arm="real", config=dataclasses.replace(config, students=len(results)), model_id=""
    )
    summary["rescored_from_database"] = True
    summary["run_spend_cents"] = None
    summary["run_spend_cents_conservative"] = None
    return results, summary


async def main_async(args) -> int:
    url = resolve_database_url(args.database_url)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log = print

    engine = create_engine(url)
    session_factory = create_session_factory(engine)
    corpus_start = gen.DEFAULT_CORPUS_START

    try:
        if args.arm == "scripted":
            config = gen.CorpusConfig(students=1, seed=args.seed)
            async with session_factory() as session:
                await reset_tables(session)
                topic_id, skill_ids = await gen.seed_catalog(session, config)
                bounds = gen.window_bounds(config, corpus_start)
                await session.commit()
                log(
                    f"scripted lane: {SCRIPTED_FLIP_STUDENTS} lifecycle students + "
                    f"{SCRIPTED_SCREEN_STUDENTS} screen students (no provider, $0)"
                )
                summary = await run_scripted_lane(
                    session, topic_id=topic_id, skill_ids=skill_ids, bounds=bounds
                )
                await session.commit()
                (out_dir / "scripted_lane_results.json").write_text(
                    json.dumps(summary, indent=2) + "\n", encoding="utf-8"
                )
                for name, bucket in sorted(summary["checks"].items()):
                    log(f"  {name}: {bucket['passed']}/{bucket['n']}")
                log(f"failures: {summary['failure_count']}")
                if args.cleanup:
                    await reset_tables(session)
                    await session.commit()
                    log(f"cleanup: {await table_counts(session)}")
            return 0

        pool_config = gen.CorpusConfig(students=args.pool_students, seed=args.seed)
        pool = gen.plan_corpus(pool_config)

        if args.arm == "score-only":
            plans = gen.stratified_subset(pool, args.students)
            async with session_factory() as session:
                results, summary = await rescore_from_database(
                    session,
                    config=pool_config,
                    plans=plans,
                    corpus_start=corpus_start,
                    log=lambda *a: None,
                )
            if not results:
                raise SystemExit("no consolidated students found in this database")
            e43 = raw_vs_consolidated_table(results)
            prefix = "real" + (f"_{args.run_label}" if args.run_label else "") + "_rescored"
            gen.write_manifest(
                out_dir / f"{prefix}_ground_truth_manifest.jsonl",
                dataclasses.replace(pool_config, students=len(results)),
                plans[: len(results)],
            )
            write_jsonl(out_dir / f"{prefix}_results_n{len(results)}.jsonl", summary, results)
            (out_dir / f"{prefix}_summary.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
            (out_dir / f"{prefix}_raw_vs_consolidated.json").write_text(
                json.dumps({k: v for k, v in e43.items() if k != "rows"}, indent=2) + "\n",
                encoding="utf-8",
            )
            write_metrics_csv(
                out_dir / f"{prefix}_metrics_summary.csv", summary_to_metric_rows(summary)
            )
            log(json.dumps({k: v for k, v in summary.items() if k != "config"}, indent=2))
            log(f"rescored {len(results)} student(s) from the database; $0 spent")
            return 0

        if args.arm == "mock":
            config = gen.CorpusConfig(students=args.students, seed=args.seed)
            plans = gen.plan_corpus(config)
            gateway = MeteringGateway(
                build_mock_gateway(),
                input_rate=HAIKU_INPUT_CENTS_PER_1K,
                output_rate=HAIKU_OUTPUT_CENTS_PER_1K,
            )
            model_id = "MockBedrockProvider (no real model)"
            budget = None
        else:
            if os.getenv("MEMORY_BENCH_REAL_BEDROCK") != "1":
                raise SystemExit(
                    "refusing to run the real arm: set MEMORY_BENCH_REAL_BEDROCK=1. This arm "
                    "calls a paid API and must never run in CI or by default."
                )
            config = dataclasses.replace(pool_config, students=args.students)
            plans = gen.stratified_subset(pool, args.students)
            if len(plans) < args.students:
                raise SystemExit(
                    f"pool of {args.pool_students} yielded only {len(plans)} standard students; "
                    "raise --pool-students"
                )
            model_id = os.getenv("MEMORY_BENCH_MODEL_ID") or DEFAULT_REAL_MODEL_ID
            region = os.getenv("AWS_REGION") or "us-east-1"
            gateway = MeteringGateway(
                build_real_gateway(model_id, region),
                input_rate=HAIKU_INPUT_CENTS_PER_1K,
                output_rate=HAIKU_OUTPUT_CENTS_PER_1K,
                output_token_floor=args.output_token_floor,
            )
            budget = RUN_BUDGET_CENTS
            projected = project_worst_case_cents([], plans, config)
            log(
                f"real arm: {len(plans)} students x {config.windows} windows against "
                f"{model_id} in {region}"
            )
            log(
                f"pre-flight worst-case projection: {projected:.1f} cents "
                f"(run ceiling {budget:.1f}, per-student ceiling {PER_STUDENT_BUDGET_CENTS:.1f})"
            )
            if projected > budget:
                raise SystemExit(
                    f"refusing to start: projected worst case {projected:.1f} cents exceeds the "
                    f"run ceiling {budget:.1f}. Lower --students or raise nothing - the ceiling "
                    "is hard."
                )
            ok, detail, probe_cost = await probe_model(gateway, model_id)
            # The probe is not part of any student's window; leaving its record in the
            # meter would attribute its tokens to the first student measured.
            gateway.drain()
            log(f"invocability probe: {'OK' if ok else 'FAILED'} - {detail} ({probe_cost:.4f} c)")
            if not ok:
                raise SystemExit(
                    "refusing to start: the model is not invocable by these credentials. "
                    "AVAILABLE is not invocable (D-273) - nothing was spent beyond the probe."
                )
            budget = budget - probe_cost

        async with session_factory() as session:
            results, summary = await run_measured_arm(
                session,
                arm=args.arm,
                config=config,
                plans=plans,
                corpus_start=corpus_start,
                gateway=gateway,
                model_id=model_id,
                run_budget_cents=budget,
                log=log,
            )
            e43 = raw_vs_consolidated_table(results)

            # The ground truth, written beside the results rather than only living in the
            # generator's seed. A scored result whose expectations cannot be re-read is a
            # result nobody can check.
            suffix = f"n{len(results)}" + (f"_{args.run_label}" if args.run_label else "")
            jsonl = out_dir / (
                f"mock_results_{suffix}.jsonl"
                if args.arm == "mock"
                else f"real_results_{suffix}.jsonl"
            )
            write_jsonl(jsonl, summary, results)
            prefix = args.arm + (f"_{args.run_label}" if args.run_label else "")
            gen.write_manifest(out_dir / f"{prefix}_ground_truth_manifest.jsonl", config, plans)
            (out_dir / f"{prefix}_summary.json").write_text(
                json.dumps(summary, indent=2) + "\n", encoding="utf-8"
            )
            (out_dir / f"{prefix}_raw_vs_consolidated.json").write_text(
                json.dumps({k: v for k, v in e43.items() if k != "rows"}, indent=2) + "\n",
                encoding="utf-8",
            )
            with (out_dir / f"{prefix}_raw_vs_consolidated.csv").open(
                "w", encoding="utf-8", newline=""
            ) as fh:
                writer = csv.DictWriter(fh, fieldnames=list(e43["rows"][0].keys()))
                writer.writeheader()
                writer.writerows(e43["rows"])
            write_metrics_csv(
                out_dir / f"{prefix}_metrics_summary.csv", summary_to_metric_rows(summary)
            )

            log("")
            log(json.dumps({k: v for k, v in summary.items() if k != "config"}, indent=2))
            log("")
            log(f"E4.3 median compression vs live memory: {e43['median_compression_vs_live']}x")
            log(
                f"E4.3 students whose raw history exceeds the {HARD_MAX_INPUT_TOKENS}-token "
                f"input ceiling: {e43['students_raw_over_ceiling']}/{e43['students']}"
            )
            log(
                f"TOTAL SPEND: {summary['run_spend_cents']} cents gateway-reported / "
                f"{summary['run_spend_cents_conservative']} cents conservative "
                f"(ceiling {budget}, hard {RUN_BUDGET_CENTS_HARD})"
            )
            log(
                "calls that hit the output ceiling (silently empty updates): "
                f"{summary['calls']['hit_output_ceiling']}/{summary['calls']['total']}"
            )

            if args.cleanup:
                await reset_tables(session)
                await session.commit()
                log(f"cleanup: {await table_counts(session)}")
            if summary.get("aborted"):
                log(
                    "EXITING NON-ZERO: this run stopped on its spend ceiling. The artifacts "
                    f"cover {summary['students']} of {summary['students_requested']} "
                    "requested students and every one of them is stamped `aborted: true`."
                )
                return 1
        return 0
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--arm", choices=("mock", "scripted", "real", "score-only"), required=True)
    parser.add_argument("--students", type=int, default=1000)
    parser.add_argument(
        "--pool-students",
        type=int,
        default=1000,
        help="corpus the real arm's stratified subset is drawn from; keeping this at the "
        "mock arm's N is what makes the two arms the same students",
    )
    parser.add_argument("--seed", type=int, default=gen.CorpusConfig.seed)
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--out-dir", default=str(ROOT / "docs" / "resume_evidence" / "04_memory"))
    parser.add_argument(
        "--run-label",
        default="",
        help="suffix for this run's artifact filenames, so two real-arm configurations "
        "(shipped vs headroom) cannot overwrite each other's evidence",
    )
    parser.add_argument(
        "--output-token-floor",
        type=int,
        default=None,
        help="E4.2 arm B ONLY: raise every consolidation call's max_output_tokens to at "
        "least this value (the gateway still caps at its own 4000 hard ceiling). This is "
        "NOT the shipped configuration - it is the ablation that separates 'the model "
        "could not' from 'the output budget would not let it'.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="TRUNCATE the benchmark tables after writing artifacts and print the row counts",
    )
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
