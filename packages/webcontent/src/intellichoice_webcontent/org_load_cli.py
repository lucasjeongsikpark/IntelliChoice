"""CLI entrypoint for `make org-load` (SPEC §5.20/plan §8 step 3).

Run with: uv run python -m intellichoice_webcontent.org_load_cli

Reads `knowledge-content/structured/{branches,team}.yaml` (already written by
`make webcontent-sync` and reviewed by a human) and upserts `org_branches`/
`org_team_members`. Safe to re-run - unchanged records are a no-op via `content_hash`.
"""

import asyncio

from intellichoice_db.engine import create_engine, create_session_factory, session_scope

from intellichoice_webcontent.org_load import run_org_load


async def main() -> None:
    engine = create_engine()
    try:
        session_factory = create_session_factory(engine)
        async with session_scope(session_factory) as session:
            summary = await run_org_load(session)
            await session.commit()
        print(
            f"Branches: {summary.branches_created} created, {summary.branches_updated} "
            f"updated, {summary.branches_unchanged} unchanged, "
            f"{summary.branches_marked_inactive} marked inactive."
        )
        print(
            f"Team members: {summary.members_created} created, {summary.members_updated} "
            f"updated, {summary.members_unchanged} unchanged, "
            f"{summary.members_marked_inactive} marked inactive."
        )
        print(
            f"Events: {summary.events_created} created, {summary.events_updated} updated, "
            f"{summary.events_unchanged} unchanged."
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
