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

import pytest
from intellichoice_evals.qa_coverage import assert_categories_present, format_report, score

from .conftest import postgres_skip_reason, rollback_session
from .qa_coverage_runner import run_all

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
