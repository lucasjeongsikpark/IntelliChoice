"""The same Q&A coverage eval as `test_qa_coverage_eval.py`, run against **real Bedrock**.

Opt-in and never part of `make test` or CI: it costs money and needs live AWS
credentials. Run it deliberately:

    eval "$(aws configure export-credentials --profile <profile> --format env)"
    AWS_REGION=us-east-1 CHAT_EVAL_REAL_BEDROCK=1 \
      .venv/bin/python -m pytest apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py -s

**`AWS_PROFILE=...` does not work here** (D-164), which cost this file's first real user some
time: both of this project's profiles use a `login_session`, and resolving one requires
`botocore[crt]`, which the project venv does not install - so every call fails
`MissingDependencyException` even with a valid `aws` CLI session. The `export-credentials`
form above hands boto3 plain session credentials it can always resolve. Add
`CHAT_EVAL_CATEGORIES=<category>[,<category>]` to narrow the run to named categories when
re-measuring one finding (see `_CATEGORIES` below).

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
     silently, because a partial run scored as if complete is a wrong measurement. Set
     `CHAT_EVAL_RUN_BUDGET_CENTS=<n>` to tighten it to whatever figure the run's spend was
     approved at; it cannot loosen it above the default;
  3. the fixture is a fixed, version-controlled case list - not a generator.
Measured cost of one full run: **76.7 cents / 13m17s** at S37 (docs/AUDIT_FINDINGS.md).

**This run does not see every fixture case (AUD-C-21/D-166).** `load_cases` is called with
`include_mock_only=False`, which drops the five nonsense-marker `role_gated` cases - a real
scope guard refuses "zqxveval2 handbook" as out_of_scope before retrieval, so under a real
model they measure the marker design and not the feature. That is also why the assertion at
the bottom is no longer `role_gated >= 0.95`: with those five cases in, no full real-model run
could ever have passed it. The count here is therefore lower than the mock run's, by design.
"""

import asyncio
import os

import pytest
from intellichoice_evals.qa_coverage import (
    assert_categories_present,
    format_report,
    score,
    wrong_role_hints,
)

from .conftest import postgres_skip_reason, rollback_session
from .qa_coverage_runner import (
    ask,
    effective_public_document_ids,
    load_cases,
    reembed_corpus,
    seed_chunk,
    to_outcome,
)

PER_CASE_BUDGET_CENTS = 15.0
# 400 is the standing headroom, not an estimate: one full run measured **76.7 cents** at S37
# (see docs/AUDIT_FINDINGS.md). `CHAT_EVAL_RUN_BUDGET_CENTS` lowers it for a run whose spend
# was approved at a specific figure, so the approved number is *enforced* by the same hard
# stop rather than checked by hand afterwards - D-178 ran the first full post-AUD-C-23 eval
# at 150. It can only tighten the ceiling: a value above the default is ignored, because a
# run must not be able to raise its own spend limit from the environment.
RUN_BUDGET_CENTS = min(float(os.getenv("CHAT_EVAL_RUN_BUDGET_CENTS") or 400.0), 400.0)

_ENABLED = os.getenv("CHAT_EVAL_REAL_BEDROCK") == "1"

# AUD-C-06/D-164: a change to one routing decision needs the three `role_gated_question`
# cases re-measured, not all 61 - so a run can be narrowed to named categories:
#
#     CHAT_EVAL_CATEGORIES=role_gated_question CHAT_EVAL_REAL_BEDROCK=1 \
#       AWS_PROFILE=... .venv/bin/python -m pytest <this file> -s
#
# A narrowed run is a **partial measurement** and says so loudly, because the exact
# failure this file's own docstring warns about is a partial run scored as if it were
# complete. The category-presence check and both invariant assertions at the bottom cover
# categories a filtered run may not have executed, so they are skipped rather than
# evaluated against absent data. Unset (the default) is the full run with every assertion
# live - narrowing is for iterating on a known finding, never for reporting coverage.
_CATEGORIES = tuple(
    c.strip() for c in os.getenv("CHAT_EVAL_CATEGORIES", "").split(",") if c.strip()
)

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
            # Same AUD-C-17 vacuity guard as `run_all` - this loop is a copy of it with
            # budget accounting added, so it owes the same precondition.
            public_document_ids = await effective_public_document_ids(session)
            assert public_document_ids, (
                "no public document is approved and effective right now - the eval "
                "would pass over an empty corpus and mean nothing (AUD-C-17)"
            )
            cases = [
                case
                for case in load_cases(include_mock_only=False)
                if not _CATEGORIES or case["category"] in _CATEGORIES
            ]
            # Same vacuity rule as the public-corpus guard above (AUD-C-17): a filter that
            # matches nothing would otherwise produce a green run over zero cases.
            assert cases, f"no case matches CHAT_EVAL_CATEGORIES={_CATEGORIES}"
            for case in cases:
                for key in ("seed", "extra_seed"):
                    if key in case:
                        await seed_chunk(session, gateway, **case[key])
                result = await ask(
                    session, gateway, query=case["query"], thread_id=f"realeval-{case['id']}"
                )
                spent += float(result.get("bedrock_spend_cents") or 0.0)
                outcomes.append(to_outcome(case, result, public_document_ids))
                if spent > RUN_BUDGET_CENTS:
                    raise RunBudgetExceeded(
                        f"run budget of {RUN_BUDGET_CENTS} cents exceeded after "
                        f"{len(outcomes)} cases ({spent:.1f} cents) - aborting rather than "
                        "reporting a partial run as a measurement"
                    )
        return outcomes

    outcomes = asyncio.run(run())
    scores = score(outcomes)

    with capsys.disabled():
        print(f"\n--- qa coverage eval (REAL Bedrock, {spent:.1f} cents) ---")
        print(format_report(scores))
        if _CATEGORIES:
            print(
                f"\n*** PARTIAL RUN - filtered to {', '.join(_CATEGORIES)}. This is not a "
                "coverage measurement, and the containment/coverage invariants below "
                "were NOT asserted. Re-run without CHAT_EVAL_CATEGORIES for those. ***"
            )

    # AUD-C-21/D-166 replaced `role_gated >= 0.95` here, and the swap is a correction rather
    # than a relaxation. That assertion could not pass a full real-model run at all (its five
    # cases are the nonsense markers `load_cases` now drops), and a rate is the wrong
    # instrument anyway: it counts a silent probe - safe, and the pre-D-165 behaviour - as
    # identical to one that names the wrong tier. The property that must hold is that no hint
    # ever points a caller at a role the case did not expect, on ANY category. Recall stays in
    # `format_report` above, where a number that moves with the model belongs.
    #
    # **Asserted before the partial-run return, unlike every other check here**, because it is
    # the one invariant that means the same thing on a subset: it needs no particular category
    # to be present and cannot be satisfied vacuously by a filter that excluded the risky
    # cases. That also makes `CHAT_EVAL_CATEGORIES=no_answer` a real safety check on the
    # distance ceiling for cents - which is how D-166's 0.45 was verified.
    assert (wrong := wrong_role_hints(outcomes)) == [], f"access hint named the wrong role: {wrong}"

    if _CATEGORIES:
        return

    # `role_gated` is deliberately absent: `load_cases(include_mock_only=False)` drops its
    # five nonsense-marker cases, so requiring the category present would fail every run.
    # `role_gated_question` replaces it - the same feature, asked the way a person asks it.
    assert_categories_present(
        scores, ["grounded", "paraphrase", "role_gated_question", "out_of_scope", "no_source",
                 "no_answer", "adversarial"]
    )
    # Only the architectural invariants are asserted. Every quality number is *reported*:
    # this run exists to measure retrieval, and a threshold invented before the first
    # measurement would be a guess dressed as a gate. S37 recorded the first numbers in
    # docs/AUDIT_FINDINGS.md; a future session can turn them into thresholds with evidence.
    assert scores["adversarial"].rate == 1.0, f"containment broke: {scores['adversarial'].failed}"
