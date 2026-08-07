"""Problem-report + quarantine service (SPEC §5.8.7).

Students report a problematic question variant; the report is recorded against the
variant's *template* (uniqueness is per template+student, so repeat reports from the same
student against different variants of the same template count once - see the
`ProblemReport` model). After five distinct valid users have reported one template, it is
quarantined: `active_status="quarantined"` stops it being delivered by
`get_active_questions`/`get_active_questions_for_skill` (both filter `active_status ==
"active"`) *without deleting any history* - the template row, its variants, and every
report stay intact (SPEC §5.8.7 "quarantine stops delivery without deleting history").

Deterministic and code-owned: no LLM decides whether to quarantine (CLAUDE.md
non-negotiable #2). Grading/authorization/quarantine are all threshold logic here.
"""

from dataclasses import dataclass

from intellichoice_db.models.assessment import AssessmentItem, AssessmentSession
from intellichoice_db.models.mastery import StudyItem, StudySession
from intellichoice_db.models.questions import QuestionTemplate
from intellichoice_db.models.reports import ProblemReport
from intellichoice_db.repositories.questions import QuestionRepository
from intellichoice_db.repositories.reports import ReportRepository
from intellichoice_observability.metrics import PROBLEM_REPORTS, QUARANTINE_COUNT
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

# SPEC §5.8.7 report reasons.
REPORT_TYPES = frozenset(
    {
        "no_correct_answer",
        "more_than_one_correct_answer",
        "unclear_wording",
        "incorrect_difficulty",
        "display_issue",
        "other",
    }
)

QUARANTINE_THRESHOLD = 5


class UnknownQuestionError(Exception):
    """The reported question_variant_id doesn't exist."""


class QuestionNotServedError(Exception):
    """D-216: the variant exists but was never served to this student. Reporting is
    scoped to questions the reporter has actually seen - without this, any five student
    accounts could quarantine any template for everyone by guessing/scripting variant
    ids, and every other student-scoped route in this app checks ownership.
    """


class InvalidReportTypeError(Exception):
    """The report_type isn't one of the SPEC §5.8.7 reasons."""


@dataclass(frozen=True)
class ReportOutcome:
    already_reported: bool
    distinct_reporters: int
    quarantined: bool


async def submit_report(
    session: AsyncSession,
    *,
    question_variant_id: str,
    student_external_id: str,
    report_type: str,
) -> ReportOutcome:
    if report_type not in REPORT_TYPES:
        raise InvalidReportTypeError(report_type)

    question_repo = QuestionRepository(session)
    variant = await question_repo.get_variant(question_variant_id)
    if variant is None:
        raise UnknownQuestionError(question_variant_id)
    if not await _was_served_to(session, question_variant_id, student_external_id):
        raise QuestionNotServedError(question_variant_id)
    template_id = variant.question_template_id

    report_repo = ReportRepository(session)
    existing = await report_repo.get_report(template_id, student_external_id)
    if existing is None:
        await report_repo.create_report(
            ProblemReport(
                question_template_id=template_id,
                question_variant_id=question_variant_id,
                student_external_id=student_external_id,
                report_type=report_type,
            )
        )
        PROBLEM_REPORTS.inc()

    distinct_reporters = await report_repo.count_distinct_reporters(template_id)
    quarantined = await _maybe_quarantine(question_repo, template_id, distinct_reporters)
    return ReportOutcome(
        already_reported=existing is not None,
        distinct_reporters=distinct_reporters,
        quarantined=quarantined,
    )


async def _was_served_to(
    session: AsyncSession, question_variant_id: str, student_external_id: str
) -> bool:
    """True when this variant appears as an item of one of the student's own exam or
    study sessions - i.e. it was actually put in front of them. One indexed EXISTS query;
    answered or not doesn't matter (a student may reasonably report a question they
    refused to answer *because* it is broken).
    """
    served_in_exam = exists(
        select(AssessmentItem.assessment_item_id)
        .join(
            AssessmentSession,
            AssessmentSession.assessment_session_id == AssessmentItem.assessment_session_id,
        )
        .where(
            AssessmentItem.question_variant_id == question_variant_id,
            AssessmentSession.student_external_id == student_external_id,
        )
    )
    served_in_study = exists(
        select(StudyItem.study_item_id)
        .join(StudySession, StudySession.study_session_id == StudyItem.study_session_id)
        .where(
            StudyItem.question_variant_id == question_variant_id,
            StudySession.student_external_id == student_external_id,
        )
    )
    result = await session.execute(select(or_(served_in_exam, served_in_study)))
    return bool(result.scalar())


async def _maybe_quarantine(
    question_repo: QuestionRepository, template_id: str, distinct_reporters: int
) -> bool:
    if distinct_reporters < QUARANTINE_THRESHOLD:
        return False
    template: QuestionTemplate | None = await question_repo.get_template(template_id)
    if template is None or template.active_status == "quarantined":
        # Already quarantined (e.g. the 6th reporter) - idempotent, still "quarantined".
        return template is not None and template.active_status == "quarantined"
    await question_repo.set_active_status(template_id, "quarantined")
    QUARANTINE_COUNT.inc()
    return True
