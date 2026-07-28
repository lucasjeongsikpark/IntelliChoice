"""Contextual learning chat (SPEC §5.12, §5.30.1 D-072; ROADMAP S24, plan §18-L5).

Everything that touches Bedrock lives here, matching `tutor.py`'s split between "LLM
calls" (this file, `tutor.py`) and "orchestration" (`graph/nodes.py::tutor_chat`).
Intent classification (`classify_intent`) picks one of six branches; only
`question_help`/`why_wrong` make a second, free `TUTOR_CHAT` call
(`generate_chat_reply`/`explain_why_wrong`) - `request_hint`/`request_solution`/
`request_video` dispatch deterministically to the existing hint-ladder/solution/video
services instead (see `nodes.py`), and `off_topic` never reaches Bedrock a second time at
all.

Every free-text reply is re-checked against the real question's real answer with the
same leak-phrase/verbatim-answer rules `tutor.generate_personalized_hint` already uses -
never trusted as safe just because the model returned it.

Self-harm/abuse keyword screen (`screen_for_safety_concern`) runs before intent
classification and before any Bedrock call - a fixed, age-appropriate response, never
LLM-improvised (SPEC §5.12.2's "route safety signals through a separately approved
policy"). This is a keyword-only screen, not exhaustive - a documented residual risk
(plan §15), same posture as `pii_redaction`'s "no name detection" caveat.
"""

from intellichoice_curriculum.authored_validation import (
    answer_text_leaked,
    leak_phrase_present,
)
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    LearningChatIntentPayload,
    LearningChatIntentResponse,
    TutorChatPayload,
    TutorChatResponse,
    TutorContext,
)

# Per-day, per-student ceiling on chat-driven Bedrock spend (SPEC §5.25.1's per-session
# budget's sibling, scoped to a day rather than a session - chat is the first surface a
# student can trigger many separate LLM calls across many sessions in one day).
# Placeholder until real usage data exists, same posture as `exam_policy.
# EXAM_TIME_LIMIT_SECONDS` and every other tuned constant in this codebase.
DAILY_COST_CEILING_CENTS = 100.0

OFF_TOPIC_RESPONSE = (
    "I'm your study helper for this question, so let's keep our chat focused on it - "
    "what part of the problem can I help with?"
)

NEEDS_WRONG_ATTEMPT_MESSAGE = (
    "Give this question a try first, and if it doesn't go the way you expect, come "
    "back and I can help you figure out what happened!"
)

CEILING_EXCEEDED_RESPONSE = (
    "You've used up today's chat help for this account - come back tomorrow for more! "
    "You can still use the Hint, Solution, and Video buttons in the meantime."
)

SAFETY_RESPONSE = (
    "It sounds like something serious might be going on. Please talk to a trusted "
    "adult - a parent, teacher, or your branch staff - right away. If you or someone "
    "else may be in danger, please contact emergency services."
)

_SAFETY_KEYWORDS = (
    "kill myself", "suicide", "hurt myself", "self harm", "self-harm",
    "want to die", "end my life", "hurting me", "abuse", "being hurt",
)

_CHAT_REPLY_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student, chatting about the question "
    "they're currently working on. Never reveal the final answer. Keep language "
    "encouraging, age-appropriate, and focused on this question - redirect politely if "
    "the student's message drifts off-topic."
)

_WHY_WRONG_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student. Explain, in age-appropriate "
    "language, why the student's selected answer is wrong and what misconception it "
    "suggests - without stating the final answer. Ground your explanation in the "
    "question and the student's own message."
)

_MAX_CHAT_REPLY_TOKENS = 400

# AUD-X-08: what one chat turn reserves against the per-day ceiling before it runs,
# replaced by the turn's real accumulated cost once it finishes. Covers the most expensive
# shape a turn can take - the intent classification every turn pays for (150 output
# tokens), plus the largest single content generation it can route to (a solution, 800).
# A hint turn therefore over-reserves briefly, which is the safe direction for a ceiling.
# `test_cost_reservation_estimates.py` asserts this still bounds the real gateway's own
# worst case for both calls, so a pricing change cannot silently make it too small.
#
# 2.625 cents is the worst case on the most expensive priced model (Sonnet 5), which is
# also the unpriced-model fallback rate; the deployed model (Haiku 4.5) is 0.875. Rounded
# up to 3.0. Against the 100-cent ceiling that still allows 33 simultaneous turns before
# any student is degraded, and `settle` returns the difference as soon as the turn ends.
INTENT_CLASSIFICATION_TOKENS = 150
MAX_TURN_CONTENT_TOKENS = 800
TURN_RESERVATION_ESTIMATE_CENTS = 3.0


def screen_for_safety_concern(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in _SAFETY_KEYWORDS)


async def classify_intent(
    *, gateway: BedrockGateway, redacted_message: str, session_spend_cents: float
) -> tuple[str, float]:
    """Raises `BedrockGatewayError` on failure - the caller (`nodes.py::tutor_chat`)
    treats that as "off_topic", the safest deterministic fallback (SPEC §5.25.3).
    """
    result = await gateway.generate_structured(
        task=BedrockTask.LEARNING_CHAT_INTENT,
        system_prompt=(
            "Classify the student's chat message into exactly one category: "
            "question_help, request_hint, request_solution, request_video, why_wrong, "
            "or off_topic."
        ),
        payload=LearningChatIntentPayload(redacted_message=redacted_message),
        response_model=LearningChatIntentResponse,
        max_output_tokens=150,
        session_spend_cents=session_spend_cents,
    )
    return result.value.intent, result.cost_cents


def _fallback_chat_response() -> TutorChatResponse:
    return TutorChatResponse(
        reply_text=(
            "I'm having a little trouble right now - try asking again in a moment, or "
            "use the Hint/Solution/Video buttons for this question."
        ),
        answer_revealed=False,
    )


async def _tutor_chat_call(
    *,
    gateway: BedrockGateway,
    system_prompt: str,
    context: TutorContext,
    redacted_message: str,
    correct_answer_text: str,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[TutorChatResponse, float]:
    payload = TutorChatPayload(
        grade=context.grade,
        current_topic=context.topic,
        skill=context.skill,
        question=context.question,
        selected_answer=context.selected_wrong_answer,
        relevant_learning_fact=relevant_learning_fact,
        redacted_message=redacted_message,
    )
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR_CHAT,
            system_prompt=system_prompt,
            payload=payload,
            response_model=TutorChatResponse,
            max_output_tokens=_MAX_CHAT_REPLY_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError:
        return _fallback_chat_response(), 0.0

    response = result.value
    if (
        response.answer_revealed
        or leak_phrase_present(response.reply_text)
        or answer_text_leaked(response.reply_text, correct_answer_text)
    ):
        return _fallback_chat_response(), result.cost_cents
    return response, result.cost_cents


async def generate_chat_reply(
    *,
    gateway: BedrockGateway,
    context: TutorContext,
    redacted_message: str,
    correct_answer_text: str,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[TutorChatResponse, float]:
    """`question_help`: a general, grounded chat reply about the current question -
    valid whether or not the student has answered it yet.
    """
    return await _tutor_chat_call(
        gateway=gateway,
        system_prompt=_CHAT_REPLY_SYSTEM_PROMPT,
        context=context,
        redacted_message=redacted_message,
        correct_answer_text=correct_answer_text,
        session_spend_cents=session_spend_cents,
        relevant_learning_fact=relevant_learning_fact,
    )


async def explain_why_wrong(
    *,
    gateway: BedrockGateway,
    context: TutorContext,
    redacted_message: str,
    correct_answer_text: str,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[TutorChatResponse, float]:
    """`why_wrong`: explains the misconception behind the student's actual wrong
    answer - only reachable once the caller has confirmed a real wrong attempt exists
    (see `nodes.py::tutor_chat`'s `has_wrong_attempt` gate).
    """
    return await _tutor_chat_call(
        gateway=gateway,
        system_prompt=_WHY_WRONG_SYSTEM_PROMPT,
        context=context,
        redacted_message=redacted_message,
        correct_answer_text=correct_answer_text,
        session_spend_cents=session_spend_cents,
        relevant_learning_fact=relevant_learning_fact,
    )
