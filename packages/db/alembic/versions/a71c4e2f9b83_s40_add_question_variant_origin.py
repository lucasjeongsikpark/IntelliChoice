"""s40_add_question_variant_origin

Separates the two populations sharing `question_variants`: the one canonical rendering
that defines a template, and the unbounded stream of runtime instances minted per
question served. SPEC §5.8.3's dedup check compares against the former only (D-106).

Revision ID: a71c4e2f9b83
Revises: 960cbc482b6e
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a71c4e2f9b83'
down_revision: Union[str, Sequence[str], None] = '960cbc482b6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    op.add_column(
        'question_variants',
        sa.Column('origin', sa.String(), nullable=False, server_default='runtime'),
    )

    # Backfill. Every existing row predates the column, so the population has to be
    # reconstructed: the curriculum loader and the AI pipeline each write exactly one
    # variant per template *at template-creation time*, before that template can be
    # served, so the earliest variant per template is the canonical one and every later
    # one is a runtime instance. Verified unambiguous before writing this migration -
    # all 50 templates in the dev database had a strictly-earliest variant, no ties.
    #
    # On an empty database (CI, and the "migrations must replay from empty" rule) this
    # matches nothing and the loader's explicit `origin` does the work instead.
    op.execute(
        """
        UPDATE question_variants SET origin = 'canonical'
        WHERE question_variant_id IN (
            SELECT question_variant_id FROM (
                SELECT question_variant_id,
                       row_number() OVER (
                           PARTITION BY question_template_id
                           ORDER BY generated_at, question_variant_id
                       ) AS rn
                FROM question_variants
            ) ranked
            WHERE rn = 1
        )
        """
    )

    # The dedup check is `WHERE rendered_question = ? AND origin = 'canonical'` and ran as
    # a sequential scan over the whole table before this - 60,906 rows in the dev database
    # against the 50 rows it actually needed to consider.
    op.create_index(
        'ix_question_variants_origin_rendered_question',
        'question_variants',
        ['origin', 'rendered_question'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_question_variants_origin_rendered_question', table_name='question_variants')
    op.drop_column('question_variants', 'origin')
