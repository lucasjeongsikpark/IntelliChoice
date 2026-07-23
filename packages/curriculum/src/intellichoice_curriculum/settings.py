"""Standalone Bedrock config for the offline AI question-generation pipeline (S9).

Deliberately does NOT import `learning_api.config` - `packages/curriculum` is a package
that both apps and offline tooling depend on, never the other way around (D-009, D-014).
Mirrors `learning_api.config.Settings`'s shape (same env-selected provider pattern,
D-002) but with its own env prefix and a batch-appropriate default cost budget, since one
pipeline run makes many more Bedrock calls than one learning session's intervention.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class CurriculumPipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CURRICULUM_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_generation_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_review_model_id: str = "anthropic.claude-sonnet-5"
    # S20 authored mode (plan §7): generator + judge get their own model slots; solver A/B
    # deliberately reuse the two slots above instead of adding a third (see ai_pipeline's
    # module docstring) so they resolve to two different models without a new setting.
    bedrock_authored_generation_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_judge_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    # A full candidate costs up to 6 calls (generator + 2 solvers + 3 reviewers); a batch
    # run generating many candidates needs a much larger ceiling than one learning
    # session's per-intervention budget (`bedrock_session_budget_cents` = 50 in
    # `learning_api.config`).
    bedrock_run_budget_cents: float = 1000.0


@lru_cache
def get_pipeline_settings() -> CurriculumPipelineSettings:
    return CurriculumPipelineSettings()
