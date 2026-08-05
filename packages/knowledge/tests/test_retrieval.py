"""Query-time retrieval unit tests (SPEC §5.21.3-5.21.7), with fakes for both external
dependencies - no Postgres, no Bedrock.

These exist because of D-115. The rerank call had been failing on *every* real request
for a week and the whole suite stayed green, because nothing tested the rerank contract
itself: the mock provider echoed whatever key the request used, retrieval accepted
whatever the mock returned, and the fallback path answered plausibly when the call blew
up. The three things that would have caught it are pinned here - the output-token budget,
the index round-trip, and the fact that a degraded rerank says so out loud.
"""

import asyncio
import logging
from datetime import UTC, datetime

import pytest
from intellichoice_db.models.rag import RagChunk
from intellichoice_db.repositories.rag import ChunkFilters
from intellichoice_knowledge.retrieval import (
    MIN_RERANK_RELEVANCE_SCORE,
    probe_access,
    retrieve,
)
from intellichoice_shared.access_probe_policy import (
    ACCESS_PROBE_MAX_DISTANCE,
    AudienceMatch,
)
from intellichoice_shared.bedrock import (
    BedrockGenerationResult,
    BedrockTask,
    EmbeddingResult,
    RerankedScore,
    RerankResponse,
    StructuredOutputError,
)
from pydantic import BaseModel

MODEL_ID = "anthropic.claude-test"


def _chunk(chunk_id: str, text: str, audience: str = "public") -> RagChunk:
    return RagChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_text=text,
        document_title="Doc",
        audience=audience,
        access_level=audience,
        academic_year="2026",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _FakeRepo:
    def __init__(
        self,
        chunks: list[RagChunk],
        *,
        fallback_matches: dict[str, AudienceMatch] | None = None,
    ) -> None:
        self._chunks = chunks
        self._fallback_matches = fallback_matches or {}
        self.fallback_calls = 0

    async def hybrid_search(
        self,
        filters: ChunkFilters,
        query: str,
        query_embedding: list[float],
        *,
        candidate_limit: int,
    ) -> list[RagChunk]:
        del filters, query, query_embedding
        return self._chunks[:candidate_limit]

    async def access_probe_candidates(
        self,
        filters: ChunkFilters,
        query_embedding: list[float],
        *,
        max_distance: float,
        limit: int,
    ) -> list[RagChunk]:
        del filters, query_embedding, max_distance
        return self._chunks[:limit]

    async def count_matching_by_audience(
        self,
        filters: ChunkFilters,
        query: str,
        query_embedding: list[float] | None = None,
        *,
        max_distance: float = ACCESS_PROBE_MAX_DISTANCE,
    ) -> dict[str, AudienceMatch]:
        del filters, query, query_embedding, max_distance
        self.fallback_calls += 1
        return self._fallback_matches


class _FakeGateway:
    """Records the rerank request and replays a scripted response (or failure)."""

    def __init__(
        self,
        *,
        scores: list[RerankedScore] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._scores = scores or []
        self._error = error
        self.rerank_max_output_tokens: int | None = None
        self.rerank_payload: BaseModel | None = None

    async def create_embedding(
        self, *, texts: list[str], session_spend_cents: float
    ) -> EmbeddingResult:
        del session_spend_cents
        return EmbeddingResult(
            vectors=[[0.1] * 4 for _ in texts],
            model_id="amazon.titan-embed-text-v2:0",
            dimensions=4,
            cost_cents=0.001,
        )

    async def generate_structured(
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type,
        max_output_tokens: int,
        session_spend_cents: float,
    ):
        del task, system_prompt, response_model, session_spend_cents
        self.rerank_max_output_tokens = max_output_tokens
        self.rerank_payload = payload
        if self._error is not None:
            raise self._error
        return BedrockGenerationResult(
            value=RerankResponse(scores=self._scores),
            input_tokens=100,
            output_tokens=50,
            cost_cents=0.01,
            model_id=MODEL_ID,
            repaired=False,
        )


# The measured need against real Bedrock (Haiku 4.5, `converse` + forced tool call) for
# the index-keyed response at 30 candidates: 613 output tokens. The pre-D-115 fixed cap of
# 1024 was under the *UUID-keyed* need of 1361, which is why every staging rerank
# truncated. Pin comfortably above the measurement so a future shape change that doubles
# the response still fits, and assert the shape itself stayed compact.
_MEASURED_TOKENS_AT_30_CANDIDATES = 613


def test_rerank_output_budget_covers_the_measured_need_at_thirty_candidates() -> None:
    budget = RerankResponse.max_output_tokens_for(30)
    assert budget >= 2 * _MEASURED_TOKENS_AT_30_CANDIDATES
    # ...and stays under the gateway's own hard ceiling, or the derived value is a lie.
    assert budget <= 4000


def test_rerank_output_budget_scales_with_candidate_count() -> None:
    assert RerankResponse.max_output_tokens_for(30) > RerankResponse.max_output_tokens_for(10)
    assert RerankResponse.max_output_tokens_for(0) > 0


def test_retrieval_sends_a_count_derived_budget_and_never_sends_chunk_ids() -> None:
    async def run() -> None:
        chunks = [_chunk(f"chunk-{i}", f"text {i}") for i in range(12)]
        gateway = _FakeGateway(
            scores=[RerankedScore(candidate_index=i, relevance_score=0.5) for i in range(12)]
        )

        await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="saturday hours",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        assert gateway.rerank_max_output_tokens == RerankResponse.max_output_tokens_for(12)
        # The model is asked about positions, not identifiers: no 36-character UUID should
        # ever appear in a rerank request or be expected back in the response.
        assert gateway.rerank_payload is not None
        request_json = gateway.rerank_payload.model_dump_json()
        for chunk in chunks:
            assert chunk.chunk_id not in request_json

    asyncio.run(run())


def test_rerank_scores_map_back_to_the_right_chunks_by_position() -> None:
    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta"), _chunk("c", "gamma")]
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=2, relevance_score=0.9),
                RerankedScore(candidate_index=0, relevance_score=0.4),
                RerankedScore(candidate_index=1, relevance_score=0.0),
            ]
        )

        result = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        # Sorted by score, and the 0.0-scored candidate dropped (the §5.21.7 filter).
        assert [c.chunk_id for c in result.chunks] == ["c", "a"]

    asyncio.run(run())


def test_a_score_for_an_unknown_index_does_not_reorder_anything() -> None:
    """A model that invents index 99 must not shift the real candidates' scores."""

    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=99, relevance_score=1.0),
                RerankedScore(candidate_index=1, relevance_score=0.7),
            ]
        )

        result = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        assert [c.chunk_id for c in result.chunks] == ["b"]

    asyncio.run(run())


def test_a_failed_rerank_falls_back_to_rrf_order_and_logs_the_degradation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The D-115 regression: silent degradation is the defect, not the fallback itself."""

    async def run() -> None:
        chunks = [_chunk(f"chunk-{i}", f"text {i}") for i in range(10)]
        gateway = _FakeGateway(
            error=StructuredOutputError("model hit max_output_tokens=1024", cost_cents=3.2)
        )

        with caplog.at_level(logging.WARNING, logger="intellichoice_knowledge.retrieval"):
            result = await retrieve(
                _FakeRepo(chunks),  # type: ignore[arg-type]
                gateway,  # type: ignore[arg-type]
                query="q",
                filters=ChunkFilters(),
                session_spend_cents=0.0,
                top_k=3,
            )

        assert [c.chunk_id for c in result.chunks] == ["chunk-0", "chunk-1", "chunk-2"]
        # The failed call's real spend still lands on the session total.
        assert result.cost_cents == pytest.approx(0.001 + 3.2)

        degraded = [r for r in caplog.records if r.message == "retrieval_rerank_degraded"]
        assert len(degraded) == 1
        assert degraded[0].reason == "StructuredOutputError"  # type: ignore[attr-defined]
        assert degraded[0].candidate_count == 10  # type: ignore[attr-defined]

    asyncio.run(run())


# --- AUD-C-12: SPEC §5.21.8's "retrieval score is below threshold" trigger -------------
#
# The only score filter used to be `score > 0.0`, so a passage the reranker rated 0.01 went to
# synthesis exactly like one it rated 0.99 - the SPEC trigger had no implementation. The floor
# was measured, not guessed: see `MIN_RERANK_RELEVANCE_SCORE`'s comment and
# `scripts/measure_retrieval_score_floor.py`.


def test_a_candidate_below_the_relevance_floor_is_dropped_before_synthesis() -> None:
    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.9),
                # Above the old `> 0.0` cut and below the measured floor: the exact band this
                # finding is about.
                RerankedScore(candidate_index=1, relevance_score=0.2),
            ]
        )

        result = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        assert [c.chunk_id for c in result.chunks] == ["a"]

    asyncio.run(run())


def test_a_turn_where_nothing_clears_the_floor_retrieves_nothing() -> None:
    """Which is the do-not-answer trigger actually firing: `answer_question` never sees an
    empty chunk list as anything but "no approved source supports an answer", and the graph
    routes it to the access-hint/no-source path without paying for synthesis.
    """

    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.2),
                RerankedScore(candidate_index=1, relevance_score=0.1),
            ]
        )

        result = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        assert result.chunks == []

    asyncio.run(run())


def test_the_caller_can_tighten_the_floor_but_the_default_is_the_measured_one() -> None:
    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
        scores = [
            RerankedScore(candidate_index=0, relevance_score=0.95),
            RerankedScore(candidate_index=1, relevance_score=0.5),
        ]

        loose = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            _FakeGateway(scores=scores),  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )
        tight = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            _FakeGateway(scores=scores),  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
            min_relevance_score=0.9,
        )

        assert [c.chunk_id for c in loose.chunks] == ["a", "b"]
        assert [c.chunk_id for c in tight.chunks] == ["a"]

    asyncio.run(run())


def test_the_default_floor_stays_inside_the_band_that_was_measured() -> None:
    """The measurement, as a guard rather than a comment. Over the coverage fixture's cases
    against real Titan + the real reranker (38.49c, D-172): no unanswerable case scored above
    **0.30**, and the weakest answerable case's own document scored **0.60**. Any floor in
    [0.30, 0.60) empties every unanswerable case while keeping every answerable one; outside
    it, one side of the trade breaks. Moving the constant out of that band means re-running
    `scripts/measure_retrieval_score_floor.py`, not editing this test.
    """
    assert 0.30 <= MIN_RERANK_RELEVANCE_SCORE < 0.60


def test_the_floor_does_not_apply_when_the_reranker_is_unavailable() -> None:
    """Deliberate, and the opposite of fail-closed for one specific reason: with no reranker
    there are no scores, so applying a floor would mean discarding *every* candidate. A
    reranker outage would then become a corpus-wide "no approved source" - the false statement
    about the corpus AUD-C-08/AUD-C-19 exist to prevent - instead of a degraded ranking. The
    degradation is loud (`retrieval_rerank_degraded`), which is what makes this safe.
    """

    async def run() -> None:
        chunks = [_chunk("a", "alpha"), _chunk("b", "beta")]
        gateway = _FakeGateway(
            error=StructuredOutputError("reranker down", cost_cents=0.1),
        )

        result = await retrieve(
            _FakeRepo(chunks),  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            filters=ChunkFilters(),
            session_spend_cents=0.0,
        )

        assert [c.chunk_id for c in result.chunks] == ["a", "b"]

    asyncio.run(run())


# --------------------------------------------------------------------------------------
# The access probe (SPEC §18-C3, D-168/AUD-C-22). Same fakes, same reasons: what broke here
# was a *selection* rule that no unit test expressed, found only by reading a live response.
# --------------------------------------------------------------------------------------


def _probe(
    repo: _FakeRepo,
    gateway: _FakeGateway,
    **kwargs: float,
):
    return probe_access(
        repo,  # type: ignore[arg-type]
        gateway,  # type: ignore[arg-type]
        query="what happens if my child's attendance has not been recorded yet",
        probe_filters=ChunkFilters(exclude_audiences=["public"]),
        query_embedding=[0.1] * 4,
        session_spend_cents=0.0,
        **kwargs,  # type: ignore[arg-type]
    )


def test_probe_scores_every_qualifying_audience_so_the_selector_can_rank_them() -> None:
    """AUD-C-22 in one test: the branch_manager passage outranks the parent one by tier and
    must lose on relevance. Under the rule this replaces, the parent could not win at all.

    The probe returns every audience above the floor rather than hard-coding a winner -
    picking is `role_access.build_access_hint`'s job and there is exactly one place that
    does it. At the shipped floor (0.9) and margin (0.10) that set is provably the winner
    alone: two audiences above 0.9 are always within 0.10 of each other, so the margin
    would already have gone silent. The branch_manager score here (0.85) is below the
    floor and must not be handed to the selector at all - under the pre-AUD-C-23 floor
    (0.8) it was, and the selector had to out-score it.
    """

    async def run() -> None:
        repo = _FakeRepo(
            [
                _chunk("bm-1", "monthly branch reporting", audience="branch_manager"),
                _chunk("p-1", "if attendance is unknown", audience="parent"),
            ]
        )
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.85),
                RerankedScore(candidate_index=1, relevance_score=0.98),
            ]
        )

        result = await _probe(repo, gateway)

        assert set(result.matches) == {"parent"}
        assert result.matches["parent"].score == pytest.approx(0.98)
        assert result.degraded is False
        assert repo.fallback_calls == 0

    asyncio.run(run())


def test_probe_margin_sees_a_runner_up_below_the_floor() -> None:
    """AUD-C-23's second measured lesson, values straight from the corpus-arm stability
    table ("how do I fix an attendance error for my child": branch_manager 0.95, parent
    0.90). A floor-first rule truncates the parent passage before the margin runs, names
    branch_manager on a parent question 3/10 repeats, and resurrects exactly the wrong
    hint AUD-C-22 was filed about. The margin must be computed over the pre-floor bests:
    0.95 - 0.90 is inside the 0.10 margin, so this stays silent.
    """

    async def run() -> None:
        repo = _FakeRepo(
            [
                _chunk("bm-1", "attendance marking procedure", audience="branch_manager"),
                _chunk("p-1", "if attendance is unknown", audience="parent"),
            ]
        )
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.95),
                RerankedScore(candidate_index=1, relevance_score=0.90),
            ]
        )

        result = await _probe(repo, gateway)

        assert result.matches == {}
        assert result.degraded is False
        # Ambiguity is answered with silence, never with the lexical arm's tier priority.
        assert repo.fallback_calls == 0

    asyncio.run(run())


def test_probe_stays_silent_on_the_measured_unanswerable_noise_ceiling() -> None:
    """AUD-C-23's headline case: a question nothing answers, where the nearest gated
    passage is branch_manager material rerank noise scores at 0.75-0.90 (22 samples, max
    0.90 - the value asserted here). Under the old 0.8 floor this fired "log in as a
    branch manager" on 2-3 of 10 repeats, live 6 of 10. With the floor at 0.9 the winner
    fails the floor, and the turn falls through to the lexical arm - which has no match
    either - so the honest no-source message stands.
    """

    async def run() -> None:
        repo = _FakeRepo(
            [
                _chunk("bm-1", "escalation contact procedure", audience="branch_manager"),
                _chunk("p-1", "program overview for parents", audience="parent"),
            ]
        )
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.90),
                RerankedScore(candidate_index=1, relevance_score=0.30),
            ]
        )

        result = await _probe(repo, gateway)

        assert result.matches == {}
        assert result.degraded is False
        # Not the margin path: the winner simply is not relevant enough to name, and the
        # lexical arm gets its measured-clean last word.
        assert repo.fallback_calls == 1

    asyncio.run(run())


def test_probe_stays_silent_when_two_tiers_are_within_the_margin() -> None:
    """The honesty clause. Both tiers genuinely hold attendance material, so naming either is
    a coin flip - and AUD-C-22's argument is that a wrong tier is worse than the honest
    no-source message. Measured: this is what takes wrong tiers from 1-4 to zero.
    """

    async def run() -> None:
        repo = _FakeRepo(
            [
                _chunk("bm-1", "attendance marking procedure", audience="branch_manager"),
                _chunk("p-1", "if attendance is unknown", audience="parent"),
            ]
        )
        gateway = _FakeGateway(
            scores=[
                RerankedScore(candidate_index=0, relevance_score=0.95),
                RerankedScore(candidate_index=1, relevance_score=0.90),
            ]
        )

        result = await _probe(repo, gateway)

        assert result.matches == {}
        assert result.degraded is False

    asyncio.run(run())


def test_probe_ignores_candidates_below_the_relevance_floor() -> None:
    # The floor is what keeps a question nothing answers from producing "log in as a tutor":
    # the nearest gated chunk always exists, and being nearest is not being an answer.
    async def run() -> None:
        repo = _FakeRepo([_chunk("t-1", "tutor register", audience="tutor")])
        gateway = _FakeGateway(scores=[RerankedScore(candidate_index=0, relevance_score=0.5)])

        result = await _probe(repo, gateway)

        assert result.matches == {}

    asyncio.run(run())


def test_probe_falls_back_to_the_distance_rule_when_the_reranker_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """This node runs *because* the turn already failed; the probe may degrade, never raise.
    D-115's lesson is the second half - the downgrade has to be audible.
    """

    async def run() -> None:
        repo = _FakeRepo(
            [_chunk("p-1", "if attendance is unknown", audience="parent")],
            fallback_matches={"parent": AudienceMatch(count=1, score=0.6)},
        )
        gateway = _FakeGateway(
            error=StructuredOutputError("model hit max_output_tokens", cost_cents=2.5)
        )

        with caplog.at_level(logging.WARNING, logger="intellichoice_knowledge.retrieval"):
            result = await _probe(repo, gateway)

        assert result.matches == {"parent": AudienceMatch(count=1, score=0.6)}
        assert result.degraded is True
        assert result.cost_cents == pytest.approx(2.5)
        assert repo.fallback_calls == 1
        degraded = [r for r in caplog.records if r.message == "access_probe_rerank_degraded"]
        assert len(degraded) == 1
        assert degraded[0].reason == "StructuredOutputError"  # type: ignore[attr-defined]

    asyncio.run(run())


def test_probe_without_an_embedding_uses_the_lexical_fallback_and_never_reranks() -> None:
    # The caller's embedding call failed. Keyword-only is the pre-D-165 rule: worse, honest,
    # and above all not a second failure on a path that exists to handle a failure.
    async def run() -> None:
        repo = _FakeRepo(
            [_chunk("t-1", "tutor register", audience="tutor")],
            fallback_matches={"tutor": AudienceMatch(count=2)},
        )
        gateway = _FakeGateway(error=AssertionError("the reranker must not be called"))

        result = await probe_access(
            repo,  # type: ignore[arg-type]
            gateway,  # type: ignore[arg-type]
            query="q",
            probe_filters=ChunkFilters(exclude_audiences=["public"]),
            query_embedding=None,
            session_spend_cents=0.0,
        )

        assert result.matches == {"tutor": AudienceMatch(count=2)}
        assert result.degraded is True
        assert result.cost_cents == 0.0

    asyncio.run(run())


def test_probe_skips_the_model_entirely_when_nothing_is_near_enough() -> None:
    """No candidate under the ceiling means no rerank call - the common case on this path is a
    question nothing answers, and it must not cost a model call to say so. The lexical arm
    still runs: it asks a different question ("does a gated chunk use these exact words") and
    needs no model, so skipping the reranker is not a reason to skip it.
    """

    async def run() -> None:
        repo = _FakeRepo([], fallback_matches={"tutor": AudienceMatch(count=1)})
        gateway = _FakeGateway(error=AssertionError("the reranker must not be called"))

        result = await _probe(repo, gateway)

        assert result.matches == {"tutor": AudienceMatch(count=1)}
        assert result.cost_cents == 0.0
        assert result.degraded is False
        assert repo.fallback_calls == 1

    asyncio.run(run())


def test_probe_sends_passages_but_returns_only_audiences_and_scores() -> None:
    """The boundary the reranked probe moved. Chunk text reaches the gateway - it has to, a
    reranker needs passages - and stops there: nothing the caller receives can carry content
    into the response, the logs or a trace.
    """

    async def run() -> None:
        repo = _FakeRepo([_chunk("p-1", "secret parent-only text", audience="parent")])
        gateway = _FakeGateway(
            scores=[RerankedScore(candidate_index=0, relevance_score=0.95)]
        )

        result = await _probe(repo, gateway)

        payload = gateway.rerank_payload
        assert payload is not None
        assert "secret parent-only text" in payload.model_dump_json()
        # ...and the way back carries no ids, no titles, no text.
        assert set(result.matches) == {"parent"}
        assert all(
            set(vars(match)) == {"count", "score"} for match in result.matches.values()
        )

    asyncio.run(run())
