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
from typing import Any

from .provider import ProviderCallError, RawGeneration

_TOOL_NAME = "emit_result"


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
    ) -> RawGeneration:
        try:
            response = await asyncio.to_thread(
                self._client.converse,
                modelId=model_id,
                system=[{"text": system_prompt}],
                messages=[{"role": "user", "content": [{"text": user_message}]}],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": _TOOL_NAME,
                                "description": "Emit the result matching the required schema.",
                                "inputSchema": {"json": json_schema},
                            }
                        }
                    ],
                    "toolChoice": {"tool": {"name": _TOOL_NAME}},
                },
                inferenceConfig={"maxTokens": max_output_tokens},
            )
        except Exception as exc:  # boto3 raises typed ClientError/BotoCoreError - all
            # transient here, same blanket catch as TitanEmbeddingProvider; the gateway's
            # bounded-retry loop is the single place that decides whether to retry.
            raise ProviderCallError(str(exc)) from exc

        content: list[dict[str, Any]] = response["output"]["message"]["content"]
        tool_use = next((block["toolUse"] for block in content if "toolUse" in block), None)
        if tool_use is None:
            raise ProviderCallError("model did not return a tool_use block")

        usage = response.get("usage", {})
        return RawGeneration(
            text=json.dumps(tool_use["input"]),
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            # `converse` still returns a `toolUse` block when it runs out of output
            # budget mid-emission; its `input` is simply a truncated fragment that
            # happens to be valid JSON of the wrong shape. Only `stopReason` tells the
            # two apart (D-115).
            truncated=response.get("stopReason") == "max_tokens",
        )
