# Audit Findings — Phase 0A (S36–S39)

The findings register for the four audit sessions defined in
[INTEGRATION_PLAN.md §2.3](INTEGRATION_PLAN.md). One row per finding, with reproduction and
evidence, so §2.6's criteria 1 and 2 can be evidenced rather than asserted.

**Severity (§2.4).** P0 authorization bypass / PII leak / data corruption / child-safety
failure / uncontrolled spend — stops the line, fixed immediately with a regression test.
P1 a launch journey broken, fail-open behavior, cost or latency out of bounds — fixed and
re-verified before the gate. P2 degraded UX or quality with a workaround. P3 polish.

**Disposition rule.** Fixes land in Phase 0B (S40–S41), *not* mid-audit — except P0s. Every
finding needs a disposition here; "won't fix" needs a written reason.

**Areas audited with no finding are recorded too**, at the bottom of each session's section.
An audit whose output is only its defects can't be told apart from an audit that stopped
early, and traceability (criterion 1) needs the negative results as much as the positive
ones.

---

## Index

| ID | Area | Severity | Status | Summary |
|---|---|---|---|---|
| **AUD-L-02** | **Money** | **P0** | **Fixed in S36** | `POST /students/{id}/report` had no cost ceiling of any kind — it passed `session_spend_cents=0.0`, so the gateway's budget check could never fire, and one authenticated caller could drive unbounded Bedrock spend |
| **AUD-L-04** | **Minors / PII** | **P1** | **Decided** — fix before the gate | D-072 accepted "names in free text may survive" *because* that text lived in a 90-day-purged table; S25 then derived permanent, never-purged `semantic_memory.fact_text` from it, and those facts reach parent-visible reports |
| AUD-L-05 | Minors / PII | P2 | Open — Phase 0B | `MemoryConsolidationPayload` carries free text but was never added to the PII-floor allowlist test, contrary to D-072's own stated rule |
| AUD-L-06 | Minors | P3 | **Decided** — delete in Phase 0B | `tutor.generate_hint` is dead code that omits the leak check its live sibling applies — a trap for whoever wires it up |
| AUD-L-03 | Money | P2 | **Decided** — Phase 0B | `pre_intro` stage-narrative spend is never folded back into the session total, so the per-session ceiling is permanently one call short |
| **AUD-L-07** | **Authorization** | **P1** | Open — before the gate | D-086's known tutor/branch_manager scope gap now reaches further than when it was written: it covers the S28 dashboard and report surface, so a tutor token can read any student's data and generate reports about them |
| AUD-L-09 | Correctness | P2 | **Decided** — Phase 0B | Numeric grounding verifies a number's *provenance*, not its *attribution*, so a report can invert a real result ("fell from 6 to 4") and still pass |
| **AUD-L-10** | **Data integrity / scoring** | **P1** | Open — before the gate | The server marks an exam item `answered` and then accepts more answers for it; exam scores are computed over the *attempt* count, so one changed answer rescores a 10-item exam as 10/11 and silently removes the `not_applicable_pre_max` flag. Enforced client-side only |
| AUD-L-11 | Robustness / contracts | P2 | Open — Phase 0B | `UnknownQuestionVariantError` is raised at four sites and caught nowhere, so an answer POST with an unknown or not-currently-served variant returns an unhandled **500** instead of a 4xx |
| AUD-L-12 | SPEC conformance | P2 | Open — Phase 0B | `recommended_difficulty` is computed, stored and displayed but routes nothing; two docstrings claim it seeds `starting_difficulty` and it does not. Masked only by the 1:1 skill↔difficulty bank |
| AUD-L-13 | Minors / correctness | P2 | Open — Phase 0B | Memory consolidation verifies a fact's evidence provenance and cross-session repetition, never the claim against the measured mastery score in the same database — a `strength` fact coexists with `weighted_score = 0.0` for that skill |
| AUD-L-14 | Correctness / parent-visible | P2 | Open — Phase 0B | `time_spent_minutes` sums a client-populated telemetry column and ignores the always-populated `assessment_attempts.response_time_ms`, so a report shows `0.0` minutes beside `attempts_count: 26` — inside `verified_facts` |
| AUD-L-15 | Correctness / parent-visible | P2 | Open — Phase 0B | Mastery excludes the post-exam by construction while "skills to strengthen" is post-exam-derived, and both are shown together labeled `date_range_label: "all time"` — one skill reads mastery 1.000 *and* "needs work" |
| AUD-L-08 | Correctness | P3 | Open — Phase 0B | `normalized_gain` has no bound in either direction and derives its denominator from the pre *attempt count*. **Reachability corrected in the S36 continuation:** −200% reached on an ordinary journey, and >1 reachable via AUD-L-10's duplicate attempts |
| AUD-L-16 | Design integrity | P3 | Open — Phase 0B | Both policy snapshots (`assessment_sessions.policy`, `study_sessions.intervention_policy`) are written at creation and never read back; only `time_limit_seconds` governs behavior, via a separate column |
| AUD-L-17 | Test integrity | P3 | **Fixed in S36 continuation** | The default mock's own hint boilerplate (`Level 1`) tripped the runtime answer-leak check whenever the served answer was `"1"`, making a hint test fail 8 times in 60 runs; `hint_events.was_personalized` still records no reason code, so the real rate is unmeasurable |
| AUD-L-01 | Auth surface | P3 | Open — Phase 0B | A gated-off `/dev/token` still discloses that it exists, and the S35 deploy gate's stated rationale is wrong about why it 404s |
| **AUD-C-01** | **Authorization** | **P1** | Open — before the gate | `POST /messages` has no thread-ownership check *and* an anonymous turn erases the owner that `/respond` and `/stream` do check. Live-verified on staging: an unauthenticated caller continued a tutor's thread, received the tutor's answer and citation, and resolved its interrupt. Locally, tutor-audience text reached the anonymous response verbatim |
| **AUD-C-02** | **Launch journey** | **P1** | Open — before the gate | The `SCOPE_AND_INTENT` prompt's topic list omits SPEC §5.19.4's first supported topic ("IntelliChoice organization"), so live staging refuses **"What is IntelliChoice?"** as out of scope, 5/5. The mock's keyword list contains `"intellichoice"`, so no test could see it |
| **AUD-C-03** | **Minors / PII** | **P1** | Open — before the gate | A caller's precise coordinates persist indefinitely in `checkpoint_writes.__resume__`, contradicting the consent notice's verbatim promise not to store them. D-045 called this "briefly"; nothing purges it, and D-045's "not eliminable" is wrong — a targeted delete works |
| AUD-C-04 | Correctness / UX | P2 | Open — Phase 0B | A turn that pauses on `interrupt()` returns the *previous* turn's answer, citations and access hint (pausing nodes never return, so nothing resets them); `ics_content` is never cleared by anything and sticks to every later turn. The leak vehicle in AUD-C-01 |
| AUD-C-05 | Test integrity | P2 | **Partly addressed in S37** | The golden Q&A eval measures `MockBedrockProvider`, not retrieval: a real model rejects 10 of its 14 gating cases before retrieval runs, and `no_answer` scores 0/8 under the mock vs 8/8 real. Fixture extended and re-scored this session; the mock's quality categories are now measured, not gated |
| AUD-C-06 | SPEC conformance | P2 | Open — Phase 0B | SPEC §18-C3's access-aware refusal fired **0 times in 8** under a real model: its precondition is zero-row retrieval, which real hybrid search essentially never produces. A parent gets "no approved source" instead of "log in to see the parent handbook" |
| AUD-C-07 | Robustness | P2 | Open — Phase 0B | An embedding-provider failure or an exhausted budget on the retrieval path is an unhandled **500** — `retrieve()`'s `create_embedding` is the one uncaught gateway call, and chat-api has no exception handler. Violates §5.29's Bedrock-timeout row |
| AUD-C-08 | UX / diagnosability | P2 | Open — Phase 0B | A total Bedrock outage, or an exhausted cost ceiling, answers every in-scope question with the *out-of-scope* refusal — fail-closed but user-misleading, and indistinguishable from a genuine refusal in logs |
| AUD-C-09 | SPEC conformance | P2 | Open — Phase 0B | §5.21.3's sixth predicate (`academic_year = requested_year`) is never applied at query time; a 2019-2020 chunk was retrievable by every audience. Fully masked while the corpus holds one academic year |
| AUD-C-10 | Frontend contract | P2 | Open — Phase 0B | Any API error leaves chat-web's turn stuck on `Thinking…` permanently — the transcript entry keeps `response: null` and nothing clears it. A §2.6 criterion-3 blank/stuck state, reachable from AUD-C-07 |
| AUD-C-11 | Correctness / UX | P2 | Open — Phase 0B | The low-confidence branch returns the "I don't have an approved source" message *with* verified citations attached, so the UI shows a source beside a sentence denying one exists. Observed live |
| AUD-C-12 | SPEC conformance | P3 | Open — Phase 0B | §5.21.8's "retrieval score is below threshold" do-not-answer trigger has no implementation: the only filter is `rerank > 0.0`, and the 0.4 threshold gates the model's self-reported confidence, not retrieval |
| AUD-C-13 | Grounding | P3 | Open — Phase 0B | The citation verbatim check accepts any non-empty substring, so a one-character quote verifies against nearly any chunk; only the quote's hash is stored, so it cannot be re-examined |
| AUD-C-14 | Contracts | P3 | Open — Phase 0B | `RespondResponse` omits `scope`/`intent`, so every SSE snapshot published after a `/respond` nulls them for connected clients — D-058's class, in the direction that decision did not name |
| AUD-C-15 | Audit trail | P3 | Open — Phase 0B | `McpToolRegistry.call` raises on an unknown tool *before* any audit write, so the one call shape a wiring bug or injection would produce is the one that leaves no `mcp_tool_calls` row |
| **AUD-C-16** | **Launch journey / data integrity** | **P3 → P1** | Open — before the gate | Stored embeddings are provider-specific with no provenance column and no re-embed path. **Settled by S38: staging's corpus is 159/159 `MockBedrockProvider` hash vectors** while both deployed services query with real Titan v2, so staging's semantic channel returns noise (peak cosine +0.074 vs +0.41 with real vectors) and hybrid search there has always been lexical-only. Live paraphrase citation rate **1/7** |
| **AUD-X-01** | **Authorization** | **P1** | Open — before the gate | `POST /sessions/{id}/student` never checks who already owns the session: a different student claimed an in-progress exam session, the owner was **locked out with 403**, and their `in_progress` assessment row was orphaned. Same structure as AUD-C-01 — the one route that *writes* the identity field all 17 others read is the one that does not check it |
| **AUD-X-02** | **Minors / child safety** | **P1** | Open — before the gate | SPEC §5.1.2's *"should verify `parental_consent_verified=true`"* has no implementation: that claim plus `account_status` and `consent_status` are carried in every token and read by **nothing**. A `suspended`/`revoked`/unverified/`under_13` token behaved identically to a consented one on all 18 learning routes |
| AUD-X-03 | Data integrity | P2 | Open — Phase 0B | `POST /sessions/{id}/topics` replayed builds a **second exam** (+1 session, +10 items, different variants) and orphans the first. Guarded only by a per-hook-instance `busyRef` in one client, with `busy={false}` hardcoded at the call site — AUD-L-10's pattern again |
| AUD-X-04 | Money / correctness | P3 | Open — Phase 0B | `POST /students/{id}/report` has no idempotency key: two clicks, two paid Bedrock calls, two rows. P3 only because AUD-L-02's daily ceiling now bounds the spend |
| **AUD-X-05** | **Authorization** | **P1** | Open — before the gate | AUD-L-07's tutor/branch_manager fall-through extends to **writes**: a tutor token answered and **finalized another student's exam** (200), and can bind any session to any student id. Fabricated attempts are indistinguishable from the student's own and feed scoring, mastery and learning-gain |
| **AUD-X-07** | **Data integrity / launch journey** | **P1** | Open — before the gate | The checkpoint commits inside `ainvoke` while domain rows commit at FastAPI dependency teardown, so any failure between them keeps the graph's state and discards the database's. Reproduced at both seams: mid-finalize leaves a scored exam `in_progress` with a dangling `study_session_id` (a reloading client is served a study question, then **500s forever**), and mid-interrupt leaves a pending `intervention_choice` for an attempt row that does not exist (`/respond` **500s** and the interrupt never clears). A task stop during any deploy enters this window with no bug required |
| **AUD-X-08** | **Money** | **P1** | Open — before the gate | Every per-day cost ceiling is read-then-act with the cost row committed at teardown. **10 concurrent reports produced 8 generated reports and 8.0× the ceiling**, while the sequential control correctly degraded — a correct check with no serialization. Weakens AUD-L-02's P0 fix; a single caller can drive it since AUD-X-04 leaves the route non-idempotent |
| AUD-X-06 | Test integrity | P3 | **Fixed in S38** | A hint test asserted a plain substring where the product's `answer_text_leaked` is boundary-aware, so it demanded more than the product guarantees and the mock's own `hint lN` prefix collided whenever the drawn answer was `"1"`–`"3"` (**17.9%** of the bank; measured **15/70**). Fixed by asserting the product's own rule: **0/40**, and three consecutive green suites. **AUD-L-17 did not regress** — it pinned a *different* test, still 0/20; its mock change *unmasked* this one |

| **AUD-F-01** | **Cost / latency** | **P1** | Open — before the gate | `App.tsx` passes `onFetchOverview` and `onRecordTime` as **inline arrows**, so they are new identities on every render, and both sit in `ExamScreen` effect dependency arrays — every render tears the effect down and re-runs it. Measured: **885 `POST /exam/items/{id}/time` in a 15-second dwell on one question (~59/s)**, each carrying the ~20 ms gap between two renders; and **76 `GET /exam/overview` for a single 10-item exam, median 30 ms apart against the declared `OVERVIEW_POLL_MS = 20000`** — a ~667× amplification. Both are database writes/reads on the main journey's hot path |
| **AUD-F-02** | **Frontend contract** | **P2** | Open — Phase 0B | After `POST /exam/finalize` returns 200 the client keeps calling the exam endpoints: **35 × 409 in a 96 ms burst** (33 `exam/overview` + 2 `exam/items/{id}/time`), zero after 5 s, with no exam screen even mounted. Each failed fetch is a browser console error, so **§2.6 criterion 3's "zero console errors" cannot be met while this exists**. Same root cause as AUD-F-01 |
| **AUD-F-03** | **Launch journey** | **P2** | Open — Phase 0B | A refresh mid-exam does **not** restore position: measured going from **"Question 3 of 10" to "Question 1 of 10"**. SPEC Phase 11's own "done when" is that a refresh restores the exact position, and `useLearningSession`'s docstring cites that requirement verbatim — but the display position is `ExamScreen` component state and is never persisted, while the hook only restores the *session*. Recoverable via the nav bar, which is what keeps it off P1 |
| AUD-F-04 | Frontend contract | P3 | Open — Phase 0B | A dismissed stage narrative **returns after a refresh**: dismissal is React state (`dismissedNarrative`, keyed by the narrative text) while `stage_narrative` persists in the snapshot, so the gate that sits ahead of every phase branch closes again. One extra click clears it (verified), which is the whole of the severity argument |
| AUD-F-05 | Frontend contract | P3 | Open — Phase 0B | The stage narrative **displaces the screen the student is already using**, because `App.tsx` gates it ahead of every phase branch and it arrives over SSE after that screen renders. The topic list is interactive for a measured **~26 ms** before being replaced; the same swap detaches the Submit-answer and retry-ladder buttons mid-click. Too narrow for a human to lose a click to (the one click that landed still reached the API), but it makes every scripted journey need retry logic — which is how it was found |
| **AUD-F-06** | **Operations** | **P2** | Open — before the gate | **No scheduled jobs exist at all**: zero EventBridge rules and zero EventBridge Scheduler schedules in the account. The four jobs are `make` targets a human runs — and only **three** of them are schedulable at all: `webcontent-sync` rewrites tracked `knowledge-content/` files and asks for a human diff review, so §2.5's work item should be re-scoped to three. §2.6 criterion 6 ("all scheduled jobs ran on schedule for ≥ 1 week with zero manual intervention") is therefore not merely unmet but **unstartable** — the one-week clock cannot begin until the schedules land, so **the earliest possible gate pass is one week after that Phase 0B item ships**. A scheduling fact about the whole milestone, not just a defect |
| **AUD-F-07** | **Money** | **P2** | Open — Phase 0B | `make memory-consolidate` processes **160 students and reports 145.97 cents in one unattended run**, and **150 of the 159 students with memory rows are `loadtest-student-N` fixtures left behind by S34's load test** — 94% of the job's paid work is synthetic. Locally the provider is the mock, so the figure is the accounting layer's projection rather than a real charge; against staging's real Bedrock it would be real money, recurring on every scheduled run. Must be resolved *before* AUD-F-06's schedules are created, not after |
| AUD-F-08 | CI coverage | P3 | Open — Phase 0B | CI builds and tests `learning-web` but has **no job for `chat-web`** (already on the Phase 0B list) and none for the new `e2e/` harness. Two of the four deployables are therefore unbuilt by CI, against §2.6 criterion 4's "CI builds and tests every deployable" |
| AUD-F-09 | Deploy pipeline | P2 | **Fixed in S39** | `deploy-staging.yml` rewrote the image tag on **every** container in the task definition. Harmless with one container — but the moment the OTel sidecar was added it would have rewritten `aws-otel-collector:v0.43.3` to `aws-otel-collector:gha-<sha>`, an image that does not exist, and every deploy would have crash-looped into a circuit-breaker rollback. Caught while adding the sidecar, before it shipped; the patch is now scoped to the app container by name, with an assertion that exactly one matches |

| **AUD-F-15** | **Retention / deployment config** | **P1** | **Fixed in S40** | **`chat-purge` could not reach the database in the deployed environment at all, so the 90-day retention promise had never once executed against real data.** It called `create_engine(get_settings().database_url)`, and `learning_api.config` uses `env_prefix="LEARNING_"` — so inside the ops task, which supplies D-092's *unprefixed* components, `settings.database_url` silently stayed at its hardcoded `localhost` default. The first scheduled run died with `ConnectionRefusedError: Connect call failed ('127.0.0.1', 5432)`. Invisible locally by construction: on a developer's machine localhost **is** the database, so every `make chat-purge` and every unit test passed. **Third instance of this exact shape** (`create_engine`'s own docstring records the S32/D-084 `curriculum-load` one), so the fix ships with a guard test over every standalone CLI plus a negative arm asserting the two FastAPI apps still pass their URL explicitly |

| **AUD-F-14** | **Capacity / latency** | **P1** | Open — before the gate | **Five concurrent chat turns take ~30 s each, and the autoscaling policy cannot see it.** Measured live: 1.62 s unloaded → p50 **26.92 s** / p95 **32.14 s** at concurrency 5, all 200s (it queues, it does not fail). ALB p95 per minute 3.56 → 31.97 → 30.96 → 30.98 s against a 3.0 s threshold. The defect is not the capacity fact but that **nothing can react**: Application Auto Scaling is a single `ECSServiceAverageCPUUtilization` target-tracking policy at 70%, and this workload waits on Bedrock rather than computing — CPU **peaked at 15.19%** during the 31 s window, so `desiredCount` never left 1. **Criterion 7's "≥2 tasks under load" is unreachable as configured.** Sharpens D-095: S34 diagnosed the single-worker bottleneck correctly and added autoscaling that the bottleneck cannot trigger — invisible from a docker-compose run against the mock |

| **AUD-F-13** | **Credential in observability store** | **P1** | **Fixed in S39 continuation** | **A bearer JWT is recorded in `http.url` on every SSE connection.** `EventSource` cannot set an `Authorization` header, so the stream authenticates as `?token=<JWT>`, and `FastAPIInstrumentor` records the full URL — a 455-character live token into X-Ray. The app's own access logger was unaffected (templated path, query string dropped), which is exactly why S38's log scan was clean: **the same request is sanitized in one store and not the other**, so a PII floor has to be re-established per store rather than inherited. Bounded impact (1-hour TTL, AWS access required, the captured token was already expired) so held at P1 — but it captures live credentials the moment authenticated traffic runs with tracing on. Fixed at the export boundary rather than in a request hook, with a regression test driving the real instrumentation and confirmed to fail without the fix |

| **AUD-F-11** | **Deploy pipeline / security** | **P2** | **Fixed in S39 continuation** | `terraform.tfvars` pinned `learning/chat_api_image_tag = "gha-6cc4a27430bd"` while both services were running `gha-d1899a483d06` — pushed six hours later, and **the commit that fixed `/dev/token` being signed with the public dev constant instead of the real secret**. So `terraform apply` registered task-definition revisions that silently reverted a security fix, and any operator who applied and then pointed a service at the new revision (rather than letting CI patch the tag) would have deployed it. Terraform cannot detect this: the tag exists and pulls fine. Only diffing the registered revision against what is *running* shows it. Found by doing exactly that before deploying the sidecar |

| **AUD-F-12** | **Observability / infrastructure** | **P2** | **Fixed in S39 continuation** | **The OTel collector accepted every span and discarded every one**, because the VPC has no `xray` interface endpoint and no NAT — AUD-F-10's root cause one layer further in. `Exporting failed. Rejecting data. {"name": "awsxray", "error": "Post \"https://xray.us-east-1.amazonaws.com/TraceSegments\": context deadline exceeded", "rejected_items": 64}`, repeating. **Nothing detected it**: the collector is `essential: false` and starts perfectly healthy, the app's export succeeds into it, both services stayed green, and no alarm watches export failures. Fixed with a single-AZ `xray` endpoint wired to `enable_otel_tracing` (~$7.30/mo, matching the existing five endpoints' cost posture); traces went from **0 to 650** on the next traffic run |

| **AUD-F-10** | **Infrastructure** | **P2** | **Fixed in S39 continuation** | **The ECS tasks cannot pull from `public.ecr.aws`.** They run in private subnets with `ecr.dkr`/`ecr.api` interface endpoints and an S3 gateway but **zero NAT gateways** (D-084's cost posture), and no interface endpoint exists for *public* ECR. Found live on the first sidecar deploy: `CannotPullContainerError ... dial tcp 75.2.101.78:443: i/o timeout`, retried 7×, services rolled back to the pre-sidecar revision and verified healthy. Fixed by mirroring the collector into this account's private ECR (`scripts/mirror-otel-collector.sh`, repository created, Terraform rewired) — **the mirror push itself did not complete before the AWS session expired**, so the image is not yet in ECR. **Live hazard while that is true:** the latest task-definition revision (18) still references the unreachable public image, and `deploy-staging.yml` patches whatever the *latest* revision is — so **the next CI deploy would fail the same way** until the mirror is pushed or `enable_otel_tracing` is set false and re-applied |

---

## S36 — AUD-L (learning product correctness)

### AUD-L-02 — `POST /students/{id}/report` had no cost ceiling at all (P0, fixed)

- **Severity:** P0 — §2.4 lists uncontrolled spend explicitly. Stopped the line and was
  fixed in-session with regression tests, per the audit's own rules.
- **Area:** money / Bedrock cost ceilings
- **Found by:** tracing every `session_spend_cents` argument to
  `BedrockGateway.generate_structured` back to its caller, rather than reading the gateway
  and concluding the ceiling exists
- **Status:** **fixed in S36**, live re-verification pending the Phase 1 deploy

**What.** The gateway is stateless about spend: it enforces the per-session budget against a
`session_spend_cents` value its *caller* supplies. Two callers supplied nothing, relying on a
`= 0.0` default — and one of them,
[routers/students.py](../apps/learning-api/src/learning_api/routers/students.py)'s
`POST /{student_id}/report`, is an on-demand endpoint with **no idempotency key**: one fresh
`student_reports` row and one fresh Bedrock call per click. So on every single call the check
evaluated `0.0 + worst_case > 50.0`, which is false, and the ceiling never applied. Not a
weakened ceiling — an absent one.

The only remaining limit was the global per-IP rate limiter, raised to 6,000 requests/60s in
S34 for a completely unrelated reason (real branches share an egress IP). A request cap is not
a spend cap.

**Reproduction.** Authenticate as any role permitted to reach a student's report (student-self,
linked parent, tutor, branch_manager) and repeat `POST /learning/students/{id}/report`. Every
request performs a real Bedrock `PARENT_REPORT` call. No counter, ledger, or ceiling is
consulted, and the response is not cached or deduplicated.

**Evidence.** Cost arithmetic from the gateway's own rate table, for the model actually
deployed (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, 0.1/0.5 cents per 1K in/out) and the
report task's real `_MAX_OUTPUT_TOKENS = 500`: roughly **0.45 cents per call** (0.2 in + 0.25
out), doubling if the structured-output repair retry fires. At the per-IP limiter's ceiling
that is ~$27/minute, ~$1,600/hour, from one IP holding one valid token. Even at a rate a plain
browser script achieves without effort, it is hundreds of dollars a month of pure waste. The
only backstop was the AWS Budget alarm — a lagging notification, not an enforcement mechanism.

The bug class is already recognized in this codebase: S24 built
`tutor_chat.DAILY_COST_CEILING_CENTS` precisely because chat is a surface where one student can
trigger many separate LLM calls in a day. Report generation is the same shape and never got the
same control.

**Fix (in this session).** Mirrors the chat precedent rather than inventing a mechanism:

1. `StudentReportRepository.get_spend_cents_since` — sums `cost_cents` over a 24h window. No
   migration: `student_reports` already stores `cost_cents` and `created_at`.
2. `report.DAILY_REPORT_COST_CEILING_CENTS = 50.0`, checked *before* the Bedrock call. On
   exceed the endpoint degrades to the deterministic facts-only template that a gateway failure
   or a failed grounding check already produces — the caller still gets their real verified
   numbers, just without LLM prose. That reuses SPEC §5.25.3/§5.27's deterministic-fallback
   rule instead of erroring.
3. `session_spend_cents` is now **required** on both `generate_student_report` and
   `generate_stage_narrative`. A cost parameter with a permissive default *is* a fail-open
   default — the same class as D-096's `ecr:DescribeImages` check and D-085's environment-string
   gate. Removing the default immediately surfaced all five call sites that had been relying on
   it, which is the point.

**Regression tests** (3): the ceiling short-circuits *before* the gateway is called (an
`_ExplodingGateway` fails the test if Bedrock is reached at all); a call just below the
threshold still generates normally (a ceiling that blocks legitimate use is a different bug, so
the threshold is pinned from both sides); and the spend query counts only this student's reports
inside the window, so neither another student's spend nor last week's can deny a legitimate
report.

**Residual, deliberately not fixed here.** The endpoint is still not idempotent — the ceiling
bounds the *cost* of hammering it, not the hammering. Per-caller request-rate limiting on
LLM-calling endpoints specifically (as opposed to the global per-IP cap) is a Phase 0B item and
belongs with the same work for chat.

### AUD-L-04 — An accepted PII risk lost its mitigation when S25 made the text permanent (P1)

- **Severity:** P1 — a data-protection promise about minors that the code no longer keeps.
  Not P0: it needs a student to type a name, the model to copy it into a fact, and that fact to
  pass the pattern screen, and there are no real student users yet. But it must be closed before
  the §2.6 gate, not in the backlog.
- **Area:** minors / PII floor / retention
- **Found by:** following `relevant_learning_fact` — an *allowlisted* field on the tutoring
  payloads — backwards to where its text is authored, instead of stopping at the allowlist
- **Status:** open, before the gate

**What.** D-072 (S24) explicitly accepted that name detection in free text is unreliable and is
not attempted: `redact_free_text` removes emails, URLs and phone numbers only. So a student
typing "my mom Sarah said to skip this" leaves a name in `tutor_chat_messages.
redacted_student_message`. That was accepted as a bounded risk, and the boundary was real:
**that table is the only one in this codebase with a retention job** (`purge_older_than`,
`make chat-purge`, 90 days, SPEC §15).

S25 (D-074) then built memory consolidation on top of that same text, and the boundary quietly
disappeared:

1. `consolidation.py:185` reads `redacted_student_message` and folds it into
   `MemoryEventSummary.summary`.
2. That goes to Bedrock, which authors `MemoryFactCandidate.fact_text`.
3. `fact_text` is screened with `contains_pii_pattern` — the *same* email/URL/phone patterns,
   which by D-072's own admission do not catch names — and stored in `semantic_memory`.
4. `semantic_memory` has **no purge, no retention job, and no `make` target.** Verified: grepping
   `purge_older_than` across every repository in `packages/db` returns exactly one hit,
   `tutor_chat.py`.
5. `fact_text` then flows outward — into `relevant_learning_fact` on `BedrockTutorPayload` and
   `HintPersonalizationPayload`, and into `ReportInterpretationPayload.relevant_learning_facts`,
   which is rendered in **parent-visible reports**.

So a name a child typed can outlive the 90-day window indefinitely, in Postgres, and surface to a
different human than the one who typed it. Neither D-072 nor D-074 records this: D-072 reasoned
about a purged table, and D-074 reasoned about consolidation quality.

**Reproduction (structural, and that is the honest description).** The chain above is verifiable
by reading it, and every link is unconditional code. What cannot be reproduced deterministically
is step 2 — whether the model copies a name into a fact — because that depends on real model
behavior, and the dev fake does not attempt it. I did not manufacture a "leak" with a scripted
fake gateway, because that would only prove the fake does what I told it to; it would be evidence
about my test, not about the system.

**Evidence.** `consolidation.py:185` and `:250`/`:324` (the screen, using the same insufficient
pattern set); the single-hit `purge_older_than` grep; `report.py`'s `relevant_learning_facts`
reaching the parent audience in `build_report_facts`.

**Disposition — DECIDED (user, S36 close-out; see D-098).** Add a retention job for
`semantic_memory`, and a line in the §6.1 privacy text. Rejected: stopping raw chat text reaching
consolidation (removes the risk at source but spends the consolidation quality D-074 deliberately
bought, and would partly supersede a settled decision); and accept-and-disclose (zero cost but
makes "we delete chat after 90 days" misleading for a product whose primary users are minors).

The chosen option restores exactly the boundary D-072 already reasoned about and approved, rather
than re-opening a settled trade-off. Phase 0B work, before the §2.6 gate:

1. `SemanticMemoryRepository.purge_older_than` + a `make memory-purge` CLI, mirroring
   `TutorChatMessageRepository.purge_older_than` / `make chat-purge` exactly.
2. Fold in the `stage_transitions` and `student_reports` retention jobs already on the standing
   carry-over list — same pattern, same session, so this is done once rather than three times.
3. The retention window must be **stated in the §6.1 privacy notice**, and the notice must not
   imply that deleting chat after 90 days removes everything derived from it.
4. All of these must run on a schedule, not by hand — the EventBridge item already seeded in
   §2.5 covers it. A retention promise that depends on someone running `make` is not a retention
   promise, which is the same reasoning §2.5 already applied to `chat-purge`.

### AUD-L-05 — `MemoryConsolidationPayload` was never added to the PII-floor allowlist (P2)

- **Severity:** P2 — no live leak today; a missing guard rail, not a broken one
- **Area:** minors / PII floor
- **Status:** open, Phase 0B

**What.** D-072's own "How to apply" clause states the rule: *"any future free-text-accepting
Bedrock task must run `redact_free_text` (or a stricter successor) before the wire and before
storage, **and its payload must appear in `test_bedrock_payload_pii_floor.py`'s allowlist set**."*
`MemoryConsolidationPayload` is a free-text-accepting payload (`MemoryEventSummary.summary`,
`MemoryExistingFact.fact_text`) added one session later, and it is not in that test.

**Reproduction / evidence.** The test covers exactly six payload types — `BedrockTutorPayload`,
`HintPersonalizationPayload`, `LearningChatIntentPayload`, `TutorChatPayload`,
`StageNarrativePayload`, `ReportInterpretationPayload` — confirmed by extracting every
`*Payload` symbol referenced in the file. `MemoryConsolidationPayload` is absent.

**Why it matters despite P2.** The payload's *current* fields are clean, so nothing leaks now.
The value of that test is that it fails when someone adds a field — it is the mechanism by which
the PII floor survives future sessions. An uncovered payload silently opts out of that
protection, and this one is the payload closest to real student free text.

**Disposition.** Phase 0B: add the allowlist case. Also worth checking the other uncovered
payloads in the same pass (`VideoClassificationPayload`, `LlmJudgePayload`, and the
curriculum-pipeline payloads); the chat-app payloads belong to AUD-C/S37.

### AUD-L-06 — `tutor.generate_hint` is unreachable and omits the leak check its sibling applies (P3)

- **Severity:** P3
- **Area:** minors / tutoring guardrails
- **Status:** open, Phase 0B

**What.** `tutor.generate_hint` performs a real Bedrock `TUTOR` call and returns
`result.value` directly — no `leak_phrase_present`, no `answer_text_leaked`, and it ignores
`HintResponse.answer_revealed` even though the field exists. Its live sibling
`generate_personalized_hint` applies all three checks plus a ladder-monotonicity check, and
`tutor_chat.generate_chat_reply` applies the leak checks too. `generate_solution` correctly has
none (revealing the answer is its job) but does cross-check the model's `final_answer` against
the real one.

**Reproduction / evidence.** `generate_hint` has **no caller in application code**: grepping the
whole repository finds it referenced only from `apps/learning-api/tests/test_tutor_service.py`
and one comment in `packages/evals`. The live hint path is `graph/nodes.py:788` →
`generate_personalized_hint`. So this is dead code, and there is no reachable defect today.

**Why log it at all.** It reads exactly like a supported entry point, it is covered by three
tests that assert it works, and it is the only LLM-output path in the learning app that trusts
the model unverified. A future session adding a "plain hint, no personalization" flow would
reasonably call it and inherit an unguarded path.

**Disposition — DECIDED (user, S36 close-out; see D-098): delete it**, along with its three tests.
There is no caller to migrate, and the live path (`generate_personalized_hint`) already has every
check. If a non-personalized hint flow is ever wanted, writing it fresh with the checks in place is
easier and safer than remembering that this one lacked them. Rejected: keeping it and adding the
checks, which would preserve unreachable code and the false impression that it is exercised.

### AUD-L-03 — `pre_intro` spend is never folded back into the session total (P2)

- **Severity:** P2 — bounded, but it means the per-session ceiling is structurally wrong
- **Area:** money / cost accounting
- **Status:** open, Phase 0B

**What.** `routers/stream.py`'s `pre_intro` narrative fires on SSE connect, outside the graph.
S26/D-075 deliberately records its cost on the `stage_transitions` row rather than in the
checkpoint's `bedrock_spend_cents`, because that path never takes a graph turn. That choice was
recorded as an *accounting* decision; its consequence for *enforcement* was not: every later
call in that session evaluates the ceiling against a total that is permanently missing this
call's cost. The same is true of chat's out-of-band spend (S24/D-073 records that one).

**Reproduction / evidence.** Structural, and visible in the code: `_maybe_fire_pre_intro`
returns only `(narrative_text, evidence_summary)` — there is no cost in its return type, so no
caller could fold it in. Bounded by the stage-narrative idempotency check (one real Bedrock call
per session per stage), so the undercount is one call's worth per session, not unbounded.

**Fixed in this session only in part:** the call now passes the checkpoint's real running total
instead of the 0.0 default (as part of AUD-L-02's fix), so the ceiling at least applies. The
write-back is the remaining half.

**Disposition — DECIDED (user, S36 close-out; see D-098): fold out-of-band spend into the
checkpoint**, settling the question D-073 and D-075 each deliberately left open. Both `pre_intro`
(SSE connect) and chat's own spend get a path to write their cost back into `bedrock_spend_cents`,
so the per-session ceiling means what its name says and there is one authoritative number instead
of two partial ones.

The cost is understood and accepted: this means writing to the checkpoint from outside a graph
turn, which is exactly what those two decisions avoided. The reason to accept it now is AUD-L-02 —
this session has already produced one P0 from a ceiling that silently did not apply, so a ceiling
that is merely *approximately* right is no longer a comfortable place to leave things. Phase 0B;
the per-day ceilings remain the real bound on those surfaces in the meantime.

### AUD-L-07 — D-086's authorization gap has grown since it was recorded (P1)

- **Severity:** P1. Already known and already launch-blocking (D-086, S33); this finding is the
  *scope update*, not the discovery.
- **Area:** authorization
- **Status:** open, before the gate — same disposition D-086 already has

**What.** `authorization.resolve_target_student` verifies students against their own `sub` and
parents against a live linked-children lookup, then returns `requested_student_id` unchecked for
tutor and branch_manager. D-086 recorded this in S33. What is new is the *reach*: S28 added the
dashboard and report surface after D-086 was written, so the unchecked path now includes
`GET /students/{id}/dashboard`, `POST /students/{id}/report`, and `GET /students/{id}/reports` —
meaning a tutor token can read any student's mastery, accuracy and usage data and generate
LLM-written reports about a student they have no relationship to. D-086's text reasons about
session history, which was the surface that existed at the time.

Also stale: the code comment says the check "land[s] with Q&A authorization (Session 13)". S13
shipped without it. A pointer to work that already happened without doing the thing is worse than
no pointer.

**Reproduction.** Mint a tutor token for any `sub`, call
`GET /learning/students/<any-student-id>/dashboard`. No relationship is required or checked. Not
independently exploitable today — obtaining a tutor token requires the `/dev/token` path, which is
secret-gated as of this session — but that is a property of the current deployment, not of the
authorization code.

**Evidence.** [authorization.py:34-36](../apps/learning-api/src/learning_api/authorization.py#L34-L36)
is the whole check for these two roles. All 17 learning routes were enumerated and traced: every
route that names a student or a session does call `resolve_target_student`, so the gap is
uniformly *this function's* gap, not a per-route omission — which is the good news, since one fix
closes all of them.

**Disposition.** Unchanged from D-086: blocked on a tutor-assignment / branch_manager-branch data
model that `ProfileAdapter` does not have yet, which S42's discovery and S43's `IcProfileAdapter`
are what unblock. This finding adds two things to that record: the dashboard/report surface is in
scope, and the formal disposition is already scheduled for S46 (§5's "D-086 disposition
recorded"). Fix the stale comment whenever the file is next touched.

### AUD-L-09 — Numeric grounding checks provenance, not attribution (P2)

- **Severity:** P2 — degraded quality in parent-facing text, with a workaround (the facts-only
  template always shows the correct numbers)
- **Area:** correctness / stage-narrative and report grounding
- **Status:** open, Phase 0B

**What.** `numeric_grounding.is_grounded` returns False only if the narrative contains a number
that appears nowhere in the evidence dict. It does not check what the number is *claimed to mean*.
So for a student who improved from 4 to 6, the sentence "your score fell from 6 to 4" is fully
grounded — both numbers are in the evidence — and is accepted and shown. Same for swapped skills,
inverted gains, or a pre-exam figure presented as a post-exam one.

**Reproduction / evidence.** Structural, and visible in the nine-line function: it iterates
`extract_numbers(narrative_text)` and asks only whether each has *some* match anywhere in the
flattened evidence values. Direction, pairing, and field identity are never consulted.

**Why it matters more than P2 suggests, and why it is still P2.** This is the last check between
an LLM and a parent reading about their child's progress, and the product's whole framing is
growth-oriented language (SPEC §5.10.3) — a narrative that inverts a real gain is worse than no
narrative. But it is genuinely bounded: the deterministic fallback always contains the correct
figures, the numbers themselves can never be invented, and both parent-facing surfaces show
`verified_facts` alongside the prose, so a wrong claim sits next to the right data.

**Disposition — DECIDED (user, S36 close-out; see D-098).** Phase 0B, two partial mitigations,
with the incompleteness stated rather than papered over:

1. **A directional check.** When the evidence carries a known gain, reject narrative text that
   pairs those two numbers in the wrong order — this is what stops "your score fell from 6 to 4"
   for a student who went 4→6, which is the damaging class.
2. **Narrow the evidence dict per stage**, so each narrative is only given the fields it needs and
   there are fewer unrelated numbers available to misattribute at all.

Rejected: accept-and-rely-on-displayed-facts (defensible at current volumes, but it leaves
unverified LLM prose as parent-facing text about a child); and real semantic verification, which is
the only *complete* answer but is a project rather than a fix, adds a paid call per narrative, and
would itself need a cost ceiling given AUD-L-02. **Neither chosen mitigation makes the check
sound** — that limitation should be recorded in the code, not just here, so nobody later mistakes
the directional check for full verification.

### AUD-L-08 — `normalized_gain` is unbounded, and its denominator comes from the attempt count (P3)

- **Severity:** P3 — but see the reachability correction at the end of this entry; "not reachable
  today" was wrong in two ways.
- **Area:** correctness / learning-gain math (SPEC §5.13.3)
- **Status:** open, Phase 0B

**What.** `learning_gain.compute_learning_gain` sets `max_score = float(len(pre_graded)) or 1.0` —
the *count of resolved pre attempts*, not the assessment's declared item count — and then computes
SPEC §5.13.3's `(post - pre) / (max - pre)` with no clamp on the result. If the post form ever
carries more items than the pre form, or pre attempts are ever missing while post attempts exist,
the quotient exceeds 1.0 and is stored and displayed as a normalized gain. The `or 1.0` guard
protects against ZeroDivisionError but converts a zero-pre-attempt case into a denominator of 1,
which is worse than an error: it produces a plausible-looking number.

**Reproduction (empirical).** Called the real function with a fake question repo:

| Case | `raw_gain` | `normalized_gain` | `status` |
|---|---|---|---|
| normal 10-item, pre 4 → post 6 | 2.00 | 0.333 | `None` |
| post form longer than pre (12 vs 10) | 8.00 | **1.333** | `None` |
| no pre attempts, post 6 correct | 6.00 | **6.0** | `None` |
| pre 1 item wrong, post 10 correct | 10.00 | **10.0** | `None` |

Note `status=None` in every row — a 1000% gain is not flagged as anomalous, it is reported as a
valid normalized gain. It would then pass the report's numeric-grounding check, because the number
*is* in the evidence; grounding verifies provenance, not plausibility.

**Why it is nevertheless P3.** I traced whether any of those inputs can occur:
`assessment_builder.build_post_exam` builds the post form by iterating `pre_items` and generating
one fresh variant per pre item, so the post length **always** equals the pre length; and
`build_pre_exam` is a fixed 5 difficulties × 2 questions with a hard `AssessmentBuildError` if any
difficulty lacks approved templates, so a zero-item pre exam cannot be created either. S22's
finalize grades every unanswered item incorrect, so the attempt count matches the item count. The
bad inputs are unreachable through the real flow.

**Why it is still worth fixing.** Nothing *states* that invariant where the arithmetic lives, and
nothing tests it. The protection is a property of a different module's loop shape. An adaptive or
variable-length post form — a plausible future change, and the kind of thing SPEC §5.13.2's
"parallel form" language does not forbid — would silently start producing >100% gains in
parent-facing reports, with no error and no flag. A one-line clamp plus a comment naming the
invariant costs nothing and converts a latent correctness bug into an impossible one.

**Reachability correction (S36 continuation).** The "not reachable today" claim above was wrong
in two independent ways, both found by driving real journeys through the real API rather than
calling the function with fabricated inputs:

1. **The negative direction is reachable right now, with no unusual setup.** A student driven
   8/10 → 4/10 through the ordinary flow was stored with
   `normalized_gain = -2.0` and `normalized_gain_status = NULL` — a −200% "normalized learning
   gain", flagged valid. The entry above only considered the `> 1` direction, so the *unbounded*
   framing was right and the *unreachable* framing was not.
2. **The `> 1` direction is reachable too, via AUD-L-10.** The reasoning above ("the post length
   always equals the pre length") is true of *item* counts, but this arithmetic uses **attempt**
   counts, and AUD-L-10 shows attempts are not one-for-one with items: a second answer to one
   post-exam item pushes `post_raw` above `max_score`. The stated invariant does not protect the
   quantity the code actually divides by.

Also worth recording, because it is the opposite of the expected failure: an extra *pre* attempt
takes the `pre_raw >= max_score` branch **off**, so a genuine 10/10 pre-exam stops reporting
`not_applicable_pre_max` and starts reporting a computed `normalized_gain` instead. The flag that
exists to mark this case unmeasurable disappears exactly when it applies.

**Bound on user exposure (checked, not assumed).** `normalized_gain` appears in
`apps/learning-web/src/types.ts` but is rendered by **no screen or component**, so −200% is not
displayed today. It *is* passed into `StageNarrativePayload` (`nodes.py:650`), so it can shape the
`post_outro` narrative text a student reads.

### AUD-L-01 — A gated-off `/dev/token` discloses its own existence; the S35 gate's rationale is incorrect

- **Severity:** P3 (information disclosure only — no token can be minted)
- **Area:** auth surface / deploy-time security gate
- **Found by:** reading [.github/workflows/deploy-staging.yml](../.github/workflows/deploy-staging.yml)'s
  gate comment while extending it for S36/D-097, then probing the claim instead of trusting it
- **Status:** open, Phase 0B

**What.** The gate comment asserts: *"with the endpoint gated off, the route is never
registered on the app at all."* That is not how the code works. `@app.post("/dev/token")` is
registered unconditionally at module import; the 404 is raised from *inside* the handler after
FastAPI has already matched the route and validated the request body. So request shapes that
fail before the handler body runs return something other than 404, and reveal that the path
exists.

**Reproduction.** Both apps, settings in staging's real posture
(`environment="staging"`, `dev_token_endpoint_enabled=False`, no shared secret):

| Request | Actual | A genuinely absent route |
|---|---|---|
| `POST /dev/token` valid body | 404 | 404 |
| `POST /dev/token` `{"role": "not-a-role"}` | **422** | 404 |
| `POST /dev/token` `{}` | **422** | 404 |
| `GET /dev/token` | **405** | 404 |

**Evidence.** Probed directly against both apps' real ASGI app via `TestClient` with settings
monkeypatched to staging's posture; the table above is that run's output. `POST /dev/nonexistent`
returns 404 in the same run, which is the control that makes 422/405 a disclosure rather than
FastAPI's normal behavior for any unknown path.

**Why it matters.** Two distinct consequences, one small and one worth more than its severity:

1. The disclosure itself is minor. No token is issued, and an attacker learning that
   `/dev/token` exists on a FastAPI service learns very little — the endpoint's name is in a
   public-shaped codebase pattern anyway.
2. The gate is *load-bearing security infrastructure written in response to a P0*, and its
   stated reason for trusting a 404 is false. It happens to still work, because it probes with
   a valid body, which is exactly the shape that does reach the handler's gate. That is luck
   rather than design: nothing recorded anywhere says the probe body must stay valid for the
   gate to mean anything, so a later well-intentioned edit ("send an empty body, we only care
   about the status code") would silently turn the gate into decoration that always fails.
   This is the same class as D-096's `ecr:DescribeImages` finding — a check that appears to
   assert something stronger than it does.

**Disposition.** Phase 0B. Two changes, neither urgent: correct the comment to describe the
real mechanism and state that the probe body must remain valid; and register the route
conditionally rather than gating inside the handler, so a disabled endpoint is genuinely
absent for every request shape. The second is the real fix but touches how both apps'
`Settings` are read at import time, and the existing tests monkeypatch `get_settings` on the
module *after* import — so it needs a small test-approach change, which is Phase 0B work, not
mid-audit work.

## S36 continuation — the four uncovered audit areas (2026-07-25)

The S36 session covered money, minors/PII, authorization and the data-integrity pattern sweep,
and ran out. This continuation covers the rest: §3.4's scoring / re-grade-consistency /
policy-snapshot remainder, §3.5's mastery + hint ladder + generation pipeline + memory work, and
all of §3.6 (independent recomputation). Method note: §3.6 could not be done against the existing
database because every learning table except `student_reports` and `stage_transitions` was empty,
so **four complete journeys were driven through the real local API first** — improving (3→9), flat
(6→6), regressing (8→4) and pre-max (10→9) — and every number below is recomputed from those raw
rows with SQL that never calls the code under audit.

### AUD-L-10 — The server marks an exam item `answered`, then accepts more answers for it; scores are attempt-counted (P1)

- **Severity:** P1 — fail-open on a data-integrity invariant the server already has the state to
  enforce. Not P0: there is no production traffic, and the shipped UI closes the common path.
- **Area:** data integrity / deterministic scoring (SPEC §5.9.2, §5.13.3)
- **Status:** open, fix before the gate

**What.** `_mark_item_answered` sets `assessment_items.status = "answered"` on every submission and
`GET /exam/overview` reports it, so the server knows an item is done. Nothing on the answer path
reads it. Idempotency is keyed `(assessment_session_id, question_variant_id, Idempotency-Key)`, so a
second submission for the same item under a *different* key grades and inserts a second attempt —
it does not replace the first, and both count.

**Reproduction (live, local API).**

```
answer item 0 wrong  (Idempotency-Key: change-1) -> 200
answer item 0 right  (Idempotency-Key: change-2) -> 200
attempt rows for that one item                   -> 2      (a,d,f / d,d,t)
answer the other 9 items once each, finalize     -> 200
pre-exam totals                                  -> 11 attempts / 10 correct   (10 items served)
```

and without any phase manipulation:

```
answer an item, confirm overview reports status=answered
answer it again with a new key -> 200, attempt rows = 2
```

Of every assessment session in the local database, exactly one has `attempts > items`, and it is
this probe — so this does not otherwise occur, it is simply unguarded.

**Why it corrupts scores.** `learning_gain.compute_learning_gain`:

```python
pre_raw   = count(correct pre attempts)
max_score = len(pre_graded)            # ATTEMPT count, not item count
normalized_gain = (post_raw - pre_raw) / (max_score - pre_raw)
```

One changed answer on a 10-item exam gives `pre_raw=10, max_score=11`: the exam scores 10/11, and
the `pre_raw >= max_score` branch stops firing, so `not_applicable_pre_max` is silently replaced by
a computed `normalized_gain`. A duplicate *post* attempt pushes `post_raw` above `max_score`,
producing AUD-L-08's `> 1` case. Changing an answer from wrong to right therefore *lowers* the
score, which is the opposite of what a student would expect.

**Why the shipped UI mostly hides it, and why that is not enough.**
`ExamScreen` gates on `isReadOnly = isExamPhase && currentOverviewItem?.status === "answered"` and
renders "You've already answered this question - it's locked in and can't be changed." But the
optional chaining makes the guard default to **permissive**: when `currentOverviewItem` is
undefined — overview not yet fetched, or its fetch failed — re-answering is allowed. And
`submitAnswer` mints `crypto.randomUUID()` per call, so SPEC §5.9.2's idempotency key can never
match a prior submission and is inert for the purpose the spec cites it for. `busy={false}` is
hardcoded at all six screen call sites in `App.tsx`, so there is no in-flight guard either;
double-click is prevented only incidentally, by `setSelected(null)` disabling the button on
re-render. Any non-browser client is unguarded entirely.

**Recommendation.** Reject (or treat as idempotent) an answer for an item already `answered`,
server-side, in the same place the status is written; and derive `max_score` from the declared item
count rather than the attempt count. The second half also closes AUD-L-08's reachable path.

### AUD-L-11 — `UnknownQuestionVariantError` is caught nowhere: unhandled 500 (P2)

- **Severity:** P2 · **Area:** robustness / API contracts · **Status:** open, Phase 0B

Raised at `flow.py` lines 295, 416, 422 and 697; `grep` finds no `except` for it in any router, in
the graph, or in `main.py`. Live: `POST /answers` with `question_variant_id="does-not-exist"` →
**500 Internal Server Error**. Also reached by answering a valid variant that is not the currently
served study item — a stale tab, or a retry landing after the phase advanced (observed while
probing AUD-L-10).

The correct pattern already exists one file away: `POST /sessions/{id}/chat` validates the same
thing and returns 400. 500s inflate error-rate metrics and can trip the CloudWatch alarms S34
added, so this is noise in exactly the signal S39 will rely on.

### AUD-L-12 — `recommended_difficulty` is computed, stored and displayed, but routes nothing (P2)

- **Severity:** P2 · **Area:** SPEC conformance (§5.11.2 rules 2–3) · **Status:** open, Phase 0B

`mastery_bootstrap.recommended_difficulty` implements the rule correctly (modal assessed tier,
nudged ±1 by accuracy, clamped 1–5) and `flow.py:233` stores it per skill. Two docstrings claim it
drives routing — `mastery_bootstrap.py:7` ("for difficulty routing (§5.11.2 rules 2-3)") and
`study_plan.py:5-7` ("`recommended_difficulty` (from bootstrap mastery) **seeds the session's
`starting_difficulty`**"). Neither is true: `build_study_plan` reads it into `recommended`
(line 133), packs it into the ranking tuple (138), and drops it — line 142 unpacks only `skill_id`.
`starting_difficulty` is assigned `first_item.difficulty` (line 169). Its only other readers are
display surfaces (`students.py:130`, `history.py:110`).

**Evidence.** `aud-student-regressing`'s weakest skill `linear_distribute` has
`weighted_score = 0.0` and `recommended_difficulty = 4` — stepped *down* from tier 5 because
accuracy was 0 — yet the study session was created with `starting_difficulty = 5`. The student was
served the tier they had just failed, with the model's step-down recommendation unused in the same
transaction.

Masked today because the bank is 1:1 skill↔difficulty (the D-060/A6 collinearity, which
`study_plan.py:7-8` acknowledges: "a skill *is* its difficulty tier"), so ranking by weakest skill
accidentally yields a defensible tier. It stops being accidental the moment real content has more
than one skill per tier. Either wire it up or delete it and correct both docstrings — a computed,
stored, displayed number that influences nothing is worse than an absent one.

### AUD-L-13 — Memory consolidation verifies provenance and repetition, never the claim against measured mastery (P2)

- **Severity:** P2 · **Area:** minors / correctness · **Status:** open, Phase 0B

`consolidation.py` verifies that a candidate fact's cited `evidence_event_ids` exist, demotes an
opposite-polarity fact to `contested` rather than replacing it, and requires ≥2 sessions of
evidence before promoting `provisional` → `active`. It never compares the fact against
`mastery.weighted_score` for the same skill, which is in the same database and the same transaction.

**Evidence.** `aud-student-regressing` has `mastery.weighted_score = 0.0` for `linear_distribute`
and an accepted `strength` fact for that same skill — *"Shows independent strength in this
skill."* — citing real events. Across all four journeys **all 20 facts are `strength` and zero
`weak_skill` facts exist**, including for the student who went 8→4 and whose own
`learning_gain.unresolved_skills` names `linear_distribute`.

**Bound, and it is a real bound.** `_resolve_relevant_fact` uses `top_fact_for_skill`, which
excludes `provisional`/`contested`/`superseded`/expired, so only `active` facts reach tutoring
payloads and parent-visible reports — and everything here is `provisional`. Nothing prevents it
after a second session, though, because the promotion criterion is repetition, not consistency.

Same class as AUD-L-09 (provenance verified, attribution not), one layer earlier in the pipeline,
and it concerns claims about a child's ability that AUD-L-04 already showed reach parents.
A deterministic floor — refuse a `strength` fact for a skill whose measured mastery is below
`WEAK_SKILL_THRESHOLD`, and vice versa — is cheap and does not depend on model quality.

### AUD-L-14 — `time_spent_minutes` reads best-effort client telemetry and ignores the always-populated server column (P2)

- **Severity:** P2 — a wrong parent-visible number, presented as a *verified fact*. Fails low.
- **Area:** correctness / reporting · **Status:** open, Phase 0B

`build_dashboard` computes `time_spent_minutes = total_time_ms / 60000`, where
`total_assessment_time_ms_in_range` sums `AssessmentItemState.time_spent_ms` — populated only by
S23's autosave tick (`POST /exam/items/{id}/time`), sent by the frontend. Meanwhile
`assessment_attempts.response_time_ms` is `NOT NULL` and written on every answer.

**Evidence.** The four journeys produced **140 `assessment_item_state` rows with
`sum(time_spent_ms) = 0`**, while the same students' attempts hold 41,250 ms per exam (≥82.5 s
each across both exams). `POST /students/{id}/report` accordingly returned, inside
`verified_facts`: `attempts_count: 26` and `time_spent_minutes: 0.0`. `verified_facts` is the
grounding set the narrative is checked against, so "0.0 minutes" is presented as verified.

The repository docstring claims item-state is "the only populated per-question timing source in
this schema". Half true: `study_attempts` genuinely has no response-time column, so study time
really is unavailable — but for exams an always-populated source exists and is ignored.

Frontend fragility compounds it: `ExamScreen` records time in a `useEffect` **cleanup** (fires on
item/phase change or unmount), gated on `currentOverviewItem?.assessment_item_id` being present,
and `useLearningSession.recordItemTime` swallows every failure with `.catch(() => {})`. A hard
refresh, a closed tab, a failed overview fetch, or any non-browser client yields 0.0.

### AUD-L-15 — Mastery and "skills to strengthen" use different windows and are shown together as "all time" (P2)

- **Severity:** P2 · **Area:** correctness / reporting · **Status:** open, Phase 0B

`_recompute_all_skill_mastery` accepts only `pre_assessment_session_id` and `study_session_id`;
the post-exam is **structurally excluded**, and its docstring says so ("every skill touched by the
pre-exam or study phase"). `unresolved_skills` / `weak_skill_names` come from `learning_gain`,
which is post-exam-derived. Both land in one report payload.

**Evidence** — `aud-student-premax` (10/10 pre, 9/10 post):

| skill | `mastery_by_skill` | listed in `unresolved_skills` |
|---|---|---|
| `linear_distribute` | **1.000** | **yes** |

The same report's `interpretation_text` reads *"Skills to strengthen: Solve linear equations
requiring distribution and combining like terms"* while `mastery_by_skill` gives that skill 1.0,
and `verified_facts.date_range_label` says **"all time"** — which misdescribes mastery, since
mastery never sees the post-exam. A parent sees 100% mastery and "needs work" for one skill in one
view, both labeled verified.

**The arithmetic is correct.** Recomputing mastery from raw rows restricted to the pre+study window
reproduces all five skills exactly (`linear_both_sides` 1.0000, `linear_distribute` 0.0000,
`linear_neg_frac_coeff` 1.0000, `linear_one_step` 1.0000, `linear_two_step` 1.0000). This is a
windowing and labeling defect, not a computation defect — the fix is to state each number's window,
and to decide deliberately whether mastery should include the post-exam.

### AUD-L-16 — Both policy snapshots are write-only (P3)

- **Severity:** P3 (no behavioral defect today) · **Area:** design integrity (SPEC §5.9/§5.13)
- **Status:** open, Phase 0B

`assessment_sessions.policy` and `study_sessions.intervention_policy` are written at creation and
**never read back anywhere**. The only consumers of `exam_policy` in either app are the two
`get_policy()` calls in `assessment_builder`, both at creation time. Only `time_limit_seconds`
governs runtime behavior, and it does so through its own denormalized column
(`flow.py:142-144`), not through the snapshot.

`hints_allowed`, `navigation` and `feedback_visibility` are enforced — where at all — by hardcoded
phase-string checks: chat returns 409 unless `phase == "study"` (its comment says it is "matching
`exam_policy`'s `hints_allowed=False`", i.e. the policy is documentation, not the mechanism), and
intervention interrupts are only ever created on the study path. Those checks agree with the
snapshot today, but a policy change would apply retroactively to in-flight sessions — the one thing
snapshotting exists to prevent. `intervention_policy` is a hardcoded `{"hints_enabled": True}`
literal at `study_plan.py:152`.

### AUD-L-17 — The default mock's hint boilerplate tripped the runtime leak check; `was_personalized` records no reason (P3, mock half fixed in-session)

- **Severity:** P3 · **Area:** test integrity + observability · **Status:** mock fixed; the
  observability half is open, Phase 0B

D-097's addendum recorded the long-standing
`test_hint_reflects_the_students_actual_wrong_option` flake as unseeded-RNG-driven at ~1 in 4 and
prescribed "seeding the fixture's RNG". The mechanism was RNG-driven; the attribution was wrong,
and no fixture RNG exists to seed — `_turn_context` constructs `random.Random()` per request
inside the route handler.

**Real cause.** `tutor.generate_personalized_hint` discards any hint in which
`answer_text_leaked` finds the served question's correct answer standing alone, substituting the
canonical ladder text. `MockBedrockProvider`'s personalization stand-in prefixed its output with
`Level {level} hint`, and `answer_text_leaked("Level 1 hint…", "1")` is `True` — a bare `1` with
non-alphanumerics on both sides. ~6% of this bank's variants have the answer `"1"`, and the
unseeded per-request RNG chooses the variant, so the test failed whenever that variant was served.
Measured **8 failures in 60 standalone runs** (13%), not 1 in 4; every failure returned the level-1
canonical text verbatim, confirming the fallback path.

**Fixed** by changing the marker to `Hint L{level}` — gluing the digit to a letter satisfies the
check's lookarounds — with the reason written into the docstring so it is not "tidied" back.
**60/60 passing** afterwards, against 52/60 before. Pinned by a new deterministic guard,
`packages/curriculum/tests/test_mock_hint_is_leak_clean.py`, which asserts the mock's output is
leak-clean for every reachable short answer at every level of every shape ladder, and that it still
names the misconception and varies by level.

**The half that is not fixed, and matters more.** `hint_events.was_personalized` is a single
boolean with no reason code, so *gateway failure*, *leaked answer*, *ladder monotonicity violation*
and *model set `answer_revealed`* are indistinguishable after the fact. `answer_text_leaked` is a
boundary-anchored substring match and roughly 54% of this bank's variants have a single-digit
answer, so any real model hint whose prose contains that digit standing alone ("Step 1", "try 2
more") is silently downgraded to the canonical hint. It fails safe — the student gets a generic
hint, never a leaked answer — but the rate is unmeasurable from what is stored, which means the
quality cost of a safety check cannot be observed in production.

### Areas audited with no finding

**Money — no Bedrock call bypasses the gateway.** Grepped every `raw_generate` / `raw_embed` /
`invoke_model` / `boto3` reference across `apps/` and `packages/`: the only hits outside
`adapters/bedrock/` are two comments. Every paid call in both apps really does go through
`ResilientBedrockGateway`, so the timeout, bounded retry, `_HARD_MAX_OUTPUT_TOKENS = 4000` cap,
circuit breaker, and cost accounting are unavoidable rather than conventional. This is the
premise AUD-L-02 depends on, so it was checked rather than assumed.

**Money — every other `session_spend_cents` call site passes a real accumulated value.** All 20+
call sites traced. The graph nodes thread `bedrock_spend_cents` (persisted in the checkpoint, so
it survives a process restart) and correctly pass `bedrock_spend_cents + cost` where several
calls happen inside one node; `video_catalog`, `tutor`, `tutor_chat`, and chat's own nodes all
receive a real total. The two defaults were the only two gaps, and both are now closed or logged.

**Money — bounded-by-design behaviors, noted but not findings.** The pre-flight budget check
estimates input at a hardcoded 2,000 tokens, so a call whose real payload is larger can overshoot
the ceiling by one call's worth; and a `generate_structured` call can make up to four provider
calls (three attempts plus one repair) while the budget is checked only once, at entry. Both are
bounded overshoots of a ceiling rather than absent ceilings, and the circuit breaker limits
sustained failure spend (verified with a real concurrency test in S34). Recording them so a
future session doesn't have to re-derive that they were considered.

**Money — no account-level enforcement exists**, only the AWS Budget *alarm*. This is
infrastructure rather than learning-product code, so it belongs to S39/AUD-F's operations audit
(§2.6 criterion 8 already requires proving alarms reach a human); noted here as a cross-reference
so it is not lost between the two sessions.

**Authorization — every learning route enforces the check; the coverage is uniform.** All 17
routes across `questions.py`, `sessions.py`, `stream.py` and `students.py` were enumerated and
each traced to its authorization call. Student-scoped routes call `resolve_target_student` with
the path's `student_id`; session-scoped routes call it with the *checkpoint's*
`student_external_id` rather than anything client-supplied, which is the right source. The four
`exam/items/...` routes share one helper, so they cannot drift apart. `POST /sessions` (create)
deliberately has no student yet and says so (`del claims  # authentication only`). No route was
found missing a check — the only authorization defect is AUD-L-07, which lives in the shared
function, not in any route.

**Authorization — the SSE `?token=` path verifies audience and ownership.** `stream.py` verifies
the token against `Audience.LEARNING` explicitly (a chat-audience token is rejected), then applies
`resolve_target_student`, and for a session that has no student selected yet falls back to
comparing `claims.sub` against the checkpoint's `user_external_id` — so a brand-new session cannot
be attached to by a different caller either. `/resume` has the same two-branch check. Deeper
SSE/thread-hijack work is AUD-X/S38's, but these two properties hold.

**Data integrity — the D-071 checkpoint-overwrite bug class does not recur in the learning app.**
Swept every explicit `": None"` channel write in both graphs. The learning app has exactly two,
and both are correct *because* they erase: `"last_items": None` when attendance blocks a start (a
stale question batch must not sit beside a blocked message) and `"last_message": None` when
entering the pre-exam with fresh items. Neither is the S23 shape, which was writing `None` to mean
"nothing new to report". The chat app has ~40, including 12 writes of `"access_hint": None` — not
audited here (AUD-C/S37 owns it) but flagged as a cross-reference, since `access_hint` is the field
in the known S22.5 blank-turn bug and that combination deserves a deliberate look.

**Data integrity — finalize is genuinely idempotent, at both layers.** `flow.finalize_exam`
returns `None` when the target `AssessmentSession` already has `finalized_at`, and the node then
returns `{}` — which under LangGraph's default merge preserves every channel, the same
"omit to preserve" convention D-071 established. The route additionally allows the `study` and
`completed` phases through on purpose, so a retry arriving after the phase has visibly moved still
re-serves the same result instead of 409ing, and it 409s explicitly when no student is selected
rather than relying on a downstream failure.

**Test signal — the known RNG flake is characterized more precisely than before, and it matters
for the gate.** `test_hint_reflects_the_students_actual_wrong_option` failed once in a full run and
once standalone this session, then passed three consecutive standalone runs and two full runs.
PROGRESS.md's prior sessions describe confirming it "via an immediate clean standalone rerun" — but
it reproduces standalone too (roughly 1 in 4 attempts here), so it is **purely unseeded-RNG driven,
not test-order dependent**. That is good news for whoever fixes it: seeding the RNG in the fixture
is sufficient, and no ordering investigation is needed. It is bad news for §2.6 criterion 4, which
requires three consecutive green full runs — at this failure rate that is a coin flip, so the
criterion would be met by luck rather than by signal. Fix the seed before attempting the gate.

**Question bank — what is actually `approved` and deliverable today, measured.** Queried the real
dev Postgres rather than reasoning from the seed scripts: **1 topic, 5 skills, 50 templates**, all
`validation_status=approved` and `active_status=active`, exactly 10 templates at each difficulty
1–5. `build_pre_exam` needs 2 per difficulty, so exam construction is satisfiable with 5× headroom
— the bank is *sufficient*, which is worth stating separately from being *broad*. It is not broad:
one topic, and **exactly one skill per difficulty level**, so skill and difficulty are perfectly
collinear in this data. Any "skill-level gain" is also a difficulty-level gain, and no test using
this bank can distinguish the two. That is the known A6/D-060 content gap (which gates the pilot,
not the build), now quantified.

**Two known carry-overs re-measured, both materially worse than last recorded** — numbers handed
to Phase 0B rather than left as "worsening": `question_variants` is at **42,023 rows across 50
templates**, with a worst single template at **1,559** (S23 recorded 610 on one template, so ~2.5×
growth in one session's worth of elapsed work); the `checkpoints` table is at **264,475 rows**
(S34 recorded 249,250). Both confirm the accumulation is ongoing rather than a one-off, which is
the assumption the seeded backlog items were written under.

**Correctness — the retry ladder matches SPEC §5.11.7 exactly, including the part that looked
wrong.** `study_outcomes.ladder_step` maps attempt counts to moves precisely as the spec's table
does (1st → retry, 2nd → retry with more explicit support, 3rd → easier prerequisite, 4th →
unresolved + tutor review), all six final outcome labels exist, and mastery is recomputed only
*after* the label is final so an assisted or unresolved answer can never inflate independent
mastery. There is also a sensible unspecified degradation: the prerequisite drop only happens if
the prerequisite actually has approved templates, otherwise it retries the same skill rather than
serving nothing.

I went in expecting a real bug here and did not find one. The escalation counts attempts on a
"line" filtered by the item's `target_skill_id`, so dropping to an easier prerequisite looked like
it would start a fresh line and make the 4th-attempt tutor-review escalation unreachable — a
student could fail forever without ever being flagged. It does not: `create_study_item` takes
`target_skill_id` (the base skill whose line the item belongs to) *separately* from `skill_id` (the
skill the question is drawn from), so a prerequisite question keeps the original line's identity
and the counter keeps climbing to the tutor-review threshold. Recording this as a negative result
specifically because the correct behavior depends on a two-parameter distinction that is easy to
misread as a bug, and the next person to look will otherwise re-derive the same false alarm.

**Correctness — the learning-gain formulas match SPEC §5.13.3 exactly.** `Raw Gain = Post − Pre`
and `Normalized Gain = (Post − Pre) / (Max − Pre)` are implemented literally, and the perfect-pre
case sets `normalized_gain_status = "not_applicable_pre_max"` with `normalized_gain = None` as the
spec requires (rather than emitting a division-by-zero or a misleading 0.0). All twelve fields
§5.13.3 says to store are present and populated: pre/post raw, raw gain, weighted gain, normalized
gain, skill-level gain, difficulty transition, independent-correct rate, hint dependency, solution
dependency, unresolved skills, and response-time change. AUD-L-08 is a missing bound on the result,
not a wrong formula.

### Areas audited with no finding — S36 continuation

**Scoring is deterministic, and stored rather than re-derived.** All 93 stored
`assessment_attempts` satisfy `is_correct == (selected_option == correct_option)` — zero
disagreements. `resolve_graded_attempts` uses `attempt.is_correct` for assessment attempts, so a
later edit to a variant cannot retroactively re-grade a past exam. Zero attempt rows disagree with
their variant's *current* `correct_option`, so no drift has occurred either. Every field SPEC §5.9.3
requires on an attempt is present, including `correct_option` frozen at submission time.

**Template edits cannot retroactively move historical analytics.** `skill_id` and
`difficulty_label` *are* read live from `question_templates` when grading attempts for mastery and
gain, which looked like a re-grade-consistency hole. It is not: templates are versioned by creating
new rows, and `supersede_template` only flips `validation_status` while keeping the prior row — so
the fields the analytics read are immutable per row.

**Unanswered items fail closed.** A skipped item and a never-visited item both received attempts
with `selected_option = NULL, is_correct = false` under a `finalize-unanswered-*` key; totals stayed
10 attempts / 8 correct on a 10-item exam. Unknown is not treated as correct.

**Exam assistance cannot leak in, matching `hints_allowed=False`.** During `pre_exam`: `/respond`
with `intervention_choice` → 409 "no interrupt is pending"; `/chat` → 409 "chat is only available
during study"; a wrong answer produces no interrupt and withholds correctness (`is_correct: null`,
matching `feedback_visibility=hidden_until_finalize`). The enforcement is structural rather than
policy-driven (AUD-L-16), but it holds.

**SPEC §5.9.1 exam composition is exact.** Every pre- and post-exam served 2 questions per
difficulty tier 1–5, total 10, verified by joining `assessment_items` through `question_variants` to
`question_templates.difficulty_label` for two students across four exams.

**SPEC §5.10.1's weights and formula are literal.** `DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.4, 3: 1.9,
4: 2.5, 5: 3.2}` matches the spec's example exactly, and `weighted_score` is exactly
`Σ(weight where correct) / Σ(weight)`.

**SPEC §5.11.1's `base_problem_count = 5` holds.** The 6 study items per journey are 5 base + 1
remediation; §5.11.1 says remediation is "tracked separately", so 6 is conformant, not off-by-one.

**The hint ladder is correct end-to-end, driven live.** Three levels served in order, all texts
distinct, `answer_revealed=False` throughout, none containing the question's real answer text, and a
fourth request closes the ladder with 409 rather than looping or re-serving. All three rounds landed
in `hint_events`.

**Question-bank integrity is clean** across 50 templates / 43k variants: zero duplicate option sets,
zero `correct_option` outside `a–d`, zero null option text, zero empty `rendered_question`, zero
difficulty outside 1–5, zero templates without variants.

**Dashboard and report numbers reconcile against independent SQL.** `overall_accuracy` recomputed
bit-identically (`0.9230769230769231`, 24/26); `accuracy_trend` matched (17/26 = 0.6538);
`mastery_by_skill` matched all five skills exactly once restricted to its real window;
`pre_post_by_skill` reconciled item-by-item against difficulty tiers. The only report numbers that
did **not** reconcile are AUD-L-14 and AUD-L-15.

**`starting_difficulty` is not inverted** — I suspected it was, since a 10/10 student got tier 1
while an 8/10 student got tier 5. That is §5.11.2 rule 1 (lowest mastery first) working: the 8/10
student's two misses were both tier 5, and a perfect scorer ties on every skill so the documented
curriculum-order tie-break decides. Recorded because it reads like a bug.

**My own first recomputation was wrong, not the API.** An initial independent mastery calculation
disagreed with the dashboard on two skills (0.6 vs 1.0) because it summed *all* attempts while
mastery covers pre+study only. Recorded so the next session does not repeat it — and it is what led
to AUD-L-15.

**Note, not a finding:** `accuracy_trend` and `overall_accuracy` count hint-assisted corrects as
correct, while mastery counts only `independent_correct`. Both appear on one dashboard. Defensible
(one is "accuracy", the other "independent mastery") but the labels do not say so.

_(Still **not** covered: the browser-driven adversarial runs — refresh mid-exam, concurrent tabs,
expired timers, dropped SSE — and the live-staging half of §2.3. See PROGRESS.md for the explicit
list, rather than leaving the absence to be inferred from this file. The API-level adversarial
probes that *were* run are the ones evidenced above and in AUD-L-10/11.)_

---

## S37 — AUD-C (chat product correctness)

Method as §2.3 requires: traceability over SPEC §5.19–§5.24, §5.25.3, §5.29's chat rows and
§5.30.2/§5.30.4; defect-pattern sweeps for every class this project has already produced; and
adversarial runs — local against the real graph and real Postgres, plus a bounded pass against
**live staging** (`d222glidpp4azv.cloudfront.net`). Retrieval quality was measured twice, once with
`MockBedrockProvider` and once against **real Bedrock** (Haiku 4.5 + Titan v2, 76.7¢, 13m17s), which
is what made AUD-C-05 and AUD-C-06 visible at all.

### AUD-C-01 — `/messages` has no thread-ownership check, and an anonymous turn *erases* the owner the other two endpoints check (P1)

- **Severity:** P1. §2.4 lists authorization bypass under P0; this is held at P1 only because
  exploitation requires the thread's `uuid4` session id, which is never published, never in a URL
  bar, and not enumerable. The P0 argument is recorded below — it is not a comfortable margin.
- **Reproduction (live staging, deployed config, this session):**
  1. `POST /chat/sessions` → session id.
  2. `POST /chat/sessions/{id}/messages` with a **tutor** bearer token → grounded answer, and the
     thread's checkpointed `user_external_id` becomes `aud-c-tutor`.
  3. `POST /chat/sessions/{id}/messages` with **no Authorization header at all** → **HTTP 200**.
     The response body carries the tutor's previous answer *and* its citation
     (`public-organization-overview`) verbatim.
  4. `POST /chat/sessions/{id}/respond` with no token → **HTTP 200**. It succeeds because step 3
     rewrote `user_external_id` to `None`.
- **Locally, with a tutor-audience chunk that only a tutor could retrieve**, step 3's response
  contained the tutor-only text verbatim (`"Confidential tutor procedure: … the pager rota and the
  incident register are kept behind the lanyard cabinet"`), i.e. content the pre-retrieval filter
  had correctly withheld from anonymous callers one turn earlier. The same text was then served
  again by `GET /stream`'s initial snapshot, and every *subsequent* tutor turn was pushed to an
  event-bus subscriber that attached while the thread was owner-less — the SSE access check runs
  once, at connect time, and is never re-evaluated when ownership returns.
- **Two independent defects compose here.** The leak vehicle is AUD-C-04 (stale presentation
  fields); the authorization hole is this one. Either alone is much less serious. Fixing only
  AUD-C-04 would still leave an unauthenticated caller able to drive, and resolve interrupts on,
  someone else's thread.
- **Why it is asymmetric, and therefore unintentional.** `respond_to_interrupt` and
  `_initial_snapshot` contain the *same* five-line owner check. `post_message` does not — and it is
  the only one of the three that *writes* the field the other two read.
- **P0 argument, recorded rather than acted on.** Content that SPEC §5.21.3 requires be filtered
  before retrieval reaches a caller who may not retrieve it, and a documented access boundary is
  removable by an unauthenticated request. What holds it at P1: the attacker must already hold a
  128-bit session id, staging has no real users, and `/dev/token` is secret-gated. §2.4 reserves
  mid-audit fixes for P0s, so this is logged, not fixed — but it is the first item of Phase 0B, and
  both halves must land together.
- **Fix shape:** apply the existing owner check in `post_message`, and make `resolve_role` refuse to
  *downgrade* a thread's `user_external_id` from a value to `None`.

### AUD-C-02 — The scope guard's own topic list omits the organization, so "What is IntelliChoice?" is refused as out of scope (P1)

- **Severity:** P1 — a launch journey is broken for what is plausibly the most common question an
  anonymous visitor asks, on the deployed system, today.
- **Reproduction (live staging, 5/5):**

  | query | scope | intent | citations |
  |---|---|---|---|
  | `What is IntelliChoice?` | **out_of_scope** | clarification | — |
  | `Who leads IntelliChoice, and what did they do before?` | **out_of_scope** | document_qa | — |
  | (same query, repeated) | **out_of_scope** | document_qa | — |
  | `Who is on the IntelliChoice leadership team?` | **out_of_scope** | clarification | — |
  | `Tell me about the people who run IntelliChoice` | **out_of_scope** | clarification | — |

  Each returns SPEC §5.19.4's refusal — *"I cannot answer unrelated general-purpose questions"* —
  while `public-organization-overview` and `public-our-team` are approved, effective today, and
  ingested (the same corpus answers other questions with citations in the same session).
- **Root cause, and it is one line.** SPEC §5.19.4's supported-topic list begins with
  **"IntelliChoice organization"**. The `SCOPE_AND_INTENT` system prompt in
  `chat_api/graph/nodes.py` enumerates *"branches, schedules, volunteering, student learning, parent
  information, tutor/branch procedures, the academic calendar, and learning-app support"* — the
  organization itself is missing, as is §5.19.4's "student participation". A real classifier obeys
  the list it was given.
- **Why no test caught it.** `MockBedrockProvider._scope_and_intent_json` keys on a keyword tuple
  that *does* contain `"intellichoice"`, so every mock-backed test scores these queries in scope.
  The prompt text is never asserted against SPEC's list anywhere.
- **Note:** two of the five runs returned `in_scope=false` alongside `intent=document_qa` — the
  model contradicting itself within one structured response. The pipeline resolves that toward
  refusal (fail-closed, correct), but it is a signal the prompt is confusing the classifier.

### AUD-C-03 — The caller's precise coordinates are stored indefinitely in `checkpoint_writes`, contradicting the consent notice shown to them (P1)

- **Severity:** P1 — minors' precise location, against an explicit promise. Same shape as AUD-L-04:
  an accepted residual risk whose mitigating assumption stopped holding.
- **What the product promises**, verbatim in `LOCATION_CONSENT_NOTICE` (SPEC §5.1.3):
  *"IntelliChoice will not permanently store your precise location."*
- **What is stored.** After one locator turn with `latitude=32.9876543, longitude=-96.7654321`,
  decoding the checkpoint tables with LangGraph's own serializer finds the coordinates in
  **`checkpoint_writes`, channel `__resume__`**, twice:
  `{'approved': True, 'zip_code': None, 'city': None, 'address': None, 'latitude': 32.9876543,
  'longitude': -96.7654321}`. They are still present after **two further turns** on the thread, and
  no job deletes them — `chat-purge`'s 90-day retention covers `tutor_chat_messages`, not the
  checkpoint tables, and PROGRESS.md already tracks ~268k checkpoint rows accumulating unswept.
- **D-045 anticipated the mechanism and understated the duration.** It records that the saver
  "persists the raw `Command(resume=…)` value … so the location transits Postgres **briefly** at the
  framework level". Measured, "briefly" is "for the lifetime of the thread, which nothing bounds".
- **D-045 also overstates the difficulty.** It concludes removal "would mean disabling checkpointing
  for one specific node". It would not: `DELETE FROM checkpoint_writes WHERE thread_id = :t AND
  channel = '__resume__'` immediately after the locator node completes removes the value while
  keeping crash-safety for the window it exists to cover. A retention job over the checkpoint tables
  (already on the Phase 0B list for volume reasons) would bound it as a backstop.
- **Method note:** the first version of this check used `CAST(blob AS text) LIKE '%32.98%'` and
  reported zero hits. Checkpoint blobs are msgpack, so a float is eight binary bytes and a bytea
  cast renders as hex — that check would have certified a database full of coordinates as clean. It
  is recorded because it is the kind of PII probe that silently passes.

### AUD-C-04 — A turn that pauses on `interrupt()` returns the *previous* turn's answer, citations and access hint; `ics_content` never clears at all (P2)

- **Reproduction (local, real graph):** ask a document question (grounded answer + citation
  `public-organization-overview`), then on the same thread ask to contact an administrator. The
  second turn's response repeats the first turn's answer *and* its citation, with
  `pending_interrupt: email_approval` beside them. In chat-web that renders the previous answer, its
  citation chip, and any escalation/access-hint banner as if they answered the new question, while
  the approval modal sits on top.
- **Root cause.** Every terminal node explicitly resets the presentation fields (`answer`,
  `citations`, `confidence`, `missing_information`, `escalation_recommended`, `access_hint`). A node
  that pauses via `interrupt()` **never returns**, so nothing is reset and `ainvoke` hands back the
  channels as the previous turn left them. All three interrupt paths are affected
  (`admin_escalation`, `calendar_action`, `branch_locator_consent`). On a session's *first* turn the
  same code path returns `answer: null` — harmless only because a modal happens to cover it.
- **`ics_content` is worse: it is never reset by anything.** Measured across a real sequence —
  calendar turn → `.ics` choice → two unrelated document questions — `ics_content` was still
  populated on every later turn. chat-web renders a "Download .ics" button on each of those answers,
  all serving the original event.
- **Fix shape:** clear the presentation fields in `resolve_role`, which already runs first on every
  turn and already sets `query`/`standalone_query`.

### AUD-C-05 — The golden Q&A eval measures `MockBedrockProvider`, not retrieval; a real model rejects 10 of its 14 gating cases before retrieval runs (P2)

- **What the suite reported before this session:** refusal correctness 100%, no-hallucination 100%,
  citation grounding 100% (9/9) — all gated in CI.
- **The same fixture against real Bedrock:**

  | category | mock | real Bedrock |
  |---|---|---|
  | `grounded` | 100% (9/9) | **11.1% (1/9)** |
  | `role_gated` (marker-based) | 100% (5/5) | **0% (0/5)** |
  | `out_of_scope` | 100% | 100% |
  | `no_source` | 100% | 100% |
  | `adversarial` (added S37) | 100% | 83.3% |
  | `paraphrase` (added S37) | 28.6% | 42.9% |
  | `no_answer` (added S37) | **0% (0/8)** | **100% (8/8)** |
  | **grounded_citation_rate** | 68.8% | 25.0% |
  | **correct_refusal_rate** | 79.5% | 87.2% |

- **The collapse is not retrieval quality — it is the fixture.** Per-case diagnosis shows 7 of 9
  `grounded` cases and all 5 `role_gated` cases never reached retrieval: the real classifier returned
  `clarification` or `out_of_scope` and the graph refused first. That is *correct behavior* on those
  inputs. `"Baton Rouge Carver Public Library Terrace Street Saturday hours"` is a keyword list, not
  a question; `"zqxveval1 handbook"` is gibberish. Both were written that way deliberately — the
  fixture's own docstring explains that literal words from the target chunk were required to survive
  the mock's word-overlap reranker, and that nonsense markers were required to avoid coincidental
  matches. The suite was reverse-engineered into the mock's shape until a real model rejects it.
- **The two suites are close to inverted.** `no_answer` — plausible in-scope questions the corpus
  cannot answer — scores 0/8 under the mock and 8/8 under the real model. The mock cannot ever pass
  it: `_rag_answer_json` always answers from the first context chunk with a fixed confidence of 0.8,
  so every unanswerable question is answered from an unrelated document with a *verified* citation
  ("Does IntelliChoice provide transportation?" → a branch manager's biography, cited).
- **What this means for the §2.6 gate.** The 100% figures certify the mock, not the product. This
  session left the mock run in place as a deterministic CI gate for the categories it can genuinely
  decide (routing, filtering, deterministic citation verification, adversarial containment) and moved
  the retrieval-quality categories to measured-not-gated, with the real-Bedrock run as the instrument
  — see `apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py` (opt-in, three spend ceilings).
- **One genuine pipeline result inside the noise:** `grounded-overview-2` did run end to end under
  the real model — 8 chunks retrieved including the correct document — and still produced no citation
  and confidence 0.0. n=1, but it is the only case where the real pipeline was actually exercised and
  it declined to cite a document it had in hand.

### AUD-C-06 — SPEC §18-C3's access-aware refusal never fires under a real model (P2)

- **Measured 0 for 8.** Five marker-based `role_gated` cases and three newly written as real
  questions against seeded gated content ("How many sessions can my child miss before losing their
  place?", with a parent-audience chunk that answers exactly that). Under real Bedrock **not one**
  produced an `access_hint`.
- **Two distinct causes, both structural.** The marker cases are refused as out of scope before
  retrieval. The realistic ones reach `document_qa` and retrieve **8 chunks** — all public, because
  the pre-retrieval filter correctly withheld the gated ones — so retrieval is *non-empty* and
  `_route_after_answer_document_qa` sends them to `synthesize_answer`, never to `explain_access`.
  The feature's entire precondition is `retrieved_chunk_ids == []`, a lexical-emptiness condition
  that real hybrid search over a non-trivial corpus essentially never produces.
- **User-visible effect:** a parent asking a question the parent handbook answers is told *"I don't
  have an approved source for that yet"* rather than *"that's in the parent handbook — log in"*, even
  though `count_matching_by_audience` would have found it. The refusal is safe but unhelpful, which
  is precisely the outcome S19 built the feature to avoid.
- **Safety half held:** no gated content leaked in any of the 8 (consistent with the phase-B result
  below).
- **Fix shape:** run the access probe whenever the answer is a no-source refusal, not only when
  retrieval returned zero rows.

### AUD-C-07 — An embedding failure or an exhausted budget on the retrieval path is an unhandled 500 (P2)

- **Reproduction:** with the generation provider healthy and the embedding provider raising,
  `POST /messages` returns **HTTP 500** for both a `document_qa` query and a `calendar` query.
- **Cause.** `scope_guard` catches `BedrockGatewayError` and `retrieve`'s *rerank* call catches it,
  but `retrieve`'s `create_embedding` call is unguarded, and no exception handler exists in
  `chat_api.main`. `CostBudgetExceededError` and `CircuitOpenError` are the same exception family, so
  a budget exhausted at exactly that point produces a 500 too.
- **Reachability is not exotic:** generation and embeddings are different models from different
  families (`AnthropicBedrockProvider` vs `TitanEmbeddingProvider`) with separate quotas and separate
  model-access enablement. Titan throttling, or Titan access lapsing in the region, takes out every
  document question while classification keeps working. The shared circuit breaker also allows a
  half-open window where generation succeeds and the embedding call re-fails.
- **§5.29 requires "bounded retry and smaller-model fallback" for a Bedrock timeout.** A 500 is
  neither. Same class as AUD-L-11, and it is the most likely real-world trigger of AUD-C-10.

### AUD-C-08 — A total Bedrock outage answers every in-scope question with the out-of-scope refusal (P2)

- **Reproduction:** with every provider call failing, `POST /messages` returns 200 and SPEC §5.19.4's
  *"I cannot answer unrelated general-purpose questions."* Same for an exhausted session budget,
  which trips on the first `scope_guard` call.
- This is `scope_guard`'s deliberate fail-closed branch, and failing closed is right. The problem is
  the *message*: during an outage the product tells a user their in-scope question was off-topic, and
  a user who has exhausted the cost ceiling is told the same thing. §5.29's common mechanisms list
  "user-safe error message"; this is a user-*misleading* one. There is no operator-visible difference
  either — the response is identical to a genuine refusal.

### AUD-C-09 — §5.21.3's `academic_year` predicate is not implemented (P2)

- SPEC §5.21.3 lists six pre-retrieval predicates. Five are enforced. `academic_year = requested_year`
  is not: `ChunkFilters.academic_year` exists and `_apply_filters` honours it, but
  `role_access.role_access_filter` never sets it and no caller does.
- **Measured:** a chunk seeded with `academic_year = "2019-2020"` was retrieved by every audience
  including anonymous, in the same run where draft, future-dated, expired and other-branch chunks
  were all correctly excluded.
- **Entirely masked today** — all 23 documents and 159 chunks are `2026-2027` — and unmasks the first
  time a second year is ingested, which is inherent to a yearly-refreshed handbook corpus. Same shape
  as AUD-L-12: correct code, never wired, hidden by uniform data.

### AUD-C-10 — chat-web leaves a permanent "Thinking…" bubble on any API error (P2)

- `sendMessage` appends `{query, response: null}`, then awaits `postMessage`. On any throw, `run`'s
  catch sets the error banner and **the transcript entry keeps `response: null` forever**;
  `ChatScreen` renders `!turn.response` as a `Thinking…` bubble with no timeout and no retry. A 500
  (AUD-C-07), a 409, a 401 or a dropped connection all land here.
- §2.6 criterion 3 requires "zero blank/stuck states" on every launch journey. This is one, and it is
  reachable from the most ordinary failure there is.
- **Same class as the S22.5 blank-turn bug**, which is the seeded Phase 0B exemplar: a render gated
  on a field that is legitimately absent. The full response-shape × render enumeration this session
  ran is below; this and AUD-C-04 are the two shapes that render wrongly.

### AUD-C-11 — The no-source refusal is returned *with* citations attached (P2)

- **Observed live:** turn 1 of the staging session returned
  `answer: "I don't have an approved source for that yet…"` together with
  `citations: ["public-organization-overview"]` and `confidence: 0.4`.
- **Cause:** `qa.answer_question`'s low-confidence branch is `_no_answer(NO_SOURCE_MESSAGE, verified)`
  — it passes the verified citations *into* the no-answer result. chat-web then renders the refusal
  text with a citation chip under it. A reader is being shown a source next to a sentence saying no
  source exists. (The conflict branch does this deliberately and correctly; the low-confidence branch
  appears to have inherited it.)

### AUD-C-12 — §5.21.8's "retrieval score below threshold" has no implementation (P3)

- SPEC §5.21.8 lists "Retrieval score is below threshold" as a do-not-answer trigger. The only
  score-based filter in the pipeline is `retrieve()`'s `rerank_score > 0.0` (D-052), and the only
  threshold is `groundedness_confidence_threshold` (0.4), which gates the *model's self-reported
  confidence about its own answer*, not retrieval. A chunk the reranker scored 0.01 is passed to
  synthesis exactly like one scored 0.99. No minimum-relevance setting exists.

### AUD-C-13 — The citation verbatim check accepts a one-character quote (P3)

- `qa._verify_citations` accepts a citation when `quote.lower() in chunk.chunk_text.lower()` and the
  quote is non-empty. There is no minimum length and no requirement that the quote overlap the
  answer, so `"a"` verifies against nearly any chunk. Only the quote's **hash** is stored
  (`supporting_quote_hash`, per SPEC's Citation schema), so nothing downstream can re-examine what
  was actually quoted. The defense is real but its floor is one character.

### AUD-C-14 — `RespondResponse` omits `scope` and `intent`, so the post-resume SSE snapshot nulls them (P3)

- `MessageResponse` and `SessionSnapshotEvent` both carry `scope`/`intent`; `RespondResponse` does
  not. `_publish_snapshot` validates the snapshot from `response.model_dump()`, so every broadcast
  after a `/respond` sets both to `null` for any connected client. Exactly the class D-058 was written
  to prevent ("any field added to `MessageResponse` must also be added to `_initial_snapshot`"), in
  the one direction that decision did not name. chat-web does not currently render either field, so
  the impact today is nil — logged because the next field added here may not be inert.

### AUD-C-15 — An unknown-tool call raises without writing an audit row (P3)

- `McpToolRegistry.call` raises `McpToolError(f"unknown tool {tool_name!r}")` **before** `start` is
  set and before any `_audit` call. Every other failure path (permission, validation, timeout,
  execution) writes an `mcp_tool_calls` row with `success=False`. A call to an unregistered tool —
  the shape a prompt-injection or a wiring bug would produce — leaves no trace at all.

### AUD-C-16 — Stored embeddings are provider-specific, with no provenance and no re-embed path (P3)

- `rag_chunks.embedding` records no model or provider. Switching `BEDROCK_PROVIDER` between `mock`
  and `bedrock` silently invalidates every stored vector: a real Titan query vector compared against
  `MockBedrockProvider`'s hash-based vectors is noise, and nothing detects it — keyword search keeps
  working, so the system degrades to lexical-only retrieval while appearing healthy.
- This session hit it directly: the real-Bedrock eval had to re-embed all 144 approved chunks inside
  its rolled-back transaction to measure anything meaningful. There is no `make` target for that and
  no way to tell from the database which provider produced what.
- **Not yet checked against staging** (RDS is in private subnets and this session's live pass was
  black-box over the API): whether staging's corpus was ingested with real Titan vectors or mock ones
  is unknown, and if it were mock, staging's semantic half is currently noise. Recorded as the first
  thing S38's live pass should settle.

### Areas audited with no finding — S37

**Pre-retrieval filtering holds for every audience, on real content.** Five audiences (anonymous/
public, student, parent, tutor, branch_manager) × eight queries drawn from the real documents' own
wording, run twice: once against the corpus as it stands, and once inside a rolled-back transaction
with every `effective_from` pulled back a day so the 19 date-gated real documents become live. **No
role retrieved a chunk outside `{public, its own role}` in either pass** — anonymous saw only public
in all 51 hits; student, parent, tutor and branch_manager each saw only public plus their own tier.
This is the check that most needed real content rather than synthetic seeds, and it passed cleanly.

**Four of §5.21.3's other five predicates verified individually**, with purpose-built chunks that
differ in exactly one attribute: a `draft` chunk, a chunk with `effective_from` 30 days in the
future, one with `effective_to` a day in the past, and one tagged to `branch-B`. None was ever
returned. A `branch-A` chunk *was* returned to a branch-A student and correctly withheld from a
branchless one; an org-wide (`branch_external_id IS NULL`) chunk reached both. Only `academic_year`
failed (AUD-C-09).

**The access-hint probe leaks nothing it shouldn't.** `count_matching_by_audience` clears only the
audience allowlist; `status = approved` and the date window still apply, so the probe cannot reveal
that draft or expired content exists, and it returns counts grouped by audience — never ids, never
text. `build_access_hint`'s priority order is backend-authored and never model-proposed.

**Prompt-injection containment held under real Bedrock.** Five of six adversarial cases passed
(role-claim in the query text, system-override instruction, citation bait, document enumeration, PII
bait): none leaked seeded gated text and none cited outside the public allowlist. The sixth
(`adversarial-false-premise`) failed only its forbidden-string check by repeating the fabricated
time back in its answer — worth a closer read next session, but no content-boundary was crossed.

**Interrupt-approval and tool-call audit rows are written correctly.** Approving an email escalation
and completing a locator turn produced `interrupt_approvals` rows with the right `interrupt_type`,
`decision` and `source_app = "chat"`, and `mcp_tool_calls` rows for `maps.geocode` /
`maps.compute_routes` / `gmail.send_email` with `success` and `duration_ms`. `ToolCallAuditEvent`
carries no PII by construction — tool name, external id, success, exception *type*. The one gap is
AUD-C-15.

**A thread with a pending interrupt correctly rejects new messages.** `_reject_if_paused` returned
409 for both an anonymous caller and a second authenticated caller, so D-021's "a fresh `ainvoke`
silently discards a paused task" trap is genuinely closed. `/respond` also correctly 409s on a
mismatched `interrupt_type` and on "no interrupt is pending".

**Response-shape × render enumeration (the S22.5 class).** All fourteen shapes the API can emit were
enumerated against `ChatScreen`/`App`: grounded answer, no-source refusal, conflict message,
out-of-scope refusal, clarification, access hint, event listing, `.ics` result, rate-limited
escalation, email sent/declined/failed, location declined/missing, and each of the three pending
interrupts. **Twelve render correctly.** The two that do not are AUD-C-04 (a paused turn renders the
previous turn's answer) and AUD-C-10 (an errored turn renders `Thinking…` forever). One latent
gap: `App.tsx` renders a modal only for the three known `interrupt_type` values, and
`busy = pending !== null` — a fourth interrupt type added later would disable the composer with no
modal to resolve it, deadlocking the session. Not reachable today.

**Anonymous access works end to end on live staging.** `POST /chat/sessions` and `/messages` with no
token returned in-scope answers with real citations from the deployed corpus, confirming both that
§5.19.1's anonymous tier is genuinely open and that staging's RAG content is ingested and effective
— which S36's experience with empty learning tables made worth checking rather than assuming.

_(Not covered this session: the LLM-judge dimensions of answer quality — `packages/evals/llm_judge.py`
exists and is unused by this suite; multi-turn conversational context, which `QAState` does not yet
implement (`standalone_query` is always identical to `query`, a known carry-over); and browser-driven
runs, since no browser automation exists in this environment — the frontend findings above are from
code enumeration plus API-level evidence, not from a rendered page.)_

---

## S38 — AUD-X (cross-cutting integrity)

Scope per §2.3's AUD-X paragraph, risk-ordered and deliberately bounded at session start:
(0) settle AUD-C-16 against staging, (1) authn/authz boundaries across every route,
(2) idempotency of every retryable write, (3) the PII floor re-verified against **live staging**.

Crash-consistency (mid-node / mid-interrupt / mid-finalize) and cost ceilings under concurrency
were deferred when the session first ran and are **now covered** — AUD-X-07 and AUD-X-08, both P1,
both reproduced with sequential/consistent control arms. AUD-X-06 was also fixed, because it left
the test baseline intermittently red and so blocked §2.6 criterion 4 regardless of the audit.

### AUD-C-16 (settled) — Staging's corpus is entirely mock hash vectors; its semantic channel has never worked (P3 → **P1**)

S37 left this as the first question for S38's live pass: real Titan vectors or `MockBedrockProvider`
hash vectors? **Mock, all of them.**

- **Method — an exact, free discriminator.** `MockBedrockProvider._deterministic_vector` is a pure
  function of the embedded text, and `_persist_chunks` embeds exactly `draft.chunk_text`, which is
  stored verbatim. So recomputing the mock vector from the stored text and taking the cosine against
  the stored vector answers the question with no Bedrock call at all.
- **Both controls were run before trusting it.** Positive: the local dev corpus scores
  **159/159 at cosine 1.000000**. Negative: a real Titan v2 vector for the same text scores
  **−0.002925** against its mock counterpart — so "not-mock" would have been distinguishable had it
  been true. A discriminator that can only return one answer is not a measurement.
- **Result on staging** (one-off Fargate `ops-task` in the private subnets, the same mechanism the
  deploy uses for Alembic; read-only `SELECT`s; ids and cosines printed, never chunk text):

  ```
  PROBE totals chunks=159 embedded=159 docs=23
  PROBE rag_chunks verdict mock_like=159/159
  PROBE youtube_videos verdict mock_like=0/0   (no rows)
  ```

- **The runtime half, which is what makes it live.** Both deployed services run
  `BEDROCK_PROVIDER=bedrock` with `amazon.titan-embed-text-v2:0`. Every semantic search on staging
  therefore compares a real Titan query vector against hash noise.
- **The effect is measured, not inferred.** Same real Titan query vector, same corpus text, one
  variable — what the *chunk* vectors are (A: the stored mock vectors, B: the same 89 public
  approved chunks embedded with real Titan in memory, never written):

  | query | A — stored mock, top-1 | B — real Titan, top-1 |
  |---|---|---|
  | "What kind of help do you offer families whose kids are struggling in math class?" | `public-student-participation-guide` **+0.065** | `public-organization-overview` **+0.409** |
  | "Do students pay anything to join the tutoring program?" | `public-volunteer-guide` +0.074 | `public-volunteer-guide` +0.254 |
  | "How long has this organization been running, and who does it serve?" | `public-our-team` +0.065 | `public-organization-overview` **+0.190** |

  Arm A's similarities are indistinguishable from chance: random unit vectors in 1024 dimensions sit
  at |cos| ≈ 1/√1024 ≈ 0.031, and the best of 89 draws landing at 0.065–0.074 is exactly that
  distribution's tail. Arm A is not a weak ranking, it is **no ranking**.
- **User-visible, on the deployed system, today.** The seven `paraphrase` fixture cases — written
  specifically to reuse no rare word from the target chunk, so only the semantic channel can find
  them — run anonymously against live staging cite the expected document **1/7**. Of the three that
  actually reached retrieval as `document_qa`, two returned *"I don't have an approved source for
  that yet"* about documents that are approved, effective and ingested. (Two of the other four were
  refused by AUD-C-02's scope gap — independently reconfirmed here — and two routed to
  `branch_locator`, which is correct behavior and returned proper `location_consent` interrupts,
  not blank turns.)
- **Severity: P1, upgraded from P3.** §2.4's P1 is "a launch journey broken". Asking a question in
  your own words rather than the document's is the ordinary case, not an edge case, and on staging
  that path is answered by keyword overlap alone. It also invalidates any retrieval-quality claim
  made *about staging*, including S37's live observations, and §2.6 criterion 3 cannot be evidenced
  on a corpus whose retrieval half is inert. **Counter-argument, recorded:** keyword search still
  answers lexically-close questions (S37 saw real citations live), there are no real users, and the
  fix is mechanical. What moves it off P3 is not the misconfiguration — it is that nothing anywhere
  detects it.
- **Note on framing, corrected against a first reading.** This is not a mock-vs-real *mismatch*
  problem. A mock-embedded corpus has no semantic signal even when queried by the mock, because the
  vectors are hashes of text rather than representations of it. So staging has not "regressed" —
  its semantic channel has never worked, and neither has local dev's. What the real-provider runtime
  changes is only that nothing will ever coincidentally line up again.
- **Fix shape (Phase 0B):** a provenance column on `rag_chunks` (model id + provider) written at
  ingestion, a `make knowledge-reembed` target, a startup or readiness assertion that the configured
  embedding model matches what the corpus was built with, and a re-ingest of staging under
  `BEDROCK_PROVIDER=bedrock`. The assertion is the part that matters — the other three are one-time.

### AUD-X-01 — `POST /sessions/{id}/student` never checks who owns the session; any student can seize another's in-progress exam and lock them out (P1)

- **Severity:** P1. §2.4 puts authorization bypass under P0; this is held at P1 on the same
  reasoning AUD-C-01 was, and the reasoning is weaker here in one respect and stronger in another:
  the attacker still needs a `uuid4` session id, but unlike the chat case the victim **loses
  access to their own data permanently**, so this is a destructive write, not only a read.
- **Reproduction (local, real graph, real Postgres):**

  | step | result |
  |---|---|
  | `student-ext-1` builds a pre-exam session and answers an item | 200, attempt persisted |
  | `student-ext-4` (different branch, no relationship) `POST /sessions/{A's id}/student {"student_id": "student-ext-4"}` | **200** |
  | `student-ext-1` re-reads their own exam overview | **403** — *"Students may only access their own records"* |
  | `student-ext-4` reads the overview | 409 — the claim reset `phase` to `student_selected`, so there is no exam to read |

  A's `assessment_sessions` row stays `in_progress` with `student_external_id = student-ext-1`
  forever: the data is not misattributed, it is **orphaned**, and A has no route back to it.
- **Confirmed on live staging** (`d35dfnjzmgrm01.cloudfront.net`, deployed config, two
  secret-gated `/dev/token` student tokens):

  ```
  A creates + owns session:                200 phase=student_selected
  A selects topic:                         200 phase=blocked        (attendance gate, fail-closed)
  B claims A's session:                    200 phase=student_selected
  A reads own overview AFTER B's claim:    403 "Students may only access their own records"
  A tries to answer in own session AFTER:  403 "Students may only access their own records"
  ```

  The lockout reproduces exactly. The *orphaned in-progress exam* half is local-only evidence:
  staging's synthetic students have no attendance rows, so A's session stopped at `phase=blocked`
  and never built an exam. The authorization defect is identical either way; only the size of what
  the owner loses differs.
- **Root cause, and it is the same shape as AUD-C-01 in the other app.** Seventeen learning
  routes authorize by calling `resolve_target_student(claims, state["student_external_id"], …)`
  — the checkpoint's value, never the client's, which S36 recorded as a negative result and which
  is correct. `select_student` is the eighteenth route, it is **not** one of them, and it is the
  route that *writes* `student_external_id`. It validates the *requested* student against the
  caller's claims (`graph/nodes.py: resolve_student`) and never reads the existing value. **The
  one route that writes the field every other route reads is the one route that does not check
  it** — stated almost verbatim in AUD-C-01 about `post_message`. Two independent apps, same
  structure, found in consecutive audits.
- **The owner can do it to themselves.** The same call replayed by the legitimate owner also
  resets `phase` and 409s their own overview — see AUD-X-03; `busy={false}` is hardcoded at that
  call site too.
- **Fix shape:** in `resolve_student`, refuse to change `student_external_id` once it is set to a
  different value (a rebind is only legitimate for a parent switching children, which routes
  through `await_child_selection` and already carries its own check).

### AUD-X-02 — SPEC §5.1.2's `parental_consent_verified` check does not exist; three consent/account claims are carried in every token and read by nothing (P1)

- **What SPEC says**, §5.1.2, verbatim: *"`learning.intellichoice.org` must not use a
  student-facing notice as a substitute for parental consent for users under 13. It should verify
  `parental_consent_verified=true` from the existing system"*. `account_status` and
  `consent_status` are in the same required claim list.
- **What exists.** `TokenClaims` carries all three. `grep` across both apps finds **zero**
  readers outside the model definition and the dev issuer. Both `get_current_claims` functions
  check signature, expiry and audience, and stop there.
- **Measured, not inferred.** A token with `account_status="suspended"`,
  `consent_status="revoked"`, `parental_consent_verified=False`, `student_age_band="under_13"` —
  same signature, same audience — was run against all 18 learning routes. It behaved **identically
  to a fully-consented active token on every one**: created sessions, selected topics, read the
  dashboard, generated a report, finalized an exam.
- **Why no test catches it.** Three test files construct these claims; all three pass the
  permissive value. No test asserts the restrictive path, because there is no restrictive path.
- **The seam this actually lives in, stated plainly.** S45 owns consent and the roadmap's design
  is *"no-consent → no-token"* — enforcement at issuance rather than at the API. That is a
  defensible placement, but nothing records the decision to move the check out of the consuming
  app that SPEC assigns it to, and the failure mode is specific: if S44 builds the issuer and S45
  builds the ledger, and neither adds a consuming-side assertion, §5.1.2 stays unmet and **no test
  anywhere will notice**, because the claim is already present and already ignored. A fixture that
  always sets the safe value is not coverage.
- **Severity: P1, not P0.** The only issuer today is `FakeTokenIssuer`, which hardcodes the
  permissive defaults, and `/dev/token` is secret-gated on staging — so no token with these values
  can currently be minted by anyone but this audit. It is a child-safety requirement with no
  implementation and no test, on a platform whose primary users are minors, and it must not be
  allowed to fall between S44 and S45.

### AUD-X-03 — `POST /sessions/{id}/topics` is a non-idempotent exam-creating write; a replay silently abandons the first exam (P2)

- **Measured by row counts, not response codes:** replaying `/topics` on a session that already
  built a pre-exam returns **200** and adds **+1 `assessment_sessions`, +10 `assessment_items`**,
  with a **different variant set** (`same_variants=False`). The first exam is left `in_progress`
  and unreachable; any attempts already recorded against it are stranded.
- **The only guard is client-side and single-instance.** `useLearningSession.run()` holds a
  `busyRef` that swallows a second in-flight call — per hook instance. Two tabs, a refresh
  mid-request, a retrying proxy or any non-browser client bypasses it, and the server has no guard
  at all. `TopicSelectScreen` is passed `busy={false}` hardcoded at its `App.tsx` call site, so the
  button is not even visually disabled — **the same hardcoded-`busy` pattern AUD-L-10 found at
  ExamScreen's six call sites**.
- Contributes to the standing `question_variants` accumulation carry-over: every abandoned exam
  is a fresh variant draw.

### AUD-X-04 — `POST /students/{id}/report` remains non-idempotent: one click, one paid call, one row (P3)

- Confirmed by row count: two identical calls → **+1 `student_reports` row each**, both 200. There
  is no idempotency key on this route, as AUD-L-02 noted in passing.
- **P3, not higher, and only because AUD-L-02's fix landed.** Before S36 this was the unbounded
  spend path; the `DAILY_REPORT_COST_CEILING_CENTS = 50.0` window now caps the damage at a day's
  ceiling, so what remains is duplicated work and duplicated rows rather than uncontrolled cost.

### AUD-X-05 — AUD-L-07 extends to *writes*: a tutor token can answer and finalize another student's exam (P1, extends AUD-L-07)

- AUD-L-07 recorded that `resolve_target_student` returns without a check for tutor and
  branch_manager, and described the impact as reading any student's data and generating reports.
  The route × caller matrix shows the same fall-through covers **every mutating session route**:

  | route | tutor on another student's session |
  |---|---|
  | `POST /sessions/{}/answers` | **ALLOW 200** — an attempt is graded and persisted |
  | `POST /sessions/{}/topics` | ALLOW 200 |
  | `POST /sessions/{}/resume` | ALLOW 200 |
  | `POST /sessions/{}/exam/finalize` | **ALLOW 200** — the exam is scored and closed |
  | `POST /sessions/{}/student` | ALLOW 200 — and `resolve_student` binds the session to *any* id (`target = requested_student_id or claims.sub`, unvalidated for this role) |
  | `GET /sessions/{}/stream` | stream opens |

- **Why this matters beyond the existing finding:** answers submitted by someone other than the
  student are indistinguishable from the student's own in `assessment_attempts`, and they feed
  scoring, mastery and learning-gain. A read-scope gap discloses data; a write-scope gap
  *fabricates* it. The one-line fix AUD-L-07 proposes closes both, which is the argument for
  keeping it a single finding rather than splitting it.

### AUD-X-07 — The checkpoint commits before the domain transaction, so a failure between them leaves the graph ahead of the database and the session permanently stuck (P1)

- **Severity: P1** — §2.4's "a launch journey broken". Both reproduced instances leave the
  student in a state with **no route forward**: every subsequent request 500s, and the exam they
  completed is orphaned. **Counter-argument for P0 ("data corruption"), recorded:** nothing is
  silently *misattributed* — the exam row stays truthfully `in_progress` and the checkpoint is
  merely ahead — and recovery needs a failure event rather than an attacker. What keeps it at P1
  rather than P2 is that the end state is unrecoverable through the API and needs operator DB
  surgery. Held at P1 on the same reasoning as AUD-C-01 and AUD-X-01.

- **The structure, which is the finding.** Two independent stores commit at two different times,
  in a fixed order, with no coordination:

  | # | when | what commits | connection |
  |---|---|---|---|
  | 1 | end of each superstep, inside `graph.ainvoke` | the **checkpoint** | `AsyncPostgresSaver`'s own psycopg pool |
  | 2 | FastAPI dependency teardown, **after the route returns** | the **domain rows** | the SQLAlchemy engine |

  `get_db_session` yields the session and only then calls `await session.commit()`
  ([learning-api dependencies.py:53-55](apps/learning-api/src/learning_api/dependencies.py#L53-L55));
  `main.py` documents that the saver "opens its own psycopg connections, separate from the
  SQLAlchemy engine". So step 1 always precedes step 2, and **anything that fails in between keeps
  the checkpoint and discards the rows** — FastAPI throws the exception in at the `yield`, so
  `session.commit()` is skipped and the session closes with a rollback. `apps/chat-api`'s
  dependency is **identical** ([dependencies.py:86-88](apps/chat-api/src/chat_api/dependencies.py#L86-L88)),
  so the seam exists in both apps.

- **Reproduced twice, at the two seams §2.3 names.** The induced failure is a raise at
  `_publish_snapshot` ([sessions.py:601](apps/learning-api/src/learning_api/routers/sessions.py#L601)) —
  the real statement that sits in that window — against the real graph and real Postgres, with row
  counts read on a second connection.

  **(a) mid-finalize.** A 10-item pre-exam, all answered, then finalize:

  | | checkpoint | database |
  |---|---|---|
  | after the crash | `phase=study`, `study_session_id=f530cf42…` | exam still `in_progress`; **0** `study_sessions` rows with that id; **0** `learning_gain` |

  The student's completed exam is never scored, and the checkpoint's `study_session_id` is a
  dangling reference. **What a reloading client then does, in order:** `POST /resume` → **200**,
  `phase=study`, and it **serves a study question**; the student answers it → **500**; every retry
  → **500**; `GET /exam/overview` → **409** *"session is not in an exam phase (phase=study)"*, so
  there is no way back to the exam either. The session is a dead end that still renders a question.
  (Probe 2 appeared to self-heal only because it called finalize a *second* time explicitly — a
  client that reads `phase=study` never would.)

  **(b) mid-interrupt.** `submit_answer → intervention_choice` is the graph's one multi-superstep
  turn. A wrong study answer writes a `study_attempts` row, then pauses on `interrupt()`:

  | | checkpoint | database |
  |---|---|---|
  | after the crash | `phase=study`, pending task `intervention_choice`, interrupt `intervention_choice` | **0** `study_attempts` rows |

  `POST /respond {"choice":"hint"}` → **500**, `hint_events` **0**, and the pending interrupt
  **never clears** (still `intervention_choice` afterwards). The student is paused on an interrupt
  that cannot be resolved and cannot answer anything else.

- **A negative result that sharpens it: the ordinary answer path does *not* diverge.** A pre-exam
  answer crashed at the same point left `assessment_attempts` at 0, the checkpoint at
  `phase=pre_exam`, and the overview showing every item `unseen` — consistent, because that route's
  entire effect lives in domain tables with nothing durable in the checkpoint to get ahead. A
  same-`Idempotency-Key` replay then produced exactly 1 attempt. **The seam only bites where the
  checkpoint carries a domain-row id**, which is what makes the two reproduced cases the dangerous
  ones rather than a general property of every route.

- **Why the 500s are unhandled: the checkpoint holds row ids and the code `assert`s the rows
  exist.** Both dead ends are bare asserts on a lookup the checkpoint promised —
  [study.py:45](packages/db/src/intellichoice_db/repositories/study.py#L45) `assert attempt is not
  None` (via `state.last_study_attempt_id`) and
  [sessions.py:874](apps/learning-api/src/learning_api/routers/sessions.py#L874) `assert session_row
  is not None`. The pattern is **84 instances** of `assert … is not None` across `learning-api/src`
  and the `packages/db` repositories, **35 in `graph/nodes.py` alone**. They are load-bearing
  invariant checks on cross-store consistency, expressed as a statement Python removes entirely
  under `-O`.

- **Realistic triggers, since the reproduction used injection.** The one that needs no bug at all
  is **a task stop between the two commits** — ECS drains tasks on **every deploy**, and S35 made
  deploys routine, so this window is entered on a schedule. Others: any unhandled exception after
  `ainvoke` in a route that already wrote rows (the MySQL-backed `_pending_interrupt_response` sits
  exactly there for `child_selection` and `email_approval`), a lost database connection at commit
  time, and a worker OOM. **Two candidates were checked and ruled out**, and both are worth
  recording so nobody re-derives them: `LearningGainResponse` makes `normalized_gain` and
  `normalized_gain_status` optional, so AUD-L-08's NULL status does **not** raise here; and
  `SessionSnapshotEvent` is a deliberately all-optional superset, so `_publish_snapshot`'s own
  `model_validate` is not itself a realistic raiser. `_publish_snapshot` is the *location* of the
  window, not the cause.

- **The chat app inherits the same seam with an audit-trail consequence.** `mcp_tool_calls` is
  written on the domain session while the tool result lands in the checkpoint, so the same window
  drops the SPEC §5.1.4 approval/audit row while keeping the effect — the same direction as
  AUD-C-15, reached by a different route. Not separately reproduced this session.

- **Fix shape (Phase 0B), in order of value.** (1) Commit the domain session *before* the
  checkpoint, or bring both under one transaction — LangGraph's saver accepts an external
  connection, which is the only real fix for the ordering. (2) Failing that, make the divergence
  *recoverable* rather than fatal: replace the asserts on checkpointed ids with a reconciliation
  path (missing row → rebuild or roll the phase back) so a stuck session self-heals on the next
  request. (3) A consistency check at session read time comparing `phase` against the rows it
  implies. (2) is the cheap one and would have converted both reproduced dead ends into ordinary
  recoverable turns.

### AUD-X-08 — Every per-day cost ceiling is a read-then-act race: 10 concurrent reports spent 8× the ceiling (P1, weakens AUD-L-02's P0 fix)

- **Severity: P1, with the P0 reading recorded.** §2.4 puts "uncontrolled spend" under P0, and
  there is a real argument for it: the daily ceiling is *the* control bounding this route's spend,
  and the multiplier is the caller's concurrency, which the caller chooses. It is held at P1 on the
  same basis as the other findings here — `/dev/token` is secret-gated on staging, there are no
  real users, and each individual call is still token-capped by the gateway, so what a caller gets
  is a multiple of one report's cost rather than unbounded spend. **This is the top money item for
  Phase 0B**, and unlike AUD-L-02 it was not fixed in-session (§2.4 reserves that for P0s).
- **The shape.** `generate_student_report` reads the spend, then spends:

  ```python
  spend_today = await repo.get_spend_cents_since(student_external_id, now - 24h)   # report.py:206
  if spend_today >= DAILY_REPORT_COST_CEILING_CENTS: ...return the facts-only fallback
  result = await gateway.generate_structured(...)                                  # report.py:242
  ```

  There are **two** windows, not one. Concurrent callers all read the same pre-call value; and
  because the row carrying `cost_cents` is committed by the **dependency teardown after the
  response** (AUD-X-07's ordering), even a *staggered* caller that starts after an earlier call has
  finished its Bedrock request still reads a stale spend.
- **Measured, with the sequential control that makes it meaningful.** Local, real Postgres, real
  graph, `MockBedrockProvider` (the gateway's cost accounting is provider-independent, so the
  arithmetic is real even though the calls are free). The ceiling was monkeypatched down to exactly
  one report's measured cost so that 10 requests can reach it — the race is scale-invariant:

  | arm | result |
  |---|---|
  | one report, to calibrate | `generated=True`, **0.0819¢** |
  | **sequential control** — ceiling = 0.0819¢, second report | `generated=False`, cost **0.0** — *the ceiling works correctly when nothing races* |
  | **10 concurrent**, ceiling = 0.0819¢, zero prior spend | **all 200**, **8 of 10 generated**, total **0.6552¢** = **8.0× the ceiling** |

  The control arm is the point: this is not a broken check, it is a correct check with no
  serialization around it. (8 rather than 10 because two requests happened to read a spend that had
  already committed — the exact multiple is a timing artifact; the direction is not.)
- **A single authenticated caller can drive it**, because AUD-X-04 records that this route has no
  idempotency key: 10 identical concurrent POSTs are 10 accepted paid calls. Via AUD-X-05's
  tutor/branch_manager write fall-through, the same loop can be aimed at any student.
- **Two more ceilings have the identical shape.** Neither was separately measured; both are named
  so the gap is legible rather than inferred:
  - `nodes.py:1126` — the tutor-chat per-day ceiling, read from `tutor_chat_messages` and committed
    at teardown. Same read-then-act, same commit lag.
  - The per-session gateway budget (`_session_budget_cents`, default 50¢). The gateway is
    **stateless with respect to spend** — `session_spend_cents` is a caller-supplied argument
    ([gateway.py:136](packages/adapters/src/intellichoice_adapters/bedrock/gateway.py#L136)), read
    from `state.bedrock_spend_cents` at ~20 call sites — so concurrent turns on one thread each
    read the same checkpointed total and each receive a full budget. Related and already known:
    `run_chat_turn`'s docstring records that chat's own calls are **never persisted back** into
    `bedrock_spend_cents` (D-072), so that ceiling already under-counts by design.
- **Fix shape (Phase 0B):** make the reservation atomic rather than advisory — a single
  `INSERT … SELECT` guarded by the ceiling, or `SELECT … FOR UPDATE` on a per-student spend row, so
  the check and the debit happen in one statement. An idempotency key on the route (AUD-X-04) is a
  partial mitigation for the duplicate-click case but does nothing for distinct concurrent requests.
  Whatever lands must be re-verified **with a concurrent arm**, since the sequential test passes
  today and would keep passing.

### Areas audited with no finding — S38

**The token layer holds on every axis tested.** Every route in both apps (18 learning + 6 chat)
was called with thirteen caller shapes. Anonymous, expired, bad-signature, `alg: none`, and
**wrong-audience tokens in all three directions** (chat→learning, go→learning, learning→chat)
returned **401 on every authenticated route, without exception**. `JwtTokenVerifier` pins
`algorithms=["HS256"]`, so the unsigned-token attack is rejected at the library boundary rather
than by a claim check that could be reordered away.

**Cross-caller isolation holds wherever `resolve_target_student` is actually called.** A different
student and an unlinked parent got **403 on every one of the 18 learning routes**. The failures
above are all *missing calls* to that helper (AUD-X-01) or *fall-through inside* it (AUD-X-05) —
the helper itself is correct for the roles it checks.

**The interrupt-resume path is stricter than the rest of the app, and is the pattern to copy.**
`/respond` against a genuinely pending `child_selection` interrupt denied **every** non-owner —
another parent, a tutor, and even the child the interrupt is about — with 403. It is stricter
because `await_child_selection` compares `ctx.claims.sub` against the **checkpointed**
`parent_external_id` rather than going through the role-based helper. That is exactly the check
AUD-X-01 and AUD-X-05 are missing, already written and working, one file away.

**SSE `?token=` is not a weak spot.** Ownership and audience are both enforced on the query-string
path (other student 403, chat-audience 401, `alg:none` 401, missing token 422), and a tutor's
stream opening is AUD-X-05, not a stream-specific gap. **The token does not reach application
logs**: the access-log middleware records the *route template*
(`/learning/sessions/{learning_session_id}/stream`), so neither the JWT nor the session id is
written — verified by making a real `?token=` request and grepping the log.

**Idempotency holds everywhere it was implemented.** Same-`Idempotency-Key` answer replays produce
**zero** new `assessment_attempts`; double finalize produces zero new completions; duplicate
problem reports dedupe per reporter. AUD-L-10's defect is specific and remains exactly as it was
recorded — a *fresh* key on an already-answered item adds an attempt (+1, reconfirmed here from
S38's side). Two identical chat questions produce two full turns, which is correct behavior, not a
missing dedupe.

**§2.6 criterion 9, logs half: clean, with the positive control that makes that meaningful.**
Fifteen patterns — six exact fixture names, both manager emails, both street addresses, the four
branch coordinates, and shape patterns for email/JWT/`Bearer `/`token=`/PII field names/echoed
query and answer text — over **30 days of both application log groups**: **zero hits**, while the
two positive controls in the same batch returned **32,744** and **2**. *The first version of this
scan reported zero for everything including strings that are demonstrably present*, because
`filter-log-events --max-items` paginates and only the first page's count was read. That is
D-101 §5's failure mode reproduced exactly one session later, caught only because a positive
control was run. Logs Insights `stats count()` over the whole window is the shape that works.

**§2.6 criterion 9, stored-payload half: staging's checkpoints are clean, scanned in full.** All
**1,552 `checkpoint_writes` and 181 `checkpoint_blobs`** rows on staging — the entire tables, not a
sample — deserialized with the checkpointer's own serde and walked as objects: **zero coordinates,
zero names, zero emails, zero JWTs**. The one `street-address` hit is public branch-directory text
inside a RAG `answer`, which is the product working. The same scanner run against local dev as a
positive control found **24 keyed coordinate values across 12 `__resume__` rows**, independently
reproducing AUD-C-03 by a different method than S37 used.

**Metrics carry no identifiers by construction.** Every Prometheus metric uses bounded enum
labels (`result`, `phase`, `support_type`) — no ids, no free text, no unbounded cardinality.

**`/metrics` and `/healthz` are not publicly reachable.** The staging CloudFront distribution
forwards only `/chat/*`, `/dev/token` and `/me` to the ALB; everything else falls through to the
SPA origin. A `curl` of `/metrics` returns **200 with `text/html`** — the SPA's `index.html`, not
the metrics endpoint. Worth stating because the status code alone reads as an exposed endpoint.

**AUD-L-01 reconfirmed on the deployed chat app** (it was recorded against learning): missing and
wrong `X-Staging-Token-Secret` both 404 correctly, while `GET /dev/token` → **405** and
`POST` with `{}` → **422** each disclose that the route exists.

**Crash-consistency and cost ceilings are covered** — see AUD-X-07 and AUD-X-08. Both carry a
control arm rather than only a failure arm, and both controls passed: the ordinary pre-exam answer
path stays *consistent* across the same induced crash (checkpoint and rows both roll back, and a
same-key replay produces exactly one attempt), and the report ceiling *correctly* degrades to the
facts-only template when requests do not overlap. The defects are specific to where the checkpoint
carries a domain-row id, and to concurrency.

_(Limits that remain, stated because they bound what criterion 9 can currently claim: **traces cannot be audited at all — `OTEL_ENABLED` is
`false` on both staging services**, so the "traces" half of criterion 9 is unevidenced rather than
passing; and **AUD-C-03's coordinates are absent from staging only because no locator turn has
ever completed there**, not because anything prevents them — the 22 `__resume__` rows are other
interrupt types. The full route × caller matrix ran against the real local APIs rather than
staging — driving 13 caller shapes × 18 routes live would have created far more residue than the
finding warrants — but **AUD-X-01, the most serious of them, was reproduced end to end on live
staging** and is recorded there.)_

### AUD-X-06 — A hint test asserted a stricter rule than the product's own leak check (P3, fixed in S38)

- **Found by the routine baseline re-run**, on a working tree containing **only documentation
  changes**: `test_hint_ladder_escalates_through_three_levels_without_leaking_answer` failed —
  512 passed, 1 failed.
- **Measured before diagnosing** (D-100's own lesson), twice, with random ordering disabled:
  **7/30** at discovery and **8/40** on re-measurement — **15/70 (21%)** combined. The cause is
  the handler's unseeded `random.Random()` per request, not test order.
- **The failing assertion, and every failure had the same shape** — the answer digit equals the
  hint level, so answer `"1"` fails on round 1, `"2"` on round 2, `"3"` on round 3:

  ```
  AssertionError: assert '3' not in 'hint l3, addressing sign_error: subtract that number ...'
  ```

- **Root cause.** The test asserted `correct_answer_text.lower() not in
  intervention["hint_text"].lower()` — a **plain substring check**. The product's rule,
  `authored_validation.answer_text_leaked`, is a boundary-aware regex that deliberately *does not*
  fire for a digit adjacent to another alphanumeric: it would not flag `hint l3` for the answer
  `"3"`, because the `3` is preceded by `l`. **The test asserted something stricter than the
  product guarantees**, and the mock's own boilerplate is what tripped it.
- **The rate is a property of the bank's answer distribution, not its size.** Of the bank's
  **51,613 variants, 9,215 (17.9%)** have a correct answer of `"1"`, `"2"` or `"3"` — which is the
  measured 15/70 (21%). The earlier draft of this finding guessed "the question bank has grown";
  that hypothesis is **withdrawn**, and it was never needed, because —
- **AUD-L-17 did not regress. This finding originally conflated two different tests.** AUD-L-17
  diagnosed and pinned `test_hint_reflects_the_students_actual_wrong_option`
  (`test_learning_flow.py:1292`), which is **still 0 failures in 20 runs** today. The 60/60 it
  recorded was that test's, not this one's — so there was no contradiction to explain. (A 60/60 run
  at a 17.9% per-run failure rate has probability 0.821^60 ≈ 1×10⁻⁶, which is itself the tell that
  two different tests were being compared.)
- **What AUD-L-17 actually did was *unmask* this flake, and the mechanism is verifiable in one
  line.** Before it, the mock emitted `Level 1`, where the digit is space-delimited — so
  `answer_text_leaked` **fired**, the tutor discarded the personalized hint and substituted the
  canonical ladder text, and the canonical text carries no bare digit, so the substring assertion
  passed. After the change to `Hint L1` the runtime check **stopped** firing, the mock's own hint
  was served for the first time, and the substring assertion started seeing `hint l1`:

  | mock prefix | runtime check (`answer_text_leaked`, answer `"1"`) | plain substring | escalation test |
  |---|---|---|---|
  | `Level 1` (before AUD-L-17) | **leak → canonical served** | leak | passes |
  | `Hint L1` (after AUD-L-17) | no leak → **mock hint served** | leak | **fails 21%** |

- **The transferable part.** AUD-L-17 concluded "the mock's own boilerplate made the mock's own
  hint unusable" and adjusted the boilerplate — which was correct for the test it was fixing, and
  is precisely what exposed a *second*, independent defect one file away. The durable coupling is
  between a **test assertion** and a **mock string**, neither of which is the product; any fix
  applied to the mock only moves which answers collide.
- **Fix applied (in-session, because it blocked the baseline rather than the product):** the
  assertion now calls the two functions `tutor.py:240` itself calls — `leak_phrase_present` and
  `answer_text_leaked` — so the test asserts exactly the guarantee the product makes. The mock was
  **not** touched, on this finding's own reasoning. **0 failures in 40 runs** after (8/40 before),
  and `make lint typecheck test` green **three consecutive times** — the run count §2.6
  criterion 4 asks for.
- **Note on why the S36-continuation guard did not catch it.**
  `test_mock_hint_is_leak_clean.py` asserts the mock's hint against `answer_text_leaked` for every
  reachable answer, and it passes — correctly. It could not have caught this, because the defect
  was in a *different* test's stricter assertion, not in the mock.

---

## S39 — AUD-F (frontend contracts + operations)

**Method.** The browser-driven half of §2.3, which S36 and S37 each left uncovered because no
browser automation existed in this environment. A Playwright harness now lives in
[e2e/](../e2e/) (`make e2e`), chromium-only, one worker, zero retries. Every run attaches a
console/network capture to the page and enforces §2.6 criterion 3's three properties at
teardown over the whole run rather than at any single assertion: zero console errors, zero
5xx, zero blank/stuck states. A test that deliberately drives an error path narrows that check
with an explicit, greppable `audit.allow({...})`; the default is strict.

**The harness carries its own positive control** (`tests/smoke.spec.ts`), for the reason D-101 §5
and D-102 record: a probe that can only return "clean" is not a measurement. It produces a
console error and a failed request on purpose and asserts the fixture saw both.

**Three hypotheses were formed and then disproved by measurement**, which is worth recording
because each would have been a plausible finding written up from code reading alone:
- *"The requested hint is displaced before the student can read it."* Measured: the hint panel
  survives **14.7 s** of no interaction. Not a defect. The journey walk's apparent disappearance
  was the graph having already advanced past that pause.
- *"The SSE stream reconnects ~2×/second."* Suggested by 71 `net::ERR_ABORTED` entries against
  the stream URL in one 38-second run. Measured with the student idle: **0 stream reopens in
  20 s**. The aborts are the session hook's own `EventSource` cleanup on screen swaps — expected
  behavior, and the harness now excludes them rather than reporting a phantom.
- *"The attendance gate is bypassed for an absent student."* The browser reached a stage
  narrative instead of the gate, which looked like a fail-closed violation. Checked directly at
  the API for both fixtures first: the gate fires at `/topics`, not at `/student` — absent →
  `phase: blocked`, present → `pre_exam`. **The gate is correct and the test was asserting at the
  wrong step.** Rule 5 holds.

### AUD-F-01 — Inline-arrow callbacks in effect dependency arrays fire two endpoints per render (P1)

`App.tsx` passes `onFetchOverview={() => void session.fetchExamOverview()}` and
`onRecordTime={(id, ms) => session.recordItemTime(id, ms)}` — new function identities on every
render. `ExamScreen` lists both in effect dependency arrays: the overview poll effect
(`[isExamPhase, phase, onFetchOverview]`) and the view-time autosave effect
(`[currentDisplayOrder, phase, currentOverviewItem?.assessment_item_id, onRecordTime]`). Every
App render therefore tears both effects down and re-runs them — the poll fires an immediate
fetch and installs a fresh interval, and the autosave's *cleanup* reports elapsed time and its
body immediately resets `viewStartRef`.

**Measured, with the student sitting on one question for 15 seconds and touching nothing:**

- **885 `POST /exam/items/{id}/time` requests** (~59/second), values
  `[21, 24, 19, 18, 17, 19, 18, 19, 17, 17, 19, 18, …]`, **max 94 ms**. Each report covers the
  gap between two renders, not time on task.
- **76 `GET /exam/overview` for one 10-item exam** — 7.6 per answer submitted — at a **median
  gap of 30 ms** against the code's own `OVERVIEW_POLL_MS = 20000`, a ~667× amplification.

Both endpoints hit the database (`add_item_time` does a read-modify-write on
`assessment_item_state`). §2.4 puts "cost or latency out of bounds" at P1, and this is on the
hot path of the primary launch journey at 1,000-MAU scale, so P1 is the reading recorded here.
The fix is small — memoize both callbacks, or drop them from the dependency arrays via a ref —
but it must be **re-verified by counting requests**, not by observing that the screen still
works, because the screen has always still worked.

**Bearing on AUD-L-14, which needs re-examination rather than a fix as written.** The server
*accumulates* (`state.time_spent_ms += elapsed_ms`), and the browser's 885 reports total
**15,591 ms for a 15,000 ms dwell** — approximately correct. So client telemetry is not
inherently zero, and S36's "140 item-state rows summing to 0 ms" is most consistent with those
journeys having been driven **through the API with no browser in the loop**, which is exactly
how S36 drove them. AUD-L-14's underlying point stands (the report depends on client telemetry
while ignoring the always-populated `assessment_attempts.response_time_ms`), but its headline
evidence should be re-measured with a browser before anything is built on it.

### AUD-F-02 — The client keeps calling exam endpoints after finalize, flooding the console with 409s (P2)

After `POST /exam/finalize` returns 200: **35 requests rejected 409 in a 96 ms burst** — 33
`GET /exam/overview` and 2 `POST /exam/items/{id}/time` — and **zero arriving more than 5 s
later**, with no exam screen mounted at the end of the window. Timestamped precisely to
separate a leaked interval (unbounded) from a remount burst (bounded); it is the latter, driven
by AUD-F-01's per-render effect churn as the app transitions out of the exam phase.

Bounded, self-limiting, and invisible to the student — but each failed fetch is a browser
console error, so a single journey accumulates **35–59** of them. **§2.6 criterion 3 requires
zero console errors on every launch journey, so the criterion cannot be met until this is
fixed**, independently of any user-visible symptom. Reproduced by
`tests/learning/post-finalize-poll.spec.ts`, which is marked `test.fail()` so the suite stays
green while the count keeps being measured on every run; when Phase 0B fixes it the test passes
unexpectedly and fails the run, which is the signal to promote it to a regression test.

### AUD-F-03 — A refresh mid-exam does not restore the student's position (P2)

Answer two questions, refresh: **"Pre-exam Question 3 of 10" becomes "Pre-exam Question 1 of
10"**. The session, the answers and the read-only locks all survive — only the position is lost,
because `sessionId` is persisted in `sessionStorage` while `currentDisplayOrder` is `ExamScreen`
state that a reload discards.

SPEC Phase 11's own "done when" is that a page refresh restores the exact position, and
`useLearningSession`'s docstring cites it verbatim as the reason the session id is persisted at
all — so this is a documented requirement that no test covered. P2 rather than P1 because the
student can navigate forward with the nav bar and loses no work.

### AUD-F-04 / AUD-F-05 — Stage narratives return after a refresh, and displace live screens (P3, P3)

`App.tsx` gates `stage_narrative` ahead of every phase branch and tracks dismissal in React
state keyed by the narrative text. Two consequences, both measured:

- **After a reload the narrative returns** (`"Welcome back! Let's see what you remember today."`)
  because the snapshot still carries it and the dismissal did not survive. One further click
  clears it and the exam returns — verified, and the whole of why this is P3.
- **The narrative displaces a screen already in use.** The topic list renders from the `/student`
  response and is interactive for a measured **~26 ms** before the SSE snapshot carrying the
  narrative replaces it; the same swap detaches the Submit-answer and ladder buttons mid-click.
  A human is unlikely to lose a click to a 26 ms window, and the one scripted click that landed
  inside it still reached `POST /topics` — so the real cost is that every automated journey needs
  retry logic, which is how this was found in the first place.

### AUD-F-06 — No scheduled jobs exist, so criterion 6's clock has not started (P2)

`aws events list-rules` and `aws scheduler list-schedules` both return **empty**. All four jobs
run clean when invoked by hand (`chat-purge`: 0 rows older than 90 days; `memory-consolidate`:
160 students; `youtube-sync`: 4 updated; `webcontent-sync`: 5 sections / 50 members / 26
branches / 42 events) — but nothing invokes them.

**Only three of the four are schedulable at all, which changes the Phase 0B work item.**
`make webcontent-sync` **rewrote seven tracked files** under `knowledge-content/` when run here,
and prints "Review the git diff before running `make org-load`/`make knowledge-load`" — it is a
content-authoring step that expects a human to inspect its output, not an unattended job. It also
**broke the test suite** while those edits were in the working tree
(`test_ingestion_creates_all_documents_then_is_idempotent_on_rerun`), which is how it was noticed;
reverting the files restored 513 passed. Scheduling it in ECS would additionally fail outright
against D-088's `readonlyRootFilesystem = true`. §2.5's "EventBridge schedules for the four manual
jobs" should therefore be re-scoped to **three** (`chat-purge`, `memory-consolidate`,
`youtube-sync`), with `webcontent-sync` left manual and that decision recorded.

**Fixed in S40, and building it changed the answer twice.** `terraform/modules/scheduled-jobs`
creates EventBridge **Scheduler** schedules (not a rule + cron: explicit timezone, per-target retry
policy, per-job enable gate) targeting the existing ops task with a command override, plus an
EventBridge rule on any non-zero-exit ops-task run routed to the alerts topic.

**Re-scoped again: three schedulable jobs became *two* enabled ones.** This finding counted three
from a *local* run, and running them against the deployed environment is what showed the
difference. `memory-consolidate` and `youtube-sync` read `MEMORY_*`/`YOUTUBE_*`-prefixed settings
that the ops task never set, and both default to **`bedrock_provider = "mock"`**. A mocked
scheduled job does not fail - **it succeeds and writes fabricated data into the real database on a
weekly cadence**, which is strictly worse than an outage, and AUD-C-16 is precisely what that looks
like discovered months later. `memory-consolidate` is now wired explicitly - including pointing
`MEMORY_BEDROCK_CONSOLIDATION_MODEL_ID` at the model IAM actually grants, since its own default is
Sonnet 5 which this task role cannot invoke, so the unwired job would have been *either* mocked or
denied. **`youtube-sync` is DISABLED**: `youtube_provider` defaults to `"fake"` and no real key
exists (D-002's posture, still true), so an unattended run would refresh the catalog from a fake
source every week.

**The failure notification was itself dead on arrival, and only a test caught it.** The rule fired
correctly - `Invocations = 1` - and `FailedInvocations = 1` while SNS delivered **0**: the topic
policy did not permit `events.amazonaws.com` to publish. **CloudWatch *alarms* publish to that same
topic fine on the default policy alone** (4 delivered during S39's induction), which is exactly why
this was worth measuring rather than reasoning about - the working service gave false confidence
about a different one. Fixed with an explicit topic policy that reproduces the default statement
verbatim (dropping it would revoke the account's own Subscribe rights and orphan the email
subscription) plus an `events.amazonaws.com` publish grant scoped by `SourceAccount`. Re-verified:
the next two deliberate failures both delivered, 0 failed. **The notification built to stop a
scheduled job failing unnoticed would itself have failed unnoticed** - AUD-F-12's shape reproduced
inside its own remedy, one session later.

The consequence is a schedule fact, not just a defect: §2.6 criterion 6 requires the jobs to have
run **unattended for ≥ 1 week**, so **the earliest the gate can pass is one week after the
EventBridge schedules land in Phase 0B**. That should be sequenced early in S40–S41 rather than
late, or it becomes the critical path to S42 on its own. It also means the 90-day `chat-purge`
retention promise currently depends entirely on a human remembering to run `make`.

### AUD-F-07 — The memory-consolidation job spends 94% of its budget on load-test fixtures (P2)

One `make memory-consolidate` run: **160 students, 577 facts added, 145.97 cents**. Of the 159
distinct students with `semantic_memory` rows, **150 are `loadtest-student-N`** — disposable
fixtures S34's load test created and never removed.

**Premise corrected in S40: staging has *zero* `loadtest-` rows** - its `semantic_memory` table is
empty entirely, and `learning_events`/`stage_transitions`/`assessment_sessions` contain no
loadtest-prefixed ids at all (checked directly against staging Postgres via the ops task). The 150
fixtures are **local-only**, which follows from D-095: S34's load test ran against docker-compose
because that session had no live AWS access. So the ordering constraint below - clean the fixtures
*before* creating the schedule - **was not actually load-bearing**, and no scheduled run was ever
going to spend Bedrock money on synthetic students. Cleaning the local dev database is now
optional hygiene (it does make `make memory-consolidate` locally report 160 students and 145.97
cents, which is noise that could mask a real regression). Recorded because the reasoning was sound
and the premise was still wrong: **a measurement taken locally is not a measurement of staging**,
the same correction D-103 §3 made about browser-vs-API evidence.

Locally the provider is `MockBedrockProvider`, so that figure is what the cost-accounting layer
would charge rather than a real charge; the same job against staging's real Bedrock spends real
money, and would do so on **every** scheduled run once AUD-F-06 is addressed. Ordering matters:
clean the fixtures (or scope the job to real students) **before** creating the schedule, not
after. Same family as AUD-L-02 and AUD-X-08 — a paid path with no bound on how much work it
decides to do.

### AUD-F-08 — Two of four deployables have no CI job (P3)

`ci.yml` has `lint-typecheck-test` (Python) and `learning-web` (lint + typecheck + build).
**`chat-web` has no job**, already known and on the Phase 0B list, and the new `e2e/` harness has
none either. Against criterion 4's "CI builds and tests every deployable", two of four are
uncovered. Recorded rather than fixed here because §2.5 already owns chat-web CI; the e2e harness
should join the same job when it lands.

### AUD-F-09 — The deploy workflow would have crash-looped the new sidecar (P2, fixed in S39)

`deploy-staging.yml` patched the image tag with `for c in td['containerDefinitions']` — every
container, not just the app's. Correct while each task had exactly one container, and silently
fatal the moment Terraform added the `aws-otel-collector` sidecar: the loop would have rewritten
`aws-otel-collector:v0.43.3` to `aws-otel-collector:gha-<sha>`, an image that does not exist,
and every subsequent deploy would have failed to start and rolled back via the circuit breaker.

Found by reading the deploy path *before* applying the sidecar rather than by watching a deploy
fail. Fixed in the same session because it is a defect in the change being made, not a
pre-existing product defect: the patch now selects the app container by name and asserts exactly
one match, so a future container-name change fails loudly instead of mis-tagging.

### Negative results, S39

All of the following were exercised **in a real browser** and behaved correctly.

- **Every chat response shape renders.** All **18** payload shapes the API can emit — S37's
  fourteen, with the email and location outcomes split into their sub-variants — rendered
  correctly, including citations, escalation banner, access hint, `.ics` download button,
  suggestion chips, and a visible modal for each of the three interrupt types. **S37's
  code-reading conclusion is confirmed by rendering**, which is what its ⏸ was waiting for.
- **The fixtures are not fiction.** A drift control runs one *real*, un-stubbed turn and asserts
  the live `/messages` field set equals the fixtures' — so a backend change that outgrew these
  shapes fails the suite instead of letting it audit a payload the API no longer sends.
- **AUD-C-04, AUD-C-10 and AUD-C-11 reproduced visually**, not just at the API: the paused turn
  renders the previous turn's answer *and* citation above an unrelated approval modal; an errored
  turn keeps a `Thinking…` bubble indefinitely while the error text renders separately below; and
  the no-source refusal renders a citation chip beside the sentence denying a source exists.
- **The composer locks and unlocks correctly** around a pending interrupt — which is what makes
  S37's "a fourth interrupt type would deadlock the session" a genuine latent gap rather than a
  live one.
- **Attendance fails closed in the browser for both cases.** Absent (`student-ext-2`) and
  **unknown-attendance** (`student-ext-3`, no row at all) students both reach the gate and never
  reach an exam screen; the branch-manager path shows the email draft with both Send and Decline
  before anything is sent (SPEC §5.1.4), and declining leaves the gate closed.
- **The parent journeys work.** A two-child parent is offered exactly both children and the
  selection sticks; a **single-child parent is auto-selected** without being asked, so S11's
  auto-select gap does not reproduce here.
- **Chat answers render for every audience** — guest and signed-in student, parent, tutor and
  branch_manager — plus out-of-scope refusal, welcome-card suggestion chips, new-chat reset, real
  login-screen sign-in, and transcript restoration across a refresh.
- **The branch locator asks consent before collecting anything**, renders the notice text,
  disables the composer while pending, honors "Don't use my location", and returns a rendered
  answer when a ZIP is shared.
- **No SSE reconnect storm**: 0 stream reopens in 20 s of idle.
- **X-Ray held 0 traces over 6 hours** before any change — a clean baseline for the trace work,
  recorded so that traces appearing after the sidecar deploys means something.

### AUD-F-10 — Private-subnet tasks cannot reach public.ecr.aws, so the sidecar could not be pulled (P2)

The VPC has interface endpoints for `ecr.dkr`, `ecr.api`, `secretsmanager`, `logs` and
`bedrock-runtime`, an S3 gateway endpoint for image layers, and **no NAT gateway** — deliberate,
per D-084's cost posture. Private ECR works through those endpoints; `public.ecr.aws` is a
separate registry with **no interface endpoint at all**, so it is simply unroutable from a task.

Nothing predicted this. It appeared the moment the sidecar deployed:

```
CannotPullContainerError: pull image manifest has been retried 7 time(s): failed to resolve ref
public.ecr.aws/aws-observability/aws-otel-collector:v0.43.3: ... dial tcp 75.2.101.78:443: i/o timeout
```

`essential: false` on the sidecar did **not** help, and the reason is worth recording: a
non-essential container that *exits* leaves the task running, but one that cannot be **pulled**
fails the whole task before it starts. Non-essential protects against a crashing collector, not
against an unreachable image.

**Handled, and the state is precise.** Both services were rolled back to the pre-sidecar revision
and re-verified through the public edge — frontends 200, learning `/readyz` **200** (which proves
real Postgres *and* MySQL connectivity), chat `/me` 401, `/dev/token` **404** with no credential,
so S35's security gate is intact. An `aws-otel-collector` repository now exists in this account's
private ECR, `scripts/mirror-otel-collector.sh` pins the version and pushes **linux/arm64** (to
match `runtime_platform`, since an amd64 image on an ARM64 task fails with an exec-format error
that looks nothing like a platform mismatch), and Terraform points the sidecar at the mirror.
**The push did not finish before the AWS session expired**, so the mirror is empty.

**The one thing that must be done first next session.** Task-definition revision 18 is the latest
and still references the public image, and `deploy-staging.yml` resolves
`--task-definition intellichoice-staging-<svc>` to the *latest* revision before patching it — so
**the next CI deploy inherits the unreachable sidecar and fails** (safely: the circuit breaker
rolls it back, as it just did). Either run the mirror script, or set `enable_otel_tracing = false`
and re-apply, before the next push to `main`.

**Closed in the S39 continuation.** The mirror was pushed (`sha256:ba3c3f06…`, 39 MB,
`linux/arm64` confirmed against `runtime_platform`), Terraform re-applied, and both services
deployed onto the sidecar revision cleanly — `COMPLETED`, both `otel-collector` containers
RUNNING, both target groups healthy, the hazard above de-armed because the latest revision now
names the private mirror. **One addition to the script:** the anonymous pull failed with
`toomanyrequests: Rate exceeded`. `public.ecr.aws` rate-limits unauthenticated pulls, and
`aws ecr-public get-login-password | docker login public.ecr.aws` clears it — worth knowing before
concluding the image is gone.

### AUD-F-11 — Terraform's image pin had gone stale behind deployed reality, so `apply` reverted a security fix (P2, fixed in the S39 continuation)

`terraform.tfvars` pinned both services at `gha-6cc4a27430bd`. Both services were *running*
`gha-d1899a483d06`. The gap matters because of which commit that is:

| tag | commit | pushed to ECR | what it is |
|---|---|---|---|
| `gha-6cc4a27430bd` | 6cc4a27 | 2026-07-24 10:34 | the asyncpg SSL fix |
| `gha-d1899a483d06` | d1899a4 | 2026-07-24 **16:31** | **"`/dev/token` signed with the public dev constant, not the real secret"** |

So every `terraform apply` registered a task-definition revision that **silently reverted a
security fix**, and an operator who applied and then pointed the service at the new revision —
the natural reading of "apply, then deploy what I just applied" — would have deployed the
regression. CI never noticed because `deploy-staging.yml` patches the image tag on top of
whatever Terraform registered, so the stale pin is invisible on the path that is normally used.

**Why nothing could have caught it.** `terraform plan` is clean: the tag exists in ECR and pulls
fine. `terraform validate` is clean. The tfvars comment even asserted the pin was "latest on
main", true when written and false six hours later. The only thing that reveals it is diffing the
*registered* revision against the *running* one, which is what found it here — done because
D-103 §5's lesson was to read the deploy path before applying, and the same discipline applied one
step further.

**Fixed** by bumping the pin to `gha-d1899a483d06` with a comment stating the failure mode, and
the sidecar revision was then verified to differ from the running revision in exactly one
dimension (OTel on, sidecar added) before deploying. **Third occurrence of this project's
recurring shape:** config-level intent and deployed reality disagreeing with nothing tying them
together — D-096 (P0, `/dev/token` open for two days) and AUD-F-09 (the per-container tag rewrite)
are the first two.

### AUD-F-12 — The collector accepted every span and discarded every one, and nothing detected it (P2, fixed in the S39 continuation)

With the sidecar finally running, no trace reached X-Ray. The app was exporting correctly and the
collector was receiving correctly; the **export leg** failed, every time:

```
Exporting failed. Rejecting data. {"kind": "exporter", "data_type": "traces", "name": "awsxray",
 "error": "Post \"https://xray.us-east-1.amazonaws.com/TraceSegments\": context deadline exceeded",
 "rejected_items": 64}
```

**AUD-F-10's root cause, one layer further in.** No NAT gateway, and no interface endpoint for
`xray` — so in this VPC, every AWS API the tasks call needs its own endpoint, and X-Ray had been
overlooked exactly as public ECR was. The lesson generalises past both: **`terraform plan` cannot
see reachability**, and each of these appeared only at runtime.

**The part that makes it a finding rather than a config oversight is that nothing detected it.**
The sidecar is `essential: false` and starts perfectly healthy. The app's own export succeeds — it
hands spans to a local collector that accepts them. Both services stayed green, both target
groups healthy, no alarm watches collector export failures, and the only evidence was a WARN
buried in a sidecar log stream nobody reads. **Criterion 9 would have been reported "clean" from
an empty trace store** — which is precisely why `scripts/scan_xray_pii.py` treats zero traces
scanned as an explicit FAIL rather than a pass. That guard, not the endpoint, is the durable fix.

**Fixed** with a single-AZ `xray` interface endpoint (`var.xray_endpoint_enabled`, wired to
`enable_otel_tracing` so it is not paid for when tracing is off), matching the cost posture of the
existing five (~$7.30/mo; a NAT to carry the same traffic would be ~$32). Traces went from the
recorded baseline of **0 over 6 hours** to **650** on the next traffic run. The failures logged
*after* the endpoint went live were the batch queue draining spans buffered during the outage —
identical `rejected_items: 64` each time — not new failures, which is worth stating because they
read exactly like an unfixed problem for several minutes.

### AUD-F-13 — A bearer JWT is recorded in `http.url` on every SSE connection (P1, fixed in the S39 continuation)

The very first PII scan of real traces found a **455-character JWT** in a span attribute:

```
$.http.request.url   http://d35dfnjzmgrm01.cloudfront.net/learning/sessions/
                     65bb3d96-.../stream?token=<JWT>
```

**Mechanism.** The SSE stream authenticates via a query parameter because `EventSource` cannot
set an `Authorization` header, and `FastAPIInstrumentor` sets `http.url` to the **full** request
URL, query string included. Reproduced locally in three lines: `http.route` is templated and
`http.target` is the bare path — **`http.url` alone carries the credential.**

**The same request is sanitized in one store and not the other**, which is the transferable part.
Access log and trace segment for the identical request (`trace_id 3a10417997b2a36996a5fb2c75194901`,
19:44:47 UTC, 401):

```
log:   {"event": "http_request", "path": "/learning/sessions/{learning_session_id}/stream", "status_code": 401}
trace: http.request.url = ".../stream?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

The app's own access logger templates the path and drops the query string — deliberately. That is
why **S38's log scan was clean and this trace scan was not**, and why a PII floor has to be
re-established per store rather than inherited: instrumentation added later does not honour the
sanitisation the application wrote for itself.

**Impact, bounded honestly.** Token TTL is 1 hour, so a captured token is usable for at most an
hour after issuance; reading it requires AWS access to this account; and the one token actually
captured was **already expired when recorded** (hence the 401). X-Ray has no delete API, so it
ages out with the 30-day retention. Held at **P1 rather than P0** on that basis — but it becomes a
live-credential capture the moment authenticated traffic runs with tracing on, which the load run
and any `make e2e` against staging both do.

**Fixed in-session**, on the D-103 §5 rule: enabling tracing on staging is this session's own
change, and this is a defect in that change rather than a pre-existing product defect §2.4 would
defer. Redaction happens in a `RedactingSpanExporter` at the **export boundary**, not in a
`server_request_hook`. The hook does work — measured, the instrumentation sets `http.url` before
calling it, so an override wins — but that is an ordering guarantee no library documents, and
`tracing.py` already records two upstream ordering footguns that silently dropped spans. Export is
the one point every span from every instrumentation must cross. **The regression test drives the
real instrumentation** (a FastAPI app, a real SSE-shaped route, `TestClient`) rather than the
regex, because the defect was about which attribute the instrumentation populates, not about the
pattern — and it was confirmed to fail with redaction disabled before being trusted. A second test
asserts ordinary attributes survive, since a redactor that rewrote everything would also pass the
first one.

**Re-verified live on staging after the CI deploy (`bccc3ac`, task-definition revision 21)**, which
matters because the local test proves the code and not the deployment. Three SSE requests carrying a
deliberately fake JWT — a 401 is irrelevant, since the URL is recorded either way, which is what
makes this testable **without holding a real credential**:

```
$.http.request.url = .../learning/sessions/00000000-0000-4000-8000-000000000001/stream?token=REDACTED
leaked_jwt: False | redacted: True   (×3)
```

The path and session id survive, so the span stays diagnostically useful. Found live, fixed,
deployed through the normal pipeline, and re-verified live by the same scanner that found it.
**Both services confirmed**, which matters because chat's stream takes the same optional `?token=`
(SPEC §5.19.1) and the fix lives in shared `packages/observability` rather than in either app:

```
chat-api:     .../chat/sessions/88cd4977-.../stream?token=REDACTED   leaked=False redacted=True (×2)
learning-api: .../learning/sessions/00000000-.../stream?token=REDACTED  leaked=False redacted=True (×3)
```

**Still to do before the gate:** a re-scan against *authenticated* traffic — see the coverage limit
below.

### Criterion 9, traces half: clean, with both a positive control and a coverage control

**1,925 traces / 9,614 segments / 749,155 strings** scanned clean over a 2-hour window, and the
apparatus matters more than the number:

- **Positive control, every run: 20/20 patterns fired** against a synthetic segment. Without it,
  "clean" is unfalsifiable — the failure mode S38 hit and D-101 §5 recorded.
- **Coverage control.** The one request that carried precise coordinates in its body (a guest
  locator consent flow, `latitude: 39.781712, longitude: -89.650143`) was proven to be *in the
  scanned set* — session `fa31a009-…`, with a `langgraph.branch_locator_consent` subsegment — and
  **no coordinate appeared anywhere in it.** Request bodies are not captured into spans. Without
  this control, a clean result could equally mean the interesting request was never scanned.
- **17 hits in the first run were all false positives**, and the fix is recorded because the shape
  recurs: `39.85` as a *substring* matches the epoch `start_time` on every segment
  (`1785093039.8546414`). Now boundary-aware and control-tested both ways — epochs do not match,
  `39.850012` does. Same mistake AUD-X-06 records in a test assertion one session earlier.
- **One narrow allowlist, printed rather than silent:** `sql.sanitized_query` legitimately contains
  the column names `manager_email, address, latitude, longitude`. That is schema, not data, and its
  presence alongside no parameter values is evidence the stripping works. A coordinate *value* in a
  sanitized query would still be reported.

**Coverage limit, stated plainly.** Only guest and unauthenticated traffic could be driven — the
per-app `STAGING_TOKEN_SECRET_*` values were not available to this session, and reading them out
of Secrets Manager is not something an audit should do. Authenticated journeys are where names and
emails would actually enter a span, so **the trace scan is real but narrow**; it must be re-run
against authenticated traffic before the gate. AUD-F-13 was found in unauthenticated traffic only
because a stale browser token happened to be retrying.

### AUD-F-15 — `chat-purge` had never run against the deployed database, so the 90-day retention promise was never kept (P1, fixed in S40)

Found by the **first ever scheduled run** of the job, which is the only thing that could have found
it:

```
ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)
```

**Mechanism.** The CLI called `create_engine(get_settings().database_url)`.
`learning_api.config.Settings` sets `env_prefix = "LEARNING_"`, so it looks for
`LEARNING_DB_HOST`/`LEARNING_DB_PORT`/… — while the **ops task** supplies D-092's *unprefixed*
`DB_HOST`/`DB_PORT`/`DB_NAME` plus credentials from Secrets Manager, which is what
`create_engine()`'s bare fallback resolves. Finding none of its prefixed variables, the settings
object kept `database_url`'s hardcoded default: `postgresql+asyncpg://…@localhost:5432/…`.

**Why three prior audits and a CLI-level test all missed it.** On a developer's machine, and in CI,
**localhost genuinely is the database**. `make chat-purge` worked. `test_tutor_chat_purge_cli.py`
worked — it exercises the real cutoff arithmetic against a real Postgres, which is worth having and
is orthogonal to this. Every signal available without a deployment said the job was fine. The
consequence is not a crash but an unkept promise: SPEC's 90-day tutor-chat retention **had never
once executed against real data**, and would not have until someone ran it by hand inside the VPC.

**Fix:** `create_engine()`, bare, matching `consolidate_cli` and `sync_cli`. Local behaviour is
unchanged (no components set → `DATABASE_URL` → the same localhost default).

**Verified on the real path after deploying, not just locally** — the fix is in app code, so only a
deployed run proves it. A one-shot Scheduler probe was fired against the rebuilt image:

```
startedBy: chronos-schedule/probe-chat-purge-af    (i.e. EventBridge Scheduler, not run-task)
taskDefinition: intellichoice-staging-ops-task:17  (the image containing the fix)
exitCode: 0
log: "purged 0 tutor_chat_messages row(s) older than 90 days"
```

`0` is the correct answer here — staging holds no tutor-chat rows past the cutoff — and it is
distinguishable from the failure it replaced, because the broken form could not reach a database at
all. **The same probe technique is what found the defect and what confirmed the fix**, and it cost
about two minutes each time; waiting for 18:10 UTC would have deferred both by a day.

**Third instance of one shape, so the fix is a guard rather than a patch.** `create_engine`'s own
docstring already records the S32/D-084 instance (`curriculum-load` against real RDS, same
`ConnectionRefusedError`). `packages/db/tests/test_standalone_clis_use_the_env_fallback.py` now
asserts every standalone CLI calls `create_engine()` with no argument, **with a negative arm**
asserting the two FastAPI apps still pass theirs explicitly — because a blanket "never pass an
argument" rule would be wrong for them, and a guard that over-applies gets deleted by the next
person who trips over it. Deliberately a source-level check: the behaviour to guard is "does not
read the app's prefixed settings", and the only runtime condition that reveals it is having no
database at localhost — which is exactly what a developer's machine cannot reproduce.

### AUD-F-14 — Five concurrent chat turns take 30 seconds each, and the autoscaling policy cannot see it (P1)

**Measured on live staging**, 45 guest RAG turns against real Bedrock, all **200** — no errors, no
timeouts. The service queues rather than failing, which is the right failure mode, and then:

| condition | response time |
|---|---|
| unloaded, single turn | **1.62–1.88 s** |
| 5 concurrent turns | p50 **26.92 s**, p95 **32.14 s**, max **33.41 s** |

ALB-observed p95 per minute: **3.56 → 31.97 → 30.96 → 30.98 s** against the alarm's 3.0 s
threshold — roughly **10× out of bounds at a concurrency of five**, which for a launch aimed at
~1,000 MAU is not a stress test.

**The part that is a defect rather than a capacity fact: nothing can react to it.** Application
Auto Scaling is configured (min 1, max 3) with a single **`ECSServiceAverageCPUUtilization`
target-tracking policy at 70%**. The workload is I/O-bound — it is waiting on Bedrock, not
computing — so during the window where p95 sat at 31 s, CPU **peaked at 15.19%** against an idle
baseline of ~1.3%:

```
15:43  CPU max  1.44%   p95  3.56s
15:44  CPU max 15.19%   p95 31.97s     <- worst CPU of the whole run, still 55 points below target
15:45  CPU max 12.56%   p95 30.96s
15:46  CPU max  9.11%   p95 30.98s
```

`desiredCount` never left **1**. So the scaling policy will not fire at any latency this workload
can produce, and **§2.6 criterion 7's "live load meeting the S34-calibrated thresholds with ≥2
tasks" is unreachable as configured** — not because scaling is absent, but because it is wired to
the one signal that stays flat. The fix is a different signal (`ALBRequestCountPerTarget`
target-tracking, or a step policy on the p95 latency alarm that already exists), or a higher static
`desired_count`; the choice belongs in Phase 0B alongside the item the roadmap already carries.

**This also sharpens D-095's diagnosis rather than contradicting it.** S34 concluded "the real
bottleneck is that `desired_count=1` with one uvicorn worker means all concurrent request handling
serializes on one Python process… the real fix for the P95 gap is capacity, not code," and added
this autoscaling. Correct on the cause. What could not be seen from a docker-compose run against
`MockBedrockProvider` — S34 had no live AWS session (D-095) — is that **the capacity fix it added
cannot be triggered by the bottleneck it diagnosed.** S34 measured 2.77 s p95 at 150 concurrent
sessions with a mock; real Bedrock puts ~2 s of I/O wait into every turn, and five of those
serialized is 30 s at a CPU cost of nothing.

### Criterion 5 — deliberate bad-image deploy, auto-rolled back, with downtime measured

A revision was registered with an unpullable tag on the **essential** container (`gha-deadbeefdead0`),
so the task fails before any bad code serves a request — the breaker is what is under test.

```
15:28:11  task 1 started -> CannotPullContainerError, pull retried 7 time(s), not found
15:30:21  task 2 started -> same
15:32:34  task 3 started -> same
15:39:09  task 4 started -> same
15:42:06  deployment failed: tasks failed to start
15:42:06  rolling back to deployment ecs-svc/5798213581200726447
```

`failedTasks` reached **3**, the threshold for a single-task service; the bad deployment ended
`FAILED`/`DRAINING` with 0 running, and revision 21 returned as `PRIMARY`. **13 m 55 s** from bad
deploy to rollback — worth knowing, because it is the floor on how long a bad deploy is stuck
before ECS gives up.

**Zero downtime, measured rather than assumed: 200 edge probes across the whole window
(20:27:56 → 20:44:56), every one a 401 from the application, zero 5xx and zero connection
failures.** `minimum_healthy_percent = 100` kept the old task serving the entire time.

**Two tooling mistakes made while measuring this, both recorded because they are the recurring
shape of this project's near-misses.** (1) The poller first targeted the CloudFront **root**, which
is the S3-hosted SPA and returns 200 with the API completely dead — the availability number would
have been meaningless. It was changed to `/learning/*`, one of the three behaviours CloudFront
forwards to the ALB, where a 401 proves the application answered. (2) The script's summary line
still compared against literal `200` after that change, so it reported `non-200=200` — every probe
"failing" when every probe was the expected 401. The raw log settled it. **A check that cannot
fail, and a check that cannot pass, are the same bug.**

**Cleanup:** revision 22 was deregistered. Leaving a poisoned revision as the family's *latest* is
precisely AUD-F-10's trap, since `update-service` against a bare family name resolves to latest.

### Criterion 8 — one alarm induced genuinely end to end, three on the delivery leg only

**`chat-api-p95-latency`: fully induced, detection and delivery.** Real 30-second latency drove it
`OK → ALARM` at 15:48:54 on its own evaluation, citing the actual datapoints:

```
Threshold Crossed: 3 datapoints [30.955 (20:45), 31.966 (20:44), 3.558 (20:43)]
were greater than the threshold (3.0).
```

and the topic action executed. **Delivery is proven by SNS's own metrics, not inferred from the
alarm**: `NumberOfMessagesPublished` 1, **`NumberOfNotificationsDelivered` 1**,
`NumberOfNotificationsFailed` 0, against a three-hour baseline of zero. Across all four inductions:
**4 delivered, 0 failed**, to the one confirmed email subscription on
`intellichoice-staging-alerts`.

**Human receipt confirmed by the maintainer, 2026-07-26: all four emails arrived.** Recorded
explicitly because it is the half of criterion 8 that no AWS API can evidence — `Delivered` means
SNS handed the message to SES, not that it survived spam filtering into a monitored inbox. **So the
"reaching a monitored inbox" half of criterion 8 is now met for all four alarms**; what remains
partial is the *detection* half for the three that could only be driven with `set-alarm-state`.

**The other three used `set-alarm-state`, and that is a real limit, not a formality.** No
unauthenticated path exists to induce them: every learning route depends on `get_current_claims`,
and chat has no reachable 5xx (a malformed session id and a nonexistent one both return **200** —
any string is a valid LangGraph thread id for a guest, which is AUD-C-01's shape again). So for
`learning-api-5xx-rate`, `learning-api-p95-latency` and `chat-api-5xx-rate`, what is proven is that
**each alarm's own action wiring reaches a delivering subscriber** — worth having, since a
mis-wired action on one alarm would otherwise be invisible — but **not** that the metric and
threshold detect the condition they exist for. Those three need `STAGING_TOKEN_SECRET_*` and stay
**partial**.

**Two operational facts learned here, both of which will bite whoever repeats this.**
**(1) An alarm fires several minutes after the breach ends.** ALB metrics publish with ~1.5–2 min
lag (a period's `SampleCount` was watched growing 9 → 20 after the minute closed), so the p95 alarm
transitioned at 15:48:54 for a window that closed at 15:46. An interim conclusion that a short
burst *cannot* fire it was wrong, and the correction is the useful part: the lag **delays** firing,
it does not prevent it — so do not extend a load run just because the alarm has not tripped yet.
**(2) `set-alarm-state` is transient and the next real evaluation overrides it.** The p95 alarm was
manually cleared to OK, then legitimately returned to ALARM minutes later on the tail of the load
data. **This matters beyond tidiness: `deploy-staging.yml`'s canary-bake step rolls a deploy back
if any of these four alarms is in ALARM**, so an induction left lit — or cleared too early and
re-firing — breaks the next deploy. Staging was left with all four settled `OK` naturally.
