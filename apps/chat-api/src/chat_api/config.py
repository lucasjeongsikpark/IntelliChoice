from functools import lru_cache

from intellichoice_adapters.fake_auth import DEV_JWT_SECRET
from intellichoice_shared.access_probe_policy import ACCESS_PROBE_MAX_DISTANCE
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_", env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    mysql_url: str = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

    # D-092: mirrors `learning_api.config.Settings`'s identical fields - see that
    # class's comment for the full rationale (RDS `manage_master_user_password`
    # real auto-rotation, S33).
    db_username: str | None = None
    db_password: str | None = None
    db_host: str | None = None
    db_port: str | None = None
    db_name: str | None = None
    mysql_db_username: str | None = None
    mysql_db_password: str | None = None
    mysql_db_host: str | None = None
    mysql_db_port: str | None = None

    @model_validator(mode="after")
    def _build_dsns_from_managed_secret_components(self) -> "Settings":
        if self.db_username and self.db_password and self.db_host and self.db_port and self.db_name:
            self.database_url = (
                f"postgresql+asyncpg://{self.db_username}:{self.db_password}"
                f"@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        mysql_components_present = (
            self.mysql_db_username
            and self.mysql_db_password
            and self.mysql_db_host
            and self.mysql_db_port
        )
        if mysql_components_present:
            self.mysql_url = (
                f"mysql+aiomysql://{self.mysql_db_username}:{self.mysql_db_password}"
                f"@{self.mysql_db_host}:{self.mysql_db_port}"
            )
        return self

    # D-085: mirrors `learning_api.config.Settings.dev_token_endpoint_enabled` - see
    # that field's comment for the full rationale.
    dev_token_endpoint_enabled: bool = True

    # S36/D-097: mirrors `learning_api.config.Settings.staging_token_shared_secret` - see
    # that field's comment for the full rationale. A distinct secret from learning-api's,
    # for the same reason the two `jwt_signing_secret`s are distinct.
    staging_token_shared_secret: str = ""

    # D-085: mirrors `learning_api.config.Settings.jwt_signing_secret` - see that
    # field's comment. A distinct secret from learning-api's (not shared) - the two
    # apps' tokens are already audience-scoped (`Audience.LEARNING`/`Audience.CHAT`)
    # and mutually rejected regardless, so there's no reason to also let a compromised
    # secret cross apps.
    jwt_signing_secret: str = DEV_JWT_SECRET

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
    # AUD-C-20/D-165, raised by AUD-C-21/D-166. Measured, not guessed, and defined once in
    # `intellichoice_shared.access_probe_policy` - that module carries the sweep that chose it.
    access_probe_max_distance: float = ACCESS_PROBE_MAX_DISTANCE
    # SPEC §5.24.2 anonymous-email rate limiting - keyed by caller (external id or IP),
    # applies only to the admin-escalation send, not every chat message.
    email_rate_limit_max_per_window: int = 5
    email_rate_limit_window_s: float = 3600.0
    # D-087: general per-IP request cap across every route (except /healthz, /metrics) -
    # a stopgap against gross traffic/cost abuse (every request can reach Bedrock) until
    # a real WAF exists (SPEC §6.22 lists both separately; no AWS WAF built this
    # session). Generous by design, not a precise abuse threshold: single-process/
    # in-memory (same D-032 caveat as the admin-escalation limiter above), so it must
    # stay well above plausible legitimate burst traffic (including this app's own
    # `TestClient`-driven test suite, which shares one client identity across many
    # tests within the same rolling window) rather than precisely targeting abuse -
    # that precision is the WAF's job once one exists.
    #
    # S34: the original 1,000 was *not* well above plausible legitimate burst traffic -
    # this app is used from real school branches, where many concurrent students
    # legitimately share one egress IP, which is exactly the key this limiter keys on.
    # A real local k6 run (load-tests/k6/, one-shot, no retries) of 150 concurrent
    # legitimate learning sessions produced ~2,100 requests total (~14/session: token +
    # create + select-student + select-topic + up to 10 answers) and tripped the old
    # 1,000 cap well before every session finished, with ~1,100 legitimate requests
    # rejected. 6,000 gives roughly 3x that measured real burst - headroom for a larger
    # branch and for per-session activity the bare k6 flow doesn't exercise (hints,
    # tutor chat) - while still bounding a single runaway/malicious source (100 req/s
    # sustained is far beyond anything an organic browser client generates). See
    # DECISIONS.md's S34 entry for the full finding, including a related bug this also
    # surfaced: 429s from this middleware weren't reaching the access log/metrics at
    # all (fixed by reordering middleware registration in main.py).
    global_rate_limit_max_per_window: int = 6000
    global_rate_limit_window_s: float = 60.0

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
        `learning_api.config.Settings.checkpoint_database_url`, including S34's
        `?sslmode=require` fix for real RDS's `rds.force_ssl=1`).
        """
        url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        if make_url(url).host not in ("localhost", "127.0.0.1"):
            url += "?sslmode=require"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
