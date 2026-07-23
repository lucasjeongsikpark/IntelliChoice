"""Graph-route unit tests for the S6/S7 LangGraph workflow (SPEC §5.5.1, Phase 7 §6.8
and Phase 8 §6.9 "Done when": graph-route tests cover every branch, no external action
fires before approval).

These exercise `resolve_student`, `select_topic`, and `resolve_attendance` directly
through a compiled graph backed by `InMemorySaver` and fake dependencies - no live
Postgres/MySQL required, so they always run (unlike the live-DB HTTP tests in
`test_learning_flow.py`). `intervention_choice` needs real assessment/study/mastery
repositories (it calls `flow.finish_study_turn`), so that one is covered by the live-DB
HTTP test instead.
"""

import asyncio

from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_adapters.fake_email import FakeEmailTransport
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_shared.auth import Audience, Role, TokenClaims
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.mcp import McpTool, McpToolRegistry
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from learning_api.graph.build import EntryInput, build_graph
from learning_api.graph.nodes import TurnContext
from learning_api.services import attendance

issuer = FakeTokenIssuer()
verifier = JwtTokenVerifier()


def _claims(sub: str, role: Role) -> TokenClaims:
    token = issuer.issue(sub=sub, role=role, audience=Audience.LEARNING)
    return verifier.verify(token, Audience.LEARNING)


class FakeProfileAdapter:
    """Minimal `ProfileAdapter` double: parent -> children map, student profiles,
    branches, plus an optional attendance override/failure for the attendance-gate
    branch tests.
    """

    def __init__(
        self,
        children_by_parent: dict[str, list[str]] | None = None,
        attendance: AttendanceStatus | Exception | None = None,
        students: dict[str, StudentProfile] | None = None,
        branches: dict[str, BranchInfo] | None = None,
    ) -> None:
        self._children_by_parent = children_by_parent or {}
        self._attendance = attendance
        self._students = students or {}
        self._branches = branches or {}

    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        return self._students.get(student_external_id)

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        raise NotImplementedError

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        return self._children_by_parent.get(parent_external_id, [])

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
        if isinstance(self._attendance, Exception):
            raise self._attendance
        assert self._attendance is not None
        return self._attendance

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None:
        return self._branches.get(branch_external_id)

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None:
        branch = self._branches.get(branch_external_id)
        return branch.manager_email if branch else None

    async def list_branches(self) -> list[BranchInfo]:
        return list(self._branches.values())


class FakeInterruptApprovalRepository:
    """No real Postgres needed - `resolve_attendance` only calls `.record()`."""

    def __init__(self) -> None:
        self.recorded: list[InterruptApproval] = []

    async def record(self, approval: InterruptApproval) -> InterruptApproval:
        self.recorded.append(approval)
        return approval


class FakeBlockedSessionAssessmentRepository:
    """No real Postgres needed - `select_topic`'s blocked branch only ever calls
    `create_blocked_session`, and `BlockedSession.blocked_session_id`'s Python-side
    `default=new_uuid` isn't applied until a real SQLAlchemy flush, so a bare model
    instance built without one needs its id filled in some other way.
    """

    async def create_blocked_session(self, blocked):
        blocked.blocked_session_id = "blocked-fake-1"
        return blocked


def _registry_for(transport: FakeEmailTransport) -> McpToolRegistry:
    """A real (not faked) `McpToolRegistry`, since it's pure/dependency-free logic -
    just registers `gmail.send_email` against whichever `FakeEmailTransport` a test
    wants to assert on.
    """
    registry = McpToolRegistry()
    registry.register(
        McpTool(name="gmail.send_email", args_model=EmailMessage, handler=transport.send)
    )
    return registry


def _turn_context(claims: TokenClaims, **kwargs) -> TurnContext:
    email_transport = kwargs.pop("email_transport", FakeEmailTransport())
    return TurnContext(
        claims=claims,
        profile_adapter=kwargs.pop("profile_adapter", FakeProfileAdapter()),
        assessment_repo=kwargs.pop("assessment_repo", None),  # type: ignore[arg-type]
        study_repo=None,  # type: ignore[arg-type]
        mastery_repo=None,  # type: ignore[arg-type]
        question_repo=None,  # type: ignore[arg-type]
        curriculum_repo=None,  # type: ignore[arg-type]
        youtube_repo=None,  # type: ignore[arg-type]
        hint_event_repo=None,  # type: ignore[arg-type]
        memory_repo=None,  # type: ignore[arg-type]
        stage_transition_repo=None,  # type: ignore[arg-type]
        interrupt_repo=kwargs.pop("interrupt_repo", FakeInterruptApprovalRepository()),
        mcp_registry=kwargs.pop("mcp_registry", _registry_for(email_transport)),
        mcp_call_repo=None,  # type: ignore[arg-type]
        bedrock_gateway=None,  # type: ignore[arg-type]
        rng=None,
        **kwargs,
    )


def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


async def _select_student(claims: TokenClaims, thread_id: str, **ctx_kwargs) -> dict:
    graph = build_graph(InMemorySaver())
    return await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_student"),
        config=_config(thread_id),
        context=_turn_context(claims, **ctx_kwargs),
    )


def test_student_self_select() -> None:
    claims = _claims("student-ext-1", Role.STUDENT)
    result = asyncio.run(_select_student(claims, "t-student-self"))
    assert result["phase"] == "student_selected"
    assert result["student_external_id"] == "student-ext-1"


def test_student_cannot_select_another_student() -> None:
    claims = _claims("student-ext-1", Role.STUDENT)
    try:
        asyncio.run(
            _select_student(claims, "t-student-cross", requested_student_id="student-ext-2")
        )
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


def test_parent_single_child_auto_selected() -> None:
    claims = _claims("parent-ext-1", Role.PARENT)
    adapter = FakeProfileAdapter(children_by_parent={"parent-ext-1": ["student-ext-1"]})
    result = asyncio.run(_select_student(claims, "t-parent-auto", profile_adapter=adapter))
    assert result["phase"] == "student_selected"
    assert result["student_external_id"] == "student-ext-1"


def test_parent_multi_child_pauses_for_interrupt() -> None:
    """SPEC §5.6.1/§5.16: multi-child parent pauses via a real `interrupt()` instead of
    an immediate error - the payload carries only external ids (D-020), never MySQL-
    sourced display data.
    """
    claims = _claims("parent-ext-2", Role.PARENT)
    adapter = FakeProfileAdapter(
        children_by_parent={"parent-ext-2": ["student-ext-2", "student-ext-3"]}
    )
    result = asyncio.run(_select_student(claims, "t-parent-multi", profile_adapter=adapter))
    interrupts = result["__interrupt__"]
    assert len(interrupts) == 1
    value = interrupts[0].value
    assert value["type"] == "child_selection"
    assert set(value["candidate_children"]) == {"student-ext-2", "student-ext-3"}
    assert "display_name" not in str(value)


async def _resume_child_selection(chosen: str) -> dict:
    claims = _claims("parent-ext-2", Role.PARENT)
    adapter = FakeProfileAdapter(
        children_by_parent={"parent-ext-2": ["student-ext-2", "student-ext-3"]}
    )
    graph = build_graph(InMemorySaver())
    cfg = _config("t-parent-multi-resume")
    await graph.ainvoke(
        EntryInput(session_id="t-parent-multi-resume", entry_action="select_student"),
        config=cfg,
        context=_turn_context(claims, profile_adapter=adapter),
    )
    return await graph.ainvoke(
        Command(resume=chosen), config=cfg, context=_turn_context(claims, profile_adapter=adapter)
    )


def test_parent_multi_child_resume_selects_child() -> None:
    result = asyncio.run(_resume_child_selection("student-ext-3"))
    assert result["phase"] == "student_selected"
    assert result["student_external_id"] == "student-ext-3"
    assert result["parent_external_id"] == "parent-ext-2"


def test_parent_multi_child_resume_rejects_unlinked_choice() -> None:
    try:
        asyncio.run(_resume_child_selection("student-ext-9"))
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


def test_parent_explicit_linked_child() -> None:
    claims = _claims("parent-ext-2", Role.PARENT)
    adapter = FakeProfileAdapter(
        children_by_parent={"parent-ext-2": ["student-ext-2", "student-ext-3"]}
    )
    result = asyncio.run(
        _select_student(
            claims,
            "t-parent-explicit",
            profile_adapter=adapter,
            requested_student_id="student-ext-3",
        )
    )
    assert result["phase"] == "student_selected"
    assert result["student_external_id"] == "student-ext-3"
    assert result["parent_external_id"] == "parent-ext-2"


def test_parent_cannot_select_unlinked_student() -> None:
    claims = _claims("parent-ext-2", Role.PARENT)
    adapter = FakeProfileAdapter(children_by_parent={"parent-ext-2": ["student-ext-2"]})
    try:
        asyncio.run(
            _select_student(
                claims,
                "t-parent-unlinked",
                profile_adapter=adapter,
                requested_student_id="student-ext-9",
            )
        )
        raise AssertionError("expected PermissionError")
    except PermissionError:
        pass


def test_tutor_role_resolves_without_scope_check() -> None:
    claims = _claims("tutor-ext-1", Role.TUTOR)
    result = asyncio.run(
        _select_student(claims, "t-tutor", requested_student_id="student-ext-1")
    )
    assert result["phase"] == "student_selected"
    assert result["student_external_id"] == "student-ext-1"


async def _select_topic(
    claims: TokenClaims, thread_id: str, attendance: AttendanceStatus | Exception
) -> dict:
    graph = build_graph(InMemorySaver())
    await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_student"),
        config=_config(thread_id),
        context=_turn_context(claims),
    )
    adapter = FakeProfileAdapter(attendance=attendance)
    return await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_topic"),
        config=_config(thread_id),
        context=_turn_context(claims, topic_id="linear_equations", profile_adapter=adapter),
    )


def test_attendance_failure_routes_to_error_not_a_crash() -> None:
    """SPEC §5.29: "MySQL attendance failure -> block learning start" - the node
    catches the failure and routes to an error phase instead of raising into the caller.
    """
    claims = _claims("student-ext-1", Role.STUDENT)
    result = asyncio.run(
        _select_topic(claims, "t-attendance-error", RuntimeError("mysql unreachable"))
    )
    assert result["phase"] == "error"
    assert "mysql unreachable" in result["last_error"]


_BRANCH = BranchInfo(
    branch_external_id="branch-ext-1",
    name="Main Branch",
    manager_email="manager@example.test",
    address="100 Learning Way, Springfield",
    latitude=39.7817,
    longitude=-89.6501,
)
_STUDENT = StudentProfile(
    student_external_id="student-ext-1",
    display_name="Ava Only",
    grade="3",
    branch_external_id="branch-ext-1",
)


async def _blocked_graph(saver: BaseCheckpointSaver, thread_id: str) -> tuple:
    claims = _claims("student-ext-1", Role.STUDENT)
    graph = build_graph(saver)
    await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_student"),
        config=_config(thread_id),
        context=_turn_context(claims),
    )
    await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_topic"),
        config=_config(thread_id),
        context=_turn_context(
            claims,
            topic_id="linear_equations",
            profile_adapter=FakeProfileAdapter(attendance=AttendanceStatus.ABSENT),
            assessment_repo=FakeBlockedSessionAssessmentRepository(),
        ),
    )
    return graph, claims


def test_attendance_acknowledge_needs_no_interrupt() -> None:
    """SPEC §5.6.5: acknowledging is immediate - no external action, so no `interrupt()`."""

    async def run() -> dict:
        graph, claims = await _blocked_graph(InMemorySaver(), "t-attendance-ack")
        adapter = FakeProfileAdapter(
            students={"student-ext-1": _STUDENT}, branches={"branch-ext-1": _BRANCH}
        )
        interrupt_repo = FakeInterruptApprovalRepository()
        result = await graph.ainvoke(
            EntryInput(session_id="t-attendance-ack", entry_action="resolve_attendance"),
            config=_config("t-attendance-ack"),
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="acknowledge",
                interrupt_repo=interrupt_repo,
            ),
        )
        assert "__interrupt__" not in result
        assert interrupt_repo.recorded == []
        return result

    result = asyncio.run(run())
    assert result["phase"] == "blocked"
    assert result["attendance_resolution"] == "absence_acknowledged"


def test_attendance_ask_branch_manager_pauses_then_sends_only_after_approval() -> None:
    """Phase 8 (§6.9) completion criterion: no external action before approval."""

    async def run() -> tuple:
        saver = InMemorySaver()
        graph, claims = await _blocked_graph(saver, "t-attendance-email")
        adapter = FakeProfileAdapter(
            students={"student-ext-1": _STUDENT}, branches={"branch-ext-1": _BRANCH}
        )
        transport = FakeEmailTransport()
        interrupt_repo = FakeInterruptApprovalRepository()
        cfg = _config("t-attendance-email")

        paused = await graph.ainvoke(
            EntryInput(session_id="t-attendance-email", entry_action="resolve_attendance"),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        value = paused["__interrupt__"][0].value
        assert value["type"] == "email_approval"
        assert value["student_external_id"] == "student-ext-1"
        # Nothing sent yet - the interrupt hasn't been approved.
        assert transport.sent == []
        assert interrupt_repo.recorded == []

        result = await graph.ainvoke(
            Command(resume={"approved": True}),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        return result, transport, interrupt_repo

    result, transport, interrupt_repo = asyncio.run(run())
    assert result["phase"] == "blocked"
    assert result["attendance_resolution"] == "email_requested"
    assert len(transport.sent) == 1
    assert transport.sent[0].recipient == "manager@example.test"
    assert "Ava Only" in transport.sent[0].body
    assert len(interrupt_repo.recorded) == 1
    assert interrupt_repo.recorded[0].decision == "approved"
    assert interrupt_repo.recorded[0].interrupt_type == "email_approval"


def test_attendance_email_declined_sends_nothing_but_records_decision() -> None:
    async def run() -> tuple:
        saver = InMemorySaver()
        graph, claims = await _blocked_graph(saver, "t-attendance-decline")
        adapter = FakeProfileAdapter(
            students={"student-ext-1": _STUDENT}, branches={"branch-ext-1": _BRANCH}
        )
        transport = FakeEmailTransport()
        interrupt_repo = FakeInterruptApprovalRepository()
        cfg = _config("t-attendance-decline")

        await graph.ainvoke(
            EntryInput(session_id="t-attendance-decline", entry_action="resolve_attendance"),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        result = await graph.ainvoke(
            Command(resume={"approved": False}),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        return result, transport, interrupt_repo

    result, transport, interrupt_repo = asyncio.run(run())
    assert result["phase"] == "blocked"
    assert transport.sent == []
    assert len(interrupt_repo.recorded) == 1
    assert interrupt_repo.recorded[0].decision == "cancelled"


class _FailingEmailTransport:
    """SPEC §5.29 "Gmail MCP failure -> Preserve draft" test double - mirrors
    `test_bedrock_gateway.py`'s style of deliberately-broken doubles."""

    def __init__(self) -> None:
        self.sent: list = []

    async def send(self, message) -> None:
        raise ConnectionError("smtp unavailable")


def test_attendance_email_send_failure_preserves_draft_and_still_records_approval() -> None:
    async def run() -> tuple:
        saver = InMemorySaver()
        graph, claims = await _blocked_graph(saver, "t-attendance-email-fail")
        adapter = FakeProfileAdapter(
            students={"student-ext-1": _STUDENT}, branches={"branch-ext-1": _BRANCH}
        )
        transport = _FailingEmailTransport()
        interrupt_repo = FakeInterruptApprovalRepository()
        cfg = _config("t-attendance-email-fail")

        await graph.ainvoke(
            EntryInput(session_id="t-attendance-email-fail", entry_action="resolve_attendance"),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        result = await graph.ainvoke(
            Command(resume={"approved": True}),
            config=cfg,
            context=_turn_context(
                claims,
                profile_adapter=adapter,
                attendance_choice="ask_branch_manager",
                email_transport=transport,
                interrupt_repo=interrupt_repo,
            ),
        )
        return result, interrupt_repo

    result, interrupt_repo = asyncio.run(run())
    assert result["phase"] == "blocked"
    assert result["last_message"] == attendance.EMAIL_FAILED_MESSAGE
    # The approval itself is still a real fact (the user did approve) - only the send
    # failed, which is a separate concern the `mcp_tool_calls` audit trail captures.
    assert len(interrupt_repo.recorded) == 1
    assert interrupt_repo.recorded[0].decision == "approved"
