"""s42_cost_reservations

AUD-X-08. The per-day paid-API ceilings were read-then-act with the spending row committed
at request teardown, so concurrent callers each read a stale total: 10 concurrent reports
produced 10 generated reports and 10x the ceiling. This table is the serialization point -
a caller reserves its worst-case cost in an immediately-committed transaction before the
model call and settles the real cost after.

Revision ID: c94e2a6b1d38
Revises: b83c1d5f7a02
Create Date: 2026-07-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c94e2a6b1d38'
down_revision: Union[str, Sequence[str], None] = 'b83c1d5f7a02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    op.create_table(
        'cost_reservations',
        sa.Column('reservation_id', sa.String(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('subject_external_id', sa.String(), nullable=False),
        sa.Column('reserved_cents', sa.Float(), nullable=False),
        sa.Column('actual_cents', sa.Float(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('reservation_id'),
    )
    op.create_index(
        'ix_cost_reservations_scope_subject_created',
        'cost_reservations',
        ['scope', 'subject_external_id', 'created_at'],
    )

    # Backfill the ceiling windows. Without this the ledger reads zero on the day of
    # deploy, so every ceiling resets once - small, but it is exactly the kind of one-off
    # money hole that is cheaper to close here than to explain later. Bounded to 2 days:
    # both ceilings use a 24h window, so anything older can never be counted.
    #
    # `settled_at` is set so these read as historical rather than in flight. On an empty
    # database (CI, and the "migrations must replay from empty" rule) both match nothing.
    op.execute(
        """
        INSERT INTO cost_reservations
            (reservation_id, scope, subject_external_id, reserved_cents, actual_cents,
             created_at, settled_at)
        SELECT gen_random_uuid()::text, 'student_report', student_external_id,
               cost_cents, cost_cents, created_at, created_at
        FROM student_reports
        WHERE created_at >= now() - interval '2 days' AND cost_cents > 0
        """
    )
    op.execute(
        """
        INSERT INTO cost_reservations
            (reservation_id, scope, subject_external_id, reserved_cents, actual_cents,
             created_at, settled_at)
        SELECT gen_random_uuid()::text, 'tutor_chat', student_external_id,
               cost_cents, cost_cents, created_at, created_at
        FROM tutor_chat_messages
        WHERE created_at >= now() - interval '2 days' AND cost_cents > 0
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_cost_reservations_scope_subject_created', table_name='cost_reservations')
    op.drop_table('cost_reservations')
