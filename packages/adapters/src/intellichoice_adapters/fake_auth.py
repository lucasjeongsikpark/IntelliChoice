from datetime import UTC, datetime, timedelta
from enum import StrEnum

import jwt
from intellichoice_shared.auth import Audience, Role, TokenClaims

DEV_JWT_SECRET = "dev-insecure-secret-do-not-use-in-production"
DEV_JWT_ALGORITHM = "HS256"


class TokenErrorReason(StrEnum):
    EXPIRED = "expired"
    BAD_SIGNATURE = "bad_signature"
    WRONG_AUDIENCE = "wrong_audience"
    MALFORMED = "malformed"


class TokenError(Exception):
    def __init__(self, reason: TokenErrorReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


class FakeTokenIssuer:
    """Dev-only stand-in for the existing go.intellichoice.org auth system.

    Issues JWTs carrying the SPEC §5.1.2 claim set. Never used outside dev/test.
    """

    def __init__(self, secret: str = DEV_JWT_SECRET) -> None:
        self._secret = secret

    def issue(
        self,
        *,
        sub: str,
        role: Role,
        audience: Audience,
        account_status: str = "active",
        consent_status: str = "granted",
        parental_consent_verified: bool = True,
        consent_version: str = "v1",
        student_age_band: str | None = None,
        ttl: timedelta = timedelta(hours=1),
    ) -> str:
        now = datetime.now(UTC)
        claims = TokenClaims(
            sub=sub,
            role=role,
            account_status=account_status,
            consent_status=consent_status,
            parental_consent_verified=parental_consent_verified,
            consent_version=consent_version,
            student_age_band=student_age_band,
            issued_at=now,
            expires_at=now + ttl,
            audience=audience,
        )
        payload = claims.model_dump(mode="json")
        return jwt.encode(payload, self._secret, algorithm=DEV_JWT_ALGORITHM)


class JwtTokenVerifier:
    def __init__(self, secret: str = DEV_JWT_SECRET) -> None:
        self._secret = secret

    def verify(self, token: str, audience: Audience) -> TokenClaims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[DEV_JWT_ALGORITHM],
                options={"verify_exp": False},
            )
        except jwt.InvalidSignatureError as exc:
            raise TokenError(TokenErrorReason.BAD_SIGNATURE) from exc
        except jwt.PyJWTError as exc:
            raise TokenError(TokenErrorReason.MALFORMED) from exc

        try:
            claims = TokenClaims.model_validate(payload)
        except Exception as exc:
            raise TokenError(TokenErrorReason.MALFORMED) from exc

        if claims.expires_at <= datetime.now(UTC):
            raise TokenError(TokenErrorReason.EXPIRED)

        if claims.audience != audience:
            raise TokenError(TokenErrorReason.WRONG_AUDIENCE)

        return claims
