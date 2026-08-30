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
from collections.abc import Callable
from typing import Any, TypeVar

from intellichoice_observability.tracing import traced_span
from intellichoice_shared.bedrock import (
    NOT_JSON_DIGEST,
    BedrockGenerationResult,
    BedrockTask,
    BedrockTimeoutError,
    CircuitOpenError,
    CostBudgetExceededError,
    EmbeddingResult,
    InputBudgetExceededError,
    OutputTruncatedError,
    StructuredOutputError,
    estimate_input_tokens,
    inline_schema_refs,
    schema_error_digest,
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
    # Added 2026-08-11 (D-273, C1 Phase 0), when this became the only invocable model
    # above Haiku in the account - see QUESTION_GENERATION.md §6 for the measurement.
    # The fallback below already produced these exact numbers, so nothing about accounting
    # changes; the key exists so a mid-tier generator is billed by an entry someone chose
    # rather than by a default that happened to be right.
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": (0.3, 1.5),
}
_DEFAULT_RATE_PER_1K_CENTS = (0.3, 1.5)

# Titan Text Embeddings V2 bills input tokens only - placeholder rate, not tied to a
# real invoice (same caveat as _MODEL_RATES_PER_1K_CENTS above).
_EMBEDDING_RATE_PER_1K_CENTS: dict[str, float] = {
    "amazon.titan-embed-text-v2:0": 0.002,
}
_DEFAULT_EMBEDDING_RATE_PER_1K_CENTS = 0.002

# A spend guard: no single call may bill for more output than this, whatever it asks for.
#
# **Deliberately left at 4000 (D-233), after raising it to 6000 and measuring that it bought
# nothing.** The §5.8.5 judge truncated here, so the obvious move was more headroom - but the
# same `place_value` items produced 1847, then 2263, then 4370, then over 5000 tokens as the
# ceiling rose. Its `reasoning` field has no length bound, so it expands to fill whatever it
# is given and a bigger cap is a moving target that costs more per call for the same failure.
# The fix belongs in the prompt, which now asks for brevity.
#
# **A request above this is logged.** It used to be silently reduced: a caller asking for 5000
# got 4000 with no signal anywhere, noticed only because the truncation error happened to
# print the capped number rather than the requested one. A guard that quietly rewrites its
# caller's argument makes every constant upstream of it a guess.
_HARD_MAX_OUTPUT_TOKENS = 4000

# The other half of the same guard: no single `generate_structured` call may *send* more
# than this, estimated pessimistically (`estimate_input_tokens`, chars/3) over everything
# that actually goes on the wire - system prompt, serialised payload, the inlined JSON
# schema, and the tool definitions when the caller passes them.
#
# **The bound this project did not have.** AUD-F-34 (D-141): `memory-consolidate` assembled
# a 215,355-token prompt out of 13,865 unbounded rows, failed *every* call on prompt length
# for its whole existence, and exited 0 each time. The fix bounded that one job's batches at
# its own layer, which left the shape intact for every future caller - output, spend, timeout
# and the circuit breaker were enforced here, and input was enforced nowhere. This is that
# missing seam, so a new paid caller inherits the bound instead of inheriting the incident.
#
# **32k, and each of the three constraints D-141 named is slack at that value.** The largest
# legitimate caller today is consolidation's own 20k-token batch, so 32k clears it with real
# headroom; it is an order of magnitude under the deployed model's 200k context; and at
# Haiku 4.5's 0.1 cents/1k it is ~3 cents of input, single-digit cents against a 50-cent
# session budget. Sizing it against the *context window* is the mistake D-141 §3 already
# paid for once - a 120k prompt fits the window and still cannot finish inside the 20 s
# call timeout.
#
# **A payload above this is refused, never truncated or chunked.** Truncating asks the model
# a different question and gets a fluent answer to it; chunking needs to know what the
# payload means, which only the caller does - `intellichoice_memory.consolidation` does it
# correctly at its layer and keeps doing so as defense in depth.
_HARD_MAX_INPUT_TOKENS = 32_000

# What `worst_case_cost_cents` assumes about input when the caller does not measure its own
# payload. **A reserve heuristic and nothing else.** It is not the admission number - the
# session-budget check inside `generate_structured` prices the payload it is actually about
# to send (`estimate_input_tokens`) - and it is not what anything is billed: `settle`
# replaces a reservation with the call's real accumulated usage the moment it finishes.
# Its only failure direction is *low*, which would let two callers reserve less than they
# spend; raising it costs nothing but per-day concurrency, which is why it can stay a round
# number nobody has had to defend.
_RESERVE_INPUT_TOKENS = 2000

# Amazon Titan Text Embeddings V2 accepts at most 8,192 input tokens in one `invoke_model`
# call, and `TitanEmbeddingProvider.raw_embed` sends one call *per text* - so the bound that
# matters on this path is per text, not per batch. Set slightly under the model's own maximum
# because the estimate is pessimistic in the same direction the ceiling is: refuse a
# borderline text here rather than pay three retries and a circuit-breaker trip to learn the
# same thing from Bedrock's own ValidationException, which is exactly AUD-F-34's shape.
#
# The batch total needs no second ceiling: the session-budget check below already prices the
# whole batch, and embeddings bill 0.002 cents/1k, so cost is not what breaks this path.
_HARD_MAX_EMBEDDING_INPUT_TOKENS_PER_TEXT = 8_000


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
        """Count a *provider-health* failure (timeout, network, throttle, 5xx).

        Deliberately not called for structured-output failures. The circuit breaker
        exists to stop hammering a Bedrock that cannot answer; a response that arrives
        promptly and fails our schema says the opposite - Bedrock is healthy and our
        request is wrong. Counting those together is what turned one rerank defect into
        a 30-second outage of every task, `scope_and_intent` included (D-115).
        """
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._circuit_failure_threshold:
            self._circuit_opened_until = time.monotonic() + self._circuit_cooldown_s

    def _record_success(self) -> None:
        self._consecutive_failures = 0
        self._circuit_opened_until = None

    def _log_failure(
        self,
        *,
        task: BedrockTask,
        model_id: str | None,
        reason: str,
        detail: str,
        attempts: int,
        started_at: float,
        max_output_tokens: int | None = None,
    ) -> None:
        """Every failure exit from this gateway logs exactly once, at WARNING.

        Before D-115 only successes were logged, so a call that failed on every single
        request left no trace at all: staging's reranker was dead for a week and the
        only visible symptom was a latency gap between two unrelated log lines. A
        degraded path that keeps returning 200s has to say so itself, because nothing
        downstream will.
        """
        logger.warning(
            "bedrock_call_failed",
            extra={
                "task": task.value,
                "model_id": model_id,
                "reason": reason,
                "detail": detail,
                "attempts": attempts,
                "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
                "max_output_tokens": max_output_tokens,
                "consecutive_failures": self._consecutive_failures,
            },
        )

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

    @staticmethod
    def _estimated_input_tokens(
        *,
        system_prompt: str,
        user_message: str,
        json_schema: dict | None = None,
        tools: list[dict] | None = None,
    ) -> int:
        """What this call is about to send, in tokens, counted the same way twice.

        The single place the input estimate is produced, so the hard ceiling and the
        session-budget check below cannot disagree about how big a call is - the property
        `worst_case_cost_cents` used to hold by sharing a literal, now held by sharing a
        computation over the real strings.

        The schema and tool blocks are counted because they are *sent*: `raw_generate` puts
        the inlined JSON schema in the tool definition on every call, and a caller passing
        `tools` adds more. Leaving them out would under-count exactly the payloads that are
        most likely to need refusing.
        """
        return estimate_input_tokens(
            system_prompt,
            user_message,
            json.dumps(json_schema, separators=(",", ":")) if json_schema is not None else None,
            json.dumps(tools, separators=(",", ":")) if tools else None,
        )

    def worst_case_cost_cents(
        self,
        task: BedrockTask,
        max_output_tokens: int,
        estimated_input_tokens: int | None = None,
    ) -> float:
        """The most one `generate_structured` call for this task can cost.

        Public so a caller can *reserve* this amount against a per-day ceiling before
        making the call (AUD-X-08's reserve-then-settle).

        **`estimated_input_tokens=None` is a reserve heuristic, not the admission number.**
        It falls back to `_RESERVE_INPUT_TOKENS`, and until this method grew the parameter
        that constant *was* also what the in-gateway session-budget check priced with - the
        docstring here said so. It no longer is: that check now estimates the payload it is
        actually about to send, so the two numbers are deliberately allowed to differ. That
        costs nothing, because a reservation is replaced by the call's real usage at `settle`
        and over-reserving only ever costs per-day concurrency. A caller that already knows
        its payload size can pass it and reserve honestly.
        """
        model_id = self._model_registry.get(task)
        if model_id is None:
            raise ValueError(f"no Bedrock model configured for task {task!r}")
        input_tokens = (
            _RESERVE_INPUT_TOKENS if estimated_input_tokens is None else estimated_input_tokens
        )
        return self._cost_cents(
            model_id, input_tokens, min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS)
        )

    async def generate_structured(
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
        tools: list[dict] | None = None,
        tool_executor: Callable[[str, dict], dict] | None = None,
        # D-233: per-call, because one global timeout cannot serve both ends of this
        # pipeline. The serving-path calls are a few hundred tokens and 20s is a real
        # guard for them; the §5.8.5 judge writes ~2000-4400 tokens and was measured at
        # 15.0s, 18.8s, 25.9s and 34.3s - so it sat *on* the 20s line and failed
        # intermittently, ~28% of a topic's items, with an empty error string because
        # `str(asyncio.TimeoutError())` is "". Raising the global value instead would have
        # weakened the guard on every fast call to accommodate the slowest one, which is
        # the same mistake as the shared token ceiling D-231 had to split.
        timeout_s: float | None = None,
    ) -> BedrockGenerationResult[T]:
        with traced_span("bedrock.generate_structured", task=task.value):
            started_at = time.monotonic()
            model_id = self._model_registry.get(task)
            try:
                self._circuit_check()
            except CircuitOpenError as exc:
                self._log_failure(
                    task=task,
                    model_id=model_id,
                    reason="circuit_open",
                    detail=str(exc),
                    attempts=0,
                    started_at=started_at,
                )
                raise

            if model_id is None:
                raise ValueError(f"no Bedrock model configured for task {task!r}")

            capped_max_tokens = min(max_output_tokens, _HARD_MAX_OUTPUT_TOKENS)
            if capped_max_tokens < max_output_tokens:
                logger.warning(
                    "bedrock_max_tokens_capped task=%s requested=%d capped_to=%d",
                    task.value,
                    max_output_tokens,
                    capped_max_tokens,
                )
            user_message = payload.model_dump_json()
            # D-243: `$ref`/`$defs` indirection is inlined before the schema is shown to
            # the model. Measured on Haiku 4.5, the one response model with a nested model
            # inside it returned only the `$ref`'d field and nothing else, 12 times out of
            # 12 - which is the whole of D-240's 41% generator failure rate. Same schema,
            # different representation; flat models are returned untouched.
            json_schema = inline_schema_refs(response_model.model_json_schema())
            json_schema.setdefault("title", response_model.__name__)

            # Assembled above the two checks below, not just above the provider call: both
            # of them price this exact text, so it has to exist before either runs. Nothing
            # here is paid or even I/O - it is `model_dump_json` and a schema walk.
            estimated_input = self._estimated_input_tokens(
                system_prompt=system_prompt,
                user_message=user_message,
                json_schema=json_schema,
                tools=tools,
            )
            if estimated_input > _HARD_MAX_INPUT_TOKENS:
                self._log_failure(
                    task=task,
                    model_id=model_id,
                    reason="input_too_large",
                    detail=(
                        f"estimated {estimated_input} input tokens against a ceiling of "
                        f"{_HARD_MAX_INPUT_TOKENS}"
                    ),
                    attempts=0,
                    started_at=started_at,
                    max_output_tokens=capped_max_tokens,
                )
                raise InputBudgetExceededError(
                    f"input ceiling of {_HARD_MAX_INPUT_TOKENS} tokens would be exceeded "
                    f"(this call estimates {estimated_input}); batch the payload rather "
                    f"than sending it"
                )

            worst_case_cost = self._cost_cents(model_id, estimated_input, capped_max_tokens)
            if session_spend_cents + worst_case_cost > self._session_budget_cents:
                self._log_failure(
                    task=task,
                    model_id=model_id,
                    reason="budget_exceeded",
                    detail=(
                        f"spent {session_spend_cents:.2f} of "
                        f"{self._session_budget_cents} cents; this call could cost "
                        f"{worst_case_cost:.2f}"
                    ),
                    attempts=0,
                    started_at=started_at,
                    max_output_tokens=capped_max_tokens,
                )
                raise CostBudgetExceededError(
                    f"session budget of {self._session_budget_cents} cents would be "
                    f"exceeded (already spent {session_spend_cents:.2f}, this call could "
                    f"cost up to {worst_case_cost:.2f})"
                )

            tool_kwargs: dict[str, Any] = (
                {"tools": tools, "tool_executor": tool_executor} if tools else {}
            )
            raw_text: str | None = None
            truncated = False
            stop_reason = ""
            total_input = 0
            total_output = 0
            # D-217: prompt-cache tokens, accumulated so a warm-cache hit is visible in the
            # log (D-203 measured the saving but the gateway dropped these).
            total_cache_read = 0
            total_cache_write = 0
            attempts = 0
            for attempt in range(self._max_retries + 1):
                attempts = attempt + 1
                try:
                    raw = await asyncio.wait_for(
                        self._provider.raw_generate(
                            model_id=model_id,
                            system_prompt=system_prompt,
                            user_message=user_message,
                            json_schema=json_schema,
                            max_output_tokens=capped_max_tokens,
                            # Only forwarded when the caller asked for tools, so the
                            # `BedrockProvider` Protocol - and every fake implementing it -
                            # stays exactly as narrow as it was (D-202).
                            **tool_kwargs,
                        ),
                        timeout=timeout_s or self._call_timeout_s,
                    )
                except (TimeoutError, ProviderCallError) as exc:
                    self._record_failure()
                    if attempt < self._max_retries:
                        await asyncio.sleep(self._backoff_base_s * (2**attempt))
                        continue
                    self._log_failure(
                        task=task,
                        model_id=model_id,
                        reason="provider_unavailable",
                        detail=f"{type(exc).__name__}: {exc}",
                        attempts=attempts,
                        started_at=started_at,
                        max_output_tokens=capped_max_tokens,
                    )
                    raise BedrockTimeoutError(f"Bedrock call failed: {exc}") from exc
                else:
                    raw_text = raw.text
                    truncated = raw.truncated
                    stop_reason = raw.stop_reason
                    total_input += raw.input_tokens
                    total_output += raw.output_tokens
                    total_cache_read += raw.cache_read_tokens
                    total_cache_write += raw.cache_write_tokens
                    break

            assert raw_text is not None

            try:
                (
                    value,
                    repaired,
                    repair_input,
                    repair_output,
                    repair_cache_read,
                    repair_cache_write,
                ) = await self._validate_or_repair(
                    raw_text=raw_text,
                    response_model=response_model,
                    model_id=model_id,
                    system_prompt=system_prompt,
                    user_message=user_message,
                    json_schema=json_schema,
                    max_output_tokens=capped_max_tokens,
                    tokens_so_far=(total_input, total_output),
                    truncated=truncated,
                )
            except StructuredOutputError as exc:
                self._log_failure(
                    task=task,
                    model_id=model_id,
                    reason="output_truncated" if truncated else "schema_invalid",
                    detail=f"{exc} (response_model={response_model.__name__})",
                    attempts=attempts,
                    started_at=started_at,
                    max_output_tokens=capped_max_tokens,
                )
                raise
            total_input += repair_input
            total_output += repair_output
            total_cache_read += repair_cache_read
            total_cache_write += repair_cache_write
            self._record_success()

            cost_cents = self._cost_cents(model_id, total_input, total_output)
            logger.info(
                "bedrock_call",
                extra={
                    "task": task.value,
                    "model_id": model_id,
                    "input_tokens": total_input,
                    "output_tokens": total_output,
                    # D-217: a warm-cache hit shows as a large `cache_read_tokens` beside a
                    # small `input_tokens` (D-203 measured 4185 read / 3 billed on Haiku).
                    "cache_read_tokens": total_cache_read,
                    "cache_write_tokens": total_cache_write,
                    "cost_cents": cost_cents,
                    "repaired": repaired,
                    "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
                },
            )
            return BedrockGenerationResult(
                value=value,
                input_tokens=total_input,
                output_tokens=total_output,
                cost_cents=cost_cents,
                model_id=model_id,
                repaired=repaired,
                stop_reason=stop_reason,
                cache_read_tokens=total_cache_read,
                cache_write_tokens=total_cache_write,
            )

    async def create_embedding(
        self,
        *,
        texts: list[str],
        session_spend_cents: float,
    ) -> EmbeddingResult:
        with traced_span("bedrock.create_embedding", num_texts=len(texts)):
            started_at = time.monotonic()
            if self._embedding_provider is None:
                raise ValueError(
                    "this gateway was constructed without an embedding_provider - "
                    "create_embedding is unavailable"
                )
            model_id = self._model_registry.get(BedrockTask.EMBEDDING)
            try:
                self._circuit_check()
            except CircuitOpenError as exc:
                self._log_failure(
                    task=BedrockTask.EMBEDDING,
                    model_id=model_id,
                    reason="circuit_open",
                    detail=str(exc),
                    attempts=0,
                    started_at=started_at,
                )
                raise

            if model_id is None:
                raise ValueError(f"no Bedrock model configured for task {BedrockTask.EMBEDDING!r}")

            # Same estimator as the generate path, so the refusal below and the price
            # immediately after it are the same measurement (`len(text) // 4` before this,
            # which under-counted in the one direction a spend guard must not).
            per_text_tokens = [estimate_input_tokens(text) for text in texts]
            oversized = [
                (index, tokens)
                for index, tokens in enumerate(per_text_tokens)
                if tokens > _HARD_MAX_EMBEDDING_INPUT_TOKENS_PER_TEXT
            ]
            if oversized:
                index, tokens = oversized[0]
                self._log_failure(
                    task=BedrockTask.EMBEDDING,
                    model_id=model_id,
                    reason="input_too_large",
                    # An index and two counts, never the text: a chunk of an org document is
                    # exactly the kind of content this project keeps out of logs (SPEC §5.30).
                    detail=(
                        f"{len(oversized)} of {len(texts)} texts exceed the per-text ceiling "
                        f"of {_HARD_MAX_EMBEDDING_INPUT_TOKENS_PER_TEXT} tokens; first at "
                        f"index {index}, estimated {tokens}"
                    ),
                    attempts=0,
                    started_at=started_at,
                )
                raise InputBudgetExceededError(
                    f"embedding input ceiling of "
                    f"{_HARD_MAX_EMBEDDING_INPUT_TOKENS_PER_TEXT} tokens per text would be "
                    f"exceeded by {len(oversized)} of {len(texts)} texts (first at index "
                    f"{index}, estimated {tokens}); chunk them smaller rather than sending"
                )

            estimated_tokens = sum(per_text_tokens)
            worst_case_cost = self._embedding_cost_cents(model_id, estimated_tokens)
            if session_spend_cents + worst_case_cost > self._session_budget_cents:
                self._log_failure(
                    task=BedrockTask.EMBEDDING,
                    model_id=model_id,
                    reason="budget_exceeded",
                    detail=(
                        f"spent {session_spend_cents:.2f} of "
                        f"{self._session_budget_cents} cents; this call could cost "
                        f"{worst_case_cost:.2f}"
                    ),
                    attempts=0,
                    started_at=started_at,
                )
                raise CostBudgetExceededError(
                    f"session budget of {self._session_budget_cents} cents would be "
                    f"exceeded (already spent {session_spend_cents:.2f}, this call could "
                    f"cost up to {worst_case_cost:.2f})"
                )

            raw = None
            attempts = 0
            for attempt in range(self._max_retries + 1):
                attempts = attempt + 1
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
                    self._log_failure(
                        task=BedrockTask.EMBEDDING,
                        model_id=model_id,
                        reason="provider_unavailable",
                        detail=f"{type(exc).__name__}: {exc}",
                        attempts=attempts,
                        started_at=started_at,
                    )
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
                    "duration_ms": round((time.monotonic() - started_at) * 1000, 2),
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
        truncated: bool = False,
    ) -> tuple[T, bool, int, int, int, int]:
        already_in, already_out = tokens_so_far
        # **Checked BEFORE validation, and that ordering is the whole fix (D-460/R1).**
        #
        # It used to run after, so a truncated response only failed when its fragment also
        # failed Pydantic. That holds for a fragment cut mid-string, but Converse does not
        # return a fragment: on `max_tokens` it returns the *partial `toolUse` input*, and a
        # model cut off before its first key gives `{}`. `{}` is valid JSON and valid against
        # any response model whose fields all default - `MemoryUpdateResponse` is exactly
        # that shape - so `_try_validate` succeeded and the gateway handed back a
        # legitimate-looking empty result while this guard sat unreached.
        #
        # Measured cost of that ordering (E4, D-460): 29 of 30 real consolidation calls
        # stopped on `max_tokens`, 10 of 10 students had one, and the run reported
        # `added=0, calls_failed=0, exit 0` - AUD-F-34's silent-zero shape again, one layer
        # up. The signal that a response is unusable is the *stop reason*, never whether the
        # fragment happened to survive validation, so the stop reason is what decides.
        #
        # A repair call here is still pure waste: same prompt, same ceiling, same truncation,
        # at full input cost and ~10 s of latency. Raise on the spot and let the caller's
        # fallback run - the honest fix is a bigger ceiling or a smaller response shape, not
        # another attempt (D-115). And still no `_record_failure()`: the call reached Bedrock
        # and came back, so this stays a schema-class failure that cannot open the circuit on
        # every other task (D-115's blast-radius half, unchanged).
        if truncated:
            raise OutputTruncatedError(
                f"model hit max_output_tokens={max_output_tokens} before completing the "
                f"{response_model.__name__} response; not retrying under the same ceiling",
                cost_cents=self._cost_cents(model_id, already_in, already_out),
            )

        value, _ = self._try_validate(raw_text, response_model)
        if value is not None:
            return value, False, 0, 0, 0, 0

        # D-217: the correction goes in the *user* turn, leaving `system_prompt` byte-for-
        # byte identical to the first call - so the system cache point (D-203) still hits on
        # the repair. It used to be appended to the system prompt, which changed that block
        # and made every repair re-write the cache instead of reading it.
        repair_user_message = (
            f"{user_message}\n\nYour previous output did not match the required JSON "
            "schema. Return corrected JSON only, matching the schema exactly."
        )
        try:
            repaired_raw = await asyncio.wait_for(
                self._provider.raw_generate(
                    model_id=model_id,
                    system_prompt=system_prompt,
                    user_message=repair_user_message,
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

        value, schema_errors = self._try_validate(repaired_raw.text, response_model)
        if value is None:
            # No `_record_failure()`: both calls reached Bedrock and came back. The
            # schema mismatch is ours to fix, and counting it as provider ill-health
            # opens the circuit on every other task too (D-115).
            #
            # The digest is the *repair's* failure, not the first call's, on purpose: the
            # repair prompt has already told the model its output was off-schema, so what
            # it got wrong the second time is the defect that survived being told (D-243).
            raise StructuredOutputError(
                "structured output still invalid after one repair retry",
                cost_cents=self._cost_cents(
                    model_id,
                    already_in + repaired_raw.input_tokens,
                    already_out + repaired_raw.output_tokens,
                ),
                schema_errors=schema_errors,
            )
        return (
            value,
            True,
            repaired_raw.input_tokens,
            repaired_raw.output_tokens,
            repaired_raw.cache_read_tokens,
            repaired_raw.cache_write_tokens,
        )

    @staticmethod
    def _try_validate(raw_text: str, response_model: type[T]) -> tuple[T | None, list[str]]:
        """Returns the value, or `None` plus a digest of what stopped it (D-243).

        The two failure arms stay distinguishable all the way to the caller. Prose back
        from the model means the tool was never called - a model or parser problem, which
        `smoke_cli` already classifies as `PARSER INCOMPATIBILITY`. Valid JSON of the wrong
        shape means the contract is being read and missed. They are fixed by opposite
        actions and used to arrive as the same sentence.
        """
        try:
            data = json.loads(raw_text)
        except ValueError:
            return None, [NOT_JSON_DIGEST]
        try:
            return response_model.model_validate(data), []
        except ValidationError as exc:
            return None, schema_error_digest(exc)
