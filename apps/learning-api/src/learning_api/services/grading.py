"""Deterministic multiple-choice grading (SPEC §5.9.3). No LLM is ever involved."""

from typing import Literal

from intellichoice_db.models.assessment import AssessmentAttempt
from intellichoice_db.repositories.assessment import AssessmentRepository


class ItemAlreadyAnsweredError(Exception):
    """AUD-L-10: this exam item already has a recorded attempt and this submission is not a
    replay of it. Exam items are grade-on-submit and locked once answered (D-064); the
    `Idempotency-Key` deduplicates a retry of *the same* submission, it does not license a
    second answer, and scoring counts attempts, so a second one corrupts the score.

    Defined here rather than in `flow` because the insert that detects the race lives here
    and `flow` already imports this module; `flow` re-exports it for its callers.
    """

    def __init__(self, question_variant_id: str) -> None:
        self.question_variant_id = question_variant_id
        super().__init__(f"item {question_variant_id} has already been answered")


def grade(selected_option: str | None, correct_option: str) -> bool:
    # `selected_option is None` (S22: an item skipped through to `finalize_exam`) is
    # always incorrect - it never equals a real option string, so no special case needed.
    return selected_option == correct_option


async def record_assessment_attempt_idempotent(
    *,
    assessment_repo: AssessmentRepository,
    student_external_id: str,
    assessment_session_id: str,
    question_variant_id: str,
    correct_option: str,
    selected_option: str | None,
    response_time_ms: int,
    idempotency_key: str,
    on_duplicate_item: Literal["conflict", "keep_existing"],
) -> tuple[AssessmentAttempt, bool]:
    """Returns `(attempt, created)`. A resubmission with the same
    (session, variant, Idempotency-Key) returns the original stored result instead of
    grading and inserting again (SPEC §5.9.2).

    `on_duplicate_item` says what to do when the item already has an attempt under a
    *different* key - the AUD-L-10 case, now refused by
    `uq_assessment_attempts_session_variant`:

    - `"conflict"` for the student answer paths: a second answer is a client defect and
      must surface, not be absorbed.
    - `"keep_existing"` for `finalize_exam`'s synthesizer, where losing the race means a
      concurrent finalize already recorded the item and the correct behaviour is to serve
      that row.

    Required rather than defaulted, on the same reasoning as `generate_student_report`'s
    `session_spend_cents` (AUD-L-02): the recurring defect in this codebase is a caller
    quietly getting the permissive branch, so a new call site should fail typecheck rather
    than pick a behaviour by accident.
    """
    existing = await assessment_repo.get_attempt_by_idempotency_key(
        assessment_session_id, question_variant_id, idempotency_key
    )
    if existing is not None:
        return existing, False

    attempt = await assessment_repo.record_attempt_if_first(
        AssessmentAttempt(
            student_external_id=student_external_id,
            assessment_session_id=assessment_session_id,
            question_variant_id=question_variant_id,
            selected_option=selected_option,
            correct_option=correct_option,
            is_correct=grade(selected_option, correct_option),
            response_time_ms=response_time_ms,
            idempotency_key=idempotency_key,
        )
    )
    if attempt is not None:
        return attempt, True

    # The constraint rejected the insert: another request recorded this item between the
    # `flow.ensure_item_unanswered` read and here. That read-then-act window is why the
    # constraint exists rather than the check alone.
    if on_duplicate_item == "conflict":
        raise ItemAlreadyAnsweredError(question_variant_id)
    winner = next(
        a
        for a in await assessment_repo.get_attempts(assessment_session_id)
        if a.question_variant_id == question_variant_id
    )
    return winner, False
