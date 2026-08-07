"""LangGraph node bodies for the Adaptive Learning workflow (SPEC §5.5).

Each node reads its runtime dependencies (repositories, the profile adapter, the caller's
claims, per-turn input like a submitted answer) from `runtime.context` (a `TurnContext`
built fresh for every `ainvoke` call), rather than the checkpointed `LearningState`,
since those objects (a DB session-bound repo, a `random.Random`) aren't
checkpoint-serializable and shouldn't be (SPEC §5.5.3: state holds ids and results, not
live connections). Only `LearningState` is persisted by the `PostgresSaver`.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from intellichoice_curriculum.hint_ladders import SHAPE_HINT_LADDERS
from intellichoice_db.models.cost_reservation import SCOPE_TUTOR_CHAT
from intellichoice_db.models.hints import HintEvent
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.models.mastery import StudyAttempt
from intellichoice_db.models.questions import QuestionTemplate
from intellichoice_db.models.tutor_chat import TutorChatMessage
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.cost_reservation import (
    CeilingReachedError,
    CostReservationRepository,
    Reservation,
)
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
from intellichoice_observability.metrics import (
    ATTENDANCE_CHECKS,
    EXAM_COMPLETIONS,
    LEARNING_GAIN,
    SESSION_COST_CENTS,
    SESSIONS_COMPLETED,
    SUPPORT_USAGE,
)
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.bedrock import BedrockGateway, BedrockGatewayError, StageNarrativePayload
from intellichoice_shared.mcp import McpToolRegistry
from intellichoice_shared.profiles import ProfileAdapter
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from learning_api.services import (
    attendance,
    flow,
    memory_events,
    stage_narrative,
    topic_resolver,
    tutor,
    video_catalog,
)
from learning_api.services import tutor_chat as tutor_chat_service
from learning_api.services.assessment_builder import AssessmentBuildError, build_pre_exam
from learning_api.services.attendance import check_attendance_gate
from learning_api.services.consolidation_scheduler import (
    ConsolidationScheduler,
    InlineConsolidationScheduler,
)
from learning_api.services.study_plan import StudyPlanBuildError

from .state import LearningState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnContext:
    """Everything one `ainvoke` call needs beyond the checkpointed state: injected
    dependencies plus this turn's user-supplied payload. Built per-request by the
    router - including on the `/respond` call that resumes a paused interrupt, since
    nothing in this dataclass is checkpoint-serializable (SPEC §5.5.3: state holds ids
    and results, not live connections).
    """

    claims: TokenClaims
    profile_adapter: ProfileAdapter
    assessment_repo: AssessmentRepository
    study_repo: StudyRepository
    mastery_repo: MasteryRepository
    question_repo: QuestionRepository
    curriculum_repo: CurriculumRepository
    youtube_repo: YoutubeRepository
    hint_event_repo: HintEventRepository
    memory_repo: MemoryRepository
    stage_transition_repo: StageTransitionRepository
    interrupt_repo: InterruptApprovalRepository
    mcp_registry: McpToolRegistry
    mcp_call_repo: McpToolCallRepository
    bedrock_gateway: BedrockGateway
    # AUD-X-08's spend ledger. Unlike every repo above it is bound to the session
    # *factory*, not this request's session: a reservation must commit before the model
    # call returns, and the request session commits only at dependency teardown.
    cost_ledger: CostReservationRepository
    rng: Any
    # D-217: when True (real Bedrock), a `study_step`/`study_outro` narrative is not
    # generated inside the answer turn - the node leaves an ids-only marker and the route
    # hands it to the background scheduler, so the answer response no longer waits ~1.5s
    # for a Bedrock call. False under the mock provider, so every existing test still sees
    # the narrative synchronously on the turn that fired it.
    defer_study_narrative: bool = False
    requested_student_id: str | None = None
    topic_id: str | None = None
    question_variant_id: str | None = None
    selected_option: str | None = None
    response_time_ms: int | None = None
    idempotency_key: str | None = None
    attendance_choice: str | None = None
    # S22 (SPEC §5.9/§5.13, D-064): the `/exam/finalize` request's confirmation flag - only
    # read by `finalize_exam` below.
    confirm_unanswered: bool = False
    # S24 (SPEC §5.12/§5.30.1 D-072): only read by `tutor_chat` below.
    # `student_message` is already `pii_redaction.redact_free_text`-ed by the router
    # before this dataclass is built - the raw message never reaches this far.
    tutor_chat_repo: TutorChatMessageRepository | None = None
    student_message: str | None = None
    # D-208: where `finalize_exam` hands memory consolidation instead of awaiting it.
    # Bound to the session *factory* in a deployed environment, for the same reason
    # `cost_ledger` above is - see services/consolidation_scheduler.py. `None` keeps the
    # pre-D-208 inline behaviour, which is what every graph-level test uses.
    consolidation_scheduler: ConsolidationScheduler | None = None


def _ctx(runtime: Runtime[TurnContext]) -> TurnContext:
    assert isinstance(runtime.context, TurnContext)
    return runtime.context


def _items_payload(items: list[flow.QuestionItemView]) -> list[dict[str, str | int]]:
    return [
        {
            "question_variant_id": item.question_variant_id,
            "display_order": item.display_order,
            "rendered_question": item.rendered_question,
            "option_a": item.option_a,
            "option_b": item.option_b,
            "option_c": item.option_c,
            "option_d": item.option_d,
        }
        for item in items
    ]


def _gain_payload(gain: flow.LearningGainResult) -> dict:
    return {
        "pre_raw_score": gain.pre_raw_score,
        "post_raw_score": gain.post_raw_score,
        "raw_gain": gain.raw_gain,
        "weighted_gain": gain.weighted_gain,
        "normalized_gain": gain.normalized_gain,
        "normalized_gain_status": gain.normalized_gain_status,
        "skill_level_gain": gain.skill_level_gain,
        "difficulty_transition": gain.difficulty_transition,
        "independent_correct_rate": gain.independent_correct_rate,
        "hint_dependency": gain.hint_dependency,
        "solution_dependency": gain.solution_dependency,
        "unresolved_skills": gain.unresolved_skills,
        "response_time_change_ms": gain.response_time_change_ms,
    }


async def _skill_name(ctx: TurnContext, skill_id: str) -> str:
    skill = await ctx.curriculum_repo.get_skill(skill_id)
    return skill.name if skill is not None else skill_id


async def _grade_for_narrative(ctx: TurnContext, student_external_id: str) -> str:
    profile = await ctx.profile_adapter.get_student_profile(student_external_id)
    assert profile is not None
    return profile.grade


async def _fire_stage_narrative(
    ctx: TurnContext,
    state: LearningState,
    payload: StageNarrativePayload,
    bedrock_spend_cents: float,
    related_skill_id: str | None = None,
) -> tuple[str, list[str], float]:
    """S26 (plan §18-L7): shared call site for all four in-graph narrative moments -
    folds the cost into the running `bedrock_spend_cents` total the same way S25's
    inline memory consolidation does, since this always runs as part of a real graph
    turn (unlike `pre_intro`, fired from the SSE connect path - see
    `routers/sessions.py`). Returns `(narrative_text, evidence_summary,
    updated_bedrock_spend_cents)`.
    """
    assert state.student_external_id is not None
    result = await stage_narrative.generate_stage_narrative(
        gateway=ctx.bedrock_gateway,
        repo=ctx.stage_transition_repo,
        student_external_id=state.student_external_id,
        learning_session_id=state.session_id,
        payload=payload,
        related_skill_id=related_skill_id,
        session_spend_cents=bedrock_spend_cents,
    )
    return result.narrative_text, result.evidence_summary, bedrock_spend_cents + result.cost_cents


async def resolve_student(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.6.1 role -> child-selection routing.

    - Student role: verified against the token's own `sub`.
    - Parent role, explicit `requested_student_id`: verified against a live linked-
      children lookup.
    - Parent role, no id, exactly one linked child: auto-selected.
    - Parent role, no id, multiple linked children: commits identity (`user_external_id`/
      `parent_external_id`) and routes to `await_child_selection` for the actual
      `interrupt()` pause, rather than pausing inline here. Identity must land in
      checkpointed state *before* the pause - `/resume` authenticates a still-paused
      caller against exactly that state, and nothing else is available to check against
      while paused (SPEC §5.16's "Parent exits during child selection" checkpoint case).
    """
    ctx = _ctx(runtime)
    claims = ctx.claims
    requested_student_id = ctx.requested_student_id
    existing_student_id = state.student_external_id

    def bind(target: str) -> str:
        """AUD-X-01 (S40, D-107): refuse to move a session to a different student.

        Seventeen learning routes authorize by passing the *checkpoint's*
        `student_external_id` to `authorization.resolve_target_student`. This node is the
        eighteenth route's entry point and the only place that *writes* that field - and
        it validated the requested student against the caller's own claims while never
        reading the value already there. So any caller holding a session id could bind it
        to themselves: the original owner was locked out of their own exam with 403 and
        their `in_progress` row was orphaned with no route back to it (verified on live
        staging). Applied to every role, before the role split, because the tutor and
        branch-manager branch below accepts an unvalidated `requested_student_id` and is
        the widest version of the same hole (AUD-X-05).

        The one legitimate rebind - a parent switching children - never reaches here: it
        pauses at `await_child_selection`, which re-checks the live parent-child link on
        resume. A session is per-student by construction (it owns an exam, a study plan
        and a mastery trail), so switching students within one is not a supported action
        for anybody; the parent's route to a second child is a second session.
        """
        if existing_student_id is not None and existing_student_id != target:
            # Deliberately does not name the owner - the caller has already proven only
            # that they hold a session id.
            raise PermissionError("This session already belongs to another student")
        return target

    if claims.role == Role.STUDENT:
        target = requested_student_id or claims.sub
        if claims.sub != target:
            raise PermissionError("Students may only access their own records")
        return {
            "user_external_id": claims.sub,
            "user_role": claims.role.value,
            "student_external_id": bind(target),
            "phase": "student_selected",
        }

    if claims.role == Role.PARENT:
        linked_children = await ctx.profile_adapter.get_parent_children(claims.sub)
        if requested_student_id is not None:
            if requested_student_id not in linked_children:
                raise PermissionError("Parent is not linked to this student")
            return {
                "user_external_id": claims.sub,
                "user_role": claims.role.value,
                "parent_external_id": claims.sub,
                "student_external_id": bind(requested_student_id),
                "phase": "student_selected",
            }
        if len(linked_children) == 1:
            return {
                "user_external_id": claims.sub,
                "user_role": claims.role.value,
                "parent_external_id": claims.sub,
                "student_external_id": bind(linked_children[0]),
                "phase": "student_selected",
            }
        return {
            "user_external_id": claims.sub,
            "user_role": claims.role.value,
            "parent_external_id": claims.sub,
            "phase": "awaiting_child_selection",
        }

    # Tutor / branch manager: still no per-student *scope* check - that needs the
    # tutor-assignment / branch-roster data `ProfileAdapter` does not carry until S43's
    # `IcProfileAdapter` (D-086, AUD-L-07), so the read-scope gap is a recorded, accepted
    # risk rather than an oversight. `bind` below closes the part that does not need that
    # data: a tutor can no longer *seize* a session that already belongs to a student
    # (AUD-X-05's `select_student` row). Writes through the other session routes are
    # blocked separately, in `authorization.resolve_target_student`.
    target = requested_student_id or claims.sub
    return {
        "user_external_id": claims.sub,
        "user_role": claims.role.value,
        "student_external_id": bind(target),
        "phase": "student_selected",
    }


async def await_child_selection(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """The actual `interrupt()` pause for SPEC §5.6.1's multi-child case, split out of
    `resolve_student` so identity commits to checkpointed state before the pause (see
    that function's docstring). Only reached via the conditional edge from
    `resolve_student` - never a top-level entry action.
    """
    ctx = _ctx(runtime)
    assert state.parent_external_id is not None
    linked_children = await ctx.profile_adapter.get_parent_children(state.parent_external_id)

    # External ids only in the interrupt payload (D-020) - it's checkpointed to Postgres
    # by `AsyncPostgresSaver`, so no MySQL-sourced display data belongs here; the router
    # builds the human-readable selector from a live MySQL lookup.
    chosen = interrupt({"type": "child_selection", "candidate_children": linked_children})

    # Re-fetched fresh (not the payload above, which may be stale on a replay) so a
    # parent-child link change between pause and resume can't select a stale student.
    current_linked_children = await ctx.profile_adapter.get_parent_children(ctx.claims.sub)
    if ctx.claims.sub != state.parent_external_id or chosen not in current_linked_children:
        raise PermissionError("Parent is not linked to this student")

    return {"student_external_id": chosen, "phase": "student_selected"}


async def select_topic(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.6.2-§5.6.5 attendance gate, then §5.9 pre-exam build."""
    ctx = _ctx(runtime)
    assert state.student_external_id is not None
    assert ctx.topic_id is not None

    # AUD-X-03: this node creates an exam, so a replayed turn must not create a second one.
    # `flow.is_topic_selection_replay` raises `TopicAlreadySelectedError` for the cases the
    # route answers 409; reaching that here means the route's pre-flight was bypassed or lost a
    # race, and the exception propagating out of the turn is correct - the router maps it to the
    # same 409 rather than letting the build proceed.
    if flow.is_topic_selection_replay(
        requested_topic_id=ctx.topic_id,
        selected_topic_id=state.topic_id,
        pre_assessment_session_id=state.pre_assessment_session_id,
        phase=state.phase,
    ):
        # Serve the exam that already exists, item for item. Deliberately ahead of the
        # attendance gate: re-running it costs a MySQL round-trip and, if the week's mark had
        # changed in between, could record a `blocked_session` and blank the phase of a student
        # who is mid-exam.
        assert state.pre_assessment_session_id is not None
        replay_items = await ctx.assessment_repo.get_items(state.pre_assessment_session_id)
        return {
            "phase": "pre_exam",
            "topic_id": ctx.topic_id,
            "pre_assessment_session_id": state.pre_assessment_session_id,
            "last_message": None,
            "last_items": _items_payload(await flow.items_view(ctx.question_repo, replay_items)),
        }

    try:
        gate = await check_attendance_gate(
            profile_adapter=ctx.profile_adapter,
            assessment_repo=ctx.assessment_repo,
            student_external_id=state.student_external_id,
        )
    except Exception as exc:  # SPEC §5.29: MySQL attendance failure -> block start
        return {"phase": "error", "last_error": f"attendance check failed: {exc}"}

    ATTENDANCE_CHECKS.labels(result="blocked" if gate.blocked else "present").inc()
    if gate.blocked:
        return {
            "phase": "blocked",
            "topic_id": ctx.topic_id,
            "week_id": gate.week_id,
            # D-216: `attendance_status` was declared in state and read by the `pre_intro`
            # narrative evidence, but nothing ever wrote it - the "Attendance:" evidence
            # line was dead code until this write.
            "attendance_status": gate.status.value,
            "blocked_session_id": gate.blocked_session_id,
            "last_message": gate.message,
            "last_items": None,
        }

    try:
        pre_exam = await build_pre_exam(
            question_repo=ctx.question_repo,
            assessment_repo=ctx.assessment_repo,
            student_external_id=state.student_external_id,
            topic_id=ctx.topic_id,
            rng=ctx.rng,
        )
    except AssessmentBuildError as exc:
        return {"phase": "error", "last_error": str(exc)}

    items = await ctx.assessment_repo.get_items(pre_exam.assessment_session_id)
    items_view = await flow.items_view(ctx.question_repo, items)
    return {
        "phase": "pre_exam",
        "topic_id": ctx.topic_id,
        "week_id": gate.week_id,
        "attendance_status": gate.status.value,
        "pre_assessment_session_id": pre_exam.assessment_session_id,
        "last_message": None,
        "last_items": _items_payload(items_view),
    }


async def resolve_attendance(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.6.3-§5.6.4: the user's choice once blocked.

    `acknowledge` finalizes immediately (§5.6.5) - no external action, no interrupt.
    `ask_branch_manager` pauses via a real `interrupt()` to preview the email before
    sending (SPEC §5.16's "Email approval is pending" checkpoint case); the session
    stays `blocked` either way (§5.6.4: "Session remains blocked").
    """
    ctx = _ctx(runtime)
    assert state.student_external_id is not None
    assert ctx.attendance_choice in ("acknowledge", "ask_branch_manager")

    if ctx.attendance_choice == "acknowledge":
        return {
            "phase": "blocked",
            "attendance_resolution": "absence_acknowledged",
            "last_message": attendance.ACKNOWLEDGED_MESSAGE,
        }

    # External ids only (D-020) - this is what `AsyncPostgresSaver` checkpoints to
    # Postgres. The router re-derives the human-readable email preview per request from
    # a live MySQL lookup, never cached here.
    decision = interrupt(
        {
            "type": "email_approval",
            "student_external_id": state.student_external_id,
            "week_id": state.week_id,
        }
    )
    approved = bool(decision.get("approved")) if isinstance(decision, dict) else False

    if approved:
        assert state.week_id is not None
        try:
            await attendance.send_attendance_email(
                profile_adapter=ctx.profile_adapter,
                mcp_registry=ctx.mcp_registry,
                mcp_call_repo=ctx.mcp_call_repo,
                student_external_id=state.student_external_id,
                week_id=state.week_id,
                caller_external_id=ctx.claims.sub,
            )
            message = attendance.EMAIL_SENT_MESSAGE
        except attendance.AttendanceEmailFailedError:
            # SPEC §5.29 "Gmail MCP failure -> Preserve draft" - the approval itself is
            # still recorded below (the user did approve); the failed *send* is a
            # separate fact captured by the `mcp_tool_calls` audit row's `success=False`.
            message = attendance.EMAIL_FAILED_MESSAGE
    else:
        message = attendance.EMAIL_DECLINED_MESSAGE

    await ctx.interrupt_repo.record(
        InterruptApproval(
            session_id=state.session_id,
            source_app="learning",
            interrupt_type="email_approval",
            decision="approved" if approved else "cancelled",
            decided_by_external_id=ctx.claims.sub,
        )
    )

    return {
        "phase": "blocked",
        "attendance_resolution": "email_requested",
        "last_message": message,
    }


def _study_narrative_marker(state: LearningState, result: flow.AnswerResult) -> dict | None:
    """The ids-only description of which `study_step`/`study_outro` narrative this turn's
    `flow.advance_study` result should fire, or None if none. Pure: no I/O, no Bedrock, no
    grade or skill names (those are PII-adjacent and are resolved only when the narrative
    is actually generated). `result.items is not None` alongside `phase == "post_exam"`
    distinguishes a genuine study-completion transition from an ordinary post-exam answer.
    """
    if result.new_target_skill_id is not None:
        assert result.target_skill_id is not None
        return {
            "stage": "study_step",
            "completed_skill_id": result.target_skill_id,
            "target_skill_id": result.new_target_skill_id,
        }
    if result.phase == "post_exam" and result.items is not None:
        assert state.study_session_id is not None
        return {"stage": "study_outro", "study_session_id": state.study_session_id}
    return None


async def _study_narrative_update(
    ctx: TurnContext,
    state: LearningState,
    result: flow.AnswerResult,
    bedrock_spend_cents: float,
) -> tuple[dict, float]:
    """S26 (plan §18-L7): decide and apply the `study_step`/`study_outro` narrative for
    `submit_answer`'s immediate-correct path and `intervention_choice`'s resumed path.

    D-217: under `ctx.defer_study_narrative` (real Bedrock) the ~1.5s narrative call is
    kept off the answer's critical path - the returned update carries an ids-only
    `pending_study_narrative` marker and the route hands it to the background scheduler.
    Under the mock provider it fires inline exactly as before, so every existing test
    still sees `stage_narrative` on the turn that produced it. Returns
    `(update_fragment, updated_bedrock_spend_cents)`.
    """
    assert state.student_external_id is not None
    marker = _study_narrative_marker(state, result)
    if marker is None:
        return {}, bedrock_spend_cents

    if ctx.defer_study_narrative:
        return {"pending_study_narrative": marker}, bedrock_spend_cents

    payload, related = await stage_narrative.payload_from_marker(
        profile_adapter=ctx.profile_adapter,
        curriculum_repo=ctx.curriculum_repo,
        study_repo=ctx.study_repo,
        student_external_id=state.student_external_id,
        marker=marker,
    )
    text, evidence, spend = await _fire_stage_narrative(
        ctx, state, payload, bedrock_spend_cents, related_skill_id=related
    )
    return {"stage_narrative": text, "stage_narrative_evidence": evidence}, spend


async def submit_answer(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """Grades the current phase's answer and advances phases via `flow.submit_answer`.

    A study-phase incorrect answer returns with `phase` still `"study"` and
    `last_is_correct=False` - the conditional edge in `build.py` routes that combination
    to `intervention_choice` instead of `END` (SPEC §5.11.3).
    """
    ctx = _ctx(runtime)
    assert ctx.question_variant_id is not None
    assert ctx.selected_option is not None
    assert ctx.response_time_ms is not None
    assert ctx.idempotency_key is not None
    assert state.student_external_id is not None
    submitted_phase = state.phase

    try:
        result = await flow.submit_answer(
            learning_session=state,
            question_variant_id=ctx.question_variant_id,
            selected_option=ctx.selected_option,
            response_time_ms=ctx.response_time_ms,
            idempotency_key=ctx.idempotency_key,
            assessment_repo=ctx.assessment_repo,
            study_repo=ctx.study_repo,
            mastery_repo=ctx.mastery_repo,
            question_repo=ctx.question_repo,
            rng=ctx.rng,
        )
    except StudyPlanBuildError as exc:
        return {"phase": "error", "last_error": str(exc)}

    # S25 (plan §9): episodic events for the answer itself, and - only when
    # `flow.advance_study` ran synchronously here (the immediate-correct study path;
    # an incorrect study answer pauses for `intervention_choice` instead, which emits
    # its own `study_outcome`) - the resolved skill line's outcome.
    await memory_events.emit_answer_submitted(
        ctx.memory_repo,
        ctx.question_repo,
        student_external_id=state.student_external_id,
        session_id=state.session_id,
        question_variant_id=ctx.question_variant_id,
        is_correct=result.is_correct,
        response_time_ms=ctx.response_time_ms,
        phase=submitted_phase,
    )
    if result.outcome_label is not None:
        assert result.target_skill_id is not None
        await memory_events.emit_study_outcome(
            ctx.memory_repo,
            ctx.question_repo,
            student_external_id=state.student_external_id,
            session_id=state.session_id,
            question_variant_id=ctx.question_variant_id,
            target_skill_id=result.target_skill_id,
            outcome_label=result.outcome_label,
        )

    narrative_update, bedrock_spend_cents = await _study_narrative_update(
        ctx, state, result, state.bedrock_spend_cents
    )
    update: dict = {
        "phase": result.phase,
        "topic_id": state.topic_id,
        "pre_assessment_session_id": state.pre_assessment_session_id,
        "study_session_id": state.study_session_id,
        "post_assessment_session_id": state.post_assessment_session_id,
        "last_is_correct": result.is_correct,
        "last_learning_gain": (
            _gain_payload(result.learning_gain) if result.learning_gain is not None else None
        ),
        "last_study_attempt_id": result.study_attempt_id,
        "last_message": result.message,
        "bedrock_spend_cents": bedrock_spend_cents,
        **narrative_update,
    }
    # S23 fix: `result.items is None` means "no new question this turn" (every pre/post-
    # exam answer under free navigation, D-064; a wrong study answer pausing for
    # intervention_choice) - it does NOT mean "nothing is current". Omitting the key
    # entirely leaves the `last_items` channel holding its previous value (LangGraph's
    # default `LastValue` merge only touches keys actually present in the returned dict),
    # so a refresh/resume mid-exam or mid-ladder still has real question content to show.
    # Explicitly writing `None` here used to silently erase the pre/post-exam batch (or
    # the in-progress study question) from the checkpoint the instant any answer that
    # doesn't hand back new items was submitted.
    if result.items is not None:
        update["last_items"] = _items_payload(result.items)
    return update


async def finalize_exam(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """S22 (SPEC §5.9/§5.13, D-064): the explicit "submit exam" action - see
    `flow.finalize_exam`'s docstring for what it does. Only reached as a top-level entry
    action (`entry_action="finalize_exam"`), never a conditional-edge target.
    """
    ctx = _ctx(runtime)
    result = await flow.finalize_exam(
        learning_session=state,
        confirm_unanswered=ctx.confirm_unanswered,
        now=datetime.now(UTC),
        assessment_repo=ctx.assessment_repo,
        study_repo=ctx.study_repo,
        mastery_repo=ctx.mastery_repo,
        question_repo=ctx.question_repo,
        rng=ctx.rng,
        memory_repo=ctx.memory_repo,
    )
    if result is None:
        # Already finalized (a retried call) - re-serve the existing checkpointed state
        # verbatim, no recompute, no side effects (same pattern `resume_view` uses).
        return {}

    EXAM_COMPLETIONS.labels(phase="pre" if result.session_type == "pre_exam" else "post").inc()

    assert state.student_external_id is not None
    await memory_events.emit_exam_finalized(
        ctx.memory_repo,
        student_external_id=state.student_external_id,
        session_id=state.session_id,
        topic_id=state.topic_id,
        session_type=result.session_type,
        raw_score=result.raw_score,
    )

    bedrock_spend_cents = state.bedrock_spend_cents
    grade = await _grade_for_narrative(ctx, state.student_external_id)
    narrative_text: str | None = None
    narrative_evidence: list[str] = []

    if result.session_type == "pre_exam":
        # S26 (plan §18-L7): `pre_outro` - the study plan's own weakest-first ranked
        # target skills (§5.11.2 rule 1) are both "the student's actual weak topics"
        # and "the actual adaptation" (the first one is what study serves next).
        # Deliberately no numeric score here: `result.raw_score` (`_complete_pre_exam`'s
        # own field) is a 0-1 accuracy *fraction*, a different scale than the raw-count
        # `pre_raw_score` the `post_outro` narrative below reports from the real
        # `LearningGain` row (`learning_gain.py::compute_learning_gain`) - reusing the
        # same payload field name for both would show a confusing "0.8" here against an
        # "8.0" later for what looks like the same number to a student.
        target_skill_ids = result.target_skill_ids or []
        weak_skill_names = [await _skill_name(ctx, sid) for sid in target_skill_ids]
        narrative_text, narrative_evidence, bedrock_spend_cents = await _fire_stage_narrative(
            ctx,
            state,
            StageNarrativePayload(
                stage="pre_outro",
                grade=grade,
                weak_skill_names=weak_skill_names,
                target_skill_name=weak_skill_names[0] if weak_skill_names else None,
            ),
            bedrock_spend_cents,
        )

    if result.learning_gain is not None:
        await memory_events.emit_learning_gain_computed(
            ctx.memory_repo,
            student_external_id=state.student_external_id,
            session_id=state.session_id,
            topic_id=state.topic_id,
            weighted_gain=result.learning_gain.weighted_gain,
            unresolved_skills=result.learning_gain.unresolved_skills,
        )
        # S25 (plan §9 trigger (a)): a post-exam completion is exactly one full
        # pre->study->post cycle, so this cycle's events are consolidated now rather than
        # waiting for the weekly batch.
        #
        # D-208: **scheduled, not awaited.** The comment that used to sit here said "Never
        # blocks the response", which was true of a *failure* - `consolidate_student_session`
        # swallows `BedrockGatewayError` - and false of the latency. Measured on staging:
        # `POST /exam/finalize` at 65-81 s, of which 61.5 s was this one call timing out
        # three times over. Nothing in the response depends on it; the learning gain the
        # results screen renders was computed deterministically above.
        #
        # The ordering that mattered still holds. Consolidation screens each proposed
        # ability fact against the measured mastery score for the same skill (AUD-L-13,
        # D-156), and this still runs after the cycle's mastery recompute - the scheduler
        # reads mastery from the database when it runs, and the recompute has committed by
        # then, so the floor still compares against this cycle's numbers.
        assert ctx.tutor_chat_repo is not None
        scheduler: ConsolidationScheduler = ctx.consolidation_scheduler or (
            InlineConsolidationScheduler(
                memory_repo=ctx.memory_repo,
                mastery_repo=ctx.mastery_repo,
                tutor_chat_repo=ctx.tutor_chat_repo,
                gateway=ctx.bedrock_gateway,
            )
        )
        await scheduler.schedule(
            student_external_id=state.student_external_id,
            session_id=state.session_id,
        )
        # Deliberately no longer added to `bedrock_spend_cents`: a scheduled call has not
        # happened yet, so attributing its cost to this turn's total would be a guess. The
        # background runner logs its own `cost_cents`, and the per-day chat ceiling - the
        # only budget a student can actually exhaust - never counted consolidation anyway.

        # S26: `post_outro` - the full SPEC §5.13.3 gain, not just the pre-exam's
        # weakest skills, is the richest evidence source of the three narrative moments.
        gain = result.learning_gain
        unresolved_names = [await _skill_name(ctx, sid) for sid in gain.unresolved_skills]
        relevant_facts: list[str] = []
        for skill_id in gain.unresolved_skills:
            fact = await _resolve_relevant_fact(ctx, state.student_external_id, skill_id)
            if fact is not None:
                relevant_facts.append(fact)
        narrative_text, narrative_evidence, bedrock_spend_cents = await _fire_stage_narrative(
            ctx,
            state,
            StageNarrativePayload(
                stage="post_outro",
                grade=grade,
                weak_skill_names=unresolved_names,
                pre_raw_score=gain.pre_raw_score,
                post_raw_score=gain.post_raw_score,
                raw_gain=gain.raw_gain,
                # AUD-L-08: a flagged gain (`unmeasurable_out_of_range`) is not a
                # normalized gain and must not shape narrative text a student reads -
                # the payload gets None, same as the `not_applicable_pre_max` case.
                normalized_gain=(
                    gain.normalized_gain if gain.normalized_gain_status is None else None
                ),
                independent_correct_rate=gain.independent_correct_rate,
                relevant_learning_facts=relevant_facts,
            ),
            bedrock_spend_cents,
        )
        LEARNING_GAIN.observe(gain.weighted_gain)
        SESSIONS_COMPLETED.inc()
        SESSION_COST_CENTS.observe(bedrock_spend_cents)

    update: dict = {
        "phase": result.phase,
        "study_session_id": state.study_session_id,
        "post_assessment_session_id": state.post_assessment_session_id,
        "last_learning_gain": (
            _gain_payload(result.learning_gain) if result.learning_gain is not None else None
        ),
        "last_message": result.message,
        "bedrock_spend_cents": bedrock_spend_cents,
    }
    if narrative_text is not None:
        update["stage_narrative"] = narrative_text
        update["stage_narrative_evidence"] = narrative_evidence
    # Same "omit rather than clear" fix as `submit_answer` above - a post-exam finalize's
    # `items=None` (transitioning to phase="completed") is genuinely nothing-to-show
    # (`ResultsScreen` never reads `items`), but omitting is just as correct there and
    # keeps this node consistent with `submit_answer`'s rule.
    if result.items is not None:
        update["last_items"] = _items_payload(result.items)
    return update


async def _video_intervention(
    ctx: TurnContext, attempt: StudyAttempt, session_spend_cents: float
) -> tuple[dict, float]:
    """SPEC §5.11.6/§5.18.3: look up an approved video for the attempt's skill via the
    real Postgres catalog + `youtube_catalog.search` (metadata filter + pgvector rank,
    no real-time YouTube call), or return the verbatim fallback message when none is
    available.
    """
    variant = await ctx.question_repo.get_variant(attempt.question_variant_id)
    assert variant is not None
    template = await ctx.question_repo.get_template(variant.question_template_id)
    assert template is not None
    skill = await ctx.curriculum_repo.get_skill(template.skill_id)
    assert skill is not None

    # S27 query enrichment (SPEC §5.18.3): misconception tag + grade band + mastery
    # state, when available - all three come from data this node already has cheap
    # access to (no extra Bedrock/DB round trip beyond the one `get_mastery` lookup).
    mastery = await ctx.mastery_repo.get_mastery(attempt.student_external_id, template.skill_id)
    video, cost = await video_catalog.search_video(
        repo=ctx.youtube_repo,
        gateway=ctx.bedrock_gateway,
        mcp_call_repo=ctx.mcp_call_repo,
        caller_external_id=attempt.student_external_id,
        skill_id=template.skill_id,
        skill_name=skill.name,
        difficulty=template.difficulty_label,
        session_spend_cents=session_spend_cents,
        misconception_tag=topic_resolver.resolve_misconception_tag(
            template, variant, attempt.selected_option
        ),
        grade_band=template.grade_band,
        mastery_state=topic_resolver.resolve_mastery_state(mastery),
    )
    if video is None:
        return {"type": "video", "message": video_catalog.FALLBACK_MESSAGE}, cost
    return {
        "type": "video",
        "video_title": video.title,
        "video_url": video.url,
        "video_source": video.source,
    }, cost


async def _resolve_relevant_fact(
    ctx: TurnContext, student_external_id: str, skill_id: str
) -> str | None:
    """S25 (plan §9) read path: the student's top-confidence `active` semantic-memory
    fact for this skill, or `None` if none exists yet - `MemoryRepository.
    top_fact_for_skill` already excludes `provisional`/`contested`/`superseded`/expired
    facts, so anything this returns is safe to hand straight to a Bedrock payload's
    `relevant_learning_fact` field.
    """
    fact = await ctx.memory_repo.top_fact_for_skill(student_external_id, skill_id)
    return fact.fact_text if fact is not None else None


def _canonical_hint_ladder(template: QuestionTemplate) -> list[str]:
    """SPEC §5.11.4/S21: authored templates carry their own S20-generated ladder;
    shape templates use the hand-authored, per-shape static ladder (`hint_ladders.py`) -
    never invented, never varying by the specific sampled numbers.
    """
    if template.authoring_mode == "authored":
        assert template.hint_ladder is not None, "authored template missing its hint_ladder"
        return template.hint_ladder
    return SHAPE_HINT_LADDERS[template.solution_function]


async def _hint_round(
    ctx: TurnContext, attempt: StudyAttempt, level: int, bedrock_spend_cents: float
) -> tuple[dict, float]:
    """Generates one level of the within-question hint ladder (S21) - `level` is
    1-based, the level about to be served (already incremented past whatever was last
    served for this variant). Records a `hint_events` row regardless of whether the
    result was personalized or fell back to canonical text (D-026-style "every attempt
    gets an audit row" posture).
    """
    variant = await ctx.question_repo.get_variant(attempt.question_variant_id)
    assert variant is not None
    template = await ctx.question_repo.get_template(variant.question_template_id)
    assert template is not None
    ladder = _canonical_hint_ladder(template)
    # A caller that miscounts (the chat path reads its level from `hint_events`, the
    # button path from the checkpoint - D-072 records that they can drift) must get the
    # deepest hint again, never an IndexError past the ladder.
    level = min(level, len(ladder))
    canonical_text = ladder[level - 1]
    next_canonical_text = ladder[level] if level < len(ladder) else None

    context = await topic_resolver.resolve_tutor_context(
        profile_adapter=ctx.profile_adapter,
        question_repo=ctx.question_repo,
        curriculum_repo=ctx.curriculum_repo,
        mastery_repo=ctx.mastery_repo,
        student_external_id=attempt.student_external_id,
        question_variant_id=attempt.question_variant_id,
        selected_option=attempt.selected_option,
    )
    misconception_tag = topic_resolver.resolve_misconception_tag(
        template, variant, attempt.selected_option
    )
    correct_answer_text = await topic_resolver.resolve_correct_answer_text(
        question_repo=ctx.question_repo, question_variant_id=attempt.question_variant_id
    )
    prior_events = await ctx.hint_event_repo.get_events_for_attempt(attempt.attempt_id)
    previous_summaries = [event.personalized_hint_text for event in prior_events]
    relevant_fact = await _resolve_relevant_fact(
        ctx, attempt.student_external_id, template.skill_id
    )

    hint, cost, was_personalized = await tutor.generate_personalized_hint(
        gateway=ctx.bedrock_gateway,
        context=context,
        canonical_hint_text=canonical_text,
        next_canonical_hint_text=next_canonical_text,
        hint_level=level,
        attempt_count=attempt.retry_count + 1,
        misconception_tag=misconception_tag,
        previous_hint_summaries=previous_summaries,
        correct_answer_text=correct_answer_text,
        session_spend_cents=bedrock_spend_cents,
        relevant_learning_fact=relevant_fact,
    )

    await ctx.hint_event_repo.record(
        HintEvent(
            student_external_id=attempt.student_external_id,
            study_attempt_id=attempt.attempt_id,
            question_variant_id=attempt.question_variant_id,
            hint_level=level,
            canonical_hint_text=canonical_text,
            personalized_hint_text=hint.hint_text,
            misconception_tag=misconception_tag,
            was_personalized=was_personalized,
        )
    )

    content = {
        "type": "hint",
        **hint.model_dump(),
        "hint_level": level,
        "max_hint_level": len(ladder),
    }
    return content, cost


async def _generate_intervention_content(
    ctx: TurnContext,
    attempt: StudyAttempt,
    choice_value: str,
    level: int,
    bedrock_spend_cents: float,
) -> tuple[dict, float]:
    """SPEC §5.11.4-§5.11.6: hint/solution content, or a §5.11.6 catalog video (or its
    fallback message). Reads `question_variant_id`/`selected_option`/`student_external_id`
    from the already-recorded `attempt` row, never from `ctx` - `ctx.question_variant_id`
    isn't guaranteed set on the `/respond` call that resumes this pause (D-021's replay rule
    only guarantees checkpointed state, not this turn's `TurnContext`, survives to after
    `interrupt()` returns).
    """
    if choice_value == "video":
        return await _video_intervention(ctx, attempt, bedrock_spend_cents)

    if choice_value == "hint":
        return await _hint_round(ctx, attempt, level, bedrock_spend_cents)

    context = await topic_resolver.resolve_tutor_context(
        profile_adapter=ctx.profile_adapter,
        question_repo=ctx.question_repo,
        curriculum_repo=ctx.curriculum_repo,
        mastery_repo=ctx.mastery_repo,
        student_external_id=attempt.student_external_id,
        question_variant_id=attempt.question_variant_id,
        selected_option=attempt.selected_option,
    )
    correct_answer_text = await topic_resolver.resolve_correct_answer_text(
        question_repo=ctx.question_repo, question_variant_id=attempt.question_variant_id
    )
    variant = await ctx.question_repo.get_variant(attempt.question_variant_id)
    assert variant is not None
    template = await ctx.question_repo.get_template(variant.question_template_id)
    assert template is not None

    # D-207: an authored template already carries a solution the S20 pipeline verified
    # before approval, so re-deriving it with an LLM is both worse and paid for. Prefer
    # the stored one; `stored_solution` returns None for shape templates (which have
    # none) and for a stored blob that fails its own re-check, and both fall through to
    # generation below.
    stored = tutor.stored_solution(template.canonical_solution, correct_answer_text)
    if stored is not None:
        return {"type": "solution", **stored.model_dump()}, 0.0

    relevant_fact = await _resolve_relevant_fact(
        ctx, attempt.student_external_id, template.skill_id
    )
    solution, cost = await tutor.generate_solution(
        gateway=ctx.bedrock_gateway,
        context=context,
        correct_answer_text=correct_answer_text,
        session_spend_cents=bedrock_spend_cents,
        relevant_learning_fact=relevant_fact,
    )
    return {"type": "solution", **solution.model_dump()}, cost


async def intervention_choice(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """SPEC §5.11.3: pauses for the hint/solution/video choice on an incorrect study
    answer, generates that content (S8), applies the choice to the attempt
    `submit_answer` already recorded, and runs the same phase-completion tail a correct
    answer would have run immediately.

    Only reached via the conditional edge from `submit_answer` (SPEC §5.16's "Student
    exits before selecting hint, solution, or video" checkpoint case) - never a top-level
    entry action, since it isn't something a client chooses to invoke directly.

    S21: a `"hint"` choice below the ladder's final level does NOT run the retry-ladder
    tail below - it returns with `hint_ladder_awaiting_choice=True`, and
    `graph/build.py`'s conditional edge routes straight back to this same node for a
    fresh superstep (a brand-new node execution, hitting its own `interrupt()`
    immediately - no replay-duplication risk, unlike a `while` loop inside one
    invocation would have, D-021 gotcha #1). Only `"solution"`/`"video"`/`"continue"`,
    or a `"hint"` choice that reaches the ladder's final level, runs `flow.advance_study`
    and ends the turn.
    """
    ctx = _ctx(runtime)
    assert state.last_study_attempt_id is not None

    choice = interrupt(
        {"type": "intervention_choice", "question_variant_id": ctx.question_variant_id}
    )
    choice_value = choice.get("choice") if isinstance(choice, dict) else None
    if choice_value not in ("hint", "solution", "video", "continue"):
        choice_value = None
    if choice_value in ("hint", "solution", "video"):
        SUPPORT_USAGE.labels(support_type=choice_value).inc()

    attempt = await ctx.study_repo.update_intervention_choice(
        state.last_study_attempt_id,
        hint_used=choice_value == "hint",
        video_used=choice_value == "video",
        solution_used=choice_value == "solution",
    )

    last_intervention: dict | None = None
    bedrock_spend_cents = state.bedrock_spend_cents
    assistance_levels = dict(state.assistance_level_by_variant)
    awaiting_next_hint = False

    if choice_value == "hint":
        current_level = assistance_levels.get(attempt.question_variant_id, 0)
        next_level = current_level + 1
        last_intervention, cost = await _generate_intervention_content(
            ctx, attempt, "hint", next_level, bedrock_spend_cents
        )
        bedrock_spend_cents += cost
        assistance_levels[attempt.question_variant_id] = next_level
        awaiting_next_hint = next_level < last_intervention["max_hint_level"]
    elif choice_value in ("solution", "video"):
        last_intervention, cost = await _generate_intervention_content(
            ctx, attempt, choice_value, 0, bedrock_spend_cents
        )
        bedrock_spend_cents += cost
    # choice_value in (None, "continue"): no new content this round - fall through to
    # advance_study below, same as an unrecognized/absent choice always has.

    # S25 (plan §9): one `intervention_chosen` event per resumed round - "continue"/no
    # choice isn't a support choice, so it doesn't get one.
    if choice_value in ("hint", "solution", "video"):
        hint_level = (
            assistance_levels.get(attempt.question_variant_id) if choice_value == "hint" else None
        )
        await memory_events.emit_intervention_chosen(
            ctx.memory_repo,
            ctx.question_repo,
            student_external_id=attempt.student_external_id,
            session_id=state.session_id,
            question_variant_id=attempt.question_variant_id,
            choice=choice_value,
            hint_level=hint_level,
        )

    if awaiting_next_hint:
        return {
            "assistance_level_by_variant": assistance_levels,
            "hint_ladder_awaiting_choice": True,
            "last_intervention": last_intervention,
            "bedrock_spend_cents": bedrock_spend_cents,
        }

    # Runs the §5.11.7 retry ladder now that the support choice is recorded: labels this
    # attempt, recomputes mastery, and serves a retry / prerequisite remediation / the next
    # base skill / the post-exam.
    result = await flow.advance_study(
        learning_session=state,
        last_attempt_id=state.last_study_attempt_id,
        is_correct=False,
        assessment_repo=ctx.assessment_repo,
        study_repo=ctx.study_repo,
        mastery_repo=ctx.mastery_repo,
        question_repo=ctx.question_repo,
        rng=ctx.rng,
    )
    if result.outcome_label is not None:
        assert result.target_skill_id is not None
        await memory_events.emit_study_outcome(
            ctx.memory_repo,
            ctx.question_repo,
            student_external_id=attempt.student_external_id,
            session_id=state.session_id,
            question_variant_id=attempt.question_variant_id,
            target_skill_id=result.target_skill_id,
            outcome_label=result.outcome_label,
        )

    narrative_update, bedrock_spend_cents = await _study_narrative_update(
        ctx, state, result, bedrock_spend_cents
    )

    update = {
        "phase": result.phase,
        "study_session_id": state.study_session_id,
        "post_assessment_session_id": state.post_assessment_session_id,
        "last_is_correct": result.is_correct,
        "last_items": _items_payload(result.items) if result.items is not None else None,
        "last_message": result.message,
        "last_intervention": last_intervention,
        "bedrock_spend_cents": bedrock_spend_cents,
        "assistance_level_by_variant": assistance_levels,
        "hint_ladder_awaiting_choice": False,
        **narrative_update,
    }
    return update


async def resume_view(state: LearningState, runtime: Runtime[TurnContext]) -> dict:
    """Re-serves the last turn's response verbatim - no side effects, no DB writes.

    This is what makes `/resume` prove SPEC §5.16's checkpointing use case: killing the
    process mid-session and calling resume returns to the same pending question, read
    straight from the checkpoint instead of recomputing anything.
    """
    del runtime
    return {}


def _chat_reply_from_content(content: dict) -> str:
    """Turns a solution/video intervention dict (the same shapes `_generate_
    intervention_content` produces for the button panel) into one natural-language chat
    line - the chat transcript is uniform bubbles of text, never a mix of rich cards and
    text (unlike `AssistancePanel`, which renders solution steps/video links as
    structured markup).
    """
    if content["type"] == "video":
        if "video_title" in content:
            return (
                f"Here's a video that might help: {content['video_title']} "
                f"({content['video_url']})"
            )
        return content["message"]
    steps = "; ".join(f"{step['explanation']}" for step in content["steps"])
    return f"{steps} Answer: {content['final_answer']}"


@dataclass(frozen=True)
class ChatTurnResult:
    reply_text: str
    intent: str


async def run_chat_turn(
    ctx: TurnContext,
    *,
    student_external_id: str,
    learning_session_id: str,
    bedrock_spend_cents: float,
) -> ChatTurnResult:
    """S24 (SPEC §5.12/§5.30.1 D-072): contextual, on-question learning chat.

    A plain service call, **not** an `ainvoke` graph turn (same "not a graph turn"
    precedent as `flow.mark_item_skipped`/`mark_item_flagged`, S22/S23) - a chat message
    has no routing consequence, and this exact assistance surface is routinely reachable
    while the graph is *already paused* at `intervention_choice`'s `interrupt()` (the
    same wrong-answer state the button panel shows). A fresh top-level `ainvoke` - or
    even `graph.aupdate_state` - on a thread with a pending task silently discards it
    (confirmed empirically this session: a scripted check showed `/respond` 409 "no
    interrupt is pending" immediately after one `aupdate_state` call) - so this function
    never touches the graph at all, checkpoint or otherwise.

    Two consequences of not touching the checkpoint:
    - Hint-ladder position is read from `hint_event_repo.get_events_for_attempt` (the
      durable audit table), not `LearningState.assistance_level_by_variant` - correct
      for chat-only usage, but if a student mixes chat and the original button panel for
      the *same* wrong attempt in the *same* turn cycle, the button panel's own
      checkpoint-based level (unaware of chat's rows) can drift from what chat already
      served. Documented, not fixed this session - see DECISIONS.md D-072.
    - `bedrock_spend_cents` isn't persisted back for chat's own calls (same reason); the
      per-day ceiling below - backed by the real `tutor_chat_messages` table, not the
      checkpoint - is chat's actual cost control, stronger in some ways than the
      checkpoint-only per-session budget it doesn't update.

    Six intents, in the order they're checked: a safety-concern keyword match and the
    per-day cost ceiling both short-circuit before any Bedrock call at all; `off_topic`
    stops after the one intent-classification call; `request_hint`/`request_solution`/
    `request_video`/`why_wrong` all require a real, most-recently-*wrong* `StudyAttempt`
    for the current question (the same precondition the button-panel `intervention_
    choice` flow already enforces) - absent one, chat answers with a fixed clarifying
    message rather than guessing. `request_hint`/`request_solution`/`request_video`
    reuse the exact same content-generation helpers `intervention_choice` uses, so a
    chat-driven hint records the identical `hint_events` row a button-driven one would -
    and sets the same `study_attempts` support flags, so outcome labels, mastery and the
    gain's dependency rates cannot tell the two surfaces apart (D-216).
    """
    assert ctx.tutor_chat_repo is not None
    assert ctx.student_message is not None
    assert ctx.question_variant_id is not None
    message = ctx.student_message
    cost = 0.0
    # Set once the turn holds a spend reservation; settled with the real cost on every
    # path out of this node (AUD-X-08).
    reservation: Reservation | None = None

    async def _finish(
        *, intent: str, reply_text: str, flagged: bool = False, resolved: bool = True
    ) -> ChatTurnResult:
        assert ctx.tutor_chat_repo is not None
        if reservation is not None:
            await ctx.cost_ledger.settle(reservation.reservation_id, cost)
        chat_message = await ctx.tutor_chat_repo.record(
            TutorChatMessage(
                student_external_id=student_external_id,
                learning_session_id=learning_session_id,
                question_variant_id=ctx.question_variant_id,
                intent=intent,
                redacted_student_message=message,
                reply_text=reply_text,
                cost_cents=cost,
                flagged_for_review=flagged,
            )
        )
        # S25 (plan §9): intent + resolution only - the message text stays in
        # `tutor_chat_messages` (see `memory_events.emit_chat_turn`'s own docstring).
        await memory_events.emit_chat_turn(
            ctx.memory_repo,
            ctx.question_repo,
            student_external_id=student_external_id,
            session_id=learning_session_id,
            question_variant_id=ctx.question_variant_id,
            intent=intent,
            resolved=resolved,
            tutor_chat_message_id=chat_message.message_id,
        )
        return ChatTurnResult(reply_text=reply_text, intent=intent)

    if tutor_chat_service.screen_for_safety_concern(message):
        return await _finish(
            intent="safety_concern",
            reply_text=tutor_chat_service.SAFETY_RESPONSE,
            flagged=True,
            resolved=False,
        )

    # AUD-X-08: reserve this turn's worst-case cost before making any call. The old check
    # read `tutor_chat_messages` and then spent, with the cost row committed at request
    # teardown - so concurrent turns each read a stale total and each received a full
    # ceiling. The reservation commits immediately, so an in-flight turn is visible.
    try:
        reservation = await ctx.cost_ledger.reserve(
            scope=SCOPE_TUTOR_CHAT,
            subject_external_id=student_external_id,
            estimate_cents=tutor_chat_service.TURN_RESERVATION_ESTIMATE_CENTS,
            ceiling_cents=tutor_chat_service.DAILY_COST_CEILING_CENTS,
        )
    except CeilingReachedError:
        return await _finish(
            intent="cost_ceiling",
            reply_text=tutor_chat_service.CEILING_EXCEEDED_RESPONSE,
            resolved=False,
        )

    try:
        intent, call_cost = await tutor_chat_service.classify_intent(
            gateway=ctx.bedrock_gateway,
            redacted_message=message,
            session_spend_cents=bedrock_spend_cents + cost,
        )
        cost += call_cost
    except BedrockGatewayError as exc:
        logger.warning("chat intent classification fell back to off_topic: %s", exc)
        intent = "off_topic"
        cost += exc.cost_cents

    if intent == "off_topic":
        return await _finish(
            intent=intent, reply_text=tutor_chat_service.OFF_TOPIC_RESPONSE, resolved=False
        )

    attempt = await ctx.study_repo.get_latest_attempt_for_variant(
        student_external_id, ctx.question_variant_id
    )
    has_wrong_attempt = attempt is not None and not attempt.is_correct
    if not has_wrong_attempt:
        return await _finish(
            intent=intent,
            reply_text=tutor_chat_service.NEEDS_WRONG_ATTEMPT_MESSAGE,
            resolved=False,
        )
    assert attempt is not None

    if intent == "request_hint":
        prior_events = await ctx.hint_event_repo.get_events_for_attempt(attempt.attempt_id)
        variant = await ctx.question_repo.get_variant(attempt.question_variant_id)
        assert variant is not None
        template = await ctx.question_repo.get_template(variant.question_template_id)
        assert template is not None
        ladder_length = len(_canonical_hint_ladder(template))
        if len(prior_events) >= ladder_length:
            # The ladder is spent for this attempt (button hints count too - both paths
            # write `hint_events`). Answer deterministically and for free rather than
            # indexing past the ladder, which was a 500.
            return await _finish(
                intent=intent,
                reply_text=tutor_chat_service.HINT_LADDER_EXHAUSTED_MESSAGE,
                resolved=False,
            )
        next_level = len(prior_events) + 1
        content, call_cost = await _hint_round(ctx, attempt, next_level, bedrock_spend_cents + cost)
        cost += call_cost
        # Chat-served support must leave the same durable trace button-served support
        # does, or everything downstream of `study_attempts.hint_used` (outcome labels,
        # independent mastery, gain dependency rates, the parent dashboard) records a
        # chat-assisted answer as unaided.
        await ctx.study_repo.update_intervention_choice(
            attempt.attempt_id, hint_used=True, video_used=False, solution_used=False
        )
        SUPPORT_USAGE.labels(support_type="hint").inc()
        reply_text = (
            f"{content['hint_text']} (hint {content['hint_level']} of "
            f"{content['max_hint_level']})"
        )
    elif intent in ("request_solution", "request_video"):
        choice_value = intent.removeprefix("request_")
        content, call_cost = await _generate_intervention_content(
            ctx, attempt, choice_value, 0, bedrock_spend_cents + cost
        )
        cost += call_cost
        await ctx.study_repo.update_intervention_choice(
            attempt.attempt_id,
            hint_used=False,
            video_used=choice_value == "video",
            solution_used=choice_value == "solution",
        )
        SUPPORT_USAGE.labels(support_type=choice_value).inc()
        reply_text = _chat_reply_from_content(content)
    else:
        assert intent in ("question_help", "why_wrong")
        context = await topic_resolver.resolve_tutor_context(
            profile_adapter=ctx.profile_adapter,
            question_repo=ctx.question_repo,
            curriculum_repo=ctx.curriculum_repo,
            mastery_repo=ctx.mastery_repo,
            student_external_id=student_external_id,
            question_variant_id=attempt.question_variant_id,
            selected_option=attempt.selected_option,
        )
        correct_answer_text = await topic_resolver.resolve_correct_answer_text(
            question_repo=ctx.question_repo, question_variant_id=attempt.question_variant_id
        )
        variant = await ctx.question_repo.get_variant(attempt.question_variant_id)
        assert variant is not None
        template = await ctx.question_repo.get_template(variant.question_template_id)
        assert template is not None
        relevant_fact = await _resolve_relevant_fact(ctx, student_external_id, template.skill_id)
        chat_fn = (
            tutor_chat_service.explain_why_wrong
            if intent == "why_wrong"
            else tutor_chat_service.generate_chat_reply
        )
        result, call_cost = await chat_fn(
            gateway=ctx.bedrock_gateway,
            context=context,
            redacted_message=message,
            correct_answer_text=correct_answer_text,
            session_spend_cents=bedrock_spend_cents + cost,
            relevant_learning_fact=relevant_fact,
        )
        cost += call_cost
        reply_text = result.reply_text

    return await _finish(intent=intent, reply_text=reply_text)
