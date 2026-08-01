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

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from intellichoice_adapters.fake_auth import TokenError
from intellichoice_shared.auth import Audience, account_refusal_reason
from sqlalchemy.ext.asyncio import AsyncSession

from chat_api.dependencies import get_db_session, get_graph, get_session_events, get_token_verifier
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="chat session not found"
        )
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
        access_hint=AccessHintResponse(**access_hint) if access_hint else None,
        suggested_followups=followups,
        ics_content=state.get("ics_content"),
        pending_interrupt=(
            _pending_interrupt_preview(pending, state) if pending is not None else None
        ),
    )


@router.get("/{chat_session_id}/stream")
async def stream_session(
    chat_session_id: str,
    events: Annotated[ChatSessionEventBus, Depends(get_session_events)],
    graph: Annotated[QAGraph, Depends(get_graph)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    token: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    # AUD-F-36 (found on learning-api's identical endpoint): subscribe BEFORE the
    # initial-snapshot read, so an action completing during the read lands in the queue
    # and corrects the initial frame instead of publishing to nobody and leaving this
    # stream permanently stale. The window here is smaller than learning-api's (no
    # Bedrock call on connect) but `_suggested_followups` does real DB work inside it.
    queue = events.subscribe(chat_session_id)
    try:
        initial = await _initial_snapshot(chat_session_id, graph, token, db)
    except BaseException:
        events.unsubscribe(chat_session_id, queue)
        raise

    async def event_stream():
        try:
            yield f"data: {initial.model_dump_json()}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_INTERVAL_S)
                    yield f"data: {json.dumps(event)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            events.unsubscribe(chat_session_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
