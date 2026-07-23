"""s14 rename interrupt_approvals session id, add source_app

Revision ID: a91f2c6e4b17
Revises: c20398cd5739
Create Date: 2026-07-17 14:20:00.000000

S14: chat-api now writes `interrupt_approvals` rows too (admin-escalation email
approval, calendar action), not just learning-api - `learning_session_id` is renamed to
the app-agnostic `session_id`, and a new `source_app` ("learning" | "chat") column
disambiguates which app's checkpointed session the id refers to. A true column rename
(`alter_column(new_column_name=...)`), not add+drop, so existing rows keep their data.
`source_app` gets a `server_default='learning'` (S14's own convention, matching
`f6dcf62cdba4`'s precedent for a new NOT NULL column on a populated table) since every
row before this migration was written by learning-api; application code always supplies
an explicit value going forward. `decided_by_external_id` becomes nullable - chat-api
allows anonymous callers (SPEC §5.19.1) with no external id to record.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a91f2c6e4b17'
down_revision: Union[str, Sequence[str], None] = 'c20398cd5739'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_interrupt_approvals_learning_session_id'), table_name='interrupt_approvals')
    op.alter_column('interrupt_approvals', 'learning_session_id', new_column_name='session_id')
    op.create_index(op.f('ix_interrupt_approvals_session_id'), 'interrupt_approvals', ['session_id'], unique=False)
    op.add_column(
        'interrupt_approvals',
        sa.Column('source_app', sa.String(), nullable=False, server_default='learning'),
    )
    op.alter_column(
        'interrupt_approvals', 'decided_by_external_id',
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'interrupt_approvals', 'decided_by_external_id',
        existing_type=sa.String(),
        nullable=False,
    )
    op.drop_column('interrupt_approvals', 'source_app')
    op.drop_index(op.f('ix_interrupt_approvals_session_id'), table_name='interrupt_approvals')
    op.alter_column('interrupt_approvals', 'session_id', new_column_name='learning_session_id')
    op.create_index(
        op.f('ix_interrupt_approvals_learning_session_id'),
        'interrupt_approvals', ['learning_session_id'], unique=False,
    )
