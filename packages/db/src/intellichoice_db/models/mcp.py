from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from intellichoice_db.models.base import Base, new_uuid

# S14 (SPEC §6.16 completion criterion: "Only Pydantic-validated tool arguments can
# execute"). The audit trail for every `intellichoice_shared.mcp.McpToolRegistry.call`
# - no PII, mirrors `InterruptApproval`'s own "audit record, not the data the decision
# was about" rationale: the tool name, an external id (or None for anonymous), and
# whether it succeeded, never the request/response payload itself.


class McpToolCall(Base):
    __tablename__ = "mcp_tool_calls"

    call_id: Mapped[str] = mapped_column(String, primary_key=True, default=new_uuid)
    tool_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    caller_external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
