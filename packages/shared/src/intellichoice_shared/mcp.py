"""MCP tool registry (SPEC §5.22-§5.24, Phase 15 / §6.16): a generic, Pydantic-validated
tool-call boundary. Concrete tools (Gmail, Google Calendar) are registered by each app's
own lifespan, mirroring how `BedrockGateway` is a Protocol here with the real client
built in `packages/adapters` and wired via `app.state` (D-002's pattern).

No automatic retry: every tool registered this session (`gmail.send_email`,
`calendar.create_event`) is a non-idempotent external side effect with no
idempotency-key support in its fake transport - retrying a timed-out send risks a
duplicate. Bounded retry already exists at the Bedrock-gateway layer for a different
concern (LLM call flakiness, not external side effects). A future tool with a real
idempotency story (e.g. a read-only lookup) can add a `retryable` flag then - see
DECISIONS.md.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

# AUD-C-15: a *registered* tool name is short and developer-authored, but an unknown one is
# whatever the caller (or a model's tool call) asked for, and it is now written to an indexed
# `mcp_tool_calls.tool_name` column with no length limit. Two reasons to bound it, both about
# the audit write not becoming its own failure: a Postgres btree entry over ~2704 bytes raises
# on INSERT, which would mean failing *while recording a failure*; and an unbounded
# caller-controlled string is the wrong thing to copy into Postgres verbatim (SPEC §5.30).
# Applied on every path so the invariant does not depend on which branch audited - registered
# names are far shorter than this, so it is a no-op for them.
_MAX_AUDITED_TOOL_NAME_CHARS = 128


class McpToolError(Exception):
    """Base for every registry-raised failure - unknown tool, failed validation,
    disallowed role, or a handler timeout/exception."""


class ToolValidationError(McpToolError):
    """`raw_args` failed `args_model.model_validate` - the handler was never called
    (this is Phase 15's literal completion criterion: "Only Pydantic-validated tool
    arguments can execute")."""


class ToolPermissionError(McpToolError):
    """`caller_role` is not in the tool's `allowed_roles`."""


class ToolTimeoutError(McpToolError):
    """The handler did not complete within `timeout_s`."""


class ToolExecutionError(McpToolError):
    """The handler raised - wraps the original exception (`__cause__`) so every
    registry-raised failure is an `McpToolError` a caller can catch uniformly (e.g.
    `learning_api.services.attendance.send_attendance_email`'s "preserve draft on
    Gmail failure" path), regardless of what the underlying transport happened to
    raise.
    """


class ToolCallAuditEvent(BaseModel):
    """No PII: tool name, an external id (or None for anonymous), success/failure, and
    the exception *type* name only - never the raw exception message, which could carry
    request content. Mirrors `InterruptApproval`'s own "audit record, not the data the
    decision was about" rationale.
    """

    tool_name: str
    caller_external_id: str | None
    success: bool
    error_type: str | None
    duration_ms: float


class AuditRepo(Protocol):
    async def record(self, event: ToolCallAuditEvent) -> ToolCallAuditEvent: ...


@dataclass(frozen=True)
class McpTool[ArgsT: BaseModel, ResultT]:
    name: str
    args_model: type[ArgsT]
    handler: Callable[[ArgsT], Awaitable[ResultT]]
    timeout_s: float = 10.0
    allowed_roles: frozenset[str] | None = None


class McpToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, McpTool[Any, Any]] = {}

    def register(self, tool: McpTool[Any, Any]) -> None:
        self._tools[tool.name] = tool

    async def call(
        self,
        tool_name: str,
        raw_args: dict[str, Any],
        *,
        caller_external_id: str | None,
        caller_role: str | None = None,
        audit_repo: AuditRepo | None = None,
    ) -> Any:
        start = time.monotonic()

        tool = self._tools.get(tool_name)
        if tool is None:
            # AUD-C-15: audited before raising. Every other failure path here writes an
            # `mcp_tool_calls` row with `success=False`, and this one - a call to a tool that
            # does not exist - is precisely the shape a wiring bug or a prompt injection
            # produces, so it was the one that left no trace at all.
            await self._audit(
                audit_repo,
                tool_name,
                caller_external_id,
                False,
                "McpToolError",
                start,
            )
            raise McpToolError(f"unknown tool {tool_name!r}")

        if tool.allowed_roles is not None and caller_role not in tool.allowed_roles:
            await self._audit(
                audit_repo,
                tool_name,
                caller_external_id,
                False,
                "ToolPermissionError",
                start,
            )
            raise ToolPermissionError(f"role {caller_role!r} may not call {tool_name!r}")

        try:
            args = tool.args_model.model_validate(raw_args)
        except Exception as exc:
            await self._audit(
                audit_repo,
                tool_name,
                caller_external_id,
                False,
                type(exc).__name__,
                start,
            )
            raise ToolValidationError(str(exc)) from exc

        try:
            result = await asyncio.wait_for(tool.handler(args), timeout=tool.timeout_s)
        except TimeoutError as exc:
            await self._audit(
                audit_repo,
                tool_name,
                caller_external_id,
                False,
                "ToolTimeoutError",
                start,
            )
            raise ToolTimeoutError(f"{tool_name!r} exceeded {tool.timeout_s}s") from exc
        except Exception as exc:
            await self._audit(
                audit_repo,
                tool_name,
                caller_external_id,
                False,
                type(exc).__name__,
                start,
            )
            raise ToolExecutionError(f"{tool_name!r} failed: {type(exc).__name__}") from exc

        await self._audit(audit_repo, tool_name, caller_external_id, True, None, start)
        return result

    @staticmethod
    async def _audit(
        audit_repo: AuditRepo | None,
        tool_name: str,
        caller_external_id: str | None,
        success: bool,
        error_type: str | None,
        start: float,
    ) -> None:
        if audit_repo is None:
            return
        duration_ms = (time.monotonic() - start) * 1000
        await audit_repo.record(
            ToolCallAuditEvent(
                tool_name=tool_name[:_MAX_AUDITED_TOOL_NAME_CHARS],
                caller_external_id=caller_external_id,
                success=success,
                error_type=error_type,
                duration_ms=duration_ms,
            )
        )
