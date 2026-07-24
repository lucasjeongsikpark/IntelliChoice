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
