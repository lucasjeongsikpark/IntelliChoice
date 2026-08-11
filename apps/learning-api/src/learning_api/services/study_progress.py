"""How far through the study phase a student is (D-272).

### Why this counts skill lines and not questions

The study screen said `Practice question 4` with no denominator, and `ExamScreen` carried a
comment explaining that the denominator was unknowable: `create_study_item` assigns
`display_order = len(items)` and the retry ladder adds items as the student needs them, so the
total is not decided until the session ends. Printing `base_problem_count` there would say
"4 of 5" and then serve a sixth.

That reasoning is right about *questions* and it hides a denominator that is genuinely fixed.
`StudySession.target_skill_ids` is chosen once, at plan time, and never grows - five skills
(`study_plan.BASE_PROBLEM_COUNT`). Each one is worked until its line resolves. So **"skill 3 of
5" is a fact**, and inside a line "try 2 of 4" is another (`maximum_attempts_per_skill`). Two
honest bounded numbers where there was one unbounded one.

The trade is that the two counters move at different speeds - a student can sit on skill 3 for
four questions - and that is a truthful thing to show. A single fake percentage that ran
backwards when the ladder added a question would be worse.

### Deterministic, and it has to be

This is SPEC §5.11 routing state read back out. No LLM, no estimate, no prediction (CLAUDE.md
#2). It reads rows the answer turn has already committed, so it can never disagree with the
question actually on screen.

### No PII

Skill *names* from the curriculum content, never `skill_id` (SPEC §5.10.3: internal ids stay
internal). Names are curriculum text, not student data.
"""

from dataclasses import dataclass

from intellichoice_curriculum.content import load_curriculum
from intellichoice_db.models.mastery import StudyAttempt, StudyItem, StudySession

from learning_api.services import study_outcomes


@dataclass(frozen=True)
class StudyProgress:
    skills_total: int
    skills_resolved: int
    current_skill_name: str | None
    current_skill_position: int | None
    attempt_in_line: int
    max_attempts: int


def _skill_names() -> dict[str, str]:
    return {skill.skill_id: skill.name for skill in load_curriculum().skills}


def compute(
    session_row: StudySession,
    items: list[StudyItem],
    attempts: list[StudyAttempt],
) -> StudyProgress:
    """Pure: rows in, counters out. No I/O, so the routing arithmetic is unit-testable on
    its own the way `study_outcomes` is.

    `items` is expected in `display_order` (what `StudyRepository.get_items` returns), because
    the last one is the question on screen and that is what names the current line.
    """
    targets = list(session_row.target_skill_ids)
    line_of = {item.question_variant_id: item.target_skill_id for item in items}

    # A line is resolved when one of its attempts carries a *terminal* label. Not "has any
    # label": an attempt mid-ladder is labelled `incorrect` or `answer_revealed`, and
    # counting those would march the progress bar forward on every wrong answer, which is
    # the opposite of what it should tell a struggling student.
    resolved = {
        line_of[attempt.question_variant_id]
        for attempt in attempts
        if attempt.question_variant_id in line_of
        and attempt.outcome_label in study_outcomes.RESOLVING_LABELS
    }

    current_skill_id = items[-1].target_skill_id if items else None
    # Items served on the current line, which is exactly "which try the student is on" -
    # item 1 of the line is try 1. Counted from items rather than attempts so the number is
    # right *while* the question is on screen and its attempt does not exist yet.
    attempt_in_line = (
        sum(1 for item in items if item.target_skill_id == current_skill_id)
        if current_skill_id is not None
        else 0
    )

    names = _skill_names()
    return StudyProgress(
        skills_total=len(targets),
        # Clamped to the total. A line can only resolve once, and `targets` is fixed, so this
        # cannot exceed it - but a progress bar that reads "6 of 5" in front of a child is the
        # kind of thing worth making unrepresentable rather than arguing about.
        skills_resolved=min(len(resolved & set(targets)), len(targets)),
        current_skill_name=names.get(current_skill_id) if current_skill_id else None,
        # 1-based, and `None` for a skill that is not one of the plan's targets - which is
        # what a prerequisite remediation item is. Its `target_skill_id` is still the base
        # skill, so in practice this resolves; `None` rather than a guess if that ever changes.
        current_skill_position=(
            targets.index(current_skill_id) + 1
            if current_skill_id is not None and current_skill_id in targets
            else None
        ),
        attempt_in_line=attempt_in_line,
        max_attempts=session_row.maximum_attempts_per_skill,
    )
