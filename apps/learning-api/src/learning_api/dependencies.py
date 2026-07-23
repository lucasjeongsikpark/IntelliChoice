from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException, Request, status
from intellichoice_adapters.fake_auth import JwtTokenVerifier, TokenError
from intellichoice_shared.auth import Audience, TokenClaims
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.email import EmailTransport
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.graph.build import LearningGraph
from learning_api.services.session_events import SessionEventBus


@lru_cache
def get_token_verifier() -> JwtTokenVerifier:
    return JwtTokenVerifier()


def get_profile_adapter(request: Request) -> ProfileAdapter:
    return request.app.state.profile_adapter


def get_email_transport(request: Request) -> EmailTransport:
    return request.app.state.email_transport


def get_mcp_registry(request: Request) -> McpToolRegistry:
    return request.app.state.mcp_registry


def get_bedrock_gateway(request: Request) -> BedrockGateway:
    return request.app.state.bedrock_gateway


def get_graph(request: Request) -> LearningGraph:
    return request.app.state.learning_graph


def get_session_events(request: Request) -> SessionEventBus:
    return request.app.state.session_events


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, built from the engine-bound factory on `app.state`
    (D-007's lifespan pattern - the async engine/session factory is constructed once in
    `main.py`'s lifespan, not via `lru_cache`).
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session
        await session.commit()


async def get_current_claims(request: Request) -> TokenClaims:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = auth_header.split(" ", 1)[1]
    try:
        return get_token_verifier().verify(token, Audience.LEARNING)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
        ) from exc
