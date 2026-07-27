import hmac
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel


class Role(StrEnum):
    STUDENT = "student"
    PARENT = "parent"
    TUTOR = "tutor"
    BRANCH_MANAGER = "branch_manager"


class Audience(StrEnum):
    LEARNING = "learning"
    CHAT = "chat"
    GO = "go"


class TokenClaims(BaseModel):
    sub: str
    role: Role
    account_status: str
    consent_status: str
    parental_consent_verified: bool
    consent_version: str
    student_age_band: str | None = None
    issued_at: datetime
    expires_at: datetime
    audience: Audience


class TokenVerifier(Protocol):
    def verify(self, token: str, audience: Audience) -> TokenClaims: ...


ACCOUNT_STATUS_ACTIVE = "active"
CONSENT_STATUS_GRANTED = "granted"

AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT: frozenset[str] = frozenset()
"""Age bands old enough that SPEC §5.1.2's parental-consent rule does not apply.

Deliberately **empty**. The real vocabulary lives in the production system and is not
known until S42's discovery survey (INTEGRATION_PLAN §3 lists the live role-string survey
and schema snapshot as S42 asks); `student_age_band` is a free-form `str` here for exactly
that reason. Guessing a value like `"13_plus"` and allowing it would create a string that
silently waives parental consent the moment the real system happens to emit it - a
fail-open default written on a guess, in the one check that exists to protect children.

Empty means every student needs verified parental consent today. That is stricter than
§5.1.2's literal "under 13" wording, and it is the right way round to be wrong: S42 fills
this in from measured values and the rule relaxes to match the spec exactly."""


def account_refusal_reason(claims: TokenClaims) -> str | None:
    """SPEC §5.1.2's consuming-side check: may this account use the product at all?

    Returns a short reason to refuse with, or `None` to allow. Returns a value rather
    than raising so the shared package stays free of a FastAPI dependency; each app maps
    it to a 403.

    AUD-X-02 (S40, D-107) found that this did not exist. `account_status`,
    `consent_status` and `parental_consent_verified` are carried in *every* token and were
    read by **nothing** - `grep` across both apps found zero readers outside the model
    definition and the dev issuer. Measured: a token with `account_status="suspended"`,
    `consent_status="revoked"`, `parental_consent_verified=False` and
    `student_age_band="under_13"` behaved **identically** to a fully consented one on all
    18 learning routes. SPEC §5.1.2 is verbatim that the learning app "should verify
    `parental_consent_verified=true` from the existing system", and this is a product
    whose primary users are minors.

    The *issuing* side belongs to S44 (token issuer) and S45 (consent ledger). Those
    sessions decide what the values mean and who may receive them; this function is the
    half that can exist today, and putting it in first means neither session can land
    without something already reading its output. AUD-X-02 warned this sits in the seam
    between them and could be missed by both.

    Three rules, each failing closed:

    1. `account_status` must be exactly `active`. Not "not suspended" - an unrecognised
       status from a system this app does not own is refused, not waved through.
    2. `consent_status` must be exactly `granted`, on the same reasoning.
    3. A student needs `parental_consent_verified` unless their age band is listed in
       `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` - which is empty until S42 measures the
       real vocabulary, so today it applies to every student. An unknown or absent band
       therefore requires consent, matching this project's standing rule that unknown
       attendance is not presence (SPEC §5.4.4): §5.1.2 exists because the strictest
       branch is the one for children, so it has to be the default branch too.

    Roles other than `student` are not age-gated - a parent, tutor or branch manager is
    an adult - but rules 1 and 2 apply to everyone.
    """
    if claims.account_status != ACCOUNT_STATUS_ACTIVE:
        return "account is not active"
    if claims.consent_status != CONSENT_STATUS_GRANTED:
        return "consent has not been granted"
    if claims.role == Role.STUDENT:
        band = claims.student_age_band
        exempt = band is not None and band in AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT
        if not exempt and not claims.parental_consent_verified:
            return "parental consent has not been verified"
    return None


def staging_secret_matches(presented: str | None, configured: str) -> bool:
    """Constant-time check for the S36/D-097 staging token gate, shared by both apps'
    `/dev/token` handlers rather than mirrored, so the two edge cases below can't drift
    apart between them.

    Fails closed on an unconfigured secret: `configured == ""` is never a match, even
    against a caller presenting `""` or omitting the header - otherwise every environment
    that simply doesn't set the secret (local dev, CI, tests, and any future production
    deployment) would treat the *absence* of a credential as possession of it. That is the
    fail-open default this project has now produced three times (D-096's ECR check, S35's
    `2>/dev/null`, D-085's environment-string gate), so it is spelled out rather than
    implied.
    """
    if not configured or presented is None:
        return False
    return hmac.compare_digest(presented, configured)
