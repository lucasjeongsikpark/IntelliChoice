"""Tutor Agent / Hint & Solution Generators (SPEC §5.12, §5.11.4-5.11.5).

Both generators call the Bedrock Gateway once, then always return usable content: on
any `BedrockGatewayError` (timeout, circuit open, budget exceeded, still-invalid after
repair) they fall back to a deterministic, pre-verified message instead of surfacing an
error to the student (SPEC §5.25.3's "deterministic fallback"; ROADMAP S8's "safe
fallbacks work" completion criterion). `generate_solution` additionally cross-checks the
model's `final_answer` against the question's actual correct answer before accepting it
(SPEC §5.12.2 "verify calculations with tools") - a mismatch is treated exactly like an
invalid structured output.

`generate_personalized_hint` (S21, SPEC §5.11.4/§5.30.1 widened) rewrites one canonical
hint-ladder level using context TUTOR's payload doesn't carry (attempt count, hint
level, misconception tag, prior-hint summaries) - see DECISIONS.md's D-023 follow-up.
It never trusts the model's output as-is: a failed leak or monotonicity check is
treated exactly like a `BedrockGatewayError`, falling back to the canonical text
verbatim (never surfacing bad content, same posture as every other Bedrock caller in
this module).
"""

import logging

from intellichoice_curriculum.authored_validation import (
    answer_text_leaked,
    leak_phrase_present,
)
from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockGatewayError,
    BedrockTask,
    BedrockTutorPayload,
    HintPersonalizationPayload,
    HintPersonalizationResponse,
    HintResponse,
    SolutionResponse,
    SolutionStep,
    TutorContext,
)

logger = logging.getLogger(__name__)

_HINT_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student. Given the student's grade, "
    "topic, skill, question, and the wrong answer they chose, write an age-appropriate "
    "hint. Never reveal the final answer. Keep language encouraging and growth-oriented."
)

_SOLUTION_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student. Given the student's grade, "
    "topic, skill, and question, write a clear step-by-step solution ending in the "
    "final answer. Keep language age-appropriate and growth-oriented."
)

_MAX_HINT_TOKENS = 400
_MAX_SOLUTION_TOKENS = 800

_HINT_PERSONALIZATION_SYSTEM_PROMPT = (
    "You are a friendly math tutor for a K-12 student. Rewrite the canonical hint below "
    "so it speaks to this specific student's wrong answer and the misconception it "
    "suggests, at the given hint level (higher levels may be more explicit than the "
    "canonical text, but must never state the final answer). Keep language encouraging "
    "and age-appropriate, and stay grounded in the canonical hint's method - do not "
    "introduce a different approach."
)

_MAX_HINT_PERSONALIZATION_TOKENS = 400


def _payload_from_context(
    context: TutorContext, relevant_learning_fact: str | None
) -> BedrockTutorPayload:
    return BedrockTutorPayload(
        grade=context.grade,
        current_topic=context.topic,
        skill=context.skill,
        estimated_level=context.estimated_level,
        question=context.question,
        selected_answer=context.selected_wrong_answer,
        relevant_learning_fact=relevant_learning_fact,
    )


def _fallback_hint(context: TutorContext) -> HintResponse:
    return HintResponse(
        hint_text=(
            f"Take another look at the {context.skill} step in this problem - what "
            "operation would undo what's happening to the unknown value?"
        ),
        concept_reminder=f"Review how {context.skill} works within {context.topic}.",
        next_step_prompt="Try applying that operation to both sides and see what you get.",
        answer_revealed=False,
        difficulty=1,
    )


def _fallback_solution(context: TutorContext, correct_answer_text: str) -> SolutionResponse:
    return SolutionResponse(
        steps=[
            SolutionStep(
                step_number=1,
                explanation=f"Start from the question: {context.question}",
                expression=context.question,
                common_mistake=None,
            ),
            SolutionStep(
                step_number=2,
                explanation=(
                    f"Apply the standard method for {context.skill} to isolate the answer."
                ),
                expression=correct_answer_text,
                common_mistake="Forgetting to apply the same operation to both sides.",
            ),
        ],
        final_answer=correct_answer_text,
    )


async def generate_hint(
    *,
    gateway: BedrockGateway,
    context: TutorContext,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[HintResponse, float]:
    """Returns the hint plus the cost actually incurred - 0.0 on a fallback with no real
    provider spend, or the partial spend a failed-but-billed call still incurred.
    """
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt=_HINT_SYSTEM_PROMPT,
            payload=_payload_from_context(context, relevant_learning_fact),
            response_model=HintResponse,
            max_output_tokens=_MAX_HINT_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("hint generation fell back to deterministic content: %s", exc)
        return _fallback_hint(context), exc.cost_cents
    return result.value, result.cost_cents


async def generate_solution(
    *,
    gateway: BedrockGateway,
    context: TutorContext,
    correct_answer_text: str,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[SolutionResponse, float]:
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt=_SOLUTION_SYSTEM_PROMPT,
            payload=_payload_from_context(context, relevant_learning_fact),
            response_model=SolutionResponse,
            max_output_tokens=_MAX_SOLUTION_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("solution generation fell back to deterministic content: %s", exc)
        return _fallback_solution(context, correct_answer_text), exc.cost_cents

    if result.value.final_answer.strip() != correct_answer_text.strip():
        # SPEC §5.12.2 "verify calculations with tools" - never let the model's stated
        # final answer stand in for the score-bearing correct answer; the deterministic
        # fallback is guaranteed correct because it's built directly from
        # `correct_answer_text` (already validated at question-generation time, §5.8.5).
        logger.warning(
            "solution generation returned a final_answer that didn't match the correct "
            "answer; using deterministic fallback instead"
        )
        return _fallback_solution(context, correct_answer_text), result.cost_cents
    return result.value, result.cost_cents


def _canonical_as_response(canonical_hint_text: str) -> HintPersonalizationResponse:
    return HintPersonalizationResponse(
        hint_text=canonical_hint_text,
        concept_reminder="Review the method this hint describes.",
        next_step_prompt="Try applying that method to this problem.",
        answer_revealed=False,
        difficulty=1,
    )


async def generate_personalized_hint(
    *,
    gateway: BedrockGateway,
    context: TutorContext,
    canonical_hint_text: str,
    next_canonical_hint_text: str | None,
    hint_level: int,
    attempt_count: int,
    misconception_tag: str | None,
    previous_hint_summaries: list[str],
    correct_answer_text: str,
    session_spend_cents: float,
    relevant_learning_fact: str | None = None,
) -> tuple[HintPersonalizationResponse, float, bool]:
    """Rewrites `canonical_hint_text` for this student's actual wrong option and attempt
    history (SPEC §5.11.4/§5.30.1 widened, D-023 follow-up). Returns
    `(content, cost incurred, was_personalized)` - `was_personalized=False` on any
    fallback path (gateway failure, a leaked answer, or a monotonicity violation against
    `next_canonical_hint_text`), in which case `content.hint_text ==
    canonical_hint_text` verbatim. Never trusts the model's own output as safe -
    every accepted response is re-checked against the same leak-phrase and
    verbatim-answer rules `authored_validation.py` already enforces at authoring time,
    applied here at generation time against the real question's real answer.
    """
    payload = HintPersonalizationPayload(
        grade=context.grade,
        skill=context.skill,
        question=context.question,
        selected_answer=context.selected_wrong_answer,
        canonical_hint_text=canonical_hint_text,
        misconception_tag=misconception_tag,
        attempt_count=attempt_count,
        hint_level=hint_level,
        previous_hint_summaries=previous_hint_summaries,
        relevant_learning_fact=relevant_learning_fact,
    )
    try:
        result = await gateway.generate_structured(
            task=BedrockTask.HINT_PERSONALIZATION,
            system_prompt=_HINT_PERSONALIZATION_SYSTEM_PROMPT,
            payload=payload,
            response_model=HintPersonalizationResponse,
            max_output_tokens=_MAX_HINT_PERSONALIZATION_TOKENS,
            session_spend_cents=session_spend_cents,
        )
    except BedrockGatewayError as exc:
        logger.warning("hint personalization fell back to canonical content: %s", exc)
        return _canonical_as_response(canonical_hint_text), exc.cost_cents, False

    response = result.value
    if response.answer_revealed:
        logger.warning("hint personalization set answer_revealed; using canonical content")
        return _canonical_as_response(canonical_hint_text), result.cost_cents, False
    if leak_phrase_present(response.hint_text) or answer_text_leaked(
        response.hint_text, correct_answer_text
    ):
        logger.warning("hint personalization leaked the answer; using canonical content")
        return _canonical_as_response(canonical_hint_text), result.cost_cents, False
    if next_canonical_hint_text and next_canonical_hint_text.strip() in response.hint_text:
        logger.warning(
            "hint personalization violated ladder monotonicity; using canonical content"
        )
        return _canonical_as_response(canonical_hint_text), result.cost_cents, False
    return response, result.cost_cents, True
