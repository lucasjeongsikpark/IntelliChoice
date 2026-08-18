"""Bootstrap mastery model (SPEC §5.10.1). Pure deterministic scoring - no LLM.

The enterprise IRT/Bayesian model (§5.10.2) still needs production response data that
doesn't exist pre-launch, so S10 keeps this bootstrap formula and adds only the pieces the
adaptive planner needs on top of it: outcome-aware grading (a study answer counts toward
*independent* mastery only if it was `independent_correct`, §5.10.3/§5.11.5) and a
deterministic `recommended_difficulty` for difficulty routing (§5.11.2 rules 2-3).

**What `recommended_difficulty` actually routes** (AUD-L-12, corrected 2026-08-03 - this
docstring previously claimed routing that did not exist): it narrows *template choice within
an already-chosen skill*, in `study_plan._select_template`. It does not choose the skill -
§5.11.2 ranks "lowest mastery skill" above "difficulty matching estimated level", so the
weakest skill is served even when its tier is above the recommendation - and it is not
assigned to `StudySession.starting_difficulty`, which records the tier actually served.
On the current 1:1 skill<->difficulty bank the narrowing is inert by construction; see
`_closest_to_recommended`.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from intellichoice_db.models.assessment import AssessmentAttempt
from intellichoice_db.models.mastery import StudyAttempt
from intellichoice_db.repositories.questions import QuestionRepository

from learning_api.services import study_outcomes

DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.4, 3: 1.9, 4: 2.5, 5: 3.2}
MIN_DIFFICULTY = 1
MAX_DIFFICULTY = 5

# D-017's weak-skill cut used to live here. It moved to
# `intellichoice_shared.mastery_policy` in D-156 (AUD-L-13): `intellichoice_memory
# .consolidation` needs the same number to check a proposed memory fact against measured
# mastery, and a package cannot import an app. Import it from there.

# Difficulty-routing thresholds (§5.11.2 rules 2-3, §5.10): step up a level when the
# student is clearly on top of the current one, hold steady when they're passing, step
# down otherwise. Deterministic so identical inputs route identically (Phase 10).
STEP_UP_ACCURACY = 0.8
HOLD_ACCURACY = 0.5


@dataclass(frozen=True)
class GradedAttempt:
    skill_id: str
    difficulty: int
    is_correct: bool


def _study_counts_as_correct(attempt: StudyAttempt) -> bool:
    """A study attempt contributes a *correct* to mastery only if it was independently
    correct - hint/video/solution-assisted corrects don't (SPEC §5.10.3, §5.11.5).
    """
    return attempt.is_correct and study_outcomes.counts_as_independent(attempt.outcome_label)


async def resolve_graded_attempts(
    question_repo: QuestionRepository,
    attempts: Iterable[AssessmentAttempt | StudyAttempt],
) -> list[GradedAttempt]:
    """Joins attempt rows (assessment or study - both have `question_variant_id`) through
    `question_variants` -> `question_templates` to get the skill/difficulty each attempt
    counts toward. Assessment attempts count their raw `is_correct`; study attempts count
    as correct only when independently correct (`_study_counts_as_correct`), so an
    assisted or unresolved study answer never inflates mastery.
    """
    # D-217: batched, not a `get_variant`+`get_template` pair per attempt. This runs on
    # every study answer over *all* pre-exam + study attempts (`_recompute_all_skill_
    # mastery`), so the per-attempt round-trips grew with the session; two `IN (...)`
    # queries make it flat. `get_variants`/`get_templates` are the AUD-F-31 batch forms.
    attempts = list(attempts)
    variants = await question_repo.get_variants([a.question_variant_id for a in attempts])
    templates = await question_repo.get_templates(
        [v.question_template_id for v in variants.values()]
    )
    graded: list[GradedAttempt] = []
    for attempt in attempts:
        variant = variants[attempt.question_variant_id]
        template = templates[variant.question_template_id]
        if isinstance(attempt, StudyAttempt):
            is_correct = _study_counts_as_correct(attempt)
        else:
            is_correct = attempt.is_correct
        graded.append(
            GradedAttempt(
                skill_id=template.skill_id,
                difficulty=template.difficulty_label,
                is_correct=is_correct,
            )
        )
    return graded


def raw_accuracy(attempts: list[GradedAttempt]) -> float:
    if not attempts:
        return 0.0
    return sum(1 for a in attempts if a.is_correct) / len(attempts)


def weighted_score(attempts: list[GradedAttempt]) -> float:
    if not attempts:
        return 0.0
    denominator = sum(DIFFICULTY_WEIGHTS[a.difficulty] for a in attempts)
    if denominator == 0:
        return 0.0
    numerator = sum(DIFFICULTY_WEIGHTS[a.difficulty] for a in attempts if a.is_correct)
    return numerator / denominator


def accuracy_by_difficulty(attempts: list[GradedAttempt]) -> dict[str, float]:
    by_difficulty: dict[int, list[GradedAttempt]] = {}
    for attempt in attempts:
        by_difficulty.setdefault(attempt.difficulty, []).append(attempt)
    return {str(difficulty): raw_accuracy(group) for difficulty, group in by_difficulty.items()}


def highest_consistent_difficulty(attempts: list[GradedAttempt]) -> int | None:
    """Highest difficulty level for which every attempt at that level (and every level
    below it) was correct - an ascending scan that stops at the first miss.
    """
    by_difficulty: dict[int, list[GradedAttempt]] = {}
    for attempt in attempts:
        by_difficulty.setdefault(attempt.difficulty, []).append(attempt)

    highest: int | None = None
    for difficulty in sorted(by_difficulty):
        group = by_difficulty[difficulty]
        if group and all(a.is_correct for a in group):
            highest = difficulty
        else:
            break
    return highest


def recommended_difficulty(attempts: list[GradedAttempt]) -> int | None:
    """The difficulty to route this skill's next questions to (SPEC §5.10.2's
    `recommended_difficulty`, §5.11.2 rules 2-3). Anchored on the difficulty the student
    was actually assessed at for the skill (its modal tier), nudged +/-1 by accuracy:
    step up when they're clearly on top of it, hold when passing, step down otherwise.
    Clamped to the 1-5 range. Returns None when there's nothing to base it on.
    """
    if not attempts:
        return None
    base = Counter(a.difficulty for a in attempts).most_common(1)[0][0]
    accuracy = raw_accuracy(attempts)
    if accuracy >= STEP_UP_ACCURACY:
        target = base + 1
    elif accuracy >= HOLD_ACCURACY:
        target = base
    else:
        target = base - 1
    return max(MIN_DIFFICULTY, min(MAX_DIFFICULTY, target))
