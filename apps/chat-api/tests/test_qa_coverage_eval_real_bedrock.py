"""The same Q&A coverage eval as `test_qa_coverage_eval.py`, run against **real Bedrock**.

Opt-in and never part of `make test` or CI: it costs money and needs live AWS
credentials. Run it deliberately, e.g.

    AWS_PROFILE=intellichoice-staging CHAT_EVAL_REAL_BEDROCK=1 \
      .venv/bin/python -m pytest apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py -s

Why it exists (S37/AUD-C). The mock-backed run cannot measure retrieval quality, because
the thing it would be measuring is `MockBedrockProvider`: its reranker scores literal
query/chunk word overlap and its answer synthesiser always answers from the first context
chunk with a fixed confidence of 0.8. Under that provider the `no_answer` category scores
0/8 - every plausible-but-unanswerable question is answered from an unrelated document
with a verified citation - and no amount of tuning the *pipeline* would change it. Only a
real model can tell you whether the pipeline refuses when it should, so the two named
metrics (grounded-citation rate, correct-refusal rate) are only meaningful here.

**Cost control** (CLAUDE.md: anything that calls a paid API needs a spend limit). Three
independent ceilings, smallest first:
  1. `PER_CASE_BUDGET_CENTS` - the gateway's own per-session budget, so one runaway case
     cannot spend the run's whole allowance;
  2. `RUN_BUDGET_CENTS` - a hard stop across the whole run, checked after every case by
     summing each turn's own `bedrock_spend_cents`; the run aborts rather than truncating
     silently, because a partial run scored as if complete is a wrong measurement;
  3. the fixture is a fixed, version-controlled 61 cases - not a generator.
Measured cost of one full run at S37: see docs/AUDIT_FINDINGS.md.
"""

import asyncio
import os

import pytest
from intellichoice_evals.qa_coverage import assert_categories_present, format_report, score

from .conftest import postgres_skip_reason, rollback_session
from .qa_coverage_runner import ask, load_cases, reembed_corpus, seed_chunk, to_outcome

PER_CASE_BUDGET_CENTS = 15.0
RUN_BUDGET_CENTS = 400.0

_ENABLED = os.getenv("CHAT_EVAL_REAL_BEDROCK") == "1"

pytestmark = [
    pytest.mark.skipif(not _ENABLED, reason="set CHAT_EVAL_REAL_BEDROCK=1 (costs money)"),
    pytest.mark.skipif((_r := postgres_skip_reason()) is not None, reason=_r or ""),
]


class RunBudgetExceeded(RuntimeError):
    pass


def _gateway():
    from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
    from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
    from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
    from intellichoice_shared.bedrock import BedrockTask

    region = os.getenv("CHAT_EVAL_AWS_REGION", "us-east-1")
    model = os.getenv("CHAT_EVAL_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
    embedding_model = os.getenv("CHAT_EVAL_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        embedding_provider=TitanEmbeddingProvider(aws_region=region),
        model_registry={
            BedrockTask.SCOPE_AND_INTENT: model,
            BedrockTask.RERANK: model,
            BedrockTask.RAG_ANSWER: model,
            BedrockTask.CALENDAR_EXTRACTION: model,
            BedrockTask.EMBEDDING: embedding_model,
        },
        session_budget_cents=PER_CASE_BUDGET_CENTS,
    )


def test_qa_coverage_eval_against_real_bedrock(capsys: pytest.CaptureFixture[str]) -> None:
    spent = 0.0

    async def run():
        nonlocal spent
        outcomes = []
        gateway = _gateway()
        async with rollback_session() as session:
            n = await reembed_corpus(session, gateway)
            print(f"re-embedded {n} approved chunks with the real embedding model")
            for case in load_cases():
                for key in ("seed", "extra_seed"):
                    if key in case:
                        await seed_chunk(session, gateway, **case[key])
                result = await ask(
                    session, gateway, query=case["query"], thread_id=f"realeval-{case['id']}"
                )
                spent += float(result.get("bedrock_spend_cents") or 0.0)
                outcomes.append(to_outcome(case, result))
                if spent > RUN_BUDGET_CENTS:
                    raise RunBudgetExceeded(
                        f"run budget of {RUN_BUDGET_CENTS} cents exceeded after "
                        f"{len(outcomes)} cases ({spent:.1f} cents) - aborting rather than "
                        "reporting a partial run as a measurement"
                    )
        return outcomes

    scores = score(asyncio.run(run()))

    with capsys.disabled():
        print(f"\n--- qa coverage eval (REAL Bedrock, {spent:.1f} cents) ---")
        print(format_report(scores))

    assert_categories_present(
        scores, ["grounded", "paraphrase", "role_gated", "out_of_scope", "no_source",
                 "no_answer", "adversarial"]
    )
    # Only the architectural invariants are asserted. Every quality number is *reported*:
    # this run exists to measure retrieval, and a threshold invented before the first
    # measurement would be a guess dressed as a gate. S37 recorded the first numbers in
    # docs/AUDIT_FINDINGS.md; a future session can turn them into thresholds with evidence.
    assert scores["adversarial"].rate == 1.0, f"containment broke: {scores['adversarial'].failed}"
    assert scores["role_gated"].rate >= 0.95, f"role-gated refusals: {scores['role_gated'].failed}"
