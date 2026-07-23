"""S17 (plan §2.3/§8 step 3): `org-load`'s natural-key + content_hash upsert and
inactive-marking, against real Compose Postgres via the same rollback-session pattern
`packages/knowledge/tests/test_ingest.py` uses (D-013). Skips cleanly when Postgres is
unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import intellichoice_webcontent.org_load as org_load
import pytest
import yaml
from intellichoice_db.engine import create_engine
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM org_branches LIMIT 1"))
                except Exception:
                    return "Postgres schema is not migrated (run `make up && make db-upgrade`)"
            return None
        except Exception:
            return "PostgreSQL is not reachable at localhost:5432 (run `make up`)"
        finally:
            await engine.dispose()

    return asyncio.run(check())


@asynccontextmanager
async def _rollback_session() -> AsyncIterator[AsyncSession]:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            trans = await conn.begin()
            session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
            try:
                yield session
            finally:
                await session.close()
                await trans.rollback()
    finally:
        await engine.dispose()


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)


def _write_structured(tmp_path: Path, name: str, source_url: str, records: list[dict]) -> None:
    payload = {
        "source_url": source_url,
        "extracted_at": "2026-07-18T00:00:00+00:00",
        "records": records,
    }
    (tmp_path / f"{name}.yaml").write_text(yaml.safe_dump(payload))


def test_org_load_upserts_then_marks_missing_inactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(org_load, "_STRUCTURED_DIR", tmp_path)

    _write_structured(
        tmp_path,
        "branches",
        "https://www.intellichoice.org/branches/",
        [
            {
                "branch_external_id": "zqxvorgload-riverside",
                "name": "Riverside",
                "address": "100 Main St",
                "hours_raw": "Saturday 10 am",
                "online_only": False,
                "detail_url": "https://www.intellichoice.org/portfolio/riverside/",
                "content_hash": "hash-v1",
            }
        ],
    )
    _write_structured(
        tmp_path,
        "team",
        "https://www.intellichoice.org/pages/our-team/",
        [
            {
                "team_member_id": "zqxvorgload-administration-jane-doe",
                "name": "Jane Doe",
                "role_title": "Founder & CEO",
                "category": "Administration",
                "biography": "A public bio.",
                "content_hash": "hash-v1",
            }
        ],
    )
    _write_structured(
        tmp_path,
        "events",
        "https://www.intellichoice.org/wp-json/tribe/events/v1/events/",
        [
            {
                "event_external_id": "zqxvorgload-banquet",
                "title": "Scholarship Banquet",
                "description": "",
                "starts_at": "2023-12-10 17:00:00",
                "ends_at": "2023-12-10 20:00:00",
                "timezone": "America/Chicago",
                "location": None,
                "registration_url": None,
                "recurrence_rule": None,
                "content_hash": "hash-v1",
            }
        ],
    )

    async def run() -> None:
        async with _rollback_session() as session:
            summary = await org_load.run_org_load(session)
            assert summary.branches_created == 1
            assert summary.members_created == 1
            assert summary.events_created == 1

            branch = await session.get(org_load.OrgBranch, "zqxvorgload-riverside")
            assert branch is not None
            assert branch.status == "active"
            member = await session.get(
                org_load.OrgTeamMember, "zqxvorgload-administration-jane-doe"
            )
            assert member is not None
            assert member.audience == "public"
            event = await session.get(org_load.OrgEvent, "zqxvorgload-banquet")
            assert event is not None
            assert event.audience == "public"
            assert event.status == "scheduled"

            # Re-running with the same content_hash is a no-op on the fields.
            summary_again = await org_load.run_org_load(session)
            assert summary_again.branches_unchanged == 1
            assert summary_again.members_unchanged == 1
            assert summary_again.events_unchanged == 1

            # A branch/member missing from the next sync is marked inactive, not deleted.
            _write_structured(
                tmp_path, "branches", "https://www.intellichoice.org/branches/", []
            )
            _write_structured(
                tmp_path, "team", "https://www.intellichoice.org/pages/our-team/", []
            )
            summary_final = await org_load.run_org_load(session)
            assert summary_final.branches_marked_inactive >= 1
            assert summary_final.members_marked_inactive >= 1
            branch = await session.get(org_load.OrgBranch, "zqxvorgload-riverside")
            assert branch is not None
            assert branch.status == "inactive"

    asyncio.run(run())


def test_org_load_event_resync_never_clears_a_manually_set_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A re-sync that changes an event's own content (e.g. a corrected time) must not
    silently un-cancel it - `status` is the one field a human, not the scraper, owns
    once set to `"canceled"`/`"changed"` (there's no real source signal for either yet).
    """
    monkeypatch.setattr(org_load, "_STRUCTURED_DIR", tmp_path)
    events_url = "https://www.intellichoice.org/wp-json/tribe/events/v1/events/"
    _write_structured(
        tmp_path,
        "branches",
        "https://www.intellichoice.org/branches/",
        [],
    )
    _write_structured(tmp_path, "team", "https://www.intellichoice.org/pages/our-team/", [])
    _write_structured(
        tmp_path,
        "events",
        events_url,
        [
            {
                "event_external_id": "zqxvorgload-workshop",
                "title": "Summer Workshop",
                "description": "",
                "starts_at": "2023-07-10 18:00:00",
                "ends_at": "2023-07-10 20:00:00",
                "timezone": "America/Chicago",
                "location": None,
                "registration_url": None,
                "recurrence_rule": None,
                "content_hash": "hash-v1",
            }
        ],
    )

    async def run() -> None:
        async with _rollback_session() as session:
            await org_load.run_org_load(session)
            event = await session.get(org_load.OrgEvent, "zqxvorgload-workshop")
            assert event is not None
            event.status = "canceled"
            await session.flush()

            _write_structured(
                tmp_path,
                "events",
                events_url,
                [
                    {
                        "event_external_id": "zqxvorgload-workshop",
                        "title": "Summer Workshop (corrected time)",
                        "description": "",
                        "starts_at": "2023-07-10 18:30:00",
                        "ends_at": "2023-07-10 20:00:00",
                        "timezone": "America/Chicago",
                        "location": None,
                        "registration_url": None,
                        "recurrence_rule": None,
                        "content_hash": "hash-v2",
                    }
                ],
            )
            summary = await org_load.run_org_load(session)
            assert summary.events_updated == 1

            event = await session.get(org_load.OrgEvent, "zqxvorgload-workshop")
            assert event is not None
            assert event.title == "Summer Workshop (corrected time)"
            assert event.status == "canceled"

    asyncio.run(run())


def test_org_load_raises_on_missing_structured_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(org_load, "_STRUCTURED_DIR", tmp_path)

    async def run() -> None:
        async with _rollback_session() as session:
            with pytest.raises(org_load.OrgLoadError):
                await org_load.run_org_load(session)

    asyncio.run(run())
