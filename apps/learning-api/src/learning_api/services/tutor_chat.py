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
    OutputTruncatedError,
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

HINT_LADDER_EXHAUSTED_MESSAGE = (
    "You've already seen every hint for this question. Want to look at the full "
    "solution, or give it one more try with what you know now?"
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

# D-207: both prompts now bound the reply's *length* as well as its content. The ceiling
# alone did not - a model told only "be encouraging" writes until it is cut off, which is
# exactly what happened on staging at 2026-08-06T20:14:08Z: `output_truncated` at 400
# tokens, and the student got `_fallback_chat_response`'s apology instead of an answer.
# Asking for 3-4 sentences is cheaper than raising the ceiling and hoping, and it is also
# the better reply for a K-12 student reading on a phone.
_BREVITY_RULE = (
    " Reply in at most 4 short sentences - a student reads this on a phone, and a wall of "
    "text is not help. Do not restate the question back to them."
    # D-217 (point 3): the chat bubble renders a tiny **bold**/`code` subset only, so
    # Markdown headings/bullets and LaTeX arrive as literal characters. Write plain text.
    " Write plain sentences - no Markdown headings or bullet characters and no LaTeX;"
    " write any math inline like 2x + 3 = 7."
)

_CHAT_REPLY_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student, chatting about the question "
    "they're currently working on. Never reveal the final answer. Keep language "
    "encouraging, age-appropriate, and focused on this question - redirect politely if "
    "the student's message drifts off-topic." + _BREVITY_RULE
)

_WHY_WRONG_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student. Explain, in age-appropriate "
    "language, why the student's selected answer is wrong and what misconception it "
    "suggests - without stating the final answer. Ground your explanation in the "
    "question and the student's own message." + _BREVITY_RULE
)

_MAX_CHAT_REPLY_TOKENS = 400
# The one honest retry D-115 names: same prompt under a *bigger* ceiling, used only after
# a real truncation, bounded to a single extra attempt.
#
# It **does** widen what a turn can cost, and `TURN_RESERVATION_ESTIMATE_CENTS` below was
# raised for it. The first version of this comment claimed otherwise, reasoning that
# `MAX_TURN_CONTENT_TOKENS` (800, sized for a solution) already exceeded it - which is
# wrong twice over: 400 + 800 is 1200, and the retry is a whole extra call, so it pays a
# second time for the ~2000 input tokens the worst-case estimate assumes. Measured on the
# most expensive priced model: 2.6250 -> 3.8250 cents.
_RETRY_CHAT_REPLY_TOKENS = 800

# AUD-X-08: what one chat turn reserves against the per-day ceiling before it runs,
# replaced by the turn's real accumulated cost once it finishes. It must cover the most
# expensive *shape* a turn can take, and since D-207 there are two shapes rather than one:
#
#   - dispatch to a solution: intent (150 out) + one content call (800 out)
#   - a chat reply that truncates: intent (150 out) + 400 out + the retry's 800 out
#
# The second is now the worse of the two, and not only because 400 + 800 > 800: the retry
# is a separate call, so it pays again for the ~2000 input tokens `worst_case_cost_cents`
# assumes. `test_cost_reservation_estimates.py` asserts both shapes, so neither a pricing
# change nor another retry can silently make this too small - which is exactly what
# happened when the retry was added and the constant was not revisited.
#
# 3.825 cents is the worst case on the most expensive priced model (Sonnet 5), which is
# also the unpriced-model fallback rate; the deployed model (Haiku 4.5) is 1.275. Rounded
# up to 4.0. Against the 100-cent ceiling that still allows 25 simultaneous turns before
# any student is degraded, and `settle` returns the difference as soon as the turn ends.
INTENT_CLASSIFICATION_TOKENS = 150
MAX_TURN_CONTENT_TOKENS = 800
# The two content calls a truncated-then-retried chat turn makes, in order.
CHAT_RETRY_CONTENT_TOKENS = (_MAX_CHAT_REPLY_TOKENS, _RETRY_CHAT_REPLY_TOKENS)
TURN_RESERVATION_ESTIMATE_CENTS = 4.0


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
    async def _call(max_output_tokens: int, spend: float):
        return await gateway.generate_structured(
            task=BedrockTask.TUTOR_CHAT,
            system_prompt=system_prompt,
            payload=payload,
            response_model=TutorChatResponse,
            max_output_tokens=max_output_tokens,
            session_spend_cents=spend,
        )

    truncation_cost = 0.0
    try:
        result = await _call(_MAX_CHAT_REPLY_TOKENS, session_spend_cents)
    except OutputTruncatedError as exc:
        # D-207. The gateway refuses to retry under the *same* ceiling and is right to
        # (D-115) - but "the honest fix is a bigger ceiling" is a fix the caller can
        # actually apply, and this is the only place that knows a truncated tutor reply
        # is worth one more try. Without it the student's question is answered with an
        # apology, which is what staging did. Still bounded: one retry, then the fallback.
        truncation_cost = exc.cost_cents
        try:
            result = await _call(
                _RETRY_CHAT_REPLY_TOKENS, session_spend_cents + truncation_cost
            )
        except BedrockGatewayError as retry_exc:
            return _fallback_chat_response(), truncation_cost + retry_exc.cost_cents
    except BedrockGatewayError as exc:
        return _fallback_chat_response(), exc.cost_cents

    result_cost = result.cost_cents + truncation_cost
    response = result.value
    if (
        response.answer_revealed
        or leak_phrase_present(response.reply_text)
        or answer_text_leaked(response.reply_text, correct_answer_text)
    ):
        return _fallback_chat_response(), result_cost
    return response, result_cost


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
