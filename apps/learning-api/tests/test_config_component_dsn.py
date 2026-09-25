"""D-092 (S33): `Settings.database_url`/`mysql_url` build themselves from RDS-managed-
secret component fields when present, since ECS extracts individual JSON keys per env
var rather than a ready DSN string. See `Settings._build_dsns_from_managed_secret_
components`'s docstring on the fields themselves.
"""

import pytest
from learning_api.config import Settings


def test_database_url_stays_at_default_when_no_components_are_set() -> None:
    settings = Settings()
    assert settings.database_url == (
        "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    )


def test_database_url_is_built_from_components_when_all_five_are_present() -> None:
    settings = Settings(
        db_username="intellichoice",
        db_password="s3cr3t",
        db_host="staging-postgres.example.rds.amazonaws.com",
        db_port="5432",
        db_name="intellichoice",
    )
    assert settings.database_url == (
        "postgresql+asyncpg://intellichoice:s3cr3t@"
        "staging-postgres.example.rds.amazonaws.com:5432/intellichoice"
    )


def test_database_url_stays_at_default_when_only_some_components_are_present() -> None:
    settings = Settings(db_username="intellichoice", db_password="s3cr3t")
    assert settings.database_url == (
        "postgresql+asyncpg://intellichoice:intellichoice@localhost:5432/intellichoice"
    )


def test_mysql_url_is_built_from_components_when_all_four_are_present() -> None:
    settings = Settings(
        mysql_db_username="intellichoice",
        mysql_db_password="s3cr3t",
        mysql_db_host="staging-mysql.example.rds.amazonaws.com",
        mysql_db_port="3306",
    )
    assert settings.mysql_url == (
        "mysql+aiomysql://intellichoice:s3cr3t@staging-mysql.example.rds.amazonaws.com:3306"
    )


# D-473 (`STAGING-CONN-CEILING`): the pool shape is settings-driven so a deployment can
# retune one service; the defaults are the connection budget's, not a copied number.
def test_db_pool_defaults_are_the_connection_budget_defaults() -> None:
    from intellichoice_db.engine import DEFAULT_MAX_OVERFLOW, DEFAULT_POOL_SIZE

    settings = Settings()
    assert settings.db_pool_size == DEFAULT_POOL_SIZE
    assert settings.db_max_overflow == DEFAULT_MAX_OVERFLOW


def test_db_pool_shape_is_overridable_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEARNING_DB_POOL_SIZE", "3")
    monkeypatch.setenv("LEARNING_DB_MAX_OVERFLOW", "2")
    settings = Settings()
    assert (settings.db_pool_size, settings.db_max_overflow) == (3, 2)
