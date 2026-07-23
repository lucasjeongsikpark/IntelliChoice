"""CLI entrypoint for the S24 tutor-chat 90-day retention purge (plan §15).

Run with: uv run python -m learning_api.services.tutor_chat_purge_cli

Manual trigger only - the same "schedule later" posture `youtube-sync`/`webcontent-sync`
(S15/S17) already established; no EventBridge-style scheduler exists anywhere in this
codebase yet.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository

from learning_api.config import get_settings

RETENTION_DAYS = 90


async def purge() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
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
