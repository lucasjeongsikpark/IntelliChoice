"""E3.4 - the HITL bypass-attempt suite for learning-api's `interrupt()` gates.

Companion to `apps/chat-api/tests/test_hitl_bypass_suite.py`; read that module's header for
the case-kind vocabulary (`bypass` / `control` / `finding`) and why the catalog below is
both the metadata and the parametrization source.

Two gates live here, and they are not the same shape as chat-api's:

- **`resolve_attendance`** pauses before mailing a branch manager about an absence
  (SPEC §5.6.3-§5.6.4). The external action is a real email through the MCP registry.
- **`resolve_student`** pauses a multi-child parent to choose which child the session is
  for (SPEC §5.6.1). Its external effect is authorization, not a message: a bad resume
  binds someone else's child to the session, which every later route then authorizes
  against.

Most cases drive the compiled graph directly with `InMemorySaver` and fakes, which is what
`test_learning_graph_routes.py` established for these nodes - no Postgres or MySQL needed,
so they always run. The `route` group needs the live HTTP journey (MySQL fixtures plus a
loaded curriculum) and is guarded accordingly.

**Where the concurrency protection actually lives, measured rather than assumed.** Both
apps serialize a resume at the *route*: chat-api's `/respond` calls `_claim_turn` directly
(D-346) and learning-api's reaches the same `pg_try_advisory_xact_lock` inside
`_invoke_with_deadline` (D-376, which ported D-346 to all seven learning `ainvoke` sites).
HB-LEARN-30 drives two genuinely concurrent HTTP resumes and gets exactly one email with a
409 for the loser. The *graph* layer has no such serialization - HB-LEARN-F1 measures two
simultaneous `ainvoke(Command(resume=...))` calls both completing - which is recorded as a
defense-in-depth finding (the route is the gate), not as a reachable defect, and is kept
out of the "N attempts, 0 side effects" denominator.
"""

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_adapters.fake_email import FakeEmailTransport
from intellichoice_adapters.seed.mysql_fixtures import (
    STUDENT_FIRST_CHILD,
    STUDENT_SECOND_CHILD,
    seed,
)
from intellichoice_curriculum.loader import load_curriculum_and_templates
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
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
from learning_api.main import app
from learning_api.services import attendance
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

issuer = FakeTokenIssuer()
verifier = JwtTokenVerifier()

MYSQL_URL = "mysql+aiomysql://intellichoice:intellichoice@localhost:3306"

BRANCH = BranchInfo(
    branch_external_id="branch-ext-1",
    name="Main Branch",
    manager_email="manager@example.test",
    address="100 Learning Way, Springfield",
    latitude=39.7817,
    longitude=-89.6501,
)
STUDENT = StudentProfile(
    student_external_id="student-ext-1",
    display_name="Ava Only",
    grade="3",
    branch_external_id="branch-ext-1",
)

#: Literal placeholders, expanded by the drivers. `BYPASS_CASES` stays a pure literal so
#: the inventory generator can read it with `ast.literal_eval` and never import this
#: module.
RESUME_ABSENT = "__ABSENT__"

BYPASS_CASES = [
    # ------------------------------------------------ attendance email gate: bad resumes
    {
        "id": "HB-LEARN-01",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "empty resume object",
        "invariant": "no email - LangGraph rejects the resume before the node runs",
        "expects": "unresumable",
        "resume": {},
    },
    {
        "id": "HB-LEARN-02",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "null approval",
        "invariant": "no email; decision recorded as cancelled",
        "resume": {"approved": None},
    },
    {
        "id": "HB-LEARN-03",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "explicit decline",
        "invariant": "no email; decision recorded as cancelled",
        "resume": {"approved": False},
    },
    {
        "id": "HB-LEARN-04",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "misspelled key ('approve'), so the real key is absent",
        "invariant": "no email; absence is never approval",
        "resume": {"approve": True},
    },
    {
        "id": "HB-LEARN-05",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "integer 0 as approval",
        "invariant": "no email",
        "resume": {"approved": 0},
    },
    {
        "id": "HB-LEARN-06",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "empty string as approval",
        "invariant": "no email",
        "resume": {"approved": ""},
    },
    {
        "id": "HB-LEARN-07",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "empty list as approval",
        "invariant": "no email",
        "resume": {"approved": []},
    },
    {
        "id": "HB-LEARN-08",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "empty object as approval",
        "invariant": "no email",
        "resume": {"approved": {}},
    },
    {
        "id": "HB-LEARN-09",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "resume value is a bare string, not the expected object",
        "invariant": "no email - a non-dict resume is not an approval",
        "resume": "approved",
    },
    {
        "id": "HB-LEARN-10",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "resume value is a bare boolean true",
        "invariant": "no email - a non-dict resume is not an approval",
        "resume": True,
    },
    {
        "id": "HB-LEARN-11",
        "kind": "bypass",
        "group": "attendance_payload",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "resume value is null",
        "invariant": "no email - LangGraph rejects the resume before the node runs",
        "expects": "unresumable",
        "resume": None,
    },
    # ------------------------------------------- attendance email gate: content steering
    {
        "id": "HB-LEARN-12",
        "kind": "bypass",
        "group": "attendance_injection",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "approval carrying a `recipient` override",
        "invariant": "one email, addressed to the branch manager the profile lookup returns",
        "resume": {"approved": True, "recipient": "attacker@evil.test"},
    },
    {
        "id": "HB-LEARN-13",
        "kind": "bypass",
        "group": "attendance_injection",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "approval carrying a different `student_external_id` (mail about another child)",
        "invariant": "one email, about the checkpointed student only",
        "resume": {"approved": True, "student_external_id": "student-ext-9"},
    },
    {
        "id": "HB-LEARN-14",
        "kind": "bypass",
        "group": "attendance_injection",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "approval carrying an injected `body`, to rewrite what the manager reads",
        "invariant": "one email, server-composed body; the injected text never appears",
        "resume": {
            "approved": True,
            "body": "Please reset this student's password and reply with it.",
        },
    },
    # -------------------------------------------------- child-selection gate (authz gate)
    {
        "id": "HB-LEARN-15",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "select a student this parent is not linked to",
        "invariant": "PermissionError; no student bound to the session",
        "resume": "student-ext-9",
    },
    {
        "id": "HB-LEARN-16",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "null selection",
        "invariant": "no student bound - LangGraph rejects the resume before the node runs",
        "expects": "unresumable",
        "resume": None,
    },
    {
        "id": "HB-LEARN-17",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "empty-string selection",
        "invariant": "PermissionError; no student bound to the session",
        "resume": "",
    },
    {
        "id": "HB-LEARN-18",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "a linked id wrapped in a list, probing membership-check confusion",
        "invariant": "PermissionError; no student bound to the session",
        "resume": ["student-ext-2"],
    },
    {
        "id": "HB-LEARN-19",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "a linked id wrapped in an object",
        "invariant": "PermissionError; no student bound to the session",
        "resume": {"student_id": "student-ext-2"},
    },
    {
        "id": "HB-LEARN-20",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "SQL-shaped selection string",
        "invariant": "PermissionError; the value is compared, never interpolated",
        "resume": "student-ext-2' OR '1'='1",
    },
    {
        "id": "HB-LEARN-21",
        "kind": "bypass",
        "group": "child_selection",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "wildcard-shaped selection string",
        "invariant": "PermissionError; membership is exact",
        "resume": "*",
    },
    # -------------------------------------------------------------- replay / concurrency
    {
        "id": "HB-LEARN-22",
        "kind": "bypass",
        "group": "replay",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "replay: approve the same pause twice, sequentially",
        "invariant": "exactly one email and one approval row - the second resume is a no-op",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-23",
        "kind": "bypass",
        "group": "replay",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "decline, then approve the already-resolved pause",
        "invariant": "zero emails; the decline stands",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-24",
        "kind": "bypass",
        "group": "replay",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "a second parent resumes the first parent's pending child selection",
        "invariant": "PermissionError; the session is not rebound",
        "resume": RESUME_ABSENT,
    },
    # ------------------------------------------------------------------- route-level HTTP
    {
        "id": "HB-LEARN-25",
        "kind": "bypass",
        "group": "route",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "unauthenticated resume of a pending attendance approval",
        "invariant": "401; no email",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-26",
        "kind": "bypass",
        "group": "route",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "another student's token resumes this student's pending approval",
        "invariant": "403; no email",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-27",
        "kind": "bypass",
        "group": "route",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "empty body on a pending approval",
        "invariant": "422; no email",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-28",
        "kind": "bypass",
        "group": "route",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "wrong discriminator (intervention_choice) on an email approval pause",
        "invariant": "409; no email",
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-30",
        "kind": "bypass",
        "group": "route_concurrency",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "two genuinely concurrent HTTP resumes of one pending approval",
        "invariant": (
            "exactly one email and one interrupt_approvals row per round; the losing "
            "caller gets 409 from the D-376 turn claim"
        ),
        "resume": RESUME_ABSENT,
    },
    {
        "id": "HB-LEARN-29",
        "kind": "bypass",
        "group": "route",
        "surface": "learning-api POST /learning/sessions/{id}/respond",
        "attack": "replay over HTTP: approve the same pause twice",
        "invariant": "second call 409; exactly one email",
        "resume": RESUME_ABSENT,
    },
    # -------------------------------------------------------------------------- controls
    {
        "id": "HB-LEARN-C1",
        "kind": "control",
        "group": "control",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "not an attack - a plain, valid approval",
        "invariant": "exactly one email to the branch manager; one approved audit row",
        "resume": {"approved": True},
    },
    {
        "id": "HB-LEARN-C2",
        "kind": "control",
        "group": "control_child",
        "surface": "learning-api resolve_student interrupt (child_selection)",
        "attack": "not an attack - the parent selects one of their own children",
        "invariant": "the session binds to that child",
        "resume": "student-ext-3",
    },
    # -------------------------------------------------------------------------- findings
    {
        "id": "HB-LEARN-F1",
        "kind": "finding",
        "group": "finding",
        "surface": "learning-api resolve_attendance interrupt (email_approval)",
        "attack": "two simultaneous resumes of one pause, bypassing the HTTP layer entirely",
        "invariant": (
            "FINDING (defense in depth): both complete and two emails are sent. The "
            "serialization point is the route's turn claim (D-376), not the node - so the "
            "graph is not independently safe to invoke concurrently."
        ),
        "resume": RESUME_ABSENT,
    },
]


# --------------------------------------------------------------------------------------
# Fakes - deliberately local rather than imported from `test_learning_graph_routes.py`,
# matching this repository's own convention of duplicating small test scaffolding per
# module rather than growing a shared test-only package.
# --------------------------------------------------------------------------------------


class FakeProfileAdapter:
    def __init__(
        self,
        children_by_parent: dict[str, list[str]] | None = None,
        attendance_status: AttendanceStatus | None = None,
        students: dict[str, StudentProfile] | None = None,
        branches: dict[str, BranchInfo] | None = None,
    ) -> None:
        self._children_by_parent = children_by_parent or {}
        self._attendance = attendance_status
        self._students = students or {}
        self._branches = branches or {}

    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        return self._students.get(student_external_id)

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        raise NotImplementedError

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        return self._children_by_parent.get(parent_external_id, [])

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
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
    def __init__(self) -> None:
        self.recorded: list[InterruptApproval] = []

    async def record(self, approval: InterruptApproval) -> InterruptApproval:
        self.recorded.append(approval)
        return approval


class FakeBlockedSessionAssessmentRepository:
    async def create_blocked_session(self, blocked):
        blocked.blocked_session_id = "blocked-fake-1"
        return blocked


def _claims(sub: str, role: Role) -> TokenClaims:
    token = issuer.issue(sub=sub, role=role, audience=Audience.LEARNING)
    return verifier.verify(token, Audience.LEARNING)


def _registry_for(transport: FakeEmailTransport) -> McpToolRegistry:
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
        cost_ledger=None,  # type: ignore[arg-type]
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


def _params(group: str) -> list:
    return [pytest.param(c, id=c["id"]) for c in BYPASS_CASES if c["group"] == group]


def _case(case_id: str) -> dict:
    for case in BYPASS_CASES:
        if case["id"] == case_id:
            return case
    raise AssertionError(f"unknown bypass case id {case_id!r}")


async def _blocked_graph(saver: BaseCheckpointSaver, thread_id: str) -> tuple:
    """A session parked at the attendance block, one `resolve_attendance` away from the
    email-approval pause.
    """
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
            profile_adapter=FakeProfileAdapter(attendance_status=AttendanceStatus.ABSENT),
            assessment_repo=FakeBlockedSessionAssessmentRepository(),
        ),
    )
    return graph, claims


def _attendance_adapter() -> FakeProfileAdapter:
    return FakeProfileAdapter(
        students={"student-ext-1": STUDENT}, branches={"branch-ext-1": BRANCH}
    )


async def _paused_attendance(thread_id: str, transport: FakeEmailTransport, repo) -> tuple:
    graph, claims = await _blocked_graph(InMemorySaver(), thread_id)
    kwargs = {
        "profile_adapter": _attendance_adapter(),
        "attendance_choice": "ask_branch_manager",
        "email_transport": transport,
        "interrupt_repo": repo,
    }
    paused = await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="resolve_attendance"),
        config=_config(thread_id),
        context=_turn_context(claims, **kwargs),
    )
    assert paused["__interrupt__"][0].value["type"] == "email_approval"
    assert transport.sent == [], "an email left before any approval - the gate is open"
    return graph, claims, kwargs


# --------------------------------------------------------------------------------------
# Attendance gate: resumes that must not produce an email
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("attendance_payload"))
def test_attendance_gate_refuses_every_non_approval(case: dict) -> None:
    """SPEC §5.1.4: the email only goes out on an approval. Everything else - malformed,
    absent, falsy, wrongly-typed - has to end as a decline, and the audit row has to say
    so rather than recording an approval that never happened.
    """

    async def run() -> tuple:
        thread_id = f"hb-att-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        try:
            result = await graph.ainvoke(
                Command(resume=case["resume"]),
                config=_config(thread_id),
                context=_turn_context(claims, **kwargs),
            )
        except Exception as exc:  # noqa: BLE001 - the outcome is the assertion below
            return exc, transport, repo
        return result, transport, repo

    result, transport, repo = asyncio.run(run())
    assert transport.sent == [], f"{case['id']}: an email was sent without an approval"

    if case.get("expects") == "unresumable":
        # These two shapes never reach the node. LangGraph reads a dict resume as a
        # per-interrupt *resume map* when every key is an interrupt id - which `{}`
        # vacuously satisfies - and a `None` resume is refused outright, so the paused task
        # is simply not resumed. Kept as cases rather than deleted, for two reasons: the
        # invariant they assert is still the one that matters (nothing sent, nothing
        # recorded, no approval fabricated), and the reason they cannot reach the node is
        # worth pinning - `/respond` builds the resume value from a validated Pydantic body
        # (`{"approved": <bool>}`), so neither shape is reachable through the API at all.
        assert repo.recorded == [], (
            f"{case['id']}: an approval was recorded for a resume that never resolved"
        )
        return

    assert not isinstance(result, Exception), f"{case['id']}: unexpected {result!r}"
    assert result["last_message"] == attendance.EMAIL_DECLINED_MESSAGE
    assert [r.decision for r in repo.recorded] == ["cancelled"], (
        f"{case['id']}: the audit row does not say the approval was refused"
    )


@pytest.mark.parametrize("case", _params("attendance_injection"))
def test_an_approved_attendance_email_cannot_be_steered_by_the_resume(case: dict) -> None:
    """These approvals are real, so one email is expected. The bypass is whether extra
    fields in the resume can change who it goes to or what it says - everything in the
    message is composed server-side from the checkpointed student id and a live profile
    lookup, and the resume contributes nothing but the boolean.
    """

    async def run() -> tuple:
        thread_id = f"hb-att-inj-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        await graph.ainvoke(
            Command(resume=case["resume"]),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        return transport, repo

    transport, repo = asyncio.run(run())
    assert len(transport.sent) == 1, f"{case['id']}: expected exactly one email"
    message = transport.sent[0]
    assert message.recipient == BRANCH.manager_email, (
        f"{case['id']}: the resume redirected the email"
    )
    assert "attacker@evil.test" not in message.body
    assert "student-ext-9" not in message.body, (
        f"{case['id']}: the resume changed which student the email is about"
    )
    assert "reset this student's password" not in message.body, (
        f"{case['id']}: injected text reached the outbound body"
    )
    assert STUDENT.display_name in message.body
    assert [r.decision for r in repo.recorded] == ["approved"]


# --------------------------------------------------------------------------------------
# Child-selection gate: resumes that must not bind a student
# --------------------------------------------------------------------------------------


async def _resume_child_selection(resume: object, *, resumer: TokenClaims | None = None) -> dict:
    thread_id = f"hb-child-{uuid.uuid4().hex[:8]}"
    claims = _claims("parent-ext-2", Role.PARENT)
    adapter = FakeProfileAdapter(
        children_by_parent={"parent-ext-2": ["student-ext-2", "student-ext-3"]}
    )
    graph = build_graph(InMemorySaver())
    cfg = _config(thread_id)
    paused = await graph.ainvoke(
        EntryInput(session_id=thread_id, entry_action="select_student"),
        config=cfg,
        context=_turn_context(claims, profile_adapter=adapter),
    )
    assert paused["__interrupt__"][0].value["type"] == "child_selection"
    return await graph.ainvoke(
        Command(resume=resume),
        config=cfg,
        context=_turn_context(resumer or claims, profile_adapter=adapter),
    )


@pytest.mark.parametrize("case", _params("child_selection"))
def test_child_selection_refuses_any_unlinked_or_wrongly_typed_choice(case: dict) -> None:
    """`resolve_student`'s pause is an authorization gate rather than a message gate: the
    value the caller sends becomes `student_external_id`, and every later route authorizes
    against it. A resume that is not exactly one of this parent's currently-linked children
    must raise, and the re-fetch on resume is what keeps a link revoked mid-pause from
    still resolving.
    """
    expected: type[Exception] = (
        Exception if case.get("expects") == "unresumable" else PermissionError
    )
    with pytest.raises(expected) as exc:
        asyncio.run(_resume_child_selection(case["resume"]))
    if case.get("expects") != "unresumable":
        assert "student-ext-2" not in str(exc.value), (
            f"{case['id']}: the refusal names a child the caller had not proven access to"
        )


def test_hb_learn_24_a_second_parent_cannot_resume_the_first_parents_selection() -> None:
    case = _case("HB-LEARN-24")
    assert case["group"] == "replay"
    stranger = _claims("parent-ext-9", Role.PARENT)
    with pytest.raises(PermissionError):
        asyncio.run(_resume_child_selection("student-ext-3", resumer=stranger))


# --------------------------------------------------------------------------------------
# Replay
# --------------------------------------------------------------------------------------


def test_hb_learn_22_replaying_an_approved_attendance_pause_sends_once() -> None:
    """The pause is consumed by the first resume: LangGraph has no pending task left, so a
    second `Command(resume=...)` on the same thread completes no node and sends nothing.
    Measured rather than assumed - the sequential replay is safe here even though the
    *concurrent* one (HB-LEARN-F1) is not.
    """

    async def run() -> tuple:
        thread_id = f"hb-replay-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        await graph.ainvoke(
            Command(resume={"approved": True}),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        assert len(transport.sent) == 1, "the legitimate approval did not send"
        await graph.ainvoke(
            Command(resume={"approved": True}),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        return transport, repo

    transport, repo = asyncio.run(run())
    assert len(transport.sent) == 1, "the replay produced a second branch-manager email"
    assert len(repo.recorded) == 1


def test_hb_learn_23_approving_after_declining_sends_nothing() -> None:
    async def run() -> tuple:
        thread_id = f"hb-replay2-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        await graph.ainvoke(
            Command(resume={"approved": False}),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        await graph.ainvoke(
            Command(resume={"approved": True}),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        return transport, repo

    transport, repo = asyncio.run(run())
    assert transport.sent == [], "a declined approval was overturned into a send"
    assert [r.decision for r in repo.recorded] == ["cancelled"]


# --------------------------------------------------------------------------------------
# Controls
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", _params("control"))
def test_a_legitimate_attendance_approval_still_sends(case: dict) -> None:
    async def run() -> tuple:
        thread_id = f"hb-ctl-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        result = await graph.ainvoke(
            Command(resume=case["resume"]),
            config=_config(thread_id),
            context=_turn_context(claims, **kwargs),
        )
        return result, transport, repo

    result, transport, repo = asyncio.run(run())
    assert len(transport.sent) == 1
    assert transport.sent[0].recipient == BRANCH.manager_email
    assert result["last_message"] == attendance.EMAIL_SENT_MESSAGE
    assert [r.decision for r in repo.recorded] == ["approved"]


@pytest.mark.parametrize("case", _params("control_child"))
def test_a_legitimate_child_selection_still_binds(case: dict) -> None:
    result = asyncio.run(_resume_child_selection(case["resume"]))
    assert result["student_external_id"] == case["resume"]
    assert result["phase"] == "student_selected"


# --------------------------------------------------------------------------------------
# Finding: nothing serializes two simultaneous resumes of one pause
# --------------------------------------------------------------------------------------


def test_hb_learn_f1_two_simultaneous_resumes_both_complete() -> None:
    """**Finding, not a passing guard.**

    chat-api's `/respond` claims the thread with `pg_try_advisory_xact_lock` before
    resuming (D-346: "a LangGraph thread is not safe to invoke concurrently"), and its
    escalation send is additionally claimed in `chat_escalation_sends` (D-421). The
    learning-api attendance path has neither. Measured here at the graph layer, which is
    the layer both apps share: two simultaneous resumes of one pause both complete the
    node, so two branch-manager emails go out for one absence and two approval rows are
    written for one human decision.

    Asserted as the observed behaviour on purpose. If this starts failing because only one
    email is sent, a serialization point has been added and the finding in
    `docs/resume_evidence/03_gateway_agents/E3_REPORT.md` should be closed.
    """

    async def run() -> tuple:
        thread_id = f"hb-conc-{uuid.uuid4().hex[:8]}"
        transport = FakeEmailTransport()
        repo = FakeInterruptApprovalRepository()
        graph, claims, kwargs = await _paused_attendance(thread_id, transport, repo)
        await asyncio.gather(
            graph.ainvoke(
                Command(resume={"approved": True}),
                config=_config(thread_id),
                context=_turn_context(claims, **kwargs),
            ),
            graph.ainvoke(
                Command(resume={"approved": True}),
                config=_config(thread_id),
                context=_turn_context(claims, **kwargs),
            ),
            return_exceptions=True,
        )
        return transport, repo

    transport, repo = asyncio.run(run())
    assert len(transport.sent) == 2, (
        f"observed {len(transport.sent)} emails from two simultaneous resumes - if this is "
        "now 1, a serialization point was added and E3_REPORT.md's finding is stale"
    )
    assert len(repo.recorded) == 2


# --------------------------------------------------------------------------------------
# Route-level cases (live HTTP journey: MySQL fixtures + loaded curriculum)
# --------------------------------------------------------------------------------------


def _mysql_available() -> bool:
    async def check() -> bool:
        engine = create_async_engine(MYSQL_URL, connect_args={"connect_timeout": 1})
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


def _postgres_available() -> bool:
    async def check() -> bool:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1 FROM topics LIMIT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(check())


live_journey = pytest.mark.skipif(
    not (_mysql_available() and _postgres_available()),
    reason="MySQL/PostgreSQL not reachable or not migrated (run `make up && make db-upgrade`)",
)


@pytest.fixture(scope="module")
def seeded() -> None:
    asyncio.run(seed(MYSQL_URL))

    async def load() -> None:
        engine = create_engine()
        try:
            async with session_scope(create_session_factory(engine)) as session:
                await load_curriculum_and_templates(session)
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(load())


def _token(sub: str, role: Role = Role.STUDENT) -> str:
    return issuer.issue(sub=sub, role=role, audience=Audience.LEARNING)


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _paused_attendance_over_http(client: TestClient, headers: dict[str, str]) -> str:
    session_id = client.post("/learning/sessions", headers=headers).json()["learning_session_id"]
    client.post(
        f"/learning/sessions/{session_id}/student",
        headers=headers,
        json={"student_id": STUDENT_FIRST_CHILD},
    )
    topics = client.post(
        f"/learning/sessions/{session_id}/topics",
        headers=headers,
        json={"topic_id": "linear_equations"},
    ).json()
    assert topics["phase"] == "blocked", (
        f"the attendance gate no longer blocks this fixture student ({topics.get('phase')})"
    )
    asked = client.post(
        f"/learning/sessions/{session_id}/attendance-resolution",
        headers=headers,
        json={"choice": "ask_branch_manager"},
    ).json()
    assert asked["pending_interrupt"]["interrupt_type"] == "email_approval"
    return session_id


def _http_approvals(session_id: str) -> list[InterruptApproval]:
    async def fetch() -> list[InterruptApproval]:
        engine = create_engine()
        try:
            async with session_scope(create_session_factory(engine)) as session:
                result = await session.execute(
                    select(InterruptApproval).where(InterruptApproval.session_id == session_id)
                )
                return list(result.scalars().all())
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


@live_journey
@pytest.mark.parametrize("case", _params("route"))
def test_the_respond_route_refuses_unauthorized_or_malformed_resumes(
    case: dict, seeded: None
) -> None:
    del seeded
    headers = _auth(_token(STUDENT_FIRST_CHILD))
    with TestClient(app) as client:
        session_id = _paused_attendance_over_http(client, headers)
        before = len(app.state.email_transport.sent)

        if case["id"] == "HB-LEARN-25":
            response = client.post(
                f"/learning/sessions/{session_id}/respond",
                json={"interrupt_type": "email_approval", "approved": True},
            )
            expected = (401, 403)
        elif case["id"] == "HB-LEARN-26":
            response = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=_auth(_token(STUDENT_SECOND_CHILD)),
                json={"interrupt_type": "email_approval", "approved": True},
            )
            expected = (403, 404)
        elif case["id"] == "HB-LEARN-27":
            response = client.post(
                f"/learning/sessions/{session_id}/respond", headers=headers, json={}
            )
            expected = (422,)
        elif case["id"] == "HB-LEARN-28":
            response = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=headers,
                json={"interrupt_type": "intervention_choice", "choice": "solution"},
            )
            expected = (409,)
        else:  # HB-LEARN-29 - replay
            first = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=headers,
                json={"interrupt_type": "email_approval", "approved": True},
            )
            assert first.status_code == 200, first.text
            assert len(app.state.email_transport.sent) == before + 1
            before += 1
            response = client.post(
                f"/learning/sessions/{session_id}/respond",
                headers=headers,
                json={"interrupt_type": "email_approval", "approved": True},
            )
            expected = (409,)

        after = len(app.state.email_transport.sent)

    assert response.status_code in expected, (
        f"{case['id']}: {response.status_code} {response.text[:300]}"
    )
    assert after == before, f"{case['id']}: an email was sent by a refused resume"


@live_journey
def test_hb_learn_30_two_concurrent_http_resumes_send_exactly_one_email(seeded: None) -> None:
    """The advisory-lock race at the resume boundary, driven for real over HTTP.

    Both apps serialize here, but by different routes to the same lock: chat-api calls
    `_claim_turn` in the handler, learning-api reaches it inside `_invoke_with_deadline`
    (D-376 - "both bounds now apply at exactly the same seven call sites"). The lock is a
    transaction-scoped `pg_try_advisory_xact_lock` on `learning_turn:{id}`, so it holds
    across replicas rather than only within one process, and it is a *try*-lock: the loser
    gets an immediate 409 rather than queueing.

    Repeated rather than run once. A concurrency test that fires a single pair proves very
    little about a window it happened not to hit - the D-110 ss2 lesson applied to this
    probe - so each round asserts the invariant and the rounds together are the evidence
    quoted in `E3_REPORT.md`.
    """
    del seeded
    headers = _auth(_token(STUDENT_FIRST_CHILD))
    body = {"interrupt_type": "email_approval", "approved": True}
    rounds = 3
    observed: list[tuple[list[int], int, int]] = []

    with TestClient(app) as client:
        for _ in range(rounds):
            session_id = _paused_attendance_over_http(client, headers)
            before = len(app.state.email_transport.sent)

            def fire(sid: str = session_id) -> int:
                return client.post(
                    f"/learning/sessions/{sid}/respond", headers=headers, json=body
                ).status_code

            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = sorted(f.result() for f in [pool.submit(fire), pool.submit(fire)])
            emails = len(app.state.email_transport.sent) - before
            observed.append((statuses, emails, len(_http_approvals(session_id))))

    for statuses, emails, approvals in observed:
        assert emails == 1, (
            f"{emails} branch-manager emails from one approval (statuses={statuses}) - "
            "the resume boundary is no longer serialized"
        )
        assert approvals == 1, f"{approvals} approval rows for one human decision"
        assert 200 in statuses, f"neither concurrent resume succeeded: {statuses}"
        assert 409 in statuses, (
            f"both concurrent resumes were admitted: {statuses} - the turn claim did not fire"
        )


# --------------------------------------------------------------------------------------
# Catalog self-check
# --------------------------------------------------------------------------------------


def test_the_bypass_catalog_is_internally_consistent() -> None:
    ids = [c["id"] for c in BYPASS_CASES]
    assert len(ids) == len(set(ids)), "duplicate case ids"
    for case in BYPASS_CASES:
        assert case["kind"] in {"bypass", "control", "finding"}, case["id"]
        for field in ("surface", "attack", "invariant", "group"):
            assert case[field], f"{case['id']} is missing {field}"

    with open(__file__.replace(".pyc", ".py")) as handle:
        body = handle.read()
    tests_body = body[body.index("# Fakes - deliberately local") :]
    for case in BYPASS_CASES:
        used = (
            f'_params("{case["group"]}")' in tests_body
            or case["id"].lower().replace("-", "_") in tests_body
            or f'_case("{case["id"]}")' in tests_body
        )
        assert used, f"{case['id']} is catalogued but never driven by a test"
