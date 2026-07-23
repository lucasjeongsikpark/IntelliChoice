from datetime import timedelta

import pytest
from intellichoice_adapters.fake_auth import (
    FakeTokenIssuer,
    JwtTokenVerifier,
    TokenError,
    TokenErrorReason,
)
from intellichoice_shared.auth import Audience, Role


def test_valid_token_round_trips() -> None:
    issuer = FakeTokenIssuer()
    verifier = JwtTokenVerifier()
    token = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.LEARNING)

    claims = verifier.verify(token, Audience.LEARNING)

    assert claims.sub == "student-ext-1"
    assert claims.role == Role.STUDENT
    assert claims.audience == Audience.LEARNING


def test_expired_token_is_rejected() -> None:
    issuer = FakeTokenIssuer()
    verifier = JwtTokenVerifier()
    token = issuer.issue(
        sub="student-ext-1",
        role=Role.STUDENT,
        audience=Audience.LEARNING,
        ttl=timedelta(seconds=-1),
    )

    with pytest.raises(TokenError) as exc_info:
        verifier.verify(token, Audience.LEARNING)
    assert exc_info.value.reason == TokenErrorReason.EXPIRED


def test_wrong_audience_is_rejected() -> None:
    issuer = FakeTokenIssuer()
    verifier = JwtTokenVerifier()
    token = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.LEARNING)

    with pytest.raises(TokenError) as exc_info:
        verifier.verify(token, Audience.CHAT)
    assert exc_info.value.reason == TokenErrorReason.WRONG_AUDIENCE


def test_tampered_signature_is_rejected() -> None:
    issuer = FakeTokenIssuer()
    verifier = JwtTokenVerifier(secret="a-different-secret-that-is-long-enough-for-hs256")
    token = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.LEARNING)

    with pytest.raises(TokenError) as exc_info:
        verifier.verify(token, Audience.LEARNING)
    assert exc_info.value.reason == TokenErrorReason.BAD_SIGNATURE


def test_malformed_token_is_rejected() -> None:
    verifier = JwtTokenVerifier()

    with pytest.raises(TokenError) as exc_info:
        verifier.verify("not-a-jwt", Audience.LEARNING)
    assert exc_info.value.reason == TokenErrorReason.MALFORMED
