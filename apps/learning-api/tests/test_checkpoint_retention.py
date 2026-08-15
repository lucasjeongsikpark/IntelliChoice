"""U7/D-333: the retention job's decisions, isolated from its plumbing.

**Every test here is about refusing to delete.** The job's happy path is easy and its failure mode
is silent, irreversible loss of a K-12 student's learning history, so what needs pinning is the set
of conditions under which it declines: consolidation not done, consolidation failed, budget
exhausted, apply not enabled, already deleted.

The database round trip and the "does anything actually break" question belong to
`test_checkpoint_deletion_restore.py`, which deletes a real session's checkpoint and reads the
durable record back.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.models.learning_session import LearningSession
from learning_api.services import checkpoint_retention_cli as cli

NOW = datetime(2026, 8, 15, tzinfo=UTC)


def _summary(**overrides: object) -> LearningSession:
    fields: dict[str, object] = {
        "learning_session_id": "thread-1",
        "student_external_id": "student-ext-1",
        "phase": "completed",
        "bedrock_spend_cents": 0.0,
        "last_activity_at": NOW - timedelta(days=40),
        "memory_consolidated_at": None,
        "checkpoint_deleted_at": None,
        **overrides,
    }
    return LearningSession(**fields)


class _FakeMemoryRepo:
    """Stands in for `MemoryRepository`, which `_ensure_consolidated` uses only to answer
    "was this already consolidated?"."""

    def __init__(self, events: list[object] | None = None, facts: list[object] | None = None):
        self._events = events or []
        self._facts = facts or []

    # The Protocol declares these positionally (`/`), because the real `MemoryRepository`
    # names the same argument `student_external_id` on one method and `student_id` on the
    # other - matching on names would mean mirroring that inconsistency here.
    async def list_events_for_session(self, student_id: str, session_id: str) -> list[object]:
        return self._events

    async def list_facts_for_student(
        self, student_id: str, *, statuses: Sequence[str]
    ) -> list[object]:
        return self._facts


class _Event:
    def __init__(self, event_id: str) -> None:
        self.event_id = event_id


class _Fact:
    def __init__(self, evidence: list[str]) -> None:
        self.evidence_event_ids = evidence


@pytest.mark.parametrize(
    ("events", "facts", "expected", "why"),
    [
        ([], [], True, "no events at all is the no-op case the rule names as success"),
        (
            [_Event("e1")],
            [_Fact(["e1"])],
            True,
            "a live fact citing this session's event proves consolidation already ran",
        ),
        (
            [_Event("e1")],
            [_Fact(["other-session-event"])],
            False,
            "facts exist for the student but none derive from this session",
        ),
        ([_Event("e1")], [], False, "events with no facts at all - never consolidated"),
        (
            [_Event("e1")],
            [_Fact([])],
            False,
            "a fact with empty evidence must not be read as covering anything",
        ),
    ],
)
def test_consolidation_evidence_is_judged_per_session_not_per_student(
    events: list[object], facts: list[object], expected: bool, why: str
) -> None:
    """**The check that keeps the gate honest and affordable at the same time.**

    Per-student would be wrong in the dangerous direction: a student with any fact at all would
    look consolidated for every session they ever had, including one whose events were never
    processed. Per-session costs one extra intersection and cannot make that mistake.
    """
    import asyncio

    result = asyncio.run(
        cli._has_consolidation_evidence(_FakeMemoryRepo(events, facts), "student-ext-1", "thread-1")
    )
    assert result is expected, why


def test_apply_is_off_unless_explicitly_true(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dry-run is the default and every near-miss spelling stays a dry run.

    A job that deletes when its flag is `"True"`, `"1"`, `"yes"` or an accidental `"false "` is a
    job whose safety depends on typing. Only an exact, case-insensitive `true` arms it.
    """
    for value in ("", "false", "1", "yes", "TRUE ", "no", "0", "None"):
        monkeypatch.setenv("CHECKPOINT_RETENTION_APPLY", value)
        assert cli.apply_enabled() is (value.strip().lower() == "true"), value

    monkeypatch.delenv("CHECKPOINT_RETENTION_APPLY", raising=False)
    assert cli.apply_enabled() is False


def test_the_three_windows_are_the_decided_ones() -> None:
    """Pinned because they are a *policy*, not a tuning parameter: 30 days is SPEC's own number
    for completed checkpoints, and 90/180 are the user's decision for pending and chat. A silent
    edit to any of them changes how long a student's data lives."""
    assert cli.COMPLETED_RETENTION_DAYS == 30
    assert cli.ABANDONED_RETENTION_DAYS == 90
    assert cli.CHAT_RETENTION_DAYS == 180


def test_the_windows_are_ordered_shortest_for_the_least_recoverable_case() -> None:
    """A completed session is the safest to delete - it has nothing left to resume and its record
    is fully durable - so it gets the shortest window. A pending session a student may return to
    gets longer. Chat, which has no durable record at all, gets longest. If an edit ever inverts
    that ordering, the policy has stopped matching its own reasoning."""
    assert cli.COMPLETED_RETENTION_DAYS < cli.ABANDONED_RETENTION_DAYS < cli.CHAT_RETENTION_DAYS


def test_the_delete_covers_all_three_checkpoint_tables() -> None:
    """A partial delete leaves a checkpoint LangGraph can load but not resume - worse than either
    deleting or keeping it. `checkpoint_writes` is the one most likely to be forgotten, since it is
    the only one not named in most of the design discussion."""
    assert set(cli._CHECKPOINT_TABLES) == {
        "checkpoints",
        "checkpoint_writes",
        "checkpoint_blobs",
    }


def test_the_chat_classifier_requires_the_absence_of_phase_not_just_a_missing_summary() -> None:
    """**The hole this closes was in my own first implementation.**

    The obvious chat rule is "has checkpoints but no `learning_sessions` row". A *learning* thread
    the reconciler has not projected yet also has no row - so under that rule, if the reconciler
    had never run, every learning thread past 180 days would be deleted here under the chat policy,
    bypassing the consolidation gate. The gate would still be in the code and simply never be
    reached, which is the worst version of a safety check.

    Measured on dev at the time of the fix: 12,836 threads had no summary row, but only **12,716**
    of those also carried no `phase`. The 120-thread difference was real learning threads created
    since the reconciler last ran.

    A source-level assertion, because the behaviour is a SQL predicate: the only honest runtime
    observation would need a 180-day-old unprojected learning thread, which no test database has.
    """
    import inspect

    source = inspect.getsource(cli._chat_thread_ids)
    assert "learning_sessions" in source, "chat threads must exclude anything with a summary row"
    assert "'phase'" in source, (
        "chat classification must also require the absence of `phase` across the thread's "
        "checkpoints - see this test's docstring for what a missing-row-only rule deletes"
    )


def test_a_thread_with_no_student_is_treated_as_nothing_to_remember() -> None:
    """An abandoned thread that never resolved a student emitted no learning events, so there is
    no memory to lose. It must not be blocked forever waiting for a consolidation that can never
    have anything to do."""
    import asyncio

    class _Session:
        async def execute(self, *args: object, **kwargs: object) -> None:
            return None

    counts = cli.RetentionCounts()
    allowed = asyncio.run(
        cli._ensure_consolidated(
            session=_Session(),  # type: ignore[arg-type]
            summary=_summary(student_external_id=None, phase="pre_exam"),
            gateway=None,  # type: ignore[arg-type]
            counts=counts,
        )
    )
    assert allowed is True
    assert counts.already_consolidated == 1
    # And crucially it never reached the gateway, which was None - a call would have raised.
