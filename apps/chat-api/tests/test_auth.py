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
