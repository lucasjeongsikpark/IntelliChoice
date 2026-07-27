"""CLI entrypoint for the S24 tutor-chat 90-day retention purge (plan §15).

Run with: uv run python -m learning_api.services.tutor_chat_purge_cli

Runs unattended on an EventBridge schedule since S40 (`intellichoice-staging-chat-purge`,
daily) - daily rather than weekly because the cutoff is computed per run, so a weekly
schedule would let a message sit up to 97 days against a 90-day promise.

**`create_engine()` is called bare, and that is load-bearing.** This module runs inside the
ops task, whose environment supplies the *unprefixed* five-component DSN vars
(`DB_HOST`/`DB_PORT`/`DB_NAME` + username/password from Secrets Manager) that
`create_engine`'s D-092 fallback understands. It used to pass `get_settings().database_url`
instead - and `learning_api.config.Settings` has `env_prefix="LEARNING_"`, so it looked for
`LEARNING_DB_HOST` etc., found nothing, and silently kept its hardcoded localhost default.
The first scheduled run therefore died with `ConnectionRefusedError: Connect call failed
('127.0.0.1', 5432)`: this job had never once run against the deployed database, because
every prior invocation was a developer's `make chat-purge` where localhost is correct.
Third time this exact shape has appeared (see `create_engine`'s own docstring for the
S32/D-084 curriculum-load instance), hence the guard test in
`packages/db/tests/test_standalone_clis_use_the_env_fallback.py`.

The two FastAPI apps' `main.py` still pass their settings URL explicitly, correctly - they
get the `LEARNING_`/`CHAT_`-prefixed components from their own task definitions.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository

RETENTION_DAYS = 90


async def purge() -> int:
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
            deleted = await TutorChatMessageRepository(session).purge_older_than(cutoff)
            await session.commit()
            return deleted
    finally:
        await engine.dispose()


def main() -> None:
    deleted = asyncio.run(purge())
    print(f"purged {deleted} tutor_chat_messages row(s) older than {RETENTION_DAYS} days")


if __name__ == "__main__":
    main()
