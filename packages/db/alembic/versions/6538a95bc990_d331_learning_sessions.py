"""d331_learning_sessions - the durable summary a learning session never had

Revision ID: 6538a95bc990
Revises: d4b81f6c2e70
Create Date: 2026-08-14 18:18:45.478396

**Hand-edited, and the edit is the important part.** `alembic revision --autogenerate` produced
this table *plus* `drop_table` for all four LangGraph checkpoint tables and `drop_index` for
`ix_question_variants_origin_rendered_question` and the three `rag_chunks` indexes. Those objects
are real and load-bearing; they are simply not in `Base.metadata`, because LangGraph's
`AsyncPostgresSaver` creates its own schema and those indexes are built by earlier migrations
rather than declared on the models. Autogenerate reads "not in metadata" as "should not exist".

Running the generated version unedited would have deleted every live learning and chat session.
Everything except the `learning_sessions` creation has been removed by hand (D-331 §3).

See U7_CHECKPOINT_CONSOLIDATION.md for what this table is for: the five `LearningState` fields
that the enumeration found had no durable home anywhere.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6538a95bc990"
down_revision: str | Sequence[str] | None = "d4b81f6c2e70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learning_sessions",
        sa.Column("learning_session_id", sa.String(), nullable=False),
        sa.Column("student_external_id", sa.String(), nullable=True),
        sa.Column("parent_external_id", sa.String(), nullable=True),
        sa.Column("user_external_id", sa.String(), nullable=True),
        sa.Column("user_role", sa.String(), nullable=True),
        sa.Column("week_id", sa.String(), nullable=True),
        sa.Column("topic_id", sa.String(), nullable=True),
        sa.Column("phase", sa.String(), nullable=False),
        sa.Column("attendance_status", sa.String(), nullable=True),
        sa.Column("attendance_resolution", sa.String(), nullable=True),
        sa.Column("pre_assessment_session_id", sa.String(), nullable=True),
        sa.Column("study_session_id", sa.String(), nullable=True),
        sa.Column("post_assessment_session_id", sa.String(), nullable=True),
        sa.Column("blocked_session_id", sa.String(), nullable=True),
        sa.Column("bedrock_spend_cents", sa.Float(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checkpoint_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consolidated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("learning_session_id"),
    )
    op.create_index(
        op.f("ix_learning_sessions_parent_external_id"),
        "learning_sessions",
        ["parent_external_id"],
    )
    op.create_index(op.f("ix_learning_sessions_phase"), "learning_sessions", ["phase"])
    op.create_index(
        op.f("ix_learning_sessions_student_external_id"),
        "learning_sessions",
        ["student_external_id"],
    )
    op.create_index(op.f("ix_learning_sessions_topic_id"), "learning_sessions", ["topic_id"])
    op.create_index(op.f("ix_learning_sessions_week_id"), "learning_sessions", ["week_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_learning_sessions_week_id"), table_name="learning_sessions")
    op.drop_index(op.f("ix_learning_sessions_topic_id"), table_name="learning_sessions")
    op.drop_index(
        op.f("ix_learning_sessions_student_external_id"), table_name="learning_sessions"
    )
    op.drop_index(op.f("ix_learning_sessions_phase"), table_name="learning_sessions")
    op.drop_index(
        op.f("ix_learning_sessions_parent_external_id"), table_name="learning_sessions"
    )
    op.drop_table("learning_sessions")
