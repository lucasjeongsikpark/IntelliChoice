"""Standalone Bedrock + sync config for the offline YouTube catalog sync worker (S15),
mirroring `intellichoice_knowledge.settings.KnowledgeIngestSettings`'s shape (D-014's
pattern applied to this pipeline) - own env prefix, no `learning_api`/`chat_api` import.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class YoutubeSyncSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="YOUTUBE_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_classification_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    # One classification + one embedding call per video; a small catalog per channel.
    bedrock_run_budget_cents: float = 200.0
    # SPEC §5.18.1's single hardcoded source channel for this session - a real deployment
    # would sync several; adding more is a config change, not a pipeline change. This is
    # also the S27 channel pin `sync_channel` re-validates every fetched item against.
    channel_id: str = "khan-academy-math"
    # "fake" (default, D-002) or "youtube" - mirrors `bedrock_provider`'s env-selection
    # pattern. `youtube_api_key` is required only when `youtube_provider="youtube"`; no
    # real key exists yet, so this path is unexercised (same posture as `bedrock_provider
    # ="bedrock"` before real AWS creds exist).
    youtube_provider: str = "fake"
    youtube_api_key: str = ""


@lru_cache
def get_sync_settings() -> YoutubeSyncSettings:
    return YoutubeSyncSettings()
