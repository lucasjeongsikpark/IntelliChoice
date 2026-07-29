"""Low-level Bedrock call, one layer below `BedrockGateway` (SPEC §5.25.1).

A provider makes exactly one raw model call and returns raw output plus token counts -
no retry, no validation, no cost accounting. `gateway.ResilientBedrockGateway` is the
only thing that talks to a provider; it adds every resilience concern on top. This
split is what lets `MockBedrockProvider` stand in for `AnthropicBedrockProvider`/
`TitanEmbeddingProvider` without duplicating any of that logic (mirrors D-002's
adapter-with-dev-fake pattern used for `EmailTransport`/`ProfileAdapter`).

`BedrockProvider` (chat/structured-output) and `EmbeddingProvider` are two separate
Protocols, not one merged interface - Amazon Titan Text Embeddings V2 isn't served by
the same Bedrock model family or request shape as Claude chat, so `AnthropicBedrock
Provider` only ever implements the former and `TitanEmbeddingProvider` only the latter
(D-035). `MockBedrockProvider` implements both, since it's the shared dev default for
every gateway call.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawGeneration:
    text: str
    input_tokens: int
    output_tokens: int
    # True when the model stopped because it hit `max_output_tokens` rather than because
    # it finished. The text is then a fragment, and the gateway must not spend a repair
    # call on it - an identical retry under the same ceiling truncates identically
    # (D-115: exactly this cost ~21 s and ~3.2 cents on every staging chat turn).
    truncated: bool = False


@dataclass(frozen=True)
class RawEmbedding:
    vectors: list[list[float]]
    input_tokens: int


class ProviderCallError(Exception):
    """A raw provider call failed for a transient reason (network, rate limit, 5xx) -
    the gateway's bounded-retry loop catches this specifically, distinct from a
    structured-output validation failure.
    """


class BedrockProvider(Protocol):
    async def raw_generate(
        self,
        *,
        model_id: str,
        system_prompt: str,
        user_message: str,
        json_schema: dict,
        max_output_tokens: int,
    ) -> RawGeneration: ...


class EmbeddingProvider(Protocol):
    async def raw_embed(self, *, model_id: str, texts: list[str]) -> RawEmbedding: ...
