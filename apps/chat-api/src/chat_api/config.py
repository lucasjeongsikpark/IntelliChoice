from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_", env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    mysql_url: str = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

    # SPEC §5.25.1 Bedrock Gateway - same "mock" (default, dev/tests) or "bedrock" (real
    # AnthropicBedrockMantle client) env-selection as `learning_api.config` (D-002).
    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_scope_and_intent_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_rerank_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_rag_answer_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_calendar_extraction_model_id: str = "anthropic.claude-sonnet-5"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    bedrock_session_budget_cents: float = 50.0

    # SPEC §5.21.4-5.21.7 retrieval tuning.
    retrieval_candidate_limit: int = 30
    retrieval_top_k: int = 8
    # SPEC §5.21.8: below this confidence the Response Verifier refuses rather than
    # returning a low-confidence guess (§5.29's "No RAG result -> do not guess").
    groundedness_confidence_threshold: float = 0.4

    # SPEC §5.24/§6.16 MCP tool registry.
    mcp_tool_timeout_s: float = 10.0
    # SPEC §5.24.1 "Q&A escalation: Recipient: configured Admin recipient" - a hardcoded
    # dev default (D-006's pattern), not a real secret/credential.
    admin_escalation_email: str = "admin@intellichoice.example"
    # SPEC §5.24.2 anonymous-email rate limiting - keyed by caller (external id or IP),
    # applies only to the admin-escalation send, not every chat message.
    email_rate_limit_max_per_window: int = 5
    email_rate_limit_window_s: float = 3600.0

    # SPEC §5.32 Observability (S31) - off by default (D-002's "fake/off by default,
    # real opt-in" posture), same rationale as `learning_api.config.Settings.
    # otel_enabled` (repeated `TestClient(app)` lifespan re-entry on the same module-
    # level `app` object across the test suite). A real dev run points
    # `CHAT_OTEL_ENABLED=true` at `docker-compose.yml`'s `otel-collector` service.
    otel_enabled: bool = False
    otel_service_name: str = "chat-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    log_level: str = "INFO"

    @property
    def checkpoint_database_url(self) -> str:
        """Same Postgres instance, driverless DSN - `AsyncPostgresSaver` uses `psycopg`,
        not the SQLAlchemy `asyncpg` driver `database_url` names (mirrors
        `learning_api.config.Settings.checkpoint_database_url`).
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
