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

    # D-244: matches the apps' `log_level`, so a pipeline run's verbosity is set the same
    # way as a service's rather than being a second convention to remember.
    log_level: str = "INFO"
    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    # D-273 (C1 Phase 0, 2026-08-11): the four slots below are the roster that was
    # measured invocable on this account and then actually run, not the one that reads
    # best. `anthropic.claude-sonnet-5` - what all four defaulted to until now - reports
    # `agreementAvailability = AVAILABLE` and returns `AccessDenied` when invoked, so the
    # old defaults named a pipeline that could not start; and being one id in all four
    # slots, preflight's solver-diversity gate refused it before the first call anyway.
    # The invocable set is two models (Haiku 4.5, Sonnet 4.5), so Generator, Solver A and
    # Solver B cannot all differ - Solver B shares the Generator's weights, the documented
    # asymmetric weakness (QUESTION_GENERATION.md §6). Availability is a dated measurement,
    # not a property: re-measure before a paid run rather than trusting 2026-08-11.
    # Solver A.
    bedrock_generation_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    # Solver B - deliberately the Generator's model (see above).
    bedrock_review_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # S20 authored mode (plan §7): generator + judge get their own model slots; solver A/B
    # deliberately reuse the two slots above instead of adding a third (see ai_pipeline's
    # module docstring) so they resolve to two different models without a new setting.
    # Generator: the role where capability matters most, so it takes the mid-tier model.
    bedrock_authored_generation_model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # D-205. Defaults to the authoring model, so an unset environment behaves exactly as
    # before and splitting the two is a deliberate act.
    bedrock_equation_design_model_id: str = ""
    # Judge, as measured through D-231 -> D-240.
    bedrock_judge_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
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
