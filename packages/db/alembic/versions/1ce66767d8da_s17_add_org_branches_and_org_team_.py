"""s17_add_org_branches_and_org_team_members

Revision ID: 1ce66767d8da
Revises: 4001aafe1ebe
Create Date: 2026-07-18 22:49:38.277440

S17 (plan §2.3/§8): the real org content directory scraped by `packages/webcontent`.
The `checkpoint*`/`rag_chunks` index drops autogenerate also proposed here are
intentionally NOT included - same known false positives as prior migrations (e.g.
4001aafe1ebe): the checkpoint tables are created/owned by `AsyncPostgresSaver.setup()`
at app startup, not Alembic, and the `rag_chunks` indexes were created via raw
`op.execute` in an earlier migration, which autogenerate can't map back to a model
construct.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1ce66767d8da'
down_revision: Union[str, Sequence[str], None] = '4001aafe1ebe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('org_branches',
    sa.Column('branch_external_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('address', sa.String(), nullable=True),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=True),
    sa.Column('hours', sa.JSON(), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('source_url', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('branch_external_id')
    )
    op.create_table('org_team_members',
    sa.Column('team_member_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('role_title', sa.String(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('biography', sa.String(), nullable=False),
    sa.Column('branch_external_id', sa.String(), nullable=True),
    sa.Column('audience', sa.String(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=False),
    sa.Column('content_hash', sa.String(), nullable=False),
    sa.Column('last_verified_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('team_member_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('org_team_members')
    op.drop_table('org_branches')
