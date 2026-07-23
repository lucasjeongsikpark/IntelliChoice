import asyncio
import os

import pytest
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_evals.llm_judge import (
    LEARNING_JUDGE_DIMENSIONS,
    QA_JUDGE_DIMENSIONS,
    run_llm_judge,
)
from intellichoice_evals.settings import get_eval_settings
from intellichoice_shared.bedrock import BedrockTask


def test_judge_model_default_differs_from_production_answerer_models() -> None:
    # SPEC §5.31.3: "use a judge model different from the production answerer when
    # possible" - satisfied architecturally by the default settings alone, ahead of any
    # real credential to verify it against (D-025/D-035/D-046 posture).
    settings = get_eval_settings()
    assert settings.bedrock_judge_model_id != "anthropic.claude-sonnet-5"


def test_run_llm_judge_scores_exactly_the_requested_learning_dimensions() -> None:
    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={BedrockTask.LLM_JUDGE: "anthropic.claude-haiku-4-5"},
        )
        result = await run_llm_judge(
            gateway,
            domain="learning",
            content_to_judge="Think about what happens when you subtract 3 from both sides.",
            context="Skill: linear_one_step. Grade: 7.",
            session_spend_cents=0.0,
        )
        assert {score.dimension for score in result.scores} == set(LEARNING_JUDGE_DIMENSIONS)
        assert result.overall_pass is True

    asyncio.run(run())


def test_run_llm_judge_accepts_a_narrower_qa_dimension_list() -> None:
    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={BedrockTask.LLM_JUDGE: "anthropic.claude-haiku-4-5"},
        )
        result = await run_llm_judge(
            gateway,
            domain="qa",
            content_to_judge="Our North branch is open Monday-Friday, 9am-6pm.",
            context="Source: public-branch-directory.",
            session_spend_cents=0.0,
            dimensions=["citation_support"],
        )
        assert [score.dimension for score in result.scores] == ["citation_support"]

    asyncio.run(run())


def _no_real_bedrock_creds_reason() -> str | None:
    if not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        return "no real AWS credentials in this environment (D-025 posture)"
    return None


@pytest.mark.skipif(
    (_reason := _no_real_bedrock_creds_reason()) is not None, reason=_reason or ""
)
def test_run_llm_judge_against_real_bedrock_creds() -> None:
    """Never runs in this project (no real AWS credentials exist anywhere in this
    codebase's history, D-025) - the point is that the skip condition and the real-
    provider wiring are correct, so this runs against staging creds per ROADMAP S30's
    own "Done when" wording, not that it's exercised here.
    """

    async def run() -> None:
        settings = get_eval_settings()
        gateway = ResilientBedrockGateway(
            provider=AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region),
            model_registry={BedrockTask.LLM_JUDGE: settings.bedrock_judge_model_id},
            call_timeout_s=settings.bedrock_call_timeout_s,
            max_retries=settings.bedrock_max_retries,
            circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
            circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
            session_budget_cents=settings.bedrock_run_budget_cents,
        )
        result = await run_llm_judge(
            gateway,
            domain="qa",
            content_to_judge="Our North branch is open Monday-Friday, 9am-6pm.",
            context="Source: public-branch-directory.",
            session_spend_cents=0.0,
            dimensions=QA_JUDGE_DIMENSIONS,
        )
        assert result.scores

    asyncio.run(run())
