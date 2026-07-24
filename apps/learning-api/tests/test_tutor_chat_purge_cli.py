"""S33 Security Hardening (SPEC §6.22 "data-deletion testing"). SPEC §15's 90-day
tutor-chat retention purge already had repository-level coverage
(`packages/db/tests/test_repositories.py::test_tutor_chat_message_repository_round_trip`
- an old row purges, a recent one survives) but nothing exercised the actual CLI
entrypoint (`make chat-purge` -> `tutor_chat_purge_cli.purge()`), which computes its own
90-day cutoff and opens its own engine/session rather than reusing an injected one - a
real bug in either of those (wrong cutoff math, wrong timezone) would be invisible to
the repository-level test alone.

Uses `STUDENT_UNLINKED` (D-018's convention for tests that commit real rows against the
shared dev Postgres) - `apps/learning-api/tests/conftest.py`'s autouse teardown already
sweeps `tutor_chat_messages` for this student id before and after every test in this
directory, so no manual cleanup is needed here.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from intellichoice_adapters.seed.mysql_fixtures import STUDENT_UNLINKED
from intellichoice_db.engine import create_engine, create_session_factory, session_scope
from intellichoice_db.models.tutor_chat import TutorChatMessage
from intellichoice_db.repositories.tutor_chat import TutorChatMessageRepository
from learning_api.config import get_settings
from learning_api.services.tutor_chat_purge_cli import RETENTION_DAYS, purge
from sqlalchemy import select


def test_purge_cli_deletes_only_rows_past_the_real_90_day_cutoff() -> None:
    async def run() -> None:
        settings = get_settings()
        engine = create_engine(settings.database_url)
        try:
            session_factory = create_session_factory(engine)
            async with session_scope(session_factory) as session:
                chats = TutorChatMessageRepository(session)
                old = await chats.record(
                    TutorChatMessage(
                        student_external_id=STUDENT_UNLINKED,
                        learning_session_id="purge-cli-test-session",
                        question_variant_id=None,
                        intent="off_topic",
                        redacted_student_message="old message",
                        reply_text="old reply",
                        cost_cents=0.0,
                    )
                )
                # Just past the retention boundary - proves the CLI's own cutoff math
                # (RETENTION_DAYS, not a hardcoded test-local value), not merely that
                # "some very old row" gets deleted.
                old.created_at = datetime.now(UTC) - timedelta(days=RETENTION_DAYS + 1)

                recent = await chats.record(
                    TutorChatMessage(
                        student_external_id=STUDENT_UNLINKED,
                        learning_session_id="purge-cli-test-session",
                        question_variant_id=None,
                        intent="off_topic",
                        redacted_student_message="recent message",
                        reply_text="recent reply",
                        cost_cents=0.0,
                    )
                )
                recent.created_at = datetime.now(UTC) - timedelta(days=RETENTION_DAYS - 1)
                await session.commit()
                old_id, recent_id = old.message_id, recent.message_id

            # The real CLI function - its own engine/session, its own cutoff computation.
            deleted_count = await purge()
            assert deleted_count >= 1

            async with session_scope(session_factory) as session:
                remaining = await session.execute(
                    select(TutorChatMessage.message_id).where(
                        TutorChatMessage.student_external_id == STUDENT_UNLINKED
                    )
                )
                remaining_ids = {row[0] for row in remaining.all()}
                assert old_id not in remaining_ids
                assert recent_id in remaining_ids
        finally:
            await engine.dispose()

    asyncio.run(run())
