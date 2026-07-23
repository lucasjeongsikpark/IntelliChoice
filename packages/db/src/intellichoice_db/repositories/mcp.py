from intellichoice_shared.mcp import ToolCallAuditEvent
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.mcp import McpToolCall


class McpToolCallRepository:
    """Implements `intellichoice_shared.mcp.AuditRepo` - takes the registry's own
    `ToolCallAuditEvent` and persists it as an `McpToolCall` row, so
    `intellichoice_shared.mcp` never needs to import a DB model.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: ToolCallAuditEvent) -> ToolCallAuditEvent:
        self._session.add(
            McpToolCall(
                tool_name=event.tool_name,
                caller_external_id=event.caller_external_id,
                success=event.success,
                error_type=event.error_type,
                duration_ms=event.duration_ms,
            )
        )
        await self._session.flush()
        return event
