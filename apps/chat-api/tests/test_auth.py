import pytest
from chat_api import main as main_module
from chat_api.config import Settings
from chat_api.main import app
from fastapi.testclient import TestClient
from intellichoice_adapters.fake_auth import FakeTokenIssuer, JwtTokenVerifier
from intellichoice_shared.auth import Audience, Role

issuer = FakeTokenIssuer()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_me_with_chat_audience_token() -> None:
    token = issuer.issue(sub="parent-ext-1", role=Role.PARENT, audience=Audience.CHAT)
    client = TestClient(app)

    response = client.get("/me", headers=_auth_header(token))

    assert response.status_code == 200
    assert response.json() == {"sub": "parent-ext-1", "role": "parent", "audience": "chat"}


def test_me_rejects_learning_audience_token() -> None:
    token = issuer.issue(sub="parent-ext-1", role=Role.PARENT, audience=Audience.LEARNING)
    client = TestClient(app)

    response = client.get("/me", headers=_auth_header(token))

    assert response.status_code == 401


def test_dev_token_issues_a_verifiable_chat_audience_token() -> None:
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "parent", "sub": "parent-ext-1"})
    assert resp.status_code == 200

    claims = JwtTokenVerifier().verify(resp.json()["token"], Audience.CHAT)
    assert claims.sub == "parent-ext-1"
    assert claims.role == Role.PARENT


def test_dev_token_404s_outside_dev_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_module, "get_settings", lambda: Settings(environment="production"))
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "student", "sub": "student-ext-1"})
    assert resp.status_code == 404


def test_dev_token_404s_when_endpoint_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """D-085: mirrors learning-api's equivalent test - see that one's docstring."""
    monkeypatch.setattr(
        main_module,
        "get_settings",
        lambda: Settings(environment="dev", dev_token_endpoint_enabled=False),
    )
    client = TestClient(app)
    resp = client.post("/dev/token", json={"role": "student", "sub": "student-ext-1"})
    assert resp.status_code == 404


STAGING_SECRET = "s" * 64


def _staging_settings() -> Settings:
    """Exactly staging's real posture (S36/D-097): not a dev environment, the D-085 flag
    off, and only the shared secret configured - so these tests prove the secret alone is
    what opens the endpoint, not some residual dev setting.
    """
    return Settings(
        environment="staging",
        dev_token_endpoint_enabled=False,
        staging_token_shared_secret=STAGING_SECRET,
    )


def test_dev_token_issues_a_token_on_staging_with_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """S36/D-097: mirrors learning-api's equivalent test - see that one's docstring."""
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.post(
        "/dev/token",
        json={"role": "parent", "sub": "parent-ext-1"},
        headers={"X-Staging-Token-Secret": STAGING_SECRET},
    )

    assert resp.status_code == 200
    claims = JwtTokenVerifier().verify(resp.json()["token"], Audience.CHAT)
    assert claims.sub == "parent-ext-1"


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no_header"),
        pytest.param({"X-Staging-Token-Secret": "wrong-secret"}, id="wrong_secret"),
        pytest.param({"X-Staging-Token-Secret": ""}, id="empty_secret"),
    ],
)
def test_dev_token_404s_on_staging_without_the_shared_secret(
    monkeypatch: pytest.MonkeyPatch, headers: dict[str, str]
) -> None:
    """S36/D-097: mirrors learning-api's equivalent test - see that one's docstring."""
    monkeypatch.setattr(main_module, "get_settings", _staging_settings)
    client = TestClient(app)

    resp = client.post(
        "/dev/token", json={"role": "student", "sub": "student-ext-1"}, headers=headers
    )

    assert resp.status_code == 404


CONSENT_REFUSALS = [
    pytest.param({"account_status": "suspended"}, id="suspended-account"),
    pytest.param({"consent_status": "revoked"}, id="revoked-consent"),
    pytest.param(
        {"parental_consent_verified": False, "student_age_band": "under_13"},
        id="unverified-parental-consent",
    ),
]


@pytest.mark.parametrize("claim_overrides", CONSENT_REFUSALS)
def test_account_and_consent_state_is_enforced(claim_overrides: dict) -> None:
    """AUD-X-02 (S40, D-107). SPEC §5.1.2's claims were read by nothing in either app.

    403, not 401: the signature is valid and the token is genuine - the account may not
    use the product. Asserted per-claim rather than with one all-bad token because a
    single token failing three rules passes even if only one is implemented.
    """
    token = issuer.issue(
        sub="student-ext-1", role=Role.STUDENT, audience=Audience.CHAT, **claim_overrides
    )
    with TestClient(app) as client:
        response = client.get("/me", headers=_auth_header(token))
    assert response.status_code == 403


def test_a_fully_consented_token_is_still_accepted() -> None:
    """The control. Every refusal test above passes trivially if `/me` 403s for everyone."""
    token = issuer.issue(sub="student-ext-1", role=Role.STUDENT, audience=Audience.CHAT)
    with TestClient(app) as client:
        response = client.get("/me", headers=_auth_header(token))
    assert response.status_code == 200


def test_a_withdrawn_consent_does_not_silently_downgrade_to_anonymous() -> None:
    """`get_optional_claims` treats a missing header as anonymous, so the tempting
    reading of a revoked token is "fall back to public access". It is refused instead,
    on the same reasoning that function already applies to an expired token: a caller
    whose consent was withdrawn gets a clear signal, not quietly reduced scope. The
    anonymous arm proves the endpoint really does serve callers with no token at all.
    """
    revoked = issuer.issue(
        sub="student-ext-1",
        role=Role.STUDENT,
        audience=Audience.CHAT,
        consent_status="revoked",
    )
    with TestClient(app) as client:
        anonymous_response = client.post("/chat/sessions", json={})
        revoked_response = client.post(
            "/chat/sessions", json={}, headers=_auth_header(revoked)
        )
    assert anonymous_response.status_code in (200, 201)
    assert revoked_response.status_code == 403
