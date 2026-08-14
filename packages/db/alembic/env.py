import asyncio
import os
from logging.config import fileConfig

from alembic import context
from intellichoice_db.engine import (
    DEFAULT_DATABASE_URL,
    database_url_from_component_env_vars,
    ssl_connect_args,
)
from intellichoice_db.migration_filters import include_object
from intellichoice_db.models import Base
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Dev-only hardcoded default (mirrors D-006); `DATABASE_URL` env var (or, since S33/
# D-092, the five-component `DB_USERNAME`/`DB_PASSWORD`/`DB_HOST`/`DB_PORT`/`DB_NAME`
# fallback - see `database_url_from_component_env_vars`'s docstring) overrides it for
# deployed environments (S32/D-084), since a migration-runner task has no `localhost` to
# reach.
config.set_main_option(
    "sqlalchemy.url",
    database_url_from_component_env_vars() or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL),
)

target_metadata = Base.metadata

# D-332: `include_object` keeps autogenerate from proposing `drop_table` for LangGraph's four
# checkpoint tables, which hold every live session and are absent from `Base.metadata`. Defined in
# `intellichoice_db.migration_filters` rather than here so it is importable and unit-tested - see
# `packages/db/tests/test_autogenerate_never_drops_the_checkpoint_tables.py`.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # S34: `async_engine_from_config` builds its own engine directly from the
    # `sqlalchemy.url` config option - it never goes through `intellichoice_db.engine.
    # create_engine`, so that function's own SSL fix doesn't reach here on its own (found
    # live: fixing `create_engine` alone did not stop a real migration-task failure
    # against real RDS - see `ssl_connect_args`'s docstring for the full story).
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=ssl_connect_args(config.get_main_option("sqlalchemy.url") or ""),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
