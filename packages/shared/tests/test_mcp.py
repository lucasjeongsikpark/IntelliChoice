"""Phase 15 (SPEC §6.16) completion criterion: "Only Pydantic-validated tool arguments
can execute." Pure, dependency-free tests - no DB/network needed since
`McpToolRegistry` itself has none.
"""

import asyncio

import pytest
from intellichoice_shared.mcp import (
    McpTool,
    McpToolError,
    McpToolRegistry,
    ToolCallAuditEvent,
    ToolExecutionError,
    ToolPermissionError,
    ToolTimeoutError,
    ToolValidationError,
)
from pydantic import BaseModel


class Args(BaseModel):
    value: str


class FakeAuditRepo:
    def __init__(self) -> None:
        self.events: list[ToolCallAuditEvent] = []

    async def record(self, event: ToolCallAuditEvent) -> ToolCallAuditEvent:
        self.events.append(event)
        return event


def _registry(
    *, timeout_s: float = 10.0, allowed_roles: frozenset[str] | None = None
) -> tuple[McpToolRegistry, list[Args]]:
    calls: list[Args] = []

    async def handler(args: Args) -> str:
        calls.append(args)
        return f"handled: {args.value}"

    registry = McpToolRegistry()
    registry.register(
        McpTool(
            name="test.echo",
            args_model=Args,
            handler=handler,
            timeout_s=timeout_s,
            allowed_roles=allowed_roles,
        )
    )
    return registry, calls


def test_valid_args_reach_the_handler() -> None:
    registry, calls = _registry()

    async def run() -> None:
        result = await registry.call("test.echo", {"value": "hi"}, caller_external_id="u-1")
        assert result == "handled: hi"
        assert calls == [Args(value="hi")]

    asyncio.run(run())


def test_invalid_args_never_reach_the_handler() -> None:
    registry, calls = _registry()

    async def run() -> None:
        with pytest.raises(ToolValidationError):
            await registry.call("test.echo", {"wrong_field": 1}, caller_external_id="u-1")
        assert calls == []

    asyncio.run(run())


def test_unknown_tool_never_calls_anything() -> None:
    registry, calls = _registry()

    async def run() -> None:
        with pytest.raises(McpToolError):
            await registry.call("test.does_not_exist", {"value": "hi"}, caller_external_id="u-1")
        assert calls == []

    asyncio.run(run())


def test_unknown_tool_is_audited_before_it_raises() -> None:
    """AUD-C-15. Every other failure path writes a `success=False` row; this one raised first
    and left no trace, which is the worst case for the one call shape a wiring bug or a
    prompt injection produces. Watched failing before the fix (0 events recorded).
    """
    registry, calls = _registry()
    audit = FakeAuditRepo()

    async def run() -> None:
        with pytest.raises(McpToolError):
            await registry.call(
                "test.does_not_exist",
                {"value": "hi"},
                caller_external_id="u-1",
                audit_repo=audit,
            )
        assert calls == []
        assert len(audit.events) == 1
        event = audit.events[0]
        assert event.tool_name == "test.does_not_exist"
        assert event.caller_external_id == "u-1"
        assert event.success is False
        # The attempted name is the whole value of the row, so it must be recorded as asked
        # for - not normalised to a placeholder like "unknown".
        assert event.error_type == "McpToolError"
        assert event.duration_ms >= 0

    asyncio.run(run())


def test_an_absurdly_long_unknown_tool_name_is_bounded_before_it_is_audited() -> None:
    """AUD-C-15's second half: an unknown tool name is caller-controlled and lands in an
    indexed column. Left unbounded, a long enough name makes the INSERT itself raise (a
    Postgres btree entry is capped at ~2704 bytes) - i.e. the audit write would fail on
    exactly the malicious input it exists to record.
    """
    registry, _ = _registry()
    audit = FakeAuditRepo()
    absurd = "x" * 10_000

    async def run() -> None:
        with pytest.raises(McpToolError):
            await registry.call(absurd, {"value": "hi"}, caller_external_id="u-1", audit_repo=audit)
        assert len(audit.events) == 1
        recorded = audit.events[0].tool_name
        assert len(recorded) == 128
        assert recorded == "x" * 128

    asyncio.run(run())


def test_disallowed_role_never_calls_the_handler() -> None:
    registry, calls = _registry(allowed_roles=frozenset({"tutor"}))

    async def run() -> None:
        with pytest.raises(ToolPermissionError):
            await registry.call(
                "test.echo", {"value": "hi"}, caller_external_id="u-1", caller_role="student"
            )
        assert calls == []

        # An allowed role still succeeds.
        result = await registry.call(
            "test.echo", {"value": "hi"}, caller_external_id="u-1", caller_role="tutor"
        )
        assert result == "handled: hi"

    asyncio.run(run())


def test_handler_timeout_raises_and_is_audited_without_retry() -> None:
    registry = McpToolRegistry()
    call_count = 0

    async def slow_handler(args: Args) -> str:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(10)
        return args.value

    registry.register(
        McpTool(name="test.slow", args_model=Args, handler=slow_handler, timeout_s=0.05)
    )
    audit_repo = FakeAuditRepo()

    async def run() -> None:
        with pytest.raises(ToolTimeoutError):
            await registry.call(
                "test.slow", {"value": "hi"}, caller_external_id="u-1", audit_repo=audit_repo
            )
        # No automatic retry - the handler was attempted exactly once.
        assert call_count == 1
        assert len(audit_repo.events) == 1
        assert audit_repo.events[0].success is False
        assert audit_repo.events[0].error_type == "ToolTimeoutError"

    asyncio.run(run())


def test_audit_event_never_carries_the_raw_exception_message() -> None:
    registry = McpToolRegistry()

    async def failing_handler(args: Args) -> str:
        raise ValueError(f"leaking the secret value {args.value}")

    registry.register(McpTool(name="test.fails", args_model=Args, handler=failing_handler))
    audit_repo = FakeAuditRepo()

    async def run() -> None:
        with pytest.raises(ToolExecutionError) as exc_info:
            await registry.call(
                "test.fails", {"value": "hi"}, caller_external_id="u-1", audit_repo=audit_repo
            )
        assert isinstance(exc_info.value.__cause__, ValueError)
        assert len(audit_repo.events) == 1
        event = audit_repo.events[0]
        assert event.success is False
        assert event.error_type == "ValueError"
        assert "secret value" not in (event.error_type or "")

    asyncio.run(run())


def test_successful_call_is_audited() -> None:
    registry, _ = _registry()
    audit_repo = FakeAuditRepo()

    async def run() -> None:
        await registry.call(
            "test.echo", {"value": "hi"}, caller_external_id="u-1", audit_repo=audit_repo
        )
        assert len(audit_repo.events) == 1
        assert audit_repo.events[0].success is True
        assert audit_repo.events[0].tool_name == "test.echo"
        assert audit_repo.events[0].caller_external_id == "u-1"

    asyncio.run(run())


def test_call_with_no_audit_repo_still_succeeds() -> None:
    registry, _ = _registry()

    async def run() -> None:
        result = await registry.call("test.echo", {"value": "hi"}, caller_external_id=None)
        assert result == "handled: hi"

    asyncio.run(run())
