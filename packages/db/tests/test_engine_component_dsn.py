"""D-092 (S33): RDS's native `manage_master_user_password` (real auto-rotation) makes
the master password a Secrets-Manager JSON secret, not a ready DSN string - ECS extracts
individual JSON keys per env var, so `create_engine()`'s bare-call fallback (used by
every standalone CLI - curriculum loader, knowledge ingest, etc. - and, separately,
`alembic/env.py`) needs to assemble a DSN from five component env vars when present.
"""

import pytest
from intellichoice_db.engine import DEFAULT_DATABASE_URL, database_url_from_component_env_vars

_COMPONENT_ENV_VARS = ("DB_USERNAME", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME")


@pytest.fixture(autouse=True)
def _clear_component_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _COMPONENT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_returns_none_when_no_components_are_set() -> None:
    assert database_url_from_component_env_vars() is None


def test_returns_none_when_only_some_components_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USERNAME", "intellichoice")
    monkeypatch.setenv("DB_PASSWORD", "secret")
    # DB_HOST/DB_PORT/DB_NAME deliberately left unset.
    assert database_url_from_component_env_vars() is None


def test_builds_dsn_when_all_five_components_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_USERNAME", "intellichoice")
    monkeypatch.setenv("DB_PASSWORD", "s3cr3t")
    monkeypatch.setenv("DB_HOST", "staging-postgres.example.rds.amazonaws.com")
    monkeypatch.setenv("DB_PORT", "5432")
    monkeypatch.setenv("DB_NAME", "intellichoice")
    dsn = database_url_from_component_env_vars()
    assert dsn == (
        "postgresql+asyncpg://intellichoice:s3cr3t@"
        "staging-postgres.example.rds.amazonaws.com:5432/intellichoice"
    )
    assert dsn != DEFAULT_DATABASE_URL
