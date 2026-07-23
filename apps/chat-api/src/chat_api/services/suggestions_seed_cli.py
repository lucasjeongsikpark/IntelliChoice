"""CLI entrypoint for `make chat-suggestions-load`.

Run with: uv run python -m chat_api.services.suggestions_seed_cli
"""

import asyncio

from intellichoice_db.engine import create_engine, create_session_factory, session_scope

from chat_api.services.suggestions_seed import seed_default_suggestions


async def main() -> None:
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            created, updated = await seed_default_suggestions(session)
            await session.commit()
        print(f"Chat suggestions: {created} created, {updated} updated.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
