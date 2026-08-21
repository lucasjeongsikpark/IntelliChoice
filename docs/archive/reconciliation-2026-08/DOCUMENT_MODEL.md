> **ARCHIVED 2026-08-20. Historical record — do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** describes a transition that has completed; the tree it proposed is now the real tree.
> **Superseded by:** the executed tree; see `docs/archive/README.md`.

# DOCUMENT_MODEL.md — the future role of every documentation file

**Status:** PROPOSAL. Nothing in this document has been executed. No file outside
`docs/reconciliation/proposal/` was created or modified to produce it.

**Authored:** 2026-08-20, as Phase 5 (Canonical Documentation Proposal) of the documentation
reconciliation. Inputs: the Phase-5 design spec (§11.1 final tree, §11.4 risk map, §4/§5 archive
design), the A3 documentation inventory (26 per-document profiles + the 49-entry risk register
digest + the verified disk listing), and the A1 extraction of `FINAL_OPEN_WORK_REGISTER.md`
(Section 3's 44 `DOCUMENTATION_ONLY` entries, Section 5.4's `ARCH-21-SCHEMA-SPLIT` obligation).

**Role assignments are fixed by the design spec §11.1 and are not re-decided here.** This
document supplies the reasoning, the destination path, the extract-before-move obligations, the
ordering constraints, and the mis-migration risk for each file — the material a migration executor
needs in order to move a file without losing anything.

---

## 1. Scope: what is covered

| group | count | covered in |
|---|---|---|
| Inventoried documents (23 at `docs/` top level + 2 in `docs/plans/` + root `CLAUDE.md`) | 26 | §5–§8 |
| `docs/reconciliation/` audit artifacts | 15 | §9 |
| `docs/reconciliation/proposal/` files (this file included) | 4 | §10 |
| **Total files assigned a role** | **45** | |
| New files created at migration (not assigned a role — they do not exist yet) | 3 | §4, §11 |
| Code-adjacent READMEs, out of scope | 2 | §12 |

**Count correction (reconciliation artifacts): 15, not 16.** The A3 inventory's §3.3 header says
"16 files" and its §3.6 says "the other 14", but its own §3.3 table has 15 rows, its §3.6
parenthetical enumerates 13 names, and a live listing of `docs/reconciliation/` on 2026-08-20
returns exactly 15 `.md` files. The design spec §4 agrees at 15 (2 live registers + 13
evidence/register artifacts). The header count is an off-by-one; the enumeration wins. Every one of
the 15 is named in §9, so nothing is left unassigned.

**Count correction (risk register): 49 entries, and 18 HIGH — not 40 and 16.** The A3 digest's
"40 risk entries total" line is a typo against its own section arithmetic (8+6+8+7+7+6+3+3+1 = 49),
and its "HIGH = 16" line is contradicted by the 18 IDs it enumerates on the same line and by the
per-table severities (HIGH 18, MEDIUM 24, LOW 7 = 49). §14 covers all 18 HIGH risks. This is
itself an instance of R8.1 — a hand-written summary line contradicting the table above it — in the
register that reports R8.1.

---

## 2. The five roles

| role | meaning | the file's fate |
|---|---|---|
| **KEEP_ACTIVE** | An agent must read or update it during ordinary non-trivial work. Stays in the always-current tier at `docs/`. | Stays in place; gets hygiene work, not a move. |
| **MERGE_INTO_ACTIVE** | Its content folds into an active file and the source stops existing as a document. | *Assigned to zero files — see §3.* |
| **MOVE_TO_REFERENCE** | Durable, read-on-demand content that is true regardless of the current date, or frozen-but-load-bearing content a specific task needs. Read when the topic comes up, not per session. | Moves under `docs/reference/`, usually with a banner. |
| **ARCHIVE** | Historical record. Valuable as provenance, dangerous as instruction. | Moves under `docs/archive/` with a tombstone banner. Never deleted. |
| **SPECIAL_CASE** | The file is split, promoted, or rewritten rather than moved — one role name cannot describe its fate. | Per-file plan, always stated explicitly. |

Role boundary that decided most assignments: **"must an agent read this at the start of
non-trivial work?"** `INCIDENT_RESPONSE.md` is the strongest near-miss — it is read when an
incident happens, which is a trigger, not a session. `TRACEABILITY.md` passes because it is read
*and written* whenever launch scope is touched and it is the live §2.6 criterion-1 instrument.

---

## 3. Why MERGE_INTO_ACTIVE is empty

Two files look like merge candidates: `FINAL_ARCHITECTURE.md` (its topology diagram belongs in
`ARCHITECTURE.md`) and `docs/plans/2026-07-19-branding-plan.md` (its brand table and BD3
do-not-revert rule belong somewhere active). Both are instead **extract-then-archive**, because a
true merge implies the source ceases to exist and the hard rule is *archive, never delete*. The
extracted content lands in an active file; the body survives under `archive/` as the provenance
record for where that content came from and when it was true.

Consequence for executors: an extraction is not finished when the text is copied. It is finished
when the copy is in its destination **and** the source is archived with a banner naming the
destination. Half-done extraction is the failure mode that produced R2.1 in the first place —
`FINAL_ARCHITECTURE.md`'s own fold-back-and-delete instruction fired on 2026-07-22 and was never
executed (R6.6).

---

## 4. The final directory tree

Per design spec §11.1. `[new]` marks a file that does not exist yet; `[renamed]` marks a file whose
original name is recorded in its archive banner.

```
CLAUDE.md                        # repo root. Pointer + non-negotiables + the complete doc index.
docs/
  PROJECT_STATE.md               # [new] THE entry point. Reconciled current state + doc map.
  SPEC.md                        # Normative requirements. Amended in place, dated, with D-refs.
  ARCHITECTURE.md                # Single as-built authority: topology, invariants, storage split.
  DECISIONS.md                   # Append-only decision log; system of record for rationale.
  TRACEABILITY.md                # Live §2.6 criterion-1 evidence instrument.
  reference/
    AUTHORITY_MODEL.md           # [new] Precedence rules + conflict protocols.
    INCIDENT_RESPONSE.md         # Incident runbook: severity tiers, five playbooks.
    QUESTION_GENERATION.md       # As-built offline question-generation pipeline design.
    HINT_SOLUTION_REVIEW.md      # Hint/solution review instrument design (reconciled first).
    U7_CHECKPOINT_CONSOLIDATION.md  # Staging checkpoint sizing measurements (as-of banner).
    CONTENT_COVERAGE.md          # Math-taxonomy disposition record (as-of banner).
    FIRST_VISIT_NOTICE.md        # Written copy for the eleven §5.1.2 disclosures.
    integration/                 # The D-152-frozen world. Every file freeze-banner-gated.
      INTEGRATION_PLAN.md        # Tier 0/1/2 taxonomy, auth options, I1–I15, §2.6 gate criteria.
      S42_DISCOVERY.md           # Production-system facts read from source (§0–§6 durable).
      S42_OPEN_QUESTIONS.md      # What source could not answer + the D-152 re-entry protocol.
      ROADMAP_FROZEN_SESSIONS.md # [new] S42–S51 scope bullets + 5 embedded constraints (no "Done when" exists in range).
    org-drafts/                  # Send-ready outbound text awaiting a human send decision.
      S42_SECURITY_REPORT.md     # The one production security hand-off message (+ send status).
      ENROLLMENT_FAQ_APPROVAL.md # The enrollment-FAQ claim-confirmation ask + flip procedure.
    audits/
      README.md                  # [new] Audit ID-namespace map + source-qualified citation rule.
      AUDIT_FINDINGS.md          # Phase 0A register, frozen 2026-08-05.
      AUDIT_2026_08_16.md        # Four post-C1 sweeps; owns the symmetry-drift table.
      AUDIT_LIVE_2026_08_17.md   # Deployed-build browser walks; owns the coverage-gap lesson.
    reconciliation-2026-08/
      FINAL_OPEN_WORK_REGISTER.md  # The 166-entry provenance backbone PROJECT_STATE links into.
      USER_DECISION_QUEUE.md       # Full UD-1…UD-12 option analyses.
  archive/
    README.md                    # [new] Archive index: what, why, superseded-by.
    ROADMAP.md                   # Session-by-session build history (after frozen-session extract).
    PROGRESS.md                  # The project's history of record, S0 → 2026-08-18.
    OPEN_DECISIONS.md            # Deliberation record for 14 closed judgement calls.
    2026-07-21-final-architecture-projection.md  # [renamed] was docs/FINAL_ARCHITECTURE.md.
    2026-07-24-org-asks-drafts.md                # [renamed] was docs/S42_ORG_ASKS.md.
    plans/
      2026-07-18-expansion-plan.md  # Design reference behind S17–S28 (executed-as header).
      2026-07-19-branding-plan.md   # Visual-identity plan executed as S22.5 (executed-as header).
    reconciliation-2026-08/      # The 13 evidence artifacts + DOCUMENT_MODEL + MIGRATION_MANIFEST
                                 #   (the last two only after the migration executes).
```

**File counts in the proposed tree:** 1 root + 5 active + 19 reference + 23 archive = **48 files**.
That is the 45 role-assigned files plus the 3 `[new]` files. Nothing is deleted, so the arithmetic
must close and does. (The design spec's "reference ≈ 18 / archive ≈ 21" were estimates made before
`reference/audits/README.md`, `ROADMAP_FROZEN_SESSIONS.md` and `archive/README.md` were counted.)

---

## 5. KEEP_ACTIVE — the four surviving active documents (4 files)

Together with the new `PROJECT_STATE.md` these are the five files at `docs/` top level. The test
each one passed: an agent doing ordinary non-trivial work must read or update it, and no other file
can hold its content without destroying a distinction (normative requirement ≠ as-built fact ≠
recorded rationale ≠ evidence method).

### 5.1 `docs/SPEC.md` → **KEEP_ACTIVE**

- **Destination:** `docs/SPEC.md` (unchanged).
- **Why:** 4,210 lines of normative truth with no substitute. It uniquely owns the token claim set,
  the eleven first-visit disclosures, the curriculum band tables, the eleven §5.8.5 validation
  checks, the difficulty weights and gain formula, verbatim user-facing strings, the §5.19.5
  `TurnReason` table, the §5.29 failure matrix, the §5.30.1 Bedrock wire allowlist and the §5.33.4
  SLO targets. Nothing else in the corpus states what the system is *required* to do.
- **Extract first:** nothing leaves SPEC. The migration work is inward: one systematic
  `AMENDMENT-SWEEP` pass (A1 §3 item 15) adding dated amendment markers — or a single "SPEC
  amendments" index — at the sixteen named points of departure (§5.33, §5.33.4, §5.36, §5.8.1,
  §5.17, §5.32.1, §5.2.2, §5.26.3, §5.25.1, §5.5.2, §5.19.3, §5.30.1, §5.11.2, §5.13, §5.1.4,
  §5.29). SPEC currently carries **two** in-text markers in 4,210 lines (D-351, D-092); the D-111
  MySQL sweep rewrote ~40 lines and four headings and left none.
- **Ordering:** the D-351 pattern (amend in place, dated, with the D-number) becomes mandatory
  *before* any other file is told to defer to SPEC. §6's 24-phase sequence is marked historical in
  the same pass. Three items inside `AMENDMENT-SWEEP` are non-editorial and need user sign-off
  during migration, not before: DRIFT-15's two unbuilt §5.29 mechanisms, REQ-49's unbuilt
  mechanisms, and DRIFT-16's reading question.
- **Risk if migrated incorrectly:** R1.4 — a reader cannot distinguish never-amended text from
  silently-amended text, and `CLAUDE.md` says "the spec wins on detail". Because SPEC references
  nothing, that rule is safe about *granularity* and unsafe as a *conflict-resolution* rule; for
  §5.8.1, §5.11.2, §5.13.2, §5.28.2 and §5.33 the decision log wins and SPEC still reads as if it
  does not. Also R4.5 (§5.2.2's auth-option menu reads live inside the D-152 freeze), R2.6 (the
  always-loaded `CLAUDE.md` compression is the copy actually read), R3.8 (the H1 is
  `# 5. Very Detailed Version`, a section number from an absent parent).

### 5.2 `docs/ARCHITECTURE.md` → **KEEP_ACTIVE**

- **Destination:** `docs/ARCHITECTURE.md` (unchanged). Becomes the **single** as-built authority and
  the sole owner of the storage-split table.
- **Why:** 2,180 lines, actively maintained, and the `/end-session` ritual already mandates updating
  it. It uniquely owns the ten rendered dataflow diagrams, the measured capacity/pricing table with
  its extrapolation ban, the access-probe rule-history table, the egress/sink table ("LangSmith is
  the only egress that leaves AWS") and the two shipped plan-deviations (D-064, D-130).
- **Receives at migration (inbound extractions):** (a) the end-to-end deployed-topology diagram from
  `FINAL_ARCHITECTURE.md:46-105`, refreshed; (b) a new **"Open architecture questions (undecided —
  do not treat as designed)"** block holding the SPEC §5.33.3 six-schema logical split; (c) the
  one-line as-built fact "today's system is one `intellichoice` Postgres database", which currently
  exists only inside the stale projection; (d) the brand table and BD3 do-not-revert rule from the
  branding plan.
- **Extract first:** nothing leaves. Inward hygiene: de-duplicate the scheduler state so it lives
  once (`DOC-SCHEDULER-SECTIONS` — L28-30 lists four enabled EventBridge schedules and is
  contradicted at `:1850-1851` and `:2068` in the same file); reduce the §7-R8/R9 restatements to
  pointers or carry the expiry conditions; add the AUD-F-28 resize caveat to the D-136 price table;
  reword the Vite content-hash "deploy gate" to describe the procedure it actually is; correct the
  storage-split table's under-count of twelve shipped Postgres tables; reframe the zero-egress
  invariant as baseline-with-exception (currently false by deliberate decision, ~$33/mo).
- **Ordering:** the two `FINAL_ARCHITECTURE` extractions must land here **before** that file is
  renamed and archived. Neither ARCHITECTURE self-contradiction may be resolved from the document
  alone — resolve against code and deployed state, then record which layer each sentence describes.
- **Risk if migrated incorrectly:** R2.1 — two architecture documents with no ratified hierarchy,
  where deference is stated only in the weaker file and the filename "FINAL" points the wrong way.
  R2.2 — ARCHITECTURE is the file sessions read and update, and it restates both accepted P1 risks
  **without** their expiry conditions. R1.5 — three verified internal live/stale pairs on scheduler
  state. If ARCHITECTURE is not declared the single owner at migration, the storage table has two
  owners again the moment anyone appends a row.

### 5.3 `docs/DECISIONS.md` → **KEEP_ACTIVE**

- **Destination:** `docs/DECISIONS.md` (unchanged).
- **Why:** 28,787 lines, 443 D-entry headings, D-001 → D-423. It is the system of record for
  rationale: supersession chains, correction trails, measured constants, incident post-mortems
  (D-084, D-085, D-310, D-400) and user decisions *with the options that lost*. It is also SPEC's
  de-facto amendment layer (~220 SPEC references). Its loud-correction culture is the strongest
  documentation discipline in the repo and must be preserved, not smoothed.
- **Extract first:** nothing. Migration work is mechanical hygiene, in three bounded pieces:
  (1) a status-tag pass over the **eight verified-misleading entries** plus adoption of D-153 §5's
  backward-pointer convention going forward — a full 120-entry sweep is explicitly deferred as the
  Phase-4 safe default; (2) an ID index; (3) phantom-ID annotation.
- **Phantom IDs — the hard rule:** `D-190`, `D-191`, `D-192`, `D-329` and `D-363` are
  **cited-never-written**. D-190/191/192 are cited 18× in code and 8× in docs with no entry;
  D-329 exists only as a sub-heading inside D-330; D-363 is referenced 4× with no heading anywhere.
  They are annotated as cited-never-written in the index. They must never be cited as existing
  entries, and reconstructing their content from 26 citation sites is real work with a judgement
  component — prefer a stub-with-provenance. D-192's content is an accepted UNKNOWN: no resolution
  step exists, and D-193's description must **not** be adopted as D-192's content.
- **Ordering:** any tooling keyed on `## D-nnn` headings — including this audit's own merge keys —
  is unsafe until the phantom-ID and heading-format problems (format changes mid-file at D-274)
  close. So the ID index is built *before* anything mechanical is run over the log. `DECISIONS.md`
  also gains a pointer from the D-310 chain to the archived rotation record.
- **Risk if migrated incorrectly:** R6.1 — the declared `proposed | accepted | superseded`
  vocabulary is unmaintained and a scan of headings by status finds **zero** supersessions among
  ~40 chains. R6.2 — phantom IDs make ID-grep unreliable. R1.3 — entries are edited in place and
  reference later decisions, so an entry's text cannot be dated by its heading. A "cleanup" that
  rewrites bodies to look consistent would destroy the correction trail, which is the file's most
  valuable property. Consistency is not evidence of correctness.

### 5.4 `docs/TRACEABILITY.md` → **KEEP_ACTIVE** (the justified fifth active file)

- **Destination:** `docs/TRACEABILITY.md` (unchanged).
- **Why:** the only candidate that passed the active test on the merits. It is a **living
  instrument**, not a snapshot: created 2026-07-30 (D-124), swept in six tranches to 37/37 sections,
  actively maintained through 2026-08-17 (D-387). It is unmergeable because its content is a third
  thing — evidence method — distinct from SPEC's norms and ARCHITECTURE's as-built claims. It
  uniquely owns the method rule ("unverified counts as not traced"), the four-verdict vocabulary
  with its fenced "structural" definition, the launch-scope determination and exclusions, and T-01/
  T-02 with dispositions. Any session touching launch scope reads *and writes* it.
- **Extract first:** nothing. Inward: the four `TRACEABILITY-ARITHMETIC` defects — re-derive the
  three thin exclusion attributions (D-004, "§6.19 Phase 18 (D-078)", D-087/S50 A7) by quoting the
  decisions or record them as inferences; correct the 37-of-37 label over a 36-section launch-scope
  denominator and the stale "21 of 37" running total; delete or date the 16-section present-tense
  tail sitting under a "nothing remains" banner; add GuardDuty to both S50 A7 scope lists. Coverage
  is complete — only the labels are wrong.
- **Ordering:** apply the `file:line` as-of stamping convention **here first**. This is the §2.6
  criterion-1 instrument, so a drifted citation degrades launch evidence rather than merely
  confusing a reader; it was already burned once when the §5.8.5 row was evidence for a requirement
  satisfied by code no student could reach until D-226 rewrote it. The T-02 block also needs a
  forward pointer to `FIRST_VISIT_NOTICE.md`, which it does not reference at all.
- **Risk if migrated incorrectly:** R8.1 — its own summary lines have contradicted its own tables
  twice; both were kept and annotated, deliberately, as method. Preserve that. R6.4 — T-02's "S45"
  owner inherits the S45 label collision (ROADMAP's unstarted consent session vs PROGRESS's
  completed unnumbered "S45"), so the collision must be disambiguated before anyone can state who
  owns T-02. Its §7-R8 acceptance expires at first real traffic and that expiry must survive into
  `PROJECT_STATE`'s parked section.

---

## 6. SPECIAL_CASE (4 files)

Four files whose fate no single role name describes. Three are inventoried documents; the fourth is
this proposal's `PROJECT_STATE.md` draft (§10.1).

### 6.1 `CLAUDE.md` (repo root) → **SPECIAL_CASE: rewritten index at migration**

- **Destination:** stays at the repository root. **Not modified in this phase** — the rewrite is a
  migration action, not a proposal action.
- **Why not simply KEEP_ACTIVE:** because its content changes character. Today it is a partial
  doc-index plus a lossy compression of SPEC §5.x; after migration it is a pointer file whose
  index must name **every non-archive document** and whose front door is `PROJECT_STATE.md`. It
  keeps its unique assets: the two credential hard rules, the production-freeze rule, the D-152
  do/don't list, `signups.attended = null` is routine, and the ten condensed rules.
- **Extract first:** nothing leaves. What must be *added or fixed* at rewrite:
  1. **Index completeness.** The index names 11 files and omits 13 that exist. Every non-archive
     document is indexed, or explicitly listed as "deliberately unlisted because …".
  2. **The OPEN_DECISIONS description** — currently "everything still open … ten decisions … the
     answer is often 'ask the user'" against 14 items, all closed. This single description sends
     every session to a closed file looking for work. Cheapest, highest-value fix in the corpus.
  3. **Freeze cross-links.** The ⛔ section names `S42_OPEN_QUESTIONS.md` only; it must name
     `reference/integration/INTEGRATION_PLAN.md`, `S42_DISCOVERY.md` and the archived org-asks
     drafts — the three files the freeze actually binds.
  4. **A last-reviewed date marker** (`DOC-VINTAGE-HEADERS`): it is continuously maintained present
     tense with no date or version anywhere, and it has drifted before — rule 1 said "MongoDB"
     until the D-082/D-111 sweep.
  5. **Stale descriptions:** SPEC is "~2,600 lines" (4,210 — a 38% understatement); rule 8 guards a
     deferred feature and needs one clarifying line; the SPEC-wins wording is corrected from a
     conflict-resolution rule to a granularity rule; `HINT_SOLUTION_REVIEW.md` is no longer "the
     planned design"; add the CloudFront-domains sentence from `RD-12-INGRESS`.
- **Ordering:** the rewrite is **last** in the migration, because the index must name final paths.
  One exception may land early as an interim: fixing the OPEN_DECISIONS description costs nothing
  and removes a live wrong-action pointer.
- **Risk if migrated incorrectly:** R7.1 (HIGH) — omission from this index *is* invisibility;
  `ARCHITECTURE.md` is the file every session must update and none is told to read, and
  `ENROLLMENT_FAQ_APPROVAL.md` claims to be the only launch-checklist gate while being invisible at
  session start. R5.1 (HIGH) — the resolved-looks-open pattern in the one file every session loads.
  R9.1 (HIGH) — the freeze is stated here but not linked to the documents it binds. R2.6 — the
  compression is the copy actually read. **Nothing references `CLAUDE.md` back, so drift here is
  unpoliced**: it is the only file in the corpus with no external check on it.

### 6.2 `docs/ROADMAP.md` → **SPECIAL_CASE: split (reference extraction + archive)**

- **Destinations:**
  1. `docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md` `[new]` — the extracted S42–S51
     scope bullets and rollout paragraph with their five embedded constraints (no "Done when"
     acceptance criteria exist in that range — none are authored).
  2. `docs/archive/ROADMAP.md` — everything else: the gate ledger, the C1/A6-C track logs, the
     M10–M15 retrospectives, the ~100 completed work units.
- **Why split:** the frozen-session scope bullets are ROADMAP's unique normative asset for S43–S51 —
  **ROADMAP holds NO "Done when" acceptance criteria in that range** (verified: zero occurrences
  between lines 525 and 1769; the 95 "Done when" blocks all belong to S0–S41 and the milestone work
  units) — that content is load-bearing the moment the user reopens integration. The other ~60% is completed-work retrospective that
  `PROGRESS.md` and `DECISIONS.md` already own, including three "✅ CLOSED" banners and ~470 lines
  of superseded gate standings interleaved with a live "THE GATE IS CLOSED".
- **Extract first (HARD ordering):** the frozen-session extraction happens **before** the archive
  move. Extract the S42–S47 scope bullets and the S48–S51 rollout paragraph (not just S43–S47), with
  their five embedded constraints — the D-153 §5 role gate (production `role` must never by itself
  grant an elevated role), the six structural dev-fake mismatches, the two-source `BranchInfo` merge,
  the D-153 §4 session-window assertion, and D-167's `/dev/token` deletion cascade including the
  `sub` assertion — and, during extraction, **add the freeze annotation to
  S48–S51**, which today carry none at all despite depending entirely on frozen sessions. Also
  carry across, or re-home: the SPEC-section→session mapping, the sequencing rationale and
  dependency spine, the "decide at session start" gates, and ROADMAP's **anchored-awk derivation**
  precedent — the register itself tells readers to trust the awk over hand-maintained counts, so the
  technique is worth preserving as the mechanical-summary exemplar (R8.1's countermeasure).
  **No acceptance criteria exist for S43–S51; do not author any during extraction** — a fabricated
  "Done when" for frozen work is the R4.5 failure in its worst form. The new file carries a line-1
  D-152 freeze banner above the H1.
- **Ordering:** ROADMAP's two live pointers into `docs/plans/` must be repointed to
  `docs/archive/plans/` in the same pass (the pointers survive the archive move; a dangling pointer
  inside an archived file is still a dangling pointer). Sequence after the branding-plan and
  expansion-plan headers exist, so the pointer lands on a file that announces itself as historical.
- **Risk if migrated incorrectly:** R1.2 (HIGH) — the superseded gate standings, five coexisting
  criterion-6 dates, and multi-tier numbers carrying 3–4 unreconciled values where later-in-file is
  earlier-in-truth. R4.5 — S43–S47 are imperative build specs with the freeze only *above* them;
  archiving without extraction destroys the frozen-session scope and its five embedded constraints,
  and extracting without the freeze
  banner produces a clean-looking build spec for frozen work, which is worse than the status quo.
  R3.7, R8.2 (18 headings carry no glyph while a line asserts all are done), R8.3 (duplicate
  blocks), R2.3 (session status has three homes).

### 6.3 `docs/plans/2026-07-19-branding-plan.md` → **SPECIAL_CASE: archive + data promotion**

- **Destinations:** `docs/archive/plans/2026-07-19-branding-plan.md` (the plan body, with an
  executed-as header), **plus** the brand table and BD3's do-not-revert rule promoted into
  `docs/ARCHITECTURE.md`.
- **Why split rather than plain archive:** BD3's exact contrast ratios carry a **standing
  do-not-revert rule** — a deliberate WCAG deviation that a future contributor will otherwise
  "fix". A file whose line 2 reads "Status: planned, not started" is the weakest possible home for
  a standing rule. The plan itself is history: executed the same day as Session 22.5, with
  BD1–BD5 = D-065–D-069.
- **Extract first (before archive):** (a) the brand table (fonts, colors, gradient, geometry);
  (b) BD3's do-not-revert rule with the **as-shipped** ratios sourced from D-067 and
  `packages/ui-brand/tokens.css` — green `#387e40` (4.97:1) and pink `#c22f73` (4.88:1 on `--bg` /
  5.32:1 on `--panel-bg`); the plan's own `#d13a80` (4.54:1 on white) was superseded by D-067 as
  **a real fail (4.16:1) on `--bg`** and must not be promoted — the archived plan's header states
  this; (c) the "the site's dark CSS is Impreza defaults, not brand truth" ruling, which is the
  reason the table exists; (d) the outstanding org ask — request an SVG logo original (raster soft at
  large sizes; display ≤150px from the largest source) — is added to the org-asks tracking set;
  (e) the brand source-of-truth rule (live WordPress theme CSS; no re-scrape unless values look
  wrong).
- **Fix regardless of sequencing:** the line instructing readers to log decisions at "next free
  D-numbers — D-064 was the last used". The log is past D-423, so **following that instruction mints
  duplicate D-numbers**. Fix it even if the rest of the archive work waits.
- **Ordering:** the documents-only half (ARCHITECTURE + header + D-number line) is in scope for a
  documents-only migration. The `packages/ui-brand` token promotion is **engineering** and is split
  out — do not block the archive on it. The codebase-recon section describes deleted files and must
  be marked as an as-of snapshot, not "trust this".
- **Risk if migrated incorrectly:** R4.2 (HIGH) — a session executed the same day still reads
  "planned, not started", with no done/superseded marker, a duplicate-D-number instruction, and a
  standing rule hidden inside it. R3.6 — `docs/plans/` reads as "current plans". The rule itself is
  already held by KEEP_ACTIVE `DECISIONS.md` (D-067, titled 'do not "fix" back'); the promotion
  consolidates the brand data with its consumers rather than rescuing an otherwise-lost rule.

---

## 7. MOVE_TO_REFERENCE — inventoried documents (14 files)

Durable or frozen-but-load-bearing. These are read when their topic comes up, and every one of them
carries a banner stating what it is and when it was last true.

### 7.1 `docs/INCIDENT_RESPONSE.md` → `docs/reference/INCIDENT_RESPONSE.md`

- **Why reference, not active:** it is read when an incident happens — a trigger, not a session.
  That is the whole distinction; the content is otherwise first-rate. It uniquely owns almost all of
  itself: the PII-boundary triage rule, rotation commands including the `-replace` scoping trap, the
  D-310 lesson ("a safety claim in a comment is a hypothesis; measure it once"), scanner cautions
  (~97% health-check dilution) and the full D-400 cost-attribution procedure with measured
  baselines. It has the least overlap of any file in its cluster.
- **Extract first:** nothing. Three in-file fixes before the move: a **date/vintage header** (today
  a paragraph's vintage is inferable only from the D-number it cites); the **S34 tense fix** ("S34 …
  is where failure drills get built" — S34 shipped 2026-07-24); and **one D-152 freeze-context
  line**, because the runbook never mentions the freeze. The line is **scoped, in the manifest
  §2.B.1's required wording**: D-152 stops our integration actions; it does **not** mean the
  MySQL-adjacent tier is not a live exposure surface (the committed credentials in the local
  `../IntelliChoice-web` checkout are one) — triage severity unchanged.
- **Ordering:** before the move, grep this file for a `D-093 → D-137` routing on RDS rotation. The
  A1 register flags a **live operational hazard** if a runbook still routes an RDS rotation through
  the conflated remediation commands. That is a safety check, not cosmetics — do it first.
- **Risk if migrated incorrectly:** R4.7 (a reader concludes no DR procedure exists), R9.1 (the
  freeze is invisible in a document that tells you to touch production-adjacent systems),
  `DOC-VINTAGE-HEADERS`. Also `BATCH-LOW-OVERSTATEMENT`: the no-PII rule is stated here without
  D-050's four-column exemption — those four columns are correct and allowlisted, and the fix must
  not imply a PII violation.

### 7.2 `docs/QUESTION_GENERATION.md` → `docs/reference/QUESTION_GENERATION.md`

- **Why:** the design-of-record for the offline pipeline, and `CLAUDE.md` already requires reading it
  before touching `packages/curriculum`'s pipeline — a topic trigger, not a session read. Uniquely
  owns the pipeline stage graph, the `requested/proposed/reviewed` difficulty model with D-239's
  re-tier rule, the repair-feedback filter table, preflight fail conditions including the
  availability-vs-invocability distinction, run-metric definitions and D-223's per-topic volume
  rationale.
- **Extract first:** nothing leaves. Before the move: a `last updated` header; the **four dated
  strata** (2026-08-05 superseded roster, 08-06 pilot, 08-11 re-measurement, 08-12 "Current") are
  boxed or the 08-05 roster is moved to an appendix; the header decision list is advanced from
  D-194 to the body's actual horizon (~150 decisions of drift); and the **trailing "Next:"** naming
  Mistral Large 3 is evicted or dated — it is undated, it is the last thing a reader sees, and it is
  contradicted 180 lines earlier by the 08-11 re-measurement (Sonnet 4.5).
- **Ordering:** the D-342 parking banner at the top must survive the move verbatim (all
  coverage-driven generation runs are parked). Combine the as-of banner work with `CONTENT_COVERAGE`
  as one convention pass rather than two per-file decisions.
- **Risk if migrated incorrectly:** R1.6 (HIGH-adjacent MEDIUM) — the "superseded" 08-05 roster
  block holds present-tense imperatives with no visual containment, and a "Current, 2026-08-12"
  696-item block sits beside a superseded 127-item block separated only by bold prose. R4.6 (the
  stale imperative tail), R2.5 (the 189-item depth gap and the `difficulty_tiers` rule duplicated
  across three files with independent lifecycles — re-derived at least three times because the
  copies drifted).

### 7.3 `docs/HINT_SOLUTION_REVIEW.md` → `docs/reference/HINT_SOLUTION_REVIEW.md`

**This is the single most ordering-sensitive move in the migration.**

- **Why reference and not archive:** it **cannot** be archived. Its §3, §4.5b, §4.6, §6 and §9 rules
  exist nowhere else: the two-scorer diagnosis, the `PASS`/`REPAIR`/`REJECT` contract and why
  `run_llm_judge` cannot be reused, the deterministic-vs-LLM boundary, the five falsification checks
  with pre-registered disqualifiers and measured values, the "generator is not the repairer"
  measurement, the pre-registered stopping rule and the `hint_quality_score` disposition table.
  **Seven source files and two scripts cite it as normative.**
- **Extract first — reconcile before moving (HARD ordering):** the front page describes a pre-pilot
  world that no longer exists. The title says "design (D-251 → D-256)", the body reaches D-261, and
  there are **zero mentions of any D-262+ decision** although its subject moved the same day it was
  last touched (2026-08-10, D-262…D-269). Concretely: the header says the loop "is not built" while
  naming `review_loop.py` fifteen lines later; reviewer C is "measured" in one place and "does not
  yet exist" in another; §8 leaves steps 4 and 7 unticked though both completed 2026-08-10 (D-254 at
  29.1¢; D-252, 126 readings, minimum observed 2); three lines still assert
  `_HINT_QUALITY_REJECT_BELOW` "has never been measured". The correct wording is **"built but
  uncalled"**. Also correct the line citing `ai_pipeline.py:1769` for a constant that lives at
  `:834`.
- **Ordering:** reconcile to the D-262+ horizon **before** the file moves, for one reason: seven
  source files treat it as normative, so any window in which it sits in a "reference" directory with
  a wrong front page is a window in which a reader implements a superseded design. `CLAUDE.md`'s
  description ("the **planned** design") is fixed in the same pass. One sub-item is engineering, not
  documentation — three source docstrings (`review_loop.py`, `review_panel.py`,
  `hint_solution_repair.py`) carry the same stale claim; split that out if the migration is
  documents-only, but record it.
- **Risk if migrated incorrectly:** R5.6 — the front page is a pre-pilot description of a shipped
  instrument. R4.6 — §8's unticked "First paid step" whose results §5 already reports. The compound
  risk is the one that matters: this file is simultaneously the only source of five design rules
  *and* wrong about the state of its own subject. Archive it and the rules vanish; move it unfixed
  and it keeps teaching a superseded design to seven call sites.

### 7.4 `docs/U7_CHECKPOINT_CONSOLIDATION.md` → `docs/reference/U7_CHECKPOINT_CONSOLIDATION.md`

- **Why:** the measurements are durable and unique — the only staging checkpoint sizing anywhere,
  the bytes-by-phase table (completed sessions 1.7%, abandoned 77%, chat 19%), the five orphan
  `LearningState` fields, and the shared-tables constraint (a `phase=='completed'` job silently
  skips every chat thread). It also carries two corrections of other documents.
- **Extract first:** nothing leaves. Before the move: a **completion banner** pointing at D-333
  (or an explicit "historical working note" marker); annotate §9.2 as answered (`learning_sessions`
  is built, migrated, modelled, with a scheduled producer) and §10 as closed by D-336; **an as-of
  banner**; and an absolute date on every self-expiring claim (it says "nothing eligible for at
  least another 8 days" with no anchor date, and it was never edited after the day it was written,
  2026-08-14). One banner closes DRIFT-47, DRIFT-94 and DRIFT-95 together.
- **Ordering:** §9's four questions to the user must be dispositioned before the move — question 2
  was answered the same day the file was written (the table was built, D-332) and the file still
  asks it. This matters more than it looks: `PROGRESS.md` **gates session U7 on this file's §9**
  while the file is unindexed, so an unfixed §9 keeps a live gate pointed at an answered question.
- **Risk if migrated incorrectly:** R3.5 (the filename names an action §8.1 recommends **not**
  starting, and conveys nothing about what the file is), R4.6, R5.5, R2.5 (the checkpoint sizing
  differs ~17× from `OPEN_DECISIONS` #4's numbers with no cross-link — this is **not** a
  contradiction and must not be "resolved" by picking one: label the environment on each, dev
  ~4.8 GB vs staging ~285 MB), `DOC-SNAPSHOT-BANNERS`.

### 7.5 `docs/CONTENT_COVERAGE.md` → `docs/reference/CONTENT_COVERAGE.md`

- **Why:** the taxonomy facts are worth keeping — the 246→245 denominator and duplicate triple, the
  books→topics / rows→skills mapping, the eight measured `derive_answer` outcomes, the family split
  173/37/34/1, and the grade-band-ordering trap with its pinning test. The status columns are not.
- **Extract first:** nothing leaves. **An as-of/superseded banner is mandatory**, not optional: the
  status columns describe needs built the same day or since (the Phase R router, figure support,
  `place_value_compare`, 4→7 grade bands, bank size 47/30/28/25 against 958+), so a reader following
  them would rebuild an existing router or re-author fixed items. Also drop or requalify the
  `selection` "answer-model family", which is not a distinct answer model.
- **Ordering:** annotate the `C1` label collision at the same time (this file's "C1" is the 08-11
  taxonomy-seeding session, not S17's chat-content session). Record the process recommendation
  rather than deferring it: **nothing regenerates this file**, so it should be regenerated as part
  of the pipeline change (`scripts/build_content_coverage.py`) instead of hand-patched.
- **Risk if migrated incorrectly:** stale HIGH per the A3 profile, R2.5 (taxonomy figures stated
  verbatim in three files with independent lifecycles), R6.4 (the C1 collision),
  `DOC-SNAPSHOT-BANNERS`, `BATCH-LOW-UNMARKED-SPEC`.

### 7.6 `docs/FIRST_VISIT_NOTICE.md` → `docs/reference/FIRST_VISIT_NOTICE.md`

- **Why:** unconsumed input to unstarted work (S45). It uniquely owns the only written copy for all
  eleven §5.1.2 disclosures, the register-split rule, the retention table with per-clock columns,
  the no-implied-erasure rule, and the ship-eight-not-eleven recommendation. It is read at S45
  start, which is a trigger.
- **Extract first:** one item must be lifted **out**: the open product decision it names — the three
  §5 gaps needing a product judgement before S45 — is tracked in **no** decision-tracking document.
  That becomes the UD-10 pointer in `PROJECT_STATE`'s open-user-decisions table. The file keeps the
  copy; `PROJECT_STATE` keeps the fact that a decision is owed.
- **Ordering:** the S45 label ambiguity is a **prerequisite** for stating who owns this file's
  obligations — "Owner: S45" resolves to either ROADMAP's unstarted consent session or PROGRESS's
  completed unnumbered "S45". Disambiguate before assigning ownership. Every "True because" row is
  a dated code measurement and must be re-verified at S45 start; say so in the banner rather than
  re-verifying now.
- **Risk if migrated incorrectly:** R5.7 (the **inverse** class — a genuinely open item that looks
  closed, or rather is tracked nowhere), R6.4 (the S45 collision), R7.1 (absent from `CLAUDE.md`),
  R2.6 (retention windows are triple-stated across this file, D-114/D-333 and the purge CLIs).
  If moved to reference without the UD-10 pointer, the only record that a product decision is owed
  sits in a file nobody reads until the session that needs the decision already started.

### 7.7 `docs/INTEGRATION_PLAN.md` → `docs/reference/integration/INTEGRATION_PLAN.md`

- **Why reference:** it is the only place several things exist — the Tier 0/1/2 taxonomy (the sole
  definition of "what counts as touching production"), the auth option matrix O1/O1b/O2–O4 with
  coupling-surface reasoning, the I1–I15 catalog with resolutions, the §4 accepted-reduced-scope
  table, the §7 R8/R9 accepted risks **with their expiry conditions**, the nine §2.6 gate criteria
  (which `TRACEABILITY.md` is evidence *for*), and §8's `attendanceClaimed` fail-open trap. It is
  frozen, not obsolete: it is exactly what gets read the day the user reopens integration.
- **Extract first — two obligations:**
  1. **A D-152 freeze banner at line 1**, mandatory. `D-152` appears **zero times** in 626 lines,
     and read standalone the document directs all four forbidden actions: measure AWS→icrest
     reachability, send Tier 1 org asks, finalize the §3.1 auth option, and align the adapter with
     production's schema.
  2. **The §7-R8/R9 expiry conditions are single-homed.** They land in `PROJECT_STATE`'s parked
     section (with reopen conditions inline) and `ARCHITECTURE.md`'s two restatements are reduced to
     pointers or carry the expiry text. Consider making the expiry **mechanical** rather than prose.
- **Ordering:** apply `S42_DISCOVERY.md`'s **two corrections** to this file in place during the same
  pass (R6.5): today the corrections live only in the correcting document, and the uncorrected copy
  is the one a session reads first — and the corrected facts are production-system facts. Mark §2
  historical, reduce §5's session table to a pointer at `ROADMAP_FROZEN_SESSIONS.md` (ROADMAP has
  newer statuses), and fold §1 with §8 so §8's by-reference patches stop patching unedited text.
- **Risk if migrated incorrectly:** R4.1 (HIGH) — **the most consequential single finding in the
  corpus**: the guard and the temptation are not linked in either direction. R2.2 (HIGH) — the
  expiry-carrying copy is the unindexed one. R9.1 (HIGH), R7.2 (it declares outbound drafts
  gitignored and not committed while three committed drafts exist), R6.6. Moving it into a
  `reference/integration/` directory *without* the line-1 banner is strictly worse than leaving it
  where it is: the new path implies curation, which reads as endorsement.

### 7.8 `docs/S42_DISCOVERY.md` → `docs/reference/integration/S42_DISCOVERY.md`

- **Why:** §0–§6 are the largest block of production facts in the repo and there is no substitute —
  exact API contracts, role facts, the schema-drift mechanism, the three-way timezone split, §6's
  security findings, and the production-vs-dev-fake mismatch table, all produced by an adversarial
  verification method (8 CONFIRMED, 2 REFUTED-with-correction). `CLAUDE.md` already directs readers
  here before assuming anything about production.
- **Extract first:** a **freeze banner**, plus **section-level supersession tombstones on §7–§9**.
  §7's org asks are superseded by `S42_OPEN_QUESTIONS.md`'s groups; §8's auth recommendation (O1b)
  is demoted to a recommendation-until-measured; §9's "every row below must be fixed" is now
  **prohibited** — a reader obeying §9 violates `CLAUDE.md`.
- **Ordering:** add the forward pointer to `S42_OPEN_QUESTIONS.md` here. This is the R6.5 defect in
  its purest form: supersession runs *opposite* to citation direction — OPEN_QUESTIONS supersedes
  DISCOVERY §7 while citing DISCOVERY as its evidence base, and DISCOVERY (the `CLAUDE.md`-indexed
  one) carries no forward pointer. Do the freeze banner and the forward pointer in one pass per
  file, together with §7.7's correction propagation.
- **Risk if migrated incorrectly:** R4.4 (HIGH), R6.5, R9.1, R2.4 (its §6 findings are one of four
  copies of the same four production security findings). The header also says the runtime half is
  "still owed" when it is frozen. It is pinned to the 2026-08-01 checkout against a database that
  ALTERs on every boot — its own finding — so the banner must state the checkout date and that
  group-B2 (deployment-matches-source) must be verified before the facts are trusted at integration
  start.

### 7.9 `docs/S42_OPEN_QUESTIONS.md` → `docs/reference/integration/S42_OPEN_QUESTIONS.md`

- **Why:** the freeze model citizen. It is the only S42 file where the D-152 freeze is visible
  *in the file itself*, and it uniquely owns the freeze rationale in operational form, the
  resolved-items ledger, the re-entry protocol, and the warning that group B2 must precede trusting
  `S42_DISCOVERY.md`. Its urgency labels are explicitly relative to integration start, not to now —
  the discipline the rest of the corpus lacks.
- **Extract first:** two cheap repairs. **Annotate the resolved rows in-table** (C1/C2/C3/C8 remain
  full rows, with C3 still at 🔴 "미룰 수 없음", after the same file's own ledger declares them
  closed), and **point the E-group at `S42_SECURITY_REPORT.md`**. Do not blanket-retire the line
  instructing that the C3 ask be sent — its E-group notification half is still valid; retire only
  the answered C3 half.
- **Ordering:** its ⛔ banner shape is the **template** for the freeze banners the other files need
  (§14, R9.1), so this file is read before those banners are written, and it is not restructured in
  a way that loses the template. Korean-language file: the banner and annotations stay in Korean to
  match, with the freeze statement matching `PROJECT_STATE`'s canonical wording in substance.
- **Risk if migrated incorrectly:** R5.3 (resolved items tabled as open, one marked "cannot be
  deferred"), R2.4, R6.5. It also holds three mutually contradictory statements in 121 lines, so a
  partial fix can easily leave the contradiction intact while looking addressed.

### 7.10 `docs/S42_SECURITY_REPORT.md` → `docs/reference/org-drafts/S42_SECURITY_REPORT.md`

- **Why:** the only S42 work item that legitimately survives the freeze — it is the freeze's designed
  exception (a courtesy hand-off to the production operator, not an integration action). It uniquely
  owns the maintainer-addressed Korean form of the four findings, the non-accusatory framing rules,
  the ported check-old-rows recommendation rescued from the deleted `docs/SECURITY_REPORT_TO_ORG.md`,
  and the rule never to quote the source-visible secret literals.
- **Extract first:** **a send-status line** (fixes half of R5.7). The file has no send-status field,
  so "unsent" is indistinguishable from "sent and unlogged" — and it appears still unsent as of
  drafting on 2026-08-02. Add an index entry so it stops being untracked, and record that severity
  gates on still-unknown runtime facts, so a re-verification step is owed if the operator changed
  anything in the intervening weeks.
- **Ordering:** this file is the **declared winner** among the four copies of the four security
  findings (R2.4). Declare that in `CLAUDE.md`'s index — today the index points at
  `S42_DISCOVERY.md` instead, which is how the collision recurs after a fifth copy was already
  deleted to settle it. Its credentials-mention policy is deliberately the *opposite* of the org-asks
  drafts'; preserve both policies and state that the difference is intentional.
- **Risk if migrated incorrectly:** R5.7, R2.4, R7.1, R7.2. The specific failure to avoid: filing
  this under `org-drafts/` with the other outbound text and letting a reader conclude the whole
  directory is frozen. It is not — this one is live, permitted, and waiting on a human.

### 7.11 `docs/ENROLLMENT_FAQ_APPROVAL.md` → `docs/reference/org-drafts/ENROLLMENT_FAQ_APPROVAL.md`

- **Why:** active until the org answers, then archived with the outcome — and "until the org answers"
  is an external trigger, which is what `reference/org-drafts/` is for. It uniquely owns the four
  claims and their exact ask, the flip procedure (manifest `draft → approved`, re-run
  `make knowledge-load`), the routing rule (do not bundle with the security report), and the claim
  that it is **the only launch-checklist item gating the guest journey's canonical question**.
  Verified still pending: the manifest is still `draft`.
- **Extract first:** the sole-gate claim goes into `PROJECT_STATE` as a one-line blocked/external
  row (owner: external-org, `INT-29-FAQ`), because a launch gate must be visible from the entry
  point. Fix the two dead pointers before the move: the manifest line-number pointer and the
  instruction to sync a `knowledge-content copy/` directory deleted by D-253.
- **Ordering:** the `PROJECT_STATE` row and the `CLAUDE.md` index entry land together — the defect
  here is not the content but its invisibility. No ordering dependency on any other file.
- **Risk if migrated incorrectly:** R7.1 (a sole launch gate invisible at session start), R7.3
  (dangling refs), R7.2. Its own staleness risk is LOW-MED, which makes it the easiest of the 26 to
  get right and the easiest to forget.

### 7.12 `docs/AUDIT_FINDINGS.md` → `docs/reference/audits/AUDIT_FINDINGS.md`

- **Why:** a frozen register with an archival core, but reference on the strength of what only it
  holds: reproduction recipes and raw measurements per finding, **negative results** (the only record
  of what was checked and found correct), measurement-method corrections, measured constants and
  threshold sweeps, capacity curves, and the `AUDIT_FINDINGS.md:AUD-L-17` → `AUD-L-19` ID-collision
  history. 5,822 lines; frozen 2026-08-05 by D-183.
- **Extract first:** an **as-of banner stating the freeze date and scope** (Phase 0A, S36–S39 plus
  continuations) and **successor pointers** — it sits beside two dated successor audits and mentions
  neither. A status-column disclaimer on the Index: its "0 open" reads project-wide but is true only
  of this register, while the 08-16 and 08-17 audits filed 46 and 48 findings in separate
  namespaces. Add one §7-style residual-risk line for `AUDIT_FINDINGS.md:AUD-C-23` recording
  "measured <26%, not certified" — and do not "improve" the recall reporting by dropping the
  negative controls (D-221: protect precision over recall, and score both directions).
- **Ordering:** `reference/audits/README.md` exists **before or with** this move (§7.15). Also
  execute ROADMAP's anchored awk and record the **actual** output rather than carrying the
  hand-maintained count line that has been wrong three times; verify every Index section now has a
  row, and confirm the four extra-pipe rows keep status in field 5.
- **Risk if migrated incorrectly:** R3.4 (undated, unscoped name for a scoped frozen register),
  R5.4 (residual open-looking strata: `AUD-F-27`'s heading says both "✅ fixed" and "not fixed";
  "Status: open, Phase 0B" bullets inside closed entries; known-wrong "Fix shape (Phase 0B)" blocks
  retained verbatim), R6.3 (HIGH), R8.1, R8.3 (the Index is split into six fragments by stray blank
  lines with dangling `Original: |` cells, which breaks naive parsers — do not "fix" this by
  reflowing without checking what parses it).

### 7.13 `docs/AUDIT_2026_08_16.md` → `docs/reference/audits/AUDIT_2026_08_16.md`

- **Why:** two durable assets outlive its status lines — the **§1 symmetry-drift table** (seven
  fixes shipped in one app and never ported to the sibling), which is a standing class of defect for
  a two-app codebase, and the **§6 process lesson** ("a check that is correct and no longer checks").
  The ten P1 narratives with `file:line` evidence are the reproduction record.
- **Extract first:** an as-of banner. Its "Still open" lines were overtaken by D-397→D-423 and its
  §3/§4 P2/P3 lists carry no status marks at all. Its own 08-17 update already corrects its own
  count ("was **22**, not the 15 stated above") — that self-correction is kept, not tidied away.
- **Ordering:** after `reference/audits/README.md`. Its ID scheme (`P1-1`…`P1-10` plus unnumbered
  prose) is the third of three and must be named in the namespace map.
- **Risk if migrated incorrectly:** R1.7 (audit documents patched by blockquote strata, unevenly),
  R6.3. If the status lines are neither dated nor disclaimed, a reader re-fixes items closed by
  Milestones 13–15.

### 7.14 `docs/AUDIT_LIVE_2026_08_17.md` → `docs/reference/audits/AUDIT_LIVE_2026_08_17.md`

- **Why:** the live-walk finding catalogue over deployed build `gha-6841d9d9b169` (D-381), and the
  corpus's best-maintained audit. It uniquely owns the **green-suite-with-live-P1s coverage lesson**
  and the three blind spots — nothing terminal ever completed, every approval declined and never
  approved, every failure injected client-side — plus the reasoned non-actions
  (`AUDIT_LIVE_2026_08_17.md:AEL-06`, `AUDIT_LIVE_2026_08_17.md:AUD-CHAT-05`). `CLAUDE.md` already
  tells readers to read its coverage section before adding tests. It is the only audit document in
  the current index.
- **Extract first:** an as-of banner naming the **build SHA**, and closure marks on the residual
  still-open tail partly overtaken with no in-file marks (`EDGE-CHAT-07`,
  `AUDIT_LIVE_2026_08_17.md:AUD-L-09`, `AUDIT_LIVE_2026_08_17.md:AUD-L-10`/`AUD-L-11`,
  `AUD-CHAT-14`; the never-exercised list was closed elsewhere by D-391/D-392→D-399/D-398 without
  updating the file).
- **Ordering:** after `reference/audits/README.md` — this is the file that makes the namespace map
  necessary, because it **reuses the entire `AUD-L-01`…`AUD-L-19` range with unrelated meanings**,
  including the very ID that was renumbered because of a previous collision. Its live numbers
  predate the current HEAD, so the banner also carries the LB-05 discipline: state the build SHA
  beside every live number.
- **Risk if migrated incorrectly:** R6.3 (HIGH), R1.7. The specific trap: a bare `AUD-L-09` cited
  from anywhere resolves to two different findings in two registers. No mechanical re-map exists,
  because the earlier renumber was applied per-reference with ranges deliberately left ambiguous —
  so the fix is the citation rule, never a renumber.

### 7.15 New file: `docs/reference/audits/README.md` `[new]`

Not a role assignment — a file the migration creates. It holds the ID-namespace map for the three
registers and the corpus-wide rule: **never treat a bare audit ID as uniquely identifying one
finding; always cite `<document>:<id>`.** Fix early — every cross-document finding lookup after
2026-08-16 is ambiguous until it exists, and the reconciliation corpus must adopt the rule too.
Directly closes R6.3 and unblocks §7.12–§7.14.

---

## 8. ARCHIVE — inventoried documents (5 files)

Historical record. Each gets the §15.1 banner. **None is deleted**, and two are renamed with their
original filename recorded in the banner.

### 8.1 `docs/PROGRESS.md` → `docs/archive/PROGRESS.md` — **plain ARCHIVE**

- **Why plain archive:** this is the project's history of record — 16,690 lines of per-session
  verification transcripts and carry-over ledgers back to S0 — and `PROJECT_STATE.md` replaces its
  live function by design. The A3 profile proposed a split (active current-status block + archived
  log), but **Phase 4 already performed that extraction**: the register's `ACTIVE_REMEDIATION` (16)
  and `ACTIVE_IMPLEMENTATION` (11) entries plus the deferred/parked/unknown sets are exactly the
  live items the "Current status" block held. What remains after that is history.
- **Verification step, not extraction (the distinction matters):** before the move, confirm that
  each of PROGRESS's freshest live items has a register key, and a `PROJECT_STATE` row **iff** its
  disposition is an open one (`SNS-CONFIRMATION` and `WORK-04-ANSWER-CACHE` are RESOLVED and
  correctly have no row) —
  `SNS-CONFIRMATION` (resolved: both topics confirmed, zero pending account-wide),
  `WORK-04-ANSWER-CACHE` (resolved by D-423's numbers; the decision also lives in `DECISIONS.md`
  D-423's body — PROGRESS is a surviving copy, not the sole home), `LB-05-DEPLOY-GAP` (the staging
  deploy gap), the standalone
  2026-08-07 carry-over, and the four-row queued block claiming C8 is "⏳ next" with "168 of 494"
  files against ROADMAP's done/168-of-437. If any item has no register key, **capture it first**;
  otherwise archive. Retire or date the whole four-row block, not one line of it.
- **Ordering:** archive **after** `PROJECT_STATE.md` exists (a banner may not point at a file that
  does not exist — guaranteed by manifest step 0a), and after the verification sweep above. The "Next session" pointer — the
  project's actual post-gate sequencer — must have a successor before this file stops being read;
  that successor is `PROJECT_STATE` §work sections, updated in place.
- **Risk if migrated incorrectly:** R1.1 (HIGH) — the block meant to be current state is a
  newest-first stack ~1,800 lines deep in which the same metric reads 4-of-112, 102-of-112 and 497
  at different depths. R8.1, R8.3 (a duplicate `### S20` heading), R2.3, R5.7 (the answer-cache
  conclusion needed an owned record — verified: D-423 carries it). The failure mode is the opposite of the obvious one: the danger is
  not losing history, it is archiving a live item because it looked like history.

### 8.2 `docs/OPEN_DECISIONS.md` → `docs/archive/OPEN_DECISIONS.md` — **ARCHIVE**

- **Why:** all 14 items are answered or parked, confirmed by its own two banners (the 2026-08-14
  D-322 note and the 2026-08-18 D-417 "✅ Nothing in this file is awaiting a decision"). What it
  uniquely owns is genuinely valuable but genuinely historical: the **option space** and the
  recommendation-vs-outcome divergences for 14 decisions — `DECISIONS.md` records what won, this
  records what else was on the table and why the recommendation lost in three cases — plus the
  meta-lesson "a status line is a measurement with an expiry date".
- **Extract first:** nothing needs extracting; three annotations are owed *at* archive so the
  archived record is not itself misleading: mark item #8 (D-310) **superseded-operationally** rather
  than leaving it ⏸ UNCHANGED, because as written it tells the next reader that the exposure is
  live; date D-419's ⚠️ `PendingConfirmation` block as resolved; correct D-419's NAT sentence. Also
  correct the "D-401 and D-406 stay unapplied" line (both applied, proven by AWS resource
  existence), the "staging numbers nobody has read" line (read 2026-08-14), the "answered on
  2026-08-14" banner (items 11–14 were decided 08-17/08-18), item #6's "parked" against PROGRESS's
  "blocked on the YouTube key", and item #10's `formatDateLabel` symbol name.
- **Ordering:** `CLAUDE.md`'s description of this file is fixed in the same pass or earlier (§6.1).
  A rename was considered and rejected: the filename is not the stalest thing about it — the
  description in the always-loaded file is — and archiving under the original name keeps the
  citation **text** in `DECISIONS.md` and `PROGRESS.md` stable. Note the links themselves still
  break (the path changes to `docs/archive/`): every inbound reference from the surviving files is
  repathed at manifest step 9a(ii), and the mid-file-landing hazard on these two high-traffic
  archives (banners are top-of-file; grep lands mid-file) is accepted and recorded.
- **Risk if migrated incorrectly:** R3.2 (HIGH) — line 1 says "Open decisions", line 8 says nothing
  is awaiting a decision. R5.1 (HIGH) — `CLAUDE.md` compounds it. R5.5, R7.1. The pattern this file
  exhibits is the one its own text warns about: **a closed record left in the active read path**.
  Archiving it is the structural fix; fixing only the description leaves the trap one edit away from
  returning.

### 8.3 `docs/FINAL_ARCHITECTURE.md` → `docs/archive/2026-07-21-final-architecture-projection.md` — **ARCHIVE, renamed**

**This carries the migration's single hardest ordering constraint.**

- **Why archive:** it is a self-dated 2026-07-21 projection of the system after S32–S34, 10× smaller
  and three weeks older than `ARCHITECTURE.md`, with zero functional inbound references. Nearly
  every status claim in it is false, and it loses every disagreement it is in. It even carries its
  own retirement instruction, whose trigger fired on 2026-07-22 (R6.6).
- **Why renamed:** it is the audit's misleading-filename exhibit. "FINAL" reads as latest and
  definitive; the new name states what the document is (a dated projection) and when it was true.
  The banner records `Original filename: docs/FINAL_ARCHITECTURE.md`.
- **Extract first — three extractions, all before the rename/archive (HARD ordering):**
  1. **The topology diagram** (`FINAL_ARCHITECTURE.md:46-105`) — the **only end-to-end deployed
     topology diagram in the repo** — refreshed against current deployed state, into
     `ARCHITECTURE.md`.
  2. **Open question 5: the SPEC §5.33.3 six-schema logical split** (`learning`, `rag`, `memory`,
     `checkpoint_learning`, `checkpoint_chat`, `evaluation`). Destination per design spec §11.2: a
     new **"Open architecture questions (undecided — do not treat as designed)"** block in
     `ARCHITECTURE.md` holding one entry, with reopen condition = production schema design, **plus**
     a one-line row in `PROJECT_STATE` §deferred (register key `ARCH-21-SCHEMA-SPLIT`).
     **No new decision is created** — the point is to preserve an *unmade* decision, not to make it.
  3. **The one-line as-built fact** "today's system is one `intellichoice` Postgres database", which
     is asserted only in this stale projection, into `ARCHITECTURE.md`.
- **Why extraction 2 is a hard constraint:** `FINAL_ARCHITECTURE.md:179-180` is, per the A1 register
  §5.4 and the A3 inventory independently, **the only record anywhere that this decision is unmade**
  (SPEC §5.33.3 still *prescribes* the split as a requirement; TRACEABILITY's §5.33 row gains a
  deferred-not-traced sub-row at step 2 so the two active files cannot disagree).
  `OPEN_DECISIONS.md` declares nothing open, `ARCHITECTURE.md` never mentions a schema split, and no
  D-number owns it. The repository confirms no split is implemented (`packages/db/alembic/env.py`
  has no `include_schemas` and no `schema_translate_map`) and the deployed Postgres runs without it.
  Archive this file before extracting, and an unmade decision disappears from the corpus entirely.
  It was excluded from the user-decision queue deliberately — "never" is defensible at one database
  and ~1,000 MAU — so it is **low urgency and high loss-if-dropped**, which is exactly the profile
  that gets lost in a migration.
- **Ordering:** extractions 1–3 → verify they are present in `ARCHITECTURE.md` and `PROJECT_STATE`
  → then rename and archive. State the architecture hierarchy in the survivor (`ARCHITECTURE.md`)
  and in `CLAUDE.md`'s index in the same pass, or R2.1 simply reappears in a new form. Adopt F-07's
  split when writing the banner: this file is "behind on session provenance", but the claim that
  `ARCHITECTURE.md` is "behind on decisions" is **false**.
- **Risk if migrated incorrectly:** R3.1 (HIGH), R2.1 (HIGH), R5.2 (HIGH **and** its inverse) —
  four decided questions presented as live, including D-004 still marked "proposed" six days after
  it was accepted, sitting indistinguishably beside the one question that really is open. R6.6. The
  compound risk is precisely what makes ordering non-negotiable: one live item hidden among four
  dead ones, in a file that is otherwise safe to throw away.

### 8.4 `docs/S42_ORG_ASKS.md` → `docs/archive/2026-07-24-org-asks-drafts.md` — **ARCHIVE, renamed**

- **Why archive:** the highest staleness of the entire S42 set. It **predates S42 despite its
  filename** — drafted at S36 close-out on 2026-07-24, cut down 07-25, last amended 07-31 — and
  D-151/D-152/D-153 are entirely absent. Message A remains owed before S43 opens (frozen by D-152)
  and Message B before S48 — pending, re-arms at integration reopen; only Message C's hold-until-S42
  release condition can no longer arrive as written, and Message D prices a purchase that was
  withdrawn.
- **Why renamed:** the `S42_` prefix asserts a session the content predates. The new name is dated
  by authorship, and the banner records `Original filename: docs/S42_ORG_ASKS.md`.
- **Extract first (before archive):** **preserve the message text verbatim** — it is the only
  send-ready outbound text for these asks, and the Korean text in particular is not reproducible
  from any other file — and **stamp per-message D-153 dispositions at the top** so no reader can
  reach a "Send now" marker without first reading that the ask was answered, demoted or withdrawn.
  Keep the one-ask-per-message rule, the deliberate exclusion of the committed-credentials topic
  (deliberately opposite to `S42_SECURITY_REPORT.md`'s policy — say so), and the corrected DST
  arithmetic note.
- **Ordering: sequence this FIRST among all freeze-banner work.** It has the corpus's purest
  wrong-action consequence — three live "Send now" instructions for questions the org has already
  answered. Every other freeze defect misleads a reader; this one gets an email sent to the
  customer. Everything else in the migration can wait behind it.
- **Risk if migrated incorrectly:** R4.3 (HIGH), R3.3, R9.1 (HIGH), R7.2. Archiving it *without*
  the per-message dispositions is the worst outcome: the banner says "historical", the reader scrolls
  to a table that says "Send now", and archive banners are exactly the thing readers skim past.
- **Tracking status:** the file is **gitignored and untracked** (`.gitignore:67`; "deliberately never
  committed" per PROGRESS). The rename updates `.gitignore:67` to the new archive path in the same
  commit and the file **stays untracked** — whether outbound drafts are ever committed is UD-12(f)
  and is not decided by a rename.

### 8.5 `docs/plans/2026-07-18-expansion-plan.md` → `docs/archive/plans/2026-07-18-expansion-plan.md` — **ARCHIVE**

- **Why:** dated 2026-07-18 and fully executed as S17–S28 (shipped 07-19/20), with ~30 sessions of
  history on top. It survives as the full design reference behind the expansion — the task→session
  map with the D-049 renumber, the ten architecture calls, and design rationale no other document
  restates in full. **ROADMAP still tells readers to "read the plan rather than re-deriving"**, which
  is why deletion is not an option even beyond the archive-never-delete rule.
- **Extract first:** nothing leaves. What the header must state: executed as S17–S28; §1 is an
  as-of-2026-07-18 snapshot whose "Does not exist" claims are all long false; §19's unresolved
  decisions are all closed; the `effective_from: 2026-08-01 (future)` premise has inverted; and
  **the file still says Mongo** in two places because `docs/plans/` was excluded from the D-111
  MySQL sweep without being marked historical. Resolve its internal authority tangle in the header:
  two lines claim to supersede ROADMAP S17 while line 5 names ROADMAP its source of truth.
- **Ordering:** the header lands before or with ROADMAP's pointer repoint (§6.2), so the pointer
  arrives at a file that announces itself as executed history. No dependency on the branding plan.
- **Risk if migrated incorrectly:** R1.8 — §1 is a present-tense snapshot 87 lines below the saving
  status line, which is not close enough to protect a skimming reader. R3.6, R7.3, R6.4 (its own
  session-label usage feeds the C1/S43 collisions). The Mongo references are the clearest possible
  demonstration of why an archive banner must be at the **top**: a reader who greps for "Mongo" lands
  mid-file, with no vintage marker in sight.

---

## 9. The reconciliation artifacts (15 files)

`docs/reconciliation/` was created 2026-08-19/20 as this audit's own output: 15 files, 23,262 lines,
~2.32 MB — 25% more files than the entire inventoried corpus and roughly a third of its volume. It
is currently uncommitted (`?? docs/reconciliation/`) and **entirely absent from `CLAUDE.md`'s
index**, i.e. it reproduced R7.1 the day it was created. Two of the 15 are live registers; 13 are
point-in-time evidence.

**All 15 must adopt R6.3's source-qualified citation rule** (§7.15): the reconciliation corpus cites
audit IDs heavily and is subject to exactly the same ambiguity it documents.

### 9.1 MOVE_TO_REFERENCE — the two live registers (2 files)

Destination: `docs/reference/reconciliation-2026-08/`.

| file | lines | why reference, not archive |
|---|---|---|
| `FINAL_OPEN_WORK_REGISTER.md` | 7,418 | **The provenance backbone.** 166 entries across 11 dispositions, merged from 349 source items, with a Justification field on every adjudicated override. `PROJECT_STATE` carries one line per open item and links here for detail; every `ACTIVE_REMEDIATION` / `ACTIVE_IMPLEMENTATION` / `DEFERRED` / `PARKED_BY_DECISION` / `UNKNOWN` row is keyed to an entry here. Load-bearing until the items close. |
| `USER_DECISION_QUEUE.md` | 1,006 | The full UD-1…UD-12 option analyses — the material behind `PROJECT_STATE`'s one-line-per-question table (question, blocks?, default safe action). A user answering UD-5 needs the options, not the summary. |

- **Extract first:** nothing. Both need an **as-of banner** (reconciliation date 2026-08-20, repo
  HEAD `344f016`, deployed staging `gha-44a12dfc9549`) and a line stating that they are point-in-time
  registers whose entries close over time — the register is provenance for *why* an item is open, and
  `PROJECT_STATE` is the authority on *whether* it still is — plus one sentence of precedence: *the
  register is authority for why an item was opened; `PROJECT_STATE` is authority for whether it still
  is* (AUTHORITY_MODEL §4.7).
- **Ordering:** these move at migration, not before; `PROJECT_STATE.md` is written against them
  first. Two internal corrections the register records rather than drops: `OPEN_DECISIONS.md` #8 must
  read superseded-operationally, and `DEPLOYED_INFRA_DRIFT_REGISTER.md`'s §3.2 row still listing
  RD-02 as a user decision is superseded by its own addendum; RD-02's **in-entry** "Genuine decision
  required?" field (below its resolution addendum) receives the same superseded annotation as the
  §3.2 row, with the resolution stamp as the entry's last line.
- **Risk if migrated incorrectly:** if these are archived with the other 13, every `PROJECT_STATE`
  work row points into `archive/` — and §15.4's rule is that nothing in `archive/` is linked as
  normative. That would either break the rule or strand the detail. Conversely, treated as *active*
  rather than reference they become a second `PROGRESS.md`: an accumulating list nobody prunes.
  Reference with an as-of banner is the only position that holds.

### 9.2 ARCHIVE — the 13 evidence and register artifacts

Destination: `docs/archive/reconciliation-2026-08/`. All keep their original filenames (they are
already dated by directory, and their names are cited across the Phase-5 outputs).

| file | lines | what it is | archive note |
|---|---|---|---|
| `DOCUMENT_INVENTORY.md` | 914 | The 26 per-document profiles this model is built on | Superseded for *decisions* by this DOCUMENT_MODEL; retained as the evidence for them |
| `DOCUMENTATION_RISK_REGISTER.md` | 487 | The 49 risk entries (R1.1…R9.1) | Superseded for *countermeasures* by §14; retained as risk evidence. Note its own summary-line arithmetic errors (§1) |
| `CLAIM_LEDGER.md` | 3,958 | 70 claim rows with leading status | Point-in-time claim adjudication |
| `DECISION_SUPERSESSION_MAP.md` | 2,322 | 29 supersession chains + 6 phantom IDs | Feeds `DECISIONS.md`'s ID index; chain G6 closed cleanly, no register entry needed |
| `REPOSITORY_STATE_EVIDENCE.md` | 2,366 | Raw repo-state evidence | Evidence base for `REPOSITORY_DRIFT_REGISTER` |
| `REPOSITORY_DRIFT_REGISTER.md` | 1,230 | DRIFT-01…DRIFT-102 (HIGH 8 / MED 45 / LOW 49) | Every drift ID maps to an owning register entry |
| `LOCAL_EXECUTION_EVIDENCE.md` | 855 | Local run transcripts | Evidence base for `LOCAL_EXECUTION_FINDINGS` |
| `LOCAL_EXECUTION_FINDINGS.md` | 810 | F-01…F-17 plus §4/§5 rows (29 rows) | Includes the F-07 and F-17 corrections carried into §5.2/§5.4 |
| `DEPLOYED_INFRA_STATE_EVIDENCE.md` | 633 | Live AWS reads | Evidence base for the deployed-state layer |
| `LIVE_BEHAVIOR_FINDINGS.md` | 541 | LB-01…LB-09 plus residuals (13 rows) | Source of the LB-05 build-SHA discipline |
| `DEPLOYED_INFRA_DRIFT_REGISTER.md` | 435 | RD-01…RD-12 | RD-01's mechanism and one-line fix options carry into `PROJECT_STATE` §known-drift |
| `LIVE_BEHAVIOR_EVIDENCE.md` | 166 | Live-behaviour transcripts | Very long lines; the line count understates its mass |
| `REMEDIATION_D310_ROTATION.md` | 121 | The D-310 rotation record | **Resolved historical remediation — see below** |

- **Extract first:** nothing leaves these files, with one named exception —
  `REMEDIATION_D310_ROTATION.md`'s three residual routings and its standing-framing line, specified
  in the manifest §2.G.3. Their load-bearing conclusions were already lifted
  into `FINAL_OPEN_WORK_REGISTER.md` (349 source items → 166 entries, each mapped to exactly one
  owning entry and verified by the §11 coverage tables). That mapping is what makes plain archival
  safe here and unsafe for, say, `FINAL_ARCHITECTURE.md`.
- **`REMEDIATION_D310_ROTATION.md` — archived explicitly as a resolved historical remediation.** Its
  banner must say so in words: the rotation was **executed 2026-08-20T03:20:57Z**, both services
  force-redeployed and stable by 03:24Z with no pre-rotation task surviving; a behavioural probe
  through CloudFront returned 200 with the new secret and 404 for a wrong literal and for a missing
  header on both apps (fail-closed intact); post-apply `terraform plan -detailed-exitcode` returned
  0; old versions were destroyed, not deprecated. **D-310 is never to be presented as an active
  exposure.** `DECISIONS.md`'s D-310 chain gains a pointer to this archived record at migration.
  Its three surviving residuals are **not** archived with it — they live in `PROJECT_STATE` under
  `D310-RESIDUALS`: (1) any browser still holding the rotated value in `localStorage` now holds a
  dead credential that presents as an unexplained 404, un-enumerable and un-clearable from AWS or the
  repository; (2) `make load-staging-learning`'s docker env pass-through was never re-measured for
  `ps` visibility, so that exposure class is **unmeasured, not cleared**; (3) `e2e/README.md:16-17`
  still documents the pre-D-310 export shape. Record too the accepted residual that **no standing
  rotation mechanism was added** (no `keepers`, no rotation resource) — accepted because the S44 plan
  deletes these secrets outright when real auth lands.
- **Ordering:** archive at the end of the migration, after `PROJECT_STATE` and the two reference
  registers are in place. Nothing else depends on them.
- **Risk if migrated incorrectly:** the R7.1 pattern repeating — 23,262 lines of unindexed
  documentation is exactly how the corpus reached its current state, so `archive/README.md` (§15.2)
  must index this directory. `DOCUMENTATION_RISK_REGISTER.md` in particular must not be read as the
  current countermeasure plan once §14 exists. For `REMEDIATION_D310_ROTATION.md` the specific risk
  is a live-exposure scare: an archived remediation record with no resolution banner reads exactly
  like an open incident.

---

## 10. The four proposal files (`docs/reconciliation/proposal/`)

Phase 5's own output has roles too, and stating them is part of not repeating the mistake this
exercise is about.

### 10.1 `PROJECT_STATE.md` (draft) → **SPECIAL_CASE: promoted to `docs/PROJECT_STATE.md`**

- **Why special case:** it is not moved as a document with an existing role — it is **promoted**, and
  on promotion it becomes the corpus's entry point and the most-read file after `CLAUDE.md`. It
  replaces `PROGRESS.md`'s and `OPEN_DECISIONS.md`'s live functions and carries the LB-05 dual status
  (repo HEAD `344f016` vs deployed `gha-44a12dfc9549`, ten commits behind), the 27 open engineering
  items by register key, the UD-1…UD-12 questions table, the parked/deferred set with reopen
  conditions inline (D-152 prominent), the four UNKNOWNs plus `ARCH-34`'s named tfvars half (five
  substances) with named resolution steps, and the doc map.
- **Extract first:** nothing — it is the destination of other files' extractions, not a source. Its
  governing rule is the **anti-PROGRESS rule**: it holds only current state, and when an item
  resolves it is **deleted** from the file rather than annotated, with the resolution recorded in
  `DECISIONS.md` and git.
- **Ordering:** promoted at **step 0a, before anything else** (manifest Phase 0). Every archive banner
  points at `docs/PROJECT_STATE.md`, which exists from step 0a; the frozen-session extraction, the
  §5.33.3 deferred row and the UD table all land in it.
- **Risk if migrated incorrectly:** it becomes PROGRESS again. Two mechanisms prevent that — the
  delete-on-resolve rule and the staleness rule (if the snapshot date is more than 14 days old or
  HEAD has moved, re-verify before trusting the repo/deployed and known-drift sections). Without
  both, R1.1 reconstitutes itself in a new file within one milestone.

### 10.2 `AUTHORITY_MODEL.md` → **MOVE_TO_REFERENCE: `docs/reference/AUTHORITY_MODEL.md`**

- **Why reference:** durable and date-independent — precedence rules and conflict protocols, not
  state. Read when two documents disagree, which is a trigger. Its precedence table is also
  summarized in `PROJECT_STATE`'s doc map so a reader meets the rule without a second hop.
- **Extract first:** nothing; it is new content authored in this phase.
- **Ordering:** promoted at **step 0a**, with `PROJECT_STATE.md` (manifest Phase 0) — it defines the rules the
  rest of the migration applies (evidence beats snapshot; a newer accepted decision beats older SPEC
  text; repo and deployed are both true in their own layer; never silently "fix" code to match an old
  decision; never convert a UD-x into a D-xxx without the user). Its core rule is load-bearing for
  every judgement in this document: **"Consistency is not evidence of correctness."**
- **Risk if migrated incorrectly:** if it lands after the moves, the migration's own conflict calls
  get made ad hoc and unrecorded — the process failure that produced R2.1 and R6.5.

### 10.3 `DOCUMENT_MODEL.md` (this file) → **ARCHIVE, after the migration executes**

- **Destination:** `docs/archive/reconciliation-2026-08/DOCUMENT_MODEL.md`.
- **Why:** it is a migration instrument. Once every file is at its destination this document
  describes a completed transition: the structure is self-evident from the tree and the reasoning is
  provenance. Keeping it active would give the corpus a second, competing description of where things
  live — the R2.1 pattern, freshly minted.
- **Extract first:** two things must survive outside it before it is archived — the **archive
  conventions** (§15) belong in `archive/README.md`, and the **single-home rule plus the doc map**
  belong in `PROJECT_STATE` and `reference/AUTHORITY_MODEL.md`. With both in place, archiving loses
  nothing operational.
- **Ordering:** archived **only after** the last file has moved; it is the instruction set, so it
  stays readable at its proposal path until the manifest's final validation passes.
- **Risk if migrated incorrectly:** archived early, executors lose the extract-before-archive
  constraints in §8.3 and §7.3 mid-migration. Kept active, it drifts against the tree it describes
  the first time a file moves — and a stale map is worse than no map.

### 10.4 `MIGRATION_MANIFEST.md` → **ARCHIVE, after the migration executes**

- **Destination:** `docs/archive/reconciliation-2026-08/MIGRATION_MANIFEST.md`.
- **Why:** the per-document old→new mapping and the validation coverage table are the execution
  record. Afterwards they are the audit trail proving each of the 45 files reached its destination and
  each extraction landed — valuable as provenance, inert as instruction.
- **Extract first:** nothing, provided its validation table has been **run** and its results recorded
  in it before archival. An unexecuted manifest archived as if executed is the exact failure this
  reconciliation exists to fix.
- **Ordering:** archived last, paired with §10.3.
- **Risk if migrated incorrectly:** it is the only place the old→new mapping exists. Archived without
  its validation results, no future reader can tell whether a file is missing or was deliberately
  never moved — and `git log --follow` across a bulk move plus two renames is a poor substitute for a
  written mapping.

---

## 11. Files the migration creates (3 files, no role assignment)

| file | purpose | why it is new rather than moved |
|---|---|---|
| `docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md` | S42–S51 scope bullets + five embedded constraints (no "Done when" exists in that range), line-1 freeze banner | Extracted from ROADMAP; the surrounding 3,328 lines are history (§6.2) |
| `docs/reference/audits/README.md` | Audit ID-namespace map + source-qualified citation rule | No current document states which register a bare `AUD-L-nn` belongs to (§7.15) |
| `docs/archive/README.md` | Archive index: what, why, superseded-by | The archive needs a front door or it reproduces R7.1 (§15.2) |

`docs/PROJECT_STATE.md` and `docs/reference/AUTHORITY_MODEL.md` are also new to `docs/`, but they are
promotions of §10.1/§10.2 rather than fresh files, and are counted there.

---

## 12. Out of scope: code-adjacent READMEs (2 files)

`e2e/README.md` and `load-tests/README.md` stay with their code and receive no role in the
documentation tree. One tracked defect touches them: `e2e/README.md:16-17` still documents the
pre-D-310 token export shape, recorded as residual (3) under `D310-RESIDUALS` in the open-work
register — a code-adjacent doc fix, not a migration item. (`docs/.DS_Store` and
`.pytest_cache/README.md` are tool artifacts, out of scope by the inventory's own declaration.)

---

## 13. Consolidated ordering constraints

The general rule, stated once: **extraction always precedes archival, and a banner may never point at
a file that does not yet exist.** Below, the specific constraints, strongest first. "HARD" means
executing out of order loses information that exists nowhere else.

| # | constraint | strength | why |
|---|---|---|---|
| **O1** | `PROJECT_STATE.md` promoted, and `reference/AUTHORITY_MODEL.md` promoted, **before any file moves** | HARD | Every archive banner names `docs/PROJECT_STATE.md` as current state; AUTHORITY_MODEL defines the conflict rules the migration itself must apply — implemented as manifest step 0a (HC-8) |
| **O2** | `FINAL_ARCHITECTURE.md`: topology diagram → ARCHITECTURE; **open question 5 (SPEC §5.33.3 six-schema split) → ARCHITECTURE "Open architecture questions (undecided)" block + `PROJECT_STATE` §deferred row**; one-database fact → ARCHITECTURE — **then** rename and archive | HARD | It is the only record of an unmade decision (A1 §5.4, corroborated by the inventory). Archive-before-extract deletes it from the corpus |
| **O3** | `S42_ORG_ASKS.md`: stamp per-message D-153 dispositions **before** archive/rename; sequence this **first among all freeze work** | HARD | Three live "Send now" markers for questions the org already answered — the corpus's only defect whose consequence is an email leaving the building |
| **O4** | `HINT_SOLUTION_REVIEW.md`: reconcile the front page to the D-262+ horizon **before** moving to `reference/` | HARD | Seven source files and two scripts cite it as normative; a curated path on an unreconciled file reads as endorsement of a superseded design |
| **O5** | `ROADMAP.md`: extract the S42–S51 scope bullets + five embedded constraints into `ROADMAP_FROZEN_SESSIONS.md` (line-1 freeze banner; no "Done when" exists in the range — author none), adding the missing S48–S51 freeze annotation, **before** archiving ROADMAP | HARD | The frozen-session scope and its five embedded constraints exist nowhere else |
| **O6** | `reference/audits/README.md` namespace map exists **before or with** the three audit registers' move | HARD | Every cross-document finding lookup after 2026-08-16 is ambiguous until it does; no mechanical re-map is possible |
| **O7** | `PROGRESS.md`: **verify** (not extract) that every live item it holds has a register key — `WORK-04-ANSWER-CACHE`, `LB-05-DEPLOY-GAP`, `SNS-CONFIRMATION`, the 2026-08-07 carry-over, the four-row queued block — **then** archive | HARD-ish | Phase 4 already captured these; the check is cheap and the failure (archiving a live item as history) is silent |
| **O8** | `docs/plans/2026-07-19-branding-plan.md`: brand table + BD3 do-not-revert rule → ARCHITECTURE before archive; fix the "D-064 was the last used" line **regardless of sequencing** | HARD for BD3 | Following that line mints duplicate D-numbers against a log past D-423 |
| **O9** | `INTEGRATION_PLAN.md`: D-152 banner at line 1, and §7-R8/R9 expiry conditions single-homed in `PROJECT_STATE`, at the same time as the move | HARD | The move into `reference/integration/` implies curation; curation without the banner is worse than the status quo |
| **O10** | `S42_DISCOVERY.md`: freeze banner + §7–§9 tombstones + forward pointer to `S42_OPEN_QUESTIONS.md`, and **apply its two corrections into INTEGRATION_PLAN in place**, in one pass per file | strong | Corrections currently live only in the correcting document, and they are production-system facts |
| **O11** | `S42_OPEN_QUESTIONS.md` read **before** the freeze banners are written (two banner-less files gain line-1 banners at 7c, plus the new `ROADMAP_FROZEN_SESSIONS.md` at step 3; `S42_ORG_ASKS` gets its banner at 7a) | strong | Its ⛔ banner is the template (R9.1's "one banner per file" fix); its in-table annotations are independent and can follow |
| **O12** | `INCIDENT_RESPONSE.md`: grep for a `D-093 → D-137` RDS-rotation routing **before** anything else touches it | strong | Flagged as a live operational hazard, not a documentation defect — implemented as read-only manifest step 0b, before any edit touches the file |
| **O13** | `U7_CHECKPOINT_CONSOLIDATION.md`: completion banner (D-333) + §9.2/§10 annotations + as-of banner before move | strong | `PROGRESS.md` gates session U7 on its §9, and question 2 was answered the day the file was written — implemented as manifest step 7e |
| **O14** | `S42_SECURITY_REPORT.md`: send-status line before move; `ENROLLMENT_FAQ_APPROVAL.md`: dead pointers fixed and sole-gate row added to `PROJECT_STATE` before move | moderate | Both are open items currently tracked nowhere |
| **O15** | `SPEC.md`: the `AMENDMENT-SWEEP` pass (or a single amendments index) before other files are told to defer to SPEC | moderate | "The spec wins on detail" is unsafe as a conflict rule until vintage is marked. Satisfied structurally by AUTHORITY_MODEL §3.1 step 2 (a newer accepted decision beats stale SPEC text), so the AMENDMENT-SWEEP is a completeness pass, not a precedence prerequisite — it does not conflict with O1. |
| **O16** | `DECISIONS.md`: build the ID index **before** running anything mechanical over the log | moderate | Tooling keyed on `## D-nnn` is unsafe while phantom IDs and the D-274 format change persist — batch G order is W-25, W-16, W-18. |
| **O17** | `TRACEABILITY.md`: apply the `file:line` as-of stamping convention here first; disambiguate the S45 label before assigning T-02/FIRST_VISIT ownership | moderate | A drifted citation here degrades launch evidence rather than merely confusing a reader — W-35 runs in batch A; W-39 first in batch I. |
| **O18** | `ROADMAP.md`'s pointers into `docs/plans/` repointed to `docs/archive/plans/` **after** both plans carry executed-as headers | moderate | Otherwise the pointer arrives at a file that still claims to be a live plan |
| **O19** | `CLAUDE.md` index rewrite **last** (it must name final paths); the OPEN_DECISIONS description fix may land early as an interim | moderate | It is the index of the finished tree; the one exception removes a live wrong-action pointer at zero cost |
| **O20** | `DOCUMENT_MODEL.md` + `MIGRATION_MANIFEST.md` archived **only after** the migration executes and the manifest's validation table has been run and recorded | HARD | They are the instruction set and the proof of execution |

Two engineering items are deliberately **not** ordering constraints on a documents-only migration,
but must be recorded so they are not lost: the three stale source docstrings that repeat
`HINT_SOLUTION_REVIEW.md`'s "not built" claim (`review_loop.py`, `review_panel.py`,
`hint_solution_repair.py`), and the `packages/ui-brand` token promotion from the branding plan.

---

## 14. Risk → structural countermeasure

Per design spec §11.4, expanded with the A3 risk digest. **All 18 HIGH risks are covered** (see the
§1 count correction: the digest's per-table severities give HIGH 18 / MEDIUM 24 / LOW 7 = 49, against
a summary line that says 16 and then lists 18 IDs).

The design principle behind every row: a countermeasure that depends on a reader noticing something
is not a countermeasure. Structure has to make the wrong action harder, not merely discouraged.

| risk | HIGH | structural countermeasure |
|---|---|---|
| **R1.1** PROGRESS "Current status" is ~1,800 lines of strata | ● | `PROGRESS.md` → `archive/`. `PROJECT_STATE.md` replaces it with a **delete-on-resolve** rule and no strata, so accumulation is structurally impossible rather than discouraged. Per-session narration goes to git commit messages |
| **R1.2** ROADMAP keeps ~470 lines of superseded gate standings inline | ● | `ROADMAP.md` → `archive/` after the frozen-session extraction. Gate standings stop being a live document; the current gate position is a dated line in `PROJECT_STATE` |
| **R2.1** Two architecture documents, no ratified hierarchy | ● | `FINAL_ARCHITECTURE.md` archived **and renamed** after its two extractions. **Single storage-table owner = `ARCHITECTURE.md`**, stated in ARCHITECTURE itself and in `CLAUDE.md`'s index |
| **R2.2** §7-R8/R9 accepted risks in two homes, expiry in only one | ● | Expiry conditions **single-homed** in `PROJECT_STATE`'s parked section with reopen conditions inline; ARCHITECTURE's restatements reduced to pointers at migration. Consider making the expiry mechanical rather than prose |
| **R3.1** `FINAL_ARCHITECTURE.md` — the misleading-filename exhibit | ● | Renamed to `archive/2026-07-21-final-architecture-projection.md`: the name now states genre and vintage. Original filename preserved in the banner |
| **R3.2** `OPEN_DECISIONS.md` says both "open" and "nothing open" | ● | `OPEN_DECISIONS.md` → `archive/`; `CLAUDE.md`'s index entry rewritten. Structural, not cosmetic: a closed record leaves the active read path entirely |
| **R4.1** INTEGRATION_PLAN contains no trace of the D-152 freeze | ● | Mandatory **line-1 freeze banner**, plus the canonical freeze statement in `PROJECT_STATE` and a `CLAUDE.md` cross-link naming this file. Guard and temptation linked in both directions |
| **R4.2** branding plan reads "planned, not started" for executed work | ● | Both plans archived under `archive/plans/` with **executed-as headers**; BD3's do-not-revert rule promoted into ARCHITECTURE; the duplicate-D-number instruction fixed; BD3's ratios are sourced from D-067/tokens.css, not the plan's superseded draft values |
| **R4.3** ORG_ASKS carries three "Send now" for answered asks | ● | Archived and renamed with **per-message D-153 dispositions stamped above the message text**, and sequenced first (O3) so the wrong-action window closes before anything else |
| **R4.4** S42_DISCOVERY §7–§9 read as live work | ● | Freeze banner + **section-level supersession tombstones** on §7–§9; §0–§6 stay in `reference/integration/` where they are genuinely useful |
| **R5.1** `CLAUDE.md`'s index keeps OPEN_DECISIONS open | ● | Index rewritten with a completeness rule and a last-reviewed marker; the file it describes is archived, so the stale description has nothing to point at |
| **R5.2** FINAL_ARCHITECTURE presents decided questions as live — **and its inverse** | ● | The four decided questions die with the archive; the **one undecided question is extracted first** (O2) into ARCHITECTURE's "Open architecture questions (undecided)" block + a `PROJECT_STATE` §deferred row keyed `ARCH-21-SCHEMA-SPLIT`. The inverse half is why O2 is HARD |
| **R6.1** DECISIONS status tags never updated; supersession only in body text | ● | Convention: append-only bodies + a **mutable status line** + back-annotation on supersession. Fix the eight actively-misleading entries at migration; the full ~120-entry sweep is deferred (Phase-4 E-9 safe default) |
| **R6.2** Phantom decision IDs cited but never written | ● | Phantom-ID annotation in the `DECISIONS.md` index — D-190/D-191/D-192, D-329, D-363 marked **"cited-never-written"** — plus the standing rule: never fabricate an entry, prefer a stub-with-provenance, and never adopt D-193's description as D-192's content |
| **R6.3** Three audit registers with colliding ID namespaces | ● | `reference/audits/README.md` namespace map + the corpus-wide **source-qualified citation rule** (`<document>:<id>`). No renumber — the earlier renumber was applied per-reference with ranges left ambiguous |
| **R7.1** Thirteen of twenty-five docs absent from the index | ● | `CLAUDE.md` **index completeness rule** (every non-archive document indexed, or explicitly listed as deliberately unlisted) + `archive/README.md` as the archive's own index |
| **R8.1** Summary lines contradicting their own tables | ● | `AUTHORITY_MODEL` rule: summary lines are **date-stamped or mechanically derived**; tables beat summaries. ROADMAP's anchored-awk derivation is the preserved exemplar. This document's §1 count corrections are the rule applied to the register that reported the risk |
| **R9.1** The freeze is visible where least needed, absent where it binds | ● | One banner per file, using `S42_OPEN_QUESTIONS.md`'s ⛔ shape — see the cost table below |

### R9.1's cost table — the whole fix, itemized

The A3 register states the reconciliation cost as **one banner per ❌ row**. With the new `ROADMAP_FROZEN_SESSIONS.md` line-1 banner that is five banners,
plus one annotation and one cross-link:

| document | freeze visible today | action | cost |
|---|---|---|---|
| `S42_OPEN_QUESTIONS.md` | ✅ dedicated ⛔ banner + re-entry protocol | none — it is the template | 0 |
| `CLAUDE.md` | ✅ full ⛔ section, but names only S42_OPEN_QUESTIONS | add cross-links to INTEGRATION_PLAN, S42_DISCOVERY, the archived org-asks drafts | 1 cross-link |
| `ROADMAP.md` | ✅ above S43–S47 | annotate **S48–S51**, which carry none | 1 annotation (during O5's extraction) |
| `PROGRESS.md` | ✅ reconfirmed banner | none (archived) | 0 |
| `INTEGRATION_PLAN.md` | ❌ zero mentions | **line-1 freeze banner** | 1 banner |
| `S42_DISCOVERY.md` | ❌ zero mentions | freeze banner + §7–§9 tombstones | 1 banner |
| `S42_ORG_ASKS.md` | ❌ zero mentions (predates D-152) | freeze banner + per-message dispositions | 1 banner |
| `SPEC.md` §5.2.2 | ❌ | amendment marker on the auth-option menu (rides `AMENDMENT-SWEEP`) | 1 marker |
| `S42_SECURITY_REPORT.md` | states the *production* freeze in its own words | none — it is the freeze's designed exception | 0 |

Total: **5 banners (incl. the new `ROADMAP_FROZEN_SESSIONS.md` line-1 banner) + 1 annotation + 1 cross-link.** R9.1 is registered as one risk rather than nine
because the freeze is the project's single most consequential standing instruction and its
documentation is concentrated in the files a reader is *least* likely to be inside when it matters.
The freeze text itself is canonical in `PROJECT_STATE` (D-152 verbatim, reconfirmed by D-417 §A1:
"it is closed until reopened"), with the reopen condition stated as **an explicit user statement** —
and the standing rule that no amount of verification can trigger it and it must never be solicited.

### MEDIUM and LOW risks — covered by convention, not per-file effort

The 24 MEDIUM and 7 LOW risks are absorbed by five house rules rather than 31 individual fixes:

1. **Vintage headers** (`DOC-VINTAGE-HEADERS`) — every living document states when it was last
   reviewed. Covers R1.4, R1.6, R4.7 and the four documents with no vintage marker at all
   (`CLAUDE.md`, `SPEC.md`, `INCIDENT_RESPONSE.md`, `QUESTION_GENERATION.md`). The cheapest
   structural improvement available and a precondition for most others: a stale line is only
   detectable if the document says when it was last true.
2. **As-of banners on measurement snapshots** (`DOC-SNAPSHOT-BANNERS`) — every measured number
   carries its date, environment/build and denominator. Covers R1.7, R5.3, R5.4, R5.5, and the
   LB-05 discipline of stating the build SHA beside every live number. One convention, not per-file
   banners.
3. **Source-qualified IDs** — audit IDs (§7.15) and session labels (R6.4: `C1`, `S43`, `S45`, and
   `§2.6` resolving to INTEGRATION_PLAN rather than SPEC) are always qualified by their document.
4. **Forward pointers on superseded content** (R6.5, R6.6) — when B supersedes A, A gets the pointer,
   not just B. The corpus has a preservation convention and no companion convention for adding the
   pointer; this adds it.
5. **Single-home rule** (R2.3, R2.4, R2.5, R2.6, R7.2, R8.2, R8.3) — each volatile fact has exactly
   one authoritative location and every other file links to it. Two explicit carve-outs: the
   checkpoint-sizing pair is **not** a contradiction and must not be resolved by picking one (label
   dev ~4.8 GB vs staging ~285 MB), and the two org-facing drafts' opposite credentials-mention
   policies are **both intentional**.

---

## 15. Archive conventions

Per design spec §5. The goal is narrow and testable: **make historical content hard to mistake for
current instruction.** Every rule below exists because the corpus already failed the corresponding
test at least once.

### 15.1 The banner

Every archived file gets a prepended banner block — at migration, not now:

```
> ⚠️ ARCHIVED <date>. Historical record — do not treat as current state.
> Current state: docs/PROJECT_STATE.md
> Reason: <one line>
> Superseded by: <target, or "nothing — this content has no successor">
```

Rules for the banner:

- **Top of file, before the H1.** Non-negotiable, and the reason is empirical: a reader who greps
  into `2026-07-18-expansion-plan.md` for "Mongo" lands mid-file, and a status line 87 lines above
  the stale claim did not protect anyone.
- **"Superseded by" is mandatory and may say "nothing".** An empty successor is information; a
  missing field is a question.
- **Renamed files additionally carry `Original filename:`** (§15.3).
- **Files with a live residual say so explicitly.** `REMEDIATION_D310_ROTATION.md` is the worked
  example: the banner states the remediation is executed and resolved, *and* that three residuals
  live on in `PROJECT_STATE` under `D310-RESIDUALS`. An archived record with an open tail must name
  where the tail lives, or the tail is lost.
- **Self-expiring claims get absolute dates** during the same edit ("nothing eligible for at least
  another 8 days" is meaningless in an archive).

### 15.2 `archive/README.md`

A directory-level index: what is in the archive, why each file is there, and what superseded it.
Without it, the archive becomes a 23-file unindexed directory — precisely the R7.1 condition that
`docs/reconciliation/` reproduced on the day it was created. The index is also the safety net for the
one thing archival can genuinely lose: an obligation nobody remembers. If an archived document
reveals a forgotten obligation, the protocol is to **re-open it as a `PROJECT_STATE` work item citing
the archive** — never to start following the archived document.

### 15.3 Renames

Archived files **keep their original filenames** by default, for provenance and to preserve inbound
citations in `DECISIONS.md` and `PROGRESS.md`. Exactly **two** files are renamed, both because the
filename itself is the defect:

| original | archived as | why the rename is justified |
|---|---|---|
| `docs/FINAL_ARCHITECTURE.md` | `archive/2026-07-21-final-architecture-projection.md` | "FINAL" reads as latest and definitive (R3.1). Zero functional inbound references, so nothing breaks |
| `docs/S42_ORG_ASKS.md` | `archive/2026-07-24-org-asks-drafts.md` | The `S42_` prefix asserts a session the content predates (R3.3) |

Rename rules:
- **Provenance is preserved in the banner**: `Original filename: docs/FINAL_ARCHITECTURE.md`.
- **Rename only when the name misleads and the inbound-link cost is near zero.** Renames were
  *considered and rejected* for `OPEN_DECISIONS.md`, `AUDIT_FINDINGS.md` and
  `U7_CHECKPOINT_CONSOLIDATION.md` — all three have real inbound citations, and for OPEN_DECISIONS
  the stalest thing about it is `CLAUDE.md`'s description, not its filename. A rename alone would not
  have fixed it.
- **The date in a renamed file is the authorship date**, not the archival date (2026-07-21 and
  2026-07-24 respectively) — the point of the rename is to state vintage.
- **`docs/plans/` keeps its already-dated filenames** and moves wholesale to `archive/plans/`; the
  directory name was the defect (R3.6), not the filenames.

### 15.4 Nothing in `archive/` is linked as normative

The load-bearing rule, and the one most likely to be violated by accident:

- **`SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TRACEABILITY.md` and `PROJECT_STATE.md` never cite
  a file under `archive/` as authority.** They may cite it as *provenance* ("the topology diagram was
  refreshed from the 2026-07-21 projection"), which is a different verb.
- **`CLAUDE.md`'s index does not list archive contents.** `archive/README.md` is the archive's index;
  the completeness rule in §6.1 covers non-archive documents only. This is what keeps the index short
  enough to stay accurate.
- **A pointer *into* an archived file must be repointed, not left dangling** — including pointers
  from one archived file to another (ROADMAP → `docs/plans/`, O18).
- **Corollary that decided three role assignments:** any content that a normative file needs to cite
  cannot be archived without being extracted first. That is exactly why `FINAL_ARCHITECTURE.md`'s
  §5.33.3 question, the branding plan's BD3 rule, and ROADMAP's frozen-session criteria are
  extract-before-archive rather than plain archive — and why `FINAL_OPEN_WORK_REGISTER.md` and
  `USER_DECISION_QUEUE.md` go to `reference/`, since `PROJECT_STATE` links into them by design.
- **Ordinary maintenance never edits `archive/`.** Its files are frozen; a correction to archived
  content is recorded in the current document that supersedes it, not backported. Deletion is never
  the answer: **archive, never delete.**

---

## 16. Summary

### 16.1 By role

| role | count | documents |
|---|---|---|
| **KEEP_ACTIVE** | 4 | `SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TRACEABILITY.md` |
| **MERGE_INTO_ACTIVE** | 0 | *none — every merge candidate becomes extract-then-archive under the archive-never-delete rule (§3)* |
| **MOVE_TO_REFERENCE** | 17 | `INCIDENT_RESPONSE.md`, `QUESTION_GENERATION.md`, `HINT_SOLUTION_REVIEW.md`, `U7_CHECKPOINT_CONSOLIDATION.md`, `CONTENT_COVERAGE.md`, `FIRST_VISIT_NOTICE.md`, `INTEGRATION_PLAN.md`, `S42_DISCOVERY.md`, `S42_OPEN_QUESTIONS.md`, `S42_SECURITY_REPORT.md`, `ENROLLMENT_FAQ_APPROVAL.md`, `AUDIT_FINDINGS.md`, `AUDIT_2026_08_16.md`, `AUDIT_LIVE_2026_08_17.md`, `FINAL_OPEN_WORK_REGISTER.md`, `USER_DECISION_QUEUE.md`, `AUTHORITY_MODEL.md` |
| **ARCHIVE** | 20 | `PROGRESS.md`, `OPEN_DECISIONS.md`, `FINAL_ARCHITECTURE.md`†, `S42_ORG_ASKS.md`†, `2026-07-18-expansion-plan.md`, plus the 13 reconciliation evidence artifacts, plus `DOCUMENT_MODEL.md` and `MIGRATION_MANIFEST.md` (post-migration) |
| **SPECIAL_CASE** | 4 | `CLAUDE.md` (rewritten index), `ROADMAP.md` (split: reference extraction + archive), `2026-07-19-branding-plan.md` (archive + data promotion), `PROJECT_STATE.md` (promoted to `docs/`) |
| **Total assigned** | **45** | 26 inventoried + 15 reconciliation artifacts + 4 proposal files |

† renamed on archive, original filename recorded in the banner.

Out of scope, no role: `e2e/README.md`, `load-tests/README.md` (stay with code).

### 16.2 By destination tier

| tier | files | contents |
|---|---|---|
| **Root** | 1 | `CLAUDE.md` |
| **Active** (`docs/`) | 5 | `PROJECT_STATE.md`, `SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TRACEABILITY.md` |
| **Reference** (`docs/reference/`) | 19 | 7 top level + 4 `integration/` + 2 `org-drafts/` + 4 `audits/` + 2 `reconciliation-2026-08/` |
| **Archive** (`docs/archive/`) | 23 | 6 top level (incl. `README.md`) + 2 `plans/` + 15 `reconciliation-2026-08/` |
| **Total** | **48** | 45 role-assigned files + 3 created at migration |

Arithmetic check: 45 assigned + 3 new = 48 = 1 + 5 + 19 + 23. Nothing is deleted, so this must
close, and it does. Documentation mass is unchanged (~91,000 lines across `docs/`); what changes is
that **5 files instead of 26 are in the active read path**, and every file outside it states what it
is and when it was last true.

### 16.3 The three claims this model rests on

1. **Six semantic layers never flatten** — normative truth (`SPEC` + accepted decisions), observed
   repo state (code/tests/config), deployed state (runtime observation), historical state
   (`archive/` + git), open work (`PROJECT_STATE` §work, keyed to the register), user judgment
   (`PROJECT_STATE` §open-user-decisions + `USER_DECISION_QUEUE`). Every role assignment above is
   a layer assignment.
2. **A dated claim can go stale; an undated claim lies.** Vintage headers and as-of banners are the
   cheapest structural improvement in the corpus and a precondition for detecting any future drift.
3. **Consistency is not evidence of correctness.** This model deliberately preserves the corpus's
   loud-correction culture — `DECISIONS.md`'s correction trails, `TRACEABILITY.md`'s
   summary-contradicts-table annotations, `AUDIT_FINDINGS.md`'s negative results and its record of
   its own integrity failures. A migration that smoothed those away would produce a tidier corpus
   that had lost its only means of self-correction.
