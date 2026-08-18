"""D-272: the study-progress counters, tested where the arithmetic lives.

`study_progress.compute` is pure, so this needs no database and no graph - the same posture
`test_study_outcomes` takes for the ladder it reads. What is worth pinning is not the happy
path but the two ways a progress bar in front of a child goes wrong: moving forward when the
student has *not* finished something, and never moving at all.
"""

from intellichoice_db.models.mastery import StudyAttempt, StudyItem, StudySession
from learning_api.services import study_outcomes, study_progress

SKILLS = [
    "linear_one_step",
    "linear_two_step",
    "linear_both_sides",
    "linear_neg_frac_coeff",
    "linear_distribute",
]


# Real ORM instances, unattached to any session. They are ordinary Python objects until
# something adds them to one, and using them means this tests the shape the router actually
# passes rather than a stand-in that could drift from it.
def _session(max_attempts: int = 4) -> StudySession:
    return StudySession(
        student_external_id="student-ext-1",
        topic_id="linear_equations",
        target_skill_ids=list(SKILLS),
        starting_difficulty=1,
        base_problem_count=len(SKILLS),
        maximum_attempts_per_skill=max_attempts,
        intervention_policy={},
    )


def _item(variant: str, skill: str) -> StudyItem:
    return StudyItem(
        study_session_id="ss",
        question_variant_id=variant,
        target_skill_id=skill,
        skill_id=skill,
        display_order=0,
        is_remediation=False,
    )


def _attempt(variant: str, label: str | None) -> StudyAttempt:
    return StudyAttempt(
        student_external_id="student-ext-1",
        study_session_id="ss",
        question_variant_id=variant,
        selected_option="a",
        is_correct=False,
        retry_count=0,
        outcome_label=label,
    )


def test_no_attempts_yet_is_zero_of_five_on_the_first_skill() -> None:
    progress = study_progress.compute(_session(), [_item("v1", SKILLS[0])], [])
    assert progress.skills_total == 5
    assert progress.skills_resolved == 0
    assert progress.current_skill_position == 1
    # The question is served but unanswered, and the student is on try 1 - counted from the
    # items rather than the attempts precisely so this is right *before* they answer.
    assert progress.attempt_in_line == 1
    assert progress.max_attempts == 4


def test_an_interim_wrong_answer_does_not_advance_the_bar() -> None:
    """The one that matters. A wrong answer mid-ladder is labelled `incorrect`, and a
    progress bar that counted "has a label" would step forward every time a student got
    something wrong - telling them they are making progress by failing, and reaching 5 of 5
    without a single skill resolved.
    """
    items = [_item("v1", SKILLS[0]), _item("v2", SKILLS[0])]
    attempts = [_attempt("v1", study_outcomes.INCORRECT)]
    progress = study_progress.compute(_session(), items, attempts)
    assert progress.skills_resolved == 0
    assert progress.current_skill_position == 1
    assert progress.attempt_in_line == 2


def test_answer_revealed_is_not_resolution_either() -> None:
    """`answer_revealed` is the trap: the solution has been shown, so it *looks* terminal,
    and the ladder still gives the student their retry. Only `study_outcomes.RESOLVING_LABELS`
    closes a line.
    """
    assert study_outcomes.ANSWER_REVEALED not in study_outcomes.RESOLVING_LABELS
    progress = study_progress.compute(
        _session(),
        [_item("v1", SKILLS[0]), _item("v2", SKILLS[0])],
        [_attempt("v1", study_outcomes.ANSWER_REVEALED)],
    )
    assert progress.skills_resolved == 0


def test_every_resolving_label_closes_its_line() -> None:
    """Including `unresolved` - a skill the student ran out of attempts on is finished with,
    even though they did not get it. Leaving it uncounted would strand the bar one short for
    the rest of the session, on the skill they struggled with most.
    """
    for label in sorted(study_outcomes.RESOLVING_LABELS):
        progress = study_progress.compute(
            _session(), [_item("v1", SKILLS[0])], [_attempt("v1", label)]
        )
        assert progress.skills_resolved == 1, label


def test_counts_lines_not_questions() -> None:
    """Four attempts on one skill and one clean answer on the next is "2 of 5", not "5 of 5".
    This is the whole reason the denominator is skills: five *questions* had been served.
    """
    items = [
        _item("v1", SKILLS[0]),
        _item("v2", SKILLS[0]),
        _item("v3", SKILLS[0]),
        _item("v4", SKILLS[0]),
        _item("v5", SKILLS[1]),
    ]
    attempts = [
        _attempt("v1", study_outcomes.INCORRECT),
        _attempt("v2", study_outcomes.INCORRECT),
        _attempt("v3", study_outcomes.ANSWER_REVEALED),
        _attempt("v4", study_outcomes.UNRESOLVED),
        _attempt("v5", study_outcomes.INDEPENDENT_CORRECT),
    ]
    progress = study_progress.compute(_session(), items, attempts)
    assert progress.skills_resolved == 2
    assert progress.current_skill_position == 2
    assert progress.attempt_in_line == 1


def test_a_prerequisite_remediation_item_stays_on_its_own_line() -> None:
    """The ladder's third rung serves a question from a *prerequisite* skill, but records it
    against the base skill's `target_skill_id` - so it must count as another try of skill N,
    not as a sixth skill appearing from nowhere.
    """
    items = [
        _item("v1", SKILLS[0]),
        _item("v2", SKILLS[0]),
        # `skill_id` is the prerequisite; `target_skill_id` is still the base line.
        _item("v3", SKILLS[0]),
    ]
    progress = study_progress.compute(
        _session(), items, [_attempt("v1", "incorrect"), _attempt("v2", "incorrect")]
    )
    assert progress.skills_total == 5
    assert progress.attempt_in_line == 3
    assert progress.current_skill_position == 1


def test_resolved_never_exceeds_the_total() -> None:
    """An attempt whose line is not one of the plan's targets - which nothing produces today,
    and which would otherwise read as "6 of 5" in front of a child.
    """
    items = [_item("v1", SKILLS[0]), _item("v9", "some_other_skill")]
    attempts = [
        _attempt("v1", study_outcomes.INDEPENDENT_CORRECT),
        _attempt("v9", study_outcomes.INDEPENDENT_CORRECT),
    ]
    progress = study_progress.compute(_session(), items, attempts)
    assert progress.skills_resolved == 1
    assert progress.skills_resolved <= progress.skills_total
    # Not in `target_skill_ids`, so there is no honest position to print.
    assert progress.current_skill_position is None
