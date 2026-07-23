"""SPEC §5.14.3 parent-dashboard data: assembles a student's session history from
existing domain tables. No single "learning session" row exists post-S6 (the
`LearningSession` table was retired once LangGraph checkpoints became the resume
mechanism) - a completed cycle is reconstructed from its `LearningGain` row (S11 gave it
`study_session_id`/`topic_id`), and a still-blocked week is its own `BlockedSession` row.

Every skill referenced here is resolved to its display `Skill.name` before leaving this
module - `skill_id` never crosses into a response DTO (CLAUDE.md non-negotiable #10,
"internal skill IDs stay internal").

Out of scope: SPEC §5.14.3's "weekly automated report" (a scheduled digest, needs a
worker) and long-run progress-trend charting - both flagged as carry-over in
docs/PROGRESS.md rather than approximated here.
"""

from dataclasses import dataclass
from datetime import datetime

from intellichoice_db.models.mastery import LearningGain, Mastery
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.reports import ReportRepository
from intellichoice_db.repositories.study import StudyRepository


@dataclass(frozen=True)
class CompletedSessionSummary:
    learning_gain_id: str
    topic_id: str | None
    pre_raw_score: float
    post_raw_score: float
    raw_gain: float
    weighted_gain: float
    normalized_gain: float | None
    normalized_gain_status: str | None
    unresolved_skill_names: list[str]
    hint_count: int
    solution_count: int
    video_count: int
    tutor_review_flagged: bool
    completed_at: datetime


@dataclass(frozen=True)
class BlockedSessionSummary:
    week_id: str
    blocked_reason: str
    blocked_at: datetime


@dataclass(frozen=True)
class ProblemReportSummary:
    question_template_id: str
    report_type: str
    status: str
    created_at: datetime


@dataclass(frozen=True)
class MasterySummary:
    skill_name: str
    weighted_score: float
    recommended_difficulty: int | None


@dataclass(frozen=True)
class StudentHistory:
    completed_sessions: list[CompletedSessionSummary]
    blocked_sessions: list[BlockedSessionSummary]
    problem_reports: list[ProblemReportSummary]
    mastery: list[MasterySummary]


async def _skill_name(curriculum_repo: CurriculumRepository, skill_id: str) -> str:
    skill = await curriculum_repo.get_skill(skill_id)
    return skill.name if skill is not None else skill_id


async def _completed_session_summary(
    gain: LearningGain, study_repo: StudyRepository, curriculum_repo: CurriculumRepository
) -> CompletedSessionSummary:
    attempts = await study_repo.get_attempts(gain.study_session_id) if gain.study_session_id else []
    return CompletedSessionSummary(
        learning_gain_id=gain.learning_gain_id,
        topic_id=gain.topic_id,
        pre_raw_score=gain.pre_raw_score,
        post_raw_score=gain.post_raw_score,
        raw_gain=gain.raw_gain,
        weighted_gain=gain.weighted_gain,
        normalized_gain=gain.normalized_gain,
        normalized_gain_status=gain.normalized_gain_status,
        unresolved_skill_names=[
            await _skill_name(curriculum_repo, skill_id) for skill_id in gain.unresolved_skills
        ],
        hint_count=sum(1 for a in attempts if a.hint_used),
        solution_count=sum(1 for a in attempts if a.solution_used),
        video_count=sum(1 for a in attempts if a.video_used),
        tutor_review_flagged=any(a.tutor_review_flagged for a in attempts),
        completed_at=gain.computed_at,
    )


async def _mastery_summary(
    mastery: Mastery, curriculum_repo: CurriculumRepository
) -> MasterySummary:
    return MasterySummary(
        skill_name=await _skill_name(curriculum_repo, mastery.skill_id),
        weighted_score=mastery.weighted_score,
        recommended_difficulty=mastery.recommended_difficulty,
    )


async def build_student_history(
    *,
    student_id: str,
    mastery_repo: MasteryRepository,
    assessment_repo: AssessmentRepository,
    study_repo: StudyRepository,
    report_repo: ReportRepository,
    curriculum_repo: CurriculumRepository,
) -> StudentHistory:
    gains = await mastery_repo.list_learning_gains_for_student(student_id)
    completed = [
        await _completed_session_summary(gain, study_repo, curriculum_repo) for gain in gains
    ]

    blocked_rows = await assessment_repo.list_blocked_sessions_for_student(student_id)
    blocked = [
        BlockedSessionSummary(
            week_id=row.week_id, blocked_reason=row.blocked_reason, blocked_at=row.blocked_at
        )
        for row in blocked_rows
    ]

    report_rows = await report_repo.list_by_student(student_id)
    reports = [
        ProblemReportSummary(
            question_template_id=row.question_template_id,
            report_type=row.report_type,
            status=row.status,
            created_at=row.created_at,
        )
        for row in report_rows
    ]

    mastery_rows = await mastery_repo.list_for_student(student_id)
    mastery = [await _mastery_summary(row, curriculum_repo) for row in mastery_rows]

    return StudentHistory(
        completed_sessions=completed,
        blocked_sessions=blocked,
        problem_reports=reports,
        mastery=mastery,
    )
