# Final Resume Bullets

> Written 2026-08-30, after the nine-experiment measurement program (D-458..D-465), the
> four-part remediation (D-467..D-470), and the staging deploy + smoke verification of
> `523b9f0` (`POST_REMEDIATION_STAGING_VERIFICATION.md`). Every number traces to an artifact
> under `docs/resume_evidence/`.
>
> The `Evidence / Environment / Interview caveat` lines under each bullet are INTERNAL NOTES —
> they are not part of the resume text. Pattern: ACTION + MECHANISM + MEASURED OUTCOME.

---

## Version A — Agentic AI / AI Platform / AI Engineer

**A1.** Engineered a transactional cost-reservation ledger (Postgres advisory lock,
reserve-then-settle) for an LLM gateway, cutting budget overshoot from **9.0× to 1.000×**
across 126 concurrency trials up to 200 parallel requests, and proved **0 unauthorized
external side effects across 84 human-in-the-loop bypass attempts**.

- Evidence: `03_gateway_agents/E3_REPORT.md`, `overshoot_table.csv`, `hitl_bypass_inventory.json` (D-459)
- Environment: local simulation — real Postgres lock, mock model with injected latency (250 ms–3 s), $0
- Interview caveat: single-machine asyncio concurrency, not multi-process; the 9.0× baseline is the reproduced pre-fix logic on the identical workload; one honest 1.035× admission-order edge is in the report

**A2.** Built a long-term LLM memory layer (append-only events → consolidated semantic facts
with code-verified provenance) achieving **15.82× median context compression** over 346,320
synthetic learning events — then caught a silent consolidation failure through real-model
evaluation that mock tests structurally could not see, fixed it fail-closed, and re-validated
**119 facts at 100% provenance** on the corpus that had silently produced 6.

- Evidence: `04_memory/E4_REPORT.md` (D-460), `04_memory/post_remediation/R1_POSTFIX_REPORT.md` (D-467), staging fail-closed proof in `staging_verification/` (8/8 truncations surfaced, 0 silent)
- Environment: compression = mock/synthetic at N=1,000 (provider-independent arithmetic, labeled); quality + fix = real Haiku 4.5, local isolated DB; fail-closed additionally verified on deployed staging
- Interview caveat: truncation is not eliminated — it fails closed and is reported; the staging fixture cohort still saturates the 4,000-token cap (open design decision); fact-quality findings #2–#5 (polarity, stale-fact ranking) remain open

**A3.** Load-tested a two-service FastAPI/ECS platform to **22.36 req/s sustained over 10
minutes at 0% errors** (13,550 requests, p95 3.08 s) and validated **100% cross-replica SSE
delivery (240/240 events across 3 replicas)** over Postgres LISTEN/NOTIFY — diagnosing a
capacity defect where autoscaling to a third replica exhausted the database connection ceiling.

- Evidence: `01_platform/E1_REPORT.md`, `sweep_metrics.csv`, `sse_staging_results.json`, `cloudwatch_join.json` (D-461)
- Environment: deployed staging, simulated load-test traffic (learning path makes no model calls, $0); local 2-process rig for the 1,100/1,100 tier
- Interview caveat: "validated at", never "served" — no real users; the sustained leg ran at 3 tasks (scale-in lag); the defect (STAGING-CONN-CEILING) is reported, not yet fixed

**A4.** Instrumented end-to-end observability measured at **100% per-hop trace coverage across
12,888 authenticated requests** (API → workflow → retrieval → Bedrock → DB), built a 651-probe
labeled corpus measuring PII redaction at **97.1% precision / 96.4% recall**, and closed the
gaps both measurements exposed — a trace-ID collision, an unwatched telemetry exporter, and
silent unhandled-500s (fixed fail-visible with a log-pattern alarm proven end-to-end).

- Evidence: `06_eval_observability/E6_1_REPORT.md`, `E6_2_REPORT.md` (D-458/D-464), `post_remediation/R2_POSTFIX_REPORT.md`, `R4_POSTFIX_REPORT.md` (D-468/D-470), `staging_verification/`
- Environment: PII = local offline $0 (frozen corpus); traces = deployed staging read-only over load-test traffic; the 500-alarm proof = staging with a synthetic event, nothing paged
- Interview caveat: recall is scoped to the implemented regex classes (email/URL/phone — names are governed by a separate structural allowlist layer); trace-ID collision (0.14%) is found + queued, its mechanism a labeled hypothesis; no safe real unhandled-500 trigger exists on staging, so the app-side line's staging proof is code-presence + permanent tests

**A5.** Designed a synthetic math-content pipeline (LLM generation → SymPy validation → blind
dual-solver agreement → LLM-as-judge) that cut deterministically-invalid output from **14.85%
to 4.60%** on a controlled 204-item run, and hardened its detection to **F1 0.949 at zero false
positives** across a six-class seeded-defect corpus after the benchmark exposed two gate blind
spots.

- Evidence: `05_content_generation/e5_3/E5_3_REPORT.md` (D-465), `E5_2_REPORT.md` (D-463), `post_remediation/R3_POSTFIX_REPORT.md` (D-469)
- Environment: generation = real Bedrock (Haiku 4.5 + Sonnet 4.5), isolated local DB ($7.23); detection = deterministic, $0, frozen denominators
- Interview caveat: 4.60%'s residual is a measured-open skeleton-collision class; the raw arm's "answer-key" 9.41% was a verifiability failure, not wrong answers; machine-acceptance ≠ human approval

**Ranking A (strongest → weakest): A1 → A2 → A3 → A4 → A5.**
If only four fit, drop A5 (or A4 for a content-heavy role).

---

## Version B — RAG / GenAI / ML Engineer

**B1.** Built a hybrid RAG retriever (pgvector HNSW + Postgres FTS + LLM reranking, fail-closed
with substring-verified citations) and evaluated it with an 8-arm ablation over 363 query
instances, measuring that **LLM reranking raised recall on hard lexical-mismatch queries from
70.7% to 82.9%** — while quantifying, and declining to claim, rank fusion the data showed inert
on this corpus.

- Evidence: `02_rag/E2_REPORT.md`, `ablation_metrics.csv`, `fixture_provenance.md` (D-462)
- Environment: real Titan v2 embeddings + Haiku 4.5 rerank, local corpus/DB (rolled-back transactions), $2.97
- Interview caveat: effective n ≈ 123 independent ground truths (363 instances are correlated phrasings — stated in the report); the corpus is small (7.5k words); the e2e lane scored 100%/category at n=20/37 — report it as supporting, never as the headline

**B2.** Built a long-term LLM memory layer (append-only events → consolidated semantic facts
with code-verified provenance) achieving **15.82× median context compression** over 346,320
synthetic learning events — then caught a silent consolidation failure through real-model
evaluation that mock tests structurally could not see, fixed it fail-closed, and re-validated
**119 facts at 100% provenance**.

- Evidence / Environment / Interview caveat: same as A2.

**B3.** Designed a synthetic math-content pipeline (LLM generation → SymPy validation → blind
dual-solver agreement → LLM-as-judge) that cut deterministically-invalid output from **14.85%
to 4.60%** on a controlled 204-item run, with defect detection hardened to **F1 0.949 at zero
false positives** across six seeded-defect classes.

- Evidence / Environment / Interview caveat: same as A5.

**B4.** Built the evaluation and privacy instrumentation for a K-12 LLM platform: a 651-probe
labeled corpus measuring PII redaction at **97.1% precision / 96.4% recall** (then fixing and
re-measuring its two worst gaps at zero new false positives), a 68-case golden Q&A suite gated
in CI on mock and report-only on real models, and **100% per-hop trace coverage across 12,888
requests**.

- Evidence: `06_eval_observability/` (E6.1/E6.2, R4), `apps/chat-api/tests/fixtures/qa_coverage_eval.yaml` + the shared mock/real eval driver
- Environment: PII local $0; traces staging read-only; golden-set real lane = real Haiku 4.5 (~53–77¢/run), mock lane CI-gated
- Interview caveat: mock-lane gates measure plumbing, not model quality — real-lane numbers are reported, deliberately un-gated ("a threshold invented before the first measurement is a guess dressed as a gate"); PII recall scope as in A4

**B5.** Engineered a transactional cost-reservation ledger for an LLM gateway, cutting budget
overshoot from **9.0× to 1.000×** at up to 200 concurrent requests, with **0 unauthorized
external side effects across 84 human-in-the-loop bypass attempts**.

- Evidence / Environment / Interview caveat: same as A1.

**Ranking B (strongest → weakest): B2 → B5 → B3 → B1 → B4.**
Lead with B1 only when the role is explicitly retrieval-centric; its honest scale (n≈123) is
the set's smallest. If only four fit, drop B4.

---

## Cross-version rules

- Never merge numbers across bullets; each is independently traceable with its denominator.
- Load and traffic are always "validated at N" (simulated load-test traffic), never "served N".
- Do not claim RRF/hybrid-fusion gains, duplicate-free generation, or name-detection in PII.
- The interview-defense pack is `RESUME_INTERVIEW_DEFENSE.md`.
