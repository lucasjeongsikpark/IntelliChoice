"""SPEC §5.19.1 access scope -> §5.21.3 pre-filter construction. Pure/no-DB - uses a
fake `ProfileAdapter` double, mirroring `learning_api`'s existing test doubles for the
same Protocol.
"""

import asyncio
from datetime import datetime

from chat_api.services.role_access import (
    build_access_hint,
    resolve_role_context,
    role_access_filter,
)
from intellichoice_shared.access_probe_policy import AudienceMatch
from intellichoice_shared.auth import Role, TokenClaims
from intellichoice_shared.profiles import (
    AttendanceStatus,
    BranchInfo,
    ParentProfile,
    StudentProfile,
)


class _FakeProfileAdapter:
    def __init__(self, students: dict[str, StudentProfile] | None = None) -> None:
        self._students = students or {}

    async def get_student_profile(self, student_external_id: str) -> StudentProfile | None:
        return self._students.get(student_external_id)

    async def get_parent_profile(self, parent_external_id: str) -> ParentProfile | None:
        raise NotImplementedError

    async def get_parent_children(self, parent_external_id: str) -> list[str]:
        raise NotImplementedError

    async def get_current_week_attendance(self, student_external_id: str) -> AttendanceStatus:
        raise NotImplementedError

    async def get_branch(self, branch_external_id: str) -> BranchInfo | None:
        raise NotImplementedError

    async def get_branch_manager_email(self, branch_external_id: str) -> str | None:
        raise NotImplementedError

    async def list_branches(self) -> list[BranchInfo]:
        raise NotImplementedError


def _claims(role: Role, sub: str = "user-1") -> TokenClaims:
    from intellichoice_shared.auth import Audience

    return TokenClaims(
        sub=sub,
        role=role,
        account_status="active",
        consent_status="granted",
        parental_consent_verified=True,
        consent_version="v1",
        issued_at=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
        expires_at=datetime.fromisoformat("2027-01-01T00:00:00+00:00"),
        audience=Audience.CHAT,
    )


def test_anonymous_caller_resolves_to_public_role_and_no_branch() -> None:
    async def run() -> None:
        user_role, branch_external_id = await resolve_role_context(None, _FakeProfileAdapter())
        assert user_role == "public"
        assert branch_external_id is None

    asyncio.run(run())


def test_student_role_resolves_branch_from_profile() -> None:
    async def run() -> None:
        adapter = _FakeProfileAdapter(
            {
                "student-ext-1": StudentProfile(
                    student_external_id="student-ext-1",
                    display_name="Test Student",
                    grade="7",
                    branch_external_id="branch-ext-1",
                )
            }
        )
        user_role, branch_external_id = await resolve_role_context(
            _claims(Role.STUDENT, "student-ext-1"), adapter
        )
        assert user_role == "student"
        assert branch_external_id == "branch-ext-1"

    asyncio.run(run())


def test_parent_role_resolves_to_no_branch() -> None:
    """Parents may have children at different branches - SPEC's data model gives no
    single unambiguous "current branch" for a parent this session (no child-selection
    concept exists in chat), so branch stays unresolved (`None`), which
    `role_access_filter` still handles safely (org-wide chunks only).
    """

    async def run() -> None:
        user_role, branch_external_id = await resolve_role_context(
            _claims(Role.PARENT, "parent-ext-1"), _FakeProfileAdapter()
        )
        assert user_role == "parent"
        assert branch_external_id is None

    asyncio.run(run())


def test_role_access_filter_always_includes_public_and_restricts_to_branch() -> None:
    filters = role_access_filter("student", "branch-ext-1")
    assert filters.audiences == ["public", "student"]
    assert filters.branch_external_id == "branch-ext-1"
    assert filters.restrict_to_branch is True
    assert filters.as_of is not None


def _unscored(count: int = 1) -> AudienceMatch:
    """A lexical-arm match: real, but with no relevance scale (see `AudienceMatch`)."""
    return AudienceMatch(count=count)


def test_build_access_hint_none_when_nothing_matched() -> None:
    assert build_access_hint("public", {}) is None
    assert build_access_hint("student", {"student": _unscored(0), "public": _unscored(0)}) is None


def test_build_access_hint_returns_role_guidance_for_a_higher_tier_match() -> None:
    hint = build_access_hint("public", {"tutor": _unscored(2)})
    assert hint is not None
    assert hint.required_role == "tutor"
    assert "tutor" in hint.message.lower()


def test_build_access_hint_ignores_a_match_under_the_callers_own_accessible_audience() -> None:
    # A match under the caller's own accessible audiences alone (no other-tier match) is
    # deliberately not turned into a hint - see `build_access_hint`'s own docstring for
    # why (the probe's looseness makes that signal unreliable, confirmed via live
    # verification during this session).
    assert build_access_hint("student", {"student": _unscored(3), "public": _unscored(1)}) is None


def test_build_access_hint_falls_back_to_priority_when_no_audience_is_scored() -> None:
    """The pre-AUD-C-22 rule, kept as the tie-break. This is the path every mock-backed test
    takes (hash-seeded vectors carry no relevance) and the path a semantic-arm failure
    degrades to, so it has to keep working exactly as it did.
    """
    hint = build_access_hint(
        "public", {"tutor": _unscored(), "branch_manager": _unscored(), "parent": _unscored()}
    )
    assert hint is not None
    assert hint.required_role == "branch_manager"


def test_build_access_hint_picks_the_most_relevant_tier_over_the_highest_ranked_one() -> None:
    """AUD-C-22, as it was observed live: a parent asking about their own child's attendance
    was told to log in as a *branch manager*, because branch_manager outranks parent and
    nothing compared the two. The scores here are the measured ones - the parent chunk that
    answers that question sat at cosine distance 0.499, the branch_manager material further
    out - and priority must now lose to them.
    """
    hint = build_access_hint(
        "public",
        {
            "branch_manager": AudienceMatch(count=3, score=1.0 - 0.52),
            "parent": AudienceMatch(count=1, score=1.0 - 0.499),
        },
    )
    assert hint is not None
    assert hint.required_role == "parent"


def test_build_access_hint_prefers_a_scored_audience_over_an_unscored_one() -> None:
    # A relevance number is strictly more information than "some lexeme matched somewhere",
    # so the lexical-only arm must not win on tier rank against a semantic match.
    hint = build_access_hint(
        "public",
        {"branch_manager": _unscored(9), "student": AudienceMatch(count=1, score=0.4)},
    )
    assert hint is not None
    assert hint.required_role == "student"


def test_build_access_hint_breaks_an_exact_score_tie_by_priority() -> None:
    # Two equal scores must not resolve by dict/row order - that would make the hint depend
    # on which row Postgres returned first.
    hint = build_access_hint(
        "public",
        {"parent": AudienceMatch(count=1, score=0.6), "tutor": AudienceMatch(count=1, score=0.6)},
    )
    assert hint is not None
    assert hint.required_role == "tutor"


def test_build_access_hint_ignores_an_audience_it_has_no_message_for() -> None:
    """The message set is the closed §5.19.1 tier list. A new `audience` value in the corpus
    must not reach a user through this path, and must not raise either - before AUD-C-22 the
    loop simply never looked at unknown audiences, and that property is worth keeping
    explicit now that selection iterates what the probe returned instead.
    """
    assert build_access_hint("public", {"regional_coordinator": AudienceMatch(1, 0.9)}) is None
