import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.fake_calendar import FakeCalendarTransport
from intellichoice_adapters.fake_email import FakeEmailTransport
from intellichoice_adapters.fake_maps import FakeMapsProvider
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_observability.langsmith_config import configure_langsmith
from intellichoice_observability.logging_config import configure_logging
from intellichoice_observability.metrics import install_http_metrics_middleware, render_metrics
from intellichoice_observability.request_logging import install_request_logging_middleware
from intellichoice_observability.tracing import (
    configure_tracing_provider,
    instrument_fastapi_app,
    instrument_sqlalchemy_engines,
)
from intellichoice_shared.auth import Audience, Role, TokenClaims, staging_secret_matches
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.calendar import CalendarEvent
from intellichoice_shared.db_ready import ping_engine
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.maps import GeocodeQuery, RouteQuery
from intellichoice_shared.mcp import McpTool, McpToolRegistry
from intellichoice_shared.rate_limit import (
    InMemoryRateLimiter,
    install_global_rate_limit_middleware,
)
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import BaseModel

from chat_api.config import get_settings
from chat_api.dependencies import get_current_claims
from chat_api.graph.build import build_graph
from chat_api.routers.events import router as events_router
from chat_api.routers.meta import router as meta_router
from chat_api.routers.sessions import router as sessions_router
from chat_api.routers.stream import router as stream_router
from chat_api.services.session_events import ChatSessionEventBus

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # SPEC §5.32 Observability (S31) - structured logging first, mirrors
    # `learning_api.main.lifespan`'s same ordering.
    configure_logging(level=settings.log_level)
    configure_langsmith()

    adapter = MySQLProfileAdapter(settings.mysql_url)
    app.state.profile_adapter = adapter
    app.state.session_events = ChatSessionEventBus()

    # Gmail/Google Calendar/Google Maps MCP stand-ins (SPEC §5.23-§5.24, §5.22) - real
    # clients selected by env once real Google credentials exist (D-002's pattern); only
    # ever called through `mcp_registry` below.
    email_transport = FakeEmailTransport()
    calendar_transport = FakeCalendarTransport()
    maps_provider = FakeMapsProvider()
    app.state.email_transport = email_transport
    app.state.calendar_transport = calendar_transport
    app.state.maps_provider = maps_provider

    # MCP tool registry (SPEC §5.22-§5.24, Phase 15/§6.16) - one instance for the app's
    # lifetime (D-007's lifespan pattern).
    app.state.mcp_registry = McpToolRegistry()
    app.state.mcp_registry.register(
        McpTool(
            name="gmail.send_email",
            args_model=EmailMessage,
            handler=email_transport.send,
            timeout_s=settings.mcp_tool_timeout_s,
        )
    )
    app.state.mcp_registry.register(
        McpTool(
            name="calendar.create_event",
            args_model=CalendarEvent,
            handler=calendar_transport.create_event,
            timeout_s=settings.mcp_tool_timeout_s,
        )
    )
    app.state.mcp_registry.register(
        McpTool(
            name="maps.geocode",
            args_model=GeocodeQuery,
            handler=maps_provider.geocode,
            timeout_s=settings.mcp_tool_timeout_s,
        )
    )
    app.state.mcp_registry.register(
        McpTool(
            name="maps.compute_routes",
            args_model=RouteQuery,
            handler=maps_provider.compute_route,
            timeout_s=settings.mcp_tool_timeout_s,
        )
    )

    # SPEC §5.24.2 anonymous-email rate limiting - scoped to the admin-escalation send.
    app.state.email_rate_limiter = InMemoryRateLimiter(
        max_per_window=settings.email_rate_limit_max_per_window,
        window_s=settings.email_rate_limit_window_s,
    )

    # Bedrock Gateway (SPEC §5.25.1) - env-selected provider (D-002's pattern), one
    # instance for the app's lifetime so its circuit-breaker state persists (D-007).
    # `MockBedrockProvider` implements both `raw_generate` and `raw_embed`, so it
    # doubles as both the chat provider and the embedding provider in dev/tests
    # (mirrors `intellichoice_knowledge.ingest_cli._build_gateway`).
    if settings.bedrock_provider == "bedrock":
        chat_provider = AnthropicBedrockProvider(aws_region=settings.bedrock_aws_region)
        embedding_provider = TitanEmbeddingProvider(aws_region=settings.bedrock_aws_region)
    else:
        mock = MockBedrockProvider()
        chat_provider = mock
        embedding_provider = mock

    app.state.bedrock_gateway = ResilientBedrockGateway(
        provider=chat_provider,
        embedding_provider=embedding_provider,
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: settings.bedrock_scope_and_intent_model_id,
            BedrockTask.RERANK: settings.bedrock_rerank_model_id,
            BedrockTask.RAG_ANSWER: settings.bedrock_rag_answer_model_id,
            BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id,
            BedrockTask.CALENDAR_EXTRACTION: settings.bedrock_calendar_extraction_model_id,
        },
        call_timeout_s=settings.bedrock_call_timeout_s,
        max_retries=settings.bedrock_max_retries,
        circuit_failure_threshold=settings.bedrock_circuit_failure_threshold,
        circuit_cooldown_s=settings.bedrock_circuit_cooldown_s,
        session_budget_cents=settings.bedrock_session_budget_cents,
    )

    engine = create_engine(settings.database_url)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)

    if _otel_provider is not None:
        instrument_sqlalchemy_engines(engine, adapter.engine, provider=_otel_provider)

    # One checkpointer connection pool for the app's lifetime (D-007), mirroring
    # `learning_api.main.lifespan`. `.setup()` is safe to call every startup.
    async with AsyncPostgresSaver.from_conn_string(settings.checkpoint_database_url) as saver:
        await saver.setup()
        app.state.qa_graph = build_graph(saver)
        yield

    await adapter.close()
    await engine.dispose()


# SPEC §5.32 Observability (S31) - must run *before* `FastAPI(...)` receives its first
# ASGI call of any kind, mirroring `learning_api.main`'s same fix (see
# `configure_tracing_provider`'s docstring for the live bug this avoids).
_otel_provider = configure_tracing_provider(
    service_name=get_settings().otel_service_name,
    otlp_endpoint=get_settings().otel_exporter_otlp_endpoint,
    enabled=get_settings().otel_enabled,
)

app = FastAPI(title="IntelliChoice Q&A API", lifespan=lifespan)
if _otel_provider is not None:
    instrument_fastapi_app(app, _otel_provider)
# `apps/chat-web`'s dev server - dev-only convenience, not a production CORS policy
# decision, matching `learning_api.main`'s same caveat (docs/DECISIONS.md D-032). Both
# 5173 (Vite's default, used by `learning-web`) and 5174 (`chat-web`'s pinned port when
# both frontends run side by side, since they'd otherwise collide on 5173) are allowed -
# only one of the two apps' web clients is ever actually served from a given origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# D-087: general per-IP request cap, a stopgap against gross traffic/cost abuse until a
# real WAF exists - see `Settings.global_rate_limit_max_per_window`'s comment.
#
# S34: installed BEFORE (so it ends up *inside*/wrapped-by) request_logging/http_metrics
# below - see the matching comment in `learning_api.main` for the full reasoning (a real
# S34 load-test finding: the original order made every 429 invisible to both the access
# log and Prometheus metrics, not just to the rejected caller).
install_global_rate_limit_middleware(
    app,
    max_per_window=get_settings().global_rate_limit_max_per_window,
    window_s=get_settings().global_rate_limit_window_s,
)
# SPEC §5.32 Observability (S31) - registered at module level, mirrors
# `learning_api.main`'s same reasoning (middleware must be in place before the first
# request; the FastAPI/SQLAlchemy auto-instrumentation stays lifespan-scoped since it
# needs the per-lifespan `engine`s).
install_request_logging_middleware(app)
install_http_metrics_middleware(app, service_name=get_settings().otel_service_name)

app.include_router(sessions_router)
app.include_router(stream_router)
app.include_router(events_router)
app.include_router(meta_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}


@app.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """S34: the ALB target group's real health check - see `intellichoice_shared.
    db_ready`'s docstring for why this is separate from `/healthz` above.

    AUD-C-16: also fails closed when any stored rag_chunks embedding was not produced
    by the configured embedding provider/model. Staging served real Titan query vectors
    against mock hash vectors for weeks - retrieval was noise and nothing detected it.
    A mismatched corpus means every semantic search is wrong, so the service is not
    ready; `make knowledge-reembed` (run by the deploy after migrations) clears it.
    An *empty* corpus passes - fresh environments boot before first ingestion, and the
    no-approved-source refusal (SPEC §5.21.8) already covers the no-corpus case.
    """
    settings = get_settings()
    postgres_ok = await ping_engine(request.app.state.db_engine)
    mysql_ok = await ping_engine(request.app.state.profile_adapter.engine)
    corpus_mismatches: int | None = None
    if postgres_ok:
        async with request.app.state.db_session_factory() as session:
            corpus_mismatches = await RagRepository(
                session
            ).count_embedding_provenance_mismatches(
                embedding_provider=settings.bedrock_provider,
                embedding_model_id=settings.bedrock_embedding_model_id,
            )
    corpus_ok = corpus_mismatches == 0
    if postgres_ok and mysql_ok and corpus_ok:
        return JSONResponse(
            {"status": "ready", "postgres": True, "mysql": True, "corpus": True}
        )
    return JSONResponse(
        {
            "status": "not_ready",
            "postgres": postgres_ok,
            "mysql": mysql_ok,
            "corpus": corpus_ok,
            "corpus_embedding_mismatches": corpus_mismatches,
        },
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


@app.get("/me")
async def me(claims: Annotated[TokenClaims, Depends(get_current_claims)]) -> dict[str, str]:
    return {"sub": claims.sub, "role": claims.role.value, "audience": claims.audience.value}


class DevTokenRequest(BaseModel):
    role: Role
    sub: str
    audience: Audience = Audience.CHAT


class DevTokenResponse(BaseModel):
    token: str


@app.post("/dev/token", response_model=DevTokenResponse)
async def issue_dev_token(
    body: DevTokenRequest,
    x_staging_token_secret: Annotated[str | None, Header()] = None,
) -> DevTokenResponse:
    """Dev-only stand-in for `go.intellichoice.org`'s real auth (out of scope here) so
    `apps/chat-web` has something to call locally - mirrors `learning_api.main.
    issue_dev_token` (D-006/D-032's pattern) verbatim, just defaulting to
    `Audience.CHAT`. 404s unless EITHER the local-dev path (`environment=="dev"` AND
    `dev_token_endpoint_enabled`, D-085) or the staging-secret path (S36/D-097) holds -
    see that function's docstring for the full rationale of both.
    """
    settings = get_settings()
    local_dev_path = settings.environment == "dev" and settings.dev_token_endpoint_enabled
    staging_path = staging_secret_matches(
        x_staging_token_secret, settings.staging_token_shared_secret
    )
    if not (local_dev_path or staging_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    # S36: mirrors learning-api's identical fix - see that comment for the real staging
    # failure this closes (issuer signed with the public dev constant, verifier used the
    # real per-app secret, so every minted token was rejected).
    token = FakeTokenIssuer(secret=settings.jwt_signing_secret).issue(
        sub=body.sub, role=body.role, audience=body.audience
    )
    if not local_dev_path:
        # S36/D-097: mirrors learning-api's audit-trail log - see that comment.
        logger.warning(
            "staging_dev_token_issued sub=%s role=%s audience=%s",
            body.sub,
            body.role.value,
            body.audience.value,
        )
    return DevTokenResponse(token=token)
