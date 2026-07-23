"""Problem-report endpoint (SPEC §5.8.7). Separate from the session-flow router since a
report is about a question, not a learning-session turn.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from intellichoice_shared.auth import Role, TokenClaims
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from learning_api.dependencies import get_current_claims, get_db_session
from learning_api.services import question_reports
from learning_api.services.question_reports import (
    InvalidReportTypeError,
    UnknownQuestionError,
)

router = APIRouter(prefix="/learning/questions", tags=["learning-questions"])


class ProblemReportRequest(BaseModel):
    report_type: str


class ProblemReportResponse(BaseModel):
    question_variant_id: str
    already_reported: bool
    distinct_reporters: int
    quarantined: bool


@router.post(
    "/{question_variant_id}/reports",
    response_model=ProblemReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def report_problem(
    question_variant_id: str,
    body: ProblemReportRequest,
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProblemReportResponse:
    # The reporter is always the authenticated student (`claims.sub`) - never taken from
    # the request body (SPEC §5.30.2 authorization principle). Only students report.
    if claims.role != Role.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="only students can report a problematic question",
        )
    try:
        outcome = await question_reports.submit_report(
            db,
            question_variant_id=question_variant_id,
            student_external_id=claims.sub,
            report_type=body.report_type,
        )
    except UnknownQuestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"unknown question_variant_id {question_variant_id!r}",
        ) from exc
    except InvalidReportTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown report_type {body.report_type!r}",
        ) from exc

    return ProblemReportResponse(
        question_variant_id=question_variant_id,
        already_reported=outcome.already_reported,
        distinct_reporters=outcome.distinct_reporters,
        quarantined=outcome.quarantined,
    )
