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
    # **120 s, not the 20 s every interactive surface uses (D-141 §6).** Measured on staging
    # twice: this job's calls time out as a function of the *output* budget, not the input.
    # `max_output_tokens_for` scales with a student's existing fact count - 0 facts is 1280
    # tokens and completes; 7 facts is 2176 and does not finish in 20 s. The evidence is that
    # `student-ext-4` (0 facts) succeeded in every arm while `student-ext-1` succeeded on the
    # one call it made with 0 facts and timed out on every call it made with 7.
    #
    # Raising a timeout is what AUD-F-34's own fix warned against - but that warning was about
    # growing a bound to accommodate *unbounded* work, and both bounds now exist: 20k input
    # tokens per call and at most 4 calls per student. With the work bounded, 20 s is simply the
    # wrong number for a weekly background job where nobody is waiting; it was inherited from
    # surfaces where a user is. Two timeouts also cost 6 attempts against a
    # `circuit_failure_threshold` of 5, so a timeout here does not fail one call, it ends the run.
    bedrock_call_timeout_s: float = 120.0
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
