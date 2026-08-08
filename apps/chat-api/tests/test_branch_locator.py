"""SPEC §5.1.3/§5.22 Branch Locator: location-consent `interrupt()`, the Maps geocode/
route MCP tools, and all three §5.22 fallbacks (Maps unavailable, route unavailable,
no location supplied). Mirrors `test_calendar_action.py`'s real-Postgres-checkpoint
shape - no RAG content is needed here since branch data comes from `ProfileAdapter`,
not retrieval.
"""

import asyncio

import pytest
from chat_api.graph import nodes
from chat_api.graph.build import AskInput, build_graph
from chat_api.graph.nodes import (
    LOCATION_CONSENT_NOTICE,
    LOCATION_DECLINED_MESSAGE,
    LOCATION_MISSING_MESSAGE,
    TurnContext,
)
from chat_api.services.branch_locator import (
    BranchDistance,
    BranchLocatorResult,
    BranchLocatorStatus,
)
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_adapters.fake_maps import FakeMapsProvider
from intellichoice_db.models.interrupts import InterruptApproval
from intellichoice_db.repositories.interrupts import InterruptApprovalRepository
from intellichoice_db.repositories.mcp import McpToolCallRepository
from intellichoice_db.repositories.org import OrgEventRepository
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockTask
from intellichoice_shared.calendar import CalendarEvent
from intellichoice_shared.email import EmailMessage
from intellichoice_shared.maps import GeocodeQuery, RouteQuery
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

BRANCH_QUERY = "What is the nearest branch to me?"

_MAIN = BranchInfo(
    branch_external_id="branch-ext-1",
    name="Main Branch",
    manager_email="manager.main@example.test",
    address="100 Learning Way, Springfield",
    latitude=39.7817,
    longitude=-89.6501,
)
_NORTH = BranchInfo(
    branch_external_id="branch-ext-2",
    name="North Branch",
    manager_email="manager.north@example.test",
    address="45 Oakridge Ave, Springfield",
    latitude=39.8500,
    longitude=-89.6900,
)


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
        return [_MAIN, _NORTH]


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: "test-model",
            BedrockTask.RERANK: "test-model",
            BedrockTask.RAG_ANSWER: "test-model",
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
        session_budget_cents=50.0,
    )


async def _unused_send(message: EmailMessage) -> None:  # pragma: no cover - never called here
    raise AssertionError("gmail.send_email should not be called by branch-locator tests")


async def _unused_calendar(event: CalendarEvent) -> str:  # pragma: no cover - never called
    raise AssertionError("calendar.create_event should not be called by branch-locator tests")


def _registry(maps_provider: FakeMapsProvider) -> McpToolRegistry:
    registry = McpToolRegistry()
    registry.register(
        McpTool(name="gmail.send_email", args_model=EmailMessage, handler=_unused_send)
    )
    registry.register(
        McpTool(
            name="calendar.create_event", args_model=CalendarEvent, handler=_unused_calendar
        )
    )
    registry.register(
        McpTool(name="maps.geocode", args_model=GeocodeQuery, handler=maps_provider.geocode)
    )
    registry.register(
        McpTool(
            name="maps.compute_routes",
            args_model=RouteQuery,
            handler=maps_provider.compute_route,
        )
    )
    return registry


def _ctx(session, *, maps_provider: FakeMapsProvider, query: str = BRANCH_QUERY) -> TurnContext:
    return TurnContext(
        claims=None,
        profile_adapter=FakeProfileAdapter(),
        rag_repo=RagRepository(session),
        bedrock_gateway=_gateway(),
        interrupt_repo=InterruptApprovalRepository(session),
        mcp_registry=_registry(maps_provider),
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


def test_branch_locator_intent_pauses_with_the_spec_consent_notice() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            thread_id = "chat-zqxv-branch-notice-1"

            paused = await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            interrupt = paused["__interrupt__"][0]
            assert interrupt.value["type"] == "location_consent"
            assert interrupt.value["notice"] == LOCATION_CONSENT_NOTICE

    asyncio.run(run())


def test_declining_consent_never_calls_maps() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            thread_id = "chat-zqxv-branch-decline-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": False}),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            assert result["answer"] == LOCATION_DECLINED_MESSAGE

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "cancelled"
            assert approvals[0].interrupt_type == "location_consent"

    asyncio.run(run())


def test_approved_with_no_location_asks_for_zip_or_city() -> None:
    """SPEC §5.22 "Location denied -> ZIP or city input" - also covers "approved but the
    browser's own geolocation prompt was denied", which looks identical from here.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            thread_id = "chat-zqxv-branch-nolocation-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True}),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            assert result["answer"] == LOCATION_MISSING_MESSAGE

    asyncio.run(run())


def test_approved_with_zip_returns_branches_sorted_nearest_first() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            thread_id = "chat-zqxv-branch-zip-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True, "zip_code": "62704"}),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            answer = result["answer"]
            assert "Main Branch" in answer
            assert "North Branch" in answer
            # ZIP 62704 is geocoded (by the fake) to the Main Branch's exact coordinates,
            # so it must be listed first (0 km away) and never flagged as an estimate.
            assert answer.index("Main Branch") < answer.index("North Branch")
            assert "estimated straight-line distance" not in answer

            approvals = await _interrupt_approvals(session, thread_id)
            assert approvals[0].decision == "approved"

    asyncio.run(run())


def test_maps_geocode_failure_falls_back_to_address_list() -> None:
    """SPEC §5.22 "Maps unavailable -> branch-address list", no distances shown."""

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            maps_provider.fail_geocode = True
            thread_id = "chat-zqxv-branch-geofail-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True, "city": "Springfield"}),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            answer = result["answer"]
            assert "100 Learning Way, Springfield" in answer
            assert "45 Oakridge Ave, Springfield" in answer
            # D-219 changed the unit; the property is still "no distance was claimed".
            assert "miles away" not in answer

    asyncio.run(run())


def test_route_failure_falls_back_to_labeled_straight_line_estimate() -> None:
    """SPEC §5.22 "Route unavailable -> clearly labeled straight-line ... estimate"."""

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            maps_provider.fail_routes = True
            thread_id = "chat-zqxv-branch-routefail-1"

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            result = await graph.ainvoke(
                Command(resume={"approved": True, "zip_code": "62704"}),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            answer = result["answer"]
            assert "miles away" in answer
            assert "estimated straight-line distance" in answer

    asyncio.run(run())


def test_precise_coordinates_never_land_in_checkpointed_state() -> None:
    """SPEC §5.1.3 "do not store precise coordinates in PostgreSQL... or application
    logs" - a distinctive, never-elsewhere-used latitude/longitude pair is supplied in
    the resume payload; after the turn completes, the full checkpointed `QAState` (what
    `AsyncPostgresSaver` would persist) must not contain it anywhere, proving
    `branch_locator_consent` never assigns the raw location to a named field (D-045).
    LangGraph's own internal resume-value bookkeeping is a separate, documented
    caveat (D-045) this test doesn't (and can't) reach.
    """

    async def run() -> None:
        async with rollback_session() as session:
            graph = build_graph(InMemorySaver())
            maps_provider = FakeMapsProvider()
            thread_id = "chat-zqxv-branch-nocoords-1"
            distinctive_lat, distinctive_lon = 12.345678, -98.765432

            await graph.ainvoke(
                AskInput(session_id=thread_id, query=BRANCH_QUERY),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )
            await graph.ainvoke(
                Command(
                    resume={
                        "approved": True,
                        "latitude": distinctive_lat,
                        "longitude": distinctive_lon,
                    }
                ),
                config=_config(thread_id),
                context=_ctx(session, maps_provider=maps_provider),
            )

            snapshot = await graph.aget_state(_config(thread_id))
            serialized = repr(snapshot.values)
            assert str(distinctive_lat) not in serialized
            assert str(distinctive_lon) not in serialized
            assert "latitude" not in snapshot.values
            assert "longitude" not in snapshot.values

    asyncio.run(run())


def test_drive_time_reads_as_time_not_as_a_minute_count() -> None:
    """D-219. The deployed build said "about 918 min drive" - a true number nobody can read
    at a glance. Under an hour stays in minutes, which is the common case for a real nearest
    branch; beyond that it becomes hours.
    """
    assert nodes._format_drive_time(0) == "0 min"
    assert nodes._format_drive_time(45) == "45 min"
    assert nodes._format_drive_time(59.4) == "59 min"
    # The boundary rounds into hours rather than reading "60 min".
    assert nodes._format_drive_time(60) == "1 hr"
    assert nodes._format_drive_time(90) == "1 hr 30 min"
    assert nodes._format_drive_time(918) == "15 hr 18 min"


def test_distance_is_shown_in_miles_while_the_internal_figure_stays_metric() -> None:
    """IntelliChoice is a Dallas, TX organization and its audience is US families. Only the
    user-facing string converts: `distance_km` is what the Maps route and `haversine_km` both
    return, and nothing downstream should have to know which unit it is looking at.
    """
    result = BranchLocatorResult(
        status=BranchLocatorStatus.OK,
        branches=[
            BranchDistance(
                branch_external_id="branch-ext-1",
                name="Main Branch",
                address="100 Learning Way, Springfield",
                distance_km=16.09344,
                duration_minutes=25,
                is_estimate=False,
            )
        ],
    )
    answer = nodes._format_branch_locator_answer(result)

    assert "10.0 miles away" in answer
    assert "about 25 min drive" in answer
    assert "km" not in answer
