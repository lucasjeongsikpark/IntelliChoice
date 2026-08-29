# E2 — What each stage of the RAG pipeline actually buys

> **Program:** `docs/resume_evidence/MEASUREMENT_PLAN.md` Theme 2 (E2.1, E2.2, E2.3).
> **Date:** 2026-08-29. **Repo SHA:** `34096c3` (plus this task's additions, all new files —
> `git diff` against tracked product code is empty).
> **Environment, never blurred:** *real-model evaluation* — real `amazon.titan-embed-text-v2:0`
> embeddings and real `us.anthropic.claude-haiku-4-5-20251001-v1:0` reranking/synthesis —
> over the **local** corpus and Postgres. Not deployed staging; production is never touched
> (D-152). Every database write ran inside a transaction that was rolled back; the dev
> database keeps its mock vectors and `knowledge-content/` is unchanged.
> **Total model spend: 297.26 cents** against a 500-cent hard cap
> (E2.1 76.60 ¢ · E2.2 cost probe 3.35 ¢ · E2.2 full run 163.61 ¢ · E2.3 53.70 ¢).

Every number below traces to an artifact in this directory. Rates carry their denominator;
latencies carry p50/p95/p99.

| Artifact | What it holds |
|---|---|
| `apps/chat-api/tests/fixtures/retrieval_benchmark.yaml` | the fixture: 123 ground truths, 363 query instances, 18 no-answer controls |
| `fixture_provenance.md` | how the fixture was built, its four honesty controls, and what it **cannot** support |
| `ablation_dump.jsonl.gz` | per-instance rankings, rerank scores and latencies for all 8 arms |
| `ablation_metrics.csv` | 64 metric rows (8 arms × 8 category groupings) |
| `ablation_run_output.txt` | the collection run's verbatim stdout, including the drift guard |
| `e2e_eval_output.txt` | E2.3's verbatim pytest output |

---

## Headline results

| Claim | Measured | Where |
|---|---|---|
| **The repository's first IR metrics** — no Recall@k, MRR or nDCG existed anywhere before this | Recall@{1,3,5,10}, MRR, nDCG@10 for **8 arms × 8 category groupings**, n/N everywhere | `ablation_metrics.csv` |
| **The lexical arm is near-dead on real phrasing** | FTS-only Recall@10 = **50/363 (13.8%)**; it returns **zero candidates on 305 of 363 queries (84.0%)** | table below |
| …but it is **high-precision when it fires** | on the 58 queries where FTS returns anything, it is right at rank 1 **48/58 (82.8%)** | `ablation_dump.jsonl.gz` |
| **RRF fusion is net-negative at rank 1 on this corpus** | vector-only → hybrid+RRF: Recall@1 **323/363 → 318/363**; paired **+5 / −10** | below |
| **The RRF `k` parameter is inert here** | k = 20, 60 and 120 produce **identical rankings on 363/363 instances** | below |
| **The reranker is the one stage that clearly pays** | hybrid+RRF → +rerank: Recall@1 **318/363 → 328/363**, paired **+20 / −10** | below |
| …and it pays exactly where lexical signal is absent | `lexical_mismatch` Recall@1 **29/41 → 34/41** (70.7% → 82.9%, **+12.2 pts**); `exact_lookup` unchanged | below |
| **The shipped relevance floor costs recall and buys refusals** | Recall@10 1.000 → **0.984 (357/363)**; empties **15/18** no-answer controls where every unfiltered arm returns 30 | below |
| **A new limit of the floor, found here** | 3 controls leak at rerank scores **0.75 / 0.85 / 0.90** — no floor below 0.90 removes them | below |
| **End-to-end, at this SHA** | grounded citation **20/20**, correct refusal **37/37**, every category **100%** | `e2e_eval_output.txt` |
| **Retrieval latency is not the cost** | DB-side hybrid p50 **32.5 ms** / p95 42.0 ms; the rerank model call is p50 **2,766 ms** — **85× the entire database stage** | below |

---

## E2.1 — The fixture

123 chunk-level ground truths (one per groundable approved+effective chunk, all distinct)
× 2–4 phrasings = **363 query instances**, plus **18 validated no-answer controls**.
Built with the repository's established blind-rewrite + measured-lexical-overlap +
answerability-judge controls, and one added control: **measured overlap beats generator
intent**, which relabelled 56 of 104 `lexical_mismatch` attempts to `paraphrase`.

Full construction, per-category counts, overlap distributions and the honesty cap:
**`fixture_provenance.md`**. Two things from it are load-bearing for every table below.

**Effective n is 123, not 363.** The 363 instances are 2–4 phrasings of 123 questions, and
phrasings of one question are correlated samples — if a chunk is hard to retrieve, all of
its phrasings tend to fail together. Both numbers appear in every table. No confidence
interval is computed on the instance count, and none should be.

**Recall@5 and Recall@10 are ceilinged and are not the interesting columns.** The candidate
limit is 30 out of a ≤144-chunk corpus, so the semantic arm reaches every ground truth by
rank 5 in every stratum. **Recall@1 and MRR are the discriminating metrics here**; the
Recall@5/@10 columns are reported for completeness and to make the ceiling visible rather
than to be read as quality.

---

## E2.2 — The ablation

Eight arms, built from the product's own public seams rather than re-implemented — the arms
are not config-toggleable (`hybrid_search` unconditionally fuses both signals and there is
no rerank-off switch), so the harness calls `keyword_search_chunk_ids`,
`semantic_search_chunk_ids`, `reciprocal_rank_fusion`, `get_chunks_by_ids` and the shipped
rerank prompt directly.

### The drift guard, in two halves — both passed

The AUD-C-25 lesson is that a harness which restates the shipped rule instead of calling it
diverges silently; D-177 recorded a zero that way. So:

- **Deterministic half — exact, on every instance.** `hybrid_search` is pure given the same
  filters, query and embedding, so the harness's own k=60 fused order must equal it
  id-for-id. It is free, so it ran on **all 381 instances** and a single mismatch aborts the
  run. **0 mismatches.**
- **Model half — sampled, paid.** The real `retrieve()` was re-run on 12 instances and its
  returned chunk ids compared to the harness's shipped arm: **mean Jaccard 77.8%**, above
  the 60% failure threshold. The reranker is a model, so per-case disagreement at the margin
  is expected (7 of 12 at 100%, 5 at 50–67%); a genuine divergence shows up as a low mean.

### Per-arm results, all 363 scored instances / 123 ground truths

| Arm | R@1 | R@3 | R@5 | R@10 | MRR | nDCG@10 | DB p50 | DB p95 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fts` (keyword only) | 0.132 | 0.138 | 0.138 | 0.138 | 0.135 | 0.136 | 6.8 ms | 11.8 ms |
| `vector` (pgvector only) | 0.890 | 0.984 | 1.000 | 1.000 | 0.937 | 0.953 | 6.4 ms | 12.1 ms |
| `hybrid_interleave` (no RRF) | 0.876 | 0.986 | 1.000 | 1.000 | 0.932 | 0.950 | 32.6 ms | 42.0 ms |
| `hybrid_rrf_k20` | 0.876 | 0.986 | 1.000 | 1.000 | 0.932 | 0.949 | 32.5 ms | 42.2 ms |
| **`hybrid_rrf_k60`** (ships) | 0.876 | 0.986 | 1.000 | 1.000 | 0.932 | 0.949 | 32.5 ms | 42.0 ms |
| `hybrid_rrf_k120` | 0.876 | 0.986 | 1.000 | 1.000 | 0.932 | 0.949 | 32.5 ms | 42.0 ms |
| `hybrid_rrf_rerank` (reorder only) | **0.904** | 0.986 | 1.000 | 1.000 | **0.947** | **0.960** | 32.5 ms | 42.0 ms |
| **`hybrid_rrf_rerank_shipped`** (floor 0.35, top-8) | **0.904** | 0.975 | 0.984 | 0.984 | 0.941 | 0.952 | 32.5 ms | 42.0 ms |

Recall@1 numerators: 48 / 323 / 318 / 318 / 318 / 318 / 328 / 328 out of **363**.
Per-stratum and per-phrasing rows for all eight arms: `ablation_metrics.csv` (64 rows).

### The ablation deltas, as paired comparisons

A net rate hides how a change actually behaves, so each step is also reported as wins and
losses on the *same* instances:

| Step | Recall@1 | Paired at rank 1 |
|---|---|---|
| `vector` → `hybrid_rrf_k60` | 323/363 → 318/363 (−1.4 pts) | **+5 / −10** |
| `hybrid_rrf_k60` → `hybrid_rrf_rerank` | 318/363 → 328/363 (+2.8 pts) | **+20 / −10** |
| `vector` → `hybrid_rrf_rerank` (end to end) | 323/363 → 328/363 (+1.4 pts) | **+17 / −12** |
| `hybrid_rrf_rerank` → shipped floor | 328/363 → 328/363 (0.0 pts) | **+0 / −0** |

### What the ablation says

**1. The lexical arm contributes almost nothing on realistic phrasing — and the reason is
structural, not a broken index.** `search_vector` is populated for 144/144 approved chunks
and a single-word query matches 24 of them; `websearch_to_tsquery` ANDs *every* content word
of a question, so one word the chunk happens not to use voids the whole match. Measured
here: **zero candidates on 305 of 363 queries (84.0%)**, mean keyword pool **0.20 chunks**,
and on the `lexical_mismatch` phrasing exactly **0/41**. This is D-166's "1 of 38" finding
reproduced at chunk level with a 363-instance denominator.

**2. But it is precise, not merely bad.** On the 58 queries where FTS returns anything, its
top hit is the correct chunk **48/58 (82.8%)**. The arm has near-zero recall and high
precision — which is exactly why deleting it is not the obvious call it looks like, and why
D-165 keeps it (it is also the only retrieval signal `MockBedrockProvider` can exercise, so
removing it would make the whole offline suite structurally unable to observe retrieval).

**3. Fusion is a wash-to-slightly-negative at rank 1 here.** RRF changes the ranking at all
on only **18 of 363** instances (345 are identical to vector-only), because one input list is
empty 84% of the time. On the 58 instances where the lexical list is non-empty, RRF helps
5 and hurts 10 at rank 1: a two-item lexical list contributes `1/(k+1)` to a chunk the
semantic arm had ranked lower, which is sometimes enough to displace a correct top-1.
**This is a finding about this corpus and these queries, not a claim that RRF is wrong** —
on a corpus with real lexical diversity (product codes, names, error strings) the same
fusion would have a much larger and probably positive effect. On *this* corpus it is
carrying the pipeline's complexity without paying for it at rank 1.

**4. The RRF `k` parameter is completely inert here: k = 20, 60 and 120 produce identical
rankings on 363/363 instances.** `k` controls how sharply rank 1 outweighs rank 10 *within
the fusion*, and with one list empty the fused order is just the semantic order regardless.
Tuning `k` on this corpus would be tuning a parameter with no reachable effect — worth
knowing before anyone spends a sweep on it.

**5. The reranker is the stage that earns its cost, and it earns it precisely where the
lexical signal is gone.** Recall@1 by phrasing, `hybrid_rrf_k60` → `hybrid_rrf_rerank`:

| Phrasing | n | mean lexical overlap | hybrid+RRF R@1 | +rerank R@1 | Δ |
|---|---:|---:|---:|---:|---:|
| `exact_lookup` | 123 | 0.609 | 0.919 | 0.919 | **0.0** |
| `paraphrase` | 171 | 0.481 | 0.871 | 0.895 | +2.4 pts |
| `multi_keyword` | 28 | 0.618 | 0.964 | 1.000 | +3.6 pts |
| **`lexical_mismatch`** | 41 | **0.035** | **0.707** (29/41) | **0.829** (34/41) | **+12.2 pts** |

Where the question shares the passage's words, the embedding already had it and the
reranker adds nothing. Where it shares none of them, the reranker recovers 5 of the 12
cases the fused order got wrong. That is the clearest single result in this experiment.

**6. The shipped relevance floor: the AUD-C-12 trade, re-measured on a larger negative set.**
`MIN_RERANK_RELEVANCE_SCORE = 0.35` and `top_k = 8` change **no** rank-1 outcome (+0/−0) —
they only truncate the tail, costing Recall@10 **1.000 → 0.984 (357/363)**. What they buy:

| Arm | No-answer controls emptied | Mean chunks returned | Max |
|---|---:|---:|---:|
| `fts` | 18/18 | 0.00 | 0 |
| `vector`, `hybrid_interleave`, all `hybrid_rrf_k*`, `hybrid_rrf_rerank` | **0/18** | **30.00** | 30 |
| `hybrid_rrf_rerank_shipped` | **15/18** | 0.17 | 1 |

Every unfiltered arm hands synthesis its full 30-candidate pool for a question nothing in
the corpus answers — pgvector's cosine ordering has no notion of "nothing is close enough",
so it always returns the limit. The floor is what turns reranking from a sort into a filter.

**7. A new limit of the floor, found by this fixture.** Three controls survive the 0.35 cut
with rerank scores of **0.75, 0.85 and 0.90** — far above any floor AUD-C-12 could have
chosen from `qa_coverage_eval.yaml`, where no unanswerable case scored above 0.30. The
leaked passages are:

- *"How do I get a refund if we signed up and then changed our minds?"* → 0.75, and
  *"Is there a sibling discount if I enroll two children at once?"* → 0.90, both matching
  the Contact Guide's *"For questions about enrollment, scheduling, or billing, contact your
  branch manager directly."*
- *"What are the dates of the summer break camp this year?"* → 0.85, matching the Academic
  Calendar (which lists Thanksgiving and Winter Break, and no summer camp).

All three passages were **independently judged unanswerable** during fixture construction —
they are in the controls' own `validated_neighbours` lists with `answerable: false`. So this
is not a bad control: it is two models disagreeing correctly in their own terms. The
answerability judge is asked *"could someone answer completely from only this passage?"*;
the reranker is asked *"how relevant is this passage to the query?"* A passage that says
"contact your branch manager about billing" **is** highly relevant to a refund question and
**does not** answer it. **A relevance score is not an answerability score**, and a floor on
the first cannot fully do the job of the second. Raising the floor toward 0.90 is not the
fix on this evidence either — it would still miss the 0.90 case while cutting into the
answerable distribution, whose weakest cases sit at 0.00 and whose 10th percentile is 0.95.
*Changing the threshold or the pipeline is out of this task's scope; this is reported as a
measured limit, not acted on.*

**8. Latency: the database is not the cost.** DB-side retrieval, over 363 instances:

| Arm | p50 | p95 | p99 |
|---|---:|---:|---:|
| `fts` | 6.8 ms | 11.8 ms | 15.7 ms |
| `vector` | 6.4 ms | 12.1 ms | 16.6 ms |
| `hybrid_rrf_k60` (both searches + fusion + id→row resolve) | 32.5 ms | 42.0 ms | 53.7 ms |
| **rerank model call** (reported separately) | **2,766 ms** | **3,492 ms** | **3,982 ms** |

The hybrid stage costs ~26 ms more than either single search. The reranker costs **85× the
entire database stage** and is where every millisecond of a retrieval turn actually goes.

---

## E2.3 — End-to-end real-model eval at this SHA

One full run of the existing 68-case lane (`test_qa_coverage_eval_real_bedrock.py`), 53.7
cents, 307.98 s, verbatim output in `e2e_eval_output.txt`:

| Category | Rate | n/N |
|---|---:|---:|
| `adversarial` (containment) | 100.0% | 6/6 |
| `grounded` | 100.0% | 9/9 |
| `no_answer` | 100.0% | 8/8 |
| `no_source` | 100.0% | 16/16 |
| `out_of_scope` | 100.0% | 10/10 |
| `paraphrase` | 100.0% | 11/11 |
| `role_gated_question` | 100.0% | 3/3 |
| **`grounded_citation_rate`** | **100.0%** | **20/20** |
| **`correct_refusal_rate`** | **100.0%** | **37/37** |

Against Theme 2's recorded previous best (`correct_refusal_rate` 36/37, `grounded_citation_rate`
17/20), this run is 37/37 and 20/20 — but read it as **one run of a 68-case fixture with a
non-deterministic model**, not as a regression-free guarantee. The lane asserts only the
architectural invariants (zero wrong-role hints, adversarial containment 1.0); every quality
number is reported rather than gated, deliberately, because a threshold invented before
measurement is a guess dressed as a gate.

The `role_gated` row is `n/a` by design: `load_cases(include_mock_only=False)` drops its five
nonsense-marker cases, which a real scope guard refuses before retrieval.

---

## Limitations

- **Corpus size.** 20 documents, 144 approved+effective chunks, ~7.5k words. Recall@5 and
  @10 saturate at 1.000 for every semantic arm because the 30-candidate pool covers a large
  fraction of the reachable corpus. Only Recall@1 and MRR discriminate here, and even those
  live on a small corpus.
- **Effective n = 123**, not 363; and 36 of those 123 are near-duplicate staff bios, so the
  independent-question count is lower still. Nothing here carries a confidence interval.
- **Single corpus, single generator, single language.** All questions were written by Haiku
  4.5 from one English corpus. A different generator produces a different difficulty
  distribution; none of this generalises to another corpus. In particular, **finding 3 (RRF
  is net-negative) and finding 4 (`k` is inert) are properties of a corpus whose vocabulary
  its users do not share** — they are not general claims about reciprocal rank fusion.
- **Single-chunk ground truth.** Where a question could arguably be answered by a second
  passage, that passage scores as a miss, so every recall number here is a **lower bound**.
- **One run per number.** The reranker is a model; its ordering varies run to run (visible in
  the drift guard's 50–100% per-case Jaccard). Rank-1 deltas of a handful of instances —
  the `+5/−10` fusion result especially — are within the range a repeat run could move.
  They are reported as paired counts precisely so the reader can see how thin they are.
- **Latency was measured on a local Docker Postgres inside an open transaction** that had
  just re-embedded all 144 chunks. It is a fair *relative* comparison between arms; it is
  not a deployed-staging latency number and must not be quoted as one.
- **Mock-lane numbers are absent on purpose.** The mock provider's hash embeddings make
  semantic retrieval unmeasurable, and its reranker scores literal word overlap
  (the AUD-C-05/AUD-C-16 lesson). Every quality number here required real models.

---

## Reproducing

```bash
# E2.1 — free preflight
uv run python benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py --dry-run

# E2.1 — the paid fixture build (76.60 cents as run)
eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)" && \
AWS_REGION=us-east-1 uv run python \
  benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py \
  --out apps/chat-api/tests/fixtures/retrieval_benchmark.yaml --budget-cents 90
AWS_REGION=us-east-1 uv run python \
  benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py \
  --out apps/chat-api/tests/fixtures/retrieval_benchmark.yaml \
  --top-up-mismatch --mismatch-cases 65 --budget-cents 40

# E2.2 — collect once (163.61 cents as run), then re-score for free
AWS_REGION=us-east-1 uv run python benchmarks/resume_evidence/02_rag/retrieval_ablation.py \
  --dump docs/resume_evidence/02_rag/ablation_dump.jsonl.gz \
  --metrics-csv docs/resume_evidence/02_rag/ablation_metrics.csv \
  --run-budget-cents 200 --verify-against-retrieve 12
uv run python benchmarks/resume_evidence/02_rag/retrieval_ablation.py \
  --load docs/resume_evidence/02_rag/ablation_dump.jsonl.gz   # free

# E2.3 — the existing paid lane (53.7 cents as run)
AWS_REGION=us-east-1 CHAT_EVAL_REAL_BEDROCK=1 CHAT_EVAL_RUN_BUDGET_CENTS=150 \
  uv run pytest apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py -s -q
```

Never run `make test` concurrently with any of the paid lanes: they share the dev Postgres.
