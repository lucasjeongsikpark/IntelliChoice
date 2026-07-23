"""drop learning_sessions (superseded by LangGraph checkpointing)

Revision ID: f3d82932ed10
Revises: 05a193bc739b
Create Date: 2026-07-15 19:04:09.420706

S6 replaces this table with LangGraph `PostgresSaver` checkpointing (SPEC §5.16) -
`learning_sessions` was the S5 stand-in orchestrator row before graph state existed
(see PROGRESS.md's S5 carry-over note). The `checkpoint*` tables autogenerate picked up
here are intentionally NOT touched: they're created/owned by
`AsyncPostgresSaver.setup()` at app startup, not by Alembic.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f3d82932ed10'
down_revision: Union[str, Sequence[str], None] = '05a193bc739b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index(op.f('ix_learning_sessions_student_external_id'), table_name='learning_sessions')
    op.drop_table('learning_sessions')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('learning_sessions',
    sa.Column('learning_session_id', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('student_external_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('topic_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('week_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('phase', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('pre_assessment_session_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('study_session_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('post_assessment_session_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('blocked_session_id', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['blocked_session_id'], ['blocked_sessions.blocked_session_id'], name=op.f('learning_sessions_blocked_session_id_fkey')),
    sa.ForeignKeyConstraint(['post_assessment_session_id'], ['assessment_sessions.assessment_session_id'], name=op.f('learning_sessions_post_assessment_session_id_fkey')),
    sa.ForeignKeyConstraint(['pre_assessment_session_id'], ['assessment_sessions.assessment_session_id'], name=op.f('learning_sessions_pre_assessment_session_id_fkey')),
    sa.ForeignKeyConstraint(['study_session_id'], ['study_sessions.study_session_id'], name=op.f('learning_sessions_study_session_id_fkey')),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.topic_id'], name=op.f('learning_sessions_topic_id_fkey')),
    sa.PrimaryKeyConstraint('learning_session_id', name=op.f('learning_sessions_pkey'))
    )
    op.create_index(op.f('ix_learning_sessions_student_external_id'), 'learning_sessions', ['student_external_id'], unique=False)
