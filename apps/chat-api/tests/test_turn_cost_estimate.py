"""D-345: `TURN_RESERVATION_ESTIMATE_CENTS` must keep bounding what a real turn can cost.

The sibling of `apps/learning-api/tests/test_cost_reservation_estimates.py`, and for the
same reason: the estimate is a constant because `BedrockGateway` deliberately keeps
pricing off the Protocol, and the cost of a constant is that it can drift low - which
silently reopens the race it was written to close.

**Two tests, doing genuinely different work.** The pricing tests re-price the declared
worst-case shape through the real gateway, for every model the registry can hold; they
catch a pricing change, a model change or a token-budget increase. They cannot catch the
failure that actually matters - somebody adding a *fifth* model call to a turn and not
declaring it here - because they read the same declaration the estimate is built from, and
a test that re-derives its own code's arithmetic proves nothing (D-335).

`test_a_real_turn_makes_no_call_the_estimate_has_not_priced` is the one that can fail that
way: it drives a real turn through a recording gateway and compares the calls it actually
made against `WORST_CASE_CALLS`.
"""

import asyncio
from collections import Counter

import pytest
from chat_api.services.turn_cost import (
    DEFAULT_CANDIDATE_LIMIT,
    DEFAULT_TOP_K,
    REPAIR_RETRY_MULTIPLIER,
    TURN_RESERVATION_ESTIMATE_CENTS,
    WORST_CASE_CALLS,
    worst_case_calls,
)
from intellichoice_adapters.bedrock.gateway import (
    _MODEL_RATES_PER_1K_CENTS,
    ResilientBedrockGateway,
)
from intellichoice_shared.bedrock import BedrockTask

from .conftest import postgres_skip_reason, rollback_session
from .test_qa_graph import _ask, _gateway, _seed_chunk

_GENERATIVE_TASKS = (
    BedrockTask.SCOPE_AND_INTENT,
    BedrockTask.RERANK,
    BedrockTask.RAG_ANSWER,
    BedrockTask.CALENDAR_EXTRACTION,
)


def _priced_gateway(model_id: str) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=None,  # type: ignore[arg-type]  # never called; only pricing is read
        model_registry=dict.fromkeys(_GENERATIVE_TASKS, model_id),
    )


def _worst_case_cents(model_id: str, *, candidate_limit: int, top_k: int) -> float:
    gateway = _priced_gateway(model_id)
    return REPAIR_RETRY_MULTIPLIER * sum(
        gateway.worst_case_cost_cents(call.task, call.max_output_tokens)
        for call in worst_case_calls(candidate_limit=candidate_limit, top_k=top_k)
    )


@pytest.mark.parametrize("model_id", sorted(_MODEL_RATES_PER_1K_CENTS))
def test_the_reservation_bounds_the_worst_turn_on_every_priced_model(model_id: str) -> None:
    worst_case = _worst_case_cents(
        model_id, candidate_limit=DEFAULT_CANDIDATE_LIMIT, top_k=DEFAULT_TOP_K
    )
    assert TURN_RESERVATION_ESTIMATE_CENTS >= worst_case, (
        f"{model_id}: a turn can cost up to {worst_case:.4f} cents but only "
        f"{TURN_RESERVATION_ESTIMATE_CENTS} is reserved - raise the constant"
    )


def test_an_unpriced_model_cannot_under_reserve() -> None:
    """A typo in the model registry must not become a cheaper reservation. The gateway's
    fallback rate is the expensive end of the table; this pins that it stays so.
    """
    unknown = _worst_case_cents(
        "model-that-does-not-exist",
        candidate_limit=DEFAULT_CANDIDATE_LIMIT,
        top_k=DEFAULT_TOP_K,
    )
    priced = [
        _worst_case_cents(
            model_id, candidate_limit=DEFAULT_CANDIDATE_LIMIT, top_k=DEFAULT_TOP_K
        )
        for model_id in _MODEL_RATES_PER_1K_CENTS
    ]
    assert unknown >= max(priced)
    assert TURN_RESERVATION_ESTIMATE_CENTS >= unknown


def test_the_reservation_is_priced_at_the_settings_actually_shipped() -> None:
    """The two retrieval knobs feed token budgets that scale, so the constant is only
    correct for the values it was computed at. `Settings` is the thing that decides them,
    and this fails if either default is raised without revisiting the estimate.
    """
    from chat_api.config import Settings

    shipped = Settings()
    assert shipped.retrieval_candidate_limit == DEFAULT_CANDIDATE_LIMIT
    assert shipped.retrieval_top_k == DEFAULT_TOP_K


class _RecordingGateway:
    """The real mock-backed gateway, plus a log of every generate call it was asked for."""

    def __init__(self) -> None:
        self._real = _gateway()
        self.calls: list[tuple[BedrockTask, int]] = []

    async def generate_structured(self, **kwargs):
        self.calls.append((kwargs["task"], kwargs["max_output_tokens"]))
        return await self._real.generate_structured(**kwargs)

    async def create_embedding(self, **kwargs):
        return await self._real.create_embedding(**kwargs)


# Two turn shapes the offline harness can actually drive, chosen because they exercise
# different halves of the graph: one that finds nothing it may cite and falls through to
# the refusal-plus-probe path, and one that retrieves and synthesises an answer.
_PATHS = (
    ("refusal-then-probe", "tutor"),
    ("retrieved-and-answered", "public"),
)


@pytest.mark.parametrize(("name", "corpus_audience"), _PATHS)
@pytest.mark.skipif(postgres_skip_reason() is not None, reason=postgres_skip_reason() or "")
def test_a_real_turn_costs_no_more_than_the_reservation(name: str, corpus_audience: str) -> None:
    """**The test that can catch a model call nobody priced.**

    The pricing tests above read `WORST_CASE_CALLS` - the same declaration the estimate is
    derived from - so they are structurally blind to the declaration being *incomplete*.
    This one drives a real turn, records the calls it actually made, prices those recorded
    calls at the most expensive model, and asserts the total is inside the reservation. A
    fifth call added to the graph fails it whatever the declaration says.

    **What it cannot cover, stated rather than implied.** The access probe's reranker arm
    is unreachable under `MockBedrockProvider`: its embeddings are hash vectors, so
    `access_probe_candidates` never returns anything within the distance threshold and
    `probe_access` always takes the lexical arm. `retrieval.probe_access` documents this
    directly ("the only arm the mock-backed suite can exercise", D-165/D-179). Verified
    while writing this test: deleting that call from `WORST_CASE_CALLS` did not fail it.
    So the second RERANK in the declaration is priced-but-unexercised here, deliberately -
    it is real in production, where embeddings are real, and dropping it would under-
    reserve exactly the refusal path D-343 measured live.
    """
    gateway = _RecordingGateway()

    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                audience=corpus_audience,
                chunk_text=(
                    "Tutors record zqxvchunk attendance in the branch register at the "
                    "start of every session before the pre-exam begins."
                ),
            )
            # Anonymous throughout: against a tutor-audience corpus the chunk is filtered
            # out before retrieval and the turn refuses, against a public one it answers.
            await _ask(
                session,
                claims=None,
                query="zqxvchunk handbook attendance register",
                thread_id=f"t-turn-cost-{name}",
                gateway=gateway,
            )

    asyncio.run(run())

    assert gateway.calls, f"{name}: the turn made no model calls - the harness is not driving it"

    # Priced on the dearest model, and on the *declared* allowance for each task rather
    # than the tokens this particular turn happened to ask for: a one-passage answer bills
    # less than an eight-passage one, and the reservation has to cover the latter.
    allowance: Counter[BedrockTask] = Counter()
    for call in WORST_CASE_CALLS:
        allowance[call.task] = max(allowance[call.task], call.max_output_tokens)

    undeclared = [(task.value, tokens) for task, tokens in gateway.calls if task not in allowance]
    assert not undeclared, (
        f"{name}: the turn made calls the reservation does not price at all: {undeclared}. "
        f"Add them to `turn_cost.worst_case_calls` and raise the constant to match."
    )

    dearest = max(_MODEL_RATES_PER_1K_CENTS, key=lambda m: _MODEL_RATES_PER_1K_CENTS[m][1])
    priced = _priced_gateway(dearest)
    actual_cost = REPAIR_RETRY_MULTIPLIER * sum(
        priced.worst_case_cost_cents(task, max(tokens, allowance[task]))
        for task, tokens in gateway.calls
    )
    assert actual_cost <= TURN_RESERVATION_ESTIMATE_CENTS, (
        f"{name}: a real turn made {[(t.value, n) for t, n in gateway.calls]}, which prices "
        f"at {actual_cost:.4f} cents on {dearest} - above the {TURN_RESERVATION_ESTIMATE_CENTS}"
        f"-cent reservation. Raise the constant."
    )
