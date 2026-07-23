"""s19 add chat_suggestions

Revision ID: 6af7c901bab1
Revises: a4dba285898c
Create Date: 2026-07-19 10:48:53.335234

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6af7c901bab1'
down_revision: Union[str, Sequence[str], None] = 'a4dba285898c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('chat_suggestions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('role_audience', sa.String(), nullable=False),
    sa.Column('category', sa.String(), nullable=False),
    sa.Column('prompt_text', sa.String(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('chat_suggestions')
