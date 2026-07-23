"""SPEC §5.14.1 SSE endpoint - the browser's single subscription for real-time session
progress (S11). One `ainvoke` per HTTP action already runs to completion synchronously
(`routers/sessions.py`), so there is no long-running graph execution to stream mid-turn;
this instead pushes the resulting snapshot every time an action completes, sourced from
`services/session_events.py`'s in-process pub/sub. On (re)connect the current snapshot is
read straight from the `AsyncPostgresSaver` checkpoint before anything is replayed, which
is what makes a page refresh restore exact position - no different from `/resume`, just
pushed instead of polled.

The browser's native `EventSource` client can't set custom headers, so the bearer token
travels as `?token=` instead of `Authorization` (documented trade-off, D-032) - this is
also what gives the "browser client with auto-reconnect" requirement for free, since
`EventSource` reconnects on its own using this same URL.
"""

import asyncio
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from intellichoice_adapters.fake_auth import TokenError
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_shared.auth import Audience
from intellichoice_shared.bedrock import BedrockGateway, StageNarrativePayload
from intellichoice_shared.profiles import ProfileAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.authorization import resolve_target_student
from learning_api.dependencies import (
    get_bedrock_gateway,
    get_db_session,
    get_graph,
    get_profile_adapter,
    get_session_events,
    get_token_verifier,
)
from learning_api.graph.build import LearningGraph
from learning_api.services import stage_narrative
from learning_api.services.session_events import SessionEventBus

from .sessions import (
    LearningGainResponse,
    SessionSnapshotEvent,
    _graph_config,
    _items_response,
    _pending_interrupt_response,
    _pending_task_interrupt,
)

router = APIRouter(prefix="/learning/sessions", tags=["learning-sessions"])

KEEPALIVE_INTERVAL_S = 15.0


async def _maybe_fire_pre_intro(
    *,
    learning_session_id: str,
    state: dict,
    db: AsyncSession,
    profile_adapter: ProfileAdapter,
    bedrock_gateway: BedrockGateway,
) -> tuple[str | None, list[str]]:
    """S26 (plan §18-L7): `pre_intro` fires on first SSE connect to a session, not from
    a graph turn - `stage_narrative.generate_stage_narrative`'s own idempotency check
    (a `stage_transitions` row already existing for this session's `pre_intro`) bounds
    this to exactly one real Bedrock call regardless of how many times a student
    reconnects or refreshes. Its cost is recorded on that row's own `cost_cents`, not
    folded into the checkpoint's `bedrock_spend_cents` total, since this never touches
    the graph (same "own audit trail, not the checkpoint" posture D-073 already
    established for chat's out-of-band spend).
    """
    student_external_id = state.get("student_external_id")
    if student_external_id is None:
        return None, []
    profile = await profile_adapter.get_student_profile(student_external_id)
    if profile is None:
        return None, []
    result = await stage_narrative.generate_stage_narrative(
        gateway=bedrock_gateway,
        repo=StageTransitionRepository(db),
        student_external_id=student_external_id,
        learning_session_id=learning_session_id,
        payload=StageNarrativePayload(
            stage="pre_intro",
            grade=profile.grade,
            attendance_status=state.get("attendance_status"),
        ),
    )
    return result.narrative_text, result.evidence_summary


async def _initial_snapshot(
    learning_session_id: str,
    graph: LearningGraph,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
    bedrock_gateway: BedrockGateway,
    token: str,
) -> SessionSnapshotEvent:
    try:
        claims = get_token_verifier().verify(token, Audience.LEARNING)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
        ) from exc

    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
    state = snapshot.values
    if state.get("student_external_id") is not None:
        await resolve_target_student(claims, state["student_external_id"], profile_adapter)
    elif claims.sub != state.get("user_external_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="token does not match this session"
        )

    pending = _pending_task_interrupt(snapshot)
    # S26: the checkpoint's own real narrative (pre_outro/study_step/study_outro/
    # post_outro) wins if one already exists (matching how `last_message` already
    # re-serves verbatim on reconnect) - `pre_intro` only ever fires as a fallback,
    # since it's the one moment with nothing else yet to show.
    narrative_text = state.get("stage_narrative")
    narrative_evidence = state.get("stage_narrative_evidence")
    if narrative_text is None:
        narrative_text, narrative_evidence = await _maybe_fire_pre_intro(
            learning_session_id=learning_session_id,
            state=state,
            db=db,
            profile_adapter=profile_adapter,
            bedrock_gateway=bedrock_gateway,
        )
    return SessionSnapshotEvent(
        learning_session_id=learning_session_id,
        phase=state.get("phase", "created"),
        message=state.get("last_message"),
        is_correct=state.get("last_is_correct"),
        items=_items_response(state.get("last_items")),
        learning_gain=(
            LearningGainResponse.from_dict(state["last_learning_gain"])
            if state.get("last_learning_gain") is not None
            else None
        ),
        pending_interrupt=(
            await _pending_interrupt_response(pending, profile_adapter)
            if pending is not None
            else None
        ),
        attendance_resolution=state.get("attendance_resolution"),
        stage_narrative=narrative_text,
        stage_narrative_evidence=narrative_evidence,
    )


@router.get("/{learning_session_id}/stream")
async def stream_session(
    learning_session_id: str,
    token: Annotated[str, Query()],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
) -> StreamingResponse:
    initial = await _initial_snapshot(
        learning_session_id, graph, profile_adapter, db, bedrock_gateway, token
    )
    queue = events.subscribe(learning_session_id)

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
            events.unsubscribe(learning_session_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
