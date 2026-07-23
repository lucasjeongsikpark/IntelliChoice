from fastapi import HTTPException, status
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.profiles import ProfileAdapter


async def resolve_target_student(
    claims: TokenClaims,
    requested_student_id: str,
    profile_adapter: ProfileAdapter,
) -> str:
    """Verify (server-side) that `claims` grants access to `requested_student_id`.

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

    # Tutor / branch manager: role resolves without a per-student scope check in
    # this session; role-filtered views land with Q&A authorization (Session 13).
    return requested_student_id
