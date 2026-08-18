"""Real `BedrockProvider` (SPEC §5.25.1), env-selected in place of `MockBedrockProvider`
(D-002's pattern).

Uses plain `boto3` `bedrock-runtime` `converse` calls with a forced single tool call for
structured output - same client/call style `TitanEmbeddingProvider` already uses for
embeddings, no extra SDK. Model ids need a real invocable id for this surface - Claude
Haiku 4.5 requires its cross-region inference profile id (e.g.
`us.anthropic.claude-haiku-4-5-20251001-v1:0`), not a bare foundation-model id.

This previously called Bedrock Mantle (a separate PrivateLink surface) via the
`anthropic` SDK's `AnthropicBedrockMantle` client. That was abandoned during S32/D-084's
model-access investigation: every flagship model tried on Mantle (Claude Sonnet 5, GPT-5.6
Sol/Terra/Luna) hit an account-wide "not available for this account, contact AWS Sales"
gate, unaffected by IAM permissions or quota - Claude Haiku 4.5 via this classic
`bedrock-runtime` surface is what's actually callable on this account today.
"""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from .provider import ProviderCallError, RawGeneration

_TOOL_NAME = "emit_result"

# Families measured to accept Converse `cachePoint` blocks on this account (D-203). Others
# are left alone rather than probed: an unsupported block is a `ValidationException`, and a
# failed paid call to learn something a prefix check already tells us is a bad trade.
_PROMPT_CACHE_MODEL_MARKERS = ("anthropic.",)


def _supports_prompt_caching(model_id: str) -> bool:
    return any(marker in model_id for marker in _PROMPT_CACHE_MODEL_MARKERS)


class AnthropicBedrockProvider:
    def __init__(self, *, aws_region: str) -> None:
        import boto3  # local import: keeps boto3 optional for callers that never chat

        self._client = boto3.client("bedrock-runtime", region_name=aws_region)

    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
        tools: list[dict] | None = None,
        tool_executor: Callable[[str, dict], dict] | None = None,
        max_tool_rounds: int = 4,
    ) -> RawGeneration:
        """One structured-output call, optionally letting the model use tools first (D-202).

        Without `tools` this is a single forced `emit_result` call, exactly as before.

        With them it becomes a short Converse loop: the model may call a tool, we execute
        it here and hand the result back, and it continues - until it emits the structured
        result or `max_tool_rounds` is reached, at which point `emit_result` is forced so a
        model that never stops calling tools still produces something the caller can
        validate rather than hanging.

        Token usage is summed across every round, so cost accounting stays honest about
        what a tool-using call actually spent.
        """
        emit_spec = {
            "toolSpec": {
                "name": _TOOL_NAME,
                "description": "Emit the final result matching the required schema.",
                "inputSchema": {"json": json_schema},
            }
        }
        all_tools = [*(tools or []), emit_spec]
        # Two cache points, at the two prefixes that actually repeat (D-203):
        #
        #   after `system` - identical for every candidate in a run, so an 11-slot batch
        #     writes it once and reads it ten times;
        #   after the first user message - identical for every round of one candidate's
        #     tool loop, which is where the loop's cost lives, since Converse resends the
        #     whole conversation each round.
        #
        # Measured on Haiku 4.5: 4188 billed input tokens became 3 billed + 4185 cache-read,
        # and a cache read is roughly a tenth of the normal input rate.
        cacheable = _supports_prompt_caching(model_id)
        system_blocks: list[dict[str, Any]] = [{"text": system_prompt}]
        first_user: list[dict[str, Any]] = [{"text": user_message}]
        if cacheable:
            system_blocks.append({"cachePoint": {"type": "default"}})
            first_user.append({"cachePoint": {"type": "default"}})
        messages: list[dict[str, Any]] = [{"role": "user", "content": first_user}]
        total_input = 0
        total_output = 0
        cache_read = 0
        cache_write = 0
        stop_reason = ""

        for round_index in range(max_tool_rounds + 1):
            # The last round forces the emit tool; earlier ones let the model choose, which
            # is what makes calling a tool possible at all - a forced single tool cannot.
            last = round_index == max_tool_rounds or not tools
            choice: dict[str, Any] = {"tool": {"name": _TOOL_NAME}} if last else {"auto": {}}
            try:
                response = await asyncio.to_thread(
                    self._client.converse,
                    modelId=model_id,
                    system=system_blocks,
                    messages=messages,
                    toolConfig={"tools": all_tools, "toolChoice": choice},
                    inferenceConfig={"maxTokens": max_output_tokens},
                )
            except Exception as exc:  # boto3 raises typed ClientError/BotoCoreError - all
                # transient here, same blanket catch as TitanEmbeddingProvider; the
                # gateway's bounded-retry loop is the single place that decides to retry.
                raise ProviderCallError(str(exc)) from exc

            usage = response.get("usage", {})
            total_input += usage.get("inputTokens", 0)
            total_output += usage.get("outputTokens", 0)
            cache_read += usage.get("cacheReadInputTokens", 0) or 0
            cache_write += usage.get("cacheWriteInputTokens", 0) or 0
            stop_reason = response.get("stopReason", "")
            message = response["output"]["message"]
            content: list[dict[str, Any]] = message["content"]
            uses = [b["toolUse"] for b in content if "toolUse" in b]

            emitted = next((u for u in uses if u["name"] == _TOOL_NAME), None)
            if emitted is not None:
                return RawGeneration(
                    text=json.dumps(emitted["input"]),
                    input_tokens=total_input,
                    output_tokens=total_output,
                    truncated=stop_reason == "max_tokens",
                    stop_reason=stop_reason,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                )

            helper_calls = [u for u in uses if u["name"] != _TOOL_NAME]
            if not helper_calls or tool_executor is None:
                # The model answered in prose, or asked for a tool we cannot run. Round-trip
                # again with emit forced rather than failing here.
                continue

            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "toolResult": {
                                "toolUseId": call["toolUseId"],
                                "content": [{"json": tool_executor(call["name"], call["input"])}],
                            }
                        }
                        for call in helper_calls
                    ],
                }
            )

        raise ProviderCallError("model did not return a tool_use block")
