"""REQ-27-FROZENSET: pins for the fail-closed COPPA consent gate in
`intellichoice_shared.auth` (`AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` and
`account_refusal_reason`).

F-16/E4-16 found the gate correct but *unpinned*: nothing asserted the frozenset was empty and
nothing pinned what a non-empty one would mean, so a future addition to it could open the
parental-consent gate for minors with a green suite. Both halves are pinned below, on top of a
small refusal ladder so the two headline pins can't pass for the wrong reason.

`account_refusal_reason` reads the module-level frozenset at call time, so the module global -
not a re-imported copy - is the injection seam for the non-empty case.
"""

from datetime import UTC, datetime

import pytest
from intellichoice_shared import auth
from intellichoice_shared.auth import (
    ACCOUNT_STATUS_ACTIVE,
    AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT,
    CONSENT_STATUS_GRANTED,
    Audience,
    Role,
    TokenClaims,
)

_ACCOUNT_NOT_ACTIVE = "account is not active"
_CONSENT_NOT_GRANTED = "consent has not been granted"
_NO_PARENTAL_CONSENT = "parental consent has not been verified"


def _claims(
    *,
    role: Role = Role.STUDENT,
    account_status: str = ACCOUNT_STATUS_ACTIVE,
    consent_status: str = CONSENT_STATUS_GRANTED,
    parental_consent_verified: bool = True,
    student_age_band: str | None = None,
) -> TokenClaims:
    """A claim set that is *allowed* by default, so each test varies exactly one field."""
    return TokenClaims(
        sub="student-external-id",
        role=role,
        account_status=account_status,
        consent_status=consent_status,
        parental_consent_verified=parental_consent_verified,
        consent_version="v1",
        student_age_band=student_age_band,
        issued_at=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
        expires_at=datetime(2026, 8, 21, 13, 0, tzinfo=UTC),
        audience=Audience.LEARNING,
    )


# --- The emptiness pin (REQ-27-FROZENSET, half 1) ---------------------------------------------


def test_age_band_consent_exemptions_are_empty() -> None:
    """The frozenset must stay empty, and this test is the only thing that says so.

    Emptiness is what makes the gate fail closed: with no exempt band, *every* student needs
    `parental_consent_verified`. Adding any string here waives parental consent for whichever
    band the production system happens to emit that string for - a COPPA gate protecting minors,
    opened by a guess, with nothing else in the suite going red.

    If you are reading this because you tripped it: the only legitimate way to fill this set is
    S42's discovery survey measuring the real `student_age_band` vocabulary from the production
    system (see the symbol's own docstring, and D-152 - integration is deferred, so S42 has not
    run). A value chosen from anywhere else is fail-open. When S42 does supply measured bands,
    update this pin deliberately, together with the exemption semantics pinned by
    `test_a_listed_band_is_exempt_but_an_unlisted_or_absent_band_is_not`.
    """
    assert AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT == frozenset()
    assert auth.AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT == frozenset()


# --- The non-empty-set pin (REQ-27-FROZENSET, half 2) -----------------------------------------


def test_a_listed_band_is_exempt_but_an_unlisted_or_absent_band_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What a non-empty frozenset is allowed to mean: an exemption scoped to the listed bands
    and nothing wider.

    The real set is empty, so this is the only place the exemption branch executes at all.
    Pinning it now means S42's measured vocabulary lands on already-pinned semantics: listing a
    band waives rule 3 *for that band*, an unlisted band is unaffected, and a `None` band is
    never exempt - matching the project's standing "unknown is not permission" rule (SPEC
    §5.4.4). Silent breakage of any of the three would be a fail-open change to a COPPA check.
    """
    monkeypatch.setattr(
        auth, "AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT", frozenset({"example_band"})
    )

    # The listed band: exempt, so no parental consent needed.
    allowed = _claims(student_age_band="example_band", parental_consent_verified=False)
    assert auth.account_refusal_reason(allowed) is None

    # A different band is not covered by that entry.
    unlisted = _claims(student_age_band="other_band", parental_consent_verified=False)
    assert auth.account_refusal_reason(unlisted) == _NO_PARENTAL_CONSENT

    # An absent band is never exempt - it is not "not under 13", it is unknown.
    absent = _claims(student_age_band=None, parental_consent_verified=False)
    assert auth.account_refusal_reason(absent) == _NO_PARENTAL_CONSENT

    # The exemption is band-scoped, not a global switch: a listed band still doesn't buy a
    # student past rules 1 and 2.
    suspended = _claims(
        student_age_band="example_band",
        parental_consent_verified=False,
        account_status="suspended",
    )
    assert auth.account_refusal_reason(suspended) == _ACCOUNT_NOT_ACTIVE


# --- The refusal ladder the two pins sit on ---------------------------------------------------


def test_a_consented_active_student_is_allowed() -> None:
    """The positive control: without it, a gate that refused everything would pass every pin
    above."""
    assert auth.account_refusal_reason(_claims()) is None


def test_a_student_without_verified_parental_consent_is_refused() -> None:
    """Rule 3 under the *real* (empty) frozenset: no band is exempt, so every student needs it.
    Both a stated band and an absent one refuse."""
    assert auth.account_refusal_reason(_claims(parental_consent_verified=False)) == (
        _NO_PARENTAL_CONSENT
    )
    assert (
        auth.account_refusal_reason(
            _claims(parental_consent_verified=False, student_age_band="under_13")
        )
        == _NO_PARENTAL_CONSENT
    )


@pytest.mark.parametrize("account_status", ["suspended", "", "Active", "unrecognised"])
def test_any_account_status_other_than_active_is_refused(account_status: str) -> None:
    """Rule 1 is an allowlist of exactly one value, not a "not suspended" denylist: a status
    this app does not own and does not recognise is refused, not waved through."""
    assert auth.account_refusal_reason(_claims(account_status=account_status)) == (
        _ACCOUNT_NOT_ACTIVE
    )


@pytest.mark.parametrize("consent_status", ["revoked", "", "granted ", "pending"])
def test_any_consent_status_other_than_granted_is_refused(consent_status: str) -> None:
    """Rule 2, same allowlist reasoning as rule 1."""
    assert auth.account_refusal_reason(_claims(consent_status=consent_status)) == (
        _CONSENT_NOT_GRANTED
    )


def test_non_student_roles_are_not_age_gated_but_still_face_rules_1_and_2() -> None:
    """Adults are not age-gated, so rule 3 must not fire for them even with
    `parental_consent_verified=False` - but rules 1 and 2 apply to every role."""
    for role in (Role.PARENT, Role.TUTOR, Role.BRANCH_MANAGER):
        assert auth.account_refusal_reason(_claims(role=role, parental_consent_verified=False)) is (
            None
        )
        assert (
            auth.account_refusal_reason(
                _claims(role=role, parental_consent_verified=False, account_status="suspended")
            )
            == _ACCOUNT_NOT_ACTIVE
        )
        assert (
            auth.account_refusal_reason(
                _claims(role=role, parental_consent_verified=False, consent_status="revoked")
            )
            == _CONSENT_NOT_GRANTED
        )


def test_rule_precedence_is_status_then_consent_then_parental() -> None:
    """The reason string returned when several rules fail at once. Pinned because the apps map
    it to a 403 body: rule 1 wins over rule 2, and rule 2 over rule 3."""
    assert (
        auth.account_refusal_reason(
            _claims(
                account_status="suspended",
                consent_status="revoked",
                parental_consent_verified=False,
            )
        )
        == _ACCOUNT_NOT_ACTIVE
    )
    assert (
        auth.account_refusal_reason(
            _claims(consent_status="revoked", parental_consent_verified=False)
        )
        == _CONSENT_NOT_GRANTED
    )
