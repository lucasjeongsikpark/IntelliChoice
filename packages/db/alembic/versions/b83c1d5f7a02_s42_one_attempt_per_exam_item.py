"""s42_one_attempt_per_exam_item

AUD-L-10. Scoring reads `len(pre_graded)` - the *attempt* count - as an exam's max score,
so it has always assumed one attempt per item. Nothing enforced that: uniqueness included
`idempotency_key`, which makes a resubmission under a *new* key a second graded attempt.
One changed answer rescored a 10-item exam as 10/11 and silently replaced the
`not_applicable_pre_max` flag with a computed gain.

Enforced in the database rather than only in the service, because a read-then-act check in
Python is exactly the shape AUD-X-08 is in this same cluster for: two concurrent answers
under different keys would both pass it. `flow` still checks first, so the ordinary path
gets a 409 instead of an IntegrityError; this constraint is what makes the invariant true.

Revision ID: b83c1d5f7a02
Revises: a71c4e2f9b83
Create Date: 2026-07-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b83c1d5f7a02'
down_revision: Union[str, Sequence[str], None] = 'a71c4e2f9b83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_CONSTRAINT = 'assessment_attempts_assessment_session_id_question_variant__key'
_NEW_CONSTRAINT = 'uq_assessment_attempts_session_variant'


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: as in every migration since f6dcf62cdba4, the autogenerate diff's proposal to
    # drop/recreate the LangGraph checkpoint tables and three rag_chunks indexes is the
    # known false positive and is omitted.

    # Existing duplicates have to go before the constraint can exist. Keep the *earliest*
    # attempt per item: D-064 made exam items grade-on-submit and locked once answered
    # ("answered items are locked" - flow.mark_item_flagged), so the first attempt is the
    # one the system meant to record and every later one is the defect. Ordered by
    # `attempt_id` as a tiebreak so the choice is deterministic rather than
    # physical-row-order dependent.
    #
    # Two rows matched in the dev database, both left by S38's AUD-L-10 probe. On an empty
    # database (CI, and the "migrations must replay from empty" rule) this matches nothing.
    op.execute(
        """
        DELETE FROM assessment_attempts WHERE attempt_id IN (
            SELECT attempt_id FROM (
                SELECT attempt_id,
                       row_number() OVER (
                           PARTITION BY assessment_session_id, question_variant_id
                           ORDER BY submitted_at, attempt_id
                       ) AS rn
                FROM assessment_attempts
            ) ranked
            WHERE rn > 1
        )
        """
    )

    op.drop_constraint(_OLD_CONSTRAINT, 'assessment_attempts', type_='unique')
    op.create_unique_constraint(
        _NEW_CONSTRAINT,
        'assessment_attempts',
        ['assessment_session_id', 'question_variant_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # The deleted duplicate rows are not restored - a downgrade returns the schema, not the
    # data the constraint was incompatible with.
    op.drop_constraint(_NEW_CONSTRAINT, 'assessment_attempts', type_='unique')
    op.create_unique_constraint(
        _OLD_CONSTRAINT,
        'assessment_attempts',
        ['assessment_session_id', 'question_variant_id', 'idempotency_key'],
    )
