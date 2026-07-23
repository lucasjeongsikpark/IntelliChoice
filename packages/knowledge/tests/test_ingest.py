"""SPEC §5.20/§5.21.1 ingestion pipeline tests - real Compose Postgres via the same
rollback-session pattern as `packages/curriculum/tests/test_ai_pipeline.py` (D-013).
Skips cleanly when Postgres is unreachable (D-008).
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.rag import ChunkFilters, RagRepository
from intellichoice_knowledge.content_store import LocalFilesystemContentStore
from intellichoice_knowledge.ingest import ingest_entry, run_ingestion
from intellichoice_knowledge.manifest import DocumentManifestEntry, load_all_manifests
from intellichoice_shared.bedrock import BedrockTask
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _postgres_skip_reason() -> str | None:
    async def check() -> str | None:
        engine = create_engine()
        try:
            async with engine.connect() as conn:
                try:
                    await conn.execute(text("SELECT 1 FROM rag_documents LIMIT 1"))
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


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0"},
    )


class _DictContentStore:
    """In-memory `ContentStore` double - proves the Protocol is swappable without
    touching real files, and lets the update-path test change content deterministically.
    """

    def __init__(self, files: dict[str, str]) -> None:
        self._files = files

    def read_text(self, key: str) -> str:
        return self._files[key]


async def _document_row_count(session: AsyncSession, document_ids: list[str]) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM rag_documents WHERE document_id = ANY(:ids)"),
        {"ids": document_ids},
    )
    return result.scalar() or 0


async def _chunk_row_count(session: AsyncSession, document_ids: list[str]) -> int:
    result = await session.execute(
        text("SELECT count(*) FROM rag_chunks WHERE document_id = ANY(:ids)"),
        {"ids": document_ids},
    )
    return result.scalar() or 0


def test_ingestion_creates_all_documents_then_is_idempotent_on_rerun() -> None:
    """Deliberately doesn't assume the table starts empty - a real `make knowledge-load`
    run against the shared dev Postgres (outside this test's rollback transaction) may
    have already ingested some or all of these documents. What matters for idempotency
    is that every manifest document ends up existing exactly once, and that a second
    identical run creates nothing new.
    """

    async def run() -> None:
        async with _rollback_session() as session:
            gateway = _gateway()
            content_store = LocalFilesystemContentStore()
            manifest_entries = load_all_manifests()
            document_ids = [entry.document_id for entry in manifest_entries]

            first = await run_ingestion(
                session,
                content_store=content_store,
                gateway=gateway,
                run_budget_cents=1000.0,
            )
            assert first.documents_updated == 0
            assert first.documents_created + first.documents_unchanged == len(
                manifest_entries
            )

            row_count = await _document_row_count(session, document_ids)
            assert row_count == len(manifest_entries)
            chunk_count_after_first = await _chunk_row_count(session, document_ids)
            assert chunk_count_after_first > 0

            second = await run_ingestion(
                session,
                content_store=content_store,
                gateway=gateway,
                run_budget_cents=1000.0,
            )
            assert second.documents_created == 0
            assert second.documents_updated == 0
            assert second.documents_unchanged == len(manifest_entries)
            assert second.chunks_created == 0

            row_count_after_rerun = await _document_row_count(session, document_ids)
            chunk_count_after_rerun = await _chunk_row_count(session, document_ids)
            assert row_count_after_rerun == row_count
            assert chunk_count_after_rerun == chunk_count_after_first

    asyncio.run(run())


def test_draft_document_chunks_are_never_returned_by_search_document_chunks() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            await run_ingestion(
                session,
                content_store=LocalFilesystemContentStore(),
                gateway=_gateway(),
                run_budget_cents=1000.0,
            )
            repo = RagRepository(session)

            # A phrase that only exists in a status=draft document.
            draft_only = await repo.search_document_chunks(
                ChunkFilters(), "still in draft review and is not yet published"
            )
            assert draft_only == []

            # The same document exists in the DB (as status=draft), proving the empty
            # result above is the status filter working, not an ingestion miss.
            row = (
                await session.execute(
                    text(
                        "SELECT status FROM rag_chunks WHERE chunk_text LIKE "
                        "'%still in draft review%'"
                    )
                )
            ).scalar()
            assert row == "draft"

            # A phrase from a status=approved document is findable. Uses the static
            # template wording `render_branch_directory` always emits (S17), not
            # scraped branch names/addresses that change on every real re-sync.
            approved_hit = await repo.search_document_chunks(
                ChunkFilters(), "assigned to exactly one branch at enrollment"
            )
            assert len(approved_hit) >= 1
            assert all(chunk.status == "approved" for chunk in approved_hit)

    asyncio.run(run())


def test_ingest_entry_updates_in_place_when_content_hash_changes() -> None:
    async def run() -> None:
        entry = DocumentManifestEntry(
            document_id="test-changing-doc",
            title="Changing Doc",
            source_path="test/changing.md",
            audience="public",
            access_level="public",
            academic_year="2026-2027",
            effective_from=date(2026, 8, 1),
            version=1,
            status="approved",
        )
        async with _rollback_session() as session:
            gateway = _gateway()
            store_v1 = _DictContentStore(
                {"test/changing.md": "# Title\n\n## Section\n\noriginal content here"}
            )
            outcome, chunks_created, _ = await ingest_entry(
                session,
                entry,
                content_store=store_v1,
                gateway=gateway,
                session_spend_cents=0.0,
            )
            assert outcome == "created"
            assert chunks_created > 0

            # Re-ingesting identical content is a no-op.
            outcome_again, chunks_again, _ = await ingest_entry(
                session,
                entry,
                content_store=store_v1,
                gateway=gateway,
                session_spend_cents=0.0,
            )
            assert outcome_again == "unchanged"
            assert chunks_again == 0

            # Changed content under the same document_id replaces the chunks, not dupes.
            store_v2 = _DictContentStore(
                {"test/changing.md": "# Title\n\n## Section\n\ncompletely different text now"}
            )
            outcome_updated, chunks_updated, _ = await ingest_entry(
                session,
                entry,
                content_store=store_v2,
                gateway=gateway,
                session_spend_cents=0.0,
            )
            assert outcome_updated == "updated"
            assert chunks_updated > 0

            remaining = (
                await session.execute(
                    text(
                        "SELECT chunk_text FROM rag_chunks WHERE document_id = "
                        "'test-changing-doc'"
                    )
                )
            ).scalars().all()
            joined = " ".join(remaining)
            assert "completely different text now" in joined
            assert "original content here" not in joined
            assert len(remaining) == chunks_updated

    asyncio.run(run())
