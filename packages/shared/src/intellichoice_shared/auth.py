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
