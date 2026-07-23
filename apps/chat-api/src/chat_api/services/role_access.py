"""SPEC §5.19.1 access scope -> §5.21.3 metadata pre-filter. The only place that
decides which `audience` values and branch a caller may retrieve - authorization lives
in the query layer, never in a prompt (CLAUDE.md non-negotiable #3).
"""

from datetime import UTC, datetime

from intellichoice_db.repositories.rag import ChunkFilters
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.profiles import ProfileAdapter
from pydantic import BaseModel

PUBLIC_AUDIENCE = "public"

# SPEC §18-C3's access-aware refusal: a fixed audience -> "requires X login" message,
# never generated from chunk content or an LLM (CLAUDE.md non-negotiable #3). Ordered by
# priority (most specific/highest tier first) for `build_access_hint` below - when the
# probe finds matches in more than one non-accessible audience, the most specific,
# accurate guidance wins rather than naming every role that happens to match.
ACCESS_HINT_MESSAGES: dict[str, str] = {
    "branch_manager": (
        "That's part of branch management materials - available to branch managers. "
        "Log in with a branch manager account to see it."
    ),
    "tutor": (
        "That's available to tutors - log in with a tutor account to see it."
    ),
    "parent": (
        "That's available to parents - log in with a parent account to see it."
    ),
    "student": (
        "That's available to students - log in with a student account to see it."
    ),
}
_ACCESS_HINT_PRIORITY = ("branch_manager", "tutor", "parent", "student")


class AccessHint(BaseModel):
    """Backend-only, never proposed by an LLM. `required_role` always names a specific
    SPEC §5.19.1 tier - see `build_access_hint`'s docstring for why the generic
    "different branch" case described in plan §18-C3 isn't built this session.
    """

    required_role: str
    message: str


def build_access_hint(user_role: str, audience_counts: dict[str, int]) -> AccessHint | None:
    """Classifies an empty role-filtered retrieval using the metadata-only probe's
    per-audience counts (`RagRepository.count_matching_by_audience`, called with branch
    restriction removed - see `chat_api.graph.nodes.explain_access`). Returns `None` when
    no higher-tier audience matched - a genuine no-answer, nothing to explain access for.

    Deliberately does **not** implement plan §18-C3's other case (a match under the
    caller's *own* audience, just for a different branch -> generic "different branch"
    message): confirmed via live verification that the probe's own looseness makes that
    signal unreliable. The probe has no `candidate_limit` and never reranks, so it's a
    much looser filter than the real retrieval pipeline (`intellichoice_knowledge.
    retrieval.retrieve`) - a query whose real answer simply reranked to score 0 (a
    legitimate no-answer, see D-052) can still match the caller's own audience somewhere
    else in the whole approved corpus via the probe's plain keyword search, which would
    have produced a false, actively misleading "that's for a different branch" message
    instead of the honest no-source message. The role-gated case above doesn't have this
    problem in the same way: even when its match is loose, it's still true that
    role-restricted content mentioning the query's terms exists, which is directionally
    correct guidance rather than an invented reason.
    """
    accessible = {PUBLIC_AUDIENCE, user_role}
    for role in _ACCESS_HINT_PRIORITY:
        if role not in accessible and audience_counts.get(role, 0) > 0:
            return AccessHint(required_role=role, message=ACCESS_HINT_MESSAGES[role])
    return None


async def resolve_role_context(
    claims: TokenClaims | None, profile_adapter: ProfileAdapter
) -> tuple[str, str | None]:
    """Returns `(user_role, branch_external_id)`. `user_role` is `"public"` for an
    anonymous caller, else the claim's `Role.value` (§5.19.1's four authenticated
    tiers). `branch_external_id` is resolved from the caller's own profile only where
    SPEC's data model makes that unambiguous - a student has exactly one branch.
    Parents (who may have children at different branches) and tutor/branch_manager (no
    profile lookup exists yet - S2's `ProfileAdapter` only models students/parents)
    fall back to `None`, which `role_access_filter` below still handles correctly
    (only org-wide, non-branch-restricted chunks match - never another branch's).
    """
    if claims is None:
        return PUBLIC_AUDIENCE, None
    if claims.role == Role.STUDENT:
        profile = await profile_adapter.get_student_profile(claims.sub)
        return claims.role.value, profile.branch_external_id if profile else None
    return claims.role.value, None


def role_access_filter(user_role: str, branch_external_id: str | None) -> ChunkFilters:
    """SPEC §5.21.3's pre-retrieval filter, built from a resolved role/branch - never
    from the raw query text (that would let a prompt-injected document or a crafted
    question smuggle in an access-scope change; see §5.30.4).
    """
    return ChunkFilters(
        audiences=[PUBLIC_AUDIENCE, user_role],
        branch_external_id=branch_external_id,
        restrict_to_branch=True,
        as_of=datetime.now(UTC),
    )
