"""SPEC §5.21.8 citation grounding + no-answer/conflict policy -
`chat_api.services.qa.answer_question`. Real Postgres via the rollback-session pattern
(D-013) since verified citations need a real `RagDocument`/`RagChunk` pair to check
against; the Bedrock side is a scripted double (mirrors `apps/learning-api/tests/
test_tutor_service.py::_FakeGateway`) so each test controls exactly what the model
"said" without depending on the mock provider's heuristics.
"""

import asyncio
from datetime import UTC, datetime

import pytest
from chat_api.services import qa
from intellichoice_db.models.rag import RagChunk, RagDocument
from intellichoice_db.repositories.rag import RagRepository
from intellichoice_shared.bedrock import (
    BedrockGatewayError,
    BedrockGenerationResult,
    BedrockTask,
    LlmCitation,
    RagAnswerResponse,
)
from pydantic import BaseModel

from .conftest import postgres_skip_reason, rollback_session

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)


class _FakeGateway:
    """Mirrors `apps/learning-api/tests/test_tutor_service.py::_FakeGateway` - returns
    a fixed outcome regardless of what it's called with, so each test controls the
    model's claimed answer/citations/confidence directly.
    """

    def __init__(self, outcome: BedrockGenerationResult[BaseModel] | BedrockGatewayError) -> None:
        self._outcome = outcome

    async def generate_structured[T: BaseModel](
        self,
        *,
        task: BedrockTask,
        system_prompt: str,
        payload: BaseModel,
        response_model: type[T],
        max_output_tokens: int,
        session_spend_cents: float,
    ) -> BedrockGenerationResult[T]:
        if isinstance(self._outcome, BedrockGatewayError):
            raise self._outcome
        assert isinstance(self._outcome.value, response_model)
        return self._outcome  # type: ignore[return-value]

    async def create_embedding(self, *, texts: list[str], session_spend_cents: float):
        raise NotImplementedError


def _result(value: RagAnswerResponse) -> BedrockGenerationResult[RagAnswerResponse]:
    return BedrockGenerationResult(
        value=value,
        input_tokens=10,
        output_tokens=10,
        cost_cents=0.1,
        model_id="test-model",
        repaired=False,
    )


async def _seed_chunk(session, *, chunk_text: str) -> RagChunk:
    repo = RagRepository(session)
    document = await repo.create_document(
        RagDocument(
            title="Parent Handbook",
            source_path="parent/handbook/content.md",
            audience="parent",
            academic_year="2026-2027",
            effective_from=datetime.now(UTC),
            status="approved",
            source_sha256="b" * 64,
        )
    )
    return await repo.add_chunk(
        RagChunk(
            document_id=document.document_id,
            chunk_text=chunk_text,
            document_title=document.title,
            section_title="Attendance",
            audience="parent",
            access_level="parent",
            academic_year="2026-2027",
            effective_from=document.effective_from,
            status="approved",
            source_sha256="b" * 64,
        )
    )


def test_answer_question_with_no_chunks_returns_no_answer_without_calling_the_model() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            gateway = _FakeGateway(BedrockGatewayError("should never be called"))

            answer, cost = await qa.answer_question(
                repo,
                gateway,
                query="When is attendance required?",
                user_role="parent",
                chunks=[],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert answer.citations == []
            assert answer.confidence == 0.0
            assert answer.escalation_recommended is True
            assert cost == 0.0

    asyncio.run(run())


def test_answer_question_verifies_citation_quote_against_real_chunk_text() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is required for every on-site session.",
                        citations=[
                            LlmCitation(
                                chunk_id=chunk.chunk_id,
                                quote="Attendance is required for every on-site session.",
                            )
                        ],
                        confidence=0.9,
                    )
                )
            )

            answer, cost = await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert len(answer.citations) == 1
            citation = answer.citations[0]
            assert citation.document_title == "Parent Handbook"
            assert citation.source_reference == chunk.document_id
            assert citation.section_title == "Attendance"
            assert answer.escalation_recommended is False
            assert cost == 0.1

    asyncio.run(run())


def test_answer_question_drops_a_citation_whose_quote_is_fabricated() -> None:
    """The model is never trusted just because it *claims* a quote supports the
    answer - a quote that isn't a real substring of the cited chunk is dropped, and
    with no other citations surviving the whole answer becomes a no-answer response
    (SPEC §5.21.8: "Citations do not support the response" -> do not answer).
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is optional for parents.",
                        citations=[
                            LlmCitation(
                                chunk_id=chunk.chunk_id,
                                quote="Attendance is completely optional for everyone.",
                            )
                        ],
                        confidence=0.9,
                    )
                )
            )

            answer, _cost = await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert answer.citations == []
            assert answer.escalation_recommended is True
            assert answer.answer != "Attendance is optional for parents."

    asyncio.run(run())


def test_answer_question_refuses_below_confidence_threshold() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Probably attendance is required, not fully sure.",
                        citations=[
                            LlmCitation(
                                chunk_id=chunk.chunk_id,
                                quote="Attendance is required for every on-site session.",
                            )
                        ],
                        confidence=0.1,
                    )
                )
            )

            answer, _cost = await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert answer.escalation_recommended is True

    asyncio.run(run())


def test_answer_question_surfaces_conflict_instead_of_picking_a_side() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Sources disagree.",
                        citations=[
                            LlmCitation(
                                chunk_id=chunk.chunk_id,
                                quote="Attendance is required for every on-site session.",
                            )
                        ],
                        confidence=0.9,
                        sources_conflict=True,
                    )
                )
            )

            answer, _cost = await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert answer.escalation_recommended is True
            assert answer.answer == qa.CONFLICT_MESSAGE

    asyncio.run(run())


def test_answer_question_falls_back_to_no_answer_on_gateway_error() -> None:
    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(BedrockGatewayError("boom", cost_cents=0.2))

            answer, cost = await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert answer.escalation_recommended is True
            assert cost == 0.2

    asyncio.run(run())
