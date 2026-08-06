

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
