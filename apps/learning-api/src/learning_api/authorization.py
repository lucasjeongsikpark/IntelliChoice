from typing import Literal

from fastapi import HTTPException, status
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.profiles import ProfileAdapter

Access = Literal["read", "write"]
"""Whether the caller is about to *read* a student's data or *change* it.

Required at every call site rather than defaulted, because the recurring defect in this
codebase is a route that quietly gets the permissive branch: AUD-C-01, AUD-X-01 and
AUD-X-05 are all "the one route nobody classified". A new route cannot compile without
answering the question.
"""


async def resolve_target_student(
    claims: TokenClaims,
    requested_student_id: str,
    profile_adapter: ProfileAdapter,
    *,
    access: Access,
) -> str:
    """Verify (server-side) that `claims` grants `access` to `requested_student_id`.

    Never trusts the client-supplied id on its own (SPEC §5.6.1) — students are
    checked against their own `sub`, parents against a live MySQL lookup of
    their linked children.
    """
    if claims.role == Role.STUDENT:
        if claims.sub != requested_student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students may only access their own records",
            )
        return claims.sub

    if claims.role == Role.PARENT:
        linked_children = await profile_adapter.get_parent_children(claims.sub)
        if requested_student_id not in linked_children:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Parent is not linked to this student",
            )
        return requested_student_id

    # Tutor / branch manager.
    #
    # These two roles have no per-student scope check, because the data model that would
    # support one — which students a tutor is assigned, which students a branch manager's
    # branch contains — does not exist in `ProfileAdapter` yet. That is D-086's recorded,
    # accepted risk since S33, and S43's `IcProfileAdapter` is what unblocks it; the
    # formal disposition is scheduled for S46. AUD-L-07 widened its *reach* (S28's
    # dashboard and report surface joined it) without changing that reasoning.
    #
    # AUD-X-05 (S40, D-107) is the part that could not wait for S43, because it is a
    # different kind of failure. A read-scope gap discloses data that already exists; the
    # same fall-through on a *write* fabricates data that does not. Measured: a tutor
    # token answered and finalized another student's exam, and those `assessment_attempts`
    # rows are indistinguishable from the student's own — they feed scoring, mastery and
    # learning-gain, and the report a parent eventually reads. Nothing downstream can tell
    # a fabricated attempt from a real one, so nothing downstream can undo it.
    #
    # So writes fail closed now and reads keep the documented gap. Deleting this branch
    # entirely is the S43/S46 job, and it should delete the read half too.
    if access == "write":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role may not modify a student's records",
        )
    return requested_student_id
