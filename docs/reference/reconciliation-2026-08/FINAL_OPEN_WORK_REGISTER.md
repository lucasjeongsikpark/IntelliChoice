> **REFERENCE — not an archive. Added 2026-08-20 (migration step 7d).**
> **This file moves to `docs/reference/reconciliation-2026-08/`.** It is point-in-time but
> load-bearing until its items close, so it carries *no* do-not-treat-as-current banner.
> **It is the provenance backbone for `docs/PROJECT_STATE.md`:** PROJECT_STATE holds **one line
> per open item** and links here for the evidence, the options and the reopen conditions —
> it does not restate them (single-home rule). An item **deleted from PROJECT_STATE on
> resolution remains readable here**, which is what makes deletion-on-resolve safe.
> **As-of date: 2026-08-20.** When PROJECT_STATE's snapshot date advances, an entry here is
> evidence for **what was true on 2026-08-20**, not a current-state claim; do not restate a
> count from this file without that date. This register is **evidence, never authority for
> intent** — `docs/DECISIONS.md` owns intent.
> Scope: 166 entries. The 41 RESOLVED / SUPERSEDED / OBSERVATION_ONLY entries stay here as
> the historical tail — the record of what was checked and found closed.

# FINAL_OPEN_WORK_REGISTER.md — Phase 4 consolidated open-work register

**Date:** 2026-08-20. **Phase:** 4 (reconciliation merge). **Inputs:** the seven Phase-4 extraction
streams over `CLAIM_LEDGER.md` (E1), `DECISION_SUPERSESSION_MAP.md` (E2),
`REPOSITORY_DRIFT_REGISTER.md` + `LOCAL_EXECUTION_FINDINGS.md` (E3),
`LOCAL_EXECUTION_FINDINGS.md`/`_EVIDENCE.md` (E4), `DEPLOYED_INFRA_DRIFT_REGISTER.md` +
`DEPLOYED_INFRA_STATE_EVIDENCE.md` + `REMEDIATION_D310_ROTATION.md` (E5),
`LIVE_BEHAVIOR_FINDINGS.md`/`_EVIDENCE.md` + `DOCUMENTATION_RISK_REGISTER.md` +
`DOCUMENT_INVENTORY.md` (E6), and `OPEN_DECISIONS.md` + `DECISIONS.md` D-417…D-423 (E7), merged
under the Phase-4 adjudication's canonical rulings.

**Companion:** [USER_DECISION_QUEUE.md](USER_DECISION_QUEUE.md) — the twelve decisions this register
routes to the user, with options and consequences. This file does not re-argue them; it records
where each one sits in the work.

**This file fixes nothing and decides nothing.** It is the single place where every open item found
by the audit is stated once, with its evidence, its disposition, and what remains.

---

## §0 Method

### 0.1 Scope

Every candidate item produced by the seven extraction streams is accounted for here — 131 (E1),
50 (E2), 60 (E3), 24 (E4), 33 (E5), 39 (E6) and 12 (E7) source items, 349 in total. They are merged
into **166 register entries**, each keyed by a canonical topic ID. §11 proves that no source finding
vanished: nine coverage tables plus a source-item roll-call map every original ID to exactly one
entry.

The register covers the *IntelliChoice* repository and its staging deployment. It does **not** cover
the `go.intellichoice.org` production system except as a reporting obligation: production is frozen,
so production-side findings route to the org-communication decision (`ORG-COMMS`, UD-8) and never to
a fix here.

### 0.2 The ten global rules

Every entry below is written under these rules. They are the adjudication's §A, condensed.

1. **Repository state and deployed state are never flattened.** The deployed staging build is image
   tag `gha-44a12dfc9549` = commit `44a12dfc9549`, **10 commits behind local HEAD `344f016`**
   (`LIVE_BEHAVIOR_FINDINGS.md:295-312`). Undeployed: the whole B4 escalation series (D-420, D-421,
   D-422), C8 (`f6f84a2`) and D-423's docs (`6f107c1`). Every entry whose state differs between the
   two records **both**, in separate fields, never merged into one sentence.
2. **Green tests never disposition an identified untested defect as resolved.** The F-09/F-11/F-12/
   F-16 class — a passing suite that structurally cannot reach the defect — stays open.
3. **D-152 attribution rule.** Frozen items are `PARKED_BY_DECISION` or `DEFERRED` with the freeze as
   the reopen condition, and the block is attributed to **a deliberate user decision**, never to an
   obstacle. Nothing in this register "unblocks" the freeze, and no accumulation of readiness reopens
   it (D-417 §A1: "it is closed until reopened").
4. **Post-extraction supersessions are applied everywhere.** Three facts post-date parts of the
   extraction and override them:
   - **The D-310 rotation was executed 2026-08-20T03:20:57Z** and verified
     (`REMEDIATION_D310_ROTATION.md`). Text implying "rotation declined and the exposure is live" is
     historical only. Affects DRIFT-84, RD-02, chain G4, OPEN_DECISIONS #8, SEC-26, WORK-39.
   - **SNS `PendingConfirmation` is resolved live** (COST-23 read 2026-08-20T00:05:15Z: both topics
     `SubscriptionsConfirmed 1` / `SubscriptionsPending 0`). Affects COST-26, WORK-02, chain M5.
   - **The NAT gateway exists** (`nat-07ab02d5cd28b6f72`, `CreateTime 2026-08-07T04:47:31Z`,
     ~$32.9/mo gross, net $0.00 on credits). Affects ARCH-29, COST-28, chain M5's unresolved item (e).
5. **UNKNOWN is never silently converted.** Exactly five UNKNOWNs survive, each naming its resolution
   step (§12.2).
6. **Audit IDs are cited as `<document>:<id>`** wherever a bare ID is ambiguous. `AUD-L-01…AUD-L-19`
   is reused across `AUDIT_FINDINGS.md` and `AUDIT_LIVE_2026_08_17.md` for unrelated findings.
7. **Disposition semantics.** `ACTIVE_REMEDIATION` = fixing an existing defect or broken control.
   `ACTIVE_IMPLEMENTATION` = building something owed (a test, a feature, a guard) that never existed.
   `DOCUMENTATION_ONLY` = the only remaining action is editing documents.
8. **Production is frozen.** See §0.1.
9. **Entries are keyed by canonical topic ID** (§0.4).
10. **PROJECT_STATE guidance.** `ACTIVE_*`, `USER_DECISION_REQUIRED`, `BLOCKED`, `DEFERRED`,
    `PARKED_BY_DECISION` → yes for a future PROJECT_STATE document (parked items as a parked list
    with their reopen conditions). `RESOLVED` / `SUPERSEDED` / `OBSERVATION_ONLY` → historical or
    archive material only. `DOCUMENTATION_ONLY` → belongs in the canonical-document migration
    worklist, not in current work.

### 0.3 Disposition vocabulary

| Disposition | Meaning | Entries |
|---|---|---|
| `USER_DECISION_REQUIRED` | Cannot be closed without a judgement only the user can make. | 16 |
| `ACTIVE_REMEDIATION` | An existing defect or broken control to fix. | 16 |
| `ACTIVE_IMPLEMENTATION` | Something owed that was never built. | 11 |
| `BLOCKED` | Cannot proceed on an external party, an unreadable surface, or wall-clock time. | 6 |
| `DEFERRED` | Real work with a named later occasion; nothing owed now. | 15 |
| `PARKED_BY_DECISION` | Closed by an explicit user decision, with a reopen condition. | 13 |
| `DOCUMENTATION_ONLY` | Only document edits remain. | 44 |
| `OBSERVATION_ONLY` | Recorded so it is not later "discovered"; no work owed. | 21 |
| `RESOLVED` | Measured closed, or closed by action. | 19 |
| `SUPERSEDED` | Overtaken by a later phase or decision. | 1 |
| `UNKNOWN` | Genuinely undetermined; the resolution step is named. | 4 |

### 0.4 Key convention

Each entry is keyed by its canonical topic ID: a claim ID where one exists (`SEC-13`, `COST-06`,
`WORK-40`), else a drift/register ID (`DRIFT-49`, `RD-01`, `LB-05`), else a supersession-map chain
label or phantom ID (`K5`, `D-192`), else a merge-key slug (`RETENTION-CLUSTER`,
`DISCLOSURES-LEGAL`). One entry per topic; all merged source items are listed as **Members**.

### 0.5 The LB-05 dual-status rule

Because the deployed build is 10 commits behind HEAD, "the documents say X but staging does Y" often
means only "X has not shipped". Two fields therefore appear in every entry and are never merged:

- **Repository evidence** — what is true of HEAD `344f016`.
- **Deployed/live evidence** — what is true of `gha-44a12dfc9549`, or `n/a — repo-only`, or
  `not deployed: <reason>`.

The reciprocal caution applies too: staging is never credited with behaviour that exists only on
HEAD. LB-05's own method move is the model — the `journey-student.spec.ts` instrument was verified
**byte-identical** between the deployed build and HEAD before a HEAD-checkout run was trusted
against the older build.

### 0.6 Namespace flags — four cases where one ID names two things

These are recorded so no reader collapses them, and so §11's tables stay unambiguous.

1. **`WORK-35` (E5 vs E1).** E5's WORK-35 is the 3B-1 evidence block for §2.6 criterion 6 (the ≥1
   week unattended nightly firing). E1's WORK-35 is the ledger claim for OPEN_DECISIONS #4 / U7
   (checkpoint consolidation criteria). The register uses two entries: **`C6-UNATTENDED`** (§7) for
   the 3B-1 block and **`WORK-35-LEDGER`** (§1) for the ledger claim.
2. **`WORK-40`.** E4's F-02 is the chat-web `CalendarActionModal` viewer-locale defect
   (**`WORK-40-TZ`**, §6). E1's WORK-40 is the OPEN_DECISIONS #10 build items (**`WORK-40`**, §5).
   Both are adjudicated as separate entries.
3. **`REQ-27`.** E1's REQ-27 is the token-claim contract that depends on frozen production
   (**`REQ-27-TOKEN-CONTRACT`**, DEFERRED). E4's F-16 REQ-27 is the fail-closed empty-frozenset guard
   (**`REQ-27-FROZENSET`**, ACTIVE_IMPLEMENTATION). Different substances, same claim id.
4. **`REQ-39`.** E1's REQ-39 is the deferred IRT/Bayesian upgrade (**`IRT-UPGRADE`**). E3/E4's REQ-39
   is the missing "Current estimated level" UI wording (**`REQ-39-ESTIMATED-LEVEL`**, UD-12(e)).

### 0.7 How the sections are organised

§1–§8 are domain sections and hold every entry in their domain, whatever its disposition. §9 holds
the grouped documentation and decision-log hygiene entries — including E3's seven LOW batches and
E6's risk groups, with their member lists preserved verbatim. §10 holds audit-method observations
and the resolved/superseded record; §10.3 is a roll-up table pointing at every `RESOLVED` /
`SUPERSEDED` entry wherever it sits, so the historical record is readable in one place.

Two of E3's LOW batches (E and F) carry non-documentation dispositions and are kept in §9 anyway,
because splitting them would break the member lists the adjudication requires be preserved; each is
cross-referenced into the relevant domain section.

---

## §1 Security & privacy

### `D310-ROTATION` — the D-310-exposed staging token secrets are rotated, drained and verified

- **Work/Issue ID (topic key):** `D310-ROTATION` (RD-02 / SEC-26 / chain G4 / DRIFT-84 /
  OPEN_DECISIONS #8)
- **Members:** E5-2, E2-15 (rotation half), E3-58:DRIFT-84, E7-5, E1-40 (SEC-26), E1-122 (WORK-39),
  E2-3 (S44 deletion-plan half)
- **Description:** The two `/dev/token` staging shared secrets exposed in the 2026-08-13 process-table
  incident (D-310) were still `AWSCURRENT` and actively read as of 2026-08-20T00:08Z. Following user
  approval of a remediation plan with six safeguards, both were rotated by targeted `terraform apply`
  at 2026-08-20T03:20:57Z; both services force-redeployed and were stable by 03:24Z with every task
  started 03:22Z, so no pre-rotation task survived. A behavioural probe through CloudFront returned
  **200** with the new secret and **404** for a wrong literal and for a missing header on both apps,
  so fail-closed behaviour is intact. Post-apply `terraform plan -detailed-exitcode` returned exit 0,
  no changes. The old versions were **destroyed, not deprecated**. A Step-0 CloudTrail access review
  found only known consumers (5 Terraform reads during the known 2026-08-18 apply, 3 Fargate-agent
  reads at task startup; zero `UpdateSecret`/`DeleteSecret`/`RestoreSecret`).
- **Domain:** security — credential exposure
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:119-150` (resolution addendum at `:149`);
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:307-317` (SEC-26); `REMEDIATION_D310_ROTATION.md:1-99`;
  `DECISION_SUPERSESSION_MAP.md:965-971`, `:980-992`; `REPOSITORY_DRIFT_REGISTER.md:957`;
  `CLAIM_LEDGER.md:1509`, `:3345`; `OPEN_DECISIONS.md:307-318`
- **Related claim IDs:** SEC-26, SEC-25 (ARN wiring), SEC-35, WORK-39
- **Related decision IDs:** D-310 (the decline, now operationally superseded), D-097, D-132, D-417 §E
- **Repository evidence:** no rotation mechanism exists and none ever did —
  `git log -S"staging_token_shared_secret" -- terraform` returns exactly one commit (`168de30`,
  creation); no `keepers`, no rotation trigger, no `aws_secretsmanager_secret_rotation` resource
  anywhere. The rotation was performed by `-replace=` on the two `random_password` resources plus
  targeted version applies, so **the repository still has no standing rotation mechanism**. The S44
  deletion plan at `terraform/environments/staging/main.tf:355-360` is unchanged.
- **Deployed/live evidence:** pre-remediation both secrets had exactly one version,
  `LastChangedDate 2026-07-24`, `LastRotatedDate null`, `LastAccessedDate` 2026-08-18/2026-08-17.
  Post-remediation both show `LastChangedDate 2026-08-20T03:20:57Z` with a single new terraform
  version on `AWSCURRENT`.
- **Final disposition:** `RESOLVED`
- **Justification:** the rotation was executed, drained, behaviourally verified and drift-checked.
  This *was* a user call on security posture and the user made it; D-310's decline stands as the
  historical record and is operationally superseded. RD-02 must not be re-raised as an open security
  gap: the DRIFT register's §3.2 table row at `DEPLOYED_INFRA_DRIFT_REGISTER.md:361` still lists
  RD-02 as a user decision because that table predates the addendum — **the addendum at `:149` wins**,
  and the §3.2 row is recorded here as an audit-artifact correction.
- **Remaining action:** none for the rotation. Two things survive it and are tracked elsewhere: the
  three residual follow-ups (`D310-RESIDUALS`) and the recorded acceptance that **no standing
  rotation mechanism was added** — a future rotation is again a manual targeted apply, accepted
  because the S44 plan deletes these secrets entirely when real auth lands. OPEN_DECISIONS #8's
  wording should be marked superseded-operationally rather than left ⏸ UNCHANGED, because as written
  it tells the next reader the exposure is live (that edit is a member of
  `RISK-GROUP-RESOLVED-LOOKS-OPEN`).
- **Owner type:** none (closed); documentation for the #8 wording
- **Reopen condition:** n/a. The historical trigger in OPEN_DECISIONS #8 ("staging stops being
  synthetic") is unmet and frozen behind D-152 regardless.
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `D310-RESIDUALS` — three follow-ups survive the rotation, one of them an unmeasured exposure of the same class

- **Work/Issue ID (topic key):** `D310-RESIDUALS` (`REMEDIATION_D310_ROTATION.md` §8/§9)
- **Members:** E5-3, E2-15 (residual half)
- **Description:** Three items survive the rotation. **(1)** Any browser holding
  `intellichoice.staging_token_secret` in `localStorage` — any machine where a human pasted it into
  the dev-login screen's staging-secret field — now holds a **dead credential** that fails with 404.
  Whoever uses that screen must re-fetch the current value by secret id and re-paste; this cannot be
  automated from the repository side and presents as an unexplained 404 to anyone who does not know.
  **(2)** `make load-staging-learning`'s docker env pass-through was **never re-measured for `ps`
  visibility** — the D-310 *class* of exposure is unverified on that command path, i.e. unmeasured,
  not cleared. **(3)** `e2e/README.md:16-17` still documents the pre-D-310 export shape. Also noted:
  the transcript that captured the old values still exists wherever transcripts are retained, and the
  values it contains are now worthless.
- **Domain:** security hygiene / operator documentation
- **Original source(s):** `REMEDIATION_D310_ROTATION.md:100-110` (§8 consumers, the localStorage line
  at `:107-110`), `:112-121` (§9 residual notes); `DECISION_SUPERSESSION_MAP.md:205` (via E2-15)
- **Related claim IDs:** SEC-26 (residual), SEC-25
- **Related decision IDs:** D-310, D-132 (whose now-false Makefile comment — "never in argv, ps, or a
  shell history" — is criticised inside D-310 but was never corrected in D-132's own entry)
- **Repository evidence:** `e2e/README.md:16-17` still carries the pre-D-310 export shape on HEAD.
  `make load-staging-learning`'s docker env pass-through is unchanged and un-measured. Operator
  workflows that fetch by id per run (`e2e/config.ts`, `make load-staging-learning`,
  `scripts/measure_hint_delivery.py`) are self-healing and need no change; CI holds no copy by design
  (`deploy-staging.yml:532-537` runs negative probes only).
- **Deployed/live evidence:** the AWS side is fully consistent post-rotation. The stale copies live
  **outside AWS and outside the repository** — in browser `localStorage` on operator machines — so no
  control-plane read can enumerate or clear them.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** mechanical follow-through on an already-decided remediation. Item (2) is the only
  one with security weight left: it is the same exposure class as D-310 on a different command path
  and it is currently unmeasured rather than cleared, so it gets its own line rather than being
  folded into a documentation bucket.
- **Remaining action:** (a) tell the user to re-paste the current secret into any browser
  `localStorage` that holds the dead one — an action, not a decision; (b) measure `ps` visibility of
  `make load-staging-learning`'s docker env pass-through; (c) update `e2e/README.md:16-17`.
- **Owner type:** (a) user-action, (b) engineering, (c) documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `R8-READ-SCOPE` — tutor and branch_manager reads are unscoped; the acceptance expires on the one event that could unfreeze its fix

- **Work/Issue ID (topic key):** `R8-READ-SCOPE` (§7-R8; REQ-09 / SEC-09 / ARCH-18 / DRIFT-17 /
  chain G3)
- **Members:** E1-2 (REQ-09), E1-21 (ARCH-18), E1-33 (SEC-09), E2-14 (chain G3), E3-17 (DRIFT-17)
- **Description:** `resolve_target_student` verifies students against their own `sub` and parents
  against a live linked-children lookup, but returns the **client-supplied** student id unchecked for
  `tutor` and `branch_manager`. A tutor token can therefore read any student's dashboard, history and
  reports. Writes fail closed (`if access == "write": raise 403`), so the exposure is read-scope only,
  and tutor tokens today come solely from the secret-gated `/dev/token`. Reach is confirmed:
  dashboard, history and report routes all call with `access="read"` (15 call sites across
  `students.py`, `sessions.py`, `stream.py:173,220`, `main.py:464`). D-123 accepted this as documented
  residual risk §7-R8 with an **expiry** — "R8 expires at first real traffic" — and a named closure
  owner, S43/S46.
- **Domain:** security / authorization
- **Original source(s):** `CLAIM_LEDGER.md:149`, `:946`, `:1288`;
  `REPOSITORY_DRIFT_REGISTER.md:213-222`; `DECISION_SUPERSESSION_MAP.md:169-174`, `:913-915`,
  `:935-946`; `INTEGRATION_PLAN.md:535-550`; `TRACEABILITY.md:180-185`, `:498-499`;
  `DECISIONS.md:6496-6502`
- **Related claim IDs:** REQ-09, SEC-09, ARCH-18, SEC-04, SEC-34, INT-33, TEST-13
- **Related decision IDs:** D-086 (the acceptance, self-labelled launch-blocking), D-107 (write half
  closed), D-123 (§7-R8 with expiry), D-097, D-152, D-417 §A1
- **Repository evidence:** `apps/learning-api/src/learning_api/authorization.py:7-14`, `:22`,
  `:47-71` — the read branch falls through returning the requested id; the write branch raises 403.
  The in-code disposition states the two roles have no per-student scope check, that this is D-086's
  accepted risk since S33, that S43's `IcProfileAdapter` unblocks it and that formal disposition is
  scheduled for S46. Both named sessions are inside the D-152-frozen block. The expiry condition is
  unreconciled in code or comment. A grep across `DECISIONS.md` finds **no closure anywhere**
  (`DECISION_SUPERSESSION_MAP.md:935-942`: "Is there ANY later entry closing R8? NOT FOUND").
- **Deployed/live evidence:** n/a — repo-only. Whether "first real traffic" has begun is not
  determinable from the repository, and no live probe in Phase 3B re-owned the acceptance; LB-09's
  null result does not bear on an accepted-risk ownership question.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** D-086/D-123 accepted the gap explicitly and D-107 closed the write half. The
  expiry trigger ("first real traffic") **coincides with the only event that can unfreeze the closure
  path** — so the freeze does not defer the risk, it defers only the fix, and no decision is owed
  now. What the freeze does not do is make the acceptance self-monitoring: "expires at first real
  traffic" is unenforceable as written because no code or config can trip on it.
- **Remaining action:** none now. The item **must be re-presented to the user at integration start**,
  reframed so the expiry is something a running system can trip. Listed in the queue document's
  excluded section with exactly this reasoning. The per-student-scope half is the same gap as
  `DRIFT-12-ADMIN-ROLE`'s tutor/manager rows and must not be counted twice.
- **Owner type:** user (at integration), engineering (for a trippable expiry)
- **Reopen condition:** integration reopen, or first real traffic — whichever comes first.
- **PROJECT_STATE?** yes — parked, launch-blocking-at-integration
- **Historical/archive only?** no

### `SEC-13-PURGE` — the location-coordinate purge is unreachable on two paths and has zero tests

- **Work/Issue ID (topic key):** `SEC-13-PURGE` (F-11 / DRIFT-09 / SEC-12 / REQ-28)
- **Members:** E4-11 (F-11), E3-9 (DRIFT-09), E4-22 (the three-test package, whose other two members
  are `COST-06-FLUSH` and `REQ-27-FROZENSET`)
- **Description:** `purge_resume_writes` is exactly as documented — a parameterized
  `DELETE FROM checkpoint_writes WHERE thread_id = :thread_id AND channel = '__resume__'` — and it is
  the enforcement point for the §5.30 no-PII boundary on the branch-locator path, where a visitor's
  ZIP, city, typed address, latitude and longitude stop existing. It has **exactly one trigger**, the
  successful/declined resume return path. Ordering inside `respond_to_interrupt` is
  `_run_turn(...)` → `if cancelled: return` → the purge, so (a) a **cancelled** location-consent
  resume returns before the purge and (b) any **exception** inside `_run_turn` skips it — leaving
  precise coordinates or a manually typed address in `checkpoint_writes.__resume__`. Execution added
  that the cancel path has **no executable guard whatsoever**: an exhaustive grep returns three files,
  all under `src/` (definition, single call site, one comment) and **no `tests/` path at all**. The
  single call site is one `await` inside a router, so a refactor deleting that line would break no
  test and fail no CI job. An abandoned consent is safe by construction — no `__resume__` row is ever
  written.
- **Domain:** privacy / PII boundary / minors' location data
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:510-541`, `:799-802`;
  `REPOSITORY_DRIFT_REGISTER.md:125-134`
- **Related claim IDs:** SEC-13 (`PARTIALLY_IMPLEMENTED`, flagged in 3A as new material drift —
  privacy/minors), SEC-12, REQ-28
- **Related decision IDs:** D-045, D-333, AUD-C-03 [AUDIT_FINDINGS]; SPEC §5.1.3, §5.30;
  non-negotiable rule 1
- **Repository evidence:** `apps/chat-api/src/chat_api/services/checkpoint_privacy.py:24-30`
  (definition); `apps/chat-api/src/chat_api/routers/sessions.py:66` (import), `:897-905` (the cancel
  return, preceding), `:907-914` (the single call site);
  `apps/chat-api/src/chat_api/graph/nodes.py:801` (explanatory comment).
  `REPOSITORY_DRIFT_REGISTER.md:126` carries the code defect. The purge is **not** in a
  `finally`/`except`, so the defect is live, not merely untested.
- **Deployed/live evidence:** n/a — repo-only for the defect. The related live question (whether the
  `__resume__` purge was ever confirmed on staging) is `G2-LOCATOR-PURGE`; and no retention job covers
  `checkpoint_writes.__resume__` rows for live threads, so nothing sweeps up what this path leaves
  behind (`RETENTION-CLUSTER`).
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** the requirement is not in question — only the code path is wrong. This is the
  intersection of every aggravating factor the project's own rules name: PII, minors, fail-closed, and
  a deterministic enforcement point with zero coverage. The green 562-test local run says nothing about
  it (rule 2). Green branch-locator tests (REQ-28/SEC-12 passing under F-17) must **not** be read as
  covering it: F-11 is explicit that zero tests touch the function.
- **Remaining action:** two separable, undone things. **(1) The code fix:** move the purge into a
  `finally` (or equivalent) so the cancelled-resume and exception paths are covered. **(2) The
  tests:** write the cancel-path test first — a test in `apps/chat-api/tests/` that cancels a resume
  and asserts the `__resume__` row survives — so the leak is *demonstrable* rather than inferred, then
  fix. Both are closable locally against the dev fakes and dev Postgres, with no live or paid
  dependency. Ranked first of the three named new-test candidates.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no
- **⚠️ RESOLVED 2026-08-22 — implementation evidence supersedes this entry's disposition.**
  Both remaining actions are done (commit `b6fa067`, PR #364): the purge now runs in a `finally`
  covering all four ways a location-consent resume turn can end, **on its own committed
  `session_scope` unit of work** — necessary because `get_db_session` commits only on the normal
  path, so a purge on the request session is silently rolled back exactly on the exception path
  while `AsyncPostgresSaver`'s `autocommit=True` connection has already committed the
  coordinates. Test-first evidence: both leak paths were demonstrated failing pre-fix against
  committed Postgres state (`test_a_cancelled_locator_resume_still_purges_the_location`,
  `test_a_locator_resume_that_raises_still_purges_the_location` in
  `apps/chat-api/tests/test_chat_endpoints.py`); an asymmetric vacuity control proved the
  exception-path test catches a rolled-back purge; a third test pins that a failed resume stays
  retryable. This entry's heading and its "not in a `finally`" / line-reference evidence are
  historical as of `b6fa067`; the "zero tests" clause was already corrected (the success path was
  covered pre-fix). **Deployed staging (`gha-44a12dfc9549`) still has the defect until the next
  image deploy (UD-1, LB-05)**, and rows already leaked on live threads are not swept
  (`RETENTION-CLUSTER` / UD-7). No new judgment — no D-number; git history and
  `docs/log/2026-08-22-sec13-purge-orca.md` are the record.

### `REQ-32-SAFETY` — the minors-safety posture is a ten-keyword screen on one of two surfaces, with one test repo-wide

- **Work/Issue ID (topic key):** `REQ-32-SAFETY` (DRIFT-13 / DRIFT-14 / F-10 / REQ-19)
- **Members:** E1-13 (REQ-32), E4-10 (F-10), E3-13 (DRIFT-13), E3-14 (DRIFT-14)
- **Description:** SPEC requires the Tutor Agent to route self-harm, abuse and safety signals through
  a "separately approved safety policy", and lists Bedrock Guardrails among the gateway's features.
  Neither exists. A repo-wide case-insensitive grep for "guardrail" across `packages`, `apps`,
  `scripts` including `.tf`/`.yaml`/`.json` returns **zero hits**. What exists is a fixed 10-item
  substring screen that short-circuits to a fixed response and persists `flagged_for_review=True`,
  with **one caller** — no equivalent screen exists anywhere in `apps/chat-api`, the app minors also
  use. A flagged conversation has **no escalation destination** beyond the boolean. Execution
  confirmed the coverage is one test function repo-wide:
  `apps/learning-api/tests/test_learning_chat.py:474`
  `test_self_harm_keyword_short_circuits_to_a_fixed_response_and_flags_for_review` (recovered after
  the as-briefed `-k "safety"` collected zero, then `11 passed`), and a grep for
  `safety_screen|crisis|self_harm|safety_flag` over `apps/` and `packages/` hits that one file and no
  other. Eight of the ten listed gateway features *are* present and quotable
  (`call_timeout_s=20.0`, retry loop, `_HARD_MAX_OUTPUT_TOKENS=4000`, `session_budget_cents=50.0`
  checked pre-call, circuit breaker, `worst_case_cost_cents`); gateway-level PII redaction is the
  second absent one, and lives at callers instead.
- **Domain:** child safety (minors are the primary users) / LLM gateway feature list
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:487-506`, `:108-112`;
  `REPOSITORY_DRIFT_REGISTER.md:169-178`, `:180-189`; `CLAIM_LEDGER.md:448`
- **Related claim IDs:** REQ-32, REQ-19, COST-02, WORK-28, WORK-29
- **Related decision IDs:** SPEC §5.11.4, §5.12.2, §5.25.1; D-022, D-233, D-251
- **Repository evidence:** `packages/shared/src/intellichoice_shared/bedrock.py:111-120`;
  `apps/learning-api/src/learning_api/services/tutor.py:96-107`; `tutor_chat.py:66-84`, `:161`;
  `apps/chat-api/src/chat_api/graph/nodes.py:1457`;
  `packages/db/src/.../models/tutor_chat.py:33-36`;
  `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:78-194`, `:215-263`, `:285-310`;
  zero-hit "guardrail" grep. No approval artifact, policy document or escalation destination beyond
  the boolean flag was found anywhere.
- **Deployed/live evidence:** n/a — repo-only. No deployed control adds a model-side backstop; the
  absence is a repository property, not a deployment gap.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-9**
- **Justification:** child-safety posture on a platform whose primary users are K-12 minors is the
  user's call, not an engineer's. The document that surfaced the thinness explicitly declined the
  judgement ("Whether chat-api should also carry a safety screen is a product judgement and is not
  made here"), and the same is true of the escalation destination. The scope decision governs what
  tests are even worth writing, so it must precede remediation. F-10's passing test is necessary and
  nowhere near sufficient — do not let the green test soften this.
- **Remaining action:** the user decides one of: adopt Bedrock Guardrails; define the "separately
  approved" self-harm/abuse routing policy (escalate to whom, tell whom); or amend SPEC §5.12.2 and
  §5.25.1's feature list to describe what is actually built. Engineering then follows: chat-api
  coverage, a real escalation destination, and tests pinning the keyword list's contents, near-miss
  phrasing and the flag's downstream effect. Keep the feature-list amendment separable so the eight
  present gateway features stop being under-credited.
- **Owner type:** user (with counsel input plausible), then engineering
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `DISCLOSURES-LEGAL` — the first-visit notice, the eight-vs-eleven ruling, and the §6.1 legal track

- **Work/Issue ID (topic key):** `DISCLOSURES-LEGAL` (WORK-33 / WORK-32 / REQ-25 / REQ-26 / SEC-20 /
  TEST-10 / DRIFT-08 / DRIFT-11 / DRIFT-36 / REQ-30 / INT-19 legal half / REQ-27 notice half)
- **Members:** E1-9 (REQ-25), E1-10 (REQ-26), E1-12 (REQ-30), E1-39 (SEC-20), E1-60 (TEST-10),
  E1-76 (INT-19), E1-115 (WORK-32), E1-116 (WORK-33), E3-8 (DRIFT-08), E3-11 (DRIFT-11),
  E3-36 (DRIFT-36), E4-16 (F-16, notice half)
- **Description:** SPEC §5.1.2 requires a first-visit notice on the learning app disclosing eleven
  enumerated items. **Nothing is built**: an exhaustive grep for
  `parental|consent|under 13|guardian` over both frontend `src` trees returns 23 matches, **all in
  chat-web and all location-consent** — a different consent under SPEC §5.1.4 that does not discharge
  the COPPA notice — and **zero in `apps/learning-web/src`**, the app `SPEC.md:96` names
  specifically. Three of the eleven describe behaviour that does not exist: §2.11's right to
  "challenge learning results" (the phrase appears once in the whole SPEC, with no section, endpoint
  or UI), §2.8's solution images (S29 deferred, no upload path), and §2.5's tutor/branch-manager
  sharing (roles gate the Q&A corpus, but learning-api has no tutor- or manager-facing view). The
  document recommends shipping **eight**, and states the three gaps "need a product decision before
  S45 starts, because they change how many disclosures there are". No DECISIONS ruling exists on the
  number. Counsel review by U.S. education and child-privacy counsel is a **mandatory production
  release gate** (SPEC §5.1.1, COPPA as amended 2025-04-22, FERPA, PPRA, state law, breach
  notification, school contracts) and all six non-ledger `counsel` hits state it prospectively, never
  as performed. The §6.1 legal track has **no owner, no schedule and no status field** anywhere — it
  is tracked only by narrative mentions in four documents, and there is **no launch-checklist document
  at all**: the only file self-describing as a launch-checklist item is `ENROLLMENT_FAQ_APPROVAL.md`,
  whose scope is narrower and does not enumerate the counsel gate.
- **Domain:** privacy / legal / product (minors)
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:112-121` (DRIFT-08), `:147-156` (DRIFT-11),
  `:427-436` (DRIFT-36); `LOCAL_EXECUTION_FINDINGS.md:666-690` (F-16);
  `CLAIM_LEDGER.md:357`, `:370`, `:422`, `:1431`, `:2141`, `:2626`, `:3254`, `:3267`;
  `FIRST_VISIT_NOTICE.md:33-35`, `:201-218`, `:214-218`, `:231-237`, `:3-13`;
  `SPEC.md:96-110`, `:112-128`, `:38-78`; `TRACEABILITY.md:109-122`, `:650-698`;
  `ROADMAP.md:1500-1507`, `:2148-2160`; `INTEGRATION_PLAN.md:357-363`, `:437`, `:467`
- **Related claim IDs:** REQ-25, REQ-26, REQ-30, SEC-20, TEST-10, INT-19, WORK-32, WORK-33, REQ-27
  (notice half), T-02
- **Related decision IDs:** T-02, D-129, D-114 §4, D-127 §3, D-078, D-086, D-152 (S45 frozen), SPEC
  §6.1
- **Repository evidence:** `apps/learning-web/src` holds thirteen `components/*.tsx` and eight
  `screens/*Screen.tsx`, **none** named notice/disclosure/consent; a case-insensitive grep returns
  only forward-looking comments; there is no `localStorage`/`sessionStorage` first-visit flag (the
  only keys are the dev token/sub/role). The sibling pattern exists in the chat app
  (`LocationConsentModal.tsx`). The **prerequisite is discharged**: T-02's disclosure enumeration
  shipped 2026-08-15 as `docs/FIRST_VISIT_NOTICE.md` (237 lines, `da2549f`), and `ROADMAP.md:2148-2157`
  now enumerates the eleven — so "the §6.1 track has not started" is false in one respect and true in
  three (Privacy Notice, consent text, counsel review, owner and schedule all still missing). The
  backend consent gate *is* built and tested: `packages/shared/src/intellichoice_shared/auth.py:106`
  refuses a non-exempt student without `parental_consent_verified`, covered by
  `apps/learning-api/tests/test_auth_and_attendance.py:178`, `:182` inside Batch 1's `183 passed`.
- **Deployed/live evidence:** not deployed: S45 is unstarted, so there is nothing live to observe.
  The deployed build carries no notice, consistent with the repository.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-10**
- **Justification:** the eight-vs-eleven call and counsel engagement are user-owned and are **not**
  frozen — they are product- and document-side, and INT-19's legal-text dependency is explicitly
  independent of the freeze and called "a true pilot blocker". Three separate items (REQ-26, SEC-20,
  INT-19) name the §6.1 track as their unblocked prerequisite. Only the **S45 build itself** stays
  BLOCKED behind D-152. Do not read the shipped enumeration (DRIFT-99/DRIFT-101) as progress on the
  ruling: the deliverable that discharged the prerequisite is what raises the eight-vs-eleven
  question. §2.11 is the sharpest of the three gaps — the *right* to challenge results is asserted
  nowhere but this disclosure, so dropping it silently removes a right the SPEC gestured at, which is
  a product and legal call rather than a copy edit.
- **Remaining action:** the user decides: ship 8 or 11; whether the three unbuilt behaviours are
  built or the disclosures dropped; engage counsel; and own and schedule the §6.1 track. Then, as
  documentation, create the one launch-checklist document that would give DRIFT-08, DRIFT-11,
  DRIFT-36 and DRIFT-99/101 a single home — the highest-leverage cheap fix in this cluster. The S45
  build follows only when the freeze lifts. `REQ-27-FROZENSET` is the coupled engineering guard and is
  tracked separately.
- **Owner type:** user + external counsel; then documentation; then engineering at S45
- **Reopen condition:** the S45 build half reopens when D-152 lifts. The decisions themselves are open
  now.
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `REQ-27-FROZENSET` — the fail-closed COPPA frozenset has no test pinning it empty

- **Work/Issue ID (topic key):** `REQ-27-FROZENSET` (F-16 frozenset half; DRIFT-70 carve-out)
- **Members:** E4-16 (F-16, frozenset half), E4-22 (item 3 of the three-test package),
  E3-60:DRIFT-70 (carve-out)
- **Description:** The consent gate fails closed today because
  `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` is a deliberately **empty** frozenset — so every student
  needs verified parental consent. Nothing pins that emptiness: **no test asserts the frozenset is
  empty**, and no test pins `account_refusal_reason`'s behaviour against a non-empty set. A future
  addition to that frozenset would silently open the COPPA gate **with a green suite**.
- **Domain:** COPPA / consent / fail-closed invariants / minors
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:666-690`, `:806-808`;
  `REPOSITORY_DRIFT_REGISTER.md:803` (DRIFT-70), `:807`
- **Related claim IDs:** REQ-27, REQ-25, REQ-26
- **Related decision IDs:** SPEC §5.1.4, SPEC:96; D-152 (production's real token is `{id, iat, exp}`
  only, so the ten-claim set is minted by `fake_auth.py` today — expected)
- **Repository evidence:** `packages/shared/src/intellichoice_shared/auth.py:26-36`, `:106`;
  consuming sites at `apps/learning-api/dependencies.py:122`, `routers/stream.py:162`,
  `apps/chat-api/dependencies.py:46`, `routers/stream.py:73`. `TokenClaims` carries exactly the ten
  named claims, no extras and no omissions. The refusal path's tests ran and passed; the frozenset's
  emptiness is asserted by nothing.
- **Deployed/live evidence:** n/a — repo-only invariant.
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** the invariant is already decided (fail closed); what is owed is the guard that
  never existed. It is the cheapest fail-closed test in the whole audit and it protects a COPPA
  boundary for minors. F-16 named it; nothing acted.
- **Remaining action:** one test pinning `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` empty and one
  pinning `account_refusal_reason` against a non-empty set. Pair with `SEC-13-PURGE` and
  `COST-06-FLUSH` as a single "fail-closed invariants have no pins" package — three tests, one
  afternoon, no credentials, no spend.
- **⚠️ RESOLVED 2026-08-21 — implementation evidence supersedes this entry's disposition.**
  Both tests exist: `packages/shared/tests/test_auth_consent_gate.py` pins the frozenset empty
  and pins the exemption semantics against a non-empty set; the mutation check confirmed the
  emptiness pin is the only thing that catches a frozenset addition. No new judgment was made,
  so no D-number exists for this — the executable test and git history are the record
  (session narrative: `docs/log/2026-08-21-req-27-frozenset-orca-pilot.md`). The
  `SEC-13-PURGE` / `COST-06-FLUSH` members of the three-test package remain open — this
  resolution covers the REQ-27 half only.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — resolved and deleted from PROJECT_STATE 2026-08-21 (was: yes)
- **Historical/archive only?** no

### `REQ-27-TOKEN-CONTRACT` — the ten-claim token contract depends on frozen production

- **Work/Issue ID (topic key):** `REQ-27-TOKEN-CONTRACT`
- **Members:** E1-11 (REQ-27)
- **Description:** SPEC forbids substituting a student notice for parental consent under 13 and
  requires the auth token to carry ten named claims including `parental_consent_verified`.
  Production's own token is `{id, iat, exp}` only, so the claim set must be minted by the new stack —
  and the auth contract is frozen until S44. Production stores no consent/COPPA data and its
  registration flow cannot be extended, so the new stack keeps its own consent ledger in Postgres
  (external ids and enums only) with first-entry consent UI and fail-closed minting.
- **Domain:** product requirements / integration / COPPA
- **Original source(s):** `CLAIM_LEDGER.md:383` — `SPEC.md:112-128` (§5.1.2); `CLAUDE.md:58-62`
- **Related claim IDs:** REQ-27, INT-19, INT-31, INT-32, SEC-20
- **Related decision IDs:** D-152, SPEC §3.1, I9, I10
- **Repository evidence:** the claim set is minted by `fake_auth.py`; the ten-claim `TokenClaims` model
  exists and is consumed at four app-level sites. What cannot be established from the repository is
  whether production can supply the claims.
- **Deployed/live evidence:** n/a — repo-only. Measuring production's token contract is one of the
  four acts `CLAUDE.md:58-62` forbids before S44.
- **Final disposition:** `DEFERRED`
- **Justification:** a real launch-blocking requirement whose satisfiability is answerable only at
  integration, which D-152 freezes by choice. It is the most legally consequential DEFERRED item in
  the ledger and should not be filed alongside routine INT-* freeze rows.
- **Remaining action:** none now. Surface it explicitly when the user decides to start integration —
  it is the concrete COPPA-shaped consequence of the freeze.
- **Owner type:** user (at integration), then engineering
- **Reopen condition:** integration start (S44), or an explicit user instruction to finalise the §3.1
  auth option.
- **PROJECT_STATE?** yes — deferred, launch-blocking-at-integration
- **Historical/archive only?** no

### `RETENTION-CLUSTER` — five retention windows, three policy families, one job nobody schedules, and an undischarged privacy notice

- **Work/Issue ID (topic key):** `RETENTION-CLUSTER` (D-333 dry-run / DRIFT-45 / DRIFT-46 / WORK-19 /
  WORK-21 / WORK-22 / §8-21 / D-114 §4 privacy notice / REQ-18 invalid-output capture)
- **Members:** E2-10 (D-333 dry-run), E2-11 (D-114 §4 privacy notice), E1-102 (WORK-19),
  E1-104 (WORK-21), E1-105 (WORK-22), E1-131 (§8-21), E3-45 (DRIFT-45), E3-46 (DRIFT-46),
  E1-3 (REQ-18), E5-22 (REQ-18 deployed half), E1-22 (ARCH-19, storage-split anchor)
- **Description:** Retention is governed by **three unlinked policy families**: D-114 §1's 90/90/365
  on derived-text tables, D-153 §2's 365 days on `learning_events`, and D-333's 30/90/180 on LangGraph
  checkpoints. D-333 cites none of D-072/D-114/D-126, so presenting it as one chain conflates two
  families (the supersession map's confidence on that link is explicitly **LOW**). D-333's status is
  `implemented, dry-run by default`, so the checkpoint windows **delete nothing today**, and no entry
  states the condition or date on which dry-run is lifted. The floors *are* chosen and in code —
  completed 30 / abandoned 90 / chat 180 days — with `apply_enabled()` true only for an explicit
  `CHECKPOINT_RETENTION_APPLY=true` and the reason written in place: "A job whose failure mode is
  silently deleting a K-12 student's learning history does not get to delete by default." The job is
  **absent from terraform entirely**, deliberately, because "scheduling it before this one would be
  actively unsafe". Consequences: chat checkpoints are **unbounded in practice** (2,178 threads /
  35.6 MB = 19.3% of checkpoint bytes) and abandoned sessions — **77% of bytes** (`pre_exam` 64.7% +
  `study` 12.4%) — were scoped out by the user, against the document's own counter-recommendation of a
  90-day floor as "a bigger, more honest win". The §9.1 age floor is unchosen; the dry-run reports zero
  eligible threads at 30, 90 and 180 days, so the choice costs nothing today and can be made on
  principle. Spanning all of it, **D-114 §4's privacy-notice obligation is undischarged** and now
  covers at least five windows across three entries with no single reconciled statement. A separate
  member: the `rag_answer` path has a measured ~2–4% `schema_invalid` rate whose invalid text is
  deliberately **not captured** pending a PII decision, so the failures cannot be diagnosed — and no
  schema-invalid capture exists on the deployed side either.
- **Domain:** privacy / data lifecycle (minors' data)
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:736-742`, `:753-757`, `:762-774`;
  `CLAIM_LEDGER.md:266`, `:959`, `:3085`, `:3111`, `:3124`, `:3576-3586`;
  `REPOSITORY_DRIFT_REGISTER.md:526-535`, `:537-546`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:479-489` (REQ-18);
  `U7_CHECKPOINT_CONSOLIDATION.md:52-63`, `:261-263`, `:268-273`, `:276-279`
- **Related claim IDs:** WORK-19, WORK-20, WORK-21, WORK-22, WORK-23, WORK-35, ARCH-04, ARCH-05,
  ARCH-19, SEC-13, SEC-20, TEST-10, REQ-18, REQ-25
- **Related decision IDs:** D-072, D-114 §1/§4, D-126, D-153 §2, D-322 §4, D-331, D-332, D-333,
  D-135
- **Repository evidence:** `apps/learning-api/src/.../checkpoint_retention_cli.py:5-7`, `:19-24`,
  `:23`, `:28-34`, `:88-90`, `:90`, `:97-99`; `_chat_thread_ids` classifies "chat" by **two** positive
  conditions precisely so an unprojected learning thread cannot be deleted under the chat policy;
  `terraform/modules/scheduled-jobs/main.tf:41-51` explains the absence; a `checkpoint_retention`
  grep over `terraform/` returns nothing. `test_checkpoint_retention.py` ran inside a 55-test batch,
  all passed, including `test_apply_is_off_unless_explicitly_true` and the two-condition chat
  classifier — so the policy is implemented **and tested** and **not scheduled**. No schema-invalid
  capture is configured anywhere.
- **Deployed/live evidence:** the four *other* nightly job schedules exist in AWS (ARCH-04, confirmed
  exact including the per-job retry asymmetry `memory-consolidate = 0`); **no `checkpoint-retention`
  schedule exists** and no deletion job beyond the two enabled purges. Schema-invalid capture is
  absent from the deployed stack too: **no schema-invalid metric filter on any of the five log
  groups** (7 filters per app group, 11 on `ops-task`, 0 on both `/emf` groups; an env-var name scan
  for `SCHEMA|INVALID|CAPTURE|REPAIR|SAMPLE` returned `NONE-MATCHED`), so the documented
  schema-invalid rate has **no live source** and cannot be re-measured from CloudWatch. The precision
  of that negative matters: what is proven is the absence of **CloudWatch-side capture**, not the
  absence of the underlying event.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-7**
- **Justification:** one coherent cluster, not six items. Choosing any single floor in isolation adds a
  fourth policy family, and the causal chain runs: no reconciled retention policy → no statable
  windows → the first-visit notice cannot be written → S45 cannot build it. That makes the retention
  decision the **first unblocked step** toward a launch-gating privacy requirement, and it is **not**
  frozen by D-152. The dry-run default is good engineering, not a defect — the defect is that nothing
  re-raised scheduling after the safety prerequisite was satisfied. A closure recorded on code
  presence alone would be wrong.
- **Remaining action:** **Precondition, carried verbatim:** D-333's own user instruction — "Before
  deleting any eligible checkpoint, run long-term memory consolidation first" — must be **verified
  implemented before any dry-run flip**. Then the user decides, as one bundle: lift D-333's dry-run;
  schedule the DRIFT-45/46 jobs; set the U7 §9.1 age floor; scope chat checkpoints (WORK-21) and
  abandoned sessions (WORK-22, 77% of bytes); reconcile the five windows into one statement; discharge
  D-114 §4's privacy notice (content and timing user-owned, and the notice must state honestly that
  some windows are not yet enforcing); and rule on REQ-18 — may schema-invalid LLM output, possibly
  embedding student text, be stored for triage? The privacy-notice **drafting** becomes
  `ACTIVE_IMPLEMENTATION` once content and timing are decided. DRIFT-09 (the purge unreachable on the
  cancelled-resume path) is a **separate** entry, `SEC-13-PURGE`, and is not closed by any retention
  schedule.
- **Owner type:** user, then engineering (scheduling, the notice draft, capture)
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `WORK-35-LEDGER` — the U7 consolidation criteria are gated on a free staging measurement nobody has taken

- **Work/Issue ID (topic key):** `WORK-35-LEDGER` (OPEN_DECISIONS #4 / ROADMAP U7). See §0.6 for the
  WORK-35 namespace split.
- **Members:** E1-118 (WORK-35, ledger), E7-12
- **Description:** Against three pruning options the user chose **option D, which was not on the
  list**: "Consolidate the checkpoint into long-term durable memory according to some criteria, then
  keep it there" — reframing the question from how long to hold working state to what in a finished
  session is worth remembering. The decision explicitly requires "design review before code; staging
  numbers before sizing", and routes to ROADMAP U7. `packages/memory` (S25) already consolidates and
  already has a scheduled entrypoint. The sizing evidence on record is **dev-DB only**:
  `checkpoint_writes` 5,290,217 rows / 2557 MB, `checkpoints` 1,245,390 / 1872 MB, blobs 339 MB ≈
  **4.8 GB over 6.5 M rows, ~37× `question_variants`** (352,198 / 127 MB), after ~4 weeks *including
  load tests*. **No staging measurement has been read**, and the decision says to read it before
  sizing N. Retention N is also supposed to align with the Privacy Notice's existing 90/90/365 windows
  rather than inventing a second number, which removes most of the discretion.
- **Domain:** data lifecycle / memory consolidation
- **Original source(s):** `CLAIM_LEDGER.md:3293`; `OPEN_DECISIONS.md:171-216`, `:34-35`;
  E7's method note on the U7 measurement
- **Related claim IDs:** WORK-19, WORK-20, WORK-21, WORK-22, WORK-23, ARCH-19
- **Related decision IDs:** OPEN_DECISIONS #4, D-322 §4, D-331, S25, ROADMAP U7
- **Repository evidence:** `packages/memory` consolidates and has a scheduled entrypoint;
  `session-consolidate` is first in `locals.jobs` with `cron(0 18 * * ? *)`. The repository can show
  the mechanism exists; it cannot show what staging holds.
- **Deployed/live evidence:** the `session-consolidate` schedule is DEPLOYED_CONFIRMED (cron, timezone,
  target, retries all exact). The staging *sizing* numbers have never been read — that read needs a
  database session (`DB-CONTENT-VERIFY`).
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** the *decision* is taken (option D). What remains is an engineering design review
  gated on an **unread free measurement**, which is the prerequisite the decision itself names. It
  becomes a user question only if the criteria turn out to trade privacy retention against learning
  value, and that cannot be known before the measurement. Take the measurement first.
- **Remaining action:** take the staging measurement (free), then hold the design review and size N
  against the Privacy Notice's existing windows. Note the adjacent unresolved fact: DRIFT-09 records
  that no retention job covers `checkpoint_writes.__resume__` rows for live threads, and **D-420
  deliberately added redacted visitor free text to exactly that column**. Not urgent at today's
  volumes; urgent the moment real students arrive.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `LANGSMITH-RETENTION` — the SaaS account's run-retention setting has no in-repo expression and has never been read

- **Work/Issue ID (topic key):** `LANGSMITH-RETENTION` (SEC-23 / DRIFT-83)
- **Members:** E5-7, E3-58:DRIFT-83
- **Description:** The LangSmith account's **run-retention setting** has no in-repository expression at
  all and is reachable only through LangSmith's own console or API. It matters because trace payloads
  are governed by the project's no-PII rule and `HIDE_INPUTS`/`HIDE_OUTPUTS` are **client-side** flags
  — the repository can show what it intended to send, never what the SaaS stored or for how long. The
  item was routed out of Phase 3B-1 as external and out of 3B-2 as not-its-work; nothing has verified
  it.
- **Domain:** security / privacy / third-party data retention (minors' product)
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:592-596` (§3.2 external), `:446`
  (COST-27's masking note); `DEPLOYED_INFRA_DRIFT_REGISTER.md:388-390`;
  `REPOSITORY_DRIFT_REGISTER.md:946` (DRIFT-83)
- **Related claim IDs:** SEC-23, COST-27, ARCH-30
- **Related decision IDs:** D-242, SPEC §5.32.1
- **Repository evidence:** client-side masking is forced in code, not `setdefault`, so an env var
  cannot opt out, and a test asserts it is not optional; the per-environment project is real and
  env-driven (`LANGSMITH_PROJECT = var.name_prefix`). There is **no repository expression whatsoever**
  of the account's retention setting, so the repository cannot be right or wrong about it — it is
  silent, and nothing in the repository would detect its absence.
- **Deployed/live evidence:** AWS shows tracing enabled (`LANGSMITH_TRACING = "true"`,
  `LANGSMITH_PROJECT = intellichoice-staging`, `LANGSMITH_WORKSPACE_ID` present, one shared
  `LANGSMITH_API_KEY` secret ARN) and nothing more. **No AWS API can report a LangSmith account
  setting.** Genuinely out of reach from this account.
- **Final disposition:** `BLOCKED` → direct ask **UD-11**
- **Justification:** blocked on an external console the audit lane does not touch, not on effort. This
  is the one privacy-relevant item in the infrastructure lane that no amount of AWS reading can close,
  and the alternative to asking is that it stays open indefinitely.
- **Remaining action:** a two-minute user action — open LangSmith → workspace settings → retention and
  report the value — plus the judgement of what retention is acceptable for a K-12 minors product.
  Pair it with `LANGSMITH-INGEST`: if traces are failing to ingest, **less** data reached the SaaS than
  the documents assume, which is relevant in the *safe* direction but is not a substitute for reading
  the setting.
- **Owner type:** user (console read) + user (privacy judgement)
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `IMAGE-WORK-PARK` — SPEC §5.17's solution-image requirements have no subject, and two preconditions gate any future build

- **Work/Issue ID (topic key):** `REQ-23` (image-work park; spans REQ-21, REQ-22, REQ-24, SEC-14,
  SEC-15)
- **Members:** E1-5 (REQ-21), E1-6 (REQ-22), E1-7 (REQ-23), E1-8 (REQ-24), E1-35 (SEC-14),
  E1-36 (SEC-15)
- **Description:** SPEC §5.17 requires validation, malware scanning, ephemeral encrypted storage and
  immediate deletion of solution images, with the S3 lifecycle rule explicitly a final safeguard
  rather than the primary mechanism; §5.17.3 forbids image analysis from affecting the score;
  CLAUDE.md rule 8 states immediate deletion as active product behaviour. **The feature does not
  exist.** The user declined S29 before implementation: no `BlobStore`, no `MalwareScanner`, no
  `BedrockGateway.analyze_image` implementation, no upload router, no executable math validator, no
  `"image"` intervention choice. Two **unresolved preconditions** gate any future build: (1) a minor's
  solution photo can incidentally capture a face, other homework or a home background — a privacy
  question the consent language assumes away, including whether parent-level opt-in is needed; and
  (2) every supporting dependency (a real malware scanner, real S3 encryption at rest) is still on
  D-002's no-real-credentials footing.
- **Domain:** product requirements / privacy (minors)
- **Original source(s):** `CLAIM_LEDGER.md:305`, `:318`, `:331`, `:344`, `:1353`, `:1366`;
  `SPEC.md:1710-1770` (§5.17), `:1736-1754`, `:1756-1770`, `:27`; `CLAUDE.md:104-105`;
  `TRACEABILITY.md:230`, `:250-253`; `DECISIONS.md:2025-2049`
- **Related claim IDs:** REQ-21, REQ-22, REQ-23, REQ-24, SEC-14, SEC-15, COST-02, WORK-32
- **Related decision IDs:** D-078 (S29 deferred), D-002, D-020, S29
- **Repository evidence:** a five-pattern absence sweep confirms it: zero hits for `BlobStore`,
  malware scanning, `solution_image`, `image_url`, `base64`; no `multipart`/`UploadFile`/`File(`
  endpoint anywhere; the intervention enum is closed at hint/solution/video/continue; `analyze_image`
  occurs once, in a docstring recording its own absence; `registry.py:74` reads "No image-upload
  feature exists to emit this event." (`REPOSITORY_DRIFT_REGISTER.md:792`, DRIFT-69).
- **Deployed/live evidence:** n/a — repo-only; there is no deployed image path to observe.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** an explicit user deferral with the absence enumerated, and the requirements are
  correctly absent rather than broken. The two preconditions become **reopen conditions on the park**
  rather than open questions now — nothing needs deciding while the feature is not being built.
- **Remaining action:** none while D-078 holds. Two documentation tails are tracked elsewhere: the
  missing SPEC/CLAUDE.md amendment markers so §5.17 and rule 8 stop reading as descriptions of live
  behaviour (`AMENDMENT-SWEEP`, and DRIFT-69 in `BATCH-LOW-OVERSTATEMENT`), and the fact that SPEC
  §5.1.4 still lists image analysis as an interrupt-gated action. The live consequence is that T-02's
  disclosure list promises the behaviour — carried by `DISCLOSURES-LEGAL` (WORK-32).
- **Owner type:** user (to reopen); documentation for the markers
- **Reopen condition:** the user reopens §5.17. On reopening, both preconditions must be answered
  first: the incidental-capture privacy question (with counsel, including parent-level opt-in) and the
  real-credential footing for a malware scanner and S3 encryption at rest.
- **PROJECT_STATE?** yes — parked, with the two preconditions recorded as reopen gates
- **Historical/archive only?** no

### `SEC-17-GUARDDUTY` — GuardDuty is absent as an account fact, by a costed decision

- **Work/Issue ID (topic key):** `SEC-17` (with TEST-09, SEC-16)
- **Members:** E1-37 (SEC-17), E1-59 (TEST-09 GuardDuty half), E5-26 (TEST-09 / SEC-16)
- **Description:** GuardDuty, required by SPEC §5.30.3, is absent. D-125 deferred it with a written
  reason — an always-on paid service against a no-user staging account, the same argument as WAF's
  D-087 — and tracked it to S50 A7. T-01 closed 2026-07-30 as **two opposite answers**: CloudTrail
  built and live-verified, GuardDuty deferred. The record changed, not the state.
- **Domain:** security posture
- **Original source(s):** `CLAIM_LEDGER.md:1392`, `:2128`; `TRACEABILITY.md:649`, `:700-720`,
  `:736-744`; `SPEC.md:2868`; `DEPLOYED_INFRA_STATE_EVIDENCE.md:505-515` (TEST-09), `:283-293`
  (SEC-16); `DEPLOYED_INFRA_DRIFT_REGISTER.md:412-415`
- **Related claim IDs:** SEC-16, SEC-17, TEST-06, TEST-09
- **Related decision IDs:** T-01, D-125, D-087, D-124, S50 A7, AUD-F-12 [AUDIT_FINDINGS]
- **Repository evidence:** **no `aws_guardduty_*` resource anywhere**, deliberate and annotated at
  `terraform/environments/staging/main.tf:740-748`. CloudTrail is wired at `:743-748` with
  multi-region, global events and log-file validation all `true`, no `event_selector`, and a 90-day
  bucket lifecycle.
- **Deployed/live evidence:** GuardDuty returns **`{"DetectorIds": []}`** — an **account** property,
  not merely an absence from terraform, so nobody enabled it out of band. CloudTrail is
  `IsLogging: true` with delivery ~90 s fresh (`LatestDeliveryAttemptSucceeded: 2026-08-20T00:06:12Z`),
  multi-region and log-file-validated, management events only; an `ap-northeast-1` delivery path under
  a `us-east-1` home region independently proves multi-region is *functioning*, not merely set.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** a recorded decision with a stated cost rationale, and the deployed state matches
  the repository exactly. Cleanly confirmed, no remaining security work.
- **Remaining action:** none for the control. One documentation residual is tracked elsewhere: the
  ROADMAP and INTEGRATION_PLAN **S50 A7 scope lists do not name GuardDuty** (DRIFT-02, in
  `TRACEABILITY-ARITHMETIC`), so a required control is deferred to a destination that does not list
  it; and SPEC §5.30.3 carries no deferral marker (`AMENDMENT-SWEEP`). Two residual precision notes:
  `list-detectors` is **regional** and only `us-east-1` was checked, and CloudTrail's bucket-policy
  statements (the two `aws:SourceArn` conditions) were not read, so that half is config-only evidence.
- **Owner type:** documentation (the scope-list edit); user at production posture review
- **Reopen condition:** production posture review, or staging ceasing to be synthetic — where
  always-on cost trades against threat detection on a system serving minors.
- **PROJECT_STATE?** yes — parked
- **Historical/archive only?** no

### `SEC-18-WAF` — WAF is absent and the in-memory rate limiter weakens as the service scales

- **Work/Issue ID (topic key):** `SEC-18`
- **Members:** E1-38
- **Description:** AWS WAF is absent and deferred to S50 A7 (D-087), which added per-IP rate limiting
  as an in-memory stopgap explicitly "not a replacement for one". D-181 measured the stopgap's
  ceiling as **per task**: one source IP gets `6000 × running tasks` requests/minute, accepted as ~3×
  a legitimate burst.
- **Domain:** security posture
- **Original source(s):** `CLAIM_LEDGER.md:1405`; `TRACEABILITY.md:734`;
  `INCIDENT_RESPONSE.md:29-33`, `:209-213`
- **Related claim IDs:** SEC-17, SEC-18, SEC-19, INT-31, TEST-06
- **Related decision IDs:** D-087, D-181, D-002, S50 A7
- **Repository evidence:** the middleware is in-process; no WAF resource exists in `terraform/`.
- **Deployed/live evidence:** WAF returns `{"WebACLs": []}` on `--scope REGIONAL` **and** on
  `--scope CLOUDFRONT` — both absences confirmed as account facts. This also answers
  FINAL_ARCHITECTURE's open question about whether S33/S34's "WAF-class controls" shipped: they did
  not.
- **Final disposition:** `DEFERRED`
- **Justification:** measured, reasoned and owned by S50 A7. Recorded as DEFERRED rather than parked
  because the per-task ceiling means the stopgap **weakens as the service scales**, which is the
  opposite of what a stopgap should do — that is a real property, not a wording nit.
- **Remaining action:** none at pilot scale. Before public launch, decide WAF (a recurring cost).
  Note S50 A7 is **not** inside the D-152 freeze, so two launch-blocking security items sit in an
  unfrozen-but-unstarted block while one launch-blocking privacy item (S45) sits in a frozen one.
- **Owner type:** user (before public launch)
- **Reopen condition:** public launch, or staging serving anything real — the same trigger as SEC-17
  and OPEN_DECISIONS #8's historical condition.
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `DRIFT-12-ADMIN-ROLE` — SPEC's six-role matrix names an admin row with no role, no route and no enforcement point

- **Work/Issue ID (topic key):** `DRIFT-12` (SEC-04; also SEC-09, REQ-07)
- **Members:** E3-12
- **Description:** Four of SPEC §5.30.2's six rows are enforced in the query layer, two partially, one
  is absent. `Role` declares exactly STUDENT/PARENT/TUTOR/BRANCH_MANAGER — **no admin member** — and
  no admin route or admin role check exists in either API; the only "admin" strings are the
  admin-escalation email recipient. The admin row is therefore **unenforceable as specified** rather
  than unenforced. Tutor and branch_manager have the audience predicate enforced in SQL but no
  per-student scope, and their `branch_external_id` resolves to `None`.
- **Domain:** security / authorization
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:158-167`
- **Related claim IDs:** SEC-04, SEC-09, REQ-07
- **Related decision IDs:** D-086, D-153 §5 (the allowlist constraint)
- **Repository evidence:** `packages/shared/src/intellichoice_shared/auth.py:13-17` (the four-member
  enum); `apps/chat-api/.../role_access.py:119-145`;
  `apps/learning-api/.../authorization.py:30-45`, `:47-71`; `routers/parents.py:44-48`;
  `packages/db/.../repositories/rag.py:47-84`; `TRACEABILITY.md:185`. The fail-closed direction is
  intact: writes 403, so the exposure is read-scope only.
- **Deployed/live evidence:** n/a — repo-only. Deployed role behaviour matches the repository; the
  16 gate tests for SEC-25/ARCH-03 passed and zero external identity providers exist.
- **Final disposition:** `DEFERRED`
- **Justification:** S43/S44-bound. Defining admin's fate — build it, scope it to the S43/S44
  allowlist, or amend the matrix — is a scope question that only makes sense once the real profile
  adapter and the role allowlist exist, both of which are frozen. A role that exists in the contract
  and not in the type system is a scope decision, not an edit, but the occasion for it is integration.
- **Remaining action:** now: a documentation marker on SPEC §5.30.2 recording that the admin row is
  unenforceable as specified (folded into `AMENDMENT-SWEEP`). At S43/S44: decide admin's fate. The
  per-student-scope half is the same gap as `R8-READ-SCOPE` and must not be counted twice.
- **Owner type:** documentation now; user + engineering at S43/S44
- **Reopen condition:** S43/S44 (integration) start.
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `G2-LOCATOR-PURGE` — the branch-locator purge was never confirmed on staging

- **Work/Issue ID (topic key):** `G2` (chain G2; D-113 §1)
- **Members:** E2-13
- **Description:** The active decision — D-113 §1's `purge_resume_writes` on `channel = '__resume__'`
  — records *"Not yet on staging"* at the time of writing, and nothing the supersession map read
  confirms that the post-deploy live probe was ever taken. This is a privacy mechanism (raw
  coordinates in LangGraph checkpoint writes) whose live behaviour is unverified. D-045 additionally
  still asserts "briefly" and "not fully eliminable", both measured false, with no forward pointer, so
  a reader arriving at D-045 first gets no signal at all.
- **Domain:** privacy / branch locator
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:887-889`, `:896-898`
- **Related claim IDs:** SEC-12, SEC-13, REQ-28
- **Related decision IDs:** D-045, D-101, D-113 §1
- **Repository evidence:** the purge exists and is parameterized; its reachability defect is
  `SEC-13-PURGE`. *(2026-08-22: that defect is repo-fixed at `b6fa067` but NOT deployed — staging
  runs `gha-44a12dfc9549`. If this entry's staging `SELECT` over `checkpoint_writes` is ever run,
  state which build it probed: before the next image deploy it tests the defective code, after it
  the fixed code — LB-05.)*
- **Deployed/live evidence:** **not established.** Phase 3B-1 could not query database contents
  (`DB-CONTENT-VERIFY`) and Phase 3B-2's chat lane probed a guest QA turn, not a location consent, so
  no live read of `checkpoint_writes` exists in the corpus.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** the map establishes absence of confirmation, not a defect. One live query would
  settle it, and that query is the same read-only database session `DB-CONTENT-VERIFY` needs.
- **Remaining action:** if a read-only staging database session is authorised (rider on UD-2), add one
  `SELECT` over `checkpoint_writes` where `channel = '__resume__'` to the query list. Separately, D-045
  needs a forward pointer (a documentation edit, folded into `DOC-DECISION-LOG-CORRECTIONS`).
- **Owner type:** engineering (if the session is authorised); documentation for D-045's pointer
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes — as an unconfirmed-not-refuted record

### `FIRST-VISIT-REVERIFY` — the first-visit notice's "True because" rows are dated code measurements

- **Work/Issue ID (topic key):** `FIRST-VISIT-REVERIFY` (DOC-FIRST-VISIT-NOTICE)
- **Members:** E6-37
- **Description:** Every "True because" row in `FIRST_VISIT_NOTICE.md` is a dated code measurement.
  The 102-of-112 video figure in it is "exactly the class of line OPEN_DECISIONS flags as having gone
  100× stale before". The owner label "S45" is ambiguous between ROADMAP's unstarted consent session
  and PROGRESS's completed unnumbered "S45". The inventory's explicit instruction is to **re-verify the
  rows at S45 start**, against HEAD at that time rather than against these rows.
- **Domain:** consent / first-visit disclosures / launch copy
- **Original source(s):** `DOCUMENT_INVENTORY.md:703-711`; overlaps
  `DOCUMENTATION_RISK_REGISTER.md:311-317` (R5.7), `:358-367` (R6.4)
- **Related claim IDs:** T-02
- **Related decision IDs:** D-114, D-127, D-333
- **Repository evidence:** repository-side measurements only, all dated.
- **Deployed/live evidence:** n/a — S45 is unstarted, so nothing is deployed.
- **Final disposition:** `DEFERRED`
- **Justification:** scheduled work attached to an unstarted session, not outstanding drift. The three
  §5 product gaps inside the same file *do* need a person and are carried by `DISCLOSURES-LEGAL`.
- **Remaining action:** re-verify the "True because" rows at S45 start. The file is also **not in
  CLAUDE.md's index** (`RISK-GROUP-INDEX`), so the S45 session may never find its own stated input,
  and the "S45" label collision (`RISK-R6.4-SESSION-LABELS`) must be resolved before anyone can state
  who owns it.
- **Owner type:** engineering at S45
- **Reopen condition:** S45 start.
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `DRIFT-66-NL2SQL` — SPEC §5.26.3's internal NL2SQL subsystem is unowned in both directions

- **Work/Issue ID (topic key):** `DRIFT-66` (REQ-06, REQ-05)
- **Members:** E3-57:DRIFT-66 (batch D exception), E1-1 (REQ-06)
- **Description:** SPEC §5.26.3 permits an internal NL2SQL for dev, eval and analytics under twelve
  named controls (SELECT-only, allowlists, a PII-column prohibition, a mandatory LIMIT, an
  SQLGlot-class parser, an audit log). A corpus-wide `NL2SQL` grep returns 10 non-ledger hits, **every
  one** addressing only the *runtime* prohibition or the untestability of the SQL-parser eval item;
  **none** says the internal dev/eval/analytics variant is planned, dropped or partially present.
  `SPEC.md:2641-2643` carries no amendment or deferral marker, and TRACEABILITY says ROADMAP S30's
  SQL-parser validation was never built because there is no NL2SQL feature. So this is an unowned spec
  requirement with no entry in ROADMAP or DECISIONS in *either* direction.
- **Domain:** deterministic-core guarantees (non-negotiable rule 2)
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:759` (DRIFT-66); `CLAIM_LEDGER.md:110`;
  `SPEC.md:2652-2690`; `TRACEABILITY.md:161-164`
- **Related claim IDs:** REQ-05, REQ-06
- **Related decision IDs:** none — the absence is the finding
- **Repository evidence:** the **runtime** prohibition is separately confirmed and holds: no
  `QueryIntent` model, every RAG query a parameterized `select()`, and the only raw `text()` calls in
  runtime paths are advisory locks, `pg_notify` and a parameterized purge. Nothing implements the
  internal variant.
- **Deployed/live evidence:** n/a — repo-only. No runtime NL2SQL exists to observe, consistent with
  the repository.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(d)**
- **Justification:** it grades LOW because nothing user-facing depends on it; the "unowned" property is
  what makes it decision-worthy. One line either way closes it, and no evidence can choose the
  direction.
- **Remaining action:** one DECISIONS line: build, scope, or formally drop SPEC §5.26.3's internal
  NL2SQL pipeline. If the answer is "drop", SPEC §5.26.3 also needs an amendment marker
  (`AMENDMENT-SWEEP`).
- **Owner type:** user (one line), then documentation
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `DRIFT-70-CONSENT-GATE` — the consent-verification half is enforced; both known gaps are tracked elsewhere

- **Work/Issue ID (topic key):** `DRIFT-70` (REQ-27, REQ-25, REQ-26) — batch G exception
- **Members:** E3-60:DRIFT-70
- **Description:** `TokenClaims` carries exactly the ten named claims, no extras and no omissions;
  `parental_consent_verified` is read by `account_refusal_reason()` from four app-level sites; and the
  gate **fails closed** because `AGE_BANDS_NOT_REQUIRING_PARENTAL_CONSENT` is a deliberately empty
  frozenset, so today every student needs verified consent. Two known gaps: no student-facing notice in
  either web app, and the claim set is minted only by `fake_auth.py` — production's real token is
  `{id, iat, exp}` only, expected under D-152.
- **Domain:** consent / auth
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:803` (DRIFT-70)
- **Related claim IDs:** REQ-27, REQ-25, REQ-26
- **Related decision IDs:** D-152, T-02
- **Repository evidence:** the ten-claim `TokenClaims` model, four consuming sites and the empty
  frozenset, all as described; the backend refusal path's tests ran and passed inside Batch 1's
  `183 passed`.
- **Deployed/live evidence:** both apps carry `*_DEV_TOKEN_ENDPOINT_ENABLED=false`, confirming staging
  `/dev/token` is the D-097 shared-secret path — so the fake issuer is the live issuer, as expected
  pre-integration.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** both halves are already tracked and dispositioned — the notice by T-02
  (`DISCLOSURES-LEGAL`) and the issuer by D-152 (`REQ-27-TOKEN-CONTRACT`) — so nothing new is owed
  here. The one carve-out is not parked: the empty frozenset is the load-bearing safety property and it
  has no test, which is `REQ-27-FROZENSET` (`ACTIVE_IMPLEMENTATION`).
- **Remaining action:** none in this entry. Cross-references: `REQ-27-FROZENSET` (the test),
  `DISCLOSURES-LEGAL` (the notice), `REQ-27-TOKEN-CONTRACT` (the issuer).
- **Owner type:** none (tracked elsewhere)
- **Reopen condition:** the notice half reopens at S45; the issuer half at S44.
- **PROJECT_STATE?** yes — parked, as a pointer
- **Historical/archive only?** no

---

## §2 Cost & spend

### `BUDGET-GROSS-SPEND` — the $20 budget is breached and ~$230 of credits hide a ~$250/mo gross run rate

- **Work/Issue ID (topic key):** `RD-03` (COST-15 / COST-16 / COST-25-billing / credit horizon)
- **Members:** E5-4, E5-5, E5-14 (billing input), E2-8(b) (the credit-burn horizon half)
- **Description:** `intellichoice-staging-monthly-budget` reads `ActualSpend $20.939` against a
  `$20.00` limit (**104.7%**) with its `ACTUAL > 80%` notification in **ALARM**. Because the repository
  budget sets `IncludeCredit: true` it measures **post-credit** spend. Cost Explorer by `RECORD_TYPE`
  for 2026-08-01…08-20: `Usage $249.9294`, `Tax $1.30`, `Credit $-230.2909`. The true run rate is
  therefore **~$250/mo gross** (Bedrock Haiku 4.5 dominant at 93.8% of *net*, plus NAT ~$32.9/mo, plus
  infrastructure) and it is **invisible to every net-spend control until the credits are exhausted**, at
  which point the same workload registers as roughly **12×** the configured limit. Credit expiry is not
  exposed by any read-only API, so *when* the step change lands cannot be predicted — D-139 §3 already
  established that every price in the capacity chain is credit burn, not cash, and that "the date at
  which any of it becomes payable is **unknown**", and nothing closed it. A second budget exists that is
  **not in terraform**: `"My Monthly Cost Budget"`, `$10.00` limit, `CostFilters: null`,
  `CostTypes: null`, `ActualSpend $251.229`, three notifications (`ACTUAL>100` ALARM, `ACTUAL>85`
  ALARM, `FORECASTED>100` OK), `LastUpdatedTime 2026-08-19T15:56:54Z` — console-created, and currently
  the **only** control that sees gross spend, and it is firing. Internal oddity recorded: the repository
  budget's `FORECASTED > 100%` notification still reads `OK` while ACTUAL has already crossed 100%.
- **Domain:** cost / spend control / infrastructure-as-code hygiene
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:154-186`, `:176-179`, `:362`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:321-343` (COST-15/COST-16), `:339` (observation 2), `:71`
  (ARCH-02 default VPC), `:417-427` (COST-25), `:453-463` (COST-28 NAT cost);
  `DECISION_SUPERSESSION_MAP.md:700-712`
- **Related claim IDs:** COST-15, COST-16, COST-25, COST-28, ARCH-02
- **Related decision IDs:** D-136 (the price table and the cost model built on it), D-139 §3, D-401
- **Repository evidence:** `aws_budgets_budget.monthly` at
  `terraform/modules/observability/main.tf:1-23`, `limit_amount = tostring(var.monthly_budget_usd)`
  default 20, exactly the two configured notifications, both emailing `var.notification_email`. **No
  gross/credit-excluding budget is configured anywhere**, and nothing in the repository mentions a
  second budget — so anyone reading the repository would conclude the $20 net budget is the whole
  spend-control surface. There is correctly no `aws_default_vpc` resource.
- **Deployed/live evidence:** the repository budget exists exactly as configured, breached,
  `IncludeCredit: true`, `LastUpdatedTime 2026-08-19T15:48:57Z`, subscriber `k***@gmail.com` on both
  notifications. **Two** budgets exist; the unmanaged one is doing the load-bearing gross-spend work,
  is invisible to `terraform plan`, will not be reproduced in any other environment, and can be
  deleted by anyone in the console without trace. Also present and benign: the account's untouched
  default VPC `vpc-0a540ff27b5b06b31` (`172.31.0.0/16`, `IsDefault: true`, untagged) alongside the
  managed `intellichoice-staging-vpc` — recorded so nobody later "discovers" a second VPC.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-3**
- **Justification:** spend posture is the user's money call, explicitly
  (`DEPLOYED_INFRA_DRIFT_REGISTER.md:186`, `:362`). What makes it urgent rather than untidy is the
  **latent step change with an unknowable date**.
- **Remaining action:** the user decides: raise, accept or re-scope the $20 net limit; and whether a
  gross (credit-excluding) control is wanted *before* the credits run out — recommended framing is to
  keep the net budget as an early-warning tripwire **and** add a terraform-managed gross budget at
  ~$300, versus raising the single net limit. Either way the console budget should not stay as an
  undocumented artifact: adopt it into terraform or delete it as shadow configuration. Inputs to carry:
  alarm billing ~$2.40/mo, X-Ray forecast over free tier, NAT $32.9/mo gross. Two mechanical riders are
  separated from the judgement and tracked as their own entries: `D136-PRICE-TABLE` (the uncaveated
  price table) and `COST-25-ALARM-COUNT` (the billing line for the cost model).
- **Owner type:** user, then engineering (a small terraform change implements whatever is decided)
- **Reopen condition:** n/a — open now; and it re-opens by itself when credits are exhausted
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `SPEND-AUTHORIZATION` — the paid-measurement and spend-authorization bundle

- **Work/Issue ID (topic key):** `SPEND-AUTHORIZATION`
- **Members:** E7-2 (four arms), E7-11 (depth generation $13–16), E6-12 (whole-directory e2e re-run),
  E6-13 (access-hint recall re-measurement), E6-14 (real-Bedrock eval opt-ins), E1-112 (WORK-29 step 4),
  E5-23 (REQ-50(b) load-run cost note), E5-28 (the six behavioural queue items), E1-119 (WORK-36)
- **Description:** Six deferred measurements share one wallet and one shape — "is now the moment to
  spend?" **(1) Access-hint recall re-run**: `scripts/measure_access_hint_live.py` exists, 8 GATED + 5
  PUBLIC questions, guest path, `BASE = "https://d222glidpp4azv.cloudfront.net"`, `CONFIRM_PAID_RUN=1`
  guard; the rule is *frozen* (`access_probe_policy.py`'s last constant change is `e1ab0ad`,
  2026-08-04) and `git diff 44a12dfc9549..HEAD` on it is empty, so the deployed build carries the
  identical rule and D-351's baseline still applies — a 13-turn run "re-derives nothing statistically at
  n=8/n=6". **(2) Whole-directory staging e2e re-run** (`E2E_ARGS="tests/learning"`, ~37 tests
  including four band walks): deliberately not run, out of budget scope and **not** blocked by safety.
  It is the only way to reach the seventeen-spec cross-spec contention that produced the original
  2026-08-07 failure; today's run reproduced the two-test combination only. **(3) Two real-Bedrock eval
  opt-ins** (`CHAT_EVAL_REAL_BEDROCK=1`, `EVAL_REAL_BEDROCK=1`) — the suite's **only two skips**, so
  the free suite is structurally silent about real-Bedrock eval quality. Paid exposure was verified
  absent rather than assumed in the local run: `bedrock_call` lines reported `"duration_ms": 0.33`/`0.37`,
  i.e. `MockBedrockProvider`. **(4) Tutor-path reading level** (D-303): `tutor_chat_messages` holds 0
  rows, so measuring it means paying to generate a fresh sample. **(5) Depth generation**: 84 of 153
  occupied `(topic, tier)` cells at target, short **189 items** ≈ 315 candidates at the measured 60%
  acceptance ≈ **$13–16** and ~3.5 h wall clock at the account's measured ~1.5 candidates/min (which is
  account-capped — 3 parallel streams == 1). Every run sits behind a green preflight and an explicit
  `--run-budget-cents`, and D-193's per-candidate commit makes stopping part-way safe. **(6) WORK-29's
  step 4**, the hard-capped validation run, is the first paid step of the hint/solution review
  sequencing. Free-tier context: CloudWatch alarm and metric monitors **at limit** (10.0/10.0, forecast
  16.32) and X-Ray traces **91% used, forecast to exceed**.
- **Domain:** cost discipline / verification method
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:521-535`, `:285-289`, `:184-186`, `:397-404`;
  `LIVE_BEHAVIOR_EVIDENCE.md:140-160`, `:152-159`; `DEPLOYED_INFRA_STATE_EVIDENCE.md:491-501`,
  `:583-590`; `DEPLOYED_INFRA_DRIFT_REGISTER.md:370-386`, `:431-433`; `OPEN_DECISIONS.md:219-231`,
  `:36`; `CLAIM_LEDGER.md:3215`, `:3306`; `PROGRESS.md:1561`
- **Related claim IDs:** REQ-46, TEST-21, TEST-28, WORK-05, WORK-13, WORK-29, WORK-36, REQ-50, COST-25
- **Related decision IDs:** D-351, D-371, D-303, D-313, D-322 row 5, D-223, D-193, D-342, RD-04, RD-10
- **Repository evidence:** every instrument exists and was confirmed present; the two skips are the
  only two in the suite; the depth preflight and `--run-budget-cents` guard are in place. The
  repository holds the quoted numbers but no evidence they still hold.
- **Deployed/live evidence:** arms (1) and (2) must run **against the deployed build**, which is 10
  commits behind HEAD — so any run measures a mixture unless the spec or rule is verified unchanged,
  which is exactly what LB-05 did for `journey-student.spec.ts` and what the empty
  `access_probe_policy.py` diff does for arm (1). A deploy (UD-1) would change the build under test, so
  the order matters.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-2**
- **Justification:** real money on a credit-funded account whose free tier is at its limit and whose
  monthly budget is itself a flagged open call, and the technical value of two of the arms is *already
  known to be low*. That makes it purely a priority call. Phase 3B explicitly ruled these
  residual-not-blocking, so nothing waits on them.
- **Remaining action:** the user authorizes a subset or none (default: none — carry each claim
  as-documented with its n and its date, which is what the records already do). Two sequencing
  constraints must survive: the **whole-directory arm only after the `WORK-13-FIXTURES` fixture fix**,
  or it just re-measures a known bug; and the **WORK-29 arm needs exported model ids and a budget
  flag** — placeholder model ids fail into an opaque circuit breaker, and generation throughput is
  account-capped, so "just run it" is both a spend and a wall-clock commitment. **Rider:** authorize a
  time-boxed, read-only staging database session to close `DB-CONTENT-VERIFY` (WORK-20 / SEC-27 /
  INT-29-applied), and add `G2-LOCATOR-PURGE`'s one `SELECT` to it. `WORK-13` itself is **closed live**
  and must not be double-counted.
- **Owner type:** user
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `COST-06-FLUSH` — a duplicate-id branch loses paid spend from the row, the run total and the budget gate

- **Work/Issue ID (topic key):** `COST-06` (F-12 / DRIFT-18 / REQ-20 part)
- **Members:** E4-12 (F-12), E3-18 (DRIFT-18), E1-45 (COST-06), E1-4 (REQ-20)
- **Description:** Two branches, and only one is covered. The `_settle` **commit-time** branch adds
  cost to `summary.total_cost_cents` before incrementing, so money stays in the run total, and its test
  passed (`test_per_candidate_settlement_survives_a_duplicate_id` with
  `test_a_slots_rows_account_for_every_cent_the_slot_reports`, `2 passed`). The `run_plan`
  **flush-time** branch catches `IntegrityError`, rolls back and `continue`s at `pipeline_cli.py:618`
  **before** `spend += outcome.cost_cents` at `:619`, and never reaches `_settle`. Paid calls precede
  the row flush, so real spend on that branch reaches **neither the row, nor
  `summary.total_cost_cents`, nor the `spend` total the run-budget check reads** — which also means the
  defect can let a run exceed its budget. There is **no test in the repository** forcing an
  `IntegrityError` inside `run_plan`'s flush; the money loss is demonstrated by code path only. The
  related REQ-20 finding is the same gap from the spend-accounting side:
  `question_validation_runs.cost_cents` omitted the per-slot equation-design call, understating
  accepted rows by a measured 32.0%, partially remediated, with the `skipped_duplicate_id` path still
  untested and unattributable at row level. The ledger disagrees with itself here — COST-06 reads
  UNKNOWN and REQ-20 reads "CURRENT (partially remediated; one path still uncovered)" about the same
  path.
- **Domain:** cost accounting / pipeline correctness
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:545-565`, `:803-805`;
  `LOCAL_EXECUTION_EVIDENCE.md:806`; `REPOSITORY_DRIFT_REGISTER.md:224-233`;
  `CLAIM_LEDGER.md:292`, `:1708`
- **Related claim IDs:** COST-06, COST-05, COST-07, COST-08, REQ-20
- **Related decision IDs:** D-294, D-342 (the pipeline is parked); the user's standing rule that cost
  bugs are real production bugs
- **Repository evidence:** `packages/curriculum/src/.../pipeline_cli.py:295-312`, `:560-635` (the
  `continue` at `:618` preceding `:619`), `:577`; `ai_pipeline.py:981`, `:1328`, `:1600-1615`, `:2046`;
  `tests/test_authored_pipeline.py:1673-1716`. `REPOSITORY_DRIFT_REGISTER.md:228` carries the
  two-branch analysis. The code is **unfixed**.
- **Deployed/live evidence:** n/a — repo-only; the pipeline is an offline content path with no deployed
  surface.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** a cost bug on an error branch, per the user's standing rule, with the fix shape an
  engineering choice rather than a judgement. Two things must not be flattened: the green test covers
  the **other** branch, and execution "narrowed the conflict by half and could not close it" — so the
  claim's classification stays `CONFLICT`, neither confirmed nor refuted. D-342's parking lowers
  urgency but does not make an untracked paid-spend path correct.
- **Remaining action:** write the test that forces an `IntegrityError` inside `run_plan`'s flush (the
  fake gateway suffices — **no paid run needed**), then reorder the statement so `spend +=` and
  `_settle` run before the `continue`. Verify the budget-overrun consequence rather than asserting it:
  the source document stops at "incurred and then not attributed". Cheapest material item in the audit
  to close, and it retires a standing `CONFLICT`. Part of the three-test package with `SEC-13-PURGE`
  and `REQ-27-FROZENSET`.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no
- **⚠️ RESOLVED 2026-08-22 — implementation evidence supersedes this entry's disposition.**
  Fixed at `ba660e1` (PR #366), test-first: the forcing test recorded the pre-fix loss (exactly
  the colliding candidate's cents missing from `summary.total_cost_cents`), and a second test
  **measured the budget-overrun consequence** — with the budget below one candidate's cost, the
  pre-fix gate admitted, paid for and persisted a slot it should have refused. This resolves the
  entry's standing ledger `CONFLICT` in the confirming direction: the branch did lose the money.
  **One correction to the remaining-action wording above:** "reorder so `spend +=` and `_settle`
  run before the `continue`" was not implementable as written — `outcome` is never assigned on
  that branch (the exception escapes `generate_authored_candidate` with the cost trapped in its
  locals). The implemented shape carries the cost across the exception boundary
  (`DuplicateTemplateIdError(IntegrityError)` raised at the flushing `create_template`, the
  slot-level design/repair spend added on re-raise) and mirrors `_settle`'s commit-time
  accounting; `_settle` and its two tests are untouched. Known non-widened residuals, reported
  not fixed: a non-duplicate `IntegrityError` on the same path still carries no cost
  (theoretical — those keys are generated, not plan-reserved), and REQ-20's row-level
  attribution for skipped duplicates remains impossible (no row can exist for a taken id). No
  new judgment — no D-number; git history and `docs/log/2026-08-22-cost06-flush-orca.md` are
  the record.

### `COST-10-INPUT-BOUND` — the gateway has no input-token ceiling and the cost reserve hard-codes 2000 input tokens

- **Work/Issue ID (topic key):** `COST-10` (F-01 / DRIFT-19)
- **Members:** E4-1 (F-01), E3-19 (DRIFT-19)
- **Description:** `grep -rniE "max_input|MAX_PROMPT|D-141"` over `packages/adapters/src` and
  `packages/shared/src` returns nothing: there is **no input-size ceiling anywhere** in the gateway or
  the shared payload layer. The only ceiling is on output (`_HARD_MAX_OUTPUT_TOKENS = 4000`,
  `gateway.py:78`, applied `:236`, logged `:239`). `worst_case_cost_cents` (`gateway.py:182-194`)
  prices every call as if the input were **2000 tokens**, and the same expression is recomputed inline
  for the session-budget check — so a 50k-token prompt is **neither refused nor correctly priced**: it
  reserves against the 50-cent session budget as though it were 2000 input tokens. The docstring
  concedes the assumption ("inherited here rather than re-guessed"). The one real input bound lives a
  layer above and is caller-local (`packages/memory/src/.../consolidation.py:103-108`,
  `_MAX_EVENT_TOKENS_PER_CALL = 20_000`), with the AUD-F-34 incident written in place — a
  215,355-token prompt against a 200,000-token context, every call failing while the process exited 0.
  So input bounding is **per-caller and voluntary** rather than enforced at the gateway seam, and any
  *new* paid caller inherits the AUD-F-34 shape. The AREAS note additionally mis-locates D-141's fix as
  "an input-token bound in gateway code", pointing a future reader at the wrong package.
- **Domain:** cost / LLM gateway
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:122-184`; `LOCAL_EXECUTION_EVIDENCE.md:807`;
  `REPOSITORY_DRIFT_REGISTER.md:235-244`, `:239`
- **Related claim IDs:** COST-10, REQ-19, COST-03, COST-04
- **Related decision IDs:** D-141, D-233, AUD-F-34; non-negotiable rule 7
- **Repository evidence:** `packages/adapters/src/intellichoice_adapters/bedrock/gateway.py:78`,
  `:182-194`, `:236-243`, `:244-263`; `packages/memory/src/.../consolidation.py:103-108`;
  `packages/memory/src/.../settings.py:17`, `:36`. All **44** gateway and cost-reservation tests pass,
  so this is not a broken mechanism but a missing one; and **no test pins the absence**, so adding an
  input bound has no failing test to satisfy.
- **Deployed/live evidence:** n/a — repo-only. The deployed gateway carries the same code as HEAD for
  this path; nothing in the control plane exposes token accounting.
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** **override of the extractor's user-decision proposal.** The user's standing global
  rule — anything calling a paid API carries maximum token or spend limits — already decides that an
  input bound is owed, and non-negotiable rule 7 puts it at the gateway seam. No new judgement is
  needed about *whether*; only the value and the refuse-vs-truncate-vs-chunk shape remain, and those
  are engineering choices once the settlement question below is answered.
- **Remaining action:** three things, in order. **(1) Named verification step, carried from F-01:**
  read the code to determine whether **settlement uses actual input tokens**. If it does, exposure is
  bounded to the reserve-settle window; if it does not, the mispricing persists into the accumulated
  session and day totals. This materially changes the exposure size and must be answered *before* the
  ceiling value is chosen. **(2)** Add the input-token ceiling at the gateway or shared payload layer.
  **(3)** Stop pricing input at the flat 2000-token constant in `worst_case_cost_cents` and the
  session-budget check. Also correct the AREAS note's mis-location.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `COST-25-ALARM-COUNT` — the alarm inventory reconciles exactly; only the billing line is missing from the cost model

- **Work/Issue ID (topic key):** `COST-25`
- **Members:** E1-51 (COST-25)
- **Description:** The configured-versus-deployed alarm count reconciles **exactly**: 34 deployed
  `MetricAlarms` and 0 `CompositeAlarms` = 30 observability-module instances + 4 created by Application
  Auto Scaling from the step-scaling policies, with a **per-name delta of 0** against configuration —
  not one configured instance missing, not one deployed alarm unaccounted for. The honest headline is
  the three-number chain **15 resource blocks → 30 module instances → 34 account alarms**, which is
  also why the configuration test's own warning that "the deployed alarm count and the configured one
  are not the same number" is right about blocks and wrong about instances. What is *not* reconciled is
  the cost model: free-tier usage shows `AmazonCloudWatch CW:AlarmMonitorUsage` **Actual 10.0 /
  Forecast 16.32 / Limit 10.0 — at limit and forecast to exceed**, so **24 of 34 alarms are billable**
  at ~$0.10/alarm/month ≈ **$2.40/mo**, and **no cost-model document mentions a per-alarm charge**. On
  the same read, `AWS X-Ray XRay-TracesStored` is **91,077 actual / 148,599 forecast against a 100,000
  limit** (91% used, forecast to exceed) — a second small forthcoming charge, consistent with the OTel
  sidecar actively exporting.
- **Domain:** cost model / observability billing
- **Original source(s):** `CLAIM_LEDGER.md:1955`; `DEPLOYED_INFRA_DRIFT_REGISTER.md:294-303`, `:299`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:417-427`
- **Related claim IDs:** COST-25, COST-21, COST-24, COST-26, WORK-02, WORK-08, COST-15
- **Related decision IDs:** D-401, D-406, D-419
- **Repository evidence:** 15 `aws_cloudwatch_metric_alarm` resource blocks
  (`modules/observability/main.tf:132,208,231`; `alarms.tf:29,56,87,115,136,163,187,213`;
  `app_events.tf:45,96,130,202`) expanding to **30** instances at staging cardinality. The omission of
  alarm and trace-storage charges from the cost model is repository-side.
- **Deployed/live evidence:** 34 alarms, reconciling exactly to 30 + 4 AAS, per-name delta 0.
- **Final disposition:** `RESOLVED` for the count; **`DOCUMENTATION_ONLY` residual** for the billing
  line
- **Justification:** the ledger's UNKNOWN was "configured alarm count ≠ deployed alarm count", and E5's
  delta-0 reconciliation answers it directly and positively. That positive result must stay visible and
  not be lost behind a "we're over free tier" headline. At ~$2.40/mo the billing line is too small to be
  a posture call, but it belongs in the cost model and in UD-3's inputs.
- **Remaining action:** add alarm billing **and** the X-Ray trace-storage line to the cost model — the
  X-Ray forecast is the only *new* cost line and deserves its own sentence rather than being folded into
  the alarm note. The alarm inventory itself needs no change. The related "configured is not deployed
  for any `count`-gated Terraform resource" lesson is carried by `KPI-ALARM-FLOOR`.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no (the count); the billing edit belongs to the migration worklist
- **Historical/archive only?** yes for the count

### `D136-PRICE-TABLE` — the D-136 price table is quoted as current without its resize caveat

- **Work/Issue ID (topic key):** `DRIFT-22` (COST-29; also ARCH-12, ARCH-13)
- **Members:** E3-22
- **Description:** Task count is unchanged (learning-api pinned at two tasks) but **task size changed**
  to `cpu = 512 / memory = 1024`. The terraform comment identifies the measurement's provenance: the
  AUD-F-28 sweep was run on the old **256/512** task, where p95 ≤ 3 s held only to ~8 concurrent
  sessions. `docs/ARCHITECTURE.md:254-283` quotes the table's per-task columns as current with **no
  resize caveat**, so its per-task columns understate learning-api by 2×. chat-api meanwhile runs on
  module defaults (256/512, min 1), so the two services are not the same size at all, and reusing the
  table today understates capacity per task.
- **Domain:** infrastructure / cost / documentation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:268-277`;
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:154-186` (the same defect noted independently from the budget side)
- **Related claim IDs:** COST-29, ARCH-12, ARCH-13
- **Related decision IDs:** D-122 (AUD-F-28), D-134, D-136
- **Repository evidence:** `terraform/environments/staging/main.tf:423-447`, `:517-556`, `:819-835`;
  `terraform/modules/ecs-service/variables.tf:53-69`, `:187-191`; `docs/ARCHITECTURE.md:254-283`. The
  configuration is correct and deliberate; only the prose is wrong.
- **Deployed/live evidence:** the 512/1024/desired-2 versus 256/512/desired-1 asymmetry is **live
  verified** against AWS (ARCH-12/ARCH-13/COST-29 confirmed in Phase 3B-1 §3.4), so F-03's
  config-is-not-live caution is discharged for this entry specifically.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** one of the very few entries where the repository→deployed chain is fully closed
  (configuration verified in 3A, tests in 3A.5, AWS in 3B-1). The defect is a missing caveat on a table
  that is otherwise right, and it is a documentation defect regardless of what UD-3 decides about the
  budget.
- **Remaining action:** add the AUD-F-28 resize caveat to `ARCHITECTURE.md:254-283`. See
  `BATCH-LOW-CONFIG-VS-PLAN` (DRIFT-56) for the related plan-versus-ceiling note on the same table, and
  `COST-29-EXTRAPOLATION-BAN` for the extrapolation rule that governs its reuse.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `COST-29-EXTRAPOLATION-BAN` — the measured throughput constraint, and the purchase it justified is withdrawn

- **Work/Issue ID (topic key):** `COST-29`
- **Members:** E1-54
- **Description:** Throughput saturates near 5 concurrent requests per task and latency grows
  ~`concurrency^1.55`. D-136 prices p95 from r = 12.5 (2 tasks) to r = 2.5 (10 tasks) with a **binding
  rule against extrapolating outside r ∈ [2.5, 12.5]**. The purchase that table justified was
  **withdrawn** by D-153 §3 — the only WITHDRAWN verdict in the ledger.
- **Domain:** cost control / capacity evidence
- **Original source(s):** `CLAIM_LEDGER.md:2007` — `docs/ARCHITECTURE.md:254-283`
- **Related claim IDs:** COST-29, ARCH-13, ARCH-24, REQ-50, INT-10
- **Related decision IDs:** D-132, D-134, D-136, D-153 §3, SPEC §6.23
- **Repository evidence:** the measurement and the rule are recorded at `ARCHITECTURE.md:254-283`; the
  quoted throughput figures are **load measurements**, not deployed properties, so they cannot be
  confirmed or refuted from the control plane.
- **Deployed/live evidence:** the autoscaling ceiling is 3 tasks per service, which is itself a bound on
  what any live demonstration could show without raising it. The related live fact —
  100-concurrent capacity was **never demonstrated** (30-day peak ≈ 3 req/s, busiest minute 51
  requests) — is carried in `SPEND-AUTHORIZATION` (REQ-50(b)).
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** a measured constraint plus a closed purchase decision; no work is owed unless the
  table is reused. It matters mainly as the counterweight to SPEC §5.33.4's still-cited ">100
  concurrent" target and to `INT-10-PEAK-CONCURRENCY`'s unmeasured peak.
- **Remaining action:** none. If capacity is ever revisited, start from three facts together: the plan
  is withdrawn, the configured ceiling is 3, and the 100-concurrent figure was never demonstrated live.
  The honest current statement is "capacity is an extrapolation", and any launch-readiness claim resting
  on 100-concurrent must say so.
- **Owner type:** none
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `INT-10-PEAK-CONCURRENCY` — the capacity purchase is withdrawn and the 150-concurrent org ask is parked

- **Work/Issue ID (topic key):** `INT-10` (chain F5)
- **Members:** E1-71 (INT-10), E2-7 (chain F5), E2-8(a) (the 150-concurrent org-ask half)
- **Description:** The user fixed the planning assumption at ~1,000 students across a week with peak
  concurrency **explicitly unmeasured**, and D-153 §3 **withdrew — not deferred** — the r = 5 capacity
  purchase (+3 tasks, ~$43/month, D-139 §2), on the ground that it was priced against a self-authored,
  never-applied concurrency figure: "there is nothing to undo and nothing to buy." Task counts stay at
  learning-api 2 / chat-api 1; a recommended reduction to 1 was declined on gate-evidence-integrity
  grounds. The separate 150-concurrent sizing question (~$173–433/month plus an RDS resize, with a
  `db.t4g.small` Free-Tier rejection **lead time** as a prerequisite) is neither withdrawn nor approved
  — it is parked behind an **unsent org message**. Also unresolved: D-133 §3(a)'s "150 has never been
  validated as a requirement".
- **Domain:** cost / capacity planning / org communication
- **Original source(s):** `CLAIM_LEDGER.md:2509`; `DECISION_SUPERSESSION_MAP.md:678-685`, `:696-698`,
  `:700-712`; `DECISIONS.md:9022-9025`, `:9068-9082`; `S42_OPEN_QUESTIONS.md:21`
- **Related claim IDs:** INT-10, ARCH-13, ARCH-24, COST-29, REQ-50, INT-26
- **Related decision IDs:** D-133, D-134, D-136, D-139 §2/§3, D-153 §1/§3, C8, Message D
- **Repository evidence:** r = 5 itself was only ever a **recommendation**, never user-approved, and
  must not be carried forward as a decision. `S42_ORG_ASKS.md` nonetheless still argues Message D is
  worth sending now, for a cancelled purchase.
- **Deployed/live evidence:** deployed task counts and the ceiling of 3 match the repository exactly
  (verified in Phase 3B-1). No live measurement of peak concurrency exists.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** a user decision withdrew the spend and named the revisit trigger verbatim
  ("Revisit at integration" — D-153 §3), and the org-ask half is parked behind the same event. Per §C
  the 150-concurrent org ask is PARKED and revisited at integration; only the **credit-burn horizon**
  half of chain F5 is live, and that is a member of `BUDGET-GROSS-SPEND` (UD-3).
- **Remaining action:** none now. At integration, measure peak concurrency — "when it is a measurement
  instead of an assumption" — and only then decide whether the 150-concurrent ask is worth sending. The
  stale "Send now" marker on Message D is a documentation defect carried by `RISK-GROUP-FREEZE`.
- **Owner type:** user at integration
- **Reopen condition:** integration start, per D-153 §3.
- **PROJECT_STATE?** yes — parked
- **Historical/archive only?** no

### `SPEND-ATTRIBUTION-DOC` — per-student spend attribution is built and two documents still call it open

- **Work/Issue ID (topic key):** `DRIFT-23` (COST-11; also COST-13, COST-14)
- **Members:** E3-23 (DRIFT-23), E1-46 (COST-11)
- **Description:** D-400 rejected the audit's "never per student or per session" as too strong:
  `bedrock_call` carries no session id, but the formatter stamps `trace_id` on every line and the access
  line carries `learning_session_id` in the same log group, so the join happens in a Logs Insights
  `stats`. Coverage was measured at 2209/2212 narrative and 297/299 personalization calls. Two documents
  still carry it as open: `AUDIT_2026_08_16.md:239-241` states spend is "never per student or per
  session" with **no resolution marker**, while an adjacent paragraph in the same block *does* carry one
  (`✅ resolved 2026-08-17, D-394`) — the file marks resolutions selectively and left this one unmarked;
  and `PROGRESS.md:11664` still calls it one of "the last two observability items". Both are contradicted
  by ROADMAP (W8 ✅ done 2026-08-17, D-400) and by PROGRESS's own current section.
- **Domain:** documentation / observability
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:279-288`; `CLAIM_LEDGER.md:1773`;
  `INCIDENT_RESPONSE.md:222-268`
- **Related claim IDs:** COST-11, COST-12, COST-13, COST-14, COST-23
- **Related decision IDs:** D-394, D-400
- **Repository evidence:** `docs/AUDIT_2026_08_16.md:239-241` versus `:247-248`;
  `docs/PROGRESS.md:11664` versus `:250-258`; `docs/ROADMAP.md:2909-2914`. The closure is in-repository
  and dated; the capability is verified.
- **Deployed/live evidence:** n/a — repo-only; the mechanism is a log-join, not a deployed resource.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** two stale statements against a dated, committed closure. The generalisable defect
  is that audit-file finding text is not dated in place, so it reads as current forever — the same shape
  as DRIFT-93, DRIFT-94, DRIFT-95 and DRIFT-97.
- **Remaining action:** two edits. Fold the convention recommendation (date audit findings in place) into
  the canonical-migration proposal alongside `RISK-GROUP-AUDIT-REGISTERS`.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DRIFT-86-COST-RUNBOOK` — the cost-anomaly runbook's primary lever does not move a live service

- **Work/Issue ID (topic key):** `DRIFT-86` (COST-16) — batch C exception
- **Members:** E3-56:DRIFT-86
- **Description:** The cost-anomaly runbook's "scale `desired_count` to 0" lever is **not literally
  effective** on a live service: `desired_count` is inside `ignore_changes` and autoscaling owns
  capacity once the service exists, so the operative knob is `autoscaling_min_capacity` — and the
  terraform comment says exactly that. Every other named control does exist (a monthly budget with
  `ACTUAL>80%`/`FORECASTED>100%` notifications, a 50.0¢ session budget, circuit threshold 5, cooldown
  30 s).
- **Domain:** cost control / incident runbook accuracy
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:979` (DRIFT-86)
- **Related claim IDs:** COST-16
- **Related decision IDs:** none cited
- **Repository evidence:** the `ignore_changes` block and the terraform comment naming
  `autoscaling_min_capacity` as the real knob; the runbook text naming `desired_count`.
- **Deployed/live evidence:** autoscaling owns capacity on both live services (four StepScaling
  policies, chat-api scalable target `MinCapacity 1 / MaxCapacity 3`), so the runbook's lever would be
  ignored in exactly the situation it is written for.
- **Final disposition:** `ACTIVE_REMEDIATION` — **batch C exception**
- **Justification:** an incident runbook naming a lever that does not move a live service is an
  operational defect, not a wording nit, and RD-03 shows the cost scenario is **live**: the $20 budget
  is breached and ~$230 of credits hide a ~$250/mo gross run rate. This is a document someone may
  actually need.
- **Remaining action:** correct the runbook to name `autoscaling_min_capacity` (and, if wanted, the
  full sequence for a genuine cost-anomaly stop). Cross-reference `BUDGET-GROSS-SPEND`.
- **Owner type:** engineering (runbook is operational, not editorial)
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

---

## §3 Observability & alerting

### `RD-01` — the nightly-job dead-man's switch is structurally non-functional

- **Work/Issue ID (topic key):** `RD-01` (COST-18 / COST-19 / WORK-35-3B1 / ARCH-04)
- **Members:** E5-1, E1-47 (COST-18), E1-48 (COST-19), E3-58:DRIFT-87 (the fifth-entrypoint
  correction), E4 §5 live-half lane note (`LOCAL_EXECUTION_FINDINGS.md:786-793`)
- **Description:** The four nightly-job heartbeat alarms **can never leave ALARM and can never enter
  OK**, because the deployed CloudWatch metric-filter patterns search for **hyphenated** event names
  (`{ $.event = "session-consolidate_job_complete" }`, and the same for `chat-purge`,
  `retention-purge`, `memory-consolidate`) while the Python emitter produces **underscored** names
  (`session_consolidate_job_complete`). `JobCompletions` has therefore **never published a single
  datapoint** — zero datapoints on all four `job` dimensions over 14 days, and the metric is absent from
  `list-metrics` for its namespace, which returns 7 other metrics that *do* carry data from the same log
  group's other filters. All four alarms have exactly **one** state transition in their entire history,
  `INSUFFICIENT_DATA → ALARM`, on 2026-08-16T23:15:15Z / 23:27:54Z / 23:49:48Z and 2026-08-17T00:04:18Z
  — a permanent false ALARM since 2026-08-16, routed to the confirmed page mailbox with
  `ActionsEnabled: true`. The jobs themselves **do** run (ops-task log streams at 18:01/18:11/18:50 UTC
  on both 2026-08-18 and 2026-08-19, metadata only). A related residual from 3A: a **fifth** scheduled-job
  entrypoint, `checkpoint_retention_cli`, does not call `report_job_complete` at all and is also
  unscheduled; and the reporting helper swallows all exceptions by design, so a silent reporting failure
  would leave only the `print()`.
- **Domain:** observability / alerting — a broken control
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:43-115`, `:96-111`, `:427-429`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:357-367` (COST-18), `:369-379` (COST-19), `:567-577` (WORK-35);
  `REPOSITORY_DRIFT_REGISTER.md:990` (DRIFT-87); `CLAIM_LEDGER.md:1864`, `:1877`
- **Related claim IDs:** COST-18, COST-19, WORK-35 (3B-1 sense), ARCH-04, WORK-19, WORK-21
- **Related decision IDs:** D-377 (the `*_job_complete` record and the heartbeat pair), D-385 (the
  missing cross-boundary parity test), D-333, P1-6 and P1-7 [AUDIT_2026_08_16], D-419
- **Repository evidence:** emitter underscored at
  `packages/observability/src/intellichoice_observability/scheduled_jobs.py:61`; hyphenated job keys at
  `:39-43` with the comment at `:37-38` asserting they are hyphenated *because the alarm's `job`
  dimension will match*; the filter pattern built from the hyphenated `each.key` at
  `terraform/modules/observability/app_events.tf:170/173`; the four keys passed at
  `terraform/environments/staging/main.tf:777-782`. Both sides are internally consistent and mutually
  incompatible, and unchanged on HEAD. **No cross-boundary parity test exists**: no local test asserts
  terraform-pattern ↔ Python-event-name parity, and
  `packages/observability/tests/test_alarm_severity_routing.py` cannot catch it — its three tests
  assert alarm **routing**, not filter-pattern/emitter agreement, and they passed.
- **Deployed/live evidence:** all four filters present on `/ecs/intellichoice-staging-ops-task` with the
  hyphenated pattern verbatim; `JobCompletions` absent from the namespace; 0 datapoints × 4 dimensions ×
  14 days; four alarms in ALARM with identical `StateReason` ("…no datapoints were received for 1 period
  and 1 missing datapoint was treated as [Breaching]."); page-topic `AlarmActions` **and** `OKActions`.
  Everything else about the pair matches exactly — period 172800, threshold 1, statistic Sum,
  `LessThanThreshold`, `dimensions job=$.job`, `treat_missing_data = "breaching"`, `default_value`
  deliberately absent, page-topic routing. **Do not "fix" any of those.**
- **Final disposition:** `ACTIVE_REMEDIATION` — the highest-priority engineering item in the register
- **Justification:** a broken control with a known one-line fix plus a required test; nothing to decide,
  only to do. It also refutes two earlier comforts, and both refutations must survive: COST-18's
  "filters correct, so the metric will flow" expectation, and the Phase-3A comfort that the dead-man's
  switch posture was "resolved at config level". 3A found one job uninstrumented; 3B found the
  *instrumented* path structurally incapable of publishing — so the four-of-five instrumentation must
  not be reported as reassurance.
- **Remaining action:** four steps, in order. **(a)** A **one-line** change on exactly one side — either
  make `scheduled_jobs.py:61` stop rewriting hyphens (emit the hyphenated job key verbatim), or make
  `app_events.tf:173` build the pattern from an underscored key
  (`pattern = "{ $.event = \"${replace(each.key, "-", "_")}_job_complete\" }"`). **Note the deploy-cost
  asymmetry:** the terraform side is `apply`-only; the **Python side needs a full image build and
  deploy**, and per LB-05 a repo-side emitter fix is **inert until a deploy** — so RD-01's Python-side
  fix reaching staging is a consequence of UD-1. **(b)** `terraform apply` or a new image build and
  deploy, depending on the side chosen. **(c)** Wait ≥1 nightly firing and confirm `JobCompletions`
  publishes and the four alarms transition ALARM → OK; the alarms cannot self-clear before a real
  datapoint arrives. **(d)** **Add the missing cross-boundary parity test** — a *second deliverable*,
  not optional polish: without it the defect is re-introducible on the next rename, and this is exactly
  the class D-385's parity test was invented for. Also wire `report_job_complete` into
  `checkpoint_retention_cli` when that job is scheduled (`WORK-23-RETENTION-JOB-GATING`).
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes — top of the engineering queue
- **Historical/archive only?** no
- **Dependency chain to carry:** fix → deploy → **then** start counting §2.6 criterion 6's unattended
  week (`C6-UNATTENDED`) and unblock the `WORK-23` retention-job gating, whose stated prerequisite is
  the session-consolidate job **having a record of firing** — which RD-01 currently makes unobtainable.
  **Job SUCCESS remains unproven** independently of the fix: the 18:01/18:11/18:50 streams prove
  *invocation*, not outcome, and could equally hold tracebacks. The one EventBridge rule
  (`intellichoice-staging-ops-task-failed`, ENABLED, firing on any ops-task container that stops with a
  non-zero exit code) **narrows but does not close** the silent-failure space: a job that fails *and*
  exits 0 is still invisible.
- **⚠️ STEPS (a), (b), (d) DONE 2026-08-21 — only the step-(c) confirmation remains.**
  (a) The terraform-side fix (`replace(each.key, "-", "_")`) landed as `b06a5df` via PR #362.
  (d) The cross-boundary parity test exists
  (`packages/observability/tests/test_scheduled_job_event_parity.py`) — verified failing against
  the hyphenated pattern pre-fix, and failing again under a temporary emitter-side mutation, so a
  one-sided rename on either side now fails locally. (b) The targeted `terraform apply` executed
  the same day (plan: exactly `0 add / 4 change / 0 destroy`) and all four live filter patterns
  were read back underscored from `/ecs/intellichoice-staging-ops-task`. (c) is time-blocked:
  the first post-fix nightly firing (earliest 2026-08-22 ~19:00 UTC) must publish `JobCompletions`
  and the four alarms must be observed transitioning ALARM → OK. The
  `checkpoint_retention_cli` wiring stays with `BATCH-LOW-UNSCHEDULED-CONTROLS`. No new judgment
  was made — no D-number; git history and the session narrative
  (`docs/log/2026-08-21-rd01-cost22-orca.md`) are the record.
- **⚠️ STEP (c) CONFIRMED FOR THE THREE NIGHTLY JOBS 2026-08-22 — and it surfaced one new
  defect.** The first post-fix firings published `JobCompletions`' first-ever datapoints
  (18:00/18:10/18:50 UTC, one per nightly `job` dimension; `session_consolidate_job_complete`
  read back from the ops-task log group with the underscored `event`, the hyphenated `job`, and
  real counts — threads 5623, written 0), and three of the four heartbeat alarms transitioned
  ALARM → OK the same evening: `chat-purge` 19:05:51Z, `retention-purge` 19:11:05Z,
  `session-consolidate` 19:42:40Z (long-period alarm evaluation lags its datapoint by ~1–1.7 h).
  **The fourth cannot confirm and will not stay confirmed: `memory-consolidate` is a WEEKLY job
  (`cron(30 18 ? * SUN *)`, `terraform/modules/scheduled-jobs/main.tf:91`) sitting in the
  `nightly_job_events` list under the uniform two-day heartbeat period
  (`app_events.tf:225`, `period = 172800`).** Even after a Sunday run its alarm will be OK for
  ~2 days and then re-enter ALARM for the rest of every week — permanent weekly flapping to the
  page mailbox, the exact noise class this entry existed to end. Previously invisible because the
  alarm never left ALARM at all; no document had connected "weekly job" (ARCHITECTURE knows) with
  "two-day period" (this register verified it matches the filter — which it does; the mismatch is
  against the schedule, not the filter). **New remaining action (replaces step (c)'s
  memory-consolidate half):** give the weekly job a weekly-scaled heartbeat period (the nightly
  rule "one missed night is a blip and two is an alarm" scales to one missed week/two weeks),
  apply-only, then confirm its ALARM → OK after the first post-fix Sunday run. Job success still
  unproven for all four — the events report completion, not correctness.

### `KPI-ALARM-FLOOR` — zero product-KPI alarms are deployed while both KPI metrics carry live data

- **Work/Issue ID (topic key):** `COST-21` (P1-10 / DRIFT-20 / RD-07), with the R9 tripwire
  sub-question (SEC-10 / DRIFT-10 / RD-08)
- **Members:** E5-10, E5-20 (the 63/12 umbrella context), E3-20 (DRIFT-20), E1-49 (COST-21), E7-4;
  sub-question: E5-11, E3-10 (DRIFT-10), E1-34 (SEC-10)
- **Description:** **Product-KPI alarm count deployed = 0**, proven three independent ways: the prefix
  query for `intellichoice-staging-learning-sessions-completed-floor` returns
  `{"MetricAlarms":0,"CompositeAlarms":0}`; a name and metric regex over the unfiltered 34-alarm dump
  hits only `intellichoice-staging-job-session-consolidate-heartbeat` (matched on the word "session" in
  a *job* name whose metric is `JobCompletions`); and all four `describe-alarms-for-metric` calls across
  both namespaces for `learning_sessions_completed_total` and `qa_answers_total` return
  `{"MetricAlarms":0}`. Meanwhile **both KPI metrics exist and carry data** —
  `learning_sessions_completed_total` 11 datapoints / Sum 8 over 30 days,
  `qa_answers_total{result=grounded}` 9 datapoints / Sum 409 over 30 days. So the blind spot is not "no
  data to alarm on": a floor would be **meaningful today**, which falsifies the previous defence that a
  floor would just flap. The 34 deployed alarms break down as ALB 6, ECS/ContainerInsights 4, RDS 6,
  metric-math 2, custom-namespace app plumbing 12, pipeline ops 4 — **none a product KPI**. The umbrella
  pattern: **63 custom app metrics carry data (learning-api 35, chat-api 28, pipeline 7) and 12 have
  alarms**, all of them app *plumbing*; the 19-widget dashboard charts far more than is alarmed, so most
  signals are look-if-you-remember rather than tell-me. **Sub-question (R9 tripwire):** §7-R9 treats
  checkpoint repairs as a tripwire — "acceptance is void the moment the counter moves" — and a regex over
  the full alarm dump for `checkpoint|repair` returns `[]`. `learning_checkpoint_repairs_total` exists
  **with data** in the deployed learning-api namespace and **is** charted on the live
  `intellichoice-staging-overview` dashboard, and no alarm references it. So a human must be looking at a
  dashboard for the tripwire to trip.
- **Domain:** observability / product monitoring / risk governance
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:242-251` (RD-07), `:255-264` (RD-08),
  `:247`; `DEPLOYED_INFRA_STATE_EVIDENCE.md:381-391` (COST-21), `:491-501` (REQ-50, the 63/12 figure at
  `:497`), `:543-553` (WORK-08), `:271-281` (SEC-10), `:405-415` (COST-24);
  `REPOSITORY_DRIFT_REGISTER.md:246-255` (DRIFT-20), `:136-145` (DRIFT-10);
  `CLAIM_LEDGER.md:1903`, `:1301`; `LOCAL_EXECUTION_FINDINGS.md:353-383` (F-06)
- **Related claim IDs:** COST-21, COST-22, COST-24, COST-25, COST-26, REQ-50, SEC-10, ARCH-17, INT-22,
  P1-10 [AUDIT_2026_08_16], WORK-02
- **Related decision IDs:** D-377 §P1-10, D-401 (the informational-routing set whose third member is
  count-gated out), D-419, D-148 §7-R9 and its criterion-2 qualification, AUD-X-07
- **Repository evidence:** a **double guard** makes the KPI alarm impossible in staging —
  `count = var.daily_completed_sessions_floor > 0 ? 1 : 0` at
  `terraform/modules/observability/app_events.tf:130-131`, **and**
  `terraform/environments/staging/main.tf:787` sets the variable to `0` explicitly with the reason
  written out ("Staging traffic is synthetic … Left at 0 (disabled) rather than guessed at").
  `qa_answers_total` has no alarm resource anywhere. For the sub-question:
  `learning_checkpoint_repairs_total` is instrumented at exactly one site
  (`apps/learning-api/.../routers/sessions.py:756`), bridged to CloudWatch and rendered on a dashboard
  widget, and **no `aws_cloudwatch_metric_alarm` block references it** — `alarms.tf` is the only alarms
  file, defines eight alarms, and their metrics are `BedrockCircuitOpen`, `LangSmithIngestFailed`,
  `BedrockCallFailed`, `CPUUtilization`, `FreeStorageSpace`, `DatabaseConnections`, `MemoryUtilized`,
  `BedrockCostCents`. F-06 corrected the terraform line count from three to **four**
  (`modules/ecs-service/main.tf:209` the otel `filter/kpis` include list, `:255` the `awsemf` exporter's
  `metric_declarations`, `dashboard.tf:425` a comment and `:436` the widget) without changing the
  substance; the register still says three, and that count fix is tracked in
  `DOC-TEST-CLAIM-WORDING`.
- **Deployed/live evidence:** exactly what the configuration predicts — **zero instances**, and
  `sessions-completed-floor` is **absent from AWS entirely**, matching the configuration test's own
  in-file note ("Configured, not deployed"). So deployed **agrees with** the repository; the gap is
  intent-versus-both, not drift. For the sub-question the deployed state matches the repository exactly
  (metric present with data, dashboard widget present, alarm absent), which moves SEC-10 from file state
  to runtime-proven rather than contradicting it. SEC-10's positive half is also confirmed live: all
  eight `alarms.tf` blocks exist at ×2 = 16 instances with every threshold, period, evaluation period
  and `treat_missing_data` matching configuration, including `ecs_memory` at 716.0 MiB and the
  per-engine `rds_connections` split (postgres 80.0 / mysql 40.0).
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-5**
- **Justification:** choosing a KPI floor is a product and launch-posture call — what counts as "too few
  completed sessions to be normal" — and picking a number wrongly generates page-channel noise, the
  exact failure mode D-401's quiet channel exists to avoid and the same lesson D-418 just paid for. The
  engineering half is trivial once the number exists. RD-07's own ruling is that it **strengthens** an
  existing decision-required entry rather than creating one, so it is not double-counted. **E1-49's
  "configured-but-absent" framing is corrected here:** deployed matches configuration exactly (double
  guard), so this is an intent gap, not drift — the transferable lesson is that "configured" and
  "deployed" are different claims for any `count`-gated Terraform resource.
- **Remaining action:** the user decides with the observed magnitudes attached (Sum 8 sessions / 409
  grounded answers / 30 days): raise `daily_completed_sessions_floor` to a real number, alarm
  `qa_answers_total` instead (the denser series, needs a new resource), defer to first real traffic
  (which ties an observability gap to an event D-152 has frozen), or record the disabled state as the
  deliberate answer to P1-10 — the option that leaves the record honest at zero cost and is what the
  terraform comment already says in everything but name. **Sub-question, decided with it:** alarm the R9
  checkpoint-repair tripwire, or accept the dashboard-review cadence as R9's detector. Establish the
  counter's current value first: **if it has moved, the §7-R9 acceptance is void by its own terms** and
  D-148's criterion-2 qualification needs re-reading — a materially bigger consequence than "add an
  alarm". Resolve the pattern once ("which of these 63 deserve an alarm, and what does a page mean in
  this project") rather than metric by metric, and do **not** turn 63/12 into a target ratio: alarming
  everything is how a single mailbox becomes unreadable, which is the failure mode `ALERT-ENDPOINT` is
  already partway into. The audit-claim-integrity half is separable and documentation-only: "all 10 P1s
  closed" was counted at the level of "an alarm resource now exists in configuration", which is true and
  misleading.
- **Owner type:** user, then engineering
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `ALERT-ENDPOINT` — 26 page alarms reach one personal Gmail address, and the informational mailbox has no setter

- **Work/Issue ID (topic key):** `COST-23` (COST-26 / WORK-02 / DRIFT-89)
- **Members:** E5-19, E3-58:DRIFT-89
- **Description:** Exactly two SNS topics exist account-wide, each with `SubscriptionsConfirmed: 1`,
  `SubscriptionsPending: 0`, and **`KmsMasterKeyId: NONE`** (both unencrypted). **Both** subscriptions
  are the *same* address — `k***@gmail.com`, a personal `gmail.com` address rather than an
  `intellichoice.org` one — so D-401's routing split is real at the **topic** level while the **mailbox
  stays one**: 26 of 34 alarms page that address, 4 go to `alerts-info`, 4 are AAS-actioned, and no
  alarm carries both topics. Separation is achievable only by topic ARN and a mail filter. This is
  exactly what the configuration predicts, not drift: the info endpoint is
  `coalesce(var.informational_notification_email, var.notification_email)` with the informational
  variable defaulting to `null` and **no setter anywhere in the repository**, and the module's own
  comment concedes it ("Both default to the same address, so nothing about delivery changes until a
  second endpoint is configured"). Since 2026-08-16 that single mailbox has also been receiving RD-01's
  permanent false-ALARM traffic.
- **Domain:** alerting / operational ownership / security
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:393-403` (COST-23, the gmail and encryption
  note at `:402`), `:429-439` (COST-26), `:519-529` (WORK-02);
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:195`; `REPOSITORY_DRIFT_REGISTER.md:1012` (DRIFT-89)
- **Related claim IDs:** COST-23, COST-24, COST-26, WORK-02
- **Related decision IDs:** D-377, D-401, D-419
- **Repository evidence:** `aws_sns_topic.alerts` + `alerts_email`
  (`modules/observability/main.tf:45`, `:50`) and `aws_sns_topic.alerts_info` + `alerts_info_email`
  (`:61`, `:66`); the `coalesce` default with no setter; no KMS key configured for either topic. The
  alarm→topic routing is complete and enforced by a terraform-parsing test (15 alarm resources → ~30
  instances, every one carrying `alarm_actions`, none carrying both topics). The audit's "26" is a
  pre-D-377 count.
- **Deployed/live evidence:** as above, with both subscriptions **genuinely CONFIRMED** (real
  subscription ARNs, nothing pending anywhere in the account) — which also resolves the audit-era
  `PendingConfirmation` observation (`SNS-CONFIRMATION`). Configuration, the terraform-parsing test and
  live AWS all agree, so this is ready to decide with no further measurement.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-6**
- **Justification:** who receives production pages, on what address, is an operational-ownership call
  for a solo maintainer, not an engineering default. Setting `informational_notification_email` is a
  one-line change once the answer exists.
- **Remaining action:** the user decides whether the page channel should reach an org address or a second
  endpoint rather than one personal mailbox, whether a second informational mailbox is configured or one
  address is recorded as the answer, and whether topic encryption is wanted. **Present it together with
  `RD-01`:** alert-channel hygiene matters much less in the abstract than it does when a
  permanently-false alarm is already training the recipient to ignore that mailbox. Encryption
  (`KmsMasterKeyId: NONE`) is the weakest sub-point — alarm names and states are not sensitive — so do
  not let it dominate the ask.
- **Owner type:** user, then engineering (one line)
- **Reopen condition:** n/a — open now
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `LANGSMITH-INGEST` — trace ingestion is failing at volume, flapping, and by design nobody is paged

- **Work/Issue ID (topic key):** `RD-04` (COST-27)
- **Members:** E5-6
- **Description:** `LangSmithIngestFailed` 14-day Sums are **learning-api 2800, chat-api 1441** — zero
  on 08-09…08-14, then 2252/1153 on 08-15, 524/239 on 08-16, 0/44 on 08-17, 24/5 on 08-18. The alarm
  (threshold 10 over 900 s, 2 evaluation periods) shows **10 state transitions each in ~2 days** —
  learning-api flipped OK→ALARM→OK five times between 2026-08-17T03:02Z and 23:12Z — so the signal is
  real and *flapping*, not pinned. Every flap lands in the quiet `alerts-info` topic by deliberate D-401
  design, and both topics deliver to the **same single mailbox**. So the tracing leg — the thing that
  would let anyone debug a production LLM path — is substantially broken right now, and the routing that
  was designed to prevent alert fatigue also guarantees nobody is paged about it. The **cause is not
  determined**: 403 versus quota versus timeout needs log content, which the control-plane phase could
  not read.
- **Domain:** observability / third-party integration
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:190-199`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:441-451` (COST-27), `:393-403` (COST-23)
- **Related claim IDs:** COST-27, ARCH-30, ARCH-31, SEC-23
- **Related decision IDs:** D-242, D-401
- **Repository evidence:** the filter is `for_each = var.log_group_names` with a pattern keyed on
  `$.logger = "langsmith.client"`; the alarm is threshold 10 / 900 s with
  `alarm_actions = [aws_sns_topic.alerts_info.arn]` at
  `terraform/modules/observability/alarms.tf:56-84` (action at `:80-81`). The D-401 comment at
  `terraform/modules/observability/main.tf:75-…` predicted the alarm would "sit in ALARM indefinitely" —
  **the repository's own prediction is wrong about live behaviour**: it flaps.
- **Deployed/live evidence:** filters on both app log groups, pattern verbatim, `default=0.0`,
  `unit=Count`; alarms on both routed to `alerts-info` with identical `OKActions`; current state OK on
  both; the failure volumes and flap history above. `LANGSMITH_TRACING = "true"`,
  `LANGSMITH_PROJECT = intellichoice-staging`, `LANGSMITH_WORKSPACE_ID` present as plain env on both
  task definitions; one shared `LANGSMITH_API_KEY` secret ARN.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** an ops investigation with a concrete next step, not a judgement. Two things are easy
  to conflate and must not be: the **routing** works exactly as D-401 intended (not a defect), and the
  **ingest failures** are the finding.
- **Remaining action:** read the ops and app log content for the `langsmith.client` lines and classify
  403 / quota / timeout. **Flag the fork rather than pre-deciding it:** if the cause turns out to be
  quota or plan limits, the remedy becomes a paid-plan question, which is a user call. Note the NAT
  dependency chain — LangSmith is the NAT's sole egress consumer today, so ~$33/mo of NAT exists to serve
  a leg that is partly failing; if the failures are network-shaped, this and the NAT are the same
  investigation. What LangSmith actually *received* is external and unverifiable from here
  (`LANGSMITH-RETENTION`).
- **Owner type:** engineering; user only if the cause is a paid-plan limit
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `SNS-CONFIRMATION` — the `alerts-info` subscription is confirmed; D-419's warning is stale

- **Work/Issue ID (topic key):** `COST-26` (WORK-02 / chain M5 `PendingConfirmation`)
- **Members:** E1-52 (COST-26), E1-85 (WORK-02), E2-42
- **Description:** D-419 created the `alerts-info` topic and moved four alarms to it, and ended with a ⚠️
  block titled "The follow-up the user has to do, and it is not optional":
  `aws sns list-subscriptions-by-topic` reported the new subscription as **`PendingConfirmation`**, so
  the four informational alarms were routed to a topic with **no confirmed subscriber** — "the correct
  direction taken one step too far … it resolves with one click rather than a change". **That is no
  longer true.** COST-23, read 2026-08-20T00:05:15Z, shows both topics `SubscriptionsConfirmed 1` and
  **`SubscriptionsPending 0`**, with real subscription ARNs and exactly the four expected `alerts-info`
  members (`{chat,learning}-api-capacity-above-floor`,
  `{chat,learning}-api-langsmith-ingest-failed`).
- **Domain:** alerting
- **Original source(s):** `CLAIM_LEDGER.md:1968`, `:2864`; `DECISION_SUPERSESSION_MAP.md:134-136`,
  `:2219-2223`, `:2268-2270`; `DECISIONS.md:28482-28488`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:393-403`
- **Related claim IDs:** COST-26, WORK-02, COST-21, COST-23, COST-24, COST-25, WORK-08
- **Related decision IDs:** D-401, D-406, D-418, D-419
- **Repository evidence:** the topic and subscription resources exist as configured; the repository never
  claimed the subscription was confirmed.
- **Deployed/live evidence:** both topics confirmed, zero pending anywhere in the account, and the
  non-vacuity control holds live (`target_5xx`, `rds_free_storage`, `bedrock_circuit_open`,
  `bedrock_spend_spike` all carry the **page** ARN, none carries `alerts-info`).
- **Final disposition:** `RESOLVED`
- **Justification:** post-extraction supersession (§0.2 rule 4). This was the cheapest closable item in
  the ledger and it closed itself; any Phase-4 output repeating "four informational alarms reach nobody"
  would be wrong.
- **Remaining action:** one documentation edit — annotate D-419's ⚠️ block as resolved and dated, so
  nobody chases it. Tracked as a member of `RISK-GROUP-RESOLVED-LOOKS-OPEN`. Two facts recorded but not
  judged in the same evidence, and carried by `ALERT-ENDPOINT`: both topics are `KmsMasterKeyId: NONE`
  and the confirmed endpoint is a `gmail.com` address.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `COST-22-LABEL-PREINIT` — no labelled counter pre-initialises its labels, so every low-frequency KPI is unalarmable until its first occurrence

- **Work/Issue ID (topic key):** `COST-22` (DRIFT-21; also COST-20)
- **Members:** E1-50 (COST-22), E3-21 (DRIFT-21)
- **Description:** **Not fixed, and the gap is module-wide.** There is exactly one metrics module in the
  repository and it contains **no import-time `.labels()` call for any labelled counter**.
  `QA_SERVICE_DEGRADED` is declared with three documented `stage` values and touched at one runtime site
  inside the degradation handler, so **no series exists until a provider actually fails** — the metric
  built specifically so a Bedrock outage stops reading as a surge of off-topic questions cannot be
  alarmed on until an outage creates it. All 21 `.labels(` call sites are inside functions or handlers,
  none at module scope; no `preinit` or warm-up loop exists. The same shape applies to
  `ATTENDANCE_CHECKS`, `QA_ANSWERS`, `SSE_RELAY_FAILURES` and every other labelled counter.
- **Domain:** observability
- **Original source(s):** `CLAIM_LEDGER.md:1916`; `REPOSITORY_DRIFT_REGISTER.md:257-266`
- **Related claim IDs:** COST-22, COST-20, COST-21
- **Related decision IDs:** the recorded fix for `qa_service_degraded_total`; P1-10
  [AUDIT_2026_08_16]
- **Repository evidence:** `packages/observability/src/.../metrics.py:85-89`;
  `apps/chat-api/.../graph/nodes.py:271`; exhaustive `.labels(` and metrics-module greps.
- **Deployed/live evidence:** consistent with the repository — the counter is absent from the deployed
  namespace, which is what lazy label creation predicts.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** a mechanical fix (import-time label pre-initialisation) on a metric whose whole
  purpose is outage detection; the mechanism is known and the finding is HIGH-confidence. Prometheus and
  EMF's lazy label creation makes this invisible until the first event, which is exactly when the alarm
  is needed.
- **Remaining action:** pre-initialise label sets at import for every labelled counter. Group with
  `RD-01` and `KPI-ALARM-FLOOR`'s tripwire half as one **"silent instrument"** remediation batch — the
  pattern recurs six times across DRIFT-10, DRIFT-21, DRIFT-85, DRIFT-87, RD-01 and RD-08: a metric
  exists, is charted or named as evidence, and nothing can page on it.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no
- **⚠️ RESOLVED IN REPO 2026-08-21 — deploy-gated in staging (LB-05).** All eight bounded
  labelled metrics (20 label combinations) are pre-initialised at import in `metrics.py`
  (commit `4dbcc41`, PR #362); `HTTP_REQUESTS`/`HTTP_REQUEST_DURATION` are explicitly exempt
  (route×status cardinality), and
  `packages/observability/tests/test_metrics_label_preinitialisation.py` fails on any future
  labelled metric that is neither pre-initialised nor exempted (mutation-checked). The
  undocumented `qa_maps_calls_total`/`qa_calendar_calls_total` vocabularies were enumerated from
  all call sites as `success|failure`. Staging namespaces gain the series only at the next image
  deploy (UD-1): upper bound **34 new always-present custom-metric series** (17 × 2 services).
  Observed in passing: `sse_relay_failures_total` (D-396) is in neither the otel `filter/kpis`
  include list nor `metric_declarations`, so it cannot be alarmed on in AWS at all — the same
  silent-instrument shape, recorded in ARCHITECTURE's observability lessons. The UD-5 tripwire
  half of the batch stays a user decision. No new judgment — no D-number; git history and
  `docs/log/2026-08-21-rd01-cost22-orca.md` are the record.

### `COST-17-CLIENT-ERRORS` — the client-error alarm path is correctly deployed and has never been exercised end to end

- **Work/Issue ID (topic key):** `COST-17`
- **Members:** E5-21
- **Description:** The `client_errors` filter and its per-service alarm are deployed exactly as
  configured — pattern `{ $.event = "client_error" }` → `ClientErrors` with `default=0.0`, alarm
  `Threshold 0.0 GT`, `Period 900`, `ev 1`, `TreatMissingData notBreaching`, routed to the **page** topic.
  But the 14-day series is **4 datapoints / total 0** on each service, which indicates the app log groups
  received very few matching-shaped JSON lines — not that the filter is broken. Confirming that a real
  client-side crash flows end to end (app → log line → filter → metric → alarm → email) needs a
  **synthetic `client_error` post**, which no control-plane read can substitute for.
- **Domain:** observability / alarm efficacy
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:345-355` (COST-17, the datapoint note at
  `:354`), `:405-415` (COST-24's limitation: attributes, not efficacy)
- **Related claim IDs:** COST-17, COST-24
- **Related decision IDs:** D-419 (alarm-inventory routing)
- **Repository evidence:** filter `client_errors` with `default_value = 0` at
  `terraform/modules/observability/app_events.tf:40-43`; alarm `for_each = var.log_group_names`,
  `period = 900`, `Sum`, `treat_missing_data = "notBreaching"`,
  `alarm_actions = [aws_sns_topic.alerts.arn]` at `app_events.tf:45-72`.
- **Deployed/live evidence:** every attribute matches, on both services, in each service's own namespace.
  Only the *exercise* is missing.
- **Final disposition:** `DEFERRED`
- **Justification:** a cheap synthetic-event verification belongs to a behavioural lane, not to a
  control-plane phase. **Not a defect today — do not report it as one.**
- **Remaining action:** one synthetic `client_error` post would convert the whole "configured correctly"
  family from *plausible* to *proven*, and RD-01 is the standing proof that the difference is not
  academic — attribute-level agreement with configuration proves nothing about efficacy. Batch it with
  any future live-probe work rather than tracking it alone.
- **Owner type:** engineering (a behavioural lane)
- **Reopen condition:** the next live-probe or behavioural session.
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `ARCH-30-OTEL` — the collector's allow-list and the empty `/emf` filter sets are harmless artifacts

- **Work/Issue ID (topic key):** `ARCH-30`
- **Members:** E5-31
- **Description:** The OTel sidecar is confirmed live and correctly sourced — both task definitions hold
  exactly two containers, the app (`essential: true`) and `otel-collector` (`essential: false`, cpu 128 /
  mem 256, one env var `AOT_CONFIG_CONTENT`), running the **private mirror** image
  `…/aws-otel-collector:v0.43.3` with a digest identical to the only image in that ECR repository, and
  `lastStatus: RUNNING` on all three tasks. `AOT_CONFIG_CONTENT` confirms the live pipeline: OTLP
  receivers (grpc 4317 / http 4318) plus a Prometheus scrape of `localhost:8001`/`8002` `/metrics` every
  60 s; processors `filter/kpis` (a strict allow-list of **22** metric names) and `batch`; exporters
  `awsemf` → `/ecs/intellichoice-staging-{learning,chat}-api/emf` with `NoDimensionRollup`, plus
  `awsxray`. Two observations: **chat-api's collector allow-lists the full 22-metric set including the
  `learning_*` names** — a shared-module artifact, so the chat-api namespace will simply never receive
  those series — and **both `/emf` log groups carry zero metric filters**, which nothing in the
  configured side claims otherwise.
- **Domain:** observability plumbing
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:233-243` (ARCH-30, limitations at `:242`),
  `:479-489` (REQ-18, the `/emf` filter inventory)
- **Related claim IDs:** ARCH-30, ARCH-31, REQ-18
- **Related decision IDs:** D-401-adjacent observability build-out
- **Repository evidence:** sidecar at `terraform/modules/ecs-service/main.tf:112`/`:119`, enabled per
  service at `environments/staging/main.tf:462`/`:555`, image built at `main.tf:56` from the private
  mirror with `otel_collector_version = "v0.43.3"` overriding the module's public-ECR fallback. The
  shared allow-list is a single module-level list applied to both services — the artifact is by
  construction, not a mistake.
- **Deployed/live evidence:** matches configuration on every checked attribute, including all four
  Bedrock filters present on **both** app log groups (8 instances) with patterns, values, defaults and
  units verbatim.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** harmless artifacts, recorded so neither is later mistaken for a defect.
- **Remaining action:** none. One precision note generalises across the whole lane: `lastStatus: RUNNING`
  means the **container process is up** — it does not prove EMF metrics or X-Ray segments are being
  emitted, and `healthStatus` is `UNKNOWN` everywhere because no container `healthCheck` is defined
  (readiness is judged by the ALB target group). The X-Ray free-tier consumption in `COST-25-ALARM-COUNT`
  is the strongest *indirect* evidence that the export path really works.
- **Owner type:** none
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

---

## §4 Infrastructure & deployment

### `LB-05-DEPLOY-GAP` — the deployed build is 10 commits behind HEAD, and B4 has zero live evidence

- **Work/Issue ID (topic key):** `LB-05` (with WORK-03, ARCH-33 artifact-freshness half)
- **Members:** E6-5, E5-29, E1-86 (WORK-03), E7-1, E4-13 (F-13, artifact-freshness half)
- **Description:** Both ECS services run app image tag `gha-44a12dfc9549` (learning task definition
  `:150`, 2/2 running; chat `:148`, 1/1 running) = commit `44a12dfc95499fc40fc875681907951f5958ce5a`
  (2026-08-18, #336, D-415), confirmed by tag **and** digest on every running container with one
  `PRIMARY`/`COMPLETED` deployment per service. Local HEAD is `344f016`. **Stated as two sides, never
  merged:**
  - *Implemented in the repository (HEAD `344f016`)*: **10 commits** — `f7c9d10`, `a6da941`, `f6f84a2`,
    `899547f`, `2e301d6`, `e583cb9`, `b41efc7`, `5b324a0`, `6f107c1`, `344f016`. This includes the whole
    **B4 escalation series** (`e583cb9` D-420, the escalation draft taking the visitor's note;
    `b41efc7` D-421, no duplicate staff email, with additive migration `8509c0486d8d`; `5b324a0` D-422,
    the approval-modal note field), **C8** (`f6f84a2`, ruff format) and **D-423**'s documentation
    (`6f107c1`).
    Migration `8509c0486d8d` creating `chat_escalation_sends` is in the repository and is the single
    Alembic head (37 migrations, base-to-head replay verified).
  - *Deployed in staging (`gha-44a12dfc9549`)*: **none of the above.** B4 escalation behaviour **could
    not have been observed live at all**; the `chat_escalation_sends` table is absent from staging, so
    D-421's duplicate-send guard is **not protecting staging today**; and LB-08's measured 10.55 s guest
    QA latency is a **pre-D-423** number, so D-423's ~22% improvement is not in it.
  - *Instrument validation*: `journey-student.spec.ts` is byte-identical between the deployed build and
    HEAD (`git diff --stat 44a12dfc9549..HEAD -- e2e/` shows the only e2e change is
    `chat/response-shapes.spec.ts`), which is why the WORK-13 run is a valid instrument for the older
    build rather than a newer spec run against older code.
  A second, structural half rides here: the deploy pipeline has **no artifact-freshness check**. A
  negative grep over the 711-line workflow returns no `sha256`, no `md5`, no `ETag`, no `content-hash`;
  the only `dist/` hits are the two `aws s3 sync` lines (`:669`, `:674`). The pipeline is `npm ci` →
  `npm run build` → `s3 sync --delete` → a blanket `create-invalidation --paths "/*"` → two `curl -sf`
  liveness checks, with **no step comparing the built artifact to the served artifact** — and the
  workflow says so itself at `deploy-staging.yml:690-691`: "The first two curls only prove the S3 origin
  serves the SPA - they would pass against a completely stale deployment, and they never touch the API."
  The `/me` 401 probe that follows does have teeth for **edge routing** (D-158/AUD-F-37) and says nothing
  about whether the bundle served is the bundle built.
- **Domain:** deployment / staging currency / audit framing
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:295-325`, `:323`;
  `LIVE_BEHAVIOR_EVIDENCE.md:17-29`, `:87`, `:101`, `:110`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:531-541` (WORK-06), `:245-255` (ARCH-34);
  `LOCAL_EXECUTION_FINDINGS.md:569-593` (F-13); `CLAIM_LEDGER.md:2877`;
  `DECISIONS.md:28379-28384` (D-417 §C9), `:28189` (D-416), `:28581` (D-421);
  `OPEN_DECISIONS.md:345-346`
- **Related claim IDs:** WORK-03, WORK-06, ARCH-33, ARCH-34; frames WORK-13, REQ-46, TEST-28, WORK-05
- **Related decision IDs:** D-415, D-416, D-417 §C9 (deployment stays manual, the `push` trigger stays
  commented out), D-418, D-420, D-421, D-422, D-423, D-158, AUD-F-37
- **Repository evidence:** HEAD contains ten commits' worth of behaviour that **no live observation in
  this audit could have seen**; CI is green on HEAD, `make image-check` reads **OK**, and the e2e
  instrument was proven byte-identical between the two builds. `ARCHITECTURE.md` presents a Vite
  content-hash comparison as the frontend half of the deploy gate; the pipeline does not contain one, and
  neither does any `make` target or script.
- **Deployed/live evidence:** the older image, as above. The gap is a normal deploy-cadence artifact, not
  drift — the 3B-2 adjudication records it as an **environment note, severity deliberately unassigned**.
  A silently-failed `s3 sync` or a cached edge object would be undetectable by CI today, and LB-05 is
  that blind spot observed from the live side.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-1**
- **Justification:** every technical input is already measured; what is left is a **timing and
  risk-appetite call** on a deploy that also runs an additive migration, re-seeds, and fires five
  one-off tasks. D-417 §C9 deliberately left that trigger with a human, which does not defer the deploy
  question — it makes "when" a standing user trigger by construction. Engineering evidence can say the
  deploy is safe; it cannot say now is the moment to spend the migration and re-seed.
- **Remaining action:** the user chooses: deploy now and re-walk B4 live; deploy after the next session
  so one deploy carries both (fewer windows, but any live regression then has 11+ commits of suspects);
  or leave it and stop describing staging as current. **Consequences to carry:** migration
  `8509c0486d8d` applies on deploy and closes WORK-03; **B4 has zero live evidence until then**;
  deploying HEAD **destroys the pre-D-423 latency baseline**, so record LB-08's 10.55 s with its build
  SHA *first*; and **RD-01's Python-side fix is inert until a deploy**, so if the terraform side is not
  chosen for RD-01 then RD-01 waits on this decision. The default safe action is option C plus the
  discipline LB-05 already imposes — **state the build SHA beside every live number**. The
  artifact-freshness half has its own immediate documentation fix (`DRIFT-24-ARTIFACT-FRESHNESS`) and a
  derived mechanism question (whether to add a real freshness check) that F-13 and LB-05 together argue
  is worth implementing rather than rewording.
- **Owner type:** user (the deploy trigger), engineering (the freshness check)
- **Reopen condition:** n/a — open now, and re-opens with every subsequent commit
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `RDS-POSTURE` — 1-day backups, deletion protection off, both databases in one AZ, and no document records any of it as a decision

- **Work/Issue ID (topic key):** `RD-09` (ARCH-14)
- **Members:** E5-12, E5-13 (the parameter-group half), E7-3
- **Description:** Identical on both instances: `BackupRetentionPeriod` **1**, `DeletionProtection`
  **`false`**, `MultiAZ` `false`, `AvailabilityZone` **`us-east-1a` on both**, `db.t4g.micro`,
  `StorageEncrypted: true`, `PubliclyAccessible: false`, `PerformanceInsightsEnabled: false`. Two
  consequences: **one AZ loss takes out both databases**, and point-in-time recovery reaches back **one
  day**. Deletion protection off means a single mistaken destroy is not fenced. This is defensible for
  staging on its face — the material point is that **this is the environment the §2.6 gate criteria were
  measured on**, and **no document anywhere records the backup window or the disabled deletion
  protection as a choice with its consequence** (RD-09 states explicitly "Related decisions: none
  recorded"). A second half: `DBParameterGroups` are `default.postgres16` and `default.mysql8.4` — AWS
  defaults, with **no custom group attached to either instance** — so any parameter-level tuning claim
  anywhere in the documentation **cannot be true today**.
- **Domain:** data durability / launch posture
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:268-290`, `:284-286`, `:363`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:173-183` (ARCH-14, the limitation note at `:182` routing these facts
  here), `:179`; `OPEN_DECISIONS.md:171-216` (which touches retention as a *privacy* control, not a
  durability posture)
- **Related claim IDs:** ARCH-14
- **Related decision IDs:** **none recorded** — that absence is the finding. Adjacent: D-122
  (instance-sizing rationale family), AUD-F-28
- **Repository evidence:** `multi_az` defaults `false` in both modules with no environment override, so
  single-AZ is intentional-by-default; `allocated_storage_gb` default 20; no `instance_class` override at
  `terraform/environments/staging/main.tf:248` or `:257`. **No variable, comment or document records
  backup retention or deletion protection as a deliberate staging posture** — they are defaults nobody
  wrote down. No `aws_db_parameter_group` resource is configured for either engine, so the repository and
  the deployed state **agree** on parameter groups; the exposure there is against *prose* elsewhere, not
  against terraform.
- **Deployed/live evidence:** as tabulated, read 2026-08-20T00:04Z. Both instances co-located in
  `us-east-1a` — a fact neither module *chose*; it is where the single-AZ default landed twice. Default
  parameter groups confirmed on the same `describe-db-instances` call; `describe-db-parameters` was
  deliberately not run because with default groups there is nothing repository-configured to compare
  against. A restore drill was out of the phase's scope entirely.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-4**
- **Justification:** backup and deletion-protection posture is explicitly the user's call
  (`DEPLOYED_INFRA_DRIFT_REGISTER.md:290`, `:363`) and RD-09 flagged it `Genuine decision required?:
  YES`. The configuration is fully measured, internally consistent, and nothing is broken; the undecided
  part is how much irreversible loss is acceptable on a synthetic environment whose measurements are
  load-bearing for a launch gate. Engineering can implement any answer in a few lines; only the user can
  say what loss is acceptable.
- **Remaining action:** the user chooses, with the **fix-cost asymmetry split** presented rather than one
  all-or-nothing question: `deletion_protection = true` and a longer `backup_retention_period` are
  near-free and reversible; `multi_az = true` roughly **doubles the instance bill** and therefore
  interacts with UD-3. Options run from "record the current posture as the deliberate staging answer,
  with its consequence, in DECISIONS plus a Terraform comment" (zero cost, makes the risk explicit
  instead of accidental) through deletion protection only, plus 7-day retention, to a full production
  posture. **The §2.6 documentation obligation stands regardless of the answer:** the honest statement is
  not "staging is under-protected" but "the gate criteria were measured on a 1-day-RPO, unfenced,
  single-AZ environment". The parameter-group half is `OBSERVATION_ONLY` with one named cheap follow-up
  — grep the documentation set for parameter-tuning claims (shared buffers, max connections, work_mem,
  innodb settings); if none exists, close it outright, and if one exists it is a documentation defect of
  the ARCH-15 kind. No defect is asserted that was not located.
- **Owner type:** user, then engineering; documentation for the §2.6 sentence
- **Reopen condition:** n/a — open now; and again at production design
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `NAT-EXISTENCE` — the NAT gateway exists, is priced, and has existed since 2026-08-07

- **Work/Issue ID (topic key):** `ARCH-29` (COST-28 / chain M5 item (e))
- **Members:** E1-31 (ARCH-29), E1-53 (COST-28), E2-44 (chain M5 (e))
- **Description:** The corpus disagreed about whether a NAT gateway exists: `ARCHITECTURE.md` describes
  one in the present tense, D-406/D-419 treat it as "absent from the plan entirely", and PROGRESS carried
  a "~$33/mo for nothing while tracing is disabled" note dated outside the re-verified ranges. **The NAT
  exists.** Exactly one (`nat-07ab02d5cd28b6f72`, `available`, public subnet `us-east-1a`,
  `CreateTime 2026-08-07T04:47:31Z`, `ManagedBy=terraform`); the **unfiltered**
  `describe-nat-gateways` returns the same single element, so no deleted or failed NAT exists anywhere in
  the account's history; and the private route table `rtb-0ae773acec1e7ee86` carries an **active**
  `0.0.0.0/0 → nat-…` route. Dated against the commits, D-406 (`15bb6b3`, 2026-08-18T07:52:56Z) and
  D-419's apply (`2e301d6`, 2026-08-18T20:32:35Z) both **post-date the NAT by eleven days** — the plan
  showed no NAT diff because there was nothing to change. Cost measured: `NatGateway-Hours` 290 h =
  $13.0516 over 12.08 days = **$1.080/day ≈ $32.9/mo**, confirming the repository's "~$33/mo" to within
  rounding; split by `RECORD_TYPE` it is `Usage +$13.05` fully offset by `Credit -$13.05`, i.e. **net
  $0.00 today**. Traffic is real but small and bursty: 26.4 MB out / 12.5 MB in over 14 days, non-zero
  every day except 2026-08-19 — and the hourly charge continues on the zero-byte day.
- **Domain:** networking / cost
- **Original source(s):** `CLAIM_LEDGER.md:1089`, `:1994`; `DECISION_SUPERSESSION_MAP.md:191-193`;
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:203-219` (RD-05);
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:221-231` (ARCH-29), `:453-463` (COST-28), `:209-219` (ARCH-28),
  `:101-111` (ARCH-07)
- **Related claim IDs:** ARCH-28, ARCH-29, ARCH-30, ARCH-31, COST-27, COST-28, WORK-08
- **Related decision IDs:** D-084, D-214, D-242, D-406, D-419
- **Repository evidence:** D-406's two-consumer gate at
  `terraform/environments/staging/main.tf:115-117`/`:119`/`:136`; `aws_nat_gateway.this` at
  `terraform/modules/vpc/main.tf:85-94`; the `~$33/mo` figure at `modules/vpc/main.tf:170`. Under
  checked-in defaults (`langsmith_tracing_enabled = true`, turned on 2026-08-06 at the user's explicit
  request) the gate evaluates to **count 1** — so a plan showing no NAT would have required
  `langsmith_tracing_enabled = false`, which only the gitignored `terraform.tfvars` could supply.
  `docs/ARCHITECTURE.md`'s "one NAT in one AZ, deliberately" is the **accurate** text.
- **Deployed/live evidence:** one NAT, matching the gate's evaluation, created 11 days before either
  commit, with the route active and the cost measured. `youtube-sync` is DISABLED live ⇒ applied
  `youtube_sync_enabled = false` ⇒ with a live NAT the `anytrue` gate forces
  `langsmith_tracing_enabled = true`, so **LangSmith is the NAT's sole consumer today** — established by
  observation rather than by reading the unread `terraform.tfvars`.
- **Final disposition:** `RESOLVED`
- **Justification:** post-extraction supersession (§0.2 rule 4). The resource, route, traffic and price
  are all measured, and the repository's cost figure is now empirically right. The tfvars question the
  3A entry created was **dissolved rather than answered**: RD-05 settled the NAT by direct AWS
  observation, so no tfvars read was needed. There is no live cost bug — the feature the NAT serves is
  enabled, and the charge is net $0.00 on credits.
- **Remaining action:** one documentation edit only, tracked in `DOC-DEPLOYED-STATE-CLAIMS`: D-419's
  "absent from the plan entirely" sentence is **misleading, not wrong about the plan** — it described a
  plan *diff*, and the diff was empty because the NAT already existed. Keep `ARCHITECTURE.md`'s wording.
  Two residual unknowns, both recorded and both cheap to leave open: attributing the egress to LangSmith
  specifically would need **VPC Flow Logs, which are not enabled**; and `CreateTime` dates the resource,
  not the commit, so it cannot distinguish *which version* of the gate applied it — only that it was not
  D-406 or D-419. Whether to keep paying for the NAT is a spend question belonging to
  `BUDGET-GROSS-SPEND`.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `ARCH-21-SCHEMA-SPLIT` — SPEC §5.33.3's six-schema split is genuinely undecided and recorded in one file scheduled for archive

- **Work/Issue ID (topic key):** `ARCH-21` (SPEC §5.33.3; `FINAL_ARCHITECTURE.md` question 5)
- **Members:** E1-24 (ARCH-21), E6-18
- **Description:** Whether to adopt SPEC §5.33.3's six-schema split (`learning`, `rag`, `memory`,
  `checkpoint_learning`, `checkpoint_chat`, `evaluation`) now, later or not at all was recorded as an
  open question S32 was to resolve. No read document settles it and no decision entry exists.
  `FINAL_ARCHITECTURE.md:179-180` (question 5) appears to be the **only** record of the unmade decision:
  `OPEN_DECISIONS.md` declares nothing open, and `ARCHITECTURE.md` never mentions a schema split. The
  inventory concurs — "question 5 … appears to be the only one with no recorded closure anywhere" — and
  the file is routed to **ARCHIVE after two extractions**. If it is archived without extracting this,
  an unmade decision disappears from the corpus entirely.
- **Domain:** data-layer architecture / decision tracking
- **Original source(s):** `CLAIM_LEDGER.md:985`; `FINAL_ARCHITECTURE.md:163-167`, `:179-180`,
  `:182-185`; `SPEC.md:3178-3187`; `DOCUMENTATION_RISK_REGISTER.md:281-284`;
  `DOCUMENT_INVENTORY.md:289-293`, `:305-308`
- **Related claim IDs:** ARCH-19, ARCH-21, ARCH-22, ARCH-23
- **Related decision IDs:** D-004, SPEC §5.33.3 — **no D-number owns it**
- **Repository evidence:** `packages/db/alembic/env.py:36,59,72` has no `include_schemas` and no
  `schema_translate_map`, so no split is implemented. The unresolved status is inferred from absence
  (confidence MEDIUM): if a grep of DECISIONS/ROADMAP were to find a ruling, this would collapse to
  `DOCUMENTATION_ONLY`.
- **Deployed/live evidence:** the deployed Postgres runs **without** the logical split, so the SPEC
  requirement is unmet and undispositioned — which is the substance of the open question. The precise
  number of logical databases and schemas is a database-content read (`DB-CONTENT-VERIFY`).
- **Final disposition:** `DEFERRED`
- **Justification:** a production-time schema question. "Never" is defensible at one database and ~1,000
  MAU, so it is low urgency and high loss-if-dropped rather than a live decision. It is **excluded from
  the user-decision queue** on that basis.
- **Remaining action:** one **mandatory extraction before archive**: lift question 5 out of
  `FINAL_ARCHITECTURE.md` into an owned decision record (or an explicit "deliberately undecided" note)
  *before* `RISK-GROUP-ARCH-AUTHORITY` archives the file. Sequencing matters — do not archive first.
  Then reopen at production schema design. The related one-line as-built fact ("today's system is one
  `intellichoice` Postgres database", asserted only in the stale projection) belongs in the canonical
  architecture document and is a member of `RISK-GROUP-ARCH-AUTHORITY`.
- **Owner type:** documentation (the extraction), user + engineering at production design
- **Reopen condition:** production schema design.
- **PROJECT_STATE?** yes — deferred, with a pre-archive extraction obligation
- **Historical/archive only?** no

### `ARCH-34-REVISION-DRIFT` — both services run one task-definition revision behind, harmlessly; the tfvars half is UNKNOWN

- **Work/Issue ID (topic key):** `ARCH-34` (RD-11)
- **Members:** E5-15
- **Description:** learning-api's service runs `:150` while its family's latest is `:151`; chat-api runs
  `:148` against latest `:149`; ops-task's latest is `:144` with no service. All three latest revisions
  were registered **within 3 milliseconds** of each other at 2026-08-18T20:20:41Z — the signature of a
  single `terraform apply` ~1.5 h *after* the two service deployments were created, with
  `ignore_changes = [task_definition]` preventing adoption. A normalised diff (ignoring `revision`,
  `registeredAt`, `taskDefinitionArn`, `registeredBy`) shows `chat-api:148` versus `:149`
  **byte-identical**, and `learning-api:150` versus `:151` differing **only** in the ordering of the
  `compatibilities` array (`["MANAGED_INSTANCES","FARGATE"]` versus `["FARGATE","MANAGED_INSTANCES"]`) —
  a server-side serialisation artifact. Image identity is unaffected: `gha-44a12dfc9549` is live on both
  services **by tag and by digest**, one `PRIMARY` deployment each, both `rolloutState: COMPLETED`. So
  the D-137 family-resolution trap is **live-armed but harmless today**: a tool comparing revision
  *numbers* reports drift, a tool comparing *images* reports none — and that distinction is the finding.
- **Domain:** deployment / operator tooling
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:307-322`;
  `DEPLOYED_INFRA_STATE_EVIDENCE.md:245-255` (ARCH-34), `:531-541` (WORK-06)
- **Related claim IDs:** ARCH-34, ARCH-33, WORK-06, WORK-07
- **Related decision IDs:** D-418, D-137, D-244
- **Repository evidence:** `make image-check` at `Makefile:292-294` invoking
  `scripts/check_deployed_image_consistency.py` — **operator-invoked only, wired into neither CI nor
  `deploy-staging.yml`**. `adopt_deployed_image` defaults `true`
  (`terraform/environments/staging/variables.tf:201-202`), consumed by the `for_each` guard at
  `main.tf:12`; image expression at `main.tf:45`/`:49`; `learning_api_image_tag` and
  `chat_api_image_tag` both default `"unset"`.
- **Deployed/live evidence:** as tabulated; the un-adopted revisions are functionally no-ops (same image,
  cpu and memory, env, secrets, sidecar).
- **Final disposition:** `OBSERVATION_ONLY`; **the tfvars-staleness half is `UNKNOWN`**
- **Justification:** nothing is broken, and the existing operator control already covers it — the
  recorded insight is the semantic gap in *what* it compares. Its value is demonstrated by its own
  absence: RD-11 and LB-05 both found drift the uninvoked check was designed to catch.
- **Remaining action:** none required. Two residual unknowns, both structural rather than neglected.
  **(1) UNKNOWN — the tfvars-staleness half of ARCH-34 is not answerable from AWS at all**: with
  `adopt_deployed_image = true` the `var.*_image_tag` pin is bypassed, so pin staleness is invisible
  from the control plane; `terraform.tfvars` exists (7,917 bytes, mtime 2026-08-17 22:41) and its content
  was **not read by policy**. Classify that half UNKNOWN, **not clean**; the resolution step is
  method-bounded — the file is unreadable under this audit's rules, so it can only be closed by the user
  or by a policy change. This also remains a standing hazard for future audits: a gitignored tfvars file
  means the tracked tree does not determine the plan. **(2)** `list-task-definitions --max-items 5`
  truncated (a `NextToken` was returned each time), so revisions below 147/145/140 were never enumerated.
  Whether the deploy-time version gate ever *fired* is GitHub state (`ARCH-33-CI-GATE`) and **must not
  be double-counted** against this entry.
- **Owner type:** none for the observation; user for the tfvars policy question
- **Reopen condition:** n/a
- **PROJECT_STATE?** no for the observation; the UNKNOWN half is listed in §12.2
- **Historical/archive only?** yes, with the UNKNOWN carried forward

### `RD-12-INGRESS` — the documented product hostnames do not exist live; staging is reached through CloudFront

- **Work/Issue ID (topic key):** `RD-12` (ARCH-28 ingress half)
- **Members:** E5-16
- **Description:** Two CloudFront distributions exist, both `Enabled`/`Deployed`, `PriceClass_100`,
  `CloudFrontDefaultCertificate: true`, **`Aliases: null`** — `E371R2SNCXJW2C` →
  `d35dfnjzmgrm01.cloudfront.net` (learning; `learning-s3` OAC + `learning-alb`) and `E3EP2M0Q2XRXWZ` →
  `d222glidpp4azv.cloudfront.net` (chat; same ALB). The deployed entry points are therefore the
  `*.cloudfront.net` domains, not the `learning.` / `chat.intellichoice.org` hostnames CLAUDE.md and SPEC
  document. **Operationally load-bearing companion fact:** the ALB security group
  `sg-04a0e7a83052aeb8c` admits tcp/80 **only** from the managed prefix list `pl-3b927c52`
  (`com.amazonaws.global.cloudfront.origin-facing`) — there is no `0.0.0.0/0` on port 80 anywhere — and
  the ALB has **no port-443/HTTPS listener** (one HTTP:80 listener, default action
  `fixed-response 404`). Any probe must go through CloudFront; **a direct-to-ALB timeout is by design and
  must not be read as an outage.**
- **Domain:** networking / ingress / documentation
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:326-340`, `:336`, `:384-386`
- **Related claim IDs:** ARCH-28, plus the documented-hostname claims in `CLAUDE.md` and SPEC
- **Related decision IDs:** C3, S48 (DNS at integration time), D-152
- **Repository evidence:** `terraform/modules/cloudfront-spa-api/main.tf:128`
  `cloudfront_default_certificate = true`, `:53` `price_class = var.price_class`; **no alias or ACM
  certificate configuration anywhere**, which is self-consistent because a custom alias would require an
  ACM certificate. The deployed state matches the repository exactly; the gap is between the repository
  and the **documented hostnames**.
- **Deployed/live evidence:** as above — matches the repository, differs from the documents.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** DNS records are C3/S48 scope, added by the org at integration time, so absence today
  is expected pre-integration state rather than a defect — and D-152 keeps integration deliberately
  deferred. Sequencing is already decided.
- **Remaining action:** none for the infrastructure. This entry's real value is **procedural**: any live
  probing in this or a later phase must target the two `*.cloudfront.net` domains, and a direct-ALB
  timeout is expected. Keep that hazard note attached rather than dropping the item as "no action". One
  small documentation opportunity: CLAUDE.md and SPEC state the product hostnames without noting that
  staging is reached via CloudFront domains — worth one clarifying sentence, because it has already cost
  re-walk confusion before (folded into `RISK-GROUP-INDEX`'s CLAUDE.md pass).
- **Owner type:** external-org at integration; documentation for the clarifying sentence
- **Reopen condition:** integration (C3/S48), when the org adds DNS records.
- **PROJECT_STATE?** yes — parked, with a standing probing hazard
- **Historical/archive only?** no

### `WORK-23-RETENTION-JOB-GATING` — the checkpoint-retention job is genuinely unscheduled, and RD-01 blocks its prerequisite

- **Work/Issue ID (topic key):** `WORK-23`
- **Members:** E5-32, E1-106 (WORK-23)
- **Description:** `ARCHITECTURE.md:31-36` says the retention job "stays **unscheduled** until this one
  has a record of firing", so the *correct* deployed state is absence — and absence is what is deployed.
  **No `checkpoint-retention` schedule exists**; the complete schedule list is the five names under
  ARCH-04, none containing "checkpoint" and none a deletion job beyond the two already-enabled purges.
  EventBridge **Rules** hold exactly one entry and it is not a cron:
  `intellichoice-staging-ops-task-failed`, ENABLED, on the default bus, firing on any ops-task container
  that stops with a non-zero exit code (`detail.containers.exitCode = [{anything-but:[0]}]`, scoped by
  task-definition prefix and cluster ARN). The documented restraint is **real, not merely documented**.
  The measurement that framed the job's scope is dated and expiring: completed sessions are 9 threads /
  3.2 MB = **1.7%** of checkpoint storage, abandoned **77%** and chat **19%**; at a 30-day floor the job
  addresses **0% today** because the oldest staging thread is 22 days old, so the dry-run's honest answer
  is zero threads and zero bytes — which is why the U7 document recommends *not* writing the
  completed-session deletion yet.
- **Domain:** scheduled jobs / data retention
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:555-565` (WORK-23), `:89-99` (ARCH-04);
  `CLAIM_LEDGER.md:3137`; `U7_CHECKPOINT_CONSOLIDATION.md:52-70`, `:259-279`
- **Related claim IDs:** WORK-19, WORK-20, WORK-21, WORK-22, WORK-23, WORK-35, ARCH-04, ARCH-05
- **Related decision IDs:** the `ARCHITECTURE.md` retention-sequencing rule, D-331, D-333, D-322 §4
- **Repository evidence:** `checkpoint_retention_cli.py` exists with a manual `Makefile:106` target and
  its own tests, and is deliberately **not** in `locals.jobs`; `grep -i checkpoint` over `terraform/`
  returns only comments and dashboard metric names — no `aws_scheduler_schedule` resource anywhere.
- **Deployed/live evidence:** no such schedule. Repository and deployed agree, and both agree with the
  document.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** deliberately unscheduled, pending the prerequisite job having a record of firing —
  the gating rule is already written down, so nothing needs deciding here. Cleanly confirmed.
- **Remaining action:** none directly, but **note the dependency: `RD-01` silently blocks this.** The
  prerequisite for scheduling is *the session-consolidate job having a record of firing*, and that record
  is exactly what RD-01 currently makes unobtainable. The item is also **split, not closed**:
  re-measuring the underlying eligibility figures needs a query against the private Postgres
  (`DB-CONTENT-VERIFY`), and the numbers age fast because the staging database is young. The scheduling
  and apply-enable decisions themselves belong to `RETENTION-CLUSTER` (UD-7). Also record positively that
  the one EventBridge rule is a real, working safety net for ops-task failures — relevant when reasoning
  about RD-01's "job success unproven", since a non-zero exit *would* fire it.
- **Owner type:** none now; engineering after RD-01 and UD-7
- **Reopen condition:** the session-consolidate job has a verified record of firing (i.e. after RD-01's
  fix ships and publishes), and UD-7 decides scheduling.
- **PROJECT_STATE?** yes — parked, with RD-01 named as the blocker
- **Historical/archive only?** no

### `ARCH-33-CI-GATE` — whether the deploy-time version gate ever fired, and whether the PR backlog is cleared, are unread GitHub facts

- **Work/Issue ID (topic key):** `ARCH-33` (with WORK-44)
- **Members:** E5-30
- **Description:** Two items sit outside AWS and outside the repository. **ARCH-33** — whether the
  deploy-time version gate has ever actually fired is GitHub Actions run history
  (`gh run list --workflow=deploy-staging.yml`); the *deployed* side of the same concern is already
  covered by WORK-06 and ARCH-34 and **must not be double-counted**. **WORK-44** — whether the 26-PR
  dependency backlog is actually cleared is GitHub state (`gh pr list`). Neither was executed in any
  phase.
- **Domain:** CI/CD / project hygiene
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:592-596` (§3.2);
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:388-390`
- **Related claim IDs:** ARCH-33, WORK-44
- **Related decision IDs:** D-418 (the image and version gate), D-315 (the batch-merge rule)
- **Repository evidence:** the gate exists in `deploy-staging.yml`; the repository shows it is *wired*,
  never that it *fired*. PR state has no repository expression at all.
- **Deployed/live evidence:** AWS shows the *outcome* of deploys (image tag, digest, rollout state) but
  carries no record of a CI gate's decision.
- **Final disposition:** `DEFERRED`
- **Justification:** two `gh` commands away, just not any lane's surface so far. Genuinely cheap.
- **Remaining action:** run `gh run list --workflow=deploy-staging.yml` and `gh pr list`. ARCH-33 in
  particular is the only evidence that a **preventive** control has ever engaged. Watch the
  double-counting warning against `ARCH-34-REVISION-DRIFT`.
- **Owner type:** engineering
- **Reopen condition:** n/a
- **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `COST-28-EIP` — no unassociated Elastic IP exists, so the idle-EIP cost concern does not fire

- **Work/Issue ID (topic key):** `COST-28` (ARCH-28 EIP half)
- **Members:** E5-33
- **Description:** **Three EIPs, all associated**: `eipalloc-0715fd3228e854c56` →
  `eni-02a5fb06297ad95e0` (Name=`intellichoice-staging-nat-eip`), and two untagged ones that resolve via
  `describe-network-interfaces` to the ALB's two per-AZ ENIs
  (`ELB app/intellichoice-staging-alb/a1e99fb6d592d3d4`). **No unassociated EIP anywhere**, so the
  idle-EIP charge COST-28 asked about does not apply. Recorded in the same pass: seven VPC endpoints all
  `available` (6 Interface — `ecr.api`, `ecr.dkr`, `logs`, `secretsmanager`, `bedrock-runtime`, `xray` —
  all pinned to the single private subnet `subnet-0fab49a3bf8fc3a8f` for the per-AZ-per-hour cost reason,
  plus the free S3 **Gateway** endpoint on the private route table); no `bedrock-mantle` endpoint; three
  route tables, with the VPC main table carrying `local` only and **zero** subnet associations.
- **Domain:** cost / networking
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:209-219` (ARCH-28), `:453-463` (COST-28)
- **Related claim IDs:** COST-28, ARCH-28
- **Related decision IDs:** the single-subnet endpoint-placement rationale
  (`modules/vpc/main.tf:168-173`)
- **Repository evidence:** endpoints `["ecr.api","ecr.dkr","logs","secretsmanager"]` plus conditional
  `bedrock-runtime` and `xray` at `terraform/modules/vpc/main.tf:143-160`, all pinned to
  `subnet_ids = [aws_subnet.private[0].id]`, plus the S3 gateway endpoint at `:183-191`. No standalone
  EIP resources beyond the NAT's.
- **Deployed/live evidence:** exactly as configured, with the two ALB EIPs being AWS-managed rather than
  repository-declared.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** a negative finding; the coverage record can state the EIP question as **closed
  clean** rather than unexamined.
- **Remaining action:** none. One method note worth keeping: AWS does not expose whether a route came
  from an inline `route` block or a standalone `aws_route` resource, so the **mechanism** half of
  ARCH-28 stays config-only evidence — and interface-endpoint DNS resolution *from the second AZ* is a
  runtime property the control plane cannot show.
- **Owner type:** none
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `F-03-DRIFT-DETECTOR` — `terraform apply` is not in the deploy workflow, and no automated drift detector exists

- **Work/Issue ID (topic key):** `F-03`
- **Members:** E4-3
- **Description:** `terraform/environments/staging/main.tf:547-552` documents, in the repository's own
  words, a configuration change written and never applied: D-344 authored
  `autoscaling_max_capacity = 1` "and **it was never applied** - `terraform apply` is not part of
  `deploy-staging.yml` and nobody ran it, so live stayed at the module default of 3 the whole time."
  Consequence: every terraform-derived number in Phases 3A and 3A.5 is **file state only**. The
  second-order point is a genuine strengthening: the terraform-*parsing* pytest tests
  (`packages/observability/tests/test_alarm_severity_routing.py`, 3 tests) passed, upgrading those
  configuration claims from "a file read by an auditor" to "a file asserted by an executed test" — which
  is still not a statement about AWS.
- **Domain:** infrastructure / deployment / audit epistemics
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:241-271`; `LOCAL_EXECUTION_EVIDENCE.md:852-855`;
  `REPOSITORY_DRIFT_REGISTER.md:325`
- **Related claim IDs:** COST-19, COST-23, COST-24, COST-28, COST-29, SEC-10, ARCH-02, ARCH-10, ARCH-12,
  ARCH-29, ARCH-35, WORK-08, REQ-49
- **Related decision IDs:** D-344 (the stopgap never applied), D-349
- **Repository evidence:** `terraform/environments/staging/main.tf:547-552`;
  `.github/workflows/deploy-staging.yml` has **no `terraform` step**. **No automated config-versus-live
  drift detector exists** anywhere.
- **Deployed/live evidence:** the deployed reality confirms the testimony: chat-api's scalable target is
  `MinCapacity 1 / MaxCapacity 3` — **not** the D-344 value of 1 — empirically confirming the
  "written but never applied" example.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** as a *framing constraint on Phase 3B* this has been consumed: Phase 3B ran and
  produced both an infrastructure half (`DEPLOYED_INFRA_*`) and a behavioural half (`LIVE_BEHAVIOR_*`),
  so the named numbers were re-verified against AWS rather than assumed. This entry keeps the constraint
  visible as a standing method rule and preserves the F-03 confirmation: a configuration change can be
  written, committed, commented and never applied, which is the whole reason this audit kept terraform
  configuration and AWS state as two separate evidence sources.
- **Remaining action:** the *finding* is discharged by 3B; the *open work* is the absence of a drift
  detector. Whether a plan-only `terraform plan` drift-detection step runs in CI or on a schedule is a
  derived judgement about operational burden versus detection — without it, the divergence this finding
  documents is undetectable except by an audit. It is deliberately **not** promoted to a queue entry: it
  is a recommendation-shaped derived question, and the register records it here rather than adding a
  thirteenth decision. All the items F-03 named as required 3B targets were reached (learning-api
  512/1024/desired-2 versus chat-api 256/512/desired-1, the eight alarms, the `anytrue`-driven NAT
  gateway, the single-worker task definitions) — see `D136-PRICE-TABLE`, `KPI-ALARM-FLOOR`,
  `NAT-EXISTENCE`.
- **Owner type:** engineering, if the detector is wanted
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes, with the method rule carried forward

### `DRIFT-24-ARTIFACT-FRESHNESS` — `ARCHITECTURE.md` describes a content-hash deploy control the pipeline does not contain

- **Work/Issue ID (topic key):** `DRIFT-24` (ARCH-33; also ARCH-34)
- **Members:** E3-24
- **Description:** The ECS half of the deploy gate is confirmed exactly (five FATAL assertions, tag
  comparison outside the retry, bounded by `WAIT_SECONDS=300`). But grepping the whole 711-line workflow
  for `sha256|md5|ETag|content-hash|dist/|vite` yields **no hash-comparison step**, and no `make` target
  or script implements one. The frontend leg is `aws s3 sync --delete` plus a CloudFront invalidation plus
  three curls. `ARCHITECTURE.md` itself phrases the check as "building the commit locally and comparing"
  — a **procedure, not a control** — which refutes the Phase-2 reading of ARCH-33 as a standing control.
- **Domain:** deploy / documentation accuracy
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:290-299`;
  `LOCAL_EXECUTION_FINDINGS.md:569-593` (F-13, the workflow's own admission)
- **Related claim IDs:** ARCH-33, ARCH-34
- **Related decision IDs:** D-418, D-158, AUD-F-37
- **Repository evidence:** `.github/workflows/deploy-staging.yml:409-501`, `:667-711`, `:690-691`;
  `docs/ARCHITECTURE.md:455-458`; negative grep over the workflow, `Makefile` and `scripts/`.
- **Deployed/live evidence:** LB-05 is the live consequence — the deployed build is 10 commits behind
  local HEAD, and a silently-failed sync or a cached edge object would be undetectable by CI.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the immediately actionable defect is that a document describes a control the
  pipeline does not contain; retracting or correcting that sentence costs nothing and removes a false
  assurance. The register's own grading calls it editorial-or-engineering, not product.
- **Remaining action:** reword `ARCHITECTURE.md:455-458` to describe the procedure it actually is. The
  **mechanism** question — implement a real freshness check, e.g. assert the served `index.html`
  references the just-built hashed asset — rides on `LB-05-DEPLOY-GAP`, where F-13 and LB-05 together
  make the case for implementing rather than rewording; the two findings are the same gap from opposite
  directions and must not be counted as independent evidence of two problems. Related:
  `ARCH-34-REVISION-DRIFT` records that `make image-check` is likewise operator-invoked only.
- **Owner type:** documentation (the sentence); engineering (the optional mechanism)
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `LB-06-TRANSPORT-POSTURE` — no email or calendar provider lever exists on either deployed task definition

- **Work/Issue ID (topic key):** `LB-06`
- **Members:** E6-6
- **Description:** Full env-var **name** lists were enumerated from both active task definitions (21
  names on learning `:150`, 24 on chat `:148`; secret *names* only, no value fetched or printed).
  **No email-provider or calendar-provider variable of any kind** — nothing matching `EMAIL`, `GMAIL`,
  `SES`, `MAPS`, or any `*_PROVIDER_*` transport selector; the only `*PROVIDER*` names are
  `{LEARNING,CHAT}_BEDROCK_PROVIDER`. Transports are dev fakes **by construction, not by env**:
  `learning_api/main.py:111` → `FakeEmailTransport()` with no env branch; `chat_api/main.py:85-87` →
  `FakeEmailTransport()`, `FakeCalendarTransport()`, `FakeMapsProvider()`, all unconditional; a tree-wide
  grep returns exactly those two construction sites. Two open questions close with it: staging
  `BEDROCK_PROVIDER` is **`bedrock`** on both apps (overriding the committed tfvars default `"mock"`),
  and both apps carry `*_DEV_TOKEN_ENDPOINT_ENABLED=false`, confirming staging `/dev/token` is the D-097
  shared-secret path.
- **Domain:** deployment safety posture / external-transport gating
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:329-366`; `LIVE_BEHAVIOR_EVIDENCE.md:17-29`
- **Related claim IDs:** the phase's own safety gate; ARCH-31
- **Related decision IDs:** D-002, D-097, SPEC §5.1.4, §5.24
- **Repository evidence:** the fakes are unconditional in code, with no env-selected alternative anywhere
  in `apps` or `packages` outside tests.
- **Deployed/live evidence:** no selector variable exists on either task definition, so **there is no
  lever even if the code had one**. Bedrock, by contrast, is genuinely real, so every staging number in
  the audit is a paid measurement.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** a positive finding, recorded so the safety argument can be re-derived rather than
  re-assumed.
- **Remaining action:** none. Two cautions to preserve: the safety argument is **re-derivable, not
  permanent** — it expires the day `main.py:111` grows an env branch or a future task definition adds a
  provider variable, so a standing pre-probe check is preferable to a recorded conclusion; and it proves
  nothing about production. The `BEDROCK_PROVIDER` closure belongs in the 3B-1 evidence file, so this
  item has a small documentation tail.
- **Owner type:** documentation (the small tail)
- **Reopen condition:** any future live-probe session must re-derive it.
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `DOC-DEPLOYED-STATE-CLAIMS` — documents asserting deployed state that AWS contradicts

- **Work/Issue ID (topic key):** `DOC-DEPLOYED-STATE-CLAIMS`
- **Members:** E5-8 (RD-05, D-419's NAT sentence), E5-9 (RD-06, ARCH-15 refuted), E5-17 (WORK-08,
  PROGRESS's "unapplied"), E5-18 (ARCH-11 wording), E1-90 (WORK-07, the phantom tfvars-floor warning),
  E1-91 (WORK-08 contradiction), E1-32 (ARCH-34's absence from `ARCHITECTURE.md`), E2-43 (chain M5
  applied-versus-unapplied), E3-28 (DRIFT-28), E3-29 (DRIFT-29)
- **Description:** One themed edit class: every document statement about **deployed** state that a live
  read contradicts, plus the two repository statements about live behaviour that AWS falsifies.
  **(a) D-419's "NAT absent from the plan entirely"** is misleading, not wrong about the plan — it
  described a plan *diff*, and the diff was empty because the NAT already existed eleven days earlier;
  `ARCHITECTURE.md`'s "one NAT in one AZ, deliberately" is the accurate text. **(b) ARCH-15 refuted:**
  the repository justifies `db.t4g.micro` by asserting "this AWS account has Free Tier restrictions
  active (confirmed via a real `CreateDBInstance` rejection during S32/D-084)". CloudTrail's 90-day
  window (reaching back to 2026-05-22, so the S32 window is fully covered) holds exactly **three**
  `CreateDBInstance` events, all by `jeongsik-staging-admin`: a 2026-07-23T01:03:47Z mysql **8.4.3**
  request **already at `db.t4g.micro`**, rejected with `InvalidParameterCombinationException` /
  `Cannot find version 8.4.3 for mysql`; then postgres 16.4 at `db.t4g.micro` succeeding at 01:05:44Z;
  then mysql **8.4.10** at `db.t4g.micro` succeeding at 01:05:45Z. The single rejection was an
  engine-version typo retried successfully two minutes later and has nothing to do with instance size or
  Free Tier. Independently, `freetier get-free-tier-usage` returns 16 rows, **every one "Always Free"**,
  with no "12 Month Free" row at all (notably no RDS `db.t*.micro` 750-hour row), and paid RDS, NAT and
  Fargate all provisioned fine. **(c) `PROGRESS.md:155-156` records D-401 and D-406 as unapplied; AWS
  refutes it** — see `DRIFT-93-D401-D406-APPLIED`. **(d) ARCH-11 is worded as if the p95-latency
  step-scaling policy were chat-api's alone**; both services carry it (exactly four scaling policies,
  all `StepScaling`, zero `TargetTrackingScaling`; +1 on [0,7), +2 on [7,∞), cooldown 120; −1 on
  (−∞,0], cooldown 300), with per-service alarm thresholds differing (chat-api p95 **20.0 s** versus
  learning-api **3.0 s**), and the policies fire for real (chat-api to 3 tasks at 2026-08-18T22:10:07Z
  then back to 1 by 22:32:39Z; learning-api to 3 at 2026-08-19T22:19:09Z). **(e) The retracted
  tfvars-floor warning** — a self-authored claim that a fresh-checkout apply would "roll staging back
  past Milestone 13" — was measured false (Terraform reads the image from the deployed container
  definition; `adopt_deployed_image` has defaulted true since D-244), yet `PROGRESS.md:85` and
  `OPEN_DECISIONS.md:15` still say "D-401 and D-406 stay unapplied until this exists", which is *why*
  PROGRESS reads them as unapplied. **(f) `ARCHITECTURE.md` has no section for the deploy-consistency
  control at all** (`make image-check` / `scripts/check_deployed_image_consistency.py`); its
  deploy-verification section stops at the ECS control-plane and frontend-hash checks.
  **(g) DRIFT-28/29:** the documented NAT gate is described as a single `langsmith_tracing_enabled` flag
  while the configuration has been a two-consumer `anytrue` map since D-406 — the documented condition is
  **narrower** than the implemented one, and the reason is recorded in place ("switching tracing off
  would have silently stripped that job's egress").
- **Domain:** documentation accuracy about deployed state
- **Original source(s):** `DEPLOYED_INFRA_DRIFT_REGISTER.md:203-219` (RD-05), `:223-238` (RD-06),
  `:399-403`, `:422`, `:425`; `DEPLOYED_INFRA_STATE_EVIDENCE.md:185-195` (ARCH-15), `:137-147`
  (ARCH-11, the wording note at `:146`), `:543-553` (WORK-08); `REPOSITORY_DRIFT_REGISTER.md:334-343`,
  `:345-354`; `CLAIM_LEDGER.md:1154`, `:2929`, `:2942`; `DECISION_SUPERSESSION_MAP.md:176-182`,
  `:2225-2228`
- **Related claim IDs:** ARCH-11, ARCH-15, ARCH-28, ARCH-29, ARCH-33, ARCH-34, COST-28, WORK-07,
  WORK-08
- **Related decision IDs:** D-084, D-122, D-137, D-244, D-344, D-401, D-406, D-417 §A3, D-418, D-419
- **Repository evidence:** ARCH-15's assertion is a **self-report only** — the comment at
  `terraform/modules/rds-postgres/variables.tf:25-28` and its twin in `modules/rds-mysql`; Phase 3A left
  it UNVERIFIED precisely because it is the repository testifying about itself.
  `enable_latency_step_scaling = true` for chat-api at `main.tf:544` **and** learning-api at `:457`; the
  CPU target-tracking policy is `count`-ed out; the D-344 stopgap is reverted and its own comment at
  `main.tf:547-552` says it was never applied — **the repository is accurate there**; only ARCH-11's
  prose is stale. The two-consumer gate is at `main.tf:100-138`, `variables.tf:163-189`,
  `modules/scheduled-jobs/main.tf:120-124`, against `ARCHITECTURE.md:2161-2174`'s single-flag prose.
- **Deployed/live evidence:** the CloudTrail record ARCH-15's comment **names as its own evidence** was
  retrieved in full and **falsifies the comment on its own stated evidence** — the audit's only
  `DEPLOYED_DIFFERS_FROM_REPOSITORY` classification. D-401/D-406 are applied (topic exists with a
  confirmed subscription and exactly the four predicted member alarms; the NAT exists with an active
  default route and `ManagedBy=terraform`; three task-definition families re-registered within 3 ms at
  2026-08-18T20:20:41Z). Four StepScaling policies live, zero target-tracking.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** one edit class — a document asserting deployed state that AWS contradicts — with
  seven one-liner members and one generalisable lesson worth recording once rather than seven times: **a
  commit title claiming an apply is not an apply**, and PROGRESS-style status lines about infrastructure
  should cite a resource, not a commit. **ROADMAP was right and PROGRESS.md is wrong.** Method point
  worth preserving from ARCH-15: a claim that names its own evidence becomes falsifiable the moment that
  evidence is retrievable, so this does **not** close as "unfalsifiable read-only".
- **Remaining action:** the edits, as a single pass. Two cautions: do **not** over-correct ARCH-15 into
  "Free Tier is irrelevant to this account" — the `freetier` read is strong but *indirect* evidence,
  because there is no first-class describe API for "are Free-Tier restrictions active" — and the
  `db.t4g.micro` **choice** remains sound, so nothing about the infrastructure changes; and when
  correcting the applied-versus-unapplied contradiction, do **not** move the "stay unapplied" quote onto
  D-406: that sentence lives at `DECISIONS.md:28296-28297` inside **D-417/A3**, and D-406's own body says
  only "nothing applied". Record ARCH-15 as **WEAKENED** wherever ARCH-15 is tracked.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-SCHEDULER-SECTIONS` — `ARCHITECTURE.md` contradicts itself about which nightly jobs are scheduled

- **Work/Issue ID (topic key):** `DRIFT-25` (ARCH-04 / ARCH-05 / ARCH-06)
- **Members:** E3-25 (DRIFT-25), E1-17 (ARCH-04), E1-18 (ARCH-05), E1-19 (ARCH-06)
- **Description:** `ARCHITECTURE.md:28-30` lists four unattended EventBridge schedules
  (`session-consolidate`, `chat-purge`, `retention-purge`, `memory-consolidate`) with a fixed nightly
  order, and is **directly contradicted by `:1850-1851` and `:2068` in the same file**, which still
  record the older posture — `make memory-consolidate` as "manual trigger only this session" and
  `make chat-purge` as having "no scheduler yet". The configuration falsifies the stale sections: both
  jobs have enabled `aws_scheduler_schedule` resources (`chat-purge` `cron(10 18 * * ? *)`,
  `memory-consolidate` `cron(30 18 ? * SUN *)`, `schedule_expression_timezone = "UTC"`), and the
  module's own opening comment records exactly the prior state those sections describe ("Before this
  existed … all four jobs were `make` targets a human ran (AUD-F-06)"). A separate ambiguity in the same
  neighbourhood: `ARCHITECTURE.md:30-36` closes with "that retention job stays unscheduled until this
  one has a record of firing" while `:28` lists `retention-purge` among the four enabled schedules — the
  referent (`checkpoint_retention_cli` versus `retention-purge`) is ambiguous in a
  correctness-critical paragraph. The nightly order is itself a correctness constraint (D-357): an
  unprojected learning thread is invisible to learning windows and looks like chat to the other branch.
- **Domain:** infrastructure / documentation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:301-310`; `CLAIM_LEDGER.md:764`, `:777`, `:790`
- **Related claim IDs:** ARCH-04, ARCH-05, ARCH-06, ARCH-07, WORK-19, WORK-21, WORK-23
- **Related decision IDs:** AUD-F-06, D-114, D-333, D-357
- **Repository evidence:** `terraform/modules/scheduled-jobs/main.tf:3-6`, `:52-125`, `:196-198`;
  `terraform/environments/staging/main.tf:842-866`; `docs/ARCHITECTURE.md:28-30`, `:30-36`,
  `:1850-1851`, `:2068`.
- **Deployed/live evidence:** **AWS holds the schedules** — ARCH-04/ARCH-07 confirmed exact at runtime,
  including the per-job retry asymmetry (`memory-consolidate = 0`). `checkpoint_retention_cli` has **no**
  schedule, which resolves the ambiguous referent in favour of `retention-purge` being the scheduled one.
  **Counterweight that must travel with the correction:** RD-01 shows the jobs' dead-man's switch is
  structurally non-functional, so "scheduled" does **not** imply "observed to have run successfully".
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** four claims, one edit. An operator reading the stale sections would believe a
  90-day retention promise depends on a human. The infra read settled which text is true; the loser is
  document rot.
- **Remaining action:** delete or date the two stale per-pipeline sections and disambiguate the retention
  referent. Keep the distinction RD-01 forces: schedules exist in AWS (verified) **and** nothing would
  alarm if a job silently stopped completing — do not let "confirmed at runtime" read as "the retention
  promise is being kept". The stale terraform header comment in the same module ("Four jobs are defined,
  three are enabled" against its own five-defined/four-enabled `locals.jobs`) is DRIFT-75/DRIFT-102,
  members of `BATCH-LOW-STALE-STATUS`, and is **one** operative comment across those two entries.
- **Owner type:** documentation
- **Reopen condition:** n/a
- **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DRIFT-93-D401-D406-APPLIED` — D-401 and D-406 are applied, proven by resource existence

- **Work/Issue ID (topic key):** `DRIFT-93` (WORK-08) — batch B exception
- **Members:** E3-55:DRIFT-93
- **Description:** PROGRESS carried D-401 and D-406 as unblocked-but-unapplied against a commit titled
  "applied", with the register's own caution that "a commit title is a *claim* of an apply, not the
  apply". Phase 3B-1 settled it by **resource existence**: the `intellichoice-staging-alerts-info` topic
  exists in AWS with a confirmed email subscription and exactly the four predicted member alarms, with
  `sessions-completed-floor` absent from AWS entirely — exactly what the configuration test's own in-file
  note predicts — and the test's non-vacuity control also holds live. D-406's side: the NAT exists
  (`nat-07ab02d5cd28b6f72`, `CreateTime 2026-08-07`) with an active default route and
  `ManagedBy=terraform`. Independent corroboration that an apply ran that day: all three
  task-definition families registered a new revision within **3 ms** at 2026-08-18T20:20:41Z.
- **Domain:** infrastructure state / documentation currency
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:1056` (DRIFT-93);
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:399-403`, `:425`; `DEPLOYED_INFRA_STATE_EVIDENCE.md:543-553`
- **Related claim IDs:** WORK-07, WORK-08, COST-24, COST-28
- **Related decision IDs:** D-401, D-406, D-418, D-419
- **Repository evidence:** both decisions are fully present in configuration and committed before the
  disputed date (`15bb6b3`, `73e29c6`, `2e301d6`). The *document* is the only thing asserting
  "unapplied" — a repository-side statement about deployed state, exactly the class of claim that cannot
  be trusted without an AWS read.
- **Deployed/live evidence:** both applied, as enumerated. **`PROGRESS.md:155-156`'s "unapplied" is
  REFUTED.**
- **Final disposition:** `RESOLVED` — **batch B exception**
- **Justification:** a measurement, not a document going quiet. Resource existence settles
  applied-versus-unapplied, which is why the CloudTrail `CreateTopic`/`CreateNatGateway` cross-check was
  not needed; and the registration burst proves *an* apply ran on 2026-08-18, not which configuration it
  carried.
- **Remaining action:** the stale PROGRESS line is a documentation tail, carried by
  `DOC-DEPLOYED-STATE-CLAIMS`.
- **Owner type:** documentation (the tail only)
- **Reopen condition:** n/a
- **PROJECT_STATE?** no
- **Historical/archive only?** yes

---

## §5 Learning product & content

*From here on entries are written in compressed form: the same fifteen fields, one or two lines each.
Nothing is omitted; the evidence citations are the load-bearing part.*

### `WORK-40` — OPEN_DECISIONS #10's three build items are unverified as built

- **Work/Issue ID (topic key):** `WORK-40` (OPEN_DECISIONS #10). See §0.6 for the WORK-40 split.
- **Members:** E1-123
- **Description:** All five sub-items of #10 are recorded decided, but three name build work whose
  completion is unverified: the narrative modal's reused header needs a **new API field** (a wire-shape
  change, hence a decision); `clearInterventionIfPresent` missing the retry-ladder pause ~1 in 12
  staging walks was classified a harness race with a **breadcrumb** as the next step; and
  `formatDateLabel`'s date-only shift was settled as **CDT**. "Decided" is not "built".
- **Domain:** learning app / frontend
- **Original source(s):** `CLAIM_LEDGER.md:3358`; `OPEN_DECISIONS.md:334-349`; `PROGRESS.md:82`
- **Related claim IDs:** WORK-40, WORK-13, ARCH-35, WORK-14
- **Related decision IDs:** OPEN_DECISIONS #10, D-321, D-324, D-356, C9
- **Repository evidence:** E7 confirms the per-iteration breadcrumb **shipped** and stays per D-356, and
  `formatDateLabel` is settled as CDT via `buildDateLabelFormatter(timeZone)` using the server-supplied
  `org_time_zone` with a UTC fallback deliberately *not* `America/Chicago`; the narrative API field's
  status is unverified. The header calling all five decided is what stops anyone noticing.
- **Deployed/live evidence:** n/a — repo-only; the breadcrumb's three specs sit in the deferred
  Playwright lane (`PLAYWRIGHT-LANE`).
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** decided, not built — the recurring §7 defect. The fifth sub-item was **never raised**
  and is `PROSE-QUALITY` (UD-12(c)); the armed date-only shift is `DRIFT-59-DATE-SHIFT`; the chat-web
  timezone defect is `WORK-40-TZ`.
- **Remaining action:** verify or build the narrative API field; confirm the breadcrumb and
  `formatDateLabel` fixes are present at HEAD.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `DIFFICULTY-TIERS-CONFLICT` — two explicit user decisions about `difficulty_tiers` are both live

- **Work/Issue ID (topic key):** `DIFFICULTY-TIERS-CONFLICT` (§8-02; D-322 §7 versus D-341)
- **Members:** E2-30, E1-129
- **Description:** On 2026-08-14 D-322's decision table records, as a user decision "as recommended",
  **"Edit `difficulty_tiers` to match the judge"** (row 7, `DECISIONS.md:22918`). On 2026-08-15 D-341
  records the user deciding the opposite in a quoted blockquote (`:24523-24528`): "Keep the existing
  `difficulty_tiers` declarations unchanged. Do not modify the taxonomy solely because the current bank
  is thin or concentrated in one tier." D-342's supersession list names **D-322 §5, not §7**, and D-417
  §D10 fixed only OPEN_DECISIONS #7. So D-322 §7 stands unannotated and contradicts the later active
  decision, and because **both sides are explicit user decisions** the corpus's own ranking rule cannot
  break the tie. Verified verbatim at source.
- **Domain:** curriculum taxonomy / content pipeline
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:131`, `:159-167`, `:1716-1720`, `:1933-1935`;
  `CLAIM_LEDGER.md:3472-3477`, `:3332`; `DECISIONS.md:22918`, `:24519-24532`, `:24569`
- **Related claim IDs:** WORK-14, WORK-15, WORK-30, WORK-31, WORK-38
- **Related decision IDs:** D-313, D-322 §7, D-341, D-342, D-417 §D10
- **Repository evidence:** in practice **D-341 is being followed** — D-342 rests on it and D-417 §D10
  rewrote OPEN_DECISIONS to defer to it — so the likely resolution is a confirmation, not a
  re-derivation. WORK-38 records only the D-341 side and reads as settled, so a reader of §7 alone would
  never see the conflict.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(a)**
- **Justification:** only the user can say which of their two decisions governs; every automated rule in
  the supersession map is explicitly powerless here. Framed as a **one-line confirmation** ("D-341
  governs; D-322 §7 gets a dated annotation"), not an open architectural question.
- **Remaining action:** obtain the one-line confirmation, then annotate D-322 §7 with a date. Note that
  D-342's list naming §5 and not §7 may simply be an omission; confirming that is cheap.
- **Owner type:** user, then documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `PROSE-QUALITY` — the ~13% prose-defect class and the repeated context sentence have no home

- **Work/Issue ID (topic key):** `PROSE-QUALITY` (D-289 consequence + the repeated-context sentence)
- **Members:** E2-31, E7-10
- **Description:** D-289 records the user's decision to auto-approve generated content with **no
  sampling** (a 20-item-per-wave spot check was recommended and declined), and states the consequence
  precisely: "prose defects now reach students unless someone reads the bank for another reason." D-342
  parks *quantity* findings only, and whether the ~13% prose-defect class is parked under it is **not
  stated** — so a quality finding is not closed, not parked and not owned. The concrete instance:
  `rendered_question` is `context_block + "\n\n" + stem`, and the model writes the setup into both, so
  **15 of 92** items with a context block repeat the opening sentence, concentrated in new content —
  **6 of 8** in one recent batch against **9 of 84** pre-existing. No gate checks for it. OPEN_DECISIONS
  #10 is headed `✅ ALL DECIDED` while annotating this sub-item **`not raised`**, and it is absent from
  D-417's twelve answers.
- **Domain:** content quality / student-facing text (K-12 minors)
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1650-1655`, `:1726-1728`;
  `OPEN_DECISIONS.md:334`, `:347-349`; `PROGRESS.md:1567-1570`, `:12353-12354`
- **Related claim IDs:** WORK-40, WORK-14
- **Related decision IDs:** D-273, D-289, D-342, D-417
- **Repository evidence:** the 15-of-92 and 6-of-8 measurements; no preflight rule for it.
- **Deployed/live evidence:** n/a — offline content pipeline.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(c)**
- **Justification:** student-facing text for minors reaching them unsampled, under a governing decision
  (D-289) that was the user's, and SPEC §5.10.3's register makes the taste call the user's rather than
  an engineer's. Frame it as "is the prose-defect rate accepted as residual risk, or parked like the
  quantity findings?" — **not** as a request to reopen auto-approval, which the user already settled.
- **Remaining action:** the user picks: accept as residual; park-with-quantity under D-342; a one-off
  content pass on the 15; or a preflight gate rule rejecting a stem that opens with the context block's
  first sentence (which stops the source but adds a rule that can be wrong, on a pipeline
  `QUESTION_GENERATION.md` says to read before changing). Low stakes; ranks last of the genuine
  decisions. The honest cost of deferring is that #10's ✅ conceals an unasked question.
- **Owner type:** user
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D356-FAMILY` — the erasure-guard family has no completeness claim, and two entries both call themselves "the third place"

- **Work/Issue ID (topic key):** `D-356` (chain M2 / §8-05)
- **Members:** E2-37 (completeness), E2-38 (cross-document status conflict), E1-130 (§8-05),
  E2-46 (the wrong-id citation)
- **Description:** The guard design of record (D-358's `last_intervention_attempt_id` pairing plus
  D-369's evaluate-immediately-before-publish) has been applied at four call sites — D-373 porting it to
  one publisher, D-381 to another — and **both claim to be the third place**. **No entry states how many
  publishers exist and no entry claims completeness**: D-373 says "seven fixes have now gone one way
  only", D-381 then finds a further site, and whether a fifth exists is unaddressed. Separately,
  `DECISIONS.md:25322-25324` still carries `Status: ⛔ open — characterised, not fixed` (re-verified
  verbatim) while `PROGRESS.md:834` reads `✅ D-356 IS FIXED` — a **cross-document status conflict, not
  merely a stale tag** — with D-358's `Fixes: D-356` as the tiebreaker in favour of
  fixed-for-the-narrative-scheduler-only. Compounding it, `DECISIONS.md:27790` (inside D-406) and
  `PROGRESS.md:334` both cite "D-137/D-141/**D-356**" for CI-registers-then-terraform-re-registers image
  drift, where D-356 is the erasure defect and **D-357** is almost certainly meant — the same wrong id in
  two documents.
- **Domain:** learning app / study-step narrative erasure / decision-log integrity
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:184-189`, `:2024-2032`, `:2036-2037`,
  `:2046-2048`, `:2057-2065`, `:2271-2273`, `:2311`, `:2314`; `CLAIM_LEDGER.md:3491-3495`
- **Related claim IDs:** none in the ledger — §8-05 is the only §8 contradiction with **no owning claim
  block**, so a register built from §1–§7 alone would lose it entirely
- **Related decision IDs:** D-356, D-357, D-358, D-369, D-373, D-381, D-137, D-141, D-406
- **Repository evidence:** a full-file grep finds exactly one D-356 heading and 20 citations, none of
  which edit it. The "third place" numbering conflict between D-373 and D-381 is the concrete symptom
  that **nobody is counting**.
- **Deployed/live evidence:** n/a — repo-only; no live probe touched the publisher set.
- **Final disposition:** `ACTIVE_REMEDIATION`, with a `DOCUMENTATION_ONLY` member
- **Justification:** the honest close is an **enumeration of publishers that write the shared state**,
  checked against the guard — four sites were patched reactively, one at a time, with no denominator.
  That is a bounded code sweep, not a judgement. **Answering the "cleanly closed?" question for the
  D-356 family: NOT cleanly closed**, on two independent threads.
- **Remaining action:** (1) enumerate every publisher that writes the shared state and check each against
  the guard. (2) One dated status correction in `DECISIONS.md`, **scoped exactly as D-358 scoped it**
  (fixed for the narrative scheduler; family completeness still open). (3) Fix the D-137/D-141/D-356 →
  D-357 wrong-id citation in both documents, alongside (2), since both are D-356 mis-references spanning
  the same two files.
- **Owner type:** engineering (the sweep), documentation (the status and the citation)
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `REQ-39-ESTIMATED-LEVEL` — "Current estimated level" appears nowhere in either frontend

- **Work/Issue ID (topic key):** `REQ-39` (DRIFT-30 / F-15). See §0.6 for the REQ-39 split.
- **Members:** E3-30 (DRIFT-30), E4-15 (F-15)
- **Description:** SPEC prescribes a literal UI label twice — `SPEC.md:1111` as an instruction ("Do not
  treat ten questions as an absolute measure of ability. The UI should say 'Current estimated level'.")
  and `:1451` in a screen's field list. The absence is now exhaustive in the strongest available form:
  `grep -rniE "current estimated level"` over both frontend `src` trees → exit 1, **and**
  `grep -rniE "estimated"` over the same → exit 1, so the substring does not occur anywhere in either
  frontend's source in any case. What renders instead is `<h2>Mastery by skill</h2>` and a flat
  percentage with no estimate hedge (`StudentDashboardScreen.tsx:532`/`:544`/`:571`). The only
  level-shaped labels shipped are per-question difficulty (`ExamScreen.tsx:71`, `Level ${difficulty}`)
  and hint-ladder position (`InterventionScreen.tsx:262`), neither of which is the ability estimate SPEC
  wants hedged. **The deviation has no disposition in any document**, so SPEC and code disagree with
  nothing recording that the disagreement was noticed and accepted.
- **Domain:** student-facing language / SPEC conformance (non-negotiable rule 10)
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:356-365`, `:1208`;
  `LOCAL_EXECUTION_FINDINGS.md:637-662`
- **Related claim IDs:** REQ-39, REQ-40
- **Related decision IDs:** D-409 (mastery bands in `ReportView`), SPEC §5.10.2
- **Repository evidence:** as above; the bootstrap weights half passed
  (`test_mastery_bootstrap.py`, inside Batch 1's `183 passed`), and no IRT path exists.
- **Deployed/live evidence:** n/a — repo-only; the wording is absent on both HEAD and the deployed build.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(e)**
- **Justification:** rule 10 (growth-oriented, age-appropriate student-facing language) is what makes
  this more than a string, so the user's judgement is the right instrument. Two legitimate outcomes and
  no basis in the repository to pick one — and F-15's observation that **D-409's mastery bands partly
  meet the hedging intent** is the strongest argument for dispositioning rather than shipping, which
  means the user may already consider it satisfied. The 3A.5 contribution is the *exhaustiveness* of the
  absence, which removes the "you grepped for the wrong string" defence.
- **Remaining action:** ship the wording, or disposition the SPEC requirement against D-409's bands.
  Cheap either way; should not sit in the queue. Do not open a duplicate row — DRIFT-30 already exists
  with the user as owner.
- **Owner type:** user
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `IRT-UPGRADE` — the IRT/Bayesian mastery upgrade has no trigger threshold and no owning session

- **Work/Issue ID (topic key):** `IRT-UPGRADE` (REQ-39 deferred half)
- **Members:** E1-15
- **Description:** Mastery is a bootstrap weighted score that SPEC says "may later adopt IRT or Bayesian
  estimation" after enough response data. **No threshold and no owning session are recorded.** The
  bootstrap model is the shipped and adequate answer at pilot scale; no IRT path exists (only deferral
  docstrings). A neighbouring requirement in the same SPEC section — "difficulty label to be superseded
  by observed evidence" — is likewise a trigger that has not occurred: `recalibrat` returns documentation
  only, and `success_rate`/`p_value`/"observed difficulty"/`item_difficulty` return nothing outside
  tests (DRIFT-73, in `BATCH-LOW-OVERSTATEMENT`).
- **Domain:** product requirements / mastery estimation
- **Original source(s):** `CLAIM_LEDGER.md:539` — `SPEC.md:1060-1122`
- **Related claim IDs:** REQ-36, REQ-39, REQ-41, REQ-42
- **Related decision IDs:** none cited; SPEC §5.10.1–§5.10.2
- **Repository evidence:** `mastery_bootstrap.py:3-4`, `:29`, `:105-109` — the exact weights, with no
  IRT implementation.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `DEFERRED`
- **Justification:** a conditional future upgrade with no unmet obligation today; SPEC's own trigger
  ("as production data accumulates") has not occurred, and TRACEABILITY dispositions the sibling
  requirement as "a requirement whose trigger condition has not occurred".
- **Remaining action:** none. Revisit only if response volume makes it live. The genuinely checkable half
  of REQ-39 — the UI wording — is `REQ-39-ESTIMATED-LEVEL`.
- **Owner type:** none · **Reopen condition:** response volume sufficient for item-response modelling
- **PROJECT_STATE?** yes — deferred · **Historical/archive only?** no

### `ARCH-17-COMMIT-SEAM` — the checkpoint/domain commit seam is entered by routine deploys, and one seam is still open

- **Work/Issue ID (topic key):** `ARCH-17` (§7-R9 remainder)
- **Members:** E1-20
- **Description:** The LangGraph saver commits per superstep on its own pool while domain rows commit at
  dependency teardown, so a failure between the two **keeps the checkpoint and discards the rows** — and
  ECS drains tasks on every deploy, so the window is entered without a bug.
  `checkpoint_reconcile.py` fixes only the mid-finalize seam; the **mid-interrupt seam and the commit
  ordering remain open**, accepted for the pilot per §7-R9.
- **Domain:** data integrity / learning app
- **Original source(s):** `CLAIM_LEDGER.md:933` — `docs/ARCHITECTURE.md:601-609`
- **Related claim IDs:** ARCH-17, SEC-10, INT-33, WORK-24
- **Related decision IDs:** §7-R9, D-110 §3, D-123, AUD-X-07 [AUDIT_FINDINGS]
- **Repository evidence:** the reconcile module and metric exist; `checkpoint_reconcile.py:88-99` leaves
  seam (b) open. **`ARCHITECTURE.md` restates the seam without R9's expiry condition**, so a reader of
  that file alone sees an accepted design rather than a time-boxed acceptance (the expiry-text loss is
  also `RISK-R2.2-ACCEPTED-RISK-HOMES`).
- **Deployed/live evidence:** the tripwire metric carries **live data** in the deployed learning-api
  namespace and no alarm reads it — see `KPI-ALARM-FLOOR`.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** a known data-loss seam entered by routine deploys, accepted only "for the pilot",
  whose non-occurrence evidence is a counter nobody is recorded as watching. The acceptance is not real
  until someone can page on it.
- **Remaining action:** fix the commit ordering and the mid-interrupt seam, or re-accept them explicitly
  with a trippable expiry. Establish the counter's current value first: if it has moved, the acceptance
  is void by its own terms. Pair with `WORK-24-DUPLICATE-GAIN`, whose observed duplicate row is exactly
  what a re-entered finalize produces.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `WORK-24-DUPLICATE-GAIN` — one completed thread has two `learning_gain` rows and nobody chased it

- **Work/Issue ID (topic key):** `WORK-24`
- **Members:** E1-107
- **Description:** One completed staging thread (`98abc0f0…`) has **two** `learning_gain` rows for a
  single `pre_assessment_session_id` while the other eight have one — either a re-finalize legitimately
  writes a second row, or gain is computed twice for one cycle. Declared out of U7's scope and recorded
  as a carry-over rather than investigated.
- **Domain:** deterministic core (CLAUDE.md rule 2) / learning gain
- **Original source(s):** `CLAIM_LEDGER.md:3150` — `U7_CHECKPOINT_CONSOLIDATION.md:291-297`
- **Related claim IDs:** WORK-24, WORK-22, REQ-36, ARCH-17, SEC-10
- **Related decision IDs:** U7 §10, D-336
- **Repository evidence:** D-336 later diagnosed a closely related cause —
  `POST /exam/finalize` carries no `Idempotency-Key`, so a retry re-inserts; two byte-identical rows 46 s
  apart; history returned 10 summaries for 9 cycles — and closed it by measurement (staging holds "9 gain
  rows and 0 duplicate pre-assessment ids"), with the existing duplicate row deliberately left alone as
  the user's call. U7 §10 was never updated (`DOC-U7-BANNER`).
- **Deployed/live evidence:** the original observation is a staging database read; re-measuring needs
  `DB-CONTENT-VERIFY`.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** a possible correctness defect in the deterministic learning-gain service, observed
  once and never chased on its own terms. The plausible root cause is the same as `ARCH-17-COMMIT-SEAM`:
  a re-entered finalize writing a second row is exactly what the mid-finalize seam produces — and if so,
  `learning_checkpoint_repairs_total` should have moved, **which would void R9**.
- **Remaining action:** test that hypothesis first, then confirm whether D-336's fix fully covers it.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D342-PARKING` — all question-bank coverage work is parked by standing user instruction

- **Work/Issue ID (topic key):** `D-342` (chain K3)
- **Members:** E1-97 (WORK-14), E1-98 (WORK-15), E2-29 (chain K3), E1-108 (WORK-25), E1-121 (WORK-38),
  E1-110 (WORK-27)
- **Description:** D-342 is the **only heading-level supersession marker in the entire corpus**, and it
  parks a whole *class* of finding rather than a single item:
  `### D-342 — ⛔ ALL question-bank coverage work is parked. Do not reopen it.` Status: standing
  instruction from the user. Verbatim scope: "every finding of the form 'the bank is thin / a tier is
  unstocked / a skill does not span / a cell is under-filled' is parked, and stays parked until the user
  explicitly asks for new problems to be generated." Prohibitions are explicit — do not narrow
  declarations to make a gap disappear, do not open a session or spend, do not re-derive it as a new
  finding. Named scope: depth (84 of 153 cells, 189 items short, ≈$13–16, ~3.5 h), missing tiers (15 of
  96 spanning skills at one tier), thin banks (5 skills at 1–3 items), skills with no video (10 of 112
  plus 3 holding only inactive). The test is "is the fix 'write more questions'?" — if yes, cite D-342
  and stop. Volume target of record when work resumes is D-273's 5–7 per occupied tier; auto-approval
  remains D-289. Two riders: the parking **does not** cover non-quantity problems (a wrong answer key, an
  item contradicting its own judge rating, an unservable path), and it depends on one tested behaviour —
  `_closest_to_recommended` never returns empty, so an unstocked tier stays servable. Also parked here:
  `QUESTION_GENERATION.md`'s banner forbidding a generation run to close a coverage gap, and D-341's
  standing instruction to keep `difficulty_tiers` declarations unchanged. Model-diversity residual
  (WORK-27): only Haiku 4.5 and Sonnet 4.5 are actually invocable — `claude-sonnet-5` reports AVAILABLE
  and denies the call — so with Generator, Solver A and Solver B all wanting independence, two of three
  must share and Solver B runs the Generator's own model; the unmeasured cost question (does a better
  Generator lower cost per accepted item) can only be answered by a paid run, which D-342 parks.
- **Domain:** content volume / coverage
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1661-1670`, `:1701-1704`;
  `DECISIONS.md:24567-24573`; `CLAIM_LEDGER.md:3020`, `:3033`, `:3163`, `:3189`, `:3332`;
  `ROADMAP.md:2484-2507`; `QUESTION_GENERATION.md:1-20`, `:243-282`, `:403`
- **Related claim IDs:** WORK-14, WORK-15, WORK-25, WORK-27, WORK-30, WORK-31, WORK-36, WORK-37, WORK-38
- **Related decision IDs:** D-060, D-185, D-223, D-273, D-289, D-300, D-302, D-313, D-322 §5, D-341,
  D-342, D-417 §B5/§D10
- **Repository evidence:** D-342's parking premise is **executed-verified** (F-17/WORK-15): "every
  declared tier of every spanning skill is servable, driven from the real taxonomy rather than a fixture,
  with its own vacuity guard" passed — a failure would have invalidated the parking decision.
- **Deployed/live evidence:** n/a — offline content pipeline.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** an explicit standing user instruction with a stated reopen trigger and no evidence
  owed. It must **not** be re-raised: re-deriving it is the specific behaviour D-342 prohibits, and the
  same finding has been re-derived at least four times. Any Phase-4 item that reads as "coverage is thin"
  is filed against this parking, not as a new finding.
- **Remaining action:** none. Keep the two riders visible: non-quantity defects stay defects, and
  `_closest_to_recommended` non-empty is load-bearing for the whole parking and is worth verifying once.
  The depth spend itself is a member of `SPEND-AUTHORIZATION` (UD-2). The provenance fuzziness of the
  "5–7 per tier" number — D-223 never states it as a target, and D-273/D-313/D-342 render it three
  different ways — is a documentation member of `DOC-CONTENT-PIPELINE`, and the actual per-cell target
  should be confirmed **at the moment D-342 is lifted**, not before.
- **Owner type:** user (to reopen)
- **Reopen condition:** the user explicitly asks for new problems to be generated.
- **PROJECT_STATE?** yes — parked, prominently · **Historical/archive only?** no

### `VIDEO-COVERAGE-PARK` — video coverage is parked, and the figure the park was argued from was wrong by two orders of magnitude

- **Work/Issue ID (topic key):** `WORK-37` (OPEN_DECISIONS #6 / chain M4)
- **Members:** E1-120 (WORK-37), E7-6, E2-41 (chain M4)
- **Description:** Item #6 is **parked 2026-08-18 on the user's instruction** (D-417 §B5): no coverage
  expansion now, a further seeding run is the user's to schedule, and `YOUTUBE_API_KEY` remains theirs to
  provision. A live staging probe that day via a read-only `ops-task` read `TOTAL 497`,
  `BY_STATUS [('active','approved',363), ('inactive','approved',134)]`, `SKILLS_SERVABLE 102` of 112,
  `LAST_SYNCED 2026-08-15 07:39 UTC` — nothing changed since the recovery, **no current data loss**. The
  figure the item was argued from — "4 videos covering 4 of 112 skills and 1 of 33 topics" — was true on
  2026-08-13 and **wrong by two orders of magnitude** two days later, and it was the premise for a
  product recommendation to accept video intervention as effectively absent at launch. A real loss event
  occurred (182 rows wrongly deactivated on 2026-08-15 by D-326's guard reading
  `saw_whole_channel = deferred == 0`), was fixed to `covered == 0 and deferred == 0`, deployed
  `6e48084`, and run 2 reactivated them the same day. Three residual measurement gaps: D-337 §4's honest
  gap — "I captured the before *count* but not the before *set*" — means **which** of the 25 skills lost
  coverage in run 1 can never be answered; three skills hold only inactive videos; and the coverage
  baseline moves 4 → 10 → 72 → 76 → 102 across entries with the **4-vs-10 discrepancy reconciled
  nowhere**. Nothing in D-418…D-423 mentions video, YouTube or the catalog.
- **Domain:** video intervention / content catalog
- **Original source(s):** `CLAIM_LEDGER.md:3319`; `OPEN_DECISIONS.md:23-33`, `:234-270`;
  `DECISION_SUPERSESSION_MAP.md:2173-2194`; `PROGRESS.md:89-98`, `:105`; `ROADMAP.md:3232-3237`
- **Related claim IDs:** WORK-14, WORK-37, REQ-34, WORK-42
- **Related decision IDs:** OPEN_DECISIONS #6, D-031, D-046, D-207, D-305, D-314, D-326 (+ addendum),
  D-337 (+ verification), D-339, D-342, D-390, D-417 §B5
- **Repository evidence:** the D-326 guard's corrected condition is confirmed verbatim and sound, and its
  regression test targets the **computation** rather than the effect; F-17 confirms the three
  `test_sync_preflight.py` tests pinning the 182-row deactivation computation all passed. D-031 is only
  *partially* superseded by D-046, so it is not fully retired.
- **Deployed/live evidence:** the 497/363/102-of-112 read above, taken from staging on 2026-08-18.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** parked by explicit user instruction eight lines into the file, with no reopen
  condition met and nothing after D-417 touching it; the catalog is healthy at 102/112. Explicitly
  re-framed from "blocking" to "parked". Its lesson stands and is worth carrying forward: **this item is
  the corpus's best example of a stale status line justifying a product decision** — the strongest
  argument in the corpus for re-measuring before deciding — which is a documentation-hygiene finding, not
  an open decision.
- **Remaining action:** none. The residual wording tension ("parked, not blocking" versus PROGRESS's
  "still blocked on the YouTube key") and the two entries still asserting the 4-video figure (D-314 at
  `:22375` and D-322 §6 at `:22941`, both left unannotated by D-417 §B5) are documentation members of
  `BATCH-LOW-STALE-STATUS` and `DOC-DECISION-LOG-CORRECTIONS`. The 10 uncovered skills are a **content**
  question about the pinned channel — D-337 establishes no further run changes them.
- **Owner type:** user (a run and the API key)
- **Reopen condition:** the user schedules a further seeding run and provisions `YOUTUBE_API_KEY`.
- **PROJECT_STATE?** yes — parked · **Historical/archive only?** no

### `WORK-12-BANNER` — learning-web's disconnect-banner condition is untested and carries two live statuses

- **Work/Issue ID (topic key):** `WORK-12` (DRIFT-44 / F-14)
- **Members:** E3-44 (DRIFT-44), E4-14 (F-14), E1-95 (WORK-12), E2-21 (chain H4)
- **Description:** The gap is confirmed and one-directional. learning-web: `Test Files 4 passed (4) /
  Tests 26 passed (26)`, enumerated — `masteryBands` (7), `stream.test.ts` liveness (6),
  `attendanceLabels` (8), `ConnectingPanel` (5) — and **none asserts on a rendered banner or a
  `streamState` value**; the only grep hit is prose inside a test *name* (`stream.test.ts:148`), and no
  Playwright spec exists (`ls e2e/tests/learning/ | grep -i disconnect` → exit 1). chat-web, for the
  **same user-visible failure**: `Test Files 5 passed (5) / Tests 49 passed (49)`, including **six**
  dedicated `ChatScreen.test.tsx` assertions in both directions (banner appears on error / does not
  appear while connecting / does not appear while open / does not steal the alert role; connection dot
  reads idle before any turn / follows real stream state) **plus**
  `e2e/tests/chat/stream-disconnect-visible.spec.ts`. So the asymmetry is quantified: 6 assertions + 1
  spec versus 0 + 0. The disagreement is about **status**: `apps/learning-web/src/App.tsx:958-960` reads
  "This condition is deliberately untested, and that is a decision rather than an oversight (D-417 /
  C7). Do not re-file it as missing coverage", while `docs/PROGRESS.md:107-117` carries it as an open
  carry-over after W21. Both are live and unretracted. D-414 also deliberately leaves it untested, on the
  reasoning that "extracting the banner JSX into a component would move the markup and leave the
  condition untested" — recording the D-347 two-frontends-drift defect shape as **named, not closed**.
- **Domain:** testing coverage asymmetry / documentation conflict
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:515-524`;
  `LOCAL_EXECUTION_FINDINGS.md:597-633`; `LOCAL_EXECUTION_EVIDENCE.md:826`; `CLAIM_LEDGER.md:2994`;
  `DECISION_SUPERSESSION_MAP.md:1391-1393`, `:1402-1409`
- **Related claim IDs:** WORK-12, WORK-43, TEST-21
- **Related decision IDs:** D-347, D-403, D-405, D-413, D-414, D-417 §C7, W20, W21
- **Repository evidence:** `App.tsx:947-984` (the condition is `session.streamState === "error"` inline
  in render logic, so testing it means mocking `useLearningSession`; W21's one working extraction,
  `ConnectingPanel`, does not apply because its condition *is* its lifetime whereas the banner's
  condition is data). The in-code "deliberately untested" note is **accurate as to state**.
- **Deployed/live evidence:** n/a — repo-only; the absent spec cannot run anywhere.
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** the banner-condition test is owed regardless of which status line wins — the
  approach is already reasoned (mock the hook, do not extract) and the chat-side equivalent is done
  (W20/D-414), so this is exactly the asymmetric half D-405 was chosen to prevent, still present. The
  documentary status conflict is reconciled by **reading D-417/C7's own scope** rather than by assuming
  the code comment wins; F-14 is explicit that no command can settle a documentary conflict, and the
  quantified asymmetry strengthens the case that the exclusion was scope drift rather than a considered
  decision. Do not let the green suite read as resolving it.
- **Remaining action:** write the banner-condition test by mocking `useLearningSession`; reconcile the
  two status lines by reading D-417/C7's scope and retracting the loser.
- **Owner type:** engineering, with a documentation tail
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `WORK-44-DECIDED-NOT-BUILT` — two closed OPEN_DECISIONS items are decided but unverified as built

- **Work/Issue ID (topic key):** `WORK-44` (OPEN_DECISIONS #2/#3/#9/#13)
- **Members:** E1-127
- **Description:** Four items closed without contradicting their recommendations, but two are "decided,
  not built". **#3** URL routing was decided as `react-router` and is a **named prerequisite for
  §5.1.2's first-visit disclosures** — installation and routing are unverified. **#9** dependency PRs
  were decided as a batch merge with a standing rule (patch/minor automatic, majors read individually),
  the item's own count corrected from 7 to **26**, and whether the backlog is cleared is unverified
  (GitHub state — `ARCH-33-CI-GATE`). **#2** the client-error sink is built on both apps (learning
  D-328, chat D-372), with chat unable to have an authenticated endpoint because its primary caller is
  anonymous, so the gate became a rate limit — per `sub` with a token and **a single shared app-wide
  bucket for anonymous reports**, whose weakness is stated in the router docstring ("two unrelated
  visitors competing for one allowance"). **#13** `downloadIcs`'s DOM contract was closed by D-399 after
  two remedies that did not close it.
- **Domain:** frontend / project hygiene
- **Original source(s):** `CLAIM_LEDGER.md:3410`; `OPEN_DECISIONS.md:102-144`, `:148-167`, `:321-330`,
  `:452-543`
- **Related claim IDs:** WORK-43, WORK-44, TEST-25, REQ-25, COST-17
- **Related decision IDs:** OPEN_DECISIONS #2/#3/#9/#13, D-315, D-328, D-352, D-372, D-391, D-397,
  D-399, SPEC §5.19.1, §5.1.2
- **Repository evidence:** both `/client-errors` routes and the `.ics` DOM-contract spec exist; #3's and
  #9's states are the unverified ones.
- **Deployed/live evidence:** n/a for #3; #9 is GitHub state.
- **Final disposition:** `ACTIVE_IMPLEMENTATION` (for #3 and #9); #2 and #13 are `RESOLVED` and recorded
  in §10.3
- **Justification:** the ledger states plainly that "'decided' is not 'built'" for both, and #3 being an
  unverified prerequisite adds a **fourth blocker** to the first-visit-notice chain
  (`DISCLOSURES-LEGAL`).
- **Remaining action:** verify `react-router` is installed and routing; run `gh pr list` for the 26-PR
  backlog. #2's single shared anonymous bucket is a documented live weakness of the same
  insufficient-stopgap shape as `SEC-18-WAF` — record it in the residual-risk set rather than fixing it
  here.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D329-PHANTOM` — personalized hints ran dead in production, and the detection gap is unchanged

- **Work/Issue ID (topic key):** `D-329` (phantom; chain M6)
- **Members:** E2-27
- **Description:** No `## D-329` or `### D-329` heading exists; D-329 lives as a `####` sub-heading inside
  D-330 (`DECISIONS.md:23582`) plus nine citations, and **D-334's `Follows: D-329` is a dangling
  reference**. The citations establish the subject — personalized hints failing silently,
  `background_hint_personalization_failed` × **117 in 48 hours**, fixed in `0deb31c` around 2026-08-14 —
  and, more importantly, two things still open: a carry-over "**still unproven: that a student sees the
  personalized hint**" (D-334, `:23943`), and "**D-329's detection gap, unchanged since the incident**"
  (a sub-heading at `:26276`, i.e. still open at D-381's date). D-334 §5 also retracts D-329's own
  history claim as measured false — a regression, not an original defect. The same class of silent
  swallow recurs at D-344 and D-350 by the map's own citations, so it is a **repeating shape**, not a
  one-off.
- **Domain:** learning app / personalized hints / observability
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:316-351` (esp. `:326-340`, `:342-351`)
- **Related claim IDs:** none owning; adjacent to COST-22 (silent instruments)
- **Related decision IDs:** D-329, D-330, D-334, D-344, D-350, D-381
- **Repository evidence:** the fix commit landed; the detection gap for silently-swallowed background
  failures is unaddressed, and nothing proves end-to-end delivery to a student.
- **Deployed/live evidence:** `BackgroundTaskFailures` is one of the 12 alarmed app-plumbing metrics, so
  a *failure count* is watched; what is not watched is whether the personalized hint reaches a student.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** two named open threads on a feature that once ran dead in production emitting 117
  errors in 48 hours. This is work, not a judgement. Highest-substance phantom of the six.
- **Remaining action:** (1) close the detection gap for silently-swallowed background failures — the
  higher-value half, and generalisable across D-344/D-350. (2) Prove end-to-end that a student sees the
  personalized hint. (3) Write the missing D-329 entry, or record its absence at each citation site
  (`RISK-GROUP-DECISIONS-HYGIENE`).
- **Owner type:** engineering, with a documentation tail
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D141-TRIM` — a recommendation reverses a user-approved action and no later user decision restates it

- **Work/Issue ID (topic key):** `D-141 §5` (chain F4)
- **Members:** E2-5
- **Description:** D-141 §5 says "Recommendation: do not trim, and this supersedes the approved action" —
  a **recommendation overriding a prior explicit user approval**. Under the corpus's own ranking rule
  (explicit user decisions outrank recommendations, including later ones) a recommendation cannot
  supersede a user approval, and the map records that no later user decision in the chain restates the
  disposition. So the action's true status is indeterminate.
- **Domain:** launch gate / scheduled jobs (memory-consolidation trimming)
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:596-598`, `:640-643`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-141 §5, D-148
- **Repository evidence:** the trim setting's current state follows the recommendation in practice; the
  record does not settle whether that is authorised.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(b)**
- **Justification:** a documented user approval currently overridden by an assistant recommendation —
  precisely the shape the corpus's own ranking rule refuses to resolve automatically. Low blast radius (a
  trim setting), but it is one of only **two** places in the whole map where a recommendation is asserted
  to beat a user decision; the other is D-313 versus D-341 (`DIFFICULTY-TIERS-CONFLICT`).
- **Remaining action:** one line confirming which stands — the approved trim, or the recommendation that
  replaced it.
- **Owner type:** user
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `DRIFT-49-MODEL-ROSTER` — `.env.example` configures the mirror image of the documented model roster

- **Work/Issue ID (topic key):** `DRIFT-49` (WORK-27, WORK-26)
- **Members:** E3-49
- **Description:** The structural halves hold — two invocable models, the pigeonhole that two of three
  roles must share, and a fail-closed preflight comparing
  `underlying_model(solver_a) != underlying_model(solver_b)` ("their agreement would be one opinion
  counted twice"), with both tests present. But the slot→role mapping means `.env.example` configures
  **Generator = Haiku 4.5, Solver A = Haiku 4.5, Solver B = Sonnet 4.5** — Generator sharing with
  **Solver A**, the *mirror* of the documented roster — so the "better Generator" gain the roster claims
  is not what the example configures. Separately, `settings.py` defaults all four slots to
  `anthropic.claude-sonnet-5`, the id D-273's 1-token probe measured as **AccessDenied**, which also
  collapses all four slots onto one model the preflight would reject.
- **Domain:** content pipeline / configuration
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:570-579`, `:1208` (§3.2 row 20)
- **Related claim IDs:** WORK-26, WORK-27
- **Related decision IDs:** D-273
- **Repository evidence:** `.env.example:10-39`; `packages/curriculum/src/.../settings.py:16-33`;
  `ai_pipeline.py:967-968`, `:1247`, `:1329`, `:1911`, `:1923`, `:1970`; `pipeline_cli.py:732-745`;
  `QUESTION_GENERATION.md:243-282`. F-17 confirms the preflight is fail-closed and executed.
- **Deployed/live evidence:** n/a — offline pipeline. **The operative `.env` is forbidden to read and
  stayed unread**, so the operative roster is unresolvable in 3A and was not resolvable by 3B either.
- **Final disposition:** `UNKNOWN`
- **Justification:** which roster is intended cannot be determined from any readable artifact, and the
  user is the only available evidence source. Two distinct defects sit inside it: a mirrored roster
  (design intent unclear) and placeholder defaults that fail into an opaque circuit breaker.
- **Remaining action:** **Named resolution step:** check `DECISIONS.md` and git history for the intended
  roster; if that does not settle it, ask the user. The second defect — the `claude-sonnet-5` defaults —
  is fixable **without any decision** and should not wait on the first.
- **Owner type:** engineering (the defaults), user (the roster intent)
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `K5-HINT-INSTRUMENTS` — the hint-instrument chain's terminal state is composite and one antecedent was never read

- **Work/Issue ID (topic key):** `K5` (chain K5)
- **Members:** E2-35
- **Description:** The active state is assembled from five entries (D-201's single-leak rule per D-250;
  `hint_reveals_answer` demoted to a flag per D-246; `hint_quality_score` out of triage ordering per
  D-249; the two-reviewer union with missing-verdict-blocks per D-256; all inside D-251's
  falsification-only frame), with **D-271 as the content state of record — 0 of 130 unambiguous
  defects**. Three residuals: **D-264 was not read** in that pass, so its status tag and any in-place
  correction are unverified; D-269's inline correction covers only the export claim, leaving its
  D-264-inherited "no solution-step repair reaches that" conclusion refuted by D-271 but unannotated at
  both D-269 and D-264, with **D-270 adding a third partly-overlapping account** of the same finding;
  and D-246 now reads as operative design although D-250 deleted half of what it built.
- **Domain:** hint and solution quality instruments
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1894-1898`, `:1910-1924`
- **Related claim IDs:** WORK-28, WORK-29
- **Related decision IDs:** D-201, D-243, D-245, D-246, D-248, D-249, D-250, D-251, D-255, D-256,
  D-264, D-269, D-270, D-271
- **Repository evidence:** the composite is coherent in code; D-251's design rule bounds any future
  claim — "the five checks can only ever **disqualify** the instrument. Surviving all five means *not yet
  falsified*, never *validated*."
- **Deployed/live evidence:** n/a — offline pipeline.
- **Final disposition:** `UNKNOWN`
- **Justification:** the map's confidence is HIGH on what the entries say and the composite is coherent,
  but one antecedent's current annotation state was never verified and three overlapping accounts of one
  finding coexist. UNKNOWN is not converted silently.
- **Remaining action:** **Named resolution step:** one targeted read of D-264 (its status tag and any
  in-place correction). That single read converts this entry to `DOCUMENTATION_ONLY`. Also check that
  `docs/HINT_SOLUTION_REVIEW.md` does not present D-251's falsification frame as validation
  (`DOC-HINT-SOLUTION-REVIEW`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D288-D317-CLOSURE` — whether D-317 resolves D-288's open product defect is asserted, not stated

- **Work/Issue ID (topic key):** `D-288` (chain M3)
- **Members:** E2-40
- **Description:** D-288's status still reads `⏸ partial — band walks green, one product defect open`,
  and D-317 **reframes** that defect as a client-side position race **without stating closure**. D-288's
  tag was never touched, and its "one product defect" is not named in the status line, so confirming that
  D-317 closes *that* one requires reading both bodies. The map's confidence on "D-288 fully resolved by
  D-317" is **MEDIUM**. D-317's own `What is not yet known` section is additionally contradicted by its
  immediately-following addendum, so a reader who stops at the section boundary gets the wrong state.
- **Domain:** exam position / decision-log hygiene
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:2103-2108`, `:2128-2134`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-288, D-317 (+ addendum)
- **Repository evidence:** the map deliberately stopped rather than infer closure.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `UNKNOWN`
- **Justification:** resolvable by reading, but not resolved; inferring closure is exactly what the audit
  refuses to do.
- **Remaining action:** **Named resolution step:** read both bodies (D-288 and D-317 plus its addendum)
  and determine whether the named product defect is closed. **Caution:** D-288 carries three further
  substantive findings the map says are still live — SymPy in student text, 17-of-33 unopenable topics,
  the calculus 503 tie-break, and the never-exercised ladder — so "D-288 resolved" must not be read as
  retiring those.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `DOC-CONTENT-PIPELINE` — content-pipeline documents that describe superseded state

- **Work/Issue ID (topic key):** `DOC-CONTENT-PIPELINE`
- **Members:** E3-31 (DRIFT-31), E3-48 (DRIFT-48), E3-51 (DRIFT-51), E3-52 (DRIFT-52),
  E1-109 (WORK-26), E1-113 (WORK-30), E2-33 (the volume-target provenance)
- **Description:** Six document defects on one surface. **(a) DRIFT-48 / WORK-26:**
  `QUESTION_GENERATION.md:449` still ends in the imperative with "Next: … stop using Mistral Large 3 as
  Generator and obtain additional model access" — superseded by the 2026-08-11 Anthropic-only roster at
  `:243-282`, and **no Mistral model id is configured anywhere** (a repo-wide grep across
  `.py`/`.yaml`/`.yml`/`.toml`/`.example`/`.tf`/`.json` yields five non-configuration hits: three prose
  comments citing `mistral-large-3` as historical evidence for a *rejected* behaviour, and two adapter
  test assertions). The harm is **placement**: a superseded plan left in the imperative at the end of the
  document, where a reader looks for what to do next. **(b) DRIFT-51 / WORK-30:** `CONTENT_COVERAGE.md:96`
  still shows family B as "⚠️ needs the Phase R answer-model router" and `:165` still routes it to Phase
  R as future work, although the router landed the same day and is explicitly fail-closed ("a form no
  model claims is an error, never a skip"), with four of five named models real `DerivedAnswer` kinds
  plus `value`, both-directions tests, and `place_value_compare` re-authored at 15/15.
  **(c) DRIFT-52:** the same file records 4 of 12 grade bands populated where
  `grade_topic_mapping.yaml` now populates **seven**, and treats family C as gated where 40 items carry a
  non-null `figure_spec` across a bank of 958 with two figure checks wired into `validate_authored_item`.
  **(d) DRIFT-31:** `validate_authored_item` runs eleven named checks, six of which are not in SPEC at
  all, while **four SPEC bullets have no implementing deterministic check inside the gate** — no division
  by zero, numeric range (the only range check is on *metadata*), semantic topic/skill alignment, and no
  duplicate question (absent from the gate, implemented one layer up with a cosine threshold whose own
  comment calls it "a placeholder pending real-embedding calibration") — with two further checks
  materially narrower than their bullets and one self-described as "a rough proxy only". Fifteen of
  nineteen §5.29-adjacent rows remain unsampled. **(e)** The volume target's provenance is fuzzy: D-223
  never states 5–7 as a target, and D-273/D-313/D-342 render it three different ways.
- **Domain:** content pipeline / documentation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:367-376`, `:559-568`, `:592-601`, `:603-612`;
  `CLAIM_LEDGER.md:3176`, `:3228`; `DECISION_SUPERSESSION_MAP.md:1632-1642`, `:1721-1725`
- **Related claim IDs:** REQ-41, REQ-42, TEST-11, WORK-14, WORK-15, WORK-26, WORK-27, WORK-30, WORK-31
- **Related decision IDs:** D-194, D-223, D-226, D-249, D-273, D-286, D-313, D-342
- **Repository evidence:** as cited per member; F-17 confirms the router's both-directions tests and
  WORK-15's parking premise by execution.
- **Deployed/live evidence:** n/a — offline pipeline. Two coverage limitations must travel with the
  edits: `CONTENT_COVERAGE.md` is **generated** by `scripts/build_content_coverage.py` over a live
  database and **nothing regenerates it**, and its census figures were **never re-derived in any phase**
  (the histogram re-derivation was blocked by lane, not by environment) — so "stale in three places" is a
  floor, not a ceiling.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** DRIFT-48 is the cheapest fix in the MEDIUM band and grades MEDIUM only because it is
  reader-facing and actionable. DRIFT-51/52 plus DRIFT-96 all trace to one missing process step, so the
  generalisable fix is **process** (regenerate the document as part of the pipeline change), not three
  edits. DRIFT-31 is dispositioned DOCUMENTATION_ONLY as adjudicated but **flagged**: the interesting
  finding is not the count but the *direction of delegation* — four SPEC bullets and two narrowed checks
  all resolve to "the LLM judge does this", which is in tension with non-negotiable rule 2 for a content
  gate feeding minors' assessments. D-342's parking lowers urgency.
- **Remaining action:** the edits, plus one process recommendation for `CONTENT_COVERAGE.md`
  regeneration, plus an explicit ruling on DRIFT-31's delegation direction if the user wants one rather
  than an edit. Confirm the per-cell volume target **at the moment D-342 is lifted**, not before.
- **Owner type:** documentation; engineering for the regeneration step
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-HINT-SOLUTION-REVIEW` — the document under-reports its own completed work, in the direction that invites re-buying evidence

- **Work/Issue ID (topic key):** `LB-01` (DRIFT-50 / WORK-28)
- **Members:** E6-1 (LB-01), E3-50 (DRIFT-50), E1-111 (WORK-28)
- **Description:** `HINT_SOLUTION_REVIEW.md` §8 leaves steps 4 and 7 unticked (`:527`, `:530`) and three
  lines (`:27`, `:452`, `:463-464`) still assert `_HINT_QUALITY_REJECT_BELOW` (`< 2`) "has never been
  measured" / "stays until measured". **Both steps completed 2026-08-10**: step 4 = D-254
  (`DECISIONS.md:18463-18478`, 29.1¢, 82 Haiku 4.5 calls, all four pre-registered metrics survived) and
  step 7 = D-252 (`:18376`, `:18403-18405`, 126 readings, **minimum observed 2, floor never fired**), with
  the same conclusion carried in code at `ai_pipeline.py:821-827`. Its header also says "the loop around
  them is not built" while naming `review_loop.py` in the same fifteen lines, and three in-code
  docstrings are stale the same way (`review_loop.py:3` "**Nothing calls this.**";
  `review_panel.py:5-6` "the repair loop … not built"; `hint_solution_repair.py:3`) — although
  `scripts/repair_authored_solutions.py:211` **is** `run_review_loop`'s non-test caller (D-262). What
  still holds: **no pipeline caller exists** (grep against `ai_pipeline.py` and `pipeline_cli.py` returns
  zero in both), steps 5 and 6 are genuinely open, and §9's four out-of-scope items are unchanged. Two
  adjacent drifts: `:452`'s line cite is stale (the constant is now `ai_pipeline.py:834`, its only gate
  `:2005`), and the front page describes a pre-pilot world — `:3` "the loop around them is not built"
  versus `:9-10` "`review_loop.py` implement[s] … the bounded loop" six lines apart; `:378` reviewer C
  "measured" versus `:440` "reviewer C does not yet exist"; and **zero grep hits for any D-262+ id**
  although D-262–D-269 all landed. Five required document changes are enumerated at
  `LIVE_BEHAVIOR_FINDINGS.md:142-151`.
- **Domain:** curriculum question-quality pipeline / ops-doc accuracy
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:65-153`; `LIVE_BEHAVIOR_EVIDENCE.md:118-130`;
  `REPOSITORY_DRIFT_REGISTER.md:581-590`; `CLAIM_LEDGER.md:3202`;
  `DOCUMENTATION_RISK_REGISTER.md:255-257` (R4.6), `:305-309` (R5.6); `DOCUMENT_INVENTORY.md:600-608`
- **Related claim IDs:** WORK-28, WORK-29, REQ-32
- **Related decision IDs:** D-240, D-249, D-251, D-252, D-254, D-259, D-260, D-262
- **Repository evidence:** verified against HEAD `344f016`; all three modules exist and are implemented,
  with `run_review_loop` calling `review_panel` and returning `LoopOutcome("accepted", …)` on unanimity.
- **Deployed/live evidence:** n/a — offline content pipeline, no deployed surface.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the highest-consequence finding of Phase 3B-2 **because it points the wrong way** —
  as written it invites re-buying ~29¢ of already-paid evidence, or treating a measured floor as an open
  launch risk. It is also the register's clearest **under-**reporting case, where most entries
  over-report. Three independent readers found the same defect from three directions (register,
  inventory, live probe), which is the strongest signal in the extraction.
- **Remaining action:** the five enumerated edits, plus the correct wording "built but uncalled" for the
  loop. **Split note:** fix item 5 edits **source docstrings**, not documents, so if the canonical
  migration is documents-only that item is `ACTIVE_REMEDIATION` and belongs with engineering. The file
  **cannot be archived** (its §3/§4.5b/§4.6/§6/§9 rules exist nowhere else) and is the highest
  reconciliation priority of the ops documents. Note also that it is cited as normative by **seven source
  files and two scripts** while CLAUDE.md calls it "the **planned** design" — code treats as law a
  document the index calls unbuilt. Whether to wire the loop into the pipeline is a separate question
  neither phase asked, and the pipeline is parked (D-342).
- **Owner type:** documentation, with one engineering item (the docstrings)
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, at the top of it
- **Historical/archive only?** no

### `DOC-U7-BANNER` — three sections of one document still pose questions D-333 answered and shipped

- **Work/Issue ID (topic key):** `DRIFT-47` (WORK-22 / WORK-20 / WORK-24)
- **Members:** E3-47 (DRIFT-47), E1-103 (WORK-20)
- **Description:** No follow-up was scheduled for U7 because the recommendation was adopted directly one
  day later: D-333 records the user's decision in their own words with a three-window table, and PROGRESS
  confirms "✅ U7 IS COMPLETE (2026-08-15, D-333)", merged (`8c86685`, #274) and deployed. **The U7
  document itself was never updated** — its Status line still reads "design review, measured. Steps 1–2
  of §8 are done; no deletion code written", and §9's four items are still posed as open questions with
  no completion banner, so a reader taking §9 at face value would re-open a settled policy decision.
  §9.2 specifically asks whether `learning_sessions` gets built; it **is** built, migrated (in the live
  chain), modelled, and has a **scheduled** producer — and the earlier drop migration is not a later
  reversal but a revision of a 2026-07-15 revision that dropped the S5 stand-in. §10 still records the
  duplicate `learning_gain` observation as un-investigated four days after D-336 diagnosed and closed it
  by measurement.
- **Domain:** documentation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:548-557`, `:1067` (DRIFT-94), `:1078`
  (DRIFT-95); `CLAIM_LEDGER.md:3098`; `U7_CHECKPOINT_CONSOLIDATION.md:1-5`, `:52-63`, `:265-279`,
  `:281-292`; `DECISIONS.md:23837-23860`; `PROGRESS.md:1238-1247`
- **Related claim IDs:** WORK-19, WORK-20, WORK-22, WORK-24
- **Related decision IDs:** D-331, D-332, D-333, D-336
- **Repository evidence:** F-17's WORK-03 replay independently confirms the migration chain — 37
  migrations base-to-head in one run, single head `8509c0486d8d`, `packages/db/tests/` `83 passed`.
  ARCH-05's dependency corroborates: `session-consolidate` projects into `learning_sessions` and the
  schedule list says it runs.
- **Deployed/live evidence:** the `session-consolidate` schedule exists in AWS. Whether migration
  `6538a95bc990` is **applied to the deployed database** was routed to forbidden — the repository half is
  closed and the deployed half is not (`DB-CONTENT-VERIFY`).
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** DRIFT-47, DRIFT-94 and DRIFT-95 are the **same document needing the same one-line
  banner**; consolidate the remediation and keep the coverage rows distinct. The open questions are
  stale, not open — one migration grep closes §9.2.
- **Remaining action:** add a completion banner pointing at D-333, or mark the document a historical
  working note; annotate §9.2 and §10 as answered. The genuinely open retention decisions are
  `RETENTION-CLUSTER` (UD-7) and the sizing prerequisite is `WORK-35-LEDGER`. The document also needs an
  as-of banner and a date on every self-expiring claim (`DOC-SNAPSHOT-BANNERS`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DRIFT-72-OUTCOME-ENUM` — a seventh interim outcome label is persisted in an unconstrained column

- **Work/Issue ID (topic key):** `DRIFT-72` (REQ-31, REQ-33) — batch C exception
- **Members:** E3-56:DRIFT-72
- **Description:** A seventh interim outcome label (`INCORRECT = "incorrect"  # interim: wrong answer,
  skill line still open`) is persisted beside the six terminal ones, in a **nullable unconstrained
  `String`** column documented as "one of the six §5.11.7" — so the taxonomy is Python-enforced only, not
  a database enum. The four-step ladder is as claimed. Additive and documented in code.
- **Domain:** learning product / data model
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:825` (DRIFT-72)
- **Related claim IDs:** REQ-31, REQ-33
- **Related decision IDs:** none cited; SPEC §5.11.7
- **Repository evidence:** as described; the column's docstring is the narrower statement.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `OBSERVATION_ONLY` — **batch C exception**
- **Justification:** the taxonomy being Python-enforced rather than a database enum is a **design
  observation**, not a documented promise being broken — which is why it leaves batch C's
  DOCUMENTATION_ONLY default.
- **Remaining action:** none. Record it so a future reader does not treat the column as constrained.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `DRIFT-59-DATE-SHIFT` — the date-only back-a-day shift is still armed under an "ALL DECIDED" heading

- **Work/Issue ID (topic key):** `DRIFT-59` (WORK-40) — batch G exception
- **Members:** E3-60:DRIFT-59
- **Description:** OPEN_DECISIONS #10 is headed "ALL DECIDED" and records a `formatDateLabel` CDT fix
  that **names no symbol that exists**: the actual formatter is `buildDateLabelFormatter(timeZone)` using
  the **server-supplied** `org_time_zone` with a fallback of `UTC` that is "deliberately **not**
  `America/Chicago`". The zone policy **is** implemented via D-324's design, so #10's wording simply
  predates the mechanism. **The residual is not a wording defect:** the date-only back-a-day shift — a
  date-only string parsed as UTC midnight and then rendered in the org zone — **remains unmitigated,
  still armed**, under a heading that reads ALL DECIDED. Two of #10's three build items are confirmed
  built (`stage_narrative_stage` on five response models consumed by `StageTransitionScreen`; the
  ladder-pause breadcrumb sink, "**Instrument only — this function's behaviour is deliberately
  unchanged**", passed by three specs).
- **Domain:** frontend correctness / learning app
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:682` (DRIFT-59), `:686`
- **Related claim IDs:** WORK-40
- **Related decision IDs:** D-324, OPEN_DECISIONS #10
- **Repository evidence:** `buildDateLabelFormatter` is **module-private** (no exported symbol), so the
  fix is not unit-testable as written, and its only coverage is the deferred Playwright spec
  `e2e/tests/learning/dashboard-chart-labels.spec.ts`.
- **Deployed/live evidence:** n/a — repo-only; the guarding spec sits in `PLAYWRIGHT-LANE`.
- **Final disposition:** `ACTIVE_IMPLEMENTATION` — **batch G exception**
- **Justification:** an armed correctness edge case, not a document defect, and "ALL DECIDED" headings
  are a rot hazard worth a convention note. The **chat-web** half of the same D-324 family is a separate
  and larger finding (`WORK-40-TZ`) and must not be absorbed here.
- **Remaining action:** fix the date-only shift; export or relocate `buildDateLabelFormatter` so it is
  unit-testable, which closes both this untestability and the chat-web gap at once.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

---

## §6 Chat/RAG & escalation

### `WORK-40-TZ` — chat-web renders calendar-approval times in the viewer's browser locale

- **Work/Issue ID (topic key):** `WORK-40-TZ` (F-02; defect class D-324). See §0.6 for the WORK-40 split.
- **Members:** E4-2 (F-02)
- **Description:** **New finding, owned by no 3A entry.** `apps/chat-web/src/screens/CalendarActionModal.tsx:11-15`
  `formatDateTime` calls `date.toLocaleString()` with **no `timeZone` and no locale argument**, so calendar
  times render in whatever zone and format the viewer's browser is set to. This is exactly the defect D-324
  fixed in learning-web: the cross-app grep for `formatDateLabel|buildDateLabelFormatter` returns three
  hits, all in `apps/learning-web/src/screens/StudentDashboardScreen.tsx` (`:79`, `:220`, `:427`) and
  **zero in `apps/chat-web/src`** — the fix never crossed the app boundary. The org timezone is available
  and plumbed: `ORG_TIMEZONE`, `ORG_TIME_CONVENTION` and `ORG_TIME_CONFIRMED` are set identically into
  **both** task definitions (`staging/main.tf:497-499`, `:582-584`) and read by one shared module,
  `packages/shared/src/intellichoice_shared/org_time.py`. chat-web simply does not use it here.
- **Domain:** frontend correctness / human-approval integrity (non-negotiable rule 4)
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:188-238`; `LOCAL_EXECUTION_EVIDENCE.md:736`,
  `:738`; cross-referenced at `REPOSITORY_DRIFT_REGISTER.md:686` for the *different* still-armed residual
  in the same family
- **Related claim IDs:** WORK-40, ARCH-35 (the org-time plumbing)
- **Related decision IDs:** D-324, D-417 §C7
- **Repository evidence:** as above; verified absent from `REPOSITORY_DRIFT_REGISTER.md` by grep for
  `CalendarActionModal` (only the 3A.5 documents hit), confirming novelty. **The learning-web fix it
  should reuse is module-private** (`grep -n "export function buildDateLabelFormatter"` → exit 1), so
  porting it requires exporting or relocating it; and that fix has **no unit coverage** — its only guard
  is the deferred Playwright spec `e2e/tests/learning/dashboard-chart-labels.spec.ts`, and the four
  executed learning-web test files cover `masteryBands`, stream liveness, `attendanceLabels` and
  `ConnectingPanel`, none touching it. So a fix in either app today lands with no locally-runnable test
  asserting it.
- **Deployed/live evidence:** not deployed as a fix: the defect is present on both HEAD and
  `gha-44a12dfc9549`. Its severity depends on whether chat-web's calendar approval is reachable by parents
  or managers in other zones — worth confirming against the deployed build rather than assuming.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** a located, reproducible correctness defect on a **human-approval surface** — the
  times a human reads before approving an external action under rule 4 — with the fix pattern already
  existing in the sibling app and an in-repository precedent (D-324). Nothing about it requires a
  judgement. It is the only genuinely *new implementation* defect Phase 3A.5 produced and it must be
  carried on its own merits, **not** absorbed as "part of DRIFT-59".
- **Remaining action:** export or relocate `buildDateLabelFormatter` to a shared module — which closes
  both the chat-web gap and the learning-web untestability at once — then fix `CalendarActionModal` and
  land a unit test with it, or the defect repeats. The separate armed date-only shift is
  `DRIFT-59-DATE-SHIFT`.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `WORK-01-SCOPE-GUARD` — the `scope_guard`/retrieval overlap is specified, measured and not built

- **Work/Issue ID (topic key):** `WORK-01` (B6; WORK-18 measurement)
- **Members:** E1-84 (WORK-01), E7-9, E1-101 (WORK-18)
- **Description:** A grounded turn makes **four sequential Bedrock round trips**, written down nowhere
  until W27: `RAG_ANSWER` **4124 ms (~42%)**, retrieval **3411 ms (~35%)**, `scope_guard`
  **2129 ms (~22%)**, `create_embedding` **124 ms (~1.3%)** — measured on staging over 12 grounded turns
  (two `VUS=1 ITERATIONS=6` k6 runs, X-Ray spans by name), with k6 `http_req_duration` p95 **13.1 s**.
  The 1.3% figure **cancelled an optimisation the author proposed and the user had already approved** (the
  embedding was pitched at ~2.5 s). The replacement — overlap `scope_guard` with retrieval — buys median
  ~9.6 s → **~7.5 s (~22%)** with **no prompt changed and therefore no quality delta**, verified against
  three code facts: `standalone_query` is written by `resolve_role` (`nodes.py:314`) *before*
  `scope_guard`; `QAState` holds chunk **ids not bodies**, so the answer node must re-fetch by
  `retrieved_chunk_ids`; and **every non-`document_qa` turn pays one wasted rerank** (a fraction of a
  cent, and the turn mix cannot be measured honestly today because staging's only traffic is a 100%
  `document_qa` load script). D-423 left it **specified rather than half-built** and says "nothing about
  it needs re-deriving".
- **Domain:** chat RAG latency
- **Original source(s):** `CLAIM_LEDGER.md:2851`, `:3072`; `PROGRESS.md:12-24`;
  `ROADMAP.md:3303-3320`; `DECISIONS.md:28714-28787`
- **Related claim IDs:** WORK-01, WORK-04, WORK-18
- **Related decision IDs:** D-417 §B6 ("implement what has a favourable quality/latency trade-off, and
  measure rather than assume"), D-423, W27, B6
- **Repository evidence:** no concurrent-`scope_guard` implementation exists in the graph code; the three
  constraints are code-verified.
- **Deployed/live evidence:** the measurement was taken **on staging** against `gha-44a12dfc9549`, so it
  is a **pre**-D-423 baseline; LB-08's independently measured 10.55 s guest turn corroborates it and is
  destroyed by a deploy (`LB-05-DEPLOY-GAP`).
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** covered by an accepted decision that **delegated the call with a criterion** the
  measurement meets — 22% for a fraction of a cent per non-QA turn is "favourable" by the user's own
  criterion — so it is engineering work, not a decision. It is the explicit next-session pointer in two
  documents and the only genuinely queued code work.
- **Remaining action:** build D-423 steps 1–3 as specified. **One user-facing note, not a decision:** the
  user approved a *different* optimisation on a premise D-423 falsified, so if anything here needs a user
  sentence it is an **acknowledgement of that substitution**. Verify the wasted-rerank trade-off is still
  acceptable before building. The measurement itself is settled and supersedes an earlier 25% estimate.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `WORK-04-ANSWER-CACHE` — the answer cache is settled by D-423's numbers, not deferred

- **Work/Issue ID (topic key):** `WORK-04`
- **Members:** E1-87 (WORK-04), E7-8
- **Description:** An answer cache "remains a decision, not an optimisation" because citations carry
  `effective_to`, so a cached answer can outlive its sources' effective window (rule 5), and the named fix
  is clamping each entry's TTL to its earliest citation expiry. **D-423 decided it by making the
  precondition go away:** with ~7.5 s remaining after the planned overlap and no ungrounded fast answer
  permitted, **stage 1 is a progress line naming the stage** — "nothing else can be said before retrieval
  has run". A cache is the only thing that could make stage 1 substantive, and stage 2's transport already
  exists (D-348/D-395/D-404), so the UX is "mostly a render-state change rather than new plumbing".
- **Domain:** chat RAG / caching
- **Original source(s):** `CLAIM_LEDGER.md:2890`; `PROGRESS.md:31-33`; `DECISIONS.md:28346-28362`
  (D-417 §B6), `:28771-28782` (D-423)
- **Related claim IDs:** REQ-14, WORK-01, WORK-04, WORK-18
- **Related decision IDs:** D-379 (removed the fabricated refusal an ungrounded stage 1 would re-create),
  D-417 §B6, D-423, B6; CLAUDE.md rule 5
- **Repository evidence:** **no answer cache exists** — only `functools.lru_cache` on settings and
  dependencies; no Redis, no answer-keyed store, no TTL. And "citations carry `effective_to`" is
  imprecise: `effective_to` lives on `RagDocument`/`RagChunk` and is enforced as a retrieval predicate,
  while the `Citation` model and the API's `CitationResponse` carry **none** — so the named clamp would
  need an extra lookup, which *strengthens* the "this is a decision, not an optimisation" conclusion
  (DRIFT-92, in `BATCH-LOW-OVERSTATEMENT`).
- **Deployed/live evidence:** n/a — nothing to observe; no cache is deployed.
- **Final disposition:** `RESOLVED`
- **Justification:** contingent on a requirement that does not exist. It is a *specified option*, not an
  open question, and promoting it would be re-litigating rule 5. The progress line is honest by
  construction under the user's own constraint. Raised in the extraction only because D-423 uses the word
  "decision" about it, which is exactly the shape the filter was told to catch.
- **Remaining action:** none. Revisit only if a **substantive** stage 1 ever becomes a requirement — the
  clamped cache stays on record as the design that would then be needed. Excluded from the queue on this
  basis.
- **Owner type:** none · **Reopen condition:** a requirement for a substantive stage 1 · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `H1-ACCESS-PROBE` — the access-probe rule is closed by measurement, over an unread span

- **Work/Issue ID (topic key):** `H1` (chain H1)
- **Members:** E2-18
- **Description:** D-371 closes the access-probe item on measurement ("the item closes"), but three
  cautions attach: two asserted links have **no stated relation at all** (D-180→D-220 and D-221→D-359), so
  the chain is LOW-confidence at those joints; entries D-181–D-219 and D-222–D-358 **were not read**, so
  an unnamed intermediate probe decision could exist; and D-180's own live row is **vacuous by its own
  admission**, so AUD-C-26's user-exposure question is recorded as **permanently unanswerable**. The
  chain's numbers (25/43, 23/38, 29/38, 27/38, 22/38, 11/38, 2/8…) are **not one series**.
- **Domain:** chat RAG / role-gated retrieval
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1210-1213`, `:1224-1246`
- **Related claim IDs:** REQ-46
- **Related decision IDs:** D-164…D-169, D-177…D-180, D-219, D-220, D-221, D-351, D-359, D-371
- **Repository evidence:** the rule is decided and measured; D-371's status is "measured, deliberately not
  tuned — the item closes".
- **Deployed/live evidence:** the rule is **byte-identical** between the deployed build and HEAD
  (`git diff --stat` on `access_probe_policy.py` empty), so the closure holds for the deployed build too.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** the rule is settled; what is open is the map's own coverage and one unanswerable
  question. Nothing is owed.
- **Remaining action:** none. **If any conclusion depends on "no probe decision exists between D-181 and
  D-358", that is an unverified assumption the map explicitly disclaims.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `H2-AUDC23` — the access-hint flip finding is never closed with a "never", and never formally accepted

- **Work/Issue ID (topic key):** `H2` (AUD-C-23; chain H2)
- **Members:** E2-19
- **Description:** The AUD-C-23 oscillation ends with a shipped remedy (D-177 §2: floor 0.9 plus a
  pre-floor margin) verified live 0/10 by D-178 — but D-178 explicitly **refuses to certify** ("Nothing
  here licenses writing 'never'"), D-179 finds the harness never matched production and marks every
  non-shipped row a lower bound, and **nothing in the chain closes AUD-C-23**. The residual false-hint
  flip rate is bounded only at **<26%**.
- **Domain:** chat RAG access-hint correctness
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1170`, `:1277-1287`, `:1302-1307`
- **Related claim IDs:** REQ-46, AUD-C-23 [AUDIT_FINDINGS]
- **Related decision IDs:** D-172…D-179; the D-072/D-123 residual-risk convention
- **Repository evidence:** the remedy is shipped and pinned; the finding has never been given the
  project's own §7-style residual-risk treatment with an expiry condition.
- **Deployed/live evidence:** the shipped constants are live and unchanged since 2026-08-04.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** §C override. D-371 closed the *item* by measurement, so the formal residual is a
  wording act: record "**measured <26%, not certified**" as the disposition. The gap here is procedural —
  a finding that cannot be closed and has not been accepted just sits.
- **Remaining action:** write the one-line residual note, in the §7 style, wherever AUD-C-23 is tracked.
  **Do not "improve" recall reporting by dropping the negative controls** — this is a precision-over-recall
  claim.
- **Owner type:** documentation · **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `H5-LIVENESS-TIMER` — the 40 s/15 s SSE ratio is argued, not measured live

- **Work/Issue ID (topic key):** `H5` (chain H5)
- **Members:** E2-22
- **Description:** The chat turn-lifecycle chain is additive and internally clean (D-346 → D-402 → D-403
  → D-404 → D-405, extended by D-413). Two residuals: whether a **40 s stale timer against a 15 s
  keepalive** is the right ratio is **argued, not measured live**; and learning-web parity is asserted only
  structurally (D-415). D-403's "Deferred" paragraph also stands with no forward pointer to its closure.
- **Domain:** SSE / chat turn lifecycle
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1447-1451`, `:1465-1469`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-346, D-402, D-403, D-404, D-405, D-413, D-414, D-415
- **Repository evidence:** a reasoned engineering constant with a falsification test behind it — removing
  the timer fails 2 of 6.
- **Deployed/live evidence:** none taken; live confirmation would be nice-to-have, not owed.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** a reasoned constant with a falsifying test; nothing is broken.
- **Remaining action:** none. The learning-web banner half overlaps `WORK-12-BANNER` — treat as one
  carry-over, not two.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `ACCESS-HINT-FIGURES` — the recall figure is superseded, precision is stated at opposite polarity, and D-371 names a constant that does not exist

- **Work/Issue ID (topic key):** `LB-02` (with LB-03)
- **Members:** E6-2 (LB-02), E6-3 (LB-03)
- **Description:** **(a)** The Phase-2 ledger re-quotes `DECISIONS.md:25129-25130` ("Recall **1 of 8**",
  "Precision **0 of 5** public questions produced a false one"). D-371 (2026-08-16, `:25966-25972`)
  already replaced it: "recall **2/8**, precision **5/5**", plus the methodological correction that **the
  denominator was never 8** — the probe's precondition is a no-source refusal, so an *answered* question
  never reaches it, making it 2 of the 6 reachable. **(b)** "0 of 5 false" and "precision 5/5" are the same
  fact counted in opposite directions, so a reader comparing sees `0` against `5`. **(c)**
  `DECISIONS.md:25953` says "a shipped ceiling of **0.40**" and **no constant equals 0.40**: 0.40 was
  D-165's value; `ACCESS_PROBE_MAX_DISTANCE = 0.45` has been the *fallback* since D-166 and is documented
  as such (`access_probe_policy.py:37-40`); and since D-168 the live rule is three constants —
  `ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60`, `ACCESS_PROBE_RERANK_MIN_SCORE = 0.9`,
  `ACCESS_PROBE_TIER_MARGIN = 0.10`. D-371's argument is unaffected; only the label is wrong — but the
  label is the actionable part, because someone "tuning the shipped ceiling" would edit the fallback used
  by the lexical, `MockBedrockProvider` and degraded paths and see **no production change**.
- **Domain:** chat RAG / access-hint probe metrics and constants
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:157-234`, `:503`; `LIVE_BEHAVIOR_EVIDENCE.md:51-60`
- **Related claim IDs:** REQ-46
- **Related decision IDs:** D-165, D-166, D-168, D-177, D-221 (score both directions), D-351, D-359,
  D-371
- **Repository evidence:** `access_probe_policy.py` has 4 commits, none after 2026-08-04; the last constant
  change is `e1ab0ad` (D-177, `0.8 → 0.9`); no B4 or C8 commit touched a hint-path line.
- **Deployed/live evidence:** the rule is identical on both sides; the **rate is unmeasured on either**.
  The live arm reproduced **one cell** only — a guest turn returned `access_hint = null` with 1 citation
  on a public question, and that turn landed in `classify()`'s `ANSWERED` bucket which by D-371's own
  argument never reaches the probe's precondition. One turn is not a rate.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** restatements and one wording correction in a DECISIONS entry body; correcting an entry
  in place is the log's established culture (correct loudly, keep the trail).
- **Remaining action:** restate REQ-46 with D-371's numbers **naming the denominator** (2/8 versus
  2-of-6-reachable) or the defect reproduces; normalise the precision polarity; correct the "0.40 ceiling"
  label. The *re-measurement* is a separate paid item (`SPEND-AUTHORIZATION`), and moving recall at all
  requires the separate measured offline rule sweep bounded by AUD-C-20 — not this probe.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

---

## §7 Testing & verification method

### `C6-UNATTENDED` — §2.6 criterion 6 cannot be satisfied yet, and job success is unproven

- **Work/Issue ID (topic key):** `C6-UNATTENDED` (WORK-35, 3B-1 sense). See §0.6.
- **Members:** E5-24
- **Description:** Two independent obstacles, neither removed by the RD-01 fix. **(1) Arithmetic:** the
  `session-consolidate` schedule was created **2026-08-16T04:10:34Z** and never modified, so as of
  2026-08-20T00:08Z it had existed 3 days ~20 hours — **at most four** firing opportunities (18:00Z on
  08-16/17/18/19). "≥1 week of unattended firing" is arithmetically impossible today; the earliest possible
  satisfaction on the schedule alone is **2026-08-23T18:00Z**. **(2) Instrument:** the thing meant to
  measure it cannot — `JobCompletions` has zero datapoints ever and the heartbeat alarm has one transition
  and has never been OK. Job **execution** is confirmed only at metadata level (ops-task log streams at
  18:01/18:11/18:50 UTC on 2026-08-18 and 2026-08-19); **job success is not proven at all** — those
  streams could equally hold tracebacks, and reading them is an ops log-content read. The claimed
  idempotency numbers (36,929 rows, 0 written on a second run, 40 s versus 4m00s) also cannot be verified
  read-only.
- **Domain:** scheduled jobs / launch-gate evidence
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:567-577` (WORK-35), `:89-99` (ARCH-04);
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:102-107`
- **Related claim IDs:** WORK-35 (3B-1), COST-18, COST-19, ARCH-04
- **Related decision IDs:** D-377, §2.6 criterion 6
- **Repository evidence:** `session-consolidate` first in `locals.jobs`, enabled, `cron(0 18 * * ? *)`,
  `retry_attempts = 2`; app code, migrations, model/repository, the job constant and four test files all
  exist. The repository can show the job is *written*; it cannot show it *ran*.
- **Deployed/live evidence:** the schedule is present and `ENABLED` with cron, timezone, target and retries
  all exact (`ScheduleExpressionTimezone: UTC`, `MaximumEventAgeInSeconds: 3600`, container override
  `python -m learning_api.services.session_consolidation_cli`, both private subnets,
  `AssignPublicIp: DISABLED`). The **schedule half is DEPLOYED_CONFIRMED**; the firing-duration half is
  not confirmable today.
- **Final disposition:** `BLOCKED`
- **Justification:** blocked on wall-clock time **and** on RD-01's fix. No amount of work closes it before
  the clock allows, and it cannot be *measured* until the heartbeat instrument works.
- **Remaining action:** **dependency ordering, easy to miss:** fix RD-01 → deploy → *then* start counting
  the week. If the fix lands on 08-21, the earliest defensible satisfaction is **~08-28, not 08-23**. Keep
  the execution/success distinction sharp: "the streams exist" is currently the only evidence any nightly
  job works, and it is compatible with every run failing. **Sub-question attached to UD-1:** whether §2.6
  criterion 6 may be satisfied by an instrument repaired mid-window, or whether the week must restart clean
  after the RD-01 fix ships — a gate-integrity call, and exactly the kind of thing that gets quietly
  fudged.
- **Owner type:** engineering, then wall clock; user for the gate-integrity framing (UD-1 sub-question)
- **Reopen condition:** RD-01 fixed and deployed, plus seven days of confirmed firings.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `DB-CONTENT-VERIFY` — four claims about database contents are unverifiable read-only, and one needs a mutation

- **Work/Issue ID (topic key):** `DB-CONTENT-VERIFY` (SEC-27 / INT-29-applied / WORK-03 / WORK-20 /
  TEST-04)
- **Members:** E5-27
- **Description:** Five items cannot be closed under the audit's rules. **SEC-27** (do `cost_reservations`
  rows exist in staging Postgres), **INT-29** (does the deployed knowledge store still hold the enrollment
  FAQ as `status: draft`), **WORK-03** (has migration `8509c0486d8d` been applied to the deployed
  database) and **WORK-20** (is migration `6538a95bc990` applied — `alembic_version` lives in the private
  Postgres) are **the same blocker wearing four hats**: the staging databases are
  `PubliclyAccessible: false` in private subnets and their credentials are Secrets Manager values, so any
  answer needs a `SELECT` plus a resolved secret. **TEST-04** (does a deployed container actually fail on a
  missing required env var) is a different blocker in kind: demonstrating that fence means deregistering an
  env var and forcing a task start — **a mutation**.
- **Domain:** verification method / data layer / migrations
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:598-606` (§3.3);
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:388-393`
- **Related claim IDs:** SEC-27, INT-29, WORK-03, WORK-20, TEST-04
- **Related decision IDs:** the read-only constraint of the audit phases; D-152 for anything
  integration-shaped
- **Repository evidence:** migrations, models and the knowledge-store code all exist and are readable; the
  repository can prove a migration was **written**, never that it was **applied** to a specific deployed
  database.
- **Deployed/live evidence:** genuinely unreachable through the control plane. Circumstantial proxies exist
  (ops-task ingestion log lines for INT-29) but log content was unreadable in that phase and would in any
  case show *that* an ingest ran, not *what* the store holds.
- **Final disposition:** `BLOCKED` — by the verification method's own rules, deliberately, not by neglect
- **Justification:** **one structural limitation plus one mutation-shaped item, not five gaps** — do not
  let the count inflate the finding. WORK-03 and WORK-20 are the two with real launch consequence: an
  unapplied migration is a live outage waiting for the first request that touches the new table, and today
  nothing in the audit can rule it out. WORK-03 specifically closes on the UD-1 deploy.
- **Remaining action:** **rider on UD-2** — authorize a *time-boxed, read-only, user-approved* database
  session (bastion or session-manager port-forward, `SELECT` only) to close the migration-applied
  questions. Without it, "is the migration applied on staging?" stays permanently unanswerable, which is a
  poor place for a launch gate to sit. Add `G2-LOCATOR-PURGE`'s `__resume__` query and
  `WORK-35-LEDGER`'s staging sizing read to the same session. TEST-04 stays out: it needs a mutation.
- **Owner type:** user (authorization), then engineering
- **Reopen condition:** UD-2 authorizes the session, or the UD-1 deploy closes WORK-03 by itself.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `WORK-13-FIXTURES` — the staging e2e isolation defect is behaviourally resolved; the test-side fix and the carry-over remain

- **Work/Issue ID (topic key):** `WORK-13` (LB-04)
- **Members:** E1-96 (WORK-13), E6-4 (LB-04), E7's note 3 (the named test-side fix)
- **Description:** `PROGRESS.md:16659-16690` — the file's physically last entry, dated 2026-08-07 — presents
  the `journey-student.spec.ts` isolation defect as current, including a "Fix when picked up" list of two
  test-side fixes. The staging run reproduced **none** of the three symptoms: `pre-exam: answered 10 items`
  → **10/10** (was 1 of 10); `refused=0` across all 12 study iterations with `POST …/answers` ×15 all 200
  and `failedRequests: []` (was 7 refusals); refresh identity stable (`Pre-exam Question 3 of 10` before
  and after, only the countdown differing). Both tests ran in one file, one process, `workers: 1`,
  `retries: 0`, first try — **the exact "in combination" condition the carry-over says fails**. Only the
  first proposed fix was applied (per-test fixture students, D-365 §2 / D-367) and it is behaviourally
  sufficient; the second (`beforeEach` session clearing) is **not needed**. What is still owed is the
  test-side fixture-isolation fix named in the 2026-08-07 carry-over — "give each test its own fixture
  student, or clear sessions in `beforeEach`" — as the **prerequisite for UD-2's whole-directory re-run**,
  because running that re-run before the fix would just re-measure a known bug.
- **Domain:** e2e test isolation / PROGRESS currency
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:238-291`, `:505`;
  `LIVE_BEHAVIOR_EVIDENCE.md:104-116`; `CLAIM_LEDGER.md:3007`;
  `DEPLOYED_INFRA_DRIFT_REGISTER.md:381`
- **Related claim IDs:** WORK-13, WORK-34, TEST-21, TEST-27
- **Related decision IDs:** D-213, D-355, D-365 §2, D-367, AUD-F-23
- **Repository evidence:** the fix is present at HEAD and **byte-identical in the deployed build**
  (`git diff --stat 44a12dfc9549..HEAD -- e2e/` shows the only e2e change is
  `chat/response-shapes.spec.ts`), which is what makes the run a legitimate instrument for that build.
- **Deployed/live evidence:** the passing run was executed against `gha-44a12dfc9549` via CloudFront with
  `EXPECT_BUILD_SHA` enforced, exit 0.
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** the **claim** is closed live and must not be double-counted as open. What survives is
  the test-side fix, owed because it gates UD-2's broader arm. The register-level scope is a **different
  and wider** statement and stays open: `DEPLOYED_INFRA_DRIFT_REGISTER.md:381`'s wording is "when the
  learning e2e walks run in **combination** against staging", i.e. the seventeen-spec cross-spec contention
  that produced the original failure (the walk then shared `studentPresent` with seventeen other specs).
  **Do not flatten the two scopes.**
- **Remaining action:** land the fixture-isolation fix, then the whole-directory arm becomes worth
  authorising. Retire or date the PROGRESS carry-over and record that fix 2 is unnecessary (documentation
  half). A deploy would change the build under test, so decide the order with UD-1.
- **Owner type:** engineering, with a documentation tail
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `PLAYWRIGHT-LANE` — the browser lane was not executed, so the one new implementation defect has no runnable guard

- **Work/Issue ID (topic key):** `PLAYWRIGHT-LANE` (§5 unreached area 1)
- **Members:** E4-19
- **Description:** Deferred by phase design: the Playwright suite shares the dev Postgres with pytest
  (running both concurrently manufactures network-level failures that look like regressions) and it needs
  both APIs plus both Vite dev servers up. Specifically not reached: **TEST-22's 5 specs** — the audit's
  **only** remaining `TEST_EXISTS_NOT_EXECUTED` residue; **TEST-27's behavioural half** (the
  `assertClean()` / `expectNotBlank` / `expectNotStuck` claims — only `make e2e-typecheck` ran, which
  proves the fixture *compiles*); **WORK-40's three breadcrumb specs** and
  `e2e/tests/learning/dashboard-chart-labels.spec.ts`, the *only* coverage of the module-private
  `buildDateLabelFormatter`; **WORK-12's absent learning-web banner spec**; and
  `e2e/tests/chat/stream-disconnect-visible.spec.ts`.
- **Domain:** testing coverage / audit completeness
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:766-785`; `LOCAL_EXECUTION_EVIDENCE.md:841-843`
- **Related claim IDs:** TEST-22, TEST-27, WORK-12, WORK-40
- **Related decision IDs:** the pytest/Playwright shared-Postgres constraint (project memory)
- **Repository evidence:** the specs exist; `make e2e-typecheck` passes.
- **Deployed/live evidence:** the staging Playwright lane *was* exercised for `journey-student.spec.ts`
  (`WORK-13-FIXTURES`); the local lane was not.
- **Final disposition:** `DEFERRED`
- **Justification:** a deliberate scope boundary with a stated technical reason, not an omission, and the
  lane is locally runnable at some future point with no live or paid dependency — hence DEFERRED rather
  than BLOCKED. It **bounds `WORK-40-TZ` directly**: a chat-web timezone fix cannot be validated by any
  executed test today.
- **Remaining action:** run the lane in a serialized window. If only one spec is ever run, the
  highest-value single one is `dashboard-chart-labels.spec.ts` — the guard on the function at the centre of
  the audit's one new implementation defect, which has still never been observed to run.
- **Owner type:** engineering · **Reopen condition:** a serialized test window
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `PAID-RUNS-LANE` — paid generation and measurement scripts were not invoked

- **Work/Issue ID (topic key):** `PAID-RUNS-LANE` (§5 unreached area 3)
- **Members:** E4-21
- **Description:** `question-gen-run`, `question-gen-authored` and `scripts/measure_*` spend real money and
  were not invoked. **No finding in the audit depends on a paid run.**
- **Domain:** cost discipline / audit completeness
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:794-795`
- **Related claim IDs:** COST-06 (whose test explicitly needs **no** paid run — the fake gateway
  suffices), TEST-13
- **Related decision IDs:** the project's paid-run budget conventions
- **Repository evidence:** the `Makefile` targets and `scripts/measure_*` exist and are guarded.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DEFERRED`
- **Justification:** correct restraint for an audit — spending money to confirm a documentation claim is not
  warranted. Worth stating positively: the measured constants (quote floor, rerank floor) are asserted by
  band tests that **ran**, so the paid measurement scripts were not needed to verify the constants are *in
  force*, only to re-derive them.
- **Remaining action:** none in this entry. Any authorised paid run belongs to `SPEND-AUTHORIZATION`
  (UD-2).
- **Owner type:** user (if ever authorised) · **Reopen condition:** UD-2 authorises spend
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `REQ-44-REASON-SWEEP` — the reason-code sweep covers 5 of 10 reason sets and passes vacuously outside the dict

- **Work/Issue ID (topic key):** `REQ-44` (F-09; DRIFT-74)
- **Members:** E4-9 (F-09)
- **Description:** `apps/chat-api/tests/test_turn_reasons.py` ran inside a 43-test batch, `43 passed` — the
  no-reason-code-restated sweep works. But it **iterates only `REASON_MESSAGES`**, 5 entries
  (`outcomes.py:134-140`) against **ten** enum values. The copy that is *not* swept:
  `UNAVAILABLE_INTENT_MESSAGES`, the `LOCATION_*` strings, `RATE_LIMITED_MESSAGE` and the calendar copy —
  all node-local and outside the dict. The assertion is a plain substring check, so it **passes vacuously
  for any copy defined outside the dict**: adding a new user-facing message that restates a reason code
  would leave this test green. The docstring's promise that "the next message added is covered by
  construction" is true **only** for messages added to `REASON_MESSAGES`.
- **Domain:** testing rigor / user-facing copy
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:466-483`, `:69-71`;
  `REPOSITORY_DRIFT_REGISTER.md:847`, `:851`
- **Related claim IDs:** REQ-43, REQ-44, REQ-45, REQ-48
- **Related decision IDs:** none; the vacuity caveat was adjudicated to stand
- **Repository evidence:** `test_turn_reasons.py:46-55`; `outcomes.py:134-140`. The five-of-ten arithmetic
  is already carried in the drift register.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** the phase's own nominated **"clearest case of a green test that must not be read as
  coverage"** — the pass is necessary and not sufficient. If REQ-44 is reported as LOCALLY_VERIFIED, that
  classification must travel with the vacuity caveat, or it overstates the evidence in exactly the
  direction 3A.5 existed to correct.
- **Remaining action:** widen the sweep to enumerate all user-facing copy constants, **or** assert
  `REASON_MESSAGES` is exhaustive over the ten enum values — the structural fix that would make the
  existing sweep total. Local, cheap, no live or paid dependency. Quote F-09 verbatim in any summary.
- **Owner type:** engineering · **Reopen condition:** n/a · **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `M3-D370-SOLUTION-RUNG` — the solution terminal rung has no staging e2e coverage under a roadmap-closing ✅

- **Work/Issue ID (topic key):** `M3` (D-370 scope; chain M3)
- **Members:** E2-39
- **Description:** D-370 closes C1 Phase 6 on five consecutive clean runs (`gha-aaad6cfec153`) with status
  "✅ the last engineering clause in the roadmap" — but its own body qualifies the claim ("Zero 5xx… is
  **not yet proof**") and carries a `#### What did not close` section: **the solution terminal rung has no
  staging e2e coverage.** So the ✅ is scoped narrower than the tag suggests. D-366 (⏸, 140 lines earlier)
  still gives the opposite verdict on the identical clause with no forward cross-link.
- **Domain:** e2e coverage / study walk
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:2099-2100`, `:2110-2112`, `:2124-2127`
- **Related claim IDs:** TEST-22, TEST-27
- **Related decision IDs:** D-340, D-355, D-365, D-366, D-367, D-370
- **Repository evidence:** the named coverage gap is unblocked — nothing prevents writing the spec.
- **Deployed/live evidence:** the five clean runs were against an older build; no run covers the terminal
  rung.
- **Final disposition:** `ACTIVE_IMPLEMENTATION`
- **Justification:** a named, unblocked test-coverage gap on the terminal rung of the hint/solution path,
  closed only in tag. This is the one place where a roadmap-closing ✅ rests on a tag broader than its
  evidence — directly relevant to any claim that "the last engineering clause is closed".
- **Remaining action:** write the staging e2e coverage for the solution terminal rung. Separately, the
  D-366 ⏸ versus D-370 ✅ contradiction is a documentation fix in the same chain
  (`DOC-DECISION-LOG-CORRECTIONS`).
- **Owner type:** engineering, with a documentation tail
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `TEST-05-DESCRIPTIVE-REREAD` — the owed human re-read of §5.3 and §5.36 never fired across four qualifying changes

- **Work/Issue ID (topic key):** `TEST-05` (DRIFT-37)
- **Members:** E3-37 (DRIFT-37), E1-56 (TEST-05)
- **Description:** SPEC §5.3 and §5.36 are recorded as *descriptive* rather than traced, on the condition
  that a human re-reads them whenever the architecture changes. Multiple qualifying changes landed after
  tranche 6 and **no re-read record exists**: D-334/D-335 (the SSE bus replaced by Postgres
  `LISTEN`/`NOTIFY`), D-349 (the same relay for chat-api), D-406/W14 (NAT topology moved), and
  D-393/D-394. TRACEABILITY *was* edited on 2026-08-17 and the §5.32 row updated, but the §5.3 and §5.36
  descriptive rows were not touched. A corpus grep returns only the two places that state the obligation.
  §5.36 is independently known stale, so **the mechanism the descriptive verdict substituted for did not
  fire.**
- **Domain:** traceability governance / testing method
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:438-447`; `CLAIM_LEDGER.md:2076`;
  `TRACEABILITY.md:45-47`, `:622`, `:626-633`; git log for TRACEABILITY.md → `7285951`, `2dd9e7e`
- **Related claim IDs:** TEST-03, TEST-04, TEST-05, TEST-07, ARCH-25, TEST-06
- **Related decision IDs:** D-334, D-335, D-349, D-393, D-394, D-406
- **Repository evidence:** DRIFT-100 confirms the fence's bookkeeping is otherwise honoured — the two
  "nothing mechanical — descriptive" rows are consistent with the fence and recorded as such. So the fence
  is honest; the substitute mechanism is what failed. F-07 supplies an independent instance of the same rot
  (the `(Sn)` provenance convention abandoned around S39 while the header still advertises it).
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `ACTIVE_REMEDIATION`
- **Justification:** the obligation is already recorded; execution is owed. The generalisable lesson is
  sharp: **a *descriptive* traceability verdict is only as good as the human habit substituting for a
  mechanism**, and this is the proof that the habit did not fire across four qualifying changes. Worth
  naming in the final report as a method finding, not just an entry. These two rows also sit under the
  37-of-37 claim while being neither traced nor structural, which qualifies TEST-07.
- **Remaining action:** perform the re-read, **or** replace a human habit with a definable trigger.
  "What counts as an architecture change" is undefined, which is arguably a convention decision worth
  settling at the same time.
- **Owner type:** engineering/documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `TEST-24-429` — a real HTTP 429 has never rendered and stays deliberately open

- **Work/Issue ID (topic key):** `TEST-24`
- **Members:** E1-65
- **Description:** A genuine 429 remains unrendered: it is reachable only through the message limiter (too
  expensive to drive) or the global middleware (a load test), while the escalation limiter is in-graph and
  returns 200 with `RATE_LIMITED_MESSAGE`, not a 429.
- **Domain:** error-path coverage
- **Original source(s):** `CLAIM_LEDGER.md:2323`; `AUDIT_LIVE_2026_08_17.md:84-86`;
  `ROADMAP.md:2580-2583`
- **Related claim IDs:** TEST-22, TEST-24, TEST-25, TEST-26, SEC-18, SEC-19, REQ-43
- **Related decision IDs:** D-383, AUD-C-27 [AUDIT_FINDINGS]
- **Repository evidence:** the paths are as described; no test drives a real 429.
- **Deployed/live evidence:** none — driving it live is the cost.
- **Final disposition:** `DEFERRED`
- **Justification:** a knowingly-unexercised error path with a stated cost reason. It **qualifies TEST-22's
  "all three closed"** and must not be silently absorbed by it — the honest residue of an otherwise-closed
  batch, kept visible precisely because its parent claim reads as closed.
- **Remaining action:** none unless someone funds a load test (`SPEND-AUTHORIZATION` context).
- **Owner type:** user (if funded) · **Reopen condition:** a funded load test
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `TEST-01-CRITERION1` — criterion 1 is MET on a written reading that an unbuilt launch requirement does not satisfy

- **Work/Issue ID (topic key):** `TEST-01`
- **Members:** E1-55
- **Description:** §2.6 criterion 1 (100% of launch-scope SPEC requirements mapped to implementation plus
  test, every discrepancy dispositioned) is recorded MET as of 2026-07-30 on an **explicitly written
  reading**: it means nothing is undecided, **not** nothing is missing.
- **Domain:** traceability / launch gate
- **Original source(s):** `CLAIM_LEDGER.md:2024`; `TRACEABILITY.md:5-6`, `:101-111`
- **Related claim IDs:** TEST-01, TEST-02, TEST-07, TEST-10, SEC-20, REQ-25
- **Related decision IDs:** D-123, D-129, T-02
- **Repository evidence:** the reading is verbatim and self-disclosed.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** the risk is not the reading but the quotation: "criterion 1 MET" quoted **without** it
  competes with the plain reading of the criterion, which T-02's unbuilt state does not satisfy — a MET
  gate over an unbuilt launch requirement.
- **Remaining action:** none, except that any launch-readiness summary must carry the reading with the
  verdict. Cross-reference `DISCLOSURES-LEGAL`.
- **Owner type:** documentation (when quoted) · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `F4-CRITERION6` — criterion 6 is closed conditionally, and the condition is live and unmonitored

- **Work/Issue ID (topic key):** `F4` (chain F4 / D-148 §2)
- **Members:** E2-4
- **Description:** The §2.6 gate's criterion 6 was closed early on an **explicit user bypass**, with the
  waived evidence (the weekly cron's own Sunday slot, and the purge jobs' full ≥7 unattended days) demoted
  to "free confirmation reads" — under a written condition, read at `DECISIONS.md:8673-8674`: **"a failure
  in any of those scheduled firings reopens criterion 6"**, because "the bypass waives the wait, not the
  evidence standard going forward". D-149 then proved the cron path via a `SAT` clone, leaving the `SUN`
  enum value itself unexercised.
- **Domain:** launch gate / scheduled jobs
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:626-628`, `:645`; `DECISIONS.md:8670-8674`,
  `:8725`
- **Related claim IDs:** WORK-35 (3B-1 sense), COST-18, COST-19
- **Related decision IDs:** D-135, D-138, D-140, D-141, D-142, D-148 §2, D-149
- **Repository evidence:** the closure and its condition are recorded; the `SUN` enum remains unexercised
  as of D-149.
- **Deployed/live evidence:** **the reopen condition requires someone to actually *read* the scheduled
  firings — and RD-01 makes the instrument that would report a failure structurally silent.** So the
  condition is currently unmonitored, which is the risk rather than the closure.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** the gate is closed by an explicit user decision and re-asking would reopen a settled
  call. The residual verification is parked as confirmation reads under a standing reopen trigger.
- **Remaining action:** none for the closure. Once `RD-01` is fixed and deployed, the confirmation reads
  become possible and the reopen condition becomes monitorable — that is the concrete dependency, and
  `C6-UNATTENDED` carries the arithmetic side.
- **Owner type:** none now; engineering after RD-01
- **Reopen condition:** a failure in any of the waived scheduled firings — currently undetectable.
- **PROJECT_STATE?** yes — parked, with an unmonitored condition flagged
- **Historical/archive only?** no

### `H3-ICS-WEBKIT` — the `.ics` item is closed; "no engine can catch this" and the WebKit project are unmeasured residuals

- **Work/Issue ID (topic key):** `H3` (chain H3; OPEN_DECISIONS #13)
- **Members:** E2-20
- **Description:** OPEN_DECISIONS #13 is closed by D-399's DOM-contract test, after two remedies that did
  not close it. Three residuals survive: D-397's **labelled guess** (Playwright drives downloads via the
  automation protocol, so this defect class may be invisible to every engine) is explicitly **not
  measured**; the WebKit Playwright project **outlives the reason it was purchased**, on an iOS-coverage
  rationale that was never the user's decision; and whether D-352's original two bugs were ever
  user-visible in a real browser is established nowhere. D-352's status is also still `implemented` and
  was never annotated as unverified even though D-392 says in terms that it "remains unverified".
- **Domain:** frontend test coverage / calendar `.ics`
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1330-1332`, `:1336-1338`, `:1346-1350`
- **Related claim IDs:** TEST-22, TEST-25
- **Related decision IDs:** D-352, D-392, D-397, D-399
- **Repository evidence:** the DOM-contract spec exists; the WebKit project remains a recurring CI cost.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** the decision closed and the residuals are **labelled-unmeasured hypotheses, honestly
  recorded**. The WebKit sub-point is recommendation-shaped — a recurring CI-cost choice on a rationale the
  user never chose — and is **excluded from the decision queue** on that basis rather than promoted.
- **Remaining action:** none owed. The stale D-352 tag is a documentation member of
  `DOC-DECISION-LOG-CORRECTIONS`.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `TEST-21-HISTORICAL` — the historical green-suite-with-live-P1s pairing is unobservable by construction

- **Work/Issue ID (topic key):** `TEST-21` (historical half)
- **Members:** E6-11
- **Description:** The claim that a green suite (`88 passed / 7 skipped` on `gha-6841d9d9b169`) coexisted
  with two live P1s hours before the 2026-08-17 audit **cannot be probed** — that build and that run are
  gone. No probe was manufactured; the orchestrator ruled it recorded as **context, not a blocked item**.
  It remains the more valuable half of TEST-21: **a green suite is not evidence about behaviour nobody
  asserted.** The current half is live-confirmed (127 ≥ 88, green with fewer skips, 2 < 7, all five D-383
  specs non-vacuous).
- **Domain:** test-coverage epistemics
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:508-511`; `LIVE_BEHAVIOR_EVIDENCE.md:62-74`
- **Related claim IDs:** TEST-21
- **Related decision IDs:** D-381, D-383
- **Repository evidence:** the historical build is not reconstructible.
- **Deployed/live evidence:** today's counts describe HEAD, not the deployed build.
- **Final disposition:** `OBSERVATION_ONLY`
- **Justification:** dispositioned as unobservable by construction; no work is owed. It is **distinct from
  BLOCKED_NOT_OBSERVABLE at claim level** — the evidence file records **0** blocked claims — so it must
  not be re-opened as a gap.
- **Remaining action:** none. Carry the lesson wherever a suite total is quoted as coverage
  (`SUITE-COUNT-CITATIONS`).
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `TRACEABILITY-ARITHMETIC` — three attributions, one off-by-one, and one deferral destination that does not list its item

- **Work/Issue ID (topic key):** `TRACEABILITY-ARITHMETIC` (DRIFT-02 / DRIFT-38 / DRIFT-39 / TEST-06 /
  TEST-07)
- **Members:** E3-2 (DRIFT-02), E3-38 (DRIFT-38), E3-39 (DRIFT-39), E1-57 (TEST-06), E1-58 (TEST-07)
- **Description:** Four defects in the **evidence base for gate criterion 1**. **(a) DRIFT-38:** two of
  three launch-scope exclusion attributions are unsupported by the decision text and one is thin — **D-004**
  supports "EKS-only concepts" generically but the words "Pod Security Standards" and "NetworkPolicy"
  **do not appear in D-004**; **`6.19` appears nowhere in `DECISIONS.md`**, so the "§6.19 Phase 18
  (D-078)" attribution has no supporting text; and **D-087** does carry the WAF deferral but **"S50" and
  "A7" appear nowhere in it**. This matters because the exclusion table is the **denominator** of the
  37-of-37 claim. **(b) DRIFT-39:** the sweep coverage is genuinely complete — every top-level section §5.0
  through §5.36 receives a verdict — but the arithmetic label is wrong: the scope section states §5 has 37
  top-level sections and then excludes "§5.17 Multimodal solution images (**all of it**)", leaving **36**
  launch-scope sections, while the Status line claims "37 of 37 **launch-scope** sections". 37 is reachable
  only by counting the excluded section's disposition inside the launch-scope denominator. The tranche-5
  running total still reads "Sections swept: 21 of 37", and §5.20/§5.23 have zero standalone mentions.
  **(c) TEST-07:** the "What remains" tail still lists **16 sections in present tense** under a "nothing
  remains to sweep" banner. **(d) DRIFT-02:** GuardDuty is "tracked to S50 A7" in TRACEABILITY, and
  ROADMAP's and INTEGRATION_PLAN's S50 A7 scope lists name WAF, a backup-restore drill, ZAP and a runbook
  — **and no GuardDuty**; the only ROADMAP mention is tranche-1 narrative describing it as a gap. Also
  noted: GuardDuty (D-125) is **absent from the exclusion list** although it is equally deferred, so the
  exclusion enumeration may be incomplete.
- **Domain:** traceability / audit-claim integrity
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:46-55`, `:449-458`, `:460-469`;
  `CLAIM_LEDGER.md:2089`, `:2102`; `TRACEABILITY.md:55-68`, `:57-58`, `:72`, `:99`, `:250-253`, `:576`,
  `:635`, `:641-650`, `:737-744`, `:759-773`, `:782`; `DECISIONS.md:29-36`, `:2025-2035`, `:2883-2896`;
  `ROADMAP.md:1429`, `:1516-1519`; `INTEGRATION_PLAN.md:475`; `SPEC.md:2868`
- **Related claim IDs:** TEST-01, TEST-05, TEST-06, TEST-07, TEST-08, TEST-10, SEC-17
- **Related decision IDs:** D-004, D-078, D-087, D-123, D-125, D-129
- **Repository evidence:** as cited; the per-section presence check across §5.0–§5.36 confirms coverage is
  complete.
- **Deployed/live evidence:** 3B-1's confirmation that GuardDuty is genuinely absent at **account** level
  makes the D-087/S50-A7 attribution question sharper, not softer.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the work is done; the **labels and attributions** are wrong, on the instrument that
  carries a launch-gate claim. Be precise in any summary: coverage is complete, the label is wrong — this
  entry reads worse than it is if summarised carelessly. Together these are the strongest argument in the
  corpus for a **targeted re-audit of TRACEABILITY's scope arithmetic and attributions** rather than
  piecemeal edits.
- **Remaining action:** re-derive the three attributions by quoting the decisions (or record them
  explicitly as inferences); correct the denominator and the stale running total; delete or date the
  16-section tail; add GuardDuty to the two S50 A7 scope lists (the fix can be batched with DRIFT-38's,
  since they are the same attribution-defect class).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `AUDIT-COUNT-INSTRUMENT` — "0 open findings" is true of one register and unknown project-wide, on an instrument with four recorded failure modes

- **Work/Issue ID (topic key):** `AUDIT-COUNT-INSTRUMENT` (TEST-15 / TEST-17 / TEST-18)
- **Members:** E1-61 (TEST-15), E1-62 (TEST-17), E1-63 (TEST-18)
- **Description:** `AUDIT_FINDINGS.md` reports open findings from both Index halves as **0**, with the
  arithmetic spelled out "because this line has now been wrong three times", and calls the Phase 0B backlog
  empty for the first time. The register is **frozen at 2026-08-05**, while the 08-16 and 08-17 audits filed
  **46 + 48** findings in separate namespaces — so "0 open" is true of one register and **unknown as a
  project-wide statement**. The Index also stopped being maintained once: **27 findings had a section and no
  row** (89 sections, 68 rows), breaking one-row-per-finding; two open findings were invisible to every
  table-derived count and five headings still read "not fixed" after their fixes landed. All were corrected
  the same day, and the pre-D-174 count was "wrong in both directions" — but the "every section has a row"
  property is **unverified**, and it is exactly the property that failed. ROADMAP records **four** ways the
  count goes wrong: carrying it forward; table-derived counts missing row-less findings; naive
  `grep -i open` over-counting because rows carry their own history in the status cell; and a stray pipe
  shifting the positional field (four rows carry an extra pipe, checked, all still correct).
- **Domain:** audit state / verification method
- **Original source(s):** `CLAIM_LEDGER.md:2206`, `:2232`, `:2245`; `AUDIT_FINDINGS.md:103-123`,
  `:131-150`, `:159-169`, `:179-180`; `ROADMAP.md:734-765`, `:749-753`, `:786-790`
- **Related claim IDs:** TEST-15, TEST-16, TEST-17, TEST-18, TEST-20, TEST-21, TEST-25
- **Related decision IDs:** D-174, D-178, D-183, AUD-F-32/AUD-C-09 [AUDIT_FINDINGS]
- **Repository evidence:** three registers with three namespaces and no roll-up is the underlying defect.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** "the audit backlog is empty" is the quantity most likely to be quoted, and it is a
  scoped statement masquerading as a project one. TEST-18 itself is a **method invariant, not open work** —
  it is the reason any count in this corpus must be **re-derived rather than quoted**, and it is the
  register's standing caveat on every count-shaped claim (TEST-15, TEST-28, WORK-05, WORK-11).
- **Remaining action:** consolidate the registers or give each count an explicit scope label; execute the
  anchored awk and record the **actual output** rather than re-quoting; verify every section now has a row;
  confirm the four extra-pipe rows still keep status in field 5. Pair with
  `RISK-GROUP-AUDIT-REGISTERS`.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `SUITE-COUNT-CITATIONS` — the quoted suite totals are reproducible and structurally silent about two things

- **Work/Issue ID (topic key):** `LB-07` (TEST-28 / WORK-05)
- **Members:** E6-7 (LB-07), E6-10 (the §4 WORK-05 correction), E1-67 (TEST-28), E1-88 (WORK-05)
- **Description:** `PROGRESS.md:35-38` records pytest **1735 passed / 2 skipped**; the whole suite at HEAD
  reproduced **both totals exactly** (`1735 passed, 2 skipped, 1 xfailed in 500.43s`), alongside 0 typecheck
  errors, Playwright 127 passed / 2 skipped, chat-web 49 unit tests, learning-web 26, and both builds clean.
  Two silences, neither a contradiction. **(a)** Collection was `collected 1738 items`; the missing item is
  `test_identical_inputs_reproduce_identical_routing_and_scores`
  (`apps/learning-api/tests/test_learning_flow.py:1247`, `@pytest.mark.xfail(strict=False)`,
  D-206/D-238) whose own comment records it "XPASSed once in a full run and xfailed on the next, from the
  same tree" — **nondeterministic by design**, so a run can legitimately print `1 xpassed`. The two-number
  pair is *more* stable than a three-number one; if the line is ever made to sum it must say so. **(b)**
  Both skips are **paid opt-ins**, so the free local suite is **structurally silent about real-Bedrock eval
  quality** — the same shape as the D-383 lesson. Counterweight in the claims' favour: ~14 conditional
  `test.skip(!reached, …)` non-vacuity guards exist across `e2e/tests/` and **none fired**, so the local
  127 is the non-vacuous 127 and the 2 Playwright skips are the *predicted* two
  (`deployed-authorization.spec.ts:188`, `:218`, both `TARGET !== "staging"`); all five D-383 blind-spot
  specs ran and passed non-vacuously. A separate correction: the extraction's "2 commits ahead of the
  snapshot" is **1** — `6f107c1` **is** #345, so only `344f016` (#346, docs-only) sits after WORK-05's
  snapshot (`git rev-list 6f107c1..HEAD --count` → 1), which means no Python or TypeScript exists between
  the snapshot and the measurement that could have moved a count, **strengthening** WORK-05's
  `aged-by-SHA` confirmation.
- **Domain:** test-count citation hygiene / eval coverage
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:370-422`, `:506`;
  `LIVE_BEHAVIOR_EVIDENCE.md:62-88`, `:98`, `:102`; `CLAIM_LEDGER.md:2375`, `:2903`
- **Related claim IDs:** TEST-21, TEST-28, WORK-05, WORK-11
- **Related decision IDs:** D-206, D-238, D-381, D-383, Milestone 15
- **Repository evidence:** the counts describe **HEAD `344f016`**, not the deployed build.
- **Deployed/live evidence:** **no staging suite total exists**, and the local 127/2-skip set differs from a
  staging run's by construction.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** whenever the total is cited **as coverage**, the citation needs the unstated exclusion
  attached; and per TEST-21 a green suite is not evidence that no P1 is live. The two halves — the caveat
  and the non-vacuity counterweight — are only honest together.
- **Remaining action:** attach the exclusion to every "1735 passed" citation, and **do not** "fix" the pair
  into a three-number sum without the nondeterminism caveat, which would make the documented line
  intermittently wrong. Correct the one-cell "2 commits" figure in the audit's own ledger (route to the
  ledger owner, not to the canonical-document migration). Running the two paid opt-ins is
  `SPEND-AUTHORIZATION` and does **not** gate this annotation. Also record the wording discipline from
  E4: "the suite is green" and "everything run passed" are different statements.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-TEST-CLAIM-WORDING` — three test-related claims whose corrections were never integrated

- **Work/Issue ID (topic key):** `DOC-TEST-CLAIM-WORDING`
- **Members:** E4-6 (F-06), E4-8 (F-08), E3-41 (DRIFT-41)
- **Description:** **(a) F-06:** `REPOSITORY_DRIFT_REGISTER.md:140` still reads "returns **only those
  three lines**" for `checkpoint_repair` in terraform; the grep returns **four**
  (`modules/ecs-service/main.tf:209` the otel `filter/kpis` strict include list, `:255` the `awsemf`
  exporter's `metric_declarations` — which promotes it to a real CloudWatch metric —
  `modules/observability/dashboard.tf:425` a comment and `:436` the widget). The substance is unchanged: no
  alarm references it. **(b) F-08:** the executed `extra="forbid"` count is **41** against a documented
  **31** at `docs/TRACEABILITY.md:623` and repeated at `docs/DECISIONS.md:6870`, and two facts the row
  should carry beyond the count: the strictness covers **41 of 184** non-test `BaseModel`/`BaseSettings`
  classes repo-wide (**22%**), and only **35 of the 64** `BaseModel` classes inside `bedrock.py` itself
  carry it — so "types every payload as an `extra="forbid"` model" is true for the **Bedrock payload
  surface** and is **not a repo-wide invariant**. The drift register integrated the correction; the
  repository documents did not. **(c) DRIFT-41:** "zero blank/stuck states enforced at teardown" overstates
  the e2e harness — `assertClean()` asserts `pageErrors`, `consoleErrors`, `serverErrors` and
  `failedRequests`, but "zero blank/stuck states" is **not a distinct teardown assertion**; it is carried by
  the `pageerror` listener and per-spec helpers `expectNotBlank`/`expectNotStuck`, i.e. asserted in-test
  rather than over the whole run. `clientErrors` (4xx) is explicitly "reported, not enforced".
- **Domain:** documentation accuracy / testing claims
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:353-383`, `:415-462`, `:757`, `:755`;
  `REPOSITORY_DRIFT_REGISTER.md:482-491`, `:140`, `:1136-1140`; `TRACEABILITY.md:623`;
  `DECISIONS.md:6870`
- **Related claim IDs:** SEC-10, TEST-04, SEC-06, TEST-22, TEST-25, TEST-27
- **Related decision IDs:** SPEC §5.27; AUD-X-07; D-355, D-383
- **Repository evidence:** `make typecheck` produced `0 errors, 0 warnings, 0 informations`, so §5.27's
  cited mechanism *does* run — but the register's sharper point stands: **pyright does not fail if an
  `extra="forbid"` is deleted**, so clause (b) holds only for the Bedrock subset pinned by
  `test_bedrock_payload_pii_floor.py:26-32`. `test_alarm_severity_routing.py`'s three tests passed and
  structurally **cannot** detect a missing alarm, so "tests pass" is not coverage for F-06's substance.
- **Deployed/live evidence:** RD-08 escalates F-06's substance to runtime (the metric has live data in the
  deployed account and still no alarm) — carried by `KPI-ALARM-FLOOR`, not closed here.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** three corrections that were **not** integrated where they matter. Keep the count fixes
  and the substantive gaps distinct so a register edit does not read as resolving the alarm gap; a bare
  31 → 41 edit would leave the row still overclaiming, so the edit must carry the **denominator (41/184)
  and the mechanism caveat together** or the row drifts again the next time a model is added.
- **Remaining action:** the three edits, each carrying its qualifier. The *substantive* nugget inside
  DRIFT-41 is separable and worth calling out: teardown runs `persist()` then
  `if (testInfo.status === "passed") log.assertClean()`, so a **failing** test's criterion-3 evidence is
  **reported but not enforced** — precisely backwards from an evidence standpoint, since a failing test is
  when you most want the console and network assertions to bite.
- **Owner type:** documentation, with one engineering question (the conditional teardown)
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DRIFT-58-E2E-ISOLATION` — the 3A e2e-isolation record is refuted at claim scope, with a paid residual

- **Work/Issue ID (topic key):** `DRIFT-58` (WORK-13) — batch B exception
- **Members:** E3-55:DRIFT-58
- **Description:** The 3A entry recorded the e2e isolation finding as unresolved against a spec that **now
  carries two dedicated fixture students** (`FIXTURES.studentJourney`, `studentResume`; `e2e/config.ts:128-165`
  defines three). The per-test-fixture remedy is present; the `beforeEach` session-clear remedy was **not**
  applied and is not needed. PROGRESS's last entry on the item (2026-08-07) is stale.
- **Domain:** e2e test isolation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:671` (DRIFT-58);
  `LIVE_BEHAVIOR_FINDINGS.md:238-291`, `:521-525`
- **Related claim IDs:** WORK-13
- **Related decision IDs:** D-288, D-365 §2, D-367
- **Repository evidence:** the fixture students exist at HEAD and byte-identically in the deployed build.
- **Deployed/live evidence:** the staging run reproduced **none** of the three 2026-08-07 symptoms, in the
  same process, first try.
- **Final disposition:** `RESOLVED` at claim scope — **batch B exception** — with a **DEFERRED residual**
- **Justification:** a measurement, not a document going quiet. **The residual must not be flattened:**
  LB-04 refuted the *claim*; it did **not** run the seventeen-spec combination that produced the original
  symptom, and that whole-directory re-run is paid and optional (`SPEND-AUTHORIZATION`, UD-2). Say both.
- **Remaining action:** the test-side fixture fix and the PROGRESS retirement are `WORK-13-FIXTURES`; the
  register-level cross-spec scope stays open at `DEPLOYED_INFRA_DRIFT_REGISTER.md:381`.
- **Owner type:** documentation for the record; user for the paid residual
- **Reopen condition:** the whole-directory re-run, if authorised.
- **PROJECT_STATE?** no for the claim; yes for the residual (tracked under UD-2)
- **Historical/archive only?** yes for the claim

---

## §8 Integration & organization (D-152 domain)

*Standing rule for this section (§0.2 rule 3): every parked or deferred item below is attributed to a
deliberate user decision, never to an obstacle. D-152 is "closed until reopened" (D-417 §A1) and no
accumulation of readiness reopens it.*

### `ORG-COMMS` — two High findings against a live production system sit in an unsent draft

- **Work/Issue ID (topic key):** `ORG-COMMS` (SEC-32 / INT-13 / INT-25 / DRIFT-03 + SEC-33 / INT-33 /
  DRIFT-04 R1 sign-off)
- **Members:** E1-42 (SEC-32), E1-43 (SEC-33), E1-73 (INT-13), E1-78 (INT-25), E1-82 (INT-33), E1-80
  (INT-28, the E-group half), E1-41 (SEC-31 severity rider), E3-3 (DRIFT-03), E3-4 (DRIFT-04)
- **Description:** `S42_SECURITY_REPORT.md` is a bilingual hand-off drafted 2026-08-02, intended to go as
  one message to the production operator. It carries only `**Drafted:** 2026-08-02 (S43)` and a `**Send:**`
  instruction: **no send date, no recipient, no confirmation field**, unfilled recipient placeholders, and a
  corpus grep in English and Korean returns **zero** send confirmations. PROGRESS still lists sending as
  the user's outstanding step, and the E-group notification is still one of only two currently-valid actions
  in `S42_OPEN_QUESTIONS.md`. So on the evidence, **two High findings against someone else's live
  production system sit in an unread draft** — and the report has no field that would make its absence
  visible. Three claims independently ask the same unanswered question (SEC-32 "was it sent", INT-13 "was
  the E-group notification sent", INT-25 "was the org notification actually sent"), which is itself evidence
  the answer is no. A second obligation rides here: **§7-R1's org sign-off is orphaned.** The
  password-HMAC key and write-capable database credentials live committed in the production repository's
  permanent history, so repository plus network access lets an attacker set a known password hash and log
  into the new apps as that user — accepted as **permanent**, "to be signed off by the org at S42", an
  occasion D-152 freezes, with no completion visible; §7-R1 occurs exactly once, at
  `INTEGRATION_PLAN.md:513`, and a `sign.off|signed off` grep returns nine hits, none about R1. A
  compounding fact: rung 1 — the confirmed viable data path — makes **I14's password-hash-fingerprint
  revocation check impossible**, so R1's named mitigation is unavailable **by design**, not merely unbuilt.
  Third, R8/R9's expiry conditions have **no monitor**, and one of their two homes drops the expiry text
  entirely. A severity rider: production's 6-digit `accounts.code` (one INTEGER column serving both email
  verification and password reset, generated with `Math.random`, no server-side expiry despite the email
  claiming 20 minutes, no rotation after use, no rate limiting) is graded **Medium** in the outgoing report
  while `INTEGRATION_PLAN.md` §7-R3 carries the same fact as a **permanent account-takeover residual
  risk** — and the grade would be corrected *before* sending, not after.
- **Domain:** security / integration / real-world obligation
- **Original source(s):** `CLAIM_LEDGER.md:1574`, `:1587`, `:1600`, `:2548`, `:2704`, `:2743`, `:2808`;
  `REPOSITORY_DRIFT_REGISTER.md:57-66`, `:68-77`; `S42_SECURITY_REPORT.md:1-30`, `:144-153`,
  `:167-170`; `INTEGRATION_PLAN.md:500-517`, `:518-520`, `:535`, `:551-565`;
  `ARCHITECTURE.md:605-609`; `S42_OPEN_QUESTIONS.md:39-40`, `:94-104`, `:108-113`;
  `DECISIONS.md:8928-8931`, `:9000-9005`, `:9105-9109`, `:9156-9160`
- **Related claim IDs:** SEC-28, SEC-29, SEC-30, SEC-31, SEC-32, SEC-33, INT-13, INT-25, INT-28, INT-33,
  INT-21, INT-30
- **Related decision IDs:** D-151, D-152, D-153 §5/§7, §7-R1, §7-R2, §7-R3, §7-R8, §7-R9, I14, E1–E4,
  INT-28's freeze exception
- **Repository evidence:** the documents represent the action as open **correctly**; what is missing is the
  action itself and any field that would make its absence visible. The client-supplied-role finding moved
  from *accepted* to *to be fixed by the org*, joining §6.1/§6.3/§6.4 on the list the user will send, with
  a prescribed fix inside the existing system (allowlist `Parent`/`Student`/`Tutor` at create with a 400
  otherwise, accept no role in the duplicate-unverified branch, keep `Manager` a database/admin
  operation). `ARCHITECTURE.md:605-609` reproduces R8/R9 **without the expiry text**, and INTEGRATION_PLAN
  is unindexed while ARCHITECTURE is the file sessions are told to update.
- **Deployed/live evidence:** not reachable — a send is an out-of-band real-world act, explicitly outside
  every audit lane's surface, and the report has no tracked side at all.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-8**
- **Justification:** **whether the report was ever sent is unestablished** — the E3-3-versus-E1-42 split is
  ruled that way rather than assumed either direction. Sending is an external org action only the user can
  take (HITL rule 4), and **INT-28 establishes it is PERMITTED under the freeze**, so this is **live user
  work, not parked**. It is the highest real-world-consequence item in the register: findings about a
  system serving real users today, sitting in a draft.
- **Remaining action:** the user confirms or authorizes sending the production security report, and decides
  who owns the R1 sign-off now that its occasion is frozen and who owns R8/R9 expiry monitoring. Add a
  one-line **send-status field** to the report so absence is visible. Harmonise the 6-digit-code severity
  across the outgoing report and the residual-risk register **before** sending. **Riders:** the ORG_TIME
  hours one-message ask (`ARCH-35-ORG-TIME`) and the enrollment-FAQ approval nudge (`INT-29-FAQ`) — note
  they have **different audiences** (system operator versus content owner) and must not be bundled. The
  ARCHITECTURE.md copy losing R8/R9's expiry qualifier is a separable documentation fix that should **not**
  wait on the ownership decision (`RISK-R2.2-ACCEPTED-RISK-HOMES`); the R8/R9 monitoring substance is
  cross-referenced to `R8-READ-SCOPE` and `KPI-ALARM-FLOOR`. The `:110` action list must **not** be
  blanket-retired: the E-group notification half is genuinely still valid.
- **Owner type:** user, then external-org
- **Reopen condition:** n/a — open now, and permitted under the freeze
- **PROJECT_STATE?** yes — top of the user-facing list · **Historical/archive only?** no

### `ARCH-35-ORG-TIME` — `ORG_TIME_CONFIRMED = false` in the deployed build, and the durable guard is owed at a frozen session

- **Work/Issue ID (topic key):** `ARCH-35` (chain G5 / D-153 §4)
- **Members:** E5-25, E2-16
- **Description:** All three `ORG_TIME` env vars are present on both task definitions with identical values
  — `ORG_TIMEZONE = America/Chicago`, `ORG_TIME_CONVENTION = local_dst_aware`, and
  **`ORG_TIME_CONFIRMED = false`**. The flag exists precisely to mark the org's operating hours as
  **unconfirmed**, and the deployed build still says they are. Anything time-of-day dependent (calendar,
  branch hours, scheduling copy shown to students or parents) is running on assumed hours, and the zone is
  still inferred from someone else's hard-coded −6. The time-convention question was closed *by evidence*
  (the org runs neither the Sunday-evening nor the 00:00–01:00 window, so all conventions agree), but
  D-153 §4's durable form is a **guard owed at S43** — assert no session starts 00:00–01:00 local or Sunday
  evening, and log loudly — and S43 is frozen, so the guard is presumptively unbuilt and nothing read
  confirms it exists.
- **Domain:** configuration / time handling / external dependency
- **Original source(s):** `DEPLOYED_INFRA_STATE_EVIDENCE.md:257-267` (ARCH-35);
  `DECISION_SUPERSESSION_MAP.md:1026-1041`
- **Related claim IDs:** ARCH-35
- **Related decision IDs:** D-130, D-152, D-153 §4, D-324, D-417 §A1
- **Repository evidence:** all three set at `terraform/environments/staging/main.tf:497-499` (learning) and
  `:582-584` (chat), with `ORG_TIME_CONFIRMED = var.org_time_confirmed ? "true" : "false"` — the mechanism
  to flip it exists and is unused.
- **Deployed/live evidence:** the flag is `false` on both services. Deployed **matches** the repository; the
  gap is that the underlying real-world fact has never been confirmed by the org.
- **Final disposition:** `BLOCKED` — on an answer from the organization
- **Justification:** included because it is a **live `false` in production-shaped configuration**, which is
  easy to mistake for a stale default. Consistent with D-152 it stays parked, but it belongs on the list of
  things the org must answer before integration rather than being lost in an env-var diff.
- **Remaining action:** **rider on UD-8** — a one-message ask ("are these your operating hours?") whose
  answer flips one variable; cheap and worth batching with any other org-facing question. **Important
  note:** the D-153 §4 guard is a **local assertion, not an integration measurement** — it asserts against
  the org's own published sessions — so it is **buildable now without integration**, and "frozen" may be
  over-applied here. That is the one low-risk win in this section.
- **Owner type:** external-org (the answer), user (the ask), engineering (the guard, buildable now)
- **Reopen condition:** the org answers, or the user authorises building the guard early.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `INT-29-FAQ` — the enrollment FAQ is still `draft` and is the sole launch gate on the guest journey's canonical question

- **Work/Issue ID (topic key):** `INT-29`
- **Members:** E1-81 (INT-29), E6-36
- **Description:** The Q&A app's canonical guest question "How do I enroll a student?" **refuses to answer
  on purpose**, because the only covering document `public-enrollment-faq` is synthetic **draft** content.
  Four draft claims need the org content owner's sign-off; on approval the action is **editorial only**
  (correct four facts, drop the DRAFT banner, flip `status: draft → approved`, re-run
  `make knowledge-load`) and `effective_from` is already past, so it goes live immediately. The core
  premise was **verified still true**: the manifest still reads `draft` (checked against
  `knowledge-content/manifests/public.yaml`). The file claims to be "the only launch-checklist item gating
  the guest journey's canonical question" (`:88-89`) and is **not in CLAUDE.md's index**, so it is invisible
  at session start despite that claim. Two dead pointers: the manifest line-number pointer, and the deleted
  `knowledge-content copy/` directory.
- **Domain:** content approval / launch checklist / org communication
- **Original source(s):** `CLAIM_LEDGER.md:2756`; `ENROLLMENT_FAQ_APPROVAL.md:1-28`, `:86-94`;
  `DOCUMENT_INVENTORY.md:665-684`
- **Related claim IDs:** REQ-14, INT-13, INT-25, INT-29
- **Related decision IDs:** D-146, D-253 (the deleted directory)
- **Repository evidence:** the manifest entry is `draft`; the post-approval procedure is written out and
  editorial.
- **Deployed/live evidence:** the guest RAG path **answered a public question with 1 citation** in the live
  phase, so the deployed corpus serves the canonical question from *some* approved source — whether that is
  the synthetic draft or another document **is not established here**. Whether the deployed knowledge store
  still holds the FAQ as `status: draft` is a database-content read (`DB-CONTENT-VERIFY`), routed to
  forbidden, so **the substance is unresolvable by any phase**: a draft, unapproved FAQ in the deployed
  store is a fail-closed question no phase could answer.
- **Final disposition:** `BLOCKED` — on the org's content owner
- **Justification:** nothing in this codebase can close it, and it is **not frozen** by D-152: it is content
  approval, not a Tier-1 integration ask. The highest-value, lowest-effort user action in the integration
  domain — the post-approval work is editorial and it unblocks the product's most obvious guest question.
- **Remaining action:** **rider on UD-8** — the user decides whether and when to send the approval request,
  noting the audience is the **content owner**, not the system operator, so it must **not** be bundled with
  the security report or the timezone/DNS asks. Two cheap follow-ups: verify which source the deployed guest
  answer actually cited before accepting the "sole launch gate" claim (a free check no phase ran), and fix
  the two dead pointers (`RISK-R7.3-DANGLING-REFS`). Add the file to CLAUDE.md's index
  (`RISK-GROUP-INDEX`).
- **Owner type:** external-org (the approval), user (the send)
- **Reopen condition:** the org content owner answers.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `D152-FREEZE` — integration is closed until the user reopens it

- **Work/Issue ID (topic key):** `D-152` (chain G1)
- **Members:** E2-12 (chain G1), E7-7, E1-93 (WORK-10), E1-99 (WORK-16)
- **Description:** D-152's sequencing decision — finish and test against the dev fakes first — is
  reconfirmed **verbatim** by D-417 §A1 on 2026-08-18: "D-152 is unchanged and is not 'nearly met' — it is
  closed until reopened." Its §5 prohibitions are live: no reachability measurement, no production API URL,
  no test account, no finalizing the §3.1 auth option, no rewriting the MySQL dev fake. The user
  **reconfirmed it after being told the audit lists were empty and the suite green**, so the "finish and
  test first" condition is explicitly **not** treated as met — no amount of verification can trigger the
  unfreeze. ROADMAP marks S42–S47 "⛔ DEFERRED BY USER DECISION (D-152)" and "frozen by choice, not
  blocked", with S42's source half done; **the S48–S51 rollout block (production environment, real
  credentials, A7 close-out, pilot) carries no such banner** and is simply unstarted downstream work.
  D-418 through D-423 are, in order, an infra check correction, a Terraform apply, three chat-escalation
  commits and a latency measurement — **none** references integration, `icrest`, the production API URL, a
  test account, the §3.1 auth option or the MySQL dev fake's schema.
- **Domain:** sequencing / integration posture
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:832-833`, `:848-851`, `:858-861`;
  `CLAIM_LEDGER.md:2968`, `:3046`; `DECISIONS.md:28266-28271`; `OPEN_DECISIONS.md:20`, `:634-635`;
  `ROADMAP.md:1438-1446`, `:1512-1521`
- **Related claim IDs:** INT-03, INT-04, INT-05, INT-06, WORK-10, WORK-16, WORK-17
- **Related decision IDs:** D-151, D-152, D-153, D-417 §A1, S42–S51, I1–I15
- **Repository evidence:** the freeze is the active decision and the authority for dispositioning every
  INT-* item; the one engineering obligation *during* the freeze is keeping the `ProfileAdapter` seam
  honest. D-151's heading still reads plain `accepted` while two of its load-bearing recommendations
  (fix-the-fake urgency; O1b as the pre-S44 decision) have been withdrawn or demoted.
- **Deployed/live evidence:** n/a — no integration surface exists. No reachability measurement was taken,
  correctly.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** frozen **by choice, not stuck**. The freeze is deliberately insulated from technical
  evidence, and only the user reopens it; the brief and CLAUDE.md both forbid soliciting that. It is the
  *reason* `F2-ADAPTER-SHAPE`, `F3-DEVTOKEN-S44`, `R8-READ-SCOPE`'s closure path, `ARCH-35-ORG-TIME`'s
  guard, `S43-SCOPE` and `AUTH-OPTION-O1B` cannot progress, and those must be attributed to this decision
  rather than to an obstacle.
- **Remaining action:** none. Keep the freeze; keep the seam honest. **Asymmetry worth recording:** S45
  (consent and the first-visit notice) is **inside** the freeze while S50 A7 (GuardDuty, WAF) is **not**,
  so two launch-blocking security items sit in an unfrozen-but-unstarted block and one launch-blocking
  privacy item sits in a frozen one. The freeze's *visibility* problem — it is absent from the documents it
  binds — is `RISK-GROUP-FREEZE`.
- **Owner type:** user (to reopen)
- **Reopen condition:** an explicit user statement reopening integration. Not met, and no evidence can meet
  it.
- **PROJECT_STATE?** yes — the parked list's governing entry · **Historical/archive only?** no

### `S43-SCOPE` — S43's scope is known, and rewriting the dev fake is forbidden

- **Work/Issue ID (topic key):** `S43-SCOPE` (WORK-17 / INT-35)
- **Members:** E1-100 (WORK-17), E1-83 (INT-35)
- **Description:** S43's scope is known from D-151 but handled only when S43 runs: the MySQL dev fake models
  a system that does not exist (**six structural mismatches**, so "a green contract test against today's
  fake is evidence about a fiction"); `IcProfileAdapter` is to be built against production-shaped fixtures
  rather than by extending the fake; the mismatches provably stay behind the `ProfileAdapter` Protocol seam
  because the Protocol types are **SPEC-derived, not fake-derived**; and production `role` must never by
  itself grant an elevated role here, because pre-fix rows may already carry a self-assigned `Manager`.
  D-152 **withdrew** the fix-the-fake urgency: rewriting now would be work months before first use against
  a schema `sync({alter:true})` can still move.
- **Domain:** integration / adapter design
- **Original source(s):** `CLAIM_LEDGER.md:2834`, `:3059`; `S42_DISCOVERY.md:324-342`;
  `DECISIONS.md:8933-8942`, `:8959-8976`; `CLAUDE.md:64-68`; `ROADMAP.md:1469-1497`
- **Related claim IDs:** INT-12, INT-24, INT-35, SEC-34, ARCH-18, ARCH-20, TEST-27, WORK-17
- **Related decision IDs:** D-002 (the seam), D-151 §6, D-152 §1, D-153, I3–I7, I12, I15
- **Repository evidence:** the Protocol types are SPEC-derived; the fake's shape is wrong on purpose.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** an explicit user withdrawal with a verified rationale and detailed frozen scope; no
  evidence owed. Note the tension worth checking: INT-07 records "S43 partly in progress per D-154" against
  WORK-16's "S43–S47 frozen".
- **Remaining action:** none, **except one standing obligation that is genuinely active**: the
  **seam-honesty check**. CLAUDE.md makes anything that would make an app-level decision depend on the
  fake's *schema* a **real defect**, so this is a standing verification rather than a parked row. One known
  housekeeping instance is `DRIFT-91-ORGTIME-IMPORT`.
- **Owner type:** user (to reopen); engineering for the standing seam check
- **Reopen condition:** S43 opens.
- **PROJECT_STATE?** yes — parked, with an active standing check
- **Historical/archive only?** no

### `AUTH-OPTION-O1B` — O1b stays a recommendation until measured, right before S44

- **Work/Issue ID (topic key):** `INT-05`
- **Members:** E1-68
- **Description:** `S42_DISCOVERY.md` §8 recommends **O1b** (a server-side call to
  `POST /api/accounts/login`, a transient header-borne legacy token for `GET /api/accounts` and
  `GET /api/accounts/signups`, then the new stack minting its own SPEC §5.1.2 token) with **O2** (HMAC
  re-verification) as the documented fallback, and says of itself "This is a recommendation, not a
  decision." CLAUDE.md adds that it **stays one until measured, right before S44**.
- **Domain:** integration / authentication
- **Original source(s):** `CLAIM_LEDGER.md:2444`; `S42_DISCOVERY.md:37-42`, `:301-322`;
  `CLAUDE.md:59-61`; `DECISIONS.md:8889-8891`
- **Related claim IDs:** INT-05, INT-06, INT-20, INT-31, REQ-27
- **Related decision IDs:** D-151 §2, O1/O1b/O2/O3/O4, A4, B1, B2, I11 rung 1
- **Repository evidence:** the option matrix is intact and remains useful reference material.
- **Deployed/live evidence:** the evidence it needs — B1 (AWS→icrest reachability) and B2 (deployed build
  matches checkout) — is exactly what D-152 forbids measuring now.
- **Final disposition:** `PARKED_BY_DECISION`
- **Justification:** explicitly frozen by D-152 and CLAUDE.md; **measuring it now is the specific act the
  instructions forbid**. One framing conflict is worth one line so the register does not later read
  `S42_OPEN_QUESTIONS` A4 as an outstanding user ask: A4 labels it "a decision pending from the user" while
  the source document calls itself a recommendation.
- **Remaining action:** none. At integration, take B1 and B2 first, then finalise the option.
- **Owner type:** user at integration
- **Reopen condition:** integration start (immediately before S44).
- **PROJECT_STATE?** yes — parked · **Historical/archive only?** no

### `F2-ADAPTER-SHAPE` — direct MySQL versus an HTTP API is still the open seam decision, with rung 1 confirmed viable

- **Work/Issue ID (topic key):** `F2` (chain F2; INT-20 / ARCH-20)
- **Members:** E2-2 (chain F2), E1-23 (ARCH-20), E1-77 (INT-20)
- **Description:** D-082's own carve-out — "still unconfirmed: direct MySQL vs. HTTP API fronting it" —
  survives D-083, D-111 §4 and everything after, and is **answered nowhere in the chain**. This is the seam
  decision the entire `ProfileAdapter` Protocol is designed to absorb. Partial progress exists: I11 frames
  data access as a **four-rung ladder** descended only as far as discovery forces (API-only; hybrid API
  plus read-only database; database-only; org-operated snapshot replica), and §8 records **rung 1 confirmed
  viable** — signups returns `attended`, scoped to the caller — so the Tier 1 database ask is off the
  critical path and rungs 2–4 remain documented fallbacks. The target-state PII row is the real
  `go.intellichoice.org` MySQL, read-only via `ProfileAdapter`, and that row lives only in a 2026-07-21
  projection document that was never regenerated.
- **Domain:** integration architecture / data access
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:494-502`; `CLAIM_LEDGER.md:972`, `:2639`;
  `INTEGRATION_PLAN.md:369-393`, `:598-603`; `S42_DISCOVERY.md:39-42`;
  `FINAL_ARCHITECTURE.md:154-161`, `:169-174`
- **Related claim IDs:** ARCH-19, ARCH-20, ARCH-22, INT-05, INT-14, INT-20, INT-21, INT-35, SEC-33
- **Related decision IDs:** D-002, D-082, D-083, D-111, D-152, I11, O1b, O2, A1, C4, C9, R5
- **Repository evidence:** the Protocol seam absorbs the difference by design; INT-20's rung-1 confirmation
  answers the *open question* the ARCH-20 row poses, so that row is SUPERSEDED as written while the seam
  decision itself remains open.
- **Deployed/live evidence:** n/a — and the **safety-relevant half of ARCH-20's evidence line is worth
  keeping**: "confirm no real-system connectivity or credential exists" is a live D-152 compliance check.
- **Final disposition:** `DEFERRED`
- **Justification:** a real open architectural question, deliberately not decided until integration — and
  exactly one of the items D-152 §5 forbids finalizing. It must **not** be surfaced as "unblock
  integration" work.
- **Remaining action:** none now. At integration: take B1 reachability; if it fails, switch immediately to
  O2 / rung ≥ 2 and the C4/C9 database asks start then. **Two consequences of rung 1 are easy to lose:** it
  makes **I14's password-hash-fingerprint revocation check impossible** (so `ORG-COMMS`'s R1 mitigation is
  unavailable by design), and it makes **I6's manager-email SQL lookup unavailable**, forcing a
  new-stack-owned branch→manager-email configuration table — **unbuilt work nobody owns**.
- **Owner type:** user + engineering at integration
- **Reopen condition:** integration start.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `F3-DEVTOKEN-S44` — the whole staging `/dev/token` path is scheduled for deletion at a frozen session

- **Work/Issue ID (topic key):** `F3` (chain F3)
- **Members:** E2-3
- **Description:** The active auth path (D-097 as amended + D-167 localStorage persistence + D-310's
  in-process secret fetch) is explicitly temporary — D-097 states the whole path is **"Deleted at S44"** —
  and S44 sits behind the D-152 freeze, with D-085's second gate and the settings-driven JWT secret still
  in force. Two hygiene facts inside the chain: D-085 still reads as closed although D-096 and D-167 both
  record it as **falsely closed for two days**, and D-310's status value is free prose outside the declared
  enum.
- **Domain:** authentication / staging security posture
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:553-572`; corroborated by
  `REMEDIATION_D310_ROTATION.md:115-116` ("the `main.tf:355-360` S44 plan … is unchanged")
- **Related claim IDs:** SEC-25, SEC-26, SEC-35
- **Related decision IDs:** D-006, D-085, D-096, D-097, D-152, D-167, D-310, D-388
- **Repository evidence:** the S44 deletion plan at `terraform/environments/staging/main.tf:355-360` is
  unchanged; `*_DEV_TOKEN_ENDPOINT_ENABLED=false` confirms the shared-secret path is the live one.
- **Deployed/live evidence:** both apps carry the shared-secret path; the secrets themselves were rotated
  (`D310-ROTATION`).
- **Final disposition:** `DEFERRED`
- **Justification:** the deletion is **owed work with a named trigger** (S44) that the freeze currently
  withholds — decided, not undecided.
- **Remaining action:** none now; delete the path at S44. Nothing is asked of the user unless they want the
  temporary path hardened further while the freeze persists — and the rotation already did the one
  hardening that was on the table. The two status-hygiene facts are members of
  `RISK-GROUP-DECISIONS-HYGIENE`.
- **Owner type:** engineering at S44
- **Reopen condition:** S44 opens.
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `SEC-34-ROLE-ALLOWLIST` — the our-side Tutor/Manager allowlist is asserted and not yet designed

- **Work/Issue ID (topic key):** `SEC-34` (INT-12)
- **Members:** E1-44 (SEC-34), E1-72 (INT-12)
- **Description:** Even if the org fixes the self-assignable-role finding, this stack must still gate
  `Tutor`/`Manager` behind an allowlist **we** control, on three grounds: pre-fix rows may already carry a
  self-assigned `Manager`; production is frozen and schema-drifting via `sync({alter:true})`; and
  authorization is not delegated to another system's input validation. Standing assumption A2: role
  strings match four known values, and unknowns **fail closed** with a metric (I7). Student and Parent may
  be mapped; the allowlist does **not relax** if the org fixes role validation.
- **Domain:** integration / authorization
- **Original source(s):** `CLAIM_LEDGER.md:1613`, `:2535`; `S42_SECURITY_REPORT.md:167-170`;
  `INTEGRATION_PLAN.md:521-522`, `:572-573`; `S42_DISCOVERY.md:238-241`;
  `S42_OPEN_QUESTIONS.md:33-37`; `DECISIONS.md:9115-9120`, `:9162-9170`
- **Related claim IDs:** SEC-09, SEC-34, INT-11, INT-12, INT-18, INT-24, INT-30
- **Related decision IDs:** D-153 §5/§7, §7-R4, A2, I7, I12, CLAUDE.md rule 3, S43/S44
- **Repository evidence:** the constraint is present and consistently stated in four documents, and ROADMAP
  carries a ⛔ sub-block reproducing all three grounds verbatim, closing with "Map Student/Parent from
  production; gate `Tutor`/`Manager` behind an allowlist the new stack controls". **No allowlist schema,
  storage or admin path is specified anywhere.**
- **Deployed/live evidence:** n/a — nothing to build against until integration.
- **Final disposition:** `DEFERRED`
- **Justification:** a correct, binding S43/S44 constraint with nothing to build until integration; the only
  owed artifact is that the allowlist actually appears in S43/S44 material when it is written. The
  register's own tension is worth carrying: "authorization is ours to decide" is asserted while
  `R8-READ-SCOPE`'s read path is knowingly open, so the principle and the practice disagree today.
- **Remaining action:** none now. When S43/S44 material is written, confirm the allowlist is designed into
  it. The I7 metric's missing specification is `DRIFT-85-I7-ALLOWLIST`.
- **Owner type:** engineering at S43/S44 · **Reopen condition:** S43/S44 opens
- **PROJECT_STATE?** yes · **Historical/archive only?** no

### `INT-ATTENDANCE-DERIVATION` — `attendanceClaimed` is a fail-open trap, and the signups response is PII-bearing

- **Work/Issue ID (topic key):** `INT-15` (with INT-17)
- **Members:** E1-74 (INT-15), E1-75 (INT-17)
- **Description:** `signups` has **two** attendance columns — the manager-recorded nullable `attended` and
  the non-null self-reported `attendanceClaimed`. S43 must **never** gate an exam on `attendanceClaimed`
  ("the convenient field precisely because it is never null"); **only `attended === true` means present.**
  Separately, the signups response carries `firstName`, `lastName` and the full `children`, so it must be
  projected to external ids **at the adapter boundary** before anything is returned, logged, traced or
  cached. The derivation of "present this week" is a `signups` row with `attended = true` joined to a
  non-deleted `calendars` row whose `startTime` falls in the current org-local week, with three hazards:
  `attended = null` means never-marked and must be treated as **not present**; the `children` include has
  **no `deleted: false` filter**, so soft-deleted children come back; and the week-boundary derivation is
  where the timezone question bites.
- **Domain:** integration / attendance gating / PII boundary
- **Original source(s):** `CLAIM_LEDGER.md:2574`, `:2600`; `INTEGRATION_PLAN.md:55-57`, `:325-331`,
  `:586-588`, `:609-613`; `S42_DISCOVERY.md:75-82`; `DECISIONS.md:8893-8895`
- **Related claim IDs:** INT-08, INT-14, INT-15, INT-17, INT-23, REQ-12, REQ-13, SEC-01
- **Related decision IDs:** D-099, D-151 §2, D-152 §2, D-153 §4, I3–I5, S43
- **Repository evidence:** binding S43 constraints with nothing to build now. **One documentation defect is
  fixable immediately and has high consequence:** `INTEGRATION_PLAN.md` §1 describes **one** attendance
  column, and §1 is what a reader meets first — reading `attendanceClaimed` as attendance would fail
  **open** against CLAUDE.md rule 5.
- **Deployed/live evidence:** n/a — no adapter code exists yet; verification is "no adapter or derivation
  code reads `attendanceClaimed`" once S43 code exists.
- **Final disposition:** `DEFERRED`
- **Justification:** well-specified frozen work. The timezone hazard is reduced but not eliminated by
  D-153 §4's guard (`ARCH-35-ORG-TIME`).
- **Remaining action:** correct `INTEGRATION_PLAN.md` §1's single-column description **now** — a small edit
  with a fail-open consequence. At S43, verify nothing reads `attendanceClaimed` and that the adapter
  projects to external ids at the boundary. **Carry the one production fact CLAUDE.md says must inform
  product work now:** `attended = null` is **routine**, so `AttendanceStatus.UNKNOWN` → blocked is a
  routine path — confirm the product copy for a blocked start reads "routine", not "error".
- **Owner type:** documentation now; engineering at S43
- **Reopen condition:** S43 opens. · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `COMMITTED-ORG-DRAFTS` — three committed outbound drafts against a stated no-committed-drafts rule, with opposite credential policies

- **Work/Issue ID (topic key):** `COMMITTED-ORG-DRAFTS` (from risk R7.2; normalized 2026-08-20 at migration step 9c — the entry key is the topic key, and `R7.2` is the documentation-risk id)
- **Members:** E6-31
- **Description:** `INTEGRATION_PLAN.md:619` states that outbound communication drafts are kept "outside
  this repo (gitignored … not committed)". **Three committed drafts exist**: `S42_ORG_ASKS.md`,
  `S42_SECURITY_REPORT.md`, `ENROLLMENT_FAQ_APPROVAL.md`. Either the rule was silently superseded or the
  files violate it, and **no document says which**. The two org-facing S42 drafts also implement
  **opposite policies** on mentioning the committed-credentials issue: `S42_ORG_ASKS.md:366-371` excludes
  it from any sent message, while `S42_SECURITY_REPORT.md:88-89`/`:151-153` includes it as known context.
- **Domain:** outbound-communication policy
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:405-411`; `DOCUMENT_INVENTORY.md:790-792`,
  `:806-809`
- **Related claim IDs:** SEC-32, SEC-33, INT-13, INT-25
- **Related decision IDs:** D-153 §5/§7; CLAUDE.md's never-quote-the-secret rule
- **Repository evidence:** the rule and the three files, as cited. **Neither draft quotes secret values**,
  so this is a policy inconsistency rather than an exposure — but the drafts are committed to a repository
  and one of them discusses a credential exposure.
- **Deployed/live evidence:** n/a — documentation, with a real security-hygiene edge.
- **Final disposition:** `USER_DECISION_REQUIRED` → **UD-12(f)**
- **Justification:** whether committed drafts are allowed, and which credential-mention policy governs a
  **sent** message, are both about what leaves the project — the user's calls, not editorial ones.
- **Remaining action:** one ruling. If the user rules quickly, the documentation half collapses to one
  sentence in `INTEGRATION_PLAN.md` and one in each draft. Pair with `ORG-COMMS` (UD-8), since the
  credential-mention policy decides content of a message the user is about to send.
- **Owner type:** user, then documentation
- **Reopen condition:** n/a — open now · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `DRIFT-91-ORGTIME-IMPORT` — an app module imports `current_week_key` from the MySQL adapter rather than from shared `org_time`

- **Work/Issue ID (topic key):** `DRIFT-91` (INT-35 / INT-15 / INT-32) — batch B exception
- **Members:** E3-55:DRIFT-91
- **Description:** One app module imports `current_week_key` from the **MySQL adapter module** rather than
  from shared `org_time`, and writes its value as the `week_id` into Postgres. Both apps also construct
  `MySQLProfileAdapter` directly in `main.py` rather than behind a factory. The seam's substance is intact
  and adjudicated confirmed: zero raw-SQL or table-name hits in `apps/`, all 21 app-level sites go through
  Protocol methods, and attendance is coerced at the seam.
- **Domain:** integration seam hygiene
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:1034` (DRIFT-91)
- **Related claim IDs:** INT-15, INT-32, INT-35
- **Related decision IDs:** D-082, D-083, D-152 §1
- **Repository evidence:** as described; a two-line module move plus, optionally, an adapter factory.
- **Deployed/live evidence:** n/a — repo-only.
- **Final disposition:** `ACTIVE_REMEDIATION` — **batch B exception** (it is code, not prose)
- **Justification:** housekeeping, and the distinction must be preserved: the value is org- and
  SPEC-derived and the seam's substance is intact, so this is **not** the class of defect CLAUDE.md calls a
  real defect (an app-level decision depending on the *fake's schema*). It is the only batch-B member where
  the seam-honesty rule is in play at all.
- **Remaining action:** move the import to shared `org_time`; optionally add an adapter factory.
- **Owner type:** engineering · **Reopen condition:** n/a · **PROJECT_STATE?** yes
- **Historical/archive only?** no

### `DRIFT-85-I7-ALLOWLIST` — the I7 unknown-role metric is named as an invariant's evidence and specified nowhere

- **Work/Issue ID (topic key):** `DRIFT-85` (SEC-34 / INT-12) — batch F exception
- **Members:** E3-59:DRIFT-85
- **Description:** The I7 unknown-role metric is named as the evidence for a fail-closed invariant, with
  **no plan text anywhere in the S43 scope**. The constraint itself is present and consistently stated in
  four documents, and ROADMAP carries a ⛔ sub-block reproducing all three grounds verbatim — but **no
  allowlist schema, storage or admin path is specified**, and I7 appears only as an id, with no I7 metric
  plan text in the S43 region.
- **Domain:** authorization / observability specification
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:968` (DRIFT-85)
- **Related claim IDs:** SEC-34, INT-12
- **Related decision IDs:** D-153 §5
- **Repository evidence:** the invariant is stated; its evidence mechanism is a bare id.
- **Deployed/live evidence:** n/a — S43 is frozen.
- **Final disposition:** `BLOCKED` — **batch F exception**
- **Justification:** its content belongs to frozen S43 work under D-152; the missing allowlist and metric
  specification cannot be written without starting integration, which D-152 forbids. Nothing is asked of
  the user now.
- **Remaining action:** none now. It is a **"named-but-unspecified" pattern worth generalising** — an
  invariant whose evidence is a metric id that nothing specifies — the same family as DRIFT-10 (a metric
  without an alarm) and DRIFT-04 (an expiry without a monitor).
- **Owner type:** engineering at S43 · **Reopen condition:** S43 opens
- **PROJECT_STATE?** yes · **Historical/archive only?** no

---

## §9 Documentation & decision-log hygiene

*Grouped entries. Member lists are preserved verbatim from E3's LOW batches and E6's risk groups, so
each batch can be decomposed if a member needs handling individually. Batch exceptions per the
adjudication have their own entries in the domain sections and are cross-referenced here. Two batches
(E and F) carry non-documentation dispositions and are kept here anyway so their member lists stay
intact.*

### `AMENDMENT-SWEEP` — SPEC carries no amendment marker at nine points of departure

- **Work/Issue ID (topic key):** `§8-01` (the amendment-layer problem)
- **Members:** E1-128 (§8-01), E3-26 (DRIFT-26), E3-27 (DRIFT-27), E3-28 (DRIFT-28 SPEC half),
  E3-32 (DRIFT-32), E3-33 (DRIFT-33), E3-34 (DRIFT-34), E3-35 (DRIFT-35, the five-claim family),
  E3-15 (DRIFT-15), E3-16 (DRIFT-16), E1-16 (REQ-49), E1-14 (REQ-37), E1-26 (ARCH-23),
  E1-27 (ARCH-24), E1-28 (ARCH-25), E1-114 (WORK-31)
- **Description:** The single largest class in the corpus is structural, not factual: SPEC.md is treated as
  the requirement source of truth, later decisions are recorded in DECISIONS.md, and **SPEC carries no
  amendment marker at the point of departure** — so nine strands read as current requirement to anyone
  who opens SPEC alone: the deployment substrate (§5.33 prescribes AWS Organizations, EKS with
  Karpenter/HPA/PDB/NetworkPolicy/IRSA and Aurora Multi-AZ; a grep across terraform for
  `eks|kubernetes|aurora|karpenter|aws_organizations` returns **zero resource hits**, only two comments
  explicitly rejecting the model), the scaling mechanisms (§5.33.4's five HPA signals plus SQS worker
  scaling against **exactly one** live signal per service, ALB p95, and **zero SQS resources**), the
  placement table (§5.36 still names Kubernetes → EKS), question volume (§5.8.1's "100 validated base
  templates per topic" against D-223's 5–7 per occupied tier — a ≈3.4× divergence in **content spend**),
  solution images (§5.17 and CLAUDE.md rule 8 over an unbuilt feature), observability (§5.32.1's
  "choose one" fork decided by D-214/D-242), the auth menu (§5.2.2, frozen by D-152), internal NL2SQL
  (§5.26.3), the gateway surface (§5.25.1's ten features, two absent), the component table (§5.5.2 declares
  Topic Resolver "Structured LLM" where it is deterministic by D-024, and Tutor Summary Generator
  "Structured service" where it uses the same LLM report path), the state shape (§5.19.3 says ~40
  `LearningState` fields where the code has **32** by AST parse, and `QAState.ephemeral_location` **does
  not exist** — the code is right and both SPEC and a stale in-code comment are the drift), the payload
  allowlist (§5.30.1's seven-field list describes exactly **one** of 23 Bedrock payloads; the **denylist
  half fully holds** — none of the seven forbidden names appears in any payload model), the study-plan
  priority order (§5.11.2 rule 4 deliberately inverted in code with a measured reason: 57 of 201 study
  items repeated a question, 40 at the very first item), the post-exam parallel form (§5.13 forbids reusing
  a variant; ROADMAP records post-exam "knowingly repeats an authored item"; composition moved from "2 per
  tier 1-5" to "10 total" per D-302), the interrupt list (§5.1.4 enumerates six interrupt-gated actions and
  **two of the six have nothing to gate** — no image-analysis interrupt exists, and no gate distinct from
  `email_approval` exists for "sensitive information in an email"; CLAUDE.md's four-action list is
  **closer to the code** than SPEC's six), and §5.29's failure matrix (**no dead-letter queue** — zero hits
  for `dead.letter`/`dead_letter`/`DLQ` and zero `sqs` resources — and **no smaller-model fallback**; the
  timeout path is bounded retry against the *same* `model_id`, then `_record_failure()` → circuit open, so
  **degradation is binary**). SPEC's **only** in-text amendment marker in 4,210 lines is at `:1973`, for an
  unrelated section.
- **Domain:** documentation integrity / SPEC governance
- **Original source(s):** `CLAIM_LEDGER.md:3432-3470`, `:513`, `:669`, `:1011`, `:1024`, `:1037`,
  `:3241`; `REPOSITORY_DRIFT_REGISTER.md:191-200`, `:202-211`, `:312-321`, `:323-332`, `:378-387`,
  `:389-398`, `:400-409`, `:411-425`
- **Related claim IDs:** ARCH-08, ARCH-23, ARCH-24, ARCH-25, REQ-01, REQ-06, REQ-10, REQ-11, REQ-16,
  REQ-17, REQ-19, REQ-21, REQ-22, REQ-28, REQ-35, REQ-37, REQ-43, REQ-49, REQ-51, REQ-52, SEC-03,
  SEC-05, SEC-06, SEC-14, SEC-15, COST-02, COST-27, INT-05, INT-06, WORK-31
- **Related decision IDs:** D-004, D-020, D-022, D-023, D-024, D-045, D-071, D-072, D-078, D-115,
  D-152, D-175, D-189, D-214, D-219, D-223, D-242, D-302, D-325, D-402
- **Repository evidence:** every strand's absence or divergence is confirmed by grep or AST parse, and
  several are executed rather than read: F-17 converts §5.29's two absences from an auditor's grep to an
  executed one, and REQ-52's 32 is tool-derived.
- **Deployed/live evidence:** two strands are contradicted by the **deployed** reality rather than by the
  repository: §5.33's EKS/Aurora topology against live ECS/RDS, and §5.33.4's mechanisms against four live
  StepScaling policies. **The deployment is correct and the spec is unamended.**
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** **one systematic pass** — amendment markers, or a single "SPEC amendments" index —
  closes nine strands and defuses roughly a dozen claims; the highest-leverage item in the whole
  extraction, and it should be dispositioned as one task rather than sixteen. A marker is editorial, not a
  product call: the project already records departures in DECISIONS.md and at the code site, a strong
  practice with **no step writing them back into SPEC**. The annotation is also what makes the audit's own
  judgements checkable — ARCH-23's "superseded" verdict is *inferential* precisely because SPEC carries no
  annotation.
- **Remaining action:** the systematic pass. **Flagged for explicit user sign-off DURING the canonical
  migration (amend-versus-build, not queued now):** DRIFT-15's two unbuilt §5.29 mechanisms and REQ-49's
  unbuilt mechanisms — for a solo-maintained, low-traffic pilot "amend" is the likely honest answer, but it
  is a judgement; and DRIFT-16's reading question (was "sensitive information in an email" ever meant as a
  gate distinct from `email_approval`?), which has two defensible answers and is the cheapest of them.
  **Three items must be lifted out of the family and not treated as editorial:** the **locus correction**
  for §5.13 (TRACEABILITY and the ledger point readers at `exam_policy.py` when enforcement lives in
  `assessment_builder.py`/`variant_persistence.py` — a citation defect in the traceability register
  itself); the **ten-versus-nine `TurnReason`** divergence, a **client-visible contract** with an untyped
  client (`chat-web/src/types.ts:67` types `reason?: string | null` rather than narrowing to the union);
  and two substantive payload facts — `StageNarrativePayload`'s **`attendance_status`** crossing to the
  wire against SEC-01/REQ-01's MySQL-only framing, and `RagAnswerPayload`'s **`user_role`** surviving after
  D-219 removed it from `ScopeAndIntentPayload` for prompt-authorization reasons, which is in tension with
  **non-negotiable rule 3**. Also carry two coverage limitations honestly: fifteen of §5.29's nineteen rows
  were never sampled, and the four checkpoint tables sit **outside `test_schema_purity.py`** entirely while
  untyped `dict` state fields sit outside any name-based PII check — that is the load-bearing gap inside
  DRIFT-33, not the field count. AUD-C-24 (query text unredacted before the wire) is named in-entry as a
  **live** finding and must be confirmed as tracked or it falls through. Finally, the **missing process
  step** — who writes a departure back into SPEC — is a convention decision worth surfacing with the
  migration proposal.
- **Owner type:** documentation, with named user sign-off points during migration
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, highest leverage
- **Historical/archive only?** no

### `STATUS-TAG-CONVENTION` — `superseded` is declared and never used, and at least eleven stale tags read as active

- **Work/Issue ID (topic key):** `STATUS-TAG-CONVENTION`
- **Members:** E2-47
- **Description:** The supersession map's single most consequential finding. `DECISIONS.md`'s own header
  declares `Status: proposed | accepted | superseded`, and a grep for `superseded` in any `## D-` or
  `### D-` heading returns **nothing, file-wide** — across ~120 entries read in 29 chains, **zero** carry
  the tag. The only heading-level supersession marker anywhere is D-342's metadata line, whose list is
  itself incomplete (it names D-322 §5, not §7). Two heading conventions coexist, neither complete;
  verification and addendum sub-entries sometimes carry **no status field at all**, making them
  unindexable; and observed status values are free prose outside the declared enum. Consequence, stated as
  measured: "any consumer that reads status tags to determine what is current will read **at least eleven
  stale `accepted`/`implemented` entries as active**." The corpus is traversable newest→oldest only.
- **Domain:** decision-log architecture / documentation convention
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:72-96`, `:98-118`, `:120-136`, `:138-144`,
  `:2303-2313`, `:2320-2321`
- **Related claim IDs:** none owning; exemplars are D-135, D-344, D-356, D-300, D-366, D-085, D-072,
  D-322 §7
- **Related decision IDs:** the eight verified stale-tag exemplars above
- **Repository evidence:** the map's own verified stale-tag table. It hands retagging to "Phase 3", which
  has since produced other artifacts — **confirm whether anyone accepted that hand-off** before treating it
  as owned.
- **Deployed/live evidence:** n/a — documentation.
- **Final disposition:** `DOCUMENTATION_ONLY` — **override of the extractor's user-decision proposal**
- **Justification:** it is an **input to the canonical-document proposal**, not a standalone decision:
  the eight actively-misleading entries are the separable immediate fix, and scope and appetite get decided
  when the user reviews that proposal. So it has a safe default and does not need to be a queue entry.
- **Remaining action:** annotate the eight verified-misleading entries (`DOC-DECISION-LOG-CORRECTIONS`,
  `AMENDMENT-SWEEP` and `RISK-GROUP-DECISIONS-HYGIENE` cover most of them) and adopt D-153 §5's
  backward-pointer convention going forward, rather than a 120-entry sweep. Note the standing hazard: any
  tooling keyed on `## D-nnn` headings — **including this audit's own merge keys** — is unsafe until the
  phantom-ID and heading-format problems are closed.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration backlog, as design input
- **Historical/archive only?** no

### `AUDIT-ID-NAMESPACE` — a bare audit ID does not uniquely identify one finding

- **Work/Issue ID (topic key):** `AUDIT-ID-NAMESPACE` (DRIFT-40 / TEST-20)
- **Members:** E2-48, E3-40 (DRIFT-40), E1-64 (TEST-20)
- **Description:** Three verified facts force a citation rule. `AUDIT_FINDINGS.md` (frozen 2026-08-05) and
  `AUDIT_LIVE_2026_08_17.md` both use `AUD-L-01 … AUD-L-19` for **unrelated** findings — the range is
  reused, not continued (AUDIT_LIVE's `AUD-L-17` is "Child chooser has no sign-out or exit", P3; the
  AUDIT_FINDINGS finding renumbered to `AUD-L-19` was renumbered *because of a previous collision*).
  `AUDIT_2026_08_16.md` uses a third scheme (`P1-1…P1-10`) plus later `AUD-CHAT-nn`/`AEL-nn`/`EDGE-CHAT-nn`
  labels shared with AUDIT_LIVE. And inside `AUDIT_FINDINGS.md` the `AUD-L-17 → AUD-L-19` renumber was
  applied **per reference**, with ranges like `AUD-L-10..AUD-L-17` and P3 narrative passages deliberately
  left ambiguous, so **a mechanical re-map is not available**. Per-reference application is confirmed: 41
  surviving `AUD-L-17` citations corpus-wide, of which the two P2-meaning hits are both explicitly
  historical and **no live, unqualified P2-meaning citation survives**. The unmitigated defect is the
  cross-document collision, and the disambiguation heuristic documented in AUDIT_FINDINGS **explicitly does
  not reach across documents**. The ledger's "33 places across five documents" is a 2026-08-04 snapshot; it
  is now 36 non-ledger hits across seven files **because the reconciliation corpus added its own** — a
  small self-inflicted worsening.
- **Domain:** audit method / identifier governance
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:386-401`;
  `REPOSITORY_DRIFT_REGISTER.md:471-480`; `CLAIM_LEDGER.md:2271`; `AUDIT_FINDINGS.md:35`, `:43`,
  `:182-200`; `AUDIT_LIVE_2026_08_17.md:43`, `:45`; `ROADMAP.md:744-751`
- **Related claim IDs:** TEST-15, TEST-16, TEST-17, TEST-18, TEST-20, WORK-42; all `AUD-L-*`,
  `AUD-C-*`, `AUD-X-*`, `P1-n`, `AEL-*`, `EDGE-CHAT-*`
- **Related decision IDs:** D-159, D-174, D-178, D-183
- **Repository evidence:** the rule the map states: **"never treat a bare audit ID as uniquely identifying
  one finding. Always cite it as `<document>:<id>`."**
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY` — **adopt the qualified-citation rule; no renumber**
- **Justification:** §C override of DRIFT-40's user-decision proposal. Renumbering historical audits is not
  worth it and a mechanical re-map is unavailable; the rule costs nothing and closes the ambiguity. This
  register already applies it (§0.2 rule 6).
- **Remaining action:** adopt the rule corpus-wide. **Every cross-document finding lookup after 2026-08-16
  is ambiguous until it exists — including lookups this register will make — so fix it early.** If the
  convention is adopted, the reconciliation corpus must adopt it too, or Phase 4 adds a third register with
  the same prefix scheme.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, early
- **Historical/archive only?** no

### `DOC-DECISION-LOG-CORRECTIONS` — eleven decision-log defects that are wrong relations, wrong counts, or wrong rendering

- **Work/Issue ID (topic key):** `DOC-DECISION-LOG-CORRECTIONS`
- **Members:** E2-1 (F1 relations), E2-6 (D-135's stale heading), E2-9 (F6's three policy sets),
  E2-23 (K1's shape residue), E2-26 (phantom D-210), E2-28 (phantom D-363 + the D-359–D-364 sweep),
  E2-32 (the stale video figures), E2-34 (K4's status lines), E2-36 (M1's SSE architecture),
  E2-45 (the instance counter + malformed markdown), E2-50 (the phantom count)
- **Description:** Eleven members, each a document defect with confirmed substance behind it. **F1:** D-092
  never names D-084 (the supersession text lives only downstream in D-093), and D-137's runbook fix concerns
  the **JWT signing secret** `-replace` command, not the **RDS master** rotation command D-093 fixed — so
  treating it as the next link conflates two different remediation commands. **D-135:** its heading still
  asserts "Criterion 6 closes on 2026-08-02 for all three jobs" and §5 still says "2026-08-02 is a
  read-and-tick", both known false since D-138 falsified the premise ("the 07-26 firing D-135 recorded is
  not a mis-read metric — it is an event with no possible cause"), with **no annotation anywhere** in
  7608–7679 read in full — the highest-risk stale heading found; and the correct relation to write is
  "premise falsified", **not** "superseded". **F6:** three retention policy sets coexist and no document
  reconciles them (see `RETENTION-CLUSTER`); they must **not** be collapsed into one chain. **K1:** the
  shape apparatus is deleted (~2,000 lines, D-226) and authored-only is the sole path, but D-003's chain
  membership is inference-only, D-210 has no entry, and D-193's claim to "reverse the direction of D-192" is
  asserted against a **non-existent entry**; a deliberate residue of **50 `authoring_mode='shape'` rows**
  survives in every database, "safe to delete whenever someone wants to" — the only place this chain
  touches live data. **D-210:** `grep '^#\+.*D-210'` returns exactly one hit, `## D-210 disposition`, which
  says what was decided *about* D-210's residue (a shape-template fallback is **not built**), not what
  D-210 decided; its substance (the `_servable()` / `authoring_mode == "authored"` rule and the export
  `active_status` filter) is reachable **only** through citations in D-224, D-226, D-269 and D-271, with
  **D-271 load-bearing** because "D-210 added exactly that filter" is what falsifies D-269's precaution
  claim; its text, date, status tag and weighed alternatives cannot be inferred, and **unlike the recorded
  trio, no meta-note covers it** — making it the cheapest phantom to close honestly. **D-363:** no heading
  of any level and only four citations corpus-wide (`DECISIONS.md:25728`, `:25894`; `PROGRESS.md:891`,
  `:2214`) with no `See`, `Follows:` or `Fixes:` relation anywhere; it describes a **harness** defect ("the
  click never landed") that stopped accumulation attempt 5 of C1 Phase 6 around 2026-08-16, and the
  description-to-id mapping is recoverable only from `:25728` because `:25894` collapses D-361 and D-363
  into one row with two descriptions. M6 additionally leaves an unresolved sweep item across D-359, D-360,
  D-361, D-362 and D-364. **Video figures:** D-314 (`:22375`) still asserts "the catalog holds 4 videos
  across 4 of 112 skills" in the present tense and D-322 §6 (`:22941`) repeats "4 videos across 112
  skills", both left standing — D-417 §B5 corrected OPEN_DECISIONS but **did not annotate these two
  entries**. **K4:** the active rule is D-302, but D-300's status still reads "the remedy is a decision,
  not yet taken" although D-301 and D-302 both took it, and D-301 (same day, same session) carries no
  annotation although D-302 reversed its central clause — "a reader landing on D-301 first gets the wrong
  active rule"; D-313's overridden recommendation is likewise unannotated. **M1:** the architecture of
  record is "D-335 as amended by D-395" plus D-396 for telemetry, and **no single entry states the current
  whole**; D-334's status still reads "the defect is reported, not fixed" although D-335 fixed it the same
  day; and **D-344's heading (`stopgap, removed by D-349`) is contradicted by its own correction section**
  ("the stopgap existed for the length of a code review and never once bounded the service",
  "**D-349 therefore removes nothing**") with nothing in D-349 acknowledging it — the corpus's clearest
  self-contradicting artifact, heading versus body in one entry. **The counter:** D-357 called itself the
  fifth instance of the stale-image-floor shape and D-401 the sixth; D-418 then showed the check was
  judging a value nothing reads, **partially invalidating the count without renumbering it**, and whether
  D-137/D-141/D-244 were also phantom is unaddressed — so the count is neither wholly right nor wholly
  wrong. D-401's correction blockquote is also **malformed markdown**: the `>` block starting at 27533 ends
  mid-sentence, visually fusing the correction with the original text — the only *rendering* defect found
  in the corpus, and worth fixing because a fused correction reads as the original claim. D-401's status
  additionally splits across three entries (configured / corrected / applied) with no single entry stating
  current alarm routing. **The phantom count:** the section opens "Five ids are cited across the corpus with
  no entry of their own" and then documents **six** (D-190, D-191, D-192, D-210, D-329, D-363).
- **Domain:** decision-log integrity
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:124`, `:198-201`, `:230-232`, `:296-314`,
  `:353-382`, `:424-434`, `:458-464`, `:615-617`, `:638-639`, `:753-776`, `:1539-1605`,
  `:1671-1678`, `:1729-1731`, `:1793-1821`, `:1971-2007`, `:2259-2276`, `:2288-2294`
- **Related claim IDs:** none owning individually
- **Related decision IDs:** D-003, D-016, D-060, D-072, D-082, D-084, D-092, D-093, D-114, D-126, D-135,
  D-137, D-138, D-141, D-143, D-150, D-192, D-193, D-194, D-210, D-223, D-224, D-226, D-231, D-232,
  D-233, D-244, D-292, D-296, D-300, D-301, D-302, D-313, D-314, D-322 §6, D-331, D-332, D-333, D-334,
  D-335, D-344, D-345, D-349, D-357, D-359–D-364, D-395, D-396, D-401, D-406, D-418, D-419, D-045
- **Repository evidence:** every member is verified at source; several by full-file grep.
- **Deployed/live evidence:** n/a — documentation.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** one pass over the decision log. Cheap sub-tasks with disproportionate value: the
  D-359–D-364 heading sweep settles five ids at once
  (`grep -nE "^#{2,4} D-(359|360|361|362|364)"`, and the Theme-H tag table already shows real headings for
  D-359, D-360 and D-361 at 25479/25549/25570, so only D-362 and D-364 remain genuinely unconfirmed); and
  "Five" → "Six" is a two-character fix in the sentence that introduces the phantom inventory, on an audit
  whose whole premise is that unannotated numbers get quoted forward.
- **Remaining action:** the pass. **Two cautions:** if any remediation runbook still routes an operator
  from D-093 to D-137 for an RDS rotation, that is a **live operational hazard** rather than a document nit
  — worth one grep of `INCIDENT_RESPONSE.md`; and the D-233 quote "The number was never the variable" was
  **NOT FOUND** in the window read and must **not** be attributed without a wider read. D-045 also needs the
  forward pointer noted in `G2-LOCATOR-PURGE`. The 50 shape rows deserve one sentence in a known-residues
  list. D-210's remedy is the one the corpus already invented: a `recorded`-status meta-note stating what is
  known via D-271 and what is not.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-PROGRESS-QUEUED-BLOCK` — a four-row PROGRESS block is superseded by the same milestone that produced it

- **Work/Issue ID (topic key):** `DRIFT-43` (WORK-11)
- **Members:** E3-43 (DRIFT-43), E1-94 (WORK-11)
- **Description:** PROGRESS lists C8 as "⏳ next" — one mechanical commit of "168 of **494**" files — while
  ROADMAP's W24 records it **done** with 168 of **437** Python files reformatted plus `ruff format --check`
  wired into CI and `make lint`, Markdown scoped out. **ROADMAP is right on all three counts and its 437 is
  exactly reproducible:** `5728b95` changed exactly **168** files (795 insertions / 1118 deletions, a
  pure-format commit); enforcement landed separately as `f0d2cfe`; at that commit the repository had **473**
  tracked `.py` files and ruff's `extend-exclude` removes **36** → **437**. At HEAD: 477 tracked → **440**
  ruff-visible. **No count in repository history plausibly yields 494.** The same four-row queued block also
  marks A3/B4/B6 "⏳" against ROADMAP W25/W26/W27 recording them done — so **the block, not the row, is the
  defect**.
- **Domain:** documentation / tooling
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:504-513`; `CLAIM_LEDGER.md:2981`;
  `PROGRESS.md:84`; `ROADMAP.md:3226-3236`
- **Related claim IDs:** WORK-05, WORK-07, WORK-08, WORK-11, TEST-18
- **Related decision IDs:** C8, D-417 §C8, D-418, W24
- **Repository evidence:** `git show --stat 5728b95`; tracked-`.py` counts at `5728b95` and HEAD;
  `pyproject.toml:24-40`; `Makefile:120-127`; `.github/workflows/ci.yml:74-82`. Wiring exists in both
  places, the CI "Format check" step being what branch protection requires.
- **Deployed/live evidence:** n/a. F-17 executed it: `make lint` produced `All checks passed!` and **`440
  files already formatted`** — matching the independently derived HEAD figure **exactly**, using
  `ruff format --check` so verification cannot rewrite files as a side effect.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the 440 agreement between an auditor's derivation and the tool's own output is the
  cleanest corroboration in the corpus and worth one sentence in any report as evidence the method works.
  Retire the whole four-row block, not one line.
- **Remaining action:** retire or date the block. Note the separate method point from E4: the `ruff format`
  denominator moving 437 → 440 is **not** drift — consistent growth with the mechanism unchanged and green
  (`RUFF-DENOMINATOR`, §10).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `D192-PHANTOM` — D-192's content is unknown by design and negatively characterised only

- **Work/Issue ID (topic key):** `D-192` (phantom)
- **Members:** E2-25
- **Description:** D-192 has no entry and, unlike D-190/D-191, **no citation states what it decided**; the
  corpus's own meta-note leaves it as a known unknown rather than guessing ("the id nothing in the tree
  explains … no citation states what it decided. **Left as a known unknown rather than guessed at.**").
  Yet D-193 claims to reverse its *direction* and describes it in detail ("built an inverted authoring
  mode: generate the equation from a registered shape first") — a description that exists **only in the
  reversing entry**. Citers: D-193 (12950, 12990, 12992), 13756 ("This is not D-192 returning."), 13836,
  D-199 (13908), the note (16101, 16120), 17304.
- **Domain:** content pipeline / decision-log integrity
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:259`, `:272-273`, `:286-294`, `:1544-1548`,
  `:1601-1602`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-192, D-193, D-199
- **Repository evidence:** the note's confidence is HIGH on what it says and LOW on the underlying facts.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `UNKNOWN` — **irreducible by design**
- **Justification:** the note's refusal to fabricate is itself the decision, and it is the right one:
  "writing three retrospective entries from inference would produce exactly the confident-looking,
  unverified prose this project keeps finding bugs inside."
- **Remaining action:** **Named resolution step: none exists — this is irreducible by design.** The whole
  remedy is one clarifying sentence scoping the note's "no citation states what it decided" to *code*
  citations, which is where it is in mild tension with D-193's account. **Do not resolve it by adopting
  D-193's description as D-192's content.**
- **Owner type:** documentation (the clarifying sentence)
- **Reopen condition:** n/a · **PROJECT_STATE?** yes, as a recorded permanent unknown
- **Historical/archive only?** no

### `RISK-GROUP-FREEZE` — the D-152 freeze is invisible in exactly the documents it binds

- **Work/Issue ID (topic key):** `RISK-GROUP-FREEZE` (**R4.1, R4.3, R4.4, R4.5, R9.1**)
- **Members:** E6-16 (R4.1, R4.3, R4.4, R4.5, R9.1), E3-5 (DRIFT-05), E3-6 (DRIFT-06), E3-7 (DRIFT-07),
  E1-69 (INT-06), E1-70 (INT-07), E1-79 (INT-26)
- **Description:** The project's single most consequential standing instruction is documented where it is
  least needed and absent where it binds. **R4.1:** `INTEGRATION_PLAN.md` contains **zero** occurrences of
  `D-152` (`grep -c "D-152\|D-153"` → 0) and, read standalone, actively directs all four actions
  CLAUDE.md L54–72 forbids — measure AWS→icrest reachability (`:464`), make the Tier 1 org asks
  (`:442-446`, `:464`), finalize the §3.1 auth option (`:281-283`), and work the adapter against
  production's schema (`:311-316`, `:465`) — with §5's S42–S51 table carrying **no status column** and §8
  headed "read before executing S42"; its front matter is a 2026-07-24 hardened-scope block with no freeze
  banner and no pre-freeze-artifact disclaimer; §5's 17-row table is accurate for S35–S41, wrong-as-current
  for S42 and silently wrong for the frozen S43–S47; and the file has **no representation of the 27
  W-sessions (W1–W27, D-393→D-423) that actually ran after the gate**. A reader arriving via
  `ROADMAP.md:1438` sees the ⛔ banner; a reader opening the file directly does not. **R4.3:**
  `S42_ORG_ASKS.md:7-14` still reads **A** Timezone → "Send now" ("The only item that changes what gets
  built"), **B** DNS → "Send now", **C** → "Hold until S42", with internal notes still saying A is due
  before S43 opens and B before S48, and no D-152/D-153 reference — while `S42_OPEN_QUESTIONS` records
  C3/DNS as **answered by the org**, the timezone as closed by evidence, and Message A as **downgraded to a
  courtesy question** per D-153 §4. **Anyone acting on this table sends the org a question it already
  answered** — the purest "a reader would do something wrong" case in the corpus, and the one member of
  this group with an actual wrong-action consequence. **R4.4:** `S42_DISCOVERY.md` §7–§9 read as live work,
  and §9's "every row below must be fixed" is now *prohibited* by CLAUDE.md's do-not-rewrite-the-fake rule,
  so a reader obeying it **violates CLAUDE.md**. **R4.5:** ROADMAP's S43–S47 are imperative build specs
  with the freeze only at L1440–1445 above them, and **S48–S51 carry no freeze annotation at all** — the
  easiest gap to miss because those sessions look untouched rather than frozen; SPEC §5.2.2's auth-option
  menu also reads live. **R9.1** is the summary: five documents show ✅, four show ❌, and **the ❌ rows are
  the ones a reader is inside when the freeze matters**. A third file, `S42_OPEN_QUESTIONS.md`, holds three
  mutually contradictory statements live in 121 lines: `:110` (its own "what to do now" list) says C3(DNS)
  send and E-group notify "are the only two valid now"; `:76` marks C3 🔴 "cannot be deferred — pure lead
  time"; `:17` says C3 is confirmed possible and "no longer open" — the D-153 ledger block at `:15-19` was
  prepended without rewriting the D-152-dated action list beneath it. **This is the designated re-entry
  document for integration**, which is the worst possible location for a self-contradiction.
- **Domain:** documentation corpus / integration-freeze coherence
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:207-215` (R4.1), `:229-237` (R4.3),
  `:239-244` (R4.4), `:246-250` (R4.5), `:451-470` (R9.1); `DOCUMENT_INVENTORY.md:340-347`,
  `:546-547`, `:729-741`, `:786-794`; `REPOSITORY_DRIFT_REGISTER.md:79-88`, `:90-99`, `:101-110`;
  `CLAIM_LEDGER.md:2457`, `:2470`, `:2717`
- **Related claim IDs:** INT-03, INT-04, INT-05, INT-06, INT-07, INT-08, INT-09, INT-10, INT-26, INT-28
- **Related decision IDs:** D-130, D-134, D-099, D-148, D-151, D-152, D-153 §4, D-154, D-417 §A1;
  CLAUDE.md L54–72
- **Repository evidence:** the guard and the temptation are unlinked **in both directions** — CLAUDE.md's ⛔
  section never names `INTEGRATION_PLAN.md`, and `INTEGRATION_PLAN.md` never names D-152. The inventory adds
  one more: `INCIDENT_RESPONSE.md` never mentions the freeze, so its MySQL-adjacent severity tier reads as a
  live production attack surface when no production path exists yet. The option matrix in
  INTEGRATION_PLAN §3.1 remains useful reference material.
- **Deployed/live evidence:** n/a — documentation.
- **Final disposition:** `DOCUMENTATION_ONLY` — **override of DRIFT-05/06/07's user-decision proposal**
- **Justification:** D-152 is already decided; this is **making a decided thing visible**, and the
  banner-versus-historical choice is an **editorial choice, not a judgement**. Highest-severity group in the
  risk register (four HIGH entries plus the HIGH summary). The register's own estimate is **one banner per
  ❌ row**, and R4.1 is "the first banner any reconciliation should add".
- **Remaining action:** five freeze banners plus one CLAUDE.md cross-link, plus a status column or
  historical marker on the S42-file tables. **Copy `S42_OPEN_QUESTIONS.md`'s own ⛔ banner and re-entry
  protocol shape** — it is the model citizen — rather than inventing one. Sequence `S42_ORG_ASKS`'s
  remediation **first** within the group, because it is the one with a wrong-action consequence. Do **not**
  blanket-retire `S42_OPEN_QUESTIONS.md:110`: the E-group notification half is genuinely still valid
  (`ORG-COMMS`). Pair the edits with `RISK-R6.5-SUPERSESSION-DIRECTION`, which touches the same S42 files —
  do both edits in one pass per file.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, first
- **Historical/archive only?** no

### `RISK-GROUP-ARCH-AUTHORITY` — two architecture documents with no ratified hierarchy, and the filename points the wrong way

- **Work/Issue ID (topic key):** `RISK-GROUP-ARCH-AUTHORITY` (**R2.1, R3.1, R5.2, R6.6**)
- **Members:** E6-17 (R2.1, R3.1, R5.2, R6.6), E3-1 (DRIFT-01), E3-53 (DRIFT-98), E1-29 (ARCH-26),
  E1-22 (ARCH-19), E1-25 (ARCH-22)
- **Description:** `ARCHITECTURE.md` (2,180 lines, 2026-08-18) and `FINAL_ARCHITECTURE.md` (185 lines,
  2026-07-28) both describe topology. Deference is stated only in the **weaker** file (`:3-6`);
  `ARCHITECTURE.md` never acknowledges it exists; **neither is in CLAUDE.md's index**, so a newcomer's only
  signal is the filenames — and "FINAL" reads as latest and definitive when the file is a self-declared
  projection ("planned as of 2026-07-21"), 10× smaller, three weeks older, with **zero functional inbound
  references**. All three of its status claims are stale: S33 shipped 2026-07-23 and S34 2026-07-24; D-004
  is accepted (S32) while the file still calls it "proposed"; and the "known gap" single-instance SSE bus is
  closed by `SessionEventBus`/`SessionEventRelay` over Postgres `LISTEN`/`NOTIFY`. Four decided questions
  are still presented as live (`:33` "Status: decision-gated, not yet made"; `:110` "D-004 is still
  'proposed'" — accepted six days before the file's last edit — plus ECS-versus-EKS, integration shape,
  single-versus-multi instance and RDS-versus-Aurora). The file's **own retirement instruction** (`:183-185`:
  fold back into ARCHITECTURE and delete "rather than letting the two drift apart") had its trigger fire in
  July; the fold never happened and the predicted drift is exactly R2.1/R5.2. The storage-split table has
  two owners: `ARCHITECTURE.md:2054-2073` holds it and `FINAL_ARCHITECTURE.md:156-161` appends and
  overrides its first row — and that projection is the **only** place either document states the actual
  database layout ("today's system is one `intellichoice` Postgres database"), a one-line as-built fact
  missing from the canonical document, which names stores and tables but never how many logical databases or
  schemas exist. On the sibling side, DRIFT-98: `ARCHITECTURE.md`'s declared scope **understates** a month
  of work the same file documents (it cites D-404/D-405, D-409, D-416, D-421, D-423 and
  `chat_escalation_sends`; 15 lines match `D-4xx|W2x|U7`) while PROGRESS records Milestone 15 closed, and
  provenance tagging is uneven against the header's promise — tags exist for **32 of 48** sessions, the 16
  untagged being S23, S30–S33, S35, S36, S38, S40–S47, i.e. every session from S40 onward except the
  aspirational `(S48)`, which tags the **unbuilt** production environment, and **no tag scheme at all for
  the W-milestones**.
- **Domain:** documentation corpus / architecture authority
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:97-106` (R2.1), `:156-160` (R3.1),
  `:276-284` (R5.2), `:377-382` (R6.6); `DOCUMENT_INVENTORY.md:261-278`, `:280-308`;
  `REPOSITORY_DRIFT_REGISTER.md:35-44`, `:1113-1122`; `CLAIM_LEDGER.md:959`, `:998`, `:1050`;
  `FINAL_ARCHITECTURE.md:1-11`, `:33-42`, `:107-124`, `:135-137`, `:154-167`, `:183-185`
- **Related claim IDs:** ARCH-01, ARCH-05, ARCH-06, ARCH-08, ARCH-10, ARCH-19, ARCH-20, ARCH-21, ARCH-22,
  ARCH-26, ARCH-27
- **Related decision IDs:** D-004, D-064, D-078, D-082, D-085–D-095, D-334, D-335, D-349, D-404–D-423
- **Repository evidence:** `packages/db/alembic/env.py:36,59,72` has no `include_schemas` and no
  `schema_translate_map`. **F-07 splits DRIFT-98's verdict and refutes half the 3A framing:** decision
  currency is **fine** — `ARCHITECTURE.md` cites D-423, the newest entry, the same decision as HEAD~1, so
  "it is not behind on decisions" — and the true finding is that **the `(Sn)` provenance convention was
  abandoned around S39 while the header still advertises it**. The two have different remedies.
- **Deployed/live evidence:** `FINAL_ARCHITECTURE`'s status claims are falsified by the **deployed**
  reality (ECS/RDS per D-004; replicas and the rate limit exist) — the deployed state is correct and the
  document is stale, not the reverse.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** archive one file after two extractions and state the hierarchy in the surviving one
  plus CLAUDE.md's index. §3.2 records DRIFT-01 and DRIFT-98 as **one cross-referenced decision family, not
  two** — do not double-count; and the direction of rot is opposite in each (FINAL_ARCHITECTURE overstates
  its currency; ARCHITECTURE.md's header understates its own contents).
- **Remaining action:** **two mandatory extractions before archive**: refresh the topology diagram
  (`:46-105`, the only end-to-end deployed-topology diagram in the repository) into `ARCHITECTURE.md`, and
  extract open question 5 into an owned decision record (`ARCH-21-SCHEMA-SPLIT` — **sequencing matters, do
  not archive first**). Move the one-line database-layout fact into the canonical document. Rename on
  archive. Adopt F-07's split in the wording: "behind on decisions" is **false** and must not be repeated.
  One caution when writing supersession statements: `INTEGRATION_PLAN.md:3` supersedes "the two earlier
  drafts of this document" — drafts that no longer exist, so that supersession is **unverifiable**; keep
  new ones checkable. The §5.3 deployed-topology half is not this entry's subject.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-R2.2-ACCEPTED-RISK-HOMES` — the two accepted P1 risks live in four homes and only one carries the expiry conditions

- **Work/Issue ID (topic key):** `R2.2`
- **Members:** E6-19
- **Description:** `INTEGRATION_PLAN.md` §7 (`:535-566`) owns R8 and R9 with their expiry conditions ("**This
  acceptance expires at first real traffic**", `:548`; the `learning_checkpoint_repairs_total` tripwire,
  `:565`). `ARCHITECTURE.md:486-494` and `:601-609` restate both **without the expiry conditions** — and
  ARCHITECTURE is the file sessions are instructed to update, and therefore to read, while INTEGRATION_PLAN
  is unindexed. An accepted risk whose expiry clause is invisible at the point of reading is how "accepted
  for the pilot window" silently becomes "accepted for launch" — the exact failure shape TRACEABILITY
  records for D-072/`AUDIT_FINDINGS.md`:AUD-L-04. Two further homes need the same expiry re-check:
  `AUDIT_FINDINGS.md`'s accepted residual risks and `TRACEABILITY.md`'s §7-R8 row.
- **Domain:** launch readiness / accepted-risk tracking
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:108-118`; `DOCUMENT_INVENTORY.md:266-268`,
  `:325-327`, `:378-380`, `:481-485`
- **Related claim IDs:** SEC-09, SEC-10, ARCH-17, ARCH-18, INT-22, INT-33, REQ-09
- **Related decision IDs:** D-072, D-086, D-107, D-110 §3, D-123, §7-R8, §7-R9
- **Repository evidence:** three of four homes are incomplete.
- **Deployed/live evidence:** the expiry trigger is a **deployed/production event** ("first real traffic")
  that has not occurred; the R9 tripwire's metric carries live data and has no alarm
  (`KPI-ALARM-FLOOR`).
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** carry the expiry conditions to every restatement, or reduce the restatements to
  pointers. This is the **one register item with a launch gate attached**, and it is a separable
  documentation fix that should not wait on the ownership decision in `ORG-COMMS`.
- **Remaining action:** the edits. Consider making the expiry **mechanical** rather than prose — the
  `learning_checkpoint_repairs_total` tripwire already is, which is why `KPI-ALARM-FLOOR`'s sub-question
  matters. The acceptance itself needs a fresh judgement **at first real traffic**
  (`R8-READ-SCOPE`).
- **Owner type:** documentation now; user at first real traffic
- **Reopen condition:** first real traffic · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-CURRENT-STATE` — current state and history are interleaved, and the summary layer is demonstrably unreliable

- **Work/Issue ID (topic key):** `RISK-GROUP-CURRENT-STATE` (**R1.1, R1.2, R3.7, R8.1, R8.2, R8.3**)
- **Members:** E6-20
- **Description:** `PROGRESS.md`'s "Current status" block is a newest-first stack ~1,800 lines deep reaching
  back through Milestone 10, with the boundary to the historical log marked only by a `---` and the prose
  "Prior state, still true" (~L1862). Point-in-time numbers coexist at different depths — the video catalog
  reads "4 of 112" at L1156 and "102 of 112" at L89–95, with the correct current figure only at the top —
  and the file records its own lesson: the carry-over list "has now been wrong six times this milestone"
  (L385–388). Because `ROADMAP.md:713-714` **delegates sequencing to it**, anything stale here directs the
  next session (R1.1, HIGH). `ROADMAP.md` keeps ~470 lines of superseded gate standings inline
  (L969–1436) beside the live verdict, **five coexisting criterion-6 dates**, and multi-tier and depth
  clauses carrying 3–4 unreconciled numbers each where later-in-file text is *earlier* in truth order
  (R1.2, HIGH); ~60% of the file is completed-work retrospective under a planning filename (R3.7). R8.1
  generalises it: **four self-documented cases of a summary line contradicting its own table** —
  TRACEABILITY's heading and its "Open: none" beside an open T-02; PROGRESS's "uncommitted" versus
  deployed; AUDIT_FINDINGS' count line "wrong three times" — because summaries are hand-written above
  machine-checkable detail and they drift; the corpus's own lesson is "a summary that agrees with the claim
  you want to make, above a table that contradicts it, is how a rubric passes itself". R8.2: **18 ROADMAP
  session headings carry no glyph** while L2168–2169 asserts all are done. R8.3: verbatim duplicate headings
  and blocks (`PROGRESS.md:15451`/`:15453` `### S20` twice; ROADMAP L1667–1673 ≡ L1680–1686; two "Session
  C1" headings; two Phase 5 blocks; AUDIT_FINDINGS' Index split into six fragments by stray blank lines,
  breaking naive parsers).
- **Domain:** documentation corpus / current-state authority
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:23-42` (R1.1, R1.2), `:192-195` (R3.7),
  `:424-434` (R8.1), `:436-440` (R8.2), `:442-447` (R8.3); `DOCUMENT_INVENTORY.md:158-169`,
  `:195-206`
- **Related claim IDs:** LB-04 is a concrete instance (a stale PROGRESS carry-over read as live risk)
- **Related decision IDs:** D-368, D-386, D-418 (all PROGRESS self-corrections)
- **Repository evidence:** the inventory's routes: ROADMAP **split reference + archive**; PROGRESS **split
  active + archive**.
- **Deployed/live evidence:** LB-04 shows the concrete cost — a stale carry-over read as live risk against
  the only path exercising real CloudFront → ALB → ECS (`WORK-13-FIXTURES`).
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the **largest single block of migration work** — a trustworthy current-state page plus
  archived strata. R8.1's recommendation is **structural, not editorial**: generate summaries mechanically
  or date-stamp them, because hand-maintained counts have failed at least four recorded times.
- **Remaining action:** the split, the strata, the glyphs and the duplicate blocks. ROADMAP's anchored-awk
  derivation is the existing precedent to copy (`RISK-GROUP-DUPLICATE-CONTENT`). **The *shape* of the split
  — one current-state page versus pruning in place — is a design choice worth ratifying with the user when
  the migration proposal is reviewed**, though it is not a queue entry.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, largest block
- **Historical/archive only?** no

### `RISK-R1.4-SPEC-VINTAGE` — SPEC.md is mixed-vintage with no vintage marks, and §6 is planning shelved as normative

- **Work/Issue ID (topic key):** `R1.4`
- **Members:** E6-21
- **Description:** `SPEC.md` has exactly **two** in-text amendment markers in 4,210 lines — §5.19.4/§5.19.5
  (L1973–2008, D-351) and §5.35 (L3403–3405, D-092) — while the D-111 MySQL sweep rewrote ~40 lines and
  four headings with **no marker at all** (recorded only at `DECISIONS.md:5170`). A reader cannot
  distinguish never-amended from silently-amended text, and CLAUDE.md tells sessions "the spec wins on
  detail". For §5.8.1, §5.11.2, §5.13.2, §5.28.2 and §5.33, **DECISIONS wins and the spec still reads as if
  it does not**. Requirements still reading live but decided otherwise include 100 templates per topic (vs
  D-223's ~25–35), EKS/Karpenter/Aurora topology (vs D-004's ECS/RDS), four dedicated chat endpoints (vs
  D-044), the whole §5.17 multimodal pipeline (deferred D-078, unmarked), §5.2.2's auth menu (frozen by
  D-152), §5.32.1's "choose one" observability fork (decided D-214/D-242), and §5.15.4's Sunday EventBridge
  job (manual per ARCHITECTURE).
- **Domain:** documentation corpus / normative spec currency
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:53-58`; `DOCUMENT_INVENTORY.md:101-130`
- **Related claim IDs:** the AMENDMENT-SWEEP set
- **Related decision IDs:** D-004, D-044, D-078, D-092, D-111, D-152, D-214, D-223, D-242, D-351
- **Repository evidence:** SPEC **never references any other repository document by filename** — zero
  mentions of DECISIONS, ROADMAP or ARCHITECTURE in 4,210 lines.
- **Deployed/live evidence:** SPEC §5.33's EKS/Aurora topology is contradicted by the **deployed** ECS/RDS
  reality; the deployment is correct and the spec is unamended.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** every superseding decision already exists; this is applying them. Candidate role:
  **ACTIVE with a mandatory amendment discipline** — the D-351 pattern (amend in place with a dated marker)
  becoming the rule — and **§6 demoted to historical**.
- **Remaining action:** adopt the D-351 marker as a rule, mark the known-superseded sections, demote §6.
  **Because SPEC references nothing, "the spec wins on detail" is safe about granularity and unsafe as a
  conflict-resolution rule — fixing that rule's wording in CLAUDE.md may be cheaper than annotating every
  drifted section.** Overlaps `AMENDMENT-SWEEP`, which is the per-section pass.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-DECISIONS-HYGIENE` — status tags never updated, three phantom ID families, entries edited in place

- **Work/Issue ID (topic key):** `RISK-GROUP-DECISIONS-HYGIENE` (**R6.1, R6.2, R1.3**)
- **Members:** E6-22
- **Description:** **R6.1 (HIGH):** the preamble declares `proposed | accepted | superseded` (L4) and the
  tag is never maintained — D-004 (materially rewritten twice, still "accepted"), D-135 (premise proven
  false by D-138), D-121 §3 / D-129 §5 (refuted by D-122/D-132, uncorrected in place), D-344's metadata
  still reading "removed by D-349" beside its own correction "D-349 therefore removes nothing" (L24671 vs
  L24705–24707, deliberately kept), plus undefined non-standard statuses ("accepted as launch-blocking
  carry-over" L2843; "measured, not acted on" L20916; "⏸ partial" L20679). Consequence: **a scan of
  headings by status finds zero supersessions**, and every one of the ~40 supersession chains is
  discoverable only by full-text reading. **R6.2 (verified directly):** **D-190/D-191/D-192** are cited 18×
  in code and 8× in documents and were never written (the log's own meta-note at L16101); **D-329** exists
  only as a `####` sub-heading inside D-330 (L23582); **D-363** is referenced at `DECISIONS.md:25728`/
  `:25894` and `PROGRESS.md:891`/`:2214` with no heading anywhere; informal sub-entries (`D-195 §5`,
  `D-206 addendum`, `D-210 disposition`, `D-212 addendum` inside D-211) and one three-ID heading
  (`D-266/267/268`, L19182) make ID-grep unreliable — a failure **D-223 itself demonstrates** at L16019,
  where the log's author mis-grepped their own log. **R1.3:** the log is **not append-only** — D-176 §4
  records a post-hoc paragraph edit, D-110 §2 embeds a "D-207 update" block revising its own numbers
  (L4963), and D-401 carries a 2026-08-18 correction inside a 2026-08-17 entry (L27513–27540) — so **an
  entry's text cannot be dated by its heading**. The heading format also changes mid-file at D-274.
- **Domain:** documentation corpus / decision-log integrity
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:44-51` (R1.3), `:323-344` (R6.1, R6.2);
  `DOCUMENT_INVENTORY.md:228-244`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-004, D-110, D-121, D-122, D-129, D-132, D-135, D-138, D-176, D-190,
  D-191, D-192, D-207, D-210, D-223, D-274, D-329, D-344, D-349, D-363, D-401
- **Repository evidence:** the inventory's route: **ACTIVE, system of record**; the reconciliation
  opportunity is *mechanical* — status-tag hygiene, an ID index, phantom-ID closure. The phantom IDs are
  **cited from source code (18×)**, so code comments reference decisions that do not exist.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** a status-tag pass, an ID index, and either writing the phantom entries or recording
  their absence at each citation site. The **loud-correction culture is a strength** — preserve it while
  fixing the headings.
- **Remaining action:** the pass. **Two cautions:** any tooling keyed on `## D-nnn` headings is unsafe
  until R6.2 is closed — relevant to this audit's own merge keys; and reconstructing D-190/D-191/D-192 from
  26 citation sites is **real work with a judgement component**, so consider a stub-with-provenance rather
  than a full entry. The individual phantom entries are `D190-D191-PHANTOM` (§10), `D192-PHANTOM`,
  `D329-PHANTOM` and the D-210/D-363 members of `DOC-DECISION-LOG-CORRECTIONS`; the convention question is
  `STATUS-TAG-CONVENTION`.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-AUDIT-REGISTERS` — three audit registers collide on IDs and none states its relationship to the others

- **Work/Issue ID (topic key):** `RISK-GROUP-AUDIT-REGISTERS` (**R6.3, R1.7, R5.4**)
- **Members:** E6-23 (R6.3, R1.7, R5.4), E1-66 (TEST-25)
- **Description:** **R6.3 (HIGH, verified directly):** `AUDIT_FINDINGS.md` (frozen 2026-08-05) uses
  `AUD-L/C/X/F-nn`; `AUDIT_LIVE_2026_08_17.md` **reuses the entire `AUD-L-01…AUD-L-19` range with unrelated
  meanings**; `AUDIT_2026_08_16.md` uses a third scheme (`P1-1…P1-10`) plus later
  `AUD-CHAT-nn`/`AEL-nn`/`EDGE-CHAT-nn` labels shared with AUDIT_LIVE. **No document states which register
  a bare `AUD-L-nn` in DECISIONS or PROGRESS refers to**, and AUDIT_FINDINGS mentions neither successor.
  **R1.7:** the audit documents are patched by blockquote strata unevenly — `AUDIT_2026_08_16.md`'s two
  status blockquotes close the P1s and five observability items while its §3/§4 P2/P3 lists carry **no
  status marks at all** and its "Still open" lines were overtaken by D-397→D-423; `AUDIT_LIVE_2026_08_17.md`
  is better maintained but its residual tail is partly overtaken (EDGE-CHAT-07 closed by D-408, AUD-L-09 by
  D-407, AUD-L-10/L-11 by D-409/D-410) with no in-file marks. **R5.4:** `AUDIT_FINDINGS.md` documents this
  failure five times over (L114–116: five headings said "not fixed" after fixes shipped; AUD-F-16 read
  `Open` for two weeks), and residuals persist — AUD-F-27's heading says both "✅ fixed" and "not fixed"
  (L4521); "Status: open, Phase 0B" bullets survive inside closed entries (L1804, 1985, 2345); known-wrong
  "Fix shape (Phase 0B)" blocks are retained verbatim inside closed findings. A concrete instance of the
  same class: AUDIT_LIVE's never-exercised list was narrowed four times the same day, and what the file
  still states remains un-walked — the exam timer, the calendar interrupt's `.ics` branch, and
  learning-web's tutor-chat browser leg — was **closed elsewhere** (D-391; D-392→D-397→D-399; D-398)
  **without updating the file**.
- **Domain:** documentation corpus / audit-register identity
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:76-83` (R1.7), `:291-296` (R5.4),
  `:346-356` (R6.3); `DOCUMENT_INVENTORY.md:357-387`, `:399-420`, `:440-452`;
  `CLAIM_LEDGER.md:2336`; `AUDIT_LIVE_2026_08_17.md:105-142`
- **Related claim IDs:** TEST-21, TEST-22, TEST-23, TEST-24, TEST-25, WORK-44
- **Related decision IDs:** D-183, D-381, D-383, D-385, D-387–D-392, D-397–D-399, D-403, D-407–D-413
- **Repository evidence:** the inventory's routes: AUDIT_FINDINGS → **REFERENCE** (a frozen register whose
  Index status column should stop being treated as authoritative, and whose relationship to the two
  successors "needs one written sentence each"); AUDIT_2026_08_16 → REFERENCE; AUDIT_LIVE_2026_08_17 →
  REFERENCE. TEST-25's three closures are verified against DECISIONS directly (chain H3), so that member is
  safe to close on documentation grounds.
- **Deployed/live evidence:** n/a — though LB-09 depends on AUDIT_LIVE's coverage lesson being **findable**,
  which the collision undermines.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** a namespace rule, three cross-reference sentences, a status-column disclaimer, and one
  closure note. Cheap, and it unblocks every cross-document lookup.
- **Remaining action:** the edits. **Fix it early**: every cross-document finding lookup after 2026-08-16 is
  ambiguous until the namespace rule exists (`AUDIT-ID-NAMESPACE`), and the AUD-L-17→AUD-L-19 renumber was
  applied per-reference with ranges deliberately left ambiguous, so a mechanical re-map is not available.
  Pair with `AUDIT-COUNT-INSTRUMENT`, which is the counting half of the same problem.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, early
- **Historical/archive only?** no

### `RISK-GROUP-NAMING` — six filenames and labels that misdirect a reader about what the file is

- **Work/Issue ID (topic key):** `RISK-GROUP-NAMING` (**R3.2, R3.3, R3.4, R3.5, R3.6, R3.8**)
- **Members:** E6-24
- **Description:** **`OPEN_DECISIONS.md` (HIGH)** — line 1 reads "Open decisions — what needs a person, not
  more code" while line 8 reads "✅ **Nothing in this file is awaiting a decision** (2026-08-18, D-417)";
  the filename invites treating a closed deliberation record as a live queue, and the file's own L292
  articulates the hazard ("an annotated recommendation is still a recommendation to whoever skims it").
  **`S42_ORG_ASKS.md` (MEDIUM)** — the `S42_` prefix asserts a session the content **predates** (drafted
  2026-07-24 at S36 close-out, last amended 07-31, before S42 ran on 08-01); `S42_SECURITY_REPORT.md` is
  mislabelled by one session but harmlessly. **`AUDIT_FINDINGS.md` (MEDIUM)** — an undated, unscoped name
  for a register scoped to Phase 0A and frozen 2026-08-05, sitting beside two dated successors it never
  mentions; its content also outgrew its title. **`U7_CHECKPOINT_CONSOLIDATION.md` (MEDIUM)** — the
  filename names an action §8.1 recommends **not** starting, and conveys nothing of what the file is (a
  2026-08-14 measurement snapshot plus four questions to the user, half answered since); unindexed, so the
  filename is its only signal. **`docs/plans/` (MEDIUM)** — reads as "current plans"; both files inside are
  executed history, one still labelled "planned, not started". **`SPEC.md`'s H1 (LOW)** — line 1 is
  `# 5. Very Detailed Version`, a section number from an absent parent; bare `§2.x` citations elsewhere
  resolve to `INTEGRATION_PLAN.md`, **not** SPEC (an unstated section-namespace split); and CLAUDE.md:13
  under-describes the file by **38%** ("~2,600 lines" versus 4,210).
- **Domain:** documentation corpus / naming and discoverability
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:162-168` (R3.2), `:170-174` (R3.3),
  `:176-180` (R3.4), `:182-185` (R3.5), `:187-190` (R3.6), `:197-201` (R3.8);
  `DOCUMENT_INVENTORY.md:519-521`, `:637-638`, `:793-794`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-153 (the S42 asks), D-183 (the AUDIT_FINDINGS freeze), D-331, D-332 (U7),
  D-417 (the OPEN_DECISIONS closure)
- **Repository evidence:** the inventory's routes: OPEN_DECISIONS → **REFERENCE (trending archive), rename
  or re-describe**; U7 → REFERENCE + ARCHIVE, "currently mis-shelved and invisible-but-load-bearing";
  S42_ORG_ASKS → ARCHIVE, "rename away from `S42_`".
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** renames and/or in-file re-descriptions plus index entries. **Rename-versus-re-describe
  is a judgement per file** because renames break inbound links (`ROADMAP.md:5`, `:326-331` point into
  `docs/plans/`; DECISIONS and PROGRESS cite these filenames) — that judgement belongs with the migration
  proposal, not the queue.
- **Remaining action:** the renames or re-descriptions. Keep the naming policy consistent with
  `RISK-GROUP-ARCH-AUTHORITY`, whose `FINAL_ARCHITECTURE.md` is the register's exhibit for this class. Note
  **CLAUDE.md's description of OPEN_DECISIONS is the stalest thing about it**
  (`RISK-GROUP-RESOLVED-LOOKS-OPEN`, `RISK-GROUP-INDEX`), so a rename alone is insufficient.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-RESOLVED-LOOKS-OPEN` — resolved decisions that still read as open, including in the one file every session loads

- **Work/Issue ID (topic key):** `RISK-GROUP-RESOLVED-LOOKS-OPEN` (**R5.1, R5.3, R5.5**)
- **Members:** E6-25
- **Description:** **R5.1 (HIGH):** `CLAUDE.md:38-40` says "everything still open … ten decisions … read
  before asking 'what should I work on next' — the answer is often 'ask the user'", while
  `OPEN_DECISIONS.md:3`/`:8` records all **14** items answered or parked and "Nothing in this file is
  awaiting a decision" — the resolved-looks-open pattern **in the always-loaded file**. **R5.3:**
  `S42_OPEN_QUESTIONS.md` keeps C1/C2/C3/C8 as full table rows (L74–76, 81), C3 still 🔴 "미룰 수 없음"
  ("cannot be deferred"), after the same file's own resolution ledger (L17–21) declares them closed, and
  L110 still instructs sending the answered C3 ask as one of only two live actions. **R5.5:** stale "stay
  unapplied" lines against applied decisions — `OPEN_DECISIONS.md:15` "D-401 and D-406 stay unapplied until
  it exists" versus D-419 (both applied 2026-08-18); `:35` "staging numbers nobody has read" versus
  `U7_CHECKPOINT_CONSOLIDATION.md:38` (read 2026-08-14); `:3` "Every decision … answered on 2026-08-14"
  versus items 11–14 decided 08-17/08-18 — patched by the L8 banner but never amended.
- **Domain:** documentation corpus / decision-status currency
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:271-274` (R5.1), `:286-289` (R5.3),
  `:298-303` (R5.5); `DOCUMENT_INVENTORY.md:76-80`, `:511-515`, `:762-764`
- **Related claim IDs:** WORK-07, WORK-08, WORK-39
- **Related decision IDs:** D-152, D-153, D-322, D-401, D-406, D-417, D-419
- **Repository evidence:** the three edits are small and located.
- **Deployed/live evidence:** D-401/D-406 are applied (`DRIFT-93-D401-D406-APPLIED`); the SNS follow-up is
  resolved (`SNS-CONFIRMATION`); the D-310 rotation is executed (`D310-ROTATION`) — so **three** of the
  stale "still open" lines are now falsified by measurement rather than by argument.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** **R5.1 is cheap and high-value — it is the description that sends every session to a
  closed file looking for work.**
- **Remaining action:** three edits: CLAUDE.md's description; in-table annotations in
  `S42_OPEN_QUESTIONS.md` (the inventory names the two "cheap repairs": annotate the resolved rows in-table
  and point the E-group at `S42_SECURITY_REPORT.md`); and OPEN_DECISIONS' three stale lines. Add three
  supersession annotations while there: **OPEN_DECISIONS #8** marked superseded-operationally
  (`D310-ROTATION`), **D-419's ⚠️ `PendingConfirmation` block** dated as resolved (`SNS-CONFIRMATION`), and
  **D-419's NAT sentence** corrected (`DOC-DEPLOYED-STATE-CLAIMS`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `TRACKING-HOME-FOR-OPEN-ITEMS` — genuinely open items that look closed or are tracked in no decision document

- **Work/Issue ID (topic key):** `R5.7`
- **Members:** E6-26
- **Description:** Five items are open and invisible. **(1)** `FIRST_VISIT_NOTICE.md:237` — "the three gaps
  in §5 need a product decision before S45" is open and recorded in **no** decision-tracking document.
  **(2)** `S42_SECURITY_REPORT.md` has **no send-status field**, so unsent is indistinguishable from
  sent-and-unlogged, and nothing after 2026-08-02 tracks it ("apparently still unsent"). **(3)**
  `S42_OPEN_QUESTIONS.md`'s A4/A5 are decisions awaiting a person, absent from `OPEN_DECISIONS.md` which
  declares nothing awaiting a decision. **(4)** The answer-cache decision lives only in
  `PROGRESS.md:31-33`'s top-of-file stack. **(5)** SPEC §5.33.3's six-schema split is recorded only in a
  file scheduled for archive.
- **Domain:** decision tracking
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:311-317`; `DOCUMENT_INVENTORY.md:184-186`,
  `:707-709`, `:803-805`, `:820-821`
- **Related claim IDs:** T-02, SEC-32, INT-05, WORK-04, ARCH-21
- **Related decision IDs:** D-127, D-153 §5/§7, D-417 ("nothing awaiting a decision" — falsified by these)
- **Repository evidence:** as cited. `S42_SECURITY_REPORT.md` is the only S42 work item that **legitimately
  survives the D-152 freeze**, so the freeze must not be allowed to suppress it.
- **Deployed/live evidence:** (4) affects deployed behaviour and has no owned record; (2) is an
  outbound-communication state with no tracked side at all.
- **Final disposition:** `DOCUMENTATION_ONLY` — the **tracking-home half**; the judgements themselves
  follow their canonical topics
- **Justification:** §C override: **no blanket user decision** — the members follow their canonical topic
  rulings, and the *tracking home* is documentation and can land first. Each judgement is already routed:
  (1) → `DISCLOSURES-LEGAL` (UD-10), (2) → `ORG-COMMS` (UD-8), (3) → `AUTH-OPTION-O1B` and `D152-FREEZE`,
  (4) → `WORK-04-ANSWER-CACHE` (resolved by D-423), (5) → `ARCH-21-SCHEMA-SPLIT`.
- **Remaining action:** give each item a tracking home: a send-status line and an index entry for the
  security report; index entries for the first-visit notice and A4/A5; and an owned record for the
  answer-cache conclusion and the schema split.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-INDEX` — CLAUDE.md's index is the de-facto authority mechanism and omits thirteen of twenty-five documents

- **Work/Issue ID (topic key):** `RISK-GROUP-INDEX` (**R7.1, R2.6**)
- **Members:** E6-27
- **Description:** **R7.1 (HIGH):** the Documents section names 11 files; **13 existing documents are
  omitted** — ARCHITECTURE, FINAL_ARCHITECTURE, INTEGRATION_PLAN, AUDIT_FINDINGS, AUDIT_2026_08_16,
  CONTENT_COVERAGE, ENROLLMENT_FAQ_APPROVAL, FIRST_VISIT_NOTICE, S42_ORG_ASKS, S42_SECURITY_REPORT,
  U7_CHECKPOINT_CONSOLIDATION and both `docs/plans/` files (S42_OPEN_QUESTIONS appears only outside the
  index, at L62). Consequences with teeth: **ARCHITECTURE.md** — the file every session must *update* (the
  end-session skill) is not one any session is told to *read*, so its ~70 invariants get re-derived by
  defect; **INTEGRATION_PLAN.md** — the document the D-152 freeze is *about* is undiscoverable from the
  file that states the freeze; **ENROLLMENT_FAQ_APPROVAL.md** — claims to be "the only launch-checklist item
  gating the guest journey's canonical question" and is invisible at session start;
  **S42_SECURITY_REPORT.md** — the declared single security document, so an index-only session re-derives it
  from DISCOVERY §6; **U7_CHECKPOINT_CONSOLIDATION.md** — unindexed yet `PROGRESS.md:1433` gates session U7
  on its §9; and **"the audit" is ambiguous** — three registers exist and the index names one. **R2.6
  (LOW):** CLAUDE.md L86–109 is a lossy compression of SPEC §5.x that declares SPEC the winner but is the
  always-loaded copy, and rule 8 (image deletion) compresses a **deferred feature's** requirement into a
  flat imperative, with only `FIRST_VISIT_NOTICE.md:122-123` explaining the feature does not exist.
- **Domain:** documentation corpus / discoverability and always-loaded rules
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:146-150` (R2.6), `:388-403` (R7.1);
  `DOCUMENT_INVENTORY.md:62-64`, `:84-90`, `:263-264`, `:625-626`, `:678`, `:811-812`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-078, D-082, D-111
- **Repository evidence:** CLAUDE.md has **no date or version marker anywhere**, has drifted before (rule 1
  said "MongoDB" until the D-082/D-111 sweep), and its candidate role is **ACTIVE, the highest-priority
  file to reconcile**.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** **nothing references CLAUDE.md back, so drift here is unpoliced** — this is the one
  file where a stale line silently steers every future session. It is also the cheapest fix in the register.
  *Which* documents stay unlisted is a taste call that belongs with the migration proposal.
- **Remaining action:** add index entries (or an explicit "deliberately unlisted because…" statement), add
  a last-reviewed marker, fix the stale descriptions (including the SPEC line-count understatement and the
  OPEN_DECISIONS description), and add one clarifying line on rule 8. Also add the clarifying sentence that
  staging is reached via CloudFront domains (`RD-12-INGRESS`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, cheapest and highest-priority
- **Historical/archive only?** no

### `RISK-GROUP-DUPLICATE-CONTENT` — the same facts, counts and numbers live in multiple files with independent lifecycles

- **Work/Issue ID (topic key):** `RISK-GROUP-DUPLICATE-CONTENT` (**R2.3, R2.4, R2.5**)
- **Members:** E6-28
- **Description:** **R2.3:** session status has three homes (ROADMAP's ✅ glyphs, PROGRESS's log, and
  `INTEGRATION_PLAN.md` §5's table with **no status column at all**, L455–473) and finding counts have two
  (`AUDIT_FINDINGS.md`'s hand-maintained count line L159–169, "this line has now been wrong three times",
  versus ROADMAP's anchored-awk derivation at `:708`/`:770` — **the register itself instructs readers to
  trust the awk, not the sentence**). **R2.4:** the four production security findings exist in **four**
  places (`S42_DISCOVERY.md:205-250`, `S42_OPEN_QUESTIONS.md:99-104`,
  `S42_SECURITY_REPORT.md:47-86`/`:109-149`, and DECISIONS D-153 §5/§7); `PROGRESS.md:7731-7732` already had
  to declare a winner once after deleting a fifth copy, but **CLAUDE.md's index points at DISCOVERY, not at
  the declared winner**, so the collision can recur. **R2.5:** numbers duplicated verbatim across files with
  independent lifecycles — the 189-item depth gap (`QUESTION_GENERATION.md:12`, `OPEN_DECISIONS.md:225`);
  the `difficulty_tiers`-are-authoring-targets rule in three homes, which OPEN_DECISIONS records was
  re-derived "at least three times" because copies drifted; checkpoint sizing **~17× apart**
  (OPEN_DECISIONS #4's dev ~4.8 GB versus U7 §1.1's staging ~285 MB, same subject, **no cross-link either
  way**); and taxonomy figures (245/34/194, 47/30/28/25) verbatim in CONTENT_COVERAGE,
  `ROADMAP.md:1763-1772` and `DECISIONS.md:19722`.
- **Domain:** documentation corpus / single source of truth
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:120-144`; `DOCUMENT_INVENTORY.md:507-510`,
  `:627-629`, `:654-655`, `:813-814`
- **Related claim IDs:** WORK-19, WORK-35, TEST-15
- **Related decision IDs:** D-153, D-223, D-273, D-331, D-341
- **Repository evidence:** ROADMAP's anchored awk is the **working precedent** for mechanical derivation.
- **Deployed/live evidence:** n/a — but note the U7/OPEN_DECISIONS 17× gap is **dev versus staging** data:
  two correct numbers about different environments, which is exactly the flattening this audit exists to
  avoid.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** one owner per number plus pointers; prefer mechanical derivation.
- **Remaining action:** assign owners; add the missing cross-links. **The checkpoint-sizing pair is not a
  contradiction and must not be "resolved" by picking one — label the environment on each.** Merge with
  `RISK-GROUP-CURRENT-STATE`'s summary-generation recommendation; they share the same fix shape.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-GROUP-EXECUTED-PLANS` — executed plans that still read as active work, one of them minting duplicate decision ids

- **Work/Issue ID (topic key):** `RISK-GROUP-EXECUTED-PLANS` (**R4.2, R1.8**)
- **Members:** E6-29
- **Description:** **R4.2 (HIGH):** `docs/plans/2026-07-19-branding-plan.md:2-4` still says "Status:
  planned, not started … run via `/start-session S22.5`" for a session executed the **same day**
  (`ROADMAP.md:326` "✅ done 2026-07-19"; `PROGRESS.md:15175-15177` "executed as written"), with no
  done/superseded marker anywhere; L44–45 instructs logging decisions at "next free D-numbers — D-064 was
  the last used" (**the log is past D-423, so following it mints duplicates**); L73 says "trust this, no
  need to re-derive" about a recon whose subject files the execution deleted; and it holds a **standing
  do-not-revert rule** (BD3's deliberate WCAG deviation, L155–156) **inside a file marked not-started** —
  the rule's home undermines the rule. **R1.8 (MEDIUM):**
  `docs/plans/2026-07-18-expansion-plan.md` §1 (L13–155) is a present-tense snapshot inside executed
  history, asserting "**Does not exist**" (L90, L96) and "already the 'next session'" (L110) about features
  that shipped a month ago, with the saving status line 87 lines above at L3; §19's "unresolved decisions"
  (L911–931) were all consumed and closed; and the file still says **Mongo** (L563, L649) because
  `docs/plans/` was deliberately excluded from the MySQL sweep (`DECISIONS.md:5174`) **without being visibly
  marked historical** — while `ROADMAP.md:5`, `:326-331` still point readers into it.
- **Domain:** documentation corpus / executed-plan archival
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:85-91` (R1.8), `:219-227` (R4.2);
  `DOCUMENT_INVENTORY.md:843-852`, `:870-879`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-049, D-064, D-065–D-069 (BD1–BD5), D-111's sweep exclusion at
  `DECISIONS.md:5174`
- **Repository evidence:** the inventory's routes: expansion-plan → **ARCHIVE with an explicit
  superseded/as-of header, not delete** (deleting breaks ROADMAP's live pointer); branding-plan → **SPLIT:
  archive the plan, promote the data** (the brand table and BD3's do-not-revert rule belong in
  `packages/ui-brand`).
- **Deployed/live evidence:** n/a, with one code-side tail — promoting the brand data into
  `packages/ui-brand` is a source change.
- **Final disposition:** `DOCUMENTATION_ONLY`, with one `ACTIVE_REMEDIATION` half
- **Justification:** status headers plus one archive convention for `docs/plans/`. **R4.2's D-number
  instruction is the one line in this group that could cause concrete damage if obeyed — fix it even if the
  rest waits.** The brand-data promotion touches `packages/ui-brand`, so it is engineering; split it out if
  the migration is documents-only.
- **Remaining action:** the headers, the convention, the D-number line, and the brand-data promotion.
- **Owner type:** documentation, with one engineering item
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist (the D-number line first)
- **Historical/archive only?** no

### `RISK-GROUP-OPS-DOC-STRATA` — ops documents carry internal live/stale pairs and stale imperative tails as the last thing a reader sees

- **Work/Issue ID (topic key):** `RISK-GROUP-OPS-DOC-STRATA` (**R1.5, R1.6, R4.6, R5.6, R4.7**)
- **Members:** E6-30
- **Description:** **R1.5:** `ARCHITECTURE.md` contradicts itself on scheduler state — L24–36 says the four
  schedules exist and "do run unattended", while L1791–1792, L1850–1851 and L2068 ("no scheduler yet")
  describe the same jobs in the older posture; L644 calls a `/stream` issue "carry-over" that L289–297
  records as fixed (D-348/D-356). **R1.6:** `QUESTION_GENERATION.md` holds **four dated strata under one
  roof** with live-voiced superseded text — the 2026-08-05 roster block L280–309 contains present-tense
  imperatives with no visual containment; §10's "Current, 2026-08-12" 696-item figure sits directly beside a
  superseded 127-item block; and the header's decision list stops at D-194 while the body cites D-342.
  **R4.6 — stale imperative tails, i.e. the last thing a reader sees:** `QUESTION_GENERATION.md` **ends**
  (L447–450) with an undated 2026-08-06 "**Next:**" naming Mistral Large 3 as the only viable generator,
  superseded by the 2026-08-11 re-measurement at L269 (Sonnet 4.5); `HINT_SOLUTION_REVIEW.md` §8's unticked
  "Validation run … First paid step" sits beside §5 reporting that run's results (**the same defect as
  LB-01**); and `U7_CHECKPOINT_CONSOLIDATION.md` §8.2/§9.2 recommend and ask about building
  `learning_sessions`, built the same day (migration `6538a95bc990_d331_learning_sessions.py`, D-332), while
  `PROGRESS.md:1433` still gates U7 on "the four answers in §9". **R5.6:** `HINT_SOLUTION_REVIEW.md`'s front
  page describes a pre-pilot world — L3 "the loop around them is not built" versus L9–10 "`review_loop.py`
  implement[s] … the bounded loop" six lines apart; L378 reviewer C "measured" versus L440 "reviewer C does
  not yet exist"; **zero grep hits for any D-262+ id** although D-262–D-269 (pilot, recall fix, repairs
  applied 44→0) all landed. **R4.7 (LOW):** `INCIDENT_RESPONSE.md:295-302` describes S34's failure drills in
  **future tense**; S34 shipped 2026-07-24, so a reader concludes no DR procedure exists.
- **Domain:** documentation corpus / operational-document currency
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:60-74` (R1.5, R1.6), `:252-260` (R4.6),
  `:262-265` (R4.7), `:305-309` (R5.6); `DOCUMENT_INVENTORY.md:270-278`, `:541-549`, `:571-579`,
  `:600-608`, `:630-638`
- **Related claim IDs:** WORK-26, WORK-28, WORK-29, WORK-20, ARCH-04, ARCH-05, ARCH-06
- **Related decision IDs:** D-194, D-251, D-252, D-254, D-262–D-269, D-331, D-332, D-342, D-348, D-356
- **Repository evidence:** `HINT_SOLUTION_REVIEW`'s stale front page is contradicted by **source at HEAD**
  (`review_loop.py` exists; `ai_pipeline.py:821-827`). The inventory's routes: ARCHITECTURE → ACTIVE, needs
  an index entry and de-duplicated scheduling state; QUESTION_GENERATION → ACTIVE, needs the state block and
  the trailing "Next:" dated-and-boxed or evicted and the 08-05 roster moved to an appendix;
  INCIDENT_RESPONSE → ACTIVE, needs a date header, the S34 tense fix and one freeze-context line;
  HINT_SOLUTION_REVIEW → **ACTIVE but requires reconciliation before being trusted**, cannot be archived,
  highest reconciliation priority of the ops documents.
- **Deployed/live evidence:** `ARCHITECTURE`'s scheduler pair is contradicted by the **deployed**
  EventBridge state per its own top section. **Do not resolve either contradiction from the document
  alone.**
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** de-duplicate the scheduling state, box or evict the superseded strata, and fix the two
  trailing imperatives. **Merge R5.6 and R4.6's HINT_SOLUTION_REVIEW clause with `DOC-HINT-SOLUTION-REVIEW`**
  — three independent readers found the same defect from three directions.
- **Remaining action:** the edits. The scheduler half overlaps `DOC-SCHEDULER-SECTIONS`; the U7 clause
  overlaps `DOC-U7-BANNER` and `DOC-SNAPSHOT-BANNERS`; the `QUESTION_GENERATION` "Next:" tail overlaps
  `DOC-CONTENT-PIPELINE` (DRIFT-48). Add the freeze-context line to `INCIDENT_RESPONSE.md`
  (`RISK-GROUP-FREEZE`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-R7.3-DANGLING-REFS` — dangling and out-of-repository references

- **Work/Issue ID (topic key):** `R7.3`
- **Members:** E6-32
- **Description:** `DECISIONS.md:3842` references `docs/codebase-analysis/` — **no such directory exists in
  this repository** (verified); the intended referent is `../IntelliChoice-web/docs/codebase-analysis/`
  (`S42_DISCOVERY.md:8`), an out-of-repository path cited as if local.
  `ENROLLMENT_FAQ_APPROVAL.md:93-94` instructs syncing a `knowledge-content copy/` directory that no longer
  exists (deleted, D-253), and its manifest line-number pointer is dead. `ROADMAP.md:5` and `:326-331`
  point readers into `docs/plans/` without noting they are historical.
- **Domain:** documentation corpus / reference integrity
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:413-418`; `DOCUMENT_INVENTORY.md:681-682`,
  `:899-906`
- **Related claim IDs:** INT-29
- **Related decision IDs:** D-253
- **Repository evidence:** four pointer defects, all located.
- **Deployed/live evidence:** n/a; note the out-of-repository path resolves into `../IntelliChoice-web`,
  which is deliberately out of inspection scope.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** four pointer fixes; low effort, low risk.
- **Remaining action:** the fixes. **The `../IntelliChoice-web` reference must be written as explicitly
  out-of-repository, not "fixed" into a local path that will never exist.** The `docs/plans/` pointers
  interact with `RISK-GROUP-EXECUTED-PLANS` (archive, do not delete). The ENROLLMENT_FAQ clause also
  appears in `INT-29-FAQ`.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-R6.4-SESSION-LABELS` — session-label collisions make cross-document session references ambiguous

- **Work/Issue ID (topic key):** `R6.4`
- **Members:** E6-33
- **Description:** **"C1"** names both the chat-content session (= S17; `expansion-plan.md:714`,
  `ROADMAP.md:203`) and the 2026-08-11 full-taxonomy content-seeding session (`ROADMAP.md:1718`,
  `CONTENT_COVERAGE.md:3`). **"S43"** is both ROADMAP's frozen `IcProfileAdapter` session and a
  self-applied label on the D-115/D-116 work (flagged in-text at `DECISIONS.md:5742-5744`). PROGRESS's log
  uses unnumbered "S44"–"S66" labels for Phase 0B sessions (`PROGRESS.md:12644-13695`) that collide with
  ROADMAP's frozen S44–S47 — most consequentially `PROGRESS.md:13559`'s **completed** "S45 (unnumbered)"
  against `ROADMAP.md:1501`'s **unstarted** consent-session S45, which `FIRST_VISIT_NOTICE.md:235` names as
  its owner. **"§2.6"** resolves to `INTEGRATION_PLAN.md`, not SPEC. The supersession map adds a fourth: the
  D-049 session-renumbering translation layer covers old **S17–S23 only**.
- **Domain:** documentation corpus / session and section namespaces
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:358-367`; `DOCUMENT_INVENTORY.md:483-485`,
  `:704-706`
- **Related claim IDs:** T-02
- **Related decision IDs:** D-049, D-115, D-116, D-152
- **Repository evidence:** as cited.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** a disambiguation convention plus per-collision annotations.
- **Remaining action:** the convention. **The S45 collision touches two open items —
  `DISCLOSURES-LEGAL`'s product decision and `FIRST-VISIT-REVERIFY`'s re-verification — so fixing it is a
  prerequisite for stating who owns them.** Extend or bound D-049's translation layer, which has no stated
  translation for pre-restructure references above S23 (`G7-SESSION-RENUMBER`).
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `RISK-R6.5-SUPERSESSION-DIRECTION` — supersession runs opposite to citation direction, and corrections live only in the correcting document

- **Work/Issue ID (topic key):** `R6.5`
- **Members:** E6-34
- **Description:** `S42_OPEN_QUESTIONS.md` supersedes `S42_DISCOVERY.md` §7 on ask currency but **cites
  DISCOVERY as its evidence base** (L3), and DISCOVERY carries **no forward pointer** — while DISCOVERY is
  the CLAUDE.md-indexed one and OPEN_QUESTIONS is the newer and correct one. Likewise
  `S42_DISCOVERY.md` corrects `INTEGRATION_PLAN.md` twice (L130 "28 columns", L265–267 the liveness
  endpoint) and `INTEGRATION_PLAN.md:47`/`:265`/`:528` **still carries the uncorrected text** — the
  correction lives only in the correcting document. And `INTEGRATION_PLAN.md` §8 patches §1/§5 **by
  reference** ("§5's S42 row shrinks accordingly", L615) without editing them.
- **Domain:** documentation corpus / supersession mechanics
- **Original source(s):** `DOCUMENTATION_RISK_REGISTER.md:369-375`; `DOCUMENT_INVENTORY.md:332-335`,
  `:731-733`, `:759-766`
- **Related claim IDs:** INT-06, INT-07, INT-26, INT-28
- **Related decision IDs:** D-151, D-152, D-153
- **Repository evidence:** the corrected facts are **production-system** facts read from
  `../IntelliChoice-web` source; the **uncorrected copies are the ones a session reads first**.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** forward pointers on the superseded documents, and in-place application of the two
  DISCOVERY corrections.
- **Remaining action:** the pointers and the two in-place corrections. **Pairs tightly with
  `RISK-GROUP-FREEZE` — the same S42 files — so do both edits in one pass per file.**
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-SNAPSHOT-BANNERS` — measurement-snapshot documents carry status columns as if current

- **Work/Issue ID (topic key):** `DOC-SNAPSHOT-BANNERS`
- **Members:** E6-35
- **Description:** `CONTENT_COVERAGE.md` (stale risk **HIGH**) has status columns describing needs that were
  built the same day or since — "needs the Phase R router" (done 2026-08-11), "⛔ needs figure support
  (Phase 5 decision gate)" (built, D-279), `place_value_compare` 15/15 wrong-shape (re-authored to 0/15),
  "4 bands populated" (now 7), bank size 47/30/28/25 long since superseded (958+). **A reader would rebuild
  an existing router or re-author fixed items.** `U7_CHECKPOINT_CONSOLIDATION.md` (stale risk **HIGH**) is
  single-dated 2026-08-14, **never edited after the day it was written**, contains self-expiring claims with
  no absolute dates ("nothing is eligible for at least another 8 days"), still asks a §9 question answered
  the same day, and its line 3 points at the wrong section (an error D-331 repeats).
  `QUESTION_GENERATION.md`'s "Current, 2026-08-12" 696-item block is "a measurement with no expiry marker".
- **Domain:** documentation corpus / measurement snapshots
- **Original source(s):** `DOCUMENT_INVENTORY.md:571-579`, `:610-638`, `:640-663`; adjacent register
  entries R1.6, R2.5, R3.5, R4.6
- **Related claim IDs:** WORK-19, WORK-20, WORK-22, WORK-23, WORK-30
- **Related decision IDs:** D-223, D-273, D-279, D-331, D-332, D-342
- **Repository evidence:** candidate role for CONTENT_COVERAGE: **REFERENCE with a mandatory
  as-of/superseded banner** — the taxonomy facts are worth keeping, the status columns are not.
- **Deployed/live evidence:** U7's numbers are **staging** measurements (~285 MB) against OPEN_DECISIONS
  #4's **dev** numbers (~4.8 GB) — two environments, ~17× apart, that must stay labelled separately.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** one as-of banner per snapshot plus a convention that every measured number carries its
  date and environment.
- **Remaining action:** the banners. **This is the same defect class as LB-02, LB-03 and LB-07 (a measured
  number quoted without its date, denominator, environment or build SHA), so consider one corpus-wide
  convention covering all of them rather than per-file banners: *every measurement states date,
  environment/build, and denominator*.** Combine with `DOC-VINTAGE-HEADERS` into one house rule.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `DOC-VINTAGE-HEADERS` — living documents carry no date, version or last-reviewed marker

- **Work/Issue ID (topic key):** `DOC-VINTAGE-HEADERS`
- **Members:** E6-38
- **Description:** Four load-bearing documents have **no vintage marker at all**. `CLAUDE.md` —
  "continuously maintained present tense; **no date or version marker anywhere**", and it has drifted before
  (rule 1 said "MongoDB" for many sessions until the D-082/D-111 sweep). `SPEC.md` — "**No version header,
  no date, no changelog**" across 4,210 lines. `INCIDENT_RESPONSE.md` — "**no date or version header** — a
  paragraph's vintage is inferable only from the D-number it cites". `QUESTION_GENERATION.md` — "No 'last
  updated' line; four dated strata coexist."
- **Domain:** documentation corpus / vintage marking
- **Original source(s):** `DOCUMENT_INVENTORY.md:62-64`, `:89-90`, `:101-104`, `:531-532`, `:558-561`;
  related recommendation `DOCUMENTATION_RISK_REGISTER.md:433-434`
- **Related claim IDs:** none owning
- **Related decision IDs:** D-082, D-111
- **Repository evidence:** because nothing references CLAUDE.md back, **drift there is unpoliced**.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** the **cheapest structural improvement in the whole extraction and a precondition for
  most others** — a stale line is only detectable if the document says when it was last true.
- **Remaining action:** a one-line header convention applied to the living documents. Combine with
  `DOC-SNAPSHOT-BANNERS`'s measurement convention into one house rule.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist, first
- **Historical/archive only?** no

### `DOC-LINE-CITATION-DRIFT` — `file:line` citations drift and there is no re-verification convention

- **Work/Issue ID (topic key):** `DOC-LINE-CITATION-DRIFT`
- **Members:** E6-39
- **Description:** Documents cite `file:line` and the lines move. `TRACEABILITY.md`'s rows "cite file:line
  and test names that move — it was already burned once: the §5.8.5 row was 'evidence for a requirement
  satisfied by code no student could reach' until D-226 rewrote it".
  `HINT_SOLUTION_REVIEW.md:452` cites `ai_pipeline.py:1769` while the constant is at `:834` and its only
  gate at `:2005` (verified on HEAD). `ENROLLMENT_FAQ_APPROVAL.md` has a dead manifest line-number pointer.
  The documentation-risk register's own line numbers are stamped "as of 2026-08-19", which is the discipline
  the rest of the corpus lacks.
- **Domain:** documentation corpus / evidence-citation durability
- **Original source(s):** `DOCUMENT_INVENTORY.md:481-485`, `:681-682`;
  `LIVE_BEHAVIOR_FINDINGS.md:120-122`, `:147-148`; `DOCUMENTATION_RISK_REGISTER.md:17`
- **Related claim IDs:** WORK-29, TEST-02, TEST-08, TEST-11; the DRIFT-60 citation batch
- **Related decision IDs:** D-124, D-226
- **Repository evidence:** repository-only, but the drift is caused by **source movement**, so any
  convention must survive refactors — prefer symbol or anchor citations over bare line numbers for
  load-bearing evidence rows.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `DOCUMENTATION_ONLY`
- **Justification:** adopt an as-of stamp for line citations (the register's own practice) and prefer stable
  anchors where the citation is load-bearing.
- **Remaining action:** the convention. **Apply it to `TRACEABILITY.md` first — it is the §2.6 criterion-1
  instrument, so a drifted citation there degrades launch evidence, not just readability.** Overlaps
  `BATCH-LOW-CITATIONS` (the nine already-identified stale citations) and `TRACEABILITY-ARITHMETIC`.
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `BATCH-LOW-CITATIONS` — LOW batch A: stale citations, counts and denominators

- **Work/Issue ID (topic key):** `BATCH-LOW-CITATIONS`
- **Members (9, verbatim from E3's batch A):** **DRIFT-60** — TRACEABILITY's implementation line citations
  have drifted: five cited anchors are stale against unchanged behaviour (`gateway.py:58-110` no longer
  spans the four cost mechanisms; `worst_case_cost_cents` is at `:182-194`, not `:158`;
  `attendance.py:71-80` → the function is now `:96-127`; `authorization.py:39-43` → now `:38-45`; TEST-02
  row 5 carries the same staleness; REQ-10's router symbol lines are 1819/797, not 1120/414), plus a
  secondary COST-04 point — the public `worst_case_cost_cents` reads as the pre-flight reservation but
  `generate_structured` recomputes the expression inline and the public method's only callers are tests.
  **DRIFT-61** — the measured spend undercount is **32.0%** in the documents and **31%** in the
  code/script/test that pin it, and the script's own raw numbers compute to **≈30.8%**. **DRIFT-62** —
  TRACEABILITY cites `test_judge_flags_reject_and_borderline_score_sets_high_priority`, a name that does not
  exist: the file carries `..._no_longer_sets_high_priority`, **a rename that inverts the clause** because
  D-249 removed the borderline→high-priority routing; six of seven named tests exist and the shape route is
  genuinely deleted. **DRIFT-63** — TRACEABILITY's self-cited near-miss names the **wrong commit**: the
  co-existence at `c44414f` is real but **neither line was written by it** (`git log -S` attributes them to
  `7430810` and `be6d22d`), and `c44414f` touched no T-02 table row; the lesson stands, the
  instrument-reliability citation does not. **DRIFT-64** — the "one row per finding" invariant is unheld in
  the **reverse** direction: 94 `### AUD-` headings → 93 unique ids, every section has a row, but **7** row
  ids have no detail section (`AUD-F-05` folded into a combined heading, plus F-16, F-17, F-18, F-19, F-20,
  F-38 as rows only); all are closed, so no count is affected today. **DRIFT-65** — the error-vocabulary
  spec's own header still says "twelve rules, five different 409s" against a set that matches exactly
  (learning-web 10, chat-web 8). **DRIFT-77** — ARCHITECTURE's storage-split table under-describes Postgres
  by **twelve shipped tables** (`study_sessions`, `study_items`, `study_attempts`, `mastery`,
  `learning_gain`, `hint_events`, `stage_transitions`, `interrupt_approvals`, `question_templates`,
  `question_variants`, `question_validation_runs`, `evaluation_results`) against 37 `__tablename__`
  declarations; every row that *is* present is real. **DRIFT-90** — the enrollment-FAQ content-document
  citation omits the `documents/` path segment; the substance is confirmed (still `status: draft`, the DRAFT
  banner intact, the four draft facts unchanged, and `status: approved` on the preceding entry proving the
  value is a live discriminator). **DRIFT-100** — TRACEABILITY's §5.27 structural row counts **31**
  `extra="forbid"` models against **41**, and its named mechanism is weaker than stated: **pyright does not
  fail if an `extra="forbid"` is deleted**, so clause (b) is satisfied only for the Bedrock-payload subset
  the PII-floor test pins, not for the other six models; six of six named artifacts exist, four of six name
  a mechanism that exists, and the two "descriptive" rows are consistent with the fence.
- **Description:** Nine LOW entries where the *substance* holds and a citation, count, path or denominator
  does not. The common cause is that **nothing re-derives these figures when code moves**.
- **Domain:** documentation precision / traceability
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:693`, `:704`, `:715`, `:726`, `:737`, `:748`,
  `:880`, `:1023`, `:1135`
- **Related claim IDs:** COST-03, COST-04, COST-05, REQ-10, REQ-12, REQ-20, SEC-03, SEC-06, SEC-11,
  TEST-02, TEST-04, TEST-08, TEST-11, TEST-15, TEST-16, TEST-17, TEST-22, TEST-26, ARCH-19, ARCH-21,
  ARCH-22, INT-29
- **Related decision IDs:** D-174, D-178, D-226, D-249, D-294
- **Repository evidence:** all nine verified by direct file read, grep or `git log -S`. F-08 makes DRIFT-100's
  41 **executed** (`grep … | wc -l` → 41, zero in test files, concentrated in four files with 35 in
  `bedrock.py` alone), and F-01 independently confirms `worst_case_cost_cents` at `:182-194`, corroborating
  DRIFT-60's stale anchor.
- **Deployed/live evidence:** n/a for eight. **DRIFT-90's substance is unresolvable**: whether the deployed
  knowledge store still holds the draft FAQ needs database content, routed to forbidden — a fail-closed
  question **no phase could answer**. Keep it visible (`DB-CONTENT-VERIFY`, `INT-29-FAQ`).
- **Final disposition:** `DOCUMENTATION_ONLY` (all nine; no exceptions in this batch)
- **Justification:** every member is a citation, count or path correction against confirmed substance; no
  code behaviour is in question. The nearest thing to a judgement is whether TRACEABILITY should carry
  line-number citations at all, since they decay by construction — a convention suggestion, not a decision
  (`DOC-LINE-CITATION-DRIFT`).
- **Remaining action:** the nine corrections. **Three flags.** (1) **DRIFT-100's mechanism-strength half is
  more than a count** — "pyright does not fail if an `extra="forbid"` is deleted" means a *structural*
  verdict's clause (b) is unmet for six named models, which is a traceability-integrity point of the same
  class as DRIFT-38/39 and arguably belongs with `TRACEABILITY-ARITHMETIC`; the count edit itself is in
  `DOC-TEST-CLAIM-WORDING`. (2) **DRIFT-63 is a citation inside the file's own reliability warning** — low
  stakes, high irony, worth one line in the report. (3) **DRIFT-64's discrepancy: the register's title says
  six and its body says seven row ids — carry the body's number.**
- **Owner type:** documentation
- **Reopen condition:** n/a · **PROJECT_STATE?** no — migration worklist
- **Historical/archive only?** no

### `BATCH-LOW-STALE-STATUS` — LOW batch B: stale in-repository comments and status lines contradicted by their own artifact

- **Work/Issue ID (topic key):** `BATCH-LOW-STALE-STATUS`
- **Members (10, verbatim from E3's batch B):** **DRIFT-58** — the e2e isolation finding recorded unresolved
  against a spec that now carries two dedicated fixture students (`FIXTURES.studentJourney`,
  `studentResume`; `e2e/config.ts:128-165` defines three); the per-test-fixture remedy is present, the
  `beforeEach` session-clear remedy was **not** applied, and PROGRESS's last entry (2026-08-07) is stale.
  LOW, medium-adjacent. **[EXCEPTION → `DRIFT-58-E2E-ISOLATION`, RESOLVED at claim scope, with a DEFERRED
  residual.]** **DRIFT-75** — the scheduled-jobs module header says "Four jobs are defined, three are
  enabled"; its own `locals.jobs` block sets **five defined, four enabled** (`session-consolidate`
  postdates the header). Comment only, no functional effect. **DRIFT-76** — ARCHITECTURE.md uses
  "retention" for two different jobs in the same nine lines; **both statements are true** because they name
  different jobs (`retention-purge` **is** scheduled at `cron(50 18 * * ? *)`; `checkpoint_retention_cli`
  has no schedule and appears nowhere in terraform). Documentation clarity, not configuration drift.
  **DRIFT-81** — `terraform/environments/staging/variables.tf:187` asserts "there is no tfvars file in this
  environment" while `terraform.tfvars` **exists** (gitignored, confirmed by `git check-ignore`), and
  `main.tf:35` refers to "the tfvars pin" as if it exists; its content was deliberately unread and it is
  the single unresolved dependency for several other conclusions. **DRIFT-91** — one app module imports
  `current_week_key` from the **MySQL adapter module** rather than shared `org_time` and writes its value as
  the `week_id` into Postgres; both apps also construct `MySQLProfileAdapter` directly in `main.py` rather
  than behind a factory. The seam's substance is intact (zero raw-SQL or table-name hits in `apps/`; all 21
  app-level sites go through Protocol methods; attendance coerced at the seam).
  **[EXCEPTION → `DRIFT-91-ORGTIME-IMPORT`, ACTIVE_REMEDIATION.]** **DRIFT-93** — PROGRESS carries
  D-401/D-406 as unblocked-but-unapplied against a commit titled "applied"; both are fully present in
  configuration and committed before the disputed date (`15bb6b3`, `73e29c6`, `2e301d6`); the register's own
  caution is "a commit title is a *claim* of an apply, not the apply".
  **[EXCEPTION → `DRIFT-93-D401-D406-APPLIED`, RESOLVED.]** **DRIFT-94** — U7 §9.2 still asks whether
  `learning_sessions` gets built; it is built, migrated (in the live chain), modelled, and has a
  **scheduled** producer, and the earlier drop migration is not a later reversal — it revises a 2026-07-15
  revision and dropped the S5 stand-in. **DRIFT-95** — U7 §10 still records the duplicate `learning_gain`
  observation as un-investigated four days after D-336 diagnosed it (`POST /exam/finalize` carries no
  `Idempotency-Key`, so a retry re-inserts; two byte-identical rows 46 s apart; history returned 10
  summaries for 9 cycles) and closed it by measurement (staging holds "9 gain rows and 0 duplicate
  pre-assessment ids"); the cause is fixed and the existing duplicate row was deliberately left alone as
  the user's call. **DRIFT-97** — OPEN_DECISIONS #6 is "parked, not blocking" while PROGRESS still lists it
  as "blocked on the YouTube key"; the underlying guard is confirmed verbatim and sound
  (`saw_whole_channel` returning `covered == 0 and deferred == 0`, the 182-videos-inactive loss event in the
  docstring, and a regression test targeting the *computation* rather than the effect). **DRIFT-102** — the
  scheduled-jobs header still says three enabled while its own `locals.jobs` enables four; the
  OPEN_DECISIONS #4 option-D design is otherwise **built as chosen** (`session-consolidate` first in the
  daily order per D-356; a full chain of CLI, two migrations, model and repository, the constant and four
  test files; and the "then keep it there" half honoured by omission — `checkpoint_retention_cli`
  deliberately not in `locals.jobs`).
- **Description:** Ten LOW entries where a comment, status line or open question is contradicted by the same
  file, the adjacent configuration, or a dated commit. Cause: status is recorded where the work happened and
  the originating note is never retired.
- **Domain:** documentation / infrastructure comments / status hygiene
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:671`, `:858`, `:869`, `:924`, `:1034`, `:1056`,
  `:1067`, `:1078`, `:1100`, `:1157`
- **Related claim IDs:** WORK-07, WORK-08, WORK-13, WORK-14, WORK-19, WORK-20, WORK-22, WORK-24, WORK-35,
  WORK-37, ARCH-04, ARCH-05, ARCH-06, ARCH-07, ARCH-28, ARCH-29, ARCH-34, COST-23, COST-24, COST-28,
  INT-15, INT-32, INT-35
- **Related decision IDs:** D-082, D-083, D-152 §1, D-288, D-326, D-331, D-333, D-336, D-337, D-342,
  D-356, D-365 §2, D-367, D-390, D-401, D-406, D-419, AUD-F-06
- **Repository evidence:** per member; DRIFT-93 additionally rests on `git log --oneline` dating, DRIFT-94 on
  the migration `down_revision` chain, and DRIFT-81 on `git check-ignore`. F-17 confirms WORK-37's guard by
  execution (the three `test_sync_preflight.py` tests pinning the 182-row computation all passed) and
  WORK-03's replay confirms DRIFT-94's migration chain.
- **Deployed/live evidence:** DRIFT-75/76/102's **schedule half is confirmed at runtime** — schedules exact,
  including the per-job retry asymmetry (`memory-consolidate = 0`) — **but RD-01 shows the dead-man's switch
  is structurally non-functional**, so "has it fired successfully?" remains unanswered by design. DRIFT-94's
  deployed half (is migration `6538a95bc990` applied?) was routed to forbidden. DRIFT-81's tfvars question
  was **dissolved rather than answered** — RD-05 settled the NAT by direct AWS observation, so no tfvars read
  was needed; the comment defect itself is untouched.
- **Final disposition:** `DOCUMENTATION_ONLY` as the batch default, with **three exceptions** as marked
  above.
- **Justification:** retire stale comments and status lines. Four flags. (1) **DRIFT-75 and DRIFT-102 are one
  operative comment**, explicitly cross-linked by the register — both appear in coverage, but the remediation
  is a single line of terraform comment. (2) **DRIFT-94 and DRIFT-95 join DRIFT-47** as three stale sections
  of `U7_CHECKPOINT_CONSOLIDATION.md`; one banner closes all three (`DOC-U7-BANNER`). (3) **DRIFT-58's
  residual must not be flattened** — LB-04 refuted the *claim*; it did not run the seventeen-spec
  combination. (4) **DRIFT-91 is the only member where CLAUDE.md's seam-honesty rule is in play**, and the
  register is careful: the value is org- and SPEC-derived and the seam's substance is intact, so it is
  housekeeping and **not** the class of defect CLAUDE.md calls a real defect.
- **Remaining action:** the seven documentation edits plus the three exception entries. **DRIFT-81 remains a
  standing hazard for future audits** — a gitignored tfvars file means the tracked tree does not determine
  the plan; record it as a known limitation rather than "fixed by RD-05". DRIFT-97 is *about* a parked
  decision (#6) but needs no new one: both statuses are deferral states with an identical practical
  consequence, and it would only grade MEDIUM if #6 fed a launch checklist.
- **Owner type:** documentation; engineering for DRIFT-91
- **Reopen condition:** n/a · **PROJECT_STATE?** no for the batch; yes for the three exceptions
- **Historical/archive only?** no

### `BATCH-LOW-OVERSTATEMENT` — LOW batch C: documentation reads wider than the code

- **Work/Issue ID (topic key):** `BATCH-LOW-OVERSTATEMENT`
- **Members (11, verbatim from E3's batch C):** **DRIFT-53** — the absolute "no PII in Postgres" rule is
  stated in three documents (CLAUDE.md rule 1, SPEC §5.4/§5.30, INCIDENT_RESPONSE) **without D-050's
  four-column exemption**. The floor's intent holds: exactly four PII-shaped `mapped_column` hits, all
  org-published public website content (`org_branches.address/phone/email`, `org_team_members.name`), each
  explicitly allowlisted in the purity test with `source_url`/`content_hash` provenance columns, and
  `BranchInfo.manager_email` comes from MySQL and is not persisted — but a reader auditing the schema against
  the documents would find four apparent violations. LOW, medium-adjacent. **DRIFT-67** — "interrupts after
  every incorrect answer" is broader than the implemented predicate: routing requires `phase == "study"`
  **and** `last_is_correct is False` **and** `last_study_attempt_id is not None`, so an incorrect *final
  pre-exam* answer deliberately does not interrupt; the exclusion is documented in-code as deliberate and
  the resume path is type-discriminated. **DRIFT-69** — CLAUDE.md rule 8 states the solution-image deletion
  rule as **active behaviour for a feature with no code** (see `IMAGE-WORK-PARK`); TRACEABILITY already
  records the disposition. **DRIFT-71** — **two LOW drifts:** (a) the API accepts `zip_code`/`city`/`address`
  and the missing-location message mentions all three, but the modal exposes only ZIP and city; (b)
  `chat-api/graph/state.py:4-6` still says the location fields "are still not present — S15 adds them", and
  S15 shipped with D-045's resume-value design, so the docstring describes an **abandoned plan**. The rest of
  the requirement holds: notice copy verbatim against SPEC, delivered through the `interrupt()` payload
  before any collection, geolocation only on explicit button press, coordinates function-local ("Precise
  coordinates never leave this function"), and MCP audit rows persisting no arguments. **DRIFT-72** — a
  seventh interim outcome label persisted beside the six terminal ones in a nullable unconstrained `String`.
  **[EXCEPTION → `DRIFT-72-OUTCOME-ENUM`, OBSERVATION_ONLY.]** **DRIFT-73** — "difficulty label to be
  superseded by observed evidence" reads as a live mechanism; **no recalibration from observed response data
  exists** (`recalibrat` returns documentation only; `success_rate`/`p_value`/"observed
  difficulty"/`item_difficulty` return nothing outside tests). **Adjudication: this is correct** — SPEC's own
  trigger ("as production data accumulates") has not occurred and TRACEABILITY dispositions it as "a
  requirement whose trigger condition has not occurred". Wording tension only. **DRIFT-78** — the ledger
  locates LangSmith PII masking in **task definitions**; it is enforced in **application code**
  (`LANGSMITH_HIDE_INPUTS`/`_HIDE_OUTPUTS = "true"` by assignment, not `setdefault`, so an env var cannot
  opt out, with a test asserting it is not optional); the other three sink elements *are* in terraform, so a
  reader inspecting a task definition alone would not see the control. **DRIFT-79** — "health endpoints emit
  no telemetry at all" is true of **traces**, not logs: two-layer trace suppression is present exactly as
  described (`excluded_urls=HEALTH_ENDPOINT_URLS`, `/metrics` deliberately not excluded, both apps wrapping
  the whole `/readyz` body in `suppress_instrumentation()`, six pinning tests) but the access-log middleware
  has **no path exclusion**, so `/readyz` still produces one JSON log line per poll. **DRIFT-86** — the
  cost-anomaly runbook's `desired_count` lever. **[EXCEPTION → `DRIFT-86-COST-RUNBOOK`,
  ACTIVE_REMEDIATION.]** **DRIFT-88** — `ATTENDANCE_CHECKS{result="unknown"}` means "**adapter threw**",
  while a genuine `AttendanceStatus.UNKNOWN` gate result increments `result="blocked"`; the P1-8 fix is
  present (the increment above the return inside except, plus a `logger.warning`) and all three declared
  labels are emitted somewhere — but the metric **cannot separate the routine D-152 §2 production path
  (`signups.attended = null`) from a recorded absence**. **DRIFT-92** — "citations carry `effective_to`" is
  imprecise (see `WORK-04-ANSWER-CACHE`); no answer cache exists, and the named clamp would need an extra
  lookup, which *strengthens* the "this is a decision, not an optimisation" conclusion.
- **Description:** Eleven LOW entries where a rule, claim or metric name is stated more broadly than the
  implementation supports. **In every case the narrow implementation is correct and deliberate**; the defect
  is that a reader relying on the wider statement would be wrong.
- **Domain:** documentation scope / privacy rules / observability semantics
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:616`, `:770`, `:792`, `:814`, `:825`, `:836`,
  `:891`, `:902`, `:979`, `:1001`, `:1045`
- **Related claim IDs:** REQ-01, REQ-02, REQ-10, REQ-11, REQ-12, REQ-13, REQ-14, REQ-21, REQ-22, REQ-24,
  REQ-28, REQ-31, REQ-33, REQ-41, REQ-42, REQ-52, SEC-01, SEC-12, SEC-15, SEC-23, COST-13, COST-16,
  COST-20, COST-27, ARCH-30, ARCH-32, INT-23, WORK-04
- **Related decision IDs:** D-022, D-045, D-050, D-078, D-104, D-152 §2, D-242, D-249, D-377, AUD-F-30
- **Repository evidence:** DRIFT-53 rests on an exhaustive `mapped_column` grep plus the purity-test
  allowlist; DRIFT-69 on a five-pattern absence sweep; DRIFT-79 on six passing suppression tests plus the
  middleware's missing exclusion. F-17 confirms REQ-28/SEC-12's branch-locator suite, SEC-23/COST-27/ARCH-30
  ("masking is assignment, not `setdefault`"), COST-20's adjacent halves and COST-16.
- **Deployed/live evidence:** 3B-1 confirms ARCH-30 against the deployed state. **RD-04 is a live
  counterpoint on the same subsystem as DRIFT-78:** LangSmith ingestion is failing at volume right now and
  by design nobody is paged (`LANGSMITH-INGEST`). RD-03 makes DRIFT-86's runbook accuracy matter. DRIFT-53,
  67, 69, 72, 79 and 92 were untouched by later phases; DRIFT-73's trigger still has not occurred.
- **Final disposition:** `DOCUMENTATION_ONLY` as the batch default, with **two exceptions** as marked.
- **Justification:** in each case the code is right — often deliberately, with the reason written at the site
  — and the statement is too wide.
- **Remaining action:** the nine documentation edits plus the two exception entries. **Four flags.**
  (1) **DRIFT-88 is the one with a production consequence**, not just wording: per D-152 §2
  `signups.attended = null` is a **routine** production path, so the metric that is supposed to show
  attendance-gate behaviour **cannot distinguish the common case from a recorded absence** — and no alarm
  reads this metric (DRIFT-21 / `COST-22-LABEL-PREINIT`). (2) **DRIFT-53's four columns are correct and
  allowlisted — the report must not imply a PII violation**; the defect is that three rule-stating documents
  omit the exemption. (3) **DRIFT-79's log leg is a real cost and noise item** at ALB health-check
  frequency, even though the trace claim it corrects is fine. (4) **DRIFT-71(b) duplicates DRIFT-33's stale
  docstring** — one defect, two entries, both must appear in coverage. Two latent decisions inside are
  handled elsewhere: DRIFT-69's rule-8 subject is D-078's settled deferral, and DRIFT-88's label split would
  be a mechanical metric redesign.
- **Owner type:** documentation; engineering for DRIFT-86
- **Reopen condition:** n/a · **PROJECT_STATE?** no for the batch; yes for DRIFT-86
- **Historical/archive only?** no

### `BATCH-LOW-UNMARKED-SPEC` — LOW batch D: SPEC and ledger enumerations unowned or unmarked after a decided departure

- **Work/Issue ID (topic key):** `BATCH-LOW-UNMARKED-SPEC`
- **Members (5, verbatim from E3's batch D):** **DRIFT-55** — two of SPEC's thirteen structured-output
  artifact types have no Pydantic schema. Eleven of thirteen have a model and a non-mock production call
  site. **Topic mapping:** `BedrockTask.TOPIC_MAPPING` exists with no payload model, no response model and
  no caller — a reserved-but-unbuilt slot the ledger does not mention. **Email draft:** no Pydantic LLM
  response model; both email-draft paths are server-composed and deterministic. Both gaps are
  **dispositioned** (D-024's deterministic topic resolver; D-020's §5.6.4 deterministic email composition),
  so the gap is document-side. Two models are also production-dead: `GeneratedTemplateResponse` (referenced
  only by `mock_provider.py`) and `LlmCitation` (no reference outside `bedrock.py`). LOW, medium-adjacent
  (adjudicated down from MEDIUM). **DRIFT-66** — SPEC §5.26.3's internal NL2SQL pipeline.
  **[EXCEPTION → `DRIFT-66-NL2SQL`, USER_DECISION_REQUIRED, UD-12(d).]** **DRIFT-96** —
  `CONTENT_COVERAGE.md` names `selection` (11 rows) as its own answer-model family needing a "predicate
  verifier over stated objects"; **`selection` is not a distinct answer model** — zero hits across
  `packages/curriculum`. The capability landed under a different design: comparison questions are expressed
  through the **`value`** model, as the router's own tests state ("It is `value` because the answer *is* a
  value — the point is that `Max` does the selecting"). Worth naming so a future reader does not search for
  a missing verifier. **DRIFT-99** — the ledger's "§6.1 track not started" temporal note is superseded: the
  T-02 enumeration **shipped 2026-08-15** (`docs/FIRST_VISIT_NOTICE.md`, 237 lines, `da2549f`, all eleven
  disclosures as copy in two registers, titled for T-02, with "S45 transcribes this; it does not draft it").
  The claim's **substance holds exactly** — no notice component and no first-visit gate in
  `apps/learning-web/src`: thirteen `components/*.tsx` and eight `screens/*Screen.tsx`, none named
  notice/disclosure/consent; a case-insensitive grep returns only forward-looking comments; no
  `localStorage`/`sessionStorage` first-visit flag (the only keys are the dev token, sub and role). The
  sibling pattern exists in the chat app. S45 remains unbuilt inside the frozen block. **DRIFT-101** —
  TRACEABILITY's T-02 block still asserts the §6.1 track has not started and that "**None of the eleven is
  enumerated as a deliverable anywhere in ROADMAP.md**" — both now false (`ROADMAP.md:2148-2157` enumerates
  them; FIRST_VISIT_NOTICE writes them out). The disposition text is present as claimed and **the order
  held** (the list landed before any build, which is what the claim requires). Both false statements sit
  under an explicit preservation marker ("*the finding as filed, kept because the reasoning is the
  record*"), which softens the reading — but the block never adds a "since superseded" pointer, and
  **TRACEABILITY contains no reference to `docs/FIRST_VISIT_NOTICE.md` at all**, so the traceability
  document does not cite the artifact that discharged its own prerequisite.
- **Description:** Five LOW entries where a named list, family or requirement in SPEC, the ledger or
  TRACEABILITY no longer matches what shipped, and the departure was either decided elsewhere or never
  disposed of at all.
- **Domain:** SPEC governance / traceability / legal-track documentation
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:638`, `:759`, `:1089`, `:1124`, `:1146`
- **Related claim IDs:** REQ-05, REQ-06, REQ-16, REQ-17, REQ-25, REQ-26, REQ-41, COST-02, SEC-20,
  TEST-05, TEST-10, WORK-30, WORK-32
- **Related decision IDs:** D-020, D-022, D-024, D-129, D-273
- **Repository evidence:** DRIFT-55 rests on `bedrock.py:30-72` plus a repo-wide `TOPIC_MAPPING` grep;
  DRIFT-66 on a corpus-wide `NL2SQL` grep and the runtime-path `text()` audit; DRIFT-99 on a full
  `apps/learning-web/src` inventory. **F-05 is a direct wording correction** and is recorded as a formal
  contradiction: 3A said `TOPIC_MAPPING` **absent**; there is one hit at `bedrock.py:37` with zero callers,
  so "**declared, never used**" is correct — and the class docstring concedes the reservation in advance,
  with REQ-51 explaining the vacancy: topic resolution is deterministic by construction, so the enum slot has
  no caller *because the deterministic-core rule won*. F-16 makes DRIFT-99's absence exhaustive from the
  other direction (23 matches, all chat-web, all location-consent; zero in `apps/learning-web/src`) and
  records the **new** untested item: the fail-closed empty frozenset is unpinned.
- **Deployed/live evidence:** n/a — repository-side; S45 is unstarted.
- **Final disposition:** `DOCUMENTATION_ONLY` as the batch default, with **one exception** (DRIFT-66).
- **Justification:** four document corrections plus one genuinely unowned spec requirement.
- **Remaining action:** the four edits. **Five flags.** (1) **Adopt F-05's wording for DRIFT-55**
  ("declared and never used", not "absent") — downstream summaries must not regress to "absent", which one
  grep would falsify. (2) **DRIFT-99 and DRIFT-101 are the same supersession seen from the ledger and from
  TRACEABILITY** and both need the same forward pointer to `FIRST_VISIT_NOTICE.md`; the preservation
  convention has **no companion convention for adding such a pointer**, and that gap is the reusable
  finding. (3) **Neither DRIFT-99 nor DRIFT-101 is progress on `DISCLOSURES-LEGAL`** — the eight-versus-eleven
  ruling and the notice build both remain open; only the prerequisite is discharged. (4) **Carry F-16's new
  untested item forward** (`REQ-27-FROZENSET`). (5) DRIFT-55's own residual on the same row is
  document-side and unrelated to F-05's correction: SPEC's thirteen-type list was never amended
  (`AMENDMENT-SWEEP`).
- **Owner type:** documentation; user for DRIFT-66
- **Reopen condition:** n/a · **PROJECT_STATE?** no for the batch; yes for DRIFT-66
- **Historical/archive only?** no

### `BATCH-LOW-UNSCHEDULED-CONTROLS` — LOW batch E: controls that exist but nothing schedules, invokes or rotates

- **Work/Issue ID (topic key):** `BATCH-LOW-UNSCHEDULED-CONTROLS`
- **Members (6, verbatim from E3's batch E):** **DRIFT-54** — the log-boundary PII scanner is
  **manual-invocation only**. The script exists and every named failure mode is a distinct non-zero exit,
  with a **positive control first** (returns 2 if any pattern cannot fire — "INVALID — these patterns cannot
  fire, so a clean result proves nothing"), a missing log group → 3, an unqueryable slice → 3 ("'I could not
  look' must not report as CLEAN"), any slice at the 10,000-record Insights cap → 3, zero events → 3, and it
  imports the trace scanner's matcher rather than re-implementing it. But `make scan-logs` is the **only**
  entry point — no CI workflow and no scheduler invokes it — so "the log boundary is enforced" rests on
  someone choosing to run it. LOW, medium-adjacent. **DRIFT-80** — `make image-check` is operator-invoked
  only, wired into neither CI nor the deploy workflow. All three claimed properties are confirmed (the target
  is in `.PHONY` and defined; the D-417/A3 rename is recorded with its measurement — "with the pin two
  deploys stale, `terraform plan` moved the image **forward** to what was running"; `adopt_deployed_image`
  defaults true, consumed by the `for_each` guard). The unstated property is that **nothing invokes it**, and
  `ARCHITECTURE.md:429-458` does not mention it at all. **DRIFT-83** — LangSmith retention has **no in-repo
  expression**. **[EXCEPTION → `LANGSMITH-RETENTION`, BLOCKED, UD-11.]** **DRIFT-84** — the two exposed
  staging token secrets have **no rotation mechanism configured anywhere**:
  `git log -S"staging_token_shared_secret" -- terraform` returns exactly one commit ever (the original
  creation); the two `random_password` resources carry no `keepers` and no rotation trigger; no
  `aws_secretsmanager_secret_rotation` resource exists in `terraform/`; and the block comment plans
  **deletion at S44, not rotation** — with S44 frozen. The register's own calibration: rotation in place
  would not require a repository change, so absence of a commit is weak negative evidence, while the absence
  of any in-repo control is not. **[EXCEPTION → `D310-ROTATION`, RESOLVED: the rotation was executed
  2026-08-20.]** **DRIFT-87** — a fifth scheduled-job entrypoint reports only via `print()` and is itself
  unscheduled. P1-6 is closed and itemized for the four enabled jobs (each entrypoint calls
  `report_job_complete(...)` immediately after its `print()`, emitting a structured record keyed by a `job`
  dimension deliberately identical to the verbatim Terraform job key; the `print()` calls are retained on
  purpose for humans). The residual: `checkpoint_retention_cli` does **not** call `report_job_complete` and
  is also unscheduled — and the reporting helper **swallows all exceptions by design**, so a silent
  reporting failure would leave only the `print()`. **[Superseded in the worse direction by `RD-01`.]**
  **DRIFT-89** — the alarm-severity split is real at the topic layer and still single-address at the inbox
  layer by default. **[EXCEPTION → `ALERT-ENDPOINT`, USER_DECISION_REQUIRED, UD-6.]**
- **Description:** Six LOW entries where a control is built, correct and *manual* — or configured at one
  layer and inert at the next. The shared shape: **"enforced" in the documents means "someone chooses to run
  it".**
- **Domain:** security posture / observability / deploy tooling
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:627`, `:913`, `:946`, `:957`, `:990`, `:1012`
- **Related claim IDs:** SEC-08, SEC-23, SEC-25, SEC-26, SEC-35, REQ-02, COST-18, COST-23, COST-24,
  COST-26, COST-27, ARCH-30, ARCH-33, ARCH-34, WORK-07, WORK-19, WORK-21
- **Related decision IDs:** D-097, D-104, D-137, D-242, D-244, D-310, D-333, D-377, D-401, D-417 §A3,
  D-418, D-419
- **Repository evidence:** DRIFT-84 rests on a `git log -S` over terraform plus a negative
  `aws_secretsmanager_secret_rotation` grep; DRIFT-89 on a terraform-parsing test plus the `coalesce`
  default.
- **Deployed/live evidence:** **DRIFT-84 → the rotation was executed and verified 2026-08-20**
  (`D310-ROTATION`), so 3A's LOW grading on weak negative evidence and RD-02's live-exposure escalation are
  both **historical**; the surviving residual is that **no standing rotation mechanism was added**, accepted
  because the S44 deletion plan stands and is frozen. **DRIFT-87 → RD-01** shows the deployed metric-filter
  pattern and the Python event name can **never match**, so DRIFT-87's own question ("do structured lines
  actually reach CloudWatch?") is answered **no** for the metric leg, and the four *instrumented* jobs are no
  better off than the fifth in alarm terms. **DRIFT-89 → confirmed exactly at runtime, not resolved**:
  exactly two topics account-wide, each `SubscriptionsConfirmed 1`/`SubscriptionsPending 0`, **both
  subscriptions the same single mailbox**; 26 → page, 4 → info, 4 → autoscaling, **no alarm carries both**;
  COST-23/COST-26 settled positively (zero `PendingConfirmation` anywhere) and the deployed count is 30
  module instances == 30 configured, per-name delta 0. **DRIFT-83 → routed out as external and not
  measured**, and RD-04 raises rather than lowers the value of a retention answer. **DRIFT-80 → partially
  answered**: RD-11 found both services one task-definition revision behind — precisely the class of
  question `make image-check` exists to ask, and it went unasked because nothing invokes it — and LB-05 adds
  the 10-commit gap. **DRIFT-54 → untouched**: 3A.5 routed `scripts/scan_logs_pii.py` to 3B (it needs
  staging CloudWatch) and 3B's queue does not record a run, **so no phase ran it either**.
- **Final disposition:** `ACTIVE_REMEDIATION` as the batch default — each member is a real control that
  needs wiring, scheduling or rotating, not a wording fix — with **four exceptions** as marked.
- **Justification:** the three remaining members (DRIFT-54, DRIFT-80, DRIFT-87) are mechanical wiring, not
  judgements.
- **Remaining action:** wire `scan-logs` into CI or a schedule; wire `make image-check` into CI or the
  deploy workflow and mention it in `ARCHITECTURE.md` (`DOC-DEPLOYED-STATE-CLAIMS`); add
  `report_job_complete` to `checkpoint_retention_cli`. **Five flags.** (1) **DRIFT-84 must not be reported
  at LOW *or* as an open exposure** — it is resolved by action, and that is the single largest disposition
  revision the later phases force on this register. (2) **DRIFT-87 plus RD-01 together destroy the "nightly
  jobs are observable" story** — do not report the four-of-five instrumentation as reassurance. (3)
  **DRIFT-54's positive control is exemplary engineering** (a scanner that refuses to report CLEAN when it
  could not look); the defect is only that nothing runs it — say both, and note that **the log boundary has
  one historical clean run and no continuous assurance**. (4) **DRIFT-89 is now a complete picture** —
  configuration, test and live AWS all agree — so it is ready to decide with no further measurement. (5)
  **DRIFT-80's value is demonstrated by its own absence**, which strengthens the case for wiring it and for
  `DRIFT-24-ARTIFACT-FRESHNESS`'s hash comparison.
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `BATCH-LOW-NARROW-COVERAGE` — LOW batch F: coverage narrower than the claim, and small code gaps recorded at LOW

- **Work/Issue ID (topic key):** `BATCH-LOW-NARROW-COVERAGE`
- **Members (4, verbatim from E3's batch F):** **DRIFT-68** — the synthesis-time chunk re-fetch applies **no
  status or effective-window predicate**. Fail-closed behaviour is present at the answer boundary
  (`if not verified or raw.confidence < confidence_threshold: return _no_answer(...)` with `[]` citations
  deliberately per AUD-C-11, a conflict message on `sources_conflict`, and a zero-chunk short-circuit), and
  approved/effective enforcement is **pre-retrieval** (`status == "approved"` unconditional plus the
  effective window). But `synthesize_answer` re-fetches chunk bodies via `get_chunks_by_ids`, which applies
  **no predicates** — so the guarantee rests entirely on the earlier filtered query rather than being
  re-asserted at synthesis. Behavioural impact requires an approval or effective-window change **inside one
  turn**, and that window is not asserted anywhere. **DRIFT-74** — the "no message restates its own reason
  code" sweep covers **five of ten** reasons. **[Same substance as `REQ-44-REASON-SWEEP`,
  ACTIVE_REMEDIATION.]** **DRIFT-82** — the trace-boundary redactor rebuilds span attributes and **passes
  span events through untouched**. All four claimed elements are confirmed, and the exporter wraps **both**
  branches of `build_tracer_provider` with the reason stated ("Wrapping only the production branch would make
  the test path structurally unable to catch a regression"); three redaction patterns cover
  `?token=`/`access_token`/`api_key`, a bare `eyJ...` JWT and `Bearer <x>`. The scope drift: `_redacted`
  rebuilds the span with cleaned attributes but passes `events=span.events` through, so **a credential
  inside a span event would not be redacted**. **DRIFT-85** — the I7 unknown-role metric.
  **[EXCEPTION → `DRIFT-85-I7-ALLOWLIST`, BLOCKED.]**
- **Description:** Four LOW entries where a guard, sweep or enforcement point is real but narrower than the
  sentence describing it — three in code, one in a frozen plan.
- **Domain:** security enforcement / testing / observability / frozen planning
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:781`, `:847`, `:935`, `:968`
- **Related claim IDs:** REQ-02, REQ-07, REQ-08, REQ-14, REQ-43, REQ-44, REQ-45, REQ-48, SEC-05, SEC-06,
  SEC-07, SEC-34, INT-12, WORK-18
- **Related decision IDs:** D-104, D-153 §5, AUD-C-11
- **Repository evidence:** DRIFT-82 rests on the redactor's own vacuity guard and negative arm in
  `test_tracing.py`; DRIFT-74 on the five-entry `REASON_MESSAGES` map against a ten-value enum. **F-09 is
  the register's sharpest "green test is not coverage" case:** the suite ran `43 passed` and the sweep works,
  but it iterates only `REASON_MESSAGES` and the assertion is a plain substring check, so it **passes
  vacuously for any copy defined outside the dict** — "the pass is necessary and not sufficient".
- **Deployed/live evidence:** DRIFT-68, 82 and 85 were untouched by later phases; DRIFT-85's subject sits
  inside the D-152-frozen S43 region, so no phase could advance it.
- **Final disposition:** `ACTIVE_IMPLEMENTATION` as the batch default for the three code members — each is a
  small, well-understood change on a fail-closed or privacy boundary — with **one exception** (DRIFT-85).
- **Justification:** small code changes, already reasoned, on boundaries the project's own rules make
  non-negotiable.
- **Remaining action:** add the synthesis-time predicate (DRIFT-68); widen the sweep or assert
  exhaustiveness (`REQ-44-REASON-SWEEP`); redact span events (DRIFT-82). **Four flags.** (1) **DRIFT-82 is
  the highest-value member** — span **events** are exactly where an exception's message or a request body
  tends to land, so "redacts at the span-export boundary" over-promises on the surface most likely to carry
  a credential; small fix, real privacy boundary. (2) **DRIFT-68's window is genuinely narrow** (an approval
  or effective-window change inside one turn) but the principle is **non-negotiable rule 5** — no RAG answer
  without an approved, effective source — so re-asserting the predicate at synthesis is defence in depth,
  and the re-fetch exists for a deliberate PII and size reason (`QAState` checkpoints ids, not bodies). (3)
  **Quote F-09 verbatim in the report** — the cleanest illustration of the rule that green tests do not
  disprove untested defects. (4) **DRIFT-85 is a "named-but-unspecified" pattern worth generalising** — the
  same family as DRIFT-10 (a metric without an alarm) and DRIFT-04 (an expiry without a monitor).
- **Owner type:** engineering
- **Reopen condition:** n/a · **PROJECT_STATE?** yes · **Historical/archive only?** no

### `BATCH-LOW-CONFIG-VS-PLAN` — LOW batch G: infrastructure configuration versus documented plan or invariant

- **Work/Issue ID (topic key):** `BATCH-LOW-CONFIG-VS-PLAN`
- **Members (4, verbatim from E3's batch G):** **DRIFT-56** — the latency capacity plan implies **five**
  tasks against a configured `autoscaling_max_capacity` of **3** (the module default, "Deliberately modest
  (Free Tier + solo-maintainer scale, not enterprise headroom)"); learning-api is pinned min 2 / desired 2,
  chat-api min 1 / max 3. **Adjudication qualifier: D-153 §3 withdrew that purchase**, so no active plan
  exceeds the configured ceiling — this is a plan-versus-ceiling note for whenever capacity is revisited,
  not a live mismatch. LOW, medium-adjacent (adjudicated down from MEDIUM). **DRIFT-57** — the
  zero-internet-egress invariant is a **conditional default that the checked-in variables currently switch
  off**. The PrivateLink half is confirmed (interface endpoints for `ecr.api`, `ecr.dkr`, `logs`,
  `secretsmanager` unconditionally, plus `bedrock-runtime` and `xray` when enabled, all in one subnet for the
  per-AZ cost reason, plus an S3 gateway endpoint), and so is the no-inline-default-route design
  (`aws_route_table.private` declares no inline route "so that flipping `nat_gateway_enabled` back to false
  removes the route and restores the no-egress property without recreating the route table"). But the
  zero-NAT property is **off** under checked-in defaults (`langsmith_tracing_enabled` defaults true → NAT
  count 1), so ARCHITECTURE's framing is baseline-with-exception rather than an invariant. LOW,
  medium-adjacent. **DRIFT-59** — OPEN_DECISIONS #10's `formatDateLabel` CDT record and the armed date-only
  shift. **[EXCEPTION → `DRIFT-59-DATE-SHIFT`, ACTIVE_IMPLEMENTATION; the chat-web half is
  `WORK-40-TZ`.]** **DRIFT-70** — the consent-verification half of REQ-27.
  **[EXCEPTION → `DRIFT-70-CONSENT-GATE`, PARKED_BY_DECISION, with the frozenset carve-out at
  `REQ-27-FROZENSET`.]**
- **Description:** Four LOW entries, three adjudicated LOW–MEDIUM, where a documented plan, invariant or
  "ALL DECIDED" heading is out of step with the checked-in configuration or with what actually shipped.
- **Domain:** infrastructure configuration / frontend correctness / auth
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:649`, `:660`, `:682`, `:803`
- **Related claim IDs:** ARCH-12, ARCH-13, ARCH-28, ARCH-29, COST-28, COST-29, REQ-25, REQ-26, REQ-27,
  WORK-40
- **Related decision IDs:** D-136, D-152, D-153 §3, D-324, D-406, D-419, T-02
- **Repository evidence:** DRIFT-57 rests on the VPC module's endpoint set and route-table design; DRIFT-70
  on the ten-claim `TokenClaims` model, four consuming sites and the empty frozenset.
- **Deployed/live evidence:** **DRIFT-57 → settled at runtime, and the invariant does not currently hold**:
  the NAT exists (`nat-07ab02d5cd28b6f72`, `CreateTime 2026-08-07T04:47:31Z`) with an active
  `0.0.0.0/0 → nat` route and `ManagedBy=terraform`, and the repository's ~$33/mo figure is confirmed by
  Cost Explorer (~$32.9/mo gross) — so the zero-egress baseline is **off today, by the deliberate 2026-08-06
  tracing decision**. **DRIFT-56 → COST-29's configuration half is confirmed by executed
  terraform-parsing tests and ARCH-12/ARCH-13/COST-29 are confirmed against the deployed state**; the
  adjacent live fact is that **100-concurrent capacity was never demonstrated live** (30-day peak ≈ 3
  req/s, busiest minute 51 requests), so capacity remains a load-test-era extrapolation. **DRIFT-70 → F-16**
  confirms the backend gate by execution, the exhaustive absence of the student-facing half, and the
  unpinned frozenset.
- **Final disposition:** `DOCUMENTATION_ONLY` as the batch default — annotate the withdrawn capacity plan,
  reframe the egress invariant as baseline-with-exception, correct #10's symbol name — with **two
  exceptions** as marked.
- **Justification:** two document annotations plus two real code items lifted out.
- **Remaining action:** the two annotations plus the two exception entries. **Five flags.** (1) **F-02 is a
  new MEDIUM-graded finding that no 3A entry owns** and must be carried on its own merits
  (`WORK-40-TZ`) — do not let it be absorbed as "part of DRIFT-59". (2) **DRIFT-57's invariant is currently
  false, by a deliberate decision, at ~$33/mo** — three separate facts, and the documentation should carry
  all three. (3) **"ALL DECIDED" headings are a rot hazard** — DRIFT-59 sits under one while carrying an
  unmitigated armed edge case; recommend a convention note. (4) **DRIFT-70's fail-closed empty frozenset is
  the load-bearing safety property and it has no test** — F-16 named it, nothing acted, and it is a one-line
  test. (5) **DRIFT-56 plus REQ-50(b) together**: the capacity table's plan is withdrawn, its ceiling is 3,
  and the 100-concurrent figure was never demonstrated live — any future capacity discussion should start
  from that, not from the table. DRIFT-56 becomes decision-relevant the moment capacity is revisited.
- **Owner type:** documentation; engineering for DRIFT-59
- **Reopen condition:** capacity revisited (DRIFT-56) · **PROJECT_STATE?** no for the batch; yes for
  DRIFT-59 · **Historical/archive only?** no

---

## §10 Audit-method observations & resolved/superseded record

*Entries here are `OBSERVATION_ONLY`, `RESOLVED` or `SUPERSEDED` and are historical or archive material
only (§0.2 rule 10). §10.3 rolls up every such entry in the register, wherever it sits, so the historical
record is readable in one place. Field labels are the same fifteen; several are compressed to one line
because there is no open work to describe.*

### `LB-09-NULL-RESULT` — no new behavioural defect was discovered in any live probe

- **Work/Issue ID:** `LB-09` · **Members:** E6-9 · **Domain:** live behavioural verification
- **Description:** Across every live walk: **0 console errors, 0 page errors, 0 5xx**. The staging journey
  teardown reported, for both tests, `consoleErrorCount: 0`, `pageErrorCount: 0`, `serverErrorCount: 0`,
  `clientErrors: []`, `pageErrors: []`, `failedRequests: []`, with 50 + 18 = 68 API calls and **zero
  non-2xx**, and no `audit.allow({…})` narrowing needed. The guest RAG turn returned 200 on both calls with a
  1133-character grounded answer, 1 citation, `scope="in_scope"`, `intent="document_qa"`,
  `access_hint=null`, `escalation_recommended=false`. Neither local suite hit a port conflict, a DB-down or a
  missing-migration error; both collected non-zero and exited 0 first attempt.
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:37-48`, `:458-482`; `LIVE_BEHAVIOR_EVIDENCE.md:165-166`
- **Related claim IDs:** all six 3B-2 claims · **Related decision IDs:** D-381, D-383
- **Repository evidence:** local suites at HEAD, clean. **Deployed/live evidence:** staging walks on
  `gha-44a12dfc9549`, clean. Neither lane covers the 10 undeployed commits.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** a null result; no defect to register, and it
  is why every other LB item is a *sharpening* rather than a breakage.
- **Remaining action:** none. **Its stated limit must travel with it:** `AUDIT_LIVE_2026_08_17.md` warns not
  to over-read a green run — on 2026-08-17 a green Playwright suite coexisted with two live P1s. What is
  *newly* true is that the five specs D-383 added to close those blind spots all ran and passed
  non-vacuously. **Do not let it be quoted as absence-of-defect evidence for behaviour nobody asserted.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `LB-08-CORROBORATIONS` — three independent corroborations of existing measurements

- **Work/Issue ID:** `LB-08` · **Members:** E6-8 · **Domain:** staging journey / latency and grading
- **Description:** (1) A guest QA turn measured **10.55 s** (session creation 0.25 s) against D-423's
  recorded **10.62 s** and "~10.6 s p95 accepted for launch"; because `6f107c1` is undeployed this is a
  **pre**-D-423 number, so the match is with the pre-optimisation baseline and D-423's ~22% improvement
  retains an untouched before-measurement. (2) D-355 reconciliation drift measured **5 − 5 = 0** (the
  2026-08-14 failing run recorded 11 submitted / 1 graded). (3) D-325's no-re-served-stem rule holds:
  `stems seen: 10 pre_exam, 5 study, 0 repeated`. Also decided in the same process, none skipped:
  `studyAnswers` 5, `ladderOffered` 4, `interventions` 4, 4 of 5 study answers wrong — so wrong-answer and
  ladder paths were genuinely reached.
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:426-454`; `LIVE_BEHAVIOR_EVIDENCE.md:112`
- **Related claim IDs:** REQ-46, WORK-13 · **Related decision IDs:** D-325, D-355, D-423
- **Repository evidence:** the documents corroborated describe HEAD. **Deployed/live evidence:** all three are
  deployed-side observations on `gha-44a12dfc9549`; the latency one is only meaningful *because* of that gap.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** corroboration of documented behaviour.
- **Remaining action:** **capture the 10.55 s figure with its build SHA before any deploy
  (`LB-05-DEPLOY-GAP`), or the pre-D-423 anchor is lost.**
- **Owner type:** documentation (record the number) · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `JUDGE-HISTOGRAM-PROVENANCE` — the D-252-style judge histogram was not independently re-derived

- **Work/Issue ID:** `LBF §5 lane note` · **Members:** E6-15 · **Domain:** question-quality measurement
- **Description:** Re-deriving the `question_validation_runs.stage_results->'judge'` distribution needs the
  dev Postgres, which the staging lane was forbidden to touch — **BLOCKED_BY_LANE, not by environment**. It
  was not needed: D-254 and D-252 decide both of WORK-29's questions from documents and source, and re-buying
  D-254 at ~29¢ would **replace** the record rather than check it. So the "minimum observed 2, zero below"
  figure rests on D-252's record plus the code comment at `ai_pipeline.py:821-827`, not on a fresh `SELECT`.
- **Original source(s):** `LIVE_BEHAVIOR_FINDINGS.md:537-541`; `LIVE_BEHAVIOR_EVIDENCE.md:123`, `:129`,
  `:161-163`
- **Related claim IDs:** WORK-29 · **Related decision IDs:** D-249, D-252, D-254
- **Repository evidence:** the record and the code comment agree. **Deployed/live evidence:** n/a — a
  dev-database lane with no deployed surface.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** recorded for completeness, not as a gap; the
  claim was decided without it exactly as its decision rule permits.
- **Remaining action:** none. **If an independent check is ever wanted, attach D-252's two contamination
  guards to the query — mock contamination by `MockBedrockProvider`'s constant `hint_quality_score: 5`, and
  the eight pre-bound-era 8s and 9s dated 2026-08-05 only. An unguarded re-derivation would produce a *worse*
  number than the one on record.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `G7-SESSION-RENUMBER` — the session-renumbering translation layer covers old S17–S23 only

- **Work/Issue ID:** `G7` (chain G7) · **Members:** E2-17 · **Domain:** audit method / navigation
- **Description:** D-049 remains the live translation layer, but it maps old **S17–S23 only**;
  pre-restructure references to sessions **above S23** have no stated translation. Because historical entries
  were deliberately not rewritten, the same string ("S20", "S17", "S18"…) means two different sessions
  depending on the writing date, and **any audit pattern-matching session ids without checking entry dates
  will mis-resolve at least seven ids**.
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:1102-1122` · **Related claim IDs:** none
- **Related decision IDs:** D-049, D-050
- **Repository evidence:** nothing supersedes D-049. **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** a method hazard for this audit rather than
  open project work.
- **Remaining action:** none, except the standing rule: **any claim in the reconciliation corpus keyed on a
  bare session id from a pre-2026-07-18 entry needs a date check.** The collision half is
  `RISK-R6.4-SESSION-LABELS`.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `MAP-HORIZON` — the supersession map stops at D-419 while DECISIONS runs to D-423

- **Work/Issue ID:** `meta/map-horizon` · **Members:** E2-49 · **Domain:** audit coverage
- **Description:** The map is dated 2026-08-19 and its newest cited entry is D-419 (`DECISIONS.md:28463`).
  The file now contains D-420 (`:28518`), D-421 (`:28581`) and its addendum (`:28643`), D-422 (`:28669`) and
  D-423 (`:28714`) — roughly 270 unmapped lines. A back-reference grep over `:28518-28787` shows those
  entries cite only D-021, D-164, D-221, D-348, D-395, D-402, D-404, D-412, D-416 and D-417/C8, and touch
  **no terminal decision in any of the 29 chains**, so **no extracted item is stale because of them**.
- **Original source(s):** `grep -nE "^#{2,4} D-4[12][0-9]" docs/DECISIONS.md`; the back-reference grep;
  `DECISION_SUPERSESSION_MAP.md:2219`
- **Related claim IDs:** none · **Related decision IDs:** D-420, D-421, D-422, D-423
- **Repository evidence:** verified. **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** verified not to affect the findings;
  recorded so nobody assumes the map is current to HEAD.
- **Remaining action:** none. **Any statement of the form "the decision log ends at D-419" is wrong** —
  D-420–D-423 are unmapped by timing, not by omission. Also confirmed: **no decision heading exists above
  D-423**, and `344f016` is docs-only and adds no decision id.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `F-17-STRENGTHENINGS` — the evidence conversions that make the claim ledger trustworthy

- **Work/Issue ID:** `F-17` · **Members:** E4-17 · **Domain:** audit evidence quality (cross-domain)
- **Description:** None is a defect; each was adjudicated a strengthening. **TEST-02** — the largest single
  evidence conversion in the audit: all 13 cited pytest files ran in one invocation, **`183 passed in
  18.90s`**, 0 failed / 0 skipped / 0 errors, moving five sampled TRACEABILITY criterion-1 rows from "the
  cited artifact exists" to "the cited artifact passes" (the 14th cite, `scripts/scan_logs_pii.py`, needs
  staging CloudWatch). **WORK-15** — D-342's parking premise is now executed-verified; a failure would have
  invalidated the parking decision. **WORK-37** — the 182-row deactivation incident guard holds
  (`test_sync_preflight.py:157` and its three tests). **WORK-03 + ARCH-08** — replay from empty verified: a
  scratch database migrated base-to-head, **37 migrations**, `9e6877432c14` → `8509c0486d8d`,
  `alembic current` and `alembic heads` both reporting a single head, no branch divergence; that head **is**
  the D-421 `chat_escalation_sends` migration; `packages/db/tests/` then ran **`83 passed`**, including all
  four `test_autogenerate_never_drops_the_checkpoint_tables.py` tests; no repository file was touched and the
  scratch database was confirmed absent afterwards. **WORK-11** — `make lint` produced `All checks passed!` /
  `440 files already formatted` using `ruff format --check` per D-417/C8, so verification cannot rewrite
  files as a side effect. **WORK-21** — both halves confirmed by test, including the dry-run default and the
  two-condition chat classifier. Plus ~25 rows confirmed as claimed with no new finding (REQ-51, ARCH-02,
  ARCH-12, ARCH-35, COST-16, COST-29 configuration half, TEST-09 absent *by decision* D-125 tracked to
  S50 A7, REQ-49, REQ-52, SEC-23/COST-27/ARCH-30, SEC-25/ARCH-03, REQ-28/SEC-12, COST-17, TEST-12 — which
  ran against the local database, **not** skipped, and passed — WORK-27, WORK-35, TEST-22/TEST-23 API
  halves, REQ-20, REQ-40, TEST-14).
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:31-51`, `:693-743`;
  `LOCAL_EXECUTION_EVIDENCE.md:839-851`
- **Related claim IDs:** as listed · **Related decision IDs:** D-125, D-342, D-417 §C8, D-421
- **Repository evidence:** all five `TEST_EXISTS_NOT_EXECUTED` claims are resolved at the pytest level
  (REQ-20, REQ-40, TEST-14 fully; TEST-22 and TEST-23 for their API halves), the project's own "migrations
  must replay from empty" convention is directly satisfied, and the declared gate
  `make lint typecheck test` reproduces CI's `lint-typecheck-test` exactly and is clean.
- **Deployed/live evidence:** staging schema state for WORK-03 stays out of scope (`DB-CONTENT-VERIFY`).
- **Final disposition:** `RESOLVED` · **Justification:** evidence conversions, not closures of defects — and
  **no item anywhere in this register is dispositioned RESOLVED on the strength of the green suite.**
- **Remaining action:** none. **Residue explicitly carried, not resolved here:** TEST-22's **5 Playwright
  specs** remain the audit's only `TEST_EXISTS_NOT_EXECUTED` residue (`PLAYWRIGHT-LANE`);
  `scripts/scan_logs_pii.py` needs staging CloudWatch (`BATCH-LOW-UNSCHEDULED-CONTROLS`, DRIFT-54); staging
  schema state stays open; and **WORK-21's unscheduled-in-terraform drift stands unchanged** — the retention
  policy is implemented, tested, and *not scheduled* (`RETENTION-CLUSTER`). One correction to carry: X1's
  reported **583** tests was an **addition error** — the addend list sums to 566, and one 4-test confirmation
  re-run was already counted inside the 83-test database-suite run, so any downstream summary quoting 583
  should read "**562 unique tests (566 executions)**". Run hygiene, which bounds the whole result:
  `git status --porcelain` showed only the pre-existing `?? docs/reconciliation/` after every step, and
  `make fmt`, git-mutating commands, terraform, aws, gh, Playwright and `npm install`/`npm ci` were never
  invoked, with no `.env` or `*.tfvars` read.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `F-04-QUOTE-FLOOR-LOCATION` — the quote-floor tests are in `apps/chat-api/tests/`, not `packages/knowledge/tests/`

- **Work/Issue ID:** `F-04` (TEST-13) · **Members:** E4-4 · **Domain:** audit hygiene / test-citation accuracy
- **Description:** The 3A.5 batch specification located the citation quote-floor tests in
  `packages/knowledge/tests/`. Running the cited command there **collected zero** (exit 5,
  `40 deselected in 0.89s`) — recorded as **not-evidence** per the Makefile's own AUD-F-12
  instrument-honesty rule. Recovery by grep: the six quote-floor tests live in
  `apps/chat-api/tests/test_qa_service.py`, which ran **`23 passed`**. The separate
  `packages/knowledge/tests/test_retrieval.py` suite (TEST-14) ran independently, `22 passed`.
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:104-107`, `:275-306`, `:754`
- **Related claim IDs:** TEST-13 (`CONFIRMED`), TEST-14 · **Related decision IDs:** D-172; AUD-F-12
- **Repository evidence:** **the durable documents are already correct** — `REPOSITORY_STATE_EVIDENCE.md:1609`
  cites `apps/chat-api/tests/test_qa_service.py:369-395` for the quote floor alongside
  `packages/knowledge/tests/test_retrieval.py:375-378` for the rerank floor; the mislocation was in the run
  plan's collapse of the two, not in the ledger row. A grep for `packages/knowledge/tests` paired with
  `quote_floor` returns no such pairing elsewhere.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` · **Justification:** the correction is recorded and the durable artifacts
  already carry the correct path, so nothing remains to edit. What it corrected: a citation that would hand
  the next reader a zero-collection exit-5, i.e. the AUD-F-12 false-negative shape — no error, no evidence.
- **Remaining action:** none. **The transferable lesson is worth a line in the audit's method notes: a `-k`
  filter against the wrong package exits 5 and looks like a pass.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `F-05-TOPIC-MAPPING` — `TOPIC_MAPPING` is declared and never used, not absent

- **Work/Issue ID:** `F-05` (REQ-17) · **Members:** E4-5 · **Domain:** documentation accuracy / LLM surface
- **Description:** The 3A wording rested on a repo-wide negative grep. The grep returns **one** hit:
  `packages/shared/src/intellichoice_shared/bedrock.py:37: TOPIC_MAPPING = "topic_mapping"`, a `BedrockTask`
  enum member whose class docstring (`:30-34`) **concedes the reservation in advance** ("the others are named
  now so the model registry's keys are stable … not because logic exists for them yet"). Absent is everything
  downstream: no payload model, no response model, no caller in any of the 18 non-test `generate_structured`
  files or anywhere in `apps`/`packages`. REQ-51's execution **explains the vacancy rather than contradicting
  it**: `topic_resolver.py` makes zero LLM calls and every import is a database repository, a model or a
  deterministic policy constant — topic resolution is deterministic by construction, so **the enum slot has
  no caller *because* non-negotiable rule 2 won.**
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:310-349`, `:756`
- **Related claim IDs:** REQ-17, REQ-51 · **Related decision IDs:** D-024; non-negotiable rule 2
- **Repository evidence:** `REPOSITORY_DRIFT_REGISTER.md:642-643` **already carries the corrected wording**
  ("exists at `bedrock.py:37` with no payload model, no response model and no caller … a
  reserved-but-unbuilt slot") and already dispositions it against D-024.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` · **Justification:** the correction was integrated into the drift register
  before the extraction ran. What it corrected — "`TOPIC_MAPPING` does not exist" — is falsifiable by one
  grep and would have discredited the surrounding row; the correct and materially different finding is
  "declared, never used, with a documented reason".
- **Remaining action:** none. The register's own residual on the same row is document-side and unrelated:
  SPEC's thirteen-type list was never amended (`BATCH-LOW-UNMARKED-SPEC`, `AMENDMENT-SWEEP`).
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `F-07-ARCH01-SPLIT` — `ARCHITECTURE.md` is current on decisions and stale on session provenance

- **Work/Issue ID:** `F-07` (ARCH-01) · **Members:** E4-7 · **Domain:** documentation accuracy
- **Description:** The 3A framing implied `ARCHITECTURE.md` is stale "up to" the present. Execution splits
  it. **Decision currency is fine:** it cites D-423 (`grep -noE "D-4[0-9][0-9]"` → ten lines, eleven
  occurrences, `1177:D-423`), and D-423 is the newest entry in `DECISIONS.md:28714`, the same decision as
  HEAD~1. **Session provenance is genuinely incomplete:** the header (`:3-13`) promises "Session provenance
  is tagged in each node (e.g. `(S6)`)" and claims coverage through S0–S34 plus the S36–S43 audit work, but
  tags exist for only **32 of 48** sessions; the 16 untagged are S23, S30, S31, S32, S33, S35, S36, S38,
  S40, S41, S42, S43, S44, S45, S46, S47 — every session from S40 onward except the aspirational `(S48)`,
  which tags the *unbuilt* production environment. The accurate finding is "**the `(Sn)` convention was
  abandoned around S39 while the header still advertises it**".
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:387-411`, `:758`
- **Related claim IDs:** ARCH-01, ARCH-02 · **Related decision IDs:** D-423
- **Repository evidence:** `REPOSITORY_DRIFT_REGISTER.md:1116`, `:1122`, `:1215` **already carry both
  halves** as DRIFT-98, whose §3.2 row is the decision family.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` · **Justification:** the correction is already integrated as DRIFT-98.
  What it corrected — "ARCHITECTURE.md is behind on decisions" — is **false** and has a different remedy from
  the real defect.
- **Remaining action:** none, except that the **16-session enumeration is the precise number DRIFT-98
  lacked** and should be attached to that row as evidence rather than opened as a new item
  (`RISK-GROUP-ARCH-AUTHORITY`).
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `LIVE-HALVES-SUPERSEDED` — every live and deployed half was out of 3A.5's scope and was discharged by 3B

- **Work/Issue ID:** `§5 unreached area 2` · **Members:** E4-20 · **Domain:** audit completeness
- **Description:** Not reached in 3A.5: all AWS-credentialed make targets (`scan-traces`, `scan-logs`,
  `scheduler-evidence`, `scaling-evidence`, `image-check`, `profile-span`, `e2e-staging`,
  `load-staging-chat`, `load-staging-learning`, `security-scan-staging`); `scripts/scan_logs_pii.py`;
  `terraform plan`/`apply`/`init` (forbidden — live state); live ALB reachability (SEC-25/ARCH-03); live task
  size and count (COST-29, ARCH-10); staging schema state (WORK-03); applied-versus-unapplied terraform
  (WORK-08); and every LangSmith-side fact (SEC-23's retention, span attributes). F-03 is the governing
  constraint: **configuration is not live.**
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:786-793`
- **Related claim IDs:** SEC-25, ARCH-03, ARCH-10, COST-29, WORK-03, WORK-08, SEC-23, TEST-02
- **Related decision IDs:** F-03's terraform-apply constraint
- **Repository evidence:** the credentialed targets exist. **Deployed/live evidence:** Phase 3B ran after
  3A.5 and produced both an infrastructure half (`DEPLOYED_INFRA_*`) and a behavioural half
  (`LIVE_BEHAVIOR_*`).
- **Final disposition:** `SUPERSEDED` · **Justification:** the deferral was discharged rather than left
  standing — **but "SUPERSEDED" is a claim to verify, not a closure**, and this was the completeness-accounting
  item most likely to hide a gap.
- **Remaining action:** the item-by-item verification **has been done in this register**, and three of the
  named targets were **not** reached and are carried as open entries rather than vanishing between two
  phases: `scripts/scan_logs_pii.py` (no phase ran it — `BATCH-LOW-UNSCHEDULED-CONTROLS`, DRIFT-54);
  LangSmith retention and span-attribute facts (`LANGSMITH-RETENTION`, external); and staging schema state
  (`DB-CONTENT-VERIFY`). WORK-08 **was** reached and refuted (`DRIFT-93-D401-D406-APPLIED`); live ALB, task
  size and count were reached (`RD-12-INGRESS`, `D136-PRICE-TABLE`).
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `RUFF-DENOMINATOR` — the `ruff format` denominator moved 437 → 440, and that is not drift

- **Work/Issue ID:** `§4 row 6` (WORK-11) · **Members:** E4-18 · **Domain:** audit method
- **Description:** Prior evidence recorded 437 files for `ruff format --check`; `make lint` reported
  `440 files already formatted`. Adjudicated **not a contradiction**: consistent growth (three files added
  after C8) with the enforcement mechanism unchanged and green. The stated reason for including it at all:
  "A moved denominator on a growing codebase is expected; calling it drift would dilute the five real
  corrections above it."
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:759`, `:761-762` · **Related claim IDs:** WORK-11
- **Related decision IDs:** D-417 §C8 · **Repository evidence:** `make lint` → `All checks passed!` /
  `440 files already formatted`. **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** its value is **methodological** — it
  demonstrates the audit distinguishing a stale *number* (F-08's 31-versus-41, which is drift) from a
  *moving* number (this one, which is not), and that distinction must survive into the final report.
- **Remaining action:** none; keep it in the completeness accounting rather than dropping it. The stale-count
  half is `DOC-PROGRESS-QUEUED-BLOCK`.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `WHOLE-SUITE-NOT-RUN` — the blanket `make test` was not run, so "the suite is green" means "everything run passed"

- **Work/Issue ID:** `§5 unreached area 5` · **Members:** E4-23 · **Domain:** audit method / testing
- **Description:** The blanket `make test` was not run "because the targeted batches answered every claim at
  claim level and a blanket run adds no claim-level evidence". **16 targeted pytest invocations covered 562
  unique tests (566 executions).**
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:773-776` · **Related claim IDs:** TEST-02 and the
  whole executed set · **Related decision IDs:** the declared gate `make lint typecheck test` = CI's
  `lint-typecheck-test`
- **Repository evidence:** `Makefile` `test:` target; `.github/workflows/ci.yml:88` (`uv run pytest`) — CI
  runs the full suite on every push, so a full local run would duplicate an existing signal.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** defensible: the claims were the unit of
  evidence.
- **Remaining action:** none, but **the bound must be recorded**: no single command in that phase
  demonstrated the *whole* suite green simultaneously; 562 tests passed across 16 invocations, and any test
  outside those selections was neither run nor claimed. **"The suite is green" and "everything run passed"
  are different statements — downstream summaries must not upgrade the claim.** Note that
  `SUITE-COUNT-CITATIONS` records a *separate* whole-suite run at HEAD reproducing 1735/2 exactly, which is
  the fuller signal.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `NO-NEW-TEST-CODE` — no new test code was authored, and three defects are therefore established by code reading only

- **Work/Issue ID:** `§5 unreached area 6` · **Members:** E4-24 · **Domain:** audit method
- **Description:** "No new test code was written because authoring tests exceeds 'repository-defined
  validation commands' in an audit." This is the boundary that leaves `SEC-13-PURGE`, `COST-06-FLUSH` and
  `REQ-27-FROZENSET` as code-path claims rather than demonstrated behaviours.
- **Original source(s):** `LOCAL_EXECUTION_FINDINGS.md:538-539`, `:559-560`, `:773-776`, `:810`
- **Related claim IDs:** SEC-13, COST-06, REQ-27 · **Related decision IDs:** the audit's own scope rules;
  the Makefile's AUD-F-12 instrument-honesty rule applied to zero-collection runs
- **Repository evidence:** the three "*Not fixed — recorded*" markers in the findings document.
- **Deployed/live evidence:** n/a.
- **Final disposition:** `OBSERVATION_ONLY` · **Justification:** a legitimate and clearly stated boundary;
  the consequence it creates is carried by the three entries above, not by this row.
- **Remaining action:** none. **The consequence must be stated once, next to any headline null result:**
  three defects in this audit — a PII-persistence path on a minors' privacy boundary, an unattributed-spend
  branch, and an unpinned fail-closed COPPA frozenset — are established **by code reading only**. None is
  demonstrated, and **none would be caught by any existing CI job**, so the green suite and these three
  defects coexist without contradiction. Without that sentence, "562 tests green, zero failures" reads as an
  assurance the phase explicitly declines to give. The packaging claim is the useful one: **three tests, one
  afternoon, no credentials, no spend, closing one CONFLICT and two untested fail-closed boundaries.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `WORK-06-DEPLOY-EVENT` — staging was deployed and current, and its own post-deploy probe found a defect the green suite did not

- **Work/Issue ID:** `WORK-06` · **Members:** E1-89 · **Domain:** deployment history
- **Description:** Staging was deployed and current for the first time since Milestone 11 (`44a12df`, run
  32171998780, both services on `gha-44a12dfc9549`, rollout COMPLETED, one additive migration applied before
  the switch, canary clean, previously 27 commits behind). The post-deploy probe then found
  `POST /chat/sessions/{invented}/turns/x/cancel` answering **202 to an anonymous caller** — not an
  authorization bypass — fixed by unscoping the sweep inside `request()`.
- **Original source(s):** `CLAIM_LEDGER.md:2916`; `PROGRESS.md:118-137`; `ROADMAP.md:3209-3224`
- **Related claim IDs:** WORK-03, WORK-06, TEST-21, TEST-25 · **Related decision IDs:** D-416, W10, W22
- **Repository evidence:** the fix landed. **Deployed/live evidence:** the deploy state is confirmed by tag
  and digest; the residue is WORK-03's pending migration, now `LB-05-DEPLOY-GAP`.
- **Final disposition:** `RESOLVED` · **Justification:** the deploy landed and the defect was found and
  fixed. "Staging is deployed and current" and WORK-03's pending migration are consistent **only** because
  that migration post-dates the deploy — and ten commits have accumulated since.
- **Remaining action:** none. **The transferable lesson reinforces TEST-21 and should survive into the method
  notes: a post-deploy probe found what the green suite did not.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `WORK-09-AGENT-TOOLING` — the commit-or-ignore question was answered by committing

- **Work/Issue ID:** `WORK-09` (DRIFT-42) · **Members:** E3-42 (DRIFT-42), E1-92 (WORK-09)
- **Domain:** repository hygiene
- **Description:** PROGRESS records the commit-versus-ignore choice for `.agents/skills/` and
  `skills-lock.json` as an open user preference that "was not chosen for you". **They are tracked.**
  `git status --short` returns exactly one line (`?? docs/reconciliation/`, this audit's own directory);
  `git ls-files skills-lock.json .agents` returns `.agents/skills/agent-browser/SKILL.md` and
  `skills-lock.json`, both tracked, committed in `a6da941` (D-417); `.gitignore` contains no `skills` or
  `agents` pattern, so "not ignored" is still literally true but no longer a problem.
- **Original source(s):** `REPOSITORY_DRIFT_REGISTER.md:493-502`; `CLAIM_LEDGER.md:2955`;
  `PROGRESS.md:83`, `:158-160`
- **Related claim IDs:** WORK-09 · **Related decision IDs:** D-417, D10/D11
- **Repository evidence:** git state — the most reliable evidence class in the corpus.
  **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` · **Justification:** the *choice* was actually made and is observable, not
  merely un-mentioned. Recorded as RESOLVED on that basis; if strictness is preferred,
  `DOCUMENTATION_ONLY` is the fallback because the stale line still misleads.
- **Remaining action:** one stale PROGRESS line at `:158-160` (`:83`'s "agent tooling committed ✅ done" is
  the accurate line) — folded into `DOC-DECISION-LOG-CORRECTIONS`.
- **Owner type:** documentation · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `WORK-34-STUDY-RESERVE` — study no longer re-serves the exam's questions, via option A

- **Work/Issue ID:** `WORK-34` (OPEN_DECISIONS #1) · **Members:** E1-117 · **Domain:** learning product
- **Description:** Study re-serving the exam's questions was fixed by D-325 via **option A** (exclude the
  session's exam templates from study selection) while the entry recommended **B**; B is recorded as
  **unachievable on today's bank** because since D-226 every servable template has exactly one rendering, so
  B would serve the same question with options shuffled — "B does not fix the defect; it disguises it". The
  genuinely open remnant is **content**: re-rendering with different numerical parameters is authoring work
  D-189 costed and the user rejected.
- **Original source(s):** `CLAIM_LEDGER.md:3280`; `OPEN_DECISIONS.md:43-98`
- **Related claim IDs:** WORK-13, WORK-14, WORK-31, WORK-34, REQ-37
- **Related decision IDs:** OPEN_DECISIONS #1, D-189, D-226, D-314, D-325, D-370, SPEC §5.9/§5.12
- **Repository evidence:** decided, built and code-verified (`flow.py:245-283`,
  `variant_persistence.py:107-200`). **Deployed/live evidence:** `journey-student.spec.ts:377` green in five
  consecutive staging runs (D-370), and LB-08 independently measured `0 repeated` stems.
- **Final disposition:** `RESOLVED` · **Justification:** decided, built and live-verified; the open remnant is
  content quantity, which D-342 parks.
- **Remaining action:** none. It counts toward the against-recommendation set that makes
  `WORK-43-FRONTEND-TESTS`'s header count wrong.
- **Owner type:** none · **Reopen condition:** the D-342 parking lifts · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `WORK-41-CVE-REPRODUCIBILITY` — option B was chosen because two measurements made C impossible today

- **Work/Issue ID:** `WORK-41` (OPEN_DECISIONS #11) · **Members:** E1-124 · **Domain:** container security
- **Description:** The container-scan gate failure was resolved by **option B** (install security updates in
  the runtime stage) against the entry's recommendation of C (pin-and-bump by digest), because
  `python:3.12-slim` still shipped the vulnerable `util-linux` so **there was no fixed digest to pin to**
  while `apt-cache policy` reported the fix already in the archive. Also corrected: it is **one CVE across
  nine binary packages from one source**, not nine HIGH CVEs — Trivy's `Total: 9` counts rows.
- **Original source(s):** `CLAIM_LEDGER.md:3371`; `OPEN_DECISIONS.md:353-401`
- **Related claim IDs:** ARCH-33, ARCH-34, WORK-41, WORK-43
- **Related decision IDs:** OPEN_DECISIONS #11, D-384, PR #310
- **Repository evidence:** the `apt-get` upgrade line in `apps/*/Dockerfile`.
  **Deployed/live evidence:** the running images carry it.
- **Final disposition:** `RESOLVED` **with a standing known limitation** · **Justification:** B knowingly
  makes image contents depend on **when the build ran**, sacrificing the reproducibility the pinned base tag
  exists to provide; that cost is **accepted, not overlooked**, and C "stays the better long-term shape",
  unblocked when upstream republishes.
- **Remaining action:** none. **One combined observation is worth a register line:** the accepted
  reproducibility loss interacts with `ARCH-34-REVISION-DRIFT`'s `adopt_deployed_image` behaviour — **two
  independent mechanisms now make "what is in the running image" a runtime question rather than a repository
  question.**
- **Owner type:** none · **Reopen condition:** upstream republishes the base image · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `WORK-42-INTERSTITIAL-BYPASS` — the YouTube interstitial ships with an accepted middle-click bypass

- **Work/Issue ID:** `WORK-42` (OPEN_DECISIONS #12) · **Members:** E1-125 · **Domain:** minors' safety /
  external navigation
- **Description:** For `AUDIT_FINDINGS.md`:AUD-L-16 (video help sending a minor to youtube.com) the user
  chose **option B, the interstitial** (D-390), against the recommendation of a narrowly-scoped
  `youtube-nocookie` embed, preserving the property that the page loads nothing third-party. Implemented so
  the card stays a real anchor with a real `href` (the click is intercepted, the element is not replaced) so
  middle-click and open-in-new-tab still work and the existing href assertion holds — **and a power user can
  still bypass the step with a middle-click, accepted rather than overlooked.**
- **Original source(s):** `CLAIM_LEDGER.md:3384`; `OPEN_DECISIONS.md:403-450`
- **Related claim IDs:** REQ-25, REQ-34, WORK-37, WORK-42
- **Related decision IDs:** OPEN_DECISIONS #12, D-390, `video-intervention.spec.ts`
- **Repository evidence:** the interstitial in `InterventionScreen.tsx` / `VideoContent`.
  **Deployed/live evidence:** present in the deployed build.
- **Final disposition:** `RESOLVED` **with a standing known limitation** · **Justification:** the bypass is a
  documented accepted residual on a minor-safety control.
- **Remaining action:** none, except one placement point: **since the product's primary users are minors, the
  accepted bypass on an external-navigation interstitial belongs in the launch-readiness residual-risk set,
  not only in a decision log.**
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `WORK-43-FRONTEND-TESTS` — vitest and jsdom in both frontends, and the header count is wrong

- **Work/Issue ID:** `WORK-43` (OPEN_DECISIONS #14) · **Members:** E1-126 · **Domain:** frontend test tooling
- **Description:** The user chose **A, both frontends now** (D-405), against the recommendation of one app
  first, on the argument that two independently deployed frontends drifting is D-347 — the most repeated
  defect shape in the project — so **starting asymmetric is starting with the bug**. Built: vitest plus jsdom
  in both apps with per-app configuration, a `test` script and a CI `Test` step;
  `@testing-library/react` deferred until the first component test, which arrived with D-413 and required
  explicit `setupFiles`; closed by D-414 on the fourth assertion.
- **Original source(s):** `CLAIM_LEDGER.md:3397`; `OPEN_DECISIONS.md:5-6`, `:545-584`; `PROGRESS.md:53-60`;
  `DECISION_SUPERSESSION_MAP.md:1358-1361`, `:1374-1375`
- **Related claim IDs:** WORK-12, WORK-34, WORK-41, WORK-42, WORK-43, WORK-44
- **Related decision IDs:** OPEN_DECISIONS #14, D-347, D-399, D-403, D-404, D-405, D-413, D-414,
  EDGE-CHAT-02
- **Repository evidence:** `src/test/setup.ts` and the `Test` step in both CI jobs.
  **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` for the decision, with a **`DOCUMENTATION_ONLY` count defect**
- **Justification:** decided and built. The count defect: the file's header says "two of the answers went
  against the recommendation" while **at least four** outcomes are so labelled by the file itself (#1, #11,
  #12, #14, plus #13's WebKit sub-entry) — "a documentation defect in the summary line of the document most
  likely to be skimmed".
- **Remaining action:** correct the header count (folded into `DOC-DECISION-LOG-CORRECTIONS`). Two residuals
  to carry: `errors.ts`'s status-to-message rules remain carried by the browser suite alone, **stated as a
  choice rather than a gap**; and **`WORK-12-BANNER` is the asymmetry D-405 was chosen to prevent, still
  present.**
- **Owner type:** documentation · **Reopen condition:** n/a · **PROJECT_STATE?** no
- **Historical/archive only?** yes

### `D190-D191-PHANTOM` — the phantom trio's meta-note is the active record, and it must not be "completed"

- **Work/Issue ID:** `D-190`/`D-191` (phantom) · **Members:** E2-24 · **Domain:** decision-log integrity
- **Description:** Neither id has an entry; the log jumps D-189 → D-193. The corpus's own meta-note
  (`## D-190, D-191, D-192 — referenced everywhere, never written`, status `recorded`, line 16101)
  reconstructs both from the code and tests that cite them — **D-190** = approved authored content as a
  versioned file (`curriculum/internal_math/authored/*.yaml`, pinned by `test_authored_bank.py`);
  **D-191** = the gate made independent and `_DISALLOWED_WORDING` moved from substring to word-boundary
  matching after it destroyed a question about rolling a **die**. Citations: D-190 at 16110 and 16463; D-191
  across ~11 sites (13346, 13582, 13725, 16014, 16058, 16222, 16463, 19654, 19689–19690, 20243, 20422,
  21832, 22114). The note **refuses to backfill full entries**.
- **Original source(s):** `DECISION_SUPERSESSION_MAP.md:234-294` (esp. `:251-263`, `:270-280`)
- **Related claim IDs:** none · **Related decision IDs:** D-189, D-190, D-191, D-193, D-223, D-225, D-273
- **Repository evidence:** the substantive content is **live-in-code** for both ids.
  **Deployed/live evidence:** n/a.
- **Final disposition:** `RESOLVED` · **Justification:** the absence is recorded, the content is verifiable in
  code, and **the refusal to fabricate is itself the decision**.
- **Remaining action:** none, and one prohibition: **the note is the only resolution target for ~26
  citations — it must not be deleted or "completed".** Two soft caveats: the descriptions carry no date for
  when the decisions were actually taken, and the note's citation counts ("18 in code, 8 in docs") were never
  re-verified — only the DECISIONS side was. `D192-PHANTOM` is the third member and remains UNKNOWN by
  design.
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### `ARCH-27-SSE-GAP` — the single-instance SSE bus "known gap" was closed by the work the file says nobody scheduled

- **Work/Issue ID:** `ARCH-27` · **Members:** E1-30 · **Domain:** architecture
- **Description:** `FINAL_ARCHITECTURE.md` claims the SSE bus assumes exactly one Uvicorn worker and that
  nothing in S32/S33/S34 schedules replacing it with real pub/sub. **D-334/D-335 shipped exactly that
  replacement** (Postgres `LISTEN`/`NOTIFY` behind `SessionEventBus`), for both apps.
- **Original source(s):** `CLAIM_LEDGER.md:1063`; `FINAL_ARCHITECTURE.md:112-120`, `:146-152`, `:175-176`;
  `ARCHITECTURE.md:610-631`
- **Related claim IDs:** ARCH-10, ARCH-11, ARCH-26, ARCH-27
- **Related decision IDs:** D-032, D-334, D-335, D-395, D-396, D-349
- **Repository evidence:** `SessionEventBus`/`SessionEventRelay` exist for both apps.
  **Deployed/live evidence:** the relay is live; H5's chain records the architecture of record as "D-335 as
  amended by D-395" plus D-396 for telemetry.
- **Final disposition:** `RESOLVED` · **Justification:** the gap is closed for both apps; only the stale text
  remains, and `RISK-GROUP-ARCH-AUTHORITY`'s banner or archive covers it.
- **Remaining action:** none. Note the related documentation defect: **no single entry states the current
  whole** of the SSE architecture (`DOC-DECISION-LOG-CORRECTIONS`).
- **Owner type:** none · **Reopen condition:** n/a · **PROJECT_STATE?** no · **Historical/archive only?** yes

### §10.3 Resolved / superseded roll-up

Every `RESOLVED` or `SUPERSEDED` entry in the register, wherever it sits. **20 entries.**

| Entry key | Section | Disposition | What settled it |
|---|---|---|---|
| `D310-ROTATION` | §1 | RESOLVED | rotation executed and verified 2026-08-20T03:20:57Z |
| `COST-25-ALARM-COUNT` | §2 | RESOLVED (count) | delta-0 reconciliation, 30 configured == 30 deployed |
| `SNS-CONFIRMATION` | §3 | RESOLVED | COST-23 live read: both topics confirmed, 0 pending |
| `NAT-EXISTENCE` | §4 | RESOLVED | `nat-07ab02d5cd28b6f72` measured, priced, routed |
| `DRIFT-93-D401-D406-APPLIED` | §4 | RESOLVED | resource existence in AWS |
| `WORK-04-ANSWER-CACHE` | §6 | RESOLVED | D-423's numbers removed the precondition |
| `DRIFT-58-E2E-ISOLATION` | §7 | RESOLVED (claim scope) | staging run reproduced none of three symptoms |
| `F-17-STRENGTHENINGS` | §10 | RESOLVED | 562 tests executed; replay-from-empty verified |
| `F-04-QUOTE-FLOOR-LOCATION` | §10 | RESOLVED | durable evidence document already correct |
| `F-05-TOPIC-MAPPING` | §10 | RESOLVED | correction already integrated into the drift register |
| `F-07-ARCH01-SPLIT` | §10 | RESOLVED | correction already integrated as DRIFT-98 |
| `WORK-06-DEPLOY-EVENT` | §10 | RESOLVED | deploy landed, probe defect fixed |
| `WORK-09-AGENT-TOOLING` | §10 | RESOLVED | git state: both paths tracked in `a6da941` |
| `WORK-34-STUDY-RESERVE` | §10 | RESOLVED | D-325 option A, code-verified, five clean runs |
| `WORK-41-CVE-REPRODUCIBILITY` | §10 | RESOLVED (with limitation) | D-384 option B; C impossible today |
| `WORK-42-INTERSTITIAL-BYPASS` | §10 | RESOLVED (with limitation) | D-390 interstitial shipped |
| `WORK-43-FRONTEND-TESTS` | §10 | RESOLVED (+ count defect) | D-405/D-413/D-414 built in both apps |
| `D190-D191-PHANTOM` | §10 | RESOLVED | the meta-note is the active record |
| `ARCH-27-SSE-GAP` | §10 | RESOLVED | D-334/D-335 shipped the named remedy |
| `LIVE-HALVES-SUPERSEDED` | §10 | SUPERSEDED | Phase 3B produced both halves; three residuals re-emitted |

---

## §11 Coverage & accounting

*These tables prove no finding vanished. Each source ID appears **exactly once** per table, mapped to the
register entry that owns it, with §C overrides applied. Where an ID's substance is split across entries the
row names the owner and the cross-reference; the ID is still counted once.*

### §11(a) `REPOSITORY_DRIFT_REGISTER.md` — DRIFT-01 … DRIFT-102 (102 rows)

| DRIFT | Sev | Register entry |
|---|---|---|
| DRIFT-01 | HIGH | `RISK-GROUP-ARCH-AUTHORITY` |
| DRIFT-02 | HIGH | `TRACEABILITY-ARITHMETIC` (fix batched with DRIFT-38) |
| DRIFT-03 | HIGH | `ORG-COMMS` |
| DRIFT-04 | HIGH | `ORG-COMMS` (R1 sign-off); R8/R9-monitor half x-ref `R8-READ-SCOPE`, `KPI-ALARM-FLOOR`, `RISK-R2.2-ACCEPTED-RISK-HOMES` |
| DRIFT-05 | HIGH | `RISK-GROUP-FREEZE` |
| DRIFT-06 | HIGH | `RISK-GROUP-FREEZE` (sequenced first — wrong-action risk) |
| DRIFT-07 | HIGH | `RISK-GROUP-FREEZE` |
| DRIFT-08 | HIGH | `DISCLOSURES-LEGAL` |
| DRIFT-09 | MEDIUM | `SEC-13-PURGE` |
| DRIFT-10 | MED (high-adj) | `KPI-ALARM-FLOOR` (R9 tripwire sub-question) |
| DRIFT-11 | MED (high-adj) | `DISCLOSURES-LEGAL` |
| DRIFT-12 | MEDIUM | `DRIFT-12-ADMIN-ROLE` |
| DRIFT-13 | MEDIUM | `REQ-32-SAFETY` |
| DRIFT-14 | MEDIUM | `REQ-32-SAFETY` |
| DRIFT-15 | MEDIUM | `AMENDMENT-SWEEP` (flagged for sign-off) |
| DRIFT-16 | MEDIUM | `AMENDMENT-SWEEP` (flagged for sign-off) |
| DRIFT-17 | MEDIUM | `R8-READ-SCOPE` |
| DRIFT-18 | MEDIUM | `COST-06-FLUSH` |
| DRIFT-19 | MEDIUM | `COST-10-INPUT-BOUND` |
| DRIFT-20 | MEDIUM | `KPI-ALARM-FLOOR` |
| DRIFT-21 | MEDIUM | `COST-22-LABEL-PREINIT` |
| DRIFT-22 | MEDIUM | `D136-PRICE-TABLE` |
| DRIFT-23 | MEDIUM | `SPEND-ATTRIBUTION-DOC` |
| DRIFT-24 | MEDIUM | `DRIFT-24-ARTIFACT-FRESHNESS` (mechanism half x-ref `LB-05-DEPLOY-GAP`) |
| DRIFT-25 | MEDIUM | `DOC-SCHEDULER-SECTIONS` |
| DRIFT-26 | MEDIUM | `AMENDMENT-SWEEP` (RD-09 posture half x-ref `RDS-POSTURE`) |
| DRIFT-27 | MEDIUM | `AMENDMENT-SWEEP` |
| DRIFT-28 | MEDIUM | `DOC-DEPLOYED-STATE-CLAIMS` |
| DRIFT-29 | MEDIUM | `DOC-DEPLOYED-STATE-CLAIMS` |
| DRIFT-30 | MEDIUM | `REQ-39-ESTIMATED-LEVEL` |
| DRIFT-31 | MEDIUM | `DOC-CONTENT-PIPELINE` (delegation-direction flag carried) |
| DRIFT-32 | MEDIUM | `AMENDMENT-SWEEP` |
| DRIFT-33 | MEDIUM | `AMENDMENT-SWEEP` (schema-purity residual named there) |
| DRIFT-34 | MEDIUM | `AMENDMENT-SWEEP` (`attendance_status`/`user_role` lifted out there) |
| DRIFT-35 | MEDIUM | `AMENDMENT-SWEEP` (locus + `TurnReason` lifted out there) |
| DRIFT-36 | MEDIUM | `DISCLOSURES-LEGAL` |
| DRIFT-37 | MEDIUM | `TEST-05-DESCRIPTIVE-REREAD` |
| DRIFT-38 | MEDIUM | `TRACEABILITY-ARITHMETIC` |
| DRIFT-39 | MEDIUM | `TRACEABILITY-ARITHMETIC` |
| DRIFT-40 | MEDIUM | `AUDIT-ID-NAMESPACE` |
| DRIFT-41 | MEDIUM | `DOC-TEST-CLAIM-WORDING` |
| DRIFT-42 | MEDIUM | `WORK-09-AGENT-TOOLING` |
| DRIFT-43 | MEDIUM | `DOC-PROGRESS-QUEUED-BLOCK` |
| DRIFT-44 | MEDIUM | `WORK-12-BANNER` |
| DRIFT-45 | MEDIUM | `RETENTION-CLUSTER` |
| DRIFT-46 | MEDIUM | `RETENTION-CLUSTER` |
| DRIFT-47 | MEDIUM | `DOC-U7-BANNER` |
| DRIFT-48 | MEDIUM | `DOC-CONTENT-PIPELINE` |
| DRIFT-49 | MEDIUM | `DRIFT-49-MODEL-ROSTER` |
| DRIFT-50 | MEDIUM | `DOC-HINT-SOLUTION-REVIEW` |
| DRIFT-51 | MEDIUM | `DOC-CONTENT-PIPELINE` |
| DRIFT-52 | MEDIUM | `DOC-CONTENT-PIPELINE` |
| DRIFT-53 | LOW (med-adj) | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-54 | LOW (med-adj) | `BATCH-LOW-UNSCHEDULED-CONTROLS` |
| DRIFT-55 | LOW (med-adj) | `BATCH-LOW-UNMARKED-SPEC` |
| DRIFT-56 | LOW (med-adj) | `BATCH-LOW-CONFIG-VS-PLAN` |
| DRIFT-57 | LOW (med-adj) | `BATCH-LOW-CONFIG-VS-PLAN` |
| DRIFT-58 | LOW (med-adj) | **exception** → `DRIFT-58-E2E-ISOLATION` (listed in `BATCH-LOW-STALE-STATUS`) |
| DRIFT-59 | LOW (med-adj) | **exception** → `DRIFT-59-DATE-SHIFT` (listed in `BATCH-LOW-CONFIG-VS-PLAN`) |
| DRIFT-60 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-61 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-62 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-63 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-64 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-65 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-66 | LOW | **exception** → `DRIFT-66-NL2SQL` (listed in `BATCH-LOW-UNMARKED-SPEC`) |
| DRIFT-67 | LOW | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-68 | LOW | `BATCH-LOW-NARROW-COVERAGE` |
| DRIFT-69 | LOW | `BATCH-LOW-OVERSTATEMENT` (x-ref `IMAGE-WORK-PARK`) |
| DRIFT-70 | LOW | **exception** → `DRIFT-70-CONSENT-GATE` (listed in `BATCH-LOW-CONFIG-VS-PLAN`) |
| DRIFT-71 | LOW ×2 | `BATCH-LOW-OVERSTATEMENT` (71(b) duplicates DRIFT-33) |
| DRIFT-72 | LOW | **exception** → `DRIFT-72-OUTCOME-ENUM` (listed in `BATCH-LOW-OVERSTATEMENT`) |
| DRIFT-73 | LOW | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-74 | LOW | `BATCH-LOW-NARROW-COVERAGE` (same substance as `REQ-44-REASON-SWEEP`) |
| DRIFT-75 | LOW | `BATCH-LOW-STALE-STATUS` (one comment with DRIFT-102) |
| DRIFT-76 | LOW | `BATCH-LOW-STALE-STATUS` |
| DRIFT-77 | LOW | `BATCH-LOW-CITATIONS` |
| DRIFT-78 | LOW | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-79 | LOW | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-80 | LOW | `BATCH-LOW-UNSCHEDULED-CONTROLS` |
| DRIFT-81 | LOW | `BATCH-LOW-STALE-STATUS` (standing tfvars hazard) |
| DRIFT-82 | LOW | `BATCH-LOW-NARROW-COVERAGE` |
| DRIFT-83 | LOW | **exception** → `LANGSMITH-RETENTION` (listed in `BATCH-LOW-UNSCHEDULED-CONTROLS`) |
| DRIFT-84 | LOW → resolved | **exception** → `D310-ROTATION` (listed in `BATCH-LOW-UNSCHEDULED-CONTROLS`) |
| DRIFT-85 | LOW | **exception** → `DRIFT-85-I7-ALLOWLIST` (listed in `BATCH-LOW-NARROW-COVERAGE`) |
| DRIFT-86 | LOW | **exception** → `DRIFT-86-COST-RUNBOOK` (listed in `BATCH-LOW-OVERSTATEMENT`) |
| DRIFT-87 | LOW | `BATCH-LOW-UNSCHEDULED-CONTROLS` (superseded worse by `RD-01`) |
| DRIFT-88 | LOW | `BATCH-LOW-OVERSTATEMENT` |
| DRIFT-89 | LOW | **exception** → `ALERT-ENDPOINT` (listed in `BATCH-LOW-UNSCHEDULED-CONTROLS`) |
| DRIFT-90 | LOW | `BATCH-LOW-CITATIONS` (substance unresolvable — `DB-CONTENT-VERIFY`) |
| DRIFT-91 | LOW | **exception** → `DRIFT-91-ORGTIME-IMPORT` (listed in `BATCH-LOW-STALE-STATUS`) |
| DRIFT-92 | LOW | `BATCH-LOW-OVERSTATEMENT` (x-ref `WORK-04-ANSWER-CACHE`) |
| DRIFT-93 | LOW | **exception** → `DRIFT-93-D401-D406-APPLIED` (listed in `BATCH-LOW-STALE-STATUS`) |
| DRIFT-94 | LOW | `BATCH-LOW-STALE-STATUS` (x-ref `DOC-U7-BANNER`) |
| DRIFT-95 | LOW | `BATCH-LOW-STALE-STATUS` (x-ref `DOC-U7-BANNER`, `WORK-24-DUPLICATE-GAIN`) |
| DRIFT-96 | LOW | `BATCH-LOW-UNMARKED-SPEC` |
| DRIFT-97 | LOW | `BATCH-LOW-STALE-STATUS` (x-ref `VIDEO-COVERAGE-PARK`) |
| DRIFT-98 | **MEDIUM** | `RISK-GROUP-ARCH-AUTHORITY` (one family with DRIFT-01) |
| DRIFT-99 | LOW | `BATCH-LOW-UNMARKED-SPEC` |
| DRIFT-100 | LOW | `BATCH-LOW-CITATIONS` (count edit in `DOC-TEST-CLAIM-WORDING`) |
| DRIFT-101 | LOW | `BATCH-LOW-UNMARKED-SPEC` |
| DRIFT-102 | LOW | `BATCH-LOW-STALE-STATUS` (one comment with DRIFT-75) |

**Row count: 102.** Arithmetic check: HIGH 8 + MEDIUM 45 (DRIFT-09…52 = 44, plus DRIFT-98) + LOW 49
(DRIFT-53…97 = 45, plus DRIFT-99…102 = 4) = 102.

### §11(a2) The drift register's §3.2 decision rows (22 rows)

| # | DRIFT | Register entry | Final disposition |
|---|---|---|---|
| 1 | DRIFT-04 | `ORG-COMMS` | USER_DECISION_REQUIRED (UD-8) |
| 2 | DRIFT-05 | `RISK-GROUP-FREEZE` | DOCUMENTATION_ONLY (override) |
| 3 | DRIFT-06 | `RISK-GROUP-FREEZE` | DOCUMENTATION_ONLY (override) |
| 4 | DRIFT-07 | `RISK-GROUP-FREEZE` | DOCUMENTATION_ONLY (override) |
| 5 | DRIFT-08 | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| 6 | DRIFT-10 | `KPI-ALARM-FLOOR` | USER_DECISION_REQUIRED (UD-5 sub-question) |
| 7 | DRIFT-11 | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| 8 | DRIFT-12 | `DRIFT-12-ADMIN-ROLE` | DEFERRED (override) |
| 9 | DRIFT-13 | `REQ-32-SAFETY` | USER_DECISION_REQUIRED (UD-9) |
| 10 | DRIFT-14 | `REQ-32-SAFETY` | USER_DECISION_REQUIRED (UD-9, merged with row 9) |
| 11 | DRIFT-15 | `AMENDMENT-SWEEP` | DOCUMENTATION_ONLY (override, sign-off flagged) |
| 12 | DRIFT-16 | `AMENDMENT-SWEEP` | DOCUMENTATION_ONLY (override, sign-off flagged) |
| 13 | DRIFT-19 | `COST-10-INPUT-BOUND` | ACTIVE_IMPLEMENTATION (override) |
| 14 | DRIFT-20 | `KPI-ALARM-FLOOR` | USER_DECISION_REQUIRED (UD-5) |
| 15 | DRIFT-30 | `REQ-39-ESTIMATED-LEVEL` | USER_DECISION_REQUIRED (UD-12(e)) |
| 16 | DRIFT-40 | `AUDIT-ID-NAMESPACE` | DOCUMENTATION_ONLY (override) |
| 17 | DRIFT-44 | `WORK-12-BANNER` | ACTIVE_IMPLEMENTATION (override) |
| 18 | DRIFT-45 | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED (UD-7) |
| 19 | DRIFT-46 | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED (UD-7, merged with row 18) |
| 20 | DRIFT-49 | `DRIFT-49-MODEL-ROSTER` | UNKNOWN (override) |
| 21 | DRIFT-66 | `DRIFT-66-NL2SQL` | USER_DECISION_REQUIRED (UD-12(d)) |
| 22 | DRIFT-98 | `RISK-GROUP-ARCH-AUTHORITY` | DOCUMENTATION_ONLY (override; one family with DRIFT-01) |

**Row count: 22.** Of the register's 22 decision rows, **9 survive as genuine user decisions** (rows 1, 5, 6,
7, 9, 10, 14, 15, 18, 19, 21 — collapsing the three merged pairs gives 8 distinct queue items across UD-5,
UD-7, UD-8, UD-9, UD-10, UD-12(d), UD-12(e)); **9 are overridden to DOCUMENTATION_ONLY**; **2 to
ACTIVE_\***; **1 to DEFERRED**; **1 to UNKNOWN**. The three later-phase additions the register noted (RD-02,
RD-03, RD-09) map to `D310-ROTATION`, `BUDGET-GROSS-SPEND` and `RDS-POSTURE`.

### §11(b) `LOCAL_EXECUTION_FINDINGS.md` — F-01 … F-17 plus §4 and §5 (29 rows)

| Source row | Register entry | Final disposition |
|---|---|---|
| F-01 COST-10 input bound | `COST-10-INPUT-BOUND` | ACTIVE_IMPLEMENTATION |
| F-02 WORK-40 chat-web viewer locale | `WORK-40-TZ` | ACTIVE_REMEDIATION |
| F-03 `terraform apply` not in deploy | `F-03-DRIFT-DETECTOR` | OBSERVATION_ONLY |
| F-04 quote-floor test location | `F-04-QUOTE-FLOOR-LOCATION` | RESOLVED |
| F-05 `TOPIC_MAPPING` declared not absent | `F-05-TOPIC-MAPPING` | RESOLVED |
| F-06 four `checkpoint_repair` lines | `DOC-TEST-CLAIM-WORDING` | DOCUMENTATION_ONLY |
| F-07 ARCH-01 splits | `F-07-ARCH01-SPLIT` | RESOLVED |
| F-08 `extra="forbid"` 41 vs 31 | `DOC-TEST-CLAIM-WORDING` | DOCUMENTATION_ONLY |
| F-09 REQ-44 sweep 5 of 10 | `REQ-44-REASON-SWEEP` | ACTIVE_REMEDIATION |
| F-10 one test guards self-harm | `REQ-32-SAFETY` | USER_DECISION_REQUIRED (UD-9) |
| F-11 `purge_resume_writes` zero tests | `SEC-13-PURGE` | ACTIVE_REMEDIATION |
| F-12 COST-06 flush branch untested | `COST-06-FLUSH` | ACTIVE_REMEDIATION |
| F-13 no artifact-freshness check | `LB-05-DEPLOY-GAP` (doc half → `DRIFT-24-ARTIFACT-FRESHNESS`) | USER_DECISION_REQUIRED (UD-1) |
| F-14 WORK-12 banner conflict | `WORK-12-BANNER` | ACTIVE_IMPLEMENTATION |
| F-15 REQ-39 wording absent | `REQ-39-ESTIMATED-LEVEL` | USER_DECISION_REQUIRED (UD-12(e)) |
| F-16 REQ-27 notice + frozenset | `DISCLOSURES-LEGAL` (notice) / `REQ-27-FROZENSET` (frozenset) | UDR (UD-10) / ACTIVE_IMPLEMENTATION |
| F-17 positive strengthenings | `F-17-STRENGTHENINGS` | RESOLVED |
| §4 row 1 quote-floor path | `F-04-QUOTE-FLOOR-LOCATION` | RESOLVED (same item as F-04) |
| §4 row 2 `31` in repo docs | `DOC-TEST-CLAIM-WORDING` | DOCUMENTATION_ONLY (same item as F-08) |
| §4 row 3 `TOPIC_MAPPING` absent | `F-05-TOPIC-MAPPING` | RESOLVED (same item as F-05) |
| §4 row 4 "only three lines" | `DOC-TEST-CLAIM-WORDING` | DOCUMENTATION_ONLY (same item as F-06) |
| §4 row 5 ARCHITECTURE stale on decisions | `F-07-ARCH01-SPLIT` | RESOLVED (same item as F-07) |
| §4 row 6 `ruff format` 437 → 440 | `RUFF-DENOMINATOR` | OBSERVATION_ONLY (only §4 row with no F-xx) |
| §5 area 1 Playwright lane | `PLAYWRIGHT-LANE` | DEFERRED |
| §5 area 2 live/deployed halves | `LIVE-HALVES-SUPERSEDED` | SUPERSEDED (three residuals re-emitted) |
| §5 area 3 paid runs | `PAID-RUNS-LANE` | DEFERRED |
| §5 area 4 three new-test candidates | `SEC-13-PURGE` (+ `COST-06-FLUSH`, `REQ-27-FROZENSET`) | ACTIVE_REMEDIATION |
| §5 area 5 whole-suite `make test` | `WHOLE-SUITE-NOT-RUN` | OBSERVATION_ONLY |
| §5 area 6 no new test code | `NO-NEW-TEST-CODE` | OBSERVATION_ONLY |

**Row count: 29** (17 findings + 6 §4 rows + 6 §5 areas).

### §11(c) `DEPLOYED_INFRA_DRIFT_REGISTER.md` — RD-01 … RD-12 (12 rows)

| RD | Sev in register | Register entry | Final disposition |
|---|---|---|---|
| RD-01 | HIGH | `RD-01` | ACTIVE_REMEDIATION |
| RD-02 | MEDIUM (addendum: resolved) | `D310-ROTATION` (+ `D310-RESIDUALS`) | RESOLVED |
| RD-03 | MEDIUM | `BUDGET-GROSS-SPEND` | USER_DECISION_REQUIRED (UD-3) |
| RD-04 | MEDIUM | `LANGSMITH-INGEST` (+ `LANGSMITH-RETENTION`) | ACTIVE_REMEDIATION |
| RD-05 | MEDIUM | `DOC-DEPLOYED-STATE-CLAIMS` (fact settled by `NAT-EXISTENCE`) | DOCUMENTATION_ONLY |
| RD-06 | MEDIUM | `DOC-DEPLOYED-STATE-CLAIMS` (ARCH-15 refuted) | DOCUMENTATION_ONLY |
| RD-07 | MEDIUM | `KPI-ALARM-FLOOR` | USER_DECISION_REQUIRED (UD-5) |
| RD-08 | MEDIUM | `KPI-ALARM-FLOOR` (sub-question) | USER_DECISION_REQUIRED (UD-5) |
| RD-09 | MEDIUM | `RDS-POSTURE` | USER_DECISION_REQUIRED (UD-4) |
| RD-10 | LOW | `COST-25-ALARM-COUNT` (billing input to UD-3) | RESOLVED + DOCUMENTATION_ONLY |
| RD-11 | LOW | `ARCH-34-REVISION-DRIFT` | OBSERVATION_ONLY (tfvars half UNKNOWN) |
| RD-12 | LOW | `RD-12-INGRESS` | PARKED_BY_DECISION |

**Row count: 12.**

### §11(d) `LIVE_BEHAVIOR_FINDINGS.md` — LB-01 … LB-09 plus §5 residuals (13 rows)

| Source row | Register entry | Final disposition |
|---|---|---|
| LB-01 HINT_SOLUTION_REVIEW under-reports | `DOC-HINT-SOLUTION-REVIEW` | DOCUMENTATION_ONLY |
| LB-02 recall 1-of-8 superseded | `ACCESS-HINT-FIGURES` | DOCUMENTATION_ONLY |
| LB-03 "shipped ceiling of 0.40" | `ACCESS-HINT-FIGURES` | DOCUMENTATION_ONLY |
| LB-04 PROGRESS carries WORK-13 open | `WORK-13-FIXTURES` (register-level residual → `SPEND-AUTHORIZATION`) | ACTIVE_IMPLEMENTATION |
| LB-05 deployed build 10 commits behind | `LB-05-DEPLOY-GAP` | USER_DECISION_REQUIRED (UD-1) |
| LB-06 no email/calendar provider lever | `LB-06-TRANSPORT-POSTURE` | OBSERVATION_ONLY |
| LB-07 1735/2 structurally silent | `SUITE-COUNT-CITATIONS` | DOCUMENTATION_ONLY |
| LB-08 three corroborations | `LB-08-CORROBORATIONS` | OBSERVATION_ONLY |
| LB-09 no new behavioural defect | `LB-09-NULL-RESULT` | OBSERVATION_ONLY |
| §5(a) whole-directory e2e re-run | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| §5(b) access-hint recall re-measurement | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| §5(c) real-Bedrock eval opt-ins | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| §5 lane note judge histogram | `JUDGE-HISTOGRAM-PROVENANCE` | OBSERVATION_ONLY |

**Row count: 13.** The two §4 non-LB rows are also placed: WORK-05's "2 commits ahead" correction →
`SUITE-COUNT-CITATIONS`; TEST-21's historical half → `TEST-21-HISTORICAL`.

### §11(e) `CLAIM_LEDGER.md` — the 69 required ledger IDs plus 1 supplementary (70 rows)

| Claim ID | Leading status | Register entry | Final disposition |
|---|---|---|---|
| REQ-06 | UNKNOWN | `DRIFT-66-NL2SQL` | USER_DECISION_REQUIRED (UD-12(d)) |
| REQ-21 | DEFERRED | `IMAGE-WORK-PARK` | PARKED_BY_DECISION |
| REQ-24 | DEFERRED | `IMAGE-WORK-PARK` | PARKED_BY_DECISION |
| REQ-27 | UNKNOWN | `REQ-27-TOKEN-CONTRACT` | DEFERRED |
| ARCH-06 | UNKNOWN | `DOC-SCHEDULER-SECTIONS` | DOCUMENTATION_ONLY |
| ARCH-20 | UNKNOWN | `F2-ADAPTER-SHAPE` | DEFERRED |
| ARCH-21 | UNKNOWN | `ARCH-21-SCHEMA-SPLIT` | DEFERRED (override) |
| ARCH-22 | UNKNOWN | `RISK-GROUP-ARCH-AUTHORITY` | DOCUMENTATION_ONLY |
| ARCH-24 | UNKNOWN | `AMENDMENT-SWEEP` | DOCUMENTATION_ONLY |
| ARCH-29 | UNKNOWN | `NAT-EXISTENCE` | RESOLVED (override) |
| SEC-14 | DEFERRED | `IMAGE-WORK-PARK` | PARKED_BY_DECISION |
| SEC-15 | DEFERRED | `IMAGE-WORK-PARK` | PARKED_BY_DECISION |
| SEC-17 | DEFERRED | `SEC-17-GUARDDUTY` | PARKED_BY_DECISION (override) |
| SEC-18 | DEFERRED | `SEC-18-WAF` | DEFERRED |
| SEC-20 | DEFERRED | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| SEC-32 | UNKNOWN | `ORG-COMMS` | USER_DECISION_REQUIRED (UD-8) |
| COST-06 | UNKNOWN | `COST-06-FLUSH` | ACTIVE_REMEDIATION |
| COST-21 | UNKNOWN | `KPI-ALARM-FLOOR` | USER_DECISION_REQUIRED (UD-5) |
| COST-22 | UNKNOWN | `COST-22-LABEL-PREINIT` | ACTIVE_REMEDIATION |
| COST-25 | UNKNOWN | `COST-25-ALARM-COUNT` | RESOLVED + DOCUMENTATION_ONLY (override) |
| COST-28 | UNKNOWN | `NAT-EXISTENCE` | RESOLVED (override) |
| TEST-10 | DEFERRED | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| TEST-25 | PARTLY SUPERSEDED (suppl.) | `RISK-GROUP-AUDIT-REGISTERS` | DOCUMENTATION_ONLY |
| INT-05 | DEFERRED | `AUTH-OPTION-O1B` | PARKED_BY_DECISION |
| INT-19 | DEFERRED | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| INT-35 | DEFERRED | `S43-SCOPE` | PARKED_BY_DECISION |
| WORK-01 | CURRENT | `WORK-01-SCOPE-GUARD` | ACTIVE_IMPLEMENTATION |
| WORK-02 | CURRENT | `SNS-CONFIRMATION` | RESOLVED (override) |
| WORK-03 | CURRENT | `LB-05-DEPLOY-GAP` | USER_DECISION_REQUIRED (UD-1; closes on deploy) |
| WORK-04 | CURRENT | `WORK-04-ANSWER-CACHE` | RESOLVED (override) |
| WORK-05 | CURRENT | `SUITE-COUNT-CITATIONS` | DOCUMENTATION_ONLY |
| WORK-06 | CURRENT / HISTORICAL | `WORK-06-DEPLOY-EVENT` | RESOLVED |
| WORK-07 | CURRENT | `DOC-DEPLOYED-STATE-CLAIMS` | DOCUMENTATION_ONLY |
| WORK-08 | UNKNOWN | `DOC-DEPLOYED-STATE-CLAIMS` (fact settled by `DRIFT-93-D401-D406-APPLIED`) | DOCUMENTATION_ONLY |
| WORK-09 | CURRENT | `WORK-09-AGENT-TOOLING` | RESOLVED (override) |
| WORK-10 | DEFERRED | `D152-FREEZE` | PARKED_BY_DECISION |
| WORK-11 | UNKNOWN | `DOC-PROGRESS-QUEUED-BLOCK` | DOCUMENTATION_ONLY |
| WORK-12 | CURRENT | `WORK-12-BANNER` | ACTIVE_IMPLEMENTATION |
| WORK-13 | UNKNOWN | `WORK-13-FIXTURES` | ACTIVE_IMPLEMENTATION (override) |
| WORK-14 | DEFERRED | `D342-PARKING` | PARKED_BY_DECISION |
| WORK-15 | CURRENT | `D342-PARKING` | PARKED_BY_DECISION (rider) |
| WORK-16 | DEFERRED | `D152-FREEZE` | PARKED_BY_DECISION |
| WORK-17 | DEFERRED | `S43-SCOPE` | PARKED_BY_DECISION |
| WORK-18 | CURRENT | `WORK-01-SCOPE-GUARD` | ACTIVE_IMPLEMENTATION (measurement half settled) |
| WORK-19 | UNKNOWN | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED (UD-7) |
| WORK-20 | UNKNOWN | `DOC-U7-BANNER` (deployed half → `DB-CONTENT-VERIFY`) | DOCUMENTATION_ONLY |
| WORK-21 | UNKNOWN | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED (UD-7) |
| WORK-22 | UNKNOWN | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED (UD-7) |
| WORK-23 | HISTORICAL / CURRENT | `WORK-23-RETENTION-JOB-GATING` | PARKED_BY_DECISION |
| WORK-24 | UNKNOWN | `WORK-24-DUPLICATE-GAIN` | ACTIVE_REMEDIATION |
| WORK-25 | DEFERRED | `D342-PARKING` | PARKED_BY_DECISION |
| WORK-26 | SUPERSEDED | `DOC-CONTENT-PIPELINE` | DOCUMENTATION_ONLY |
| WORK-27 | CURRENT (with expiry) | `D342-PARKING` | PARKED_BY_DECISION |
| WORK-28 | UNKNOWN | `DOC-HINT-SOLUTION-REVIEW` | DOCUMENTATION_ONLY |
| WORK-29 | UNKNOWN | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| WORK-30 | SUPERSEDED / CURRENT | `DOC-CONTENT-PIPELINE` | DOCUMENTATION_ONLY |
| WORK-31 | CURRENT | `AMENDMENT-SWEEP` | DOCUMENTATION_ONLY |
| WORK-32 | CURRENT | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| WORK-33 | CURRENT / DEFERRED | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED (UD-10) |
| WORK-34 | CURRENT / SUPERSEDED | `WORK-34-STUDY-RESERVE` | RESOLVED |
| WORK-35 | CURRENT | `WORK-35-LEDGER` | ACTIVE_IMPLEMENTATION (override) |
| WORK-36 | DEFERRED | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| WORK-37 | DEFERRED | `VIDEO-COVERAGE-PARK` | PARKED_BY_DECISION |
| WORK-38 | CURRENT | `D342-PARKING` (conflict → `DIFFICULTY-TIERS-CONFLICT`) | PARKED_BY_DECISION |
| WORK-39 | DEFERRED | `D310-ROTATION` | RESOLVED (override) |
| WORK-40 | CURRENT | `WORK-40` | ACTIVE_IMPLEMENTATION |
| WORK-41 | CURRENT | `WORK-41-CVE-REPRODUCIBILITY` | RESOLVED (with limitation) |
| WORK-42 | CURRENT | `WORK-42-INTERSTITIAL-BYPASS` | RESOLVED (with limitation) |
| WORK-43 | CURRENT | `WORK-43-FRONTEND-TESTS` | RESOLVED + DOCUMENTATION_ONLY |
| WORK-44 | CURRENT | `WORK-44-DECIDED-NOT-BUILT` | ACTIVE_IMPLEMENTATION (#3, #9) |

**Row count: 70** (69 required + 1 supplementary). The 24 leading-UNKNOWN ids, the 19 leading-DEFERRED ids
and all 44 WORK ids appear above exactly once.

### §11(f) `DECISION_SUPERSESSION_MAP.md` — 29 chains plus 6 phantom ids (35 rows)

| # | Chain / phantom | Register entry | Final disposition |
|---|---|---|---|
| 1 | F1 deployment footprint | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY |
| 2 | F2 MongoDB→MySQL | `F2-ADAPTER-SHAPE` | DEFERRED |
| 3 | F3 dev auth / `/dev/token` | `F3-DEVTOKEN-S44` (+ `D310-ROTATION`) | DEFERRED |
| 4 | F4 criterion-6 date | `F4-CRITERION6` · `D141-TRIM` · `DOC-DECISION-LOG-CORRECTIONS` | PARKED / UDR (UD-12(b)) / DOC |
| 5 | F5 capacity purchase | `INT-10-PEAK-CONCURRENCY` (credit half → `BUDGET-GROSS-SPEND`) | PARKED_BY_DECISION (split) |
| 6 | F6 retention assumption | `RETENTION-CLUSTER` (+ `DOC-DECISION-LOG-CORRECTIONS`) | USER_DECISION_REQUIRED (UD-7) |
| 7 | G1 integration freeze | `D152-FREEZE` | PARKED_BY_DECISION |
| 8 | G2 branch-locator privacy | `G2-LOCATOR-PURGE` | OBSERVATION_ONLY |
| 9 | G3 tutor/manager read scope §7-R8 | `R8-READ-SCOPE` | PARKED_BY_DECISION (override) |
| 10 | G4 secrets exposure & rotation | `D310-ROTATION` (+ `D310-RESIDUALS`) | RESOLVED (override) |
| 11 | G5 org time convention | `ARCH-35-ORG-TIME` | BLOCKED (override) |
| 12 | G6 multi-child switcher | **cleanly closed — no register entry needed** (D-184; residuals are D-176's untagged "Known limitation, deliberate" bullet and one unopened possible softer link at ~12463) | n/a |
| 13 | G7 session renumbering | `G7-SESSION-RENUMBER` | OBSERVATION_ONLY |
| 14 | H1 access-probe rule evolution | `H1-ACCESS-PROBE` | OBSERVATION_ONLY |
| 15 | H2 AUD-C-23 oscillation | `H2-AUDC23` | DOCUMENTATION_ONLY (override) |
| 16 | H3 `.ics` / OPEN_DECISIONS #13 | `H3-ICS-WEBKIT` | OBSERVATION_ONLY (override) |
| 17 | H4 frontend unit tests / #14 | `WORK-12-BANNER` (+ `WORK-43-FRONTEND-TESTS`) | ACTIVE_IMPLEMENTATION |
| 18 | H5 chat turn lifecycle | `H5-LIVENESS-TIMER` | OBSERVATION_ONLY |
| 19 | K1 shape-pipeline retirement | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY |
| 20 | K2 phantom trio | `D190-D191-PHANTOM` · `D192-PHANTOM` | RESOLVED / UNKNOWN |
| 21 | K3 volume / coverage / parking | `D342-PARKING` · `DIFFICULTY-TIERS-CONFLICT` · `PROSE-QUALITY` · `DOC-CONTENT-PIPELINE` · `DOC-DECISION-LOG-CORRECTIONS` | PARKED / UDR ×2 / DOC ×2 |
| 22 | K4 difficulty judge / tiers | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY |
| 23 | K5 hint-quality instruments | `K5-HINT-INSTRUMENTS` | UNKNOWN |
| 24 | M1 SSE cross-replica delivery | `DOC-DECISION-LOG-CORRECTIONS` (+ `ARCH-27-SSE-GAP`) | DOCUMENTATION_ONLY |
| 25 | M2 deferred-narrative erasure | `D356-FAMILY` | ACTIVE_REMEDIATION |
| 26 | M3 study-walk drift / C1 Phase 6 | `M3-D370-SOLUTION-RUNG` · `D288-D317-CLOSURE` | ACTIVE_IMPLEMENTATION / UNKNOWN |
| 27 | M4 video catalog | `VIDEO-COVERAGE-PARK` | PARKED_BY_DECISION |
| 28 | M5 alarm split / NAT / image floor | `SNS-CONFIRMATION` · `DOC-DEPLOYED-STATE-CLAIMS` · `NAT-EXISTENCE` · `DOC-DECISION-LOG-CORRECTIONS` · `D356-FAMILY` | RESOLVED ×2 / DOC ×3 |
| 29 | M6 phantoms D-329 & D-363 | `D329-PHANTOM` · `DOC-DECISION-LOG-CORRECTIONS` | ACTIVE_REMEDIATION / DOC |
| P1 | phantom D-190 | `D190-D191-PHANTOM` | RESOLVED |
| P2 | phantom D-191 | `D190-D191-PHANTOM` | RESOLVED |
| P3 | phantom D-192 | `D192-PHANTOM` | UNKNOWN |
| P4 | phantom D-210 | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY |
| P5 | phantom D-329 | `D329-PHANTOM` | ACTIVE_REMEDIATION |
| P6 | phantom D-363 | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY |

**Row count: 35** (29 chains + 6 phantoms). Two cross-cutting map findings are also placed:
`STATUS-TAG-CONVENTION` (the `superseded`-never-used finding) and `AUDIT-ID-NAMESPACE` (bare audit ids),
plus the meta rows `MAP-HORIZON` and `DOC-DECISION-LOG-CORRECTIONS` (the phantom count).

### §11(g) `OPEN_DECISIONS.md` items 1–14 plus D-418 … D-423 (20 rows)

| Source | Register entry | Final disposition |
|---|---|---|
| #1 study re-serving exam questions | `WORK-34-STUDY-RESERVE` | RESOLVED |
| #2 client-error sink | `WORK-44-DECIDED-NOT-BUILT` | RESOLVED (that half) |
| #3 URL routing (`react-router`) | `WORK-44-DECIDED-NOT-BUILT` | ACTIVE_IMPLEMENTATION |
| #4 checkpoint pruning → option D | `WORK-35-LEDGER` | ACTIVE_IMPLEMENTATION |
| #5 depth-generation budget | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED (UD-2) |
| #6 video coverage & YouTube key | `VIDEO-COVERAGE-PARK` | PARKED_BY_DECISION |
| #7 `difficulty_tiers` declarations | `D342-PARKING` (conflict → `DIFFICULTY-TIERS-CONFLICT`) | PARKED_BY_DECISION |
| #8 D-310 dev-token posture | `D310-ROTATION` | RESOLVED by action |
| #9 dependency-PR backlog | `WORK-44-DECIDED-NOT-BUILT` | ACTIVE_IMPLEMENTATION |
| #10 five sub-items | `WORK-40` (sub-items 1–4) · `PROSE-QUALITY` (sub-item 5) | ACTIVE_IMPLEMENTATION / UDR (UD-12(c)) |
| #11 `util-linux` CVE | `WORK-41-CVE-REPRODUCIBILITY` | RESOLVED (with limitation) |
| #12 YouTube link-out | `WORK-42-INTERSTITIAL-BYPASS` | RESOLVED (with limitation) |
| #13 `downloadIcs` browser coverage | `H3-ICS-WEBKIT` | OBSERVATION_ONLY |
| #14 frontend unit tests | `WORK-43-FRONTEND-TESTS` | RESOLVED + DOCUMENTATION_ONLY |
| D-418 image floor / check defect | `ARCH-34-REVISION-DRIFT` (+ `DOC-DEPLOYED-STATE-CLAIMS`) | OBSERVATION_ONLY / DOC |
| D-419 D-401+D-406 applied | `DRIFT-93-D401-D406-APPLIED` · `SNS-CONFIRMATION` · `NAT-EXISTENCE` | RESOLVED ×3 (doc tails in `DOC-DEPLOYED-STATE-CLAIMS`, `RISK-GROUP-RESOLVED-LOOKS-OPEN`) |
| D-420 B4 part 1 escalation note | `LB-05-DEPLOY-GAP` | USER_DECISION_REQUIRED (UD-1 — no live evidence) |
| D-421 (+ addendum) B4 part 2 no duplicate email | `LB-05-DEPLOY-GAP` (migration `8509c0486d8d`) | USER_DECISION_REQUIRED (UD-1) |
| D-422 B4 part 3 note field | `LB-05-DEPLOY-GAP` | USER_DECISION_REQUIRED (UD-1) |
| D-423 B6 part 1 RAG latency split | `WORK-01-SCOPE-GUARD` · `WORK-04-ANSWER-CACHE` · `LB-08-CORROBORATIONS` | ACTIVE_IMPLEMENTATION / RESOLVED / OBSERVATION_ONLY |

**Row count: 20** (14 items + 6 decision ids; D-421's addendum is folded into D-421's row, as E7's appendix
listed it as a seventh heading with no separate decision id). E7's four "Not decisions" rows are also
placed: D-289 auto-approval → `PROSE-QUALITY`; D-302 tiers → `DOC-DECISION-LOG-CORRECTIONS`; D-152 →
`D152-FREEZE`; D-300 rubric → `BATCH-LOW-OVERSTATEMENT` (DRIFT-73).

### §11(h) `DOCUMENTATION_RISK_REGISTER.md` — all 49 risk IDs (49 rows)

| Risk | Sev | Register entry |
|---|---|---|
| R1.1 | HIGH | `RISK-GROUP-CURRENT-STATE` |
| R1.2 | HIGH | `RISK-GROUP-CURRENT-STATE` |
| R1.3 | MEDIUM | `RISK-GROUP-DECISIONS-HYGIENE` |
| R1.4 | MEDIUM | `RISK-R1.4-SPEC-VINTAGE` |
| R1.5 | MEDIUM | `RISK-GROUP-OPS-DOC-STRATA` |
| R1.6 | MEDIUM | `RISK-GROUP-OPS-DOC-STRATA` |
| R1.7 | MEDIUM | `RISK-GROUP-AUDIT-REGISTERS` |
| R1.8 | MEDIUM | `RISK-GROUP-EXECUTED-PLANS` |
| R2.1 | HIGH | `RISK-GROUP-ARCH-AUTHORITY` |
| R2.2 | HIGH | `RISK-R2.2-ACCEPTED-RISK-HOMES` |
| R2.3 | MEDIUM | `RISK-GROUP-DUPLICATE-CONTENT` |
| R2.4 | MEDIUM | `RISK-GROUP-DUPLICATE-CONTENT` |
| R2.5 | MEDIUM | `RISK-GROUP-DUPLICATE-CONTENT` |
| R2.6 | LOW | `RISK-GROUP-INDEX` |
| R3.1 | HIGH | `RISK-GROUP-ARCH-AUTHORITY` (naming policy shared with `RISK-GROUP-NAMING`) |
| R3.2 | HIGH | `RISK-GROUP-NAMING` (CLAUDE.md-description half → `RISK-GROUP-RESOLVED-LOOKS-OPEN`, `RISK-GROUP-INDEX`) |
| R3.3 | MEDIUM | `RISK-GROUP-NAMING` |
| R3.4 | MEDIUM | `RISK-GROUP-NAMING` (register-relationship half → `RISK-GROUP-AUDIT-REGISTERS`) |
| R3.5 | MEDIUM | `RISK-GROUP-NAMING` (snapshot half → `DOC-SNAPSHOT-BANNERS`) |
| R3.6 | MEDIUM | `RISK-GROUP-NAMING` (archive-convention half → `RISK-GROUP-EXECUTED-PLANS`) |
| R3.7 | LOW | `RISK-GROUP-CURRENT-STATE` |
| R3.8 | LOW | `RISK-GROUP-NAMING` (§2.6 namespace half also in `RISK-R6.4-SESSION-LABELS`) |
| R4.1 | HIGH | `RISK-GROUP-FREEZE` |
| R4.2 | HIGH | `RISK-GROUP-EXECUTED-PLANS` |
| R4.3 | HIGH | `RISK-GROUP-FREEZE` |
| R4.4 | HIGH | `RISK-GROUP-FREEZE` |
| R4.5 | MEDIUM | `RISK-GROUP-FREEZE` |
| R4.6 | MEDIUM | `RISK-GROUP-OPS-DOC-STRATA` (HINT_SOLUTION_REVIEW clause → `DOC-HINT-SOLUTION-REVIEW`; U7 clause → `DOC-SNAPSHOT-BANNERS`) |
| R4.7 | LOW | `RISK-GROUP-OPS-DOC-STRATA` |
| R5.1 | HIGH | `RISK-GROUP-RESOLVED-LOOKS-OPEN` |
| R5.2 | HIGH | `RISK-GROUP-ARCH-AUTHORITY` (the inverse, undecided question 5 → `ARCH-21-SCHEMA-SPLIT`) |
| R5.3 | MEDIUM | `RISK-GROUP-RESOLVED-LOOKS-OPEN` |
| R5.4 | MEDIUM | `RISK-GROUP-AUDIT-REGISTERS` |
| R5.5 | MEDIUM | `RISK-GROUP-RESOLVED-LOOKS-OPEN` |
| R5.6 | MEDIUM | `RISK-GROUP-OPS-DOC-STRATA` (merged with `DOC-HINT-SOLUTION-REVIEW`) |
| R5.7 | MEDIUM | `TRACKING-HOME-FOR-OPEN-ITEMS` |
| R6.1 | HIGH | `RISK-GROUP-DECISIONS-HYGIENE` |
| R6.2 | HIGH | `RISK-GROUP-DECISIONS-HYGIENE` |
| R6.3 | HIGH | `RISK-GROUP-AUDIT-REGISTERS` |
| R6.4 | MEDIUM | `RISK-R6.4-SESSION-LABELS` |
| R6.5 | MEDIUM | `RISK-R6.5-SUPERSESSION-DIRECTION` |
| R6.6 | LOW | `RISK-GROUP-ARCH-AUTHORITY` |
| R7.1 | HIGH | `RISK-GROUP-INDEX` |
| R7.2 | MEDIUM | `COMMITTED-ORG-DRAFTS` |
| R7.3 | LOW | `RISK-R7.3-DANGLING-REFS` (ENROLLMENT_FAQ clause also in `INT-29-FAQ`) |
| R8.1 | HIGH | `RISK-GROUP-CURRENT-STATE` |
| R8.2 | MEDIUM | `RISK-GROUP-CURRENT-STATE` |
| R8.3 | LOW | `RISK-GROUP-CURRENT-STATE` |
| R9.1 | HIGH (summary) | `RISK-GROUP-FREEZE` |

**Row count: 49.** Section arithmetic: §1 = 8, §2 = 6, §3 = 8, §4 = 7, §5 = 7, §6 = 6, §7 = 3, §8 = 3,
§9 = 1 → **49 risk IDs, 49 mapped rows, zero unmapped.** The five inventory-only additions are also placed:
`DOC-SNAPSHOT-BANNERS`, `INT-29-FAQ`, `FIRST-VISIT-REVERIFY`, `DOC-VINTAGE-HEADERS`,
`DOC-LINE-CITATION-DRIFT`.

### §11(i) `REMEDIATION_D310_ROTATION.md` (4 rows)

| Source | Register entry | Final disposition |
|---|---|---|
| §1–§7 the rotation itself (execution, drain, probes, post-apply plan) | `D310-ROTATION` | RESOLVED |
| §8 consumers — the browser `localStorage` re-paste (`:107-110`) | `D310-RESIDUALS` (item 1) | ACTIVE_REMEDIATION (owner: user-action) |
| §9 residual — `make load-staging-learning` docker env pass-through never re-measured for `ps` visibility (`:119-121`) | `D310-RESIDUALS` (item 2) | ACTIVE_REMEDIATION (engineering measurement) |
| §9 residual — `e2e/README.md:16-17` pre-D-310 export shape; plus the recorded acceptance that no standing rotation mechanism exists and the S44 deletion plan stands (`:115-116`) | `D310-RESIDUALS` (item 3) + `D310-ROTATION` (accepted note) | DOCUMENTATION_ONLY / accepted |

**Row count: 4.** Two audit-artifact corrections are recorded rather than dropped: the DRIFT register's
§3.2 row at `DEPLOYED_INFRA_DRIFT_REGISTER.md:361` predates the addendum at `:149` and the addendum wins;
and OPEN_DECISIONS #8's wording is marked superseded-operationally
(`RISK-GROUP-RESOLVED-LOOKS-OPEN`).

---

### §11(j) Source-item roll-call — every extraction item to its owning entry

*Compact form, one line per extractor. This guarantees that no candidate item from any stream is
unaccounted for, including the ones whose underlying finding IDs are covered by tables (a)–(i).*

**E1 (131 items).** 1 → `DRIFT-66-NL2SQL` · 2 → `R8-READ-SCOPE` · 3 → `RETENTION-CLUSTER` ·
4 → `COST-06-FLUSH` · 5,6,7,8 → `IMAGE-WORK-PARK` · 9,10 → `DISCLOSURES-LEGAL` ·
11 → `REQ-27-TOKEN-CONTRACT` · 12 → `DISCLOSURES-LEGAL` · 13 → `REQ-32-SAFETY` ·
14 → `AMENDMENT-SWEEP` · 15 → `IRT-UPGRADE` · 16 → `AMENDMENT-SWEEP` ·
17,18,19 → `DOC-SCHEDULER-SECTIONS` · 20 → `ARCH-17-COMMIT-SEAM` · 21 → `R8-READ-SCOPE` ·
22 → `RETENTION-CLUSTER` · 23 → `F2-ADAPTER-SHAPE` · 24 → `ARCH-21-SCHEMA-SPLIT` ·
25 → `RISK-GROUP-ARCH-AUTHORITY` · 26,27,28 → `AMENDMENT-SWEEP` ·
29 → `RISK-GROUP-ARCH-AUTHORITY` · 30 → `ARCH-27-SSE-GAP` · 31 → `NAT-EXISTENCE` ·
32 → `DOC-DEPLOYED-STATE-CLAIMS` · 33 → `R8-READ-SCOPE` · 34 → `KPI-ALARM-FLOOR` ·
35,36 → `IMAGE-WORK-PARK` · 37 → `SEC-17-GUARDDUTY` · 38 → `SEC-18-WAF` ·
39 → `DISCLOSURES-LEGAL` · 40 → `D310-ROTATION` · 41,42,43 → `ORG-COMMS` ·
44 → `SEC-34-ROLE-ALLOWLIST` · 45 → `COST-06-FLUSH` · 46 → `SPEND-ATTRIBUTION-DOC` ·
47,48 → `RD-01` · 49 → `KPI-ALARM-FLOOR` · 50 → `COST-22-LABEL-PREINIT` ·
51 → `COST-25-ALARM-COUNT` · 52 → `SNS-CONFIRMATION` · 53 → `NAT-EXISTENCE` ·
54 → `COST-29-EXTRAPOLATION-BAN` · 55 → `TEST-01-CRITERION1` ·
56 → `TEST-05-DESCRIPTIVE-REREAD` · 57,58 → `TRACEABILITY-ARITHMETIC` ·
59 → `SEC-17-GUARDDUTY` · 60 → `DISCLOSURES-LEGAL` · 61,62,63 → `AUDIT-COUNT-INSTRUMENT` ·
64 → `AUDIT-ID-NAMESPACE` · 65 → `TEST-24-429` · 66 → `RISK-GROUP-AUDIT-REGISTERS` ·
67 → `SUITE-COUNT-CITATIONS` · 68 → `AUTH-OPTION-O1B` · 69,70 → `RISK-GROUP-FREEZE` ·
71 → `INT-10-PEAK-CONCURRENCY` · 72 → `SEC-34-ROLE-ALLOWLIST` · 73 → `ORG-COMMS` ·
74,75 → `INT-ATTENDANCE-DERIVATION` · 76 → `DISCLOSURES-LEGAL` · 77 → `F2-ADAPTER-SHAPE` ·
78 → `ORG-COMMS` · 79 → `RISK-GROUP-FREEZE` · 80 → `ORG-COMMS` (doc half x-ref
`RISK-GROUP-FREEZE`) · 81 → `INT-29-FAQ` · 82 → `ORG-COMMS` · 83 → `S43-SCOPE` ·
84 → `WORK-01-SCOPE-GUARD` · 85 → `SNS-CONFIRMATION` · 86 → `LB-05-DEPLOY-GAP` ·
87 → `WORK-04-ANSWER-CACHE` · 88 → `SUITE-COUNT-CITATIONS` · 89 → `WORK-06-DEPLOY-EVENT` ·
90,91 → `DOC-DEPLOYED-STATE-CLAIMS` · 92 → `WORK-09-AGENT-TOOLING` · 93 → `D152-FREEZE` ·
94 → `DOC-PROGRESS-QUEUED-BLOCK` · 95 → `WORK-12-BANNER` · 96 → `WORK-13-FIXTURES` ·
97,98 → `D342-PARKING` · 99 → `D152-FREEZE` · 100 → `S43-SCOPE` · 101 → `WORK-01-SCOPE-GUARD` ·
102 → `RETENTION-CLUSTER` · 103 → `DOC-U7-BANNER` · 104,105 → `RETENTION-CLUSTER` ·
106 → `WORK-23-RETENTION-JOB-GATING` · 107 → `WORK-24-DUPLICATE-GAIN` · 108 → `D342-PARKING` ·
109 → `DOC-CONTENT-PIPELINE` · 110 → `D342-PARKING` · 111 → `DOC-HINT-SOLUTION-REVIEW` ·
112 → `SPEND-AUTHORIZATION` · 113 → `DOC-CONTENT-PIPELINE` · 114 → `AMENDMENT-SWEEP` ·
115,116 → `DISCLOSURES-LEGAL` · 117 → `WORK-34-STUDY-RESERVE` · 118 → `WORK-35-LEDGER` ·
119 → `SPEND-AUTHORIZATION` · 120 → `VIDEO-COVERAGE-PARK` · 121 → `D342-PARKING` ·
122 → `D310-ROTATION` · 123 → `WORK-40` · 124 → `WORK-41-CVE-REPRODUCIBILITY` ·
125 → `WORK-42-INTERSTITIAL-BYPASS` · 126 → `WORK-43-FRONTEND-TESTS` ·
127 → `WORK-44-DECIDED-NOT-BUILT` · 128 → `AMENDMENT-SWEEP` ·
129 → `DIFFICULTY-TIERS-CONFLICT` · 130 → `D356-FAMILY` · 131 → `RETENTION-CLUSTER`.

**E2 (50 items).** 1 → `DOC-DECISION-LOG-CORRECTIONS` · 2 → `F2-ADAPTER-SHAPE` ·
3 → `F3-DEVTOKEN-S44` · 4 → `F4-CRITERION6` · 5 → `D141-TRIM` ·
6 → `DOC-DECISION-LOG-CORRECTIONS` · 7 → `INT-10-PEAK-CONCURRENCY` ·
8 → **split**: (a) `INT-10-PEAK-CONCURRENCY`, (b) `BUDGET-GROSS-SPEND` ·
9 → `DOC-DECISION-LOG-CORRECTIONS` · 10,11 → `RETENTION-CLUSTER` · 12 → `D152-FREEZE` ·
13 → `G2-LOCATOR-PURGE` · 14 → `R8-READ-SCOPE` · 15 → `D310-ROTATION` + `D310-RESIDUALS` ·
16 → `ARCH-35-ORG-TIME` · 17 → `G7-SESSION-RENUMBER` · 18 → `H1-ACCESS-PROBE` ·
19 → `H2-AUDC23` · 20 → `H3-ICS-WEBKIT` · 21 → `WORK-12-BANNER` · 22 → `H5-LIVENESS-TIMER` ·
23 → `DOC-DECISION-LOG-CORRECTIONS` · 24 → `D190-D191-PHANTOM` · 25 → `D192-PHANTOM` ·
26 → `DOC-DECISION-LOG-CORRECTIONS` · 27 → `D329-PHANTOM` ·
28 → `DOC-DECISION-LOG-CORRECTIONS` · 29 → `D342-PARKING` ·
30 → `DIFFICULTY-TIERS-CONFLICT` · 31 → `PROSE-QUALITY` ·
32 → `DOC-DECISION-LOG-CORRECTIONS` · 33 → `DOC-CONTENT-PIPELINE` ·
34 → `DOC-DECISION-LOG-CORRECTIONS` · 35 → `K5-HINT-INSTRUMENTS` ·
36 → `DOC-DECISION-LOG-CORRECTIONS` · 37,38 → `D356-FAMILY` ·
39 → `M3-D370-SOLUTION-RUNG` · 40 → `D288-D317-CLOSURE` · 41 → `VIDEO-COVERAGE-PARK` ·
42 → `SNS-CONFIRMATION` · 43 → `DOC-DEPLOYED-STATE-CLAIMS` · 44 → `NAT-EXISTENCE` ·
45 → `DOC-DECISION-LOG-CORRECTIONS` · 46 → `D356-FAMILY` · 47 → `STATUS-TAG-CONVENTION` ·
48 → `AUDIT-ID-NAMESPACE` · 49 → `MAP-HORIZON` · 50 → `DOC-DECISION-LOG-CORRECTIONS`.

**E3 (60 items).** 1 → `RISK-GROUP-ARCH-AUTHORITY` · 2 → `TRACEABILITY-ARITHMETIC` ·
3,4 → `ORG-COMMS` · 5,6,7 → `RISK-GROUP-FREEZE` · 8 → `DISCLOSURES-LEGAL` ·
9 → `SEC-13-PURGE` · 10 → `KPI-ALARM-FLOOR` · 11 → `DISCLOSURES-LEGAL` ·
12 → `DRIFT-12-ADMIN-ROLE` · 13,14 → `REQ-32-SAFETY` · 15,16 → `AMENDMENT-SWEEP` ·
17 → `R8-READ-SCOPE` · 18 → `COST-06-FLUSH` · 19 → `COST-10-INPUT-BOUND` ·
20 → `KPI-ALARM-FLOOR` · 21 → `COST-22-LABEL-PREINIT` · 22 → `D136-PRICE-TABLE` ·
23 → `SPEND-ATTRIBUTION-DOC` · 24 → `DRIFT-24-ARTIFACT-FRESHNESS` ·
25 → `DOC-SCHEDULER-SECTIONS` · 26,27 → `AMENDMENT-SWEEP` ·
28,29 → `DOC-DEPLOYED-STATE-CLAIMS` · 30 → `REQ-39-ESTIMATED-LEVEL` ·
31 → `DOC-CONTENT-PIPELINE` · 32,33,34,35 → `AMENDMENT-SWEEP` · 36 → `DISCLOSURES-LEGAL` ·
37 → `TEST-05-DESCRIPTIVE-REREAD` · 38,39 → `TRACEABILITY-ARITHMETIC` ·
40 → `AUDIT-ID-NAMESPACE` · 41 → `DOC-TEST-CLAIM-WORDING` · 42 → `WORK-09-AGENT-TOOLING` ·
43 → `DOC-PROGRESS-QUEUED-BLOCK` · 44 → `WORK-12-BANNER` · 45,46 → `RETENTION-CLUSTER` ·
47 → `DOC-U7-BANNER` · 48 → `DOC-CONTENT-PIPELINE` · 49 → `DRIFT-49-MODEL-ROSTER` ·
50 → `DOC-HINT-SOLUTION-REVIEW` · 51,52 → `DOC-CONTENT-PIPELINE` ·
53 → `RISK-GROUP-ARCH-AUTHORITY` · 54 → `BATCH-LOW-CITATIONS` ·
55 → `BATCH-LOW-STALE-STATUS` (+ exceptions `DRIFT-58-E2E-ISOLATION`,
`DRIFT-91-ORGTIME-IMPORT`, `DRIFT-93-D401-D406-APPLIED`) ·
56 → `BATCH-LOW-OVERSTATEMENT` (+ `DRIFT-72-OUTCOME-ENUM`, `DRIFT-86-COST-RUNBOOK`) ·
57 → `BATCH-LOW-UNMARKED-SPEC` (+ `DRIFT-66-NL2SQL`) ·
58 → `BATCH-LOW-UNSCHEDULED-CONTROLS` (+ `D310-ROTATION`, `LANGSMITH-RETENTION`,
`ALERT-ENDPOINT`) · 59 → `BATCH-LOW-NARROW-COVERAGE` (+ `DRIFT-85-I7-ALLOWLIST`) ·
60 → `BATCH-LOW-CONFIG-VS-PLAN` (+ `DRIFT-59-DATE-SHIFT`, `DRIFT-70-CONSENT-GATE`).

**E4 (24 items).** 1 → `COST-10-INPUT-BOUND` · 2 → `WORK-40-TZ` · 3 → `F-03-DRIFT-DETECTOR` ·
4 → `F-04-QUOTE-FLOOR-LOCATION` · 5 → `F-05-TOPIC-MAPPING` · 6 → `DOC-TEST-CLAIM-WORDING` ·
7 → `F-07-ARCH01-SPLIT` · 8 → `DOC-TEST-CLAIM-WORDING` · 9 → `REQ-44-REASON-SWEEP` ·
10 → `REQ-32-SAFETY` · 11 → `SEC-13-PURGE` · 12 → `COST-06-FLUSH` ·
13 → `LB-05-DEPLOY-GAP` (doc half `DRIFT-24-ARTIFACT-FRESHNESS`) · 14 → `WORK-12-BANNER` ·
15 → `REQ-39-ESTIMATED-LEVEL` · 16 → `DISCLOSURES-LEGAL` + `REQ-27-FROZENSET` ·
17 → `F-17-STRENGTHENINGS` · 18 → `RUFF-DENOMINATOR` · 19 → `PLAYWRIGHT-LANE` ·
20 → `LIVE-HALVES-SUPERSEDED` · 21 → `PAID-RUNS-LANE` ·
22 → `SEC-13-PURGE` (+ `COST-06-FLUSH`, `REQ-27-FROZENSET`) · 23 → `WHOLE-SUITE-NOT-RUN` ·
24 → `NO-NEW-TEST-CODE`.

**E5 (33 items).** 1 → `RD-01` · 2 → `D310-ROTATION` · 3 → `D310-RESIDUALS` ·
4,5 → `BUDGET-GROSS-SPEND` · 6 → `LANGSMITH-INGEST` · 7 → `LANGSMITH-RETENTION` ·
8,9 → `DOC-DEPLOYED-STATE-CLAIMS` · 10,11 → `KPI-ALARM-FLOOR` · 12,13 → `RDS-POSTURE` ·
14 → `BUDGET-GROSS-SPEND` · 15 → `ARCH-34-REVISION-DRIFT` · 16 → `RD-12-INGRESS` ·
17,18 → `DOC-DEPLOYED-STATE-CLAIMS` · 19 → `ALERT-ENDPOINT` · 20 → `KPI-ALARM-FLOOR` ·
21 → `COST-17-CLIENT-ERRORS` · 22 → `RETENTION-CLUSTER` · 23 → `SPEND-AUTHORIZATION` ·
24 → `C6-UNATTENDED` · 25 → `ARCH-35-ORG-TIME` · 26 → `SEC-17-GUARDDUTY` ·
27 → `DB-CONTENT-VERIFY` · 28 → `SPEND-AUTHORIZATION` · 29 → `LB-05-DEPLOY-GAP` ·
30 → `ARCH-33-CI-GATE` · 31 → `ARCH-30-OTEL` · 32 → `WORK-23-RETENTION-JOB-GATING` ·
33 → `COST-28-EIP`.

**E6 (39 items).** 1 → `DOC-HINT-SOLUTION-REVIEW` · 2,3 → `ACCESS-HINT-FIGURES` ·
4 → `WORK-13-FIXTURES` · 5 → `LB-05-DEPLOY-GAP` · 6 → `LB-06-TRANSPORT-POSTURE` ·
7 → `SUITE-COUNT-CITATIONS` · 8 → `LB-08-CORROBORATIONS` · 9 → `LB-09-NULL-RESULT` ·
10 → `SUITE-COUNT-CITATIONS` · 11 → `TEST-21-HISTORICAL` · 12,13,14 → `SPEND-AUTHORIZATION` ·
15 → `JUDGE-HISTOGRAM-PROVENANCE` · 16 → `RISK-GROUP-FREEZE` ·
17 → `RISK-GROUP-ARCH-AUTHORITY` · 18 → `ARCH-21-SCHEMA-SPLIT` ·
19 → `RISK-R2.2-ACCEPTED-RISK-HOMES` · 20 → `RISK-GROUP-CURRENT-STATE` ·
21 → `RISK-R1.4-SPEC-VINTAGE` · 22 → `RISK-GROUP-DECISIONS-HYGIENE` ·
23 → `RISK-GROUP-AUDIT-REGISTERS` · 24 → `RISK-GROUP-NAMING` ·
25 → `RISK-GROUP-RESOLVED-LOOKS-OPEN` · 26 → `TRACKING-HOME-FOR-OPEN-ITEMS` ·
27 → `RISK-GROUP-INDEX` · 28 → `RISK-GROUP-DUPLICATE-CONTENT` ·
29 → `RISK-GROUP-EXECUTED-PLANS` · 30 → `RISK-GROUP-OPS-DOC-STRATA` ·
31 → `COMMITTED-ORG-DRAFTS` · 32 → `RISK-R7.3-DANGLING-REFS` ·
33 → `RISK-R6.4-SESSION-LABELS` · 34 → `RISK-R6.5-SUPERSESSION-DIRECTION` ·
35 → `DOC-SNAPSHOT-BANNERS` · 36 → `INT-29-FAQ` · 37 → `FIRST-VISIT-REVERIFY` ·
38 → `DOC-VINTAGE-HEADERS` · 39 → `DOC-LINE-CITATION-DRIFT`.

**E7 (12 items).** 1 → `LB-05-DEPLOY-GAP` · 2 → `SPEND-AUTHORIZATION` · 3 → `RDS-POSTURE` ·
4 → `KPI-ALARM-FLOOR` · 5 → `D310-ROTATION` · 6 → `VIDEO-COVERAGE-PARK` ·
7 → `D152-FREEZE` · 8 → `WORK-04-ANSWER-CACHE` · 9 → `WORK-01-SCOPE-GUARD` ·
10 → `PROSE-QUALITY` · 11 → `SPEND-AUTHORIZATION` · 12 → `WORK-35-LEDGER`.

**Total source items placed: 131 + 50 + 60 + 24 + 33 + 39 + 12 = 349.** Every one maps to exactly one
owning entry; splits and cross-references are named on the row and do not create a second placement.

---

## §12 Statistics

### §12.1 Entry counts per disposition

**Counting rule: these are REGISTER ENTRIES (canonical topic keys), not source items.** 349 source items
merge into **166 entries**. A single entry may own many source items (for example `AMENDMENT-SWEEP` owns 16
and `RETENTION-CLUSTER` owns 11), and one source item may be split across two entries without being counted
twice. Where an entry carries a primary disposition plus a named residual of a different kind (for example
`COST-25-ALARM-COUNT`: RESOLVED for the count, DOCUMENTATION_ONLY for the billing line) it is counted **once,
under its primary disposition**.

| Disposition | Entries | PROJECT_STATE? |
|---|---|---|
| `USER_DECISION_REQUIRED` | **16** | yes |
| `ACTIVE_REMEDIATION` | **16** | yes |
| `ACTIVE_IMPLEMENTATION` | **11** | yes |
| `BLOCKED` | **6** | yes |
| `DEFERRED` | **15** | yes |
| `PARKED_BY_DECISION` | **13** | yes (as a parked list with reopen conditions) |
| `DOCUMENTATION_ONLY` | **44** | no — canonical-migration worklist |
| `OBSERVATION_ONLY` | **21** | no — historical |
| `RESOLVED` | **19** | no — historical |
| `SUPERSEDED` | **1** | no — historical |
| `UNKNOWN` | **4** | yes, as recorded unknowns |
| **Total** | **166** | — |

Derived counts for the completion report:

- **Entries that belong in a future PROJECT_STATE document: 81** (16 + 16 + 11 + 6 + 15 + 13 + 4).
- **Entries that are open engineering work: 27** (`ACTIVE_REMEDIATION` 16 + `ACTIVE_IMPLEMENTATION` 11).
- **Entries that are documents-only work: 44**, the canonical-migration worklist.
- **Entries that are historical or archive material: 41** (`OBSERVATION_ONLY` 21 + `RESOLVED` 19 +
  `SUPERSEDED` 1).
- **Genuine user decisions: 12 queue entries** (§12.3), carried by 16 register entries because UD-12 bundles
  six one-line confirmations and UD-11 is carried by a `BLOCKED` entry. **Sub-questions attached to queue
  entries: 4** — UD-1's gate-integrity question (does §2.6 criterion 6's unattended week restart clean after
  the RD-01 fix?), UD-5's R9 checkpoint-repair tripwire, UD-7's REQ-18 invalid-output capture, and UD-2's
  read-only database-session rider. Counting UD-12's six sub-items as sub-questions instead of entries gives
  **10 top-level questions plus 6 one-line confirmations plus 4 sub-questions**.
- **Blocking answer:** **nothing in this register blocks the canonical-document proposal.** `UD-12(a)`
  (`DIFFICULTY-TIERS-CONFLICT`) and `STATUS-TAG-CONVENTION` are **inputs** to it and both have safe defaults
  — D-341 is already being followed in practice, and the eight actively-misleading status tags are a
  separable immediate fix. The only queue entry that blocks anything at all is **UD-1**, and it blocks
  *partially*: no live verification of the B4 escalation series is possible without a deploy.

### §12.2 The five surviving UNKNOWNs, with their resolution steps

| UNKNOWN | Host entry | Named resolution step |
|---|---|---|
| **D-192's content** | `D192-PHANTOM` (§9) | **None exists — irreducible by design.** The whole remedy is one clarifying sentence scoping the meta-note's "no citation states what it decided" to *code* citations. Do **not** adopt D-193's description as D-192's content. |
| **K5 / D-264's annotation state** | `K5-HINT-INSTRUMENTS` (§5) | **Read D-264** — its status tag and any in-place correction. One targeted read converts the entry to `DOCUMENTATION_ONLY`. |
| **D-288 versus D-317 closure** | `D288-D317-CLOSURE` (§5) | **Read both bodies** (D-288 and D-317 plus its addendum) and determine whether the named product defect is closed. Do not let "D-288 resolved" retire its three other live findings. |
| **ARCH-34's tfvars-staleness half** | `ARCH-34-REVISION-DRIFT` (§4) | **Method-bounded: unreadable by policy.** `terraform.tfvars` is gitignored and was deliberately not read, and with `adopt_deployed_image = true` pin staleness is invisible from the control plane. Closable only by the user or a policy change. Record as a standing hazard: a gitignored tfvars file means the tracked tree does not determine the plan. |
| **DRIFT-49's model roster** | `DRIFT-49-MODEL-ROSTER` (§5) | **Check `DECISIONS.md` and git history for the intended roster**; if that does not settle it, ask the user — the operative `.env` is forbidden to read, so the user is the only remaining evidence source. The `claude-sonnet-5` placeholder defaults are fixable without any decision and should not wait. |

Four are entry-level `UNKNOWN`; ARCH-34's is a named half inside an `OBSERVATION_ONLY` entry, recorded here
so it is not lost. **No other UNKNOWN was converted**: every disposition change from an extractor's proposal
is an adjudicated override recorded in the entry's Justification field.

### §12.3 Queue cross-reference — the twelve USER_DECISION_QUEUE ids

| Queue id | Question, in one line | Register entry or entries | Blocks current work? |
|---|---|---|---|
| **UD-1** | Deploy the 10 undeployed commits to staging, and when | `LB-05-DEPLOY-GAP` (§4); sub-question in `C6-UNATTENDED` (§7); consequences in `RD-01` (§3), `DB-CONTENT-VERIFY` (§7), `LB-08-CORROBORATIONS` (§10) | **yes, partially** — no live evidence for B4 without it |
| **UD-2** | Paid-measurement and spend authorization bundle, plus the read-only database session | `SPEND-AUTHORIZATION` (§2); riders in `DB-CONTENT-VERIFY` (§7), `G2-LOCATOR-PURGE` (§1), `WORK-35-LEDGER` (§1); prerequisite `WORK-13-FIXTURES` (§7) | no |
| **UD-3** | Budget and gross-spend posture | `BUDGET-GROSS-SPEND` (§2); inputs `COST-25-ALARM-COUNT` (§2), `NAT-EXISTENCE` (§4); rider `D136-PRICE-TABLE` (§2) | no |
| **UD-4** | RDS staging durability posture | `RDS-POSTURE` (§4); interacts with UD-3 on Multi-AZ | no |
| **UD-5** | Product-KPI alarm floor, plus the R9 tripwire sub-question | `KPI-ALARM-FLOOR` (§3); related `ARCH-17-COMMIT-SEAM` (§5), `RISK-R2.2-ACCEPTED-RISK-HOMES` (§9) | no |
| **UD-6** | Alerting endpoint ownership | `ALERT-ENDPOINT` (§3); present together with `RD-01` (§3) | no |
| **UD-7** | Retention enforcement and privacy-notice cluster | `RETENTION-CLUSTER` (§1); adjacent `WORK-23-RETENTION-JOB-GATING` (§4), `WORK-35-LEDGER` (§1), `SEC-13-PURGE` (§1) | no |
| **UD-8** | Org communications, including the unsent production security report | `ORG-COMMS` (§8); riders `ARCH-35-ORG-TIME` (§8), `INT-29-FAQ` (§8); related `COMMITTED-ORG-DRAFTS` (§8) | no |
| **UD-9** | Minors-safety policy set | `REQ-32-SAFETY` (§1) | no |
| **UD-10** | First-visit disclosures and the legal track | `DISCLOSURES-LEGAL` (§1); coupled guard `REQ-27-FROZENSET` (§1); scheduled work `FIRST-VISIT-REVERIFY` (§1) | no (the S45 build stays frozen; the decisions are not) |
| **UD-11** | LangSmith account retention — a console read and a privacy judgement | `LANGSMITH-RETENTION` (§1, disposition `BLOCKED`); pair with `LANGSMITH-INGEST` (§3) | no |
| **UD-12** | One-line confirmations bundle (six sub-items) | (a) `DIFFICULTY-TIERS-CONFLICT` (§5) · (b) `D141-TRIM` (§5) · (c) `PROSE-QUALITY` (§5) · (d) `DRIFT-66-NL2SQL` (§1) · (e) `REQ-39-ESTIMATED-LEVEL` (§5) · (f) `COMMITTED-ORG-DRAFTS` (§8) | no |

**Excluded from the queue, with their register homes** (the queue document carries the reasons in full):
E7's seven NOT-GENUINE verdicts → `D310-ROTATION`, `VIDEO-COVERAGE-PARK`, `D152-FREEZE`,
`WORK-04-ANSWER-CACHE`, `WORK-01-SCOPE-GUARD`, `SPEND-AUTHORIZATION` (the depth-spend arm), `WORK-35-LEDGER`;
`R8-READ-SCOPE` (parked, reopen unmet — **re-present at integration start**); `STATUS-TAG-CONVENTION`
(decided within the canonical-document proposal); `ARCH-21-SCHEMA-SPLIT` (deferred to production design —
**extract before archive**); the 150-concurrent org ask → `INT-10-PEAK-CONCURRENCY` (withdrawn and parked,
revisit at integration per D-153 §3); `SNS-CONFIRMATION` and `NAT-EXISTENCE` (resolved live); and the
editorial banner and wording choices → `RISK-GROUP-FREEZE`, `AUDIT-ID-NAMESPACE`,
`RISK-GROUP-ARCH-AUTHORITY` (DRIFT-98).

### §12.4 Where the work sits

| Owner type | Entries (primary owner) |
|---|---|
| documentation | 61 |
| engineering | 37 (including one shared engineering/documentation entry, `TEST-05-DESCRIPTIVE-REREAD`) |
| none (closed, observed, or owned elsewhere) | 33 |
| user | 32 (including `D310-RESIDUALS`, whose first item is a user *action* rather than a decision) |
| external-org | 3 (`ARCH-35-ORG-TIME`, `INT-29-FAQ`, `RD-12-INGRESS`) |
| **Total** | **166** |

Owner type is the *primary* owner; many entries name a secondary owner for a residual (a documentation tail
on an engineering fix, or an engineering follow-through on a user decision), and those secondary owners are
stated in each entry's Remaining action field rather than counted here.

---

*End of register. Companion: [USER_DECISION_QUEUE.md](USER_DECISION_QUEUE.md).*
