from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from intellichoice_db.models.rag import RagChunk, RagDocument


class ChunkFilters(BaseModel):
    """Metadata filters applied *before* any text/vector search runs (SPEC §5.21.3).

    `audience` is S12's original single-value exact match (kept for its existing
    caller). `audiences` is S13's role-access-filter shape: the caller's full set of
    permitted audiences (always includes "public" plus the resolved role, per §5.19.1) -
    a chunk matches if its `audience` is *any* of these, not all. `as_of` applies the
    `effective_from <= as_of <= effective_to` window; `None` skips the date check (S12's
    ingestion-time callers have no "today" to filter against).
    """

    audience: str | None = None
    audiences: list[str] | None = None
    branch_external_id: str | None = None
    restrict_to_branch: bool = False
    academic_year: str | None = None
    access_level: str | None = None
    as_of: datetime | None = None


def _apply_filters[RowT: tuple[Any, ...]](
    stmt: Select[RowT], filters: ChunkFilters
) -> Select[RowT]:
    stmt = stmt.where(RagChunk.status == "approved")
    if filters.audience is not None:
        stmt = stmt.where(RagChunk.audience == filters.audience)
    if filters.audiences is not None:
        stmt = stmt.where(RagChunk.audience.in_(filters.audiences))
    if filters.restrict_to_branch:
        # SPEC §5.21.3: "branch_id is null OR branch_id = current_branch" - applied
        # unconditionally when this flag is set (S13's real access-control path), even
        # when `branch_external_id` itself is None (an unresolved/branchless caller only
        # ever sees org-wide chunks, never another branch's). S12's original exact-match
        # `branch_external_id` filter (below) stays opt-in-only, since it was never an
        # access-control boundary - just an ingestion-verification convenience.
        stmt = stmt.where(
            or_(
                RagChunk.branch_external_id.is_(None),
                RagChunk.branch_external_id == filters.branch_external_id,
            )
        )
    elif filters.branch_external_id is not None:
        stmt = stmt.where(RagChunk.branch_external_id == filters.branch_external_id)
    if filters.academic_year is not None:
        stmt = stmt.where(RagChunk.academic_year == filters.academic_year)
    if filters.access_level is not None:
        stmt = stmt.where(RagChunk.access_level == filters.access_level)
    if filters.as_of is not None:
        stmt = stmt.where(RagChunk.effective_from <= filters.as_of).where(
            or_(RagChunk.effective_to.is_(None), RagChunk.effective_to >= filters.as_of)
        )
    return stmt


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]], *, k: int = 60, limit: int | None = None
) -> list[str]:
    """SPEC §5.21.6: combines independently-ranked candidate-id lists (e.g. keyword rank,
    vector-distance rank) into one fused order. Standard RRF formula
    `score(id) = sum(1 / (k + rank))` over every list the id appears in (0-indexed rank,
    absent from a list simply contributes nothing from that list) - pure and
    deterministic given fixed rank lists, so it's unit-testable without a live Postgres.
    """
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return ordered if limit is None else ordered[:limit]


class RagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_document(self, document: RagDocument) -> RagDocument:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_document(self, document_id: str) -> RagDocument | None:
        return await self._session.get(RagDocument, document_id)

    async def add_chunk(self, chunk: RagChunk) -> RagChunk:
        self._session.add(chunk)
        await self._session.flush()
        return chunk

    async def delete_chunks_for_document(self, document_id: str) -> None:
        """Used by re-ingestion when a document's `source_sha256` changed - old chunks
        are replaced wholesale rather than diffed, since there's no stable per-chunk
        identity across a content edit (SPEC §5.21.1's ingestion pipeline re-chunks the
        whole document every time).
        """
        await self._session.execute(delete(RagChunk).where(RagChunk.document_id == document_id))
        await self._session.flush()

    async def refresh_search_vectors(self, document_id: str) -> None:
        """Populates `search_vector` (SPEC §5.21.2) for every chunk of a document via
        Postgres `to_tsvector`, run once after a document's chunks are inserted rather
        than computed in Python - keyword search itself isn't wired until S13 (§5.21.5),
        but the column is part of the ingestion-time schema, so it's populated now.
        """
        await self._session.execute(
            update(RagChunk)
            .where(RagChunk.document_id == document_id)
            .values(search_vector=func.to_tsvector("english", RagChunk.chunk_text))
        )
        await self._session.flush()

    async def count_embedding_provenance_mismatches(
        self, *, embedding_provider: str, embedding_model_id: str
    ) -> int:
        """AUD-C-16: how many chunks carry an embedding that was NOT produced by the
        given provider/model. NULL provenance (pre-provenance rows) counts as a mismatch
        - that is the fail-closed reading, and it is what let staging serve real Titan
        queries against mock hash vectors undetected. chat-api's /readyz gates on this
        being zero.
        """
        stmt = (
            select(func.count())
            .select_from(RagChunk)
            .where(
                or_(
                    RagChunk.embedding_provider.is_distinct_from(embedding_provider),
                    RagChunk.embedding_model_id.is_distinct_from(embedding_model_id),
                )
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def get_embedding_provenance_mismatched_chunks(
        self, *, embedding_provider: str, embedding_model_id: str
    ) -> list[RagChunk]:
        """The rows behind `count_embedding_provenance_mismatches`, ordered by document
        so the re-embed path can batch one embedding call per document (the same shape
        ingestion uses).
        """
        stmt = (
            select(RagChunk)
            .where(
                or_(
                    RagChunk.embedding_provider.is_distinct_from(embedding_provider),
                    RagChunk.embedding_model_id.is_distinct_from(embedding_model_id),
                )
            )
            .order_by(RagChunk.document_id, RagChunk.chunk_id)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_document_chunks(self, filters: ChunkFilters, query: str) -> list[RagChunk]:
        """SPEC §5.26.1 predefined method. A plain substring `ILIKE` match, filter-first
        (SPEC §5.20.1's "approved only" plus §5.21.3's metadata filters) - kept as the
        simple existence-check shape S12's ingestion verification already depends on.
        `hybrid_search` below is the real retrieval path (S13, §5.21.4-5.21.6).
        """
        stmt = _apply_filters(select(RagChunk), filters)
        if query:
            stmt = stmt.where(RagChunk.chunk_text.ilike(f"%{query}%"))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def keyword_search_chunk_ids(
        self, filters: ChunkFilters, query: str, *, limit: int
    ) -> list[str]:
        """SPEC §5.21.5: PostgreSQL full-text search via `websearch_to_tsquery` against
        the GIN-indexed `search_vector` column, ranked by `ts_rank`. Returns ids only (not
        full rows) since `hybrid_search` fuses this with the vector-search id list before
        loading any chunk bodies.
        """
        tsquery = func.websearch_to_tsquery("english", query)
        stmt = _apply_filters(select(RagChunk.chunk_id), filters).where(
            RagChunk.search_vector.op("@@")(tsquery)
        )
        stmt = stmt.order_by(func.ts_rank(RagChunk.search_vector, tsquery).desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def semantic_search_chunk_ids(
        self, filters: ChunkFilters, query_embedding: list[float], *, limit: int
    ) -> list[str]:
        """SPEC §5.21.4: pgvector cosine-distance search over the HNSW-indexed
        `embedding` column. Returns ids only, same reasoning as
        `keyword_search_chunk_ids`.
        """
        stmt = _apply_filters(select(RagChunk.chunk_id), filters).where(
            RagChunk.embedding.is_not(None)
        )
        stmt = stmt.order_by(RagChunk.embedding.cosine_distance(query_embedding)).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_chunk_by_document_and_section(
        self, document_id: str, section_title: str | None
    ) -> RagChunk | None:
        """A single, known chunk of a known document, by its exact `section_title` (or
        `None` for the document's root/intro chunk - see `intellichoice_knowledge.
        chunking`'s docstring). Used for content that's grounded in one specific,
        already-known section rather than a query-driven search - e.g. `chat_api.
        services.welcome`'s deterministic welcome excerpt. `RagChunk` has no sequence
        column, so "the Nth chunk of a document" isn't otherwise expressible without
        depending on undefined row order.
        """
        stmt = select(RagChunk).where(
            RagChunk.document_id == document_id,
            RagChunk.section_title == section_title,
            RagChunk.status == "approved",
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    async def get_chunks_by_ids(self, chunk_ids: list[str]) -> dict[str, RagChunk]:
        """Loads full rows for a fused id list, preserving no particular order - callers
        re-order by their own fused ranking (`chunk_ids` from `reciprocal_rank_fusion`).
        """
        if not chunk_ids:
            return {}
        stmt = select(RagChunk).where(RagChunk.chunk_id.in_(chunk_ids))
        result = await self._session.execute(stmt)
        return {chunk.chunk_id: chunk for chunk in result.scalars().all()}

    async def count_matching_by_audience(
        self,
        filters: ChunkFilters,
        query: str,
        query_embedding: list[float] | None = None,
        *,
        max_distance: float = 0.40,
    ) -> dict[str, int]:
        """SPEC §5.19.1/plan §18-C3's access-aware-refusal probe: counts of
        query-matching chunks grouped by `audience`, applying every filter *except* the
        caller's own audience allowlist - so a chunk the caller cannot retrieve still
        contributes to a count, never to content. Returns `{audience: count}` only
        (never chunk ids or text); called only once the turn has already decided it has
        no approved source to answer from - either retrieval came back empty, or
        synthesis refused on what it retrieved (AUD-C-06/D-164, which widened the
        second case in).

        **Two signals, unioned (AUD-C-20/D-165).** The keyword arm alone could not do this
        job: `websearch_to_tsquery` ANDs every content word of the question, so one word the
        chunk happens not to use voids the whole probe - measured against a corpus-derived
        fixture it named the right audience for **3 of 43** questions. A caller does not
        phrase a question in the document's vocabulary. The semantic arm, at a cosine
        distance ceiling, gets **25 of 43** with zero false positives on either negative
        class (questions a public document answers, and questions nothing answers).

        The keyword arm is kept rather than replaced, for two reasons that are not about
        recall: an exact-wording match is free and needs no model, and `MockBedrockProvider`'s
        embeddings are hash-seeded random vectors with no semantic content, so a
        semantic-only probe would be **structurally unobservable** in the entire mock-backed
        test suite. That is D-163's trap wearing different clothes, and one arm the mock can
        exercise is what keeps these tests able to fail.

        `query_embedding` is optional and the caller may legitimately not have one: an
        embedding failure on a path that runs *because* something already failed must degrade
        to keyword-only, not raise. `max_distance` is a measured threshold, not a guess - see
        `scripts/measure_access_probe_rules.py`, which is the instrument that chose it.
        """
        probe_filters = filters.model_copy(update={"audience": None, "audiences": None})
        tsquery = func.websearch_to_tsquery("english", query)
        keyword_stmt = _apply_filters(
            select(RagChunk.audience, func.count()), probe_filters
        ).where(RagChunk.search_vector.op("@@")(tsquery))
        counts = {
            audience: count
            for audience, count in (
                await self._session.execute(keyword_stmt.group_by(RagChunk.audience))
            ).all()
        }
        if query_embedding is None:
            return counts

        # Counted per audience rather than "nearest overall": `build_access_hint` picks the
        # highest-priority *audience* that matched, so collapsing to a single nearest chunk
        # would let one close public-adjacent tier mask a more specific one.
        distance = RagChunk.embedding.cosine_distance(query_embedding)
        semantic_stmt = (
            _apply_filters(select(RagChunk.audience, func.count()), probe_filters)
            .where(RagChunk.embedding.is_not(None))
            .where(distance <= max_distance)
            .group_by(RagChunk.audience)
        )
        for audience, count in (await self._session.execute(semantic_stmt)).all():
            counts[audience] = counts.get(audience, 0) + count
        return counts

    async def hybrid_search(
        self,
        filters: ChunkFilters,
        query: str,
        query_embedding: list[float],
        *,
        candidate_limit: int = 30,
    ) -> list[RagChunk]:
        """SPEC §5.21.6: keyword + semantic candidate lists, fused by Reciprocal Rank
        Fusion, filtered *before* either search runs (§5.21.3 - never retrieve then
        hide). Returns up to `candidate_limit` chunks in fused order; reranking down to
        the final top 5-8 (§5.21.7) is a separate step over this candidate set, since it
        needs an LLM call the repository layer has no business making.
        """
        keyword_ids = await self.keyword_search_chunk_ids(filters, query, limit=candidate_limit)
        semantic_ids = await self.semantic_search_chunk_ids(
            filters, query_embedding, limit=candidate_limit
        )
        fused_ids = reciprocal_rank_fusion([keyword_ids, semantic_ids], limit=candidate_limit)
        chunks_by_id = await self.get_chunks_by_ids(fused_ids)
        return [chunks_by_id[chunk_id] for chunk_id in fused_ids if chunk_id in chunks_by_id]
