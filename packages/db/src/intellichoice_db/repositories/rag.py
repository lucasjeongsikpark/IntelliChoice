from datetime import datetime
from typing import Any

from intellichoice_shared.access_probe_policy import (
    ACCESS_PROBE_CANDIDATE_LIMIT,
    ACCESS_PROBE_CANDIDATE_MAX_DISTANCE,
    ACCESS_PROBE_MAX_DISTANCE,
    AudienceMatch,
)
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
    # The access probe's inverse of `audiences` (D-168): everything the caller *cannot* read.
    # Expressed as an exclusion rather than an allowlist of the other tiers because `audience`
    # is an open string column - a new tier appearing in the corpus must show up in the probe's
    # candidate pool, not be silently invisible to it.
    exclude_audiences: list[str] | None = None
    branch_external_id: str | None = None
    restrict_to_branch: bool = False
    # **Deliberately not set by the access-control path** (AUD-C-09, dispositioned
    # 2026-08-03): SPEC §5.21.3 lists `academic_year = requested_year` as a sixth
    # pre-retrieval predicate, and the user's call is that it does not apply to this corpus -
    # the handbook set is unified rather than partitioned by year, so retrieval scopes on
    # approved/effective document state plus role access instead. `role_access_filter` leaves
    # this `None` on purpose; an unused option here is not an oversight to re-file.
    # Kept (rather than deleted) as a working, tested repository capability for
    # ingestion-time and verification queries, which is what its existing callers are.
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
    if filters.exclude_audiences:
        stmt = stmt.where(RagChunk.audience.notin_(filters.exclude_audiences))
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

    async def get_chunks_by_ids(
        self, chunk_ids: list[str], *, as_of: datetime | None
    ) -> dict[str, RagChunk]:
        """Loads full rows for a fused id list, preserving no particular order - callers
        re-order by their own fused ranking (`chunk_ids` from `reciprocal_rank_fusion`).

        **Approved-and-effective is re-asserted here, not assumed (DRIFT-68).** This is the
        *second* read of a chunk in a turn: `hybrid_search` fuses ids from two filtered
        queries, and `chat_api.graph.nodes.synthesize_answer` then re-loads the bodies by id
        (`QAState` checkpoints ids and never bodies, deliberately - see its docstring). With
        no predicate here, non-negotiable rule 5 - no RAG answer without an approved,
        effective source - rested entirely on a query that had already run, so an approval
        revoked or a window closed *inside* one turn still reached the answer. Narrow, and
        the direction is not optional.

        Both predicates come from `_apply_filters` rather than being restated, so the
        synthesis-time check cannot drift from the pre-retrieval one. `as_of` is required
        rather than defaulted: a caller with no "today" to compare against passes `None`
        explicitly (the ingestion-time shape `ChunkFilters.as_of` already documents), and
        `status == "approved"` holds either way.

        A row the predicate drops is simply **absent** from the returned mapping, which is
        the shape both callers already handle for an id with no row - so a total loss
        degrades into the existing zero-chunk refusal rather than into an error.
        """
        if not chunk_ids:
            return {}
        stmt = _apply_filters(
            select(RagChunk).where(RagChunk.chunk_id.in_(chunk_ids)), ChunkFilters(as_of=as_of)
        )
        result = await self._session.execute(stmt)
        return {chunk.chunk_id: chunk for chunk in result.scalars().all()}

    async def count_matching_by_audience(
        self,
        filters: ChunkFilters,
        query: str,
        query_embedding: list[float] | None = None,
        *,
        max_distance: float = ACCESS_PROBE_MAX_DISTANCE,
    ) -> dict[str, AudienceMatch]:
        """SPEC §5.19.1/plan §18-C3's access-aware-refusal probe: query-matching chunks
        grouped by `audience`, applying every filter *except* the caller's own audience
        allowlist - so a chunk the caller cannot retrieve still contributes to a match,
        never to content. Returns `{audience: AudienceMatch}` - a count and a relevance
        score, never chunk ids or text; called only once the turn has already decided it
        has no approved source to answer from - either retrieval came back empty, or
        synthesis refused on what it retrieved (AUD-C-06/D-164, which widened the
        second case in).

        **The score is AUD-C-22.** This returned bare counts, so `build_access_hint` had
        nothing to rank audiences by except a fixed tier order, and live it named
        branch_manager for a parent's question because the parent chunk's *distance* -
        computed right here, in the `ORDER BY` - was discarded by `count(*)`. The semantic
        arm now reports `1 - min(distance)` per audience; the lexical arm reports no score,
        because a `@@` match has no relevance scale.

        **Two signals, unioned (AUD-C-20/D-165).** The keyword arm alone could not do this
        job: `websearch_to_tsquery` ANDs every content word of the question, so one word the
        chunk happens not to use voids the whole probe - against questions phrased the way a
        person asks them it names the right audience for **1 of 38**. A caller does not phrase
        a question in the document's vocabulary. The semantic arm, at a cosine distance
        ceiling, gets **23 of 38** with zero false positives on either negative class
        (questions a public document answers, and questions nothing answers).

        The keyword arm is kept rather than replaced, and on realistic phrasing recall is not
        the reason: it contributes nothing the semantic arm does not already find (AUD-C-21
        measured the union as **identical** to the semantic arm at every ceiling). It stays
        because an exact-wording match is free and needs no model, and because
        `MockBedrockProvider`'s embeddings are hash-seeded random vectors with no semantic
        content - a semantic-only probe would be **structurally unobservable** in the entire
        mock-backed test suite. That is D-163's trap wearing different clothes, and one arm the
        mock can exercise is what keeps these tests able to fail.

        `query_embedding` is optional and the caller may legitimately not have one: an
        embedding failure on a path that runs *because* something already failed must degrade
        to keyword-only, not raise. `max_distance` is a measured threshold, not a guess -
        `intellichoice_shared.access_probe_policy` holds the number and the sweep behind it,
        and `scripts/measure_access_probe_rules.py` is the instrument that produced it.
        """
        probe_filters = filters.model_copy(update={"audience": None, "audiences": None})
        tsquery = func.websearch_to_tsquery("english", query)
        keyword_stmt = _apply_filters(select(RagChunk.audience, func.count()), probe_filters).where(
            RagChunk.search_vector.op("@@")(tsquery)
        )
        matches = {
            audience: AudienceMatch(count=count)
            for audience, count in (
                await self._session.execute(keyword_stmt.group_by(RagChunk.audience))
            ).all()
        }
        if query_embedding is None:
            return matches

        # Grouped per audience rather than "nearest overall" because the caller has to name
        # one tier: a single nearest chunk would hide that a second, more specific audience
        # also holds an answer. `min(distance)` is what makes the audiences comparable -
        # `count` alone is a function of how the source document happened to be chunked.
        distance = RagChunk.embedding.cosine_distance(query_embedding)
        semantic_stmt = (
            _apply_filters(
                select(RagChunk.audience, func.count(), func.min(distance)), probe_filters
            )
            .where(RagChunk.embedding.is_not(None))
            .where(distance <= max_distance)
            .group_by(RagChunk.audience)
        )
        for audience, count, nearest in (await self._session.execute(semantic_stmt)).all():
            previous = matches.get(audience)
            matches[audience] = AudienceMatch(
                count=(previous.count if previous else 0) + count,
                score=1.0 - float(nearest),
            )
        return matches

    async def access_probe_candidates(
        self,
        filters: ChunkFilters,
        query_embedding: list[float],
        *,
        max_distance: float = ACCESS_PROBE_CANDIDATE_MAX_DISTANCE,
        limit: int = ACCESS_PROBE_CANDIDATE_LIMIT,
    ) -> list[RagChunk]:
        """The reranked access probe's candidate pool (D-168): the nearest non-accessible
        chunks to the caller's question, closest first, within `max_distance`.

        Unlike `count_matching_by_audience` this returns whole chunks, text included, because
        the next step is a reranker and a reranker needs passages. **That is a real boundary
        change and it is confined to one hop:** the text goes to the gateway and nowhere else -
        `intellichoice_knowledge.retrieval.probe_access` reduces it to `{audience: score}`
        before anything else sees it, and no chunk id, title or text reaches the response, the
        logs or the traces. The caller is expected to pass filters whose `exclude_audiences`
        holds everything the caller *can* read; this method does not enforce that, because the
        audience decision is `role_access`'s job and duplicating it here would be a second
        place for it to be wrong.

        Semantic only. The lexical arm is absent by measurement, not oversight: on human
        phrasing `websearch_to_tsquery` ANDs every content word and names the right audience
        for 1 case in 38 (D-166), and the union of both arms scored *identically* to the
        semantic arm at every ceiling - so ranking a pool by a signal that contributes nothing
        would only displace candidates the reranker could have used.
        """
        distance = RagChunk.embedding.cosine_distance(query_embedding)
        stmt = (
            _apply_filters(select(RagChunk), filters)
            .where(RagChunk.embedding.is_not(None))
            .where(distance <= max_distance)
            .order_by(distance)
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

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
        # `filters.as_of` rather than a fresh clock: the two id queries above already
        # applied this caller's window, so re-deriving one here could disagree with them.
        chunks_by_id = await self.get_chunks_by_ids(fused_ids, as_of=filters.as_of)
        return [chunks_by_id[chunk_id] for chunk_id in fused_ids if chunk_id in chunks_by_id]
