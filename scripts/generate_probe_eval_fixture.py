"""Generate a corpus-derived fixture for SPEC §18-C3's access probe (AUD-C-20, AUD-C-21).

Two modes. The first builds the fixture from the corpus; the second adds a **human-phrasing**
variant to an existing fixture without regenerating it:

    # AUD-C-20: chunk -> question, one call per chunk
    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/generate_probe_eval_fixture.py \
        --out apps/chat-api/tests/fixtures/probe_eval.yaml

    # AUD-C-21: add `human_query` to the cases already in that file, in place
    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/generate_probe_eval_fixture.py \
        --from-fixture apps/chat-api/tests/fixtures/probe_eval.yaml

**Why the existing fixture could not answer the question it was being asked.**
`qa_coverage_eval.yaml` has eight role-gated cases, and its negative set silently mixes two
different situations: questions a *public* document answers (the probe must stay silent) and
questions *nothing* answers (the probe must also stay silent, but for an unrelated reason).
AUD-C-20's one false hint came from the second class - the probe was being scored on a
question that was never well-posed, because no document in the corpus addresses it.

Worse, the three realistic gated cases were hand-written *beside* the chunk they target, so
they shared 5/6, 5/7 and 4/6 content words with it. Any keyword rule looks good against a
question written by whoever wrote the answer. Real users do not do that.

**So this generates each question FROM a real chunk, under an explicit instruction not to
reuse the chunk's distinctive vocabulary, and then MEASURES the resulting lexical overlap
and writes it into the fixture.** That measured `lexical_overlap` is the control: a fixture
whose questions turn out to echo their chunks is measuring its own paraphrase (ROADMAP.md's
S30 correction, and D-163's `MockBedrockProvider` trap in a new costume), and with the number
recorded per case anyone can check rather than trust.

**AUD-C-21: asking a model not to copy the passage is weaker than not showing it the passage.**
D-165 shipped a semantic ceiling of 0.40 chosen against the questions this file's first mode
produces, and the live check found it too tight: the fixture's own parent-attendance question
sits at 0.418 from the chunk that answers it, while a human wording of the same question sits
at ~0.60. The instruction in `_SYSTEM_PROMPT` reduces lexical echo but cannot remove the
*semantic* pull of a passage the generator is looking at while it writes.

`--from-fixture` closes that gap structurally rather than by asking harder. It runs two more
passes per case:

  1. **A blind rewrite.** Input is the generated question and nothing else - the rewriter
     never sees the passage, so it cannot borrow from it, by construction rather than by
     instruction. Output lands in `human_query`.
  2. **An answerability check.** Passage + rewrite -> does this passage still answer it? A
     rewrite that drifts into a *different* question would silently reclassify the case into
     the "nothing answers it" class and corrupt the negative measurement, which is the one
     way this instrument could flatter a wider threshold. Failures are dropped and counted,
     never kept.

It edits the file in place and leaves `query` untouched, so the two question sets are scored
over the same cases and the same chunks: the delta is attributable to phrasing alone, not to
regeneration noise. `scripts/measure_access_probe_rules.py --query-field human_query` is the
consumer.

Cost: one small generation per chunk (or two per case under `--from-fixture`), bounded by
`--limit-per-audience`, the gateway's own `session_budget_cents`, and a 300-token output cap.
At the deployed model's rate either run is a few cents. Read-only against the database.
"""

import argparse
import asyncio
import os
import re
import sys

import yaml
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_shared.bedrock import BedrockTask
from pydantic import BaseModel, Field
from sqlalchemy import text

_MAX_OUTPUT_TOKENS = 300

# The generator's whole value is in this instruction. "Do not reuse distinctive words" is
# what stops the fixture from being a paraphrase of its own answer; asking for how a real
# person would phrase it is what makes the divergence realistic rather than adversarial.
_SYSTEM_PROMPT = (
    "You write evaluation questions for a school organization's help assistant.\n"
    "Given one passage from an internal document, write the ONE question a real person "
    "would type that this passage answers.\n\n"
    "Hard rules:\n"
    "1. The passage must genuinely answer your question. Do not ask something it only "
    "hints at.\n"
    "2. Do NOT reuse the passage's distinctive words. Use the words a person who has "
    "never read this document would use. If the passage says 'consecutive scheduled "
    "sessions', a parent would say 'classes in a row'.\n"
    "3. Write it as one natural question, at most 20 words. No preamble, no quotes.\n"
    "4. Never mention that you were shown a passage."
)


# AUD-C-21. The whole value of this prompt is what it does NOT contain: no passage. The
# rewriter cannot echo a document it was never shown, so lexical and semantic divergence
# come from the input, not from an instruction the model may or may not follow.
#
# **`asked_by` is here because the first version of this prompt cost 17 of 55 cases.** It
# said "rewrite it as a parent, student or tutor would ask it", which invited the model to
# pick a speaker - and it picked "parent" almost every time, turning a tutor's question about
# contacting families into a parent's question about contacting teachers. That is a different
# information need with a different right answer, so the answerability judge correctly threw
# those cases out, and the fixture would have lost every case whose audience was not parent.
# Naming the asker is not a leak: it is one metadata word, not the passage's vocabulary.
_REWRITE_PROMPT = (
    "You rewrite questions the way an ordinary person would actually type them into a "
    "school's help chat.\n\n"
    "You will be given one question written by staff, and who is asking it. Rewrite it in "
    "that person's own everyday words, as someone who has never read any internal document.\n\n"
    "Hard rules:\n"
    "1. Keep the information need EXACTLY the same. Someone who answers your version must "
    "have answered the original.\n"
    "2. Do NOT change who is asking or whose situation it is. A tutor asking about a student "
    "stays a tutor asking about a student - never turn it into a parent asking about their "
    "own child.\n"
    "3. Use everyday words. Replace institutional or policy vocabulary with what a person "
    "would say instead.\n"
    "4. Write it the way people really type: direct, sometimes slightly vague, at most 25 "
    "words. One question only.\n"
    "5. Do not add details that were not in the original question."
)

# The control on the rewrite. A drifted rewrite is not a harder test case, it is a case in
# the wrong class - so this judge decides membership, and its failures are dropped.
_ANSWERABLE_PROMPT = (
    "You check whether a passage answers a question.\n\n"
    "Answer true only if someone who read ONLY this passage could give a substantially "
    "complete answer to the question. Answer false if the passage merely mentions the "
    "topic, covers a different case, or answers a related but different question."
)


class _ChunkPayload(BaseModel):
    passage: str
    audience: str


class _GeneratedQuestion(BaseModel):
    question: str = Field(min_length=8, max_length=300)


class _QuestionPayload(BaseModel):
    question: str
    # Who the original question belongs to - see `_REWRITE_PROMPT`'s note. `public` cases
    # have no gated audience, so they are described as an ordinary visitor.
    asked_by: str


class _AnswerabilityPayload(BaseModel):
    passage: str
    question: str


class _Answerability(BaseModel):
    answerable: bool
    # No `max_length`, deliberately, and this cost a run to learn: a model cannot count
    # characters, so a length bound on a free-text field turns a perfectly good judgement
    # into a `StructuredOutputError` after the repair retry. The first attempt at this pass
    # bounded it at 300 and lost **19 of 55 cases** that way - all of them recorded as
    # "dropped", which read like evidence about the cases and was evidence about the schema.
    # Truncation belongs in the consumer, and is done where this is stored.
    reason: str


def _lexemes(sql_text: str) -> set[str]:
    """Cheap stand-in for `to_tsvector` stemming, used only to report overlap. Postgres does
    the real matching in the measurement script; this is a portable approximation good enough
    to flag a fixture that echoes its source.
    """
    words = re.findall(r"[a-z]{3,}", sql_text.lower())
    stop = {
        "the",
        "and",
        "for",
        "are",
        "you",
        "your",
        "with",
        "that",
        "this",
        "from",
        "can",
        "not",
        "any",
        "all",
        "has",
        "have",
        "was",
        "were",
        "will",
        "who",
        "how",
        "what",
        "when",
        "does",
        "did",
        "why",
        "our",
        "out",
        "get",
        "one",
        "own",
        "they",
        "their",
        "there",
        "them",
        "than",
        "then",
        "into",
        "each",
        "some",
        "may",
        "must",
        "should",
    }
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words if w not in stop}


_ASKED_BY = {
    "parent": "a parent of a student",
    "student": "a student",
    "tutor": "a tutor who works here",
    "branch_manager": "a branch manager who works here",
}


def _asked_by(case: dict) -> str:
    """The asker `_REWRITE_PROMPT` must preserve, from the case's own audience label."""
    return _ASKED_BY.get(case.get("expected_required_role") or "", "someone visiting the website")


def _gateway(region: str, model: str, budget_cents: float) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        embedding_provider=None,
        model_registry={BedrockTask.SCOPE_AND_INTENT: model},
        session_budget_cents=budget_cents,
    )


async def _add_human_phrasing(args: argparse.Namespace) -> int:
    """AUD-C-21: add a blind-rewrite `human_query` to every case in an existing fixture.

    Deliberately edits in place and leaves `query` alone. Regenerating the chunk-derived
    questions as well would confound the phrasing delta with the model's run-to-run
    variation, and the delta is the entire measurement.
    """
    gateway = _gateway(args.region, args.model, args.budget_cents)
    payload = yaml.safe_load(open(args.from_fixture).read())
    cases: list[dict] = payload["cases"]
    engine = create_engine()
    spent = 0.0
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            rows = (
                await session.execute(
                    text("SELECT chunk_id, chunk_text FROM rag_chunks WHERE status = 'approved'")
                )
            ).all()
    finally:
        await engine.dispose()
    chunk_text_by_id = {str(r.chunk_id): r.chunk_text for r in rows}

    # Three outcomes, and keeping them apart is the point. A case is *dropped* only when the
    # rewrite no longer asks what its source passage answers - that is a statement about the
    # case, and leaving it in would put it in the wrong class. A case is *unrewritten* when a
    # call failed, which says nothing about the case at all: it keeps its `query`, keeps its
    # place in the fixture, and a re-run fills it in (this pass is incremental - a case that
    # already carries a `human_query` is skipped and costs nothing).
    kept: list[dict] = []
    dropped: list[tuple[str, str]] = []
    unrewritten: list[tuple[str, str]] = []
    for case in cases:
        if case.get("human_query"):
            kept.append(case)
            continue
        source_text = chunk_text_by_id.get(str(case["source_chunk_id"]))
        if source_text is None:
            # The corpus moved under the fixture. Dropping is the only honest option: the
            # answerability check has nothing to judge against, so the case's class is
            # unknown, and an unknown-class case in a negative set is exactly the defect
            # this pass exists to prevent.
            dropped.append((case["id"], "source chunk no longer approved"))
            continue
        try:
            rewrite = await gateway.generate_structured(
                task=BedrockTask.SCOPE_AND_INTENT,
                system_prompt=_REWRITE_PROMPT,
                payload=_QuestionPayload(question=case["query"], asked_by=_asked_by(case)),
                response_model=_GeneratedQuestion,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
                session_spend_cents=spent,
            )
            spent += rewrite.cost_cents
            human_query = rewrite.value.question.strip()
            check = await gateway.generate_structured(
                task=BedrockTask.SCOPE_AND_INTENT,
                system_prompt=_ANSWERABLE_PROMPT,
                payload=_AnswerabilityPayload(passage=source_text, question=human_query),
                response_model=_Answerability,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
                session_spend_cents=spent,
            )
            spent += check.cost_cents
        except Exception as exc:  # infrastructure, not evidence - keep the case
            unrewritten.append((case["id"], f"{type(exc).__name__}: {exc}"[:200]))
            kept.append(case)
            print(f"  FAIL {case['id']:<26} {type(exc).__name__}", file=sys.stderr)
            continue

        if not check.value.answerable:
            dropped.append((case["id"], f"rewrite drifted: {check.value.reason}"[:400]))
            print(f"  DROP {case['id']:<26} {human_query}", file=sys.stderr)
            continue

        q_lex, c_lex = _lexemes(human_query), _lexemes(source_text)
        case["human_query"] = human_query
        case["human_lexical_overlap"] = round(len(q_lex & c_lex) / len(q_lex), 3) if q_lex else 0.0
        kept.append(case)
        print(
            f"  {case['id']:<26} overlap {case['lexical_overlap']:.2f} -> "
            f"{case['human_lexical_overlap']:.2f}  {human_query}",
            file=sys.stderr,
        )

    payload["cases"] = kept
    payload["human_phrasing"] = {
        "added_by": "scripts/generate_probe_eval_fixture.py --from-fixture",
        "model": args.model,
        "note": (
            "AUD-C-21. `human_query` was written by a pass that saw ONLY `query` and never "
            "the source passage, so it cannot echo the document by construction rather than "
            "by instruction; `human_lexical_overlap` is the same measurement as "
            "lexical_overlap, taken on it. Every rewrite was then checked against its source "
            "passage for answerability and DROPPED if it drifted, because a drifted case "
            "belongs to the 'nothing answers it' class and would flatter a wider threshold. "
            "A case listed under `unrewritten` kept its `query` and has no `human_query`: a "
            "failed call is not evidence about a case, so it is excluded from a human-set "
            "score rather than counted as a miss. Score with measure_access_probe_rules.py "
            "--query-field human_query; `query` is kept so the two sets are comparable over "
            "the same cases and chunks."
        ),
        "dropped": [{"id": i, "reason": r} for i, r in dropped],
        "unrewritten": [{"id": i, "reason": r} for i, r in unrewritten],
    }
    with open(args.from_fixture, "w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, width=100, allow_unicode=True)

    rewritten = [c for c in kept if c.get("human_query")]
    gated = [c for c in rewritten if c["category"] == "gated"]
    pub = [c for c in rewritten if c["category"] == "public"]
    before = sum(c["lexical_overlap"] for c in rewritten) / len(rewritten) if rewritten else 0.0
    after = (
        sum(c["human_lexical_overlap"] for c in rewritten) / len(rewritten) if rewritten else 0.0
    )
    print(
        f"\nrewrote {args.from_fixture}: {len(rewritten)} of {len(kept)} cases carry a "
        f"human_query ({len(gated)} gated, {len(pub)} public); {len(dropped)} dropped for "
        f"drift, {len(unrewritten)} left unrewritten by call failures (re-run to fill) | "
        f"mean lexical overlap {before:.3f} -> {after:.3f} | spent {spent:.2f} cents",
        file=sys.stderr,
    )
    return 0


async def _run(args: argparse.Namespace) -> int:
    gateway = _gateway(args.region, args.model, args.budget_cents)
    engine = create_engine()
    spent = 0.0
    cases: list[dict] = []
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            rows = (
                await session.execute(
                    text(
                        """
                        SELECT chunk_id, document_title, audience, chunk_text,
                               row_number() OVER (PARTITION BY audience ORDER BY chunk_id) AS rn
                        FROM rag_chunks
                        WHERE status = 'approved'
                          AND effective_from <= now()
                          AND (effective_to IS NULL OR effective_to > now())
                          AND length(chunk_text) >= :min_len
                        ORDER BY audience, chunk_id
                        """
                    ),
                    {"min_len": args.min_chunk_chars},
                )
            ).all()
    finally:
        await engine.dispose()

    selected = [r for r in rows if r.rn <= args.limit_per_audience]
    print(
        f"{len(rows)} eligible chunks; generating for {len(selected)} "
        f"(<= {args.limit_per_audience} per audience)",
        file=sys.stderr,
    )

    for row in selected:
        try:
            result = await gateway.generate_structured(
                task=BedrockTask.SCOPE_AND_INTENT,
                system_prompt=_SYSTEM_PROMPT,
                payload=_ChunkPayload(passage=row.chunk_text, audience=row.audience),
                response_model=_GeneratedQuestion,
                max_output_tokens=_MAX_OUTPUT_TOKENS,
                session_spend_cents=spent,
            )
        except Exception as exc:  # a generation failure drops that chunk, never the run
            print(f"  skip {row.chunk_id}: {type(exc).__name__}: {exc}", file=sys.stderr)
            continue
        spent += result.cost_cents
        question = result.value.question.strip()

        q_lex, c_lex = _lexemes(question), _lexemes(row.chunk_text)
        overlap = round(len(q_lex & c_lex) / len(q_lex), 3) if q_lex else 0.0
        cases.append(
            {
                "id": f"probe-{row.audience}-{len(cases):03d}",
                # `gated` = the answer is behind a login for an anonymous caller, so the
                # probe SHOULD name this audience. `public` = it must stay silent.
                "category": "gated" if row.audience != "public" else "public",
                "query": question,
                "expected_required_role": None if row.audience == "public" else row.audience,
                "source_document_title": row.document_title,
                "source_chunk_id": row.chunk_id,
                # The control described in this module's docstring. High values mean the
                # question echoes its own answer and proves less than it appears to.
                "lexical_overlap": overlap,
            }
        )
        print(f"  {row.audience:<15} overlap={overlap:.2f}  {question}", file=sys.stderr)

    payload = {
        "generated_by": "scripts/generate_probe_eval_fixture.py",
        "model": args.model,
        "note": (
            "Corpus-derived (AUD-C-20). Each question was generated FROM the chunk named in "
            "source_chunk_id, under an instruction not to reuse its distinctive vocabulary; "
            "lexical_overlap is the measured fraction of the question's content words that "
            "also appear in that chunk. A high mean overlap means this fixture is measuring "
            "its own paraphrase - read it before trusting any keyword-coverage result."
        ),
        "cases": cases,
    }
    with open(args.out, "w") as fh:
        yaml.safe_dump(payload, fh, sort_keys=False, width=100, allow_unicode=True)

    gated = [c for c in cases if c["category"] == "gated"]
    pub = [c for c in cases if c["category"] == "public"]
    mean = sum(c["lexical_overlap"] for c in cases) / len(cases) if cases else 0.0
    print(
        f"\nwrote {args.out}: {len(gated)} gated, {len(pub)} public, "
        f"mean lexical overlap {mean:.3f}, spent {spent:.2f} cents",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="apps/chat-api/tests/fixtures/probe_eval.yaml")
    parser.add_argument(
        "--from-fixture",
        default=None,
        help="AUD-C-21: add a blind-rewrite `human_query` to this existing fixture, in "
        "place, instead of generating a new one. See this module's docstring.",
    )
    parser.add_argument("--limit-per-audience", type=int, default=12)
    parser.add_argument("--min-chunk-chars", type=int, default=120)
    parser.add_argument("--budget-cents", type=float, default=60.0)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    args = parser.parse_args()
    if args.from_fixture:
        return asyncio.run(_add_human_phrasing(args))
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
