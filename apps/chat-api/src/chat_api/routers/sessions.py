"""SPEC §5.28.2 chat-session endpoints: session creation, `messages`, and `respond`
(the S14 `interrupt()`-based preview/approve mechanism, D-020/D-021's pattern, used
instead of SPEC's literal `calendar-preview`/`calendar-create`/`email-preview`/
`email-send`/`location-consent` endpoint list - one generic resume endpoint already
solves preview+approve atomically, proven in `learning_api.routers.sessions`).
Backed by the QAState LangGraph workflow (SPEC §5.19.2) +
`AsyncPostgresSaver` checkpointing (SPEC §5.16).
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from intellichoice_shared.rate_limit import InMemoryRateLimiter
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt, StateSnapshot
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.config import get_settings
from chat_api.dependencies import (
    get_bedrock_gateway,
    get_db_session,
    get_email_rate_limiter,
    get_graph,
    get_mcp_registry,
    get_optional_claims,
    get_profile_adapter,
    get_session_events,
)
from chat_api.graph.build import AskInput, QAGraph
from chat_api.graph.nodes import TurnContext
from chat_api.services import suggestions
from chat_api.services.checkpoint_privacy import purge_resume_writes
from chat_api.services.session_events import ChatSessionEventBus

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])


class CreateSessionResponse(BaseModel):
    chat_session_id: str


class AskMessageRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    # D-164: the caller is forwarding a question it already asked to a human, not asking a
    # new one. Set by chat-web's "Ask an administrator" button on a no-source refusal,
    # carrying that refusal's own question text back. The turn then skips `scope_guard`
    # and goes straight to the SPEC §5.24 escalation path - see
    # `chat_api.graph.build._route_after_resolve_role` for why bypassing the scope guard
    # is safe here and what it deliberately does not bypass.
    escalate: bool = False


class CitationResponse(BaseModel):
    document_title: str
    document_version: int
    page_number: int | None = None
    section_title: str | None = None
    source_reference: str
    supporting_quote_hash: str


class AccessHintResponse(BaseModel):
    """SPEC §18-C3: mirrors `chat_api.services.role_access.AccessHint` at the API
    boundary.
    """

    required_role: str
    message: str


class MessageResponse(BaseModel):
    chat_session_id: str
    scope: str | None = None
    intent: str | None = None
    answer: str | None = None
    citations: list[CitationResponse] = []
    confidence: float | None = None
    missing_information: str | None = None
    escalation_recommended: bool = False
    access_hint: AccessHintResponse | None = None
    suggested_followups: list[str] = []
    ics_content: str | None = None
    pending_interrupt: dict | None = None


class EmailApprovalChoice(BaseModel):
    interrupt_type: Literal["email_approval"] = "email_approval"
    approved: bool


class CalendarActionChoice(BaseModel):
    interrupt_type: Literal["calendar_action"] = "calendar_action"
    choice: Literal["google", "ics", "cancel"]


class LocationConsentChoice(BaseModel):
    """SPEC §5.1.3/§5.1.4: the location itself (whichever single form the caller
    supplies) travels only in this resume payload, never in a prior `/messages` call or
    any checkpointed field - see `chat_api.graph.nodes.branch_locator_consent`'s own
    docstring for why. All location fields are optional here (unlike `GeocodeQuery`,
    which this becomes once one is present): `approved=True` with none set is a valid,
    meaningful case (browser geolocation denied, or the user just clicked "yes" with
    nothing typed yet) that routes to the SPEC §5.22 "ask for ZIP/city" fallback rather
    than failing request validation.
    """

    interrupt_type: Literal["location_consent"] = "location_consent"
    approved: bool
    zip_code: str | None = None
    city: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None


RespondRequest = Annotated[
    EmailApprovalChoice | CalendarActionChoice | LocationConsentChoice,
    Field(discriminator="interrupt_type"),
]


class RespondResponse(BaseModel):
    # AUD-C-15's sibling in the contract layer, AUD-C-14: these two were missing, and because
    # `_publish_snapshot` re-validates a `SessionSnapshotEvent` from `response.model_dump()`,
    # their absence did not fail - it *nulled* `scope`/`intent` for every connected client on
    # every broadcast after a `/respond`. Exactly the class D-058 was written to prevent
    # ("any field added to `MessageResponse` must also be added to `_initial_snapshot`"), in
    # the one direction that decision did not name: a *sibling response model* omitting a
    # field the shared snapshot carries. The rule is bidirectional, so keep all three of
    # `MessageResponse`, `RespondResponse` and `SessionSnapshotEvent` in step.
    chat_session_id: str
    scope: str | None = None
    intent: str | None = None
    answer: str | None = None
    citations: list[CitationResponse] = []
    confidence: float | None = None
    missing_information: str | None = None
    escalation_recommended: bool = False
    access_hint: AccessHintResponse | None = None
    suggested_followups: list[str] = []
    ics_content: str | None = None
    pending_interrupt: dict | None = None


class SessionSnapshotEvent(BaseModel):
    """The SSE payload - one canonical "current turn" shape shared by `/messages`'s and
    `/respond`'s post-turn broadcast and `/stream`'s initial snapshot on (re)connect,
    mirroring `learning_api.routers.sessions.SessionSnapshotEvent`.
    """

    event: Literal["session_update"] = "session_update"
    chat_session_id: str
    scope: str | None = None
    intent: str | None = None
    answer: str | None = None
    citations: list[CitationResponse] = []
    confidence: float | None = None
    missing_information: str | None = None
    escalation_recommended: bool = False
    access_hint: AccessHintResponse | None = None
    suggested_followups: list[str] = []
    ics_content: str | None = None
    pending_interrupt: dict | None = None


def _publish_snapshot(events: ChatSessionEventBus, response: BaseModel) -> None:
    snapshot = SessionSnapshotEvent.model_validate(response.model_dump())
    events.publish(snapshot.chat_session_id, snapshot.model_dump(mode="json"))


def _graph_config(chat_session_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": chat_session_id}}


def _pending_task_interrupt(snapshot: StateSnapshot) -> Interrupt | None:
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0]
    return None


def _result_interrupt(result: dict) -> Interrupt | None:
    interrupts = result.get("__interrupt__")
    return interrupts[0] if interrupts else None


async def _suggested_followups(
    db: AsyncSession, result: dict, citations: list[CitationResponse]
) -> list[str]:
    """SPEC §18-C3: deterministic, category-based follow-up chips for a just-produced
    answer. Empty whenever this turn paused (a pending interrupt has no "answer" for the
    caller to follow up on yet) or genuinely produced no answer at all.
    """
    if not result.get("answer") or _result_interrupt(result) is not None:
        return []
    active_suggestions = await ChatSuggestionRepository(db).list_active()
    category = suggestions.category_for_answer(
        result.get("intent"), [c.source_reference for c in citations]
    )
    return suggestions.followups_for_answer(
        active_suggestions,
        user_role=result.get("user_role", "public"),
        category=category,
        asked_query=result.get("query") or "",
    )


def _pending_interrupt_preview(pending: Interrupt, state: dict) -> dict:
    """Unlike `learning_api`'s `_pending_interrupt_response`, this never needs a live
    MySQL lookup - `email_draft`/`calendar_event` are checkpointed directly in `QAState`
    (no D-020 indirection needed, since neither carries MySQL-sourced PII; see
    `QAState`'s own docstring), so the preview is just what's already in `state`.
    """
    interrupt_type = pending.value.get("type")
    if interrupt_type == "email_approval":
        draft = state.get("email_draft") or {}
        return {
            "interrupt_type": interrupt_type,
            "email_subject": draft.get("subject"),
            "email_body": draft.get("body"),
        }
    if interrupt_type == "calendar_action":
        return {
            "interrupt_type": interrupt_type,
            "calendar_event": state.get("calendar_event"),
        }
    if interrupt_type == "location_consent":
        return {
            "interrupt_type": interrupt_type,
            "notice": pending.value.get("notice"),
        }
    return {"interrupt_type": interrupt_type}


def _assert_session_access(snapshot_values: dict, claims: TokenClaims | None) -> None:
    """AUD-C-01 (S40, D-107): the thread-ownership check `/respond` and `/stream` perform,
    applied to `/messages` too.

    `/messages` had none. Verified live on staging before the fix: an **unauthenticated**
    caller continued a tutor's thread, received the tutor's answer and citation back, and
    resolved its interrupt - all 200. Locally, tutor-audience text reached the anonymous
    response verbatim.

    An anonymous caller on an owned session is refused rather than served a public-scope
    answer. That looks harsher than SPEC §5.19.1's anonymous-is-first-class rule, but the
    session is someone else's: `/respond` and `/stream` already answer it exactly this way,
    and a new anonymous session is one `POST /chat/sessions` away.
    """
    owner = snapshot_values.get("user_external_id")
    if owner is not None and (claims is None or claims.sub != owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="token does not match this session"
        )


async def _reject_if_paused(
    graph: QAGraph, chat_session_id: str, claims: TokenClaims | None
) -> None:
    """`/messages` is the one entry point that may legitimately see *no* prior state
    (a session's first message) - unlike `learning_api`'s `_get_state_values`, this
    never 404s on that case, only 409s if a task is genuinely paused (D-021 gotcha #2:
    a fresh, non-`Command` `ainvoke` on a thread with a paused task silently discards
    it instead of resuming it).

    Also the ownership gate, because this is already the one place `/messages` reads the
    checkpoint - keeping them together means a future caller cannot pick up the paused
    check and quietly leave the access check behind.
    """
    snapshot = await graph.aget_state(_graph_config(chat_session_id))
    if not snapshot.values:
        return
    _assert_session_access(snapshot.values, claims)
    if _pending_task_interrupt(snapshot) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="a pending interrupt must be resolved via /respond before continuing",
        )


def _turn_context(
    *,
    claims: TokenClaims | None,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
    bedrock_gateway: BedrockGateway,
    mcp_registry: McpToolRegistry,
    rate_limiter: InMemoryRateLimiter,
    query: str | None = None,
    client_ip: str | None = None,
) -> TurnContext:
    settings = get_settings()
    return TurnContext(
        claims=claims,
        profile_adapter=profile_adapter,
        rag_repo=RagRepository(db),
        bedrock_gateway=bedrock_gateway,
        interrupt_repo=InterruptApprovalRepository(db),
        mcp_registry=mcp_registry,
        mcp_call_repo=McpToolCallRepository(db),
        org_event_repo=OrgEventRepository(db),
        rate_limiter=rate_limiter,
        admin_escalation_email=settings.admin_escalation_email,
        query=query,
        candidate_limit=settings.retrieval_candidate_limit,
        top_k=settings.retrieval_top_k,
        confidence_threshold=settings.groundedness_confidence_threshold,
        access_probe_max_distance=settings.access_probe_max_distance,
        min_relevance_score=settings.retrieval_min_relevance_score,
        client_ip=client_ip,
    )


@router.post("", response_model=CreateSessionResponse)
async def create_session(
    claims: Annotated[TokenClaims | None, Depends(get_optional_claims)],
) -> CreateSessionResponse:
    del claims  # SPEC §5.19.1: anonymous access is valid; role is resolved per message
    return CreateSessionResponse(chat_session_id=str(uuid.uuid4()))


@router.post("/{chat_session_id}/messages", response_model=MessageResponse)
async def post_message(
    chat_session_id: str,
    body: AskMessageRequest,
    request: Request,
    claims: Annotated[TokenClaims | None, Depends(get_optional_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    rate_limiter: Annotated[InMemoryRateLimiter, Depends(get_email_rate_limiter)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
) -> MessageResponse:
    await _reject_if_paused(graph, chat_session_id, claims)
    ctx = _turn_context(
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        bedrock_gateway=bedrock_gateway,
        mcp_registry=mcp_registry,
        rate_limiter=rate_limiter,
        query=body.query,
        client_ip=request.client.host if request.client else None,
    )
    result = await graph.ainvoke(
        AskInput(session_id=chat_session_id, query=body.query, escalate=body.escalate),
        config=_graph_config(chat_session_id),
        context=ctx,
    )

    pending = _result_interrupt(result)
    citations = [CitationResponse(**c) for c in result.get("citations") or []]
    access_hint = result.get("access_hint")
    response = MessageResponse(
        chat_session_id=chat_session_id,
        scope=result.get("scope"),
        intent=result.get("intent"),
        answer=result.get("answer"),
        citations=citations,
        confidence=result.get("confidence"),
        missing_information=result.get("missing_information"),
        escalation_recommended=result.get("escalation_recommended", False),
        access_hint=AccessHintResponse(**access_hint) if access_hint else None,
        suggested_followups=await _suggested_followups(db, result, citations),
        ics_content=result.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(pending, result) if pending is not None else None
        ),
    )
    _publish_snapshot(events, response)
    return response


@router.post("/{chat_session_id}/respond", response_model=RespondResponse)
async def respond_to_interrupt(
    chat_session_id: str,
    body: RespondRequest,
    request: Request,
    claims: Annotated[TokenClaims | None, Depends(get_optional_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    rate_limiter: Annotated[InMemoryRateLimiter, Depends(get_email_rate_limiter)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
) -> RespondResponse:
    """Resumes whichever `interrupt()` is currently paused on this thread (SPEC §5.1.4)
    - admin-escalation email approval, the Google Calendar/`.ics`/cancel choice, or
    branch-locator location consent. `body.interrupt_type` must match the actually
    -pending interrupt so a stale or mismatched client request fails clearly instead of
    silently resuming the wrong node.
    """
    snapshot = await graph.aget_state(_graph_config(chat_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found"
        )
    snapshot_values = snapshot.values
    pending = _pending_task_interrupt(snapshot)
    if pending is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="no interrupt is pending"
        )
    if pending.value.get("type") != body.interrupt_type:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"pending interrupt is {pending.value.get('type')!r}, not "
            f"{body.interrupt_type!r}",
        )

    _assert_session_access(snapshot_values, claims)

    if isinstance(body, EmailApprovalChoice):
        resume_value: object = {"approved": body.approved}
    elif isinstance(body, CalendarActionChoice):
        resume_value = {"choice": body.choice}
    else:
        resume_value = {
            "approved": body.approved,
            "zip_code": body.zip_code,
            "city": body.city,
            "address": body.address,
            "latitude": body.latitude,
            "longitude": body.longitude,
        }

    ctx = _turn_context(
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        bedrock_gateway=bedrock_gateway,
        mcp_registry=mcp_registry,
        rate_limiter=rate_limiter,
        client_ip=request.client.host if request.client else None,
    )
    result = await graph.ainvoke(
        Command(resume=resume_value),
        config=_graph_config(chat_session_id),
        context=ctx,
    )

    if isinstance(body, LocationConsentChoice):
        # AUD-C-03: the resume payload above is the only place the caller's precise
        # location exists, and the saver has just persisted it to `checkpoint_writes`
        # (`__resume__`). The node is done, so remove it - see
        # `services/checkpoint_privacy.py` for the full reasoning. Committed with the
        # rest of this request's session by `get_db_session`.
        await purge_resume_writes(db, chat_session_id)

    next_pending = _result_interrupt(result)
    citations = [CitationResponse(**c) for c in result.get("citations") or []]
    access_hint = result.get("access_hint")
    response = RespondResponse(
        chat_session_id=chat_session_id,
        scope=result.get("scope"),
        intent=result.get("intent"),
        answer=result.get("answer"),
        citations=citations,
        confidence=result.get("confidence"),
        missing_information=result.get("missing_information"),
        escalation_recommended=result.get("escalation_recommended", False),
        access_hint=AccessHintResponse(**access_hint) if access_hint else None,
        suggested_followups=await _suggested_followups(db, result, citations),
        ics_content=result.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(next_pending, result)
            if next_pending is not None
            else None
        ),
    )
    _publish_snapshot(events, response)
    return response
