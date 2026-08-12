"""d279 question figure spec

Adds `question_templates.figure_spec` - the structured figure a family-C question is about
(D-279). Nullable, so every existing item is unchanged and the column means exactly "this
question has no picture" for all of them.

Additive and reversible: no data is rewritten, and the downgrade drops a column nothing
else references.

Revision ID: 6aef7adeed26
Revises: c4a1e07b93df
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6aef7adeed26"
down_revision: str | Sequence[str] | None = "c4a1e07b93df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_templates",
        sa.Column("figure_spec", sa.JSON(), nullable=True),
    )
    op.add_column(
        "question_templates",
        sa.Column("figure_reading", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("question_templates", "figure_reading")
    op.drop_column("question_templates", "figure_spec")
