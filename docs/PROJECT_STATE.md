# PROJECT_STATE.md

> **PROPOSAL DRAFT (Phase 5, 2026-08-20)** — this is the proposed future `docs/PROJECT_STATE.md`.
> File paths below refer to the POST-MIGRATION tree proposed in `DOCUMENT_MODEL.md`; until the
> migration executes, the underlying documents remain at their current locations.

---

## 1. Snapshot

| Field | Value |
|---|---|
| Reconciliation date | **2026-08-20** (Phase 4 documentation-reconciliation audit) |
| Repository HEAD | **`344f016`** |
| Deployed staging image (both ECS services) | **`gha-44a12dfc9549`** = commit `44a12dfc9549`, 2026-08-18 (D-415) |
| Deployed task definitions | learning `:150` (2/2 running), chat `:148` (1/1 running) — one behind each family's latest (`:151`/`:149`), which are byte-identical no-ops; compare images, not revision numbers (`ARCH-34-REVISION-DRIFT`) |
| Repo-vs-deployed gap | **10 commits**; HEAD is ahead of staging |
| Deploy trigger | **MANUAL** — the workflow `push` trigger stays commented out (D-417 §C9) |

**LB-05 rule (standing discipline).** "Implemented locally" is not "deployed". **Every live number
must be stated with the build SHA it was measured on.** Any claim about current behaviour that
differs between HEAD and staging carries both statuses, explicitly, in §3.

**Staleness rule.** If this snapshot is more than **14 days** old, or if HEAD has moved off
`344f016`, or if the deployed staging image tag no longer matches this header's snapshot,
**re-verify §3, §4.3 and §8 before trusting them.** A dated claim can go stale; an undated
claim lies. Primary evidence (code, tests, config, live AWS reads) always beats this file.

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

## 3. Repository vs deployed (the deploy gap)

Both layers are true in their own right. Neither is "the" current state on its own — all of §3 is
conditional on staging still running `gha-44a12dfc9549`.

**Undeployed at HEAD** (register `LB-05-DEPLOY-GAP`, user decision **UD-1**):

- The whole **B4 escalation series** — D-420 (escalation draft takes the visitor's note),
  D-421 (the same question is not emailed to staff twice), D-422 (note field in the approval modal).
- **C8** (a `ruff format` pass) and **D-423's documentation** (the RAG latency split). Four further
  commits plus HEAD are docs/roadmap-only — the full ten are enumerated in UD-1's queue entry.
- **B4 escalation behaviour has never been observed live**, on any build. There is zero live
  evidence for it until a deploy happens.

**Consequences that matter operationally:**

- Migration **`8509c0486d8d`** (creating `chat_escalation_sends`) is in the repository and is the
  single Alembic head — 37 migrations, base-to-head replay verified. **The table is absent from staging by
  inference** (the creating commit is undeployed; the private RDS was not read —
  `DB-CONTENT-VERIFY`, §6.2), so **D-421's duplicate-send guard is not protecting staging today.**
- **LB-08's measured 10.55 s guest-QA latency is a pre-D-423 number.** Record it with
  `44a12dfc9549` beside it or do not quote it. It is the only untouched pre-optimisation baseline
  for `WORK-01-SCOPE-GUARD`'s ~22% win — a deploy destroys it, so capture it (with its SHA) before
  any deploy.
- `RD-01`'s Python-side fix (§4) is **inert until a deploy**; only its terraform-side variant can
  reach staging without one.
- The deploy pipeline has **no artifact-freshness check** — no content-hash, ETag or digest
  comparison anywhere in the workflow. Its own comment says the SPA curls "would pass against a
  completely stale deployment, and they never touch the API". The documentation claiming a
  content-hash gate is on the migration worklist (`DRIFT-24-ARTIFACT-FRESHNESS` — carried here for
  the operational fact only).
- The e2e instrument itself is not the variable: `journey-student.spec.ts` is byte-identical
  between the deployed build and HEAD.

---

## 4. Active engineering work

27 open engineering entries. Full evidence per entry:
[reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md](reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md).
If any row here and the register disagree, **the register wins** — rows are re-derived from it,
never patched independently. Every key below is a heading anchor in the register (append `#` + the
lowercased key to the link above). `SEC-13-PURGE`, `COST-06-FLUSH` and `REQ-27-FROZENSET` are
established **by code reading**; no executed test reproduces the defective paths
(`NO-NEW-TEST-CODE`).

### 4.1 ACTIVE_REMEDIATION (16) — something built is wrong or silently ineffective

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `RD-01` | Nightly-job dead-man's switch structurally non-functional (hyphen-vs-underscore event names) | See 4.3 — highest priority | engineering |
| `SEC-13-PURGE` | Minors' location coordinates survive cancel and exception paths | See 4.3 | engineering |
| `COST-06-FLUSH` | Duplicate-id flush branch loses paid spend from row, run total and budget gate | See 4.3 | engineering |
| `WORK-40-TZ` | chat-web renders calendar-approval times in the viewer's browser locale — shares one prerequisite with `DRIFT-59-DATE-SHIFT` (export `buildDateLabelFormatter`); whichever lands first, update both rows | See 4.3 | engineering |
| `D310-RESIDUALS` | Three follow-ups surviving the executed D-310 rotation | See 4.3 | user / engineering / docs |
| `LANGSMITH-INGEST` | Trace ingestion failing at volume and flapping; nobody paged by design | Read app/ops log content for `langsmith.client` lines; classify 403 / quota / timeout. A quota or plan-limit cause escalates to a user call | engineering |
| `COST-22-LABEL-PREINIT` | No labelled counter pre-initialises its labels, so low-frequency KPIs are unalarmable until first occurrence | Pre-initialise label sets at import for every labelled counter; batch with `RD-01` as one "silent instrument" fix | engineering |
| `ARCH-17-COMMIT-SEAM` | Checkpoint/domain commit seam is entered by every routine deploy; one seam still open | Fix commit ordering and the mid-interrupt seam, or re-accept with a trippable expiry; read the repair counter's current value first (movement voids the §7-R9 acceptance — see the accepted-risk expiries block in §6.4) | engineering |
| `WORK-24-DUPLICATE-GAIN` | One completed staging thread has two `learning_gain` rows; never investigated | Test the re-entered-finalize hypothesis (same root cause as `ARCH-17-COMMIT-SEAM`), then confirm D-336's fix covers it | engineering |
| `D329-PHANTOM` | Personalized hints ran dead in production; the detection gap is unchanged | Close the detection gap for silently-swallowed background failures (generalises to D-344/D-350); prove end-to-end that a student sees the personalized hint | engineering + docs |
| `D356-FAMILY` | Erasure-guard family has no completeness claim; two entries both claim to be "the third place" | Enumerate every publisher writing the shared state and check each against the guard; then one dated status correction; fix the D-137/D-141/D-356 → D-357 wrong-id citation in both documents (rides W-18) | engineering + docs |
| `REQ-44-REASON-SWEEP` | Reason-code sweep covers 5 of 10 sets and passes vacuously outside the dict | Widen the sweep over all user-facing copy constants, or assert `REASON_MESSAGES` is exhaustive over the ten enum values. Local, cheap | engineering |
| `TEST-05-DESCRIPTIVE-REREAD` | An owed human re-read of SPEC §5.3/§5.36 never fired across four qualifying changes — and both rows sit under the 37-of-37 criterion-1 claim | Perform the re-read, or replace the human habit with a definable trigger ("what counts as an architecture change" is undefined) | engineering + docs |
| `DRIFT-86-COST-RUNBOOK` | The cost-anomaly runbook's `desired_count` lever does not move a live service | Correct the runbook to name `autoscaling_min_capacity`; the scenario is live via `BUDGET-GROSS-SPEND` | engineering |
| `DRIFT-91-ORGTIME-IMPORT` | An app module imports `current_week_key` from the MySQL adapter instead of shared `org_time` | Move the import to shared `org_time`. Seam substance is intact — this is hygiene, not the seam defect CLAUDE.md defines; optionally add an adapter factory (both apps construct `MySQLProfileAdapter` directly in `main.py`) | engineering |
| `BATCH-LOW-UNSCHEDULED-CONTROLS` | Three built controls nothing invokes — the PII log scanner (**one historical clean run, no continuous assurance**), `make image-check`, retention CLI job reporting. Batch of six; four members routed elsewhere | Wire `scan-logs` into CI or a schedule; wire `make image-check` into CI/deploy and document it; add `report_job_complete` to `checkpoint_retention_cli` | engineering |

### 4.2 ACTIVE_IMPLEMENTATION (11) — decided or specified, not built

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `REQ-27-FROZENSET` | Nothing pins the fail-closed COPPA age-band frozenset empty; a future addition opens the gate with a green suite | One test pinning the frozenset empty, one pinning `account_refusal_reason`. Pair with `SEC-13-PURGE` and `COST-06-FLUSH` as one "fail-closed invariants have no pins" package — three tests, no spend | engineering |
| `WORK-01-SCOPE-GUARD` | `scope_guard`/retrieval overlap is specified and measured (~22% median win) and not built | Build D-423 steps 1–3 as specified; verify the wasted-rerank trade-off is still acceptable first; and tell the user (acknowledgement, not a decision): the earlier approval rested on a ~2.5 s embedding estimate that D-423 measured at 124 ms | engineering |
| `COST-10-INPUT-BOUND` | No input-token ceiling in the gateway; cost reserve hard-codes 2000 input tokens | In order: read whether settlement uses actual input tokens; add the input ceiling at the gateway/shared payload layer; stop pricing input at the flat constant | engineering |
| `WORK-35-LEDGER` | U7 consolidation sizing gated on a free staging measurement nobody took | Take the free staging measurement, then hold the design review and size N against the existing 90/90/365 windows. D-420 added redacted visitor free text no retention job covers | engineering |
| `WORK-40` | One of OPEN_DECISIONS #10's three build items is unverified; two are **confirmed built at HEAD** (`stage_narrative_stage` on five response models; the ladder-pause breadcrumb sink) | The third is not a build item — `formatDateLabel` names no symbol; the real formatter is `buildDateLabelFormatter` and its residual is `DRIFT-59-DATE-SHIFT`. Do not re-verify the two built items | engineering |
| `WORK-12-BANNER` | learning-web disconnect-banner condition untested, and it carries two live contradictory statuses | Write the banner test by mocking `useLearningSession` (do not extract the JSX); reconcile the two status lines by reading D-417 §C7's scope and retracting the loser | engineering + docs |
| `WORK-44-DECIDED-NOT-BUILT` | Two closed OPEN_DECISIONS items decided but unverified as built | Verify `react-router` is installed and routing (a named prerequisite for the §5.1.2 first-visit disclosures); run `gh pr list` for the 26-PR backlog | engineering |
| `DRIFT-59-DATE-SHIFT` | The date-only back-a-day shift is still armed under an "ALL DECIDED" heading | Fix the date-only shift; export or relocate `buildDateLabelFormatter` so it is unit-testable — the same move closes `WORK-40-TZ` | engineering |
| `WORK-13-FIXTURES` | Single-spec e2e isolation is behaviourally resolved **on `gha-44a12dfc9549`**; the **17-spec cross-spec contention scope stays open** (never re-run) and the test-side fixture fix is owed | Land the fixture-isolation fix across the seventeen specs sharing `studentPresent` (prerequisite for UD-2's whole-directory arm — the paid re-run is `DRIFT-58`'s residual, reopened by UD-2); do not re-run the closed one-file scope. Order against UD-1 — a deploy changes the build under test | engineering + docs |
| `M3-D370-SOLUTION-RUNG` | The solution terminal rung has no staging e2e coverage, under a roadmap-closing ✅ | Write the staging e2e coverage for the solution terminal rung | engineering + docs |
| `BATCH-LOW-NARROW-COVERAGE` | Coverage narrower than the claim; three small code gaps | Add the synthesis-time status/effective-window predicate; widen or assert exhaustiveness on the reason sweep; **redact span events** in the trace-boundary redactor (highest value — a credential inside a span event is not redacted today) | engineering |

### 4.3 The five items an agent should be able to act on from this file alone

**`RD-01` — the nightly-job dead-man's switch cannot ever fire.** Deployed CloudWatch metric-filter
patterns match **hyphenated** event names (`session-consolidate_job_complete`, and the same for
`chat-purge`, `retention-purge`, `memory-consolidate`); the Python emitter produces **underscored**
ones. Both sides are internally consistent and mutually incompatible, and unchanged at HEAD.
`JobCompletions` has **never published a single datapoint** (0 across four `job` dimensions over
14 days). All four alarms have exactly one state transition in their history,
`INSUFFICIENT_DATA → ALARM` on 2026-08-16/17 — a **permanent false ALARM to the confirmed page
mailbox**. Fix = a one-line change on exactly ONE side: stop rewriting hyphens in
the hyphen-rewrite line in `packages/observability/.../scheduled_jobs.py` (`job.replace('-','_')`,
line 61 as of 2026-08-20), **or** build the pattern from an underscored key in the pattern
interpolation in `terraform/modules/observability/app_events.tf` (`${each.key}_job_complete`,
line 173 as of 2026-08-20). Deploy-cost asymmetry: the terraform side is
`apply`-only, the Python side needs a full image build and deploy (so it depends on UD-1). Then wait
≥1 nightly firing, confirm ALARM→OK, and **add the missing cross-boundary parity test** (a second
deliverable, not polish). Do **not** "fix" the matching attributes — period, threshold, statistic,
dimensions and `treat_missing_data` all match exactly. Job **success** stays unproven independently
of this fix: the log streams prove invocation, not outcome.

**`SEC-13-PURGE` — minors' precise coordinates can survive a cancelled turn.**
`purge_resume_writes` has exactly one trigger; a cancelled location-consent resume returns before
the purge, and any exception inside `_run_turn` skips it, leaving precise coordinates in
`checkpoint_writes.__resume__`. No test names `purge_resume_writes`, and **no test covers the cancel
or exception path** — but the success path's effect *is* asserted, with a vacuity control, in
`apps/chat-api/tests/test_chat_endpoints.py` (the locator-turn and parameterized `__resume__`
assertions); deleting the call site would fail those two tests. The gap is the cancel/exception
paths only (the Phase-4 "zero tests" claim was a symbol-grep, corrected here). Fix: (1) write the
cancel-path test FIRST so the leak is demonstrable, (2) move the purge into a `finally` so cancel
and exception paths are covered. Closable locally against dev fakes, no paid dependency. Ranked
first of three new-test candidates. The leak is **durable**: no retention job covers
`checkpoint_writes.__resume__` rows for live threads (`RETENTION-CLUSTER` / UD-7). Green
branch-locator tests (REQ-28/SEC-12) must **not** be read as covering this.

**`COST-06-FLUSH` — a real cost bug.** In `packages/curriculum/.../pipeline_cli.py`, `run_plan`'s
flush-time `IntegrityError` branch rolls back and `continue`s **before** `spend += outcome.cost_cents`,
so real spend reaches neither the row, nor `summary.total_cost_cents`, nor the run-budget total. No
test forces it. Fix: write the test forcing an `IntegrityError` inside the flush (a fake gateway
suffices — no paid run), then reorder so `spend +=` and `_settle` run before the `continue`. Verify
the budget-overrun consequence rather than asserting it. The pipeline is parked by D-342 (§6.4
`D342-PARKING`) — the register's reason this is MEDIUM, not HIGH; the fix is still owed because the
next authorised run loses the spend silently.

**`WORK-40-TZ` — a human-approval surface renders the wrong time.**
`apps/chat-web/src/screens/CalendarActionModal.tsx` calls `date.toLocaleString()` with no `timeZone`
and no locale, so calendar times render in the **viewer's** browser zone — on a surface governed by
non-negotiable rule 4 (every external action needs human approval). The learning-web fix (D-324)
never crossed the app boundary and is module-private. Fix: export or relocate
`buildDateLabelFormatter` to a shared module (this also closes `DRIFT-59-DATE-SHIFT`'s
untestability), then fix `CalendarActionModal` and land a unit test with it.

**`D310-RESIDUALS` — three follow-ups outliving the executed rotation.** (a) **User action:**
re-paste the current secret into any browser holding the dead one in `localStorage` — it now fails
as an unexplained 404, and the stale copies are neither enumerable nor clearable from AWS or the
repo. (b) **Engineering:** `make load-staging-learning`'s docker env pass-through was never
re-measured for `ps` visibility — on that path the D-310 exposure class is **unmeasured, not
cleared**. (c) **Documentation:** `e2e/README.md` still documents the pre-D-310 export shape.
(d) **Accepted residual:** no standing rotation mechanism was added — a future rotation is again a
manual targeted apply, accepted because the S44 plan deletes these secrets when real auth lands.
D-310 itself is resolved history — see §9's standing framing and the register's `D310-ROTATION`.

---

## 5. Open user decisions (UD-1 … UD-12)

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
| **UD-1** | `LB-05-DEPLOY-GAP` | Deploy the 10 undeployed commits to staging now, before the next session, or after it? — no live verification of the B4 series is possible without it | **Yes, partially** | [agent may apply] Don't deploy; state the build SHA beside every live number and record LB-08's baseline now |
| UD-2 | `SPEND-AUTHORIZATION` | Which deferred paid measurements (if any) are worth real spend, and is a time-boxed read-only staging DB session authorized? | No | [agent may apply] Authorize none; carry each claim as-documented with its `n` and date |
| UD-3 | `BUDGET-GROSS-SPEND` | Is the $20 net monthly budget raised, accepted or re-scoped, and is a gross credit-excluding control wanted before credits run out? | No | [agent may apply] Leave both budgets in place and treat the console-created budget as **load-bearing** — do not delete it during cleanup |
| UD-4 | `RDS-POSTURE` | Is 1-day backup retention / deletion protection off / single-AZ the accepted staging posture, and what does production require? | No | [USER ONLY — hold:] change nothing; add a dated note that the posture is undeclared and that the §2.6 gate criteria were measured on this environment. Recording it as "the deliberate staging answer" is the decision itself. |
| UD-5 | `KPI-ALARM-FLOOR` | Does a product-KPI alarm get created now (which metric, what floor), or is "none while traffic is synthetic" the settled answer to P1-10? | No | [USER ONLY — hold:] change nothing; note (dated) that the alarm floor is undecided, citing the terraform comment. Recording the disabled state as "the answer to P1-10" closes the item. |
| UD-6 | `ALERT-ENDPOINT` | Should the page channel reach an organization address rather than one personal mailbox, and is a separate informational endpoint wanted? | No | [USER ONLY — hold:] change nothing; fix `RD-01` regardless — the false-ALARM noise is a defect, not a decision. Accepting one mailbox is itself the decision. |
| UD-7 | `RETENTION-CLUSTER` | One cluster of seven linked calls: how long minors' data is kept, what enforces it, what guardians are told — it is the first unblocked step toward a launch-gating privacy requirement | No | [agent may apply] Keep dry-run, keep the job unscheduled, add a dated note that the notice obligation now spans five windows across three decisions. Verbatim precondition (D-333): *"Before deleting any eligible checkpoint, run long-term memory consolidation first."* That ordering must be verified implemented before any dry-run flip is even recommended. |
| UD-8 | `ORG-COMMS` | Is the production security report sent, and who signs off the §7-R1 accepted risk? — no code waits on it; the enrollment FAQ gates the guest journey's most obvious question | No | [USER ONLY — hold:] record, with a date, that the report is deliberately unsent and why (the send-status line); sending or closing is the decision. |
| UD-9 | `REQ-32-SAFETY` | Are Bedrock Guardrails adopted, is the "separately approved" safety policy defined, or is SPEC amended to match what exists? | No | [USER ONLY — hold:] change nothing; add a dated note that the chat surface is unscreened and the learning-side screen has one caller and one test — do NOT record an accepted risk without the user. The register's three engineering deliverables (chat-api coverage, a real escalation destination, pinning tests) stay unowned until this is answered. |
| UD-10 | `DISCLOSURES-LEGAL` | Does the first-visit notice ship 8 or 11 disclosures, is counsel engaged, and who owns the §6.1 legal track? — no code waits on it; it gates a launch requirement whose owning session must not start | No | [agent may apply] Record, with a date, that the ruling is outstanding and counsel is not engaged; add an owner field even if it is "user, unscheduled" |
| UD-11 | `LANGSMITH-RETENTION` | What is the LangSmith run-retention setting, and is it acceptable for a product whose users are minors? | No | [agent may apply] Record it as an accepted unknown with a dated note, and take the two-minute console read at the next convenient moment |
| UD-12 | `(six — see below)` | Bundle of **six one-line confirmations**: (a) `DIFFICULTY-TIERS-CONFLICT`, (b) `D141-TRIM`, (c) `PROSE-QUALITY`, (d) `DRIFT-66-NL2SQL`, (e) `REQ-39-ESTIMATED-LEVEL`, (f) `COMMITTED-ORG-DRAFTS` — none blocks current work | No | [USER ONLY for (a) — hold: continue following D-341 (what the code already does), annotate nothing, record no ruling; the conflict is between two explicit user decisions and no default can settle it.] (b)–(f): each has a stated safe default in the queue. |

UD-12's six one-line questions: (a) `DIFFICULTY-TIERS-CONFLICT` — does D-341 (keep
`difficulty_tiers` unchanged) govern over D-322 §7 (edit them to match the judge)? Both are
explicit user decisions. (b) `D141-TRIM` — does D-141 §5's recommendation override the prior
explicit user approval of the trim, or does the approval stand? (c) `PROSE-QUALITY` — is
student-facing prose quality accepted as-is for now? (d) `DRIFT-66-NL2SQL` — is SPEC §5.26.3's
internal NL2SQL pipeline still wanted, deferred, or dropped? (e) `REQ-39-ESTIMATED-LEVEL` — does
the "Current estimated level" wording stand? (f) `COMMITTED-ORG-DRAFTS` — are committed outbound
drafts allowed at all, and which credential-mention policy governs a sent message?

Four items hang off queue entries and must not be lost — **two labelled sub-questions** (UD-1's
§2.6 criterion-6 gate-integrity question; UD-5's §7-R9 checkpoint-repair tripwire) plus **UD-7's
REQ-18 invalid-output capture (queue option (viii))** and **UD-2's read-only DB-session rider**.
They outlive their parent rows: when a UD is answered, re-home its item here or into the resulting
D-xxx before deleting the row. The authoritative 16-entry↔12-question crosswalk is the register's
§12.3.

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
| `C6-UNATTENDED` | §2.6 criterion 6 arithmetically unsatisfiable yet, and job success unproven | `RD-01` fixed **and deployed**, plus seven days of confirmed firings |
| `DB-CONTENT-VERIFY` | Four DB-content claims unverifiable read-only; one needs a mutation | UD-2 authorizes a read-only session, or the UD-1 deploy closes WORK-03 by itself |
| `LANGSMITH-RETENTION` | The retention setting has no in-repo expression and was never read (UD-11) | Open now — a two-minute user console read |
| `ARCH-35-ORG-TIME` | `ORG_TIME_CONFIRMED = false` is deployed; anything time-of-day dependent runs on assumed hours | The org answers, or the user authorises building the D-153 §4 guard early — the guard is a **local** assertion and is buildable now |
| `INT-29-FAQ` | Enrollment FAQ still `draft`; the sole launch gate on the guest journey's canonical question | The org **content owner** answers (do not bundle with operator-audience asks) |
| `DRIFT-85-I7-ALLOWLIST` | The I7 unknown-role metric is named as an invariant's evidence and specified nowhere | S43 opens |

### 6.3 DEFERRED (15) — deliberately not now

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
| `ARCH-33-CI-GATE` | Whether the deploy version gate ever fired, and whether the PR backlog cleared, are unread GitHub facts | n/a — run `gh run list` and `gh pr list` |
| `COST-17-CLIENT-ERRORS` | The client-error alarm path is correctly deployed and never exercised end to end | The next live-probe session (one synthetic post) |
| `PLAYWRIGHT-LANE` | The browser lane was not executed, so the one new implementation defect has no runnable guard | A serialized test window (never concurrent with `make test`) |
| `PAID-RUNS-LANE` | Paid generation and measurement scripts were not invoked; no finding depends on them | UD-2 authorises spend |
| `TEST-24-429` | A real HTTP 429 has never rendered and stays deliberately open | A funded load test |
| `IRT-UPGRADE` | The IRT/Bayesian mastery upgrade has no trigger threshold and no owning session | Response volume sufficient for item-response modelling |

### 6.4 PARKED_BY_DECISION (13) — a decision put these down

| Register key | One line | Reopen condition |
|---|---|---|
| `D152-FREEZE` | The governing entry — see §6.1 | Explicit user statement only |
| `S43-SCOPE` | S43's scope is known; rewriting the MySQL dev fake is forbidden. The **seam-honesty check** is a standing obligation, not parked | S43 opens |
| `AUTH-OPTION-O1B` | O1b stays a recommendation, not a decision, until measured right before S44 | Integration start |
| `R8-READ-SCOPE` | Tutor and branch_manager reads are unscoped; writes fail closed. Accepted as §7-R8 with an expiry that a running system cannot trip | Integration reopen, or first real traffic — whichever comes first. **At integration start this MUST be re-presented to the user; it is launch-blocking at that point. Parked ≠ closed.** |
| `INT-10-PEAK-CONCURRENCY` | The capacity purchase was **withdrawn** (not deferred); the 150-concurrent org ask is parked behind an unsent message | Integration start; measure peak concurrency then |
| `RD-12-INGRESS` | Documented product hostnames are absent live; staging is reached through two `*.cloudfront.net` domains. **Procedural:** probe those, and a direct-ALB timeout is by design, not an outage | Integration, when the org adds DNS records |
| `WORK-23-RETENTION-JOB-GATING` | The checkpoint-retention job is genuinely unscheduled — and **`RD-01` silently blocks its stated prerequisite** (a record of firing) — and D-333's consolidate-before-delete precondition (§5 UD-7) must be verified implemented first | The consolidate job has a verified record of firing, plus UD-7 |
| `F4-CRITERION6` | Criterion 6 was closed on an explicit user bypass; its reopen condition is live and **currently undetectable** because `RD-01` silences the instrument | A failure in any waived scheduled firing |
| `SEC-17-GUARDDUTY` | GuardDuty is absent as an account fact, by costed decision D-125 | Production posture review, or staging ceasing to be synthetic |
| `IMAGE-WORK-PARK` | SPEC §5.17's solution-image requirements have no subject in the codebase | The user reopens §5.17 — **both** preconditions (incidental-capture privacy with counsel; real-credential footing for scanning and encryption at rest) must be answered first |
| `D342-PARKING` | All question-bank **quantity** coverage work is parked by standing user instruction. Non-quantity defects (wrong answer key, unservable path) remain defects | The user explicitly asks for new problems to be generated |
| `VIDEO-COVERAGE-PARK` | Video coverage parked (D-417 §B5). The figure the park was argued from was 100× stale; live staging shows 102 of 112 skills servable | The user schedules a seeding run and provisions the API key |
| `DRIFT-70-CONSENT-GATE` | Consent **verification** is enforced and fails closed (empty age-band frozenset); the **notice** half is unbuilt. Carve-out **not parked**: the frozenset has no pin — §4.2 `REQ-27-FROZENSET` | Notice half at S45; issuer half at S44 |

**Accepted-risk expiries (single-homed here per W-22).** §7-R8: carried in the `R8-READ-SCOPE` row
above. **§7-R9 (checkpoint-repair acceptance, `ARCH-17-COMMIT-SEAM`):** the repair counter is
charted and **alarmed nowhere**; **any movement in `learning_checkpoint_repairs_total` voids the
acceptance**. Whether to alarm it or accept the dashboard cadence is UD-5's sub-question.

---

## 7. Known unknowns (5 — four entry-level plus `ARCH-34`'s tfvars half)

**UNKNOWN stays UNKNOWN.** These are not softened into "probably fine". Each has a named
resolution step; three of them are cheap.

| Unknown | Register key | Named resolution step |
|---|---|---|
| D-192's content | `D192-PHANTOM` | **None exists — irreducible by design.** The whole remedy is one clarifying sentence scoping the meta-note's "no citation states what it decided" to *code* citations. **Do NOT adopt D-193's description as D-192's content.** |
| D-264's annotation state | `K5-HINT-INSTRUMENTS` | **Read D-264** — its status tag and any in-place correction. One targeted read converts this entry to documentation-only. |
| Whether D-317 closes D-288's product defect | `D288-D317-CLOSURE` | **Read both bodies** (D-288, and D-317 plus its addendum) and determine whether the named defect is closed. Do not let "D-288 resolved" retire its three other live findings. |
| The intended model roster | `DRIFT-49-MODEL-ROSTER` | **Check DECISIONS and git history for the intended roster**; if that does not settle it, ask the user — the operative `.env` is forbidden to read. The placeholder `claude-sonnet-5` defaults are fixable **without any decision** and should not wait. (The ask-the-user half is deliberately not a queue entry: it fires only if DECISIONS and git history fail to settle it. The placeholder-default fix needs no decision and should not wait.) |
| Whether the deployed image pin is stale | `ARCH-34-REVISION-DRIFT` (half) | **Method-bounded: unreadable by policy.** `terraform.tfvars` is gitignored and deliberately not read; with `adopt_deployed_image = true`, pin staleness is invisible from the control plane. Closable only by the user or a policy change. Standing hazard: **a gitignored tfvars means the tracked tree does not determine the plan.** |

---

## 8. Known drift and operational risks

Every item carries its register key. These are the headline live risks, not the full list.

- **A permanently false alarm is training the operator to ignore the page mailbox.** `RD-01`'s four
  nightly-heartbeat alarms have been in ALARM continuously **since 2026-08-16/17**, routed to the
  page channel with actions enabled. This is a defect, not a decision, and it should be fixed
  before UD-6 is even discussed.
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
- **LangSmith ingest is failing at volume, and its retention is unknown.** `LANGSMITH-INGEST` +
  `LANGSMITH-RETENTION`: `LangSmithIngestFailed` 14-day sums are **learning-api 2800 /
  chat-api 1441**, each alarm records 10 state transitions in ~2 days (five OK→ALARM→OK cycles on
  learning-api), and it routes to the quiet informational topic on the same single mailbox. The
  cause is undetermined. Separately, the account's run retention for **minors' data** has never
  been read.
- **Free-tier observability is at the wall.** CloudWatch alarm/metric monitors are at
  **10.0/10.0 with a 16.32 forecast**, and X-Ray traces are **91% used** (forecast 148,599 against
  100,000). Any new alarm or trace volume now costs money (`COST-25-ALARM-COUNT`;
  spend-authorization context in `SPEND-AUTHORIZATION`).
- **A D-310-class exposure is unmeasured on one path.** `D310-RESIDUALS` item (b): `ps` visibility
  of the docker env pass-through was never re-measured. **Unmeasured, not cleared.**
- **Method rule (carried forward): no automated drift detector exists.** `terraform apply` is absent
  from the deploy workflow and nothing compares deployed reality to the tracked tree
  (`F-03-DRIFT-DETECTOR`), which is why the gitignored-tfvars hazard in §7 has no mechanical guard.
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
detail is single-homed there, not here). The three live residuals are `D310-RESIDUALS` in §4.3.

---

## 10. Update protocol

- **Who and when.** Whoever closes a working session updates this file as part of `/end-session` —
  sections **3, 4, 5, 6, 7 and 8**, plus the snapshot header's date and revisions.
- **Delete on resolve.** When an item resolves it is **REMOVED from this file**, not annotated as
  done. Its record lives in DECISIONS (the judgement) and git history (the change). PROJECT_STATE
  accumulating resolved items is exactly the failure mode this file replaces.
- **Fan-out check before deleting.** Grep the register key across this whole file before removing
  its row. Keys appearing in more than one section (today: `RD-01`, `UD-1`, `D310-RESIDUALS`,
  `WORK-40-TZ`/`DRIFT-59-DATE-SHIFT`, `LANGSMITH-RETENTION`) carry consequences in §3, §5, §6 and
  §8 that are **reversed, not deleted**.
- **§7 is closed by reading.** Three of the five unknowns resolve with a targeted document read; if
  a session performs one, delete the row and append the finding to DECISIONS the same session.
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
