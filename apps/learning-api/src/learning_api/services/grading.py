"""Deterministic multiple-choice grading (SPEC §5.9.3). No LLM is ever involved."""

from intellichoice_db.models.assessment import AssessmentAttempt
from intellichoice_db.repositories.assessment import AssessmentRepository


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
) -> tuple[AssessmentAttempt, bool]:
    """Returns `(attempt, created)`. A resubmission with the same
    (session, variant, Idempotency-Key) returns the original stored result instead of
    grading and inserting again (SPEC §5.9.2).
    """
    existing = await assessment_repo.get_attempt_by_idempotency_key(
        assessment_session_id, question_variant_id, idempotency_key
    )
    if existing is not None:
        return existing, False

    attempt = await assessment_repo.record_attempt(
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
    return attempt, True
