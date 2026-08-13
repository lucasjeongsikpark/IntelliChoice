"""d295 validation run pipeline_run_id

Adds `question_validation_runs.pipeline_run_id` - which `run_plan` invocation produced a
candidate (D-295).

**Why.** The re-tier guard is run-scoped by design (D-231): the judge's difficulty
histogram is rebuilt per run, so whether a candidate could be re-tiered instead of rejected
depends on its position within its own run. The table had no way to say which run a row
belonged to, so D-295 had to infer run boundaries by clustering `created_at` - a
reconstruction that reproduced only ~90% of the recorded decisions, which is precisely the
margin that made "how many rejections did the guard cause" impossible to pin down. Per-run
yield and per-run spend had the same problem.

Nullable, and deliberately not backfilled: every row written before this column existed has
no honest value for it, and inventing one from the `created_at` clustering would bake a
~10%-wrong guess into the data as though it were recorded fact. `NULL` means "written
before runs were identified", which is true and checkable.

Indexed because every intended query groups by it.

Additive and reversible: no data is rewritten, and the downgrade drops a column nothing
else references.

Revision ID: d4b81f6c2e70
Revises: 6aef7adeed26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4b81f6c2e70"
down_revision: str | Sequence[str] | None = "6aef7adeed26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_validation_runs",
        sa.Column("pipeline_run_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_question_validation_runs_pipeline_run_id",
        "question_validation_runs",
        ["pipeline_run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_question_validation_runs_pipeline_run_id",
        table_name="question_validation_runs",
    )
    op.drop_column("question_validation_runs", "pipeline_run_id")
