"""SPEC §5.28.1 learning-session endpoints, backed by the S6 LangGraph workflow +
`PostgresSaver` checkpointing (SPEC §5.5, §5.16) and S7's `interrupt()`-based human
approval (SPEC §5.1.4, Phase 8 §6.9). See the S5/S6/S7 session plans in docs/PROGRESS.md
for which of the nine spec'd endpoints are deferred and why.
"""

import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.cost_reservation import CostReservationRepository
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.hints import HintEventRepository
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.stage_transition import StageTransitionRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from intellichoice_db.repositories.youtube import YoutubeRepository
from intellichoice_observability.metrics import CHECKPOINT_REPAIRS, SESSION_STARTS
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.pii_redaction import redact_free_text
from intellichoice_shared.profiles import ProfileAdapter
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Interrupt, StateSnapshot
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.authorization import resolve_target_student
from learning_api.dependencies import (
    get_bedrock_gateway,
    get_cost_ledger,
    get_current_claims,
    get_db_session,
    get_graph,
    get_mcp_registry,
    get_profile_adapter,
    get_session_events,
)
from learning_api.graph import nodes
from learning_api.graph.build import EntryInput, LearningGraph
from learning_api.graph.nodes import TurnContext
from learning_api.services import attendance, checkpoint_reconcile, flow
from learning_api.services.assessment_builder import AssessmentBuildError
from learning_api.services.session_events import SessionEventBus
from learning_api.services.study_plan import StudyPlanBuildError

EXAM_PHASES = ("pre_exam", "post_exam")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning/sessions", tags=["learning-sessions"])


class ChildCandidateResponse(BaseModel):
    student_external_id: str
    display_name: str
    grade: str
    branch_name: str


class EmailPreviewResponse(BaseModel):
    recipient: str
    subject: str
    body: str


class PendingInterruptResponse(BaseModel):
    """A paused `interrupt()`, enriched with human-readable preview data pulled live
    from MySQL for this one response - never cached in graph state (D-020).
    """

    interrupt_type: str
    child_candidates: list[ChildCandidateResponse] | None = None
    email_preview: EmailPreviewResponse | None = None
    question_variant_id: str | None = None


class LearningSessionResponse(BaseModel):
    learning_session_id: str
    phase: str
    pending_interrupt: PendingInterruptResponse | None = None


class SelectStudentRequest(BaseModel):
    student_id: str | None = None


class SelectTopicRequest(BaseModel):
    topic_id: str


class QuestionItemResponse(BaseModel):
    question_variant_id: str
    display_order: int
    rendered_question: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str


class TopicSelectionResponse(BaseModel):
    learning_session_id: str
    phase: str
    message: str | None = None
    items: list[QuestionItemResponse] | None = None
    pending_interrupt: PendingInterruptResponse | None = None
    # SPEC §5.6.5: "absence_acknowledged" is the only terminal resolution (no further
    # attendance action possible); "email_requested" still allows the caller to try a
    # different choice next (SPEC §5.6.4's decline message says so explicitly). `None`
    # means the gate just blocked and no choice has been made yet. Exposed so a client
    # can tell "just blocked, awaiting a choice" apart from "already acknowledged" -
    # both otherwise look identical (phase="blocked", no pending_interrupt).
    attendance_resolution: str | None = None


class AttendanceResolutionRequest(BaseModel):
    choice: Literal["acknowledge", "ask_branch_manager"]


class SubmitAnswerRequest(BaseModel):
    question_variant_id: str
    selected_option: str
    response_time_ms: int


class LearningGainResponse(BaseModel):
    pre_raw_score: float
    post_raw_score: float
    raw_gain: float
    weighted_gain: float
    normalized_gain: float | None
    normalized_gain_status: str | None
    skill_level_gain: dict
    difficulty_transition: dict
    independent_correct_rate: float
    hint_dependency: float
    solution_dependency: float
    unresolved_skills: list[str]
    response_time_change_ms: int

    @classmethod
    def from_dict(cls, gain: dict) -> "LearningGainResponse":
        return cls(**gain)


class AnswerResponse(BaseModel):
    learning_session_id: str
    phase: str
    # S22/D-064: `None` for a pre/post-exam answer - grading still happens immediately
    # server-side, but the correctness signal is withheld from the wire response until
    # `POST .../exam/finalize` (`AssessmentPolicy.feedback_visibility=
    # "hidden_until_finalize"`). Study-phase answers are unaffected (always a real bool).
    is_correct: bool | None
    items: list[QuestionItemResponse] | None = None
    learning_gain: LearningGainResponse | None = None
    pending_interrupt: PendingInterruptResponse | None = None
    # S26 (plan §18-L7): set only when this turn fired a `study_step`/`study_outro`
    # narrative - never on the pending-interrupt early return above, since no narrative
    # can have fired before `intervention_choice` even runs.
    stage_narrative: str | None = None
    stage_narrative_evidence: list[str] | None = None


class FlagItemRequest(BaseModel):
    flagged: bool = True


class RecordItemTimeRequest(BaseModel):
    elapsed_ms: int = Field(ge=0)


class ExamItemStatusResponse(BaseModel):
    assessment_item_id: str
    question_variant_id: str
    display_order: int
    status: str
    difficulty: int
    time_spent_ms: int


class ExamOverviewResponse(BaseModel):
    learning_session_id: str
    phase: str
    items: list[ExamItemStatusResponse]
    # SPEC §5.9/§5.13 `AssessmentPolicy.time_limit_seconds` (D-064: timed by default) -
    # `None` only if the session predates this session's policy stamping.
    remaining_seconds: int | None


class FinalizeExamRequest(BaseModel):
    confirm_unanswered: bool = False


class FinalizeExamResponse(BaseModel):
    learning_session_id: str
    phase: str
    items: list[QuestionItemResponse] | None = None
    learning_gain: LearningGainResponse | None = None
    # S26 (plan §18-L7): `pre_outro`/`post_outro`, whichever this finalize just fired.
    stage_narrative: str | None = None
    stage_narrative_evidence: list[str] | None = None


class ChatMessageRequest(BaseModel):
    question_variant_id: str
    message: str = Field(min_length=1, max_length=2000)


class ChatMessageResponse(BaseModel):
    learning_session_id: str
    reply_text: str
    intent: str


class ResumeResponse(BaseModel):
    learning_session_id: str
    phase: str
    message: str | None = None
    items: list[QuestionItemResponse] | None = None
    learning_gain: LearningGainResponse | None = None
    pending_interrupt: PendingInterruptResponse | None = None
    # S26 (plan §18-L7): the checkpoint's own `stage_narrative` channel - re-served
    # verbatim on `/resume` like `message`, since it's just another `LastValue` field.
    stage_narrative: str | None = None
    stage_narrative_evidence: list[str] | None = None


class ChildSelectionChoice(BaseModel):
    interrupt_type: Literal["child_selection"] = "child_selection"
    student_id: str


class EmailApprovalChoice(BaseModel):
    interrupt_type: Literal["email_approval"] = "email_approval"
    approved: bool


class InterventionChoiceRequest(BaseModel):
    interrupt_type: Literal["intervention_choice"] = "intervention_choice"
    # S21: "continue" ends a within-question hint ladder without solution/video -
    # the "I'll try again now" action once at least one hint has been shown.
    choice: Literal["hint", "solution", "video", "continue"]


RespondRequest = Annotated[
    ChildSelectionChoice | EmailApprovalChoice | InterventionChoiceRequest,
    Field(discriminator="interrupt_type"),
]


class SolutionStepResponse(BaseModel):
    step_number: int
    explanation: str
    expression: str
    common_mistake: str | None = None


class InterventionContentResponse(BaseModel):
    """SPEC §5.11.4-§5.11.6 generated content, shaped by `type` - `hint`/`solution`
    fields come from the Tutor Agent (validated or deterministic fallback, S8); `video`
    carries only the §5.11.6 catalog-unavailable message.
    """

    type: Literal["hint", "solution", "video"]
    hint_text: str | None = None
    concept_reminder: str | None = None
    next_step_prompt: str | None = None
    answer_revealed: bool | None = None
    difficulty: int | None = None
    # S21 within-question hint ladder position ("hint 2 of 3"), populated on `type ==
    # "hint"` only.
    hint_level: int | None = None
    max_hint_level: int | None = None
    steps: list[SolutionStepResponse] | None = None
    final_answer: str | None = None
    message: str | None = None
    # §5.11.6 video option: populated from the local catalog when an approved video exists;
    # otherwise `message` carries the catalog-unavailable fallback.
    video_title: str | None = None
    video_url: str | None = None
    video_source: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "InterventionContentResponse":
        return cls(**data)


class RespondResponse(BaseModel):
    learning_session_id: str
    phase: str
    message: str | None = None
    is_correct: bool | None = None
    items: list[QuestionItemResponse] | None = None
    learning_gain: LearningGainResponse | None = None
    pending_interrupt: PendingInterruptResponse | None = None
    intervention: InterventionContentResponse | None = None
    attendance_resolution: str | None = None
    # S26 (plan §18-L7): `study_step`/`study_outro`, whichever `intervention_choice`
    # just fired this round.
    stage_narrative: str | None = None
    stage_narrative_evidence: list[str] | None = None


class SessionSnapshotEvent(BaseModel):
    """The SPEC §5.14.1 SSE payload - one canonical "current session view" shape shared
    by every action endpoint's post-turn broadcast and `/stream`'s initial snapshot on
    (re)connect. Deliberately a superset of every action response's field names (all
    optional) so `_publish_snapshot` can build one straight from whichever typed response
    a handler already constructed, instead of re-deriving the same fields twice.
    """

    event: Literal["session_update"] = "session_update"
    learning_session_id: str
    phase: str
    message: str | None = None
    is_correct: bool | None = None
    items: list[QuestionItemResponse] | None = None
    learning_gain: LearningGainResponse | None = None
    pending_interrupt: PendingInterruptResponse | None = None
    intervention: InterventionContentResponse | None = None
    attendance_resolution: str | None = None
    stage_narrative: str | None = None
    stage_narrative_evidence: list[str] | None = None


def _publish_snapshot(events: SessionEventBus, response: BaseModel) -> None:
    snapshot = SessionSnapshotEvent.model_validate(response.model_dump())
    events.publish(snapshot.learning_session_id, snapshot.model_dump(mode="json"))


def _items_response(items: list[dict] | None) -> list[QuestionItemResponse] | None:
    if items is None:
        return None
    return [QuestionItemResponse(**item) for item in items]


def _graph_config(learning_session_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": learning_session_id}}


async def _reconcile_checkpoint(
    graph: LearningGraph, learning_session_id: str, state: dict, db: AsyncSession
) -> dict:
    """AUD-X-07: roll the checkpoint back if it references a domain row that does not
    exist, and return the state to act on. A no-op for every consistent session, which is
    all of them unless a request died between the checkpoint commit and the domain commit.

    Runs before the phase is read rather than inside a node: the whole failure mode is
    that the *routing* is ahead of the data, so a node dispatched on the bad phase has
    already made the wrong decision.
    """
    repair = await checkpoint_reconcile.find_repair(
        state=state,
        assessment_repo=AssessmentRepository(db),
        study_repo=StudyRepository(db),
    )
    if repair is None:
        return state
    logger.warning(
        "reconciling learning session %s: %s", learning_session_id, repair.reason
    )
    CHECKPOINT_REPAIRS.inc()
    await graph.aupdate_state(_graph_config(learning_session_id), repair.updates)
    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    return snapshot.values


async def _get_state_values(
    graph: LearningGraph, learning_session_id: str, db: AsyncSession
) -> dict:
    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
    if _pending_task_interrupt(snapshot) is not None:
        # A fresh (non-`Command`) `ainvoke` on a thread with a paused task silently
        # discards it instead of resuming it - reject here rather than letting a client
        # accidentally abandon an unresolved interrupt (SPEC §5.1.4 wants every
        # approval-sensitive pause actually resolved, not skippable by moving on).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="a pending interrupt must be resolved via /respond before continuing",
        )
    return await _reconcile_checkpoint(graph, learning_session_id, snapshot.values, db)


async def _peek_state_values(graph: LearningGraph, learning_session_id: str) -> dict:
    """Same 404 as `_get_state_values`, deliberately **without** the pending-interrupt
    guard - only for callers (S24 chat) that read state without ever invoking the graph,
    so there's no discard risk to guard against. `intervention_choice`'s pause is exactly
    when the button-panel `AssistancePanel` (and now chat, alongside it) is shown, so
    chat must keep working while one is pending.
    """
    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
    return snapshot.values


def _pending_task_interrupt(snapshot: StateSnapshot) -> Interrupt | None:
    for task in snapshot.tasks:
        if task.interrupts:
            return task.interrupts[0]
    return None


def _result_interrupt(result: dict) -> Interrupt | None:
    interrupts = result.get("__interrupt__")
    return interrupts[0] if interrupts else None


async def _pending_interrupt_response(
    pending: Interrupt, profile_adapter: ProfileAdapter
) -> PendingInterruptResponse:
    value = pending.value
    interrupt_type = value["type"]

    if interrupt_type == "child_selection":
        candidates = []
        for student_id in value["candidate_children"]:
            profile = await profile_adapter.get_student_profile(student_id)
            assert profile is not None
            branch = await profile_adapter.get_branch(profile.branch_external_id)
            candidates.append(
                ChildCandidateResponse(
                    student_external_id=student_id,
                    display_name=profile.display_name,
                    grade=profile.grade,
                    branch_name=branch.name if branch is not None else profile.branch_external_id,
                )
            )
        return PendingInterruptResponse(interrupt_type=interrupt_type, child_candidates=candidates)

    if interrupt_type == "email_approval":
        draft = await attendance.build_attendance_email_draft(
            profile_adapter=profile_adapter,
            student_external_id=value["student_external_id"],
            week_id=value["week_id"],
        )
        return PendingInterruptResponse(
            interrupt_type=interrupt_type,
            email_preview=EmailPreviewResponse(
                recipient=draft.recipient, subject=draft.subject, body=draft.body
            ),
        )

    return PendingInterruptResponse(
        interrupt_type=interrupt_type, question_variant_id=value.get("question_variant_id")
    )


def _turn_context(
    *,
    claims: TokenClaims,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
    mcp_registry: McpToolRegistry,
    bedrock_gateway: BedrockGateway,
    cost_ledger: CostReservationRepository,
    requested_student_id: str | None = None,
    topic_id: str | None = None,
    question_variant_id: str | None = None,
    selected_option: str | None = None,
    response_time_ms: int | None = None,
    idempotency_key: str | None = None,
    attendance_choice: str | None = None,
    confirm_unanswered: bool = False,
    student_message: str | None = None,
) -> TurnContext:
    return TurnContext(
        claims=claims,
        profile_adapter=profile_adapter,
        assessment_repo=AssessmentRepository(db),
        study_repo=StudyRepository(db),
        mastery_repo=MasteryRepository(db),
        question_repo=QuestionRepository(db),
        curriculum_repo=CurriculumRepository(db),
        youtube_repo=YoutubeRepository(db),
        hint_event_repo=HintEventRepository(db),
        memory_repo=MemoryRepository(db),
        stage_transition_repo=StageTransitionRepository(db),
        interrupt_repo=InterruptApprovalRepository(db),
        mcp_registry=mcp_registry,
        mcp_call_repo=McpToolCallRepository(db),
        bedrock_gateway=bedrock_gateway,
        cost_ledger=cost_ledger,
        rng=random.Random(),
        requested_student_id=requested_student_id,
        topic_id=topic_id,
        question_variant_id=question_variant_id,
        selected_option=selected_option,
        response_time_ms=response_time_ms,
        idempotency_key=idempotency_key,
        attendance_choice=attendance_choice,
        confirm_unanswered=confirm_unanswered,
        tutor_chat_repo=TutorChatMessageRepository(db),
        student_message=student_message,
    )


def _active_exam_session_id(state: dict) -> str | None:
    if state.get("phase") == "pre_exam":
        return state.get("pre_assessment_session_id")
    if state.get("phase") == "post_exam":
        return state.get("post_assessment_session_id")
    return None


@router.post("", response_model=LearningSessionResponse)
async def create_session(
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
) -> LearningSessionResponse:
    del claims  # authentication only; the target student is resolved at /student
    learning_session_id = str(uuid.uuid4())
    SESSION_STARTS.inc()
    return LearningSessionResponse(learning_session_id=learning_session_id, phase="created")


@router.post("/{learning_session_id}/student", response_model=LearningSessionResponse)
async def select_student(
    learning_session_id: str,
    body: SelectStudentRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> LearningSessionResponse:
    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        requested_student_id=body.student_id,
    )
    try:
        result = await graph.ainvoke(
            EntryInput(session_id=learning_session_id, entry_action="select_student"),
            config=_graph_config(learning_session_id),
            context=ctx,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    pending = _result_interrupt(result)
    if pending is not None:
        response = LearningSessionResponse(
            learning_session_id=learning_session_id,
            phase=result.get("phase", "created"),
            pending_interrupt=await _pending_interrupt_response(pending, profile_adapter),
        )
        _publish_snapshot(events, response)
        return response

    response = LearningSessionResponse(
        learning_session_id=learning_session_id, phase=result["phase"]
    )
    _publish_snapshot(events, response)
    return response


@router.post("/{learning_session_id}/topics", response_model=TopicSelectionResponse)
async def select_topic(
    learning_session_id: str,
    body: SelectTopicRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> TopicSelectionResponse:
    state = await _get_state_values(graph, learning_session_id, db)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student before a topic"
        )
    # Re-verify the bearer token still grants access to this session's student, since
    # the token holder may differ from whoever created the session (SPEC §5.6.1 -
    # authorization is never trusted from session state alone).
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )

    curriculum_repo = CurriculumRepository(db)
    if await curriculum_repo.get_topic(body.topic_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"unknown topic {body.topic_id!r}"
        )

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        topic_id=body.topic_id,
    )
    try:
        result = await graph.ainvoke(
            EntryInput(session_id=learning_session_id, entry_action="select_topic"),
            config=_graph_config(learning_session_id),
            context=ctx,
        )
    except AssessmentBuildError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    if result["phase"] == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.get("last_error")
        )

    response = TopicSelectionResponse(
        learning_session_id=learning_session_id,
        phase=result["phase"],
        message=result.get("last_message"),
        items=_items_response(result.get("last_items")),
    )
    _publish_snapshot(events, response)
    return response


@router.post(
    "/{learning_session_id}/attendance-resolution", response_model=TopicSelectionResponse
)
async def resolve_attendance_choice(
    learning_session_id: str,
    body: AttendanceResolutionRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> TopicSelectionResponse:
    """SPEC §5.6.3's two choices, offered after `/topics` returns `phase="blocked"`."""
    state = await _get_state_values(graph, learning_session_id, db)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student first"
        )
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )
    if state.get("phase") != "blocked":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is not blocked (phase={state.get('phase')})",
        )

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        attendance_choice=body.choice,
    )
    result = await graph.ainvoke(
        EntryInput(session_id=learning_session_id, entry_action="resolve_attendance"),
        config=_graph_config(learning_session_id),
        context=ctx,
    )

    pending = _result_interrupt(result)
    if pending is not None:
        response = TopicSelectionResponse(
            learning_session_id=learning_session_id,
            phase="blocked",
            pending_interrupt=await _pending_interrupt_response(pending, profile_adapter),
        )
        _publish_snapshot(events, response)
        return response

    response = TopicSelectionResponse(
        learning_session_id=learning_session_id,
        phase=result["phase"],
        message=result.get("last_message"),
        attendance_resolution=result.get("attendance_resolution"),
    )
    _publish_snapshot(events, response)
    return response


@router.post("/{learning_session_id}/answers", response_model=AnswerResponse)
async def submit_answer(
    learning_session_id: str,
    body: SubmitAnswerRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> AnswerResponse:
    state = await _get_state_values(graph, learning_session_id, db)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student before answering"
        )
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )
    submitted_phase = state.get("phase")
    if submitted_phase not in ("pre_exam", "study", "post_exam"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is not accepting answers in phase {state.get('phase')}",
        )
    if submitted_phase in EXAM_PHASES:
        exam_session_id = _active_exam_session_id(state)
        assert exam_session_id is not None
        assessment_repo = AssessmentRepository(db)
        exam_session_row = await assessment_repo.get_session(exam_session_id)
        assert exam_session_row is not None
        if flow.is_exam_expired(exam_session_row, datetime.now(UTC)):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="exam time limit exceeded - finalize to submit",
            )
        # AUD-L-10, pre-flighted here so a duplicate answer never starts a graph turn.
        # `flow` re-checks and the unique constraint enforces; this only shapes the error.
        try:
            await flow.ensure_item_unanswered(
                assessment_repo, exam_session_id, body.question_variant_id, idempotency_key
            )
        except flow.ItemAlreadyAnsweredError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(exc)
            ) from exc

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        question_variant_id=body.question_variant_id,
        selected_option=body.selected_option,
        response_time_ms=body.response_time_ms,
        idempotency_key=idempotency_key,
    )
    try:
        result = await graph.ainvoke(
            EntryInput(session_id=learning_session_id, entry_action="submit_answer"),
            config=_graph_config(learning_session_id),
            context=ctx,
        )
    except StudyPlanBuildError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc
    except flow.ItemAlreadyAnsweredError as exc:
        # The pre-flight above catches the ordinary case; this is the concurrent one, where
        # the unique constraint rejected the insert after both requests read no attempt.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    pending = _result_interrupt(result)
    if pending is not None:
        # SPEC §5.11.3: incorrect study answer, paused for the hint/solution/video
        # choice. `submit_answer`'s own superstep already committed `phase`/
        # `last_is_correct` before `intervention_choice` paused (D-019's per-channel
        # merge - only the currently-paused node reruns, not its upstream node).
        response = AnswerResponse(
            learning_session_id=learning_session_id,
            phase=result["phase"],
            is_correct=result["last_is_correct"],
            pending_interrupt=await _pending_interrupt_response(pending, profile_adapter),
        )
        _publish_snapshot(events, response)
        return response

    if result["phase"] == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=result.get("last_error")
        )

    response = AnswerResponse(
        learning_session_id=learning_session_id,
        phase=result["phase"],
        # D-064: withhold correctness for a pre/post-exam answer - masked by the phase the
        # answer was *submitted* in, not the (possibly different, if a bug existed) phase
        # the turn ended in.
        is_correct=None if submitted_phase in EXAM_PHASES else result["last_is_correct"],
        items=_items_response(result.get("last_items")),
        learning_gain=(
            LearningGainResponse.from_dict(result["last_learning_gain"])
            if result.get("last_learning_gain") is not None
            else None
        ),
        stage_narrative=result.get("stage_narrative"),
        stage_narrative_evidence=result.get("stage_narrative_evidence"),
    )
    _publish_snapshot(events, response)
    return response


async def _exam_phase_state(
    graph: LearningGraph,
    learning_session_id: str,
    claims: TokenClaims,
    profile_adapter: ProfileAdapter,
    db: AsyncSession,
) -> tuple[dict, str]:
    """Shared guard for the skip/flag/overview endpoints below: session exists, caller is
    authorized for its student, and it's actually in an exam phase. Returns
    `(state, active_exam_session_id)`.
    """
    state = await _get_state_values(graph, learning_session_id, db)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student first"
        )
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )
    if state.get("phase") not in EXAM_PHASES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session is not in an exam phase (phase={state.get('phase')})",
        )
    exam_session_id = _active_exam_session_id(state)
    assert exam_session_id is not None
    return state, exam_session_id


@router.post("/{learning_session_id}/exam/items/{assessment_item_id}/skip", status_code=204)
async def skip_exam_item(
    learning_session_id: str,
    assessment_item_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
) -> None:
    """S22 (SPEC §5.9/§5.13, D-064): a plain repository write, not a graph turn - no
    routing consequence, same "high-frequency, no-consequence action stays outside the
    graph" precedent `/answers` itself already documents.
    """
    _, exam_session_id = await _exam_phase_state(
        graph, learning_session_id, claims, profile_adapter, db
    )
    try:
        await flow.mark_item_skipped(AssessmentRepository(db), exam_session_id, assessment_item_id)
    except flow.UnknownExamItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{learning_session_id}/exam/items/{assessment_item_id}/flag", status_code=204)
async def flag_exam_item(
    learning_session_id: str,
    assessment_item_id: str,
    body: FlagItemRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
) -> None:
    _, exam_session_id = await _exam_phase_state(
        graph, learning_session_id, claims, profile_adapter, db
    )
    try:
        await flow.mark_item_flagged(
            AssessmentRepository(db), exam_session_id, assessment_item_id, body.flagged
        )
    except flow.UnknownExamItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{learning_session_id}/exam/items/{assessment_item_id}/time", status_code=204)
async def record_exam_item_time(
    learning_session_id: str,
    assessment_item_id: str,
    body: RecordItemTimeRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
) -> None:
    """S23 autosave tick: accumulates time spent viewing an exam item. Same plain
    repository write as skip/flag - no graph turn, no routing consequence.
    """
    _, exam_session_id = await _exam_phase_state(
        graph, learning_session_id, claims, profile_adapter, db
    )
    try:
        await flow.record_item_time(
            AssessmentRepository(db), exam_session_id, assessment_item_id, body.elapsed_ms
        )
    except flow.UnknownExamItemError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/{learning_session_id}/exam/overview", response_model=ExamOverviewResponse)
async def exam_overview(
    learning_session_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
) -> ExamOverviewResponse:
    """Plain read (no `ainvoke`) - lets the exam nav bar restore item statuses after a
    mid-exam refresh (SPEC §5.16's checkpoint-restore property, extended to nav state).
    """
    state, exam_session_id = await _exam_phase_state(
        graph, learning_session_id, claims, profile_adapter, db
    )
    assessment_repo = AssessmentRepository(db)
    question_repo = QuestionRepository(db)
    session_row = await assessment_repo.get_session(exam_session_id)
    assert session_row is not None
    items = await assessment_repo.get_items(exam_session_id)
    item_state_rows = await assessment_repo.get_item_states(exam_session_id)
    item_states = {s.assessment_item_id: s for s in item_state_rows}

    item_responses = []
    for item in items:
        variant = await question_repo.get_variant(item.question_variant_id)
        assert variant is not None
        template = await question_repo.get_template(variant.question_template_id)
        assert template is not None
        item_state = item_states[item.assessment_item_id]
        item_responses.append(
            ExamItemStatusResponse(
                assessment_item_id=item.assessment_item_id,
                question_variant_id=item.question_variant_id,
                display_order=item.display_order,
                status=item_state.status,
                difficulty=template.difficulty_label,
                time_spent_ms=item_state.time_spent_ms,
            )
        )

    remaining_seconds: int | None = None
    if session_row.time_limit_seconds is not None:
        elapsed = (datetime.now(UTC) - session_row.started_at).total_seconds()
        remaining_seconds = max(0, int(session_row.time_limit_seconds - elapsed))

    return ExamOverviewResponse(
        learning_session_id=learning_session_id,
        phase=state["phase"],
        items=item_responses,
        remaining_seconds=remaining_seconds,
    )


@router.post("/{learning_session_id}/exam/finalize", response_model=FinalizeExamResponse)
async def finalize_exam(
    learning_session_id: str,
    body: FinalizeExamRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> FinalizeExamResponse:
    """S22 (SPEC §5.9/§5.13, D-064): the explicit "submit exam" action - grades any
    remaining unanswered item incorrect (once confirmed, or once the timer's expired) and
    advances the phase. Idempotent: a retried call sees the target `AssessmentSession`
    already `finalized_at` and re-serves the same result with no side effects - including
    a retry that arrives *after* the phase has already visibly moved to "study"/
    "completed" (`flow.finalize_exam` resolves the right target session in that case too),
    so this guard deliberately allows those two phases through as well, not just
    `EXAM_PHASES` itself.
    """
    state = await _get_state_values(graph, learning_session_id, db)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student first"
        )
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )
    if state.get("phase") not in (*EXAM_PHASES, "study", "completed"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"session has no exam to finalize (phase={state.get('phase')})",
        )

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        confirm_unanswered=body.confirm_unanswered,
    )
    try:
        result = await graph.ainvoke(
            EntryInput(session_id=learning_session_id, entry_action="finalize_exam"),
            config=_graph_config(learning_session_id),
            context=ctx,
        )
    except flow.ExamNotReadyToFinalizeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"unanswered_item_ids": exc.unanswered_item_ids},
        ) from exc

    response = FinalizeExamResponse(
        learning_session_id=learning_session_id,
        phase=result["phase"],
        items=_items_response(result.get("last_items")),
        learning_gain=(
            LearningGainResponse.from_dict(result["last_learning_gain"])
            if result.get("last_learning_gain") is not None
            else None
        ),
        stage_narrative=result.get("stage_narrative"),
        stage_narrative_evidence=result.get("stage_narrative_evidence"),
    )
    _publish_snapshot(events, response)
    return response


@router.post("/{learning_session_id}/chat", response_model=ChatMessageResponse)
async def send_chat_message(
    learning_session_id: str,
    body: ChatMessageRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
) -> ChatMessageResponse:
    """S24 (SPEC §5.12/§5.30.1 D-072): contextual learning chat, behind the study-phase
    `AssistancePanel`'s "Chat" option. Refuses outside `phase == "study"` - matching
    `exam_policy`'s `hints_allowed=False` for pre/post exam, chat is just another
    assistance surface (SPEC §5.9's per-phase policy). The student's raw message is
    redacted (`pii_redaction.redact_free_text`) here, at the request boundary, before it
    ever reaches `TurnContext`/the Bedrock wire/`tutor_chat_messages` - `run_chat_turn`
    never sees the unredacted text.

    Deliberately calls `nodes.run_chat_turn` directly rather than `graph.ainvoke` (see
    that function's own docstring for why) - so this route reads state via
    `_peek_state_values`, not `_get_state_values`: chat must keep working while the
    graph is paused at `intervention_choice`'s `interrupt()`, which is exactly when the
    button-panel `AssistancePanel` (and now chat, alongside it) is shown.
    """
    state = await _peek_state_values(graph, learning_session_id)
    if state.get("student_external_id") is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="select a student first"
        )
    await resolve_target_student(
        claims, state["student_external_id"], profile_adapter, access="write"
    )
    if state.get("phase") != "study":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"chat is only available during study (phase={state.get('phase')})",
        )
    if await QuestionRepository(db).get_variant(body.question_variant_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown question variant {body.question_variant_id!r}",
        )

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        question_variant_id=body.question_variant_id,
        student_message=redact_free_text(body.message),
    )
    result = await nodes.run_chat_turn(
        ctx,
        student_external_id=state["student_external_id"],
        learning_session_id=learning_session_id,
        bedrock_spend_cents=state.get("bedrock_spend_cents", 0.0),
    )
    return ChatMessageResponse(
        learning_session_id=learning_session_id,
        reply_text=result.reply_text,
        intent=result.intent,
    )


@router.post("/{learning_session_id}/respond", response_model=RespondResponse)
async def respond_to_interrupt(
    learning_session_id: str,
    body: RespondRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> RespondResponse:
    """Resumes whichever `interrupt()` is currently paused on this thread (SPEC §5.1.4,
    Phase 8 §6.9) - child selection, attendance-email approval, or hint/solution/video
    choice. `body.interrupt_type` must match the actually-pending interrupt so a stale or
    mismatched client request fails clearly instead of silently resuming the wrong node.
    """
    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
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

    state = snapshot.values
    # `student_external_id` isn't set yet mid child-selection - `resolve_student`'s own
    # fresh linked-children re-check on resume is the guard for that one (SPEC §5.6.1).
    if state.get("student_external_id") is not None:
        await resolve_target_student(
            claims, state["student_external_id"], profile_adapter, access="write"
        )

    resume_value: object
    if isinstance(body, ChildSelectionChoice):
        resume_value = body.student_id
    elif isinstance(body, EmailApprovalChoice):
        resume_value = {"approved": body.approved}
    else:
        resume_value = {"choice": body.choice}

    # LangGraph replays a resumed node's body from the top - only the `interrupt()`
    # call itself returns the cached value instead of pausing again. `resolve_attendance`
    # branches on `ctx.attendance_choice` *before* its `interrupt()` call, so that field
    # must be supplied again here or the replay takes the wrong branch (it's never
    # `acknowledge`, since that path never interrupts in the first place).
    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
        attendance_choice="ask_branch_manager" if body.interrupt_type == "email_approval" else None,
    )
    try:
        result = await graph.ainvoke(
            Command(resume=resume_value),
            config=_graph_config(learning_session_id),
            context=ctx,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    next_pending = _result_interrupt(result)
    response = RespondResponse(
        learning_session_id=learning_session_id,
        phase=result.get("phase", state.get("phase", "created")),
        message=result.get("last_message"),
        is_correct=result.get("last_is_correct"),
        items=_items_response(result.get("last_items")),
        learning_gain=(
            LearningGainResponse.from_dict(result["last_learning_gain"])
            if result.get("last_learning_gain") is not None
            else None
        ),
        pending_interrupt=(
            await _pending_interrupt_response(next_pending, profile_adapter)
            if next_pending is not None
            else None
        ),
        intervention=(
            InterventionContentResponse.from_dict(result["last_intervention"])
            if result.get("last_intervention") is not None
            else None
        ),
        attendance_resolution=result.get("attendance_resolution"),
        stage_narrative=result.get("stage_narrative"),
        stage_narrative_evidence=result.get("stage_narrative_evidence"),
    )
    _publish_snapshot(events, response)
    return response


@router.post("/{learning_session_id}/resume", response_model=ResumeResponse)
async def resume_session(
    learning_session_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    cost_ledger: Annotated[CostReservationRepository, Depends(get_cost_ledger)],
    mcp_registry: Annotated[McpToolRegistry, Depends(get_mcp_registry)],
    bedrock_gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    graph: Annotated[LearningGraph, Depends(get_graph)],
    events: Annotated[SessionEventBus, Depends(get_session_events)],
) -> ResumeResponse:
    """Reloads the checkpointed state and re-serves the last pending question (or
    pending interrupt) with no side effects (SPEC §5.16: "killing the process
    mid-session and calling resume continues from the same question").

    If a turn is still paused on an `interrupt()`, this must NOT call `ainvoke` with a
    fresh (non-`Command`) entry - that discards the pending task entirely and starts a
    new turn from `START` instead of resuming it. So a pending interrupt is re-served
    directly from the checkpoint instead.
    """
    snapshot = await graph.aget_state(_graph_config(learning_session_id))
    if not snapshot.values:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="learning session not found"
        )
    state = snapshot.values
    if state.get("student_external_id") is not None:
        await resolve_target_student(
            claims, state["student_external_id"], profile_adapter, access="write"
        )
    elif claims.sub != state.get("user_external_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="token does not match this session"
        )

    pending = _pending_task_interrupt(snapshot)
    if pending is not None:
        response = ResumeResponse(
            learning_session_id=learning_session_id,
            phase=state.get("phase", "created"),
            pending_interrupt=await _pending_interrupt_response(pending, profile_adapter),
        )
        _publish_snapshot(events, response)
        return response

    # AUD-X-07: this route reads the snapshot directly rather than through
    # `_get_state_values`, and it is the entry point in the reproduction - a session that
    # lost its finalize between the two commits resumed 200 with `phase=study` and served
    # a study question that then 500'd on every answer. Reconcile before invoking.
    state = await _reconcile_checkpoint(graph, learning_session_id, state, db)

    ctx = _turn_context(
        cost_ledger=cost_ledger,
        claims=claims,
        profile_adapter=profile_adapter,
        db=db,
        mcp_registry=mcp_registry,
        bedrock_gateway=bedrock_gateway,
    )
    result = await graph.ainvoke(
        EntryInput(session_id=learning_session_id, entry_action="resume"),
        config=_graph_config(learning_session_id),
        context=ctx,
    )

    response = ResumeResponse(
        learning_session_id=learning_session_id,
        phase=result["phase"],
        message=result.get("last_message"),
        items=_items_response(result.get("last_items")),
        learning_gain=(
            LearningGainResponse.from_dict(result["last_learning_gain"])
            if result.get("last_learning_gain") is not None
            else None
        ),
        stage_narrative=result.get("stage_narrative"),
        stage_narrative_evidence=result.get("stage_narrative_evidence"),
    )
    _publish_snapshot(events, response)
    return response
