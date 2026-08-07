"""D-207: a truncated tutor-chat reply gets one retry under a bigger ceiling.

Why this file exists, from the log rather than from a hunch. On staging at
2026-08-06T20:14:08Z a student's chat message produced:

    "reason": "output_truncated", "detail": "model hit max_output_tokens=400 before
    completing the TutorChatResponse response; not retrying under the same ceiling"

and the endpoint answered **200** with `_fallback_chat_response`'s "I'm having a little
trouble right now". The student's question was silently swallowed - the worst shape a
failure can take, because nothing tells them to ask again.

D-115's refusal to retry is right *as stated*: the same prompt under the same ceiling
truncates again at full input cost. It also names the honest fix - "a bigger ceiling or a
smaller response shape" - and both of those belong to the caller, which is what these
tests pin. No database, no HTTP: the retry decision is a property of
`tutor_chat._tutor_chat_call` alone.
"""

import asyncio

import pytest
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    OutputTruncatedError,
    StructuredOutputError,
    TutorChatResponse,
    TutorContext,
)
from learning_api.services import tutor_chat
from pydantic import BaseModel


def _context() -> TutorContext:
    return TutorContext(
        grade="7",
        topic="Linear Equations",
        skill="Solve two-step linear equations",
        estimated_level="2",
        question="Maya has $60 and spends $5 each day. After how many days will she have $25?",
        selected_wrong_answer="5",
    )


class _SequencedGateway:
    """Answers each successive `generate_structured` call from a script, recording the
    ceiling it was asked for. A script entry that is an exception is raised.
    """

    def __init__(self, *outcomes: object) -> None:
        self._outcomes = list(outcomes)
        self.ceilings: list[int] = []

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        self.ceilings.append(max_output_tokens)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # type: ignore[return-value]

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


def _ok(reply: str, cost: float) -> BedrockGenerationResult[TutorChatResponse]:
    return BedrockGenerationResult(
        value=TutorChatResponse(reply_text=reply, answer_revealed=False),
        input_tokens=100,
        output_tokens=100,
        cost_cents=cost,
        model_id="anthropic.claude-test",
        repaired=False,
    )


def _call(gateway: object):
    return asyncio.run(
        tutor_chat.generate_chat_reply(
            gateway=gateway,  # type: ignore[arg-type]
            context=_context(),
            redacted_message="I don't get how to start this one",
            correct_answer_text="7",
            session_spend_cents=0.0,
        )
    )


def test_a_truncated_reply_is_retried_under_a_bigger_ceiling() -> None:
    gateway = _SequencedGateway(
        OutputTruncatedError("hit the ceiling", cost_cents=0.2),
        _ok("Start by writing what she has left after d days.", 0.3),
    )
    response, cost = _call(gateway)

    assert response.reply_text.startswith("Start by writing")
    # Both attempts are billed - the truncated one produced tokens even though it
    # produced no usable content.
    assert cost == 0.5
    assert gateway.ceilings == [
        tutor_chat._MAX_CHAT_REPLY_TOKENS,
        tutor_chat._RETRY_CHAT_REPLY_TOKENS,
    ]
    assert tutor_chat._RETRY_CHAT_REPLY_TOKENS > tutor_chat._MAX_CHAT_REPLY_TOKENS


def test_the_retry_is_bounded_to_one_attempt() -> None:
    """Two truncations in a row end in the fallback, not a third call. A student waiting
    on a reply is the thing being protected here, as much as the budget.
    """
    gateway = _SequencedGateway(
        OutputTruncatedError("hit the ceiling", cost_cents=0.2),
        OutputTruncatedError("hit it again", cost_cents=0.4),
    )
    response, cost = _call(gateway)

    assert "having a little trouble" in response.reply_text
    assert cost == pytest.approx(0.6)
    assert len(gateway.ceilings) == 2


def test_a_malformed_response_is_not_retried() -> None:
    """The narrow reading of D-115 that stays true: a `StructuredOutputError` that is
    *not* a truncation gets no second attempt, because a bigger ceiling fixes nothing
    about invalid JSON.
    """
    gateway = _SequencedGateway(StructuredOutputError("bad json", cost_cents=0.2))
    response, cost = _call(gateway)

    assert "having a little trouble" in response.reply_text
    assert cost == 0.2
    assert len(gateway.ceilings) == 1


def test_an_ordinary_gateway_failure_still_reports_its_partial_cost() -> None:
    """Regression guard on the rewrite: the pre-D-207 code returned a hardcoded `0.0`
    from this branch, dropping spend the call had genuinely incurred out of the session
    total. Every other Bedrock caller in this codebase returns `exc.cost_cents`.
    """
    gateway = _SequencedGateway(BedrockGatewayError("timeout", cost_cents=0.15))
    response, cost = _call(gateway)

    assert "having a little trouble" in response.reply_text
    assert cost == 0.15


def test_both_chat_prompts_bound_the_reply_length() -> None:
    """The ceiling alone did not stop the truncation; the prompt has to ask for a short
    answer. Also the better reply for a K-12 student on a phone.
    """
    assert "at most 4 short sentences" in tutor_chat._CHAT_REPLY_SYSTEM_PROMPT
    assert "at most 4 short sentences" in tutor_chat._WHY_WRONG_SYSTEM_PROMPT
