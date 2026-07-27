"""SPEC §5.14.2-§5.14.4 parent-dashboard session-history, progress-dashboard, and
student-report endpoints. Separate from `routers/sessions.py` since these read
accumulated history/aggregates across sessions, not one session's turn-by-turn flow.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from intellichoice_db.repositories.assessment import AssessmentRepository
from intellichoice_db.repositories.curriculum import CurriculumRepository
from intellichoice_db.repositories.dashboard import DashboardRepository
from intellichoice_db.repositories.mastery import MasteryRepository
from intellichoice_db.repositories.memory import MemoryRepository
from intellichoice_db.repositories.reports import ReportRepository
from intellichoice_db.repositories.student_report import StudentReportRepository
from intellichoice_db.repositories.study import StudyRepository
from intellichoice_shared.auth import TokenClaims
from intellichoice_shared.bedrock import BedrockGateway
from intellichoice_shared.profiles import ProfileAdapter
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.authorization import resolve_target_student
from learning_api.dependencies import (
    get_bedrock_gateway,
    get_current_claims,
    get_db_session,
    get_profile_adapter,
)
from learning_api.services.dashboard import DashboardData, build_dashboard
from learning_api.services.history import StudentHistory, build_student_history
from learning_api.services.report import build_report_facts, generate_student_report

router = APIRouter(prefix="/learning/students", tags=["learning-students"])

# Cap on how many semantic-memory facts feed a single report call - same "small,
# bounded evidence list" posture `StageNarrativePayload.relevant_learning_facts`
# already established (S26).
_MAX_REPORT_FACTS = 5


class CompletedSessionResponse(BaseModel):
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
    completed_at: str


class BlockedSessionResponse(BaseModel):
    week_id: str
    blocked_reason: str
    blocked_at: str


class ProblemReportResponse(BaseModel):
    question_template_id: str
    report_type: str
    status: str
    created_at: str


class MasteryResponse(BaseModel):
    skill_name: str
    weighted_score: float
    recommended_difficulty: int | None


class StudentHistoryResponse(BaseModel):
    student_external_id: str
    completed_sessions: list[CompletedSessionResponse]
    blocked_sessions: list[BlockedSessionResponse]
    problem_reports: list[ProblemReportResponse]
    mastery: list[MasteryResponse]

    @classmethod
    def from_history(cls, student_id: str, history: StudentHistory) -> "StudentHistoryResponse":
        return cls(
            student_external_id=student_id,
            completed_sessions=[
                CompletedSessionResponse(
                    learning_gain_id=s.learning_gain_id,
                    topic_id=s.topic_id,
                    pre_raw_score=s.pre_raw_score,
                    post_raw_score=s.post_raw_score,
                    raw_gain=s.raw_gain,
                    weighted_gain=s.weighted_gain,
                    normalized_gain=s.normalized_gain,
                    normalized_gain_status=s.normalized_gain_status,
                    unresolved_skill_names=s.unresolved_skill_names,
                    hint_count=s.hint_count,
                    solution_count=s.solution_count,
                    video_count=s.video_count,
                    tutor_review_flagged=s.tutor_review_flagged,
                    completed_at=s.completed_at.isoformat(),
                )
                for s in history.completed_sessions
            ],
            blocked_sessions=[
                BlockedSessionResponse(
                    week_id=b.week_id,
                    blocked_reason=b.blocked_reason,
                    blocked_at=b.blocked_at.isoformat(),
                )
                for b in history.blocked_sessions
            ],
            problem_reports=[
                ProblemReportResponse(
                    question_template_id=r.question_template_id,
                    report_type=r.report_type,
                    status=r.status,
                    created_at=r.created_at.isoformat(),
                )
                for r in history.problem_reports
            ],
            mastery=[
                MasteryResponse(
                    skill_name=m.skill_name,
                    weighted_score=m.weighted_score,
                    recommended_difficulty=m.recommended_difficulty,
                )
                for m in history.mastery
            ],
        )


@router.get("/{student_id}/sessions", response_model=StudentHistoryResponse)
async def get_student_sessions(
    student_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StudentHistoryResponse:
    target_student_id = await resolve_target_student(
        claims, student_id, profile_adapter, access="read"
    )
    history = await build_student_history(
        student_id=target_student_id,
        mastery_repo=MasteryRepository(db),
        assessment_repo=AssessmentRepository(db),
        study_repo=StudyRepository(db),
        report_repo=ReportRepository(db),
        curriculum_repo=CurriculumRepository(db),
    )
    return StudentHistoryResponse.from_history(target_student_id, history)


class MasterySkillResponse(BaseModel):
    skill_name: str
    weighted_score: float
    target_band: float


class PrePostSkillResponse(BaseModel):
    skill_name: str
    pre_accuracy: float
    post_accuracy: float


class GainPointResponse(BaseModel):
    date: str
    raw_gain: float
    weighted_gain: float


class AccuracyPointResponse(BaseModel):
    date: str
    accuracy: float
    attempts: int


class DifficultyPointResponse(BaseModel):
    date: str
    skill_name: str
    difficulty: int


class UsageBreakdownResponse(BaseModel):
    hint_count: int
    solution_count: int
    video_count: int
    independent_count: int
    total_attempts: int


class DashboardResponse(BaseModel):
    student_external_id: str
    mastery_by_skill: list[MasterySkillResponse]
    pre_post_by_skill: list[PrePostSkillResponse]
    gains_over_time: list[GainPointResponse]
    accuracy_trend: list[AccuracyPointResponse]
    difficulty_progression: list[DifficultyPointResponse]
    usage: UsageBreakdownResponse
    attempts_count: int
    time_spent_minutes: float

    @classmethod
    def from_data(cls, student_id: str, data: DashboardData) -> "DashboardResponse":
        return cls(
            student_external_id=student_id,
            mastery_by_skill=[
                MasterySkillResponse(
                    skill_name=p.skill_name,
                    weighted_score=p.weighted_score,
                    target_band=p.target_band,
                )
                for p in data.mastery_by_skill
            ],
            pre_post_by_skill=[
                PrePostSkillResponse(
                    skill_name=p.skill_name,
                    pre_accuracy=p.pre_accuracy,
                    post_accuracy=p.post_accuracy,
                )
                for p in data.pre_post_by_skill
            ],
            gains_over_time=[
                GainPointResponse(
                    date=p.date.isoformat(), raw_gain=p.raw_gain, weighted_gain=p.weighted_gain
                )
                for p in data.gains_over_time
            ],
            accuracy_trend=[
                AccuracyPointResponse(
                    date=p.date.isoformat(), accuracy=p.accuracy, attempts=p.attempts
                )
                for p in data.accuracy_trend
            ],
            difficulty_progression=[
                DifficultyPointResponse(
                    date=p.date.isoformat(), skill_name=p.skill_name, difficulty=p.difficulty
                )
                for p in data.difficulty_progression
            ],
            usage=UsageBreakdownResponse(
                hint_count=data.usage.hint_count,
                solution_count=data.usage.solution_count,
                video_count=data.usage.video_count,
                independent_count=data.usage.independent_count,
                total_attempts=data.usage.total_attempts,
            ),
            attempts_count=data.attempts_count,
            time_spent_minutes=data.time_spent_minutes,
        )


async def _build_dashboard_data(
    target_student_id: str, start: datetime | None, end: datetime | None, db: AsyncSession
) -> DashboardData:
    return await build_dashboard(
        student_id=target_student_id,
        start=start,
        end=end,
        dashboard_repo=DashboardRepository(db),
        mastery_repo=MasteryRepository(db),
        curriculum_repo=CurriculumRepository(db),
    )


@router.get("/{student_id}/dashboard", response_model=DashboardResponse)
async def get_student_dashboard(
    student_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> DashboardResponse:
    target_student_id = await resolve_target_student(
        claims, student_id, profile_adapter, access="read"
    )
    data = await _build_dashboard_data(target_student_id, start, end, db)
    return DashboardResponse.from_data(target_student_id, data)


class StudentReportResponse(BaseModel):
    audience: str
    interpretation_text: str
    recommendations_text: str
    generated: bool
    verified_facts: dict
    created_at: str


def _date_range_label(start: datetime | None, end: datetime | None) -> str:
    if start is None and end is None:
        return "all time"
    if start is not None and end is not None:
        return f"{start.date().isoformat()} to {end.date().isoformat()}"
    if start is not None:
        return f"since {start.date().isoformat()}"
    assert end is not None
    return f"through {end.date().isoformat()}"


@router.post("/{student_id}/report", response_model=StudentReportResponse)
async def create_student_report(
    student_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    gateway: Annotated[BedrockGateway, Depends(get_bedrock_gateway)],
    start: Annotated[datetime | None, Query()] = None,
    end: Annotated[datetime | None, Query()] = None,
) -> StudentReportResponse:
    # "read" despite being a POST, and the distinction is worth stating because it looks
    # wrong at a glance. `access` classifies what the caller learns or changes *about the
    # student*, not whether a row is written. This route derives a document from data the
    # caller can already read through `/dashboard` and `/sessions`; it adds no new fact
    # about the student and cannot corrupt one. AUD-L-07 files it under the tutor
    # read-scope gap that D-086 accepted and S43/S46 close - classifying it "write" would
    # end tutor report generation outright (with no assignment model, every student is
    # "unlinked"), which is a product decision those sessions own, not a side effect of
    # AUD-X-05's fix. Its actual write concerns are idempotency (AUD-X-04) and spend
    # (AUD-L-02's ceiling), both handled on their own terms.
    target_student_id = await resolve_target_student(
        claims, student_id, profile_adapter, access="read"
    )
    # Audience is always the caller's own role - never a client-supplied field (CLAUDE.md
    # non-negotiable #3). Role enum values already match SPEC §5.14.2-§5.14.4's audience
    # names exactly.
    audience = claims.role.value

    data = await _build_dashboard_data(target_student_id, start, end, db)
    profile = await profile_adapter.get_student_profile(target_student_id)
    assert profile is not None
    memory_repo = MemoryRepository(db)
    facts = await memory_repo.list_facts_for_student(target_student_id)
    relevant_learning_facts = [fact.fact_text for fact in facts[:_MAX_REPORT_FACTS]]

    payload = build_report_facts(
        audience=audience,
        grade=profile.grade,
        date_range_label=_date_range_label(start, end),
        dashboard=data,
        relevant_learning_facts=relevant_learning_facts,
    )
    report_repo = StudentReportRepository(db)
    result = await generate_student_report(
        gateway=gateway,
        repo=report_repo,
        student_external_id=target_student_id,
        payload=payload,
        # S36/AUD-L-02: this endpoint has no session, so "spend so far" is this student's
        # report spend over the last 24h - the same window the service's own per-day
        # ceiling uses. Passing a real number is what makes the gateway's budget check
        # meaningful here at all; it previously received the 0.0 default on every call.
        session_spend_cents=await report_repo.get_spend_cents_since(
            target_student_id, datetime.now(UTC) - timedelta(hours=24)
        ),
    )
    return StudentReportResponse(
        audience=audience,
        interpretation_text=result.interpretation_text,
        recommendations_text=result.recommendations_text,
        generated=result.generated,
        verified_facts=result.verified_facts,
        created_at=result.created_at.isoformat(),
    )


@router.get("/{student_id}/reports", response_model=list[StudentReportResponse])
async def list_student_reports(
    student_id: str,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[StudentReportResponse]:
    target_student_id = await resolve_target_student(
        claims, student_id, profile_adapter, access="read"
    )
    audience = claims.role.value
    rows = await StudentReportRepository(db).list_for_student(target_student_id, audience=audience)
    return [
        StudentReportResponse(
            audience=row.audience,
            interpretation_text=row.interpretation_text,
            recommendations_text=row.recommendations_text,
            generated=row.generated,
            verified_facts=row.verified_facts,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
