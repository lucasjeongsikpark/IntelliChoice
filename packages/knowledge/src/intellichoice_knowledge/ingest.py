"""Idempotent ingestion pipeline (SPEC §5.21.1): manifest -> ContentStore -> chunk ->
embed -> Postgres. Mirrors `intellichoice_curriculum.loader`'s shape (own summary
dataclass, natural-key idempotency, D-016's pattern) but keyed by `source_sha256`
rather than natural-key-alone - a manifest entry's `document_id` is the natural key,
and `source_sha256` decides whether re-ingesting that id is a no-op, an in-place
update (content changed under the same id), or a brand-new document.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockGateway
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_knowledge.chunking import chunk_markdown
from intellichoice_knowledge.content_store import ContentStore
from intellichoice_knowledge.manifest import DocumentManifestEntry, load_all_manifests


@dataclass
class IngestSummary:
    documents_created: int = 0
    documents_updated: int = 0
    documents_unchanged: int = 0
    chunks_created: int = 0
    total_cost_cents: float = 0.0
    entries: list[tuple[str, str]] = field(default_factory=list)  # (document_id, outcome)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _to_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def _apply_entry_fields(document: RagDocument, entry: DocumentManifestEntry) -> None:
    document.title = entry.title
    document.source_path = entry.source_path
    document.audience = entry.audience
    document.branch_external_id = entry.branch_external_id
    document.academic_year = entry.academic_year
    document.effective_from = _to_datetime(entry.effective_from)
    document.effective_to = _to_datetime(entry.effective_to) if entry.effective_to else None
    document.version = entry.version
    document.status = entry.status
    document.supersedes_document_id = entry.supersedes_document_id


async def _persist_chunks(
    session: AsyncSession,
    repo: RagRepository,
    entry: DocumentManifestEntry,
    text: str,
    source_sha256: str,
    gateway: BedrockGateway,
    session_spend_cents: float,
    embedding_provider: str,
) -> tuple[int, float]:
    drafts = chunk_markdown(text, document_id=entry.document_id)
    embedding_result = await gateway.create_embedding(
        texts=[draft.chunk_text for draft in drafts],
        session_spend_cents=session_spend_cents,
    )

    persisted: list[RagChunk] = []
    for draft, vector in zip(drafts, embedding_result.vectors, strict=True):
        chunk = await repo.add_chunk(
            RagChunk(
                document_id=entry.document_id,
                chunk_text=draft.chunk_text,
                document_title=entry.title,
                page_number=None,
                section_title=draft.section_title,
                branch_external_id=entry.branch_external_id,
                audience=entry.audience,
                access_level=entry.access_level,
                academic_year=entry.academic_year,
                effective_from=_to_datetime(entry.effective_from),
                effective_to=(
                    _to_datetime(entry.effective_to) if entry.effective_to else None
                ),
                status=entry.status,
                source_sha256=source_sha256,
                embedding=vector,
                # AUD-C-16: provenance is stamped at write time. The provider string
                # comes from the caller's settings (the same value that selected the
                # provider), the model id from the gateway's own result.
                embedding_provider=embedding_provider,
                embedding_model_id=embedding_result.model_id,
            )
        )
        persisted.append(chunk)

    for draft, chunk in zip(drafts, persisted, strict=True):
        if draft.parent_index is not None:
            chunk.parent_chunk_id = persisted[draft.parent_index].chunk_id
    await session.flush()

    await repo.refresh_search_vectors(entry.document_id)
    return len(persisted), embedding_result.cost_cents


async def ingest_entry(
    session: AsyncSession,
    entry: DocumentManifestEntry,
    *,
    content_store: ContentStore,
    gateway: BedrockGateway,
    session_spend_cents: float,
    embedding_provider: str,
) -> tuple[str, int, float]:
    """Ingests one manifest entry. Returns (outcome, chunks_created, cost_cents) where
    outcome is "created" | "updated" | "unchanged".
    """
    repo = RagRepository(session)
    text = content_store.read_text(entry.source_path)
    source_sha256 = _sha256(text)

    existing = await repo.get_document(entry.document_id)
    if existing is not None and existing.source_sha256 == source_sha256:
        return "unchanged", 0, 0.0

    if existing is not None:
        await repo.delete_chunks_for_document(entry.document_id)
        _apply_entry_fields(existing, entry)
        existing.source_sha256 = source_sha256
        outcome = "updated"
    else:
        await repo.create_document(
            RagDocument(
                document_id=entry.document_id,
                title=entry.title,
                source_path=entry.source_path,
                audience=entry.audience,
                branch_external_id=entry.branch_external_id,
                academic_year=entry.academic_year,
                effective_from=_to_datetime(entry.effective_from),
                effective_to=(
                    _to_datetime(entry.effective_to) if entry.effective_to else None
                ),
                version=entry.version,
                status=entry.status,
                supersedes_document_id=entry.supersedes_document_id,
                source_sha256=source_sha256,
            )
        )
        outcome = "created"

    chunks_created, cost_cents = await _persist_chunks(
        session,
        repo,
        entry,
        text,
        source_sha256,
        gateway,
        session_spend_cents,
        embedding_provider,
    )
    return outcome, chunks_created, cost_cents


async def run_ingestion(
    session: AsyncSession,
    *,
    content_store: ContentStore,
    gateway: BedrockGateway,
    run_budget_cents: float,
    embedding_provider: str,
) -> IngestSummary:
    summary = IngestSummary()
    spend = 0.0
    for entry in load_all_manifests():
        if spend >= run_budget_cents:
            break
        outcome, chunks_created, cost_cents = await ingest_entry(
            session,
            entry,
            content_store=content_store,
            gateway=gateway,
            session_spend_cents=spend,
            embedding_provider=embedding_provider,
        )
        spend += cost_cents
        summary.total_cost_cents += cost_cents
        summary.chunks_created += chunks_created
        summary.entries.append((entry.document_id, outcome))
        if outcome == "created":
            summary.documents_created += 1
        elif outcome == "updated":
            summary.documents_updated += 1
        else:
            summary.documents_unchanged += 1
    return summary
