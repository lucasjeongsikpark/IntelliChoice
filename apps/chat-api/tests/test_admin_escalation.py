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
from chat_api.services.rate_limit import InMemoryRateLimiter
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
