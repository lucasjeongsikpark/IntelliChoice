"""S42 (AUD-X-08): the reservation estimates must keep bounding what a call can cost.

`report.REPORT_RESERVATION_ESTIMATE_CENTS` and
`tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS` are constants rather than a gateway call,
because putting a pricing method on the `BedrockGateway` Protocol would oblige a dozen
scripted test fakes to implement one they never use. The cost of that choice is that the
constants can drift from real pricing, and a constant that drifts *low* silently reopens
the race it was written to close - an under-reservation lets a caller slip in under a
total that is about to grow.

This is the guard: every estimate is checked against the real gateway's own worst-case
arithmetic, for every model the registry can be configured with. It fails on a pricing
change, a model change, or a token-budget increase, rather than under-counting quietly.
"""

import pytest
from intellichoice_adapters.bedrock.gateway import (
    _MODEL_RATES_PER_1K_CENTS,
    ResilientBedrockGateway,
)
from intellichoice_shared.bedrock import BedrockTask
from learning_api.services import tutor_chat
from learning_api.services.report import (
    _MAX_OUTPUT_TOKENS as REPORT_MAX_OUTPUT_TOKENS,
)
from learning_api.services.report import (
    REPORT_RESERVATION_ESTIMATE_CENTS,
)

# Every task the two reserved surfaces can dispatch, pointed at one model - `main.py`
# maps all generative tasks to `bedrock_tutor_model_id`, so per-task model divergence is
# not a case that exists today.
_TASKS = (
    BedrockTask.PARENT_REPORT,
    BedrockTask.LEARNING_CHAT_INTENT,
    BedrockTask.TUTOR,
)


def _gateway(model_id: str) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=None,  # type: ignore[arg-type]  # never called; only pricing is read
        model_registry=dict.fromkeys(_TASKS, model_id),
    )


@pytest.mark.parametrize("model_id", sorted(_MODEL_RATES_PER_1K_CENTS))
def test_report_reservation_bounds_a_real_report_call(model_id: str) -> None:
    worst_case = _gateway(model_id).worst_case_cost_cents(
        BedrockTask.PARENT_REPORT, REPORT_MAX_OUTPUT_TOKENS
    )
    assert REPORT_RESERVATION_ESTIMATE_CENTS >= worst_case, (
        f"{model_id}: a report can cost up to {worst_case:.4f} cents but only "
        f"{REPORT_RESERVATION_ESTIMATE_CENTS} is reserved - raise the constant"
    )


def _turn_shapes(gateway: ResilientBedrockGateway) -> dict[str, float]:
    """Every sequence of calls one chat turn can make, priced at worst case.

    D-207 added the second shape and this test did not have it, which is how the
    reservation came to under-count. The old version modelled a turn as "intent + one
    content call" - true until `_tutor_chat_call` gained a retry, after which a truncated
    reply makes *three* calls and pays the per-call input assumption a third time. The
    constant stayed at 3.0 against a real worst case of 3.825 and nothing said so.

    Enumerating the shapes rather than asserting one number is the point: adding another
    retry anywhere in a turn now has to appear here, and the assertion below fails until
    the reservation is raised to match.
    """
    intent = gateway.worst_case_cost_cents(
        BedrockTask.LEARNING_CHAT_INTENT, tutor_chat.INTENT_CLASSIFICATION_TOKENS
    )
    return {
        # request_hint / request_solution / request_video: one content generation, the
        # largest of which is a solution.
        "dispatch-to-content": intent
        + gateway.worst_case_cost_cents(BedrockTask.TUTOR, tutor_chat.MAX_TURN_CONTENT_TOKENS),
        # question_help / why_wrong where the first reply truncates and is retried once
        # under a bigger ceiling.
        "chat-reply-with-retry": intent
        + sum(
            gateway.worst_case_cost_cents(BedrockTask.TUTOR, tokens)
            for tokens in tutor_chat.CHAT_RETRY_CONTENT_TOKENS
        ),
    }


@pytest.mark.parametrize("model_id", sorted(_MODEL_RATES_PER_1K_CENTS))
def test_chat_turn_reservation_bounds_the_most_expensive_turn(model_id: str) -> None:
    shapes = _turn_shapes(_gateway(model_id))
    name, worst_case = max(shapes.items(), key=lambda pair: pair[1])
    assert tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS >= worst_case, (
        f"{model_id}: a chat turn of shape {name!r} can cost up to {worst_case:.4f} cents "
        f"but only {tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS} is reserved - raise the "
        f"constant"
    )


def test_an_unpriced_model_cannot_under_reserve_a_chat_turn() -> None:
    """The chat sibling of the report check below. An unknown model id must quote at least
    as much as any known one, or a typo in the model registry would under-reserve every
    turn.
    """
    unknown = max(_turn_shapes(_gateway("model-that-does-not-exist")).values())
    priced = [
        max(_turn_shapes(_gateway(model_id)).values()) for model_id in _MODEL_RATES_PER_1K_CENTS
    ]
    assert unknown >= max(priced)
    assert tutor_chat.TURN_RESERVATION_ESTIMATE_CENTS >= unknown


def test_an_unpriced_model_falls_back_to_the_most_expensive_rate() -> None:
    """The estimates above are only safe if an unknown model id cannot be *cheaper* to
    quote than a known one - otherwise a typo'd model id would under-reserve. The
    gateway's default rate is the expensive end of the table, and this pins that.
    """
    unknown = _gateway("model-that-does-not-exist").worst_case_cost_cents(
        BedrockTask.PARENT_REPORT, REPORT_MAX_OUTPUT_TOKENS
    )
    priced = [
        _gateway(model_id).worst_case_cost_cents(
            BedrockTask.PARENT_REPORT, REPORT_MAX_OUTPUT_TOKENS
        )
        for model_id in _MODEL_RATES_PER_1K_CENTS
    ]
    assert unknown >= max(priced)
