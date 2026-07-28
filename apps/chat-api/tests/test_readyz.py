import asyncio
import uuid
from datetime import UTC, datetime

from chat_api.main import app
from fastapi.testclient import TestClient
from intellichoice_db.engine import create_engine
from intellichoice_db.models.rag import EMBEDDING_DIM, RagChunk, RagDocument
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine


def test_readyz_reports_ready_when_both_databases_are_reachable() -> None:
    """If `corpus` is False here, the local corpus predates the AUD-C-16 provenance
    columns - run `make knowledge-reembed` once (mock provider, free, seconds)."""
    with TestClient(app) as client:
        response = client.get("/readyz")

    assert response.status_code == 200, response.json()
    assert response.json() == {
        "status": "ready",
        "postgres": True,
        "mysql": True,
        "corpus": True,
    }


def test_readyz_returns_503_when_postgres_is_unreachable() -> None:
    with TestClient(app) as client:
        app.state.db_engine = create_async_engine(
            "postgresql+asyncpg://nobody:nobody@127.0.0.1:1/nonexistent",
            connect_args={"timeout": 1},
        )
        response = client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["postgres"] is False


def test_readyz_fails_closed_on_embedding_provenance_mismatch() -> None:
    """AUD-C-16: staging served real Titan query vectors against mock hash chunk
    vectors for weeks and nothing detected it. One chunk whose stored embedding was
    produced by a different provider/model than the runtime is configured with must
    make the service not-ready - /readyz is the ALB target-group health check, so this
    is what drains a mis-embedded deployment instead of letting it answer with noise.

    The chunk is committed (readyz reads through its own session, so a rollback
    fixture can't reach it) and deleted in the cleanup.
    """
    document_id = f"test-readyz-provenance-{uuid.uuid4().hex[:8]}"

    async def seed() -> None:
        engine = create_engine()
        try:
            async with AsyncSession(engine) as session:
                session.add(
                    RagDocument(
                        document_id=document_id,
                        title="Readyz Provenance Probe",
                        source_path="test/readyz-provenance.md",
                        audience="public",
                        academic_year="2026-2027",
                        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
                        version=1,
                        status="draft",
                        source_sha256="0" * 64,
                    )
                )
                session.add(
                    RagChunk(
                        document_id=document_id,
                        chunk_text="readyz provenance probe chunk",
                        document_title="Readyz Provenance Probe",
                        audience="public",
                        access_level="public",
                        academic_year="2026-2027",
                        effective_from=datetime(2026, 8, 1, tzinfo=UTC),
                        status="draft",
                        source_sha256="0" * 64,
                        embedding=[0.0] * EMBEDDING_DIM,
                        embedding_provider="some-other-provider",
                        embedding_model_id="some-other-model",
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    async def cleanup() -> None:
        engine = create_engine()
        try:
            async with AsyncSession(engine) as session:
                await session.execute(
                    text("DELETE FROM rag_chunks WHERE document_id = :d"),
                    {"d": document_id},
                )
                await session.execute(
                    text("DELETE FROM rag_documents WHERE document_id = :d"),
                    {"d": document_id},
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(seed())
    try:
        with TestClient(app) as client:
            response = client.get("/readyz")

        assert response.status_code == 503, response.json()
        body = response.json()
        assert body["status"] == "not_ready"
        assert body["corpus"] is False
        assert body["corpus_embedding_mismatches"] >= 1
        assert body["postgres"] is True
        assert body["mysql"] is True
    finally:
        asyncio.run(cleanup())
