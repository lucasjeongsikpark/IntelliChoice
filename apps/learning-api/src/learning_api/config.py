from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEARNING_", env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    mysql_url: str = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

    # SPEC §5.25.1 Bedrock Gateway - "mock" (default, dev/tests) or "bedrock" (real
    # AnthropicBedrockMantle client, D-002's env-selected-real-client pattern).
    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_tutor_model_id: str = "anthropic.claude-sonnet-5"
    # SPEC §5.18.3: `youtube_catalog.search` embeds the query text (S15).
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    bedrock_session_budget_cents: float = 50.0

    # SPEC §5.24/§6.16 MCP tool registry - per-call timeout for `gmail.send_email`.
    mcp_tool_timeout_s: float = 10.0

    # SPEC §5.32 Observability (S31) - off by default (D-002's "fake/off by default,
    # real opt-in" posture): `make test` constructs `TestClient(app)` ~60 times across
    # the suite, re-entering `lifespan` each time on the *same* module-level `app`
    # object, which would otherwise try to `FastAPIInstrumentor.instrument_app` an
    # already-instrumented app repeatedly. `docker-compose.yml`'s `otel-collector`
    # service is what a real dev run points `LEARNING_OTEL_ENABLED=true` at.
    otel_enabled: bool = False
    otel_service_name: str = "learning-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    log_level: str = "INFO"

    @property
    def checkpoint_database_url(self) -> str:
        """Same Postgres instance, driverless DSN - `AsyncPostgresSaver` uses `psycopg`,
        not the SQLAlchemy `asyncpg` driver `database_url` names.
        """
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
