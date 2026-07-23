"""s25_memory_contradiction_columns

Revision ID: 7e51132e191f
Revises: 84da644afdb1
Create Date: 2026-07-20 12:10:25.448593

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7e51132e191f'
down_revision: Union[str, Sequence[str], None] = '84da644afdb1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: the autogenerate diff also proposed dropping/recreating the LangGraph
    # checkpoint tables and three rag_chunks indexes - the same known false positives
    # every migration since f6dcf62cdba4 has documented. Omitted here, as in every
    # prior session.
    op.add_column('semantic_memory', sa.Column('superseded_by_id', sa.String(), nullable=True))
    op.add_column('semantic_memory', sa.Column('contradicts_event_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_foreign_key(
        'fk_semantic_memory_superseded_by_id',
        'semantic_memory', 'semantic_memory',
        ['superseded_by_id'], ['semantic_memory_id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_semantic_memory_superseded_by_id', 'semantic_memory', type_='foreignkey')
    op.drop_column('semantic_memory', 'contradicts_event_count')
    op.drop_column('semantic_memory', 'superseded_by_id')
