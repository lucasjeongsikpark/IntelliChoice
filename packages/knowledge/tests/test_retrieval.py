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
from intellichoice_knowledge.retrieval import retrieve
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


def _chunk(chunk_id: str, text: str) -> RagChunk:
    return RagChunk(
        chunk_id=chunk_id,
        document_id="doc-1",
        chunk_text=text,
        document_title="Doc",
        audience="public",
        access_level="public",
        academic_year="2026",
        effective_from=datetime(2026, 1, 1, tzinfo=UTC),
    )


class _FakeRepo:
    def __init__(self, chunks: list[RagChunk]) -> None:
        self._chunks = chunks

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
