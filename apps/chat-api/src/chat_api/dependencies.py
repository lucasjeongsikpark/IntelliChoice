from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException, Request, status
from intellichoice_adapters.fake_auth import JwtTokenVerifier, TokenError
from intellichoice_db.repositories.cost_reservation import CostReservationRepository
from intellichoice_shared.auth import Audience, TokenClaims, account_refusal_reason
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from intellichoice_shared.rate_limit import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.config import get_settings
from chat_api.graph.build import QAGraph
from chat_api.services.session_events import ChatSessionEventBus


@lru_cache
def get_token_verifier() -> JwtTokenVerifier:
    return JwtTokenVerifier(secret=get_settings().jwt_signing_secret)


def _verified(token: str) -> TokenClaims:
    """Signature/expiry/audience, then SPEC §5.1.2's account and consent state.

    AUD-X-02 (S40, D-107): the second half did not exist in either app, so a `suspended`
    or `revoked` token was indistinguishable from a consented one everywhere. 403 rather
    than 401 - the token is genuine, the account may not use the product - and for
    `get_optional_claims` deliberately *not* a silent downgrade to anonymous, on the same
    reasoning that function already gives for invalid tokens: a caller whose consent was
    withdrawn should get a clear signal, not quietly reduced access.
    """
    try:
        claims = get_token_verifier().verify(token, Audience.CHAT)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
        ) from exc
    refusal = account_refusal_reason(claims)
    if refusal is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refusal)
    return claims


async def get_current_claims(request: Request) -> TokenClaims:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    return _verified(auth_header.split(" ", 1)[1])


async def get_optional_claims(request: Request) -> TokenClaims | None:
    """SPEC §5.19.1: anonymous access to public content is a first-class case for the
    Q&A app (unlike `learning_api`, which requires auth on every endpoint) - a missing
    header means "anonymous", not "unauthorized". A *present but invalid* token still
    401s rather than silently downgrading to anonymous, so a client with an expired
    token gets a clear signal instead of a silent access-scope drop.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        return None
    return _verified(auth_header.split(" ", 1)[1])


def get_profile_adapter(request: Request) -> ProfileAdapter:
    return request.app.state.profile_adapter


def get_bedrock_gateway(request: Request) -> BedrockGateway:
    return request.app.state.bedrock_gateway


def get_graph(request: Request) -> QAGraph:
    return request.app.state.qa_graph


def get_session_events(request: Request) -> ChatSessionEventBus:
    return request.app.state.session_events


def get_mcp_registry(request: Request) -> McpToolRegistry:
    return request.app.state.mcp_registry


def get_email_rate_limiter(request: Request) -> RateLimiter:
    return request.app.state.email_rate_limiter


def get_message_rate_limiter(request: Request) -> RateLimiter:
    """D-345's per-caller turn cap. A second limiter rather than a wider scope on the
    escalation one: they bound different things at very different rates (5 deliberate
    button presses an hour vs 120 questions), and sharing a counter would make either
    number un-tunable without moving the other.
    """
    return request.app.state.message_rate_limiter


def get_cost_ledger(request: Request) -> CostReservationRepository:
    """D-345's per-day spend ceiling. Takes the session *factory*, not the request's
    session: a reservation that does not commit until dependency teardown is invisible to
    exactly the concurrent callers it exists to stop (AUD-X-08).
    """
    return CostReservationRepository(request.app.state.db_session_factory)


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    """One session per request, built from the engine-bound factory on `app.state`
    (D-007's lifespan pattern, mirrors `learning_api.dependencies.get_db_session`).
    """
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session
        await session.commit()
