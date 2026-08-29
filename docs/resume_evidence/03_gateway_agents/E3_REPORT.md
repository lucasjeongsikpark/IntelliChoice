# E3 — Gateway concurrency/overshoot, failure matrix, and the HITL bypass denominator

> Experiments **E3.1 – E3.4** of `docs/resume_evidence/MEASUREMENT_PLAN.md` (Theme 3).
> Generated: **2026-08-29** at repository `62372ceebaba9d10063c3fcbe70b1ff2b60ed1e5`.
> Cost of every measurement below: **$0** — no model call, no network, no AWS, no staging.
> Environments, never blurred:
> - E3.1/E3.2 — **local simulation**: a *real* Postgres advisory-lock ledger
>   (docker-compose `pgvector/pgvector:pg16`, localhost:5432) driven by a **mock model with
>   injected latency**.
> - E3.3 — **local simulation**: the *real* `ResilientBedrockGateway` with a scripted
>   in-process provider. No network at any point.
> - E3.4 — **local**: permanent pytest suites against the real routes, real graphs and the
>   real MCP registry, with the apps' own dev fakes for Gmail/Calendar/Maps.
>
> Nothing here is a *quality* result, and nothing here was measured on production or on
> deployed staging. This is concurrency-correctness, cost-containment and
> authorization-boundary evidence.

Harnesses:

- `benchmarks/resume_evidence/03_gateway_agents/overshoot_benchmark.py` (E3.1, E3.2)
- `benchmarks/resume_evidence/03_gateway_agents/failure_matrix.py` (E3.3)
- `benchmarks/resume_evidence/03_gateway_agents/hitl_bypass_inventory.py` (E3.4 denominator)

Artifacts: `overshoot_results.json` (252 trials), `overshoot_table.csv` (84 cells),
`failure_matrix.json` / `failure_matrix.csv` (24 cells + 4 half-open probes),
`hitl_bypass_inventory.json` (91 catalogued cases).

---

## 1. Headline

- **Reserve-then-settle holds at 20× the concurrency it was ever tested at.** 252 trials
  across N ∈ {10, 50, 100, 200} concurrent, three ceiling surfaces, three call-latency
  arms: the shipped ledger's overshoot is **1.000× in all 36 divisible-ceiling cells**, and
  **0 grants beyond capacity, 0 errors, in all 126 fixed-arm trials**.
- **The pre-fix logic, same workload, same machine:** up to **9.0× the ceiling** (the real
  report ceiling, 200 concurrent) and **8.0×** on the real tutor-chat ceiling. The
  read-then-act ledger admits everyone, so its overshoot is simply N × estimate / ceiling —
  which is why it grows without bound as concurrency does.
- **The mock's speed really does hide the defect, and now there is a number for it.** At a
  0 ms call (what `MockBedrockProvider` does), the *unfixed* ledger measures **2.54×** at
  N=200; the same code at a 250 ms call measures **4.00×**. A benchmark built on mock speed
  would have under-reported the defect by **36%** — D-110 §2's lesson, quantified rather
  than narrated.
- **Circuit-breaker economics, measured:** under a sustained instantly-failing provider,
  300 logical requests produced **36 provider calls** — a retry amplification of **0.12**
  against the **3.0** a bounded-retry policy with no breaker would have reached, i.e.
  **96%** of the calls a real outage would otherwise bill for were suppressed. A
  structured-output failure, by contrast, produces **0 circuit opens** — 100 concurrent
  schema failures per burst in every trial, and 50 consecutive in the half-open probe
  (D-115's separation, verified).
- **The HITL denominator now exists: 84 bypass attempts, 0 unauthorized external side
  effects.** Up from 1 explicit adversarial case. Plus 4 controls (so the suite cannot pass
  by refusing everything), 2 documented findings and 1 architectural boundary note, all
  counted separately.

---

## 2. E3.1 / E3.2 — concurrency, overshoot, and the before/after arm

### 2.1 Method

For each cell, N coroutines run a real `reserve → model call → settle` flow against one
`(scope, subject)` pair. Both arms write to `cost_reservations` and both are measured by
the same `coalesce(actual, reserved)` sum the ceiling itself uses, so "what was spent" and
"what the ceiling would see" are one number.

| arm | what it is |
|---|---|
| `fixed` | the shipped `CostReservationRepository`: `pg_advisory_xact_lock(hashtext(scope:subject))`, reserve committed *before* the call, settle after |
| `baseline` | **E3.2** — `ReadThenActLedger`, the pre-D-110 shape reproduced **in the harness only**: read committed spend, no lock, nothing written until after the model call |

Three call-latency arms, and the first is a deliberate negative control:

| delay | why |
|---|---|
| **0 ms** | `MockBedrockProvider`'s own speed. D-110 §2: at this speed ten concurrent callers produced 1 grant and 1.0× *against the broken code* — "it looked fixed before it was fixed". Kept as a control so this benchmark can show the false negative rather than assert it. |
| **250 ms** | D-110's calibrated probe value: the smallest window that made the race visible. |
| **3 s** | A realistic single-call slice. D-343 measured whole cited chat turns at 6.2–10.9 s across several gateway calls; D-110 cites a 26.9 s p50 for the real report call. 3 s therefore **understates** the real window, which makes every baseline number below a lower bound. |

Ceiling shapes are the three real product surfaces, with their estimate constants imported
from product code rather than restated:

| shape | scope | estimate (¢) | production ceiling (¢) | subject |
|---|---|---:|---:|---|
| `report` | `student_report` | 2.25 | 50.0 | per student |
| `tutor_chat` | `tutor_chat` | 4.0 | 100.0 | per student |
| `chat_turn` | `chat_turn` | 25.0 | 1500.0 | the constant `SUBJECT_CHAT_API` — **one advisory lock for the whole app** |

Two ceiling bases. `derived_k` sets ceiling = k × estimate with k = N//4, so exact
divisibility isolates the concurrency property; `production_constant` uses the app's real
ceiling, where the estimate does not always divide it (§2.4).

3 trials per cell; medians reported with the range.

### 2.2 The fixed arm

**Every `derived_k` cell: overshoot 1.000×, granted exactly k, grants-beyond-k 0, errors 0.**
36 cells (3 shapes × 4 N × 3 delays), 108 trials. The ledger admits exactly the number of
callers the ceiling pays for and rejects the rest, at every concurrency level and at every
call latency.

| shape | N | k | granted (median) | overshoot (median, range) | wall clock (3 s arm) | reservations/s |
|---|---:|---:|---:|---|---:|---:|
| report | 10 | 2 | 2 | 1.000 [1.000, 1.000] | 3.05 s | 3.3 |
| report | 50 | 12 | 12 | 1.000 [1.000, 1.000] | 3.33 s | 15.0 |
| report | 100 | 25 | 25 | 1.000 [1.000, 1.000] | 3.36 s | 29.7 |
| report | 200 | 50 | 50 | 1.000 [1.000, 1.000] | 3.44 s | 58.2 |

`tutor_chat` and `chat_turn` are identical to three decimal places at every N — including
`chat_turn`, whose production subject is a single global constant, so all 200 callers
contend on **one** advisory lock. The full 84-cell table is `overshoot_table.csv`.

The throughput column is worth reading carefully, because it is dominated by the injected
call rather than by the ledger: 200 concurrent reservations complete in **3.44 s** against
a 3.00 s call, so the whole serialized admission path costs about **0.44 s for 200 callers
(~2.2 ms each)**. The ledger's own cost is better read off the 0 ms arm, where nothing but
the ledger is happening: 200 concurrent `reserve` + `settle` round trips in **0.675 s**,
**296 reservations/second**, against a single advisory lock. That is the design claim made
measurable — the lock is held across a sum and an insert and never across the model call,
so serializing admission costs single-digit milliseconds per caller while the expensive
part of every request runs fully in parallel.

### 2.3 The baseline arm (E3.2), and the mock-speed control

Same workload, same machine, read-then-act ledger:

| shape | N | k | delay | granted | overshoot |
|---|---:|---:|---:|---:|---:|
| report | 10 | 2 | 250 ms | 10/10 | **5.00×** |
| report | 50 | 12 | 250 ms | 50/50 | **4.17×** |
| report | 100 | 25 | 250 ms | 100/100 | **4.00×** |
| report | 200 | 50 | 250 ms | 200/200 | **4.00×** |

At 250 ms and 3 s the result is total: **every** caller is admitted, at every N, on all
three surfaces. The ceiling does not bound anything, because no caller can see another's
in-flight spend.

Now the control arm, and this is the methodological point of the whole experiment:

| shape | N | delay | granted (median, range) | overshoot (median, range) |
|---|---:|---:|---|---|
| report | 100 | **0 ms** | 81 [79, 89] | **3.24× [3.16, 3.56]** |
| report | 100 | 250 ms | 100 [100, 100] | 4.00× [4.00, 4.00] |
| report | 200 | **0 ms** | 127 [113, 158] | **2.54× [2.26, 3.16]** |
| report | 200 | 250 ms | 200 [200, 200] | 4.00× [4.00, 4.00] |
| tutor_chat | 200 | **0 ms** | 129 [127, 153] | **2.58×** |
| tutor_chat | 200 | 250 ms | 200 [200, 200] | 4.00× |

With a 0 ms model call, some callers commit before others read, so the broken ledger
partly self-corrects and the measured overshoot falls by **36%** (2.54× vs 4.00×) at
N=200 and by **19%** at N=100. It also becomes *noisy* — a 113–158 grant range across
three identical trials, versus 200/200/200 every time at 250 ms. **A cost-race benchmark
built on the mock's speed under-reports the defect and does so unstably.** D-110 recorded
this qualitatively after being bitten by it; this is the quantity.

(At N=10 and N=50 the three delay arms agree, because the connection pool cannot stagger
that few callers enough to matter. The false negative is a large-N phenomenon — which is
the regime a load test would be run in.)

### 2.4 Production ceilings, and the one cell that is not 1.000×

Run at the real constants, 200 concurrent, 3 s call:

| shape | ceiling | estimate | arm | granted | spend | overshoot |
|---|---:|---:|---|---:|---:|---:|
| report | 50.0¢ | 2.25¢ | fixed | 23 | 51.75¢ | **1.035×** |
| report | 50.0¢ | 2.25¢ | baseline | 200 | 450.00¢ | **9.00×** |
| tutor_chat | 100.0¢ | 4.0¢ | fixed | 25 | 100.00¢ | 1.000× |
| tutor_chat | 100.0¢ | 4.0¢ | baseline | 200 | 800.00¢ | **8.00×** |
| chat_turn | 1500.0¢ | 25.0¢ | fixed | 60 | 1500.00¢ | 1.000× |
| chat_turn | 1500.0¢ | 25.0¢ | baseline | 200 | 5000.00¢ | **3.33×** |

The **8.00×** on the tutor-chat ceiling happens to be the same number D-110 recorded live
for the pre-fix code, but that is a coincidence of this cell's N and ceiling rather than a
reproduction of D-110's conditions (its 8× was at n=10 against the ceilings of the time).
The reproduced *behaviour* is what matters and it is unambiguous: a clean-room
re-implementation of the described read-then-act logic admits every concurrent caller on
every surface, and the ceiling bounds nothing.

**The 1.035× is real and is reported rather than smoothed.** `reserve` tests
`spend >= ceiling` *before* adding this call's estimate, so the last admitted caller may
cross the line by up to one estimate. 22 × 2.25 = 49.50 < 50, so a 23rd caller is admitted
and the day ends at 51.75¢. The bound is exact and cheap to state:

> **overshoot ≤ 1 + estimate/ceiling**, and = 1.000 exactly when the estimate divides the
> ceiling.

For the three shipped surfaces that bound is 1.045× (report), 1.04× (tutor chat) and
1.017× (chat turn) — at most **2.25¢** of over-spend on a 50¢ daily ceiling. This is a
design property, not a defect: admitting a caller and then charging it is what makes the
reservation visible before the call, and the alternative (refuse anyone whose estimate
would cross the line) would reject a caller whose *actual* cost usually settles well below
its worst-case estimate. Recorded here so the "1.0×" claim is never made where 1.035× is
the truth.

The `chat_turn` N=50 row reads 0.833× in both arms — 50 callers × 25¢ = 1250¢ never
reaches the 1500¢ ceiling, so nothing is rejected and there is no race to lose. It is in
the artifact for completeness; it measures nothing.

### 2.5 Limitations (E3.1/E3.2)

- **Single-process, single-event-loop asyncio.** Real traffic is multi-process across ECS
  tasks. The *ledger* is genuinely shared — every reservation really commits to Postgres
  and the advisory lock is a database lock, so the serialization point under test is the
  production one — but the client-side interleaving is cooperative, not pre-emptive. A
  multi-process rig was out of scope for this task and would be a different experiment.
- Wall clock and reservations/second are local-Postgres numbers on one developer machine,
  not staging numbers.
- The model call is a mock with an injected floor. It is a **stand-in for duration only**;
  no property of a real model response is exercised here.
- Load is simulated. The right sentence is "the ledger was validated at 200 concurrent
  reservations", never "served 200 users".

---

## 3. E3.3 — failure-injection matrix under concurrency

### 3.1 Method

Bursts of N concurrent `generate_structured` calls through the **real**
`ResilientBedrockGateway` at its shipped settings (`max_retries=2`,
`backoff_base_s=0.5`, `circuit_failure_threshold=5`), with a scripted provider injecting
one failure mode. Half of the logical requests are **transient** (fail their first attempt,
succeed after) and half **persistent**, so recovery rate has a denominator that can move.
The request index travels in the payload, so provider attempts can be attributed to logical
requests — which is what makes retry amplification a measurement rather than an inference.

Two values are compressed so the run finishes, and both are stated rather than buried:
`circuit_cooldown_s` is 1.0 s for the matrix and 0.5 s for the half-open probe (shipped:
30 s), and the `timeout` mode uses `call_timeout_s=0.05` against a 0.5 s injected hang
(shipped: 20 s, or a per-call override — D-233). Everything else is the shipped
configuration, and neither compression changes *which* branch a failure takes; they change
only how long it takes to get there. 3 trials per cell.

### 3.2 The matrix

| mode | N | requests | recovered | recovery | provider calls | retry amplification | circuit opens | circuit-blocked | final failure rate |
|---|---:|---:|---:|---|---:|---:|---:|---:|---|
| `timeout` | 30 | 90 | 45 | **45/90 (50.0%)** | 225 | **2.50** | 6 | 0 | 45/90 |
| `timeout` | 100 | 300 | 150 | **150/300 (50.0%)** | 750 | **2.50** | 6 | 0 | 150/300 |
| `provider_error` | 30 | 90 | 9 | **9/90 (10.0%)** | 36 | **0.40** | 3 | 75 | 81/90 |
| `provider_error` | 100 | 300 | 9 | **9/300 (3.0%)** | 36 | **0.12** | 3 | 285 | 291/300 |
| `malformed` | 30 | 90 | 45 | **45/90 (50.0%)** | 180 | **2.00** | **0** | 0 | 45/90 |
| `malformed` | 100 | 300 | 150 | **150/300 (50.0%)** | 600 | **2.00** | **0** | 0 | 150/300 |
| `truncated` | 30 | 90 | 0 | **0/90 (0%)** | 90 | **1.00** | **0** | 0 | 90/90 |
| `truncated` | 100 | 300 | 0 | **0/300 (0%)** | 300 | **1.00** | **0** | 0 | 300/300 |

Four things in that table are worth naming.

**(a) The D-115 separation, verified at scale.** `malformed` and `truncated` produce **0
circuit opens** in every trial — a burst of 100 concurrent structured-output failures never
opens the breaker, nor do 50 consecutive ones in the half-open probe, while 5
provider-health failures always do. A response that arrives promptly and fails our schema
says Bedrock is healthy and our request is wrong; the gateway's refusal to conflate the two
is what stops one bad response model from taking every other task down with it.

**(b) Truncation costs exactly one call.** `truncated`'s amplification is **1.00** against
`malformed`'s **2.00**: the gateway spends a repair retry on a schema miss and deliberately
spends nothing on a truncation, because an identical retry under the same ceiling
truncates identically. That decision halves the cost of the failure mode it applies to, and
its price is the honest 0/300 recovery rate — the fallback, not a retry, is what serves
that caller.

**(c) The circuit is a cost control, not only an availability control.** Under a sustained
instantly-failing provider, 300 logical requests reached the provider **36 times**
(amplification 0.12). A bounded-retry policy without a breaker would have made up to 900
(3 attempts each). **96% of the calls a real outage would otherwise bill for were
suppressed** — and against even a no-retry policy's 300, 88%.

**(d) The one asymmetry, and why it is not a defect.** `timeout` blocks **0** callers while
`provider_error` blocks **285/300**, even though both open the circuit. `_circuit_check`
runs once, at the *start* of a call. When the provider fails instantly, the loop interleaves
call-start with failure-recording, so the breaker closes the door on callers that have not
yet started — the S34 result the shipped 30-concurrent test already records. When the
provider *hangs*, no failure is recorded until the first timeout fires, by which time the
whole burst is already in flight and past the check. So the breaker truncates a burst
arriving *into* an outage, and does not truncate a burst already in flight when the outage
begins. That is inherent to a check-on-entry breaker; the timeout is what bounds the
in-flight half, and it did (`timeout` never exceeded 2.5 calls per request).

### 3.3 Half-open recovery

| mode | configured cooldown | failures before open | observed open→first success | overshoot | blocked calls during cooldown |
|---|---:|---:|---:|---:|---:|
| `timeout` | 0.500 s | 5 | **0.5059 s** | +0.0059 s | 45 |
| `provider_error` | 0.500 s | 5 | **0.5043 s** | +0.0043 s | 45 |
| `malformed` | 0.500 s | 50 (never opened) | — | — | 0 |
| `truncated` | 0.500 s | 50 (never opened) | — | — | 0 |

The breaker reopens the path within **6 ms of its configured cooldown**, and the first
call through succeeds and clears the failure counter. The `malformed`/`truncated` rows are
not failures to recover — they are the D-115 property again: 50 consecutive schema failures
never opened the circuit, so there was nothing to recover from.

The opening burst in this probe uses `max_retries=0`, and that is a measurement decision
rather than a convenience: the interval starts at the closed→open transition, which happens
*inside* the call that trips the threshold, and under the shipped ladder that call then
sleeps 0.5 s and 1.0 s more before returning. Measured with retries on, the probe reports
the retry ladder's tail (1.56 s observed) rather than the cooldown. Single-attempt calls
remove the tail; the cooldown itself is untouched.

### 3.4 Restated, not fixed: 429 / 5xx / AccessDenied are indistinguishable

The retry policy catches `ProviderCallError` as one thing. A throttle (retry, with
backoff), a 5xx (retry) and an `AccessDenied` (never retryable — the credentials are wrong
and will still be wrong in 1.5 s) all take the same three attempts and the same backoff,
and all three count identically toward the breaker. This is a known finding restated for
completeness; **out of scope to fix here**, per the task's non-goals.

### 3.5 Limitations (E3.3)

- Single-process asyncio. `_circuit_check`/`_record_failure` contain no `await`, so they
  run to completion without yielding; the interleaving measured is cooperative rather than
  pre-emptive, and a multi-process burst would distribute breaker state per process (the
  breaker is in-memory per gateway instance, one per app process by design — D-007).
- The provider is scripted in-process. Latency is injected, not observed; no real Bedrock
  error taxonomy is exercised (that is E3.5, a separate Tier-2 experiment).
- The compressed cooldown (1.0 s / 0.5 s vs the shipped 30 s) changes how many callers a
  single burst can block. The *transition* behaviour it measures is unaffected.

---

## 4. E3.4 — the HITL bypass denominator

### 4.1 The number

> **84 bypass attempts, 0 unauthorized external side effects.**

Every one of the 84 is a permanent pytest case that tries to make an external action happen
— an escalation email, a branch-manager email, a calendar event, a location lookup, a
session bound to someone else's child — without a valid human approval for it. All 84 pass.

| suite | file | bypass | control | finding | architecture |
|---|---|---:|---:|---:|---:|
| chat-api | `apps/chat-api/tests/test_hitl_bypass_suite.py` | 38 | 2 | 1 | — |
| learning-api | `apps/learning-api/tests/test_hitl_bypass_suite.py` | 30 | 2 | 1 | — |
| shared / MCP | `packages/shared/tests/test_hitl_bypass_mcp.py` | 16 | — | — | 1 |
| **total** | | **84** | **4** | **2** | **1** |

Prior denominator: **1** explicit adversarial case (7 counting the replay/deny family).

`hitl_bypass_inventory.json` lists every case — id, surface, attack shape, expected
invariant, and the pytest node ids that drive it. It is **generated, not written**:
`hitl_bypass_inventory.py` reads each suite's `BYPASS_CASES` catalog out of the source with
`ast.literal_eval` (no import, nothing executed) and cross-checks it against
`pytest --collect-only`. A catalogued case with no collected test, or a collected
`[HB-…]` parametrization with no catalog entry, fails the run. So the 84 is a **collected**
count, not a claim: 91 catalogued cases → 94 collected tests (91 + 3 catalog self-checks),
all green.

Controls, findings and the architecture note are counted separately and are **never** folded
into the 84. The four controls exist because a suite that refused every request would pass
all 84 bypass cases while being useless: they assert that a plain valid approval still
sends exactly one email to the configured address and writes exactly one `approved` audit
row.

### 4.2 What the 84 cover

| surface | attempts | shapes covered |
|---|---:|---|
| chat-api `/respond` — malformed/hostile payloads | 17 | empty body, missing discriminator, missing decision, `"maybe"`, `null`, `[]`, `{}`, `2`, `"false"`, `0`, discriminator in a list, invented discriminator, wrong-but-valid discriminator (calendar / location on an email pause), oversized note, decline-with-a-body, nested approval |
| chat-api `/respond` — session, state, ownership | 9 | unknown session, no checkpoint, never-paused thread, anonymous caller on an owned thread, another authenticated user on an owned thread, cross-session thread substitution, approve-twice replay, approve-after-decline, **two genuinely concurrent approvals of one pause** |
| chat-api `/respond` — content injection through a *valid* approval | 5 | `recipient` override, `subject`/`body` override, `admin_escalation_email` override, CR/LF header-injection note, reply-channel (email + phone) in the note |
| chat-api — location consent | 4 | decline-with-coordinates (plus the `__resume__` purge), consent field omitted, wrong gate resolved, non-boolean consent |
| chat-api — `interrupt_approvals` audit invariant | 3 | a 422 writes no row, a 409 writes no row, a decline is recorded as `cancelled` |
| learning-api — attendance email gate | 11 | empty/`null`/false/`0`/`""`/`[]`/`{}` approvals, misspelled key, bare string, bare boolean, `null` resume |
| learning-api — attendance content steering | 3 | `recipient` override, `student_external_id` override, injected body |
| learning-api — child-selection authorization gate | 7 | unlinked child, `null`, `""`, id in a list, id in an object, SQL-shaped string, `*` wildcard |
| learning-api — replay & cross-caller | 3 | sequential replay, approve-after-decline, a second parent resuming the first parent's pause |
| learning-api — `/respond` route | 6 | unauthenticated, another student's token, empty body, wrong discriminator, HTTP replay, **two genuinely concurrent HTTP resumes** |
| MCP registry | 16 | unregistered tool, injected suffix, wrong case, whitespace padding, 5000-char tool name, empty/partial/wrong-typed args, CR/LF in recipient and in subject, args as a list, `null` args, undeclared `bcc`/`cc`, role outside the allowlist, no role at all, hanging handler |

Each case asserts **two** facts, not one: the expected status or exception, *and* what the
recording transport actually holds afterwards. For most cases that is "`sent` is
unchanged" — a route that 500s after sending would satisfy the first assertion and fail the
second. For the two groups where the approval is *valid* (chat-api content injection, and
the MCP `bcc`/`cc` case) the assertion is the sharper one: exactly **one** message, to the
server-configured address, carrying only the server-composed content — the bypass being
tested there is steering, not triggering.

### 4.3 The two concurrency cases — where the serialization actually lives

`HB-CHAT-26` and `HB-LEARN-30` fire two genuinely concurrent HTTP resumes at one pending
approval, from two threads. Both produce **exactly one email, one `interrupt_approvals`
row, and a `[200, 409]` status pair** — HB-LEARN-30 across 3 repeated rounds, because a
concurrency test that fires a single pair proves very little about a window it happened not
to hit (the D-110 §2 lesson applied to this probe).

The mechanism is the same in both apps but reached differently, and the Frozen Spec's
premise for this task was stale on the second half:

- chat-api's `/respond` calls `_claim_turn` in the handler (`pg_try_advisory_xact_lock` on
  `chat_turn:{id}`, D-346).
- learning-api's `/respond` reaches the **same** lock inside `_invoke_with_deadline`
  (`learning_turn:{id}`, **D-376**, which ported D-346 to all seven learning `ainvoke`
  sites). The task brief expected learning-api to have no turn claim and possibly a real
  defect here; D-376 closed that gap before this measurement, and the measurement confirms
  it rather than finding it.

Because the lock is a Postgres transaction-scoped advisory lock rather than an in-process
one, it holds across replicas — which is the property that matters, and the one an
`asyncio.Lock` would not have given.

### 4.4 Findings — recorded, not fixed

Per the task's constraints, no product code was changed. Three observations are worth the
coordinator's attention; the first two are catalogued as `finding` and the third as
`architecture`, and **none** of the three is inside the 84.

**F1 — `HB-CHAT-F1`: a pending interrupt has no expiry.** Neither `/respond` checks how old
a pause is. The route verifies that the session exists, that the caller owns it, and that
the discriminator matches the pending type — never its age — and no TTL column or sweep
exists for a live thread. A pause left open is therefore resumable indefinitely, so an
approval a person granted in one context can be exercised in another arbitrarily later.
Severity is bounded by the ownership check (only the thread's owner can resume it) and by
the fact that the pause carries no privilege beyond sending its own already-composed
message. The test pins the current behaviour and says in its docstring that it should be
deleted if an expiry is ever added.

**F2 — `HB-LEARN-F1`: the graph layer is not independently safe to invoke concurrently.**
Two simultaneous `graph.ainvoke(Command(resume=…))` calls on one paused thread both
complete the node: two branch-manager emails, two approval rows. This is *not* reachable
through the API — §4.3 shows the route serializes — and it is not a new discovery
(D-346/D-376 both say "a LangGraph thread is not safe to invoke concurrently"). It is
recorded because it locates the guarantee precisely: **the route is the gate.** Any future
caller that invokes the graph outside a route — a background job, a CLI, a scheduler —
inherits no protection and must take the same claim.

**A1 — `HB-MCP-A1`: `McpToolRegistry` has no concept of approval.** A caller holding the
registry can send an email with no approval anywhere. This is the design (SPEC §5.22–§5.24):
the registry is the *validated tool-call* boundary and `interrupt()` is the *human-in-the-
loop* boundary. Collapsing them would put an approval check on a component that cannot know
which pause it belongs to. What the registry does guarantee — and what the 16 MCP cases
assert — is that no handler with an external side effect runs unless the call named a
registered tool and every argument validated. The honest form of the claim is therefore:
*the approval property is a property of the four call sites*
(`chat_api.graph.nodes.admin_escalation`, `calendar_action`, `branch_locator_consent`,
`learning_api.services.attendance.send_attendance_email`), each covered by the app-level
suites above.

**One further observation, not a finding.** `Command(resume=None)` and `Command(resume={})`
never reach the node — LangGraph reads a dict resume as a per-interrupt resume map when
every key is an interrupt id (which `{}` vacuously satisfies) and refuses a `None` resume
outright. Both are unreachable through the API anyway, since `/respond` builds the resume
value from a validated Pydantic body. The cases are kept because the invariant they assert
still holds (nothing sent, no approval fabricated) and the reason they cannot reach the node
is worth pinning.

### 4.5 Limitations (E3.4)

- The Gmail/Calendar/Maps transports are the apps' own dev fakes. "No email was sent" means
  "the transport the graph would have called recorded nothing" — the right assertion for an
  approval gate, but it is not a test of a real Gmail client, which does not exist yet
  (D-002).
- The two concurrency cases run inside one process via `TestClient`. The advisory lock they
  exercise is a real Postgres lock and therefore cross-replica, but the *client* concurrency
  is not multi-replica.
- SPEC §5.17 (solution-image deletion) has no implementation today (`IMAGE-WORK-PARK`), so
  the fourth §5.1.4 external action — image analysis — has no surface to attack and is
  absent from the denominator. The 84 covers three of the four gated actions.
- Nothing here was run against deployed staging or production.

---

## 5. Reproducing

```bash
make up && make db-upgrade        # local Postgres, migrated
uv run python benchmarks/resume_evidence/03_gateway_agents/overshoot_benchmark.py
uv run python benchmarks/resume_evidence/03_gateway_agents/failure_matrix.py
uv run python benchmarks/resume_evidence/03_gateway_agents/hitl_bypass_inventory.py
uv run pytest apps/chat-api/tests/test_hitl_bypass_suite.py \
              apps/learning-api/tests/test_hitl_bypass_suite.py \
              packages/shared/tests/test_hitl_bypass_mcp.py -q
```

The overshoot benchmark takes roughly 8-10 minutes (252 trials, most of it the injected
3 s call); the failure matrix about 20 seconds; the inventory about 5 seconds. Both benchmarks
accept `--smoke` for a rig check and `--out-dir` to write elsewhere.

The three benchmark scripts are **not** collected by `make test`: `pyproject.toml` sets
`testpaths = ["apps", "packages"]`, so `benchmarks/` is outside the default run (it is still
linted and formatted by `make lint`, which walks the whole repository). The three E3.4 suites
*are* permanent tests and do run in `make test`, under the same `postgres_skip_reason()` /
MySQL-reachability guards the rest of the suite uses.

**Do not run these concurrently with `make test`** — the overshoot benchmark and the test
suite share the one local dev Postgres. The benchmark writes only rows whose
`subject_external_id` begins `e3-bench-` and deletes exactly that prefix before and after
every run, so it leaves nothing behind; the constraint is contention, not pollution.
