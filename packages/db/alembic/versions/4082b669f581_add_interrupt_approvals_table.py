"""add interrupt_approvals table

Revision ID: 4082b669f581
Revises: f3d82932ed10
Create Date: 2026-07-15 23:24:58.693591

S7 (SPEC §6.9 completion criterion: "no external action can execute before approval").
The `checkpoint*` tables autogenerate picked up here are intentionally NOT touched, same
as the prior migration's note: they're created/owned by `AsyncPostgresSaver.setup()` at
app startup, not by Alembic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4082b669f581'
down_revision: Union[str, Sequence[str], None] = 'f3d82932ed10'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('interrupt_approvals',
    sa.Column('approval_id', sa.String(), nullable=False),
    sa.Column('learning_session_id', sa.String(), nullable=False),
    sa.Column('interrupt_type', sa.String(), nullable=False),
    sa.Column('decision', sa.String(), nullable=False),
    sa.Column('decided_by_external_id', sa.String(), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('approval_id')
    )
    op.create_index(op.f('ix_interrupt_approvals_learning_session_id'), 'interrupt_approvals', ['learning_session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_interrupt_approvals_learning_session_id'), table_name='interrupt_approvals')
    op.drop_table('interrupt_approvals')
