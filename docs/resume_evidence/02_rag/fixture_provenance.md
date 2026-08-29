# E2.1 — `retrieval_benchmark.yaml`: how it was built, and what it can and cannot support

> **Program:** `docs/resume_evidence/MEASUREMENT_PLAN.md` Theme 2 (E2.1).
> **Fixture:** `apps/chat-api/tests/fixtures/retrieval_benchmark.yaml`.
> **Generator:** `benchmarks/resume_evidence/02_rag/generate_retrieval_benchmark.py`.
> **Date:** 2026-08-29. **Repo SHA at generation:** `34096c3`. **Seed:** `20260829` (top-up
> pass `20260830`).
> **Environment:** *real-model evaluation* — question generation and every answerability
> judgement on `us.anthropic.claude-haiku-4-5-20251001-v1:0`; no-answer validation on real
> `amazon.titan-embed-text-v2:0` embeddings, over the **local** corpus/database. Production
> is never touched (D-152); deployed staging is not involved.
> **Spend:** **76.60 cents** over 741 model calls (59.33 ¢ first pass + 17.27 ¢ top-up).
> **Writes:** none. All database work ran inside a transaction that was rolled back;
> `knowledge-content/` and `rag_chunks` are byte-identical to before the run.

---

## What it contains

| | Count |
|---|---:|
| Ground truths (one per distinct approved+effective chunk) | **123** |
| Query instances (2–4 phrasings per ground truth) | **363** |
| No-answer controls (validated, scored outside recall) | **18** |
| Distinct source chunks | **123** (no chunk carries two ground truths) |
| Source documents | 20 |
| Model calls | 741 |

### By stratum

| Stratum | Ground truths | exact_lookup | paraphrase | lexical_mismatch | multi_keyword |
|---|---:|---:|---:|---:|---:|
| `authorization_boundary` (gated audiences) | 55 | 55 | 66 | 27 | 9 |
| `near_duplicate_cluster` (`public/our-team` staff bios) | 36 | 36 | 65 | **0** | 11 |
| `general` (rest of the public corpus) | 32 | 32 | 40 | 14 | 8 |
| **Total** | **123** | **123** | **171** | **41** | **28** |

### Measured lexical overlap per phrasing

`lexical_overlap` is the fraction of a question's content words that also appear in its
source chunk, measured with the same stemmer `scripts/generate_probe_eval_fixture.py` uses
(`test_e2_retrieval_benchmark.py::test_overlap_stemmer_agrees_with_the_probe_generator`
asserts the two functions agree, so the column is comparable across both fixtures).

| Phrasing | n | mean | median | min | max |
|---|---:|---:|---:|---:|---:|
| `exact_lookup` | 123 | 0.609 | 0.600 | 0.000 | 1.000 |
| `paraphrase` | 171 | 0.481 | 0.429 | 0.000 | 1.000 |
| `lexical_mismatch` | 41 | **0.035** | 0.000 | 0.000 | 0.143 |
| `multi_keyword` | 28 | 0.618 | 0.667 | 0.167 | 1.000 |

---

## How each phrasing was produced

| Pass | Phrasing | Sees the passage? | Answerability-checked? |
|---|---|---|---|
| A | `exact_lookup` | yes | no — written directly from it |
| B | `paraphrase` | **no** (blind rewrite of A's output) | yes |
| C / C2 | `lexical_mismatch` | yes — it must know which words to avoid | yes |
| D | `multi_keyword` | yes | yes |

50 of the 123 ground truths reuse `probe_eval.yaml`'s two existing phrasings verbatim and
free of charge (its `query` is a pass-A seed, its `human_query` a pass-B blind rewrite);
their `reused_from` field names the case. Overlap was re-measured rather than copied.

---

## The four honesty controls, and what each one caught

These are carried over from `scripts/generate_probe_eval_fixture.py`, where each was added
after a specific failure. Their outcomes on this run are the point of this section: a
control that never fires is not evidence that the fixture is clean.

**1. Blind rewrite (AUD-C-21).** The `paraphrase` pass is given the seed question and
nothing else, so it cannot echo the document by construction rather than by instruction.
*Outcome:* it still only moved mean overlap from 0.609 to 0.481. That is a real limit of
this corpus, not a broken control — see "What this fixture cannot support" below.

**2. Answerability judge.** Every rewritten phrasing was re-checked against its own passage
and dropped if it had drifted into a different question, because a drifted phrasing is a
case whose *ground truth* is wrong, and a wrong ground truth flatters every arm that fails
to find it. *Outcome:* **18 phrasings dropped** — 8 `paraphrase`, 7 `lexical_mismatch`,
3 `multi_keyword`. 0 call failures. Three ground truths ended with a single phrasing as a
result; they are kept, since a ground truth with one phrasing is still a valid ground truth.

**3. Measured overlap beats generator intent.** A phrasing produced under the
`lexical_mismatch` instruction whose *measured* overlap came out above
`mismatch_max_overlap = 0.15` is relabelled `paraphrase` and records `relabelled_from`.
*Outcome:* **56 of 104 mismatch attempts were relabelled** — the control fired on more than
half of them. The category a case is reported under is the one its numbers support.
`test_measurement_beat_intent_in_both_directions` asserts this in both directions.

**4. The gate was never loosened to fill a cell.** Round 1 attempted pass C on 40 ground
truths and kept 15. Rather than widen the 0.15 ceiling — which would have filled the
category by redefining it — a second incremental pass (`--top-up-mismatch`, seed
`20260830`) made **64 more attempts at the identical threshold** and kept 26, for 41. Both
rounds' attempt/keep/relabel counts are recorded in the fixture's `top_ups` block.

---

## The no-answer controls, and why their validation is not circular

18 in-scope questions that no chunk in the corpus answers: 8 carried over from
`qa_coverage_eval.yaml`'s `no_answer` category (scored on the real lane since S37) and 10
new `na-e2-*` cases written to the same shape.

Each was **validated, not asserted**. The corpus was re-embedded with real Titan, the
question's 5 nearest approved chunks were pulled by cosine distance across *every* audience
(a control the parent handbook answers is not a no-answer case for a parent), and the
answerability judge was asked about each one: **90 neighbour judgements, all "unanswerable",
0 controls dropped.** Every judgement is stored per control in `validated_neighbours`.

The judge is deliberately **not** the retrieval threshold this benchmark measures. Using
the instrument under test to validate its own negative set is the circularity that would
make the no-answer table meaningless.

---

## What this fixture cannot support — the honesty cap

**Effective n is 123, not 363.** The 363 query instances are 2–4 phrasings of 123
questions. Phrasings of one question are *correlated samples*: if the underlying chunk is
hard to retrieve, all of its phrasings tend to fail together. Every per-arm table in
`E2_REPORT.md` therefore carries both numbers, and no confidence interval is computed on
the instance count. The corpus is 20 documents / 144 approved+effective chunks / ~7.5k
words; it cannot support 250–1,000 *independent* ground truths, and this fixture does not
claim to.

**Effective n is lower still inside the bio cluster.** 36 of the 123 ground truths are
`public/our-team` staff biographies with near-identical structure. They are distinct
passages about distinct people, so single-chunk ground truth is well defined, but they are
not 36 independent tests of the retrieval *rule*.

**`near_duplicate_cluster` × `lexical_mismatch` is empty, and that is a measurement.**
Every mismatch attempt on a bio was relabelled. A bio question must keep the person's name
to identify which passage is correct, and the name is in the passage — so no phrasing of a
bio question can clear a 0.15 overlap gate. The empty cell is a property of the corpus, not
a gap in the sampling.

**Mean paraphrase overlap is high (0.481).** Even a rewriter that never saw the passage
lands close to it, because a 100–300 character policy chunk has few ways to be referred to
and proper nouns cannot be paraphrased away. Read every "paraphrase" row with that number
beside it; the `lexical_mismatch` row (mean 0.035) is the one that isolates semantic
retrieval from lexical overlap.

**Ground truth is single-chunk by construction.** The fixture format stores `chunk_ids` as
a *list* and `ir_metrics` scores set ground truth (both `recall@k` and "hit if any"), but
every entry here is a singleton, so the report's Recall@k column is also a hit rate. Where
a question could arguably be answered by a second passage, that passage counts as a miss —
which makes every recall number here a **lower bound**.

**One generator, one corpus, one language.** All questions come from Haiku 4.5 over one
English corpus. A different generator would produce a different difficulty distribution,
and nothing here generalises to another corpus.
