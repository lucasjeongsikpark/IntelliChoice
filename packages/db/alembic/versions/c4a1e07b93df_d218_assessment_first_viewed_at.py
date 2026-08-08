"""d218_assessment_first_viewed_at

D-218. The post-exam's time limit was measured from `started_at`, which is when the row was
assembled - one graph turn *before* the student could reach a question, because the
stage-transition overlay is modal and the exam sits behind it. Measured on staging
2026-08-07: a 20-minute post-exam was down to 18:46 the moment the overlay was dismissed.

`first_viewed_at` is when the exam was first actually on screen with nothing over it.
Nullable and never backfilled: rows created before this migration, and any client that never
reports it, keep the old behaviour through `flow.exam_clock_start`'s fallback.

Revision ID: c4a1e07b93df
Revises: b7e42a91c503
Create Date: 2026-08-08 01:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c4a1e07b93df'
down_revision: Union[str, Sequence[str], None] = 'b7e42a91c503'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    op.add_column(
        'assessment_sessions',
        sa.Column('first_viewed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('assessment_sessions', 'first_viewed_at')
