"""SPEC §5.24 Gmail admin-escalation: deterministic draft, interrupt()-gated approval,
§5.29 "Gmail MCP failure -> Preserve draft", and §5.24.2 rate limiting. Mirrors
`test_qa_graph.py`'s shape (real `MockBedrockProvider` + rollback-isolated Postgres).
"""

import asyncio

import pytest
from chat_api.graph.build import AskInput, build_graph
from chat_api.graph.nodes import (
    EMAIL_DECLINED_MESSAGE,
    EMAIL_FAILED_MESSAGE,
    EMAIL_SENT_MESSAGE,
    RATE_LIMITED_MESSAGE,
    TurnContext,
)
from chat_api.services import admin_escalation
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.mcp import McpTool, McpToolRegistry
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)
from intellichoice_shared.rate_limit import InMemoryRateLimiter
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy import select

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

ADMIN_QUERY = "I need to speak to an admin about a billing issue with my account."


class FakeProfileAdapter:
    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        return None

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        raise NotImplementedError

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        raise NotImplementedError

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
        raise NotImplementedError

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None:
        raise NotImplementedError

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None:
        raise NotImplementedError

    async def list_branches(self) -> list[BranchInfo]:
        raise NotImplementedError


class RecordingEmailTransport:
    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)


class FailingEmailTransport:
    async def send(self, message: EmailMessage) -> None:
        raise ConnectionError("smtp unavailable")


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: "test-model",
            BedrockTask.RERANK: "test-model",
            BedrockTask.RAG_ANSWER: "test-model",
            BedrockTask.CALENDAR_EXTRACTION: "test-model",
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
        session_budget_cents=50.0,
    )


def _registry(email_transport) -> McpToolRegistry:
    registry = McpToolRegistry()
    registry.register(
        McpTool(name="gmail.send_email", args_model=EmailMessage, handler=email_transport.send)
    )
    return registry


def _ctx(
    session,
    *,
    email_transport,
    rate_limiter: InMemoryRateLimiter | None = None,
    query: str = ADMIN_QUERY,
) -> TurnContext:
    return TurnContext(
        claims=None,
        profile_adapter=FakeProfileAdapter(),
        rag_repo=RagRepository(session),
        bedrock_gateway=_gateway(),
        interrupt_repo=InterruptApprovalRepository(session),
        mcp_registry=_registry(email_transport),
        mcp_call_repo=McpToolCallRepository(session),
        org_event_repo=OrgEventRepository(session),
        rate_limiter=rate_limiter or InMemoryRateLimiter(max_per_window=5, window_s=3600.0),
        admin_escalation_email="admin@example.test",
        client_ip="203.0.113.5",
        query=query,
    )


def _config(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}}


async def _interrupt_approvals(session, session_id: str) -> list[InterruptApproval]:
    stmt = select(InterruptApproval).where(InterruptApproval.session_id == session_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


def test_admin_escalation_pauses_then_sends_only_after_approval() -> None:
    """Phase 15 (§6.16) pattern: no external action before approval."""

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            thread_id = "chat-zqxv-admin-1"

            paused = await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            assert paused["__interrupt__"][0].value["type"] == "email_approval"
            assert transport.sent == []

            result = await graph.ainvoke(
                Command(resume={"approved": True}),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            assert result["answer"] == EMAIL_SENT_MESSAGE
            assert len(transport.sent) == 1
            assert transport.sent[0].recipient == "admin@example.test"
            assert "billing issue" in transport.sent[0].body

            approvals = await _interrupt_approvals(session, thread_id)
            assert len(approvals) == 1
            assert approvals[0].source_app == "chat"
            assert approvals[0].decision == "approved"
            assert approvals[0].decided_by_external_id is None  # anonymous caller

    asyncio.run(run())


def test_admin_escalation_declined_sends_nothing() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            thread_id = "chat-zqxv-admin-decline-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": False}),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            assert result["answer"] == EMAIL_DECLINED_MESSAGE
            assert transport.sent == []

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "cancelled"

    asyncio.run(run())


def test_gmail_send_failure_preserves_draft() -> None:
    """SPEC §5.29 "Gmail MCP failure -> Preserve draft" - the approval is still
    recorded (the user did approve); the failed *send* is a separate fact.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = FailingEmailTransport()
            thread_id = "chat-zqxv-admin-fail-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True}),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            assert result["answer"] == EMAIL_FAILED_MESSAGE
            assert result["email_draft"]["body"]  # draft preserved for a retry

            approvals = await _interrupt_approvals(session, thread_id)
            assert len(approvals) == 1
            assert approvals[0].decision == "approved"

    asyncio.run(run())


def test_rate_limit_blocks_repeated_anonymous_escalation() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            limiter = InMemoryRateLimiter(max_per_window=1, window_s=3600.0)

            first = await graph.ainvoke(
                AskInput(session_id="chat-zqxv-rl-1", query=ADMIN_QUERY),
                config=_config("chat-zqxv-rl-1"),
                context=_ctx(session, email_transport=transport, rate_limiter=limiter),
            )
            assert first["__interrupt__"][0].value["type"] == "email_approval"

            second = await graph.ainvoke(
                AskInput(session_id="chat-zqxv-rl-2", query=ADMIN_QUERY),
                config=_config("chat-zqxv-rl-2"),
                context=_ctx(session, email_transport=transport, rate_limiter=limiter),
            )
            assert "__interrupt__" not in second
            assert second["answer"] == RATE_LIMITED_MESSAGE

    asyncio.run(run())


def test_the_node_picks_the_origin_from_the_request_not_from_the_intent() -> None:
    """D-221, and the test that would have caught the defect: every other test in this file
    calls `build_escalation_draft` directly with the boolean it wants, so none of them could
    ever see `prepare_admin_escalation` choosing that boolean wrongly - which is what it did.

    Watched failing against the D-219 discriminator before this was written. With
    `origin` chosen by `state.intent == "admin_contact"`, the second half of this test fails:
    `resolve_role` sets that intent on the escalate path too (D-164), so both branches
    produced the same value and the "could not answer" opening was unreachable through the
    graph. Every escalation email said the user had asked to be put in touch, including the
    ones raised from a no-source refusal, where that is the opposite of what happened.

    Both paths are driven through the real graph here for exactly that reason. A model's
    classification and a recorded user action can only be told apart by a run that actually
    goes through the router.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()

            # No `escalate`: the scope guard classified this `admin_contact`, which is a
            # model decision, so the draft must not assert what the user wanted.
            routed = await graph.ainvoke(
                AskInput(session_id="chat-zqxv-origin-1", query=ADMIN_QUERY),
                config=_config("chat-zqxv-origin-1"),
                context=_ctx(session, email_transport=transport),
            )
            body = routed["email_draft"]["body"]
            assert "the assistant routed it to an administrator" in body
            assert "asked to be put in touch" not in body

            # `escalate=True` is the "Contact an administrator" button - a user action on
            # the request itself, so naming the reason is reporting, not guessing.
            forwarded = await graph.ainvoke(
                AskInput(session_id="chat-zqxv-origin-2", query=ADMIN_QUERY, escalate=True),
                config=_config("chat-zqxv-origin-2"),
                context=_ctx(session, email_transport=transport),
            )
            assert (
                "asked a question the assistant could not answer"
                in forwarded["email_draft"]["body"]
            )

    asyncio.run(run())


def test_a_routed_question_is_not_reported_as_a_failure() -> None:
    """D-219. The draft opened with "asked a question the assistant could not answer" for
    every escalation, including the `admin_contact` path where the user simply asked to be
    put in touch and the assistant answered them correctly. Walked on staging 2026-08-08.

    The administrator reads that line to decide how to reply, so a wrong reason is worse
    than a vague one.
    """
    routed = admin_escalation.build_escalation_draft(
        query="Please send a message to an administrator about volunteer training dates.",
        missing_information=None,
        user_role="parent",
        chat_session_id="session-1",
        origin="assistant_routed",
    )
    assert "could not answer" not in routed.body
    assert "the assistant routed it to an administrator" in routed.body


def test_a_routed_question_does_not_claim_the_user_asked_for_contact() -> None:
    """D-221, and the reason this file's D-219 assertion changed rather than gained a
    sibling: the fix above replaced one unfounded claim with another.

    `assistant_routed` is reached when a *classifier* decided the turn was an
    admin-contact request. The scope-guard sweep measured that decision being wrong -
    "My kid got marked absent by mistake - how do I fix that?" routed here - and the draft
    then told an administrator the user had asked to be put in touch. The wording now
    reports what this system did, which stays true either way.

    Asserted as an absence, because the defect was a sentence being *present*: a future
    edit that reinstates the friendlier phrasing reinstates the false claim with it.
    """
    routed = admin_escalation.build_escalation_draft(
        query="My kid got marked absent by mistake - how do I fix that?",
        missing_information=None,
        user_role="public",
        chat_session_id="session-4",
        origin="assistant_routed",
    )
    assert "asked to be put in touch" not in routed.body
    assert "requested" not in routed.body
    # The question itself is still quoted verbatim - the administrator's actual evidence.
    assert "My kid got marked absent by mistake - how do I fix that?" in routed.body


def test_an_unanswerable_question_still_says_so() -> None:
    """The other half of the same distinction: the escalation-banner path is a genuine
    failure and must keep saying that, or the administrator loses the one signal that tells
    them the corpus has a gap.

    D-221 kept this wording deliberately. Here the reason is *recorded* - `QAState.escalate`
    arrived on the request - rather than inferred by a model, so naming it is a statement of
    fact and not a guess.
    """
    failed = admin_escalation.build_escalation_draft(
        query="What is the refund policy for the summer program?",
        missing_information="No approved source covers refunds.",
        user_role="parent",
        chat_session_id="session-2",
        origin="user_escalated",
    )
    assert "asked a question the assistant could not answer" in failed.body
    assert "No approved source covers refunds." in failed.body


def test_the_draft_never_carries_a_recipient() -> None:
    """Unchanged by D-219, asserted here because this file now edits the body: `QAState`
    promises no names or email addresses are checkpointed (SPEC §5.30), and the real
    recipient is built from config at send time.
    """
    draft = admin_escalation.build_escalation_draft(
        query="Anything",
        missing_information=None,
        user_role="student",
        chat_session_id="session-3",
        origin="assistant_routed",
    )
    assert "@" not in draft.body
    assert "@" not in draft.subject


def test_a_users_note_is_attributed_and_the_question_survives_it() -> None:
    """D-420 (B4): the visitor adds context; the server keeps the frame.

    The decision behind the shape: a fully editable body would make *"the draft carries the
    original question verbatim"* a convention rather than a property, since the first thing an
    edit can remove is the question. Both halves are asserted together for that reason - a note
    that appended correctly while dropping the question would satisfy either assertion alone.

    Attributed and quoted because an administrator decides how to reply from this email, and text
    the visitor wrote must not read in the same voice as text the system composed - the same
    reasoning D-221 applied to the opening line.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            thread_id = "chat-zqxv-admin-note-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            await graph.ainvoke(
                Command(
                    resume={"approved": True, "note": "It is urgent - the deadline is Friday."}
                ),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )

            body = transport.sent[0].body
            assert "From the user:" in body, "the note arrived unattributed"
            assert "> It is urgent - the deadline is Friday." in body, "the note was not quoted"
            assert "billing issue" in body, (
                "the note replaced the server-composed frame instead of being added to it"
            )

    asyncio.run(run())


def test_a_blank_note_adds_nothing_rather_than_an_empty_heading() -> None:
    """A heading with nothing under it tells an administrator the visitor wrote something and
    then hides it. Whitespace-only counts as blank, because a textarea produces that easily.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            thread_id = "chat-zqxv-admin-note-2"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            await graph.ainvoke(
                Command(resume={"approved": True, "note": "   \n  "}),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )

            assert "From the user:" not in transport.sent[0].body

    asyncio.run(run())


def test_the_note_never_enters_the_checkpointed_draft() -> None:
    """The note is applied at send time only.

    `state.email_draft` is the server-composed frame, and it is checkpointed. Writing the note
    back into it would mean a replay of this node quotes the note a second time - the shape D-021
    warns about, since a resume replays the node body from the top.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            transport = RecordingEmailTransport()
            thread_id = "chat-zqxv-admin-note-3"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=ADMIN_QUERY),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True, "note": "please call rather than email"}),
                config=_config(thread_id),
                context=_ctx(session, email_transport=transport),
            )

            assert "please call rather than email" in transport.sent[0].body
            draft = result.get("email_draft")
            assert draft is not None
            body = draft["body"] if isinstance(draft, dict) else draft.body
            assert "please call rather than email" not in body, (
                "the note was written back into the checkpointed draft, so a replay would quote "
                "it twice"
            )

    asyncio.run(run())
