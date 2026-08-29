# PROJECT_STATE.md

This is the entry point: current state, open work, and navigation. In force since 2026-08-20,
when the documentation reconciliation migration executed. Precedence:
[reference/AUTHORITY_MODEL.md](reference/AUTHORITY_MODEL.md) — primary evidence beats this file.

---

## 1. Snapshot

| Field | Value |
|---|---|
| Snapshot date | **2026-08-29** (D-455..D-458: the stress test found and mitigated the **RDS secret-rotation incident** and measured the ceilings; `SILENT-500S` queued; UD-14 opened; dependabot batch #3 + the nltk advisory landed; the **resume-evidence measurement program** commissioned and its first two experiments accepted — D-458) |
| Last product-code commit | **`f2731a1`** (2026-08-29, dependabot batch #3 + the nltk PYSEC-2026-3726 bump, D-457); before them `519dff4` (D-452) |
| Deployed staging image (both ECS services) | **`gha-5fa15d491057`** = head `5fa15d4` (product code `7983154`), deployed 2026-08-26 (D-448, run 32930929448); **tasks force-restarted 2026-08-29** (D-455 rotation mitigation — same image, fresh secret resolution) |
| Deployed task definitions | learning `:153` (2/2 running), chat `:151` (1/1 running) — compare images, not revision numbers (`ARCH-34-REVISION-DRIFT`) |
| Repo-vs-deployed gap | **11 product commits** (`5fa15d4` → `f2731a1`: the D-450..D-452 e2e specs and comments — test-side — plus the D-457 dependency bumps: nltk 3.10.3 (security, PYSEC-2026-3726), boto3, and dev-tooling; no product behavior change waits on a deploy, but the nltk fix reaches staging only with one). The scheduled-job **metric filters (2026-08-21), heartbeat alarm windows (2026-08-22), and the deploy role's Logs Insights statements (2026-08-24, D-439)** remain applied via control-plane targeted `terraform apply` (§8) |
| Deploy trigger | **MANUAL** — the workflow `push` trigger stays commented out (D-417 §C9) |

**LB-05 rule (standing discipline).** "Implemented locally" is not "deployed". **Every live number
must be stated with the build SHA it was measured on.** Any claim about current behaviour that
differs between HEAD and staging carries both statuses, explicitly, in §3.

**Staleness rule.** If this snapshot is more than **14 days** old, or if any **product-code**
commit lands after `f2731a1`, or if the deployed staging image tag no longer matches this
header's snapshot, **re-verify §3, §4.3 and §8 before trusting them.** A dated claim can go
stale; an undated claim lies. Primary evidence (code, tests, config, live AWS reads) always
beats this file.

---

## 2. What this system is

An AI education platform for K–12 students, where **minors are the primary users**. Two
independently deployed apps share auth from the existing `go.intellichoice.org` system:
**Adaptive Learning** (attendance-gated pre-exam → personalized study → post-exam → learning gain
→ parent reports) and **Organization Q&A** (role-aware RAG over org documents, branch locator,
calendar, admin escalation). Normative requirements live in [SPEC.md](SPEC.md); the as-built
system is described in [ARCHITECTURE.md](ARCHITECTURE.md); the non-negotiable rules an agent must
never violate are in the repo-root `CLAUDE.md`.

---

## 3. Repository vs deployed

**The D-448 deploy (2026-08-26, run 32930929448, user-ordered) shipped `gha-5fa15d491057`**
(head `5fa15d4`, product code `7983154`) to both services with all workflow gates green
(deployed-version, `/dev/token` edge, canary bake — rollback skipped, the D-439 **blocking
deployed-image consistency gate**, SPA syncs + CloudFront invalidations, smoke through
CloudFront). It closed the whole 34-commit gap; **repo and staging agree as of this snapshot**,
and no migrations were in the window (`8509c0486d8d`, applied 2026-08-23, remains the latest).

**The 2026-08-29 stress measurement (D-456, build `gha-5fa15d491057`, fresh post-D-455
tasks, through CloudFront):** learning is **error-free through 100 concurrent** (1,400/1,400
requests, 1,000/1,000 answers; warm p95 3.03 s at 25 concurrent vs D-129's 2.75 s of
2026-07-30; 8.8–10.7 s at 50–100 with autoscaling to 3 tasks) — load converts to queueing,
never failures (D-134's law). Chat is **error-free at 5 concurrent guests** (p95 12.0 s vs
D-116's 16.68 s); at 10, the single shared anonymous rate-limit bucket returns 429s by design
(WORK-44 #2) — zero 5xx. The same session found and mitigated the **rotation incident**
(D-455, §8's first bullet).

**Facts from the D-448 deploy:**

- **Now live on staging for the first time:** the D-324 date-zone pair (calendar-approval times
  render in the event's zone; the date-only back-a-day edge is gone), the seam-(b) healing
  (D-432 — a mid-interrupt hit now degrades to a re-answer instead of a dead end), the D-433
  personalization outcome counter (staging's ran-dead mode is instrumented at last —
  Prometheus-only pending UD-5's EMF ruling), the D-441 chat-graph fan-out and input bounds
  (D-440), the DRIFT-91 relocation, and the 22 dependabot bumps (D-430, D-445). D-447's
  roster defaults ship in the images but are offline tooling with no runtime path.
- **The §7-R9 tripwire held through this deploy's task drain too:**
  `learning_checkpoint_repairs_total` read 0.0 in both service namespaces before (3-day
  window) and after (4 h window, 16 datapoints, read 2026-08-26T04:58Z) — the
  `ARCH-17-COMMIT-SEAM` acceptance is intact on `gha-5fa15d491057`.
- **LB-08's post-optimisation staging comparison is now measurable** — this deploy puts the
  D-441 optimisation live for the first time. The measurement itself stays paid work under
  UD-2 and must use D-441's span mapping (summing `langgraph.*` durations double-counts the
  concurrent pair) against D-426's durable 10.55 s pre-optimisation baseline.
- **The B4 escalation series (D-420/421/422) remains deployed but never observed live**
  (carried from D-426); a live re-walk remains available work for the next live-probe session.
- **COST-22's pre-initialised label series were verified live on the previous build**
  (2026-08-23, `gha-898e2fb4270b`); nothing in this window changes that surface (cost context:
  UD-3/COST-25).
- The deploy pipeline still has **no artifact-freshness check for the SPAs** — this run synced
  and invalidated both SPAs, but the gate class is still absent: no content-hash, ETag or
  digest comparison (`DRIFT-24-ARTIFACT-FRESHNESS`). The deployed-version and image-consistency
  gates cover the API images, not the static assets.

---

## 4. Active engineering work

3 open engineering entries. Full evidence per entry:
[reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md](reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md).
If any row here and the register disagree, **the register wins** — rows are re-derived from it,
never patched independently. Every key below is a heading anchor in the register (append `#` + the
lowercased key to the link above), except post-migration discoveries, which name their evidence
home inline (none today; the convention was set by `DEP-PR-BATCH-2026-08-21` → D-429, resolved
by D-430). The `NO-NEW-TEST-CODE` category is **closed**: all three
defects the audit established by code reading only (REQ-27, SEC-13, COST-06) gained executed
tests on 2026-08-21/22.

### 4.1 ACTIVE_REMEDIATION (3) — something built is wrong or silently ineffective

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `PII-REDACTION-GAPS` (post-migration discovery; evidence: `docs/resume_evidence/06_eval_observability/E6_1_REPORT.md`, D-458) | The E6.1 probe corpus measured the free-text redaction layers for the first time and found five gaps, two worth fixing: **F-1** `_URL_RE` lacks `re.IGNORECASE` (`HTTP://`/`Https://`/`WWW.` never match, 0/6 — mobile autocapitalisation produces exactly these); **F-2** the span-export redactor's credential vocabulary drifted from the log denylist's (uppercase `BEARER`, `?refresh_token=`, `?id_token=` miss). F-3/F-4/F-5 recorded, lower value | Fix F-1 and F-2 (one-line-class changes) after the measurement program completes, so recorded baselines stay stable; the E6.1 lane's gates then get re-measured upward in the same change | engineering |
| `SILENT-500S` (post-migration discovery; evidence: D-455) | Unhandled-exception 500s emit **only uvicorn's plain-text ASGI traceback** — no JSON `level=ERROR` line — so they are invisible to every `{ $.level = "ERROR" }` filter, to log-based alarms, and to the D-454 sweep method. Staging threw 114 traceback lines during the rotation incident while the observability layer read "quiet" | Route unhandled exceptions through the JSON logger (or add a plain-text `Traceback` metric filter + alarm); verify with a test that forces a 500 and asserts the JSON ERROR line exists | engineering |
| `D310-RESIDUALS` | One follow-up surviving the executed D-310 rotation: stale dead secrets in operator-browser `localStorage` | See 4.3 — a user action on operator machines; the (b) `ps` measurement and (c) README fix landed 2026-08-24 (D-437) | user |

### 4.2 ACTIVE_IMPLEMENTATION (2) — decided or specified, not built

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `RESUME-EVIDENCE-PROGRAM` (post-migration discovery; evidence: `docs/resume_evidence/MEASUREMENT_PLAN.md`, D-458) | User-commissioned 2026-08-28: a six-theme measurement program producing artifact-backed resume evidence. Tier 2 (~$5–9 real Bedrock) and Tier 3 (the isolated 200-candidate generation benchmark, ~$5–10) are **user-authorized**; Tier 3 is isolated-DB quality measurement, outside D-342's subject. Executed via Orca, one opus/high executor per experiment; findings reported-not-fixed inside measurement tasks | E5.1 and E6.1 accepted (D-458). Remaining: E3 (gateway concurrency + HITL denominator), E4 (memory), E1 (sustained load + SSE-at-scale), E2 (retrieval IR metrics), E5.2 (seeded defects), E6.2 (trace coverage), E5.3 (the generation run), then `RESUME_METRICS_REPORT.md` + `RECOMMENDED_RESUME_BULLETS.md`. Frozen Specs for all remaining experiments sit in `tasks/` | engineering |
| `WORK-35-LEDGER` | U7 consolidation sizing gated on a staging measurement nobody took — **eligibility-gate finding 2026-08-25 (D-442): "free" meant dollars, not authorization** — the register's own evidence line says the sizing read needs a database session, and `DB-CONTENT-VERIFY` homes that session on UD-2's read-only-session rider | **Blocked on UD-2**: when the user authorizes the time-boxed read-only DB session, take the sizing read (with `G2-LOCATOR-PURGE`'s `__resume__` query in the same session), then hold the design review and size N against the 90/90/365 windows. Carries two review inputs: D-420's redacted visitor free text no retention job covers, and D-440's `existing_facts` crossover (~100–120 facts vs the 32k gateway ceiling; which-facts-to-drop deliberately unmade) | engineering, gated on user |

### 4.3 The item an agent should be able to act on from this file alone

**`D310-RESIDUALS` — one follow-up outliving the executed rotation.** (a) **User action:**
re-paste the current secret into any browser holding the dead one in `localStorage` — it now fails
as an unexplained 404, and the stale copies are neither enumerable nor clearable from AWS or the
repo. This cannot be verified from the repository side; the row stays until the user says it is
done or declares no such browser exists. Resolved 2026-08-24 (D-437): (b) the
`make load-staging-learning` docker env pass-through is **measured clear** on the D-310 channel —
zero argv/process-title occurrences across six in-flight samples of the exact mechanism, name-only
`-e`; the residual same-user `ps -E` env visibility is inherent to env passing and is not the
D-310 class. (c) `e2e/README.md` now documents the post-D-310 fetch-by-id shape.
(d) **Accepted residual:** no standing rotation mechanism was added — a future rotation is again a
manual targeted apply, accepted because the S44 plan deletes these secrets when real auth lands.
D-310 itself is resolved history — see §9's standing framing and the register's `D310-ROTATION`.

### 4.4 Execution queue — the persistent cursor (canonical execution state)

**What this is.** The single ordered choice among the §4 items currently eligible to execute. It
is a cursor over §4, **not a second backlog**: §4 and the register keep owning whether work
exists and what its status is; this queue owns only the order. Single-homed here — no other file
(and no `tasks/` artifact) may carry a competing copy. Only executable engineering work belongs
here: §5 user decisions and §6 blocked/deferred/parked items (including everything D-152
freezes) never enter.

**Selection rule.** On a generic continue/resume request ("continue the project"), the next task
is the **first eligible row below**. The cursor is positional: delete-on-resolve removes finished
rows, so the first row is always NEXT. Nobody reprioritizes this queue during an ordinary
continue — reordering is itself a state change, made here with a dated reason *before* it is
used. A user-named task overrides the queue only when it is legitimately startable and does not
conflict with existing decisions or freeze boundaries.

**Eligibility gate (checked at dispatch, before a Frozen Spec is written).** Verify the first
row against its register entry and primary evidence: (a) still open; (b) prerequisites still
hold; (c) startable now; (d) not made stale by primary evidence; (e) not dependent on an
unresolved UD; (f) not crossing D-152 or any §6 boundary. If it fails the gate, do **not**
silently skip it: reconcile this file per AUTHORITY_MODEL's conflict rules (delete or restate
the §4 row, correct this queue), and only then take the newly valid first row.

**Ownership and advance.** A standalone session or the Orca coordinator advances this queue; an
**Orca executor never selects, reorders, or advances it**. A completed item advances the cursor
only **after** coordinator acceptance and canonical-document reconciliation — in the same update
that deletes the item's §4 row. Entries are register keys plus minimal ordering metadata; the
descriptions stay in §4 and the register.

**Initial ordering (derived 2026-08-21 from the register's explicit priority statements, the
documents' own batching/prerequisite couplings, security/privacy/cost severity, and the two
UD-constrained tails; every §4 key appears exactly once):**

| # | Item(s) | Ordering evidence |
|---|---|---|
| 1 | `RESUME-EVIDENCE-PROGRAM` | **In flight this session** (user-named 2026-08-28, spend-authorized, D-458): a generic continue resumes the program's next experiment per `docs/resume_evidence/MEASUREMENT_PLAN.md` §Execution order (E5.1 ✅ E6.1 ✅; next E3 → E4 → E1 → E2 → E5.2 → E5.3 → the two report documents) |
| 2 | `SILENT-500S` | The only other unblocked engineering item (added 2026-08-29, D-455): an observability defect proven by a live incident — hundreds of 500-class tracebacks invisible to every ERROR filter and alarm. Free, local; the failing case is reproducible in a test |
| 3 | `PII-REDACTION-GAPS` | Added 2026-08-29 (D-458/E6.1): concrete, cheap fixes with a measured baseline already recorded — F-1 case-insensitive URL matching, F-2 span-redactor credential vocabulary rejoined with the log denylist's. Fix AFTER the program's measurement tasks so baselines stay stable |

Everything else in §4 waits on the user: `D310-RESIDUALS` (a) is a user action, and
`WORK-35-LEDGER` plus the staging e2e executions (the solution-rung spec and the
whole-directory re-run) ride UD-2's read-only-session / spend authorization.

---

## 5. Open user decisions (UD-1 … UD-14)

> **These are questions only the user can answer. They are NOT implementation tasks.**
> Do not infer an answer from evidence, and **do not convert one into a D-xxx without the user.**
> Where a default is tagged **[agent may apply]** it only records state or preserves optionality —
> an agent may apply it and say so. Where a default is tagged **[USER ONLY — hold:]** the queue's
> stated action is answer-shaped (applying it would decide the question); an agent applies only the
> hold text and never records an answer, an accepted risk, or a D-xxx.
> Full option analyses:
> [reference/reconciliation-2026-08/USER_DECISION_QUEUE.md](reference/reconciliation-2026-08/USER_DECISION_QUEUE.md).

| UD | Register key | Question (one line) | Blocks? | Default safe action |
|---|---|---|---|---|
| UD-2 | `SPEND-AUTHORIZATION` | Which deferred paid measurements (if any) are worth real spend, and is a time-boxed read-only staging DB session authorized? **Partially answered by conduct 2026-08-29: the user explicitly ordered and funded the stress test (D-456, cents of Bedrock spend). Still unanswered: the read-only DB session and the staging e2e lane** | **Yes (D-442/D-444): the read-only-session half blocks `WORK-35-LEDGER`'s first step, and the e2e-lane spend holds both staging e2e executions** | [agent may apply] Authorize none further; carry each claim as-documented with its `n` and date |
| UD-3 | `BUDGET-GROSS-SPEND` | Is the $20 net monthly budget raised, accepted or re-scoped, and is a gross credit-excluding control wanted before credits run out? | No | [agent may apply] Leave both budgets in place and treat the console-created budget as **load-bearing** — do not delete it during cleanup |
| UD-4 | `RDS-POSTURE` | Is 1-day backup retention / deletion protection off / single-AZ the accepted staging posture, and what does production require? | No | [USER ONLY — hold:] change nothing; add a dated note that the posture is undeclared and that the §2.6 gate criteria were measured on this environment. Recording it as "the deliberate staging answer" is the decision itself. |
| UD-5 | `KPI-ALARM-FLOOR` | Does a product-KPI alarm get created now (which metric, what floor), or is "none while traffic is synthetic" the settled answer to P1-10? | No | [USER ONLY — hold:] change nothing; note (dated) that the alarm floor is undecided, citing the terraform comment. Recording the disabled state as "the answer to P1-10" closes the item. |
| UD-6 | `ALERT-ENDPOINT` | Should the page channel reach an organization address rather than one personal mailbox, and is a separate informational endpoint wanted? | No | [USER ONLY — hold:] change nothing; `RD-01`'s fix landed 2026-08-21 independent of this question, as its false-ALARM noise was a defect, not a decision. Accepting one mailbox is itself the decision. |
| UD-7 | `RETENTION-CLUSTER` | One cluster of seven linked calls: how long minors' data is kept, what enforces it, what guardians are told — it is the first unblocked step toward a launch-gating privacy requirement | No | [agent may apply] Keep dry-run, keep the job unscheduled, add a dated note that the notice obligation now spans five windows across three decisions. Verbatim precondition (D-333): *"Before deleting any eligible checkpoint, run long-term memory consolidation first."* That ordering must be verified implemented before any dry-run flip is even recommended. |
| UD-8 | `ORG-COMMS` | Is the production security report sent, and who signs off the §7-R1 accepted risk? — no code waits on it; the enrollment FAQ gates the guest journey's most obvious question | No | [USER ONLY — hold:] record, with a date, that the report is deliberately unsent and why (the send-status line); sending or closing is the decision. |
| UD-9 | `REQ-32-SAFETY` | Are Bedrock Guardrails adopted, is the "separately approved" safety policy defined, or is SPEC amended to match what exists? | No | [USER ONLY — hold:] change nothing; add a dated note that the chat surface is unscreened and the learning-side screen has one caller and one test — do NOT record an accepted risk without the user. The register's three engineering deliverables (chat-api coverage, a real escalation destination, pinning tests) stay unowned until this is answered. |
| UD-10 | `DISCLOSURES-LEGAL` | Does the first-visit notice ship 8 or 11 disclosures, is counsel engaged, and who owns the §6.1 legal track? — no code waits on it; it gates a launch requirement whose owning session must not start | No | [agent may apply] Record, with a date, that the ruling is outstanding and counsel is not engaged; add an owner field even if it is "user, unscheduled" |
| UD-11 | `LANGSMITH-RETENTION` | What is the LangSmith run-retention setting, and is it acceptable for a product whose users are minors? | No | [agent may apply] Record it as an accepted unknown with a dated note, and take the two-minute console read at the next convenient moment |
| UD-12 | `(six — see below)` | Bundle of **six one-line confirmations**: (a) `DIFFICULTY-TIERS-CONFLICT`, (b) `D141-TRIM`, (c) `PROSE-QUALITY`, (d) `DRIFT-66-NL2SQL`, (e) `REQ-39-ESTIMATED-LEVEL`, (f) `COMMITTED-ORG-DRAFTS` — none blocks current work | No | [USER ONLY for (a) — hold: continue following D-341 (what the code already does), annotate nothing, record no ruling; the conflict is between two explicit user decisions and no default can settle it.] (b)–(f): each has a stated safe default in the queue. |
| UD-14 | `(D-455)` | RDS managed-secret auto-rotation vs ECS task lifetime: disable rotation, automate restart-on-rotation (EventBridge → forced redeploy), schedule restarts, or accept + document the manual restart each ~7 days? **Until answered, the next rotation (≈ 2026-09-04) re-breaks every new staging DB connection unless a deploy or restart follows it** | No (dated risk in §8) | [agent may apply] Change nothing; after any rotation, the D-455 mitigation (`update-service --force-new-deployment`, both services) restores service and an agent may run it when the failure signature appears |
| UD-13 | `LANGSMITH-INGEST` | LangSmith's monthly unique-traces cap is exceeded (classified 2026-08-24, D-436 — every burst line is a 429 "Monthly unique traces usage limit exceeded"): upgrade the plan, add trace sampling, disable staging tracing (which strands the NAT's sole egress consumer, ~$33/mo), or accept a monthly tracing blackout from cap-hit to reset? | No | [agent may apply] Change nothing; carry the classification. Until answered, the tracing leg goes dark each month at the cap and nobody is paged (D-401 routing, by design) |

UD-12's six one-line questions: (a) `DIFFICULTY-TIERS-CONFLICT` — does D-341 (keep
`difficulty_tiers` unchanged) govern over D-322 §7 (edit them to match the judge)? Both are
explicit user decisions. (b) `D141-TRIM` — does D-141 §5's recommendation override the prior
explicit user approval of the trim, or does the approval stand? (c) `PROSE-QUALITY` — is
student-facing prose quality accepted as-is for now? (d) `DRIFT-66-NL2SQL` — is SPEC §5.26.3's
internal NL2SQL pipeline still wanted, deferred, or dropped? (e) `REQ-39-ESTIMATED-LEVEL` — does
the "Current estimated level" wording stand? (f) `COMMITTED-ORG-DRAFTS` — are committed outbound
drafts allowed at all, and which credential-mention policy governs a sent message?

Four items hang off queue entries and must not be lost — **two labelled sub-questions on UD-5**
(the §7-R9 checkpoint-repair tripwire, and — since D-433 — whether
`learning_hint_personalization_outcomes_total` is promoted into the otel EMF allowlist so AWS can
chart/alarm it: +6 learning-api series, COST-25 context; until then it is Prometheus-only) plus **UD-7's REQ-18 invalid-output capture (queue option
(viii))** and **UD-2's read-only DB-session rider**. (UD-1's §2.6 criterion-6 gate-integrity
sub-question was re-homed into **D-426** when UD-1 was answered 2026-08-23: the defensible
reading — the week counts from the first real `JobCompletions` datapoint, earliest satisfaction
2026-08-29 — is applied as the default pending any explicit relaxing ruling.) They outlive their
parent rows: when a UD is answered, re-home its item here or into the resulting D-xxx before
deleting the row. The authoritative 16-entry↔12-question crosswalk is the register's §12.3.

---

## 6. Blocked / deferred / parked

### 6.1 The D-152 integration freeze — frozen by choice, not stuck

**Integration is closed until the user reopens it.** D-152's sequencing decision — finish and test
this codebase against the dev fakes first, then integrate — was reconfirmed **verbatim** by
D-417 §A1 on 2026-08-18: *"D-152 is unchanged and is not 'nearly met' — it is closed until
reopened."* The user reconfirmed it **after** being told the audit lists were empty and the suite
green, so the "finish and test first" condition is explicitly **not** treated as met.

- **Reopen condition: an explicit user statement reopening integration. Not met, and no evidence
  can meet it.** Soliciting it is forbidden. Do not "unblock" this.
- Live prohibitions: no AWS→icrest reachability measurement, no production API URL, no test
  account, no finalizing the §3.1 auth option, no rewriting the MySQL dev fake.
- **Attribution rule:** `F2-ADAPTER-SHAPE`, `F3-DEVTOKEN-S44`, `R8-READ-SCOPE`'s closure path,
  `ARCH-35-ORG-TIME`'s guard, `S43-SCOPE` and `AUTH-OPTION-O1B` cannot progress **because of this
  decision** — never because of an obstacle.
- **Asymmetry worth recording:** S45 (consent, first-visit notice) is **inside** the freeze while
  S50 A7 (GuardDuty, WAF) is **not** — two launch-blocking security items sit in an
  unfrozen-but-unstarted block while one launch-blocking privacy item sits in a frozen one.
- **`ORG-COMMS` (UD-8) is PERMITTED under the freeze** (INT-28) and is live user work, not parked.
- The one engineering obligation *during* the freeze: keep the `ProfileAdapter` seam honest.
- One production fact that must inform product work **now**: `signups.attended = null` is routine,
  so `AttendanceStatus.UNKNOWN` → blocked is a **routine** production path (D-152 §2).
- When the reopen condition is met, the procedure is
  `reference/integration/S42_OPEN_QUESTIONS.md`'s re-entry sequence (A1·A2·A3 → B1·B2 measurement →
  A4 auth) — do not improvise one.

### 6.2 BLOCKED (6) — an external fact or authorization is missing

| Register key | One line | Reopen condition |
|---|---|---|
| `C6-UNATTENDED` | §2.6 criterion 6 arithmetically unsatisfiable yet, and job success unproven | First `JobCompletions` datapoints observed 2026-08-22 — the seven-day confirmed-firing clock for the nightly three runs from that date (earliest satisfiable 2026-08-29); the weekly instrument is now confirmed end-to-end too (D-435: first `memory-consolidate` completion Sunday 2026-08-23 18:30 UTC, ALARM → OK 19:32:55Z), so only the clock and job **success** remain open |
| `DB-CONTENT-VERIFY` | Three DB-content claims unverifiable read-only; one needs a mutation (`WORK-03` closed 2026-08-23 — the D-426 deploy applied migration `8509c0486d8d`) | UD-2 authorizes a read-only session |
| `LANGSMITH-RETENTION` | The retention setting has no in-repo expression and was never read (UD-11) | Open now — a two-minute user console read |
| `ARCH-35-ORG-TIME` | `ORG_TIME_CONFIRMED = false` is deployed; anything time-of-day dependent runs on assumed hours | The org answers, or the user authorises building the D-153 §4 guard early — the guard is a **local** assertion and is buildable now |
| `INT-29-FAQ` | Enrollment FAQ still `draft`; the sole launch gate on the guest journey's canonical question | The org **content owner** answers (do not bundle with operator-audience asks) |
| `DRIFT-85-I7-ALLOWLIST` | The I7 unknown-role metric is named as an invariant's evidence and specified nowhere | S43 opens |

### 6.3 DEFERRED (14) — deliberately not now

| Register key | One line | Reopen condition |
|---|---|---|
| `REQ-27-TOKEN-CONTRACT` | The ten-claim token contract's satisfiability is answerable only at integration — the most legally consequential deferral in the register | Integration start (S44), or an explicit instruction to finalise §3.1 |
| `SEC-18-WAF` | WAF absent; the in-memory rate limiter weakens per task as the service scales | Public launch, or staging serving anything real |
| `DRIFT-12-ADMIN-ROLE` | SPEC's six-role matrix names an admin row with no role and no enforcement | S43/S44 start (a SPEC marker is owed now) |
| `SEC-34-ROLE-ALLOWLIST` | Our-side Tutor/Manager allowlist asserted in four documents and not yet designed | S43/S44 opens |
| `INT-ATTENDANCE-DERIVATION` | `attendanceClaimed` is a fail-open trap; the signups response is PII-bearing | S43 opens (one **fail-open** doc correction is owed now) |
| `F2-ADAPTER-SHAPE` | Direct MySQL versus HTTP API is still the open seam decision | Integration start |
| `F3-DEVTOKEN-S44` | The whole staging `/dev/token` path is scheduled for deletion at S44 | S44 opens |
| `FIRST-VISIT-REVERIFY` | The notice's "True because" rows are dated code measurements | S45 start |
| `ARCH-21-SCHEMA-SPLIT` | Whether to adopt SPEC §5.33.3's six-schema logical split (`learning`, `rag`, `memory`, `checkpoint_learning`, `checkpoint_chat`, `evaluation`) is **genuinely undecided** — no D-number owns it, and the only record that it is **undecided** is open question 5 of the 2026-07-21 projection (post-migration: `archive/2026-07-21-final-architecture-projection.md`; SPEC §5.33.3 still *prescribes* the split as a requirement). **Extraction into ARCHITECTURE.md's open-questions block must precede archival** | Production schema design |
| `COST-17-CLIENT-ERRORS` | The client-error alarm path is correctly deployed and never exercised end to end | The next live-probe session (one synthetic post) |
| `PAID-RUNS-LANE` | Paid generation and measurement scripts were not invoked; no finding depends on them | UD-2 authorises spend |
| `TEST-24-429` | A real HTTP 429 has never **rendered** and stays deliberately open — the *response* half closed 2026-08-29 (D-456: 90 real 429s produced at the API under funded load); what remains is the SPA render | A browser walk during a rate-limited window |
| `IRT-UPGRADE` | The IRT/Bayesian mastery upgrade has no trigger threshold and no owning session | Response volume sufficient for item-response modelling |
| `PY-314-MAJORS` | The Python runtime line is pinned at 3.12 by decision (D-431, 2026-08-23): PRs #1/#8 closed, and dependabot now ignores the python base image in both docker ecosystems — so **nothing will resurface a runtime upgrade on its own; this row is the only reminder** | The user schedules a deliberate runtime-upgrade session (lock re-resolved, wheel availability checked, container scan green) |

### 6.4 PARKED_BY_DECISION (13) — a decision put these down

| Register key | One line | Reopen condition |
|---|---|---|
| `D152-FREEZE` | The governing entry — see §6.1 | Explicit user statement only |
| `S43-SCOPE` | S43's scope is known; rewriting the MySQL dev fake is forbidden. The **seam-honesty check** is a standing obligation, not parked | S43 opens |
| `AUTH-OPTION-O1B` | O1b stays a recommendation, not a decision, until measured right before S44 | Integration start |
| `R8-READ-SCOPE` | Tutor and branch_manager reads are unscoped; writes fail closed. Accepted as §7-R8 with an expiry that a running system cannot trip | Integration reopen, or first real traffic — whichever comes first. **At integration start this MUST be re-presented to the user; it is launch-blocking at that point. Parked ≠ closed.** |
| `INT-10-PEAK-CONCURRENCY` | Parked by **D-153 §3/§6** (purchase withdrawn — not deferred — and the ask held for integration); the 150-concurrent org ask sits behind an unsent message | Integration start; measure peak concurrency then |
| `RD-12-INGRESS` | Parked by **D-152** (DNS records are added at integration time, D-153 §6); documented product hostnames are absent live; staging is reached through two `*.cloudfront.net` domains. **Procedural:** probe those, and a direct-ALB timeout is by design, not an outage | Integration, when the org adds DNS records |
| `WORK-23-RETENTION-JOB-GATING` | Parked by **D-333** (its consolidate-before-delete precondition is the parking condition, not yet verified); the checkpoint-retention job is genuinely unscheduled. Its stated prerequisite is now **half met**: `session-consolidate` has a verified record of firing as of 2026-08-22 (`session_consolidate_job_complete`, threads 5623, written 0, plus its `JobCompletions` datapoint and ALARM → OK). D-333's consolidate-before-delete precondition (§5 UD-7) must still be verified implemented first | UD-7, plus verifying the D-333 precondition is implemented (the firing record now exists) |
| `F4-CRITERION6` | Criterion 6 was closed on an explicit user bypass; its reopen condition is live and was undetectable while `RD-01` silenced the instrument — the instrument was repaired and confirmed 2026-08-22 (nightly three) and 2026-08-23 (the weekly job, D-435), so a waived-firing failure in any of the four is now detectable | A failure in any waived scheduled firing |
| `SEC-17-GUARDDUTY` | GuardDuty is absent as an account fact, by costed decision D-125 | Production posture review, or staging ceasing to be synthetic |
| `IMAGE-WORK-PARK` | Parked by **D-078** (feature deferred); SPEC §5.17's requirements have no subject in the codebase | The user reopens §5.17 — **both** preconditions (incidental-capture privacy with counsel; real-credential footing for scanning and encryption at rest) must be answered first |
| `D342-PARKING` | All question-bank **quantity** coverage work is parked by standing user instruction. Non-quantity defects (wrong answer key, unservable path) remain defects | The user explicitly asks for new problems to be generated |
| `VIDEO-COVERAGE-PARK` | Video coverage parked (D-417 §B5). The figure the park was argued from was 100× stale; live staging shows 102 of 112 skills servable | The user schedules a seeding run and provisions the API key |
| `DRIFT-70-CONSENT-GATE` | Parked by **D-152** (the notice half belongs to frozen session S45, the issuer half to S44); consent **verification** is enforced and fails closed (empty age-band frozenset); the **notice** half is unbuilt. The former carve-out (the frozenset had no pin) resolved 2026-08-21: `packages/shared/tests/test_auth_consent_gate.py` pins the frozenset empty and pins the exemption semantics (mutation-checked) | Notice half at S45; issuer half at S44 |

**Accepted-risk expiries (single-homed here per W-22).** §7-R8: carried in the `R8-READ-SCOPE` row
above. **§7-R9 (checkpoint-repair acceptance, `ARCH-17-COMMIT-SEAM` — narrowed 2026-08-23,
D-432):** the acceptance's subject is now the **commit ordering only** (the saver sharing the
request's connection, D-110 §3): both seams heal and count as of D-432 — mid-finalize in
`checkpoint_reconcile.py`, mid-interrupt inside the resumed `intervention_choice` node — so a
live hit degrades to a re-answer/re-finalize, not a dead end. Unchanged terms: the counter is
charted and **alarmed nowhere**; **any movement in `learning_checkpoint_repairs_total` voids the
acceptance** (read 0.0 lifetime as of 2026-08-26T04:58Z, build `gha-5fa15d491057`, through the
D-448 deploy's task drain). Whether to
alarm it or accept the dashboard cadence is UD-5's sub-question.

Two further accepted residuals belong in this launch-readiness set (W-22; minors-primary product,
same insufficient-stopgap shape as `SEC-18-WAF`):
- **`WORK-42-INTERSTITIAL-BYPASS`** — the external-link interstitial's middle-click/ctrl-click
  bypass is **accepted** (decision recorded in DECISIONS.md; register #163). Expiry: revisit if
  the interstitial is ever presented as a safety control rather than a courtesy.
- **`WORK-44` #2** — anonymous chat rate limiting is a **single shared bucket**, so one hot
  anonymous user can exhaust it for all. Accepted for the pilot; expires at first real traffic
  alongside R8 (register #64).

---

## 7. Known unknowns (2 — one entry-level plus `ARCH-34`'s tfvars half)

**UNKNOWN stays UNKNOWN.** These are not softened into "probably fine". The three
read-resolvable unknowns were closed by reading on 2026-08-26 (D-446: `K5-HINT-INSTRUMENTS`,
`D288-D317-CLOSURE`, `DRIFT-49-MODEL-ROSTER` — the last also fixed, D-447); the two rows left
close only by user action or a policy change, never by reading.

| Unknown | Register key | Named resolution step |
|---|---|---|
| D-192's content | `D192-PHANTOM` | **None exists — irreducible by design.** The one owed remedy — the clarifying sentence scoping the meta-note's "no citation states what it decided" to *code* citations — was written 2026-08-26 (D-453), in place at the note. **Do NOT adopt D-193's description as D-192's content.** This row is a recorded permanent unknown, not open work |
| Whether the deployed image pin is stale | `ARCH-34-REVISION-DRIFT` (half) | **Method-bounded: unreadable by policy.** `terraform.tfvars` is gitignored and deliberately not read; with `adopt_deployed_image = true`, pin staleness is invisible from the control plane. Closable only by the user or a policy change. Standing hazard: **a gitignored tfvars means the tracked tree does not determine the plan.** |

---

## 8. Known drift and operational risks

Every item carries its register key. These are the headline live risks, not the full list.

- **⏰ The RDS rotation clock (D-455 / UD-14): the next managed-secret rotation, expected
  ≈ 2026-09-04, re-breaks every new staging DB connection unless a deploy or task restart
  follows it.** Both RDS instances auto-rotate their master secrets (~7-day cadence); ECS
  resolves them once at task start; established pooled connections survive rotation, so the
  break is invisible until the pool grows — the signature is intermittent
  `InvalidPasswordError` 500s that worsen under load after a quiet period. Mitigation, safe
  for an agent to run on that signature: `aws ecs update-service --force-new-deployment` on
  both services. Detection is currently weak on two counts: the 500s log no JSON ERROR line
  (`SILENT-500S`, §4.1) and no alarm watches new-connection failures.
- **All four heartbeat alarms are confirmed end-to-end** (RD-01 closed, D-435): the nightly
  three cleared 2026-08-22 (`chat-purge` 19:05Z, `retention-purge` 19:11Z,
  `session-consolidate` 19:42Z) and the weekly `memory-consolidate` cleared on its first
  in-window run — Sunday **2026-08-23** 18:30 UTC datapoint, ALARM → OK 2026-08-23T19:32:55Z,
  OK held since (read 2026-08-24 19:50 UTC). The dead-man's switch now works end-to-end for
  all four jobs; job **success** (completion ≠ correctness) stays unproven and is C6's
  remaining question.
- **The alert endpoint is one personal mailbox.** `ALERT-ENDPOINT` / UD-6: exactly two SNS topics,
  both unencrypted, both subscribed to the same personal address; 26 of 34 alarms page it (a
  pre-D-377 count — the register's own caveat; see `ALERT-ENDPOINT`), and
  `informational_notification_email` has no setter anywhere.
- **Gross spend is invisible behind credits.** `BUDGET-GROSS-SPEND` / UD-3: the terraform-managed
  $20 net budget is at ~104.7% while Cost Explorer for 08-01…08-20 shows **usage ≈ $249.93 against
  ≈ $230.29 of credits**. The only gross-spend control is a **console-created $10 budget that
  terraform does not manage** — it is load-bearing and must not be deleted during cleanup. Staging
  Bedrock is real, so **every staging number is a paid measurement.**
- **RDS durability posture.** `RDS-POSTURE` / UD-4: both instances have 1-day backup retention,
  deletion protection **off**, single-AZ — and both instances sit in `us-east-1a`, so one AZ loss
  takes out both databases — default parameter groups, and no document records this as a choice.
  **The §2.6 gate criteria were measured on this environment** — that sentence is owed in writing
  regardless of which option the user picks.
- **LangSmith ingest failed on a quota, and its retention is unknown.** UD-13 + `LANGSMITH-RETENTION`:
  the flapping-alarm event is **classified** (D-436, read 2026-08-24): 4,264 `langsmith.client`
  failures 08-16 → 08-20T04:00Z, **100% HTTP 429 "tenant exceeded usage limits: Monthly unique
  traces usage limit exceeded"** — zero timeout/connection lines, so the NAT leg is exonerated;
  plus one isolated ~1-minute 403 burst (8 lines) on 2026-08-10, self-resolved. Nothing logged
  since 08-20T04Z until the D-448 deploy's traffic — then **fresh 429s on 2026-08-26** (both
  APIs, same "Monthly unique traces usage limit exceeded" body, read during the D-454 error
  sweep), confirming the earlier silence meant little traced traffic, **not recovery** — the cap presumably
  stands until the provider's monthly reset, the remedy fork is UD-13 (user), and the flap
  routing to the quiet topic remains D-401's intended design. Separately, the account's run
  retention for **minors' data** has never been read (UD-11).
- **Free-tier observability is at the wall.** CloudWatch alarm/metric monitors are at
  **10.0/10.0 with a 16.32 forecast**, and X-Ray traces are **91% used** (forecast 148,599 against
  100,000). Any new alarm or trace volume now costs money (`COST-25-ALARM-COUNT`;
  spend-authorization context in `SPEND-AUTHORIZATION`).
- **The last D-310-class exposure path is measured clear** (D-437, 2026-08-24):
  `make load-staging-learning`'s docker env pass-through showed zero argv/process-title
  occurrences across six in-flight samples of the exact mechanism (name-only `-e`); the
  remaining stale-copy risk lives only in operator-browser `localStorage` (§4.3, user action).
- **Method rule (narrowed 2026-08-24, D-439): the image-agreement class of drift is now watched
  mechanically** — a blocking post-deploy deployed-image consistency gate plus the weekly
  `scheduled-controls.yml` run (first dispatch green: run 32783980237, `VERDICT: OK` on
  `gha-898e2fb4270b`; a second manual run 2026-08-26 also green, and the D-448 deploy's own
  blocking post-deploy gate passed on `gha-5fa15d491057` — coverage continuous through
  08-26. **The first *scheduled* firing is due Monday 2026-08-31 07:17 UTC — verify it fired**;
  the workflow landed after 08-24's slot, so no cron has been missed yet, D-445). What still has **no detector**: terraform-vs-deployed drift in general —
  `terraform apply` is absent from the deploy workflow (`F-03-DRIFT-DETECTOR`) and the
  gitignored-tfvars hazard in §7 keeps no mechanical guard (the image check deliberately excludes
  the tfvars pin per D-417 A3).
- **Child-safety screening is a ten-keyword substring screen on one of two minors-facing surfaces**,
  guarded by one test, with no escalation destination beyond a boolean and no Guardrails repo-wide —
  `REQ-32-SAFETY` / UD-9. Nothing else in the active tier will resurface this if UD-9's hold is
  applied.
- **≥11 stale `accepted`/`implemented` decision status tags read as active.** Only the eight worst
  entries are annotated at migration; the full ~120-chain sweep is deliberately not done
  (`STATUS-TAG-CONVENTION`) — a status line of `accepted` is not evidence; grep the topic for later
  entries.

Documentation-layer drift (44 documentation-only entries — SPEC amendment markers, decision-log
status tags, audit-ID namespaces, stale deployed-state claims) is the **canonical-migration
worklist**, tracked in the register rather than here.

---

## 9. D-310 — standing framing: resolved historical remediation

Quoted, single-homed (AUTHORITY_MODEL §5.7): **"D-310 is resolved historical remediation. The
rotation was executed on 2026-08-20. It is a closed incident record, never an active exposure. Any
text implying a live credential exposure is stale and is corrected on sight."** Evidence: the
archived rotation record (`archive/reconciliation-2026-08/REMEDIATION_D310_ROTATION.md`) and
register `D310-ROTATION` (execution timeline, fail-closed probe, CloudTrail access review — the
detail is single-homed there, not here). The one live residual is `D310-RESIDUALS` in §4.3.

---

## 10. Update protocol

- **Who and when — role-aware (CLAUDE.md "Execution modes", AUTHORITY_MODEL §6).** A
  **standalone Claude Code** session updates this file as part of `/end-session`. An **Orca
  coordinator** updates it as part of post-acceptance canonical reconciliation — it is the only
  Orca role that edits it. An **Orca executor** never updates this file; it reports documentation
  impact to the coordinator. In every mode the update covers sections **3, 4 (including the §4.4
  execution queue), 5, 6, 7 and 8**, plus the snapshot header's date and revisions.
- **Delete on resolve.** When an item resolves it is **REMOVED from this file**, not annotated as
  done. Its record lives in DECISIONS (the judgement) and git history (the change). PROJECT_STATE
  accumulating resolved items is exactly the failure mode this file replaces. The same update
  deletes the item's §4.4 queue row, advancing the execution cursor — and only after acceptance
  and reconciliation, never before.
- **Fan-out check before deleting.** Grep the register key across this whole file before removing
  its row. Keys appearing in more than one section (today: `UD-1`, `D310-RESIDUALS`,
  `LANGSMITH-RETENTION`) carry consequences in §3, §5, §6 and
  §8 that are **reversed, not deleted**.
- **§7 is closed by reading — where reading can close it.** The three read-resolvable unknowns
  were closed 2026-08-26 (D-446); the two remaining rows are irreducible/method-bounded and close
  only by user action or a policy change. If a future row is read-resolvable, delete it on the
  read and append the finding to DECISIONS the same session.
- **No chronology in this file, ever.** No session log, no diary, no newest-first stack, no strata
  of point-in-time numbers at different depths. Per-session narration goes to git commit messages
  and to `docs/log/` — **decided by the user 2026-08-20 (DQ-1)**: `docs/log/` is append-only
  (one dated file per session) and **non-authoritative** — historical narration only, never a
  source of current truth, never overriding this file, DECISIONS, SPEC, or primary evidence;
  agents do not read the full log by default; stale entries stay historical rather than being
  rewritten. Rules: `docs/log/README.md`. The `/end-session` skill was reconciled the same day.
- **Dated claims only.** Any number about the deployed system is written with its build SHA and
  its as-of date, per the LB-05 rule in §1.
- **Fixed status vocabulary.** Use the register's dispositions and register keys — the full
  **eleven-value** enum is defined once in `reference/AUTHORITY_MODEL.md` §5.4; only the seven
  open-state values appear in this file (the four terminal values route to the register, per
  delete-on-resolve). No prose statuses.
- **Never invent a decision ID.** `D-190`, `D-191`, `D-192`, `D-329` and `D-363` are **cited but
  never written** — treat them as phantom IDs and never cite them as if they exist.
- **UD entries are not tasks.** They move out of §5 only when the user answers, at which point the
  answer becomes a D-xxx in DECISIONS.

---

## 11. Map of the documentation

**Precedence, one line:** *primary evidence beats this file — this file is a reconciled snapshot,
not primary truth.* Full precedence rules and conflict protocols:
[reference/AUTHORITY_MODEL.md](reference/AUTHORITY_MODEL.md).

**The two ladders, summarized** (full form: AUTHORITY_MODEL §3 — use the right ladder for the
question):

| Question | Ladder | Order |
|---|---|---|
| "What is required?" | A | SPEC **as amended by accepted DECISIONS entries** → a newer accepted decision beats the SPEC text it touches (a status tag of `accepted` is not evidence — grep the topic for later entries) → nothing else is normative: not a plan, a roadmap criterion, a diagram, or a comment |
| "What is true right now?" | B | Primary evidence (code/tests/config for repository state; runtime observation for deployed state — always revision-qualified) → this file's dated snapshot, within its staleness window → an archived document, never (provenance only) |

The layers never flatten: Ladder A settles requirement disputes, Ladder B current-state disputes;
when a fact differs between layers, state both, each with its layer and date. `docs/log/` sits
below every tier — narration, not evidence and not authority (user ruling DQ-1, 2026-08-20).

**Session-label convention (W-35, `RISK-R6.4-SESSION-LABELS`).** Bare session labels are ambiguous
and are always qualified at first use: "C1" names two different sessions (qualify as *content
session C1, 2026-08-11 (D-273)* vs the earlier track); "S43"–"S47" are ROADMAP's frozen sessions
(now in `reference/integration/ROADMAP_FROZEN_SESSIONS.md`) and must not be confused with
PROGRESS's unnumbered self-applied labels — most consequentially, PROGRESS's completed unnumbered
"S45" is **not** ROADMAP's unstarted consent session S45 (the owner of `DISCLOSURES-LEGAL` and
`FIRST-VISIT-REVERIFY` is the ROADMAP one); a bare "§2.6" resolves to `INTEGRATION_PLAN.md` §2.6
(the gate criteria), not SPEC. D-049's translation layer covers old S17–S23 only — outside that
range, translate nothing mechanically.

**The five active documents** (plus repo-root `CLAUDE.md`, the pointer and non-negotiables):

| Document | Role |
|---|---|
| **PROJECT_STATE.md** (this file) | THE entry point. Current state + open work + navigation. Never restates requirements |
| **SPEC.md** | Normative requirements. Amended in place with dated markers and a D-xxx citation |
| **ARCHITECTURE.md** | As-built architecture, including the explicitly-marked open architecture questions |
| **DECISIONS.md** | Append-only decision log; system of record for judgements |
| **TRACEABILITY.md** | The living §2.6 criterion-1 evidence instrument |

**`reference/`** — durable, read on demand: `AUTHORITY_MODEL.md`, `INCIDENT_RESPONSE.md`,
`QUESTION_GENERATION.md`, `HINT_SOLUTION_REVIEW.md`, `U7_CHECKPOINT_CONSOLIDATION.md`,
`CONTENT_COVERAGE.md`, `FIRST_VISIT_NOTICE.md`; `reference/integration/` (the D-152-frozen world,
banner-gated); `reference/org-drafts/`; `reference/audits/`; and
`reference/reconciliation-2026-08/` holding the two live registers this file links into.

**`archive/`** — historical only. Every file carries an ARCHIVED banner and a superseded-by
pointer, indexed by `archive/README.md`. **Nothing under `archive/` is normative**, and nothing
there should be read as current state.

**Read order for a fresh agent.** (1) `CLAUDE.md` for the non-negotiables. (2) **This file** —
§1 for what is deployed, §4/§5 for what is open, §6.1 for what is frozen. (3) The SPEC or
ARCHITECTURE sections the task actually touches. (4) A `reference/` document only when the task
reaches it. (5) `archive/` only for provenance, never for current state. **And the core rule:
consistency is not evidence of correctness** — if two documents agree and the code disagrees, the
code wins and the agreement is the finding.
