"""SPEC §5.28.2 chat-session endpoints: session creation, `messages`, and `respond`
(the S14 `interrupt()`-based preview/approve mechanism, D-020/D-021's pattern, used
instead of SPEC's literal `calendar-preview`/`calendar-create`/`email-preview`/
`email-send`/`location-consent` endpoint list - one generic resume endpoint already
solves preview+approve atomically, proven in `learning_api.routers.sessions`).
Backed by the QAState LangGraph workflow (SPEC §5.19.2) +
`AsyncPostgresSaver` checkpointing (SPEC §5.16).
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from intellichoice_db.models.cost_reservation import SCOPE_CHAT_TURN, SUBJECT_CHAT_API
from intellichoice_db.repositories.chat import ChatSuggestionRepository
from intellichoice_db.repositories.cost_reservation import (
    CeilingReachedError,
    CostReservationRepository,
)
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_observability.langsmith_config import langsmith_correlation_metadata
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.pii_redaction import redact_free_text
from intellichoice_shared.profiles import ProfileAdapter
from intellichoice_shared.rate_limit import RateLimiter
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt, StateSnapshot
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.config import get_settings
from chat_api.dependencies import (
    get_bedrock_gateway,
    get_cost_ledger,
    get_db_session,
    get_email_rate_limiter,
    get_graph,
    get_mcp_registry,
    get_message_rate_limiter,
    get_optional_claims,
    get_profile_adapter,
    get_session_events,
)
from chat_api.graph.build import AskInput, QAGraph
from chat_api.graph.nodes import TurnContext
from chat_api.services import suggestions
from chat_api.services.checkpoint_privacy import purge_resume_writes
from chat_api.services.session_events import ChatSessionEventBus
from chat_api.services.turn_cost import TURN_RESERVATION_ESTIMATE_CENTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])

# D-345/D-346. What a caller sees when a containment guard fires. Each is a distinct
# condition with a distinct remedy, so none of them reuses another's wording - the whole
# point of AUD-C-19 was that "no approved source" was being shown for three different
# causes.
TOO_MANY_TURNS_MESSAGE = (
    "You've asked a lot of questions in a short time. Please wait a little while before "
    "asking another."
)
DAILY_CEILING_MESSAGE = (
    "The assistant has reached its daily limit and can't answer new questions right now. "
    "Please try again tomorrow, or contact your branch directly."
)
TURN_TIMED_OUT_MESSAGE = (
    "That question took too long to answer and was stopped. Please try asking it again, or "
    "more simply."
)
TURN_ALREADY_RUNNING_MESSAGE = (
    "This conversation is already working on a question. Wait for it to finish before "
    "sending another."
)


class CreateSessionResponse(BaseModel):
    chat_session_id: str


class AskMessageRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    # D-348: the client's own id for this turn, echoed back on the response and on every
    # subsequent snapshot for it. Optional, so a non-browser caller need not supply one;
    # bounded, because it is checkpointed and echoed and an unbounded string should never be
    # either. Opaque to the server - it is never parsed, compared or stored anywhere else.
    client_turn_id: str | None = Field(default=None, max_length=64)
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
    """The access hint at the API boundary.

    **`required_role` was removed here in D-351 and is deliberately not coming back without
    a decision.** It named the tier a matching document belongs to ("parent"), which tells an
    unauthenticated caller that a document restricted to that tier exists and mentions their
    terms - a disclosure produced by a probe that only runs *because* the normal pipeline
    already declined, and one measured wrong in the field (AUD-C-25/D-179 named `parent` for a
    question the public corpus answers). The tier is still selected and logged, so the probe
    stays measurable; it no longer reaches the caller.

    That leaves this model carrying one field. It is kept as a model rather than flattened to
    a string because `reason == ACCESS_REQUIRED` is now the machine-readable half, and a
    client that wants to render the hint differently should key on that, not on a nullable
    string appearing.
    """

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
    # D-348: echoed straight back so a client can tell which of its turns a payload
    # describes. All three of `MessageResponse`, `RespondResponse` and
    # `SessionSnapshotEvent` carry it, because D-058/AUD-C-14 is bidirectional - a field
    # on one and not the others gets *nulled* on every broadcast rather than failing.
    client_turn_id: str | None = None
    # D-351: why this turn ended the way it did, as a closed `TurnReason` code. The field a
    # client should branch on - `answer` is the words, and inferring the cause from
    # `escalation_recommended` + `citations` + `access_hint` (which is what a client had to do
    # before) is how three different causes came to wear one message (AUD-C-19).
    reason: str | None = None


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
    # D-348: echoed straight back so a client can tell which of its turns a payload
    # describes. All three of `MessageResponse`, `RespondResponse` and
    # `SessionSnapshotEvent` carry it, because D-058/AUD-C-14 is bidirectional - a field
    # on one and not the others gets *nulled* on every broadcast rather than failing.
    client_turn_id: str | None = None
    # D-351: why this turn ended the way it did, as a closed `TurnReason` code. The field a
    # client should branch on - `answer` is the words, and inferring the cause from
    # `escalation_recommended` + `citations` + `access_hint` (which is what a client had to do
    # before) is how three different causes came to wear one message (AUD-C-19).
    reason: str | None = None


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
    # D-348: echoed straight back so a client can tell which of its turns a payload
    # describes. All three of `MessageResponse`, `RespondResponse` and
    # `SessionSnapshotEvent` carry it, because D-058/AUD-C-14 is bidirectional - a field
    # on one and not the others gets *nulled* on every broadcast rather than failing.
    client_turn_id: str | None = None
    # D-351: why this turn ended the way it did, as a closed `TurnReason` code. The field a
    # client should branch on - `answer` is the words, and inferring the cause from
    # `escalation_recommended` + `citations` + `access_hint` (which is what a client had to do
    # before) is how three different causes came to wear one message (AUD-C-19).
    reason: str | None = None


def _publish_snapshot(events: ChatSessionEventBus, response: BaseModel) -> None:
    snapshot = SessionSnapshotEvent.model_validate(response.model_dump())
    events.publish(snapshot.chat_session_id, snapshot.model_dump(mode="json"))


def _graph_config(chat_session_id: str) -> RunnableConfig:
    """The config every `graph.ainvoke` runs under - and the one seam where a LangSmith run
    gains the id that X-Ray and every CloudWatch log line already carry (D-242).

    Without it the two observability legs never met: you could find a slow request's span
    and its logs, then had to match its LangGraph node tree by timestamp, which stops
    working the moment two students are active at once. `metadata` is what LangSmith's
    tracer reads off this config; the key is absent rather than null when nothing is
    tracing, so "no correlation" and "correlation is null" stay different states.
    """
    config: RunnableConfig = {"configurable": {"thread_id": chat_session_id}}
    correlation = langsmith_correlation_metadata()
    if correlation:
        config["metadata"] = correlation
    return config


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
) -> dict:
    """`/messages` is the one entry point that may legitimately see *no* prior state
    (a session's first message) - unlike `learning_api`'s `_get_state_values`, this
    never 404s on that case, only 409s if a task is genuinely paused (D-021 gotcha #2:
    a fresh, non-`Command` `ainvoke` on a thread with a paused task silently discards
    it instead of resuming it).

    Also the ownership gate, because this is already the one place `/messages` reads the
    checkpoint - keeping them together means a future caller cannot pick up the paused
    check and quietly leave the access check behind.

    Returns the pre-turn state values so the caller can read `bedrock_spend_cents` off
    them: that field is a running *session* total, so this turn's own cost - what D-345's
    reservation settles at - is the difference across the invoke, and this read is already
    happening.
    """
    snapshot = await graph.aget_state(_graph_config(chat_session_id))
    if not snapshot.values:
        return {}
    _assert_session_access(snapshot.values, claims)
    if _pending_task_interrupt(snapshot) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="a pending interrupt must be resolved via /respond before continuing",
        )
    return snapshot.values


def _turn_cost_cents(before: dict, result: dict) -> float:
    """This turn's spend, from the session-cumulative counter either side of the invoke."""
    spent = float(result.get("bedrock_spend_cents") or 0.0) - float(
        before.get("bedrock_spend_cents") or 0.0
    )
    return max(spent, 0.0)


def _turn_context(
    *,
    claims: TokenClaims | None,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
    bedrock_gateway: BedrockGateway,
    mcp_registry: McpToolRegistry,
    rate_limiter: RateLimiter,
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


def _caller_key(claims: TokenClaims | None, request: Request) -> str:
    """Who a per-caller limit counts against - the same derivation
    `nodes.prepare_admin_escalation` uses for the escalation cap, so a signed-in caller is
    one key wherever they connect from and an anonymous one is their egress IP. Never
    stored raw: `PostgresRateLimiter` HMACs it (see `rate_limit_events`' docstring).
    """
    if claims is not None:
        return claims.sub
    return request.client.host if request.client else "anonymous"


async def _reject_if_over_caller_limit(limiter: RateLimiter, key: str) -> None:
    if not await limiter.allow(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY_TURNS_MESSAGE
        )


async def _claim_turn(db: AsyncSession, chat_session_id: str) -> None:
    """One turn at a time per thread, enforced across replicas (D-346).

    `_reject_if_paused` reads the checkpoint and *then* invokes, with nothing in between:
    two simultaneous POSTs on one thread both saw "not paused" and both ran, and a
    LangGraph thread is not safe to invoke concurrently. An `asyncio.Lock` would only fix
    the single-task case, and the same autoscaling that makes D-344 necessary makes that
    the wrong shape.

    A **try**-lock, not a blocking one: with D-346's 50s deadline, queueing behind an
    in-flight turn could make a second tab wait almost a minute for a request it will then
    have to repeat. An immediate, honest 409 is better. The lock is transaction-scoped and
    this session commits at dependency teardown, so it covers the whole turn and releases
    with the request even if it crashes.
    """
    acquired = await db.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtext(:key))"),
        {"key": f"chat_turn:{chat_session_id}"},
    )
    if not acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=TURN_ALREADY_RUNNING_MESSAGE
        )


@asynccontextmanager
async def _reserved_turn(ledger: CostReservationRepository) -> AsyncIterator[list[float]]:
    """Charge this turn's worst case against the per-day ceiling, then settle the real cost.

    Yields a one-element list the caller writes the turn's actual cost into. A list rather
    than a return value because the settle has to happen on the way out of the `with`,
    including when the body raises - a timed-out or failed turn still spent whatever it
    spent before it stopped.

    Never settling is safe by construction: the reservation stays charged at its estimate,
    which over-counts. That is the direction a spend ceiling should fail in.
    """
    settings = get_settings()
    try:
        reservation = await ledger.reserve(
            scope=SCOPE_CHAT_TURN,
            subject_external_id=SUBJECT_CHAT_API,
            estimate_cents=TURN_RESERVATION_ESTIMATE_CENTS,
            ceiling_cents=settings.chat_daily_spend_ceiling_cents,
        )
    except CeilingReachedError as exc:
        logger.warning(
            "chat_daily_spend_ceiling_reached",
            extra={"spend_cents": exc.spend_cents, "ceiling_cents": exc.ceiling_cents},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=DAILY_CEILING_MESSAGE
        ) from exc

    actual: list[float] = [0.0]
    try:
        yield actual
    finally:
        await ledger.settle(reservation.reservation_id, actual[0])


async def _run_turn(
    graph: QAGraph,
    payload: "AskInput | Command | None",
    *,
    chat_session_id: str,
    ctx: TurnContext,
) -> dict:
    """`graph.ainvoke` under the outer deadline SPEC §5.25.1's per-call timeouts never gave
    the request as a whole (D-346).

    Six sequential gateway calls, each retrying up to three times at 20s, put the worst case
    near six minutes - well past CloudFront's 60s origin read timeout, so the client was
    already gone while the backend kept working and kept spending. Cancelling mid-turn
    leaves the last completed checkpoint intact, which is the same state a crash leaves and
    a state LangGraph is built to resume from.
    """
    try:
        async with asyncio.timeout(get_settings().chat_turn_deadline_s):
            return await graph.ainvoke(
                payload, config=_graph_config(chat_session_id), context=ctx
            )
    except TimeoutError as exc:
        logger.warning("chat_turn_deadline_exceeded", extra={"thread_id": chat_session_id})
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=TURN_TIMED_OUT_MESSAGE
        ) from exc


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
    rate_limiter: Annotated[RateLimiter, Depends(get_email_rate_limiter)],
    message_limiter: Annotated[RateLimiter, Depends(get_message_rate_limiter)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
) -> MessageResponse:
    # D-345: the containment guards run in cheapest-first order, and this is the endpoint
    # they belong on. `POST /chat/sessions` was the tempting place - it is the
    # unauthenticated, unpersisted one - but a session id costs nothing until a message
    # spends against it, so limiting *creation* would not have bounded a single cent. An
    # abuser reusing one id per message would have walked straight past it.
    await _reject_if_over_caller_limit(message_limiter, _caller_key(claims, request))
    await _claim_turn(db, chat_session_id)
    before = await _reject_if_paused(graph, chat_session_id, claims)
    # AUD-C-24 (D-072's "How to apply" clause): the caller's typed text is redacted here,
    # at the request boundary - the only place free text enters this graph - before it
    # reaches `TurnContext`, the checkpointed `QAState`, or any Bedrock payload
    # (`standalone_query`, `RerankPayload.query`, `RagAnswerPayload.query`,
    # `CalendarExtractionPayload.query`). Same seam and same floor as learning-api's
    # `send_chat_message`; escalation forwards the redacted text too, which is consistent
    # with D-164 (escalation already carries no reply channel, so a stripped email
    # address was never actionable there).
    query = redact_free_text(body.query)
    ctx = _turn_context(
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        bedrock_gateway=bedrock_gateway,
        mcp_registry=mcp_registry,
        rate_limiter=rate_limiter,
        query=query,
        client_ip=request.client.host if request.client else None,
    )
    async with _reserved_turn(cost_ledger) as spent:
        result = await _run_turn(
            graph,
            AskInput(
                session_id=chat_session_id,
                query=query,
                escalate=body.escalate,
                client_turn_id=body.client_turn_id,
            ),
            chat_session_id=chat_session_id,
            ctx=ctx,
        )
        spent[0] = _turn_cost_cents(before, result)

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
        access_hint=(
            AccessHintResponse(message=access_hint["message"]) if access_hint else None
        ),
        suggested_followups=await _suggested_followups(db, result, citations),
        ics_content=result.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(pending, result) if pending is not None else None
        ),
        client_turn_id=result.get("client_turn_id"),
        reason=result.get("reason"),
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
    rate_limiter: Annotated[RateLimiter, Depends(get_email_rate_limiter)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
) -> RespondResponse:
    """Resumes whichever `interrupt()` is currently paused on this thread (SPEC §5.1.4)
    - admin-escalation email approval, the Google Calendar/`.ics`/cancel choice, or
    branch-locator location consent. `body.interrupt_type` must match the actually
    -pending interrupt so a stale or mismatched client request fails clearly instead of
    silently resuming the wrong node.
    """
    await _claim_turn(db, chat_session_id)
    snapshot = await graph.aget_state(_graph_config(chat_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found"
        )
    snapshot_values = snapshot.values

    # D-346: **before** anything that describes the thread's state. This check used to sit
    # below both 409s, so a caller holding only a session id learned that the session
    # existed, that an interrupt was pending, and - from the mismatch message - *which* one,
    # all before being told the thread was not theirs.
    #
    # The 404 above still runs first, and that is a deliberate limit rather than a claim of
    # full indistinguishability: an unknown id 404s and a foreign one 403s, so the two
    # remain tellable apart. `_assert_session_access`'s own docstring chose the 403, both
    # `/stream` and `/messages` already answer that way, and the ids are uuid4 - so the
    # enumeration this leaks is not a practical one. What was practical, and is now closed,
    # is reading a stranger's *pending approval type* out of a 409 detail string.
    _assert_session_access(snapshot_values, claims)

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
    async with _reserved_turn(cost_ledger) as spent:
        result = await _run_turn(
            graph,
            Command(resume=resume_value),
            chat_session_id=chat_session_id,
            ctx=ctx,
        )
        spent[0] = _turn_cost_cents(snapshot_values, result)

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
        access_hint=(
            AccessHintResponse(message=access_hint["message"]) if access_hint else None
        ),
        suggested_followups=await _suggested_followups(db, result, citations),
        ics_content=result.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(next_pending, result)
            if next_pending is not None
            else None
        ),
        client_turn_id=result.get("client_turn_id"),
        reason=result.get("reason"),
    )
    _publish_snapshot(events, response)
    return response
