"""Generate a corpus-derived fixture for SPEC §18-C3's access probe (AUD-C-20).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/generate_probe_eval_fixture.py \
        --out apps/chat-api/tests/fixtures/probe_eval.yaml

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

Cost: one small generation per chunk, bounded by `--limit-per-audience`, the gateway's own
`session_budget_cents`, and a 300-token output cap. At the deployed model's rate the default
run is a few cents. Read-only against the database.
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


class _ChunkPayload(BaseModel):
    passage: str
    audience: str


class _GeneratedQuestion(BaseModel):
    question: str = Field(min_length=8, max_length=300)


def _lexemes(sql_text: str) -> set[str]:
    """Cheap stand-in for `to_tsvector` stemming, used only to report overlap. Postgres does
    the real matching in the measurement script; this is a portable approximation good enough
    to flag a fixture that echoes its source.
    """
    words = re.findall(r"[a-z]{3,}", sql_text.lower())
    stop = {
        "the", "and", "for", "are", "you", "your", "with", "that", "this", "from", "can",
        "not", "any", "all", "has", "have", "was", "were", "will", "who", "how", "what",
        "when", "does", "did", "why", "our", "out", "get", "one", "own", "they", "their",
        "there", "them", "than", "then", "into", "each", "some", "may", "must", "should",
    }
    return {w[:-1] if w.endswith("s") and len(w) > 4 else w for w in words if w not in stop}


def _gateway(region: str, model: str, budget_cents: float) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        embedding_provider=None,
        model_registry={BedrockTask.SCOPE_AND_INTENT: model},
        session_budget_cents=budget_cents,
    )


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
    parser.add_argument("--limit-per-audience", type=int, default=12)
    parser.add_argument("--min-chunk-chars", type=int, default=120)
    parser.add_argument("--budget-cents", type=float, default=60.0)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument(
        "--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
