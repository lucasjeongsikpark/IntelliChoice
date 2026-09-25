import asyncio
from typing import Any


def test_prompt_caching_is_offered_only_to_families_measured_to_accept_it() -> None:
    """An unsupported `cachePoint` is a `ValidationException`, i.e. a failed paid call.

    A prefix check costs nothing and tells us the same thing, so the families here are the
    ones actually measured on this account rather than the ones documented somewhere (D-203).
    """
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import _supports_prompt_caching

    assert _supports_prompt_caching("us.anthropic.claude-haiku-4-5-20251001-v1:0")
    assert _supports_prompt_caching("anthropic.claude-sonnet-5")
    # Measured to fail or ignore it - left alone rather than probed with real money.
    assert not _supports_prompt_caching("mistral.mistral-large-3-675b-instruct")
    assert not _supports_prompt_caching("qwen.qwen3-32b-v1:0")
    assert not _supports_prompt_caching("openai.gpt-oss-120b-1:0")


# --- Where the cache points go (MEMORY-CACHE-WRITE-UNBILLED, D-460 finding #4) ---------
#
# The first-user cache point exists for the tool loop, where Converse resends the same first
# user message every round (D-203). Without tools there is exactly one round, and the D-217
# repair changes that user text, so the entry it writes can never be read - on a ~7k-token
# consolidation payload it was a 1.25x surcharge on every call and a hit on none.

HAIKU_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_CACHE_POINT = {"cachePoint": {"type": "default"}}


class _RecordingConverseClient:
    """Stands in for the boto3 `bedrock-runtime` client: records each `converse(**kwargs)`
    and answers with a canned `emit_result` tool call carrying cache usage."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {
            "stopReason": "tool_use",
            "usage": {
                "inputTokens": 24,
                "outputTokens": 50,
                "cacheReadInputTokens": 0,
                "cacheWriteInputTokens": 6785,
            },
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"toolUse": {"toolUseId": "t1", "name": "emit_result", "input": {"a": 1}}}
                    ],
                }
            },
        }


def _provider_with(client: _RecordingConverseClient):
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider

    provider = AnthropicBedrockProvider.__new__(AnthropicBedrockProvider)  # no boto3 client
    provider._client = client  # type: ignore[attr-defined]
    return provider


def _generate(client: _RecordingConverseClient, model_id: str, tools: list[dict] | None = None):
    provider = _provider_with(client)
    return asyncio.run(
        provider.raw_generate(
            model_id=model_id,
            system_prompt="system",
            user_message="payload",
            json_schema={"type": "object"},
            max_output_tokens=100,
            tools=tools,
            tool_executor=(lambda name, args: {}) if tools else None,
        )
    )


_HELPER_TOOL = {
    "toolSpec": {
        "name": "lookup",
        "description": "a helper tool",
        "inputSchema": {"json": {"type": "object"}},
    }
}


def test_a_call_without_tools_caches_the_system_prompt_only() -> None:
    client = _RecordingConverseClient()
    raw = _generate(client, HAIKU_ID)
    [call] = client.calls
    assert call["system"] == [{"text": "system"}, _CACHE_POINT]
    assert call["messages"][0]["content"] == [{"text": "payload"}]
    # The provider still reports what Bedrock billed, cache fields included.
    assert raw.cache_write_tokens == 6785
    assert raw.input_tokens == 24


def test_a_tool_using_call_keeps_both_cache_points() -> None:
    """D-203's measured path is unchanged: the tool loop is where the first-user cache
    point is read, once per round."""
    client = _RecordingConverseClient()
    _generate(client, HAIKU_ID, tools=[_HELPER_TOOL])
    [call] = client.calls
    assert call["system"] == [{"text": "system"}, _CACHE_POINT]
    assert call["messages"][0]["content"] == [{"text": "payload"}, _CACHE_POINT]


def test_a_family_without_prompt_caching_gets_no_cache_points_either_way() -> None:
    for tools in (None, [_HELPER_TOOL]):
        client = _RecordingConverseClient()
        _generate(client, "mistral.mistral-large-3-675b-instruct", tools=tools)
        [call] = client.calls
        assert call["system"] == [{"text": "system"}]
        assert call["messages"][0]["content"] == [{"text": "payload"}]
