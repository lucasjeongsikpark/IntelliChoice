"""Decide SPEC §18-C3's access-probe matching rule on evidence (AUD-C-20, AUD-C-21).

Run with:

    eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
    AWS_REGION=us-east-1 uv run python scripts/measure_access_probe_rules.py \
        --query-field human_query

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

**`--query-field` is AUD-C-21's instrument.** D-165 chose a 0.40 ceiling against `query`, the
chunk-derived phrasing, and the live check found it too tight for real users. `human_query`
is a blind rewrite of the same case - written without ever seeing the passage - so scoring the
same rules over both fields separates "how good is the rule" from "how optimistic was the
fixture". The distance table printed first is the measurement that matters: how far each
phrasing sits from the chunk it is known to come from. Cases with no `human_query` (a call
failed when the fixture was built) are excluded from a `human_query` run and counted, never
scored as misses.

**Scoring rule that earlier attempts got wrong and this one does not:** a hint counts only if
the role `role_access.build_access_hint` NAMES matches the expected audience. That function
picks by priority across every matching audience, so "some gated audience matched" flatters
every candidate; naming the wrong tier is a failure, not a hit.

**The margin rules exist because a single global ceiling has to serve two jobs at once.**
Widening the cut to catch human phrasing also lets in questions nothing answers, where every
chunk is far away and roughly equidistant - D-165 measured false hints appearing at 0.55. A
margin rule asks a *relative* question instead: is the nearest gated chunk meaningfully closer
than the nearest chunk this caller could already read? On a question a gated document answers
that gap should be real; on a question nothing answers there is no reason for it to be. The
sweep below is what says whether that holds on this corpus.

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
CUTS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
# (ceiling, margin): the gated chunk must be within `ceiling` AND at least `margin` closer
# than the nearest chunk the caller can already read. margin 0.0 is "merely closer", which is
# the weakest useful form and worth measuring next to the stricter ones.
MARGINS = [
    (0.55, 0.0),
    (0.55, 0.03),
    (0.60, 0.0),
    (0.60, 0.03),
    (0.60, 0.06),
    (0.65, 0.03),
    (0.65, 0.06),
    (0.70, 0.06),
]

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
# The comparison arm for the margin rules: the closest thing the caller could read anyway.
# `count_matching_by_audience` can run exactly this query - it already builds the same
# filters, with the audience allowlist applied instead of inverted.
_SEM_ACCESSIBLE = text(
    """
    SELECT min(c.embedding <=> (:vec)::vector) AS dist
    FROM rag_chunks c
    WHERE c.status='approved' AND c.embedding IS NOT NULL
      AND c.audience = ANY(:acc ::text[])
      AND c.effective_from <= :as_of AND (c.effective_to IS NULL OR c.effective_to >= :as_of)
    """
)
# AUD-C-21's headline: the distance from a question to the one chunk it was derived from.
# Independent of any rule, and the only number that shows phrasing bias directly.
_SRC = text("SELECT (embedding <=> (:vec)::vector) AS dist FROM rag_chunks WHERE chunk_id = :c")


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


def _load_cases(
    probe_path: Path, coverage_path: Path, query_field: str
) -> tuple[list[dict], list[str]]:
    """Returns (cases, skipped_ids). A case with no value in `query_field` is skipped rather
    than scored: the fixture records those as `unrewritten`, meaning a call failed while it
    was built, which is not evidence about the case.
    """
    cases, skipped = [], []
    for case in yaml.safe_load(probe_path.read_text())["cases"]:
        query = case.get(query_field)
        if not query:
            skipped.append(case["id"])
            continue
        cases.append({**case, "query": query})
    for case in yaml.safe_load(coverage_path.read_text())["cases"]:
        if case["category"] == "no_answer":
            # Not rephrased by `--query-field`: this class is hand-written, not
            # corpus-derived, so there is no source passage a blind rewrite could diverge
            # from. It is the same negative set in both runs, which is what makes the two
            # runs' false-positive columns directly comparable.
            cases.append(
                {
                    "id": case["id"],
                    "category": "unanswered",
                    "query": case["query"],
                    "expected_required_role": None,
                    "lexical_overlap": None,
                    "source_chunk_id": None,
                }
            )
    return cases, skipped


async def _run(args: argparse.Namespace) -> int:
    gateway = _gateway(args.region, args.model)
    cases, skipped = _load_cases(
        Path(args.probe_fixture), Path(args.coverage_fixture), args.query_field
    )
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
                    accessible = (
                        await session.execute(
                            _SEM_ACCESSIBLE, {"vec": vec, "acc": ACCESSIBLE, "as_of": as_of}
                        )
                    ).scalar()
                    src = (
                        (
                            await session.execute(
                                _SRC, {"vec": vec, "c": case["source_chunk_id"]}
                            )
                        ).scalar()
                        if case["source_chunk_id"]
                        else None
                    )
                    rows.append(
                        {
                            "case": case,
                            "n_lex": len(lex),
                            "kw": kw,
                            "sem": sem,
                            "accessible": float(accessible) if accessible is not None else None,
                            "src": float(src) if src is not None else None,
                        }
                    )
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

    def margin_hint(r, cut, margin):
        """Within `cut` AND at least `margin` closer than the nearest readable chunk.

        A caller with no accessible corpus at all (`accessible is None`) has nothing to
        compare against, so the margin condition is vacuously satisfied and the rule falls
        back to the plain ceiling - fail-open on the *hint*, which only ever tells someone to
        log in, never reveals content.
        """
        ceiling = r["accessible"] - margin if r["accessible"] is not None else float("inf")
        return build_access_hint(
            CALLER_ROLE,
            {s.audience: 1 for s in r["sem"] if float(s.dist) <= min(cut, ceiling)},
        )

    def union_hint(r, cut):
        """The rule `count_matching_by_audience` actually applies: production UNIONS the two
        arms, and the keyword arm is `websearch_to_tsquery`, i.e. every lexeme must match
        (`kw >=1` below). Scoring the arms separately can hide a disagreement, because
        `build_access_hint` picks by priority over the union - one arm naming a higher-priority
        audience than the other flips the answer. D-159's rule: measure the path that runs.
        """
        n = r["n_lex"]
        matched = {k.audience: 1 for k in r["kw"] if n and Fraction(int(k.matched), n) >= 1}
        matched.update({s.audience: 1 for s in r["sem"] if float(s.dist) <= cut})
        return build_access_hint(CALLER_ROLE, matched)

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
        f"\nquery field: {args.query_field} | cases: {n_g} gated, {n_p} public, "
        f"{n_u} unanswered"
        + (f" | skipped for no {args.query_field}: {len(skipped)}" if skipped else "")
    )
    print(f"mean lexical overlap on gated = {sum(overlaps) / len(overlaps):.3f}")

    # AUD-C-21's direct measurement, before any rule is applied: where does this phrasing
    # actually sit relative to the chunk it came from, and relative to what the caller can
    # already read? A ceiling can only be chosen honestly against these two distributions.
    def _dist_summary(label: str, values: list[float]) -> None:
        if not values:
            return
        ordered = sorted(values)
        pct = [ordered[min(len(ordered) - 1, int(len(ordered) * q))] for q in (0.5, 0.75, 0.9)]
        print(
            f"  {label:<34} n={len(values):<3} mean={sum(values) / len(values):.3f}  "
            f"p50={pct[0]:.3f}  p75={pct[1]:.3f}  p90={pct[2]:.3f}  max={ordered[-1]:.3f}"
        )

    print("\ndistance to the chunk the question was derived from:")
    for cat in ("gated", "public"):
        _dist_summary(
            f"{cat}: question -> its own source",
            [r["src"] for r in rows if r["case"]["category"] == cat and r["src"] is not None],
        )
    print("\nnearest-chunk distances (what every rule below thresholds):")
    for cat in ("gated", "public", "unanswered"):
        subset = [r for r in rows if r["case"]["category"] == cat]
        _dist_summary(
            f"{cat}: nearest GATED chunk",
            [min(float(s.dist) for s in r["sem"]) for r in subset if r["sem"]],
        )
        _dist_summary(
            f"{cat}: nearest READABLE chunk",
            [r["accessible"] for r in subset if r["accessible"] is not None],
        )

    hdr = (
        f"\n{'rule':>22} | {'right':>5} | {'wrong':>5} | {'silent':>6} | "
        f"{'FP public':>9} | {'FP unans':>8}"
    )
    print(hdr)
    print("-" * (len(hdr) - 1))
    for ratio in RATIOS:
        print(
            "{:>22} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"kw >={ratio}", *tally(lambda r, x=ratio: kw_hint(r, x))
            )
        )
    for cut in CUTS:
        print(
            "{:>22} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"sem <={cut:.2f}", *tally(lambda r, x=cut: sem_hint(r, x))
            )
        )
    for cut in CUTS:
        print(
            "{:>22} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"UNION kw+sem <={cut:.2f}", *tally(lambda r, x=cut: union_hint(r, x))
            )
        )
    for cut, margin in MARGINS:
        print(
            "{:>22} | {:>5} | {:>5} | {:>6} | {:>9} | {:>8}".format(
                f"sem <={cut:.2f} m{margin:.2f}",
                *tally(lambda r, c=cut, m=margin: margin_hint(r, c, m)),
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
    parser.add_argument(
        "--query-field",
        default="query",
        choices=["query", "human_query"],
        help="AUD-C-21: `query` is the chunk-derived phrasing D-165 chose 0.40 against; "
        "`human_query` is the blind rewrite that models how a person asks.",
    )
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--model", default="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
