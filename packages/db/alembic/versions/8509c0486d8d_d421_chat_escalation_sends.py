"""d421 chat escalation sends

Revision ID: 8509c0486d8d
Revises: a1c7e2b90d44
Create Date: 2026-08-18 15:52:51.632559

One row per escalation email actually sent, so the same question is not emailed to staff twice
(D-421). Additive: a new table and nothing else, so this replays from empty and reverses cleanly.

See `intellichoice_db.models.chat_escalation_send` for why the column is a fingerprint rather than
the question text, and why the key is the question rather than the question plus the visitor's note.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8509c0486d8d"
down_revision: str | Sequence[str] | None = "a1c7e2b90d44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_escalation_sends",
        sa.Column("chat_session_id", sa.String(), nullable=False),
        # SHA-256 hex: 64 characters, fixed by the digest rather than by a guess about how long a
        # question is. The question itself is never stored (SPEC §5.30).
        sa.Column("question_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Composite PK, so the claim can be a single `ON CONFLICT DO NOTHING ... RETURNING` and the
        # database decides which of two concurrent replicas sends. It is also the lookup.
        sa.PrimaryKeyConstraint("chat_session_id", "question_fingerprint"),
    )


def downgrade() -> None:
    op.drop_table("chat_escalation_sends")
