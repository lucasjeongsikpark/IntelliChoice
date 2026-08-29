# Resume-Evidence Measurement Plan

> Created 2026-08-28 at repository `7a486a9` (deployed staging: `gha-5fa15d491057`, D-448).
> Purpose: produce defensible, artifact-backed quantitative evidence for six resume themes.
> This is a measurement program, not product work — nothing here changes product behavior,
> touches production, or publishes benchmark content into the approved bank.
>
> Evidence rules bound into every experiment (from the commissioning request):
> - Every number traces to a saved artifact (JSON/JSONL/CSV + Markdown report + git SHA + date).
> - Rates always carry numerator AND denominator. Latency carries p50/p95/p99.
> - Environments are never blurred: `production` (never touched) / `deployed staging` /
>   `local` / `simulation` / `real-model eval` / `mock-model eval` — each result is labeled.
> - Simulated load is always described as load-test traffic ("validated at N concurrent
>   users", never "served N users").
> - Mock-model results are never headlined as quality results (the AUD-C-05 lesson: the
>   thing a mock eval measures is the mock).

## Directory layout

```
docs/resume_evidence/
  MEASUREMENT_PLAN.md          (this file)
  RESUME_METRICS_REPORT.md     (final report — written after measurement)
  RECOMMENDED_RESUME_BULLETS.md (final bullets — written last)
  01_platform/ 02_rag/ 03_gateway_agents/ 04_memory/
  05_content_generation/ 06_eval_observability/   (per-experiment evidence)
benchmarks/resume_evidence/    (reusable harness code, mirrored subdirs)
```

Each experiment directory preserves: description, git SHA, timestamp, environment,
configuration, exact commands, dataset definition, raw output (machine-readable),
processed metrics, model IDs, and limitations.

## Cost tiers and the spend decision

| Tier | Definition | Total estimated model/API cost |
|---|---|---|
| Tier 1 | deterministic / local / mock-model / analysis of already-persisted data | **$0** |
| Tier 2 | real embeddings + small real-model runs inside existing budget caps | **~$5–9** |
| Tier 3 | the isolated 200-candidate content-generation run | **~$5–10, ~2.2 h wall clock** |

Standing constraints honored throughout: D-152 (integration frozen — nothing here touches
`../IntelliChoice-web` or production reachability), D-342 (no coverage-driven generation;
Tier 3 is a quality-measurement run into an isolated database, produces nothing approvable,
and still requires the user's explicit spend authorization because D-342's rationale —
"generation costs real money and real wall clock; it is the user's call" — is spend-general),
UD-14 (⚠️ the ≈2026-09-04 RDS secret rotation re-breaks staging's new DB connections; any
staging measurement after that date must be preceded by the D-455 force-new-deployment
mitigation), and the shared-dev-Postgres rule (never run `make test` concurrently with
local load/e2e harnesses).

---

## Theme 1 — Production AI platform / infrastructure

**Existing evidence (strong).** All measured on deployed staging through CloudFront unless
noted. D-456 (2026-08-29, `gha-5fa15d491057`): learning path 0.00% errors at every level
tested — 1,400/1,400 requests and 1,000/1,000 answers at 100 concurrent VUs (autoscaled
2→3 tasks mid-ramp), warm p95 3.03 s at 25 VUs. D-134/D-136: a published capacity law
`p95 ≈ 0.31 s × (r/2.5)^1.4` (r = concurrent users/task, valid r ∈ [2.5, 12.5]), throughput
saturation at ~5 concurrent/task, Little's law within 4%. AUD-F-28: a before/after capacity
change — 1×(256/512) → 2×(512/1024) took p95@25 from 9.98 s → 2.45 s and throughput
5.8 → ~17.5 req/s (3.0×), errors@150 from 12.06% → 0.04%. Cross-replica LISTEN/NOTIFY:
delivery 3/6 (50%) before the relay → 8/8 and 10/10 after, with a 12/8 POST split across
two tasks proving real cross-replica traffic (D-335/D-349). D-455: a real incident (RDS
managed-secret rotation vs ECS task lifetime) found by load, root-caused, mitigated, and
re-measured to 0.00% the same day.

**Weaknesses.** (1) No sustained-throughput or soak evidence — every k6 scenario is
`per-vu-iterations` (a burst snapshot); no RPS number is produced by any harness.
(2) SSE/event delivery has never been measured at scale on staging (`sse_load.py` is
localhost-only; k6 opens no streams). (3) Cross-replica correctness was measured at ~1
concurrent (10 sequential rounds), never while both replicas are loaded — exactly the
regime where the single publisher connection and the fire-and-forget drop path would bite.
(4) Single-run p95s, no repeat trials.

**Proposed experiments.**
- **E1.1 — Sustained-load + repeat-trial sweep (deployed staging, learning path, $0 model
  spend — this path makes no model calls by design).** Extend
  `load-tests/k6/learning_sessions_staging.js` with a `constant-vus` + duration scenario
  and an RPS threshold; run 3 trials each at 10/25/50 VUs plus one 10-minute sustained run
  at 25 VUs. Report per level: requests, success rate (n/N), RPS, p50/p95/p99, timeout and
  4xx/5xx rates, ECS CPU/memory (Container Insights), RDS `DatabaseConnections`, task count
  over time, cold vs warm split, median across trials.
- **E1.2 — Cross-replica SSE delivery at scale (new harness).** Local tier first: two real
  uvicorn processes sharing one Postgres, hold 50 SSE streams while driving 20 events each
  → assert delivery completeness out of 1,000 expected events, under concurrent k6 load.
  Staging tier second: a staging-capable variant of `sse_load.py` (CloudFront auth path)
  against learning-api's 2 real tasks, target ≥ several hundred events with per-event
  delivery accounting — replacing the current 10-round probe as the headline.
- **E1.3 — Saturation point.** The sweep already brackets it (throughput flattens ~5
  concurrent/task; autoscaling ceiling is 3 tasks) — report the measured knee rather than
  pushing past the 3-task Terraform ceiling (raising it is product work, out of scope).

**Sample size/load:** 10/25/50 VUs × 3 trials + 1×10-min sustained; 1,000+ SSE events.
**Environment:** deployed staging (learning path) + local 2-process rig.
**Cost:** $0 model spend; negligible infra. **Safety:** staging only, prior-precedented
levels (≤100 VUs already run 2026-08-29); no chat-path load re-run needed (D-456 stands).
**Artifacts:** k6 JSON summaries per trial, CloudWatch metric exports, SSE delivery ledger
(JSONL), report. **Before/after:** the resize (AUD-F-28) and relay fix (D-335/D-349) are
already recorded before/afters; E1.2 adds scale to the "after".

---

## Theme 2 — RAG / retrieval

**Existing evidence.** 68-case golden Q&A set scored on mock and real lanes through one
shared driver; best full real-Bedrock run: correct_refusal_rate 36/37 (97.3%),
grounded_citation_rate 17/20, paraphrase 11/11, adversarial 6/6. Relevance floor chosen by
a paid sweep (at 0.30–0.35: 20/20 answerable kept, 24/24 unanswerable emptied). Embedding
provenance fix measured live: paraphrase citation 1/7 → 9/9. Access probe: 27/38 recall at
5/5 precision, 0 wrong tiers, keyword-only arm 1/38 (an accidental hybrid ablation).

**Weaknesses.** No IR metrics exist at all (no Recall@k, MRR, nDCG anywhere); ground truth
is document-level over only 3 documents; end-to-end numbers conflate classifier failures
with retrieval failures; no ablation of hybrid/RRF/reranker contribution.

**Proposed experiments.**
- **E2.1 — Chunk-level benchmark fixture.** Extend the existing generator
  (`scripts/generate_probe_eval_fixture.py` pattern, with its blind-rewrite and
  lexical-overlap controls) to build **~120 chunk-level ground truths × 2–4 phrasings
  (≈250–400 query instances)** over the 144 approved+effective chunks, stratified: exact
  lookup / paraphrase / lexical mismatch / multi-keyword / near-duplicate (staff-bio
  cluster) / authorization-boundary / no-answer. **Honesty cap: the corpus (7,526 words,
  144 chunks, ~55 near-duplicate bios) cannot support 250–1,000 *independent* queries;
  the report states effective n ≈ 120 with paraphrase-family correlation.**
- **E2.2 — Retrieval ablation harness** (~300 lines, modeled on
  `scripts/measure_retrieval_score_floor.py`, including its `--verify-against-retrieve`
  drift guard — the AUD-C-25 lesson). Arms: FTS-only / vector-only / hybrid without RRF
  (interleave) / hybrid+RRF (k sweep) / hybrid+RRF+rerank. Metrics per arm: Recall@1/3/5/10,
  MRR, nDCG@10, retrieval latency p50/p95, candidate counts. Real Titan embeddings; rerank
  arm on real Haiku 4.5. Two-phase `--dump/--load` so re-scoring is free.
- **E2.3 — End-to-end real-model eval re-run** (existing paid lane) at this SHA for current
  grounded-answer rate, citation precision, refusal correctness with denominators.

**Sample size:** ~120 ground truths / 250–400 instances. **Environment:** local Postgres +
real Bedrock models (real-model evaluation, local environment — labeled as such).
**Cost:** fixture generation ~$0.5–1; embeddings ~pennies; rerank arm ~0.3¢ × instances
≈ $1–1.5; e2e lane ~$0.6–0.8 → **~$2.5–4 total**, inside existing per-run caps.
**Safety:** rolled-back transactions / isolated local DB; no KB contamination.
**Artifacts:** fixture YAML with provenance, per-arm ranking dumps (JSONL), metrics CSV,
report. **Before/after:** yes — vector-only baseline vs hybrid vs +RRF vs +rerank.

---

## Theme 3 — Bedrock gateway / agentic workflows / cost controls

**Existing evidence.** Reserve-then-settle ledger (Postgres advisory lock): the recorded
D-110 arc — 8.0× ceiling overshoot live at n=10 concurrent (pre-fix), 10.0× reproduced
under a 250 ms call window, **1.0× after the fix**, and a lock-removal control granting
10/10 against a ceiling of 3. Checked-in concurrency tests max out at n=30 (circuit
breaker: 30 concurrent failures → exactly 5 provider calls + 25 CircuitOpenError). 43
gateway resilience tests; 10 MCP registry tests; HITL bypass denominator today: **1**
explicit bypass attempt (7 counting the replay/deny family).

**Weaknesses.** Nothing above n=30; no overshoot *ratio* computed by any harness; the
250 ms latency-injection trick that made D-110's probe honest lives only in prose; only 1
of 3 ceilings concurrency-tested; HITL bypass denominator far too small to claim "0/N";
429/5xx/AccessDenied indistinguishable in retry policy (a finding to report, not fix here).

**Proposed experiments (all Tier 1, $0).**
- **E3.1 — Concurrency/overshoot benchmark.** New harness with a `DelayedProvider`
  (250 ms floor; a realistic 3–27 s arm, from measured real p50s) driving
  `CostReservationRepository.reserve` at N ∈ {10, 50, 100, 200} concurrent against
  ceilings admitting k; report granted/rejected (n/N), **overshoot ratio spend/ceiling**,
  duplicate-grant count, race failures, throughput. Cover all three ceilings
  (report/tutor-chat/chat-turn shapes). Postgres-backed (real advisory lock), local.
- **E3.2 — Baseline reproduction (before/after).** Reproduce the pre-D-110 read-then-act
  logic in the isolated harness (never in product code) and run the identical workload:
  overshoot ratio before vs after at each N.
- **E3.3 — Failure-injection matrix under concurrency.** Timeout / provider-error /
  malformed / truncation bursts at N ∈ {30, 100}: recovery rate, retry amplification
  (provider calls per logical request), circuit-breaker activation and half-open recovery
  time, final failure rate.
- **E3.4 — HITL bypass suite.** Build the missing denominator as permanent tests:
  malformed/hostile resume payloads (`{}`, `{"approved":"yes"}`, wrong discriminator,
  extra fields), wrong-type resume after graph advance, two concurrent `/respond` calls at
  one pause (the advisory-lock race — "exactly one email"), cross-session thread
  substitution, learning-api replay (no dedupe claim exists there today — may surface a
  real defect), direct `registry.call()` outside an approved resume, expired/stale
  checkpoint resume. Target **N ≥ 50 distinct bypass-attempt cases**, asserting 0 external
  side effects and the `interrupt_approvals` row invariant, with the denominator recorded.
- **E3.5 (optional Tier 2, ~$0.90)** — 200 real-Bedrock report-path calls validating the
  ledger under genuine model latency (reusing the three-ceiling spend-guard pattern).

**Environment:** local (in-process + docker-compose Postgres); simulation labeled as such.
**Artifacts:** per-N JSONL ledgers, overshoot table, failure-matrix CSV, new pytest files.
**Before/after:** yes — read-then-act vs transactional reservation, same workload.

---

## Theme 4 — Long-term LLM memory

**Existing evidence.** All cost/bounds, none quality: 20K-token/4-call bounds
(`consolidation.py`), the 5.9× cost re-tune (66.18¢ → 11.24¢ for the same students), ~2–3¢
per student-week projected real rate, 58 tests, a weekly EventBridge schedule confirmed
firing 2026-08-23. The AUD-F-34 incident (a 215,355-token prompt from 13,865 raw events —
every call failed) is itself the strongest argument for the architecture.

**Weaknesses.** Zero measurement of memory *quality* or of consolidated-vs-raw value:
no compression ratio, no fact recall, no contradiction-resolution accuracy. No synthetic
student-history generator exists.

**Proposed experiments.**
- **E4.1 — Synthetic-history generator + mock-lane pipeline benchmark (Tier 1, $0,
  N = 1,000 students).** New ~200-line generator writing `LearningEvent` rows directly
  (closed 6-type event vocabulary, settable `occurred_at`/`session_id`), with planted
  ground truth per student: repeated facts, conflicting facts, superseded facts,
  mastery-contradicting claims, irrelevant history; distributions anchored to the recorded
  shapes (30–68 events/session; heavy-tail chat students). Measure (all deterministic,
  provider-independent): **compression ratio** (raw rendered-event tokens → live fact
  tokens, exact via `_summary_chars`), tokens and calls per student, events dropped,
  lifecycle-state distribution, contradiction/lifecycle transitions vs planted truth,
  provenance coverage (facts with verified evidence / total).
- **E4.2 — Real-model quality run (Tier 2, ~$2–3, N ≈ 25 students, Haiku 4.5).** Same
  planted-ground-truth design against real Bedrock: planted-fact recall, stale/unsupported
  fact rate, contradiction-resolution correctness, cost/student — the only honest source
  for quality numbers (the mock's facts are correct by construction).
- **E4.3 — Raw-history-vs-consolidated context comparison.** Token/cost arithmetic is free
  and exact (arm B token counts measured from the same synthetic corpora); report the
  compression + the structural finding that raw histories above the 32K gateway input
  ceiling **cannot be sent at all** (already live-evidenced at 215K tokens). A small
  real-model downstream-quality probe (does the tutor payload carry the right fact) rides
  inside E4.2's budget.

**Environment:** local Postgres; mock-model (labeled) for scale, real-model for quality.
**Cost:** $0 + ~$2–3. **Safety:** synthetic students only, external-id strings, no PII.
**Artifacts:** generator + fixture definitions (seeded, reproducible), per-student JSONL,
metrics CSV, report. **Before/after:** yes — raw events vs consolidated memory, same
histories.

---

## Theme 5 — Synthetic content generation

**Existing evidence (richest of the six).** 958 approved items / 99 of 99 authorable skills
(D-312); 4.7¢ per accepted item ($24.97 for 529 pipeline items); acceptance 35–91% by wave
(63% on the correctly-shaped large run); seeded-defect controls 12/12 (wrong answer keys,
solver panel) and 32/32 (hint leaks); the D-276 natural ablation — with the deterministic
gate off, 5 wrong answer keys shipped and **all five passed both blind solvers and the
judge** (SymPy is irreplaceable); reviewer precision 6/6, recall ~43%; 1,184 persisted
validation runs with full candidate snapshots for every rejection.

**Weaknesses.** No controlled raw-vs-validated arm on matched slots; no per-stage
"what would have shipped without this stage" table (computable for $0 from persisted
snapshots); negative controls cover only one defect class (answer-key corruption) at n=12.

**Proposed experiments.**
- **E5.1 — Per-stage funnel analysis over persisted data (Tier 1, $0).** Over the 1,184
  `question_validation_runs` rows + snapshots: stage-attributed rejection funnel, per-stage
  marginal catch rate, "counterfactual ship rate" per removed stage, combined with the
  recorded 12/12 / 32/32 / 5-of-5-missed evidence into one defect-containment table.
- **E5.2 — Expanded seeded-defect benchmark (Tier 2, ~$1–2).** Deterministically mutate
  existing bank items into **n ≥ 100** labeled defects across classes: wrong numeric answer,
  no-correct-option, duplicate/near-duplicate, mismatched hint, mismatched solution,
  contradictory constraints. Run the deterministic gate + solver panel over defects AND an
  equal-size clean control set; report precision/recall/F1 and FP/FN rates per defect class
  (solver calls ~0.34¢ × 2 × n). This upgrades "12/12" to a real detection-quality claim.
- **E5.3 — Isolated raw-vs-validated generation run (Tier 3, ~$5–10, ~2.2 h, requires
  explicit user spend authorization).** **200 candidates** in ONE `run_plan` invocation
  (the recorded 63%-yield shape) against an isolated `DATABASE_URL`, fresh reserved
  `--seed-offset`, `--run-budget-cents` inside the existing $10 hard cap. Raw arm = every
  schema-valid generator output; validated arm = full pipeline. Ground truth: SymPy
  re-derivation (deterministic, free) on all items + hand audit of a stratified sample.
  Report invalid-content rate raw vs validated, per-stage catches, cost per accepted item,
  throughput. **Nothing is approved, exported, or counted toward any coverage target**
  (D-342-clean by subject; spend still the user's call). 500–2,000 candidates is rejected
  as infeasible/imprudent: 2,000 ≈ $50–102 and ~22 h serialized wall clock on an account
  where 3 parallel streams equal 1.

**Environment:** local isolated DB; real Bedrock (D-273 roster; re-verify invocability
first — the recorded 2026-08-11 stratum expired by its own rule). **Artifacts:** funnel
CSVs, mutation corpus with labels, run summaries, snapshots, report. **Before/after:**
yes — raw generation vs validated pipeline on the same slots.

---

## Theme 6 — LLM evaluation / observability / privacy

**Existing evidence.** 1,873 tests on every PR; 68-case golden set with 5 CI-gated category
thresholds; 49 SPEC eval items registered, 46 covered, drift-tested; 100 PII tests (59
reflection-driven payload-governance tests over 28 payload types); trace-to-spend join
coverage 99.9% (2,209/2,212 + 297/299); the AUD-F-12 export-failure find (collector
silently discarding 100% of spans → 0 → 650 traces after fix); LangSmith quota exhaustion
classified on 4,264 log lines.

**Weaknesses.** PII-redaction precision/recall does not exist (the redactor has 5 unit
tests; no labeled corpus; no negative set anywhere); trace coverage is measured for one
join, not per-hop; SILENT-500S (unhandled 500s invisible to JSON-log alarms) is the known
open observability gap with live proof (114 tracebacks, zero ERROR events).

**Proposed experiments.**
- **E6.1 — Synthetic PII probe corpus (Tier 1, $0, CI-ready).** A labeled corpus of
  **~600–1,000 cases**: positives (emails, phones, URLs with punctuation/Unicode/spacing
  edge forms, plus combinations) and — the half nothing in the repo has — negatives (math
  expressions, dates, ISO timestamps, IDs, versions, currency, coordinates). Drive all
  three callable layers offline: `redact_free_text`/`contains_pii_pattern`, the JSON log
  formatter + denylist filter, the span-export redactor. Report TP/FP/FN, precision/
  recall/F1 per pattern class. **Scope stated honestly: the regex layer implements
  email/URL/phone by design (no name detection); names/IDs are governed by the structural
  payload-allowlist layer, which is measured separately by its 59 reflection tests and the
  47-needle live scanners.** Lands as a permanent pytest lane in the existing CI gate.
- **E6.2 — Per-hop trace coverage measurement (Tier 1, ~$0).** For a pinned staging
  traffic window (E1.1's run doubles as the corpus): % of authenticated requests with
  complete span chains across API → LangGraph node → SQLAlchemy → Bedrock → MCP hops,
  missing-span rate per hop, export-failure rate from collector stats; via existing
  `make scan-traces` / X-Ray reads.
- **E6.3 — Safety containment denominators.** No new experiment: consolidate theme-2/3
  results (adversarial containment n, HITL bypass n≥50, injection cases) into one
  safety-evaluation table with denominators.

**Environment:** local + deployed staging reads. **Cost:** $0 (X-Ray reads pennies).
**Artifacts:** labeled probe corpus (committed, with generation provenance), metrics CSV,
trace-coverage JSONL, report. **Before/after:** partial — redacted vs unredacted is
directly measurable (run the corpus through the identity function as baseline); trace
coverage has the recorded 0→650 export incident as its historical before.

---

## Execution order

1. **Tier 1 (all $0, start immediately):** E5.1 (funnel over persisted data), E6.1 (PII
   corpus), E3.1–E3.4 (gateway concurrency + HITL denominator), E4.1 (memory mock at
   N=1,000), E1.1/E1.2-local (sustained load + SSE-at-scale local rig).
2. **Tier 2 (~$5–9 total, on user authorization):** E2.1–E2.3 (retrieval benchmark +
   ablations + e2e eval), E4.2 (memory real-model quality, N≈25), E5.2 (seeded-defect
   n≥100), E1.2-staging (SSE staging tier), E6.2 (trace coverage), E3.5 (optional).
3. **Tier 3 (~$5–10 + 2.2 h, separate authorization):** E5.3 (isolated 200-candidate
   raw-vs-validated generation run).
4. Write `RESUME_METRICS_REPORT.md` (with the required summary table and A–D ranking) and
   `RECOMMENDED_RESUME_BULLETS.md` last, from artifacts only.

Implementation runs through the project's Orca coordinator/executor workflow (one Frozen
Spec per experiment cluster); harness code follows repo conventions (typed, tested,
`make lint typecheck test` green) and lands under `benchmarks/resume_evidence/` +
`scripts/` as appropriate.
