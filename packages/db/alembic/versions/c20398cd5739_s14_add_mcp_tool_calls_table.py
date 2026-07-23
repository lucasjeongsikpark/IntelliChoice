"""s14 add mcp_tool_calls table

Revision ID: c20398cd5739
Revises: 0e846670f363
Create Date: 2026-07-17 14:06:07.198477

S14 (SPEC §6.16 completion criterion: "Only Pydantic-validated tool arguments can
execute"). The audit trail for every `intellichoice_shared.mcp.McpToolRegistry.call` -
no PII, mirrors `interrupt_approvals`' own "audit record, not the data the decision was
about" rationale. The `checkpoint*`/`rag_chunks` index lines autogenerate also proposed
here are intentionally NOT included: the checkpoint tables are created/owned by
`AsyncPostgresSaver.setup()` at app startup, not Alembic (same note as prior sessions'
migrations), and the two `rag_chunks` indexes were created via raw `op.execute` in
`0e846670f363`, which autogenerate can't map back to a model construct - both are
known false positives, not real drift.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c20398cd5739'
down_revision: Union[str, Sequence[str], None] = '0e846670f363'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mcp_tool_calls',
    sa.Column('call_id', sa.String(), nullable=False),
    sa.Column('tool_name', sa.String(), nullable=False),
    sa.Column('caller_external_id', sa.String(), nullable=True),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('error_type', sa.String(), nullable=True),
    sa.Column('duration_ms', sa.Float(), nullable=False),
    sa.Column('called_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('call_id')
    )
    op.create_index(op.f('ix_mcp_tool_calls_tool_name'), 'mcp_tool_calls', ['tool_name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mcp_tool_calls_tool_name'), table_name='mcp_tool_calls')
    op.drop_table('mcp_tool_calls')
