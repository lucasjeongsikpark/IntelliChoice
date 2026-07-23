"""s21_add_hint_events

Revision ID: bcda490e9615
Revises: 529d2f1df0af
Create Date: 2026-07-19 17:12:05.168445

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bcda490e9615'
down_revision: Union[str, Sequence[str], None] = '529d2f1df0af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # f6dcf62cdba4 and every migration since have documented (alembic's reflection
    # doesn't see LangGraph's own checkpointer-managed tables or pgvector/GIN index
    # options the same way the ORM declares them). Omitted here, as in every prior
    # session.
    op.create_table('hint_events',
    sa.Column('hint_event_id', sa.String(), nullable=False),
    sa.Column('student_external_id', sa.String(), nullable=False),
    sa.Column('study_attempt_id', sa.String(), nullable=False),
    sa.Column('question_variant_id', sa.String(), nullable=False),
    sa.Column('hint_level', sa.Integer(), nullable=False),
    sa.Column('canonical_hint_text', sa.String(), nullable=False),
    sa.Column('personalized_hint_text', sa.String(), nullable=False),
    sa.Column('misconception_tag', sa.String(), nullable=True),
    sa.Column('was_personalized', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['question_variant_id'], ['question_variants.question_variant_id'], ),
    sa.ForeignKeyConstraint(['study_attempt_id'], ['study_attempts.attempt_id'], ),
    sa.PrimaryKeyConstraint('hint_event_id')
    )
    op.create_index(op.f('ix_hint_events_student_external_id'), 'hint_events', ['student_external_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_hint_events_student_external_id'), table_name='hint_events')
    op.drop_table('hint_events')
