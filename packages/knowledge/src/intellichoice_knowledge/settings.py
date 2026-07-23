"""Standalone Bedrock config for the offline RAG ingestion pipeline (S12), mirroring
`intellichoice_curriculum.settings.CurriculumPipelineSettings`'s shape (D-014's pattern
applied to ingestion) - own env prefix, no `learning_api`/`chat_api` import.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeIngestSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KNOWLEDGE_", env_file=".env", extra="ignore")

    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    # One embedding call per document (all its chunks batched together); 22 placeholder
    # documents plus headroom for future content growth.
    bedrock_run_budget_cents: float = 200.0


@lru_cache
def get_ingest_settings() -> KnowledgeIngestSettings:
    return KnowledgeIngestSettings()
