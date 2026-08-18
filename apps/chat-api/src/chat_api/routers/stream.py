"""SSE endpoint for the Q&A app, mirroring `learning_api.routers.stream` (SPEC
§5.14.1-style progress push, applied to `chat-api`'s single-turn-per-request graph).

Unlike `learning_api`'s stream, a token here is optional (`?token=`) - SPEC §5.19.1
allows fully anonymous Q&A sessions, so there is nothing to authenticate for a session
nobody ever attached an identity to. A session that *was* created/used by an
authenticated caller (`state["user_external_id"]` is set) still requires a matching
token, the same access check `learning_api` always enforces.
"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from intellichoice_adapters.fake_auth import TokenError
from intellichoice_shared.auth import Audience, account_refusal_reason
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.dependencies import get_graph, get_session_events, get_token_verifier
from chat_api.graph.build import QAGraph
from chat_api.services.session_events import ChatSessionEventBus

from .sessions import (
    AccessHintResponse,
    CitationResponse,
    SessionSnapshotEvent,
    _graph_config,
    _pending_interrupt_preview,
    _pending_task_interrupt,
    _suggested_followups,
)

router = APIRouter(prefix="/chat/sessions", tags=["chat-sessions"])

# D-404: the two frame shapes this endpoint emits, named and therefore testable.
#
# They were inline f-strings inside `event_stream`, a closure inside the handler - unreachable
# from a test, because `/stream` never closes and `TestClient.stream()` hangs against it (D-033,
# and `test_chat_endpoints`'s docstring says so). The first attempt at testing this change drove
# the endpoint over HTTP anyway and hung for seven minutes, which is what named constants avoid.
#
# **`data_frame` must stay unnamed and `KEEPALIVE_FRAME` must stay named.** `EventSource.onmessage`
# receives only *unnamed* events, so naming the keepalive is safe precisely because snapshots are
# not named; if snapshots ever gained an `event:` line, every client would silently stop receiving
# them - a reloaded chat tab's "Thinking…" would never resolve.
KEEPALIVE_FRAME = "event: keepalive\ndata: {}\n\n"


def data_frame(payload: str) -> str:
    """An unnamed SSE data frame - what `onmessage` receives."""
    return f"data: {payload}\n\n"


KEEPALIVE_INTERVAL_S = 15.0


async def _initial_snapshot(
    chat_session_id: str, graph: QAGraph, token: str | None, db: AsyncSession
) -> SessionSnapshotEvent:
    claims = None
    if token is not None:
        # Repeated rather than inherited: `EventSource` cannot set a header, so this path
        # verifies its own `?token=` and never passes through `get_optional_claims`
        # (AUD-X-02).
        try:
            claims = get_token_verifier().verify(token, Audience.CHAT)
        except TokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
            ) from exc
        refusal = account_refusal_reason(claims)
        if refusal is not None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refusal)

    snapshot = await graph.aget_state(_graph_config(chat_session_id))
    if not snapshot.values:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found")
    state = snapshot.values
    owner = state.get("user_external_id")
    if owner is not None and (claims is None or claims.sub != owner):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="token does not match this session"
        )

    pending = _pending_task_interrupt(snapshot)
    citations = [CitationResponse(**c) for c in state.get("citations") or []]
    access_hint = state.get("access_hint")
    # `state` is `aget_state().values` (checkpointed QAState), which has no
    # `__interrupt__` key - `_suggested_followups`'s own pending-interrupt check would
    # never see one here, so this call site guards on `pending` (from
    # `_pending_task_interrupt`, the correct mechanism for a *checkpointed* snapshot)
    # instead, matching `/messages`/`/respond`'s own "no follow-ups while paused" rule.
    followups = [] if pending is not None else await _suggested_followups(db, state, citations)
    return SessionSnapshotEvent(
        chat_session_id=chat_session_id,
        scope=state.get("scope"),
        intent=state.get("intent"),
        answer=state.get("answer"),
        citations=citations,
        confidence=state.get("confidence"),
        missing_information=state.get("missing_information"),
        escalation_recommended=state.get("escalation_recommended", False),
        # D-351: built field by field rather than `**access_hint`, because the state dict
        # carries `required_role` and this is the boundary that must not pass it on.
        access_hint=(AccessHintResponse(message=access_hint["message"]) if access_hint else None),
        suggested_followups=followups,
        ics_content=state.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(pending, state) if pending is not None else None
        ),
        # D-348: read off the checkpoint, which is what makes the reconnect case work at
        # all - after a reload the browser has rebuilt its transcript from storage and this
        # is the only thing that says which bubble this snapshot belongs under.
        client_turn_id=state.get("client_turn_id"),
        reason=state.get("reason"),
    )


@router.get("/{chat_session_id}/stream")
async def stream_session(
    chat_session_id: str,
    request: Request,
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    token: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    # AUD-F-36 (found on learning-api's identical endpoint): subscribe BEFORE the
    # initial-snapshot read, so an action completing during the read lands in the queue
    # and corrects the initial frame instead of publishing to nobody and leaving this
    # stream permanently stale. The window here is smaller than learning-api's (no
    # Bedrock call on connect) but `_suggested_followups` does real DB work inside it.
    queue = events.subscribe(chat_session_id)
    try:
        # D-348: a short-lived session from the factory rather than `Depends(get_db_session)`.
        # A dependency-with-yield is torn down *after* the response finishes, and an SSE
        # response never finishes - so the request's session, and the transaction
        # `_suggested_followups` autobegins inside it, stayed checked out and
        # idle-in-transaction for as long as the browser tab was open. The pool is 10 + 10
        # overflow, so **20 concurrent SSE connections exhausted it** and every other request
        # on that replica blocked. The keep-alive loop below needs no database at all.
        session_factory = request.app.state.db_session_factory
        async with session_factory() as db:
            initial = await _initial_snapshot(chat_session_id, graph, token, db)
    except BaseException:
        events.unsubscribe(chat_session_id, queue)
        raise

    async def event_stream():
        try:
            yield data_frame(initial.model_dump_json())
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL_S)
                    yield data_frame(json.dumps(event))
                except TimeoutError:
                    yield KEEPALIVE_FRAME
        finally:
            events.unsubscribe(chat_session_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
