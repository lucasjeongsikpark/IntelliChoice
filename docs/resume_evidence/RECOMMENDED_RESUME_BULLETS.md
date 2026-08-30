# Recommended Resume Bullets

> Written 2026-08-29 from the nine measured experiments (D-458..D-465). Each bullet's numbers
> trace to a file under `docs/resume_evidence/`; the full report is
> [RESUME_METRICS_REPORT.md](RESUME_METRICS_REPORT.md).
>
> **Honesty guardrails baked into these bullets.** Load is always "validated at N", never
> "served N" (the traffic was load-test traffic, not real users). Nothing claims a hybrid/RRF
> retrieval win — the measurement showed RRF inert on this corpus, so the retrieval bullet cites
> the reranker gain only. "Deployed staging" and "local benchmark" are never blurred. Pick the
> 3–5 strongest for a one-page resume; all six are defensible.

---

## Theme 3 — Bedrock gateway / cost controls / agentic safety  *(strongest)*

**Best metric:** budget overshoot 9.0× → 1.000× at 200 concurrent requests.
**Supporting:** 0 unauthorized external actions across 84 HITL-bypass attempts.
**Why it matters:** cost overruns and unauthorized tool-calls are the two ways an agentic LLM
system fails expensively; both are contained and measured.

> Engineered a transactional cost-reservation ledger (Postgres advisory lock + reserve-then-settle)
> for an LLM gateway, cutting budget overshoot from **9.0× to 1.000×** across 126 concurrency
> trials up to 200 parallel requests, and proved **0 unauthorized external side effects across 84
> human-in-the-loop bypass attempts** (malformed/replayed/concurrent approvals).

## Theme 1 — Production platform / load  *(strongest)*

**Best metric:** 22.36 req/s sustained at 0% errors; SSE 240/240 across 3 replicas.
**Supporting:** diagnosed a scale-out-reduces-availability connection-ceiling defect.
**Why it matters:** shows the system was load-tested to its saturation knee and that cross-replica
event delivery is provably correct, not assumed.

> Load-tested a two-service FastAPI/ECS platform on staging to **22.36 req/s sustained over 10
> minutes at 0% errors (p95 3.08 s)** and validated **100% cross-replica SSE delivery (240/240
> events across 3 replicas)** over Postgres LISTEN/NOTIFY, diagnosing a connection-pool saturation
> knee where autoscaling to a third replica exhausted the database's connection ceiling.

## Theme 4 — Long-term LLM memory  *(strongest)*

**Best metric:** 15.82× median context compression across 1,000 simulated student histories.
**Supporting:** a real-model evaluation surfaced a silent 0-facts-exit-0 consolidation defect the
mock could not.
**Why it matters:** compression is the point of a memory layer, and catching a silent failure via
real-model eval is exactly the "tested like a real system" signal.

> Built a long-term LLM memory layer (append-only events → consolidated semantic facts with
> provenance) achieving **15.82× median context compression** over 346,320 synthetic learning
> events, and caught a silent consolidation failure — truncated tool-calls validating as empty
> updates — through real-model evaluation that mock-model tests structurally could not detect.

## Theme 5 — Synthetic content generation  *(strong)*

**Best metric:** invalid-content rate cut 14.85% → 4.60% (3.2×) by the validation pipeline.
**Supporting:** defect-detection F1 0.837 across six defect classes at zero false positives.
**Why it matters:** quantifies the *quality* the SymPy/blind-solver/LLM-judge pipeline adds, not
just the volume it produces.

> Designed a synthetic math-problem pipeline (LLM generation → SymPy validation → blind dual-solver
> agreement → LLM-as-judge) that cut deterministically-invalid content from **14.85% to 4.60%** on
> a controlled 204-item run, with defect detection measured at **F1 0.837 across six defect
> classes and zero false positives** on 102 clean controls.

## Theme 6 — Evaluation / observability / privacy  *(strong)*

**Best metric:** PII-redaction precision 97.0% / recall 94.2% over 651 labeled probes.
**Supporting:** 100% per-hop request-trace coverage (12,888/12,888) across the full API→DB path.
**Why it matters:** privacy for a K-12 (minors) platform needs a measured false-negative rate, not
just "we mask PII"; end-to-end tracing needs a coverage number.

> Instrumented an OpenTelemetry trace pipeline achieving **100% per-hop coverage across 12,888
> authenticated requests** (API → workflow → retrieval → Bedrock → DB) and built a 651-probe
> labeled PII corpus that measured the redaction layer at **97.0% precision / 94.2% recall**,
> surfacing a trace-ID-collision bug and five redaction gaps.

## Theme 2 — RAG / retrieval  *(supporting)*

**Best metric:** reranking lifts hard lexical-mismatch retrieval 70.7% → 82.9%.
**Supporting:** an 8-arm ablation isolating each stage's contribution on 363 query instances.
**Why it matters:** shows retrieval was measured with real IR metrics and ablated honestly — the
reranker earns its place; RRF was shown not to (do not overclaim it).

> Built a hybrid RAG retriever (pgvector HNSW + Postgres FTS + LLM reranking, fail-closed with
> citation verification) and evaluated it with an 8-arm ablation over 363 query instances,
> measuring that **LLM reranking raised recall on lexical-mismatch queries from 70.7% to 82.9%**
> while quantifying (and declining to claim) reciprocal-rank fusion, which the data showed inert
> on this corpus.

---

## Assembly guidance

- **A one-page resume:** lead with Theme 3, Theme 1, and Theme 4 (the three A-level results),
  then one of Theme 5 / Theme 6 depending on whether the role leans ML-platform or
  observability/privacy.
- **Each bullet is ACTION + MECHANISM + MEASURED OUTCOME.** If space forces a trim, cut the
  parenthetical mechanism detail, never the number or its denominator.
- **Do not merge bullets across themes** to inflate a single number — the credibility of this set
  is that each metric is independently traceable to an artifact and honestly scoped.
- **If asked "was this real traffic?"** the honest answer is: validated with load-test and
  synthetic traffic on a deployed staging environment and local benchmarks — never presented as
  real production users. That candor is a strength in a systems interview, not a weakness.
