"""What one chat turn may cost, reserved before it runs (D-345).

The per-day ceiling this feeds is AUD-X-08's reserve-then-settle, the same mechanism
learning-api's report and tutor-chat surfaces use, for the same reason: a ceiling read from
state that other callers cannot see is not a ceiling.

**A constant rather than a gateway call, deliberately.** `BedrockGateway` excludes
`worst_case_cost_cents` from the Protocol on purpose - see that Protocol's own comment - so
pricing lives here and `test_turn_cost_estimate.py` keeps it honest against the real
gateway's arithmetic, for every model the registry can hold. That is the established shape
(`learning_api.services.tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS`), and departing from it
would put a pricing method on a dozen scripted test fakes that never call it.

The cost of a constant is that it can drift low, which silently reopens the race it closes.
Two things guard that here, and the second is the one that matters: the pinning test prices
`WORST_CASE_CALLS` through the real gateway, and a second test drives a real turn through a
recording gateway and asserts the calls it actually made are covered by that declaration. A
sum re-derived from the same declaration the code uses would prove nothing (D-335: a test
that asserts the transformation its own code performed). Adding a model call to the graph
without declaring it here fails the recording test.
"""

from dataclasses import dataclass

from intellichoice_shared.bedrock import BedrockTask, RagAnswerResponse, RerankResponse


@dataclass(frozen=True)
class PricedCall:
    task: BedrockTask
    max_output_tokens: int


# The retrieval settings the shape below is priced at. They are `Settings` fields rather
# than literals in the real app (`retrieval_candidate_limit`, `retrieval_top_k`), and both
# feed token budgets that scale - so the pinning test re-prices at the *configured* values
# and fails if tuning either one outgrows the constant. These are the shipped defaults.
DEFAULT_CANDIDATE_LIMIT = 30
DEFAULT_TOP_K = 8


def worst_case_calls(*, candidate_limit: int, top_k: int) -> tuple[PricedCall, ...]:
    """The most expensive shape a single turn can take, in the order the graph calls them.

    It is a `document_qa` question that retrieves, synthesises, fails the citation or
    confidence gate, and then runs the access probe (`nodes.explain_access`) to decide
    whether a log-in hint is warranted. Not an exotic path: it is what *every* no-source
    refusal does, and D-343 measured it live as a guest.

    Not listed, and why: the calendar-extraction call (768 output tokens) replaces the
    answer synthesis rather than adding to it, and is cheaper; the two Titan embeddings bill
    input only at 0.002 cents per 1k, so both together are ~0.004 cents against an estimate
    measured in whole cents - noise, not safety.
    """
    return (
        # `nodes.scope_guard` - combined scope + intent (D-041).
        PricedCall(BedrockTask.SCOPE_AND_INTENT, 512),
        # `retrieval.retrieve` - reranking `candidate_limit` candidates.
        PricedCall(BedrockTask.RERANK, RerankResponse.max_output_tokens_for(candidate_limit)),
        # `qa.answer_question` - synthesis over `top_k` passages.
        PricedCall(BedrockTask.RAG_ANSWER, RagAnswerResponse.max_output_tokens_for(top_k)),
        # `retrieval.probe_access` - the same reranker again, against the unfiltered corpus.
        PricedCall(BedrockTask.RERANK, RerankResponse.max_output_tokens_for(candidate_limit)),
    )


WORST_CASE_CALLS = worst_case_calls(
    candidate_limit=DEFAULT_CANDIDATE_LIMIT, top_k=DEFAULT_TOP_K
)

# `generate_structured` allows exactly one repair retry on a schema failure, and a repair is
# a whole second call that pays again for its ~2000 input tokens. Applied to every call, not
# just the priciest, because any of them can fail validation. Learning-api learned this the
# expensive way: its constant was sized without the retry and the comment claiming the retry
# was already covered was "wrong twice over" (see `tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS`).
REPAIR_RETRY_MULTIPLIER = 2

# 24.192 cents on the most expensive priced model (Sonnet 5, which is also the unpriced-model
# fallback rate): 1.368 + 2.952 + 4.824 + 2.952 = 12.096 for the four calls above, doubled for
# the repair. The deployed model is Haiku 4.5 at a third of that. Rounded up to 25.
#
# Against the 1500-cent per-day ceiling this allows 60 turns to be *simultaneously in flight*
# before one is refused - not 60 turns per day, because `settle` replaces the estimate with
# the turn's real 2-6 cents the moment it finishes. Over-counting is the safe direction for a
# ceiling, and it only ever costs concurrency.
TURN_RESERVATION_ESTIMATE_CENTS = 25.0
