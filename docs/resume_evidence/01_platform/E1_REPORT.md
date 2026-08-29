# E1 — Sustained load, saturation, and SSE delivery at scale

> **Program:** `docs/resume_evidence/MEASUREMENT_PLAN.md` Theme 1 (E1.1, E1.2, E1.3).
> **Date:** 2026-08-29. **Repo SHA:** `bd3ad7a`. **Deployed image:** `learning-api:gha-5fa15d491057`
> (task definition `intellichoice-staging-learning-api:153`).
> **Environments, never blurred:** *deployed staging, simulated load-test traffic* (E1.1, E1.2
> staging tier) and *local 2-process rig* (E1.2 local tier). Production is never touched (D-152).
> **Model spend:** E1.1 **$0** — the learning path makes no model calls and k6 opens no SSE
> stream. E1.2's staging tier is **not** $0; see "Cost" below.

Every number below is reproducible from an artifact in this directory. Rates carry their
denominator; latencies carry p50/p95/p99.

---

## Headline results

| Claim | Measured | Artifact |
|---|---|---|
| **Sustained throughput** — the repository's first steady-state RPS from a harness | **22.36 req/s** over 10 min at 25 VUs (13,550 requests, 970 complete flows, 9,668 answers) | `raw/sustained_25vu_10m.json` |
| Steady-state (warm) throughput and latency | **21.75 req/s**, p50 859 ms · p95 3,081 ms · p99 4,830 ms over 11,898 warm requests | `sweep_metrics.csv` |
| Sustained error rate | **0 5xx**; 5 non-2xx in 13,550 = **0.037%**, all HTTP 409 (correct conflict handling) | `raw/sustained_25vu_10m.json` |
| **SSE delivery, local 2-process rig** | **1,100 / 1,100 events delivered (100%)**, of which **550/550 crossed a real Postgres `NOTIFY`**; 0 lost, 0 duplicate | `sse_local_results.json` |
| **SSE delivery, deployed staging** | **240 / 240 events delivered (100%)** across **3 live replicas** (93 / 93 / 93 request split); 0 lost, 0 duplicate, 0 reconnects | `sse_staging_results.json` |
| **Saturation knee** | Throughput flat at ~15–20 req/s from 10 → 50 VUs while p95 rises 1.0 s → 2.8 s → 8.8 s; **app CPU pinned ≥ 92% from 25 VUs up** | `cloudwatch_join.json` |
| **New capacity defect found** | At 50 VUs the ALB step policy scaled 2 → 3 tasks and the third replica's connection pool **exhausted Postgres's connection slots** — 2 × HTTP 500 | this report, §"The capacity ceiling" |

---

## E1.1 — Repeat-trial burst sweep (deployed staging)

Repeat trials at each level, all through the real CloudFront edge, `per-vu-iterations`
executor (the baseline script's shape), 2-minute gaps. Medians with full ranges — the point of
repeating them at all (Theme 1's weakness 4 was "single-run p95s"). Three trials were run at
every level; the 10-VU level reports two, for the reason directly below the table.

| VUs | Replicas | Trials | Requests OK | RPS median [range] | p95 median [range] | p99 median | 5xx |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 2 | 2 | 280 / 280 | 20.24 [19.91–20.58] | 1,013 ms [975–1,051] | 1,310 ms | 0 |
| 25 | 2 | 3 | 1,050 / 1,050 | 18.39 [17.85–20.32] | 2,829 ms [2,207–3,204] | 3,545 ms | 0 |
| 50 | 2→3 | 3 | 2,098 / 2,100 | 15.30 [13.46–16.79] | 8,785 ms [8,392–9,630] | 10,440 ms | **2** |
| 10 | **3** | 2 | 280 / 280 | 28.49 [28.22–28.76] | 609 ms [571–648] | 731 ms | 0 |

Per-trial rows, timeouts, 4xx/5xx and the cold/warm split: `sweep_metrics.csv`.

**The 10-VU level has two trials, not three.** Its third trial's raw summary was destroyed by an
operator error while launching the sustained leg (macOS `seq 1 0` counts *down*, so a `TRIALS=0`
invocation re-ran a burst over a saved file). The lost trial's console numbers are recorded in
`raw/NOTES.md` and are deliberately **not** used in any median here — an evidence program should
not quote numbers whose artifact it cannot produce. The runner now refuses to overwrite a saved
summary and guards the loop, so neither half can recur.

### Where the time actually goes at 50 VUs

Per-step Trends make the aggregate p95 legible — the mistake D-116 had to correct on chat, where
a cheap call flattered the number:

| Step | p50 | p95 | max |
|---|---:|---:|---:|
| `/dev/token` | 205 ms | 271 ms | 273 ms |
| `POST /learning/sessions` | 96 ms | 146 ms | 159 ms |
| `POST .../student` | 2,493 ms | 8,715 ms | 8,781 ms |
| **`POST .../topics`** | **8,986 ms** | **10,967 ms** | 12,112 ms |
| `POST .../answers` | 2,756 ms | 4,399 ms | 11,711 ms |
| whole flow | 41,350 ms | 41,683 ms | 41,695 ms |

Exam assembly (`/topics`) dominates. Session creation stays flat under load, so the pressure is
in the per-student work, not in request handling.

### E1.3 — the saturation knee, read off the same runs

Throughput does **not** grow with concurrency: 20.2 → 18.4 → 15.3 req/s as VUs go 10 → 25 → 50,
while p95 grows ~8.7×. That is a system already past its knee at 10 VUs on two tasks, and it is
consistent with D-134/D-136's published capacity law (saturation at ~5 concurrent per task —
here, 25 VUs / 2 tasks = 12.5 concurrent per task is well beyond it). The binding resource is
visible in the join: **ECS CPU is 92–99% from 25 VUs upward.**

Adding the third replica is the control that confirms it: at 10 VUs, 3 tasks served **+41%
throughput at −40% p95** versus 2 tasks (28.49 vs 20.24 req/s; 609 ms vs 1,013 ms p95). The
service is CPU-bound and scales with replicas — right up to the ceiling in the next section.

### The capacity ceiling — a real defect this sweep found

**The sweep stopped itself at `burst_50vu_t3` on its own D-455 stop rule (2 × HTTP 500), and the
cause turned out to be new.**

```
asyncpg.exceptions.TooManyConnectionsError:
  remaining connection slots are reserved for roles with the SUPERUSER attribute
```

Both 500s were `POST /answers` at 2026-08-29T19:34:21Z, on a log stream belonging to a **third**
ECS task that had not existed earlier in the sweep. The mechanism, from `cloudwatch_join.json`:

| Run | Tasks | DB conns (1-min max) | ECS CPU | RDS CPU | ALB p95 | 5xx |
|---|---:|---:|---:|---:|---:|---:|
| `burst_50vu_t1` | 2 | 39 | 99.5% | 33.9% | 8.60 s | 0 |
| `burst_50vu_t2` | 2 | 59 | 94.1% | 43.5% | 8.49 s | 0 |
| `burst_50vu_t3` | **3** | 62 | 95.7% | 65.4% | 10.56 s | **2** |

The ALB p95 step policy scaled learning-api 2 → 3 during `t3`. Each task opens a SQLAlchemy pool
(10 + 10 overflow) **plus two dedicated relay connections** (the `LISTEN` and `NOTIFY`
connections D-335 deliberately keeps outside the pool), against a `db.t4g.micro` whose
`max_connections` is the default `LEAST({DBInstanceClassMemory/9531392}, 5000)` ≈ 112 — shared
with chat-api and the ops task. The third replica's pool is what crossed the ceiling.

**This is the D-334 shape again: a failure mode that gets *worse* as the service scales out.**
Autoscaling is supposed to add capacity; here it added the failure.

Two things worth keeping from how it was found:

- **CloudWatch alone would not have found it.** `DatabaseConnections` is sampled about once a
  minute and peaks at 62 — comfortably under the limit. Postgres refused connections in a
  sub-minute spike the metric never sampled. The 500 in the application log is the only witness.
- **The instrument stopping itself is what made it legible.** The runner aborted at the first
  5xx rather than averaging two failures into 2,100 requests and reporting 99.9% success.

**Not fixed here.** Terraform capacity, pool sizing and alarm thresholds are all outside this
task's decision boundaries (E1's spec: findings reported, not fixed). Reported for triage.

### Alarm behaviour

`intellichoice-staging-learning-api-p95-latency` went `OK → ALARM` at 19:34:18Z and back to `OK`
at 19:40:18Z — during and after `burst_50vu_t3`. This is the known, accepted behaviour recorded
in D-456; both transitions are in `cloudwatch_join.json`.

---

## E1.1 — the sustained run (the number that did not exist before)

Every k6 scenario in this repository was `per-vu-iterations` — a burst snapshot that ends before
a steady state exists, which is why no harness here had ever produced an RPS figure. This is a
`constant-vus` run: **25 VUs, 10 minutes**.

| | Whole run | Cold (first 60 s) | **Warm (steady state)** |
|---|---:|---:|---:|
| Requests | 13,550 | 1,652 | **11,898** |
| Throughput | 22.36 req/s | 27.53 req/s | **21.75 req/s** |
| p50 | 833 ms | 647 ms | **859 ms** |
| p95 | 3,105 ms | 3,260 ms | **3,081 ms** |
| p99 | 4,957 ms | 5,515 ms | **4,830 ms** |
| max | 15,116 ms | 7,589 ms | 15,116 ms |

970 complete flows, 9,668 answers submitted, **0 5xx**. The 5 non-2xx responses (0.037%) were
all **HTTP 409** — 3 on `/topics`, 2 on `/answers` — which is the `pg_try_advisory_xact_lock`
turn guard (D-376/D-346) correctly refusing a second concurrent turn on one session, not a
fault. Two `/readyz` 503s also appear in the window, consistent with 96% app CPU.

The cold window is *faster* than the warm one here, which is the opposite of the usual warm-up
story and worth stating plainly: the run began with the service already scaled to 3 tasks and an
empty request backlog, so the first minute ran under-loaded before the offered load caught up.

**Starting condition, stated because it bounds comparability:** this run began at **3 tasks**,
not 2 — the service had scaled out during the 50-VU trials and had not scaled back in (the
scale-in reluctance D-182 documents). So the sustained numbers are *not* directly comparable with
the 25-VU 2-task bursts above, and they are the more interesting condition anyway, since 3 tasks
is where the connection ceiling lives. RDS CPU reached **82.7%** and the CPU credit balance drifted
288 → 275 over the run — the database is the next constraint after app CPU, and it is close.

---

## E1.2 — SSE delivery at scale

Theme 1's weaknesses 2 and 3: SSE had never been measured at scale on staging, and cross-replica
correctness had only ever been measured at ~1 concurrent session (10 sequential rounds, D-349).

### Local tier — two real uvicorn processes, one Postgres

50 concurrent streams, 22 driven events each, under 20 concurrent background load workers.

| | Result |
|---|---|
| Expected deliveries | **1,100** |
| Delivered | **1,100 / 1,100 (100.00%)** |
| **Cross-process arm** (POSTs to the *other* process — every delivery crossed a real `LISTEN`/`NOTIFY`) | **550 / 550 (100.00%)** |
| Same-process control arm | 550 / 550 (100.00%) |
| Lost / duplicate / unmatched frames | **0 / 0 / 0** |
| Ordering | **0 out of order at 100 content-decidable transitions (100 agreed)** |
| Push latency | p50 864 ms · p95 2,976 ms · p99 4,047 ms |
| Concurrent load during delivery | 110 flows / 806 requests / 0 errors |

Two real processes, not two `SessionEventBus` objects in one — a simulated replica pair proves
nothing about `LISTEN`/`NOTIFY`, which is the mechanism under test. The **control arm is what
makes the cross arm mean something**: if both failed, the bus would be broken; only the cross arm
failing would indict the relay. A rig misconfiguration (both ports on one process) would have
scored 100% for the wrong reason, so a cross-process canary runs first and the harness exits
rather than reporting a number it cannot stand behind.

This is also, incidentally, a regression test for D-395 at scale: 50 sessions publishing
concurrently through **one** `asyncpg` publisher connection per process is exactly the burst
regime where four of five events were once lost to `another operation is in progress`.

### Staging tier — the deployed 2-task (here 3-task) service

20 concurrent streams through CloudFront, 12 driven events each.

| | Result |
|---|---|
| Expected deliveries | **240** |
| Delivered (pushed) | **240 / 240 (100.00%)** |
| Lost / duplicate | **0 / 0** |
| Reconnects (counted separately from losses) | **0** — 19 keepalives held the streams open |
| Ordering | **0 out of order at 20 content-decidable transitions (20 agreed)** |
| Push latency | p50 604 ms · p95 1,265 ms · p99 1,848 ms |
| **Cross-replica evidence** (D-349's per-task log-stream method) | **93 / 93 / 93 requests across 3 task log streams** |

**The replica split is what makes 240/240 a claim rather than a coincidence.** An even three-way
split proves the load genuinely crossed every live replica; before the D-335 relay, the roughly
two-thirds of events whose POST landed away from the stream would have reached nobody — which is
what D-334's 2-of-4 measured. This supersedes D-349's `10/10 with a 12/8 split` as the headline:
**24× the events, across three replicas instead of two, at 20× the concurrency.**

The harness refuses to conclude from one log stream, however good its delivery rate looks.

### Cost

E1.2's staging tier is **not $0**. Each session's first `/stream` connect fires `pre_intro`, one
real Bedrock call (`routers/stream.py`, S26/D-075), idempotent per session — so ≤ 21 Haiku 4.5
stage-narrative calls per run, single-digit cents. Stated rather than inherited from E1.1's $0
label. The local tier runs `MockBedrockProvider` and is free.


## Method

### E1.1 — how the sweep was run

`benchmarks/resume_evidence/01_platform/run_e1_sweep.sh` ran the whole sweep unattended, saving
each trial's k6 summary verbatim and recording each run's own UTC window to
`raw/sweep_manifest.jsonl`. The window is what makes the CloudWatch join possible at all: a
hand-kept note of "roughly 19:28-ish" cannot be joined to a 60-second metric period.

The k6 script is **new** (`load-tests/k6/learning_sessions_staging_sustained.js`) and the
existing `learning_sessions_staging.js` is **unmodified**. That was deliberate: the existing
script's shape is the comparability baseline behind D-129 and D-456, and changing its executor
would silently redefine every staging learning number this repository has published. The new
script copies the flow, the per-step Trends and the anti-vacuity thresholds verbatim, and adds
only an env-selected executor (`burst` = the old `per-vu-iterations` shape, `sustained` =
`constant-vus` for a duration) plus an `http_reqs` rate threshold.

### E1.2 — how delivery was accounted

Both tiers use one pure ledger (`benchmarks/resume_evidence/01_platform/sse_ledger.py`) under
three rules, each of which exists because the obvious alternative produces a false pass:

1. **The initial snapshot is never a delivery.** `/stream` yields the current checkpoint on
   every (re)connect before it reads the queue, so a stream whose relay is completely dead still
   receives one frame. Counting it is exactly how a 2-of-4 delivery rate (D-334) could be
   reported as 4-of-4.
2. **Delivery is credited ordinally, one action at a time.** The driver issues action *k* and
   waits for its frame before issuing *k+1*, so at most one event is ever outstanding per stream
   and the frame-to-action mapping is unambiguous by construction. A frame arriving with no
   action outstanding is recorded as an unmatched frame — which is what a duplicate looks like
   from here.
3. **Ordering is reported only where content can decide it.** See "What this cannot show".

### Verifying the instrument

`apps/learning-api/tests/test_e1_sse_ledger.py` (26 tests) covers the ledger and the k6 summary
parser on literals — no network, no Postgres, no k6. The three that matter most:

- the initial snapshot is not credited as a delivery;
- k6's exported threshold boolean means **failed**, not passed (verified empirically against a
  deliberately-breached threshold before the sweep ran — reading it backwards would invert every
  pass/fail in this report while leaving every latency correct);
- the sweep's D-455 stop rule, including `test_the_runner_and_this_module_apply_the_same_stop_rule`,
  which executes the runner's own inline copy of the rule against shared fixtures and asserts the
  two agree. The duplication is deliberate — the runner must be able to abort a live staging
  sweep without depending on a Python import — and that test is what makes it safe.

## What this cannot show

Stated here rather than left for a reader to discover, because each of these bounds a claim
somebody could otherwise over-read off the tables above.

- **Two fixture students, cycled.** Staging seeds four students and only two are
  attendance-present (`student-ext-1`, `student-ext-4`); every VU and every stream cycles over
  that pair. Sessions are independent — checkpoint, assessment session and idempotency key are
  all per-session — so this is a valid **concurrency** measurement. It is not the ">100 distinct
  students" shape SPEC §6.23 asks for, and it does not exercise per-student mastery contention.
- **Load-test traffic, not users.** Everything here is simulated load against deployed
  **staging**. Nothing in this report says anything about production, which this program never
  touches (D-152).
- **A 3-task autoscaling ceiling.** The service scales 2→3 on ALB p95 step policy and stops
  there by Terraform. The 50-VU level therefore measures a *capped* system; raising the cap is
  product work and out of scope, so the saturation knee is reported as measured rather than
  chased.
- **A single-day window.** Every number here was taken on 2026-08-29 against one deployed build.
  Repeat trials bound run-to-run variance within that window; they say nothing about day-to-day
  drift.
- **CloudWatch dilutes short runs.** The minimum standard period is 60 s and a burst trial lasts
  tens of seconds, so per-trial utilization is a mostly-idle bucket. Each run in
  `cloudwatch_join.json` carries a `dilution_note` saying so; the sustained run is the one whose
  utilization figures describe the load itself.
- **Ordering is largely undecidable on this event sequence, by measurement, not by defect.**
  During `pre_exam` every event serializes to identical JSON — an answer whose correctness is
  masked (D-064) changes no snapshot field — so the frames carry no information a reordering
  could disturb. The ledger reports how many events were content-decidable next to how many were
  out of order, rather than printing a reassuring `out_of_order: 0` over frames that could not
  have shown one. This is not a product gap: an SSE event here is a **complete** snapshot the
  client swaps in whole (`services/session_events.py`), so a late frame overwrites with equally
  current state and ordering is not a correctness property.
- **The relay's own SSE metrics are still not exported to CloudWatch.** `SSE_EVENTS_DELIVERED`,
  `SSE_CONNECTIONS` and `SSE_RELAY_FAILURES` exist in code and are not in the collector config.
  That is why delivery is accounted **in the harness** rather than read off a dashboard. Fixing
  the collector was explicitly out of scope for this task; it is reported, not fixed.


## Reproducing this

Every command that produced an artifact here, in order. All staging reads use the
`jeongsik-staging-admin` profile and are read-only apart from the load traffic itself.

```bash
# E1.1 — the sweep (3 x {10,25,50} VU bursts, 2-minute gaps, then 25 VU x 10 min sustained).
# Runs unattended, saves every k6 summary, and aborts on its own stop rule.
AWS_PROFILE=jeongsik-staging-admin caffeinate -i -s   benchmarks/resume_evidence/01_platform/run_e1_sweep.sh

# A single trial, if you want one by hand:
AWS_PROFILE=jeongsik-staging-admin make load-staging-learning-sustained   VUS=25 SCENARIO=burst SUMMARY_OUT=docs/resume_evidence/01_platform/raw/burst_25vu_t1.json
AWS_PROFILE=jeongsik-staging-admin make load-staging-learning-sustained   VUS=25 SCENARIO=sustained DURATION=10m   SUMMARY_OUT=docs/resume_evidence/01_platform/raw/sustained_25vu_10m.json

# E1.1 — the table and the CloudWatch join
python3 benchmarks/resume_evidence/01_platform/k6_summary.py   --manifest docs/resume_evidence/01_platform/raw/sweep_manifest.jsonl   --csv docs/resume_evidence/01_platform/sweep_metrics.csv   --json docs/resume_evidence/01_platform/sweep_metrics.json
AWS_PROFILE=jeongsik-staging-admin uv run python   benchmarks/resume_evidence/01_platform/collect_e1_cloudwatch.py   --manifest docs/resume_evidence/01_platform/raw/sweep_manifest.jsonl   --out docs/resume_evidence/01_platform/cloudwatch_join.json

# E1.2 local tier. NEVER run this concurrently with `make test` - shared dev Postgres.
docker compose up -d postgres mysql
uv run python load-tests/loadtest_fixtures.py --count 80
uv run uvicorn learning_api.main:app --port 8101 &
uv run uvicorn learning_api.main:app --port 8102 &
uv run python benchmarks/resume_evidence/01_platform/sse_scale_local.py   --sessions 50 --events-per-session 22 --background-workers 20   --out docs/resume_evidence/01_platform/sse_local_results.json
uv run python load-tests/loadtest_fixtures.py --cleanup

# E1.2 staging tier. Fetches the token secret itself; never exports or prints it.
AWS_PROFILE=jeongsik-staging-admin uv run python   benchmarks/resume_evidence/01_platform/sse_scale_staging.py   --streams 20 --events-per-stream 12   --out docs/resume_evidence/01_platform/sse_staging_results.json
```

**Secret handling.** The staging `/dev/token` secret is fetched per-use and never printed,
exported, or written to an artifact. The Makefile target copies `load-staging-learning`'s inline
Secrets Manager fetch verbatim and passes the value as a bare `-e NAME` pass-through, so it never
reaches a command line; `sse_scale_staging.py` fetches it in-process through an argument-list
subprocess with no shell, which is D-310's rule. Verified after the fact: the live secret value
appears in **0** files across this directory, the harness code, the Makefile and the k6 script,
and no JWT appears in any artifact.

## Verification

`make lint typecheck test` at `bd3ad7a` with these changes: **lint clean, pyright 0 errors,
2,091 passed / 2 skipped / 1 xfailed**. New tests: `apps/learning-api/tests/test_e1_sse_ledger.py`
(29). No product code was modified — the diff is one additive `Makefile` target, one new k6
script, the harness directory, and the test file. `load-tests/k6/learning_sessions_staging.js` is
byte-for-byte unchanged, deliberately.
