import asyncio

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.provider import ProviderCallError, RawEmbedding, RawGeneration
from intellichoice_shared.bedrock import (
    AlignmentReviewPayload,
    AlignmentReviewResponse,
    AmbiguityReviewPayload,
    AmbiguityReviewResponse,
    BedrockTask,
    BedrockTimeoutError,
    BedrockTutorPayload,
    CircuitOpenError,
    CostBudgetExceededError,
    DifficultyReviewPayload,
    DifficultyReviewResponse,
    GeneratedTemplateResponse,
    GeneratorPayload,
    HintResponse,
    SolverPayload,
    SolverResponse,
    StructuredOutputError,
)
from pydantic import BaseModel

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v2:0"

MODEL_ID = "anthropic.claude-test"


def _payload() -> BedrockTutorPayload:
    return BedrockTutorPayload(
        grade="6",
        current_topic="Linear Equations",
        skill="Two-Step Equations",
        estimated_level="0.40",
        question="Solve for x: x + 3 = 7",
        selected_answer="3",
        relevant_learning_fact=None,
    )


class _ScriptedProvider:
    """Test double whose `raw_generate` follows a scripted sequence of behaviors -
    return valid text, invalid text, raise, or hang - one per call.
    """

    def __init__(self, script: list[str]) -> None:
        self._script = list(script)
        self.calls = 0

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
    ) -> RawGeneration:
        self.calls += 1
        action = self._script.pop(0)
        if action == "raise":
            raise ProviderCallError("simulated transient failure")
        if action == "hang":
            await asyncio.sleep(10)
        if action == "invalid":
            return RawGeneration(text="not json", input_tokens=10, output_tokens=10)
        assert action == "valid"
        return RawGeneration(
            text='{"hint_text": "h", "concept_reminder": "c", "next_step_prompt": "n", '
            '"answer_revealed": false, "difficulty": 1}',
            input_tokens=10,
            output_tokens=10,
        )


def test_generate_structured_success_with_mock_provider() -> None:
    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={BedrockTask.TUTOR: MODEL_ID},
        )
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt="system",
            payload=_payload(),
            response_model=HintResponse,
            max_output_tokens=200,
            session_spend_cents=0.0,
        )
        assert isinstance(result.value, HintResponse)
        assert result.model_id == MODEL_ID
        assert result.cost_cents > 0
        assert result.repaired is False

    asyncio.run(run())


def test_malformed_output_repairs_once_then_falls_back() -> None:
    async def run() -> None:
        provider = _ScriptedProvider(["invalid", "invalid"])
        gateway = ResilientBedrockGateway(
            provider=provider, model_registry={BedrockTask.TUTOR: MODEL_ID}, max_retries=0
        )
        with pytest.raises(StructuredOutputError) as exc_info:
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        assert provider.calls == 2  # original attempt + exactly one repair retry
        assert exc_info.value.cost_cents > 0  # real spend still counted toward the session

    asyncio.run(run())


def test_repair_retry_recovers_a_malformed_first_attempt() -> None:
    async def run() -> None:
        provider = _ScriptedProvider(["invalid", "valid"])
        gateway = ResilientBedrockGateway(
            provider=provider, model_registry={BedrockTask.TUTOR: MODEL_ID}, max_retries=0
        )
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt="system",
            payload=_payload(),
            response_model=HintResponse,
            max_output_tokens=200,
            session_spend_cents=0.0,
        )
        assert result.repaired is True
        assert isinstance(result.value, HintResponse)

    asyncio.run(run())


def test_timeout_raises_after_exhausting_bounded_retries() -> None:
    async def run() -> None:
        provider = _ScriptedProvider(["hang", "hang"])
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            call_timeout_s=0.05,
            max_retries=1,
            backoff_base_s=0.01,
        )
        with pytest.raises(BedrockTimeoutError):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        assert provider.calls == 2

    asyncio.run(run())


def test_circuit_breaker_opens_after_threshold_and_blocks_further_calls() -> None:
    async def run() -> None:
        provider = _ScriptedProvider(["raise", "raise"])
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            max_retries=0,
            circuit_failure_threshold=2,
            circuit_cooldown_s=60,
        )
        for _ in range(2):
            with pytest.raises(BedrockTimeoutError):
                await gateway.generate_structured(
                    task=BedrockTask.TUTOR,
                    system_prompt="system",
                    payload=_payload(),
                    response_model=HintResponse,
                    max_output_tokens=200,
                    session_spend_cents=0.0,
                )

        with pytest.raises(CircuitOpenError):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        # The circuit-open guard short-circuits before any further provider call.
        assert provider.calls == 2

    asyncio.run(run())


def test_cost_budget_exceeded_before_any_provider_call() -> None:
    async def run() -> None:
        provider = _ScriptedProvider([])
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            session_budget_cents=0.01,
        )
        with pytest.raises(CostBudgetExceededError):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        assert provider.calls == 0

    asyncio.run(run())


_GENERATION_CASES: list[tuple[BedrockTask, BaseModel, type[BaseModel]]] = [
    (
        BedrockTask.QUESTION_GENERATION,
        GeneratorPayload(
            topic_name="Linear Equations",
            skill_name="One-Step Equations",
            grade_band="6-7",
            difficulty_label=1,
            allowed_shape_keys=["one_step_add", "one_step_sub"],
            allowed_correct_option_generators=["format_integer"],
            allowed_distractor_generator_keys=[
                "distractor_sign_flip",
                "distractor_off_by_one",
                "distractor_scaled",
            ],
        ),
        GeneratedTemplateResponse,
    ),
    (
        BedrockTask.QUESTION_GENERATION,
        SolverPayload(
            rendered_question="Solve for x: x + 3 = 7",
            option_a="4",
            option_b="3",
            option_c="10",
            option_d="21",
        ),
        SolverResponse,
    ),
    (
        BedrockTask.QUESTION_REVIEW,
        DifficultyReviewPayload(
            rendered_question="Solve for x: x + 3 = 7",
            option_a="4",
            option_b="3",
            option_c="10",
            option_d="21",
            skill_name="One-Step Equations",
            proposed_difficulty=2,
        ),
        DifficultyReviewResponse,
    ),
    (
        BedrockTask.QUESTION_REVIEW,
        AmbiguityReviewPayload(
            rendered_question="Solve for x: x + 3 = 7",
            option_a="4",
            option_b="3",
            option_c="10",
            option_d="21",
        ),
        AmbiguityReviewResponse,
    ),
    (
        BedrockTask.QUESTION_REVIEW,
        AlignmentReviewPayload(
            rendered_question="Solve for x: x + 3 = 7",
            topic_name="Linear Equations",
            skill_name="One-Step Equations",
        ),
        AlignmentReviewResponse,
    ),
]


@pytest.mark.parametrize(("task", "payload", "response_model"), _GENERATION_CASES)
def test_mock_provider_produces_valid_generation_pipeline_output(
    task: BedrockTask, payload: BaseModel, response_model: type[BaseModel]
) -> None:
    """The mock provider (dev/test default) must return schema-valid output for every S9
    question-generation response type, so the pipeline runs end-to-end without a real
    model - the negative/agreement paths are covered by `test_ai_pipeline`'s scripted
    gateway.
    """

    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={
                BedrockTask.QUESTION_GENERATION: MODEL_ID,
                BedrockTask.QUESTION_REVIEW: MODEL_ID,
            },
        )
        result = await gateway.generate_structured(
            task=task,
            system_prompt="system",
            payload=payload,
            response_model=response_model,
            max_output_tokens=200,
            session_spend_cents=0.0,
        )
        assert isinstance(result.value, response_model)

    asyncio.run(run())


class _ScriptedEmbeddingProvider:
    """Mirrors `_ScriptedProvider` but for `raw_embed` - used to exercise the
    embedding-specific timeout/retry path independent of `MockBedrockProvider`.
    """

    def __init__(self, script: list[str]) -> None:
        self._script = list(script)
        self.calls = 0

    async def raw_embed(self, *, model_id: str, texts: list[str]) -> RawEmbedding:
        self.calls += 1
        action = self._script.pop(0)
        if action == "raise":
            raise ProviderCallError("simulated transient failure")
        assert action == "valid"
        return RawEmbedding(vectors=[[0.1, 0.2, 0.3] for _ in texts], input_tokens=10)


def test_create_embedding_success_with_mock_provider() -> None:
    async def run() -> None:
        mock = MockBedrockProvider()
        gateway = ResilientBedrockGateway(
            provider=mock,
            embedding_provider=mock,
            model_registry={BedrockTask.EMBEDDING: EMBEDDING_MODEL_ID},
        )
        result = await gateway.create_embedding(
            texts=["hello world", "a second chunk"], session_spend_cents=0.0
        )
        assert result.model_id == EMBEDDING_MODEL_ID
        assert len(result.vectors) == 2
        assert result.dimensions == 1024
        assert all(len(v) == 1024 for v in result.vectors)
        assert result.cost_cents > 0

    asyncio.run(run())


def test_create_embedding_same_text_produces_the_same_vector() -> None:
    async def run() -> None:
        mock = MockBedrockProvider()
        gateway = ResilientBedrockGateway(
            provider=mock,
            embedding_provider=mock,
            model_registry={BedrockTask.EMBEDDING: EMBEDDING_MODEL_ID},
        )
        first = await gateway.create_embedding(texts=["repeat me"], session_spend_cents=0.0)
        second = await gateway.create_embedding(texts=["repeat me"], session_spend_cents=0.0)
        assert first.vectors == second.vectors

        different = await gateway.create_embedding(
            texts=["something else entirely"], session_spend_cents=0.0
        )
        assert different.vectors != first.vectors

    asyncio.run(run())


def test_create_embedding_without_embedding_provider_raises_clearly() -> None:
    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={BedrockTask.EMBEDDING: EMBEDDING_MODEL_ID},
        )
        with pytest.raises(ValueError, match="embedding_provider"):
            await gateway.create_embedding(texts=["x"], session_spend_cents=0.0)

    asyncio.run(run())


def test_create_embedding_retries_then_raises_timeout_error() -> None:
    async def run() -> None:
        provider = _ScriptedEmbeddingProvider(["raise", "raise", "raise"])
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            embedding_provider=provider,
            model_registry={BedrockTask.EMBEDDING: EMBEDDING_MODEL_ID},
            max_retries=2,
            backoff_base_s=0.0,
        )
        with pytest.raises(BedrockTimeoutError):
            await gateway.create_embedding(texts=["x"], session_spend_cents=0.0)
        assert provider.calls == 3

    asyncio.run(run())


def test_create_embedding_cost_budget_exceeded_before_any_provider_call() -> None:
    async def run() -> None:
        provider = _ScriptedEmbeddingProvider([])
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            embedding_provider=provider,
            model_registry={BedrockTask.EMBEDDING: EMBEDDING_MODEL_ID},
            session_budget_cents=0.0000001,
        )
        with pytest.raises(CostBudgetExceededError):
            await gateway.create_embedding(
                texts=["a fairly long chunk of text to estimate tokens from"],
                session_spend_cents=0.0,
            )
        assert provider.calls == 0

    asyncio.run(run())
