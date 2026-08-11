from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import HTTPException, Request, status
from intellichoice_adapters.fake_auth import JwtTokenVerifier, TokenError
from intellichoice_db.repositories.cost_reservation import CostReservationRepository
from intellichoice_shared.auth import Audience, TokenClaims, account_refusal_reason
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.email import EmailTransport
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.config import get_settings
from learning_api.graph.build import LearningGraph
from learning_api.services.consolidation_scheduler import ConsolidationScheduler
from learning_api.services.hint_personalization_scheduler import (
    BackgroundHintPersonalizationScheduler,
)
from learning_api.services.session_events import SessionEventBus
from learning_api.services.stage_narrative_scheduler import (
    BackgroundStudyNarrativeScheduler,
)


@lru_cache
def get_token_verifier() -> JwtTokenVerifier:
    return JwtTokenVerifier(secret=get_settings().jwt_signing_secret)


def get_profile_adapter(request: Request) -> ProfileAdapter:
    return request.app.state.profile_adapter


def get_email_transport(request: Request) -> EmailTransport:
    return request.app.state.email_transport


def get_mcp_registry(request: Request) -> McpToolRegistry:
    return request.app.state.mcp_registry


def get_bedrock_gateway(request: Request) -> BedrockGateway:
    return request.app.state.bedrock_gateway


def get_cost_ledger(request: Request) -> CostReservationRepository:
    """AUD-X-08's spend ledger. Built from the session *factory*, not from
    `get_db_session`: a reservation has to commit before the model call returns, and the
    request session does not commit until dependency teardown, after the response.
    """
    return CostReservationRepository(request.app.state.db_session_factory)


def get_consolidation_scheduler(request: Request) -> ConsolidationScheduler:
    """D-208. Bound to the session *factory*, exactly like `get_cost_ledger` above and for
    the same reason: the work outlives the request that scheduled it, so it cannot hold
    the request's session.
    """
    return request.app.state.consolidation_scheduler


def get_study_narrative_scheduler(
    request: Request,
) -> "BackgroundStudyNarrativeScheduler | None":
    """D-217. `None` under the mock provider, where study-transition narratives fire
    inline in the graph node (nothing to defer); a real scheduler under real Bedrock,
    where a ~1.5s narrative call would otherwise block the answer response.
    """
    return request.app.state.study_narrative_scheduler


def get_hint_personalization_scheduler(
    request: Request,
) -> "BackgroundHintPersonalizationScheduler | None":
    """D-272. `None` under the mock provider, where hint personalization stays inline in
    the graph node (the mock returns in microseconds, so there is nothing to defer and every
    existing test still sees the personalized hint on the turn that asked for it).
    """
    return request.app.state.hint_personalization_scheduler


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
    """Signature/expiry/audience, then SPEC §5.1.2's account and consent state.

    AUD-X-02 (S40, D-107): the second half did not exist. A token with
    `account_status="suspended"`, `consent_status="revoked"`,
    `parental_consent_verified=False` and `student_age_band="under_13"` behaved
    identically to a consented one on **all 18 learning routes** - this app requires auth
    everywhere, so this one function is the whole enforcement surface. 403 rather than
    401: the token is genuine, the account may not use the product.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token"
        )
    token = auth_header.split(" ", 1)[1]
    try:
        claims = get_token_verifier().verify(token, Audience.LEARNING)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
        ) from exc
    refusal = account_refusal_reason(claims)
    if refusal is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refusal)
    return claims
