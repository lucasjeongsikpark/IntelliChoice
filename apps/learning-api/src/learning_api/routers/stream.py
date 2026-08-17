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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from intellichoice_adapters.fake_auth import TokenError
from intellichoice_db.engine import session_scope
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_shared.auth import Audience, account_refusal_reason
from intellichoice_shared.bedrock import BedrockGateway, StageNarrativePayload
from intellichoice_shared.profiles import ProfileAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.authorization import resolve_target_student
from learning_api.dependencies import (
    get_bedrock_gateway,
    get_graph,
    get_profile_adapter,
    get_session_events,
    get_token_verifier,
)
from learning_api.graph.build import LearningGraph
from learning_api.services import stage_narrative
from learning_api.services.session_events import SessionEventBus
from learning_api.services.stage_narrative_scheduler import help_is_on_screen

from .sessions import (
    InterventionContentResponse,
    LearningGainResponse,
    SessionSnapshotEvent,
    _assistance_question,
    _graph_config,
    _is_intervention_pause,
    _items_response,
    _pending_interrupt_response,
    _pending_task_interrupt,
    _study_progress,
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
) -> tuple[str | None, list[str], str | None]:
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
        return None, [], None
    # **`pre_intro` means "before the pre-exam", and the phase is what says so** (D-381).
    #
    # Firing was gated only on "the checkpoint has no narrative", which is also true part-way
    # through a session whose last stage narrative has not been written yet. A student
    # resuming at Skill 2 of 4 was greeted with *"Welcome to math practice! You're starting an
    # exciting journey…"* - measured live 2026-08-16. Harmless-looking, and it tells a student
    # who has already sat a ten-question exam that they are at the beginning; the whole point
    # of a stage narrative is that it knows which stage it is.
    #
    # Written as a **denylist of phases that are past the intro** rather than an allowlist of
    # phases that are before it. An allowlist would also have suppressed the greeting on a
    # first connect that legitimately lands mid-`pre_exam` - the AUD-F-26 race, where the
    # browser opens `EventSource` as the exam is starting - which is a behaviour change nobody
    # asked for. A new phase added later should keep today's behaviour by default; only the
    # ones named here are known to be too late for a welcome.
    if state.get("phase") in {"study", "post_exam", "completed", "blocked", "error"}:
        return None, [], None
    profile = await profile_adapter.get_student_profile(student_external_id)
    if profile is None:
        return None, [], None
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
        # S36/AUD-L-02: the checkpoint's running per-session total. This call previously
        # relied on a 0.0 default, so the gateway's session budget never applied to it.
        # The cost still isn't written *back* into the checkpoint (deliberate, S26/D-075 -
        # this path never touches the graph), so the total this reads stays one call behind
        # reality; that under-accounting is logged separately as AUD-L-03. Reading the real
        # total is still strictly better than asserting zero.
        session_spend_cents=state.get("bedrock_spend_cents", 0.0),
    )
    # U3/D-325: this call site is the one fixed-stage narrative - `pre_intro` is a
    # literal a few lines up, so the stage is known rather than inferred.
    return result.narrative_text, result.evidence_summary, "pre_intro"


async def _initial_snapshot(
    learning_session_id: str,
    graph: LearningGraph,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
    bedrock_gateway: BedrockGateway,
    token: str,
) -> SessionSnapshotEvent:
    # SSE authenticates via `?token=` because `EventSource` cannot set a header, so it
    # verifies here rather than through `get_current_claims` - which means AUD-X-02's
    # consent gate has to be repeated, not inherited. Exactly the shape of AUD-F-13: the
    # same request was sanitized in the access log and not in the trace because the two
    # paths were written separately.
    try:
        claims = get_token_verifier().verify(token, Audience.LEARNING)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.reason.value
        ) from exc
    refusal = account_refusal_reason(claims)
    if refusal is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=refusal)

    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
    state = snapshot.values
    if state.get("student_external_id") is not None:
        await resolve_target_student(
            claims, state["student_external_id"], profile_adapter, access="read"
        )
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
    narrative_stage = state.get("stage_narrative_stage")
    if narrative_text is None:
        narrative_text, narrative_evidence, narrative_stage = await _maybe_fire_pre_intro(
            learning_session_id=learning_session_id,
            state=state,
            db=db,
            profile_adapter=profile_adapter,
            bedrock_gateway=bedrock_gateway,
        )
        # AUD-F-26: `_maybe_fire_pre_intro` is a **real Bedrock call**, and the state read
        # above is now seconds old. The browser opens `EventSource` the moment it has a
        # session id, so it routinely starts a topic - and therefore the pre-exam - while
        # this connect is still inside that call. Returning the state captured *before* it
        # would then push the client backwards, and did: measured on staging, a student
        # who had reached `pre_exam` at 994ms was sent a `student_selected` snapshot at
        # 2736ms and landed back on the topic-select screen, with the exam screen's
        # view-time cleanup flushing a truncated 1653ms into `time_spent_minutes` on the
        # way out. Invisible against `MockBedrockProvider`, which returns in ~26ms and
        # leaves no window to lose.
        #
        # So re-read, and rebuild everything derived from state - `pending` included, since
        # an interrupt can be raised or resolved inside the same window.
        refreshed = await graph.aget_state(_graph_config(learning_session_id))
        if refreshed.values:
            # Re-authorize rather than trusting the earlier check: the student can be
            # resolved *during* this window (the child-selection interrupt completing), and
            # SPEC §5.30.2 wants the check against the state actually being served, not an
            # earlier one that happened to be safe.
            refreshed_student = refreshed.values.get("student_external_id")
            if refreshed_student is not None and refreshed_student != state.get(
                "student_external_id"
            ):
                await resolve_target_student(
                    claims, refreshed_student, profile_adapter, access="read"
                )
            state = refreshed.values
            pending = _pending_task_interrupt(refreshed)
            # The checkpoint's own narrative wins if the same window produced a real one -
            # `pre_intro` is only ever the fallback for "nothing else to show yet".
            checkpoint_narrative = state.get("stage_narrative")
            if checkpoint_narrative is not None:
                narrative_text = checkpoint_narrative
                narrative_evidence = state.get("stage_narrative_evidence")
                # Must move with the text: keeping the `pre_intro` stage from the fallback
                # while serving the checkpoint's `post_outro` prose is exactly the mismatch
                # this field exists to remove.
                narrative_stage = state.get("stage_narrative_stage")
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
        # D-216: re-serve the paid intervention content a refresh would otherwise discard
        # (the student was re-shown the bare chooser, and choosing again is a second
        # Bedrock call). Gated so a *previous* question's solution cannot resurface over a
        # new pause (the D-215 §4 defect, in reverse).
        #
        # **D-381: that gate was `hint_ladder_awaiting_choice`, which is false exactly when
        # the most expensive help is on screen.** The terminal rungs - hint 3 of 3, any
        # solution, any video - close the pause and hand back the next question while the
        # help stays up; `intervention_choice` says so in its own comment. So a refresh in
        # that state served no intervention at all, and since the study phase has no
        # navigator the student came back on the *next* question with the explanation they
        # were reading unreachable. They had spent their one intervention on nothing.
        # `help_is_on_screen` is the predicate the narrative scheduler already used for this
        # exact question, and it keeps the anti-resurfacing property: its second clause pairs
        # `last_intervention` with the current attempt.
        intervention=(
            InterventionContentResponse.from_dict(state["last_intervention"])
            if help_is_on_screen(state) and state.get("last_intervention") is not None
            else None
        ),
        # D-272: gated on the *pause*, not on `hint_ladder_awaiting_choice`. A reconnect
        # that lands on the intervention menu has no intervention yet - that is the state
        # this whole change exists for - and the checkpoint's retained `last_items` is the
        # right question only by luck. This names it.
        #
        # D-381: `or help_is_on_screen(state)` for the same reason as `intervention` above -
        # help on screen after a terminal rung is not a pause, and the question it belongs to
        # still has to be named or the restored help sits beside the wrong stem.
        assistance_question=await _assistance_question(
            db,
            state,
            help_open=_is_intervention_pause(pending) or help_is_on_screen(state),
        ),
        study_progress=await _study_progress(db, state),
        attendance_resolution=state.get("attendance_resolution"),
        stage_narrative=narrative_text,
        stage_narrative_evidence=narrative_evidence,
        stage_narrative_stage=narrative_stage,
    )


@router.get("/{learning_session_id}/stream")
async def stream_session(
    learning_session_id: str,
    request: Request,
    token: Annotated[str, Query()],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
) -> StreamingResponse:
    # AUD-F-36: subscribe BEFORE the initial-snapshot read. The read can dwell (the S26
    # pre-intro is a real Bedrock call), and an action completing inside that window -
    # measured: a parent's child-selection `/respond`, stamped the same millisecond as
    # this connect - used to publish to nobody and be too early for the queue, so the
    # stream served a pre-action initial frame and then never spoke again; the client
    # sat on a cleared interrupt forever. Subscribed first, that publish waits in the
    # queue and corrects the initial frame immediately after it. A queued event older
    # than the initial read is harmless: events are full snapshots, and anything that
    # made the read newer also queued its own later event.
    queue = events.subscribe(learning_session_id)
    try:
        # D-356, the port of chat-api's D-348: a short-lived session from the factory
        # rather than `Depends(get_db_session)`. A dependency-with-yield is torn down
        # *after* the response finishes, and an SSE response never finishes - so the
        # request's session stayed checked out and idle-in-transaction for as long as the
        # browser tab was open. The pool is 10 + 10 overflow; measured on chat, 20
        # concurrent SSE connections exhausted it and every other request on that replica
        # blocked. The keep-alive loop below needs no database at all.
        #
        # **`session_scope` rather than the bare factory, and that is the difference from
        # chat's port.** chat's initial snapshot is read-only, so closing without
        # committing costs nothing. This one is not: `_maybe_fire_pre_intro` writes a
        # `stage_transitions` row and `StageTransitionRepository.record` only flushes. On
        # the old dependency that write was committed by `get_db_session` - but only when
        # the *stream* ended, so the pre-intro's audit row (its `cost_cents` included) was
        # not durable while the tab stayed open. A unit of work that commits on a clean
        # exit fixes the hold and that latent second half together.
        async with session_scope(request.app.state.db_session_factory) as db:
            initial = await _initial_snapshot(
                learning_session_id, graph, profile_adapter, db, bedrock_gateway, token
            )
    except BaseException:
        # The auth/404 failures inside `_initial_snapshot` must not leak the queue now
        # that it is registered before they run.
        events.unsubscribe(learning_session_id, queue)
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
            events.unsubscribe(learning_session_id, queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
