# PROJECT_STATE.md

This is the entry point: current state, open work, and navigation. In force since 2026-08-20,
when the documentation reconciliation migration executed. Precedence:
[reference/AUTHORITY_MODEL.md](reference/AUTHORITY_MODEL.md) — primary evidence beats this file.

---

## 1. Snapshot

| Field | Value |
|---|---|
| Snapshot date | **2026-08-23** (standalone sessions: D-428 `DRIFT-86` runbook fix, D-429 `WORK-44` verified closed, D-430 `DEP-PR-BATCH-2026-08-21` merged; earlier same day — eighth Orca run: DRIFT-91, D-427) |
| Last product-code commit | **`fb1ec87`** (2026-08-24 UTC) — the 12 dependabot patch/minor merges (D-430); before them `1768c9d` (DRIFT-91, PR #377) |
| Deployed staging image (both ECS services) | **`gha-898e2fb4270b`** = commit `898e2fb` (product code `67cd708`), deployed 2026-08-23 (D-426, run 32613654181) |
| Deployed task definitions | learning `:152` (2/2 running), chat `:150` (1/1 running) — compare images, not revision numbers (`ARCH-34-REVISION-DRIFT`) |
| Repo-vs-deployed gap | **16 product commits** (`898e2fb` → `fb1ec87`: the SPA date-zone pair — both defects live on staging until the next deploy — the behavior-identical DRIFT-91 relocation, and the 12 dependabot patch/minor bumps, D-430). The scheduled-job **metric filters (2026-08-21) and heartbeat alarm windows (2026-08-22)** were applied via control-plane `terraform apply` (§8) |
| Deploy trigger | **MANUAL** — the workflow `push` trigger stays commented out (D-417 §C9) |

**LB-05 rule (standing discipline).** "Implemented locally" is not "deployed". **Every live number
must be stated with the build SHA it was measured on.** Any claim about current behaviour that
differs between HEAD and staging carries both statuses, explicitly, in §3.

**Staleness rule.** If this snapshot is more than **14 days** old, or if any **product-code**
commit lands after `fb1ec87`, or if the deployed staging image tag no longer matches this
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

**The D-426 deploy (2026-08-23, run 32613654181) shipped `gha-898e2fb4270b`** (product code
`67cd708`) to both services with all workflow gates green (deployed-version, `/dev/token` edge,
canary bake — rollback skipped, smoke through CloudFront). **The gap reopened the same day with
the D-324 date-zone pair** (`8e82ba9` + `805e986`): the SPA date-rendering fixes are at HEAD
only, so staging still renders calendar-approval times in the viewer's zone and date-only labels
with the back-a-day edge until the next deploy. **The 12 dependabot patch/minor merges (D-430,
landed 2026-08-24 UTC)** widened the gap to 16 commits: each merged with 9/9 CI checks green and
the full local suite green on the merged HEAD; staging is unaffected until the next deploy.

**Facts from the D-426 deploy:**

- Migration **`8509c0486d8d`** (`chat_escalation_sends`) **applied 2026-08-23** — D-421's
  duplicate-send guard now protects staging, and `WORK-03` is closed (the one DB-content claim
  the deploy could settle; the rest stay with `DB-CONTENT-VERIFY`, §6.2).
- **The B4 escalation series (D-420/421/422) is now deployed but still never observed live.**
  Its evidence is CI plus this deploy's gates; a live re-walk (UD-1 Option A's second half)
  remains available work for the next live-probe session.
- **LB-08's 10.55 s pre-optimisation baseline is recorded durably in D-426** (measured on
  `gha-44a12dfc9549`, now unreproducible). Post-optimisation comparisons for
  `WORK-01-SCOPE-GUARD` cite D-426, not this file.
- **COST-22's pre-initialised label series are live** (verified post-deploy:
  `qa_service_degraded_total` exposes all three `stage` series in the deployed chat-api
  namespace) — the ~34 always-present custom-metric series upper bound is now the account's
  actual state (cost context: UD-3/COST-25).
- The §7-R9 tripwire held through the deploy's task drain: `learning_checkpoint_repairs_total`
  read 0.0 before and after (2026-08-23T03:1xZ) — the `ARCH-17-COMMIT-SEAM` acceptance is
  intact.
- The deploy pipeline still has **no artifact-freshness check for the SPAs** — no content-hash,
  ETag or digest comparison; the SPA curls "would pass against a completely stale deployment"
  (`DRIFT-24-ARTIFACT-FRESHNESS` — carried here for the operational fact only). The
  deployed-version gate covers the API images, not the static assets.

---

## 4. Active engineering work

14 open engineering entries. Full evidence per entry:
[reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md](reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md).
If any row here and the register disagree, **the register wins** — rows are re-derived from it,
never patched independently. Every key below is a heading anchor in the register (append `#` + the
lowercased key to the link above), except post-migration discoveries, which name their evidence
home inline (none today; the convention was set by `DEP-PR-BATCH-2026-08-21` → D-429, resolved
by D-430). The `NO-NEW-TEST-CODE` category is **closed**: all three
defects the audit established by code reading only (REQ-27, SEC-13, COST-06) gained executed
tests on 2026-08-21/22.

### 4.1 ACTIVE_REMEDIATION (9) — something built is wrong or silently ineffective

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `RD-01` | Dead-man's switch confirmed for the three nightly jobs 2026-08-22; the weekly job's window fix is **built and applied live** the same day (`4a5ad20`; period 604800 — CloudWatch's one-week maximum, so it pages after the *first* missed Sunday; the 2×-cadence ideal was refused by the API) | Confirmation only: after the **Sunday 2026-08-24 18:30 UTC** run, read `JobCompletions{job=memory-consolidate}` and confirm ALARM → OK; then delete this row (the last of RD-01) — see 4.3 | engineering |
| `D310-RESIDUALS` | Three follow-ups surviving the executed D-310 rotation | See 4.3 | user / engineering / docs |
| `LANGSMITH-INGEST` | Trace ingestion failing at volume and flapping; nobody paged by design | Read app/ops log content for `langsmith.client` lines; classify 403 / quota / timeout. A quota or plan-limit cause escalates to a user call | engineering |
| `ARCH-17-COMMIT-SEAM` | Checkpoint/domain commit seam is entered by every routine deploy; one seam still open | Fix commit ordering and the mid-interrupt seam, or re-accept with a trippable expiry; read the repair counter's current value first (movement voids the §7-R9 acceptance — see the accepted-risk expiries block in §6.4) | engineering |
| `WORK-24-DUPLICATE-GAIN` | One completed staging thread has two `learning_gain` rows; never investigated | Test the re-entered-finalize hypothesis (same root cause as `ARCH-17-COMMIT-SEAM`), then confirm D-336's fix covers it | engineering |
| `D329-PHANTOM` | Personalized hints ran dead in production; the detection gap is unchanged | Close the detection gap for silently-swallowed background failures (generalises to D-344/D-350); prove end-to-end that a student sees the personalized hint | engineering + docs |
| `D356-FAMILY` | Erasure-guard family has no completeness claim; two entries both claim to be "the third place" | Enumerate every publisher writing the shared state and check each against the guard; then one dated status correction; fix the D-137/D-141/D-356 → D-357 wrong-id citation in both documents (rides W-18) | engineering + docs |
| `TEST-05-DESCRIPTIVE-REREAD` | An owed human re-read of SPEC §5.3/§5.36 never fired across four qualifying changes — and both rows sit under the 37-of-37 criterion-1 claim | Perform the re-read, or replace the human habit with a definable trigger ("what counts as an architecture change" is undefined) | engineering + docs |
| `BATCH-LOW-UNSCHEDULED-CONTROLS` | Three built controls nothing invokes — the PII log scanner (**one historical clean run, no continuous assurance**), `make image-check`, retention CLI job reporting. Batch of six; four members routed elsewhere | Wire `scan-logs` into CI or a schedule; wire `make image-check` into CI/deploy and document it; add `report_job_complete` to `checkpoint_retention_cli` | engineering |

### 4.2 ACTIVE_IMPLEMENTATION (5) — decided or specified, not built

| Register key | What it is | Remaining action | Owner |
|---|---|---|---|
| `WORK-01-SCOPE-GUARD` | `scope_guard`/retrieval overlap is specified and measured (~22% median win) and not built | Build D-423 steps 1–3 as specified; verify the wasted-rerank trade-off is still acceptable first; and tell the user (acknowledgement, not a decision): the earlier approval rested on a ~2.5 s embedding estimate that D-423 measured at 124 ms | engineering |
| `COST-10-INPUT-BOUND` | No input-token ceiling in the gateway; cost reserve hard-codes 2000 input tokens | In order: read whether settlement uses actual input tokens; add the input ceiling at the gateway/shared payload layer; stop pricing input at the flat constant | engineering |
| `WORK-35-LEDGER` | U7 consolidation sizing gated on a free staging measurement nobody took | Take the free staging measurement, then hold the design review and size N against the existing 90/90/365 windows. D-420 added redacted visitor free text no retention job covers | engineering |
| `WORK-13-FIXTURES` | Single-spec e2e isolation is behaviourally resolved **on `gha-44a12dfc9549`** (a build no longer deployed — the D-426 deploy shipped `gha-898e2fb4270b`); the **17-spec cross-spec contention scope stays open** (never re-run) and the test-side fixture fix is owed | Land the fixture-isolation fix across the seventeen specs sharing `studentPresent` (prerequisite for UD-2's whole-directory arm — the paid re-run is `DRIFT-58`'s residual, reopened by UD-2); do not re-run the closed one-file scope. The UD-1 ordering constraint is discharged: the deploy happened 2026-08-23, so any re-run now tests the current build | engineering + docs |
| `M3-D370-SOLUTION-RUNG` | The solution terminal rung has no staging e2e coverage, under a roadmap-closing ✅ | Write the staging e2e coverage for the solution terminal rung | engineering + docs |

### 4.3 The two items an agent should be able to act on from this file alone

**`RD-01` — everything is built and applied; one Sunday confirmation remains.** The 2026-08-21
pattern fix (`b06a5df`) was confirmed end-to-end on 2026-08-22: first-ever `JobCompletions`
datapoints, three nightly alarms ALARM → OK (`chat-purge` 19:05:51Z, `retention-purge` 19:11:05Z,
`session-consolidate` 19:42:40Z; long-period alarms evaluate ~1–1.7 h behind their datapoints).
The weekly-job defect that confirmation surfaced (`memory-consolidate` under the uniform 2-day
window = permanent weekly flapping) was fixed and applied the same day: the heartbeat window is
now **per-job** — `min(2 × cadence, 604800)` (`4669ee2` + `4a5ad20`), because CloudWatch refused
the 2×-weekly ideal at apply time (*"EvaluationPeriods * Period must be <= 604800 for alarms
using period >= 3600"*, verbatim). The weekly alarm therefore runs a **7-day window** live
(period 604800, read back 2026-08-22): no flapping, and it pages after the **first** missed
Sunday — more sensitive than the ideal rule, the safe direction for a `retry_attempts = 0`
paid-API job. `test_scheduled_job_heartbeat_cadence_parity.py` (D-385 class) pins the capped
rule and cites the API error. **What remains:** after the Sunday **2026-08-24 18:30 UTC** run,
confirm `JobCompletions{job=memory-consolidate}` publishes and the alarm goes ALARM → OK (its
current ALARM is factually accurate: no completion in the trailing week). Job **success** stays
unproven for all four: the events report completion, not correctness.

**`D310-RESIDUALS` — three follow-ups outliving the executed rotation.** (a) **User action:**
re-paste the current secret into any browser holding the dead one in `localStorage` — it now fails
as an unexplained 404, and the stale copies are neither enumerable nor clearable from AWS or the
repo. (b) **Engineering:** `make load-staging-learning`'s docker env pass-through was never
re-measured for `ps` visibility — on that path the D-310 exposure class is **unmeasured, not
cleared**. (c) **Documentation:** `e2e/README.md` still documents the pre-D-310 export shape.
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
| 1 | `RD-01` (Sunday confirmation) | Restated 2026-08-22 (evening): the weekly-window fix is built and applied live (`4a5ad20`, 7-day capped window); the only remaining step is time-blocked — after the Sunday **2026-08-24 18:30 UTC** run, a free read-only check that `JobCompletions{job=memory-consolidate}` publishes and the alarm goes ALARM → OK (§4.3). If a continue arrives before then, the eligibility gate skips to row 2 after reconciling this note |
| 2 | `ARCH-17-COMMIT-SEAM`, then `WORK-24-DUPLICATE-GAIN` | WORK-24's stated hypothesis is the same root cause as ARCH-17; read the repair counter first — movement voids §7-R9 |
| 3 | `D329-PHANTOM` | Detection gap for silently-swallowed background failures (generalises D-344/D-350) |
| 4 | `D356-FAMILY` | Publisher enumeration, then one dated status correction (rides W-18) |
| 5 | `LANGSMITH-INGEST` | Diagnostic read/classification; a quota or plan-limit cause escalates to a user call — that boundary is why it sits below the purely local fixes |
| 6 | `D310-RESIDUALS` (engineering half (b) only) | Re-measure `ps` visibility of the docker env pass-through; (a) is user action, (c)/(d) are docs/accepted |
| 7 | `TEST-05-DESCRIPTIVE-REREAD` | Perform the owed re-read, or replace the habit with a definable trigger |
| 8 | `BATCH-LOW-UNSCHEDULED-CONTROLS` | Wire the three built-but-uninvoked controls |
| 9 | `COST-10-INPUT-BOUND` | Internally ordered: read whether settlement uses actual input tokens first, then the ceiling |
| 10 | `WORK-01-SCOPE-GUARD` | Larger build (D-423 steps 1–3); includes a user acknowledgement (not a decision) about the corrected embedding estimate |
| 11 | `WORK-35-LEDGER` | Free staging measurement first, then the design review |
| 12 | `WORK-13-FIXTURES` | The UD-1 ordering constraint discharged by the 2026-08-23 deploy; the paid re-run stays with UD-2 |
| 13 | `M3-D370-SOLUTION-RUNG` | Staging e2e is a paid measurement (real Bedrock) in the serialized Playwright lane; verify the UD-2 spend posture at dispatch |

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
| UD-2 | `SPEND-AUTHORIZATION` | Which deferred paid measurements (if any) are worth real spend, and is a time-boxed read-only staging DB session authorized? | No | [agent may apply] Authorize none; carry each claim as-documented with its `n` and date |
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

UD-12's six one-line questions: (a) `DIFFICULTY-TIERS-CONFLICT` — does D-341 (keep
`difficulty_tiers` unchanged) govern over D-322 §7 (edit them to match the judge)? Both are
explicit user decisions. (b) `D141-TRIM` — does D-141 §5's recommendation override the prior
explicit user approval of the trim, or does the approval stand? (c) `PROSE-QUALITY` — is
student-facing prose quality accepted as-is for now? (d) `DRIFT-66-NL2SQL` — is SPEC §5.26.3's
internal NL2SQL pipeline still wanted, deferred, or dropped? (e) `REQ-39-ESTIMATED-LEVEL` — does
the "Current estimated level" wording stand? (f) `COMMITTED-ORG-DRAFTS` — are committed outbound
drafts allowed at all, and which credential-mention policy governs a sent message?

Three items hang off queue entries and must not be lost — **one labelled sub-question** (UD-5's
§7-R9 checkpoint-repair tripwire) plus **UD-7's REQ-18 invalid-output capture (queue option
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
| `C6-UNATTENDED` | §2.6 criterion 6 arithmetically unsatisfiable yet, and job success unproven | First `JobCompletions` datapoints observed 2026-08-22 — the seven-day confirmed-firing clock for the nightly three runs from that date (earliest satisfiable 2026-08-29); the weekly job's instrument stays mis-specified until `RD-01`'s residual lands (§4.3) |
| `DB-CONTENT-VERIFY` | Three DB-content claims unverifiable read-only; one needs a mutation (`WORK-03` closed 2026-08-23 — the D-426 deploy applied migration `8509c0486d8d`) | UD-2 authorizes a read-only session |
| `LANGSMITH-RETENTION` | The retention setting has no in-repo expression and was never read (UD-11) | Open now — a two-minute user console read |
| `ARCH-35-ORG-TIME` | `ORG_TIME_CONFIRMED = false` is deployed; anything time-of-day dependent runs on assumed hours | The org answers, or the user authorises building the D-153 §4 guard early — the guard is a **local** assertion and is buildable now |
| `INT-29-FAQ` | Enrollment FAQ still `draft`; the sole launch gate on the guest journey's canonical question | The org **content owner** answers (do not bundle with operator-audience asks) |
| `DRIFT-85-I7-ALLOWLIST` | The I7 unknown-role metric is named as an invariant's evidence and specified nowhere | S43 opens |

### 6.3 DEFERRED (16) — deliberately not now

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
| `ARCH-33-CI-GATE` | Whether the deploy version gate ever fired is an unread GitHub fact (the PR-backlog half was read 2026-08-23: the 26-PR backlog is cleared down to the two python majors — D-429) | n/a — run `gh run list` |
| `COST-17-CLIENT-ERRORS` | The client-error alarm path is correctly deployed and never exercised end to end | The next live-probe session (one synthetic post) |
| `PLAYWRIGHT-LANE` | The browser lane was not executed, so the one new implementation defect has no runnable guard. Also carries `WORK-12-BANNER`'s C7-consistent residual (D-427, 2026-08-23): write **and run** the learning-web disconnect-visible spec — positive direction only, mirroring chat-web's — in the next lane window; the mock-test route is retracted per D-417 §C7 | A serialized test window (never concurrent with `make test`) |
| `PAID-RUNS-LANE` | Paid generation and measurement scripts were not invoked; no finding depends on them | UD-2 authorises spend |
| `TEST-24-429` | A real HTTP 429 has never rendered and stays deliberately open | A funded load test |
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
| `F4-CRITERION6` | Criterion 6 was closed on an explicit user bypass; its reopen condition is live and was undetectable while `RD-01` silenced the instrument — the instrument was repaired and confirmed 2026-08-22, so a waived-firing failure among the nightly three is detectable from that date (the weekly job's instrument stays mis-specified until `RD-01`'s residual lands) | A failure in any waived scheduled firing |
| `SEC-17-GUARDDUTY` | GuardDuty is absent as an account fact, by costed decision D-125 | Production posture review, or staging ceasing to be synthetic |
| `IMAGE-WORK-PARK` | Parked by **D-078** (feature deferred); SPEC §5.17's requirements have no subject in the codebase | The user reopens §5.17 — **both** preconditions (incidental-capture privacy with counsel; real-credential footing for scanning and encryption at rest) must be answered first |
| `D342-PARKING` | All question-bank **quantity** coverage work is parked by standing user instruction. Non-quantity defects (wrong answer key, unservable path) remain defects | The user explicitly asks for new problems to be generated |
| `VIDEO-COVERAGE-PARK` | Video coverage parked (D-417 §B5). The figure the park was argued from was 100× stale; live staging shows 102 of 112 skills servable | The user schedules a seeding run and provisions the API key |
| `DRIFT-70-CONSENT-GATE` | Parked by **D-152** (the notice half belongs to frozen session S45, the issuer half to S44); consent **verification** is enforced and fails closed (empty age-band frozenset); the **notice** half is unbuilt. The former carve-out (the frozenset had no pin) resolved 2026-08-21: `packages/shared/tests/test_auth_consent_gate.py` pins the frozenset empty and pins the exemption semantics (mutation-checked) | Notice half at S45; issuer half at S44 |

**Accepted-risk expiries (single-homed here per W-22).** §7-R8: carried in the `R8-READ-SCOPE` row
above. **§7-R9 (checkpoint-repair acceptance, `ARCH-17-COMMIT-SEAM`):** the repair counter is
charted and **alarmed nowhere**; **any movement in `learning_checkpoint_repairs_total` voids the
acceptance**. Whether to alarm it or accept the dashboard cadence is UD-5's sub-question.

Two further accepted residuals belong in this launch-readiness set (W-22; minors-primary product,
same insufficient-stopgap shape as `SEC-18-WAF`):
- **`WORK-42-INTERSTITIAL-BYPASS`** — the external-link interstitial's middle-click/ctrl-click
  bypass is **accepted** (decision recorded in DECISIONS.md; register #163). Expiry: revisit if
  the interstitial is ever presented as a safety control rather than a courtesy.
- **`WORK-44` #2** — anonymous chat rate limiting is a **single shared bucket**, so one hot
  anonymous user can exhaust it for all. Accepted for the pilot; expires at first real traffic
  alongside R8 (register #64).

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

- **Three of the four heartbeat alarms cleared on 2026-08-22** (`chat-purge` 19:05Z,
  `retention-purge` 19:11Z, `session-consolidate` 19:42Z) — the dead-man's switch works
  end-to-end for the first time since it was built. **`memory-consolidate`'s alarm is now
  correctly specified** (7-day window applied 2026-08-22, `4a5ad20`; CloudWatch's one-week
  evaluation maximum makes 2×-weekly impossible, so it pages after the *first* missed Sunday)
  and its current ALARM is **accurate signal**: no completion in the trailing week. It should
  clear after the Sunday 2026-08-24 18:30 UTC run (`RD-01`'s last step, §4.3); if it does not,
  that is a real job failure, not instrument noise.
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
  its row. Keys appearing in more than one section (today: `RD-01`, `UD-1`, `D310-RESIDUALS`,
  `LANGSMITH-RETENTION`) carry consequences in §3, §5, §6 and
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
