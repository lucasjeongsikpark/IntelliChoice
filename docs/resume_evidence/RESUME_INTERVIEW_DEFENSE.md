# Resume Interview Defense Notes

> Written 2026-08-30. Companion to `FINAL_RESUME_BULLETS.md`. Every statement below is backed
> by a repository artifact; nothing claims real production users or unmeasured behavior.
> Structure per bullet: Problem → why the original failed → mechanism → what I changed →
> how I measured → result → remaining limitation, then a 30-second and a 60-second version.

---

## 1. Gateway cost ledger + HITL safety (A1 / B5)

**Problem:** concurrent LLM requests raced a read-then-act budget check — 10 concurrent report
requests once charged 8× the daily ceiling in production-shaped testing.
**Why the original failed:** the check read the spend sum, then acted; every racer read the same
stale sum inside the model call's multi-second window.
**Mechanism:** reserve-then-settle — a reservation row is inserted inside a transaction
serialized by `pg_advisory_xact_lock(hashtext(scope:subject))`; spend counts
`COALESCE(actual, reserved)` so an unsettled reservation still occupies budget; the lock is held
across a SUM + INSERT only, never across the model call.
**How measured:** a 252-trial benchmark, N ∈ {10,50,100,200} × 3 ceiling shapes ×
fixed-vs-baseline arms × 3 injected-latency arms — including a 0 ms control that proves
mock-speed testing under-reports the race by 36% (which is why latency injection is mandatory).
The baseline arm reproduces the pre-fix logic on the identical workload. Safety: 84 catalogued
bypass attempts (malformed/replayed/concurrent approvals, cross-session substitution, direct
tool invocation) as permanent tests with a generator-cross-checked inventory.
**Result:** overshoot 9.0× → 1.000× in all 36 divisible-ceiling cells, 0 grants beyond
capacity; 0/84 unauthorized side effects.
**Remaining limitation:** single-machine asyncio concurrency (the lock itself is
cross-replica-correct by construction — it's Postgres-side); one admission-order property
yields 1.035× on one production ceiling (bound: 1 + estimate/ceiling), reported.

**30s:** "Concurrent LLM calls raced our budget check — we measured 8–9× ceiling overshoot.
I replaced read-then-act with a reserve-then-settle ledger serialized by a Postgres advisory
lock, and benchmarked it at up to 200 concurrent requests with injected model latency: overshoot
went from 9× to exactly 1.0, and I also built an 84-case bypass suite for the human-approval
layer — zero unauthorized side effects."

**60s:** add: "The subtle part was measurement honesty: with a mock that returns in
microseconds there is no race window, so the unfixed code measures as fixed — a 0 ms control
arm quantified that at 36% under-reporting, so every real arm injects 250 ms–3 s of latency
matching measured Bedrock p50s. The lock is transaction-scoped in Postgres, so it holds across
ECS replicas, and it wraps only a SUM and an INSERT — the model call happens outside it, so
serialization doesn't cost request latency. Settlement is best-effort; an unsettled reservation
stays charged at its estimate, which over-counts — the safe direction."

---

## 2. LLM memory (A2 / B2)

**Problem:** per-student histories grow unboundedly; one load-tested student reached a
215K-token prompt that failed every call while the job exited 0.
**Mechanism:** append-only learning events are rendered by code (never raw JSON) into bounded
batches (20K tokens, ≤4 calls/student), consolidated into semantic facts whose every cited
evidence id is re-verified by code against that student ("model proposes, code verifies");
facts have a 4-state lifecycle with a deterministic mastery-contradiction screen.
**What I changed (the remediation):** the real-model eval found truncated responses validating
as empty updates — Converse returns partial `toolUse` input `{}` on max_tokens, the truncation
guard ran after Pydantic validation, and the memory response model is the only one whose `{}`
validates. Fix: stop-reason checked before validation (fail closed), and the output budget
re-derived from the eval's own token measurements (base 1280→2560; the "21 safe facts" constant
was fiction, honest bound 11).
**How measured:** mock arm at N=1,000 students / 346,320 events for compression (exact token
arithmetic, provider-independent); real Haiku 4.5 arm with planted ground truth for quality;
post-fix re-run on the same seed/corpus; staging smoke on the deployed image.
**Result:** 15.82× median compression (p10 12.77/p90 19.29), 100% provenance (17,429/17,429);
post-fix: facts 6→119 at 119/119 provenance, silent truncations 29→0, 11 failures honestly
reported; on staging, 8/8 truncated calls all surfaced — the silent-zero shape can no longer
exist.
**Remaining limitation:** truncation still occurs on pathological histories (it fails closed
now); polarity defaults and confidence-over-recency ranking are measured-open model/design
findings; compression numbers are synthetic-history-derived, labeled as such.

**30s:** "Raw student histories don't fit a context window — one reached 215K tokens. I built
an event→semantic-fact consolidation layer with code-verified provenance: 15.8× median
compression across 346K synthetic events. The best part: real-model evaluation caught the
system silently producing zero facts — truncated tool calls validated as empty updates — and
the mock could never have seen it. I fixed it fail-closed and re-validated 119 facts at 100%
provenance."

**60s:** add: "The root cause was ordering: the gateway checked truncation after Pydantic
validation, and Bedrock's Converse API returns the partial tool input on max_tokens — a model
cut off before its first key returns `{}`, which happens to validate against any all-defaulted
response model. The fix is to let the stop reason decide, before validation, with no repair
retry — same prompt under the same ceiling just truncates again at full cost. I also re-derived
the output budget from the eval's measured ~149 tokens per fact instead of the old formula whose
premise the data refuted. On the deployed image, a smoke run showed 8 of 8 truncations surfacing
as counted failures with the exact ceiling named — pre-fix that identical run reported
`0 added, 0 failed, exit 0`."

---

## 3. Platform load + cross-replica SSE (A3)

**Problem:** the platform had burst-only load numbers and a 10-round hand probe for
cross-replica event delivery.
**Mechanism:** SSE fan-out across ECS replicas rides Postgres LISTEN/NOTIFY (two dedicated
connections per process, outside the ORM pool; oversized payloads dropped-not-truncated;
publish serialized per process); autoscaling is ALB-p95 step-scaling.
**How measured:** a `constant-vus` k6 scenario (repeat trials, CloudWatch-joined: ECS CPU/mem,
RDS connections, ALB p95); a two-process local rig driving 1,100 events under concurrent load;
a staging harness holding 20+ streams against real replicas with per-event accounting and
per-task log-stream splits proving traffic crossed all replicas.
**Result:** 22.36 req/s sustained 10 min, 13,550/13,550, 0 5xx, warm p95 3.08 s; SSE 1,100/1,100
local (550 crossing a real NOTIFY) and 240/240 across a 93/93/93 three-replica split — 0 lost,
0 duplicate, 0 reconnects. Plus a found defect: at 50 VUs, scale-out to a third replica
exhausted db.t4g.micro's ~112-connection ceiling (`TooManyConnectionsError`) — scaling out
reduced availability, and CloudWatch's 1-per-minute connection sampling never saw the
sub-minute refusal.
**Remaining limitation:** load-test traffic, not users; ≤3-replica ceiling; the connection-knee
defect is reported with the fix options (pool sizing vs instance class vs autoscaling ceiling)
not yet chosen.

**30s:** "I load-tested the platform to its saturation knee: 22 requests/sec sustained for ten
minutes at zero errors, and I proved cross-replica SSE delivery — 240 of 240 events across
three replicas over Postgres LISTEN/NOTIFY, with log-stream splits proving the traffic really
crossed replicas. The sweep also found a genuine distributed-systems bug: autoscaling out to a
third replica exhausted the database's connection slots, so scaling out reduced availability."

**60s:** add: "The relay design matters: LISTEN binds to a session, so each process holds two
dedicated asyncpg connections outside the SQLAlchemy pool — which is exactly what made the
third replica's marginal footprint (10+10 pool + 2 relay) cross the db.t4g.micro ceiling.
The diagnosis discipline was distinguishing it from a prior credential-rotation incident with
the same surface symptom: connection-slot exhaustion needs no credential, and the app log — not
CloudWatch, whose 1/min sampling peaked at 62 — is the only witness of the sub-minute refusal."

---

## 4. Observability + PII (A4 / B4)

**Problem:** privacy for a minors-serving platform claimed "we mask PII" with 5 unit tests and
no negative corpus; tracing had one narrow 99.9% join; unhandled 500s were invisible to every
alarm (a real incident emitted 114 tracebacks while monitors read quiet).
**Mechanism:** layered redaction (pure regex floor + a reflection-enforced payload allowlist
over 28 LLM payload types + a span-export redactor); OTel spans at every hop with a
code-derived expected-hop map; a JSON ERROR line for unhandled exceptions + a raw-traceback
log-pattern alarm; scraped ADOT exporter counters.
**How measured:** a 651-probe labeled corpus (277 in-contract positives, 264 negatives — the
half that never existed) driven through all three layers offline; per-hop trace classification
over 13,571 staging traces reconciled against k6's request counts; the alarm proven with a
synthetic event, actions disabled, everything restored (0/40 alarms left disabled).
**Result:** precision 97.1% / recall 96.4% / F1 96.7% after fixing the two worst measured gaps
at zero new false positives; 100.00% per-hop coverage (12,888/12,888); the coverage measurement
itself surfaced a 0.14% trace-ID collision; the export blind spot that once silently dropped
100% of spans is now alarmed.
**Remaining limitation:** regex recall is scoped to email/URL/phone (names are the structural
layer's job — measured separately); the collision's mechanism is a labeled hypothesis; the
unhandled-500 JSON line has no safe staging trigger, so its live proof is code-presence plus
permanent tests.

**30s:** "For a platform serving minors, I didn't want 'we mask PII' — I wanted a
false-negative rate. I built a 651-probe labeled corpus including the negative half nothing
had (math, timestamps, IDs that look like phone numbers): 97% precision, 96% recall after
fixing the two gaps it found. Same philosophy on tracing: 100% per-hop coverage measured over
12,888 requests — and the measurement itself caught a trace-ID collision bug the pretty number
would have hidden."

**60s:** add: "The redaction is layered because regex can't do names: a reflection-driven test
walks every LLM payload class and fails the build if a new field isn't explicitly governed by
an allowlist — structure catches what patterns can't. The trace claim is per-hop, not
per-request-exists: a code-derived map says which spans each route class must produce, and the
denominator is reconciled against the load generator's own request counts, which is exactly how
the 0.14% collision surfaced — 19 requests shared a trace ID and X-Ray merged them. And the
unhandled-500 fix came from a real incident where 114 tracebacks were invisible to every
`level=ERROR` filter; now there's both a structured ERROR event and a raw-traceback metric
alarm, proven end-to-end without paging anyone."

---

## 5. Content-generation quality (A5 / B3)

**Problem:** "generated 958 items" says volume, not quality — what does the validation pipeline
actually remove?
**Mechanism:** deterministic SymPy gate (answer re-derivation, option matching) → embedding
dedup + an arithmetic-identity fingerprint → two blind solvers (different model families where
invocable) whose agreement is checked before the answer key is revealed → an LLM judge blind to
the requested difficulty.
**How measured:** a controlled 204-candidate run into an isolated database (raw arm = every
schema-valid generator output, scored by deterministic re-derivation; validated arm = the full
pipeline; same slots), plus a 102-defect × 6-class seeded-mutation corpus against 102 clean
controls, plus a $0 funnel over the complete 1,827-run generation history.
**Result:** invalid content 14.85% → 4.60% (3.2×), every SymPy-checkable family to 0.00%;
detection F1 0.837 → 0.949 after the benchmark exposed two blind spots (hint-stem coherence:
0/17 → 12/17 at zero FPs including all 958 approved items; arithmetic clones: 8/17 → 17/17);
90% of paid-stage rejections are catches the free gate cannot make.
**Remaining limitation:** the 4.60% residual is a measured-open skeleton-collision class
("same sentence, different numbers" — provably outside the fingerprint); machine-acceptance ≠
human approval; the raw arm's 9.41% "answer-key" rate was a verifiability failure (equations
written as bare expressions), not 19 wrong answers.

**30s:** "I measured what the validation pipeline is actually worth: raw LLM generation carries
a deterministic defect ~15% of the time; after SymPy validation, blind dual-solver agreement,
and an LLM judge, that's 4.6% — and the seeded-defect benchmark that measured it also exposed
two blind spots, which I fixed and re-measured: detection F1 went from 0.84 to 0.95 at zero
false positives across all 958 approved items."

**60s:** add: "The design principle is that LLM stages and deterministic stages catch disjoint
defect sets — we proved it twice: five wrong answer keys once sailed past both solvers and the
judge but SymPy catches them deterministically, and inversely the solvers catch
scenario-fidelity defects SymPy can't express. The blind-solver detail matters: solvers never
see the declared answer, and a call failure is scored separately from an objection — an early
version of that control would have scored a completely broken solver as a perfect detector.
The residual 4.6% is honest: it's one duplicate class the fingerprint provably can't see — same
sentence skeleton, different numbers — and closing it re-opens a scoping decision, so it's
queued, not hand-waved."

---

## 6. RAG retrieval (B1)

**Problem:** small pass/fail sets couldn't say what each retrieval stage contributes.
**Mechanism:** authorization filters applied before retrieval → GIN FTS + pgvector HNSW → RRF
→ LLM rerank with a measured 0.35 relevance floor → substring-verified citations, fail-closed.
**How measured:** a 123-ground-truth / 363-instance chunk-level fixture (blind-rewrite
phrasings; a measured-overlap gate relabelled 56/104 too-easy "lexical mismatch" attempts) and
an 8-arm ablation whose harness is drift-guarded id-for-id against the shipped `hybrid_search`
plus a Jaccard control against real `retrieve()`.
**Result:** the reranker is the one stage that clearly pays (+20/−10 at rank 1; lexical
mismatch 70.7% → 82.9%); RRF is inert-to-net-negative here (k ∈ {20,60,120} produce identical
rankings on 363/363); FTS fires on only 16% of queries but is right 48/58 when it does.
**Remaining limitation:** effective n ≈ 123 (instances are correlated phrasings); a 7.5k-word
corpus — the finding may not transfer to a large corpus (where fusion typically earns its
place); 3 no-answer controls leak past the 0.35 floor at rerank scores 0.75–0.90, so a
relevance score is not a full answerability gate.

**30s:** "I built the first real IR benchmark for our RAG stack — chunk-level ground truth,
recall@k, MRR, nDCG — and ablated every stage. The honest answer: the LLM reranker is the one
stage that clearly pays, lifting hard lexical-mismatch recall from 71% to 83%, while rank
fusion was inert on our corpus — the k parameter literally didn't change a single ranking. So
the resume claims the reranker, not the fusion."

**60s:** add: "Two honesty controls matter. First, phrasings are generated blind — the rewriter
never sees the source chunk — and each case records its measured lexical overlap; a gate
relabelled half the 'lexical mismatch' attempts as too easy. Second, ablation harnesses drift:
ours asserts id-for-id equality with the shipped hybrid function on all 381 instances, because
an earlier project harness silently diverged from the production rule for four sessions. And I
report effective n as ~123, not 363 — the phrasings are correlated samples over the same ground
truths."

---

## Likely interviewer questions — answers from the evidence

**Why this mechanism (advisory lock) and not X (Redis, SELECT FOR UPDATE, app lock)?**
Postgres was already the transactional store, so the lock adds no new infrastructure; a
transaction-scoped advisory lock self-releases on any failure path (no lease expiry logic) and
holds across ECS replicas, unlike an in-process lock. It wraps only a SUM+INSERT
(sub-millisecond), and the model call stays outside it. `SELECT FOR UPDATE` would need a row to
lock before the first reservation exists; `hashtext(scope:subject)` gives a lock key without a
sentinel row.

**What was the baseline?**
Always the system's own prior behavior on the identical workload: the reproduced pre-fix
read-then-act ledger (9.0×), raw generator output on the same slots (14.85%), raw event
histories on the same synthetic corpus, the pre-fix consolidation run on the same seed
(6 facts/29 silent truncations), the identity function for redaction. No cross-system
comparisons are claimed.

**Production traffic or load-test traffic?**
Load-test and synthetic traffic on a deployed staging environment, plus local benchmarks —
never real users, and every document and bullet says "validated at", not "served". The staging
environment is real AWS (ECS/RDS/CloudFront/Bedrock), which is why it caught infrastructure
truths a mock can't (secret rotation, connection ceilings, autoscaling behavior).

**How were denominators constructed?**
Committed, frozen datasets with provenance: the 651 PII probes and 102+102 defect corpus are
in-repo with per-case labels and generation provenance; re-measurement after fixes reuses the
byte-identical corpus. Load denominators come from the harness's own counters reconciled
against server-side logs/traces (k6's 13,550 vs X-Ray's 13,531 is how the trace-ID collision
was found). Effective-n is stated when samples are correlated (RAG ≈ 123).

**How do you know the improvement is attributable?**
Single-variable comparisons on identical workloads: same seed/corpus/students before and after
the memory fix; same 252-trial workload for both ledger arms; the same frozen corpus for
detection before/after; fixes reproduced by a failing test first, so the delta is pinned to the
change. Where attribution was impossible we say so (RAG's 100% e2e lane is consistent-with, not
attributed).

**What failure modes remain?**
Enumerated and queued, not hidden: memory truncation still occurs on pathological histories
(fails closed now; response-shape bounding is an open design decision), polarity/staleness
model findings, the skeleton-collision duplicate class, the staging connection ceiling at
3 replicas, PII paren-phones/exotic emails, the trace-ID collision mechanism, ~120 bank items
sharing arithmetic pending a content decision.

**What changes at 10× scale?**
The measured knees name them: the DB connection ceiling binds first (per-task pools ×
max-replicas must stay under `max_connections` — cap pools or move off t4g.micro); the p95 ≈
0.31 s × (r/2.5)^1.4 queueing law says CPU next (more/larger tasks); memory consolidation cost
is linear in students (~2–3¢/student/week, run-budgeted); the anonymous chat rate-limit bucket
must become per-principal; and the prompt cache that's written-never-read should be fixed or
dropped (~25% input surcharge today).

**Which measurements are real-model vs mock?**
Real: retrieval ablations (Titan + Haiku rerank), the e2e RAG lane, memory quality + the
truncation catch and re-validation, all content generation/solver/judge runs, staging chat
smoke. Mock/synthetic, always labeled: memory compression arithmetic (provider-independent
token counts), gateway concurrency (mock + injected latency — with a control proving why),
PII corpus (deterministic layers, no model involved). The program's rule: mock results are
never quality claims — twice proven necessary (the mock measured an unfixed race as fixed, and
reported the truncation bug 0/3,135 times).

**What would you monitor in production?**
Exactly what the gaps taught: budget-ceiling refusals and spend-per-surface (the ledger emits
both), consolidation calls_failed + truncation counts and the job-failure alarm (it paged
correctly during verification), the raw-traceback alarm alongside `level=ERROR`, ADOT exporter
send-failures (the silent-drop class), DB connections vs the replica-count product (with
sub-minute resolution, since 1/min sampling missed the real refusal), 429-vs-5xx separation,
and the SSE relay's delivered/failed counters — promoting them to CloudWatch is a known
open item.
