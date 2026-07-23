"""s24_add_tutor_chat_messages

Revision ID: 84da644afdb1
Revises: 3142705419c3
Create Date: 2026-07-20 10:15:33.438902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '84da644afdb1'
down_revision: Union[str, Sequence[str], None] = '3142705419c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # every migration since f6dcf62cdba4 has documented (alembic's reflection doesn't
    # see LangGraph's own checkpointer-managed tables or pgvector/GIN index options the
    # same way the ORM declares them). Omitted here, as in every prior session.
    op.create_table('tutor_chat_messages',
    sa.Column('message_id', sa.String(), nullable=False),
    sa.Column('student_external_id', sa.String(), nullable=False),
    sa.Column('learning_session_id', sa.String(), nullable=False),
    sa.Column('question_variant_id', sa.String(), nullable=True),
    sa.Column('intent', sa.String(), nullable=False),
    sa.Column('redacted_student_message', sa.String(), nullable=False),
    sa.Column('reply_text', sa.String(), nullable=False),
    sa.Column('cost_cents', sa.Float(), nullable=False),
    sa.Column('flagged_for_review', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['question_variant_id'], ['question_variants.question_variant_id'], ),
    sa.PrimaryKeyConstraint('message_id')
    )
    op.create_index(op.f('ix_tutor_chat_messages_learning_session_id'), 'tutor_chat_messages', ['learning_session_id'], unique=False)
    op.create_index(op.f('ix_tutor_chat_messages_student_external_id'), 'tutor_chat_messages', ['student_external_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_tutor_chat_messages_student_external_id'), table_name='tutor_chat_messages')
    op.drop_index(op.f('ix_tutor_chat_messages_learning_session_id'), table_name='tutor_chat_messages')
    op.drop_table('tutor_chat_messages')
