"""D-092 (S33): mirrors `apps/learning-api/tests/test_config_component_dsn.py` - see
that file's docstring.
"""

from chat_api.config import Settings


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
