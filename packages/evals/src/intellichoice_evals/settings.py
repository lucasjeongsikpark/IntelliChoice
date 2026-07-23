"""Standalone Bedrock config for the LLM-as-judge harness (SPEC §5.31.3, S30).

Mirrors `intellichoice_curriculum.settings.CurriculumPipelineSettings`'s shape (own env
prefix, same env-selected-provider pattern, D-002) rather than importing either app's
`Settings` - this package is a test/eval-time consumer of both apps' generated content,
never the reverse (same "never the other way around" rule D-009/D-014 already state for
`packages/db`/`packages/curriculum`).

`bedrock_judge_model_id` defaults to a *different* model than either app's
`bedrock_tutor_model_id`/`bedrock_rag_answer_model_id` ("anthropic.claude-sonnet-5") -
SPEC §5.31.3's "use a judge model different from the production answerer when possible"
is satisfied architecturally by this default alone, before any real credential exists to
verify it against (same "never exercised against real AWS" caveat as D-025/D-035/D-046).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class EvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EVALS_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_judge_model_id: str = "anthropic.claude-haiku-4-5"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    bedrock_run_budget_cents: float = 200.0


@lru_cache
def get_eval_settings() -> EvalSettings:
    return EvalSettings()
