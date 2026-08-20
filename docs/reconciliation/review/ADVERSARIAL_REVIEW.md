# ADVERSARIAL_REVIEW.md — Phase 6 independent adversarial review of the Phase-5 canonical documentation proposal

**Status:** REVIEW COMPLETE, 2026-08-20. Read-only — no proposal file, project document, or source file
was modified by this review. Repo HEAD at review: `344f016`.

**Reviewed:** `proposal/PROJECT_STATE.md` (394), `proposal/DOCUMENT_MODEL.md` (1,268),
`proposal/MIGRATION_MANIFEST.md` (1,712), `proposal/AUTHORITY_MODEL.md` (452) — all four read in full
by the adjudicating reviewer — audited against the 15 reconciliation artifacts, the original project
documents (`ROADMAP.md`, `PROGRESS.md`, `OPEN_DECISIONS.md`, `FINAL_ARCHITECTURE.md`,
`S42_ORG_ASKS.md`, `docs/plans/*`, `INCIDENT_RESPONSE.md`, `SPEC.md`, `DECISIONS.md`,
`CLAUDE.md`, `.gitignore`), and, where a claim was checkable in code, the code at HEAD.

**Method:** eight independent worker readers performed mechanical source-vs-destination substance
comparison (register coverage; user-decision queue; deployed/live evidence; repository drift + local
findings; archival-hazard source reads; migration mechanics; safety invariants + authority stress
tests; PROJECT_STATE quality). The adjudicating reviewer re-read primary evidence directly for every
CRITICAL and HIGH finding before finalizing it (verification notes inline per finding). Severities
were adjudicated centrally, not taken from workers.

---

## 0. Verdict and required report

### FINAL VERDICT: **PASS_WITH_REQUIRED_CORRECTIONS**

The information architecture is sound: the five-document active surface is justified, the six-layer
authority model is the right shape, the reference/archive tiering is correct, and the 166-entry
routing is complete and disposition-faithful (verified 166/166, zero missing keys, zero disposition
mismatches). The proposal does **not** need material redesign. But it cannot be executed as written:
two CRITICAL findings make the migration structurally impossible or mis-specified against its
sources, and seventeen HIGH findings would — if executed as written — lose named obligations,
distort open items, license silent answering of user decisions, or promote a factually wrong
document onto the permanent reference path.

| # | Required report item | Answer |
|---|---|---|
| 1 | CRITICAL count | **2** (RF-01, RF-02) |
| 2 | HIGH count | **17** (RF-03 … RF-19) |
| 3 | MEDIUM count | **37** (RF-20 … RF-56) |
| 4 | LOW count | **8** grouped findings covering 44 instances (RF-57 … RF-64) |
| 5 | Migration-blocking findings | **47**: all 19 CRITICAL/HIGH plus 28 MEDIUM (each marked "Blocks: YES" with the step it blocks) |
| 6 | Was any Phase-4 item lost? | **No register entry disappears** — all 166 route, all reopen conditions survive (28/28 deferred+parked plus 6 blocked compared field-by-field). However, **seven named residual obligations would be dropped at execution as specified** (RF-20; RF-24's two placements; RF-25's reading rule; RF-33's re-presentation duty; RF-57c's stated-once sentence; RF-60c's owed acknowledgement); the corrections restore them with no loss. |
| 7 | Was any user decision silently answered? | **Not in substance** — no proposal sentence answers a UD, and the freeze/UNKNOWN/phantom rules all hold (see Cleared C-01…C-05). But **three structural channels would permit silent answering** and must close before migration: answer-shaped default actions that §5's header authorizes an agent to apply (RF-03); §4.2's missing both-sides-are-user-decisions carve-out (RF-51); and PROJECT_STATE §10 closing the PROGRESS-successor design question the manifest flags as open (RF-07). |
| 8 | Is PROJECT_STATE appropriately scoped? | **Broadly yes, with ~100 of 394 lines violating its own rules.** The factual layer is excellent (all 65 keys resolve, 61/61 rows in the disposition-correct section, every count right, all links correctly pathed). §9's 17-line resolved-item narrative and §4.3's 51 lines of register-duplicated mechanism should move out (RF-45, RF-47) — measured trim to ~290 lines with zero unique content lost. The refresh protocol has real gaps (RF-13 blocking; RF-47). |
| 9 | Is the five-document active surface justified? | **Yes.** TRACEABILITY's distinct durable responsibility is confirmed — it is read *and written* whenever launch scope is touched, its "unverified counts as not traced" method rule merges into no other file, and demoting it to reference would put the §2.6 criterion-1 instrument off the update path. No document proposed for reference/archive must remain active (INCIDENT_RESPONSE's trigger-not-session reasoning was tested and holds; the two live registers correctly go to reference, not archive, and not active). |
| 10 | Verdict | **PASS_WITH_REQUIRED_CORRECTIONS** |

**Phase-4-inherited errors surfaced by this review** (upstream of the proposal, reported for
correction in the register/queue, not counted against the proposal's architecture): the SEC-13
"no test / would break no CI" coverage claim is false at HEAD (RF-10); `CLAIM_LEDGER.md` has no
"2 commits ahead" WORK-05 cell for W-13 to fix (RF-63g); `USER_DECISION_QUEUE.md` carries a second
and third bad register key beyond the one step 9c fixes (RF-32); the queue file ends in stray
tool-call markup (RF-60d).

---

## 1. CRITICAL findings

### RF-01 — [CRITICAL] The promotion step (13) contradicts five HARD ordering statements; every archive banner written at step 7 points at a file that does not exist until step 13, and four earlier steps write into it

- **Category:** migration-mechanics / impossible-ordering
- **Proposal location:** `MIGRATION_MANIFEST.md` §3 — Phase 2 step 7 (banners, :1092–:1118), Phase 3
  step 9 (moves), step 13 (:1171, "Promote the proposal documents"); banner template :687–:689
  (`Current state: docs/PROJECT_STATE.md`); steps 2 (:1045), 10 (:1154), W-22 (:1247), W-29 (:1254)
  all write into `PROJECT_STATE` before step 13.
- **Source evidence (all verified verbatim by the adjudicating reviewer):**
  `DOCUMENT_MODEL.md` §13 O1 (HARD): promoted "**before any file moves** … every archive banner names
  `docs/PROJECT_STATE.md`"; §10.1: "promoted **first**. Every archive banner points at
  `docs/PROJECT_STATE.md`, so it must exist before the first banner is written"; §10.2: "promoted at
  migration **start**"; §8.1: "archive **after** `PROJECT_STATE.md` exists (a banner may not point at
  a file that does not exist)"; §13 general rule: "a banner may never point at a file that does not
  yet exist."
- **What would go wrong:** executed literally, 20 archive banners dangle for the entire migration
  window (steps 7–12) and steps 2/10/11 edit a nonexistent file — reproducing R7.3/R9.1, the defect
  class the banners exist to fix. Executed "charitably" (edit the draft in place, promote last), five
  HARD constraint statements are false as written and the executor is improvising the ordering the
  manifest was supposed to fix.
- **Why it matters:** O1 is the migration's own first HARD constraint, and the HC list contains no
  hard constraint on promotion order at all (HC-7 names steps 8 and 12 as step 14's prerequisites but
  not step 13). The manifest and the model disagree about the single most structural step.
- **Exact correction required:** split step 13 into a new **step 0** (create the full target
  directory skeleton; `git mv` the two proposal documents to `docs/PROJECT_STATE.md` and
  `docs/reference/AUTHORITY_MODEL.md` before step 1) and a residual **13b** (summarize
  AUTHORITY_MODEL's precedence table in PROJECT_STATE's doc map). Add
  `HC-8: promotion precedes step 1; no banner is written until docs/PROJECT_STATE.md exists at its
  final path.` Retitle Phase 1 accordingly. (This also absorbs RF-63b's directory-creation defect.)
- **Blocks migration:** **YES — nothing may execute until this is resolved.**

### RF-02 — [CRITICAL] The mandated S43–S51 "Done when" extraction targets content that does not exist in ROADMAP, and the content that IS there (five embedded constraints) is never named as an extraction target

- **Category:** loss / mis-specified mandatory extraction
- **Proposal location:** `DOCUMENT_MODEL.md` §6.2 and O5 (HARD); `MIGRATION_MANIFEST.md` §2.C.4,
  §2.F.1, step 3 (:1049–:1054), step-6 gate row (:1080), §5.10 row 2 — four separate assertions that
  S43–S51's "'Done when' acceptance criteria" are "ROADMAP's unique normative asset" existing
  "nowhere else."
- **Source evidence (re-verified by the adjudicating reviewer):**
  `grep -n "Done when" docs/ROADMAP.md` filtered to lines 525–1769 returns **zero** hits — every one
  of the 95 "Done when" occurrences belongs to S0–S41 or the Milestone 10–15 work units.
  `ROADMAP.md:1438` is a single heading over a six-item bullet list (S42–S47);
  `:1514` is seven lines of semicolon prose covering S48–S51. What that range actually holds, per
  the worker's full read: five embedded constraints — the D-153 §5 rule that production `role` must
  never by itself grant an elevated role (:1479–1486); the six structural dev-fake mismatches
  (:1469–1476); the two-source `BranchInfo` merge fact; the D-153 §4 no-Sunday-evening/00:00–01:00
  session-window assertion; and D-167's `/dev/token` deletion cascade including the `sub`-assertion
  every per-student cost ceiling depends on.
- **What would go wrong:** step 3 cannot be executed as specified. The step-6 gate row ("S43–S51
  specs and 'Done when' criteria — landed by step 3") can never be truthfully checked off, so either
  the migration halts on its own gate, or — the worse and likelier failure — an executor who trusts
  the proposal's four-fold claim **synthesizes acceptance criteria for D-152-frozen work**, producing
  exactly the "clean-looking build spec for frozen work" that `DOCUMENT_MODEL.md` §6.2 itself calls
  "worse than the status quo." Meanwhile the five real embedded constraints, being unnamed, can be
  dropped in a loose extraction.
- **Why it matters:** this is a HARD-constraint extraction whose object is fictional, in the D-152
  domain where fabricated normative content is most dangerous, and where one of the unnamed real
  constraints is a security rule (the role-elevation gate) and another underpins per-student cost
  ceilings.
- **Exact correction required:** rewrite §6.2, §2.C.4, §2.F.1, step 3, the step-6 gate row and §5.10
  row 2 to name the actual extraction set: "the S42–S47 scope bullets and the S48–S51 rollout
  paragraph, with their five embedded constraints (D-153 §5 role gate; the six dev-fake mismatches;
  the `BranchInfo` two-source merge; the D-153 §4 session-window assertion; D-167's `/dev/token`
  cascade incl. the `sub` assertion)." Delete every "Done when" claim for S43–S51 and add: *"no
  acceptance criteria exist for S43–S51; do not author them during extraction."*
- **Blocks migration:** **YES — step 3 and everything downstream of O5.**

---

## 2. HIGH findings

### RF-03 — [HIGH] Six of twelve "default safe actions" are answer-shaped, and §5's header authorizes an agent to apply them

- **Category:** decision-preservation / silent-answer channel
- **Proposal location:** `proposal/PROJECT_STATE.md:169` ("Where a default safe action exists, an
  agent may apply it and say so"), rows UD-4 (:178), UD-5 (:179), UD-6 (:180), UD-8 (:182),
  UD-9 (:183), UD-12(a) (:186).
- **Source evidence:** `USER_DECISION_QUEUE.md:298-299, :368, :436, :615-617, :671-674, :834-836` —
  the queue options these defaults compress are worded as rulings ("Record the current posture as
  **the deliberate staging answer**", "Record the disabled state as **the answer to P1-10** … and
  close the open item", "record … as an accepted risk", "Confirm D-341 governs"). Verified against
  the adjudicator's own read of PROJECT_STATE §5.
- **What would go wrong:** an agent legitimately reads :169 + :183 and appends a dated accepted-risk
  DECISIONS entry for the one-of-two-surfaces child-safety screen — laundering an unanswered
  safeguarding question into the system of record. UD-4 (durability), UD-5 (observability), UD-6,
  UD-8 and UD-12(a) have the same shape. This directly contradicts the same section's "do not convert
  one into a D-xxx without the user", `AUTHORITY_MODEL` §4.6, and manifest rule 4/HC-0.
- **Why it matters:** this is the exact failure §4.6 exists to prevent, installed in the file every
  session reads first, with an explicit permission sentence.
- **Exact correction required:** split the column into "Safe holding action (agent may apply)" —
  UD-1, UD-2, UD-3, UD-7, UD-10, UD-11 — and "Answer-shaped — user only" — UD-4, UD-5, UD-6, UD-8,
  UD-9, UD-12(a) — rewording each of the latter to a non-committal hold (e.g. UD-9: "Change nothing;
  add a dated note that the chat surface is unscreened — do not record it as an accepted risk without
  the user"; UD-12(a): "Continue following D-341, annotate D-322 §7 as contradicted-pending-
  confirmation, record no ruling").
- **Blocks migration:** **YES — before PROJECT_STATE promotion.**

### RF-04 — [HIGH] UD-7's D-333 safety precondition is absent from PROJECT_STATE while Appendix A claims it is "carried verbatim"

- **Category:** loss / safety (minors' data deletion)
- **Proposal location:** `PROJECT_STATE.md:181` (UD-7 row); `MIGRATION_MANIFEST.md:1472`
  (Appendix A row 9: "D-333 precondition carried verbatim").
- **Source evidence:** `USER_DECISION_QUEUE.md:470-472` — "**Precondition to carry verbatim.**
  D-333 records the user's own instruction: *'Before deleting any eligible checkpoint, run long-term
  memory consolidation first.'* … It is the safety precondition, not a nicety." Adjudicator-verified:
  `grep -c "consolidation first\|D-333" proposal/PROJECT_STATE.md` → **0**.
- **What would go wrong:** the entry point no longer states the ordering that must hold before
  `CHECKPOINT_RETENTION_APPLY=true` is ever flipped — on a job whose failure mode is silently
  deleting a minor's learning history — while the manifest's validation asserts it was carried.
- **Why it matters:** a carried-verbatim claim that is false is worse than an honest omission: step
  15's checker reads Appendix A, sees "carried verbatim," and signs off.
- **Exact correction required:** append the verbatim D-333 sentence and the verify-before-any-
  dry-run-flip instruction to UD-7's default cell (or delete the "(carried verbatim)" claim — but the
  right fix is to carry it; it also belongs in the `WORK-23-RETENTION-JOB-GATING` reopen row).
- **Blocks migration:** **YES — before PROJECT_STATE promotion.**

### RF-05 — [HIGH] §7-R9's expiry condition has no row in PROJECT_STATE §6.4, though four proposal locations name §6.4 as its single home

- **Category:** loss / accepted-risk expiry (R2.2 reproduced)
- **Proposal location:** `MIGRATION_MANIFEST.md:1154` (step 10 single-homing table: "§7-R8 / §7-R9
  expiry conditions | `PROJECT_STATE` §6.4"), :1325-1326 (§5.4), :452, :474; W-22 (:1247) reduces
  ARCHITECTURE's restatements to pointers at that home.
- **Source evidence:** PROJECT_STATE §6.4 (adjudicator's own read): 13 rows; `R8-READ-SCOPE` is
  present, **no R9 row exists**. R9's expiry survives only as a parenthetical inside §4.1's
  `ARCH-17-COMMIT-SEAM` cell ("movement voids the §7-R9 acceptance"). UD-5's sub-question points at
  the R9 tripwire ("alarmed nowhere", `USER_DECISION_QUEUE.md:378-384`).
- **What would go wrong:** after migration the §7-R9 acceptance has no home; W-22 executes and the
  pointers point at nothing; when the repair counter moves, nothing in the entry point says the
  acceptance is void. This is the R2.2 failure (expiry lives only in the unread file) reproduced by
  the migration that exists to fix it.
- **Exact correction required:** add a §6.4 row (e.g. `ARCH-17-R9-ACCEPTANCE` | §7-R9
  checkpoint-repair acceptance; tripwire charted and alarmed nowhere | any movement in
  `learning_checkpoint_repairs_total` voids the acceptance — the alarm-or-cadence question is UD-5's
  sub-question), and make §4.1's parenthetical a pointer to it.
- **Blocks migration:** **YES — before step 10 / W-22.**

### RF-06 — [HIGH] The UD table has neither the register-key nor the link column that three manifest statements and the step-15 validation assume; four UD carrying keys appear nowhere in PROJECT_STATE

- **Category:** migration-mechanics / broken validation + discoverability
- **Proposal location:** `PROJECT_STATE.md:173` (columns are `UD | Question | Blocks? | Default safe
  action` — adjudicator-verified); vs `MIGRATION_MANIFEST.md:929` and :1146 ("keys the UD table by
  register key"), :1298 (five-column table incl. "link"), :1307-1308 ("the table's register-key
  column resolves for all sixteen carrying entries").
- **Source evidence:** grep over the draft: `KPI-ALARM-FLOOR`, `RETENTION-CLUSTER`, `REQ-32-SAFETY`,
  `DISCLOSURES-LEGAL` — **zero occurrences anywhere in the file**. Only UD-12's six keys appear.
- **What would go wrong:** §5.2's step-15 check is unrunnable (no column to check); step 9c's stated
  rationale rests on a nonexistent column (a reviewer who checks it will find it false and may
  discard a correction that is right); the minors-retention (UD-7) and legal-disclosures (UD-10)
  questions cannot be joined to their register evidence from the entry point.
- **Exact correction required:** add a `Register key` column (UD-1 `LB-05-DEPLOY-GAP`, UD-2
  `SPEND-AUTHORIZATION`, UD-3 `BUDGET-GROSS-SPEND`, UD-4 `RDS-POSTURE`, UD-5 `KPI-ALARM-FLOOR`, UD-6
  `ALERT-ENDPOINT`, UD-7 `RETENTION-CLUSTER`, UD-8 `ORG-COMMS`, UD-9 `REQ-32-SAFETY`, UD-10
  `DISCLOSURES-LEGAL`, UD-11 `LANGSMITH-RETENTION`, UD-12 its six) — or rewrite all three manifest
  statements to the true mechanism. Adding the column is correct: §10's own vocabulary rule requires
  register keys.
- **Blocks migration:** **YES — before promotion and step 15.**

### RF-07 — [HIGH] PROJECT_STATE §10 silently closes the PROGRESS-successor design question that MIGRATION_MANIFEST §2.F.2 flags as "an open design question for the user"

- **Category:** decision-preservation / design question silently answered
- **Proposal location:** `MIGRATION_MANIFEST.md:746-750` ("**Successor question (flagged, not
  decided).** … This interacts with the `/end-session` skill's conventions and is an open design
  question for the user, not something this manifest settles") vs `PROJECT_STATE.md:344-350`
  ("**No chronology, ever.** … Narration belongs in commit messages") — both verified in the
  adjudicator's own reads.
- **What would go wrong:** promoting PROJECT_STATE (step 13) publishes the git-commits-only option as
  a standing rule while the manifest still says the user hasn't chosen it; the `docs/log/` journal
  alternative disappears; and no step touches the `/end-session` skill the rule now depends on.
- **Why it matters:** this is one of the four flagged proposal-design questions the review was
  required to verify stays open — and it is the one the proposal itself closes.
- **Exact correction required:** mark `PROJECT_STATE.md` §10's narration bullets *provisional pending
  the §2.F.2 narration decision* (naming the `docs/log/` alternative), and add a step 15b:
  "reconcile the `/end-session` skill with §10, or record that it is deliberately unchanged."
- **Blocks migration:** **YES — before promotion.**

### RF-08 — [HIGH] The branding extraction orders a superseded, WCAG-failing color preserved "verbatim" into ARCHITECTURE, contradicting D-067 and the as-built tokens

- **Category:** semantic-distortion / stale-value promotion into the normative owner
- **Proposal location:** `DOCUMENT_MODEL.md` §6.3; `MIGRATION_MANIFEST.md` §2.F.7 ("Preserve
  verbatim: BD3's exact contrast ratios"), step 4.
- **Source evidence (adjudicator-verified by grep):** the plan's BD3 carries pink `#d13a80`
  (`2026-07-19-branding-plan.md:64, :115`); `DECISIONS.md:1479-1487` (D-067) records that value as
  "**4.16:1, a real fail**" on `--bg` and ships the corrected `#c22f73`; as-built
  `packages/ui-brand/tokens.css:37` is `--pink-interactive: #c22f73`. Also: the stated justification
  ("otherwise effectively deleted") is false — D-067 is titled "do not 'fix' back" and lives in
  KEEP_ACTIVE `DECISIONS.md`.
- **What would go wrong:** step 4 imports a value that fails the project's own `check_contrast.py`
  into the file being made the single brand-data owner — the migration minting the exact
  stale-number-in-active-document defect it exists to remove, against a decision in the file it
  designates as decision authority.
- **Exact correction required:** source step 4's extraction from **D-067 and
  `packages/ui-brand/tokens.css`** (`#387e40` 4.97:1; `#c22f73` 4.88:1 on `--bg` / 5.32:1 on
  `--panel-bg`), not from the plan; state in the archived plan's header that its `#d13a80` is
  superseded by D-067; downgrade §6.3's "effectively deleted" justification to "consolidating brand
  data; the rule itself is already held by D-067."
- **Blocks migration:** **YES — step 4.**

### RF-09 — [HIGH] `S42_ORG_ASKS.md` is gitignored and untracked; the mandated rename silently un-ignores an outbound customer draft that a recorded decision deliberately kept out of version control

- **Category:** migration-mechanics / publication-boundary reversal
- **Proposal location:** `DOCUMENT_MODEL.md` §8.4/§15.3; `MIGRATION_MANIFEST.md` §2.F.5, step 7a,
  step 9 — none mentions `.gitignore`. Compounding: §2.C.1 (:470-472) lists INTEGRATION_PLAN's
  "outbound drafts are gitignored and not committed" claim as stale ("three committed drafts exist")
  while it is still exactly true of this file.
- **Source evidence (adjudicator-verified):** `git check-ignore -v docs/S42_ORG_ASKS.md` →
  `.gitignore:67`; `git ls-files docs/S42_ORG_ASKS.md` → empty. `PROGRESS.md:10137-10139`:
  "deliberately never committed."
- **What would go wrong:** rename to `docs/archive/2026-07-24-org-asks-drafts.md` no longer matches
  `.gitignore:67`; the next `git add -A` commits an outbound Korean/English customer-communication
  draft. A deliberate publication boundary is reversed as a side effect of the file the proposal
  itself calls "the corpus's purest wrong-action risk," and the evidence for UD-12(f)'s open tension
  is destroyed by the migration that promised to preserve it.
- **Exact correction required:** add a step-9 sub-step: update `.gitignore:67` to the new archive
  path (or record, with the user, an explicit decision to begin tracking it — that is UD-12(f)
  territory and must not be decided by a rename). Amend §2.C.1's stale-list entry: the rule is
  *partially* honoured (this file), not falsified.
- **Blocks migration:** **YES — step 7a/9.**

### RF-10 — [HIGH] PROJECT_STATE §4.3's "Zero tests touch the function" (SEC-13) is false at HEAD; only the cancel/exception paths are untested

- **Category:** semantic-distortion / factual error in the act-on-alone section (Phase-4 inherited)
- **Proposal location:** `PROJECT_STATE.md:135` (§4.3 SEC-13 paragraph); inherited from
  `FINAL_OPEN_WORK_REGISTER.md` `SEC-13-PURGE` and `LOCAL_EXECUTION_FINDINGS.md:519-536` (F-11),
  whose grep was for the **symbol**, not the effect.
- **Source evidence (adjudicator-verified):** `apps/chat-api/tests/test_chat_endpoints.py:503-506`
  asserts `resume_rows == []` after the locator turn (with a vacuity control), and `:560-562` asserts
  no `__resume__` row survives, parameterized. Deleting the purge call site
  (`routers/sessions.py:914`) would fail both. The mechanism description itself (single trigger,
  cancel returns before purge, exception skips it, no `finally`) was code-verified and is correct.
- **What would go wrong:** the sentence an agent acts on from §4.3 alone materially misstates the
  risk (the success path *is* effect-asserted; the gap is cancel/exception only), invites duplicate
  test authoring, and is the corpus's own "a green suite proves little" discipline applied in
  reverse — a symbol-grep promoted to a coverage conclusion through three phases.
- **Exact correction required:** replace with: "No test names `purge_resume_writes`, and **no test
  covers the cancel or exception path**. The success path's effect is asserted, with a vacuity
  control, at `test_chat_endpoints.py` (locator-turn and parameterized `__resume__` assertions). The
  gap is the cancel/exception paths only." Also correct the register entry and
  `LOCAL_EXECUTION_FINDINGS.md` F-11's "would break no test" clause (upstream correction). The
  recommended fix order (cancel-path test first, then `finally`) is unaffected.
- **Blocks migration:** **YES — before promotion (and an upstream register correction).**

### RF-11 — [HIGH] The child-safety screen's thinness (`REQ-32-SAFETY`) is invisible everywhere except a UD-9 line whose default is "change nothing"

- **Category:** safety-minors / under-promotion
- **Proposal location:** `PROJECT_STATE.md:183` (UD-9 row) — no §8 headline, no §4 row;
  `MIGRATION_MANIFEST.md` Appendix A row 5 routes the whole entry to §5.
- **Source evidence:** `LOCAL_EXECUTION_FINDINGS.md:498-506` (F-10): the self-harm short-circuit's
  "entire executable guard is a single test function against a fixed 10-keyword screen on
  learning-api only"; `REPOSITORY_DRIFT_REGISTER.md:173`: **no equivalent screen anywhere in
  `apps/chat-api`**, no policy artifact, no escalation destination beyond a boolean. The register's
  remaining action names three engineering deliverables (chat-api coverage, a real escalation
  destination, pinning tests); queue option D marks chat-api coverage "independent of the Guardrails
  question."
- **What would go wrong:** if the user takes the stated default, the only child-safety path on a
  minors-primary platform closes as an accepted risk — one keyword screen, one of two surfaces, one
  test, no escalation — and nothing in the five active documents ever surfaces it again. §8's
  headline risks include a $20 budget but not this.
- **Exact correction required:** add a §8 headline bullet naming the one-of-two-surfaces /
  one-test / no-escalation facts keyed `REQ-32-SAFETY`/UD-9; add a §4.2 row for the
  Guardrails-independent chat-api screen work (or state in UD-9's default that accepting it leaves
  the three named engineering deliverables unowned). Combine with RF-03's rewording of UD-9's
  default.
- **Blocks migration:** **YES — before promotion.**

### RF-12 — [HIGH] AUTHORITY_MODEL §0 states "40 documentation risks, 16 HIGH"; the true counts are 49 and 18 — and the wrong copy is the one promoted to the permanent reference path

- **Category:** semantic-distortion / summary-vs-table (R8.1) in the surviving file
- **Proposal location:** `AUTHORITY_MODEL.md:16` (adjudicator-verified in own read).
- **Source evidence (adjudicator-verified):** `grep -cE '^### '
  DOCUMENTATION_RISK_REGISTER.md` → **49**; `grep -cE '^### .*HIGH'` → **18**. `DOCUMENT_MODEL.md`
  §1 states the correction explicitly ("49 entries, and 18 HIGH — not 40 and 16") — and DOCUMENT_MODEL
  is the file that archives while AUTHORITY_MODEL is promoted.
- **What would go wrong:** post-migration the corpus's precedence document under-reports HIGH risks
  by two and total risks by nine, in its own motivating sentence, while the correction sits behind an
  archive banner that §15.4 forbids citing as authority. It is a verbatim R8.1 instance in the file
  that promulgates the R8.1 countermeasure.
- **Exact correction required:** edit `AUTHORITY_MODEL.md:16` to "49 documentation risks, 18 of them
  HIGH (counts derived mechanically from DOCUMENTATION_RISK_REGISTER.md's entry headings,
  2026-08-20)."
- **Blocks migration:** **YES — before AUTHORITY_MODEL promotion (one-line fix).**

### RF-13 — [HIGH] The staleness rule cannot fire on the single most likely next event: the UD-1 deploy changes the deployed build without moving HEAD or the date

- **Category:** authority-error / fail-open staleness
- **Proposal location:** `AUTHORITY_MODEL.md` §2.1 staleness rule; `PROJECT_STATE.md:24-26` — both
  triggers are "snapshot &gt;14 days old" or "HEAD moved" (adjudicator-verified in own reads).
- **Source evidence:** `PROJECT_STATE.md:18` (deploy trigger MANUAL), :175 (UD-1 is precisely this
  event). A manual deploy trips neither trigger, yet instantly falsifies everything in §3: the B4
  undeployed list, "the table is absent from staging," "D-421's guard is not protecting staging
  today," LB-08's pre-D-423 status.
- **What would go wrong:** days after the deploy, a session trusting an in-window snapshot reports
  false deployed-state claims — fail-open in exactly the direction §2.9's reciprocal caution forbids,
  with no signal.
- **Exact correction required:** add a third trigger to both §2.1 and PROJECT_STATE §1: "**or the
  deployed image tag no longer matches the snapshot header**," and make §3's undeployed list
  explicitly conditional on `gha-44a12dfc9549`.
- **Blocks migration:** **YES — before promotion (two one-line edits).**

### RF-14 — [HIGH] The INCIDENT_RESPONSE freeze-context edit, executed as written, inverts the runbook's own "don't under-react to a MySQL-adjacent incident" rule

- **Category:** safety-minors-privacy / incident triage
- **Proposal location:** `MIGRATION_MANIFEST.md:300-302` — the new line arrives "so the
  MySQL-adjacent tier **stops reading as a live production attack surface**" (verified in the
  adjudicator's own read of §2.B.1).
- **Source evidence (adjudicator-verified):** `INCIDENT_RESPONSE.md:22-25` — the MySQL-adjacent tier
  is the one that "can actually expose names/emails/relationships … **don't under-react to a MySQL-
  adjacent incident** just because it 'sounds like just a config bug.'" And per project CLAUDE.md,
  `../IntelliChoice-web` — with committed production credentials — is checked out on local disk
  today. D-152 freezes *our integration work*; it does not remove the surface.
- **What would go wrong:** an incident responder — the one reader who meets this document only under
  time pressure — is told the tier is not a live attack surface. A leaked-credential incident
  touching the local checkout is a live, maximum-severity MySQL-adjacent incident under the freeze;
  the edit as worded produces under-triage of the only incident class that can expose minors' PII.
- **Exact correction required:** rewrite the instruction: "D-152 means we take no integration action
  against production; it does **not** mean the MySQL-adjacent tier is not a live exposure surface —
  the committed credentials in the local `../IntelliChoice-web` checkout are one. Triage severity
  unchanged." The words "stops reading as a live production attack surface" must not survive into
  the executed edit.
- **Blocks migration:** **YES — before the W-33/§2.B.1 edit.**

### RF-15 — [HIGH] W-42's rule-1 instruction ("add the four-column exemption"), executed literally, writes a subject-free PII carve-out into the always-loaded CLAUDE.md

- **Category:** safety-privacy / invariant-weakening edit instruction
- **Proposal location:** `MIGRATION_MANIFEST.md:1272` (W-42) and §5.9 row 1 — both frame the fix as
  adding "D-050's four-column exemption" without its limiting principle.
- **Source evidence:** `DECISIONS.md:992-1002` (D-050): the exemption is org-published staff/branch
  contact fields only, two enumerated tables, `ALLOWED_PII_SHAPED_COLUMNS`, "the test still fails
  loudly if a *student-facing* table ever grows one of these column names" — none of which appears in
  the instruction. CLAUDE.md rule 1 has drifted before (said "MongoDB" until D-082/D-111), and
  nothing references CLAUDE.md back (W-30's own observation).
- **What would go wrong:** the executed edit reads "no PII in Postgres, except four allowlisted
  columns" — and a future session adds a student-name column with a matching allowlist entry. The
  top non-negotiable for a minors' platform is weakened by its own clarification.
- **Exact correction required:** replace W-42's clause and §5.9's cell with the required wording
  itself, not a description of it: "No student, parent or guardian PII in Postgres — absolute. Two
  tables (org staff/branch contact) carry the org's own already-public fields under an enumerated
  exemption (D-050, `ALLOWED_PII_SHAPED_COLUMNS`); `test_schema_purity.py` still fails loudly if any
  student-facing table grows one of those column names."
- **Blocks migration:** **YES — before the W-42/step-14 CLAUDE.md edit.**

### RF-16 — [HIGH] Ladder A instructs trusting `accepted` status lines while ~112 of ~120 supersession chains remain un-annotated, and the residual is recorded in no active document

- **Category:** authority-error / stale status metadata preferred over later supersession evidence
- **Proposal location:** `AUTHORITY_MODEL.md` §3.1 (Ladder A), §4.1 ("the newer accepted decision
  wins" — detect clause keys on the status label), §2.3 (states the R6.1 history in the past tense,
  implying it is fixed).
- **Source evidence (adjudicator-verified):** `FINAL_OPEN_WORK_REGISTER.md:4694-4705`
  (`STATUS-TAG-CONVENTION`): "any consumer that reads status tags to determine what is current will
  read **at least eleven** stale `accepted`/`implemented` entries as active" — and the entry is
  explicitly `PROJECT_STATE? no`. Only the eight worst entries are annotated at migration (W-16, by
  deliberate Phase-4 safe default); §4.2(b) carries the check-for-later-entries warning but §3.1 and
  §4.1 do not.
- **What would go wrong:** a session implements a requirement from an entry labelled `accepted` that
  a later entry superseded in body prose — the R6.1 defect surviving into the requirement ladder,
  which is where it does the most damage, with the reader having been told the status-line discipline
  now holds.
- **Exact correction required:** add to §3.1 (as step 2a) and §4.1's Do clause: "A status line of
  `accepted` is not evidence — only 8 of ~120 chains were back-annotated at migration; grep the topic
  for later entries before reasoning from any decision." Add one §8 residual line to PROJECT_STATE
  ("≥11 stale accepted/implemented tags read as active; the full sweep is deliberately not done —
  `STATUS-TAG-CONVENTION`").
- **Blocks migration:** **YES — before AUTHORITY_MODEL promotion.**

### RF-17 — [HIGH] The PROJECT_STATE-vs-register precedence rule exists only in the archived DOCUMENT_MODEL; AUTHORITY_MODEL read literally points the other way

- **Category:** authority-error / missing precedence rule
- **Proposal location:** `AUTHORITY_MODEL.md` §2.1 ("NOT authority for: anything"), §2.6 (a reference
  file is "authority for whatever its own scope says" — and the register's scope *is* open work),
  §4.4 (resolves PROJECT_STATE against primary evidence only); §7's quick-reference has no register
  row.
- **Source evidence:** the correct rule exists at exactly one place, `DOCUMENT_MODEL.md` §9.1: "the
  register is provenance for *why* an item is open, and `PROJECT_STATE` is the authority on *whether*
  it still is" (verified in the adjudicator's own read) — in a file that archives at step 15. The
  manifest's §2.G.1 banner spec carries only the deletion fact, not the precedence half.
- **What would go wrong:** PROJECT_STATE deletes an item on resolution; the register still shows it
  open; a later session — following §2.6 literally — trusts the register row and re-opens closed
  work. The one conflict this new architecture creates by design (delete-on-resolve vs a frozen
  register) is the one its authority model does not cover.
- **Exact correction required:** add §4.7 to AUTHORITY_MODEL ("PROJECT_STATE is authority for
  *whether* open; the register for *why* it was opened. A register row with no PROJECT_STATE row is
  closed-or-stale, not open. The register never triggers work."), add the same sentence to the
  §2.G.1 as-of banner spec, and add a "What is open?" never-trust cell for the register in §7.
- **Blocks migration:** **YES — before AUTHORITY_MODEL promotion.**

### RF-18 — [HIGH] §4's batch taxonomy and the per-row step assignments are two incompatible schedules; executing step 11 as instructed re-runs step-7 banner work and violates O12, O13, O16 and O17

- **Category:** migration-mechanics / conflicting schedules
- **Proposal location:** `MIGRATION_MANIFEST.md:1161` (step 11: "Execute the 44-row … worklist in the
  stated batch order") and :1204 (batch list) vs ~18 rows whose own destination cells carry different
  step numbers (W-20 :1245 "step 7a/7c … step 3 … step 14"; W-36 :1266 "step 7c"; W-21, W-32, W-34,
  W-29, W-28, W-19, W-17, W-26, W-23, W-27, W-30, W-31, W-05, W-22, W-12, W-39) — only W-07 and W-30
  carry explicit disclaimers.
- **Sub-violations verified against the O-table:** **O13** (U7 completion banner required before the
  step-9 move, scheduled at step 11 via W-08); **O17 both halves** (W-43 in batch F edits
  TRACEABILITY's T-02 before W-35's S45 disambiguation in batch H; W-11/W-14 precede W-39's citation
  convention within batch I); **O12** (the D-093→D-137 hazard grep lives in W-18, batch G, after
  batches A/C/E have already edited `INCIDENT_RESPONSE.md` — and HC-6 forces the violation);
  **O16** (batch G runs W-16 before W-25, which owns the ID index W-16 depends on).
- **What would go wrong:** an executor obeying step 11 re-writes freeze banners already placed,
  re-stamps executed-as headers, attempts extractions after sources are archived (the HC-1 failure),
  rewrites the launch-evidence instrument three times before its citation convention exists, and
  checks the one "live operational hazard" fourth instead of first.
- **Exact correction required:** add a `step` column to all three §4 tables carrying one
  authoritative step per row-half; restate step 11 as "execute the rows whose step column reads 11";
  move W-08 to a pre-move step (with the O14 items); promote W-35 ahead of W-43 and W-39 to the head
  of batch I; hoist the D-093→D-137 grep to a read-only step 0b; reorder batch G to W-25, W-16, W-18.
- **Blocks migration:** **YES — steps 7–11.**

### RF-19 — [HIGH] No git-provenance instruction exists anywhere: no `git mv`, no commit granularity, no separation of banner-edit from move, no rollback path

- **Category:** migration-mechanics / Git provenance loss
- **Proposal location:** `MIGRATION_MANIFEST.md` §0.2 (nine hard rules — none about version control),
  step 9 ("move every file"); the sole acknowledgement is `DOCUMENT_MODEL.md:990-993` ("`git log
  --follow` across a bulk move plus two renames is a poor substitute for a written mapping") — framed
  as a reason the manifest matters, not as an instruction.
- **What would go wrong:** a compliant executor uses plain `mv`; 41 files move, 22 with prepended
  banners (which alone can push rename-similarity below git's detection threshold on small files),
  2 renamed. `git log --follow` then returns one commit for the renamed architecture projection, and
  the *only* provenance for 41 files becomes a prose table inside an archived file — the exact
  substitution DOCUMENT_MODEL calls poor. There is also no abort path after step 9 (step 6's "stop"
  has no unwind procedure).
- **Exact correction required:** add hard rule 10 to §0.2: every move is `git mv`; banner insertion
  is a **separate commit** from the move; one commit per phase with the step range in the message;
  verify `git log --follow` on both renamed files plus samples before the next phase; commit the
  clean tree before step 9 so the migration is revertable.
- **Blocks migration:** **YES — before step 7.**

---

## 3. MEDIUM findings

Format per finding: category · proposal location · source evidence · defect → consequence ·
correction · blocks.

### RF-20 — [MEDIUM] COST-25's X-Ray trace-storage residual is dropped from W-01
Loss · `MIGRATION_MANIFEST.md` W-01 (:1221), Appendix A row 24 · register
`FINAL_OPEN_WORK_REGISTER.md:1212-1215`: the remaining action is alarm billing **and** the X-Ray
trace-storage line, which "deserves its own sentence rather than being folded into the alarm note";
"X-Ray" appears nowhere in the manifest · Executing W-01 closes COST-25's residual without the only
*new* cost line (free tier 91% used, forecast 148,599 / 100,000) — inverting the register's explicit
instruction by omission · Correction: extend W-01's absorption clause to carry both lines, the X-Ray
one as its own sentence; update row 24's destination cell · **Blocks: YES — W-01/step 11.**

### RF-21 — [MEDIUM] "Six entries carry a residual" names seven, and the wrong count is propagated into the step-15 validation gate
Migration-mechanics · `MIGRATION_MANIFEST.md:95-102` and §5.1 Check (:1289/…"the six mixed entries")
· the §1 list enumerates seven keys; independently verified against the register's compound
disposition fields — exactly seven entries carry a cross-class residual (three workers converged) ·
A step-15 validator counting six stops one short and cannot know which was meant to be excluded ·
Correction: "Seven" in both places; better, number them M1–M7 so the count derives from the list ·
**Blocks: YES — step 15.**

### RF-22 — [MEDIUM] DRIFT-58's paid cross-spec residual is routed to "PS §6.3", where no row exists
Loss/routing · `MIGRATION_MANIFEST.md:99` and Appendix A row 99 (:1592) · PROJECT_STATE §6.3 has
exactly the 15 DEFERRED keys; `DRIFT-58` appears nowhere in the file; the register forbids
flattening ("LB-04 refuted the claim, not the seventeen-spec scope") · The unrun seventeen-spec
combination becomes a parenthetical dependency on `WORK-13-FIXTURES` instead of a deferred item with
a reopen condition · Correction: add a 16th §6.3 row for the residual (reopen: UD-2 authorises the
paid re-run) or amend §1/row 99 to say it is carried inside `WORK-13-FIXTURES` · **Blocks: YES —
promotion.**

### RF-23 — [MEDIUM] WORK-43's count fix is routed to W-13 while the register folds it into W-18, with no override note
Routing override · Appendix A row 164, W-13 (:1233) · register :6647: "folded into
`DOC-DECISION-LOG-CORRECTIONS`" (= W-18); W-18's row does not mention it; the register also says the
true count is "at least four", not two · Two homes → double-edit with two different numbers, or a
W-18 executor never finds it · Correction: declare the routing override in W-13's cell (with the
at-least-four figure) and add a back-pointer in W-18 · **Blocks: NO.**

### RF-24 — [MEDIUM] Two minors-relevant residual-risk-set placements are dropped: WORK-42's interstitial bypass and WORK-44 #2's shared anonymous rate-limit bucket
Loss / safety-minors · Appendix A rows 163 (:1675) and 64 (:1547) · register :6620-6623: "since the
product's primary users are minors, the accepted bypass … belongs in the **launch-readiness
residual-risk set, not only in a decision log**"; register :2944-2947: #2's single shared anonymous
bucket is "a documented live weakness … record it in the residual-risk set" — `WORK-42`,
"interstitial", "middle-click" appear nowhere else in the proposal; row 64 relabels #2 "Historical" ·
The launch-readiness residual-risk set silently loses one minors-safety item and one
insufficient-stopgap item paired with `SEC-18-WAF` · Correction: append both placements to W-22's
accepted-residual-risk scope and amend rows 163/64 · **Blocks: YES — W-22/step 10.**

### RF-25 — [MEDIUM] TEST-01's method point is routed to "AUTHORITY_MODEL §5", which does not contain it
Broken destination · Appendix A row 91 (:1584) · AUTHORITY_MODEL §5.1–§5.7 contain no criterion-1 /
launch-readiness reading rule (grep-verified); the register requires "any launch-readiness summary
must carry the reading with the verdict" · A reader chasing the citation finds nothing and concludes
the rule was never real; a launch summary quotes "criterion 1 MET" without the written reading ·
Correction: add §5.8 to AUTHORITY_MODEL (gate verdicts are quoted with the reading that produced
them; cross-ref `DISCLOSURES-LEGAL`/UD-10) or retarget row 91 · **Blocks: YES — before
AUTHORITY_MODEL promotion.**

### RF-26 — [MEDIUM] The WORK-13 row performs the exact scope-flattening its register entry forbids
Semantic-distortion · `PROJECT_STATE.md:110` · register :3618: single-spec isolation is behaviourally
resolved **and live-verified on `gha-44a12dfc9549`**; the open scope is seventeen-spec cross-spec
contention; "Do not flatten the two scopes" · An agent re-runs the closed one-file scope (a paid
staging arm) and treats the wider scope as closed; combined with UD-2's default ("authorize none")
the wider defect is invisible in both places it could appear · Correction: rewrite the cell —
"Single-spec isolation behaviourally resolved on `gha-44a12dfc9549`; the 17-spec cross-spec scope
stays open; the test-side fixture fix is owed" · **Blocks: YES — promotion.**

### RF-27 — [MEDIUM] §3 states `chat_escalation_sends`' absence from staging as measured fact; the read that would establish it is forbidden and §6.2 says so
Semantic-distortion (inference→fact) · `PROJECT_STATE.md:56-58` vs its own §6.2 `DB-CONTENT-VERIFY`
row · `DEPLOYED_INFRA_STATE_EVIDENCE.md:603`: WORK-03 is in §3.3 "Forbidden under read-only rules";
"the available proxy is circumstantial" · The entry point asserts as fact what it elsewhere lists as
unverifiable — the "unverified counts as not traced" discipline inverted · Correction: "absent from
staging **by inference** (the creating commit is undeployed; the private RDS was not read —
`DB-CONTENT-VERIFY`)" · **Blocks: YES — promotion.**

### RF-28 — [MEDIUM] §9's "zero write operations on the secrets" is false — the rotation record says zero Update/Delete/Restore, with two PutSecretValue creation writes
Semantic-distortion · `PROJECT_STATE.md:332-333` · `REMEDIATION_D310_ROTATION.md:44-46`:
"PutSecretValue since creation: exactly 2 events … UpdateSecret / DeleteSecret / RestoreSecret:
zero" · A future CloudTrail auditor finds PutSecretValue events and concludes the D-310 closure
record is wrong — undermining the one document that proves D-310 is history · Correction: "zero
`UpdateSecret`/`DeleteSecret`/`RestoreSecret` events, and only the two 2026-07-24 Terraform creation
writes among `PutSecretValue` calls" · **Blocks: YES — promotion.**

### RF-29 — [MEDIUM] The WORK-40 row orders re-verification of two items already confirmed built, and re-issues the phantom symbol name the proposal elsewhere retires
Semantic-distortion · `PROJECT_STATE.md:106` · `REPOSITORY_DRIFT_REGISTER.md:686`: "Two of three
items are built" (`stage_narrative_stage` on five response models; the breadcrumb sink) —
code-verified at HEAD by this review; and `formatDateLabel` "names no symbol" per DRIFT-59/W-44 ·
Three of §4.2's act-on items are re-verification of measured facts, and the row whose family retires
the phantom name re-issues it as an instruction · Correction: rewrite the row — two items confirmed
built at HEAD; the third is not a build item (`formatDateLabel` names no symbol; the real formatter
is `buildDateLabelFormatter`, residual = `DRIFT-59-DATE-SHIFT`) · **Blocks: YES — promotion.**

### RF-30 — [MEDIUM] The "twelve engineering halves" list is wrong in both directions: two named rows are documentation-only, three unflagged rows carry real code targets
Migration-mechanics / silent code edits · `MIGRATION_MANIFEST.md:1212-1215` · flag audit over all 44
rows: only ten carry the in-row marker; W-25 and W-29 are `Owner type: documentation` in the
register; W-04 (two terraform variables files), W-42 (a chat-api docstring + a metrics label
comment), W-40 (an e2e spec header) name code-tree targets with no flag · A documents-only executor
silently skips five code-site edits (the "silent omission" the intro forbids) while handing
engineering two rows with no engineering work · Correction: replace the list with the thirteen rows
that actually carry a code half (W-03, W-04, W-05, W-06, W-07, W-11, W-14, W-22, W-31, W-32, W-40,
W-41, W-42); add inline flags to W-04/W-40/W-42 · **Blocks: YES — step 11.**

### RF-31 — [MEDIUM] "16 entries carried by 12 UD ids" is arithmetically wrong — they are carried by eleven; UD-11's source entry is BLOCKED
Arithmetic/representation · `MIGRATION_MANIFEST.md:82`, :1307-1308, :1687 · Appendix A's 16
USER_DECISION_REQUIRED rows map to UD-1…UD-10 + UD-12(a–f); UD-11's entry is `LANGSMITH-RETENTION`,
BLOCKED (row 11) — corroborated by register §12.3 · A count-reconciler finds one UD unaccounted for
and suspects an invented question or a lost entry · Correction: "carried by 11 UD ids; UD-11 is a
twelfth question sourced from the BLOCKED entry `LANGSMITH-RETENTION`" in all three places ·
**Blocks: NO.**

### RF-32 — [MEDIUM] Step 9c fixes one bad key in the queue; two more key defects survive — the register's own topic-key field says `R7.2`, and UD-10 cites a bare `REQ-27` that conflates two entries with opposite dispositions
Migration-mechanics / unstable references · step 9c (:1143-1147) · (a)
`FINAL_OPEN_WORK_REGISTER.md:4525`: "Work/Issue ID (topic key): `R7.2`" — the file the correction
calls authoritative, moving to the same reference directory, disagrees with its own heading;
(b) `USER_DECISION_QUEUE.md:681, :748-749`: bare `REQ-27` merges `REQ-27-FROZENSET`
(ACTIVE_IMPLEMENTATION, unblocked local test) with `REQ-27-TOKEN-CONTRACT` (DEFERRED to integration)
— the register explicitly disambiguates them ("different substances, same claim id") · The
"resolves to nothing" key survives at the authoritative end of the link; the frozenset test can be
mistakenly frozen behind D-152 or the token contract read as closable now · Correction: extend step
9c to a three-line fix (normalize the register's topic-key field; qualify both `REQ-27` citations in
UD-10) · **Blocks: YES — step 9c.**

### RF-33 — [MEDIUM] E-8's mandatory re-presentation obligation ("MUST be re-presented to the user at integration start — launch-blocking at that point") is dropped corpus-wide
Loss / reopen-condition weakening · `PROJECT_STATE.md:257` (`R8-READ-SCOPE` row);
`MIGRATION_MANIFEST.md:1466` · `USER_DECISION_QUEUE.md:981`: the queue excluded E-8 *conditionally*
on that obligation; "re-present" has zero hits across all four proposal files · The conditional
exclusion becomes an unconditional park; at integration start nothing surfaces the launch-blocking
question · Correction: extend the `R8-READ-SCOPE` reopen cell — "At integration start this MUST be
re-presented to the user; launch-blocking at that point. Parked ≠ closed." · **Blocks: YES —
promotion.**

### RF-34 — [MEDIUM] The ORG_ASKS disposition stamp declares a live, freeze-pended deadline "expired 2026-08-02"
Semantic-distortion (live→historical) · `MIGRATION_MANIFEST.md:841-842`; `DOCUMENT_MODEL.md:797-798`
· `S42_ORG_ASKS.md:386-389`: "Message A is due **before S43 opens** … B before S48" — S43 is frozen,
so the deadline is pending and re-arms at integration reopen; no 2026-08-02 date appears there
(2026-08-02 is D-153's answer date); the register reads the same line correctly and `ARCH-35-ORG-TIME`
is BLOCKED, not expired · The stamp designed to prevent wrong action converts a still-owed obligation
into apparent history — the "Send now" trap in reverse, placed where readers trust it most ·
Correction: replace with "Message A remains owed before S43 opens (frozen, D-152), B before S48; see
`ARCH-35-ORG-TIME` (BLOCKED). Message C's hold-until-S42 release condition can no longer arrive as
written." · **Blocks: YES — step 7a.**

### RF-35 — [MEDIUM] The step-6 PROGRESS gate is unsatisfiable as written: two of its four named items are RESOLVED and correctly have no PROJECT_STATE row, and step 6 says "stop"
Migration-mechanics · `DOCUMENT_MODEL.md` §8.1 (:705-712, conjunctive "register key **and** a
`PROJECT_STATE` row"); step-6 gate row (:1082) · grep: `SNS-CONFIRMATION` and `WORK-04-ANSWER-CACHE`
have 0 hits in PROJECT_STATE — both RESOLVED, by design row-less · The executor either halts on a
false positive or learns to wave the gate through, destroying its value for the rows that matter ·
Correction: make the test disposition-aware ("a `PROJECT_STATE` row **iff** the disposition is an
open one; RESOLVED items need the key only") and state inline that these two are expected row-less ·
**Blocks: YES — step 6.**

### RF-36 — [MEDIUM] The OPEN_DECISIONS extraction gate names two live items; the register attributes seven
Gate under-coverage · `MIGRATION_MANIFEST.md` §2.F.3 ("Two things, and only two"), step-6 row
(:1083) · register §11(g) (:7076-7089) maps #3, #4, #5, #6, #7, #9, #10 to live entries
(`WORK-44`, `WORK-35-LEDGER`, `SPEND-AUTHORIZATION`/UD-2, `VIDEO-COVERAGE-PARK`, `D342-PARKING`) —
all verified routed, so this is a gate-completeness defect, not a loss · If any of the five had not
been routed, this gate would not have caught it — the assurance §5.10 claims evaporates ·
Correction: replace the gate row with the seven-row §11(g) subset, citing §11(g) as authority ·
**Blocks: YES — step 6.**

### RF-37 — [MEDIUM] RD-02's live-exposure text survives in a second, unrouted location — the in-entry field *below* the resolution addendum
Archival hazard · `DOCUMENT_MODEL.md` §9.1 names only the §3.2 summary row (:864-866) ·
`DEPLOYED_INFRA_DRIFT_REGISTER.md` ~:155: the entry's trailing "Genuine decision required?: YES …
**the exposure is live and `AWSCURRENT`**" sits after the :152 RESOLVED addendum — the position a
reader reaches last and trusts most · An incident responder grepping `AWSCURRENT` lands on a live
credential-exposure claim in an archived file whose only annotation is on a different row — the
"live-exposure scare" §9.2 names, realized after its own countermeasure · Correction: extend the
§9.1 annotation to the in-entry field and require the resolution stamp to be the entry's **last**
line · **Blocks: YES — step 7d.**

### RF-38 — [MEDIUM] ~50 inbound citations of PROGRESS/OPEN_DECISIONS from surviving files break at step 9, and the no-rename rationale ("preserves the inbound citations") is illusory
Migration-mechanics / broken links · `DOCUMENT_MODEL.md` §8.2 (:739-742), §15.3; step 9a repaths
only ROADMAP's two plan pointers · counted: `OPEN_DECISIONS` — DECISIONS.md 18, ARCHITECTURE.md 1;
`PROGRESS.md` — DECISIONS.md 32, TRACEABILITY.md 1, CLAUDE.md 1, plus 9 from files moving to
reference · Keeping a filename does not preserve a citation whose **path** changes to
`docs/archive/`; and the mid-file-landing hazard the proposal articulates for the expansion plan
applies identically to a 636-line and a 16,690-line archived file, unstated · Correction: add step
9a(ii) — repath every `OPEN_DECISIONS`/`PROGRESS.md` reference in the four surviving active files
(and note the reference-tier ones); restate §8.2's rename rationale on its true ground (citation-
text stability); either add per-section vintage markers to the two high-traffic archived files or
state the accepted hazard · **Blocks: YES — step 9a.**

### RF-39 — [MEDIUM] After the six-schema extraction, SPEC §5.33.3 still prescribes the split and TRACEABILITY's §5.33 row still implies coverage; the "only record anywhere" claim is overstated
Semantic-distortion / two-owner recreation · `MIGRATION_MANIFEST.md` step 2 / HC-2;
`DOCUMENT_MODEL.md` §8.3 · `SPEC.md:3163-3187` (§5.33.3) lists the six logical databases as a
requirement; `TRACEABILITY.md:612`'s §5.33 row is section-granular with no disposition for the
unimplemented sub-items · Post-migration ARCHITECTURE records the question open while TRACEABILITY
implies it covered — a fresh two-owners-disagree in the two files made authoritative; and the HARD
constraint's own premise ("only record anywhere") is inexact (it is the only record that it is
**undecided**) · Correction: add a third destination to step 2 — a TRACEABILITY sub-row
dispositioning §5.33.3's split/Aurora/Multi-AZ as deferred-not-traced, keyed `ARCH-21-SCHEMA-SPLIT`;
soften §8.3's claim · **Blocks: YES — step 2.**

### RF-40 — [MEDIUM] Step 15 archives the two migration documents with no banner and without recording the validation results — violating O20's own HARD requirement
Migration-mechanics · `MIGRATION_MANIFEST.md:1191-1194` vs `DOCUMENT_MODEL.md:986-988` and O20
("run **and recorded** … an unexecuted manifest archived as if executed is the exact failure this
reconciliation exists to fix"); §15.1 requires a banner on every archived file — step 7's 20 targets
omit these 2 · The audit trail lands in archive with no tombstone and an unmarked validation table:
nobody can later tell whether the ten proof points passed · Correction: step 15 → record each proof
point's outcome inline with date and runner; a failed point blocks archival; add the §15.1 banner to
both files before the move · **Blocks: YES — step 15.**

### RF-41 — [MEDIUM] The archive-edit policy is applied inconsistently: nine worklist rows edit `archive/` files after step 9 while §15.4 freezes the archive and W-04 explicitly quarantines instead
Migration-mechanics / rule inconsistency · `DOCUMENT_MODEL.md` §15.4 ("Ordinary maintenance never
edits archive/") vs W-10, W-11, W-12, W-13, W-14, W-18, W-19, W-44 (post-step-9 edits into
`archive/…`) vs W-04 ("quarantined behind archive banners rather than edited") · The executor has no
decision procedure; the archive ends up partly corrected, partly quarantined, indistinguishable —
and the freeze rule is broken by the migration that establishes it · Correction: state once in §0.2
— archived files are edited only at step 7, before the move; after step 9 corrections are recorded in
the superseding current document — and move the archive-halves of the nine rows into step 7d ·
**Blocks: YES — steps 7d/11.**

### RF-42 — [MEDIUM] Step 14's CLAUDE.md rewrite enumeration omits four obligations that only step 14 can discharge
Migration-mechanics / under-enumeration · `MIGRATION_MANIFEST.md:1184-1189` vs W-07 (the
`HINT_SOLUTION_REVIEW` "planned design" description — defeating step 5's purpose), W-21 (the
architecture-hierarchy statement in the index), W-24 (the "spec wins on detail" → granularity
rewording O15 calls unsafe as a conflict rule), W-42 (rule 1's D-050 clause, see RF-15) · HC-7 makes
step 14 the single terminal write to the one unpoliced file; four obligations have no step ·
Correction: extend step 14's enumeration with the four and close with "grep §4 for every row naming
CLAUDE.md and confirm each landed" · **Blocks: YES — step 14.**

### RF-43 — [MEDIUM] AUTHORITY_MODEL §5.4 silently redefines the decision-status enum (drops `proposed`, adds undefined `reversed`) while W-16 quotes the declared three-value vocabulary
Authority / convention change without a decision · `AUTHORITY_MODEL.md:356-363` vs W-16 (:1241:
"the declared `proposed | accepted | superseded` vocabulary") · a vocabulary change presented as a
statement of the existing rule, in a file whose header declares it "creates no new architectural
decisions"; `proposed` is the state D-151's heading needs; `reversed` has no definition or worked
example anywhere · W-16's annotation pass and the promoted enum diverge on day one · Correction:
either state the enum as declared and route `reversed` through W-16 as an explicit convention change
with a D-number, or keep four values and say in §5.4 that this extends the declared vocabulary at
this migration · **Blocks: YES — before AUTHORITY_MODEL promotion.**

### RF-44 — [MEDIUM] `ROADMAP_FROZEN_SESSIONS.md` — imperative build specs for frozen work — gets per-block status lines but no line-1 freeze banner; the freeze-banner count is stated three different ways (2/4/5)
Freeze-visibility · `MIGRATION_MANIFEST.md` §2.C.4 (:540-542, per-block lines only) vs
`DOCUMENT_MODEL.md` §4 tree ("Every file freeze-banner-gated"), :1001, O11 ("the four freeze
banners"), W-20 ("Five freeze banners"), step 7c (two) · §15.1's own empirical argument (a status
line above the stale claim "did not protect anyone"; grep lands mid-file) applies verbatim to the
one new file holding imperative frozen-work specs · Correction: add to step 3 — line-1 D-152 banner
in `S42_OPEN_QUESTIONS.md`'s shape, above the H1, in addition to per-block lines; reconcile the
2/4/5 counts by enumerating the artifacts each statement means · **Blocks: YES — step 3.**

### RF-45 — [MEDIUM] Three proposal documents contradict each other about whether PROJECT_STATE §9 may exist (register: `PROJECT_STATE? no`; the file's own §10: no chronology; the manifest §2.G.3: prescribes it)
Internal contradiction / needs user ratification · `PROJECT_STATE.md` §9 (17 lines of past-tense
narrative) + §10's "No chronology, ever" + register `D310-ROTATION` (`PROJECT_STATE? no`,
`Historical/archive only? yes`) vs `MIGRATION_MANIFEST.md:966-972` (specifies §9's exact content)
and §5.6 (validates against it) · Whichever way it resolves, one proposal document is wrong; as
drafted, §9 sets the precedent that resolved work gets a section, which is how R1.1 reconstitutes ·
Correction (recommended form): delete §9 as a section; keep one quoted framing line in §8 per
AUTHORITY_MODEL §5.7 ("D-310 is resolved historical remediation … corrected on sight") + register
link; move the no-rotation-mechanism acceptance into the `D310-RESIDUALS` §4.1 row; amend §2.G.3 and
§5.6 to match. Flag to the user — this is a ratification call, not an executor call ·
**Blocks: YES — before promotion (any consistent resolution unblocks).**

### RF-46 — [MEDIUM] RD-01 occupies eight locations in six sections; "delete on resolve" is specified as a row deletion and five of the eight are semantic reversals
PROJECT_STATE structure · locations at :61, :81, :87, :116-130, :180, :189, :223, :260-261, :289 —
resolving RD-01 requires reversing F4-CRITERION6's undetectability, WORK-23's blocked prerequisite,
C6-UNATTENDED's clock, UD-6's rider and §3's inertness note, not deleting a row · The
highest-priority item's closure is the likeliest to leave the entry point internally false ·
Correction: add a three-line "fan-out check before deleting" rule to §10 (grep the key file-wide;
multi-section keys carry consequences that are reversed, not deleted) · **Blocks: NO
(recommended before first use).**

### RF-47 — [MEDIUM] §4.3 duplicates 51 lines of register mechanism detail (including two `file:line` citations against the corpus's own convention), and the refresh protocol leaves §4.3's live AWS numbers, §5, §7, §9 and §11 with no owner or trigger
PROJECT_STATE scope · §4.3 vs register entries (verbatim-compared: all nine RD-01 facts, and the
SEC-13/COST-06/WORK-40/D310 mechanisms, already live in the register); staleness rule names §3/§8
only; update protocol names §3/§4/§6/§8 — §7's three cheap unknowns have no delete-after-reading
rule; the two `file:line` cites (`scheduled_jobs.py:61`, `app_events.tf:173`) go stale the moment
the fix lands · The register's refinements silently diverge from the copy read first; the file lies
toward *more* open work, which is how entry points stop being trusted · Correction: compress §4.3 to
five one-line triage entries (why-this-one + cost class + register pointer) — measured net
51 → ~14 lines with zero unique content lost; extend the staleness rule to §4.3 and the update
protocol to §5/§7 (§7: "closed by reading — delete the row the same session") ·
**Blocks: NO (strongly recommended before promotion).**

### RF-48 — [MEDIUM] §1 publishes task-definition revisions `:150`/`:148` as deployed identity without ARCH-34's "one behind family-latest; compare images, not revision numbers" caveat
Operator-trap re-armed · `PROJECT_STATE.md:16` · register `ARCH-34-REVISION-DRIFT`: families' latest
are `:151`/`:149`, byte-identical no-ops; "a tool comparing revision numbers reports drift, a tool
comparing images reports none — and that distinction is the finding"; PROJECT_STATE carries only the
tfvars half in §7 · The next operator sees `:151`, concludes §1 stale, and re-verifies or
force-deploys a no-op · Correction: append "— one behind each family's latest, which are no-ops;
compare images, not revision numbers (`ARCH-34-REVISION-DRIFT`)" · **Blocks: NO.**

### RF-49 — [MEDIUM] §6.3's ARCH-21 row cites `FINAL_ARCHITECTURE.md:179-180` — a path this migration renames — as the only current record of the six-schema question
Unstable reference on the highest-loss item · `PROJECT_STATE.md:242`; the file's own header says
paths refer to the post-migration tree, where that path will not exist · If the extraction is missed,
the dead pointer is the only trail to the unmade decision HC-2 protects · Correction: cite the
post-migration archive name plus the register key, and keep the extraction-precedes-archival
sentence · **Blocks: YES — promotion.**

### RF-50 — [MEDIUM] §6.1 quotes the freeze but never links the D-152 re-entry protocol; on the day the user reopens integration the entry point points at no procedure
Link-depth gap · `PROJECT_STATE.md` §6.1 (zero links); the protocol exists at
`S42_OPEN_QUESTIONS.md:112` (A1·A2·A3 → B1·B2 → A4) and the tree names it as that file's content ·
An agent improvises the sequence D-151/D-153 already specify · Correction: one line — "When the
reopen condition is met, the procedure is `reference/integration/S42_OPEN_QUESTIONS.md`'s re-entry
sequence — do not improvise one." · **Blocks: NO.**

### RF-51 — [MEDIUM] AUTHORITY_MODEL §4.2 has no carve-out for "both sides are explicit user decisions"; applied to D-322 §7 vs D-341 it resolves UD-12(a) by the banned method
Authority / silent-answer channel · `AUTHORITY_MODEL.md:258-269` · register
`DIFFICULTY-TIERS-CONFLICT`: "because both sides are explicit user decisions the corpus's own
ranking rule cannot break the tie"; §4.2(b) ("check DECISIONS for a later entry … before concluding")
hands the reader a clean D-341-wins resolution without ever routing to §4.6 · UD-12(a) is silently
retired; in the asymmetric case (code follows the older decision) the conflict disappears with no
record · Correction: add a precondition to §4.2 — "First check whether both sides are explicit user
decisions. If so, no engineering rule can break the tie; route to §4.6 and record a UD. Live
example: D-322 §7 vs D-341 (UD-12(a))." · **Blocks: YES — before AUTHORITY_MODEL promotion.**

### RF-52 — [MEDIUM] No protocol covers TRACEABILITY rows orphaned by an in-place SPEC amendment — a failure mode that has already occurred once
Authority gap · `AUTHORITY_MODEL.md` §2.2/§2.5/§4 (no protocol) · W-39 records the precedent (the
§5.8.5 row was evidence for a requirement no student could reach until D-226); an amended-away
requirement leaves a row that still reads as a pass — not "unverified", verified against vanished
text · Launch evidence silently over-reports in the flattering direction · Correction: extend §2.2
("amending a SPEC §5 requirement obliges re-checking every TRACEABILITY row citing it in the same
change") and add §4.8 (row reverts to not-traced until re-evidenced; never delete silently) ·
**Blocks: NO.**

### RF-53 — [MEDIUM] §5.9's "no invariant disappears" table is authored, not derived — its check can only prove the 15 hand-picked rows survive
Validation sufficiency · `MIGRATION_MANIFEST.md:1399-1424` · invariants present in the corpus and
absent from the table (all verified surviving, so no loss today): SPEC §5.1.3's
discard-precise-coordinates rules, §5.1.5's prohibited data uses, §5.15.2's retention windows,
§5.29's VLM delete-on-failure row, D-333's consolidate-before-delete gate · The proof point cannot
be used as a gate; the authored-table blind spots are exactly where RF-15/RF-55's hazards live ·
Correction: state the generator (every CLAUDE.md non-negotiable + every SPEC §5 subsection containing
a prohibition/fail-closed rule/deletion obligation/consent or approval gate), regenerate the set, add
the five rows · **Blocks: NO.**

### RF-54 — [MEDIUM] D-333's retention windows amend SPEC §5.15.2 from outside, and §5.15.2 is on none of the amendment lists (W-15's sixteen, W-24's five, §4.1's seven)
SPEC drift omission (UD-7 cluster) · `SPEC.md:1581-1590` still lists the pre-D-333 windows
(90/30/≤90/1y); D-333 governs 30/90/180 plus a chat-checkpoint clock SPEC has no row for; the
precondition itself is safe (three surviving homes) — the *windows* are unmarked · A reader consults
§5.15.2 for retention and gets pre-D-333 numbers with no marker, in the cluster the proposal calls
"the first unblocked step toward a launch-gating privacy requirement" · Correction: add §5.15.2 to
W-15's departure list and §4.1's live examples; add a SPEC-drift row to PROJECT_STATE §8 ·
**Blocks: YES — W-15.**

### RF-55 — [MEDIUM] CLAUDE.md rule 8 is edited by three rows at two steps with no owner, and §5.9's "the feature is parked" phrasing invites reading the deletion rule as parked; two of the rule's four SPEC homes are unlisted
Safety-invariant edit hygiene · W-15 (:1240), W-30 (:1260, step 14), W-42 (:1272) all name rule 8;
§5.9's cell vs §2.A.1's narrower "no such code path currently exists"; the deletion rule also lives
at SPEC §5.15.2 and §5.29's VLM row — W-15's sweep names both areas, so a careless executor could
stamp a park marker on the delete-on-failure guarantee · The register's reopen conditions make the
privacy questions a precondition of building, so the rule binds any future implementation from line
one — the clarifying line must say that · Correction: name W-30 sole owner of the rule-8 wording
("requirement unchanged; no code path implements §5.17 today; the requirement binds any future
implementation — `IMAGE-WORK-PARK`"); cross-reference from W-15/W-42; add §5.15.2 and §5.29's VLM
row to §5.9's bearing-documents cell with "do not mark parked" · **Blocks: YES — steps 11/14.**

### RF-56 — [MEDIUM] §4.3's SEC-13 paragraph drops the two do-not-be-reassured clauses — including the one that makes the leak durable (no retention job sweeps `__resume__`)
Loss of qualifying clauses (minors-privacy) · `PROJECT_STATE.md:132-138` · register `SEC-13-PURGE`:
green branch-locator tests must not be read as covering it; "no retention job covers
`checkpoint_writes.__resume__` rows for live threads, so nothing sweeps up what this path leaves
behind (`RETENTION-CLUSTER`)" — also the only PROJECT_STATE-side link from SEC-13 to UD-7 · The
entry point presents the leak as transient when it is durable · Correction: add both clauses to the
SEC-13 residue line (composes with RF-47's compression) · **Blocks: NO.**

---

## 4. LOW findings (grouped; 44 instances)

### RF-57 — [LOW] Appendix A cell under-specifications (4 instances)
(a) row 40 `NAT-EXISTENCE` cites W-44 and omits W-04, which the register names as the *only*
remaining action (D-419's "absent from the plan entirely" sentence); (b) three residual routes
narrowed: row 153 `F-05` omits "+ W-15"; row 88 `M3-D370` omits the D-366⏸/D-370✅ contradiction's
W-18 half; row 16 `G2-LOCATOR-PURGE` omits D-045's forward pointer (W-18); (c) row 158
`NO-NEW-TEST-CODE`'s "must be stated once next to any headline null result" sentence has no
placement — one line in §4.3's preamble fixes it ("SEC-13, COST-06 and REQ-27-FROZENSET are
established by code reading only"); (d) row 131's engineering half is discoverable only inside
W-32's cell — say so. *Correction:* the four cell edits as stated. **Blocks: NO.**

### RF-58 — [LOW] PROJECT_STATE numeric/attribution precision (6 instances)
(a) §8's RDS bullet omits "both instances in `us-east-1a` — one AZ loss takes out both databases"
(the strongest UD-4 argument); (b) §8/Appendix-A say ALARM "since 2026-08-16" — one of four alarms
transitioned 08-17 (§4.3 already writes "08-16/17" correctly); (c) "flapped 10 times" — the register
says 10 state transitions **each** (= five OK→ALARM→OK cycles on learning-api); (d) "26 of 34
alarms" lacks the register's own pre-D-377-count caveat (and the register is internally ambiguous —
flag upstream); (e) §8's free-tier figures cite `SPEND-AUTHORIZATION` (a restatement) instead of
`COST-25-ALARM-COUNT` (the derivation, with the 91,077-actual figure); (f) §7's heading carries no
count while every sibling section does (5 = 4 + ARCH-34's half; also bridge A.11's "4" and
DOCUMENT_MODEL §10.1's "four" to §5.5's "five substances"). **Blocks: NO.**

### RF-59 — [LOW] PROJECT_STATE structure polish (8 instances)
(a) §3 enumerates five of UD-1's ten undeployed commits with no "plus N docs-only" line — a deploy
blast-radius reader under-sizes the decision; (b) §10 restates the disposition enum as seven of
eleven then the file uses "documentation-only" anyway — link the enum instead; (c) the LB-08
baseline's *why* (only untouched before-measurement for `WORK-01`'s ~22% win; a deploy destroys it)
appears in none of the three places the fact is split across; (d) register/queue links carry no
anchors into 7,418/1,006-line files — make row keys anchor links; (e) the
`BATCH-LOW-UNSCHEDULED-CONTROLS` row omits "one historical clean run, no continuous assurance" for
the PII log boundary — a rule-1 posture statement; (f) `Blocks?` cells carry prose answers — move
qualifiers into the question cells; the four sub-questions paragraph orphans when a parent UD row is
deleted — add a re-home rule; (g) §3 carries a `DOCUMENTATION_ONLY` item (`DRIFT-24`) and §8 an
`OBSERVATION_ONLY` headline (`F-03`) while §8's tail says such entries live in the register —
reword both as sanctioned carry-forwards (operational fact / method rule) so the routing rule isn't
self-contradicted; (h) `WORK-40-TZ` and `DRIFT-59` each claim to close the other across three
sections — name the shared prerequisite once. Also: `TEST-05`'s row drops the "both rows sit under
the 37-of-37 criterion-1 claim" consequence. **Blocks: NO.**

### RF-60 — [LOW] Queue/UD small items (6 instances)
(a) PROJECT_STATE calls four items "sub-questions"; the queue's own accounting says two
(UD-7's is option (viii), UD-2's is a rider) — and the real 16↔12 crosswalk is register §12.3,
uncited by the proposal; (b) UD-12's six sub-items are carried as bare register keys in a
"Question (one line)" table — give each its one-sentence question; (c) E-5's owed user
*acknowledgement* (the approved optimisation rested on a ~2.5 s estimate measured at 124 ms) appears
nowhere — one clause on the `WORK-01` row restores it; (d) `USER_DECISION_QUEUE.md:1005-1006` ends in
stray tool-call markup (`&lt;/content&gt;`, `&lt;/invoke&gt;`) that travels to reference — add a step-9d
deletion; (e) UD-4's default embeds a terraform comment with no engineering split named; (f)
`DRIFT-49`'s resolution step is "ask the user" but it is queued nowhere as a question — either a
UD-12(g) line or an explicit note that it is deliberately unqueued; its placeholder-default fix
needs no decision and belongs in §4, not §7. **Blocks: NO.**

### RF-61 — [LOW] D-310 record completeness (3 instances)
(a) §2.G.3's CloudTrail enumeration omits "PutSecretValue: 2 (creation writes)" (see RF-28 for the
§9 falsity); (b) the rotation record's fourth residual — the transcript that captured the
now-worthless old values — is carried only in the preserve-verbatim field, not in §9's residual
set; state it as accepted-and-neutralized; (c) `DOCUMENT_MODEL.md` §9.2's "nothing leaves these
files" contradicts §2.G.3's three moves — carve out the rotation record. **Blocks: NO.**

### RF-62 — [LOW] Manifest instruction hygiene (8 instances)
(a) W-28 assigns two D-419 edits to step 7d while naming `DECISIONS.md` in neither column, and W-04
owns the same NAT sentence at batch I — leave both with W-04; W-28's cell also says "three stale
lines" against a "four locations" source column; (b) directory creation is monopolized by step 9
while steps 3 and 8 create files in those directories (folds into RF-01's step 0); (c) O1-vs-O15
tension (AUTHORITY_MODEL's Ladder A tells files to defer to SPEC before the amendment sweep) —
resolved in substance by Ladder A step 2; add the sentence; (d) the enrollment-FAQ dead pointer is
assigned to both W-34 (step 9b) and W-39 (batch I) — keep W-34, cross-reference W-39; (e)
`DOCUMENT_MODEL.md` §8.2's "staging numbers nobody has read (read 2026-08-14)" correction appears in
no worklist row — add to W-04 and add a step-15 check that every §7/§8/§9 extract-first bullet has a
row; (f) `INTEGRATION_PLAN` §5's replacement pointer targets a file covering S43–S51 while the table
covers S35–S51 — split the pointer (S35–S42 → archived ROADMAP, labelled historical); (g) HC-6's
"precondition for most other rows" rationale is undercut by ten steps of prior edits — hoist W-38 to
step 0c or narrow the claim; (h) CLAUDE.md's vintage marker is assigned to both W-38 (batch A) and
step 14 — consolidate into step 14 per HC-7. **Blocks: NO.**

### RF-63 — [LOW] Register-fidelity small drops (7 instances)
(a) §4.3's COST-06 paragraph omits "the pipeline is parked by D-342" — the register's own reason the
item is MEDIUM not HIGH; an agent prioritising from §4.3 alone mis-ranks it against RD-01; (b)
Appendix row 47 reads bare "Historical" for `F-03-DRIFT-DETECTOR` while PROJECT_STATE §8 headlines
it — annotate the row like its AUTHORITY_MODEL-§5 siblings; (c) `DRIFT-70`'s "half enforced"
understates a fail-closed gate — reword to "verification enforced and fails closed (empty
frozenset); notice half unbuilt; carve-out not parked → `REQ-27-FROZENSET`"; (d) W-18's eleven
itemized defects omit `D356-FAMILY` item (3) (the D-137/D-141/D-356→D-357 wrong-id citation) that
its own absorption clause hands it — and PROJECT_STATE's D356 row lists two of three actions; (e)
`DRIFT-91`'s optional adapter-factory half is dropped; (f) W-13 instructs correcting a "2 commits
ahead" cell that does not exist in `CLAIM_LEDGER.md` (already corrected in
`LIVE_BEHAVIOR_FINDINGS.md:506`) — retarget the row and note the upstream provenance; (g)
`DOCUMENT_MODEL.md` §8.1's "the answer-cache decision lives **only** in PROGRESS" is false
(D-423's body carries it; the register lists `DECISIONS.md:28771-28782` as a source) — strike
"only"; the second false uniqueness claim among the HARD-ordering justifications (with RF-08's),
worth fixing to protect the constraint set's credibility. **Blocks: NO.**

### RF-64 — [LOW] Authority-model edge cases (3 instances)
(a) §4.3's detect clause and LB-05's reciprocal caution cover only HEAD-ahead-of-staging; a
rollback/revert/branch-deploy (deployed build not an ancestor of HEAD) fires no clause — and the
gitignored-tfvars fact makes that direction policy-invisible; generalize the detect clause and add
the symmetric caution to §2.9; (b) W-44's zero-egress reframe records reality (the "invariant" is
false today by deliberate decision) but lands with no D-number — route the *framing* change through
a decision entry or W-15's sign-off list, keeping the reporting half documentation-only; (c) the
branding plan holds three further unrouted items — an unanswered org ask (request an SVG original),
the brand source-of-truth/re-scrape rule, and the four content-bearing button classes — add the SVG
ask to the org-asks set and the source-of-truth rule to §6.3's extraction list. **Blocks: NO.**

---

## 5. False positives — challenged and cleared

Suspicions this review raised, tested against primary evidence, and rejected. Listed so later
reviewers do not reopen them.

- **C-01 Register coverage is complete and faithful.** All 166 `### \`KEY\`` headings extracted
  mechanically and diffed against Appendix A: zero missing, zero extra, zero transpositions, zero
  primary-disposition mismatches; all 68 compound disposition qualifiers tracked faithfully. All
  eleven §12.1 counts recomputed and correct; §5.1's 27/16/34/4/44/41 = 166 and the 81
  PROJECT_STATE-bound derivation verified both ways.
- **C-02 No reopen condition is materially weakened.** All 15 DEFERRED + 13 PARKED + 6 BLOCKED
  conditions compared field-by-field; the only drops are non-load-bearing cross-references, each
  compensated in the same row; three conditions are *strengthened* (`PLAYWRIGHT-LANE`,
  `DRIFT-12`, `INT-ATTENDANCE-DERIVATION`). `IMAGE-WORK-PARK`'s two-precondition gate,
  `R8-READ-SCOPE`'s "whichever comes first", `F4-CRITERION6`'s undetectability and `D152-FREEZE`'s
  "no evidence can meet it" all survive in substance (E-8's re-presentation duty is the one loss —
  RF-33).
- **C-03 No proposal sentence answers a UD in substance.** Targeted greps for answer-shaped
  phrasings found nothing beyond the UD rows; the manifest explicitly holds UD-12(a), UD-10,
  UD-12(f), the send status and the org-drafts policy open in six separate places; HC-0 holds
  across all 15 steps and 44 rows. (The defect is the *default-action wording* plus the
  authorization sentence — RF-03 — and two model gaps — RF-07, RF-51 — not any answered question.)
- **C-04 UNKNOWN stays UNKNOWN.** All five substances (4 entries + ARCH-34's half) survive with
  named resolution steps and explicit refusals to guess; none softened. The D-192/D-193 firewall is
  intact in three places.
- **C-05 Phantom IDs and audit-ID namespaces are handled.** D-190/D-191/D-192/D-329/D-363 are
  named phantom in PROJECT_STATE §10, W-25 and DECISIONS' plan, never reconstructed;
  `AUD-L-17→AUD-L-19`'s no-mechanical-remap history is preserved; the `<document>:<id>` rule is
  adopted corpus-wide including for the reconciliation artifacts themselves.
- **C-06 RD-01's §4.3 mechanism is exact.** Event-name spellings, 0 datapoints × 4 dimensions ×
  14 days, the single INSUFFICIENT_DATA→ALARM transition per alarm, both fix-site line numbers
  re-verified **live at HEAD** (`scheduled_jobs.py:61` rewrites hyphens; `app_events.tf:173` builds
  the hyphenated pattern), the apply-vs-deploy asymmetry, the do-not-touch list and the
  parity-test second deliverable all match the drift register. (Residuals: the 08-16/17 date in
  §8 — RF-58b; two optional diagnostic facts.)
- **C-07 D-310 is nowhere presented as an active exposure.** Rotation facts match the record
  line-by-line (timestamps, 200/404/404 probe, exit-0 plan, destroyed-not-deprecated); the
  `ps`-visibility residual reads "unmeasured, not cleared" in all three places; RD-02 appears in no
  UD; Appendix row 1 is RESOLVED. (Residuals: RF-28's "zero writes" wording; RF-37's second trap
  location in the archived register.)
- **C-08 All 12 RD ids and all 13 LB rows have destinations; no orphan.** Verified via the
  register's §11(c)/§11(d) maps into Appendix A. LB-05's SHAs (`344f016` / `gha-44a12dfc9549`,
  10 commits) are exact everywhere; LB-08's 10.55 s is build-SHA-qualified at all four occurrences.
- **C-09 Headline live numbers are accurate.** Budget 104.7% / $249.93 vs $230.29 / console $10
  unmanaged; CloudWatch 10.0/10.0 forecast 16.32; X-Ray 91% / 148,599 / 100,000; LangSmith
  2800/1441; RDS 1-day/protection-off/single-AZ/default parameter groups; two unencrypted SNS
  topics; task counts and image digest; MANUAL deploy trigger; no artifact-freshness check with
  the verbatim workflow comment; `journey-student.spec.ts` byte-identical. All traced to evidence.
- **C-10 The §6.1 freeze section's prominence is sanctioned, not a violation.** Its restatement is
  the R9.1 countermeasure; it *quotes* D-417 §A1 rather than paraphrasing, per §5.7. The D-152
  freeze is strengthened by the proposal, not touched; the manifest's "D-341 as the governing
  decision *pending* the UD-12(a) confirmation" is more guarded than the queue's own heading.
- **C-11 All 8 HIGH repository drifts route to live destinations** (none "Historical"); DRIFT-01's
  six-schema residual carries the extraction-precedes-archival constraint; DRIFT-02 is
  strengthened (GuardDuty added to both scope lists); DRIFT-86's LOW→ACTIVE_REMEDIATION escalation
  is explicitly justified, not silent. All 29 LOCAL_EXECUTION rows routed.
- **C-12 SEC-13's code-path shape, COST-06's flush mechanism and WORK-40-TZ's `toLocaleString`
  claim were all code-verified at HEAD and are correct** (only SEC-13's *coverage* claim is wrong —
  RF-10; only COST-06's parking context is dropped — RF-63a).
- **C-13 File and tier arithmetic closes in every direction.** 45 + 3 = 48 = 1 + 5 + 19 + 23,
  independently re-enumerated from the tree; the 15-file reconciliation count and the archive
  directory's 13 + 2 = 15 are consistent everywhere; every one of the 41 line counts in the
  proposal matches `wc -l` exactly (68,085 and 23,262 totals confirmed); no file has two
  destinations; every file on disk (26 + 15) has a role; Appendix A is contiguous 1–166 with no
  gaps or duplicates; the 44 W-rows map 1:1 with no duplicates.
- **C-14 PROJECT_STATE's factual layer is sound.** All 65 table keys and 83 backticked prose
  tokens resolve to canonical register entries (zero phantoms); 61/61 keyed rows sit in the
  disposition-correct section with `PROJECT_STATE? yes`; every section count is right; all five
  relative links resolve in the post-migration tree; the UD-12(f) key correction is already
  applied in the draft.
- **C-15 §14 covers all 18 HIGH documentation risks — exact set match** (independently extracted
  from the risk register's headings). DOCUMENT_MODEL's 49/18 count correction is the correct side
  of the dispute (verified on disk; AUTHORITY_MODEL's 40/16 is the error — RF-12).
- **C-16 The step-7 internal order is right where it matters.** O2/HC-2 (extract before the
  FINAL_ARCHITECTURE rename), O3/HC-4 (`S42_ORG_ASKS` first — the three "Send now" markers are
  real, at :12/:13/:278), O6 (audits README before the moves), O7 (the PROGRESS check is a Phase-1
  gate), O8 (brand data before headers; the duplicate-D-number line is real at branding-plan
  :44-45), O18, O19 all verified satisfied. `FINAL_ARCHITECTURE.md`'s topology diagram and open
  question 5 are exactly where the proposal says (:46-105, :179-180); its other four questions are
  genuinely decided (the SSE gap was closed by D-334/D-335 — register `ARCH-27-SSE-GAP` RESOLVED —
  a suspicion tested and rejected); it has zero functional inbound references.
- **C-17 The 13 evidence artifacts hold no unrouted live content** beyond the named findings
  (RF-37, RF-63f, RF-61b): a live-content marker sweep over all 13 files resolved every hit to a
  register-owned entry. The BD1/BD2/BD5 standing rules are safe in KEEP_ACTIVE `DECISIONS.md`
  (D-065/D-066/D-069 verified, including the minors'-IP CDN rationale).
- **C-18 The `docs/codebase-analysis/` out-of-repo reference is correctly handled** (step 9b:
  written as explicitly out-of-repository, not "fixed" into a local path). The D-093→D-137 hazard
  is handled as a pre-move check with the right severity framing (the defect is its scheduling —
  RF-18's O12 half — not its treatment). W-19 vs §2.F.2 vs §8.1 agree on "retire or date" — no
  contradiction. Step 14's dependency on steps 8/12 is not circular.
- **C-19 The span-event redaction gap survives as flagged, highest-value active work**
  (PROJECT_STATE §4.2), and SEC-13 is carried at full fidelity as the first-ranked new-test
  candidate. Neither minors-privacy control is weakened by the migration (contrast RF-11, which is
  about a different control's *visibility*).
- **C-20 Six-schema "extraction before archival" sequencing is correctly HARD.** The claim that
  archiving first deletes the question from the corpus is true as far as any read document shows
  (no D-number owns it; OPEN_DECISIONS declares nothing open; ARCHITECTURE never mentions it;
  `alembic/env.py` has no `include_schemas`/`schema_translate_map`) — the constraint stands;
  only the "only record anywhere" phrasing needs the RF-39 softening (SPEC §5.33.3 still
  *prescribes* the split).

---

## 6. Coverage proof

| Scope demanded by the review brief | Result |
|---|---|
| **All 166 Phase-4 register entries** | 166/166 keys verified present in Appendix A with matching dispositions; all 68 compound qualifiers compared; 41 historical entries read for unrouted live residuals (7 residual-drop instances: RF-20, RF-24×2, RF-25, RF-33, RF-57c, RF-60c); claim-ID→entry routing spot-verified on 17 owners incl. **COST-21 → `KPI-ALARM-FLOOR` → UD-5** |
| **All 12 user-decision entries** | 12/12 questions + 6/6 UD-12 sub-items + 4/4 riders/sub-questions compared line-for-line against the queue; none answered; 16/16 exclusion rows checked (2 residual losses found: RF-33, RF-60c); all 23 cited register keys resolved (2 defective beyond step 9c's fix: RF-32) |
| **All active remediation/implementation items** | 27/27 remaining actions compared against register entries (distortions: RF-10, RF-26, RF-29; context drops: RF-56, RF-63a/d/e) |
| **All deferred/parked reopen conditions** | 28/28 (+6 blocked) compared field-by-field; none weakened except E-8's re-presentation duty (RF-33); three strengthened |
| **All UNKNOWNs** | 5/5 substances preserved with named steps; none upgraded to a conclusion; D-192/D-193 firewall intact; count-presentation bridge defect only (RF-58f) |
| **All documents proposed for archival** | Read in full: `FINAL_ARCHITECTURE.md`, `OPEN_DECISIONS.md`, `S42_ORG_ASKS.md`, branding plan; targeted: `ROADMAP.md` (S42–S51 verbatim + all 95 "Done when" positions), `PROGRESS.md` (top stack + carry-over tail), expansion plan, all 13 reconciliation artifacts (live-marker sweep). Findings: RF-02, RF-08, RF-09, RF-34, RF-35, RF-36, RF-37, RF-38 |
| **Named attention items** | RD-01 clause-by-clause (C-06); SEC-13 code-verified (RF-10 + C-12); COST-06 code-verified (C-12, RF-63a); COST-10 → §4.2 verified; COST-21 → UD-5 verified; WORK-40 (RF-29); LangSmith ingest §4.1 + retention UD-11/§6.2, numbers verified (C-09); budget/gross posture verified exact (C-09); RDS posture verified (C-09, RF-58a); `ps`-visibility "unmeasured, not cleared" in all three places (C-07); D-322/D-341 held open in the manifest (C-10) with two closable leaning channels found (RF-03, RF-51); D-356 family preserved (item-3 gap: RF-63d); D-152 freeze strengthened and verified (C-10, RF-44 for the new file); LB-05 exact everywhere (C-08) |
| **Six-schema / FINAL_ARCHITECTURE sequencing** | Verified HARD and correctly ordered (C-20); two corrections needed (RF-39 TRACEABILITY disposition; RF-49 dead pointer) |
| **Safety/minors/privacy/authz/HITL invariants** | §5.9's 15 rows traced — every named SPEC anchor opened and confirmed (16 anchors); no invariant-bearing document routes to archive; 9 further invariants hunted beyond the table (5 absent from it — RF-53); defects found are edit-instruction hazards (RF-14, RF-15, RF-55) and visibility (RF-11), not archival losses |
| **Authority model** | 5/5 stress scenarios run; all five yielded defects (RF-13, RF-16, RF-17, RF-51, RF-52 + RF-64a); 18/18 HIGH risks confirmed covered by §14 |
| **Migration mechanics** | O1–O20 all checked (verdict table produced: O1 violated; O12/O13/O16/O17 violated via batch order; O9/O14/O15/O20 partial; rest satisfied); steps 1–15 all checked; HC-0…HC-7 all checked (HC-0 holds; HC-6 conflicts with O12; no HC governs promotion); W-01…W-44 mapped 1:1; the UD-12(f) key error confirmed on disk, its correction specified exactly once as an action with consistent references, and **no proposal file propagates the wrong key as if correct** |
| **Phantom decision IDs / ambiguous audit IDs** | Remain explicitly phantom (C-05); source-qualification rule intact and extended to the reconciliation corpus |
| **Four proposal-design questions** | Located and assessed: (1) W-23 split shape — OPEN, correctly flagged for ratification twice; (2) PROGRESS-successor narration — flagged open in the manifest but **closed by PROJECT_STATE §10** (RF-07); (3) W-15's three sign-off points — OPEN but visible only inside one table cell, absent from the closing ratification list; (4) W-06's DRIFT-31 delegation ruling — OPEN, weakest framing ("if wanted"). **Two additional forced design decisions missing from the flagged set:** whether the `/end-session` skill is rewritten (no step touches it — RF-07's correction adds one), and the decision-status enum's scope (`reversed` added silently — RF-43) |

**Limits of this review (stated, not hidden):** the upstream completeness of the Phase-4 merge
(349 source items → 166 entries) was not re-derived from the ~1.85 MB artifact corpus — Appendix A
is provably faithful to the register's index, and this review found five distortions *inside*
routed entries, but an item the register itself missed would be invisible here. The 45 MEDIUM and
49 LOW repository drifts were verified routed but not one-by-one re-substantiated. The truth of
underlying AWS reads was accepted from the evidence files except where re-measured.

---

## 7. Disposition summary

- **Verdict: PASS_WITH_REQUIRED_CORRECTIONS.** The architecture holds; the execution plan does not,
  yet. The two CRITICAL findings (promotion ordering; the nonexistent "Done when" extraction target)
  plus RF-18/RF-19 mean the manifest needs a corrected step sequence and a provenance rule before any
  file moves. The PROJECT_STATE/AUTHORITY_MODEL corrections (RF-03…RF-07, RF-10…RF-17) must land
  before promotion because those two files are the migration's first act.
- **Nothing here requires Phase 7 to start, and this review starts nothing.** All corrections are
  edits to the four proposal files (plus four upstream register/queue corrections flagged in §0);
  none touches project documentation or code.
