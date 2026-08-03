"""Decide SPEC §18-C3's access-probe matching rule on evidence (AUD-C-20).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/measure_access_probe_rules.py

Scores candidate rules for `RagRepository.count_matching_by_audience` against three classes,
as an anonymous caller:

  gated       - a question a GATED chunk answers; the probe must name that audience
  public      - a question a PUBLIC chunk answers; the probe must stay silent
  unanswered  - a question NOTHING answers; the probe must stay silent

The first two come from `probe_eval.yaml`, generated from the corpus itself, each carrying a
measured `lexical_overlap` so a keyword result can be read against how much the question
echoes its own answer. The third is lifted from `qa_coverage_eval.yaml`'s `no_answer` cases,
because that class is where today's rule produces its false hint and no corpus-derived
generator can invent it.

**Scoring rule that earlier attempts got wrong and this one does not:** a hint counts only if
the role `role_access.build_access_hint` NAMES matches the expected audience. That function
picks by priority across every matching audience, so "some gated audience matched" flatters
every candidate; naming the wrong tier is a failure, not a hit.

**And the effectivity filter is a per-request Python timestamp, not `now()`.** Postgres `now()`
is transaction-scoped; this script re-embeds inside one long transaction, so a `now()`-based
filter would hide rows and silently shrink the candidate set (the bug that made a semantic
probe first look unusable).

Bedrock use: re-embeds the approved corpus with real Titan inside a transaction that is rolled
back, plus one query embedding per case. Fractions of a cent. Nothing is committed.
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path

import yaml
from chat_api.services.role_access import build_access_hint
from intellichoice_adapters.bedrock.bedrock_runtime_provider import AnthropicBedrockProvider
from intellichoice_adapters.bedrock.gateway import ResilientBedrockGateway
from intellichoice_adapters.bedrock.titan_embedding_provider import TitanEmbeddingProvider
from intellichoice_db.engine import create_engine, create_session_factory
from intellichoice_shared.bedrock import BedrockTask
from sqlalchemy import text

CALLER_ROLE = "public"
ACCESSIBLE = ["public"]
RATIOS = [
    Fraction(1),
    Fraction(4, 5),
    Fraction(3, 4),
    Fraction(2, 3),
    Fraction(1, 2),
    Fraction(2, 5),
]
CUTS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

_LEX = text("SELECT unnest(tsvector_to_array(to_tsvector('english', :q))) AS lex")
_KW = text(
    """
    WITH q AS (SELECT unnest(:lex ::text[]) AS lex)
    SELECT DISTINCT ON (c.audience) c.audience,
      (SELECT count(*) FROM q WHERE c.search_vector @@ to_tsquery('english', q.lex)) AS matched
    FROM rag_chunks c
    WHERE c.status='approved' AND c.audience <> ALL(:acc ::text[])
      AND c.effective_from <= :as_of AND (c.effective_to IS NULL OR c.effective_to >= :as_of)
    ORDER BY c.audience, matched DESC
    """
)
_SEM = text(
    """
    SELECT DISTINCT ON (c.audience) c.audience, (c.embedding <=> (:vec)::vector) AS dist
    FROM rag_chunks c
    WHERE c.status='approved' AND c.embedding IS NOT NULL
      AND c.audience <> ALL(:acc ::text[])
      AND c.effective_from <= :as_of AND (c.effective_to IS NULL OR c.effective_to >= :as_of)
    ORDER BY c.audience, dist ASC
    """
)


def _gateway(region: str, model: str) -> ResilientBedrockGateway:
    return ResilientBedrockGateway(
        provider=AnthropicBedrockProvider(aws_region=region),
        embedding_provider=TitanEmbeddingProvider(aws_region=region),
        model_registry={
            BedrockTask.EMBEDDING: "amazon.titan-embed-text-v2:0",
            BedrockTask.SCOPE_AND_INTENT: model,
        },
        session_budget_cents=80.0,
    )


def _load_cases(probe_path: Path, coverage_path: Path) -> list[dict]:
    cases = list(yaml.safe_load(probe_path.read_text())["cases"])
    for case in yaml.safe_load(coverage_path.read_text())["cases"]:
        if case["category"] == "no_answer":
            cases.append(
                {
                    "id": case["id"],
                    "category": "unanswered",
                    "query": case["query"],
                    "expected_required_role": None,
                    "lexical_overlap": None,
                }
            )
    return cases


async def _run(args: argparse.Namespace) -> int:
    gateway = _gateway(args.region, args.model)
    cases = _load_cases(Path(args.probe_fixture), Path(args.coverage_fixture))
    engine = create_engine()
    rows: list[dict] = []
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            async with session.begin():
                chunks = (
                    await session.execute(
                        text(
                            "SELECT chunk_id, chunk_text FROM rag_chunks WHERE status='approved'"
                        )
                    )
                ).all()
                for chunk_id, chunk_text in chunks:
                    emb = await gateway.create_embedding(
                        texts=[chunk_text], session_spend_cents=0.0
                    )
                    await session.execute(
                        text("UPDATE rag_chunks SET embedding = :e WHERE chunk_id = :c"),
                        {"e": str(emb.vectors[0]), "c": chunk_id},
                    )
                await session.flush()
                print(
                    f"re-embedded {len(chunks)} approved chunks (rolled back after)",
                    file=sys.stderr,
                )
                as_of = datetime.now(UTC)

                for case in cases:
                    q = case["query"]
                    lex = [r.lex for r in await session.execute(_LEX, {"q": q})]
                    kw = (
                        await session.execute(
                            _KW, {"lex": lex or [""], "acc": ACCESSIBLE, "as_of": as_of}
                        )
                    ).all()
                    emb = await gateway.create_embedding(texts=[q], session_spend_cents=0.0)
                    vec = "[" + ",".join(str(v) for v in emb.vectors[0]) + "]"
                    sem = (
                        await session.execute(
                            _SEM, {"vec": vec, "acc": ACCESSIBLE, "as_of": as_of}
                        )
                    ).all()
                    rows.append({"case": case, "n_lex": len(lex), "kw": kw, "sem": sem})
                # Deliberate: the embeddings were only ever a measurement device.
                await session.rollback()
    finally:
        await engine.dispose()

    def kw_hint(r, ratio):
        n = r["n_lex"]
        if not n:
            return None
        counts = {k.audience: 1 for k in r["kw"] if Fraction(int(k.matched), n) >= ratio}
        return build_access_hint(CALLER_ROLE, counts)

    def sem_hint(r, cut):
        return build_access_hint(
            CALLER_ROLE, {s.audience: 1 for s in r["sem"] if float(s.dist) <= cut}
        )

    def tally(fn):
        right = wrong = silent = fp_pub = fp_unans = 0
        for r in rows:
            cat, h = r["case"]["category"], fn(r)
            if cat == "gated":
                if h is None:
                    silent += 1
                elif h.required_role == r["case"]["expected_required_role"]:
                    right += 1
                else:
                    wrong += 1
            elif h is not None:
                if cat == "public":
                    fp_pub += 1
                else:
                    fp_unans += 1
        return right, wrong, silent, fp_pub, fp_unans

    n_g = sum(1 for r in rows if r["case"]["category"] == "gated")
    n_p = sum(1 for r in rows if r["case"]["category"] == "public")
    n_u = sum(1 for r in rows if r["case"]["category"] == "unanswered")
    overlaps = [
        r["case"]["lexical_overlap"]
        for r in rows
        if r["case"]["category"] == "gated" and r["case"]["lexical_overlap"] is not None
    ]
    print(
        f"\ncases: {n_g} gated, {n_p} public, {n_u} unanswered | "
        f"mean lexical overlap on gated = {sum(overlaps) / len(overlaps):.3f}"
    )
    hdr = (
        f"{'rule':>16} | {'right':>5} | {'wrong':>5} | {'silent':>6} | "
        f"{'FP public':>9} | {'FP unans':>8}"
    )
    print(hdr)
    print("-" * len(hdr))
    for ratio in RATIOS:
        print(
            "{:>16} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"kw >={ratio}", *tally(lambda r, x=ratio: kw_hint(r, x))
            )
        )
    for cut in CUTS:
        print(
            "{:>16} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"sem <={cut:.2f}", *tally(lambda r, x=cut: sem_hint(r, x))
            )
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe-fixture", default="apps/chat-api/tests/fixtures/probe_eval.yaml"
    )
    parser.add_argument(
        "--coverage-fixture", default="apps/chat-api/tests/fixtures/qa_coverage_eval.yaml"
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
