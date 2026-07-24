"""SPEC §5.23.2-§5.23.4 "Add it to my calendar": role-filtered retrieval + LLM
extraction, D-038-style provenance re-derivation, interrupt()-gated Google Calendar/
.ics/cancel choice, and §5.29 "Google Calendar failure -> Generate .ics". Mirrors
`test_qa_graph.py`'s real-Postgres-chunk-seeding shape.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from chat_api.graph.build import AskInput, build_graph
from chat_api.graph.nodes import (
    CALENDAR_CANCELLED_MESSAGE,
    CALENDAR_GOOGLE_FAILED_FALLBACK_MESSAGE,
    CALENDAR_GOOGLE_MESSAGE,
    CALENDAR_ICS_MESSAGE,
    NO_EVENT_FOUND_MESSAGE,
    NO_UPCOMING_EVENTS_MESSAGE,
    UPCOMING_EVENTS_HEADER,
    TurnContext,
)
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.ics import validate_ics_text
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.models.org import OrgEvent
from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.calendar import CalendarEvent
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
from sqlalchemy import select, text

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

CALENDAR_QUERY = "Add the Fall Parent Meeting to my calendar."


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


class RecordingCalendarTransport:
    def __init__(self) -> None:
        self.created: list[CalendarEvent] = []

    async def create_event(self, event: CalendarEvent) -> str:
        self.created.append(event)
        return "fake-event-1"


class FailingCalendarTransport:
    async def create_event(self, event: CalendarEvent) -> str:
        raise ConnectionError("google calendar unavailable")


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


async def _seed_chunk(session, *, chunk_text: str) -> RagChunk:
    repo = RagRepository(session)
    document = await repo.create_document(
        RagDocument(
            title="Test Public Document",
            source_path="public/test-doc/content.md",
            audience="public",
            academic_year="2026-2027",
            effective_from=datetime.now(UTC),
            status="approved",
            source_sha256="d" * 64,
        )
    )
    embedding_result = await _gateway().create_embedding(
        texts=[chunk_text], session_spend_cents=0.0
    )
    chunk = await repo.add_chunk(
        RagChunk(
            document_id=document.document_id,
            chunk_text=chunk_text,
            document_title=document.title,
            page_number=3,
            audience="public",
            access_level="public",
            academic_year="2026-2027",
            effective_from=document.effective_from,
            status="approved",
            source_sha256="d" * 64,
            embedding=embedding_result.vectors[0],
        )
    )
    await repo.refresh_search_vectors(document.document_id)
    return chunk


def _registry(calendar_transport) -> McpToolRegistry:
    registry = McpToolRegistry()
    registry.register(
        McpTool(
            name="calendar.create_event",
            args_model=CalendarEvent,
            handler=calendar_transport.create_event,
        )
    )
    registry.register(
        McpTool(name="gmail.send_email", args_model=EmailMessage, handler=_unused_send)
    )
    return registry


async def _unused_send(message: EmailMessage) -> None:  # pragma: no cover - never called here
    raise AssertionError("gmail.send_email should not be called by calendar tests")


def _ctx(session, *, calendar_transport, query: str = CALENDAR_QUERY) -> TurnContext:
    return TurnContext(
        claims=None,
        profile_adapter=FakeProfileAdapter(),
        rag_repo=RagRepository(session),
        bedrock_gateway=_gateway(),
        interrupt_repo=InterruptApprovalRepository(session),
        mcp_registry=_registry(calendar_transport),
        mcp_call_repo=McpToolCallRepository(session),
        org_event_repo=OrgEventRepository(session),
        rate_limiter=InMemoryRateLimiter(max_per_window=5, window_s=3600.0),
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


def test_extraction_uses_real_chunk_provenance_not_the_models_own_claim() -> None:
    """D-038-style assertion: `source_document_id`/`source_page` come from the real
    seeded chunk/document row, not anything the model could fabricate.
    """

    async def run() -> None:
        async with rollback_session() as session:
            # Shares every AND-term `websearch_to_tsquery` derives from CALENDAR_QUERY
            # ("add"/"fall"/"parent"/"meet"/"calendar") so Postgres keyword search
            # deterministically surfaces this chunk - S17's real org content (now
            # genuinely retrievable "today", not future-dated) makes the mock's
            # hash-based semantic ranking alone an unreliable way to guarantee this
            # single seeded chunk wins a spot in hybrid_search's candidate_limit.
            chunk = await _seed_chunk(
                session,
                chunk_text=(
                    "Fall Parent Meeting\n\nAdd this event to your calendar. Join us "
                    "on Nov 26, 2026 at the Main Branch to discuss the upcoming term."
                ),
            )
            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-1"

            paused = await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert paused["__interrupt__"][0].value["type"] == "calendar_action"
            event = paused["calendar_event"]
            assert event is not None
            assert event["source_document_id"] == chunk.document_id
            assert event["source_page"] == 3

    asyncio.run(run())


def test_structured_event_match_wins_over_rag_extraction() -> None:
    """S18 (plan §18-C2): a confident `org_events` keyword match is used directly,
    skipping the RAG+LLM path entirely - proven by seeding a *conflicting* date in a
    RAG chunk (which the mock LLM would otherwise extract, see `_calendar_extraction_
    json`) and asserting the structured row's date/timezone wins instead.
    """

    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                chunk_text=(
                    "Fall Parent Meeting\n\nAdd this event to your calendar. Join us "
                    "on Oct 15, 2023 at the Main Branch to discuss the upcoming term."
                ),
            )
            org_event_repo = OrgEventRepository(session)
            await org_event_repo.upsert_event(
                OrgEvent(
                    event_external_id="zqxvcal-fall-parent-meeting",
                    title="Fall Parent Meeting",
                    description="",
                    starts_at=datetime(2023, 11, 1, 17, 0, tzinfo=UTC),
                    ends_at=datetime(2023, 11, 1, 19, 0, tzinfo=UTC),
                    timezone="America/Chicago",
                    audience="public",
                    source_url="https://www.intellichoice.org/event/fall-parent-meeting/",
                    content_hash="hash",
                )
            )
            await session.flush()

            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-structured-1"

            paused = await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert paused["__interrupt__"][0].value["type"] == "calendar_action"
            event = paused["calendar_event"]
            assert event is not None
            assert event["source_document_id"] == "org-event:zqxvcal-fall-parent-meeting"
            assert event["timezone"] == "America/Chicago"
            assert event["start_datetime"].startswith("2023-11-01")

    asyncio.run(run())


def test_generic_listing_query_answers_from_structured_events_no_interrupt() -> None:
    """S18: a "what's coming up" style query with no specific event named is answered
    directly from `org_events` (SPEC §5.23.1's information request) - no `interrupt()`,
    no LLM extraction call needed.
    """

    async def run() -> None:
        async with rollback_session() as session:
            org_event_repo = OrgEventRepository(session)
            now = datetime.now(UTC)
            await org_event_repo.upsert_event(
                OrgEvent(
                    event_external_id="zqxvcal-listing-banquet",
                    title="Zqxvcal Scholarship Banquet",
                    description="",
                    starts_at=now + timedelta(days=10),
                    ends_at=now + timedelta(days=10, hours=2),
                    timezone="America/Chicago",
                    audience="public",
                    source_url="https://www.intellichoice.org/event/zqxvcal-banquet/",
                    content_hash="hash",
                )
            )
            await session.flush()

            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-listing-1"

            result = await graph.ainvoke(
                AskInput(session_id=thread_id, query="What's coming up on the calendar?"),
                config=_config(thread_id),
                context=_ctx(
                    session, calendar_transport=transport, query="What's coming up on the calendar?"
                ),
            )
            assert "__interrupt__" not in result
            assert result["answer"] is not None
            assert result["answer"].startswith(UPCOMING_EVENTS_HEADER)
            assert "Zqxvcal Scholarship Banquet" in result["answer"]

    asyncio.run(run())


def test_no_upcoming_events_message_when_history_exists_but_nothing_is_upcoming() -> None:
    """S18: distinguishes "there's real event history, just nothing upcoming" from the
    pre-S18 "no event data exists at all" message (see `calendar_no_event`'s docstring).
    """

    async def run() -> None:
        async with rollback_session() as session:
            org_event_repo = OrgEventRepository(session)
            await org_event_repo.upsert_event(
                OrgEvent(
                    event_external_id="zqxvcal-past-only",
                    title="Zqxvcal Past Event",
                    description="",
                    starts_at=datetime(2020, 1, 1, tzinfo=UTC),
                    ends_at=datetime(2020, 1, 1, 1, 0, tzinfo=UTC),
                    timezone="America/Chicago",
                    audience="public",
                    source_url="https://www.intellichoice.org/event/zqxvcal-past/",
                    content_hash="hash",
                )
            )
            await session.flush()

            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-nohistory-1"
            query = "What's coming up on the calendar?"

            result = await graph.ainvoke(
                AskInput(session_id=thread_id, query=query),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport, query=query),
            )
            assert "__interrupt__" not in result
            assert result["answer"] == NO_UPCOMING_EVENTS_MESSAGE
            assert result["answer"] != NO_EVENT_FOUND_MESSAGE

    asyncio.run(run())


def test_ics_choice_returns_valid_rfc5545_text_without_calling_google() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                chunk_text="Fall Parent Meeting on Nov 26, 2026 at the Main Branch.",
            )
            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-ics-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"choice": "ics"}),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert result["answer"] == CALENDAR_ICS_MESSAGE
            assert result["ics_content"]
            validation = validate_ics_text(result["ics_content"])
            assert validation.passed, validation.failures
            assert transport.created == []  # never called Google

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "ics"

    asyncio.run(run())


def test_google_choice_creates_event() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                chunk_text="Fall Parent Meeting on Nov 26, 2026 at the Main Branch.",
            )
            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-google-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"choice": "google"}),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert result["answer"] == CALENDAR_GOOGLE_MESSAGE
            assert result["ics_content"] is None
            assert len(transport.created) == 1

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "google"

    asyncio.run(run())


def test_google_failure_falls_back_to_ics() -> None:
    """SPEC §5.29 "Google Calendar failure -> Generate .ics", verbatim."""

    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                chunk_text="Fall Parent Meeting on Nov 26, 2026 at the Main Branch.",
            )
            graph = build_graph(InMemorySaver())
            transport = FailingCalendarTransport()
            thread_id = "chat-zqxv-cal-google-fail-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"choice": "google"}),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert result["answer"] == CALENDAR_GOOGLE_FAILED_FALLBACK_MESSAGE
            assert result["ics_content"]
            validation = validate_ics_text(result["ics_content"])
            assert validation.passed, validation.failures

    asyncio.run(run())


def test_cancel_choice_takes_no_action() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            await _seed_chunk(
                session,
                chunk_text="Fall Parent Meeting on Nov 26, 2026 at the Main Branch.",
            )
            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-cancel-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=CALENDAR_QUERY),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            result = await graph.ainvoke(
                Command(resume={"choice": "cancel"}),
                config=_config(thread_id),
                context=_ctx(session, calendar_transport=transport),
            )
            assert result["answer"] == CALENDAR_CANCELLED_MESSAGE
            assert result["ics_content"] is None
            assert transport.created == []

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "cancel"

    asyncio.run(run())


def test_no_dated_event_in_retrieved_content_is_a_graceful_no_answer() -> None:
    """SPEC §5.29 "No RAG result -> do not guess" - no interrupt at all."""

    async def run() -> None:
        async with rollback_session() as session:
            # S18's real org_events seed data (`make org-load`) may already be loaded
            # into the shared dev Postgres - scoped to this test's own rollback
            # savepoint, so this never touches the real rows, but guarantees the "no
            # event data exists at all" case this test is actually about (SPEC §5.29's
            # RAG-only no-answer path), decoupled from whatever real events happen to
            # be seeded (see `calendar_no_event`'s own history-aware message).
            await session.execute(text("DELETE FROM org_events"))
            await _seed_chunk(
                session,
                chunk_text="Volunteers help at every branch throughout the year.",
            )
            graph = build_graph(InMemorySaver())
            transport = RecordingCalendarTransport()
            thread_id = "chat-zqxv-cal-noevent-1"

            result = await graph.ainvoke(
                AskInput(
                    session_id=thread_id,
                    query="Add the volunteering calendar reminder to my calendar.",
                ),
                config=_config(thread_id),
                context=_ctx(
                    session,
                    calendar_transport=transport,
                    query="Add the volunteering calendar reminder to my calendar.",
                ),
            )
            assert "__interrupt__" not in result
            assert result["answer"] == NO_EVENT_FOUND_MESSAGE

    asyncio.run(run())
