"""AUD-C-16 re-embed path: replace every stored embedding whose provenance does not
match the configured provider/model, leaving everything else about the chunk (text,
metadata, parent links, search_vector) untouched.

Provenance-aware and therefore idempotent: a corpus already embedded by the configured
model is a no-op, which is what lets `deploy-staging.yml` run this on every deploy the
way it re-seeds MySQL fixtures (D-111 §3's precedent) at near-zero cost. NULL provenance
(rows written before the provenance columns existed) counts as a mismatch - fail closed,
re-embed rather than trust.
"""

import logging
from dataclasses import dataclass
from itertools import groupby

from intellichoice_db.models.rag import RagChunk
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import BedrockGateway
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ReembedSummary:
    chunks_reembedded: int = 0
    chunks_already_current: int = 0
    documents_touched: int = 0
    total_cost_cents: float = 0.0


async def run_reembed(
    session: AsyncSession,
    *,
    gateway: BedrockGateway,
    embedding_provider: str,
    embedding_model_id: str,
    run_budget_cents: float,
) -> ReembedSummary:
    """Re-embeds mismatched chunks one document at a time (one embedding call per
    document, the same batching shape ingestion uses). Stops between documents when the
    run budget is exhausted - already-re-embedded documents keep their new vectors, so
    a re-run resumes where this one stopped.
    """
    repo = RagRepository(session)
    summary = ReembedSummary()

    total = await _count_all_chunks(session)
    mismatched = await repo.get_embedding_provenance_mismatched_chunks(
        embedding_provider=embedding_provider,
        embedding_model_id=embedding_model_id,
    )
    summary.chunks_already_current = total - len(mismatched)

    spend = 0.0
    for document_id, group in groupby(mismatched, key=lambda c: c.document_id):
        if spend >= run_budget_cents:
            logger.warning(
                "reembed run budget exhausted (%.4f cents); remaining documents left "
                "for a re-run",
                spend,
            )
            break
        chunks = list(group)
        embedding_result = await gateway.create_embedding(
            texts=[chunk.chunk_text for chunk in chunks],
            session_spend_cents=spend,
        )
        for chunk, vector in zip(chunks, embedding_result.vectors, strict=True):
            chunk.embedding = vector
            chunk.embedding_provider = embedding_provider
            chunk.embedding_model_id = embedding_result.model_id
        await session.flush()
        spend += embedding_result.cost_cents
        summary.total_cost_cents += embedding_result.cost_cents
        summary.chunks_reembedded += len(chunks)
        summary.documents_touched += 1
        logger.info("reembedded %d chunk(s) of %s", len(chunks), document_id)

    return summary


async def _count_all_chunks(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(RagChunk))
    return int(result.scalar_one())
