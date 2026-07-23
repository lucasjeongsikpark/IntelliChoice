"""SPEC §5.31.3 LLM-as-a-Judge harness - `BedrockTask.LLM_JUDGE`'s first real caller
(reserved, unused since S8, D-022).

`run_llm_judge` is a thin wrapper over `BedrockGateway.generate_structured`, same shape
as every other task-specific service function in this codebase (`tutor.generate_hint`,
`report.generate_student_report`, etc.) - it builds no gateway itself and makes no
decision about which model to use; that's the caller's `model_registry` entry
(`EvalSettings.bedrock_judge_model_id`, deliberately a different model than either app's
production answerer - see `settings.py`).

The two dimension lists below are copied verbatim from SPEC §5.31.3 - not invented here.
"""

from intellichoice_shared.bedrock import (
    BedrockGateway,
    BedrockTask,
    LlmJudgePayload,
    LlmJudgeResponse,
)

LEARNING_JUDGE_DIMENSIONS = [
    "grade_appropriateness",
    "level_appropriateness",
    "hints_avoid_revealing_the_answer",
    "solution_accuracy_and_clarity",
    "addresses_the_students_error",
    "growth_oriented_tone",
]

QA_JUDGE_DIMENSIONS = [
    "faithfulness_to_sources",
    "citation_support",
    "no_unsupported_guessing",
    "role_appropriateness",
    "appropriate_refusal",
]

_MAX_OUTPUT_TOKENS = 800


async def run_llm_judge(
    gateway: BedrockGateway,
    *,
    domain: str,
    content_to_judge: str,
    context: str,
    session_spend_cents: float,
    dimensions: list[str] | None = None,
) -> LlmJudgeResponse:
    """Scores `content_to_judge` against the SPEC §5.31.3 rubric dimensions for
    `domain` ("learning" or "qa"). `dimensions` defaults to that domain's full SPEC
    list; a caller only interested in one dimension (e.g. just leak-avoidance) can pass
    a narrower list to keep the call cheap.
    """
    resolved_dimensions = dimensions or (
        LEARNING_JUDGE_DIMENSIONS if domain == "learning" else QA_JUDGE_DIMENSIONS
    )
    payload = LlmJudgePayload(
        domain=domain,  # type: ignore[arg-type]
        dimensions=resolved_dimensions,
        content_to_judge=content_to_judge,
        context=context,
    )
    result = await gateway.generate_structured(
        task=BedrockTask.LLM_JUDGE,
        system_prompt=(
            "You are an independent quality judge for a K-12 education product. Score "
            "each requested dimension from 1 (fails) to 5 (excellent) and explain why. "
            "Never reveal or restate a correct answer that the content under review "
            "withholds - your job is to judge it, not complete it."
        ),
        payload=payload,
        response_model=LlmJudgeResponse,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
        session_spend_cents=session_spend_cents,
    )
    return result.value
