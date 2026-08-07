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
    answer_leaked_beyond_the_question,
    answers_agree,
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
from pydantic import ValidationError

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


def stored_solution(
    canonical_solution: dict | None, correct_answer_text: str
) -> SolutionResponse | None:
    """The authored bank's own verified solution for this template, or `None`.

    D-207. Authored templates carry a `canonical_solution` that the S20 pipeline already
    proved correct before the item was ever approved: `check_hint_solution_answer_agreement`
    compares its `final_answer` to the declared correct option, and
    `check_sympy_independent_solve` re-solves the equation independently. The loader writes
    it into `question_templates.canonical_solution` on every deploy - and until now nothing
    on the serving path read it back. Every "show me the solution" therefore paid for a
    Bedrock call to re-derive, less reliably, a solution the row already held.

    Preferring the stored one is better on all three axes that matter here: it is
    verified rather than merely cross-checked, it costs nothing, and it returns in a
    database read instead of ~3 s of generation. Shape templates have no canonical
    solution, so they still take the generated path - which is why this returns `None`
    rather than raising.

    The final-answer check runs again here even though the bank already passed it. The
    stored blob is JSON with no database-level constraint, the correct option can be
    re-pointed by a later variant, and this is content a child reads: re-checking costs
    one string comparison and removes the class of failure where a stale row silently
    contradicts the score.
    """
    if not canonical_solution:
        return None
    try:
        solution = SolutionResponse.model_validate(canonical_solution)
    except ValidationError:
        logger.warning("stored canonical_solution failed validation; generating instead")
        return None
    if not solution.steps:
        return None
    if not answers_agree(solution.final_answer, correct_answer_text):
        logger.warning(
            "stored canonical_solution.final_answer disagrees with the correct answer; "
            "generating instead"
        )
        return None
    return solution


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

    if not answers_agree(result.value.final_answer, correct_answer_text):
        # SPEC §5.12.2 "verify calculations with tools" - never let the model's stated
        # final answer stand in for the score-bearing correct answer; the deterministic
        # fallback is guaranteed correct because it's built directly from
        # `correct_answer_text` (already validated at question-generation time, §5.8.5).
        #
        # D-207: the comparison is `answers_agree`, not `!=` on stripped strings. The
        # strict form rejected `'8 weeks'` against an option reading `'8'` - a *correct*
        # solution thrown away over a unit word - and that is what fired on staging at
        # 2026-08-06T20:13:32Z, so the student who asked for a solution got the two-step
        # placeholder below instead of six real steps. A genuinely wrong answer still
        # fails: `answers_agree` falls back to SymPy value equality, not to substring
        # matching.
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
    # Same rule as the authoring gate (D-201): a value the question already shows the
    # student is not leaked by a hint repeating it. Without this the runtime suppresses a
    # perfectly good personalised hint - and falls back to the canonical one - for any
    # question whose answer coincides with one of its own given quantities.
    if leak_phrase_present(response.hint_text) or answer_leaked_beyond_the_question(
        hint_text=response.hint_text,
        correct_answer_text=correct_answer_text,
        question_text=context.question,
    ):
        logger.warning("hint personalization leaked the answer; using canonical content")
        return _canonical_as_response(canonical_hint_text), result.cost_cents, False
    if next_canonical_hint_text and next_canonical_hint_text.strip() in response.hint_text:
        logger.warning(
            "hint personalization violated ladder monotonicity; using canonical content"
        )
        return _canonical_as_response(canonical_hint_text), result.cost_cents, False
    return response, result.cost_cents, True
