"""s15_add_youtube_videos_table

Revision ID: 4001aafe1ebe
Revises: a91f2c6e4b17
Create Date: 2026-07-17 23:41:04.888569

S15 (SPEC §5.18.2 stored metadata / §6.17 Phase 16). The local YouTube video catalog -
`youtube_catalog.search` queries this table (metadata filter + pgvector semantic rank),
never a live YouTube API call at learning time. The `checkpoint*`/`rag_chunks` index
lines autogenerate also proposed here are intentionally NOT included: the checkpoint
tables are created/owned by `AsyncPostgresSaver.setup()` at app startup, not Alembic,
and the `rag_chunks` indexes were created via raw `op.execute` in an earlier migration,
which autogenerate can't map back to a model construct - both are known false
positives, not real drift (same note as prior sessions' migrations, e.g.
c20398cd5739).
"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4001aafe1ebe'
down_revision: Union[str, Sequence[str], None] = 'a91f2c6e4b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('youtube_videos',
    sa.Column('youtube_video_id', sa.String(), nullable=False),
    sa.Column('channel_id', sa.String(), nullable=False),
    sa.Column('channel_title', sa.String(), nullable=False),
    sa.Column('video_url', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=False),
    sa.Column('playlist_ids', sa.JSON(), nullable=False),
    sa.Column('duration', sa.String(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('thumbnail_url', sa.String(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('topic_ids', sa.JSON(), nullable=False),
    sa.Column('skill_ids', sa.JSON(), nullable=False),
    sa.Column('grade_band', sa.String(), nullable=False),
    sa.Column('difficulty_min', sa.Integer(), nullable=False),
    sa.Column('difficulty_max', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=1024), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('active_status', sa.String(), nullable=False),
    sa.PrimaryKeyConstraint('youtube_video_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('youtube_videos')
