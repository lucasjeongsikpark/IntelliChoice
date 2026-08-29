"""E2.2's scoring functions: rank list + relevant-id set -> Recall@k, MRR, nDCG@k.

Pure, dependency-free, and deliberately separated from `retrieval_ablation.py`, because
these five functions are where a retrieval benchmark is most likely to be quietly wrong.
Every number in `docs/resume_evidence/02_rag/E2_REPORT.md` is produced here, and an
instrument that miscounts produces a report that is internally consistent and false - the
same reasoning `apps/learning-api/tests/test_e1_sse_ledger.py` records for E1's ledger.
`apps/chat-api/tests/test_e2_ir_metrics.py` pins all of it on literals.

Three conventions worth stating, since IR papers do not agree on any of them:

**Recall@k vs Hit@k.** With a single relevant chunk the two are the same number, and in
this benchmark every ground truth *is* a single chunk (see `fixture_provenance.md`), so
the report's "Recall@k" column is also a hit rate. The set form is still implemented and
tested because the Frozen Spec allows set ground truth for the staff-bio near-duplicate
cluster, and a benchmark that silently redefines its own metric when the fixture grows is
the drift this module exists to prevent. `recall_at_k` is `|retrieved ∩ R| / |R|`;
`hit_at_k` is `1.0 if any`. They are reported as separate columns, never merged.

**MRR is over the FIRST relevant id**, not the mean over all of them - the standard
definition, and with singleton R the only one that means anything.

**nDCG@k uses binary gain and the log2(rank+1) discount**, with the ideal DCG computed
over `min(|R|, k)` perfect positions. Binary rather than graded because this fixture has
no graded relevance judgements: a chunk either is or is not the passage the question was
written from. Claiming graded nDCG over binary labels would be a fabricated number.

Ranks are 1-indexed in every formula and 0-indexed in every list; that boundary is the
other place this kind of code goes wrong, so it is asserted directly in the tests.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def _first_relevant_rank(ranked_ids: Sequence[str], relevant_ids: Iterable[str]) -> int | None:
    """1-indexed rank of the first relevant id, or None if none is present."""
    relevant = set(relevant_ids)
    for index, chunk_id in enumerate(ranked_ids):
        if chunk_id in relevant:
            return index + 1
    return None


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """`|retrieved@k ∩ R| / |R|`. Returns 0.0 for an empty R rather than raising, because an
    empty R is a no-answer control and those are scored by `emptied`, never by recall - a
    caller that mixes them up gets a zero it can see, not a crash it will silence.
    """
    relevant = set(relevant_ids)
    if not relevant:
        return 0.0
    if k <= 0:
        return 0.0
    return len(set(ranked_ids[:k]) & relevant) / len(relevant)


def hit_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """1.0 if any relevant id is in the top k. The Frozen Spec's "hit if any is retrieved"
    scoring for set ground truth; identical to `recall_at_k` when `|R| == 1`.
    """
    if k <= 0:
        return 0.0
    return 1.0 if set(ranked_ids[:k]) & set(relevant_ids) else 0.0


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: Iterable[str]) -> float:
    """`1 / rank` of the first relevant id over the WHOLE list, 0.0 if it never appears.

    Not truncated at k on purpose: a truncated MRR silently reports "the ranker failed"
    and "the ranker put it at 31" as the same number, and with a 30-candidate limit those
    are different findings. The cut-off metrics above carry the truncation.
    """
    rank = _first_relevant_rank(ranked_ids, relevant_ids)
    return 1.0 / rank if rank is not None else 0.0


def ndcg_at_k(ranked_ids: Sequence[str], relevant_ids: Iterable[str], k: int) -> float:
    """Binary-gain nDCG@k: `DCG / IDCG`, discount `1 / log2(rank + 1)`, IDCG over
    `min(|R|, k)` perfect positions. 0.0 when R is empty or k <= 0.
    """
    relevant = set(relevant_ids)
    if not relevant or k <= 0:
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 2)
        for index, chunk_id in enumerate(ranked_ids[:k])
        if chunk_id in relevant
    )
    idcg = sum(1.0 / math.log2(index + 2) for index in range(min(len(relevant), k)))
    return dcg / idcg if idcg else 0.0


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile on the sorted sample (p in [0, 100]).

    Nearest-rank rather than linear interpolation so every reported latency is a value the
    harness actually observed - the same choice `benchmarks/resume_evidence/01_platform`
    made, and it keeps p50/p95 comparable across the two experiments.
    """
    if not values:
        return 0.0
    ordered = sorted(values)
    if p <= 0:
        return ordered[0]
    index = math.ceil(p / 100.0 * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
