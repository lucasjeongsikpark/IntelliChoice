"""AUD-C-16 re-embed path tests - same real-Postgres rollback-session pattern as
`test_ingest.py`. The dev database's own corpus is visible inside the rollback
transaction, so every assertion is scoped to this file's synthetic document rather
than to global counts.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

import pytest
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
from intellichoice_db.engine import create_engine
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_knowledge.ingest import ingest_entry
from intellichoice_knowledge.manifest import DocumentManifestEntry
from intellichoice_knowledge.reembed import run_reembed
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


pytestmark = pytest.mark.skipif(
    (_reason := _postgres_skip_reason()) is not None, reason=_reason or ""
)

_MODEL_ID = "amazon.titan-embed-text-v2:0"


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


def _gateway() -> ResilientBedrockGateway:
    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={BedrockTask.EMBEDDING: _MODEL_ID},
    )


class _DictContentStore:
    def __init__(self, files: dict[str, str]) -> None:
        self._files = files

    def read_text(self, key: str) -> str:
        return self._files[key]


def _entry(document_id: str) -> DocumentManifestEntry:
    return DocumentManifestEntry(
        document_id=document_id,
        title="Reembed Doc",
        source_path=f"test/{document_id}.md",
        audience="public",
        access_level="public",
        academic_year="2026-2027",
        effective_from=date(2026, 8, 1),
        version=1,
        status="approved",
    )


async def _ingest_doc(session: AsyncSession, document_id: str, provider: str) -> int:
    entry = _entry(document_id)
    store = _DictContentStore({entry.source_path: "# Title\n\n## Section\n\nreembed test content"})
    _, chunks_created, _ = await ingest_entry(
        session,
        entry,
        content_store=store,
        gateway=_gateway(),
        session_spend_cents=0.0,
        embedding_provider=provider,
    )
    assert chunks_created > 0
    return chunks_created


async def _doc_provenance(session: AsyncSession, document_id: str) -> list[tuple[str, str]]:
    result = await session.execute(
        text(
            "SELECT embedding_provider, embedding_model_id FROM rag_chunks WHERE document_id = :d"
        ),
        {"d": document_id},
    )
    return [(row[0], row[1]) for row in result.all()]


def test_reembed_replaces_mismatched_provenance_and_skips_current_chunks() -> None:
    async def run() -> None:
        async with _rollback_session() as session:
            n = await _ingest_doc(session, "test-reembed-doc", provider="old-provider")

            summary = await run_reembed(
                session,
                gateway=_gateway(),
                embedding_provider="mock",
                embedding_model_id=_MODEL_ID,
                run_budget_cents=1000.0,
            )
            assert summary.chunks_reembedded >= n
            rows = await _doc_provenance(session, "test-reembed-doc")
            assert all(row == ("mock", _MODEL_ID) for row in rows), rows

            # A second run against the now-current corpus is a no-op - this is what
            # makes the deploy-time re-embed step near-free on a healthy corpus, and
            # it fails if the provenance-matching skip is removed.
            again = await run_reembed(
                session,
                gateway=_gateway(),
                embedding_provider="mock",
                embedding_model_id=_MODEL_ID,
                run_budget_cents=1000.0,
            )
            assert again.chunks_reembedded == 0
            assert again.documents_touched == 0
            assert again.chunks_already_current >= n

    asyncio.run(run())


def test_reembed_treats_null_provenance_as_mismatch() -> None:
    """Rows written before the provenance columns existed are NULL/NULL. Fail closed:
    they are re-embedded, never trusted."""

    async def run() -> None:
        async with _rollback_session() as session:
            n = await _ingest_doc(session, "test-reembed-null-doc", provider="mock")
            await session.execute(
                text(
                    "UPDATE rag_chunks SET embedding_provider = NULL, "
                    "embedding_model_id = NULL WHERE document_id = 'test-reembed-null-doc'"
                )
            )

            repo = RagRepository(session)
            mismatches = await repo.count_embedding_provenance_mismatches(
                embedding_provider="mock", embedding_model_id=_MODEL_ID
            )
            assert mismatches >= n

            summary = await run_reembed(
                session,
                gateway=_gateway(),
                embedding_provider="mock",
                embedding_model_id=_MODEL_ID,
                run_budget_cents=1000.0,
            )
            assert summary.chunks_reembedded >= n
            rows = await _doc_provenance(session, "test-reembed-null-doc")
            assert all(row == ("mock", _MODEL_ID) for row in rows), rows

    asyncio.run(run())


def test_reembed_respects_run_budget() -> None:
    """A zero budget re-embeds nothing - the same bounded-spend rule every paid-API
    caller in this repo follows (CLAUDE.md rule 7)."""

    async def run() -> None:
        async with _rollback_session() as session:
            await _ingest_doc(session, "test-reembed-budget-doc", provider="old-provider")

            summary = await run_reembed(
                session,
                gateway=_gateway(),
                embedding_provider="mock",
                embedding_model_id=_MODEL_ID,
                run_budget_cents=0.0,
            )
            assert summary.chunks_reembedded == 0

            rows = await _doc_provenance(session, "test-reembed-budget-doc")
            assert all(row == ("old-provider", _MODEL_ID) for row in rows), rows

    asyncio.run(run())
