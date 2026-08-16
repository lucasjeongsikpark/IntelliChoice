from functools import lru_cache

from intellichoice_adapters.fake_auth import DEV_JWT_SECRET
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEARNING_", env_file=".env", extra="ignore")

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    mysql_url: str = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

    # D-092: RDS's native `manage_master_user_password` (real auto-rotation, S33) makes
    # the master password a Secrets-Manager-managed JSON secret, not a ready DSN string.
    # ECS's `secrets` block extracts one JSON key per env var (can't concatenate several
    # into one URL), so a real deployment supplies these five components instead of
    # `database_url` directly; `_build_dsns_from_managed_secret_components` below
    # assembles the DSN from them. All `None` by default - local dev/CI/tests keep using
    # `database_url`'s hardcoded default unchanged.
    db_username: str | None = None
    db_password: str | None = None
    db_host: str | None = None
    db_port: str | None = None
    db_name: str | None = None

    # Mirrors the five fields above, for `mysql_url` - no `mysql_db_name` (`mysql_url`
    # itself never embeds a dbname; `MySQLProfileAdapter`/seed scripts attach it
    # separately via `make_url(...).set(database=...)`).
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

    # D-085: was an unconditional `JwtTokenVerifier()` (hardcoded `DEV_JWT_SECRET`,
    # public in source) with no override path at all - now settings-driven so a real
    # deployment can inject a random, per-environment, Secrets-Manager-backed value.
    # Defaults to the same public dev constant so local dev/CI/tests need no changes.
    jwt_signing_secret: str = DEV_JWT_SECRET

    # D-085: `/dev/token` requires BOTH this flag AND environment=="dev" - two
    # independent settings that must each be misconfigured before the endpoint reopens,
    # rather than one (S32/D-084 shipped staging with LEARNING_ENVIRONMENT=dev, which
    # alone was enough to leave this reachable on the real ALB). Defaults True so
    # existing local dev/CI/test behavior needs no changes; a real deployment must set
    # this to false explicitly (staging now does, in terraform).
    dev_token_endpoint_enabled: bool = True

    # S36/D-097: the audit sessions' only authenticated path against live staging. Real
    # auth does not exist until S44 (INTEGRATION_PLAN I1), and S35 closing the `/dev/token`
    # P0 correctly left staging with no way to obtain a token at all - which blocks
    # §2.3's adversarial end-to-end runs and §2.6's criterion 3 for all four audits.
    #
    # This is a *third*, independent way to reach `/dev/token`, deliberately unlike the
    # two above: it is gated on possession of a 64-char random secret held in Secrets
    # Manager and presented as an `X-Staging-Token-Secret` header, not on an
    # environment-name string or a boolean env var. That distinction is the whole point -
    # the P0 was an *unauthenticated* minting endpoint, and both prior gates were plain
    # config values that a single tfvars edit could flip (S32 did exactly that).
    #
    # Empty by default, so local dev, CI, and tests are unaffected and no non-staging
    # deployment can enable it by accident. Deleted at S44, when a real token issuer
    # replaces it.
    staging_token_shared_secret: str = ""

    # SPEC §5.25.1 Bedrock Gateway - "mock" (default, dev/tests) or "bedrock" (real
    # AnthropicBedrockMantle client, D-002's env-selected-real-client pattern).
    bedrock_provider: str = "mock"
    bedrock_aws_region: str = "us-east-1"
    bedrock_tutor_model_id: str = "anthropic.claude-sonnet-5"
    # SPEC §5.18.3: `youtube_catalog.search` embeds the query text (S15).
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_call_timeout_s: float = 20.0
    bedrock_max_retries: int = 2

    # SPEC §5.25.1's outer bound, ported from chat-api's `chat_turn_deadline_s` (D-346/D-374).
    # learning-api had none: the gateway ladder is 3 attempts x 20s plus 0.5s and 1.0s of
    # backoff = **61.5s**, against CloudFront's 60s origin read timeout. Measured by D-208 -
    # `POST /exam/finalize` at 65-81s with 61502.69ms of Bedrock, "identical to the
    # millisecond, the signature of a ceiling being hit". The student got an opaque edge 504
    # while the backend kept working and kept spending. 50s sits under the edge's 60s so the
    # caller sees this app's own structured 504 rather than CloudFront's.
    learning_turn_deadline_s: float = 50.0
    # D-208: memory consolidation gets its own, longer ceiling because it is a different
    # size of call. Every other task here is one short generation - a tutor reply measures
    # ~3-4 s on staging. Consolidation sends up to 20 000 tokens of session events plus
    # every existing fact for the student, and asks for a structured response sized to
    # that. Under the shared 20 s ceiling it timed out on all three attempts, every time
    # it ever ran: fourteen days of staging logs contain two attempts and zero successes.
    #
    # Safe to make this large *because* D-208 also took the call off the request path -
    # nobody is waiting on it now. Under the old inline arrangement a bigger number would
    # have made the student's wait worse, which is presumably why it was never raised.
    bedrock_consolidation_timeout_s: float = 120.0
    bedrock_circuit_failure_threshold: int = 5
    bedrock_circuit_cooldown_s: float = 30.0
    bedrock_session_budget_cents: float = 50.0

    # SPEC §5.24/§6.16 MCP tool registry - per-call timeout for `gmail.send_email`.
    mcp_tool_timeout_s: float = 10.0

    # D-087/S34: mirrors `chat_api.config.Settings.global_rate_limit_max_per_window` -
    # see that field's comment for the full rationale, including the S34 load-test
    # finding that raised this from 1,000 to 6,000.
    global_rate_limit_max_per_window: int = 6000
    global_rate_limit_window_s: float = 60.0

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

        S34: `?sslmode=require` for any real deployed host (RDS's own default parameter
        group ships `rds.force_ssl=1` - see `intellichoice_db.engine.create_engine`'s
        matching comment for the real connection failure this fixes and why it's
        detected by host, not a new setting). `psycopg` (unlike `asyncpg`) understands
        the standard libpq `sslmode` query parameter directly in the DSN string, so this
        needs its own fix distinct from `create_engine`'s `connect_args` approach -
        `AsyncPostgresSaver.from_conn_string` never goes through `create_engine` at all.
        """
        url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        if make_url(url).host not in ("localhost", "127.0.0.1"):
            url += "?sslmode=require"
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
