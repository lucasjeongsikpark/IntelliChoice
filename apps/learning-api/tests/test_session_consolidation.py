"""U7/D-331: projecting checkpoint state into a durable summary.

These test `summary_from_state` rather than the whole CLI, because the projection is where the
decisions live: what counts as a learning thread, and which fields survive. The database round trip
is covered by `packages/db/tests/test_learning_session_repository.py`.

**The classification tests are the load-bearing ones.** `checkpoints` is shared with chat-api -
measured on dev at 31,416 learning-only threads against 12,638 chat-only, zero overlap (D-331 §3).
A projection that mistakes a chat thread for a learning one writes a `learning_sessions` row for a
session that is not one; a rule that infers "learning" from a *missing* chat field breaks silently
the first time either state model grows a field.
"""

from datetime import UTC, datetime

from learning_api.services.session_consolidation_cli import summary_from_state

ACTIVITY = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)

# A learning thread mid-study, with all five orphan fields set.
LEARNING_STATE = {
    "session_id": "thread-1",
    "phase": "study",
    "student_external_id": "student-ext-1",
    "parent_external_id": "parent-ext-9",
    "user_external_id": "user-ext-1",
    "user_role": "parent",
    "week_id": "2026-W33",
    "topic_id": "topic-fractions",
    "attendance_status": "PRESENT",
    "attendance_resolution": None,
    "pre_assessment_session_id": "pre-1",
    "study_session_id": "study-1",
    "post_assessment_session_id": None,
    "blocked_session_id": None,
    "bedrock_spend_cents": 3.5,
    # Transient working state, deliberately not projected.
    "last_items": [{"question": "…"}],
    "entry_action": "submit_answer",
}

# What chat-api's `QAState` actually looks like. It shares `session_id`, `user_external_id`,
# `user_role` and `bedrock_spend_cents` with `LearningState` - which is exactly why the
# discriminator cannot be any of those.
CHAT_STATE = {
    "session_id": "thread-2",
    "user_external_id": "user-ext-2",
    "user_role": "student",
    "authenticated": True,
    "query": "when does the Saturday class start?",
    "answer": "…",
    "citations": ["chunk-1"],
    "bedrock_spend_cents": 1.25,
}


def test_a_learning_thread_projects_every_orphan_field() -> None:
    summary = summary_from_state("thread-1", LEARNING_STATE, ACTIVITY)

    assert summary is not None
    assert summary.week_id == "2026-W33"
    assert summary.parent_external_id == "parent-ext-9"
    assert summary.bedrock_spend_cents == 3.5
    assert summary.attendance_status == "PRESENT"
    assert summary.phase == "study"
    assert summary.last_activity_at == ACTIVITY


def test_a_chat_thread_is_skipped() -> None:
    """`QAState` has `session_id` but never `phase`, so it must not produce a row."""
    assert summary_from_state("thread-2", CHAT_STATE, ACTIVITY) is None


def test_an_empty_checkpoint_is_skipped() -> None:
    """A thread's first checkpoint carries `__start__` and nothing else - measured directly in the
    dev database. Projecting that would write a row with a NULL `phase` into a NOT NULL column."""
    assert summary_from_state("thread-3", {}, ACTIVITY) is None


def test_classification_requires_phase_positively_not_the_absence_of_chat_fields() -> None:
    """**The rule this codifies:** a thread is a learning thread because it has `session_id` *and*
    `phase`, not because it lacks `citations`.

    The distinction is not academic. If chat ever adds a field named `phase`, or if a learning
    state is checkpointed before `phase` is set, an absence-based rule gets it wrong in the
    direction that writes bad rows. This asserts the positive form directly: a state carrying every
    chat marker still projects, so long as it is genuinely a learning session.
    """
    hybrid = {**CHAT_STATE, "phase": "post_exam", "student_external_id": "student-ext-3"}
    summary = summary_from_state("thread-4", hybrid, ACTIVITY)

    assert summary is not None
    assert summary.phase == "post_exam"


def test_a_null_spend_becomes_zero_not_null() -> None:
    """`bedrock_spend_cents` is NOT NULL in the table, but a checkpoint written before the field
    existed carries an explicit `None`. A `.get(field, 0.0)` default would not catch that - the key
    is present, its value is null - so the projection coerces instead of defaulting."""
    summary = summary_from_state(
        "thread-5", {**LEARNING_STATE, "bedrock_spend_cents": None}, ACTIVITY
    )

    assert summary is not None
    assert summary.bedrock_spend_cents == 0.0


def test_transient_working_state_is_not_projected() -> None:
    """The summary is a durable record, not a second copy of the checkpoint. `last_items` alone is
    73 MB of blob bytes on dev; copying working state here would recreate the growth U7 exists to
    bound."""
    summary = summary_from_state("thread-6", LEARNING_STATE, ACTIVITY)

    assert summary is not None
    assert not hasattr(summary, "last_items")
    assert not hasattr(summary, "entry_action")


def test_missing_optional_fields_become_none_rather_than_raising() -> None:
    """A checkpoint from an older schema will not have every field. The reconciler runs unattended
    over every thread in the database, so one old checkpoint must not end the run."""
    minimal = {"session_id": "thread-7", "phase": "created"}
    summary = summary_from_state("thread-7", minimal, ACTIVITY)

    assert summary is not None
    assert summary.student_external_id is None
    assert summary.week_id is None
    assert summary.bedrock_spend_cents == 0.0
