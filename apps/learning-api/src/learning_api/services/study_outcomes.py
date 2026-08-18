"""Retry-ladder outcomes and step logic (SPEC §5.11.5, §5.11.7). Pure and deterministic -
no I/O, no LLM - so the Phase 10 "identical inputs reproduce identical routing/scores"
criterion is unit-testable in isolation.

Two concerns live here:

1. **Outcome labels.** Each study attempt is labeled with one of §5.11.7's six final
   outcomes (plus an interim ``incorrect`` for a wrong answer whose skill line is still
   open). Only ``independent_correct`` counts toward independent mastery - a correct
   answer that leaned on a hint, video, or (§5.11.5) the full solution does not.

2. **The escalation ladder.** After each *incorrect* attempt on a skill line, the ladder
   decides what to serve next: another same-skill retry, an easier *prerequisite* problem,
   or - once the line is exhausted - stop and flag the skill for tutor review.
"""

from dataclasses import dataclass

# Support kinds a student may invoke on an incorrect answer (SPEC §5.11.3-§5.11.6).
HINT = "hint"
VIDEO = "video"
SOLUTION = "solution"

# Outcome labels (SPEC §5.11.7 "Final outcomes", plus the interim `INCORRECT`).
INDEPENDENT_CORRECT = "independent_correct"
CORRECT_AFTER_HINT = "correct_after_hint"
CORRECT_AFTER_VIDEO = "correct_after_video"
CORRECT_AFTER_SOLUTION = "correct_after_solution"
ANSWER_REVEALED = "answer_revealed"
UNRESOLVED = "unresolved"
INCORRECT = "incorrect"  # interim: wrong answer, skill line still open

# The labels that *close* a skill line. Everything else - `INCORRECT`, `ANSWER_REVEALED`,
# and an unlabelled attempt - leaves it open for another rung of the ladder.
#
# Named here rather than at the one call site because "which labels are terminal" is the
# same fact `advance_study` already encodes in its `resolved` flag, and a second copy of it
# in the progress service would be free to drift (D-223). `ANSWER_REVEALED` is the one that
# looks terminal and is not: the solution was shown, the answer was effectively given, and
# the student still gets their retry.
RESOLVING_LABELS = frozenset(
    {
        INDEPENDENT_CORRECT,
        CORRECT_AFTER_HINT,
        CORRECT_AFTER_VIDEO,
        CORRECT_AFTER_SOLUTION,
        UNRESOLVED,
    }
)

# The full retry ladder before a skill line is declared unresolved (SPEC §5.11.7):
# attempt 1 (base) + two same-skill retries + one easier-prerequisite problem = 4.
MAX_ATTEMPTS_PER_SKILL = 4

MORE_EXPLICIT_SUPPORT_MESSAGE = (
    "Let's try a similar one. If you'd like, choose the step-by-step solution this time "
    "for more support."
)
EASIER_PREREQUISITE_MESSAGE = "Let's step back to an easier problem that builds up to this skill."


def correct_label(support_history: frozenset[str]) -> str:
    """Label for a *correct* answer given the support already used on this skill line.

    Precedence is most-revealing-first (solution > video > hint): once the solution has
    been shown, a later correct answer is `correct_after_solution` regardless of any hint
    also used earlier. `support_history` is the set of supports used on *prior* attempts of
    the same skill line (a correct answer never triggers its own intervention).
    """
    if SOLUTION in support_history:
        return CORRECT_AFTER_SOLUTION
    if VIDEO in support_history:
        return CORRECT_AFTER_VIDEO
    if HINT in support_history:
        return CORRECT_AFTER_HINT
    return INDEPENDENT_CORRECT


def incorrect_label(support_history: frozenset[str], *, terminal: bool) -> str:
    """Label for an *incorrect* answer. `terminal` marks the attempt that exhausts the
    ladder (§5.11.7 4th unresolved) - it becomes `unresolved`. Otherwise, if the solution
    was shown the answer was effectively revealed (`answer_revealed`); a plain wrong answer
    on a still-open line is the interim `incorrect`.
    """
    if terminal:
        return UNRESOLVED
    if SOLUTION in support_history:
        return ANSWER_REVEALED
    return INCORRECT


def counts_as_independent(label: str | None) -> bool:
    """Only an unaided correct answer counts toward independent (bootstrap) mastery
    (SPEC §5.10.3, §5.11.5). Assessment attempts (no label) are always independent - they
    have no hint/solution mechanism - so callers pass their own is_correct for those.
    """
    return label == INDEPENDENT_CORRECT


@dataclass(frozen=True)
class LadderStep:
    """What to serve after an incorrect answer. `kind` is one of:
    - ``retry_same``: another variant of the same skill at the same difficulty.
    - ``prerequisite``: an easier problem from the skill's prerequisite (§5.11.7 3rd step).
    - ``exhausted``: stop retrying this skill; mark it unresolved + flag for tutor review.
    """

    kind: str
    support_recommendation: str | None = None


def ladder_step(attempts_on_line: int) -> LadderStep:
    """Given the number of attempts already recorded for a skill line (>=1, since this is
    only consulted after an incorrect answer), decide the next ladder move.

    - 1 attempt so far  -> retry the same skill (hint/solution/video already offered).
    - 2 attempts        -> retry the same skill, recommending more explicit support.
    - 3 attempts        -> drop to an easier prerequisite problem.
    - 4+ attempts        -> exhausted: unresolved + tutor review.
    """
    if attempts_on_line >= MAX_ATTEMPTS_PER_SKILL:
        return LadderStep("exhausted")
    if attempts_on_line == 3:
        return LadderStep("prerequisite", EASIER_PREREQUISITE_MESSAGE)
    if attempts_on_line == 2:
        return LadderStep("retry_same", MORE_EXPLICIT_SUPPORT_MESSAGE)
    return LadderStep("retry_same")
