"""s26_add_stage_transitions

Revision ID: 2720559e2a65
Revises: 7e51132e191f
Create Date: 2026-07-20 14:09:03.374290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2720559e2a65'
down_revision: Union[str, Sequence[str], None] = '7e51132e191f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # every migration since f6dcf62cdba4 has documented (alembic's reflection doesn't
    # see LangGraph's own checkpointer-managed tables or pgvector/GIN index options the
    # same way the ORM declares them). Omitted here, as in every prior session.
    op.create_table('stage_transitions',
    sa.Column('stage_transition_id', sa.String(), nullable=False),
    sa.Column('student_external_id', sa.String(), nullable=False),
    sa.Column('learning_session_id', sa.String(), nullable=False),
    sa.Column('stage', sa.String(), nullable=False),
    sa.Column('related_skill_id', sa.String(), nullable=True),
    sa.Column('narrative_text', sa.String(), nullable=False),
    sa.Column('evidence', sa.JSON(), nullable=False),
    sa.Column('generated', sa.Boolean(), nullable=False),
    sa.Column('cost_cents', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('stage_transition_id')
    )
    op.create_index(op.f('ix_stage_transitions_learning_session_id'), 'stage_transitions', ['learning_session_id'], unique=False)
    op.create_index(op.f('ix_stage_transitions_student_external_id'), 'stage_transitions', ['student_external_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_stage_transitions_student_external_id'), table_name='stage_transitions')
    op.drop_index(op.f('ix_stage_transitions_learning_session_id'), table_name='stage_transitions')
    op.drop_table('stage_transitions')
