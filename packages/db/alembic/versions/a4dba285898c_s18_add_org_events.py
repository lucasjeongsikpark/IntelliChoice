"""s18 add org_events

Revision ID: a4dba285898c
Revises: 1ce66767d8da
Create Date: 2026-07-19 01:13:22.564151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a4dba285898c'
down_revision: Union[str, Sequence[str], None] = '1ce66767d8da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('org_events',
    sa.Column('event_external_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('timezone', sa.String(), nullable=False),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('audience', sa.String(), nullable=False),
    sa.Column('branch_external_id', sa.String(), nullable=True),
    sa.Column('registration_url', sa.String(), nullable=True),
    sa.Column('recurrence_rule', sa.String(), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('event_external_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('org_events')
