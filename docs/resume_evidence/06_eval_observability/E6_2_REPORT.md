# E6.2 — Per-hop trace coverage over two pinned staging windows

> Experiment: **E6.2** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 6).
> Generated: **2026-08-29T23:04:26Z**. Repo SHA: **`78201a9`**.
> Deployed build under measurement: **`learning-api:gha-5fa15d491057`** (task definition
> `intellichoice-staging-learning-api:153`) and **`chat-api:gha-5fa15d491057`**
> (`intellichoice-staging-chat-api:151`), both deployed **2026-08-29T00:42:18Z**
> (`describe-services` prints `createdAt` as `2026-08-28T19:42:18-05:00`; converted).
> Collector: `aws-otel-collector:v0.43.3` (ADOT).
> Environment: **deployed staging, read-only trace analysis over simulated load-test
> traffic**. Nothing was written to AWS; no product code, collector config or alarm changed.
> Cost: **$0 model spend.** X-Ray/CloudWatch reads only (pennies). No chat turns were
> generated — the ≤5-turn budget was not needed, because 210 real chat-message traces
> already sat inside the 30-day X-Ray retention.
> Harness: `benchmarks/resume_evidence/06_eval_observability/trace_coverage.py`.
> Artifacts: `trace_coverage_results.json`, `trace_coverage_summary.csv`.
> Tests: `packages/observability/tests/test_e6_2_trace_coverage.py` (28 cases).

## 1. Headline

| metric | value | n / N |
|---|---|---|
| **Trace coverage, authenticated 2xx requests, complete span chain** | **100.00%** | **12,888 / 12,888** |
| — learning window | 100.00% | 12,559 / 12,559 |
| — chat window | 100.00% | 329 / 329 |
| Missing-span rate, FastAPI hop | 0.00% | 0 / 13,855 |
| Missing-span rate, SQLAlchemy hop | 0.00% | 0 / 11,709 |
| Missing-span rate, LangGraph-node hop | 0.00% | 0 / 11,709 |
| Missing-span rate, Bedrock hop | 0.00% | 0 / 120 |
| Missing-span rate, MCP hop | **not measured** | 0 / 0 — no traffic exercised it |
| **Request-to-trace yield** (k6 ground truth vs X-Ray) | **99.86%** | 13,531 / 13,550 |
| Access-log lines carrying a `trace_id` | 98.26% | 13,580 / 13,820 |
| — of the 240 without one | 100% are `GET /readyz` | 240 / 240 |
| `trace_id` → X-Ray trace join (the id names a trace that exists) | 100.00% | 13,580 / 13,580 |
| **Requests sharing a trace id with another request** | **0.14%** | **19 / 13,550** (+ **1 / 424** in chat) |
| Health-endpoint traces in the corpus (AUD-F-30 exclusion, verified) | 0 | 0 / 14,005 |
| Collector export failure/success counts | **not externally measurable** | see §8 |

The 0.14% row is the finding. Everything above it says the instrumentation is complete;
that row says **19 requests have no trace of their own**, and the mechanism is not an
export drop.

## 2. What this measures, and what it does not

Before this run the repository's only coverage number was D-400's trace-to-spend join —
**99.9% (2,209/2,212 and 297/299)** — which answers one question about two Bedrock call
types. Nothing measured whether a request's *chain* was complete across
API → LangGraph node → SQLAlchemy → Bedrock → MCP, and no export-failure rate existed.

This experiment measures, over two pinned UTC windows of real deployed-staging traffic:
per-route-class chain completeness, per-hop missing-span rate, the reconciliation of
X-Ray's trace count against k6's request count, the log↔trace correlation join, the
sampling posture, and the collector export posture.

It does **not** measure trace *quality* (attribute richness, span timing accuracy), does
not touch LangSmith (UD-13 is open), and does not measure the MCP hop, which no traffic in
either window exercised (§7).

## 3. The corpus — two windows, both pinned in UTC

Timestamps are converted to UTC explicitly at every boundary. The `-05:00` snare is real
and on record (D-135 §3): the same `describe-services` call that dated the deployment
above printed it in local time.

| window | UTC bounds | length | traces | what it is |
|---|---|---|---|---|
| `e1_sustained_25vu_10m` | 2026-08-29T19:46:49Z → 19:56:56Z | 607 s | 13,571 | E1.1's sustained k6 run at 25 VUs — **13,550 requests with an exact per-route ground truth** |
| `chat_burst_20260829T0050Z` | 2026-08-29T00:50:00Z → 00:54:00Z | 240 s | 434 | a real chat burst 8 minutes after the deploy — the only corpus of any size in retention that exercises the model hop |

**Every trace in both windows was fetched and decomposed — no sampling of the corpus.**
13,571/13,571 and 434/434 announced traces were returned by `BatchGetTraces`
(`traces_announced_but_not_returned: 0` in both), which is itself a check: a summary that
names a trace the fetch cannot retrieve is a finding, not a rounding error.

The learning window is the stronger corpus and it is **biased toward the learning path by
construction**: k6 drives five routes, none of which call a model or an MCP tool. The chat
window is small (210 message turns) but it is the only corpus in retention large enough to
put a denominator under the Bedrock hop (§7 notes the five stray learning traces that also
carry a Bedrock span). Neither window is organic user traffic; both are load-test or smoke
traffic.

## 4. The expected-hop map — derived from the route handlers, not from the traces

Deriving expectations from what the traces contain would make every missing span invisible
by construction. Each row below comes from reading the handler; the citation is the code
that determines it.

| route class | expected hops on a 2xx | derived from |
|---|---|---|
| `POST /dev/token` | FastAPI | `learning_api/main.py` — mints a JWT in-process; no DB session, no graph |
| `POST /learning/sessions` | FastAPI | `routers/sessions.py:912` `create_session` — `del claims`, one `uuid4()`, one counter |
| `POST /learning/sessions/{id}/student` | FastAPI, SQLAlchemy, LangGraph | `routers/sessions.py:922` — `ProfileAdapter` (instrumented engine) + graph invoke |
| `POST /learning/sessions/{id}/topics` | FastAPI, SQLAlchemy, LangGraph | `routers/sessions.py:1016` — checkpoint read, `CurriculumRepository`, graph invoke |
| `POST /learning/sessions/{id}/answers` | FastAPI, SQLAlchemy, LangGraph | `routers/sessions.py:1208` — repository pre-flights, graph invoke. **No Bedrock:** grading is deterministic (rule 2) and D-217 moves the study narrative to a background task under the real provider |
| `POST /chat/sessions` | FastAPI | `chat_api/routers/sessions.py:643` — identifier only, mirrors the learning app |
| `POST /chat/sessions/{id}/messages` | FastAPI, SQLAlchemy, LangGraph, **Bedrock** | `chat_api/routers/sessions.py:650` — rate-limit read, `_claim_turn`, then the chat graph, which embeds and synthesizes |

Two classes are counted and then held **out** of the authenticated denominator:
`GET /metrics` (`internal` — the collector's own 60 s scrape on `localhost`) and
`POST /dev/token` (`unauthenticated` — it authenticates with a shared-secret header and is
the thing that mints the bearer; counting it as authenticated traffic would pad the
denominator with the cheapest request in the corpus).

**Every route in both windows matched the map: `unmapped_routes` is empty in both, and
`unknown_langgraph_span_names` is empty in both** — no node has been renamed out from
under the 25-name list in `graph/build.py`.

## 5. Coverage

### 5.1 Per route class

| window | route class | expected hops (2xx) | traces | 2xx | non-2xx (short-circuit) | complete chain | **coverage (2xx)** | coverage read naively |
|---|---|---|---|---|---|---|---|---|
| learning | `POST /dev/token` | FastAPI | 967 | 967 | 0 | 967 | **100.00%** | 100.00% |
| learning | `POST /learning/sessions` | FastAPI | 970 | 970 | 0 | 970 | **100.00%** | 100.00% |
| learning | `POST .../{id}/student` | FastAPI+SQL+LG | 970 | 970 | 0 | 970 | **100.00%** | 100.00% |
| learning | `POST .../{id}/topics` | FastAPI+SQL+LG | 969 | 966 | 3 (409) | 966 | **100.00%** | 99.69% |
| learning | `POST .../{id}/answers` | FastAPI+SQL+LG | 9,655 | 9,653 | 2 (409) | 9,653 | **100.00%** | 99.98% |
| chat | `POST /chat/sessions` | FastAPI | 209 | 209 | 0 | 209 | **100.00%** | 100.00% |
| chat | `POST /chat/sessions/{id}/messages` | FastAPI+SQL+LG+**Bedrock** | 210 | 120 | **90 (429)** | 120 | **100.00%** | **57.14%** |

Aggregated over authenticated traffic: **12,559/12,559** (learning) and **329/329** (chat)
= **12,888/12,888 = 100.00%**. Read naively across all statuses the same corpora give
99.96% and 78.52%.

### 5.2 Per hop

Denominators are **per hop**, over the traces whose route class expects that hop on a 2xx.
A corpus-wide denominator would score `POST /learning/sessions` — which correctly does no
database work — as a SQLAlchemy coverage failure.

| hop | traces expecting it | traces with it | missing | **missing-span rate** |
|---|---|---|---|---|
| FastAPI entry span | 13,855 | 13,855 | 0 | **0.00%** |
| SQLAlchemy | 11,709 | 11,709 | 0 | **0.00%** |
| LangGraph node | 11,709 | 11,709 | 0 | **0.00%** |
| Bedrock gateway | 120 | 120 | 0 | **0.00%** |
| MCP tool | 0 | 0 | — | **undefined — see §7** |

Node spans actually observed: `langgraph.submit_answer` 9,655, `langgraph.select_student`
970, `langgraph.select_topic` 967 (learning); `langgraph.resolve_role` /
`langgraph.scope_guard` / `langgraph.retrieve_context` /
`langgraph.join_scope_and_retrieval` 120 each, `langgraph.synthesize_answer` 119,
`langgraph.explain_access` 5, `langgraph.calendar_extract` and
`langgraph.calendar_no_event` 1 each (chat). Both Bedrock span names appear on every
successful chat turn.

### 5.3 The SQLAlchemy double-count, verified rather than assumed

X-Ray records each SQLAlchemy statement twice — once as a child of the span that issued it
and once as a standalone top-level segment with `origin == "Database::SQL"`.
`scripts/profile_xray_span.py` exists because a hand-rolled profile that missed this
reported 131% of wall time in SQL. Hop presence here is decided **structurally**, from
descendants of the entry segment only.

The two counts came out **exactly equal in both windows**: 208,859 descendant SQL spans
vs 208,859 orphan segments (learning), 2,697 vs 2,697 (chat). That equality is independent
confirmation that the standalone segments really are duplicates and that nothing is being
double-credited.

## 6. The two denominator traps

### 6.1 The health-check trap (AUD-F-30) — fixed, and now verified live

`~97%` of staging's traces were once `GET /readyz`. `tracing.py`'s `HEALTH_ENDPOINT_URLS`
excludes `healthz`/`readyz` at the instrumentation layer. **Verified, not assumed:
`health_endpoint_traces` is 0 in both windows**, across 14,005 traces. The complementary
evidence is in the log: 240 `GET /readyz` access lines in the learning window and 32 in
the chat window carry **no** `trace_id` — because there is no span to take one from. That
is the exclusion working, seen from the other side.

### 6.2 The short-circuit trap — found by this run

90 of the 210 `POST /chat/sessions/{id}/messages` traces contain no LangGraph and no
Bedrock span. Read naively that is **57.14% coverage** and an alarming instrumentation
gap. Every one of those 90 is an **HTTP 429**:
`install_global_rate_limit_middleware` (`packages/shared/.../rate_limit.py:114`) and
`_reject_if_over_caller_limit` (`apps/chat-api/.../routers/sessions.py:673`) refuse the
request before `_run_turn` is ever reached. There is no node to instrument and no model
call to make. The spans are not missing — **the work never happened**. Conditioned on a
2xx the same corpus is 120/120.

The separation is perfect and it is worth stating as a number: **all 90 empty-chain traces
are 429s, and all 120 complete-chain traces are 200s.** The harness therefore conditions
the expected-hop map on the response status and reports both readings side by side; the
regression is pinned by `test_a_429_is_a_short_circuit_not_a_missing_span` and its
complement `test_a_200_missing_its_langgraph_span_is_reported_missing`, so the classifier
is proved to stay quiet on the first and fire on the second.

## 7. The MCP hop is not covered by any evidence in retention

**0 MCP spans exist anywhere in the searched retention window.** All five instrumented
names (`mcp.youtube_catalog.search`, `mcp.gmail.send_email`, `mcp.maps.geocode`,
`mcp.maps.compute_routes`, `mcp.calendar.create_event`) were searched for across a full
7-day sweep of every `chat-api` trace (437 traces, including all 211 message turns) and a
targeted sweep of the learning routes that could reach one (`respond`, `finalize`,
`resume`, `report`, `branch`, `calendar` — 47 traces). None fired.

**That sweep carries its own positive control.** Five of those 47 learning traces do
contain `bedrock.generate_structured`, alongside `langgraph.intervention_choice` (3) and
`langgraph.finalize_exam` (2) — so the sweep was looking at exactly the study- and
finalize-phase traces where an MCP call would live, and it can see manual spans when they
are there. The MCP absence is a property of the traffic, not of the search. (Those five
traces are too few to report a coverage rate and are not counted in §5; they are listed
here only as evidence that the search was capable of finding what it was looking for.)

This is stated as an **uncovered hop, not a 0% or a 100%**. The instrumentation exists at
six `traced_span()` call sites, verified by code inspection; whether it emits correctly in
deployed traffic is **unverified**, and the honest denominator is 0/0. The measurement plan
budgeted ≤5 guest chat turns (~30¢) for a per-hop existence check *only if no chat traces
existed in retention*; 210 did, so no spend was incurred. Reaching an MCP call would have
required driving a location-consent or calendar-approval HITL flow to completion, which is
several turns and a different experiment.

## 8. Export posture — what is measurable and what is not

AUD-F-12 is why this section exists: the collector once accepted every span and
**discarded 100% of them**, logging
`Exporting failed. Rejecting data. {"name": "awsxray", ... "rejected_items": 64}` on
repeat, and nothing detected it — the sidecar is `essential: false`, both services stayed
green, and **no alarm watches export failures**. That alarm gap is still open.

What this run could establish:

- **No error or warning line from either collector in either window.** Learning: 0
  collector log events at all. Chat: 4 events, all `info`.
- **The reader is proved.** "Zero events, therefore no failures" is exactly the AUD-F-12
  false negative, so the empty learning window triggers a positive control: the newest
  `otel-collector` stream is read directly and returned 5 lines. That container **started
  at 2026-08-29T19:33:24Z — 13 minutes before the window opened** and was still writing at
  20:20:03Z, so it was alive across the whole window and wrote nothing. The zero is real.
- The recorded AUD-F-12 signature is an `error`-level line, which this reader classifies
  and samples. So "no export failure was logged in these windows" is a supported claim.

What is **not** measurable, and this is a finding:

> **The collector's own export counters never leave the task.** Its startup line says
> `Serving metrics {"address": "localhost:8888", "metrics level": "Normal"}` — so
> `otelcol_exporter_sent_spans` and `otelcol_exporter_send_failed_spans` are being
> computed. The Prometheus receiver in `terraform/modules/ecs-service/main.tf` scrapes
> `localhost:${var.container_port}` (the app) and nothing scrapes `localhost:8888`.
> **There is therefore no export-success or export-failure *rate* anywhere in AWS**, only
> error log lines, and only for as long as someone reads them. An export-failure rate
> sub-metric is not obtainable without a config change, which this task is scoped out of.

The independent evidence that export was in fact healthy is stronger than the yield number
alone. Every one of the 13,580 `trace_id`s the app logged names a trace this run fetched
(§10), and for all 19 colliding pairs **both** members' `span_id`s were found inside the
fetched trace documents — 38 of 38. **No span emitted in either window failed to reach
X-Ray. Measured export loss in these windows is 0.**

## 9. k6 ↔ X-Ray ↔ access-log reconciliation — and the 19

**Sampling posture, read from configuration rather than assumed.** Neither app passes a
`sampler=` to `TracerProvider` (`packages/observability/.../tracing.py`), so the SDK
default `ParentBased(ALWAYS_ON)` applies; no `OTEL_TRACES_SAMPLER` is set in
`terraform/environments/staging/main.tf`; and the collector's traces pipeline is
`otlp → batch → awsxray` with no sampling processor. **Nothing samples. One request should
equal one trace**, which is what makes the following arithmetic meaningful.

| route | k6 requests | X-Ray traces | Δ |
|---|---|---|---|
| `POST /dev/token` | 970 | 967 | −3 |
| `POST /learning/sessions` | 970 | 970 | 0 |
| `POST /learning/sessions/{id}/student` | 970 | 970 | 0 |
| `POST /learning/sessions/{id}/topics` | 970 | 969 | −1 |
| `POST /learning/sessions/{id}/answers` | 9,670 | 9,655 | −15 |
| **total** | **13,550** | **13,531** | **−19** |

k6's two independent counts agree (13,550 from the per-check totals, 13,550 from the
`http_reqs` metric). The window's whole corpus closes exactly: 13,531 k6-route traces +
40 `/metrics` traces = 13,571 fetched.

**The 19 are not an export drop.** The app's own access log is the independent witness,
and it was read over the *identical* UTC bounds:

- 13,820 access lines, of which 13,580 carry a `trace_id`; the other 240 are all
  `GET /readyz` (§6.1).
- The per-route access-line counts match k6 **exactly** — 9,670 answers, 970 each of
  `/dev/token`, `/learning/sessions`, `/student`, `/topics` (plus 30 `GET /metrics` scrape
  lines, giving the 13,580). The app served all 13,550 requests and stamped a trace id on
  every one.
- **13,580 / 13,580 = 100.00%** of those trace ids, converted to X-Ray form
  (`1-<first 8 hex>-<remaining 24 hex>`), name a trace that this run actually fetched.
  Not one points at nothing.
- But those 13,580 lines carry only **13,561 distinct** trace ids. **19 trace ids were
  each used by two different requests.**

19 shared ids × 1 extra request each = the 19 missing traces, exactly.

Characterised further, directly from the log and from X-Ray:

- All 19 pairs are **within a single ECS task** (same log stream).
- The two requests always have **different span ids**, different durations, and are
  0.014 s – 2.32 s apart — two distinct requests, not one request logged twice.
- **14/19 pairs are the same route; 5/19 are different routes.** One pair is a
  `POST /dev/token` and a `POST .../answers`.
- **Nothing was dropped.** Looking up all 38 logged `span_id`s inside the 19 fetched
  traces finds all 38. Both requests of every pair are in X-Ray; they are simply in the
  same trace.
- In X-Ray both requests' spans are present, but under **one** trace. The loser is nested
  *inside* the winner: trace `1-22f829e6-0eee92a58556735a644d030a` is a
  `POST .../{id}/answers` with an entire `POST /dev/token` — its own ASGI send/receive
  spans included — hanging off it as a subsegment named `10.0.10.199:8001`.
- The harness detects this structurally and reports it: **19 merged-request traces** in
  the learning window, and the nested routes it names match the per-route shortfall
  **exactly, route by route**: 15 nested `answers` against Δ −15, 3 nested `/dev/token`
  against Δ −3, 1 nested `topics` against Δ −1, and zero nested `student` or
  `/learning/sessions` against Δ 0 on both. Two independent instruments — a trace-count
  reconciliation against k6 and a structural walk of the span trees — land on the same
  19 requests and the same distribution across routes.

**It replicates independently.** The chat window — a different service, a different day, a
different traffic generator — shows the same thing at the same order of magnitude:
**1 shared trace id across 424 traced requests** (0.24%), and it too is cross-route
(`POST /chat/sessions` nested inside `POST /chat/sessions/{id}/messages`).

**Mechanism: leading hypothesis, not verified.** Both apps run a single uvicorn process
with no `--workers` (`apps/*/Dockerfile`), so a forked-RNG explanation is excluded, and no
code re-seeds the global `random` module (every `random.Random(seed)` in the tree is an
instance RNG). The pattern that fits every observation — same task, sub-second-to-2-second
gap, mostly same route but sometimes the *next* route a VU would call on the same
connection, and a keep-alive timeout of 125 s (D-364) — is **OTel context leaking across
two requests that share one keep-alive connection**, so the second request's server span
is created as a child of the first instead of as a new root. Confirming that requires a
local reproduction and a read of the ASGI instrumentation's context handling, which is
outside this task's scope. It is filed as a finding below.

## 10. Correlation-ID spot check

| | learning window | chat window |
|---|---|---|
| log events read | 15,992 | 1,077 |
| access-log lines | 13,820 | 456 |
| carrying a `trace_id` | 13,580 (**98.26%**) | 424 (**92.98%**) |
| lines without one | 240 — **all `GET /readyz`** | 32 — **all `GET /readyz`** |
| `trace_id` → an X-Ray trace that exists | 13,580 / 13,580 (**100.00%**) | 424 / 424 (**100.00%**) |
| X-Ray traces named by ≥1 log line | 13,561 / 13,571 (99.93%) | 423 / 434 (97.47%) |

This is a **join**, not a field-presence check: "the field is set" and "the field points at
a trace that exists" are different claims, and only the second one helps during an
incident. The reverse-direction shortfalls are fully accounted for: the learning window's
10 unnamed traces are the *chat* service's `/metrics` scrapes, which fall inside the same
UTC window and are fetched by a window-scoped query but logged to a different log group;
the chat window's 11 are the learning service's, symmetrically. Both are in the `internal`
bucket and out of every coverage denominator.

One neutral observation, recorded because it is a large share of the non-access log lines
and would otherwise look like missing correlation: 1,202 (learning) and 126 (chat)
LangSmith multipart-ingest failure lines appear in these windows and carry no `trace_id`.
They are the already-classified quota-exhaustion condition, are not access lines, and are
excluded from every denominator above. **Nothing in this experiment touches LangSmith
(UD-13 is open).**

## 11. Findings

### New, from this run

| id | severity | finding |
|---|---|---|
| **TRACE-ID-COLLISION** | medium | **0.14% of requests (19/13,550 learning, 1/424 chat) share an OTel `trace_id` with a different request in the same task.** X-Ray merges them, nesting one request's whole span tree inside another's — a real trace contains a `POST /dev/token` hanging off a `POST .../answers`. Consequences: those requests have no independently addressable trace; an operator reading the merged trace would conclude one endpoint calls another; and any trace-counting metric under-counts by that rate. Leading hypothesis (unverified): OTel context leaking across requests on one keep-alive connection. Reproduce with §12's commands; the harness reports `merged_request_traces` and `trace_ids_shared_by_more_than_one_request` on every run. |
| **COLLECTOR-STATS-UNSCRAPED** | low | The ADOT collector computes `otelcol_exporter_sent_spans` / `send_failed_spans` on `localhost:8888` (`"metrics level": "Normal"`), and nothing scrapes it — the Prometheus receiver targets the app port only. **No export success/failure rate exists anywhere in AWS.** Adding `localhost:8888` as a second scrape target would make AUD-F-12's failure mode continuously visible for roughly the cost of two more EMF series. Not done here (collector config is out of scope). |
| **CHECKPOINTER-UNINSTRUMENTED** | low | LangGraph's `AsyncPostgresSaver` opens its own psycopg connections, separate from the SQLAlchemy engines (`learning_api/main.py:246`). `SQLAlchemyInstrumentor` therefore never sees checkpoint reads or writes, so **no span in any trace represents checkpoint I/O** — on `/answers`, a route whose whole state model is the checkpoint. The chain is complete as specified; the specification has a hole. |

### Restated, unchanged

- **AUD-F-12's alarm gap is still open.** The collector is `essential: false` by design (a
  collector that fails must not take the API down), and **no alarm watches export
  failures**. This run found no failure in either window and proved its reader, but the
  detection gap that let 100% span loss go unnoticed is a posture, not an incident, and it
  has not changed.
- **`SILENT-500S` is still open** (PROJECT_STATE §4.1, evidence D-455): unhandled 500s emit
  only uvicorn's plain-text ASGI traceback, with no JSON `level=ERROR` line, so they are
  invisible to every `{ $.level = "ERROR" }` filter and to every log-based alarm — 114
  traceback lines during the rotation incident while the observability layer read "quiet".
  Nothing in these windows exercised that path (0 5xx in both), so this experiment adds no
  evidence either way.

## 12. Reproduction

```bash
eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)"
uv run python benchmarks/resume_evidence/06_eval_observability/trace_coverage.py \
  --window e1_sustained_25vu_10m=2026-08-29T19:46:49Z..2026-08-29T19:56:56Z \
  --window chat_burst_20260829T0050Z=2026-08-29T00:50:00Z..2026-08-29T00:54:00Z \
  --k6-summary docs/resume_evidence/01_platform/raw/sustained_25vu_10m.json \
  --k6-window e1_sustained_25vu_10m \
  --correlation-log-group /ecs/intellichoice-staging-learning-api \
  --correlation-log-group /ecs/intellichoice-staging-chat-api \
  --correlation-stream-prefix learning-api \
  --correlation-stream-prefix chat-api \
  --collector-log-group /ecs/intellichoice-staging-learning-api \
  --collector-log-group /ecs/intellichoice-staging-chat-api \
  --out-json docs/resume_evidence/06_eval_observability/trace_coverage_results.json \
  --out-csv docs/resume_evidence/06_eval_observability/trace_coverage_summary.csv
```

Runtime is dominated by `BatchGetTraces` (5 traces per call, 13,571 traces). It ran at
~48 traces/s cold and degraded to ~1/s under accumulated X-Ray API throttling during this
session; budget 5–60 minutes for the learning window depending on recent X-Ray call
volume. The `--window` bound is X-Ray's own 6-hour maximum per `GetTraceSummaries` range.

## 13. Limitations

- **Two windows, 14,005 traces, one deployed build, one day.** Both windows are on
  `gha-5fa15d491057`. Nothing here says anything about other builds or about day-to-day
  variance.
- **Simulated traffic.** The learning window is k6 load-test traffic ("validated at 25
  concurrent users"), and the chat window is a post-deploy burst. Neither is organic user
  traffic, and no real student or parent was involved.
- **Learning-path bias.** 12,559 of the 12,888 authenticated 2xx traces are learning
  routes, which make no model calls by design. The Bedrock hop rests on 120 traces and the
  MCP hop on none.
- **The MCP hop is unmeasured** (§7), so "trace coverage 100%" covers four of the five
  named hops. Saying otherwise would be the AUD-F-30 error in a new place.
- **Merged traces inflate slightly.** In the 19 (learning) + 1 (chat) merged traces, the
  nested request's spans sit inside the host trace, so the host route's chain can be
  satisfied by evidence belonging to a different request. The effect is bounded at
  20/12,888 = 0.16% and can only inflate coverage, never deflate it. The harness reports
  the count so the bound is checkable.
- **EMF log groups are 1-day retention**, so no metric-side corroboration is available for
  windows older than a day; the app log groups (30 days) and X-Ray (30 days) are what this
  rests on.
- **Export-failure rate is not obtainable** without a collector config change (§8). The
  absence of error lines in two short windows is much weaker than a continuous rate.
- **The collision's mechanism is a hypothesis.** The measurement — 19 shared ids, same
  task, distinct span ids, cross-route in 5 cases, replicated in a second service — is
  evidence. The keep-alive context-leak explanation is not.

## 14. Verification

- `make lint` — clean on the final tree (`ruff check` + `ruff format --check`, 476 files).
- `make typecheck` — clean on the final tree (`pyright`: 0 errors, 0 warnings).
- `make test` — **2,170 passed, 2 skipped, 1 xfailed** in 541 s, 2,173 collected, of which
  **28 are new** in `packages/observability/tests/test_e6_2_trace_coverage.py` (pre-change
  baseline 2,145).
- **One caveat, stated rather than glossed.** That full-suite run was taken on a tree that
  differs from the final one by a single behaviour-preserving edit made afterwards in
  review: an empty `if not is_entry: pass / else:` branch in `facts_from_documents` was
  rewritten as `if is_entry:`, plus docstring wording. On the **final** tree, `make lint`
  and `make typecheck` are green and all **28** E6.2 tests pass; no other test module in
  the repository imports the harness, so nothing else could be affected. A re-run of the
  whole suite on the final tree was started and abandoned after an hour at 26% — the
  machine's Docker VM was pinned at 93% CPU with the host out of free memory, starving the
  shared dev Postgres. That is an environment condition, not a signal about the code, and
  it is recorded here rather than papered over.
- **No product code changed.** The diff is one new harness file, one new test file, and
  the three artifacts in this directory.
- The classifier's tests run on literal X-Ray span trees — no AWS, no network, no
  filesystem — and pin the four failure modes that would make this report confidently
  wrong: an orphan SQL segment satisfying a hop, a 429 scored as a missing span, a
  genuinely missing span going unreported, and a per-hop denominator counting routes that
  never expected the hop.
