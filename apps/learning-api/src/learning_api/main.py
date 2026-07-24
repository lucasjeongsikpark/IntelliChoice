from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_adapters.fake_auth import FakeTokenIssuer
from intellichoice_adapters.fake_email import FakeEmailTransport
from intellichoice_adapters.mysql_profile_adapter import MySQLProfileAdapter
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_observability.langsmith_config import configure_langsmith
from intellichoice_observability.logging_config import configure_logging
from intellichoice_observability.metrics import install_http_metrics_middleware, render_metrics
from intellichoice_observability.request_logging import install_request_logging_middleware
from intellichoice_observability.tracing import (
    configure_tracing_provider,
    instrument_fastapi_app,
    instrument_sqlalchemy_engines,
)
from intellichoice_shared.auth import Audience, Role, TokenClaims
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.db_ready import ping_engine
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.mcp import McpTool, McpToolRegistry
from intellichoice_shared.profiles import AttendanceStatus, ProfileAdapter
from intellichoice_shared.rate_limit import install_global_rate_limit_middleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pydantic import BaseModel

from learning_api.authorization import resolve_target_student
from learning_api.config import get_settings
from learning_api.dependencies import get_current_claims, get_profile_adapter
from learning_api.graph.build import build_graph
from learning_api.routers.questions import router as questions_router
from learning_api.routers.sessions import router as sessions_router
from learning_api.routers.stream import router as stream_router
from learning_api.routers.students import router as students_router
from learning_api.services.session_events import SessionEventBus

UNKNOWN_ATTENDANCE_MESSAGE = (
    "We could not verify attendance at this time. For student safety and record "
    "accuracy, the learning session cannot begin until attendance is confirmed."
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()

    # SPEC §5.32 Observability (S31) - structured logging first, since every other
    # startup step's `logger.info(...)` calls should already be JSON-formatted.
    configure_logging(level=settings.log_level)
    configure_langsmith()

    adapter = MySQLProfileAdapter(settings.mysql_url)
    app.state.profile_adapter = adapter
    # SPEC §5.14.1 SSE stream's in-process pub/sub (S11) - one bus for the app's
    # lifetime, same D-007 lifespan-singleton pattern as everything else on `app.state`.
    app.state.session_events = SessionEventBus()
    # Gmail MCP stand-in (SPEC §5.24) - real client selection by env is a future
    # session's scope once real Google credentials exist (D-002's pattern). Only ever
    # called through `mcp_registry` below (S14), never directly.
    email_transport = FakeEmailTransport()
    app.state.email_transport = email_transport

    # MCP tool registry (SPEC §5.22-§5.24, Phase 15/§6.16) - one instance for the app's
    # lifetime (D-007's lifespan pattern). Only `gmail.send_email` has a caller here
    # (the attendance-escalation email); `calendar.create_event` has no learning-api
    # caller, so it isn't registered (D-022's "add when there's a real caller"
    # convention).
    app.state.mcp_registry = McpToolRegistry()
    app.state.mcp_registry.register(
        McpTool(
            name="gmail.send_email",
            args_model=EmailMessage,
            handler=email_transport.send,
            timeout_s=settings.mcp_tool_timeout_s,
        )
    )

    # Bedrock Gateway (SPEC §5.25.1) - env-selected provider (D-002's pattern), the
    # resilience wrapper built once so its circuit-breaker state persists for the app's
    # lifetime (D-007's lifespan pattern, same rationale as `AsyncPostgresSaver` below).
    # `MockBedrockProvider` implements both `raw_generate` and `raw_embed`, so it
    # doubles as both providers in dev/tests (mirrors `chat_api.main`'s S15 wiring) -
    # `create_embedding` is used by the `youtube_catalog.search` MCP tool (§5.18.3).
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
            BedrockTask.TUTOR: settings.bedrock_tutor_model_id,
            # S21: hint personalization rewrites a canonical hint - the same tutoring
            # task family as TUTOR, not a distinct capability, so it reuses the same
            # configured model rather than adding a new settings field.
            BedrockTask.HINT_PERSONALIZATION: settings.bedrock_tutor_model_id,
            # S24: chat intent classification and free replies are the same tutoring
            # task family too - same posture as HINT_PERSONALIZATION above.
            BedrockTask.LEARNING_CHAT_INTENT: settings.bedrock_tutor_model_id,
            BedrockTask.TUTOR_CHAT: settings.bedrock_tutor_model_id,
            # S25: the finalize_exam node's inline session-scoped consolidation call
            # (plan §9 trigger (a)) - the weekly batch CLI has its own separate
            # gateway/settings (`intellichoice_memory.settings`), same "own
            # process, own config" posture as `youtube-sync`/`webcontent-sync`.
            BedrockTask.MEMORY_CONSOLIDATION: settings.bedrock_tutor_model_id,
            # S26: stage narratives are the same tutoring task family too - same
            # posture as HINT_PERSONALIZATION/LEARNING_CHAT_INTENT above.
            BedrockTask.STAGE_NARRATIVE: settings.bedrock_tutor_model_id,
            # S28: report interpretation/recommendations - same tutoring task family
            # too (SPEC §5.25.2 lists "Parent report" as its own row, but this project
            # hasn't yet needed a model distinct from TUTOR for any generative task -
            # same posture as HINT_PERSONALIZATION/STAGE_NARRATIVE above; easy to split
            # into its own settings field later if a summarization-tuned model proves
            # better).
            BedrockTask.PARENT_REPORT: settings.bedrock_tutor_model_id,
            BedrockTask.EMBEDDING: settings.bedrock_embedding_model_id,
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

    # One checkpointer connection pool for the app's lifetime (D-007's lifespan pattern -
    # `AsyncPostgresSaver` opens its own psycopg connections, separate from the SQLAlchemy
    # engine above). `.setup()` creates the checkpoint tables if missing; safe to call
    # every startup (SPEC §5.16).
    async with AsyncPostgresSaver.from_conn_string(settings.checkpoint_database_url) as saver:
        await saver.setup()
        app.state.learning_graph = build_graph(saver)
        yield

    await adapter.close()
    await engine.dispose()


# SPEC §5.32 Observability (S31) - must run *before* `FastAPI(...)` receives its first
# ASGI call of any kind (including the "lifespan" scope itself), since Starlette caches
# its middleware stack on that first call - see `configure_tracing_provider`'s docstring
# for the live bug this fixes.
_otel_provider = configure_tracing_provider(
    service_name=get_settings().otel_service_name,
    otlp_endpoint=get_settings().otel_exporter_otlp_endpoint,
    enabled=get_settings().otel_enabled,
)

app = FastAPI(title="IntelliChoice Learning API", lifespan=lifespan)
if _otel_provider is not None:
    instrument_fastapi_app(app, _otel_provider)
# S11's `apps/learning-web` dev server (Vite default port) - the real deployment puts
# both apps behind `learning.intellichoice.org`, so this is a dev-only convenience, not a
# production CORS policy decision (see docs/DECISIONS.md D-032).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# D-087: general per-IP request cap, a stopgap against gross traffic/cost abuse until a
# real WAF exists - see `Settings.global_rate_limit_max_per_window`'s comment.
#
# S34: installed BEFORE (so it ends up *inside*/wrapped-by) request_logging/http_metrics
# below - Starlette's middleware stack is LIFO by registration order, so whichever
# middleware is installed *last* is outermost and sees every request/response first/last.
# The original order had rate-limit installed last (outermost), which meant a 429 short-
# circuited before request_logging or http_metrics ever ran - real 429s from S34's own
# load test were completely invisible in both the structured access log and Prometheus
# metrics, not just to the rejected caller. Found live: a realistic one-shot
# 150-concurrent-session k6 run (load-tests/k6/learning_sessions.js) tripped the
# then-default 1,000 req/60s cap - exactly 600 setup requests (150 sessions x 4 setup
# calls) plus 400 successful answers before the 1,000th request closed the window on
# everyone still in flight - and none of the ~1,100 resulting 429s left any trace in the
# access log; only the request-count math revealed it (see DECISIONS.md's S34 entry).
install_global_rate_limit_middleware(
    app,
    max_per_window=get_settings().global_rate_limit_max_per_window,
    window_s=get_settings().global_rate_limit_window_s,
)
# SPEC §5.32 Observability (S31) - registered at module level (not inside `lifespan`)
# since FastAPI's middleware stack is built once and must be in place before the first
# request; `otel_enabled`'s FastAPI/SQLAlchemy auto-instrumentation is the one piece
# that's lifespan-scoped, since it needs the per-lifespan `engine`s (see `lifespan` above).
install_request_logging_middleware(app)
install_http_metrics_middleware(app, service_name=get_settings().otel_service_name)

app.include_router(sessions_router)
app.include_router(stream_router)
app.include_router(students_router)
app.include_router(questions_router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}


@app.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    """S34: the ALB target group's real health check (see `db_ready.py`'s docstring) -
    `/healthz` above stays dependency-free.
    """
    postgres_ok = await ping_engine(request.app.state.db_engine)
    mysql_ok = await ping_engine(request.app.state.profile_adapter.engine)
    if postgres_ok and mysql_ok:
        return JSONResponse({"status": "ready", "postgres": True, "mysql": True})
    return JSONResponse(
        {"status": "not_ready", "postgres": postgres_ok, "mysql": mysql_ok},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.get("/metrics")
async def metrics_endpoint() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


class AttendanceResponse(BaseModel):
    student_external_id: str
    status: AttendanceStatus
    message: str | None = None


@app.get("/students/{student_id}/attendance", response_model=AttendanceResponse)
async def get_attendance(
    student_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
) -> AttendanceResponse:
    target_student_id = await resolve_target_student(claims, student_id, profile_adapter)
    attendance = await profile_adapter.get_current_week_attendance(target_student_id)
    message = UNKNOWN_ATTENDANCE_MESSAGE if attendance == AttendanceStatus.UNKNOWN else None
    return AttendanceResponse(
        student_external_id=target_student_id, status=attendance, message=message
    )


class DevTokenRequest(BaseModel):
    role: Role
    sub: str
    audience: Audience = Audience.LEARNING


class DevTokenResponse(BaseModel):
    token: str


@app.post("/dev/token", response_model=DevTokenResponse)
async def issue_dev_token(body: DevTokenRequest) -> DevTokenResponse:
    """Dev-only stand-in for `go.intellichoice.org`'s real auth (out of scope here) so
    `apps/learning-web` has something to call locally. 404s unless BOTH
    `environment=="dev"` AND `dev_token_endpoint_enabled` are true (D-085) - it must
    never exist as reachable surface in a real deployment - wraps the existing
    `FakeTokenIssuer` (D-006), issues no new secret.
    """
    settings = get_settings()
    if settings.environment != "dev" or not settings.dev_token_endpoint_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    token = FakeTokenIssuer().issue(sub=body.sub, role=body.role, audience=body.audience)
    return DevTokenResponse(token=token)
