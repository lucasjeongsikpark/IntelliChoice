"""S13 hybrid search (SPEC §5.21.3-5.21.6): keyword search, semantic search, Reciprocal
Rank Fusion, and the metadata pre-filter they both run behind.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_db.models.rag import EMBEDDING_DIM, RagChunk, RagDocument
from intellichoice_db.repositories.rag import ChunkFilters, RagRepository, reciprocal_rank_fusion
from intellichoice_shared.access_probe_policy import (
    ACCESS_PROBE_CANDIDATE_MAX_DISTANCE,
    ACCESS_PROBE_MAX_DISTANCE,
)

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


def test_reciprocal_rank_fusion_combines_and_ranks_by_appearance() -> None:
    # "a" is #1 in both lists - strictly outranks anything appearing in only one list.
    keyword_ids = ["a", "b", "c"]
    semantic_ids = ["a", "d", "b"]

    fused = reciprocal_rank_fusion([keyword_ids, semantic_ids])

    assert fused[0] == "a"
    assert set(fused) == {"a", "b", "c", "d"}


def test_reciprocal_rank_fusion_respects_limit() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"]], limit=2)
    assert fused == ["a", "b"]


def _axis_vector(index: int) -> list[float]:
    """A unit vector along one axis - cosine distance to another axis vector is always
    1.0 (orthogonal) while distance to itself is 0.0, so semantic ranking is
    unambiguous without depending on any real embedding model.
    """
    vector = [0.0] * EMBEDDING_DIM
    vector[index] = 1.0
    return vector


async def _seed_document(session, **overrides) -> RagDocument:
    repo = RagRepository(session)
    defaults = dict(
        title="Test Document",
        source_path="test/doc.md",
        audience="public",
        academic_year="2026-2027",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        status="approved",
        source_sha256="a" * 64,
    )
    defaults.update(overrides)
    return await repo.create_document(RagDocument(**defaults))


async def _seed_chunk(session, document: RagDocument, **overrides) -> RagChunk:
    repo = RagRepository(session)
    defaults = dict(
        document_id=document.document_id,
        chunk_text="placeholder text",
        document_title=document.title,
        audience=document.audience,
        access_level=document.audience,
        academic_year=document.academic_year,
        effective_from=document.effective_from,
        status=document.status,
        source_sha256=document.source_sha256,
        embedding=_axis_vector(0),
    )
    defaults.update(overrides)
    chunk = await repo.add_chunk(RagChunk(**defaults))
    await repo.refresh_search_vectors(document.document_id)
    return chunk


def test_hybrid_search_fuses_keyword_and_semantic_candidates() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            document = await _seed_document(session)

            # Only findable by keyword (its embedding is a distractor axis).
            keyword_hit = await _seed_chunk(
                session,
                document,
                chunk_text="Volunteers must complete a background check before helping.",
                embedding=_axis_vector(10),
            )
            # Only findable by semantic proximity to the query vector (axis 0) - its
            # text shares no words with the query.
            semantic_hit = await _seed_chunk(
                session,
                document,
                chunk_text="Instruction is suspended during the winter break period.",
                embedding=_axis_vector(0),
            )
            # Neither keyword nor semantic match.
            await _seed_chunk(
                session,
                document,
                chunk_text="Branch hours are posted on the public calendar page.",
                embedding=_axis_vector(20),
            )

            results = await repo.hybrid_search(
                ChunkFilters(audiences=["public"]),
                "volunteer background check",
                _axis_vector(0),
                candidate_limit=10,
            )

            result_ids = {chunk.chunk_id for chunk in results}
            assert keyword_hit.chunk_id in result_ids
            assert semantic_hit.chunk_id in result_ids

    asyncio.run(run())


def test_hybrid_search_excludes_draft_and_expired_chunks() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            now = datetime.now(UTC)

            draft_document = await _seed_document(session, status="draft")
            draft_chunk = await _seed_chunk(
                session,
                draft_document,
                chunk_text="Draft-only wording about the volunteer program.",
                status="draft",
            )

            expired_document = await _seed_document(
                session,
                effective_from=now - timedelta(days=30),
                effective_to=now - timedelta(days=1),
            )
            expired_chunk = await _seed_chunk(
                session,
                expired_document,
                chunk_text="Expired wording about the volunteer program.",
                effective_from=expired_document.effective_from,
                effective_to=expired_document.effective_to,
            )

            live_document = await _seed_document(session)
            live_chunk = await _seed_chunk(
                session, live_document, chunk_text="Current wording about the volunteer program."
            )

            results = await repo.hybrid_search(
                ChunkFilters(audiences=["public"], as_of=now),
                "volunteer program",
                _axis_vector(0),
                candidate_limit=10,
            )

            result_ids = {chunk.chunk_id for chunk in results}
            assert draft_chunk.chunk_id not in result_ids
            assert expired_chunk.chunk_id not in result_ids
            assert live_chunk.chunk_id in result_ids

    asyncio.run(run())


def test_count_matching_by_audience_ignores_caller_audience_and_returns_counts_only() -> None:
    # D-018-style nonsense marker phrase: the shared dev Postgres carries real seeded
    # content (including real tutor/branch_manager escalation-procedure documents), so a
    # plausible English query here would risk counting real rows this test didn't seed -
    # see PROGRESS.md's S13 carry-over on this exact collision risk for un-`as_of`-scoped
    # queries.
    marker = "zorblex-fluminate procedure"

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)

            tutor_document = await _seed_document(session, audience="tutor")
            await _seed_chunk(
                session,
                tutor_document,
                chunk_text=f"Tutor {marker} for unresolved student concerns.",
                audience="tutor",
                access_level="tutor",
            )

            public_document = await _seed_document(session, audience="public")
            await _seed_chunk(
                session,
                public_document,
                chunk_text=f"Public {marker} for branch questions.",
                audience="public",
                access_level="public",
            )

            matches = await repo.count_matching_by_audience(
                ChunkFilters(audiences=["public"]), marker
            )

            assert matches["tutor"].count == 1
            assert matches["public"].count == 1
            # The probe's own return type proves it: audience -> (count, score), never a
            # chunk id, chunk text, or any other content field could leak through it.
            assert all(
                isinstance(audience, str) and set(vars(match)) == {"count", "score"}
                for audience, match in matches.items()
            )
            # The lexical arm carries no relevance scale, so it must not invent one - a
            # fabricated score here would outrank a real semantic match in the selector.
            assert matches["tutor"].score is None

    asyncio.run(run())


def test_count_matching_by_audience_excludes_non_matching_query_text() -> None:
    marker = "zorblex-fluminate procedure"

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            document = await _seed_document(session, audience="tutor")
            await _seed_chunk(
                session,
                document,
                chunk_text="Branch hours are posted on the public calendar page.",
                audience="tutor",
                access_level="tutor",
            )

            matches = await repo.count_matching_by_audience(
                ChunkFilters(audiences=["public"]), marker
            )

            assert "tutor" not in matches

    asyncio.run(run())


def test_count_matching_by_audience_finds_a_paraphrase_the_keyword_arm_misses() -> None:
    """AUD-C-20/D-165: the probe's semantic arm.

    The keyword arm ANDs every content word of the question, so a caller who does not use
    the document's vocabulary gets nothing — against questions phrased the way a person asks
    them it named the right audience for 1 of 38, where the semantic arm got 23 with no false
    hints on either negative class (AUD-C-21/D-166 re-measured D-165's 3-of-43 vs 25-of-43 on
    a blind-rewrite fixture). This isolates that arm the only way a provider-independent test
    can: the chunk's stored vector and the "query embedding" are the *same axis vector*, so the
    distance is 0 by construction while the two texts share no word at all.

    Both halves are asserted, and the `None` half is the one that would have caught a
    regression where the semantic arm quietly became the only arm.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            document = await _seed_document(session, audience="parent")
            await _seed_chunk(
                session,
                document,
                chunk_text="Zorblex attendance places are held for four fluminate sessions.",
                audience="parent",
                access_level="parent",
                embedding=_axis_vector(7),
            )
            filters = ChunkFilters(audiences=["public"])
            paraphrase = "quibblewort dringle absence policy"

            keyword_only = await repo.count_matching_by_audience(filters, paraphrase)
            assert "parent" not in keyword_only

            with_semantic = await repo.count_matching_by_audience(
                filters, paraphrase, _axis_vector(7), max_distance=0.1
            )
            assert with_semantic["parent"].count == 1
            # Distance 0 by construction (same axis vector), so the score is 1.0 - the
            # semantic arm's score is what AUD-C-22's selector ranks audiences by.
            assert with_semantic["parent"].score == pytest.approx(1.0)

    asyncio.run(run())


def test_count_matching_by_audience_semantic_arm_respects_its_distance_ceiling() -> None:
    """The ceiling is the whole filter at this layer. Semantic search always returns
    *something* (there is no relevance floor in `semantic_search_chunk_ids`), so without a
    ceiling every refusal would produce a hint. Two orthogonal axis vectors sit at cosine
    distance 1.0, comfortably outside any threshold worth using.

    Uses the *shipped* ceiling rather than a literal, so this stays a test of production's
    ceiling as that number moves on measurement (0.40 in D-165, 0.45 in D-166).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            document = await _seed_document(session, audience="tutor")
            await _seed_chunk(
                session,
                document,
                chunk_text="Zorblex tutor register entries close each fluminate week.",
                audience="tutor",
                access_level="tutor",
                embedding=_axis_vector(3),
            )

            matches = await repo.count_matching_by_audience(
                ChunkFilters(audiences=["public"]),
                "quibblewort dringle register",
                _axis_vector(11),
                max_distance=ACCESS_PROBE_MAX_DISTANCE,
            )
            assert "tutor" not in matches

    asyncio.run(run())


def test_hybrid_search_restrict_to_branch_hides_other_branches() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)

            org_wide_document = await _seed_document(session)
            org_wide_chunk = await _seed_chunk(
                session, org_wide_document, chunk_text="Org-wide policy about branch hours."
            )

            branch_a_document = await _seed_document(
                session, audience="branch_manager", branch_external_id="branch-a"
            )
            branch_a_chunk = await _seed_chunk(
                session,
                branch_a_document,
                chunk_text="Branch A specific policy about branch hours.",
                audience="branch_manager",
                access_level="branch_manager",
                branch_external_id="branch-a",
            )

            branch_b_document = await _seed_document(
                session, audience="branch_manager", branch_external_id="branch-b"
            )
            await _seed_chunk(
                session,
                branch_b_document,
                chunk_text="Branch B specific policy about branch hours.",
                audience="branch_manager",
                access_level="branch_manager",
                branch_external_id="branch-b",
            )

            results = await repo.hybrid_search(
                ChunkFilters(
                    audiences=["public", "branch_manager"],
                    branch_external_id="branch-a",
                    restrict_to_branch=True,
                ),
                "policy about branch hours",
                _axis_vector(0),
                candidate_limit=10,
            )

            result_ids = {chunk.chunk_id for chunk in results}
            assert org_wide_chunk.chunk_id in result_ids
            assert branch_a_chunk.chunk_id in result_ids
            assert all(
                chunk.branch_external_id in (None, "branch-a") for chunk in results
            )

    asyncio.run(run())


def test_access_probe_candidates_excludes_what_the_caller_can_read_and_orders_by_distance() -> None:
    """D-168's candidate pool. Two properties, and the exclusion is the load-bearing one: the
    reranked probe ranks a *pool*, so a public chunk left in it would take a slot from the
    gated chunk the probe exists to find (the count-based probe could tolerate public rows
    because the selector discarded them afterwards; a top-N cannot).
    """

    # The shared dev Postgres carries the real approved corpus with real embeddings, and a
    # semantic query cannot be scoped by a nonsense marker the way the keyword tests are. An
    # academic year nothing else uses is the equivalent trick.
    year = "9999-9998"

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            for audience, axis in (("public", 3), ("tutor", 5), ("parent", 7)):
                document = await _seed_document(
                    session, audience=audience, academic_year=year
                )
                await _seed_chunk(
                    session,
                    document,
                    chunk_text=f"Zorblex fluminate notes for {audience}.",
                    audience=audience,
                    access_level=audience,
                    embedding=_axis_vector(axis),
                )

            # Closest to the parent axis, then tutor; public is nearest of all and excluded.
            query = [0.0] * EMBEDDING_DIM
            query[7] = 0.9
            query[5] = 0.4
            query[3] = 1.0
            candidates = await repo.access_probe_candidates(
                ChunkFilters(exclude_audiences=["public"], academic_year=year),
                query,
                max_distance=1.0,
                limit=10,
            )

            assert [c.audience for c in candidates] == ["parent", "tutor"]

    asyncio.run(run())


def test_access_probe_candidates_respects_its_distance_ceiling() -> None:
    # The ceiling is what keeps the reranker from being asked about a corpus that has nothing
    # to do with the question - and asking a model to score irrelevant passages is how a
    # relevance floor gets talked into a false hint.
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            document = await _seed_document(session, audience="tutor")
            await _seed_chunk(
                session,
                document,
                chunk_text="Zorblex tutor register entries close each fluminate week.",
                audience="tutor",
                access_level="tutor",
                embedding=_axis_vector(3),
            )

            candidates = await repo.access_probe_candidates(
                ChunkFilters(exclude_audiences=["public"]),
                _axis_vector(11),
                max_distance=ACCESS_PROBE_CANDIDATE_MAX_DISTANCE,
                limit=10,
            )

            assert candidates == []

    asyncio.run(run())
