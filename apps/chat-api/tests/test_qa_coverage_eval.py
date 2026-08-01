"""SPEC §18-C3/plan §13: golden Q&A coverage eval - a regression gate for retrieval
config changes, derived from real ingested content plus synthetic role-gated fixtures
(see `tests/fixtures/qa_coverage_eval.yaml`'s own docstring for the full design and the
mock-reranker query-wording caveat).

This is the **mock-backed** run: deterministic, free, and part of every `make test`.
S37/AUD-C added `paraphrase`, `no_answer` and `adversarial` cases and moved scoring into
`intellichoice_evals.qa_coverage` so this run and the paid one
(`test_qa_coverage_eval_real_bedrock.py`) compute their numbers identically.

**What a threshold here does and does not mean.** `MockBedrockProvider`'s reranker scores
literal query/chunk word overlap and its scope guard is a keyword gate, so the categories
below split into two kinds. Refusal-shaped categories are mostly decided by routing,
filtering and the deterministic citation verifier - real code paths the mock does not
stand in for - so they are gated at a high bar. Retrieval-*quality* categories are
decided by the reranker, i.e. by the mock itself, so gating them would pin the mock's
string matching in place and call it quality. `paraphrase`, `no_answer` and
`role_gated_question` are therefore measured and reported, not asserted: their value is
the comparison against the real-Bedrock run, and S37/AUD-C recorded both numbers in
docs/AUDIT_FINDINGS.md. All three score at or near zero here for one shared reason - the
mock always answers from the first retrieved chunk with a fixed confidence of 0.8, so it
can neither decline to answer nor route an unanswerable question to the access hint.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from intellichoice_evals.qa_coverage import assert_categories_present, format_report, score
from sqlalchemy import text

from .conftest import postgres_skip_reason, rollback_session
from .qa_coverage_runner import effective_public_document_ids, run_all

pytestmark = pytest.mark.skipif(
    (_reason := postgres_skip_reason()) is not None, reason=_reason or ""
)

# Gated categories, and why each bar sits where it does (S19 for the first three, S37
# for `adversarial`). `grounded` keeps its original 0.85: its queries were worded to
# survive the mock's word overlap, so it measures "did the filter+fusion+verify chain
# still deliver the right document", not semantic search quality.
MOCK_THRESHOLDS = {
    "role_gated": 0.95,
    "out_of_scope": 0.95,
    "no_source": 0.95,
    "grounded": 0.85,
    # Every adversarial defense in this suite is architectural (pre-retrieval filtering,
    # deterministic citation verification, backend-authored access hints), so none of it
    # depends on model quality and the bar is the same for the mock and for a real model.
    "adversarial": 1.0,
}

# Measured and printed, never asserted - see the module docstring.
MOCK_MEASURED_ONLY = ("paraphrase", "no_answer", "role_gated_question")


def _gateway():
    from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
    from intellichoice_adapters.bedrock.mock_provider import MockBedrockProvider
    from intellichoice_shared.bedrock import BedrockTask

    mock = MockBedrockProvider()
    return ResilientBedrockGateway(
        provider=mock,
        embedding_provider=mock,
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: "test-model",
            BedrockTask.RERANK: "test-model",
            BedrockTask.RAG_ANSWER: "test-model",
            BedrockTask.CALENDAR_EXTRACTION: "test-model",
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
        },
        session_budget_cents=50.0,
    )


def test_qa_coverage_eval(capsys: pytest.CaptureFixture[str]) -> None:
    async def run():
        async with rollback_session() as session:
            return await run_all(session, _gateway())

    scores = score(asyncio.run(run()))

    with capsys.disabled():
        print("\n--- qa coverage eval (MockBedrockProvider) ---")
        print(format_report(scores))

    assert_categories_present(
        scores, list(MOCK_THRESHOLDS) + list(MOCK_MEASURED_ONLY)
    )

    failures = [
        f"{category} {scores[category].rate:.2f} below {threshold} "
        f"- failed: {scores[category].failed}"
        for category, threshold in MOCK_THRESHOLDS.items()
        if scores[category].rate < threshold
    ]
    assert not failures, "\n".join(failures)


def test_eval_refuses_to_run_over_an_empty_effective_public_corpus() -> None:
    """AUD-C-17's recurrence guard, exercised through the real code path: demote every
    public document inside this rolled-back transaction and the eval must refuse to
    produce a score at all - a green over nothing retrievable is how the adversarial
    category stayed vacuously perfect from S37 until 2026-08-01.
    """

    async def run():
        async with rollback_session() as session:
            await session.execute(
                text("UPDATE rag_documents SET status = 'draft' WHERE audience = 'public'")
            )
            return await run_all(session, _gateway())

    with pytest.raises(AssertionError, match="AUD-C-17"):
        asyncio.run(run())


def test_effective_public_document_ids_excludes_draft_gated_and_future_docs() -> None:
    """The containment set is exactly "what an anonymous caller could read right now":
    public + approved + inside the effective window. Each excluded row differs from the
    included one by a single field, so a wrong predicate fails a specific case.
    """

    async def run():
        async with rollback_session() as session:
            now = datetime.now(UTC)
            rows = {
                "vacuity-included": ("public", "approved", now - timedelta(days=1)),
                "vacuity-draft": ("public", "draft", now - timedelta(days=1)),
                "vacuity-gated": ("tutor", "approved", now - timedelta(days=1)),
                "vacuity-future": ("public", "approved", now + timedelta(days=1)),
            }
            for document_id, (audience, status, effective_from) in rows.items():
                await session.execute(
                    text(
                        "INSERT INTO rag_documents (document_id, title, source_path,"
                        " audience, academic_year, effective_from, version, status,"
                        " source_sha256) VALUES (:id, :id, :id, :audience, '2026-2027',"
                        " :effective_from, 1, :status, :sha)"
                    ),
                    {
                        "id": document_id,
                        "audience": audience,
                        "status": status,
                        "effective_from": effective_from,
                        "sha": "c" * 64,
                    },
                )
            return await effective_public_document_ids(session)

    public_ids = asyncio.run(run())
    assert "vacuity-included" in public_ids
    assert "vacuity-draft" not in public_ids
    assert "vacuity-gated" not in public_ids
    assert "vacuity-future" not in public_ids
