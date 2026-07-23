"""S22 (SPEC §5.9/§5.13, D-064): `AssessmentPolicy` matrix - pure unit, no DB. Covers the
ROADMAP "hints are refused in pre/post and allowed in study (policy matrix test)" and
"timed only pre/post" Done-when criteria.
"""

from learning_api.services import exam_policy


def test_hints_allowed_only_in_study() -> None:
    assert exam_policy.get_policy("study").hints_allowed is True
    assert exam_policy.get_policy("pre_exam").hints_allowed is False
    assert exam_policy.get_policy("post_exam").hints_allowed is False


def test_only_pre_and_post_exam_are_timed() -> None:
    expected = exam_policy.EXAM_TIME_LIMIT_SECONDS
    assert exam_policy.get_policy("study").time_limit_seconds is None
    assert exam_policy.get_policy("pre_exam").time_limit_seconds == expected
    assert exam_policy.get_policy("post_exam").time_limit_seconds == expected


def test_only_pre_and_post_exam_allow_free_navigation() -> None:
    assert exam_policy.get_policy("study").navigation == "sequential"
    assert exam_policy.get_policy("pre_exam").navigation == "free"
    assert exam_policy.get_policy("post_exam").navigation == "free"


def test_feedback_visibility_matches_grading_model() -> None:
    # D-064: grading itself stays immediate everywhere - only the *response* withholds
    # correctness during pre/post exam, until an explicit finalize.
    assert exam_policy.get_policy("study").feedback_visibility == "immediate"
    assert exam_policy.get_policy("pre_exam").feedback_visibility == "hidden_until_finalize"
    assert exam_policy.get_policy("post_exam").feedback_visibility == "hidden_until_finalize"
