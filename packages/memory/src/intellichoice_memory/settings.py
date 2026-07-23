"""Standalone Bedrock + window config for the offline memory consolidation worker (S25),
mirroring `intellichoice_youtube.settings.YoutubeSyncSettings`'s shape (D-014's pattern
applied to this pipeline) - own env prefix, no `learning_api`/`chat_api` import.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryConsolidationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORY_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_consolidation_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    # One consolidation call per active student per run - a small cohort pre-launch.
    bedrock_run_budget_cents: float = 200.0
    # SPEC §5.15.4's "previous week's structured events" - the CLI computes
    # [now - window_days, now) each run rather than snapping to a calendar week, so a
    # manual trigger on any day still covers a full rolling week (D-051's "manual
    # trigger only" posture, same as `webcontent-sync`/`youtube-sync`).
    window_days: int = 7


@lru_cache
def get_consolidation_settings() -> MemoryConsolidationSettings:
    return MemoryConsolidationSettings()
