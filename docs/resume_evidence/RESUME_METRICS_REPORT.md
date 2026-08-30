# Resume Metrics Report

> Written 2026-08-29 by the resume-evidence measurement program (D-458..D-465), from the
> artifacts of nine executed experiments. Every number below traces to a file under
> `docs/resume_evidence/`. Environments are labeled and never blurred; simulated load is
> called load-test traffic; mock-model results are never headlined as quality.
>
> Program contract: [MEASUREMENT_PLAN.md](MEASUREMENT_PLAN.md). Recommended bullets:
> [RECOMMENDED_RESUME_BULLETS.md](RECOMMENDED_RESUME_BULLETS.md).

## Summary table

| Theme | Previous evidence | New measurement | Baseline | Result | Improvement | Sample size | Environment | Confidence | Resume-worthy? |
|---|---|---|---|---|---|---|---|---|---|
| **1 Platform / load** | "uses ECS/RDS/Terraform" | Steady-state RPS + cross-replica SSE at scale + a capacity defect | prior burst-only p95s | **22.36 req/s / 10 min / 0 5xx**; SSE **240/240** across a 93/93/93 three-replica split | first sustained-throughput number; SSE proven at 24× the prior hand probe | 13,550 req; 1,340 SSE events | deployed staging (load-test traffic) + local 2-proc | High | **A** |
| **3 Gateway / cost / HITL** | "10×→1× on 10 requests" | Overshoot ratio 10→200 concurrent, before/after; HITL bypass denominator | pre-D-110 read-then-act **9.0×** | **1.000×** overshoot to 200 concurrent (0 errors); **0/84** HITL bypasses | 9.0× → 1.0× | 126 overshoot trials; 84 bypass cases | local sim (real Postgres lock) | High | **A** |
| **4 LLM memory** | "20K/4-call design limits" | Compression at N=1,000 + a real-model quality defect | raw event history | median **15.82× compression**; found a **0-facts-exit-0 truncation defect** | defect invisible to the mock; 367 facts at raised budget | 346,320 events / 1,000 students; 20 real | mock (scale) + real Haiku (quality) | High | **A** |
| **5 Content generation** | "generated 958 items" | Raw-vs-validated defect rate; 6-class detection F1; funnel | raw LLM generation | **14.85% → 4.60%** defective; detection **F1 0.837**; **90%** unique paid-stage catches | 3.2× fewer defects; every SymPy-checkable family → 0.00% | 204 gen + 102 defects + 1,827 funnel | real Bedrock, isolated local DB | High | **B** |
| **2 RAG / retrieval** | small pass/fail sets | First IR metrics (Recall@k/MRR/nDCG), 8-arm ablation | vector-only / no-rerank | reranker lifts lexical-mismatch **70.7% → 82.9%**; RRF inert here | reranker is the stage that pays; e2e 100%/category | 123 GT / 363 instances | real Titan + Haiku, local | Medium (small corpus) | **C** |
| **6 Eval / observability / PII** | 100 PII tests, 99.9% join | PII precision/recall over a labeled corpus; per-hop trace coverage | identity (no redaction) | PII regex **precision 97.0% / recall 94.2%**; **100%** per-hop trace coverage; found a trace-ID collision | first PII precision/recall; D-400's join generalized | 651 PII cases; 12,888 traces | local ($0) + staging read-only | High | **B** |

Total measured spend across all paid experiments: **~$18** (E2 $2.97, E4 ~$2.6, E5.2 $1.31,
E5.3 $7.23, E6.2 ~$0; E5.1/E6.1/E3/E1.1 were $0). Nine experiments, ~110 new tests, zero
product-code change, every DB touched left byte-identical.

---

## Theme 1 — Production platform / load

**What was measured.** Sustained throughput and cross-replica event-delivery correctness on
deployed staging, plus the saturation knee. **Why it matters.** A resume that lists ECS/RDS
proves nothing about scale; a measured RPS, a p99, and a distributed-correctness proof do.
**Experiment.** A new `constant-vus` k6 scenario + repeat-trial burst sweep (10/25/50 VUs × 3)
joined to CloudWatch; a two-process local LISTEN/NOTIFY rig and a CloudFront-auth staging SSE
harness. **Workload.** 13,550 requests over a 10-minute sustained leg; 1,100 local + 240 staging
SSE events. **Baseline.** The prior evidence was burst-only single-run p95s and a 10-round hand
probe. **Result.** 22.36 req/s, 0 5xx, warm p95 3,081 ms; SSE 1,100/1,100 local (550 crossing a
real Postgres NOTIFY under load) and 240/240 across a 93/93/93 three-replica split with 0 lost /
0 duplicate / 0 reconnect. **Failure modes observed.** `STAGING-CONN-CEILING` — at 50 VUs the ALB
step policy scales learning-api 2→3 tasks and the third replica's pool crosses db.t4g.micro's
~112-connection ceiling (`asyncpg.TooManyConnectionsError`): scale-out reduced availability,
D-334's shape, distinct from D-455; CloudWatch's 1/min sampling never saw the sub-minute refusal.
**Limitations.** Two fixture students cycled; ≤3-task autoscale ceiling; one build, one day; the
sustained leg began at 3 tasks (D-182 scale-in lag). **Evidence.** `01_platform/E1_REPORT.md`,
`sweep_metrics.*`, `sse_*_results.json`, `cloudwatch_join.json`. **Recommended claim.** See bullets.

## Theme 3 — Bedrock gateway / cost controls / agentic safety

**What was measured.** Budget-overshoot ratio under concurrency with a real before/after, circuit-
breaker behavior under a sustained outage, and a HITL-bypass denominator. **Why it matters.** Cost
bugs are production bugs; "no unauthorized external actions" needs a denominator. **Experiment.** A
252-trial latency-injecting benchmark (N ∈ {10,50,100,200} × 3 ceiling shapes × fixed-vs-baseline
× 3 delay arms) driving the real transactional reservation ledger; a failure matrix through the
real gateway; three permanent bypass suites with a cross-checked inventory. **Baseline.** The
reproduced pre-D-110 read-then-act logic. **Result.** The shipped ledger holds **1.000× overshoot
in all 36 divisible-ceiling cells, 0 errors, 0 grants-beyond-capacity across 126 trials**; the
baseline reaches **9.0×**; the circuit breaker suppressed **96% of provider calls** under outage
and never opened on 300 schema failures; **84 HITL bypass attempts → 0 unauthorized external side
effects**. **Failure modes observed.** A 0 ms mock control quantifies D-110's 36% mock-speed
under-report (why latency injection is mandatory); one honest 1.035× on the report ceiling from an
admission-order property. **Limitations.** Single-machine asyncio concurrency, not multi-process.
**Evidence.** `03_gateway_agents/E3_REPORT.md`, `overshoot_table.csv`, `failure_matrix.csv`,
`hitl_bypass_inventory.json`.

## Theme 4 — Long-term LLM memory

**What was measured.** Consolidation compression at population scale (provider-independent) and
memory *quality* with the real model. **Why it matters.** The 20K/4-call design limits are inputs,
not outcomes; the value is the compression and whether it preserves information. **Experiment.** A
seeded synthetic-history generator with planted ground truth; a mock arm at N=1,000 for
token/compression/lifecycle accounting; a real Haiku 4.5 arm at N≈20 for fact quality.
**Baseline.** Raw event history. **Result.** Median **15.82× compression** (p10 12.77 / p90 19.29)
with **17,429/17,429** provenance; **40/1,000** raw histories exceed the 32k input ceiling
outright. **Failure modes observed.** The headline is a defect, honestly: under the shipped output
budget the real model truncates on 29/30 calls, Bedrock returns `{}`, the schema validates it as
an empty update, and **10/10 students consolidate three weeks into 0 facts with exit 0** — invisible
to the mock (0/3,135); raising the budget produced 367 facts on the same corpus. Plausibly a second
mechanism behind the deployed-staging "0 facts added" (AUDIT_2026_08_16/D-208). **Limitations.**
Mock-arm lifecycle correctness measures deterministic code, not model judgment; real arm n=20.
**Evidence.** `04_memory/E4_REPORT.md`, `mock_summary.json`, `real_*_summary.json`.

## Theme 5 — Synthetic content generation

**What was measured.** The quality delta the validation pipeline produces (raw vs validated), the
pipeline's defect-detection F1 across six classes, and the per-stage funnel over the complete
generation history. **Why it matters.** "958 items" is output volume; the engineering value is the
defect rate the pipeline removes. **Experiment.** A user-authorized isolated 204-candidate
`run_plan` (E5.3), a 102-defect × 6-class mutation benchmark (E5.2), and a funnel over 1,827
persisted validation runs (E5.1). **Baseline.** Raw schema-valid generator output.
**Result.** Raw generation carries a deterministic defect in **14.85%** vs **4.60%** validated
(3.2× reduction, every SymPy-checkable family → 0.00%); detection **F1 0.837** (recall 72/100,
precision 1.000, 0/102 clean FP); **90.0%** of paid-stage rejections were unique catches the free
gate would not make. **Failure modes observed.** The residual 4.60% is entirely a dedup blind spot
(same-skill different-tier duplicates the predicates can't see — E5.2 and E5.3 converge on this);
`mismatched_hint_ladder` is undetectable by every current detector; 6 genuine duplicate pairs were
found already in the approved bank. **Limitations.** Machine-acceptance ≠ human approval; one run,
one roster. **Evidence.** `05_content_generation/{E5_1_REPORT.md, E5_2_REPORT.md, e5_3/E5_3_REPORT.md}`.

## Theme 2 — RAG / retrieval

**What was measured.** The repository's first IR metrics and an 8-arm ablation isolating each
retrieval stage's contribution. **Why it matters.** Small pass/fail sets can't say what hybrid
search, RRF, or reranking actually buy. **Experiment.** A 123-ground-truth / 363-instance
chunk-level fixture (with a measured-overlap honesty gate that relabelled 56/104 too-easy
lexical-mismatch attempts) and an ablation harness with a two-way drift guard against real
`retrieve()`. **Baseline.** Vector-only / no-rerank arms. **Result.** The reranker is the one stage
that clearly pays (+20/−10 at rank 1, its gain concentrated on lexical-mismatch **70.7% → 82.9%**);
**RRF is inert-to-net-negative on this corpus** (k ∈ {20,60,120} give identical rankings on
363/363); the real-model e2e scored 100% in every category. **Failure modes observed.** 3 no-answer
controls leak at rerank scores 0.75–0.90 (a relevance score is not a full answerability gate).
**Limitations.** The 7.5k-word corpus supports ~123 independent ground truths, not the 250–1,000 the
brief imagined — stated, not inflated. **Evidence.** `02_rag/E2_REPORT.md`, `ablation_metrics.csv`.

## Theme 6 — Evaluation / observability / privacy

**What was measured.** PII-redaction precision/recall over a labeled corpus (the theme's missing
number), and per-hop request-trace coverage on staging. **Why it matters.** "100 PII tests" and
"99.9% join" don't say how well the redactor separates PII from look-alikes, or whether a request
traces end-to-end. **Experiment.** A 651-case labeled PII corpus (277 in-contract positives, 264
negatives — the negative half existed nowhere before) driven through three redaction layers; a
per-hop coverage harness over two pinned staging windows. **Baseline.** The identity function (no
redaction). **Result.** Regex layer **precision 97.0% (261/269), in-contract recall 94.2%
(261/277), F1 95.6%**; **100.00% per-hop trace coverage (12,888/12,888)** with 0% missing-span on
every instrumented hop. **Failure modes observed.** `TRACE-ID-COLLISION` — 0.14% of requests share
an OTel trace_id and X-Ray merges them; five PII findings (F-1 case-insensitive URLs, etc.); the
MCP hop and collector export-rate could not be measured and are stated as such. **Limitations.**
The regex layer covers email/URL/phone only (names are the structural-allowlist layer's job);
trace windows are one build, one day, load-test traffic. **Evidence.**
`06_eval_observability/{E6_1_REPORT.md, E6_2_REPORT.md}`.

---

## Ranking (hiring-manager view, strongest → weakest)

**A — exceptional resume evidence**
1. **Theme 3 (gateway/cost/HITL).** A real before/after (9.0× → 1.0×) at 200-concurrent scale on
   the actual transactional ledger, plus a 0/84 safety denominator. Distributed-systems + cost +
   safety, all measured, with a negative control that catches the common mock-speed lie.
2. **Theme 1 (platform).** First sustained RPS, cross-replica SSE proven at scale on real
   infrastructure, and a capacity defect found *and* root-caused (scale-out reduces availability).
   Production-like workload + distributed correctness + failure diagnosis.
3. **Theme 4 (memory).** A real-model evaluation that found a silent 0-facts-exit-0 defect the mock
   structurally could not see, alongside a 15.82× compression measured at 1,000-student scale. The
   clearest "tested like a real system" story in the set.

**B — strong resume evidence**
4. **Theme 5 (content generation).** A controlled 14.85% → 4.60% raw-vs-validated defect reduction
   on real generation, backed by an F1 of 0.837 and a 90%-unique-catch funnel. Slightly narrower
   appeal (content quality), but genuinely measured before/after.
5. **Theme 6 (eval/obs/PII).** First PII precision/recall (97.0%/94.2%) over a purpose-built
   labeled corpus, and 100% per-hop trace coverage that generalized a narrow prior join — plus a
   real trace-ID collision the coverage number would have hidden.

**C — useful supporting evidence**
6. **Theme 2 (RAG).** Intellectually the most honest result — the reranker measurably lifts
   lexical-mismatch retrieval while RRF is shown inert on this corpus — but the 123-ground-truth
   corpus caps its headline scale. Cite the reranker gain (70.7% → 82.9%), not a hybrid/RRF win.

**D — too small / weak for a headline:** none. Every theme produced at least one defensible
measured number; the weakest (Theme 2) is rescued by its candor and a real positive metric.

## The most important question, answered

*"If an experienced AI systems engineer saw this, would they believe this project has been tested
like a real system?"* — Yes, and specifically because the measurements found real defects
(`STAGING-CONN-CEILING`, `MEMORY-OUTPUT-TRUNCATION`, `TRACE-ID-COLLISION`, the hint-ladder and
dedup blind spots) and reported honest negatives (RRF inert, PII regex gaps, a mock that hides a
production failure) rather than only flattering numbers. The credibility is in the candor.
