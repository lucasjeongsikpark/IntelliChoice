"""s43_student_report_idempotency_key

AUD-X-04 (D-159). `POST /students/{id}/report` had no idempotency key: two clicks produced
two paid Bedrock calls and two `student_reports` rows. The key deduplicates a *replay* while
leaving deliberate re-generation alone - uniqueness is scoped to (student, audience, key),
not to a time window, because this table is history a parent re-opens.

Revision ID: f2c7d91a4e63
Revises: e18f4a6c2b90
Create Date: 2026-08-03 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f2c7d91a4e63'
down_revision: Union[str, Sequence[str], None] = 'e18f4a6c2b90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    #
    # Added nullable, backfilled, then set NOT NULL - the three-step shape, because staging
    # already holds real report rows and a bare NOT NULL add would fail on them.
    op.add_column('student_reports', sa.Column('idempotency_key', sa.String(), nullable=True))

    # Backfill. Every existing row predates the column and each one is its own request, so
    # the primary key is the honest key: unique by construction, and visibly synthetic so a
    # `legacy-` prefix can never collide with a client-supplied UUID. On an empty database
    # (CI, and the "migrations must replay from empty" rule) this matches nothing.
    op.execute(
        "UPDATE student_reports SET idempotency_key = 'legacy-' || student_report_id "
        "WHERE idempotency_key IS NULL"
    )

    op.alter_column('student_reports', 'idempotency_key', nullable=False)

    # The enforcement, not merely a hint: the service's replay lookup is read-then-act, so
    # two concurrent clicks can both read "no report yet". This is what makes at most one of
    # them insert - the same reasoning as `uq_assessment_attempts_session_variant` (AUD-L-10).
    op.create_unique_constraint(
        'uq_student_reports_student_audience_key',
        'student_reports',
        ['student_external_id', 'audience', 'idempotency_key'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        'uq_student_reports_student_audience_key', 'student_reports', type_='unique'
    )
    op.drop_column('student_reports', 'idempotency_key')
