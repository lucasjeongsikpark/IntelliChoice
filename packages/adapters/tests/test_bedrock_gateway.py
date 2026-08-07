import asyncio
import logging

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
        if action == "truncated":
            # What real Bedrock returns when it runs out of output budget mid-tool-call:
            # a well-formed JSON fragment of the wrong shape, plus stopReason=max_tokens.
            return RawGeneration(
                text='{"hint_text": "h", "concept_rem',
                input_tokens=10,
                output_tokens=10,
                truncated=True,
                stop_reason="max_tokens",
            )
        assert action == "valid"
        return RawGeneration(
            text='{"hint_text": "h", "concept_reminder": "c", "next_step_prompt": "n", '
            '"answer_revealed": false, "difficulty": 1}',
            input_tokens=10,
            output_tokens=10,
            stop_reason="tool_use",
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


def test_a_truncated_response_is_not_repaired_under_the_same_ceiling() -> None:
    """D-115: repairing a truncation is guaranteed waste - same prompt, same ceiling,
    same truncation, at full input cost. On staging this doubled a doomed 11 s rerank
    into a 21 s one on every single chat turn.
    """

    async def run() -> None:
        provider = _ScriptedProvider(["truncated"])
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
        assert provider.calls == 1  # no repair attempt at all
        assert "max_output_tokens=200" in str(exc_info.value)
        assert exc_info.value.cost_cents > 0  # the truncated call still cost money

    asyncio.run(run())


def test_schema_failures_alone_never_open_the_circuit() -> None:
    """D-115's blast-radius fix. Five consecutive rerank schema failures used to open the
    shared breaker, after which *every* task - `scope_and_intent` included - failed closed
    for 30 s, turning chat into 30 ms refusals. A response that arrives and fails our
    schema is our bug, not evidence that Bedrock is unhealthy.
    """

    async def run() -> None:
        provider = _ScriptedProvider(["invalid", "invalid"] * 4)
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            max_retries=0,
            circuit_failure_threshold=2,
            circuit_cooldown_s=60,
        )
        for _ in range(4):
            with pytest.raises(StructuredOutputError):
                await gateway.generate_structured(
                    task=BedrockTask.TUTOR,
                    system_prompt="system",
                    payload=_payload(),
                    response_model=HintResponse,
                    max_output_tokens=200,
                    session_spend_cents=0.0,
                )

        # Four failures at a threshold of two, and the circuit is still closed: the next
        # call reaches the provider (and succeeds) instead of raising CircuitOpenError.
        provider._script.append("valid")  # noqa: SLF001 - test double's own script
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt="system",
            payload=_payload(),
            response_model=HintResponse,
            max_output_tokens=200,
            session_spend_cents=0.0,
        )
        assert isinstance(result.value, HintResponse)
        assert provider.calls == 9

    asyncio.run(run())


def test_a_provider_outage_still_opens_the_circuit() -> None:
    """The other half of the same decision: real provider-health failures must keep
    tripping the breaker, or the D-115 narrowing would have removed the protection.
    """

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

    asyncio.run(run())


_FAILURE_LOG_CASES: list[tuple[str, list[str], dict, type[Exception]]] = [
    ("schema_invalid", ["invalid", "invalid"], {}, StructuredOutputError),
    ("output_truncated", ["truncated"], {}, StructuredOutputError),
    ("provider_unavailable", ["raise"], {}, BedrockTimeoutError),
    ("budget_exceeded", [], {"session_budget_cents": 0.01}, CostBudgetExceededError),
]


@pytest.mark.parametrize(("reason", "script", "kwargs", "expected"), _FAILURE_LOG_CASES)
def test_every_failure_exit_logs_exactly_one_warning(
    reason: str,
    script: list[str],
    kwargs: dict,
    expected: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-115's root cause was not the truncation - it was that nothing said so. The
    gateway logged successes only, so a call failing on 100% of requests was invisible
    and the symptom surfaced a week later as an unexplained latency gap.
    """

    async def run() -> None:
        provider = _ScriptedProvider(script)
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            max_retries=0,
            **kwargs,
        )
        with (
            caplog.at_level(logging.WARNING, logger="intellichoice_adapters.bedrock.gateway"),
            pytest.raises(expected),
        ):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )

        failures = [r for r in caplog.records if r.message == "bedrock_call_failed"]
        assert len(failures) == 1
        assert failures[0].reason == reason  # type: ignore[attr-defined]
        assert failures[0].task == BedrockTask.TUTOR.value  # type: ignore[attr-defined]
        assert failures[0].duration_ms >= 0  # type: ignore[attr-defined]

    asyncio.run(run())


def test_a_circuit_open_refusal_also_logs_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The 30 ms zero-Bedrock refusals D-113 could not explain: this is the log line that
    would have named them on sight.
    """

    async def run() -> None:
        provider = _ScriptedProvider(["raise"])
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            max_retries=0,
            circuit_failure_threshold=1,
            circuit_cooldown_s=60,
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

        caplog.clear()
        with (
            caplog.at_level(logging.WARNING, logger="intellichoice_adapters.bedrock.gateway"),
            pytest.raises(CircuitOpenError),
        ):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        reasons = [
            r.reason  # type: ignore[attr-defined]
            for r in caplog.records
            if r.message == "bedrock_call_failed"
        ]
        assert reasons == ["circuit_open"]

    asyncio.run(run())


def test_a_successful_call_logs_its_own_duration(caplog: pytest.LogCaptureFixture) -> None:
    """Without `duration_ms` on the success line, attributing a slow turn means diffing
    timestamps between unrelated log lines - which is how a 21 s call read as a "gap".
    """

    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=MockBedrockProvider(),
            model_registry={BedrockTask.TUTOR: MODEL_ID},
        )
        with caplog.at_level(logging.INFO, logger="intellichoice_adapters.bedrock.gateway"):
            await gateway.generate_structured(
                task=BedrockTask.TUTOR,
                system_prompt="system",
                payload=_payload(),
                response_model=HintResponse,
                max_output_tokens=200,
                session_spend_cents=0.0,
            )
        calls = [r for r in caplog.records if r.message == "bedrock_call"]
        assert len(calls) == 1
        assert calls[0].duration_ms >= 0  # type: ignore[attr-defined]

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


class _AlwaysFailProvider:
    """S34: unlike `_ScriptedProvider`, never runs out of script - models a sustained
    Bedrock throttling episode hitting many concurrent in-flight calls at once, not one
    caller retrying sequentially.
    """

    def __init__(self) -> None:
        self.calls = 0

    async def raw_generate(self, **kwargs: object) -> RawGeneration:
        self.calls += 1
        raise ProviderCallError("simulated sustained throttling")


def test_circuit_breaker_caps_provider_calls_even_under_a_concurrent_failure_burst() -> None:
    """S34 SPEC §6.23 "Bedrock throttling" drill, run under real concurrency (a burst of
    simultaneous callers, not one caller retrying sequentially - the more realistic shape
    of a real throttling episode with >100 concurrent learning sessions in flight, per
    §6.23's own "concurrent Bedrock requests" target). Went in expecting to find a gap:
    `_record_failure`/`_circuit_check` are plain instance-attribute reads/writes with no
    lock, so it seemed plausible that many coroutines could all observe "circuit closed"
    and start their own provider call before any of them recorded a failure, letting a
    whole burst through instead of just the first `circuit_failure_threshold`. Verified
    the opposite: asyncio's cooperative scheduling means `_circuit_check`/`_record_
    failure` each run to completion without yielding (no `await` inside either), and
    `asyncio.wait_for`'s own task-creation overhead is enough of a suspension point that
    the loop interleaves one call at a time in practice - exactly `circuit_failure_
    threshold` calls reach the provider, then every remaining concurrent caller gets
    `CircuitOpenError` without another provider call. A real, useful negative result, not
    a gap - see DECISIONS.md's S34 entry.
    """

    async def run() -> None:
        provider = _AlwaysFailProvider()
        gateway = ResilientBedrockGateway(
            provider=provider,
            model_registry={BedrockTask.TUTOR: MODEL_ID},
            max_retries=0,
            circuit_failure_threshold=5,
            circuit_cooldown_s=60,
        )

        async def one_call() -> Exception:
            try:
                await gateway.generate_structured(
                    task=BedrockTask.TUTOR,
                    system_prompt="system",
                    payload=_payload(),
                    response_model=HintResponse,
                    max_output_tokens=200,
                    session_spend_cents=0.0,
                )
                raise AssertionError("expected a failure")
            except (BedrockTimeoutError, CircuitOpenError) as exc:
                return exc

        concurrent_burst = 30
        results = await asyncio.gather(*(one_call() for _ in range(concurrent_burst)))

        # Exactly the configured threshold actually reached the (always-failing)
        # provider - the rest were blocked by the now-open circuit without spending
        # another real call, even though all 30 were launched concurrently.
        assert provider.calls == 5
        timed_out = [r for r in results if isinstance(r, BedrockTimeoutError)]
        circuit_blocked = [r for r in results if isinstance(r, CircuitOpenError)]
        assert len(timed_out) == 5
        assert len(circuit_blocked) == concurrent_burst - 5

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


def test_the_raw_stop_reason_reaches_the_caller() -> None:
    """Carried through rather than collapsed into `truncated` (D-195).

    A boolean that only separates `max_tokens` from everything else cannot answer the
    first question asked of a model new to this account - *why* did it stop. Measured
    need: `mistral.magistral-small-2509` returns a successful Converse response with no
    `toolUse` block at all, and telling that apart from a refusal or a truncation starts
    with the stop reason.
    """

    async def run() -> None:
        gateway = ResilientBedrockGateway(
            provider=_ScriptedProvider(["valid"]),
            model_registry={BedrockTask.TUTOR: MODEL_ID},
        )
        result = await gateway.generate_structured(
            task=BedrockTask.TUTOR,
            system_prompt="s",
            payload=_payload(),
            response_model=HintResponse,
            max_output_tokens=100,
            session_spend_cents=0.0,
        )
        assert result.stop_reason == "tool_use"

    asyncio.run(run())


def test_smoke_cli_classifies_the_failure_modes_it_has_actually_seen() -> None:
    """Each string below is a real error this project has received from Bedrock, not an
    invented one - the classifier exists so that "cannot call it" and "can call it but it
    will not emit our schema" are never reported as the same outcome, because they lead to
    opposite decisions.
    """
    from intellichoice_adapters.bedrock.smoke_cli import classify_failure

    cases = {
        "An error occurred (AccessDeniedException) when calling the Converse operation: "
        "anthropic.claude-sonnet-5 is not available for this account.": "ACCESS DENIED",
        "Bedrock call failed: model did not return a tool_use block": "PARSER INCOMPATIBILITY",
        "structured output still invalid after one repair retry": "VALID CALL, INVALID SCHEMA",
        "ValidationException: toolChoice of type tool is not supported": "UNSUPPORTED TOOL CHOICE",
    }
    for detail, expected in cases.items():
        assert classify_failure(detail).startswith(expected), detail


def test_the_smoke_schema_exercises_what_the_real_contracts_rely_on() -> None:
    """The smoke schema is only useful if passing it means something. It has to carry the
    three properties the pipeline's real response models depend on, or a model could pass
    it and still fail every actual contract - which is exactly what
    `openai.gpt-oss-120b-1:0` did (smoke pass, generator contract fail).
    """
    from intellichoice_adapters.bedrock.smoke_cli import SmokeAnswer

    schema = SmokeAnswer.model_json_schema()
    assert list(schema["properties"])[0] == "reasoning", "reasoning must precede the decision"
    assert schema["properties"]["answer"]["minimum"] == 0
    assert schema["properties"]["answer"]["maximum"] == 10
    assert SmokeAnswer.model_config.get("extra") == "forbid"


class _RecordingProvider:
    """Records the (system_prompt, user_message) of every call, and returns invalid JSON
    once then valid - so a repair happens and both calls can be inspected. Reports cache
    tokens so the gateway's accounting can be asserted (D-217).
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
    ) -> RawGeneration:
        self.calls.append((system_prompt, user_message))
        if len(self.calls) == 1:
            return RawGeneration(text="not json", input_tokens=10, output_tokens=10)
        return RawGeneration(
            text='{"hint_text": "h", "concept_reminder": "c", "next_step_prompt": "n", '
            '"answer_revealed": false, "difficulty": 1}',
            input_tokens=3,
            output_tokens=10,
            cache_read_tokens=4185,
            cache_write_tokens=0,
            stop_reason="tool_use",
        )


def test_repair_keeps_the_system_prompt_so_the_cache_point_survives() -> None:
    """D-217: the repair correction moved into the user turn, so the system block is
    byte-for-byte identical across the two calls and the D-203 system cache point still
    hits on the repair (it used to be appended to the system prompt, busting the cache).
    """

    async def run() -> None:
        provider = _RecordingProvider()
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
        assert len(provider.calls) == 2
        first_system, first_user = provider.calls[0]
        repair_system, repair_user = provider.calls[1]
        # The system block is unchanged - the cache-preserving property.
        assert repair_system == first_system == "system"
        # The correction rode the user turn instead.
        assert first_user in repair_user
        assert "did not match the required JSON schema" in repair_user
        # And the cache-read tokens from the (successful) call surface on the result.
        assert result.cache_read_tokens == 4185

    asyncio.run(run())
