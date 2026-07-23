"""s27_add_video_hardening_columns

Revision ID: 1d0b649b0101
Revises: 2720559e2a65
Create Date: 2026-07-20 15:11:13.233110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1d0b649b0101'
down_revision: Union[str, Sequence[str], None] = '2720559e2a65'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # every migration since f6dcf62cdba4 has documented (alembic's reflection doesn't
    # see LangGraph's own checkpointer-managed tables or pgvector/GIN index options the
    # same way the ORM declares them). Omitted here, as in every prior session.
    #
    # server_default is required on every non-nullable column below - the shared dev
    # Postgres already has real youtube_videos rows (S15/S17 seed data) this migration
    # must replay against; each default matches the ORM model's own Python-side default.
    op.add_column(
        'youtube_videos',
        sa.Column(
            'prerequisite_skill_ids', sa.JSON(), nullable=False, server_default='[]'
        ),
    )
    op.add_column(
        'youtube_videos',
        sa.Column(
            'transcript_available', sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column('youtube_videos', sa.Column('transcript_language', sa.String(), nullable=True))
    op.add_column(
        'youtube_videos',
        sa.Column('license', sa.String(), nullable=False, server_default='youtube'),
    )
    op.add_column('youtube_videos', sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        'youtube_videos',
        sa.Column('suitability_status', sa.String(), nullable=False, server_default='approved'),
    )
    op.add_column(
        'youtube_videos',
        sa.Column('verification_failures', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('youtube_videos', 'verification_failures')
    op.drop_column('youtube_videos', 'suitability_status')
    op.drop_column('youtube_videos', 'last_verified_at')
    op.drop_column('youtube_videos', 'license')
    op.drop_column('youtube_videos', 'transcript_language')
    op.drop_column('youtube_videos', 'transcript_available')
    op.drop_column('youtube_videos', 'prerequisite_skill_ids')
