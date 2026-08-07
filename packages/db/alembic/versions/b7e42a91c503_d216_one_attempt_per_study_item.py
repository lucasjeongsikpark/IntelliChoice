"""d216_one_attempt_per_study_item

D-216. The StudyItem docstring has always stated the invariant - "the current pending
question is the item lacking a matching StudyAttempt" - but nothing enforced it: a stale
tab re-answering a resolved item appended a second attempt to its skill line, re-ran
`advance_study`'s labeling off an old question, and inflated the "resolving attempt"
denominators `learning_gain`'s dependency rates divide by. The exam path was hardened for
exactly this in b83c1d5f7a02 (AUD-L-10); this is the study-side counterpart.

Safe as a (session, variant) pair because every serving - including a D-210 re-serve of an
already-seen rendering - mints a fresh variant row, so the pair is unique by construction
on the happy path; the constraint exists for the read-then-act race.

Revision ID: b7e42a91c503
Revises: a3f81c62b904
Create Date: 2026-08-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e42a91c503'
down_revision: Union[str, Sequence[str], None] = 'a3f81c62b904'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = 'uq_study_attempts_session_variant'


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.

    # Existing duplicates have to go before the constraint can exist. Keep the *earliest*
    # attempt per item - the one `advance_study` actually labeled and routed on; every
    # later one is the defect this migration exists to prevent. Ordered by `attempt_id`
    # as a tiebreak so the choice is deterministic. On an empty database (CI, and the
    # "migrations must replay from empty" rule) this matches nothing.
    op.execute(
        """
        DELETE FROM study_attempts WHERE attempt_id IN (
            SELECT attempt_id FROM (
                SELECT attempt_id,
                       row_number() OVER (
                           PARTITION BY study_session_id, question_variant_id
                           ORDER BY responded_at, attempt_id
                       ) AS rn
                FROM study_attempts
            ) ranked
            WHERE rn > 1
        )
        """
    )
    op.create_unique_constraint(
        _CONSTRAINT, 'study_attempts', ['study_session_id', 'question_variant_id']
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(_CONSTRAINT, 'study_attempts', type_='unique')
