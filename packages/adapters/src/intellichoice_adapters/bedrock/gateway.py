"""`ResilientBedrockGateway` - the SPEC §5.25.1 `BedrockGateway` implementation: timeout,
bounded retry+backoff, max-token ceiling, per-session cost budget, circuit breaker, and
JSON-Schema structured-output validation with one repair retry (§5.25.3). Wraps a
low-level `BedrockProvider` (`MockBedrockProvider` or `AnthropicBedrockProvider`) for
`generate_structured`, and a separate `EmbeddingProvider` for `create_embedding` - same
construction pattern as `AsyncPostgresSaver`/`MySQLProfileAdapter` (D-007): built once in
`main.py`'s lifespan, not per-request, so the circuit breaker's in-memory state is shared
across the app's whole lifetime rather than reset every call.
"""

import asyncio
import json
import logging
import time
from typing import TypeVar

from intellichoice_observability.tracing import traced_span
from intellichoice_shared.bedrock import (
    BedrockGenerationResult,
    BedrockTask,
    BedrockTimeoutError,
    CircuitOpenError,
    CostBudgetExceededError,
    EmbeddingResult,
    StructuredOutputError,
)
from pydantic import BaseModel, ValidationError

from .provider import BedrockProvider, EmbeddingProvider, ProviderCallError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Cents per 1K tokens (input, output) - placeholder rates for cost accounting, not tied
# to a real invoice; revisit once real Bedrock billing exists. Unknown model ids (e.g. in
# tests) fall back to _DEFAULT_RATE_PER_1K_CENTS.
_MODEL_RATES_PER_1K_CENTS: dict[str, tuple[float, float]] = {
    "anthropic.claude-sonnet-5": (0.3, 1.5),
    "anthropic.claude-haiku-4-5": (0.1, 0.5),
    # Real invocable id (cross-region inference profile, see D-084) - the app's actual
    # deployed model id, distinct from the bare "anthropic.claude-haiku-4-5" key above.
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": (0.1, 0.5),
}
_DEFAULT_RATE_PER_1K_CENTS = (0.3, 1.5)

# Titan Text Embeddings V2 bills input tokens only - placeholder rate, not tied to a
# real invoice (same caveat as _MODEL_RATES_PER_1K_CENTS above).
_EMBEDDING_RATE_PER_1K_CENTS: dict[str, float] = {
    "amazon.titan-embed-text-v2:0": 0.002,
}
_DEFAULT_EMBEDDING_RATE_PER_1K_CENTS = 0.002

_HARD_MAX_OUTPUT_TOKENS = 4000


class ResilientBedrockGateway:
    def __init__(
        self,
        *,
        provider: BedrockProvider,
        model_registry: dict[BedrockTask, str],
        embedding_provider: EmbeddingProvider | None = None,
        call_timeout_s: float = 20.0,
        max_retries: int = 2,
        backoff_base_s: float = 0.5,
        circuit_failure_threshold: int = 5,
        circuit_cooldown_s: float = 30.0,
        session_budget_cents: float = 50.0,
    ) -> None:
        self._provider = provider
        # None for callers that never embed (e.g. `learning_api`'s tutor-only gateway) -
        # `create_embedding` raises a clear error rather than every construction site
        # needing to pass a provider it will never use.
        self._embedding_provider = embedding_provider
        self._model_registry = model_registry
        self._call_timeout_s = call_timeout_s
        self._max_retries = max_retries
        self._backoff_base_s = backoff_base_s
        self._circuit_failure_threshold = circuit_failure_threshold
        self._circuit_cooldown_s = circuit_cooldown_s
        self._session_budget_cents = session_budget_cents
        self._consecutive_failures = 0
        self._circuit_opened_until: float | None = None

    def _circuit_check(self) -> None:
        if self._circuit_opened_until is None:
            return
        if time.monotonic() < self._circuit_opened_until:
            raise CircuitOpenError("Bedrock circuit breaker is open")
        # Cooldown elapsed - allow a half-open attempt; only a success clears the
        # failure counter, so an immediate re-failure re-opens the circuit.
        self._circuit_opened_until = None

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_failure_threshold:
            self._circuit_opened_until = time.monotonic() + self._circuit_cooldown_s

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_opened_until = None

    @staticmethod
    def _rate_for(model_id: str) -> tuple[float, float]:
        return _MODEL_RATES_PER_1K_CENTS.get(model_id, _DEFAULT_RATE_PER_1K_CENTS)

    def _cost_cents(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        input_rate, output_rate = self._rate_for(model_id)
        return (input_tokens / 1000) * input_rate + (output_tokens / 1000) * output_rate

    @staticmethod
    def _embedding_cost_cents(model_id: str, input_tokens: int) -> float:
        rate = _EMBEDDING_RATE_PER_1K_CENTS.get(model_id, _DEFAULT_EMBEDDING_RATE_PER_1K_CENTS)
        return (input_tokens / 1000) * rate

    async def generate_structured(
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        with traced_span("bedrock.generate_structured", task=task.value):
            self._circuit_check()

            model_id = self._model_registry.get(task)
            if model_id is None:
                raise ValueError(f"no Bedrock model configured for task {task!r}")

            capped_max_tokens = min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS)
            worst_case_cost = self._cost_cents(model_id, 2000, capped_max_tokens)
            if session_spend_cents + worst_case_cost > self._session_budget_cents:
                raise CostBudgetExceededError(
                    f"session budget of {self._session_budget_cents} cents would be "
                    f"exceeded (already spent {session_spend_cents:.2f}, this call could "
                    f"cost up to {worst_case_cost:.2f})"
                )

            user_message = payload.model_dump_json()
            json_schema = response_model.model_json_schema()
            json_schema.setdefault("title", response_model.__name__)

            raw_text: str | None = None
            total_input = 0
            total_output = 0
            for attempt in range(self._max_retries + 1):
                try:
                    raw = await asyncio.wait_for(
                        self._provider.raw_generate(
                            model_id=model_id,
                            system_prompt=system_prompt,
                            user_message=user_message,
                            json_schema=json_schema,
                            max_output_tokens=capped_max_tokens,
                        ),
                        timeout=self._call_timeout_s,
                    )
                except (TimeoutError, ProviderCallError) as exc:
                    self._record_failure()
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff_base_s * (2**attempt))
                        continue
                    raise BedrockTimeoutError(f"Bedrock call failed: {exc}") from exc
                else:
                    raw_text = raw.text
                    total_input += raw.input_tokens
                    total_output += raw.output_tokens
                    break

            assert raw_text is not None

            value, repaired, repair_input, repair_output = await self._validate_or_repair(
                raw_text=raw_text,
                response_model=response_model,
                model_id=model_id,
                system_prompt=system_prompt,
                user_message=user_message,
                json_schema=json_schema,
                max_output_tokens=capped_max_tokens,
                tokens_so_far=(total_input, total_output),
            )
            total_input += repair_input
            total_output += repair_output
            self._record_success()

            cost_cents = self._cost_cents(model_id, total_input, total_output)
            logger.info(
                "bedrock_call",
                extra={
                    "task": task.value,
                    "model_id": model_id,
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    "cost_cents": cost_cents,
                    "repaired": repaired,
                },
            )
            return BedrockGenerationResult(
                value=value,
                input_tokens=total_input,
                output_tokens=total_output,
                cost_cents=cost_cents,
                model_id=model_id,
                repaired=repaired,
            )

    async def create_embedding(
        self,
        *,
        texts: list[str],
        session_spend_cents: float,
    ) -> EmbeddingResult:
        with traced_span("bedrock.create_embedding", num_texts=len(texts)):
            if self._embedding_provider is None:
                raise ValueError(
                    "this gateway was constructed without an embedding_provider - "
                    "create_embedding is unavailable"
                )
            self._circuit_check()

            model_id = self._model_registry.get(BedrockTask.EMBEDDING)
            if model_id is None:
                raise ValueError(
                    f"no Bedrock model configured for task {BedrockTask.EMBEDDING!r}"
                )

            estimated_tokens = sum(len(text) // 4 for text in texts)
            worst_case_cost = self._embedding_cost_cents(model_id, estimated_tokens)
            if session_spend_cents + worst_case_cost > self._session_budget_cents:
                raise CostBudgetExceededError(
                    f"session budget of {self._session_budget_cents} cents would be "
                    f"exceeded (already spent {session_spend_cents:.2f}, this call could "
                    f"cost up to {worst_case_cost:.2f})"
                )

            raw = None
            for attempt in range(self._max_retries + 1):
                try:
                    raw = await asyncio.wait_for(
                        self._embedding_provider.raw_embed(model_id=model_id, texts=texts),
                        timeout=self._call_timeout_s,
                    )
                except (TimeoutError, ProviderCallError) as exc:
                    self._record_failure()
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff_base_s * (2**attempt))
                        continue
                    raise BedrockTimeoutError(f"Bedrock embedding call failed: {exc}") from exc
                else:
                    break

            assert raw is not None
            self._record_success()

            cost_cents = self._embedding_cost_cents(model_id, raw.input_tokens)
            logger.info(
                "bedrock_embedding_call",
                extra={
                    "task": BedrockTask.EMBEDDING.value,
                    "model_id": model_id,
                    "input_tokens": raw.input_tokens,
                    "cost_cents": cost_cents,
                    "num_texts": len(texts),
                },
            )
            return EmbeddingResult(
                vectors=raw.vectors,
                model_id=model_id,
                dimensions=len(raw.vectors[0]) if raw.vectors else 0,
                cost_cents=cost_cents,
            )

    async def _validate_or_repair(
        self,
        *,
        raw_text: str,
        response_model: type[T],
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
        tokens_so_far: tuple[int, int],
    ) -> tuple[T, bool, int, int]:
        value = self._try_validate(raw_text, response_model)
        if value is not None:
            return value, False, 0, 0

        repair_prompt = (
            f"{system_prompt}\n\nYour previous output did not match the required JSON "
            "schema. Return corrected JSON only, matching the schema exactly."
        )
        already_in, already_out = tokens_so_far
        try:
            repaired_raw = await asyncio.wait_for(
                self._provider.raw_generate(
                    model_id=model_id,
                    system_prompt=repair_prompt,
                    user_message=user_message,
                    json_schema=json_schema,
                    max_output_tokens=max_output_tokens,
                ),
                timeout=self._call_timeout_s,
            )
        except (TimeoutError, ProviderCallError) as exc:
            self._record_failure()
            raise StructuredOutputError(
                f"structured output invalid and repair call failed: {exc}",
                cost_cents=self._cost_cents(model_id, already_in, already_out),
            ) from exc

        value = self._try_validate(repaired_raw.text, response_model)
        if value is None:
            self._record_failure()
            raise StructuredOutputError(
                "structured output still invalid after one repair retry",
                cost_cents=self._cost_cents(
                    model_id,
                    already_in + repaired_raw.input_tokens,
                    already_out + repaired_raw.output_tokens,
                ),
            )
        return value, True, repaired_raw.input_tokens, repaired_raw.output_tokens

    @staticmethod
    def _try_validate(raw_text: str, response_model: type[T]) -> T | None:
        try:
            data = json.loads(raw_text)
        except ValueError:
            return None
        try:
            return response_model.model_validate(data)
        except ValidationError:
            return None
