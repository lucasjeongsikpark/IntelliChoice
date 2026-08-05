"""aud_c_27_rate_limit_events

AUD-C-27. The SPEC §5.24.2 escalation cap (5/hour/caller) was a per-process dict and a
process is one ECS task, so each task enforced a private copy of the cap. Measured on the
deployed system before this migration: 8 escalation drafts accepted from one IP against a
configured 5. This table is the shared counter.

Named for the finding rather than a session number - the S63/S64/S65 mislabel this repo
just corrected is the reason.

`caller_key_hash` holds an HMAC of the caller key, never the key: an anonymous caller's key
is a client IP, and no client IP was persisted anywhere in Postgres before this table
(SPEC §5.30).

Revision ID: a3f81c62b904
Revises: f2c7d91a4e63
Create Date: 2026-08-04 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f81c62b904'
down_revision: Union[str, Sequence[str], None] = 'f2c7d91a4e63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.
    #
    # No backfill, deliberately: the old counters lived in process memory and are gone the
    # moment the task is replaced. Starting empty means the first window after deploy is
    # generous by at most one window's worth of attempts for a caller mid-abuse, which is
    # bounded and self-correcting - unlike cost_reservations, where an empty ledger would
    # have reset a money ceiling.
    op.create_table(
        'rate_limit_events',
        sa.Column('event_id', sa.String(), nullable=False),
        sa.Column('scope', sa.String(), nullable=False),
        sa.Column('caller_key_hash', sa.String(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('event_id'),
    )
    op.create_index(
        'ix_rate_limit_events_scope_caller_created',
        'rate_limit_events',
        ['scope', 'caller_key_hash', 'created_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_rate_limit_events_scope_caller_created', table_name='rate_limit_events'
    )
    op.drop_table('rate_limit_events')
