"""Real `EmbeddingProvider` (SPEC §5.21.1), env-selected in place of
`MockBedrockProvider.raw_embed` (D-002's pattern) - not exercised in dev/tests since no
real AWS credentials exist yet (mirrors `AnthropicBedrockProvider`, D-025).

Amazon Titan Text Embeddings V2 isn't served by the Anthropic Messages API surface that
`AnthropicBedrockProvider` uses for chat/structured output - it's a separate Bedrock
model family, invoked via `bedrock-runtime`'s `invoke_model` with its own request/
response JSON shape. That's why `EmbeddingProvider` is its own Protocol (`raw_embed`
only) rather than folded into `BedrockProvider` - see D-035.
"""

import asyncio
import json
from typing import Any

from .provider import ProviderCallError, RawEmbedding


class TitanEmbeddingProvider:
    def __init__(self, *, aws_region: str) -> None:
        import boto3  # local import: keeps boto3 optional for callers that never embed

        self._client = boto3.client("bedrock-runtime", region_name=aws_region)

    async def raw_embed(self, *, model_id: str, texts: list[str]) -> RawEmbedding:
        vectors: list[list[float]] = []
        total_input_tokens = 0
        for text in texts:
            try:
                response = await asyncio.to_thread(
                    self._client.invoke_model,
                    modelId=model_id,
                    body=json.dumps({"inputText": text}),
                )
                body: dict[str, Any] = json.loads(response["body"].read())
            except Exception as exc:  # boto3 raises typed ClientError/BotoCoreError -
                # all transient here, same as AnthropicBedrockProvider's blanket catch.
                raise ProviderCallError(str(exc)) from exc

            vectors.append(body["embedding"])
            total_input_tokens += body.get("inputTextTokenCount", len(text) // 4)

        return RawEmbedding(vectors=vectors, input_tokens=total_input_tokens)
