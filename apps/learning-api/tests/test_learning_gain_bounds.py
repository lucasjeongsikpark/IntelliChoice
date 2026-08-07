"""AUD-L-08: `normalized_gain`'s denominator and bounds (SPEC §5.13.3).

The finding's reproduction table showed four inputs where the attempt-count denominator
produced an unflagged 133%, 600%, or 1000% "normalized gain", and a live journey stored an
unflagged −200%. The fix (D-175 §5's recorded decision, implemented here): the denominator
is the assessment's *declared* item count, and a quotient still outside [-1, 1] is flagged
`unmeasurable_out_of_range` rather than clamped — clamping would turn a −200% into a
plausible −100%, which is the finding's own complaint.

Every case below is one row of the finding's table (or its reachability correction),
re-run through the real function.
"""

import asyncio

from intellichoice_db.models.assessment import AssessmentAttempt
from learning_api.services.learning_gain import LearningGainResult, compute_learning_gain


class _FakeVariant:
    question_variant_id = "v"
    question_template_id = "t"


class _FakeTemplate:
    skill_id = "linear_two_step"
    difficulty_label = 2


class _FakeQuestionRepo:
    async def get_variant(self, _variant_id: str) -> _FakeVariant:
        return _FakeVariant()

    async def get_template(self, _template_id: str) -> _FakeTemplate:
        return _FakeTemplate()

    # D-217: `resolve_graded_attempts` now batches, so the fake mirrors the real batch
    # forms (dict keyed by id).
    async def get_variants(self, variant_ids) -> dict[str, "_FakeVariant"]:
        return {variant_id: _FakeVariant() for variant_id in variant_ids}

    async def get_templates(self, template_ids) -> dict[str, "_FakeTemplate"]:
        return {template_id: _FakeTemplate() for template_id in template_ids}


def _attempt(*, is_correct: bool) -> AssessmentAttempt:
    return AssessmentAttempt(
        student_external_id="s",
        assessment_session_id="a",
        question_variant_id="v",
        selected_option="a",
        correct_option="a" if is_correct else "b",
        is_correct=is_correct,
        response_time_ms=1000,
    )


def _attempts(correct: int, incorrect: int) -> list[AssessmentAttempt]:
    return [_attempt(is_correct=True) for _ in range(correct)] + [
        _attempt(is_correct=False) for _ in range(incorrect)
    ]


def _gain(
    *, declared_item_count: int, pre: list[AssessmentAttempt], post: list[AssessmentAttempt]
) -> LearningGainResult:
    return asyncio.run(
        compute_learning_gain(
            question_repo=_FakeQuestionRepo(),  # type: ignore[arg-type]
            declared_item_count=declared_item_count,
            pre_attempts=pre,
            post_attempts=post,
        )
    )


def test_normal_gain_is_computed_and_unflagged() -> None:
    """The finding's control row: 10 items, pre 4 → post 6 is 0.333, no flag."""
    gain = _gain(declared_item_count=10, pre=_attempts(4, 6), post=_attempts(6, 4))
    assert gain.normalized_gain is not None
    assert abs(gain.normalized_gain - (6 - 4) / (10 - 4)) < 1e-9
    assert gain.normalized_gain_status is None


def test_negative_gain_within_bounds_is_unflagged() -> None:
    """A real regression at the boundary: (6−8)/(10−8) = −1.0. A −100% is the worst
    measurable outcome (every pre-exam point lost), so it stays unflagged."""
    gain = _gain(declared_item_count=10, pre=_attempts(8, 2), post=_attempts(6, 4))
    assert gain.normalized_gain == -1.0
    assert gain.normalized_gain_status is None


def test_the_live_minus_200_percent_case_is_flagged_not_clamped() -> None:
    """The reachability correction's live row: 8/10 → 4/10 stored an unflagged −2.0.
    The value must survive (diagnosis) and the flag must be set (suppression)."""
    gain = _gain(declared_item_count=10, pre=_attempts(8, 2), post=_attempts(4, 6))
    assert gain.normalized_gain == -2.0
    assert gain.normalized_gain_status == "unmeasurable_out_of_range"


def test_duplicate_post_attempt_no_longer_inflates_the_denominator() -> None:
    """The finding's ">1 via AUD-L-10" row: an 11th post attempt against a declared
    10-item form. With the attempt-count denominator this was 1.333 unflagged; the
    declared count keeps the quotient in range."""
    gain = _gain(declared_item_count=10, pre=_attempts(4, 6), post=_attempts(10, 1))
    assert gain.normalized_gain is not None
    assert abs(gain.normalized_gain - 1.0) < 1e-9
    assert gain.normalized_gain_status is None


def test_zero_pre_attempts_is_not_a_600_percent_gain() -> None:
    """The finding's "no pre attempts, post 6 correct" row: the old `or 1.0` guard
    fabricated a denominator of 1 and reported 6.0 unflagged."""
    gain = _gain(declared_item_count=10, pre=[], post=_attempts(6, 4))
    assert gain.normalized_gain == 6 / 10
    assert gain.normalized_gain_status is None


def test_short_pre_form_no_longer_reports_1000_percent() -> None:
    """The finding's "pre 1 item wrong, post 10 correct" row: attempt-count denominator
    reported 10.0 unflagged. Against the declared 10-item form this is a full gain."""
    gain = _gain(declared_item_count=10, pre=_attempts(0, 1), post=_attempts(10, 0))
    assert gain.normalized_gain == 1.0
    assert gain.normalized_gain_status is None


def test_extra_pre_attempt_no_longer_hides_not_applicable_pre_max() -> None:
    """The finding's opposite-direction row: a genuine 10/10 pre-exam plus one duplicate
    pre attempt made `pre_raw < max_score` (10 < 11), so the unmeasurable flag vanished
    exactly when it applied. The declared count keeps it on."""
    gain = _gain(declared_item_count=10, pre=_attempts(10, 1), post=_attempts(10, 0))
    assert gain.normalized_gain is None
    assert gain.normalized_gain_status == "not_applicable_pre_max"


def test_perfect_pre_exam_still_reports_not_applicable_pre_max() -> None:
    gain = _gain(declared_item_count=10, pre=_attempts(10, 0), post=_attempts(10, 0))
    assert gain.normalized_gain is None
    assert gain.normalized_gain_status == "not_applicable_pre_max"
