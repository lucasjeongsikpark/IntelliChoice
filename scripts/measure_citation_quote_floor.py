"""AUD-C-13: how long does a citation quote have to be before it says anything?

`qa._verify_citations` accepts any non-empty quote that is a substring of the cited chunk,
so `"a"` verifies against nearly every chunk in the corpus. The defense is real - a quote
that is not in the chunk is rejected - but its floor is one character, and a citation that
would verify against *any* chunk is not evidence about the chunk the model named.

This script measures the two things a floor has to trade off, both against the **real
approved corpus** rather than intuition, and both for free (no model call):

1. **Discriminating power.** For each candidate length, sample word-aligned spans from real
   chunks and count how many *distinct* chunks each span occurs in. A span that appears in
   many chunks is one the model could attach to any of them.
2. **The cost of the floor.** The same corpus's sentence lengths. A floor far below the
   shortest sentences is one any faithful citation can satisfy by quoting its own sentence,
   so the false-rejection risk is a phrasing burden on the model, not a refusal to a user.

Usage (needs the dev Postgres up and the RAG corpus ingested):

    uv run python scripts/measure_citation_quote_floor.py
    uv run python scripts/measure_citation_quote_floor.py --seed 7 --samples 400
"""

from __future__ import annotations

import argparse
import asyncio
import random
import re
import statistics
from dataclasses import dataclass

from intellichoice_db.engine import create_engine
from sqlalchemy import text

CANDIDATE_LENGTHS = [1, 2, 4, 8, 12, 16, 20, 24, 32, 40]

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")


def _normalized(value: str) -> str:
    """Byte-for-byte the normalization `qa._verify_citations` applies, so a length measured
    here is a length that check would see.
    """
    return re.sub(r"\s+", " ", value).strip().lower()


@dataclass(frozen=True)
class Corpus:
    chunk_texts: list[str]

    @property
    def normalized(self) -> list[str]:
        return [_normalized(chunk) for chunk in self.chunk_texts]


async def _load_corpus() -> Corpus:
    engine = create_engine()
    try:
        async with engine.connect() as conn:
            rows = await conn.execute(
                text(
                    "SELECT chunk_text FROM rag_chunks "
                    "WHERE status = 'approved' AND chunk_text <> ''"
                )
            )
            return Corpus(chunk_texts=[row[0] for row in rows])
    finally:
        await engine.dispose()


def _word_aligned_spans(normalized_chunk: str, length: int, rng: random.Random) -> str | None:
    """A span of about `length` characters starting at a word boundary, since that is what a
    model quoting text produces - a mid-word slice is not a quote anyone would write.
    """
    starts = [0] + [match.end() for match in re.finditer(r"\s", normalized_chunk)]
    starts = [start for start in starts if start + length <= len(normalized_chunk)]
    if not starts:
        return None
    start = rng.choice(starts)
    return normalized_chunk[start : start + length]


def _occurrence_counts(corpus: Corpus, length: int, samples: int, rng: random.Random) -> list[int]:
    normalized = corpus.normalized
    counts: list[int] = []
    for _ in range(samples):
        chunk = rng.choice(normalized)
        span = _word_aligned_spans(chunk, length, rng)
        if span is None:
            continue
        counts.append(sum(1 for other in normalized if span in other))
    return counts


def _sentence_lengths(corpus: Corpus) -> list[int]:
    lengths: list[int] = []
    for chunk in corpus.chunk_texts:
        for sentence in _SENTENCE_SPLIT_RE.split(chunk):
            normalized = _normalized(sentence)
            if normalized:
                lengths.append(len(normalized))
    return lengths


def _percentile(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(fraction * len(ordered)))
    return ordered[index]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--samples", type=int, default=300)
    args = parser.parse_args()

    corpus = asyncio.run(_load_corpus())
    if not corpus.chunk_texts:
        raise SystemExit("no approved chunks found - run the RAG ingestion first")
    rng = random.Random(args.seed)

    print(f"approved chunks: {len(corpus.chunk_texts)}")
    print(f"seed={args.seed} samples={args.samples}\n")
    print("how many distinct chunks does a span of this length occur in?")
    print(f"{'chars':>6} {'median':>8} {'mean':>8} {'p90':>6} {'max':>6} {'unique':>8}")
    for length in CANDIDATE_LENGTHS:
        counts = _occurrence_counts(corpus, length, args.samples, rng)
        if not counts:
            print(f"{length:>6} {'(no chunk is this long)':>40}")
            continue
        unique = sum(1 for count in counts if count == 1) / len(counts)
        print(
            f"{length:>6} {statistics.median(counts):>8.1f} {statistics.mean(counts):>8.2f} "
            f"{_percentile(counts, 0.9):>6} {max(counts):>6} {unique:>7.0%}"
        )

    sentences = _sentence_lengths(corpus)
    print(f"\nsentence lengths over the same corpus (n={len(sentences)}):")
    for fraction, label in ((0.01, "p1"), (0.05, "p5"), (0.25, "p25"), (0.5, "median")):
        print(f"{label:>7}: {_percentile(sentences, fraction):>4} chars")
    print(f"  min: {min(sentences):>4} chars")


if __name__ == "__main__":
    main()
