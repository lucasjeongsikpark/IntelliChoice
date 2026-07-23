"""s13_rag_search_indexes

Revision ID: 0e846670f363
Revises: 8bcfca8c70f2
Create Date: 2026-07-17 11:21:38.135898

S13's hybrid search (SPEC §5.21.4-5.21.6) needs a GIN index for `websearch_to_tsquery`
keyword search and an HNSW `vector_cosine_ops` index for pgvector semantic search - S12's
ingestion pipeline populated both `search_vector`/`embedding` but nothing queried them yet
(see S12's own carry-over note). The composite btree index backs the SPEC §5.21.3
metadata pre-filter (`status`/`audience`/`branch_external_id`/`academic_year`), which runs
*before* either search per D-016's/§5.21.3's "never retrieve then hide" rule.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0e846670f363'
down_revision: Union[str, Sequence[str], None] = '8bcfca8c70f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "CREATE INDEX ix_rag_chunks_search_vector ON rag_chunks USING gin (search_vector)"
    )
    op.execute(
        "CREATE INDEX ix_rag_chunks_embedding_hnsw ON rag_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index(
        "ix_rag_chunks_filter",
        "rag_chunks",
        ["status", "audience", "branch_external_id", "academic_year"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_rag_chunks_filter", table_name="rag_chunks")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_search_vector")
