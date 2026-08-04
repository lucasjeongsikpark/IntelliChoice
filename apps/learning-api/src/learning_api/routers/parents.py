"""AUD-F-22: the parent's linked children, resolvable *before* any learning session.

Until this endpoint existed, the only way the frontend learned which child a parent is
linked to was the in-session `child_selection` interrupt - so `StartScreen`'s existing
"View progress dashboard" button (gated on a resolved `studentId`) was unreachable on the
screen a parent actually sees, and the only route to SPEC §5.14's parent dashboard was
sitting through an entire pre → study → post cycle as if they were the student.

Read-only, live from the MySQL adapter (D-020: profile data is served per-response, never
cached in Postgres or graph state), and parent-only: every other role fails closed rather
than falling through to a permissive branch (the AUD-C-01/AUD-X-01/AUD-X-05 lesson -
`authorization.py`'s module docstring names it).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.profiles import ProfileAdapter
from pydantic import BaseModel

from learning_api.dependencies import get_current_claims, get_profile_adapter

router = APIRouter(prefix="/learning/parents", tags=["learning-parents"])


class LinkedChildResponse(BaseModel):
    student_external_id: str
    display_name: str
    grade: str
    branch_name: str


@router.get("/me/children", response_model=list[LinkedChildResponse])
async def list_my_children(
    claims: Annotated[TokenClaims, Depends(get_current_claims)],
    profile_adapter: Annotated[ProfileAdapter, Depends(get_profile_adapter)],
) -> list[LinkedChildResponse]:
    """The caller's own linked children - the id comes from the verified token's `sub`,
    never from the request, so there is nothing client-supplied to authorize (SPEC §5.6.1).
    The link list itself is the MySQL source of truth, same lookup `resolve_student` and
    `resolve_target_student` make.
    """
    if claims.role != Role.PARENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only parents have linked children",
        )

    children = await profile_adapter.get_parent_children(claims.sub)
    responses: list[LinkedChildResponse] = []
    for student_id in children:
        profile = await profile_adapter.get_student_profile(student_id)
        if profile is None:
            # A link row pointing at a missing student profile is an upstream data
            # defect; skipping it fails closed (the child is not offered) rather than
            # 500ing the whole list.
            continue
        branch = await profile_adapter.get_branch(profile.branch_external_id)
        responses.append(
            LinkedChildResponse(
                student_external_id=student_id,
                display_name=profile.display_name,
                grade=profile.grade,
                branch_name=branch.name if branch is not None else profile.branch_external_id,
            )
        )
    return responses
