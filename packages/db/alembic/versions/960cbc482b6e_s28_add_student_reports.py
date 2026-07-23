"""s28_add_student_reports

Revision ID: 960cbc482b6e
Revises: 1d0b649b0101
Create Date: 2026-07-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '960cbc482b6e'
down_revision: Union[str, Sequence[str], None] = '1d0b649b0101'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # every migration since f6dcf62cdba4 has documented. Omitted here, as in every prior
    # session.
    op.create_table('student_reports',
    sa.Column('student_report_id', sa.String(), nullable=False),
    sa.Column('student_external_id', sa.String(), nullable=False),
    sa.Column('audience', sa.String(), nullable=False),
    sa.Column('verified_facts', sa.JSON(), nullable=False),
    sa.Column('interpretation_text', sa.String(), nullable=False),
    sa.Column('recommendations_text', sa.String(), nullable=False),
    sa.Column('generated', sa.Boolean(), nullable=False),
    sa.Column('cost_cents', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('student_report_id')
    )
    op.create_index(op.f('ix_student_reports_student_external_id'), 'student_reports', ['student_external_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_student_reports_student_external_id'), table_name='student_reports')
    op.drop_table('student_reports')
