"""chat_cluster_embedding_provenance

AUD-C-16. Staging's rag_chunks corpus was 159/159 MockBedrockProvider hash vectors while
both deployed services queried with real Titan v2, so the semantic channel returned noise
(top-1 cosine +0.065-0.074, i.e. the tail of random unit vectors in 1024 dims) and nothing
anywhere could detect it. These columns record which provider/model produced each stored
embedding; ingestion stamps them, `knowledge-reembed` re-embeds rows whose provenance does
not match the configured model, and chat-api's /readyz fails closed on any mismatch.

Existing rows are deliberately left NULL ("unknown") rather than backfilled: NULL counts
as a mismatch everywhere downstream, so legacy corpora are re-embedded rather than trusted.

Revision ID: e18f4a6c2b90
Revises: c94e2a6b1d38
Create Date: 2026-07-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e18f4a6c2b90'
down_revision: Union[str, Sequence[str], None] = 'c94e2a6b1d38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    op.add_column('rag_chunks', sa.Column('embedding_provider', sa.String(), nullable=True))
    op.add_column('rag_chunks', sa.Column('embedding_model_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('rag_chunks', 'embedding_model_id')
    op.drop_column('rag_chunks', 'embedding_provider')
