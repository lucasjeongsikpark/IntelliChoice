"""SPEC §5.14.2-§5.14.4, ROADMAP S28 (plan §12, §18-L9): pure-Postgres dashboard
aggregates. No LLM anywhere on this path (CLAUDE.md non-negotiable #2) - it must be
cheap and always available, unlike `services/report.py`'s one Bedrock call. Date-range
filtering happens in `DashboardRepository` (SQL WHERE clauses); this module only shapes
already-filtered rows into chart-ready DTOs and resolves skill ids to display names
(`skill_id` never crosses into a response DTO - `history.py`'s existing discipline).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from intellichoice_db.models.mastery import Mastery
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.dashboard import DashboardRepository
from intellichoice_db.repositories.mastery import MasteryRepository

# Placeholder target: mastery bars render against this band until a real per-skill
# target (curriculum-authored, not yet built) exists.
_MASTERY_TARGET_BAND = 0.8

# AUD-L-15 (D-156). Not every field on `DashboardData` covers the same window, and two of
# them cover neither the caller's date range nor each other's phases. They live here, next
# to the data they describe, because both consumers need the same words: the report payload
# (`services/report.py`, where a mismatched label put mastery 1.000 beside "needs work"
# under one "all time" heading) and `GET /dashboard` (where the mastery chart sits under a
# date-range picker it silently ignores, beside four charts that honour it).
#
# `mastery_by_skill` covers every graded attempt to date - D-156 folded the post-exam in,
# so the phase gap AUD-L-15 opened with is gone. What remains true, and is the easy half to
# miss, is that it is not date-filtered at all: `build_dashboard` reads
# `mastery_repo.list_for_student`, which takes no range. Under a report headed
# "2026-07-01 to 2026-07-31" these are still all-time numbers.
MASTERY_WINDOW_LABEL = (
    "Current standing per skill, from every graded attempt to date - pre-exam, study "
    "practice and post-exam - not just the selected date range."
)
# `pre_post_by_skill` is the other half of the pair, and it *does* honour the date range:
# it averages the `skill_level_gain` of every `LearningGain` row in range. It is post-exam
# accuracy, not a mastery score, which is why it can disagree with the line above without
# either being wrong.
PRE_POST_WINDOW_LABEL = (
    "Post-exam accuracy, averaged across the cycles completed in the selected date range."
)


@dataclass(frozen=True)
class MasterySkillPoint:
    skill_name: str
    weighted_score: float
    target_band: float = _MASTERY_TARGET_BAND


@dataclass(frozen=True)
class PrePostSkillPoint:
    skill_name: str
    pre_accuracy: float
    post_accuracy: float


@dataclass(frozen=True)
class GainPoint:
    date: datetime
    raw_gain: float
    weighted_gain: float


@dataclass(frozen=True)
class AccuracyPoint:
    date: datetime
    accuracy: float
    attempts: int


@dataclass(frozen=True)
class DifficultyPoint:
    date: datetime
    skill_name: str
    difficulty: int


@dataclass(frozen=True)
class UsageBreakdown:
    hint_count: int
    solution_count: int
    video_count: int
    independent_count: int
    total_attempts: int


@dataclass(frozen=True)
class DashboardData:
    mastery_by_skill: list[MasterySkillPoint]
    pre_post_by_skill: list[PrePostSkillPoint]
    gains_over_time: list[GainPoint]
    accuracy_trend: list[AccuracyPoint]
    difficulty_progression: list[DifficultyPoint]
    usage: UsageBreakdown
    attempts_count: int
    time_spent_minutes: float
    # SPEC §5.14.2 "pre/post change" - the most recent `LearningGain` row in range, for
    # `services/report.py`'s verified facts. `None` when no cycle completed in range.
    latest_pre_raw_score: float | None
    latest_post_raw_score: float | None
    latest_raw_gain: float | None
    tutor_review_flagged: bool


async def _skill_name(curriculum_repo: CurriculumRepository, skill_id: str) -> str:
    skill = await curriculum_repo.get_skill(skill_id)
    return skill.name if skill is not None else skill_id


async def _mastery_by_skill(
    mastery_rows: list[Mastery], curriculum_repo: CurriculumRepository
) -> list[MasterySkillPoint]:
    return [
        MasterySkillPoint(
            skill_name=await _skill_name(curriculum_repo, row.skill_id),
            weighted_score=row.weighted_score,
        )
        for row in mastery_rows
    ]


async def _pre_post_by_skill(
    gains: list, curriculum_repo: CurriculumRepository
) -> list[PrePostSkillPoint]:
    """Averages `skill_level_gain` across every `LearningGain` row in range, per skill -
    a skill studied across multiple pre->post cycles in the window gets one averaged bar,
    not one per cycle.
    """
    pre_totals: dict[str, list[float]] = defaultdict(list)
    post_totals: dict[str, list[float]] = defaultdict(list)
    for gain in gains:
        for skill_id, values in gain.skill_level_gain.items():
            pre_totals[skill_id].append(values["pre_accuracy"])
            post_totals[skill_id].append(values["post_accuracy"])

    points = []
    for skill_id in sorted(pre_totals):
        pre_values = pre_totals[skill_id]
        post_values = post_totals[skill_id]
        points.append(
            PrePostSkillPoint(
                skill_name=await _skill_name(curriculum_repo, skill_id),
                pre_accuracy=sum(pre_values) / len(pre_values),
                post_accuracy=sum(post_values) / len(post_values),
            )
        )
    return points


def _gains_over_time(gains: list) -> list[GainPoint]:
    return [
        GainPoint(date=gain.computed_at, raw_gain=gain.raw_gain, weighted_gain=gain.weighted_gain)
        for gain in gains
    ]


def _accuracy_trend(
    study_rows: list[tuple], assessment_rows: list[tuple]
) -> list[AccuracyPoint]:
    buckets: dict[str, list[bool]] = defaultdict(list)
    for attempt, _item in study_rows:
        buckets[attempt.responded_at.date().isoformat()].append(attempt.is_correct)
    for attempt, _session in assessment_rows:
        buckets[attempt.submitted_at.date().isoformat()].append(attempt.is_correct)

    points = []
    for date_key in sorted(buckets):
        outcomes = buckets[date_key]
        points.append(
            AccuracyPoint(
                date=datetime.fromisoformat(date_key),
                accuracy=sum(outcomes) / len(outcomes),
                attempts=len(outcomes),
            )
        )
    return points


async def _difficulty_progression(
    study_rows: list[tuple], curriculum_repo: CurriculumRepository
) -> list[DifficultyPoint]:
    points = []
    for attempt, item in study_rows:
        points.append(
            DifficultyPoint(
                date=attempt.responded_at,
                skill_name=await _skill_name(curriculum_repo, item.skill_id),
                difficulty=item.difficulty,
            )
        )
    return points


def _usage_breakdown(study_rows: list[tuple]) -> UsageBreakdown:
    hint_count = sum(1 for a, _ in study_rows if a.hint_used)
    solution_count = sum(1 for a, _ in study_rows if a.solution_used)
    video_count = sum(1 for a, _ in study_rows if a.video_used)
    independent_count = sum(
        1 for a, _ in study_rows if not (a.hint_used or a.solution_used or a.video_used)
    )
    return UsageBreakdown(
        hint_count=hint_count,
        solution_count=solution_count,
        video_count=video_count,
        independent_count=independent_count,
        total_attempts=len(study_rows),
    )


async def build_dashboard(
    *,
    student_id: str,
    start: datetime | None,
    end: datetime | None,
    dashboard_repo: DashboardRepository,
    mastery_repo: MasteryRepository,
    curriculum_repo: CurriculumRepository,
) -> DashboardData:
    mastery_rows = await mastery_repo.list_for_student(student_id)
    gains = await dashboard_repo.list_learning_gains_in_range(student_id, start=start, end=end)
    study_rows = await dashboard_repo.list_study_attempts_with_items_in_range(
        student_id, start=start, end=end
    )
    assessment_rows = await dashboard_repo.list_assessment_attempts_in_range(
        student_id, start=start, end=end
    )
    total_time_ms = await dashboard_repo.total_assessment_time_ms_in_range(
        student_id, start=start, end=end
    )
    latest_gain = gains[-1] if gains else None

    return DashboardData(
        mastery_by_skill=await _mastery_by_skill(mastery_rows, curriculum_repo),
        pre_post_by_skill=await _pre_post_by_skill(gains, curriculum_repo),
        gains_over_time=_gains_over_time(gains),
        accuracy_trend=_accuracy_trend(study_rows, assessment_rows),
        difficulty_progression=await _difficulty_progression(study_rows, curriculum_repo),
        usage=_usage_breakdown(study_rows),
        attempts_count=len(study_rows) + len(assessment_rows),
        time_spent_minutes=total_time_ms / 60000,
        latest_pre_raw_score=latest_gain.pre_raw_score if latest_gain else None,
        latest_post_raw_score=latest_gain.post_raw_score if latest_gain else None,
        latest_raw_gain=latest_gain.raw_gain if latest_gain else None,
        tutor_review_flagged=any(a.tutor_review_flagged for a, _ in study_rows),
    )
