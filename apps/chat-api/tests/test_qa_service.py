"""SPEC §5.21.8 citation grounding + no-answer/conflict policy -
`chat_api.services.qa.answer_question`. Real Postgres via the rollback-session pattern
(D-013) since verified citations need a real `RagDocument`/`RagChunk` pair to check
against; the Bedrock side is a scripted double (mirrors `apps/learning-api/tests/
test_tutor_service.py::_FakeGateway`) so each test controls exactly what the model
"said" without depending on the mock provider's heuristics.
"""

import asyncio
import logging
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
from sqlalchemy import text

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
        self.max_output_tokens: int | None = None
        self.payload: BaseModel | None = None

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
        self.max_output_tokens = max_output_tokens
        self.payload = payload
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
                                context_index=0,
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
                                context_index=0,
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


def test_a_quote_spanning_a_hard_wrapped_line_break_still_verifies() -> None:
    """AUD-C-18: the six documents added for 2026-08-01 are hard-wrapped at ~84
    columns, so their chunk_text carries newlines mid-sentence. A model told to quote
    "verbatim" renders that line break as a space, and the raw substring check dropped
    every such citation - staging refused four of the six documents while the retrieval
    and rerank stages ranked them first. Whitespace differences must not fail a quote.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session,
                chunk_text=(
                    "When you arrive, your tutor checks you in for attendance. You then "
                    "take a short\npre-exam on the week's topic, work through a "
                    "personalized study set, and finish with\na post-exam covering the "
                    "same material."
                ),
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Sessions start with check-in, then a pre-exam.",
                        citations=[
                            LlmCitation(
                                context_index=0,
                                quote=(
                                    "You then take a short pre-exam on the week's topic, "
                                    "work through a personalized study set, and finish "
                                    "with a post-exam covering the same material."
                                ),
                            )
                        ],
                        confidence=0.9,
                    )
                )
            )

            answer, _cost = await qa.answer_question(
                repo,
                gateway,
                query="What does a session look like?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert len(answer.citations) == 1
            assert answer.citations[0].source_reference == chunk.document_id
            assert answer.escalation_recommended is False

    asyncio.run(run())


def test_whitespace_tolerance_does_not_admit_a_reordered_or_paraphrased_quote() -> None:
    """The AUD-C-18 fix is whitespace-insensitivity ONLY - a quote whose *words*
    differ from the chunk (paraphrase, reordering, substitution) must still be dropped,
    or the verification stops being a verification.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session,
                chunk_text="Attendance is required for every\non-site session.",
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is needed.",
                        citations=[
                            LlmCitation(
                                context_index=0,
                                quote="Every on-site session requires attendance.",
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

    asyncio.run(run())


# --- AUD-C-13: the verbatim check's floor was one character -------------------------
#
# `quote in chunk_text` is a real defense, and its floor was `"a"`. Measured over the 144
# approved chunks with `scripts/measure_citation_quote_floor.py`: a 1-character span occurs
# in a **median of 140 of them** (0% unique), 2 chars in 74, 4 chars in 10. By 20 chars the
# median is 1 and the p90 is 2, which is where the curve flattens - 24 and 32 chars buy
# nothing more. So the floor below is the measured knee, not a round number someone liked.


def test_a_one_character_quote_no_longer_verifies() -> None:
    """The finding's own example. "a" is a real substring of this chunk, so the verbatim
    check passed it and shipped a citation that identified nothing - the same "a" verifies
    against 140 of the corpus's 144 approved chunks.
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
                        answer="Attendance is required.",
                        citations=[LlmCitation(context_index=0, quote="a")],
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

            # Nothing survives, so the turn fails closed the same way a fabricated quote
            # does - SPEC §5.21.8's "citations do not support the response".
            assert answer.citations == []
            assert answer.answer == qa.NO_SOURCE_MESSAGE

    asyncio.run(run())


def test_the_quote_floor_is_measured_at_its_own_boundary() -> None:
    """One character either side of `MIN_CITATION_QUOTE_CHARS`, so the constant is what
    decides rather than the shape of the test's sentence.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk_text = "Attendance is required for every on-site session, without exception."
            just_under = chunk_text[: qa.MIN_CITATION_QUOTE_CHARS - 1]
            exactly_at = chunk_text[: qa.MIN_CITATION_QUOTE_CHARS]

            for quote, expected_citations in ((just_under, 0), (exactly_at, 1)):
                chunk = await _seed_chunk(session, chunk_text=chunk_text)
                gateway = _FakeGateway(
                    _result(
                        RagAnswerResponse(
                            answer="Attendance is required.",
                            citations=[LlmCitation(context_index=0, quote=quote)],
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

                assert len(answer.citations) == expected_citations, (
                    f"{quote!r} ({len(quote)} chars) should have produced "
                    f"{expected_citations} citations"
                )

    asyncio.run(run())


def test_the_floor_is_applied_to_the_normalized_quote() -> None:
    """Length is measured after the AUD-C-18 whitespace collapse, i.e. on the same string
    the containment check uses. Padding a short quote with newlines is not a longer quote.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance\n\n   is    required for every session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is required.",
                        citations=[LlmCitation(context_index=0, quote="  Attendance  \n\n  ")],
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

    asyncio.run(run())


def test_a_quote_dropped_for_being_too_short_says_so_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-171 §2 applied forward: a floor whose effect is invisible cannot be told apart
    from one that never fires. Dropping for shortness and dropping for a fabricated quote
    are different events - the first is a model that under-quotes and may be fixable in the
    prompt, the second is a model that made something up.
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
                        answer="Attendance is required.",
                        citations=[LlmCitation(context_index=0, quote="required")],
                        confidence=0.9,
                    )
                )
            )

            with caplog.at_level(logging.WARNING, logger="chat_api.services.qa"):
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
            records = [r for r in caplog.records if r.message == "citation_quote_below_floor"]
            assert len(records) == 1
            assert records[0].dropped == 1  # type: ignore[attr-defined]
            # The quote itself is never logged: chunk text is org content, and a log line is
            # the one place this pipeline has no PII floor applied to it.
            assert "required" not in records[0].getMessage()

    asyncio.run(run())


def test_the_model_is_told_what_a_quote_has_to_be() -> None:
    """The floor is only fail-closed if the model was told about it: an unannounced
    requirement turns into refusals the user sees (the D-155/AUD-C-08 class). Asserted
    against the real system prompt rather than a copy of it.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            captured: dict[str, str] = {}

            class _PromptCapturingGateway(_FakeGateway):
                async def generate_structured(self, *, system_prompt: str, **kwargs):  # type: ignore[override]
                    captured["system_prompt"] = system_prompt
                    return await super().generate_structured(system_prompt=system_prompt, **kwargs)

            gateway = _PromptCapturingGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is required for every on-site session.",
                        citations=[
                            LlmCitation(
                                context_index=0,
                                quote="Attendance is required for every on-site session.",
                            )
                        ],
                        confidence=0.9,
                    )
                )
            )

            await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert str(qa.MIN_CITATION_QUOTE_CHARS) in captured["system_prompt"]

    asyncio.run(run())


def test_the_quote_floor_excludes_only_heading_chunks() -> None:
    """The floor's cost, as a check rather than a claim in a doc.

    A flat floor means any chunk shorter than it can never be cited at all - and refusing an
    answer the corpus does contain is AUD-C-08's defect. Measured when the floor was chosen:
    of the 144 approved chunks, the five under 20 normalized characters are all bare markdown
    headings ("# our team", "## administration"), which support no answer, so nothing citable
    was lost. That is a fact about *today's* corpus, not a property of the rule, so it is
    asserted here: a future document with a genuinely short standalone fact fails this test
    instead of silently becoming unquotable.

    Reads the real ingested corpus (CI loads it before pytest - `ingest_cli`), which is also
    the control: with an empty corpus this would pass while checking nothing.
    """

    async def run() -> None:
        async with rollback_session() as session:
            rows = await session.execute(
                text("SELECT chunk_text FROM rag_chunks WHERE status = 'approved'")
            )
            chunks = [row[0] for row in rows]
            assert len(chunks) > 100, (
                "the approved corpus looks unloaded, so this test would assert nothing - "
                "run `make knowledge-load`"
            )

            too_short = [
                chunk
                for chunk in chunks
                if len(qa._normalized_for_containment(chunk)) < qa.MIN_CITATION_QUOTE_CHARS
            ]
            not_a_heading = [chunk for chunk in too_short if not chunk.lstrip().startswith("#")]
            assert not not_a_heading, (
                "an approved chunk shorter than the citation floor is not a markdown heading, "
                f"so it can no longer be cited at all: {not_a_heading}"
            )

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
                                context_index=0,
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
                                context_index=0,
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
            # The negative control for AUD-C-11 below: this refusal *does* keep its
            # citations, deliberately. "The documents I found disagree with each other"
            # is a claim about specific documents and naming them is the point.
            assert [citation.source_reference for citation in answer.citations] == [
                chunk.document_id
            ]

    asyncio.run(run())


def test_the_no_source_refusal_carries_no_citations() -> None:
    """AUD-C-11 (D-164). Observed live: this branch returned "I don't have an approved
    source for that yet" together with `citations: ["public-organization-overview"]`, and
    chat-web rendered a citation chip under a sentence denying a source existed.

    The low-confidence arm is the one that was wrong. The `not verified` arm reaches the
    same `_no_answer` call with an empty list already, so the defect was invisible there -
    which is why the citation below verifies cleanly and only `confidence` is under the
    threshold. Pairs with the conflict test above, which is the arm that keeps them.
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
                        answer="Probably attendance is required, not fully sure.",
                        citations=[
                            LlmCitation(
                                context_index=0,
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

            assert answer.answer == qa.NO_SOURCE_MESSAGE
            assert answer.citations == []
            assert answer.confidence == 0.0
            assert answer.escalation_recommended is True

    asyncio.run(run())


def test_answer_question_reports_a_synthesis_outage_as_an_outage() -> None:
    """AUD-C-19 (D-156): the chunk below was retrieved and *does* answer the question -
    only the model that would have quoted it was unavailable. Saying "no approved source"
    here is a false statement about the corpus, which is AUD-C-08's defect at the one call
    site D-155 left alone. This test asserted the old wording until now; it was rewritten
    to assert the fix and watched failing against the unfixed code first.
    """

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

            assert answer.answer == qa.SERVICE_UNAVAILABLE_MESSAGE
            assert answer.answer != qa.NO_SOURCE_MESSAGE
            # D-156: retry, not hand-off. Escalation during an outage sends the user into
            # a second Bedrock-and-MCP failure and bills a branch manager for a question
            # the corpus can already answer.
            assert answer.escalation_recommended is False
            # Nothing is *missing*; the lookup failed. `service_unavailable` says None for
            # the same reason.
            assert answer.missing_information is None
            assert answer.citations == []
            # Fail-closed is unchanged: an outage never yields a confident answer, and the
            # cost of the failed call is still accounted for.
            assert answer.confidence == 0.0
            assert cost == 0.2

    asyncio.run(run())


# --- AUD-X-12 (D-115): the answer budget, and what a truncated answer looks like -----
#
# Measured on staging over 70 real grounded turns at top_k=8: output tokens p50 662,
# **p95 1490, max 1530** against the then-fixed cap of 1536. So ~1 turn in 30 truncated,
# and a truncated `RagAnswerResponse` is not a slow answer - it is indistinguishable, from
# inside `answer_question`, from "no source supports an answer". The student was told there
# was no approved source for a question that had one.
_MEASURED_MAX_ANSWER_TOKENS = 1530
# The cap this replaced. It is a *lower bound* on any derived cap, at every passage count -
# see `test_the_answer_token_budget_never_dips_below_the_flat_cap_it_replaced`.
_PREVIOUS_FLAT_CAP = 1536
_TOP_K = 8


def test_the_answer_token_budget_clears_the_measured_maximum_at_top_k() -> None:
    budget = RagAnswerResponse.max_output_tokens_for(_TOP_K)
    assert budget > _MEASURED_MAX_ANSWER_TOKENS * 1.4
    # ...and still inside the gateway's own hard ceiling, or the derivation is a fiction.
    assert budget <= 4000


def test_the_answer_token_budget_never_dips_below_the_flat_cap_it_replaced() -> None:
    """The regression this pins actually shipped (D-115 §10).

    The first derivation was `768 + 192n`, by analogy with the reranker - where the
    response really is one line per candidate. An answer's length is a function of the
    *question*; only its citation list scales with the passages. So single-passage turns
    got a 960-token ceiling, **below the flat 1536 being replaced**, and staging truncated
    3 of 74 turns, every one of them `context_chunk_count=1`. Any passage count must clear
    the old cap, or "derived" is a euphemism for "sometimes smaller".
    """
    for passages in range(1, 31):
        assert RagAnswerResponse.max_output_tokens_for(passages) > _PREVIOUS_FLAT_CAP


def test_the_answer_token_budget_scales_with_the_number_of_passages() -> None:
    assert RagAnswerResponse.max_output_tokens_for(8) > RagAnswerResponse.max_output_tokens_for(3)


def test_answer_question_derives_its_budget_and_sends_no_chunk_ids() -> None:
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
                                context_index=0,
                                quote="Attendance is required for every on-site session.",
                            )
                        ],
                        confidence=0.9,
                    )
                )
            )

            await qa.answer_question(
                repo,
                gateway,
                query="Is attendance required?",
                user_role="parent",
                chunks=[chunk],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            assert gateway.max_output_tokens == RagAnswerResponse.max_output_tokens_for(1)
            # The model is asked about passage positions, never identifiers: a UUID it has
            # to echo back is output tokens it cannot spare and a character it can garble
            # into an unmatchable - i.e. refused - citation.
            assert gateway.payload is not None
            assert chunk.chunk_id not in gateway.payload.model_dump_json()

    asyncio.run(run())


def test_a_citation_pointing_at_a_passage_that_was_not_sent_is_dropped() -> None:
    """Index-keying does not weaken verification: an out-of-range index is discarded the
    same way an unknown chunk id was, and with nothing else surviving the turn becomes a
    no-answer response.
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
                        answer="Attendance is required for every on-site session.",
                        citations=[
                            LlmCitation(
                                context_index=99,
                                quote="Attendance is required for every on-site session.",
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
            assert answer.answer == qa.NO_SOURCE_MESSAGE

    asyncio.run(run())


def test_a_citation_resolves_to_the_passage_at_its_own_position() -> None:
    """With several passages in play, index 1 must verify against the *second* chunk's
    text - the round-trip that used to be carried by the chunk id.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            first = await _seed_chunk(session, chunk_text="Branches open at 9am on weekdays.")
            second = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                _result(
                    RagAnswerResponse(
                        answer="Attendance is required.",
                        citations=[
                            LlmCitation(
                                context_index=1,
                                quote="Attendance is required for every on-site session.",
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
                chunks=[first, second],
                session_spend_cents=0.0,
                confidence_threshold=0.4,
            )

            # Verified against the second chunk, not the first: had the mapping been off
            # by one, this quote would not be a substring of `first` and would be dropped.
            assert len(answer.citations) == 1
            assert answer.citations[0].source_reference == second.document_id

    asyncio.run(run())


def test_a_synthesis_failure_says_why_it_became_an_outage_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D-115's point, narrowed by D-156. The *user-visible* half is now distinguishable -
    a synthesis failure says "temporarily unavailable" rather than borrowing the
    no-source refusal (AUD-C-19). What the message still cannot say is *which* failure it
    was, and it should not: truncation, timeout and throttling are all "try again" to a
    student. So the log line remains the only thing carrying the reason and the cost, and
    that is exactly the ambiguity D-115 spent a week paying for.
    """

    async def run() -> None:
        async with rollback_session() as session:
            repo = RagRepository(session)
            chunk = await _seed_chunk(
                session, chunk_text="Attendance is required for every on-site session."
            )
            gateway = _FakeGateway(
                BedrockGatewayError("model hit max_output_tokens=1536", cost_cents=0.4)
            )

            with caplog.at_level(logging.WARNING, logger="chat_api.services.qa"):
                answer, _cost = await qa.answer_question(
                    repo,
                    gateway,
                    query="Is attendance required?",
                    user_role="parent",
                    chunks=[chunk],
                    session_spend_cents=0.0,
                    confidence_threshold=0.4,
                )

            assert answer.answer == qa.SERVICE_UNAVAILABLE_MESSAGE
            records = [r for r in caplog.records if r.message == "rag_answer_unavailable"]
            assert len(records) == 1
            assert records[0].context_chunk_count == 1  # type: ignore[attr-defined]
            assert "max_output_tokens" in records[0].detail  # type: ignore[attr-defined]

    asyncio.run(run())
