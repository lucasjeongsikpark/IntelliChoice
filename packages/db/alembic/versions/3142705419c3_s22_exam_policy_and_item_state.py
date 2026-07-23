"""s22_exam_policy_and_item_state

Revision ID: 3142705419c3
Revises: bcda490e9615
Create Date: 2026-07-19 18:30:09.405174

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3142705419c3'
down_revision: Union[str, Sequence[str], None] = 'bcda490e9615'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Matches Postgres's own default `<table>_<column>_fkey` naming, same as every other FK on
# this table - needed explicitly here only because `downgrade()` must name the constraint
# it drops.
FK_TOPIC = 'assessment_sessions_topic_id_fkey'


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping the LangGraph checkpoint tables
    # and three rag_chunks indexes - the same known false positives f6dcf62cdba4 and every
    # migration since have documented. Omitted here, as in every prior session.
    op.create_table('assessment_item_state',
    sa.Column('assessment_item_state_id', sa.String(), nullable=False),
    sa.Column('assessment_item_id', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('first_viewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('time_spent_ms', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['assessment_item_id'], ['assessment_items.assessment_item_id'], ),
    sa.PrimaryKeyConstraint('assessment_item_state_id'),
    sa.UniqueConstraint('assessment_item_id')
    )
    op.alter_column('assessment_attempts', 'selected_option',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.add_column('assessment_sessions', sa.Column('topic_id', sa.String(), nullable=True))
    op.add_column('assessment_sessions', sa.Column('policy', sa.JSON(), nullable=True))
    op.add_column('assessment_sessions', sa.Column('time_limit_seconds', sa.Integer(), nullable=True))
    op.add_column('assessment_sessions', sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key(FK_TOPIC, 'assessment_sessions', 'topics', ['topic_id'], ['topic_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FK_TOPIC, 'assessment_sessions', type_='foreignkey')
    op.drop_column('assessment_sessions', 'finalized_at')
    op.drop_column('assessment_sessions', 'time_limit_seconds')
    op.drop_column('assessment_sessions', 'policy')
    op.drop_column('assessment_sessions', 'topic_id')
    op.alter_column('assessment_attempts', 'selected_option',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.drop_table('assessment_item_state')
