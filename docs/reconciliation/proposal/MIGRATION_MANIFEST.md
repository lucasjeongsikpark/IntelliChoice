# MIGRATION_MANIFEST.md — where every piece of current knowledge goes

**Status: PROPOSAL. Nothing in this file has been executed.** Written 2026-08-20 as Phase 5 of the
documentation reconciliation, against repository HEAD `344f016` and deployed staging build
`gha-44a12dfc9549`. It is the execution plan for the target tree defined in `DOCUMENT_MODEL.md`,
the state snapshot in `PROJECT_STATE.md`, and the precedence rules in `AUTHORITY_MODEL.md`.

Companion documents in this directory:

| document | answers |
|---|---|
| `PROJECT_STATE.md` | what is true right now (the proposed new entry point) |
| `AUTHORITY_MODEL.md` | which document wins when two disagree |
| `DOCUMENT_MODEL.md` | what each document is *for*, and the final tree |
| `MIGRATION_MANIFEST.md` (this file) | how today's corpus becomes that tree without losing anything |

---

## 0. Scope, and the rules this manifest obeys

### 0.1 What this manifest covers

- All **26 inventoried documents** (25 under `docs/` including `docs/plans/`, plus the repository-root
  `CLAUDE.md`) — 68,085 lines, every line count re-verified on disk 2026-08-20.
- All **15 reconciliation audit artifacts** under `docs/reconciliation/` (23,262 lines), grouped where
  their treatment is identical, plus the 4 proposal documents this phase produced.
  *(Count note: `phase5_A3_inventory.md` §3.3's header says 16 files while its own table lists 15, and
  15 is what is on disk today. The manifest routes by filename, so the discrepancy is recorded here
  rather than propagated — do not "reconcile" it by inventing a sixteenth file.)*
- All **166 register entries** from `FINAL_OPEN_WORK_REGISTER.md`, each given either a future
  destination or an explicit historical disposition (Appendix A).
- All **44 DOCUMENTATION_ONLY** entries as an executable worklist (§4).

### 0.2 Hard rules for whoever executes this

1. **Extract before archive.** Six extractions (§3, steps 1–6) must complete before any file is
   banner-stamped, renamed or moved **at step 7 or later — Phase 0's two promotions (step 0a) and
   three vintage headers (step 0c) are the sole, deliberate exceptions (HC-8)**. Archiving `FINAL_ARCHITECTURE.md` before its topology diagram
   and its open question 5 are extracted permanently loses an unmade decision.
2. **Quarantine, never silently copy.** Every stale claim named in §2 under "must NOT be copied" is
   either deleted, dated in place, or left in the archive behind a banner. It never travels into an
   active or reference document unmarked.
3. **UNKNOWN stays UNKNOWN.** Four entries (`DRIFT-49-MODEL-ROSTER`, `K5-HINT-INSTRUMENTS`,
   `D288-D317-CLOSURE`, `D192-PHANTOM`) plus one named half (`ARCH-34-REVISION-DRIFT`'s tfvars
   staleness) move with their named resolution step and no guessed answer.
4. **No user decision is answered by this migration.** All 12 UD entries survive as questions. Nothing
   here converts a UD into a `D-xxx`.
5. **The D-152 integration freeze is unchanged.** The migration adds freeze *visibility*; it takes no
   frozen action and solicits no reopening.
6. **Never fabricate an identifier.** `D-190`, `D-191`, `D-192`, `D-329` and `D-363` are cited but
   never written. They get an annotation ("cited, never written"), never a reconstructed body.
7. **Audit IDs are source-qualified.** A bare `AUD-L-nn` does not identify one finding. Every citation
   after step 8 reads `<document>:<id>`.
8. **This is a documents-only migration.** Where a worklist row would edit source code, a terraform
   comment or a docstring, that half is split out and named as engineering work — it does not ride
   along silently. Twelve such splits are flagged in §4.
9. **No line-number citations into mutable giant documents.** Use decision IDs, section anchors and
   register keys. Line numbers appear in this manifest only as *provenance for the defect being
   fixed*, valid as of 2026-08-20.
10. **Preserve provenance mechanically.** Every move and rename is `git mv`. Banner/header insertion is
   a **separate commit from the move**, so rename detection sees an unmodified blob. One commit per
   phase, its message naming the phase and step range. Before step 0a, commit the clean tree so
   the whole migration is revertable. After each phase, verify `git log --follow` on the two renamed
   files and on three sampled moved files before proceeding.
11. **Archived files are edited only at step 7, before the move.** After step 9 an archived file is
   frozen (§15.4); a defect found later is recorded in the superseding current document, never
   backported. "Quarantined behind a banner" and "corrected at banner time" are the same act — at
   step 7d.

### 0.3 Migration-time vocabulary

| term | meaning |
|---|---|
| KEEP_ACTIVE | stays in `docs/`; an agent reads it at the start of non-trivial work |
| MOVE_TO_REFERENCE | moves to `docs/reference/…`; durable, read on demand, not per-session |
| ARCHIVE | moves to `docs/archive/…` behind a banner; historical record, never normative |
| SPLIT | part moves to reference or active, the remainder archives |
| EXTRACT-FIRST | named knowledge must be lifted out before the file moves |
| BANNER | a prepended block naming the archival date, the reason and the successor |
| QUARANTINE | the stale claim stays only inside an archived file, behind its banner |

---

## 1. Routing rules — disposition to destination

These rules are mechanical. Appendix A applies them to all 166 entries; §2 applies them per document.

| register disposition | count | future destination | rule |
|---|---|---|---|
| `ACTIVE_REMEDIATION` | 16 | `PROJECT_STATE` §4.1 (active engineering) | one line + remaining action; detail stays in the register |
| `ACTIVE_IMPLEMENTATION` | 11 | `PROJECT_STATE` §4.2 (active engineering) | same |
| `USER_DECISION_REQUIRED` | 16 | `PROJECT_STATE` §5 (open user decisions) | carried by **11** UD ids (UD-1…UD-10, UD-12); UD-11 is a twelfth question sourced from the `BLOCKED` entry `LANGSMITH-RETENTION`; visually separated as questions |
| `BLOCKED` | 6 | `PROJECT_STATE` §6.2 | names the missing external fact or authorization |
| `DEFERRED` | 15 | `PROJECT_STATE` §6.3 | reopen condition inline |
| `PARKED_BY_DECISION` | 13 | `PROJECT_STATE` §6.4 (D-152 itself in §6.1) | parking decision id + reopen condition inline |
| `UNKNOWN` | 4 | `PROJECT_STATE` §7 (known unknowns) | resolution step inline; stays UNKNOWN |
| `DOCUMENTATION_ONLY` | 44 | a worklist row in §4 of this manifest | each row names its migration step |
| `RESOLVED` | 19 | historical | discoverable via `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md` |
| `SUPERSEDED` | 1 | historical | same |
| `OBSERVATION_ONLY` | 21 | historical | same |
| **total** | **166** | | |

Three routing notes that are judgements, flagged as such rather than presented as mechanical:

- **Mixed entries route by primary disposition, and their residual is named separately.** **Seven entries (M1–M7)**
  carry a residual of a different kind: `COST-25-ALARM-COUNT` (RESOLVED at count scope; billing-line
  residual rides worklist row **W-01**), `D356-FAMILY` (ACTIVE_REMEDIATION; documentation member rides
  **W-18**), `WORK-44-DECIDED-NOT-BUILT` (items 3 and 9 active; items 2 and 13 historical),
  `DRIFT-58-E2E-ISOLATION` (RESOLVED at claim scope; paid cross-spec residual carried inside
  `PS §4.2`'s `WORK-13-FIXTURES` row (the UD-2 whole-directory arm) — not a separate §6.3 row),
  `ARCH-34-REVISION-DRIFT` (OBSERVATION_ONLY; tfvars half to §7), `WORK-43-FRONTEND-TESTS` (RESOLVED;
  the wrong "two against recommendation" count rides **W-13**), and `RISK-GROUP-EXECUTED-PLANS`
  (documentation, with one engineering half — the brand-data promotion).
- **Historical is not the same as unreachable.** `FINAL_OPEN_WORK_REGISTER.md` and
  `USER_DECISION_QUEUE.md` move to `docs/reference/reconciliation-2026-08/`, **not** to the archive,
  because `PROJECT_STATE` links into them for per-item evidence. The other 13 audit artifacts archive.
- **A disposition is not a priority.** `DOCUMENTATION_ONLY` means "no code changes to close it", not
  "unimportant": `RISK-GROUP-INDEX` (W-30) is the cheapest and highest-value item in the whole set.

---

## 2. Per-document migration entries

Each block answers the same seven questions: what current knowledge moves and where; what historical
knowledge is archived in place; what decision reasoning stays in `DECISIONS.md`; where the evidence
remains reachable in the new tree; what must **not** be copied because it is stale; and what must be
preserved verbatim or provenance-linked.

"Uniquely OWNS" below means knowledge that exists in no other document — if it is not carried, it is
gone.

### 2.A The documents that stay active (5 + CLAUDE.md)

#### 2.A.1 `CLAUDE.md` (repository root) — 118 lines — SPECIAL_CASE: rewritten index, last step

- **Fate.** KEEP_ACTIVE. Rewritten in place as the last substantive step of the migration (§3 step 14),
  after every destination path exists.
- **Current knowledge that moves.** Nothing leaves the file. Three things arrive: (a) a complete
  document index — the current index names 11 files and omits 13 that exist, so completeness becomes a
  stated rule ("every non-archive document is indexed, or explicitly listed as deliberately unlisted
  with the reason"); (b) a pointer to `docs/PROJECT_STATE.md` as the first file to read; (c) a
  last-reviewed date marker (it has none today, and rule 1 said "MongoDB" until the D-082/D-111 sweep).
- **Historical knowledge archived in place.** None — the file has no history strata, which is exactly
  why it drifts silently.
- **Decision reasoning that stays in `DECISIONS.md`.** All of it. The ten condensed rules stay a
  compression; `AUTHORITY_MODEL` §3.1 states that SPEC as amended by accepted decisions wins over the
  compression, which removes the R2.6 hazard that the lossy always-loaded copy is the copy actually read.
- **Evidence still available at.** `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`RISK-GROUP-INDEX`, `RISK-GROUP-RESOLVED-LOOKS-OPEN`, `DOC-VINTAGE-HEADERS`) and
  `docs/archive/reconciliation-2026-08/DOCUMENTATION_RISK_REGISTER.md` (R7.1, R5.1, R2.6).
- **Must NOT be copied (stale).** The description of `OPEN_DECISIONS.md` as "everything still open …
  ten decisions … the answer is often 'ask the user'" — the file holds 14 items and all 14 are closed,
  and this description is what sends every session to a closed file looking for work. Also stale: SPEC
  described as "~2,600 lines" (4,210); rule 8's flat image-deletion imperative, which compresses a
  **deferred** feature (`IMAGE-WORK-PARK`) into a live obligation — it keeps the rule and gains one
  clarifying line that no such code path currently exists. Rule 1 gains D-050's scope clause and rule 8
  its park clause **only in the exact wordings fixed at W-30 (step 14), the sole owner of both edits** —
  see W-42's required wording.
- **Preserve verbatim / provenance-linked.** The two credential rules (never read
  `icrest/app/config/db.config.js` or `intellichoice-sendmail-*.json`; never quote the source-visible
  JWT secret or password-HMAC key) and the production-freeze rule, unchanged. The D-152 do/don't list,
  unchanged, plus one cross-link naming `docs/reference/integration/INTEGRATION_PLAN.md` and
  `S42_DISCOVERY.md` — the two documents the freeze binds and never names today. The
  `signups.attended = null` production fact, unchanged.

#### 2.A.2 `docs/SPEC.md` — 4,210 lines — KEEP_ACTIVE

- **Fate.** KEEP_ACTIVE, normative. Amendment discipline becomes mandatory; §6 (the 24-phase
  implementation sequence) is marked historical in place.
- **Current knowledge that moves.** Nothing moves out — SPEC is the normative layer and
  `PROJECT_STATE` links to it rather than restating any requirement. What arrives is the
  **amendment-marker pass** (W-15, `AMENDMENT-SWEEP`): dated in-text markers in the D-351 pattern, or a
  single "SPEC amendments" index, at the nine points of departure (deployment substrate, scaling
  mechanisms, placement table, question volume, solution images, observability fork, auth menu,
  internal NL2SQL, gateway surface, component table, state shape, payload allowlist, study-plan
  priority, post-exam parallel form, interrupt list, §5.29 failure matrix).
- **Historical knowledge archived in place.** §6's phase sequence is not moved out of the file — it is
  marked historical where it sits, because ROADMAP's per-session "Done when" criteria superseded it and
  the two are cross-cited. §5.2.2's auth-option menu gains a D-152 freeze note.
- **Decision reasoning that stays in `DECISIONS.md`.** Every amendment's *why*. The marker in SPEC says
  "amended <date> by D-xxx"; the argument stays in the log. ~220 SPEC references make `DECISIONS.md`
  the de-facto amendment layer today; the markers make that layer visible from inside SPEC rather than
  replacing it.
- **Evidence still available at.** `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`AMENDMENT-SWEEP`, `RISK-R1.4-SPEC-VINTAGE`, `BATCH-LOW-UNMARKED-SPEC`).
- **Must NOT be copied (stale).** Do not lift §5.33's EKS/Aurora substrate, §5.8.1's question volume,
  §5.28.2's endpoint list, §5.17's solution-image requirements, §5.2.2's auth menu, §5.32.1 or §5.15.4
  into `ARCHITECTURE.md` or `PROJECT_STATE` as as-built facts. They read live and were each decided
  otherwise. They stay in SPEC as *requirements* with an amendment marker — a requirement that was
  overtaken is not deleted, it is dated.
- **Preserve verbatim / provenance-linked.** Every verbatim user-facing string, the eleven first-visit
  disclosures, the token claim set, the §5.19.5 TurnReason table, the §5.29 failure matrix, the
  §5.30.1 Bedrock wire allowlist, the curriculum band tables, the difficulty weights and gain formula,
  the §5.33.4 SLO targets. These are the reason SPEC cannot be summarized.

#### 2.A.3 `docs/DECISIONS.md` — 28,787 lines, 443 entry headings — KEEP_ACTIVE

- **Fate.** KEEP_ACTIVE. The system of record. Hygiene, not restructuring, is the migration work.
- **Current knowledge that moves.** Nothing moves out. Three things arrive: (a) an ID index with a
  status column; (b) the phantom-ID annotation — `D-190`, `D-191`, `D-192`, `D-329`, `D-363` marked
  "cited, never written" at the index and at each citation site; (c) back-annotation on the eight
  verified-misleading status tags (W-16, W-25). The full 120-entry status sweep is **deliberately not
  done** — the Phase-4 safe default is the eight worst plus a convention going forward.
- **Historical knowledge archived in place.** None. `DECISIONS.md` is append-only by intent and stays
  whole; its bodies are history *and* current rationale simultaneously, which is why it cannot split.
- **Decision reasoning that stays here.** All of it, by definition — supersession chains, correction
  trails, measured constants, the D-084 / D-085 / D-310 / D-400 post-mortems, and every user decision
  *with the options that were rejected*. `PROJECT_STATE` never restates a rationale; it cites the D-number.
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/DECISION_SUPERSESSION_MAP.md`
  (29 chains, 6 phantom ids) and the register entries `DOC-DECISION-LOG-CORRECTIONS`,
  `STATUS-TAG-CONVENTION`, `RISK-GROUP-DECISIONS-HYGIENE`.
- **Must NOT be copied (stale).** Do not treat a `## D-nnn` heading as a reliable key: the log is not
  append-only in practice (D-176 §4, D-110's embedded D-207 update, D-401's 08-18 correction inside an
  08-17 entry), and the heading format changes at D-274 — so **any tooling keyed on the heading is
  unsafe until W-25 closes**, including this audit's own merge keys. Do not attribute the quote "The
  number was never the variable" to D-233; it was searched for and not found. Do not adopt D-193's
  description as D-192's content.
- **Preserve verbatim / provenance-linked.** The loud-correction culture — an entry that corrects
  itself in place, visibly, is the strongest documentation habit in this repository and the hygiene
  pass must not tidy it away. D-152's reconfirmation verbatim: *"D-152 is unchanged and is not 'nearly
  met' — it is closed until reopened."* D-333's precondition verbatim: *"Before deleting any eligible
  checkpoint, run long-term memory consolidation first."*

#### 2.A.4 `docs/ARCHITECTURE.md` — 2,180 lines — KEEP_ACTIVE (absorbs two extractions)

- **Fate.** KEEP_ACTIVE — the single as-built authority. The one document that *gains* content in this
  migration.
- **Current knowledge that moves in (four arrivals).**
  1. The **end-to-end deployed-topology diagram** from `FINAL_ARCHITECTURE.md:46-105`, refreshed
     against the measured 2026-08-20 deployed state. It is the only such diagram in the repository.
  2. A new, explicitly-marked block **"Open architecture questions (undecided — do not treat as
     designed)"**, whose single entry is the SPEC §5.33.3 six-schema logical split (`learning`, `rag`,
     `memory`, `checkpoint_learning`, `checkpoint_chat`, `evaluation`), with its reopen condition:
     production schema design. **No new decision is created** — the question is recorded as open, and a
     one-line row appears in `PROJECT_STATE` §6.3.
  3. The as-built one-liner "today's system is one `intellichoice` Postgres database", which today is
     asserted only inside the stale projection.
  4. From `docs/plans/2026-07-19-branding-plan.md`: the extracted **brand table** (fonts, colors,
     gradient, geometry) and **BD3's standing do-not-revert rule** with its exact contrast ratios. A
     standing rule cannot live in a file labelled "planned, not started". *(If the migration is
     documents-only, the parallel promotion of the same data into `packages/ui-brand` is engineering
     work — see §4 W-32.)*
- **Historical knowledge archived in place.** Nothing archives out of this file. Its small historical
  strata are dated in place: the access-probe rule-history table stays (it is history *as method*), and
  the two shipped plan-deviations (D-064, D-130) stay.
- **Decision reasoning that stays in `DECISIONS.md`.** The topology's *why* (D-004 and the S32-era
  substrate decisions), BD1–BD5 as D-065–D-069, and D-419's applied-infrastructure record.
- **Evidence still available at.** `docs/archive/2026-07-21-final-architecture-projection.md` (the
  original diagram, for provenance), `docs/archive/plans/2026-07-19-branding-plan.md` (the brand audit
  it was derived from), `docs/archive/reconciliation-2026-08/DEPLOYED_INFRA_STATE_EVIDENCE.md` (the
  measured deployed state the refresh is checked against).
- **Must NOT be copied (stale).** The projection's status claims — do not carry any of
  `FINAL_ARCHITECTURE`'s prose along with the diagram; nearly every status claim in it is false. Four
  of its five open questions are decided and must not arrive as live questions. Its "D-004 is proposed"
  line is wrong (accepted six days before the file's last edit). From ARCHITECTURE's own current text,
  three things must be fixed rather than preserved: the self-contradiction on scheduler state (four
  schedules enabled vs "manual trigger" / "no scheduler yet" later in the same file, W-05), the
  content-hash frontend deploy gate that the 711-line workflow does not contain (W-03), and the
  expiry-less restatements of the two accepted P1 risks (W-22).
- **Preserve verbatim / provenance-linked.** The measured capacity and pricing table **with its
  extrapolation ban** (`COST-29-EXTRAPOLATION-BAN`: the measured throughput constraint stands even
  though the purchase it justified was withdrawn); the egress/sink table's finding that LangSmith is
  the only egress leaving AWS — reframed per W-44 as baseline-with-exception, carrying all three facts
  (the zero-egress invariant is currently false, by a deliberate decision, at roughly $33/month).

#### 2.A.5 `docs/TRACEABILITY.md` — 791 lines — KEEP_ACTIVE (the justified fifth active file)

- **Fate.** KEEP_ACTIVE. It is a living instrument, not a snapshot: created 2026-07-30 (D-124), swept
  in six tranches to 37/37 sections, maintained through 2026-08-17 (D-387). Its evidence method is
  neither SPEC's norms nor ARCHITECTURE's as-built, so it cannot merge into either.
- **Current knowledge that moves.** Nothing moves out. What arrives: the arithmetic and attribution
  corrections of W-11 (`TRACEABILITY-ARITHMETIC`) and the citation-durability convention of W-39
  (`DOC-LINE-CITATION-DRIFT`) — applied here **first**, because a drifted citation in the criterion-1
  instrument degrades launch evidence directly.
- **Historical knowledge archived in place.** Per-tranche traceability lessons stay in place, dated —
  they are the method's own audit trail.
- **Decision reasoning that stays in `DECISIONS.md`.** The launch-scope determination and its
  exclusions (D-078, D-004, D-087); D-124's creation rationale; D-387's latest sweep.
- **Evidence still available at.** `docs/reference/audits/AUDIT_FINDINGS.md` (which defers to this
  file), and `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`TEST-01-CRITERION1`, `TRACEABILITY-ARITHMETIC`, `BATCH-LOW-CITATIONS`).
- **Must NOT be copied (stale).** The "37 of 37" label over a 36-section launch-scope denominator, the
  stale "21 of 37" running total, the 16-section present-tense tail sitting under a "nothing remains"
  banner, and the "Open: none" summary beside an open T-02. Coverage is genuinely complete; only the
  labels are wrong — do not "fix" the labels by weakening the coverage claim, and do not fix the
  coverage claim by trusting a summary line over its own table.
- **Preserve verbatim / provenance-linked.** The method rule *"unverified counts as not traced"*; the
  four-verdict vocabulary with the fenced definition of "structural"; the two sections downgraded to
  "descriptive" (§5.3, §5.36); and the file's self-documented hazard — its summary lines have twice
  contradicted its own tables, and **both were kept and annotated, as method**. That habit is the
  precedent behind `AUTHORITY_MODEL` §5.2 and must survive.

### 2.B The documents that become reference

#### 2.B.1 `docs/INCIDENT_RESPONSE.md` (310 lines) → `docs/reference/INCIDENT_RESPONSE.md`

- **Fate.** MOVE_TO_REFERENCE. It failed the active test only on *cadence*: it is read when an incident
  happens, not at the start of every session. Nothing about its content is demoted.
- **Current knowledge that moves.** Effectively the whole file — it has the least overlap of its
  cluster. Named as uniquely owned: the PII-boundary triage rule; the rotation commands including the
  `-replace` scoping trap; the scanner cautions (~97% health-check dilution); the full D-400
  cost-attribution procedure with its measured baselines.
- **Historical knowledge archived in place.** None. Its incident narratives are the runbook's evidence,
  not history to be shelved.
- **Decision reasoning that stays in `DECISIONS.md`.** D-084, D-085, D-310 and D-400 — the runbook is
  the procedural counterpart, the log holds the post-mortems.
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/REMEDIATION_D310_ROTATION.md`
  (the executed rotation, with its six safeguards and its probe results).
- **Must NOT be copied (stale).** The future-tense description of S34's failure drills ("S34 … is where
  failure drills get built") — S34 shipped 2026-07-24, and a reader concludes no DR procedure exists.
  Fix the tense; keep the pointer. Also check before moving: if any playbook still routes D-093 → D-137
  for an RDS rotation, that is a **live operational hazard**, not a citation nit (W-18).
- **Preserve verbatim / provenance-linked.** The D-310 lesson verbatim: *a safety claim in a comment is
  a hypothesis; measure it once.* One new line arrives, scoped: *"D-152 means we take no integration
  action against production; it does **not** mean the MySQL-adjacent tier is not a live exposure surface
  — the committed credentials in the local `../IntelliChoice-web` checkout are one. Triage severity
  unchanged."* The words "stops reading as a live attack surface" must not appear in the executed edit —
  the runbook's own rule is **don't under-react to a MySQL-adjacent incident**.

#### 2.B.2 `docs/QUESTION_GENERATION.md` (450 lines) → `docs/reference/QUESTION_GENERATION.md`

- **Fate.** MOVE_TO_REFERENCE after the strata are boxed or evicted (W-06, W-33, W-37, W-38).
- **Current knowledge that moves.** The pipeline stage graph; the `requested/proposed/reviewed`
  difficulty model and D-239's re-tier rule; the repair-feedback filter table; the preflight fail
  conditions including the availability-versus-invocability distinction; the run-metric definitions;
  D-223's per-topic volume rationale.
- **Historical knowledge archived in place.** The superseded 2026-08-05 model roster moves to an
  appendix inside the same file, dated and visually contained — it currently holds present-tense
  imperatives with no containment. The 08-06 pilot and 08-11 re-measurement strata each get a date
  header rather than being interleaved.
- **Decision reasoning that stays in `DECISIONS.md`.** Roughly 15 re-narrated decisions, D-342's
  standing park on all coverage-driven generation runs, and — unchanged — D-341 as the governing
  `difficulty_tiers` decision *pending* the UD-12(a) confirmation. The migration does **not** resolve
  D-322 §7 versus D-341; it records that the confirmation is outstanding.
- **Evidence still available at.** `docs/reference/CONTENT_COVERAGE.md` (the taxonomy denominators),
  `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md` (`DOC-CONTENT-PIPELINE`,
  `DIFFICULTY-TIERS-CONFLICT`, `PROSE-QUALITY`).
- **Must NOT be copied (stale).** **The trailing undated 2026-08-06 "Next:" line naming Mistral Large 3
  is the single most misleading thing in the file** — it is the last thing a reader sees and it is
  contradicted 180 lines earlier by the 08-11 re-measurement (Sonnet 4.5). It is dated and boxed, or
  evicted; it is never carried forward as an instruction. Likewise: the header decision list stopping
  at D-194 while the body cites D-342, family B routed to Phase R, and the 4-of-12 grade-band figure
  (now 7). Do not silently merge the two adjacent state blocks (696 items vs 127) — label each with its
  date.
- **Preserve verbatim / provenance-linked.** D-342's top banner parking coverage-driven generation runs
  (it is a standing user instruction, not an observation). The measured numbers keep their dates and
  their environment labels.

#### 2.B.3 `docs/HINT_SOLUTION_REVIEW.md` (541 lines) → `docs/reference/HINT_SOLUTION_REVIEW.md`

- **Fate.** MOVE_TO_REFERENCE — **but only after the front-page reconciliation (W-07)**. This is the
  highest-priority ops-document repair in the corpus and it must precede the move, because **seven
  source files and two scripts already cite this document as normative** while `CLAUDE.md` calls it
  "the planned design". Moving it first would relocate a wrong front page without fixing it.
- **Current knowledge that moves.** The two-scorer diagnosis (why neither earlier scorer worked); the
  `PASS`/`REPAIR`/`REJECT` contract and the argument that `run_llm_judge` cannot be reused; the
  deterministic-versus-LLM boundary; the five falsification checks with their pre-registered
  disqualifiers and measured values; the "generator is not the repairer" measurement; the pre-registered
  stopping rule; the `hint_quality_score` disposition table. §3, §4.5b, §4.6, §6 and §9 exist nowhere
  else — this file cannot be archived.
- **Historical knowledge archived in place.** The pre-pilot framing is dated in place, not deleted: it
  is the record of what was believed on 2026-08-10.
- **Decision reasoning that stays in `DECISIONS.md`.** D-245 → D-261 by the explicit split of
  authority — the log records, the document designs — plus the D-262 … D-269 decisions the file has
  **zero mentions of**. Reconciling to the D-262+ horizon means citing them, not re-narrating them.
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/LIVE_BEHAVIOR_FINDINGS.md`
  (which enumerates the five required edits) and the register entry `DOC-HINT-SOLUTION-REVIEW`.
- **Must NOT be copied (stale).** "The loop around them is not built", six lines above a reference to
  `review_loop.py` which implements the bounded loop; reviewer C "measured" in one place and "does not
  yet exist" 62 lines later; §8's steps 4 and 7 left unticked though both completed 2026-08-10 (D-254
  at 29.1 cents; D-252, 126 readings, minimum observed 2); and the three lines asserting
  `_HINT_QUALITY_REJECT_BELOW` "has never been measured". The correct replacement wording is **"built
  but uncalled"**. The three in-code docstrings that repeat the same claim are **engineering work**, not
  part of a documents-only migration (W-07, split flagged).
- **Preserve verbatim / provenance-linked.** The prohibition at the top — no hint- or solution-quality
  scoring is added without reading this document first — and the two-scorer history that justifies it.
  A stale line-citation (`ai_pipeline.py:1769` for a constant now at `:834`) is corrected to a symbol
  citation, not to another line number (W-39).

#### 2.B.4 `docs/U7_CHECKPOINT_CONSOLIDATION.md` (297 lines) → `docs/reference/U7_CHECKPOINT_CONSOLIDATION.md`

- **Fate.** SPLIT in effect, achieved by banner rather than by cutting the file: MOVE_TO_REFERENCE for
  the measurements, with §8/§9/§10 marked answered in place (W-08). It is currently mis-shelved and
  invisible-but-load-bearing — unindexed, yet `PROGRESS.md` gates session U7 on its §9.
- **Current knowledge that moves.** The only staging checkpoint sizing that exists anywhere; the
  bytes-by-phase table (completed sessions 1.7%, abandoned 77%, chat 19%); the five orphan
  `LearningState` fields; and the shared-tables constraint — a job filtering `phase == 'completed'`
  silently skips every chat thread. Plus its two corrections of other documents.
- **Historical knowledge archived in place.** §8's recommendation and §9's four questions stay in the
  file, annotated as answered, with the completion banner pointing at D-333. They are the record of
  what was asked; they must stop reading as open questions.
- **Decision reasoning that stays in `DECISIONS.md`.** D-331 (which names this file its companion),
  D-332 (which answered §9 question 2 the same day the file was written), D-333, D-336 (which closed
  the duplicate `learning_gain` row §10 still records as un-investigated).
- **Evidence still available at.** `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`WORK-35-LEDGER`, `RETENTION-CLUSTER`, `DOC-U7-BANNER`).
- **Must NOT be copied (stale).** The self-expiring claim "nothing eligible for at least another
  8 days" with no absolute date; §9.2's question about whether `learning_sessions` gets built (it is
  built, migrated, modelled, with a scheduled producer); §10's un-investigated duplicate-gain row. Do
  **not** reconcile this file's staging checkpoint numbers with `OPEN_DECISIONS` #4's development
  numbers by picking one — they are roughly 17x apart because they measure different environments. Label
  each with its environment (development ~4.8 GB versus staging ~285 MB). One banner closes DRIFT-47,
  DRIFT-94 and DRIFT-95 together.
- **Preserve verbatim / provenance-linked.** All U7 measurements, each with its date (2026-08-14) and
  its environment. And D-333's precondition verbatim, because it gates any future retention change:
  *"Before deleting any eligible checkpoint, run long-term memory consolidation first."*

#### 2.B.5 `docs/CONTENT_COVERAGE.md` (180 lines) → `docs/reference/CONTENT_COVERAGE.md`

- **Fate.** MOVE_TO_REFERENCE with a **mandatory as-of banner** (measured 2026-08-11, Session C1,
  D-273). The taxonomy facts are durable; the status columns are not.
- **Current knowledge that moves.** The 246 → 245 denominator and the duplicate triple; the
  books-to-topics and rows-to-skills mapping; the eight measured `derive_answer` outcomes; the family
  split 173/37/34/1; the grade-band-ordering trap and its pinning test.
- **Historical knowledge archived in place.** The status columns stay, behind the banner, dated.
- **Decision reasoning that stays in `DECISIONS.md`.** D-273 (the C1 Phase-0 deliverable), D-223's
  volume target and its tension with SPEC §5.8.1.
- **Evidence still available at.** the machine twin `curriculum/coverage/csv_row_dispositions.csv`, and
  `docs/reference/QUESTION_GENERATION.md` for the pipeline that consumes it.
- **Must NOT be copied (stale).** Every status column describing a need that was built the same day or
  since — "needs the Phase R router", "needs figure support", `place_value_compare` 15/15, "4 bands
  populated" (now 7), bank sizes 47/30/28/25 (now 958+). A reader following these would rebuild an
  existing router or re-author fixed items. Also do not carry the `selection` answer-model family as a
  distinct answer model (W-43), and label which "C1" is meant — the label names two different sessions
  (W-35).
- **Preserve verbatim / provenance-linked.** The measured denominators and the band-order trap. One
  process note travels with it: **nothing regenerates this file** — if the pipeline changes, regenerate
  it via `scripts/build_content_coverage.py` rather than hand-editing (W-06).

#### 2.B.6 `docs/FIRST_VISIT_NOTICE.md` (237 lines) → `docs/reference/FIRST_VISIT_NOTICE.md`

- **Fate.** MOVE_TO_REFERENCE. It is unconsumed input to unstarted work (session S45, inside the D-152
  freeze), so it is durable rather than per-session — but it is *not* archival: nothing else holds this
  copy.
- **Current knowledge that moves.** The only written copy of all eleven disclosures, in two reading
  registers; the register-split rule; the retention table with its per-clock columns; the
  no-implied-erasure rule; the ship-eight-not-eleven recommendation.
- **Historical knowledge archived in place.** None — but every "True because" row is stamped as a dated
  code measurement requiring re-verification at S45 start (`FIRST-VISIT-REVERIFY`, `PROJECT_STATE` §6.3).
- **Decision reasoning that stays in `DECISIONS.md`.** D-127 §3, D-129 (T-02), D-114 §4 (the
  undischarged privacy-notice obligation), D-333 (the third statement of the retention windows).
- **Evidence still available at.** `docs/reference/reconciliation-2026-08/USER_DECISION_QUEUE.md`
  (UD-10's full option analysis) and `SPEC.md` §5.1.2 for the requirement itself.
- **Must NOT be copied (stale).** The bare "Owner: S45" without disambiguation — "S45" names both
  ROADMAP's unstarted consent session and a completed unnumbered PROGRESS session, and this collision
  touches two live items (`DISCLOSURES-LEGAL`'s product decision and `FIRST-VISIT-REVERIFY`). Resolve
  the label (W-35) before restating the owner. Do not treat the three unbuilt disclosures as decided in
  either direction — that is UD-10, and it stays open.
- **Preserve verbatim / provenance-linked.** All eleven disclosure texts verbatim; the retention table
  with its clocks; the "Goes false if" conditions, which are the re-verification instrument.

### 2.C `docs/reference/integration/` — the D-152-frozen world, banner-gated

Grouping rationale: these four files describe work that is **closed until the user reopens it**. Putting
them in one banner-gated directory makes the freeze a property of the location, not of a reader's
memory. The freeze is currently invisible in exactly the documents it binds — the single most
consequential finding in the documentation audit (R4.1 / R9.1).

#### 2.C.1 `docs/INTEGRATION_PLAN.md` (626 lines) → `docs/reference/integration/INTEGRATION_PLAN.md`

- **Fate.** MOVE_TO_REFERENCE **with a mandatory line-1 D-152 freeze banner**. The banner is not
  cosmetic: `D-152` appears **zero times** in this file, and read standalone the document directs all
  four actions `CLAUDE.md` forbids (measure AWS-to-icrest reachability, request the production API URL
  or a test account, finalize the §3.1 auth option, rewrite the MySQL dev fake).
- **Current knowledge that moves.** The Tier 0/1/2 taxonomy — the only place "what counts as touching
  production" is drawn; the auth-option matrix (O1/O1b/O2–O4) with its coupling-surface reasoning; the
  I1–I15 catalog with resolutions; §4's accepted-reduced-scope table; the nine §2.6 gate criteria;
  §8's `attendanceClaimed` fail-open trap. **§7-R8 and §7-R9 with their expiry conditions** move with
  the file *and* are single-homed into `PROJECT_STATE` §6.4 (the parked section), because ARCHITECTURE
  restates both risks without the expiries and ARCHITECTURE is the file sessions actually read (W-22).
- **Historical knowledge archived in place.** §2 (the Phase-0 audit narrative) is marked historical in
  place. §5's session table is reduced to two pointers:
  S43–S51 → `reference/integration/ROADMAP_FROZEN_SESSIONS.md`; S35–S42 → `archive/ROADMAP.md`, labelled
  historical (executed at step 7c with W-36). §1 is folded
  with §8 so the corrected facts sit next to the ones they correct.
- **Decision reasoning that stays in `DECISIONS.md`.** D-151 (the discovery), D-152 (the freeze),
  D-153 (the dispositions), and D-146. Note for the executor: **D-151's heading still reads plain
  `accepted`** while two of its load-bearing recommendations have been withdrawn or demoted — that is a
  W-16 status-tag annotation, not a re-decision.
- **Evidence still available at.** `docs/reference/integration/S42_DISCOVERY.md` (which corrects two of
  this file's §1 facts) and `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`D152-FREEZE`, `S43-SCOPE`, `AUTH-OPTION-O1B`, `F2-ADAPTER-SHAPE`, `F3-DEVTOKEN-S44`).
- **Must NOT be copied (stale).** **§5's per-session statuses.** ROADMAP holds newer statuses and this
  table has no status column at all; copying it forward re-creates a third home for session status.
  Also stale: the two facts `S42_DISCOVERY` corrected, which still stand uncorrected here — the
  corrections are applied in place (W-36), because the uncorrected copy is the one a session reads
  first and the corrected facts are production-system facts. Also: line 619's claim that outbound
  drafts are gitignored and not committed — three committed drafts exist, and whether the rule was
  superseded or violated is **UD-12(f), unanswered**. Annotate the tension; do not resolve it — note the
  rule is *partially* honoured: `docs/S42_ORG_ASKS.md` itself is gitignored and untracked today
  (`.gitignore:67`), which is half the evidence for UD-12(f).
- **Preserve verbatim / provenance-linked.** The nine §2.6 gate criteria verbatim (they are cited from
  outside the repository, including `e2e/README.md`), and the §7-R8/R9 expiry conditions verbatim,
  including that R8's acceptance **expires at first real traffic**.

#### 2.C.2 `docs/S42_DISCOVERY.md` (342 lines) → `docs/reference/integration/S42_DISCOVERY.md`

- **Fate.** SPLIT by section marker: MOVE_TO_REFERENCE for §0–§6 with a freeze banner, plus
  **section-level supersession tombstones on §7–§9**.
- **Current knowledge that moves.** The largest block of production facts in the repository, and the
  reason this file cannot be archived: exact API contracts, role facts, the schema-drift mechanism
  (a database that ALTERs on every boot), the three-way timezone split, §6's four security findings,
  and the production-versus-dev-fake mismatch table. Plus the adversarial-verification method itself
  (8 CONFIRMED, 2 REFUTED-with-correction).
- **Historical knowledge archived in place.** §7 (org asks), §8 (the auth recommendation) and §9
  ("S43's real work list") stay in the file behind tombstones naming what superseded them:
  `S42_OPEN_QUESTIONS.md` for §7, `AUTH-OPTION-O1B` for §8, `S43-SCOPE` and D-152 for §9.
- **Decision reasoning that stays in `DECISIONS.md`.** D-151's findings acceptance and D-153 §5/§7's
  dispositions of the four security findings.
- **Evidence still available at.** `docs/reference/org-drafts/S42_SECURITY_REPORT.md` (the declared
  single security document for the same four findings) and
  `docs/reference/integration/S42_OPEN_QUESTIONS.md` (what source could not answer).
- **Must NOT be copied (stale).** §9's instruction that "every row below must be fixed" — that action
  is now **prohibited**, so a reader obeying §9 violates `CLAUDE.md`. The header's claim that the
  runtime half is "still owed" (it is frozen, not owed). The 2026-08-01 checkout pin without a
  staleness note: this file is 19 days old against a database whose schema drifts on boot — that is its
  own finding, and it applies to itself.
- **Preserve verbatim / provenance-linked.** All production facts with their as-of date
  (2026-08-01 checkout, edited 08-02) and the note that the header date did not move when the edits
  landed. The two REFUTED-with-correction results verbatim — they are the method's proof that
  adversarial verification found something.

#### 2.C.3 `docs/S42_OPEN_QUESTIONS.md` (121 lines, Korean) → `docs/reference/integration/S42_OPEN_QUESTIONS.md`

- **Fate.** MOVE_TO_REFERENCE, unchanged in substance. It is the freeze's model citizen — the only S42
  file where the freeze is visible from inside — and its own stop-sign banner shape is the template
  copied onto the other files.
- **Current knowledge that moves.** The freeze rationale in operational form; the resolved-items
  ledger; the D-152 re-entry protocol; and the warning that group B2 (does the deployment match the
  source?) must be answered before `S42_DISCOVERY` is trusted.
- **Historical knowledge archived in place.** Resolved rows C1/C2/C3/C8 stay as rows, **annotated
  in-table** as closed rather than deleted — the ledger below them already declares them closed, and
  the table is the part a reader scans.
- **Decision reasoning that stays in `DECISIONS.md`.** D-153 §7 (the third copy of the E2 correction)
  and D-152 §5's prohibitions.
- **Evidence still available at.** `docs/reference/org-drafts/S42_SECURITY_REPORT.md` — the E-group is
  pointed at it, closing the gap where the E-group duplicates §6 without linking the drafted report.
- **Must NOT be copied (stale).** C3's red "cannot be deferred" marker on an ask the org already
  answered, and line 110's instruction to send it. But **do not blanket-retire line 110** — its
  E-group notification half is still valid. Three mutually contradictory statements live in 121 lines;
  annotate each, do not delete the file's contradictions wholesale.
- **Preserve verbatim / provenance-linked.** The Korean text (this is the operator-facing register), the
  urgency labels **with their stated relativity** — urgency is measured against integration start, not
  against today — and the re-entry protocol verbatim.

#### 2.C.4 NEW: `docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md` — extracted from `docs/ROADMAP.md`

- **Fate.** CREATE by extraction, before `ROADMAP.md` archives (§3 step 3). This file exists so that
  archiving ROADMAP does not archive live acceptance criteria.
- **Current knowledge that moves in.** The S42–S47 per-session scope bullets and the S48–S51 rollout
  paragraph from `ROADMAP.md:1436-1530`, with their **five embedded constraints**: (1) the D-153 §5
  security gate — production `role` must never by itself grant an elevated role; (2) the six structural
  dev-fake mismatches; (3) the two-source `BranchInfo` merge fact; (4) the D-153 §4 session-window
  assertion (no Sunday-evening/00:00–01:00 sessions); (5) D-167's `/dev/token` deletion cascade
  including the `sub`-assertion every per-student cost ceiling depends on. **ROADMAP holds NO "Done
  when" acceptance criteria for S43–S51** (verified: zero occurrences between lines 525 and 1769) —
  **do not author any during extraction**; fabricated acceptance criteria for frozen work is the worst
  outcome.
- **Historical knowledge archived in place.** None — this file is created from live content only.
- **Decision reasoning that stays in `DECISIONS.md`.** D-152 (why S43–S47 are frozen) and D-049 (the
  session renumbering that makes old session labels ambiguous).
- **Evidence still available at.** `docs/archive/ROADMAP.md` for the full original context.
- **Must NOT be copied (stale).** The imperative voice without the freeze marker. Today S43–S47 read as
  build specs with the freeze stated only *above* them, and **S48–S51 carry no freeze annotation at
  all** — they are unstarted work that depends on frozen sessions. Every session block in the new file
  carries its own status line: frozen-by-D-152, or unstarted-and-downstream-of-frozen. Do not carry
  ROADMAP's gate-standings prose.
- **Preserve verbatim / provenance-linked.** The scope bullets and their five embedded constraints
  verbatim, plus the sequencing
  rationale and dependency spine for these sessions. Also carried: the recorded asymmetry that S45
  (consent and the first-visit notice) is **inside** the freeze while S50 A7 (GuardDuty, WAF) is
  **not** — two launch-blocking security items sit in an unfrozen-but-unstarted block while one
  launch-blocking privacy item sits in a frozen one.
- **Banner.** The new file carries a **line-1 D-152 freeze banner** in `S42_OPEN_QUESTIONS.md`'s shape,
  above the H1, in addition to the per-block status lines.

### 2.D `docs/reference/org-drafts/` — the two drafts that are still live

Grouping rationale: both are ready-to-send messages awaiting a human action, not plans. They are the
only outbound drafts that survive as current work. Note that **whether committed outbound drafts are
allowed at all is UD-12(f)** and stays open — this directory groups them so the policy question has one
visible subject, and takes no position on the answer.

#### 2.D.1 `docs/S42_SECURITY_REPORT.md` (170 lines) → `docs/reference/org-drafts/S42_SECURITY_REPORT.md`

- **Fate.** MOVE_TO_REFERENCE, plus **a send-status line added at migration**. It is the only S42 work
  item that legitimately survives the freeze: organization notification is permitted under D-152 (INT-28).
- **Current knowledge that moves.** The only maintainer-addressed Korean form of the four findings; the
  non-accusatory framing rules ("courtesy hand-off, not an audit finding or a demand"); the
  check-old-rows recommendation rescued from the deleted `docs/SECURITY_REPORT_TO_ORG.md`; the explicit
  not-sent list.
- **Historical knowledge archived in place.** None. The whole file is pending.
- **Decision reasoning that stays in `DECISIONS.md`.** D-153 §5/§7 (the findings and their
  dispositions) and INT-02 / INT-28 (why notification is permitted while integration is frozen).
- **Evidence still available at.** `docs/reference/integration/S42_DISCOVERY.md` §6 (the evidentiary
  source) and `docs/reference/reconciliation-2026-08/USER_DECISION_QUEUE.md` (UD-8's analysis).
- **Must NOT be copied (stale).** Do not record the report as sent. A corpus grep in English and
  Korean returns **zero send confirmations**, and the file has no send-status field — so unsent is
  currently indistinguishable from sent-and-unlogged. The send-status line states the known fact ("no
  send recorded as of 2026-08-20"), not an inference. Do not harmonize the 6-digit `accounts.code`
  severity by editing one side: the report says Medium and INTEGRATION_PLAN §7-R3 calls it a permanent
  takeover residual, and reconciling them **before sending** is part of UD-8.
- **Preserve verbatim / provenance-linked.** The full bilingual message text verbatim — it is
  send-ready copy, and paraphrasing it destroys the artifact. The rule never to quote the
  source-visible secret literals, verbatim. The framing rules verbatim.

#### 2.D.2 `docs/ENROLLMENT_FAQ_APPROVAL.md` (94 lines) → `docs/reference/org-drafts/ENROLLMENT_FAQ_APPROVAL.md`

- **Fate.** MOVE_TO_REFERENCE and index it. It is active until the organization answers, then it
  archives with the outcome. Today it is absent from `CLAUDE.md`'s index — invisible at session start
  despite claiming to be the only launch-checklist item gating the guest journey's canonical question.
- **Current knowledge that moves.** The four claims and the exact ask; the post-approval flip procedure
  (manifest `draft` → `approved`, then re-run `make knowledge-load`); the routing rule that it must
  **not** be bundled with the security report; and the sole-gate claim itself.
- **Historical knowledge archived in place.** None.
- **Decision reasoning that stays in `DECISIONS.md`.** The `INT-29-FAQ` blocking condition is recorded
  in `PROJECT_STATE` §6.2, and the content-approval policy stays with D-153's org-communication rules.
- **Evidence still available at.** `knowledge-content/manifests/public.yaml` — the live status
  (`public-enrollment-faq` is still `draft`, verified 2026-08-20).
- **Must NOT be copied (stale).** The two dead pointers: the manifest line-number reference (use the
  manifest key, not a line) and the instruction to sync a `knowledge-content copy/` directory deleted
  by D-253 (W-34).
- **Preserve verbatim / provenance-linked.** The bilingual ask verbatim, and the four claims exactly as
  they will be put to the content owner.

### 2.E `docs/reference/audits/` — three registers, three ID namespaces

Grouping rationale: the three audit registers **collide on identifiers** and none states its
relationship to the others. `AUDIT_LIVE_2026_08_17.md` reuses the whole `AUD-L-01`…`AUD-L-19` range
with unrelated meanings — including reusing the very ID that had already been renumbered because of an
earlier collision. Co-locating them behind one README makes the namespace rule enforceable.

#### 2.E.1 NEW: `docs/reference/audits/README.md` — created at migration (§3 step 8, early)

- **Contents.** The ID-namespace map for all three registers and the **source-qualified citation rule**:
  never treat a bare audit ID as uniquely identifying one finding; always cite `<document>:<id>`. Plus
  one sentence per register stating its scope, its freeze date if any, and its relationship to the other
  two. Plus the note that **no mechanical re-map exists** — the `AUD-L-17` → `AUD-L-19` renumber was
  applied per reference with ranges deliberately left ambiguous, so renumbering is not attempted.
- **Why early.** Every cross-document finding lookup after 2026-08-16 is ambiguous until this file
  exists (W-17). The reconciliation corpus adopts the rule too.

#### 2.E.2 `docs/AUDIT_FINDINGS.md` (5,822 lines) → `docs/reference/audits/AUDIT_FINDINGS.md`

- **Fate.** MOVE_TO_REFERENCE with an **as-of banner (register frozen 2026-08-05 by D-183)** and
  successor pointers. It has an archival core but a reference function: it is the only record of what
  was checked and found correct.
- **Current knowledge that moves.** Reproduction recipes and raw measurements per finding; the negative
  results; the measurement-method corrections; measured constants and threshold sweeps; capacity curves;
  the `AUD-L-17` → `AUD-L-19` collision history; and the register's own documented integrity failures.
- **Historical knowledge archived in place.** The Index's status column stays but is explicitly
  **disclaimed as non-authoritative** rather than deleted. Known-wrong "Fix shape (Phase 0B)" blocks
  are retained verbatim behind a marker — they are the record of a superseded plan.
- **Decision reasoning that stays in `DECISIONS.md`.** The heaviest overlap in the corpus: fix
  rationale at length, plus D-183 (the freeze).
- **Evidence still available at.** `docs/TRACEABILITY.md` (which this register defers to) and the two
  successor audits alongside it in the same directory.
- **Must NOT be copied (stale).** **"0 open findings."** It is true of this one register, frozen
  2026-08-05, and unknown project-wide — the 08-16 and 08-17 audits filed 46 and 48 findings in
  separate namespaces afterwards, and this file mentions neither. Any count carried forward must carry
  its scope label (W-12). Also do not carry `AUD-F-27`'s heading, which says both "fixed" and "not
  fixed", or the "Status: open, Phase 0B" bullets sitting inside closed entries, without annotation.
- **Preserve verbatim / provenance-linked.** The negative results (uniquely owned — nothing else records
  what was checked and found correct), and the file's self-documented status-rot failures, which it
  records five times over. When a count is restated, execute the anchored awk and record the **actual**
  output rather than re-typing a number.

#### 2.E.3 `docs/AUDIT_2026_08_16.md` (300 lines) → `docs/reference/audits/AUDIT_2026_08_16.md`

- **Fate.** MOVE_TO_REFERENCE with an as-of banner. Its findings are durable; its status lines are not.
- **Current knowledge that moves.** The symmetry-drift table (§1) — seven fixes shipped in one app and
  never ported to the sibling, which no other document holds; the ten P1 narratives with file-and-line
  evidence; the batch-ordered fix plan (§5); and §6's process lesson, *"a check that is correct and no
  longer checks"*.
- **Historical knowledge archived in place.** The 08-16 and 08-17 status blockquotes stay, dated.
- **Decision reasoning that stays in `DECISIONS.md`.** D-373 → D-380 and D-393 → D-396.
- **Evidence still available at.** `docs/reference/audits/AUDIT_LIVE_2026_08_17.md` (the next-day audit
  of the same build) and `docs/reference/audits/README.md` for the namespace map (this file uses a third
  scheme: `P1-1`…`P1-10` plus unnumbered prose).
- **Must NOT be copied (stale).** Its "Still open" lines — Milestones 13–15 (D-397 → D-423) closed most
  of them and the file was not patched. §3/§4's P2/P3 lists carry **no status at all**, so absence of a
  status mark must not be read as "open". Its own 08-17 update corrects its own count ("was 22, not the
  15 stated above"), so no count from this file travels without its correction.
- **Preserve verbatim / provenance-linked.** §1's symmetry finding and §6's process lesson verbatim —
  both are reusable method, not point-in-time status.

#### 2.E.4 `docs/AUDIT_LIVE_2026_08_17.md` (142 lines) → `docs/reference/audits/AUDIT_LIVE_2026_08_17.md`

- **Fate.** MOVE_TO_REFERENCE. The best-maintained of the three; it is also the only audit document in
  the current `CLAUDE.md` index, which is why "the audit" is ambiguous today.
- **Current knowledge that moves.** The live-walk finding catalogue against deployed build
  `gha-6841d9d9b169` (41 flows, 101 screenshots, 48 findings / 42 unique: 2 P1, 14 P2, 32 P3); the
  green-suite-with-live-P1s coverage lesson; the three blind spots — nothing terminal ever completed,
  every approval declined and never approved, every failure injected client-side — with their closure
  narratives; and the reasoned non-actions (AEL-06, AUD-CHAT-05).
- **Historical knowledge archived in place.** The four dated blockquote updates stay as strata, dated.
- **Decision reasoning that stays in `DECISIONS.md`.** D-381 (the walk itself) and
  D-391/D-392/D-398/D-399, D-407 → D-410 (the closures this file predates).
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/LIVE_BEHAVIOR_FINDINGS.md` and
  `LIVE_BEHAVIOR_EVIDENCE.md` — the 2026-08-19/20 re-walk, which supersedes parts of the residual tail.
- **Must NOT be copied (stale).** The residual still-open tail (EDGE-CHAT-07, AUD-L-09, AUD-L-10,
  AUD-L-11, AUD-CHAT-14), partly overtaken with no in-file marks. Every ID from this file is cited
  source-qualified from here on, because `AUD-L-*` means something different in `AUDIT_FINDINGS.md`.
  Also: the build SHA is part of every finding — a finding measured on `gha-6841d9d9b169` is not
  automatically true of today's `gha-44a12dfc9549` (LB-05).
- **Preserve verbatim / provenance-linked.** The coverage lesson verbatim: **the Playwright suite was
  green on the same build that carried both P1s.** That sentence is the reason the three blind spots
  exist as a category, and it is cited as the reading-before-adding-tests rule.

### 2.F The documents that archive

Every file in this group gets the banner block at line 1 (§3 step 7):

```
> ARCHIVED <date>. Historical record — do not treat as current state.
> Current state: docs/PROJECT_STATE.md
> Reason: <one line>.  Superseded by: <target>.
```

#### 2.F.1 `docs/ROADMAP.md` (3,328 lines) → `docs/archive/ROADMAP.md` — EXTRACT-FIRST

- **Fate.** SPLIT, then ARCHIVE. The extraction (§3 step 3) creates
  `docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md`; the remainder archives.
- **Current knowledge that moves.** (a) The S42–S51 scope bullets/rollout paragraph and their five
  embedded constraints → the new reference file (§2.C.4). No "Done when" criteria exist in that range —
  none are extracted and none are authored. (b) The SPEC-section-to-session mapping → kept with the extracted file, since
  it is the index that makes the criteria usable. (c) The "decide at session start" gates that are still
  unfired → `PROJECT_STATE` §6 as reopen conditions where they gate a deferred item.
- **Historical knowledge archived in place.** Roughly 60% of the file: the gate ledger (a D-number
  narrative `DECISIONS.md` already owns), the C1 and A6-C track logs, the M10–M15 retrospectives, and
  approximately 470 lines of superseded gate standings interleaved with the live "THE GATE IS CLOSED"
  banner. Also the completed sessions S0–S42 with their glyphs.
- **Decision reasoning that stays in `DECISIONS.md`.** The whole gate narrative, D-049 (the session
  renumbering), and every milestone-closing decision.
- **Evidence still available at.** `docs/archive/PROGRESS.md` (session outcomes and test counts),
  `docs/reference/audits/AUDIT_FINDINGS.md` (the counts ROADMAP restates), and
  `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.
- **Must NOT be copied (stale).** The five coexisting criterion-6 dates; the multi-tier and depth
  numbers carrying three to four unreconciled values where later-in-file is earlier-in-truth; the 18
  session headings with no glyph beneath an assertion that all are done; the duplicate blocks; the
  "Sessions 40–41 (elastic)" heading over a 245-line audit-backlog ledger. Nothing in this class travels
  into `PROJECT_STATE` — that is precisely the strata problem `PROJECT_STATE` exists to end.
- **Preserve verbatim / provenance-linked.** The anchored-awk derivation ROADMAP uses for counts: it is
  the corpus's own precedent for **mechanically derived rather than hand-maintained** summaries, and
  `AUTHORITY_MODEL` §5.2 cites it. Also preserve the live inbound pointers into `docs/plans/` by
  updating them to the archive paths rather than deleting them.

#### 2.F.2 `docs/PROGRESS.md` (16,690 lines) → `docs/archive/PROGRESS.md`

- **Fate.** ARCHIVE — the history of record. Its live items were already captured by the Phase-4
  register, which is what makes archiving safe rather than lossy.
- **Current knowledge that moves.** Nothing new: every live item in the "Current status" stack is
  already a register entry, and therefore already routed. Specifically confirmed as captured: the SNS
  PendingConfirmation item (`SNS-CONFIRMATION`, RESOLVED), the answer-cache decision
  (`WORK-04-ANSWER-CACHE`, RESOLVED by D-423's numbers), the staging deploy gap (`LB-05-DEPLOY-GAP`,
  UD-1), and the standalone 2026-08-07 carry-over. The "Next session" pointer — the project's actual
  sequencer — is replaced by `PROJECT_STATE` §4.3 plus the update protocol in §10.
- **Historical knowledge archived in place.** Everything: per-session verification transcripts, the
  carry-over ledgers, and the full log back to S0. This is the corpus's memory and it is not thinned.
- **Decision reasoning that stays in `DECISIONS.md`.** All of it — PROGRESS is a lossy mirror of the
  log by its own construction.
- **Evidence still available at.** `docs/archive/PROGRESS.md` and git history. Per
  `AUTHORITY_MODEL` §2.10, git history is provenance and forensics only, never authority for current
  intent.
- **Must NOT be copied (stale).** The "Current status" block, which is roughly 1,800 lines of
  newest-first strata: the same metric reads 4-of-112 at one depth and 102-of-112 at another. Also the
  four-row queued block listing C8 as next with "168 of 494" files against ROADMAP's W24 record of done
  with 168 of 437 — **no count in repository history plausibly yields 494**, and the whole four-row
  block is retired or dated, not one line of it (W-19). The duplicate `### S20` heading is not
  evidence of two sessions.
- **Preserve verbatim / provenance-linked.** The carry-over list's own self-assessment — that it was
  "wrong six times this milestone" — because it is the empirical case for the delete-on-resolve rule
  that replaces it. Note also the three sessions (S32, S37, S40) that were never logged as session
  entries: record the gap, do not reconstruct them.
- **Successor question (flagged, not decided).** Where per-session narrative goes after this. The
  proposal: `PROJECT_STATE` is updated in place with delete-on-resolve, and detailed narration goes to
  git commit messages. If a journal is wanted, `docs/log/` append-only and declared
  non-authoritative. **This interacts with the `/end-session` skill's conventions and is an open design
  question for the user**, not something this manifest settles.

#### 2.F.3 `docs/OPEN_DECISIONS.md` (636 lines) → `docs/archive/OPEN_DECISIONS.md`

- **Fate.** ARCHIVE. All 14 items are answered or parked; the deliberation record is history. The
  filename plus `CLAUDE.md`'s description are what keep a closed record in the active read path —
  exactly the misleading-active pattern the file's own line 292 warns about.
- **Current knowledge that moves.** **Seven live items, per the register's own §11(g) map** — (a) #8's
  D-310 status (annotated superseded-operationally); (b) #10's unverified build items → `WORK-40`/
  `WORK-44-DECIDED-NOT-BUILT`; (c) #3 URL routing → `WORK-44` (ACTIVE_IMPLEMENTATION); (d) #4 checkpoint
  consolidation → `WORK-35-LEDGER`; (e) #9 dependency-PR backlog → `WORK-44`; (f) #5 depth-generation
  budget → `SPEND-AUTHORIZATION`/UD-2; (g) #6/#7 → `VIDEO-COVERAGE-PARK`/`D342-PARKING`. All seven
  verified routed; the gate certifies the full set, not two.
- **Historical knowledge archived in place.** The option space and the recommendation-versus-outcome
  divergences for all 14 decisions — uniquely owned: `DECISIONS.md` records what won, this file records
  what else was on the table and why the recommendation lost in the three cases where it did.
- **Decision reasoning that stays in `DECISIONS.md`.** Every outcome. The archived file is the *option
  space*, not the ruling.
- **Evidence still available at.** `docs/archive/OPEN_DECISIONS.md` and, for the D-310 record,
  `docs/archive/reconciliation-2026-08/REMEDIATION_D310_ROTATION.md`.
- **Must NOT be copied (stale).** **Line 15's "D-401 and D-406 stay unapplied"** — both are applied,
  proven by AWS resource existence (D-419, `DRIFT-93-D401-D406-APPLIED`). Also: line 3's "answered on
  2026-08-14" banner, falsified by items 11–14 decided on 08-17/08-18; item #8's unchanged marker; item
  #6 "parked" against PROGRESS's "blocked on the YouTube key"; item #10's "ALL DECIDED" heading, under
  which a prose-quality sub-item is annotated "not raised" — that heading conceals a question that was
  never asked, and it must not be carried as evidence that the question is closed. Do **not** relocate
  the "stay unapplied" quote onto D-406; it lives in D-417 §A3.
- **Preserve verbatim / provenance-linked.** The meta-lesson verbatim: *"a status line is a measurement
  with an expiry date."* It is the intellectual origin of the as-of dating rule in
  `AUTHORITY_MODEL` §5.2 and it belongs in the archive banner's "Reason" line.

#### 2.F.4 `docs/FINAL_ARCHITECTURE.md` (185 lines) → `docs/archive/2026-07-21-final-architecture-projection.md` — TWO MANDATORY EXTRACTIONS FIRST

- **Fate.** ARCHIVE **and rename**, only after both extractions complete (§3 steps 1 and 2). This file
  is the audit's misleading-filename exhibit: "FINAL" reads as latest and definitive, while the file is
  a self-declared 2026-07-21 projection, roughly 10x smaller and three weeks older than
  `ARCHITECTURE.md`, with zero functional inbound references. The rename encodes what it is: a dated
  projection.
- **Current knowledge that moves — and this is the whole reason for the ordering constraint.**
  1. **The end-to-end deployed-topology diagram** → `ARCHITECTURE.md`, refreshed (§2.A.4). It is the
     only such diagram in the repository.
  2. **Open question 5 — the SPEC §5.33.3 six-schema logical split** → `ARCHITECTURE.md`'s new "Open
     architecture questions (undecided — do not treat as designed)" block, **plus** a one-line row in
     `PROJECT_STATE` §6.3 (`ARCH-21-SCHEMA-SPLIT`, DEFERRED). This file is the only record **that the
     decision is unmade** (SPEC §5.33.3 still *prescribes* the split as a requirement; no document
     records it as undecided): no read document settles it, no D-number owns it,
     `OPEN_DECISIONS` declares nothing open, and `ARCHITECTURE` never mentions a schema split.
     Repository state corroborates that no split is implemented (`packages/db/alembic/env.py` has no
     `include_schemas` and no `schema_translate_map`), and the deployed Postgres runs without it. If this
     file is archived before the extraction, **an unmade decision disappears from the corpus entirely.**
     No new decision is created by the extraction — the reopen condition is production schema design.
  3. The one-line as-built fact "today's system is one `intellichoice` Postgres database".
- **Historical knowledge archived in place.** The projection itself, its four decided open questions,
  its own self-retirement instruction (whose trigger fired 2026-07-22 and was never executed — which is
  how R2.1 and R5.2 were produced), and the storage-table row it appends to `ARCHITECTURE.md`'s table.
  After migration, **`ARCHITECTURE.md` is the single owner of the storage-split table**.
- **Decision reasoning that stays in `DECISIONS.md`.** D-004 (accepted — see below), D-082's patch, and
  the S32-era substrate decisions.
- **Evidence still available at.** `docs/archive/2026-07-21-final-architecture-projection.md` and
  `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
  (`ARCH-21-SCHEMA-SPLIT`, `RISK-GROUP-ARCH-AUTHORITY`).
- **Must NOT be copied (stale).** **The four decided questions presented as live** — questions 1
  through 4 are all decided, and the file presents all five identically, so from inside the file the one
  live item is indistinguishable from the four dead ones. Also: the claim that D-004 is still
  "proposed", when D-004 was accepted six days before this file's last edit; and every one of its
  status claims, nearly all of which are false. Adopt F-07's split when describing `ARCHITECTURE.md`:
  "behind on decisions" is **false** — ARCHITECTURE is current on decisions and stale only on session
  provenance (32 of 48 tagged).
- **Preserve verbatim / provenance-linked.** The five original open questions as a **set**, verbatim,
  inside the archived file — the set is the evidence that question 5 was never closed. The archive
  banner names the two extractions and their destinations so a future reader can verify nothing else
  was lost.

#### 2.F.5 `docs/S42_ORG_ASKS.md` (406 lines) → `docs/archive/2026-07-24-org-asks-drafts.md`

- **Fate.** ARCHIVE **and rename**, with the message text preserved verbatim. Sequenced **first** among
  the banner steps (§3 step 7a) because it is the purest wrong-action risk in the corpus: it tells a
  reader to send messages the organization has already answered. The `S42_` prefix asserts a session the
  content predates — it was drafted at S36 close-out on 2026-07-24, cut down 07-25, last amended 07-31,
  and D-151/D-152/D-153 are entirely absent from it.
- **Current knowledge that moves.** The per-message dispositions are stamped at the top of the archived
  file, from D-153, so the archive is self-explaining: which asks were answered, which were demoted,
  which were withdrawn. The still-live *substance* is already routed elsewhere —
  `ARCH-35-ORG-TIME` (BLOCKED), `RD-12-INGRESS` (PARKED), `INT-10-PEAK-CONCURRENCY` (PARKED) — so no
  obligation is lost by archiving the drafts.
- **Historical knowledge archived in place.** All four messages (A timezone, B DNS, C database hosting
  and API reliability, D peak concurrency) in Korean and English, plus the internal notes.
- **Decision reasoning that stays in `DECISIONS.md`.** D-153's per-ask dispositions, D-153 §3's
  withdrawal of the capacity purchase, and D-099/D-130/D-134 (the newest decisions this file cites).
- **Evidence still available at.** `docs/archive/2026-07-24-org-asks-drafts.md` and
  `docs/reference/integration/S42_OPEN_QUESTIONS.md` (the current form of the org-facing questions).
- **Must NOT be copied (stale).** **The three "Send now" markers.** Messages A and B are answered or
  demoted by D-153; Message C's hold-until-S42 release condition can no longer arrive **as written**;
  Message D prices a withdrawn purchase. The line-389 internal notes are **live, not expired**: Message A
  remains owed before S43 opens (frozen by D-152) and Message B before S48 — `ORG_TIME_CONFIRMED=false`
  still logs a WARNING every startup (`ARCH-35-ORG-TIME`, BLOCKED). The disposition stamp must say
  "pending, re-arms at integration reopen", never "expired". Nothing
  from this file becomes an instruction in the new tree.
- **Preserve verbatim / provenance-linked.** **The message text verbatim, in Korean and English** — it
  is the only send-ready form of these asks and the only Korean form. Also preserved: the
  one-ask-per-message rule, the corrected DST arithmetic note, and the deliberate exclusion of the
  committed-credentials topic — which is **half of UD-12(f)**, since the other org-facing draft
  implements the opposite policy. Record the tension; do not resolve it.
- **Tracking note:** the file is gitignored and untracked (`.gitignore:67`, deliberate per PROGRESS).
  The rename updates `.gitignore:67` to the new archive path in the same commit; the file **stays
  untracked** — whether it is ever committed is UD-12(f) and is not decided by a rename.

#### 2.F.6 `docs/plans/2026-07-18-expansion-plan.md` (958 lines) → `docs/archive/plans/2026-07-18-expansion-plan.md`

- **Fate.** ARCHIVE with an explicit executed-as header — **not deleted**, because `ROADMAP.md` carries
  a live pointer telling readers to read the plan rather than re-derive its design.
- **Current knowledge that moves.** Nothing moves out. The header states what it was executed as: the
  plan was fully executed as sessions S17–S28, shipped 2026-07-19/20.
- **Historical knowledge archived in place.** The task-to-session map and the D-049 renumber; the ten
  architecture calls; the schema, API, graph, LLM and frontend designs; the 13 tasks (§18) and twelve
  risks (§19). This design rationale is not restated in full anywhere else, which is why the file
  survives archival intact.
- **Decision reasoning that stays in `DECISIONS.md`.** D-049 and the S17–S28 decisions.
- **Evidence still available at.** `docs/archive/plans/2026-07-18-expansion-plan.md`, reachable from
  `docs/archive/README.md` and from the updated ROADMAP pointer.
- **Must NOT be copied (stale).** **§1's "Does not exist" claims** — every one of them is long false,
  and they sit 87 lines below the saving status line, so a reader who starts at §1 concludes that
  month-old shipped features are unbuilt. Also: the `effective_from: 2026-08-01 (future)` premise, now
  inverted; the internal authority tangle where two sections claim to supersede ROADMAP S17 while the
  file's own line 5 names ROADMAP its source of truth; and **the Mongo references**, which survive
  because `docs/plans/` was excluded from the MySQL sweep without being marked historical. The
  archive banner explicitly states that the file predates the D-082/D-111 MySQL correction — the
  Mongo text is not edited, it is dated.
- **Preserve verbatim / provenance-linked.** The ten architecture calls and the task-to-session map,
  which are the provenance for a large part of the current system's shape.

#### 2.F.7 `docs/plans/2026-07-19-branding-plan.md` (164 lines) → `docs/archive/plans/2026-07-19-branding-plan.md` — EXTRACT-FIRST

- **Fate.** SPLIT then ARCHIVE: promote the data (§3 step 4), archive the plan with an executed-as
  header reading "executed as Session 22.5; BD1–BD5 = D-065–D-069".
- **Current knowledge that moves.** The **brand table** (fonts, colors, gradient, geometry) and **BD3's
  standing do-not-revert rule** with its exact contrast ratios → `ARCHITECTURE.md`. A standing rule
  cannot live in a file whose line 2 says "planned, not started"; that is the whole argument for the
  extraction. *(The parallel promotion into `packages/ui-brand` is engineering work and is split out —
  W-32.)*
- **Historical knowledge archived in place.** The brand audit derived from the live WordPress theme
  CSS, the codebase recon, the token mapping, the four phases and the risks.
- **Decision reasoning that stays in `DECISIONS.md`.** D-065 → D-069, including the deliberate WCAG
  contrast deviation BD3 records.
- **Evidence still available at.** `docs/archive/plans/2026-07-19-branding-plan.md` and the as-built
  `packages/ui-brand` tokens.
- **Must NOT be copied (stale).** "Status: planned, not started" for a session executed the same day.
  And critically: **the instruction to log decisions at "the next free D-numbers — D-064 was the last
  used"**. The log is past D-423, so a reader following that line **mints duplicate decision IDs**. Fix
  this line even if nothing else in the file is touched (W-32). Also stale: the recon at line 73, which
  describes deleted files while telling the reader to trust it.
- **Preserve verbatim / provenance-linked.** BD3's exact contrast ratios and the ruling that *the
  site's dark CSS is Impreza defaults, not brand truth* — both are load-bearing for future visual work.

### 2.G The reconciliation artifacts (15 on disk + 4 proposal documents)

These are grouped by identical treatment. All are dated 2026-08-19 to 2026-08-20 and none is currently
indexed in `CLAUDE.md` — they reproduced the discoverability defect on the day they were created, which
is why routing them is part of this manifest rather than an afterthought.

#### 2.G.1 The two live registers (2 files) → `docs/reference/reconciliation-2026-08/`

`FINAL_OPEN_WORK_REGISTER.md` (7,418 lines, 166 entries) and `USER_DECISION_QUEUE.md` (1,006 lines,
UD-1 … UD-12).

- **Fate.** MOVE_TO_REFERENCE, **not archive**. They are point-in-time but load-bearing until their
  items close: `PROJECT_STATE` §4, §5, §6 and §7 each hold one line per item and link here for the
  evidence, the options and the reopen conditions. Archiving them would put the evidence for every
  active work item behind a do-not-treat-as-current banner.
- **Current knowledge that moves.** Nothing moves out — `PROJECT_STATE` *links* rather than restating,
  by the single-home rule. What arrives is a header stating the reference relationship: this register
  is the provenance backbone for `PROJECT_STATE`, and an item deleted from `PROJECT_STATE` on
  resolution remains readable here.
- **Historical knowledge archived in place.** The RESOLVED, SUPERSEDED and OBSERVATION_ONLY entries
  (41 of 166) stay inside the register as its historical tail — they are the record of what was checked
  and found closed, and they are the discoverability path named in Appendix A.
- **Decision reasoning that stays in `DECISIONS.md`.** Everything the register cites. The register is
  evidence, never authority for intent.
- **Evidence still available at.** The 13 archived artifacts, each cited by name from register entries.
- **Must NOT be copied (stale).** The registers are as-of 2026-08-20; when `PROJECT_STATE`'s snapshot
  date advances, a register entry is evidence for what was true on 2026-08-20, not a current-state
  claim. Do not restate a register count inside `PROJECT_STATE` without its date.
- **Corrections to apply to the moved copies (step 9c).** `USER_DECISION_QUEUE.md:935` gives
  UD-12(f)'s "Register entry" as `RISK-R7.2`, but the register's entry key is **`COMMITTED-ORG-DRAFTS`**
  — R7.2 is the *risk* id that maps to it (register §11(h)). Verified 2026-08-20 in both files. The fix
  is a one-line cross-reference correction on the moved copy: cite `COMMITTED-ORG-DRAFTS` and note
  "(from risk R7.2)". This matters because `PROJECT_STATE` §5's table carries a register-key column, and
  a key that resolves to nothing breaks the link the whole design depends on. Two further key defects
  ride the same step: the register's own `COMMITTED-ORG-DRAFTS` entry carries "Work/Issue ID (topic key):
  `R7.2`" — normalize to the entry key with "(from risk R7.2)"; and `USER_DECISION_QUEUE.md`'s UD-10
  cites bare `REQ-27`, which conflates `REQ-27-FROZENSET` (ACTIVE_IMPLEMENTATION, unblocked local test)
  with `REQ-27-TOKEN-CONTRACT` (DEFERRED to integration) — qualify both citations. Also delete the queue
  file's two trailing tool-call markup lines (`</content>`, `</invoke>`) on the moved copy (step 9d).
- **Preserve verbatim / provenance-linked.** The UD entries' "why evidence cannot decide it" and
  "default safe action" fields verbatim — they are what stops a future agent from inferring an answer.
  And every measurement with its date, environment and denominator.

#### 2.G.2 The 12 evidence and register artifacts → `docs/archive/reconciliation-2026-08/`

`CLAIM_LEDGER.md`, `DECISION_SUPERSESSION_MAP.md`, `DEPLOYED_INFRA_DRIFT_REGISTER.md`,
`DEPLOYED_INFRA_STATE_EVIDENCE.md`, `DOCUMENTATION_RISK_REGISTER.md`, `DOCUMENT_INVENTORY.md`,
`LIVE_BEHAVIOR_EVIDENCE.md`, `LIVE_BEHAVIOR_FINDINGS.md`, `LOCAL_EXECUTION_EVIDENCE.md`,
`LOCAL_EXECUTION_FINDINGS.md`, `REPOSITORY_DRIFT_REGISTER.md`, `REPOSITORY_STATE_EVIDENCE.md`.

- **Fate.** ARCHIVE with banners. They are point-in-time audit evidence, consulted for provenance only.
- **Current knowledge that moves.** Nothing directly — everything actionable was already merged into
  the 166 register entries (349 source items across seven extractors). That merge is what makes
  archiving these safe.
- **Historical knowledge archived in place.** The raw evidence: command outputs, AWS reads, code
  readings, the 102 repository drift rows, the 12 deployed-infrastructure rows, the 70 claim-ledger
  rows, the 29 supersession chains, the 49 documentation risks, the per-document inventory profiles.
- **Decision reasoning that stays in `DECISIONS.md`.** All of it. These artifacts *report*; they never
  decide.
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/…`, indexed from
  `docs/archive/README.md`, and cited by key from the reference register.
- **Must NOT be copied (stale).** Any status column from these files, into any active document, without
  its as-of date. Two specific traps: `DEPLOYED_INFRA_DRIFT_REGISTER.md:361` §3.2 still lists RD-02 as a
  user decision (the addendum at `:149` wins — D-310 is executed), and `CLAIM_LEDGER.md`'s WORK-05 cell
  says "2 commits ahead" where the figure is 1 (W-13). Route these to the ledger owner, not into the
  canonical documents; and a third trap — RD-02's **in-entry** "Genuine decision required?" field,
  *below* the :152 resolution addendum, still reads "the exposure is live and `AWSCURRENT`". The step-7d
  annotation covers that field too, and the resolution stamp is placed as the entry's **last** line.
- **Preserve verbatim / provenance-linked.** All measurements with date, environment and build SHA —
  most importantly `LIVE_BEHAVIOR_FINDINGS.md`'s 10.55-second guest QA latency, which is a
  **pre-D-423** number measured on build `gha-44a12dfc9549` and must never be quoted without both facts.

#### 2.G.3 `REMEDIATION_D310_ROTATION.md` (121 lines) → `docs/archive/reconciliation-2026-08/`

- **Fate.** ARCHIVE as a **resolved remediation record**, with a pointer added from `DECISIONS.md`'s
  D-310 chain at migration time. This is the file that proves D-310 is history rather than exposure.
- **Current knowledge that moves.** (a) `PROJECT_STATE` §9 carries the **standing framing only, quoted
  per AUTHORITY_MODEL §5.7** (resolved historical remediation, never an active exposure) with links to
  this record and to register `D310-ROTATION`; the execution timeline, probe matrix and plan-exit
  evidence live here and in the register, not in PROJECT_STATE. (b) The three
  surviving residuals become `D310-RESIDUALS` in `PROJECT_STATE` §4.1: the dead `localStorage`
  credential that now fails as an unexplained 404 and cannot be enumerated or cleared from AWS or the
  repository; the `make load-staging-learning` docker environment pass-through that was **never
  re-measured for `ps` visibility**; and `e2e/README.md`, which still documents the pre-D-310 export
  shape. (c) The accepted residual that **no standing rotation mechanism was added** — no `keepers`, no
  rotation trigger, no rotation resource — accepted because the S44 plan deletes these secrets when real
  authentication lands.
- **Historical knowledge archived in place.** The step-0 CloudTrail access review (5 Terraform reads
  during the known 2026-08-18 apply, 3 Fargate-agent reads at task startup, **zero**
  `UpdateSecret`/`DeleteSecret`/`RestoreSecret`; `PutSecretValue` = exactly 2, both the 2026-07-24
  Terraform creation writes), the six safeguards, and the before-and-after secret
  metadata.
- **Decision reasoning that stays in `DECISIONS.md`.** D-310 itself. Its *decline* stands as the
  historical record and is **operationally superseded** — that phrasing matters and is the annotation
  `OPEN_DECISIONS` #8 receives.
- **Evidence still available at.** `docs/archive/reconciliation-2026-08/REMEDIATION_D310_ROTATION.md`.
- **Must NOT be copied (stale).** Anything that presents D-310 as an active credential exposure. The
  `ps`-visibility item is **unmeasured, not cleared** — do not upgrade it to "clear", and do not
  downgrade it to "resolved" because the rotation succeeded.
- **Preserve verbatim / provenance-linked.** No secret value, ever — not the old ones either. The
  transcript that captured the old values still exists wherever transcripts are retained, and those
  values are now worthless; that fact is recorded, the values are not.
- **A fourth, self-neutralising residual is recorded:** the transcript that captured the old values still
  exists wherever transcripts are retained — the values are dead post-rotation; listed so the
  three-residual list is not mistaken for exhaustive.

#### 2.G.4 The four proposal documents (this directory)

| document | fate at migration |
|---|---|
| `PROJECT_STATE.md` | promoted to `docs/PROJECT_STATE.md` — the new entry point |
| `AUTHORITY_MODEL.md` | promoted to `docs/reference/AUTHORITY_MODEL.md`; its precedence table is also summarized in `PROJECT_STATE`'s documentation map |
| `DOCUMENT_MODEL.md` | after the migration executes → `docs/archive/reconciliation-2026-08/` (it describes a transition that has completed) |
| `MIGRATION_MANIFEST.md` (this file) | after the migration executes → `docs/archive/reconciliation-2026-08/`, as the record of what moved where |

- **Must NOT be copied (stale).** Once promoted, `PROJECT_STATE.md` owns current state and this
  manifest owns none of it. If a future reader finds this manifest disagreeing with `PROJECT_STATE`,
  `PROJECT_STATE` wins, and if `PROJECT_STATE` disagrees with primary evidence, the evidence wins
  (`AUTHORITY_MODEL` §3.2).
- **Preserve verbatim / provenance-linked.** The archived manifest is the audit trail for every
  extraction: if something is later found missing, this file names where it was supposed to land.

---

## 3. Ordered migration steps

Eighteen steps (0a–15) in five phases. **Hard constraints are flagged `HC-n` and are not optional orderings** —
each one prevents a specific, named loss.

> **HC-0 (applies to every step).** No step answers a user decision, converts a `UD-x` into a `D-xxx`,
> takes a D-152-frozen action, changes application code, or invents an identifier. A step that appears
> to require any of those is mis-specified — stop and surface it.

### Phase 0 — Promote and prepare (steps 0a–0c). HC-8: nothing else is written or banner-stamped until step 0a completes.

**Step 0a — Create the target skeleton and promote.** Create
`docs/reference/{,integration,org-drafts,audits,reconciliation-2026-08}/` and
`docs/archive/{,plans,reconciliation-2026-08}/`;
`git mv docs/reconciliation/proposal/PROJECT_STATE.md docs/PROJECT_STATE.md` and
`git mv docs/reconciliation/proposal/AUTHORITY_MODEL.md docs/reference/AUTHORITY_MODEL.md`. Every later
write into `PROJECT_STATE` (steps 2, 10, 11) targets the real file; every banner's `Current state:` line
points at a file that exists (O1, §10.1, §8.1 satisfied).

**Step 0b — Hazard grep (read-only).** Grep `INCIDENT_RESPONSE.md` for any `D-093 → D-137` RDS-rotation
routing and record the result before anything touches the file (O12). It is a read; it conflicts with
nothing.

**Step 0c — Vintage headers (W-38, three files).** Add the one-line vintage header to `SPEC.md`,
`INCIDENT_RESPONSE.md` and `QUESTION_GENERATION.md`. `CLAUDE.md`'s last-reviewed marker lands at step 14
(HC-7) — one instruction, not two.

### Phase 1 — Extract (steps 1–6). Nothing is banner-stamped, renamed or moved during this phase.

> **HC-1 — extract before archive.** Steps 1 through 6 complete before step 7 begins. Every document
> routed to the archive holds at least one piece of still-live knowledge; archiving first turns a
> reorganization into a loss.

**Step 1 — Extract the topology diagram.**
`FINAL_ARCHITECTURE.md:46-105` → `ARCHITECTURE.md`, refreshed against the measured 2026-08-20 deployed
state (two ECS services on build `gha-44a12dfc9549`, learning task definition `:150` at 2/2, chat `:148`
at 1/1, two RDS instances, one NAT gateway). It is the only end-to-end deployed-topology diagram in the
repository. Carry the diagram; carry none of the surrounding prose.

**Step 2 — Extract the six-schema question, and only then the database one-liner.**

> **HC-2 — this is the single highest-loss ordering constraint in the migration.**
> `FINAL_ARCHITECTURE.md:179-180` (open question 5) is **the only record anywhere that this decision
> is unmade**: whether to adopt SPEC §5.33.3's six-schema logical split (`learning`, `rag`,
> `memory`, `checkpoint_learning`, `checkpoint_chat`, `evaluation`). SPEC §5.33.3 still *prescribes*
> the split as a requirement, but no document settles it and no D-number owns it. Archive the file
> first and the question leaves the corpus.

- Destination A: a new block in `ARCHITECTURE.md` titled **"Open architecture questions (undecided — do
  not treat as designed)"**, whose one entry is this question, with its reopen condition (production
  schema design) and the repository fact that no split is implemented
  (`packages/db/alembic/env.py` has no `include_schemas` and no `schema_translate_map`; the deployed
  Postgres runs without it).
- Destination B: one row in `PROJECT_STATE` §6.3 — `ARCH-21-SCHEMA-SPLIT`, DEFERRED.
- Destination C: a `TRACEABILITY.md` sub-row under its §5.33 row, dispositioning §5.33.3's
  six-schema split (and its Aurora/Multi-AZ siblings) as **deferred — not traced**, keyed
  `ARCH-21-SCHEMA-SPLIT` — so TRACEABILITY cannot imply coverage while ARCHITECTURE records the
  question open.
- Also extract: the as-built one-liner "today's system is one `intellichoice` Postgres database".
- **No new decision is created.** Recording a question as open is not deciding it.

**Step 3 — Extract the frozen and downstream session specifications.**
Create `docs/reference/integration/ROADMAP_FROZEN_SESSIONS.md` from `ROADMAP.md`: the S42–S51 scope
bullets and rollout paragraph (`ROADMAP.md:1436-1530`) with their **five embedded constraints** —
the D-153 §5 role gate (production `role` must never by itself grant an elevated role), the six
structural dev-fake mismatches, the two-source `BranchInfo` merge, the D-153 §4 session-window
assertion, and D-167's `/dev/token` deletion cascade including the `sub` assertion — plus the
SPEC-section-to-session mapping for those sessions. **ROADMAP holds NO "Done when" acceptance
criteria in that range (zero occurrences between lines 525 and 1769) — do not author any during
extraction.** The new file carries a line-1 D-152 freeze banner above the H1, and each block carries
its own status line: frozen-by-D-152 (S43–S47) or unstarted-and-downstream-of-frozen (S48–S51).
Today S48–S51 carry no freeze annotation at all.

**Step 4 — Extract the brand data.**
`docs/plans/2026-07-19-branding-plan.md` → `ARCHITECTURE.md`: the brand table (fonts, colors, gradient,
geometry) and **BD3's standing do-not-revert rule** with its exact contrast ratios. A standing rule
cannot live in a file labelled "planned, not started".

**Step 5 — Reconcile `HINT_SOLUTION_REVIEW.md` to the D-262+ horizon.**

> **HC-3 — reconcile before moving.** Seven source files and two scripts already cite this document as
> normative while `CLAUDE.md` calls it "the planned design". Moving it to `reference/` first would
> relocate a wrong front page and bless it as durable.

Apply the five enumerated edits (W-07): replace "the loop around them is not built" with **"built but
uncalled"**; reconcile reviewer C's two contradictory states; tick §8 steps 4 and 7 (both completed
2026-08-10 — D-254 at 29.1 cents; D-252, 126 readings, minimum observed 2); delete the three "has never
been measured" assertions about `_HINT_QUALITY_REJECT_BELOW`; correct the `ai_pipeline.py` constant
citation to a symbol reference. **The three in-code docstrings are engineering work and are excluded
from a documents-only migration** — record them as a split, do not leave them unnamed.

**Step 6 — Extraction-completeness gate (a checkpoint, not an edit).**
Before any archival, confirm each archive-bound document's still-live knowledge has a landing place:

| archive-bound document | live knowledge | landed by |
|---|---|---|
| `FINAL_ARCHITECTURE.md` | topology diagram; open question 5; one-database fact | steps 1–2 |
| `ROADMAP.md` | S42–S51 scope bullets + the five embedded constraints (no "Done when" exists in that range — none authored) | step 3 |
| `2026-07-19-branding-plan.md` | brand table; BD3 do-not-revert rule | step 4 |
| `PROGRESS.md` | live carry-over items | Phase-4 register (register key for every live item; a `PROJECT_STATE` row **iff** the disposition is open — `SNS-CONFIRMATION` and `WORK-04-ANSWER-CACHE` are RESOLVED and correctly row-less) |
| `OPEN_DECISIONS.md` | the seven §11(g) live items (see §2.F.3) | `PROJECT_STATE` §9; `WORK-40` and `WORK-44-DECIDED-NOT-BUILT` |
| `S42_ORG_ASKS.md` | message text; live ask substance | verbatim in the archived file; substance in `ARCH-35-ORG-TIME`, `RD-12-INGRESS`, `INT-10-PEAK-CONCURRENCY` |
| `2026-07-18-expansion-plan.md` | design rationale (stays whole) | archived intact; ROADMAP pointer repathed |
| the 13 audit artifacts | all actionable content | merged into the 166 register entries |

If any row cannot be checked off, **stop**. A failed row is a finding, not a formality. Stopping is
reversible: the tree was committed clean at Phase 0, so a partial Phase 1 is unwound with `git revert`.

### Phase 2 — Banners and renames (steps 7–8). Still no file has moved besides step 0a's two promotions.

**Step 7 — Banners and renames, in this internal order.**

- **7a. `S42_ORG_ASKS.md` first.**

  > **HC-4 — sequence this before every other banner.** It is the only document in the corpus whose
  > stale instruction causes an **irreversible external action**: three "Send now" markers for asks the
  > organization has already answered or that were demoted. Every other stale document causes wasted
  > work; this one sends a message.

  Rename to `2026-07-24-org-asks-drafts.md`, stamp the per-message D-153 dispositions at the top, and
  add the archive banner. The message text is untouched.

- **7b. `FINAL_ARCHITECTURE.md`** → rename to `2026-07-21-final-architecture-projection.md` with a
  banner naming both extractions and their destinations. Permitted only if steps 1 and 2 are complete.

- **7c. D-152 freeze banners.** A mandatory line-1 banner on `INTEGRATION_PLAN.md` (which contains zero
  occurrences of `D-152` and, read standalone, directs all four forbidden actions), and on
  `S42_DISCOVERY.md` (also zero occurrences) plus section-level supersession tombstones on its §7–§9.
  Copy the banner shape from `S42_OPEN_QUESTIONS.md`, which is the only S42 file where the freeze is
  visible from inside. Annotate `S42_OPEN_QUESTIONS.md`'s resolved rows in-table and point its E-group
  at `S42_SECURITY_REPORT.md`; **do not blanket-retire its line 110** — the E-group notification half is
  still valid.

- **7d. Archive banners** on `ROADMAP.md`, `PROGRESS.md`, `OPEN_DECISIONS.md`, both `docs/plans/` files
  (executed-as headers) and the 13 audit artifacts. `OPEN_DECISIONS` #8 is annotated
  **superseded-operationally** in the same pass, because as written it tells the next reader that the
  D-310 exposure is live. The archive-half corrections of W-10, W-11, W-12, W-13, W-14, W-18, W-19 and
  W-44 are executed **here**, at banner time, per rule 11 — after step 9 those files are frozen.

- **7e. Pre-move reference-tier reconciliation (O13/O14).** `U7_CHECKPOINT_CONSOLIDATION.md`'s
  completion banner + §9.2/§10 annotations + as-of banner (W-08); `S42_SECURITY_REPORT.md`'s send-status
  line; `ENROLLMENT_FAQ_APPROVAL.md`'s two dead pointers (W-34's file half). All three land before
  step 9 moves the files.

**Step 8 — Create `docs/reference/audits/README.md` (early, before the audit worklist rows).**

> **HC-5.** Every cross-document finding lookup after 2026-08-16 is ambiguous until this file exists.
> `AUDIT_LIVE_2026_08_17.md` reuses the entire `AUD-L-01`…`AUD-L-19` range with unrelated meanings,
> including the very ID that had already been renumbered because of an earlier collision.

Contents: the namespace map for all three registers; the rule that a bare audit ID never uniquely
identifies a finding and citations read `<document>:<id>`; one sentence per register stating its scope,
freeze date and relationship to the other two; and the statement that **no mechanical re-map exists**,
so no renumbering is attempted. W-12, W-17 and W-26 depend on this file.

### Phase 3 — Moves and single-homing (steps 9–13)

**Step 9 — Execute the moves.** Move every file to the destination named in §2 (the directories exist
since step 0a). Three sub-steps that are easy to forget:

- **9a.** Repath every inbound pointer that now resolves to an archive path — most importantly
  ROADMAP's live pointers into `docs/plans/` (`ROADMAP.md:5`, `:326-331`), which must be repathed and
  labelled historical rather than deleted.
- **9a(ii).** Repath every inbound reference to `OPEN_DECISIONS.md` and `PROGRESS.md` from the surviving
  active files (`DECISIONS.md` ~18 and ~32 citations, `ARCHITECTURE.md`, `TRACEABILITY.md`, `CLAUDE.md`)
  and from the reference-tier movers to their `docs/archive/` paths — keeping a filename does not
  preserve a citation whose path changes. The mid-file-landing hazard on these two high-traffic archives
  is accepted and recorded (banners are top-of-file; grep lands mid-file).
- **9b.** Write the out-of-repository references as explicitly out-of-repository:
  `docs/codebase-analysis/` resolves to `../IntelliChoice-web/docs/codebase-analysis/` and must **not**
  be "fixed" into a local path that will never exist (W-34).
- **9c.** Apply the one-line register-key correction to the moved copy of `USER_DECISION_QUEUE.md`:
  line 935 cites UD-12(f)'s register entry as `RISK-R7.2`, but the register's entry key is
  **`COMMITTED-ORG-DRAFTS`** (R7.2 is the risk id that maps to it, per register §11(h)). Both sides
  verified on disk 2026-08-20. `PROJECT_STATE` §5 keys the UD table by register key, so an unresolvable
  key breaks the link the design depends on. Two further corrections ride this sub-step, per §2.G.1:
  the register's own `COMMITTED-ORG-DRAFTS` topic-key field (`R7.2` → the entry key, with "(from risk
  R7.2)"), and UD-10's bare `REQ-27` citation (qualified as `REQ-27-FROZENSET` versus
  `REQ-27-TOKEN-CONTRACT`).
- **9d.** Delete `USER_DECISION_QUEUE.md`'s two trailing tool-call markup lines on the moved copy.

**Step 10 — Single-home the duplicated facts.** For each, one owner and pointers elsewhere:

| fact | single owner after migration |
|---|---|
| storage-split table | `ARCHITECTURE.md` (the second owner is archived) |
| §7-R8 / §7-R9 expiry conditions | `PROJECT_STATE` §6.4, with `ARCHITECTURE.md` and `INTEGRATION_PLAN.md` pointing at it (W-22) |
| scheduler / nightly-job state | `ARCHITECTURE.md`, stated once (W-05) |
| session status | `docs/archive/ROADMAP.md` for history; `PROJECT_STATE` for what is live |
| finding counts | mechanically derived (the anchored awk), never hand-maintained (W-12) |
| the four production security findings | `docs/reference/org-drafts/S42_SECURITY_REPORT.md`, with the other three copies pointing at it |
| checkpoint sizing | **two owners on purpose** — development ~4.8 GB and staging ~285 MB are different measurements, each labelled with its environment; never "resolved" by picking one |

**Step 11 — Execute the worklist rows whose step is 11**, in batch order. Rows with work at other
steps are listed below; only their step-11 halves (if any) run here, and nothing already done at an
earlier step is re-executed: W-38 (wholly at steps 0c + 14 — nothing at step 11), W-17/W-26 (step 8;
W-26's cross-reference sentences at 11 batch B), W-20/W-36 (steps 3/7a/7c/14), W-21 (steps
1–2/7b/10/14), W-32 (steps 4/7d/9a), W-34 (steps 7e/9a/9b), W-29 (steps 2/7e/14), W-28 (steps
7c/7d/14; its 11-batch-H annotations ride the archived copies stamped at 7d), W-19 (step 7d,
annotation half with it), W-23 (steps 3/7d/9; annotations at 11 batch H), W-27 (steps 7/14), W-30
(step 14), W-08 (step 7e), archive-halves of W-10/11/12/13/14/18/44 (step 7d).

> **HC-6.** The vintage headers (W-38) landed at step 0c (`SPEC.md` — which stays active —
> `INCIDENT_RESPONSE.md`, `QUESTION_GENERATION.md`) and land at step 14 for `CLAUDE.md`; nothing of
> W-38 remains at step 11. Within step 11, batch A runs first (W-35's session-label
> disambiguation), because a stale line is only detectable if the document says when it was last
> true and an ambiguous label poisons every owner statement downstream.

**Step 12 — Create `docs/archive/README.md`.** The archive index: for every archived file, what it is,
why it was archived, what superseded it, and its as-of date. Without this the archive becomes a place
where knowledge is technically present and practically unreachable.

**Step 13 — Summarize.** The promotions happened at step 0a; here, summarize `AUTHORITY_MODEL`'s
precedence table in `PROJECT_STATE`'s documentation map and verify both promoted files' inbound links
resolve.

### Phase 4 — Index and verify (steps 14–15)

**Step 14 — Rewrite `CLAUDE.md`'s index. LAST.**

> **HC-7.** The index is rewritten only after every destination path exists, because it is the one file
> whose drift is unpoliced — nothing in the repository references `CLAUDE.md` back. An index written
> against paths that do not yet exist is a new instance of the defect being fixed. Note that both
> README files (steps 8 and 12) must exist first, since the index links to them. HC-7 now also lists
> **step 0a** as a prerequisite: the index names `docs/PROJECT_STATE.md`, which exists from step 0a.

The rewrite: point to `docs/PROJECT_STATE.md` first; index every non-archive document, or list it as
deliberately unlisted with the reason; add a last-reviewed date; fix the `OPEN_DECISIONS` description
(the highest-value single edit in the migration — it is what currently sends every session to a closed
file looking for work); correct SPEC's line count; add one clarifying line on rule 8 (the image
requirement belongs to a deferred feature); add the CloudFront-domains sentence from `RD-12-INGRESS`;
and cross-link `INTEGRATION_PLAN.md` and `S42_DISCOVERY.md` from the D-152 section; fix the
`HINT_SOLUTION_REVIEW.md` description ("the planned design" → "the as-built review instrument —
reconciled at step 5"); state the architecture hierarchy (ARCHITECTURE.md is the single as-built
authority and sole storage-table owner); reword "the spec wins on detail" from a conflict-resolution
rule to a granularity rule, pointing at `reference/AUTHORITY_MODEL.md` §3; and apply rule 1's D-050
clause **in W-42's required wording exactly**. Closing check: grep §4 for every row naming `CLAUDE.md`
and confirm each landed.

**Step 15 — Post-migration verification and archival of the instruments.** Run the ten proof points in
§5 and **record each outcome inline in §5 with its date and runner**; a failed proof point blocks
archival (O20). Then add the §15.1 banner to `DOCUMENT_MODEL.md` and this manifest (`Superseded by: the
executed tree; see docs/archive/README.md`), and `git mv` both to
`docs/archive/reconciliation-2026-08/`. Record the migration as a decision in `DECISIONS.md`, citing the
authority model's precedence ladders.

---

## 4. DOCUMENTATION_ONLY worklist — all 44 entries

These are the register entries that close with document edits and no code change. Each row: the register
key, the fix, the source documents holding the stale or missing information, and the destination or
explicit disposition with its migration step.

**Execution order across all steps.** A = foundations (W-38 at step 0c; **W-35 — session-label
disambiguation, prerequisite for W-43 and all owner statements**); B = identifier namespaces, early
(W-17, W-26, W-12); C = freeze coherence, one pass per file (W-20, W-36); D = architecture authority
(W-21, W-22, W-05, W-03); E = ops documents (W-07 at step 5, W-08, W-06, W-33, W-37); F = SPEC
governance (W-15, W-24, W-43); G = decision-log hygiene (**W-25 first — its ID index is W-16's
prerequisite**, then W-16, W-18); H = current-state split and naming (W-23,
W-19, W-28, W-29, W-31, W-32, W-27); I = citations, counts and wording (**W-39 first — the convention
governs W-11/W-14/W-40's edits**, then W-01, W-02, W-03's
wording half, W-04, W-09, W-10, W-11, W-13, W-14, W-34, W-40, W-41, W-42, W-44). W-30 executes at
**step 14**, not step 11.

**Thirteen rows carry an engineering half**: W-03, W-04 (two terraform variables files), W-05, W-06,
W-07, W-11, W-14, W-22, W-31, W-32, W-40 (an e2e spec header), W-41, W-42 (a chat-api docstring and a
metrics label comment). W-25 and W-29 are documentation-only (`Owner type: documentation` in the
register) — their earlier listing was an error.
Each is named in its row and becomes an engineering item, never a silent omission.

### Rows W-01 … W-14 — specific document defects

| # | register KEY | fix | source document(s) | destination / step |
|---|---|---|---|---|
| W-01 | `D136-PRICE-TABLE` | Add the AUD-F-28 resize caveat: the sweep ran on the old 256/512 task, so per-task columns understate learning-api by 2x. Cross-reference `COST-29-EXTRAPOLATION-BAN`'s extrapolation rule and DRIFT-56's plan-versus-ceiling note. | `ARCHITECTURE.md` (D-136 price table) | `ARCHITECTURE.md`, step 11 batch I. Also absorbs `COST-25-ALARM-COUNT`'s **two** residual cost-model lines: alarm billing (24 of 34 billable, ~$2.40/month) **and, as its own sentence, the X-Ray trace-storage line (91% of the 100,000-trace free tier, forecast 148,599)** — the register forbids folding the X-Ray line into the alarm note. |
| W-02 | `SPEND-ATTRIBUTION-DOC` | Two edits marking per-student/session spend attribution resolved (built by D-400, `trace_id` join, 2209/2212 coverage; ROADMAP W8 closed 2026-08-17). | `AUDIT_2026_08_16.md` (no resolution marker while the adjacent paragraph has one); `PROGRESS.md` ("the last two observability items") | `reference/audits/AUDIT_2026_08_16.md` + `archive/PROGRESS.md`, step 11 batch I. Convention recommendation (date audit findings in place) folded into step 12's archive README. |
| W-03 | `DRIFT-24-ARTIFACT-FRESHNESS` | Reword the frontend deploy gate to describe the procedure it actually is: the 711-line workflow contains no content-hash comparison, and neither does any make target or script. | `ARCHITECTURE.md` (deploy-gate paragraph) | `ARCHITECTURE.md`, step 11 batch D/I. **Engineering half split:** implementing a real freshness check rides on `LB-05-DEPLOY-GAP` (UD-1), not on this row. |
| W-04 | `DOC-DEPLOYED-STATE-CLAIMS` | One edit pass over seven document statements about deployed state that a live AWS read contradicts. Record ARCH-15 as WEAKENED. | `DECISIONS.md` D-419 (the NAT sentence); `terraform/modules/rds-postgres/variables.tf` + its `rds-mysql` twin; `PROGRESS.md` (two "unapplied" statements); `OPEN_DECISIONS.md:15`; `ARCHITECTURE.md` (no `make image-check` section; the single-flag NAT gate prose) | `ARCHITECTURE.md` + `DECISIONS.md`; the PROGRESS and OPEN_DECISIONS statements are **quarantined behind archive banners** rather than edited (step 7d). Step 11 batch I. Cautions: do not over-correct into "Free Tier is irrelevant"; do not move the "stay unapplied" quote onto D-406 (it lives in D-417 §A3). Lesson to record once: a commit title claiming an apply is not an apply. Also covers `OPEN_DECISIONS`' "staging numbers nobody has read" line (read 2026-08-14) and D-419's PendingConfirmation dating + NAT sentence (moved here from W-28 — single owner). **Engineering half split:** the two `rds-*/variables.tf` comment updates. |
| W-05 | `DOC-SCHEDULER-SECTIONS` | Delete or date the two stale per-pipeline sections that contradict the file's own enabled-schedules list, and disambiguate the retention referent in favour of `retention-purge`. | `ARCHITECTURE.md` (four places, self-contradicting) | `ARCHITECTURE.md`, step 10 (single-homing) + step 11 batch D. Keep RD-01's distinction: "scheduled" does not imply "observed to have run successfully". **Engineering half split:** the `scheduled-jobs` module header comment (shared with W-41). |
| W-06 | `DOC-CONTENT-PIPELINE` | Six content-pipeline edits: evict or date the superseded Mistral "Next:" imperative; family B no longer routed to Phase R; grade bands 4 → 7; family C ungated; reconcile `validate_authored_item`'s eleven checks against the four unimplemented SPEC bullets; fix the fuzzy 5–7 volume-target provenance. | `QUESTION_GENERATION.md`; `CONTENT_COVERAGE.md` (grade-band and family-C rows); `DECISIONS.md` D-223/D-273/D-313/D-342 (three renderings of 5–7) | `reference/QUESTION_GENERATION.md` + `reference/CONTENT_COVERAGE.md`, step 11 batch E. **Engineering half split:** nothing regenerates `CONTENT_COVERAGE.md` — make it an output of `scripts/build_content_coverage.py`. DRIFT-31's delegation direction is flagged for an explicit ruling if wanted, not decided here. |
| W-07 | `DOC-HINT-SOLUTION-REVIEW` | The five enumerated edits plus the wording "built but uncalled": the loop is built (`review_loop.py`); reviewer C's two states reconciled; §8 steps 4 and 7 ticked (D-254 at 29.1 cents, D-252 with 126 readings and minimum observed 2); the three "never measured" assertions about `_HINT_QUALITY_REJECT_BELOW` deleted. | `HINT_SOLUTION_REVIEW.md` (nine locations); `CLAUDE.md` (calls it "the planned design") | `reference/HINT_SOLUTION_REVIEW.md` — executed at **step 5**, before the move (HC-3). Highest ops-document priority; the file **cannot** be archived. **Engineering half split:** three source docstrings (`review_loop.py`, `review_panel.py`, `hint_solution_repair.py`). |
| W-08 | `DOC-U7-BANNER` | Add a completion banner pointing at D-333; annotate §9.2 (`learning_sessions` is built, migrated, modelled, with a scheduled producer) and §10 (the duplicate `learning_gain` row was closed by D-336) as answered; add an as-of banner and an absolute date to every self-expiring claim. | `U7_CHECKPOINT_CONSOLIDATION.md` (status line, §9.1 block, §9.2, §10) | `docs/U7_CHECKPOINT_CONSOLIDATION.md` — executed at **step 7e**, before the move (O13). One banner closes DRIFT-47, DRIFT-94 and DRIFT-95 together. |
| W-09 | `H2-AUDC23` | Write one §7-style residual-risk line recording the access-hint flip as **"measured below 26%, not certified"** — the shipped remedy verified live 0/10, D-178 declining to certify and D-179 marking every non-shipped row a lower bound. | wherever AUD-C-23 is tracked: `AUDIT_FINDINGS.md` (the AUD-C-23 entry) and the D-172 … D-179 chain in `DECISIONS.md` | `reference/audits/AUDIT_FINDINGS.md` + `DECISIONS.md`, step 11 batch I. Caution: do not "improve" recall reporting by dropping the negative controls (D-221). |
| W-10 | `ACCESS-HINT-FIGURES` | Restate REQ-46 with D-371's numbers **naming the denominator** (2/8 versus 2-of-6-reachable) or the defect reproduces; normalise the precision polarity; correct the "shipped ceiling of 0.40" label, which matches no constant — the live rule is three constants and 0.45 is the fallback. | `DECISIONS.md` (the superseded recall/precision pair; the 0.40 label; D-371's replacement); the Phase-2 `CLAIM_LEDGER.md` REQ-46 row | `DECISIONS.md` + `archive/reconciliation-2026-08/CLAIM_LEDGER.md`, step 11 batch I. |
| W-11 | `TRACEABILITY-ARITHMETIC` | Re-derive three attributions by quoting the decisions or record them explicitly as inferences (D-004; "§6.19 Phase 18 (D-078)"; D-087/S50 A7); correct the 37-of-37 label over a 36-section launch-scope denominator and the stale "21 of 37" running total; delete or date the 16-section present-tense tail under the "nothing remains" banner; add GuardDuty to both S50 A7 scope lists. | `TRACEABILITY.md` (eleven locations); `ROADMAP.md` (two); `INTEGRATION_PLAN.md` (one) | `TRACEABILITY.md` (active) + `archive/ROADMAP.md` + `reference/integration/INTEGRATION_PLAN.md`, step 11 batch I. Coverage is complete — only labels are wrong. **Engineering half split:** DRIFT-100's mechanism-strength claim is more than a count. |
| W-12 | `AUDIT-COUNT-INSTRUMENT` | Give every finding count an explicit scope label; execute the anchored awk and record the **actual** output; verify every section has a row; confirm the four extra-pipe rows keep status in field 5. | `AUDIT_FINDINGS.md` (four locations); `ROADMAP.md` (three) | `reference/audits/AUDIT_FINDINGS.md` + `archive/ROADMAP.md`, step 11 batch B — **after step 8**. "0 open findings" is true of one register frozen 2026-08-05 and unknown project-wide, while the 08-16 and 08-17 audits filed 46 and 48 findings in separate namespaces. Paired with W-26. |
| W-13 | `SUITE-COUNT-CITATIONS` | Attach the exclusion to every "1735 passed" citation (the one missing collected item is a deliberately nondeterministic `xfail(strict=False)` test; both skips are paid opt-ins, so the free suite is silent about real-Bedrock eval quality); the "2 commits ahead" figure was **already corrected** at `LIVE_BEHAVIOR_FINDINGS.md:506` (HEAD is 1 ahead) and no such cell exists in `CLAIM_LEDGER.md` — record the provenance, edit nothing there. | `PROGRESS.md`; the audit's own `CLAIM_LEDGER.md` WORK-05 cell | `archive/PROGRESS.md` (behind its banner) + `archive/reconciliation-2026-08/CLAIM_LEDGER.md`, step 11 batch I. Do **not** fix the pair into a three-number sum without the nondeterminism caveat. Also absorbs `WORK-43-FRONTEND-TESTS`'s wrong "two against recommendation" count — **routing override: the register folds this into W-18; executed here so all count corrections land in one pass** — the file's own labels make it at least four. Discipline to record: "the suite is green" is not "everything run passed". |
| W-14 | `DOC-TEST-CLAIM-WORDING` | Three edits, each carrying its qualifier: `checkpoint_repair` terraform lines are four not three; `extra="forbid"` is 41 not 31 — and the edit must carry both the denominator (41 of 184 classes, 22%) and the mechanism caveat (pyright does not fail if `extra="forbid"` is deleted) or the row drifts again; "zero blank/stuck states enforced at teardown" overstates the harness. | `REPOSITORY_DRIFT_REGISTER.md` (three locations); `TRACEABILITY.md`; `DECISIONS.md` | `TRACEABILITY.md` + `DECISIONS.md` + `archive/reconciliation-2026-08/REPOSITORY_DRIFT_REGISTER.md`, step 11 batch I. **Engineering half split / standing note:** teardown's `assertClean()` runs only when status is "passed", so a failing test's criterion-3 evidence is reported but not enforced. |

### Rows W-15 … W-29 — governance, hygiene and corpus-level structure

| # | register KEY | fix | source document(s) | destination / step |
|---|---|---|---|---|
| W-15 | `AMENDMENT-SWEEP` | One systematic pass: amendment markers in the D-351 pattern, or a single "SPEC amendments" index, at the nine points of departure — deployment substrate, scaling mechanisms, placement table, question volume, solution images, observability fork, auth menu, internal NL2SQL, gateway surface, component table, state shape, payload allowlist, study-plan priority, post-exam parallel form, interrupt list, §5.29 failure matrix, retention windows (§5.15.2 — D-333 governs 30/90/180 plus a chat-checkpoint clock SPEC has no row for). | `SPEC.md` (sixteen sections); `CLAUDE.md` rule 8; `TRACEABILITY.md` (the §5.13 locus citation) | `SPEC.md` (stays active), step 11 batch F. Largest single class and the highest-leverage row. **User sign-off points during migration:** DRIFT-15's two unbuilt §5.29 mechanisms, REQ-49's unbuilt mechanisms, DRIFT-16's reading question; also flagged for sign-off during migration: W-44's zero-egress reframing (a framing change to a stated invariant — record via a DECISIONS entry), and the two CLAUDE.md safety-rule wordings (rules 1 and 8, W-42/W-30). Three items lifted out as non-editorial: the §5.13 locus correction, the ten-versus-nine `TurnReason` client-visible contract, and two payload facts (`attendance_status` on the wire; `RagAnswerPayload.user_role` surviving D-219, in tension with non-negotiable rule 3). |
| W-16 | `STATUS-TAG-CONVENTION` | Annotate the eight verified-misleading entries and adopt D-153 §5's backward-pointer convention going forward — **not** a 120-entry sweep. The declared `proposed \| accepted \| superseded` vocabulary is unmaintained: a heading grep for `superseded` returns nothing file-wide. | `DECISIONS.md` (header and all entry headings; exemplars D-135, D-344, D-356, D-300, D-366, D-085, D-072, D-322 §7) | `DECISIONS.md` (stays active), step 11 batch G. An **input** to the canonical-document design, with a safe default. Standing hazard: any tooling keyed on `## D-nnn` headings — including this audit's merge keys — is unsafe until the phantom-ID and heading-format problems close. Prerequisite: W-25's ID index (O16) — batch G runs W-25, W-16, W-18. |
| W-17 | `AUDIT-ID-NAMESPACE` | Adopt the qualified-citation rule corpus-wide: never treat a bare audit ID as uniquely identifying one finding; always cite `<document>:<id>`. **No renumber** — the `AUD-L-17` → `AUD-L-19` renumber was applied per reference with ranges deliberately left ambiguous, so no mechanical re-map exists. | `AUDIT_FINDINGS.md` (three locations); `AUDIT_LIVE_2026_08_17.md` (two); `AUDIT_2026_08_16.md`; `ROADMAP.md` | **`reference/audits/README.md` — created at step 8, early.** Every cross-document finding lookup after 2026-08-16 is ambiguous until it exists. The reconciliation corpus adopts the rule too. |
| W-18 | `DOC-DECISION-LOG-CORRECTIONS` | One pass over eleven decision-log defects: F1's conflated remediation commands; D-135's heading asserting a premise D-138 falsified; F6's three unreconciled policy sets; K1's shape residue and 50 `authoring_mode='shape'` rows; phantom D-210 and D-363; stale 4-video figures; K4's wrong active rule at D-300/D-301; M1's SSE architecture stated in no single entry plus D-344's self-contradicting heading; the stale image-floor counter; D-401's malformed correction blockquote; "Five" phantoms introducing six. | `DECISIONS.md` (the enumerated entries); `PROGRESS.md` (four locations); `OPEN_DECISIONS.md` (header count) | `DECISIONS.md` (active) + archived copies behind banners, step 11 batch G. Cheap high-value sub-tasks: the D-359 … D-364 heading sweep settles five ids at once (only D-362 and D-364 genuinely unconfirmed); "Five" → "Six" is a two-character fix. **Two cautions:** grep `INCIDENT_RESPONSE.md` in case a runbook still routes D-093 → D-137 for an RDS rotation — that is a live operational hazard; and the D-233 quote "The number was never the variable" was **not found** and must not be attributed. Also carries `D356-FAMILY`'s documentation member; twelfth item: the D-137/D-141/D-356 → D-357 wrong-id citation (`DECISIONS.md` inside D-406; `PROGRESS.md:334`) from `D356-FAMILY` item (3). The D-093→D-137 hazard grep was hoisted to **step 0b** — W-18 consumes its recorded result. |
| W-19 | `DOC-PROGRESS-QUEUED-BLOCK` | Retire or date the whole four-row queued block, not one line: it lists C8 as next with "168 of 494" files while ROADMAP records it done with 168 of 437, and no count in repository history plausibly yields 494. The same block marks A3/B4/B6 pending against W25/W26/W27 done. | `PROGRESS.md` (the four-row queued block); against `ROADMAP.md` | `archive/PROGRESS.md` — **retired at step 7d as part of the archive banner**, step 11 batch H for the annotation. Separate method point (`RUFF-DENOMINATOR`): the `ruff format` denominator moving 437 → 440 is not drift. |
| W-20 | `RISK-GROUP-FREEZE` | Five freeze banners plus one `CLAUDE.md` cross-link, plus a status column or historical marker on the S42-file tables. `INTEGRATION_PLAN.md` has zero occurrences of `D-152` and read standalone directs all four forbidden actions; `S42_ORG_ASKS.md` still says "Send now" for an answered ask; `S42_DISCOVERY.md` §9 instructs an action `CLAUDE.md` prohibits; ROADMAP's S48–S51 carry no freeze annotation. | `INTEGRATION_PLAN.md` (whole file); `S42_ORG_ASKS.md`; `S42_DISCOVERY.md` §7–§9; `ROADMAP.md` (S43–S47, S48–S51); `SPEC.md` §5.2.2; `S42_OPEN_QUESTIONS.md` (four locations); `INCIDENT_RESPONSE.md`; `CLAUDE.md` | Banners at **step 7a/7c**; the ROADMAP half lands in `reference/integration/ROADMAP_FROZEN_SESSIONS.md` at **step 3**; the `CLAUDE.md` cross-link at **step 14**. Copy `S42_OPEN_QUESTIONS.md`'s own banner shape. **Sequence `S42_ORG_ASKS` first** (HC-4). Do not blanket-retire its line 110. Paired with W-36 — same files, one pass each. |
| W-21 | `RISK-GROUP-ARCH-AUTHORITY` | Archive one architecture document after **two mandatory extractions**; state the hierarchy in the survivor and in `CLAUDE.md`'s index; move the one-line database-layout fact into the canonical document; adopt F-07's split — "behind on decisions" is **false**, ARCHITECTURE is stale only on session provenance (32 of 48 tagged). | `FINAL_ARCHITECTURE.md` (seven locations); `ARCHITECTURE.md` (header promise; storage-split table); `CLAUDE.md` index | Extractions at **steps 1–2**, rename and banner at **step 7b**, hierarchy statement at **steps 10 and 14**. Do not archive before extracting (HC-2). |
| W-22 | `RISK-R2.2-ACCEPTED-RISK-HOMES` | Carry the §7-R8/R9 expiry conditions to every restatement, or reduce the restatements to pointers. Today only `INTEGRATION_PLAN.md` §7 carries them, while `ARCHITECTURE.md` — the file sessions are told to read and update — restates both risks without them. | `INTEGRATION_PLAN.md` (the authoritative copy); `ARCHITECTURE.md` (two expiry-less restatements); `AUDIT_FINDINGS.md` (accepted-residual-risks section); `TRACEABILITY.md` (§7-R8 row) | Single-homed into `PROJECT_STATE` §6.4 at **step 10**; pointers added at step 11 batch D. The one row with a launch gate attached; separable from `ORG-COMMS`'s ownership decision. **Engineering half split:** making the expiry mechanical rather than prose. Also lands here: `WORK-42-INTERSTITIAL-BYPASS`'s accepted middle-click bypass and `WORK-44` #2's single shared anonymous rate-limit bucket — both belong in the launch-readiness accepted-residual-risk set (minors-primary product; same insufficient-stopgap shape as `SEC-18-WAF`). |
| W-23 | `RISK-GROUP-CURRENT-STATE` | The largest single block of migration work: split ROADMAP (reference + archive) and PROGRESS (state captured + archive); un-interleave the strata; fix the missing glyphs and the duplicate headings and blocks. PROGRESS's "Current status" is a newest-first stack roughly 1,800 lines deep where the same metric reads 4-of-112 and 102-of-112 at different depths; ROADMAP keeps roughly 470 lines of superseded gate standings inline with five coexisting criterion-6 dates. | `PROGRESS.md` (Current-status block and five locations); `ROADMAP.md` (five locations); `TRACEABILITY.md` (heading plus "Open: none" beside an open T-02); `AUDIT_FINDINGS.md` (count line; Index split into six fragments by stray blank lines) | `PROJECT_STATE.md` (the replacement) + `archive/PROGRESS.md` + `archive/ROADMAP.md` + `reference/integration/ROADMAP_FROZEN_SESSIONS.md`; **steps 3, 7d, 9**, annotations at step 11 batch H. R8.1's recommendation is structural: generate summaries mechanically or date-stamp them; copy ROADMAP's anchored-awk precedent. **The shape of the split is a design choice to ratify with the user at proposal review.** |
| W-24 | `RISK-R1.4-SPEC-VINTAGE` | Adopt the D-351 pattern (amend in place with a dated marker) as a **rule**; mark the known-superseded sections; demote §6 to historical. For §5.8.1, §5.11.2, §5.13.2, §5.28.2 and §5.33, DECISIONS wins and the spec still reads as if it does not. | `SPEC.md` (ten sections plus §6); `CLAUDE.md` ("the spec wins on detail"); `DECISIONS.md` (where the D-111 sweep is recorded instead) | `SPEC.md` + `CLAUDE.md`, step 11 batch F and step 14. Because SPEC references nothing, "the spec wins on detail" is safe about **granularity** and unsafe as a **conflict-resolution** rule — fixing that rule's wording in `CLAUDE.md` may be cheaper than annotating every drifted section. Paired with W-15. |
| W-25 | `RISK-GROUP-DECISIONS-HYGIENE` | A status-tag pass, an ID index, and either writing the phantom entries or recording their absence at each citation site. Three phantom families: D-190/D-191/D-192 (cited 18 times in code and 8 in documents), D-329 (a sub-heading inside D-330), D-363 (no heading anywhere). The log is not append-only, so an entry's text cannot be dated by its heading; heading format changes mid-file at D-274. | `DECISIONS.md` (preamble, D-004, D-135, D-121 §3, D-129 §5, D-344, three non-standard statuses, the meta-note, informal sub-entries, one three-ID heading, D-176 §4, D-110 §2, D-401, D-274) | `DECISIONS.md`, step 11 batch G. **Preserve the loud-correction culture.** Two cautions: tooling keyed on `## D-nnn` is unsafe until this closes; reconstructing D-190/D-191/D-192 from 26 citation sites is real work with a judgement component — **consider a stub-with-provenance, and never invent a body.** |
| W-26 | `RISK-GROUP-AUDIT-REGISTERS` | A namespace rule, three cross-reference sentences (one per register), a status-column disclaimer on `AUDIT_FINDINGS.md`'s Index, and one closure note. | `AUDIT_FINDINGS.md` (five locations; mentions neither successor); `AUDIT_2026_08_16.md` (§3/§4 lists with no status marks; "Still open" lines overtaken by D-397 → D-423); `AUDIT_LIVE_2026_08_17.md` (residual tail overtaken by D-407 → D-410; the never-exercised list closed elsewhere by D-391/D-392/D-398/D-399 without updating the file) | `reference/audits/*` with the README from step 8; step 11 batch B. **Fix early** — it unblocks every cross-document lookup. Paired with W-12. |
| W-27 | `RISK-GROUP-NAMING` | Renames and in-file re-descriptions plus index entries for six misdirecting names: `OPEN_DECISIONS.md`, `S42_ORG_ASKS.md`, `AUDIT_FINDINGS.md`, `U7_CHECKPOINT_CONSOLIDATION.md`, `docs/plans/`, and SPEC's H1 (`# 5. Very Detailed Version`) with `CLAUDE.md` under-describing the file by 38%. | `OPEN_DECISIONS.md` (three locations); `S42_ORG_ASKS.md`; `S42_SECURITY_REPORT.md`; `AUDIT_FINDINGS.md`; `U7_CHECKPOINT_CONSOLIDATION.md`; `docs/plans/`; `SPEC.md:1`; `CLAUDE.md` | Renames executed at **step 7** (`S42_ORG_ASKS` → `2026-07-24-org-asks-drafts.md`, `FINAL_ARCHITECTURE` → `2026-07-21-final-architecture-projection.md`); the rest are **re-descriptions plus index entries**, not renames, because renaming breaks inbound links from ROADMAP, DECISIONS and PROGRESS. Rename-versus-re-describe is a judgement per file and is recorded per document in §2. A rename alone is insufficient: `CLAUDE.md`'s description of `OPEN_DECISIONS` is the stalest thing about it (step 14). |
| W-28 | `RISK-GROUP-RESOLVED-LOOKS-OPEN` | Four edits plus one supersession annotation. Highest value: `CLAUDE.md`'s description that sends every session to a closed file looking for work. Then `S42_OPEN_QUESTIONS.md`'s in-table annotations and E-group pointer, and `OPEN_DECISIONS`' four stale lines. Annotations: #8 **superseded-operationally**. | `CLAUDE.md`; `OPEN_DECISIONS.md` (four locations); `S42_OPEN_QUESTIONS.md` (four locations) | `CLAUDE.md` at **step 14**; `S42_OPEN_QUESTIONS.md` at **step 7c**; `OPEN_DECISIONS.md` annotations at **step 7d**, quarantined behind its archive banner. Step 11 batch H. |
| W-29 | `TRACKING-HOME-FOR-OPEN-ITEMS` | Give each of five invisible open items a tracking home: a send-status line and an index entry for the security report; index entries for the first-visit notice and for A4/A5; an owned record for the answer-cache conclusion; and an owned record for the six-schema split. | `FIRST_VISIT_NOTICE.md`; `S42_SECURITY_REPORT.md` (no send-status field); `S42_OPEN_QUESTIONS.md` A4/A5 versus `OPEN_DECISIONS.md`; `PROGRESS.md` (the answer-cache decision in the top stack only); `FINAL_ARCHITECTURE.md` (question 5) | `PROJECT_STATE` §5/§6/§7 + `reference/org-drafts/S42_SECURITY_REPORT.md` (send-status at step 7e, before the move — O14) + `ARCHITECTURE.md`'s open-questions block (**step 2**) + `CLAUDE.md` index (step 14). The **judgements** follow their canonical topics (UD-10, UD-8, `AUTH-OPTION-O1B`/`D152-FREEZE`, `WORK-04-ANSWER-CACHE`, `ARCH-21-SCHEMA-SPLIT`); only the tracking home lands here. |

### Rows W-30 … W-44 — discoverability, duplication, conventions and the LOW batches

| # | register KEY | fix | source document(s) | destination / step |
|---|---|---|---|---|
| W-30 | `RISK-GROUP-INDEX` | Add index entries (or an explicit "deliberately unlisted because …"), add a last-reviewed marker, fix the stale descriptions (SPEC's line count, the `OPEN_DECISIONS` description), add one clarifying line on rule 8, and add the CloudFront-domains sentence from `RD-12-INGRESS`. The index names 11 files and omits 13 that exist. | `CLAUDE.md` (Documents section, the freeze section, the condensed-rules block, rule 8) | `CLAUDE.md` — **step 14, last** (HC-7). Cheapest and highest-priority fix in the whole extraction; nothing references `CLAUDE.md` back, so drift here is unpoliced. Consequences with teeth: `ARCHITECTURE.md` is the file every session must update but none is told to read; `INTEGRATION_PLAN.md` is what the freeze is about and is undiscoverable from the file stating the freeze; `ENROLLMENT_FAQ_APPROVAL.md` claims to be the only launch gate and is invisible at session start. Sole owner of the rule-1 and rule-8 wordings (W-15/W-42 cross-reference, they do not edit): rule 8 reads — "requirement unchanged; no code path implements §5.17 today; the requirement binds any future implementation from line one (`IMAGE-WORK-PARK`)". |
| W-31 | `RISK-GROUP-DUPLICATE-CONTENT` | Assign one owner per number plus pointers; prefer mechanical derivation. Session status has three homes; finding counts two; the four production security findings four; and verbatim numbers (the 189-item depth gap, the `difficulty_tiers` rule in three homes re-derived at least three times, checkpoint sizing, taxonomy figures) drift independently. | `ROADMAP.md`; `PROGRESS.md`; `INTEGRATION_PLAN.md`; `AUDIT_FINDINGS.md`; `S42_DISCOVERY.md`; `S42_OPEN_QUESTIONS.md`; `S42_SECURITY_REPORT.md`; `DECISIONS.md` (D-153 §5/§7); `QUESTION_GENERATION.md`; `OPEN_DECISIONS.md`; `U7_CHECKPOINT_CONSOLIDATION.md`; `CONTENT_COVERAGE.md`; `CLAUDE.md` index | **Step 10 (single-homing table)**, plus step 11 batch H. The checkpoint-sizing pair is **not** a contradiction and must not be resolved by picking one — label the environment on each (development ~4.8 GB versus staging ~285 MB). Merged with W-23's mechanical-summary recommendation. **Engineering half split:** mechanical derivation of counts. |
| W-32 | `RISK-GROUP-EXECUTED-PLANS` | Status headers, one archive convention for `docs/plans/` (archive with an as-of/superseded header — **do not delete**, deleting breaks ROADMAP's live pointer), the D-number line, and the brand-data promotion. The branding plan says "planned, not started" for a session executed the same day and instructs logging at "the next free D-numbers — D-064 was the last used", which **mints duplicate ids** since the log is past D-423. | `2026-07-19-branding-plan.md` (four locations); `2026-07-18-expansion-plan.md` (nine locations); `DECISIONS.md` (the MySQL-sweep exclusion); `ROADMAP.md` (two live pointers in) | Brand-data extraction at **step 4**; executed-as headers at **step 7d**; pointer repathing at **step 9a**. **Fix the D-number line even if the rest waits.** **Engineering half split:** promoting the brand table and BD3 into `packages/ui-brand` — a file marked "not started" is a weak home for a standing rule, and so is a document. |
| W-33 | `RISK-GROUP-OPS-DOC-STRATA` | De-duplicate the scheduling state, box or evict the superseded strata, fix the two trailing imperatives, and add a date header, the S34 tense fix and one freeze-context line to `INCIDENT_RESPONSE.md`. | `ARCHITECTURE.md` (six locations); `QUESTION_GENERATION.md` (four); `HINT_SOLUTION_REVIEW.md` (four); `U7_CHECKPOINT_CONSOLIDATION.md` §8.2/§9.2; `PROGRESS.md`; `INCIDENT_RESPONSE.md` | `ARCHITECTURE.md` + `reference/QUESTION_GENERATION.md` + `reference/HINT_SOLUTION_REVIEW.md` + `reference/U7_CHECKPOINT_CONSOLIDATION.md` + `reference/INCIDENT_RESPONSE.md`; step 11 batch E (the HINT_SOLUTION_REVIEW clause merges into W-07 at step 5). **Do not resolve either ARCHITECTURE contradiction from the document alone** — check the deployed state. |
| W-34 | `RISK-R7.3-DANGLING-REFS` | Four pointer fixes: the `docs/codebase-analysis/` reference (the referent is out-of-repository); the instruction to sync a `knowledge-content copy/` directory deleted by D-253; the dead manifest line-number pointer; and ROADMAP's pointers into `docs/plans/` without a historical note. | `DECISIONS.md`; `ENROLLMENT_FAQ_APPROVAL.md`; `ROADMAP.md` (two) | `DECISIONS.md` + `reference/org-drafts/ENROLLMENT_FAQ_APPROVAL.md` + repathed ROADMAP pointers; **step 9a/9b**. The `../IntelliChoice-web` reference must be written as **explicitly out-of-repository**, not "fixed" into a local path that will never exist. |
| W-35 | `RISK-R6.4-SESSION-LABELS` | A disambiguation convention plus per-collision annotations: "C1" names two sessions; "S43" is both a frozen ROADMAP session and a self-applied label; PROGRESS's unnumbered "S44"–"S66" collide with ROADMAP's frozen S44–S47 — most consequentially a **completed** unnumbered "S45" against ROADMAP's **unstarted** consent session S45; "§2.6" resolves to `INTEGRATION_PLAN`, not SPEC. Extend or bound D-049's translation layer, which covers old S17–S23 only. | `ROADMAP.md` (three locations); `2026-07-18-expansion-plan.md`; `CONTENT_COVERAGE.md`; `DECISIONS.md`; `PROGRESS.md` (two); `FIRST_VISIT_NOTICE.md` | `PROJECT_STATE` documentation map (the convention) + per-file annotations; batch **A** (step 11, first — prerequisite for W-43's T-02 edits and for stating any S45-touching owner). **Prerequisite:** the S45 collision touches two open items (`DISCLOSURES-LEGAL`'s product decision and `FIRST-VISIT-REVERIFY`), so it must be fixed before either owner can be stated. |
| W-36 | `RISK-R6.5-SUPERSESSION-DIRECTION` | Forward pointers on the superseded documents, and **in-place application of the two `S42_DISCOVERY` corrections** to `INTEGRATION_PLAN.md`. `S42_OPEN_QUESTIONS.md` supersedes `S42_DISCOVERY.md` §7 while citing it as evidence, and DISCOVERY carries no forward pointer while being the indexed one; `INTEGRATION_PLAN` §8 patches §1/§5 by reference without editing them. | `S42_OPEN_QUESTIONS.md`; `S42_DISCOVERY.md` (two locations); `INTEGRATION_PLAN.md` (four locations) | `reference/integration/*`; **step 7c**, one pass per file together with W-20. The uncorrected copies are the ones a session reads first and the corrected facts are **production-system facts**. |
| W-37 | `DOC-SNAPSHOT-BANNERS` | One as-of banner per measurement snapshot, plus a convention that every measured number carries its date and environment. `CONTENT_COVERAGE.md` describes needs built the same day or since, so a reader would rebuild an existing router; `U7_CHECKPOINT_CONSOLIDATION.md` was never edited after the day it was written and holds self-expiring claims with no absolute dates; `QUESTION_GENERATION.md`'s "Current, 2026-08-12" block has no expiry marker. | `CONTENT_COVERAGE.md` (status columns and five figures); `U7_CHECKPOINT_CONSOLIDATION.md` (single date, a wrong section pointer, the 8-days claim); `QUESTION_GENERATION.md` | `reference/CONTENT_COVERAGE.md` + `reference/U7_CHECKPOINT_CONSOLIDATION.md` + `reference/QUESTION_GENERATION.md`; step 11 batch E. Same defect class as LB-02/LB-03/LB-07 — prefer **one corpus-wide convention** (every measurement states date, environment or build, and denominator) over per-file banners. Combined with W-38. |
| W-38 | `DOC-VINTAGE-HEADERS` | A one-line vintage header on the living documents. Four load-bearing files have no vintage marker at all: `CLAUDE.md` (and it has drifted before — rule 1 said "MongoDB"), `SPEC.md` (no version, date or changelog in 4,210 lines), `INCIDENT_RESPONSE.md` (vintage inferable only from the D-number cited), `QUESTION_GENERATION.md` (four dated strata, no "last updated"). | `CLAUDE.md`; `SPEC.md`; `INCIDENT_RESPONSE.md`; `QUESTION_GENERATION.md` | All four destinations; ****steps 0c** (`SPEC.md`, `INCIDENT_RESPONSE.md`, `QUESTION_GENERATION.md`) **and 14** (`CLAUDE.md`) — nothing remains at step 11 (HC-6)**. The cheapest structural improvement in the extraction and a **precondition** for the step-11 rows: a stale line is only detectable if the document says when it was last true. Combined with W-37. |
| W-39 | `DOC-LINE-CITATION-DRIFT` | Adopt an as-of stamp for line citations and prefer symbol or anchor citations where load-bearing. `HINT_SOLUTION_REVIEW.md` cites `ai_pipeline.py:1769` for a constant now at `:834`; `ENROLLMENT_FAQ_APPROVAL.md`'s dead manifest pointer is fixed by W-34 at step 7e — W-39 covers only the convention; TRACEABILITY was already burned once when a §5.8.5 row was evidence for a requirement satisfied by code no student could reach until D-226 rewrote it. | `TRACEABILITY.md` (all file-and-line rows); `HINT_SOLUTION_REVIEW.md`; `ENROLLMENT_FAQ_APPROVAL.md` (via W-34) | `TRACEABILITY.md` **first** — it is the criterion-1 instrument, so a drifted citation there degrades launch evidence — then the other two; step 11 batch I, **first in the batch** — the convention governs W-11/W-14/W-40. Overlaps W-40 and W-11. |
| W-40 | `BATCH-LOW-CITATIONS` (9 members: DRIFT-60/61/62/63/64/65/77/90/100) | Nine corrections where the substance holds and a citation, count, path or denominator does not: five stale TRACEABILITY implementation anchors; the spend undercount stated as 32.0% / 31% / approximately 30.8%; a cited test name that does not exist and whose real name **inverts** the clause; a self-cited near-miss naming the wrong commit; the "one row per finding" invariant unheld in reverse (7 row ids with no detail section); the error-vocabulary header's stale rule count; ARCHITECTURE's storage-split table under-describing Postgres by twelve shipped tables; an omitted `documents/` path segment; TRACEABILITY's §5.27 row counting 31 `extra="forbid"` models against 41. | `TRACEABILITY.md` (five row classes); `ARCHITECTURE.md` (storage-split table); `AUDIT_FINDINGS.md` (row/section invariant); the error-vocabulary spec header; the enrollment-FAQ content citation; the documents and code carrying 32.0% versus 31% | `TRACEABILITY.md` + `ARCHITECTURE.md` + `reference/audits/AUDIT_FINDINGS.md`; step 11 batch I. Three flags: DRIFT-100's mechanism-strength half belongs with W-11; DRIFT-63 is a citation inside the file's own reliability warning; DRIFT-64's title says six row ids and its body says seven — **carry the body's number**. **Engineering half split:** the error-vocabulary spec header (`e2e/tests/learning/error-vocabulary.spec.ts`). |
| W-41 | `BATCH-LOW-STALE-STATUS` (10 members; 3 exceptions lifted out to `DRIFT-58-E2E-ISOLATION`, `DRIFT-91-ORGTIME-IMPORT`, `DRIFT-93-D401-D406-APPLIED`) | Seven documentation edits where a comment, status line or open question is contradicted by the same file, adjacent configuration, or a dated commit: the scheduled-jobs module header ("four defined, three enabled" against five and four); ARCHITECTURE using "retention" for two different jobs; a variables file asserting no tfvars exists while `terraform.tfvars` does; U7 §9.2 and §10; `OPEN_DECISIONS` #6 "parked" versus PROGRESS's "blocked on the YouTube key". | `terraform/modules/scheduled-jobs/main.tf` header comment; `ARCHITECTURE.md` (the retention passage); `terraform/environments/staging/variables.tf` and `main.tf`; `U7_CHECKPOINT_CONSOLIDATION.md` §9.2/§10; `OPEN_DECISIONS.md` #6 versus `PROGRESS.md` | `ARCHITECTURE.md` + `reference/U7_CHECKPOINT_CONSOLIDATION.md` (via W-08's single banner, which closes DRIFT-47/94/95 together) + archived copies; step 11 batch I. DRIFT-75 and DRIFT-102 are **one** operative terraform comment (**engineering half split**). DRIFT-81 is recorded as a **known limitation**, not "fixed": a gitignored tfvars means the tracked tree does not determine the plan. |
| W-42 | `BATCH-LOW-OVERSTATEMENT` (11 members; 2 exceptions lifted out to `DRIFT-72-OUTCOME-ENUM`, `DRIFT-86-COST-RUNBOOK`) | Nine edits where a rule, claim or metric name is stated more broadly than the implementation supports — and in every case the narrow implementation is correct and deliberate: rule 1 gains D-050's clause **in exactly this wording** (owned by W-30 at step 14): "No student, parent or guardian PII in Postgres — absolute. Two tables (org staff/branch contact) carry the org's own already-public fields under an enumerated exemption (D-050, `ALLOWED_PII_SHAPED_COLUMNS`); `test_schema_purity.py` still fails loudly if any student-facing table grows one of those column names."; "interrupts after every incorrect answer"; rule 8's image deletion for a feature with no code; the location modal exposing two of three accepted fields; "difficulty superseded by observed evidence" reading as live; LangSmith masking located in task definitions rather than application code; "health endpoints emit no telemetry at all" (true of traces, not logs); `ATTENDANCE_CHECKS{result="unknown"}` meaning "the adapter threw"; "citations carry `effective_to`". | `CLAUDE.md` rules 1 and 8; `SPEC.md` §5.4/§5.30; `INCIDENT_RESPONSE.md`; the interrupt-routing prose; a chat-api state docstring; the LangSmith-masking location; the health-endpoint telemetry claim; the metric-label documentation | `CLAUDE.md` (step 14) + `SPEC.md` + `reference/INCIDENT_RESPONSE.md`; step 11 batch I. Four flags: **DRIFT-88 has a production consequence** — per D-152 §2 `signups.attended = null` is routine, so the attendance metric cannot distinguish the common case from a recorded absence, and no alarm reads it; **DRIFT-53's four columns are correct and allowlisted — the wording must not imply a PII violation**; DRIFT-79's log leg is a real cost and noise item at ALB health-check frequency; DRIFT-71(b) duplicates DRIFT-33's stale docstring (one defect, two entries, both must appear in coverage). **Engineering half split:** the chat-api state docstring and the metrics label comment. |
| W-43 | `BATCH-LOW-UNMARKED-SPEC` (5 members; 1 exception lifted out to `DRIFT-66-NL2SQL`) | Four edits where a named list, family or requirement no longer matches what shipped: two of SPEC's thirteen structured-output artifact types have no Pydantic schema (both dispositioned elsewhere, so the gap is document-side); `CONTENT_COVERAGE.md` names a `selection` answer-model family that is not a distinct answer model; the ledger's "§6.1 track not started" is superseded by the 2026-08-15 T-02 enumeration; TRACEABILITY's T-02 block still asserts the track has not started and that none of the eleven disclosures is enumerated in ROADMAP — both now false. | `SPEC.md` (the thirteen-type list); `CONTENT_COVERAGE.md`; the `CLAIM_LEDGER.md` §6.1 temporal note; `TRACEABILITY.md` T-02 block (which contains **no** reference to `FIRST_VISIT_NOTICE.md` at all) | `SPEC.md` + `reference/CONTENT_COVERAGE.md` + `TRACEABILITY.md` + archived ledger; step 11 batch F. Five flags: adopt F-05's wording **"declared and never used", not "absent"**; DRIFT-99 and DRIFT-101 are the same supersession from two directions and both need the same forward pointer to `FIRST_VISIT_NOTICE.md`; **neither is progress on `DISCLOSURES-LEGAL`**; carry F-16's new untested item forward (`REQ-27-FROZENSET`); SPEC's thirteen-type list was never amended (W-15). |
| W-44 | `BATCH-LOW-CONFIG-VS-PLAN` (4 members; 2 exceptions lifted out to `DRIFT-59-DATE-SHIFT`, `DRIFT-70-CONSENT-GATE`) | Two edits: annotate the latency capacity plan that implies five tasks against a configured ceiling of 3 (D-153 §3 withdrew that purchase, so it is a plan-versus-ceiling note for whenever capacity is revisited); and reframe the zero-internet-egress "invariant" as **baseline-with-exception**, carrying all three facts — the invariant is currently false, by a deliberate decision, at roughly $33/month. Plus correct `OPEN_DECISIONS` #10's symbol name. | `ARCHITECTURE.md` (the capacity plan; the zero-egress framing); `OPEN_DECISIONS.md` #10 (the `formatDateLabel` symbol name) | `ARCHITECTURE.md` + annotation on the archived `OPEN_DECISIONS.md`; step 11 batch I. Recommend a convention note on **"ALL DECIDED" headings as a rot hazard**. DRIFT-56 becomes decision-relevant the moment capacity is revisited. The zero-egress **reframing** is a framing change to a stated invariant: it rides W-15's sign-off list and is recorded via a `DECISIONS.md` entry before `ARCHITECTURE.md`'s framing is edited; the *reporting* half (egress is non-zero today, ~$33/month, by deliberate decision) is documentation-only. |

**Worklist row count: 44** (W-01 … W-44), one per DOCUMENTATION_ONLY register entry.

---

## 5. Validation — ten proof points

Each proof point states what must be true after the migration, how it is achieved, and how a reader
checks it. These are the step-15 checklist.

### 5.1 All 166 register entries have a future destination or a historical disposition

**Achieved by** the routing rules in §1 applied exhaustively in **Appendix A**, which lists all 166
entry keys with their disposition and destination. Distribution: 27 to `PROJECT_STATE` §4, 16 to §5,
34 to §6, 4 to §7, 44 to the §4 worklist, 41 to the historical tail of the reference register.
27 + 16 + 34 + 4 + 44 + 41 = 166.

**Check.** Every key in Appendix A resolves to a section that exists in the new tree, and the seven mixed
entries (M1–M7) named in §1 each have both their primary route and their residual route recorded.

### 5.2 All 12 user decisions remain discoverable

**Achieved by** two homes that reference each other: `PROJECT_STATE` §5 carries a dedicated table —
UD id, one-line question, "blocks?", default safe action, link — with a header stating that these are
questions only the user can answer, that they are **not** implementation tasks, and that none becomes a
`D-xxx` without the user. The full option analyses live at
`docs/reference/reconciliation-2026-08/USER_DECISION_QUEUE.md`, which is **reference, not archive**,
precisely so this link never points into a do-not-treat-as-current file.

**Check.** UD-1 … UD-12 each appear once in `PROJECT_STATE` §5 with a populated register-key column
(11 carrying `USER_DECISION_REQUIRED` entries + UD-11 from the BLOCKED `LANGSMITH-RETENTION`), and each
resolves to a section of the queue document. Only **UD-1 partially blocks work** — no live verification
of the B4 escalation series is possible without a deploy — and the table says so rather than implying
that all twelve block. The six answer-shaped defaults are tagged **[USER ONLY — hold:]** and none has
been applied as an answer.

### 5.3 All 27 active remediation and implementation items are visible

**Achieved by** `PROJECT_STATE` §4: 16 `ACTIVE_REMEDIATION` in §4.1, 11 `ACTIVE_IMPLEMENTATION` in
§4.2, one line and one remaining action each, keyed by register key. §4.3 lifts the five an agent can
act on from that file alone, so visibility does not depend on reading all 27.

**Check.** Count §4.1 and §4.2. Each line's register key resolves in the reference register. No item
appears only in an archived file — that is the specific failure this replaces, where the project's
actual sequencer was roughly 1,800 lines into `PROGRESS.md`'s stratified "Current status" block.

### 5.4 DEFERRED and PARKED reopen conditions are preserved inline

**Achieved by** `PROJECT_STATE` §6.3 (15 deferred) and §6.4 (13 parked) carrying the reopen condition
**in the row**, not by reference. Rationale: a reopen condition stored elsewhere is a reopen condition
nobody reads at the moment it fires. Load-bearing examples that must be verifiable inline:
`R8-READ-SCOPE` ("acceptance expires at first real traffic"), `INTEGRATION_PLAN` §7-R8/R9's expiry
conditions (single-homed here by step 10, since ARCHITECTURE restates the risks without them),
`F4-CRITERION6`'s live and unmonitored reopen condition, `SEC-17-GUARDDUTY`'s costed park (D-125),
`D342-PARKING`'s standing user instruction, and `AUTH-OPTION-O1B` ("stays a recommendation until
measured, right before S44"), and the §6.4 accepted-risk expiries block (§7-R9's "any movement voids the
acceptance"), plus `R8-READ-SCOPE`'s re-presentation duty ("MUST be re-presented at integration start —
launch-blocking then").

**Check.** Every §6.3 and §6.4 row has a non-empty reopen-condition field, and each parked row names
the decision that parked it.

### 5.5 UNKNOWN items are recoverable, and UNKNOWN stays UNKNOWN

**Achieved by** `PROJECT_STATE` §7, which carries the four UNKNOWN entries plus `ARCH-34`'s named
half — five substances — each with its **named resolution step** and no guessed answer:

| unknown | resolution step, as recorded |
|---|---|
| `D192-PHANTOM` — D-192's content | **None exists; irreducible by design.** The whole remedy is one clarifying sentence scoping the meta-note's "no citation states what it decided" to *code* citations. **Do not adopt D-193's description as D-192's content.** |
| `K5-HINT-INSTRUMENTS` — D-264's annotation state | Read D-264 — its status tag and any in-place correction. One targeted read converts the entry to DOCUMENTATION_ONLY. |
| `D288-D317-CLOSURE` | Read both bodies (D-288, and D-317 plus its addendum) and determine whether the named product defect is closed. Do not let "D-288 resolved" retire its three other live findings. |
| `ARCH-34-REVISION-DRIFT` — the tfvars-staleness half | **Method-bounded: unreadable by policy.** `terraform.tfvars` is gitignored and was deliberately not read; with `adopt_deployed_image = true`, pin staleness is invisible from the control plane. Closable only by the user or a policy change. |
| `DRIFT-49-MODEL-ROSTER` | Check `DECISIONS.md` and git history for the intended roster; if that does not settle it, ask the user — the operative `.env` is forbidden to read, so the user is the only remaining evidence source. The placeholder model-id defaults are fixable without any decision and should not wait. |

**Check.** §7 has exactly these five substances, each with its step, and **none has been converted to a
conclusion by the migration.** An UNKNOWN that quietly became a statement is a validation failure.

### 5.6 D-310 is a resolved historical remediation, never an active exposure

**Achieved by** three coordinated placements: (a) `PROJECT_STATE` §9 carries the standing framing
(quoted) with links to the archived record and the register entry; the timeline/probe/CloudTrail detail
lives in those two places; (b)
`REMEDIATION_D310_ROTATION.md` archives as the remediation record, with a pointer added from
`DECISIONS.md`'s D-310 chain; (c) `OPEN_DECISIONS` #8 is annotated **superseded-operationally** at
migration (step 7d) — as written today it tells the next reader the exposure is live.

**Check.** No document in the new tree describes D-310 as an open credential exposure. The three
residuals appear as `D310-RESIDUALS` in §4.1, and the `ps`-visibility item reads **unmeasured, not
cleared**. D-310's decline stands as the historical record; "operationally superseded" is the phrasing.

### 5.7 LB-05 survives — "implemented locally" is never confused with "deployed"

**Achieved by** three mechanisms. (a) `PROJECT_STATE`'s snapshot header carries **both revisions**:
repository HEAD `344f016` and deployed staging `gha-44a12dfc9549`, ten commits behind, with the
as-of date. (b) `PROJECT_STATE` §3 is a dedicated repository-versus-deployed section naming the
undeployed content — the whole B4 escalation series (D-420, D-421, D-422), C8, and D-423's
documentation — and the fact that migration `8509c0486d8d` creating `chat_escalation_sends` is in the
repository but **absent from staging**, so D-421's duplicate-send guard is not protecting staging today.
(c) `AUTHORITY_MODEL` §3.2 and §4.3 make the **build-SHA rule** explicit: state the build SHA beside
every live number, and never backport deployed behaviour into repository documents as if designed.

**Check.** Every live measurement quoted anywhere in the new tree carries its build SHA. The specific
case to verify: LB-08's 10.55-second guest QA latency is recorded as a **pre-D-423** number on build
`gha-44a12dfc9549`. Also verify that the two layers are stated as **both true** rather than reconciled
into one — repository and deployed are different layers, not a contradiction.

### 5.8 The D-152 freeze survives with its reopen condition

**Achieved by** four mechanisms. (a) `PROJECT_STATE` §6.1 carries the canonical freeze statement with
the verbatim reconfirmation from D-417 §A1 (2026-08-18): *"D-152 is unchanged and is not 'nearly met' —
it is closed until reopened."* (b) The reopen condition is recorded as **an explicit user statement
reopening integration — not met, and no evidence can meet it**; the user reconfirmed the freeze *after*
being told the audit lists were empty and the suite was green, so verification cannot trigger an
unfreeze, and soliciting one is forbidden. (c) Freeze banners on `INTEGRATION_PLAN.md` and
`S42_DISCOVERY.md` (step 7c), which today contain **zero** occurrences of `D-152`. (d) The
`docs/reference/integration/` grouping makes the freeze a property of the location.
Additionally recorded: nine parked and deferred entries are attributable to this decision
(`D152-FREEZE`, `S43-SCOPE`, `AUTH-OPTION-O1B`, `F2-ADAPTER-SHAPE`, `F3-DEVTOKEN-S44`,
`SEC-34-ROLE-ALLOWLIST`, `INT-ATTENDANCE-DERIVATION`, `R8-READ-SCOPE`'s closure path,
`ARCH-35-ORG-TIME`'s guard) — **attributed to the decision, never to an obstacle**. And the one
permitted exception is stated: `ORG-COMMS` (UD-8) is permitted under the freeze (INT-28) and is live
user work, not parked.

**Check.** No document in the new tree directs any of the five prohibited actions. The one engineering
obligation during the freeze — keeping the `ProfileAdapter` seam honest — is stated. The
`signups.attended = null` production fact is present in `CLAUDE.md`.

### 5.9 No security, privacy or HITL invariant disappears

**Achieved by** keeping every invariant-bearing document active or reference, never archive.
**Generator (so the table is derived, not authored):** every CLAUDE.md non-negotiable, plus every SPEC §5
subsection whose content is a prohibition, a fail-closed rule, a deletion obligation, a consent gate, or
an approval gate.

| invariant | bearing document | fate |
|---|---|---|
| No PII in Postgres, logs, traces or LLM payloads (with D-050's four allowlisted columns) | `CLAUDE.md` rule 1; `SPEC.md` §5.4/§5.30 | active / active — carried with D-050's full scope clause (W-42's exact wording), never as a subject-free carve-out |
| Deterministic core; no runtime NL2SQL | `CLAUDE.md` rule 2; `SPEC.md` §5.0/§5.26 | active / active (the *internal* NL2SQL requirement is UD-12(d), open) |
| Authorization in the backend and query layer, never in prompts | `CLAUDE.md` rule 3; `SPEC.md` §5.21.3/§5.30.2 | active / active |
| Human approval via `interrupt()` for every external action | `CLAUDE.md` rule 4; `SPEC.md` §5.1.4; `ARCHITECTURE.md` invariants | active / active / active |
| Fail closed (unknown attendance is not present; no ungrounded RAG answer) | `CLAUDE.md` rule 5; `SPEC.md` §5.4.4/§5.21.8/§5.29 | active / active |
| Structured output, validated, with deterministic fallback | `CLAUDE.md` rule 6; `SPEC.md` §5.25.3/§5.27 | active / active |
| All paid-API calls through the gateway with timeouts and caps | `CLAUDE.md` rule 7; `SPEC.md` §5.25.1 | active / active |
| Solution images deleted immediately | `CLAUDE.md` rule 8; `SPEC.md` §5.17 | active — requirement unchanged; one dated line: no code path implements §5.17 today; the requirement binds any future implementation (`IMAGE-WORK-PARK`). Also borne by SPEC §5.15.2 and §5.29's VLM row — **do not mark those parked** |
| External dependencies behind interfaces with dev fakes | `CLAUDE.md` rule 9; D-002 | active |
| Growth-oriented, age-appropriate student language | `CLAUDE.md` rule 10; `SPEC.md` §5.10.3 | active |
| Never read or quote the committed credentials or the source-visible secret literals | `CLAUDE.md`; `S42_SECURITY_REPORT.md` | active / reference/org-drafts |
| PII-boundary incident triage; rotation procedure | `INCIDENT_RESPONSE.md` | reference |
| The eleven first-visit disclosures and the no-implied-erasure rule | `FIRST_VISIT_NOTICE.md`; `SPEC.md` §5.1.2 | reference / active |
| Tier 0/1/2 production-touch boundary; the `attendanceClaimed` fail-open trap | `INTEGRATION_PLAN.md` §1/§8 | reference/integration, behind the freeze banner |
| "Unverified counts as not traced" | `TRACEABILITY.md` | active |
| Location-consent processing (discard precise coordinates after the Maps request; never store them) | `SPEC.md` §5.1.3 | active |
| Prohibited data uses (no selling student data, no behavioural ads, no facial-recognition retention, no precise location history, no full transcripts to tutors/managers) | `SPEC.md` §5.1.5 | active |
| Retention windows (pre-D-333 text; amendment marker owed via W-15) | `SPEC.md` §5.15.2 | active — flagged SPEC-drift |
| VLM failure → delete image and request text input | `SPEC.md` §5.29 | active — do not mark parked |
| D-333 consolidate-before-delete gate | `DECISIONS.md`; `reference/FIRST_VISIT_NOTICE.md` §3; `reference/U7_CHECKPOINT_CONSOLIDATION.md`; `PROJECT_STATE` §5 UD-7 | active/reference |

**Check.** No row above resolves to `docs/archive/`. And the W-42 caution holds: where documentation
reads wider than the implementation, the **narrow implementation is correct and deliberate** — the edit
narrows the *wording*, never the invariant, and must not imply a PII violation where the four columns
are allowlisted.

### 5.10 Every archival-bound document had its still-live knowledge extracted first

**Achieved by** HC-1 and the step-6 gate. Cross-reference:

| archive-bound | live knowledge | extraction step | verified where |
|---|---|---|---|
| `FINAL_ARCHITECTURE.md` | topology diagram; the §5.33.3 six-schema question; the one-database fact | steps 1, 2 | `ARCHITECTURE.md` (diagram + open-questions block); `PROJECT_STATE` §6.3 |
| `ROADMAP.md` | S42–S51 scope bullets + five embedded constraints (no "Done when" exists in the range); SPEC-to-session mapping | step 3 | `reference/integration/ROADMAP_FROZEN_SESSIONS.md` |
| `2026-07-19-branding-plan.md` | brand table; BD3 do-not-revert rule | step 4 | `ARCHITECTURE.md` |
| `S42_ORG_ASKS.md` | message text (verbatim); per-message dispositions | step 7a | the renamed archive file itself; substance in `ARCH-35-ORG-TIME`, `RD-12-INGRESS`, `INT-10-PEAK-CONCURRENCY` |
| `PROGRESS.md` | live carry-over items | Phase-4 register (pre-migration) | `PROJECT_STATE` §4/§5/§6 |
| `OPEN_DECISIONS.md` | #8's D-310 status; #10's unverified build items | step 7d annotation | `PROJECT_STATE` §9; `WORK-40`, `WORK-44-DECIDED-NOT-BUILT` |
| `2026-07-18-expansion-plan.md` | none extracted — archived intact | — | ROADMAP pointer repathed at step 9a |
| the 13 audit artifacts | all actionable content | pre-migration merge into 166 entries | reference register + `PROJECT_STATE` |

**Check.** For each row, open the destination and confirm the content is present *before* confirming
the source is archived. `HINT_SOLUTION_REVIEW.md` is the mirror-image case and belongs on the same
checklist: it is **not** archive-bound, and its front page is reconciled at step 5 **before** it moves
to reference, so that seven source files and two scripts do not end up citing a blessed wrong page.

---

## Appendix A — destination table for all 166 register entries

Mechanical application of §1's routing rules to `FINAL_OPEN_WORK_REGISTER.md`'s full entry index,
in the register's own section order.

**Legend.** `PS` = `docs/PROJECT_STATE.md`. `PS §4.1` active remediation · `PS §4.2` active
implementation · `PS §5` open user decisions · `PS §6.1` the D-152 freeze · `PS §6.2` blocked ·
`PS §6.3` deferred · `PS §6.4` parked · `PS §7` known unknowns. **"Historical"** = no future
destination; discoverable via `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`
(reference, not archive, so the link never points into a do-not-treat-as-current file). `W-nn` = the
§4 worklist row.

### A.1 Security and privacy (entries 1–19)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 1 | `D310-ROTATION` | RESOLVED | Historical + `PS §9` note; record archives at `archive/reconciliation-2026-08/REMEDIATION_D310_ROTATION.md` |
| 2 | `D310-RESIDUALS` | ACTIVE_REMEDIATION | `PS §4.1` |
| 3 | `R8-READ-SCOPE` | PARKED_BY_DECISION | `PS §6.4` (expiry: first real traffic) |
| 4 | `SEC-13-PURGE` | ACTIVE_REMEDIATION | `PS §4.1` |
| 5 | `REQ-32-SAFETY` | USER_DECISION_REQUIRED | `PS §5` — UD-9; §8 headline bullet (one-of-two-surfaces / one test / no escalation destination) |
| 6 | `DISCLOSURES-LEGAL` | USER_DECISION_REQUIRED | `PS §5` — UD-10 |
| 7 | `REQ-27-FROZENSET` | ACTIVE_IMPLEMENTATION | `PS §4.2` |
| 8 | `REQ-27-TOKEN-CONTRACT` | DEFERRED | `PS §6.3` (answerable only at frozen integration) |
| 9 | `RETENTION-CLUSTER` | USER_DECISION_REQUIRED | `PS §5` — UD-7 (D-333 precondition carried verbatim) |
| 10 | `WORK-35-LEDGER` | ACTIVE_IMPLEMENTATION | `PS §4.2` |
| 11 | `LANGSMITH-RETENTION` | BLOCKED | `PS §6.2` + `PS §5` pointer — UD-11 |
| 12 | `IMAGE-WORK-PARK` | PARKED_BY_DECISION | `PS §6.4`; cross-referenced from `CLAUDE.md` rule 8's clarifying line |
| 13 | `SEC-17-GUARDDUTY` | PARKED_BY_DECISION | `PS §6.4` (costed park, D-125) |
| 14 | `SEC-18-WAF` | DEFERRED | `PS §6.3` |
| 15 | `DRIFT-12-ADMIN-ROLE` | DEFERRED | `PS §6.3` |
| 16 | `G2-LOCATOR-PURGE` | OBSERVATION_ONLY | Historical (rider on UD-2's read-only database session); D-045's forward pointer → W-18 |
| 17 | `FIRST-VISIT-REVERIFY` | DEFERRED | `PS §6.3` (re-verify at S45 start) |
| 18 | `DRIFT-66-NL2SQL` | USER_DECISION_REQUIRED | `PS §5` — UD-12(d) |
| 19 | `DRIFT-70-CONSENT-GATE` | PARKED_BY_DECISION | `PS §6.4` |

### A.2 Cost and spend (entries 20–29)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 20 | `BUDGET-GROSS-SPEND` | USER_DECISION_REQUIRED | `PS §5` — UD-3 |
| 21 | `SPEND-AUTHORIZATION` | USER_DECISION_REQUIRED | `PS §5` — UD-2 |
| 22 | `COST-06-FLUSH` | ACTIVE_REMEDIATION | `PS §4.1` |
| 23 | `COST-10-INPUT-BOUND` | ACTIVE_IMPLEMENTATION | `PS §4.2` |
| 24 | `COST-25-ALARM-COUNT` | RESOLVED (count) + DOCUMENTATION_ONLY residual | Historical; billing-line residual → **W-01** (step 11 batch I) + the X-Ray trace-storage line as its own sentence (W-01) |
| 25 | `D136-PRICE-TABLE` | DOCUMENTATION_ONLY | **W-01** → `ARCHITECTURE.md` |
| 26 | `COST-29-EXTRAPOLATION-BAN` | OBSERVATION_ONLY | Historical; the extrapolation ban itself stays in `ARCHITECTURE.md`'s capacity table |
| 27 | `INT-10-PEAK-CONCURRENCY` | PARKED_BY_DECISION | `PS §6.4` |
| 28 | `SPEND-ATTRIBUTION-DOC` | DOCUMENTATION_ONLY | **W-02** → `reference/audits/AUDIT_2026_08_16.md` + archived PROGRESS |
| 29 | `DRIFT-86-COST-RUNBOOK` | ACTIVE_REMEDIATION | `PS §4.1` |

### A.3 Observability and alerting (entries 30–37)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 30 | `RD-01` | ACTIVE_REMEDIATION | `PS §4.1` + `PS §8` headline (permanent false ALARM since 2026-08-16) |
| 31 | `KPI-ALARM-FLOOR` | USER_DECISION_REQUIRED | `PS §5` — UD-5 |
| 32 | `ALERT-ENDPOINT` | USER_DECISION_REQUIRED | `PS §5` — UD-6 |
| 33 | `LANGSMITH-INGEST` | ACTIVE_REMEDIATION | `PS §4.1` |
| 34 | `SNS-CONFIRMATION` | RESOLVED | Historical (D-419's PendingConfirmation warning dated resolved by W-28) |
| 35 | `COST-22-LABEL-PREINIT` | ACTIVE_REMEDIATION | `PS §4.1` |
| 36 | `COST-17-CLIENT-ERRORS` | DEFERRED | `PS §6.3` |
| 37 | `ARCH-30-OTEL` | OBSERVATION_ONLY | Historical |

### A.4 Infrastructure and deployment (entries 38–52)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 38 | `LB-05-DEPLOY-GAP` | USER_DECISION_REQUIRED | `PS §5` — UD-1; also `PS §1` snapshot header and `PS §3` deploy gap |
| 39 | `RDS-POSTURE` | USER_DECISION_REQUIRED | `PS §5` — UD-4 (§2.6 documentation obligation stands regardless) |
| 40 | `NAT-EXISTENCE` | RESOLVED | Historical; the ~$32.9/month gross figure lands in `ARCHITECTURE.md` via W-44; D-419's "absent from the plan entirely" sentence → **W-04** |
| 41 | `ARCH-21-SCHEMA-SPLIT` | DEFERRED | `PS §6.3` **+ `ARCHITECTURE.md` "Open architecture questions (undecided)" block** — extraction at step 2 (HC-2) |
| 42 | `ARCH-34-REVISION-DRIFT` | OBSERVATION_ONLY (tfvars half UNKNOWN) | Historical; the tfvars-staleness half → `PS §7` |
| 43 | `RD-12-INGRESS` | PARKED_BY_DECISION | `PS §6.4`; the CloudFront-domains sentence → `CLAUDE.md` (step 14) |
| 44 | `WORK-23-RETENTION-JOB-GATING` | PARKED_BY_DECISION | `PS §6.4` (RD-01 blocks its stated prerequisite) |
| 45 | `ARCH-33-CI-GATE` | DEFERRED | `PS §6.3` |
| 46 | `COST-28-EIP` | OBSERVATION_ONLY | Historical |
| 47 | `F-03-DRIFT-DETECTOR` | OBSERVATION_ONLY | Historical + `PS §8` method rule (carried forward) |
| 48 | `DRIFT-24-ARTIFACT-FRESHNESS` | DOCUMENTATION_ONLY | **W-03** → `ARCHITECTURE.md`; mechanism half rides UD-1 |
| 49 | `LB-06-TRANSPORT-POSTURE` | OBSERVATION_ONLY | Historical |
| 50 | `DOC-DEPLOYED-STATE-CLAIMS` | DOCUMENTATION_ONLY | **W-04** → `ARCHITECTURE.md` + `DECISIONS.md`; PROGRESS/OPEN_DECISIONS copies quarantined behind archive banners |
| 51 | `DOC-SCHEDULER-SECTIONS` | DOCUMENTATION_ONLY | **W-05** → `ARCHITECTURE.md` (single-homed at step 10) |
| 52 | `DRIFT-93-D401-D406-APPLIED` | RESOLVED | Historical; it is the evidence that `OPEN_DECISIONS`' "stay unapplied" line must not be copied |

### A.5 Learning product and content (entries 53–74)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 53 | `WORK-40` | ACTIVE_IMPLEMENTATION | `PS §4.2` |
| 54 | `DIFFICULTY-TIERS-CONFLICT` | USER_DECISION_REQUIRED | `PS §5` — UD-12(a) |
| 55 | `PROSE-QUALITY` | USER_DECISION_REQUIRED | `PS §5` — UD-12(c) |
| 56 | `D356-FAMILY` | ACTIVE_REMEDIATION (+ documentation member) | `PS §4.1`; documentation member → **W-18** |
| 57 | `REQ-39-ESTIMATED-LEVEL` | USER_DECISION_REQUIRED | `PS §5` — UD-12(e) |
| 58 | `IRT-UPGRADE` | DEFERRED | `PS §6.3` |
| 59 | `ARCH-17-COMMIT-SEAM` | ACTIVE_REMEDIATION | `PS §4.1` |
| 60 | `WORK-24-DUPLICATE-GAIN` | ACTIVE_REMEDIATION | `PS §4.1` |
| 61 | `D342-PARKING` | PARKED_BY_DECISION | `PS §6.4`; the park banner stays in `reference/QUESTION_GENERATION.md` |
| 62 | `VIDEO-COVERAGE-PARK` | PARKED_BY_DECISION | `PS §6.4` (the figure the park was argued from was 100x stale — recorded, not re-argued) |
| 63 | `WORK-12-BANNER` | ACTIVE_IMPLEMENTATION | `PS §4.2` |
| 64 | `WORK-44-DECIDED-NOT-BUILT` | ACTIVE_IMPLEMENTATION (#3, #9); #2/#13 RESOLVED | `PS §4.2` for #3 and #9; #13 Historical; **#2's shared anonymous bucket → the accepted-residual-risk set via W-22** (same shape as `SEC-18-WAF`) |
| 65 | `D329-PHANTOM` | ACTIVE_REMEDIATION | `PS §4.1`; the phantom id itself annotated "cited, never written" by **W-25** |
| 66 | `D141-TRIM` | USER_DECISION_REQUIRED | `PS §5` — UD-12(b) |
| 67 | `DRIFT-49-MODEL-ROSTER` | UNKNOWN | `PS §7` (resolution step named; placeholder defaults fixable without a decision) |
| 68 | `K5-HINT-INSTRUMENTS` | UNKNOWN | `PS §7` (read D-264) |
| 69 | `D288-D317-CLOSURE` | UNKNOWN | `PS §7` (read both bodies) |
| 70 | `DOC-CONTENT-PIPELINE` | DOCUMENTATION_ONLY | **W-06** → `reference/QUESTION_GENERATION.md` + `reference/CONTENT_COVERAGE.md` |
| 71 | `DOC-HINT-SOLUTION-REVIEW` | DOCUMENTATION_ONLY | **W-07** → `reference/HINT_SOLUTION_REVIEW.md`, executed at step 5 before the move (HC-3) |
| 72 | `DOC-U7-BANNER` | DOCUMENTATION_ONLY | **W-08** → `reference/U7_CHECKPOINT_CONSOLIDATION.md` |
| 73 | `DRIFT-72-OUTCOME-ENUM` | OBSERVATION_ONLY | Historical |
| 74 | `DRIFT-59-DATE-SHIFT` | ACTIVE_IMPLEMENTATION | `PS §4.2` (armed under an "ALL DECIDED" heading — the heading is a rot hazard, W-44) |

### A.6 Chat, RAG and escalation (entries 75–81)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 75 | `WORK-40-TZ` | ACTIVE_REMEDIATION | `PS §4.1` (human-approval integrity: approval times render in the viewer's locale) |
| 76 | `WORK-01-SCOPE-GUARD` | ACTIVE_IMPLEMENTATION | `PS §4.2` (specified, measured at roughly 22%, not built) |
| 77 | `WORK-04-ANSWER-CACHE` | RESOLVED | Historical — settled by D-423's numbers, not deferred |
| 78 | `H1-ACCESS-PROBE` | OBSERVATION_ONLY | Historical |
| 79 | `H2-AUDC23` | DOCUMENTATION_ONLY | **W-09** → `reference/audits/AUDIT_FINDINGS.md` + `DECISIONS.md` |
| 80 | `H5-LIVENESS-TIMER` | OBSERVATION_ONLY | Historical (the 40 s / 15 s ratio is argued, not measured live) |
| 81 | `ACCESS-HINT-FIGURES` | DOCUMENTATION_ONLY | **W-10** → `DECISIONS.md` + archived ledger |

### A.7 Testing and verification method (entries 82–99)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 82 | `C6-UNATTENDED` | BLOCKED | `PS §6.2`; also UD-1's named sub-question (does the unattended week restart clean?) |
| 83 | `DB-CONTENT-VERIFY` | BLOCKED | `PS §6.2`; rider on UD-2 |
| 84 | `WORK-13-FIXTURES` | ACTIVE_IMPLEMENTATION | `PS §4.2` (behaviourally resolved; test-side fix still owed — do not re-run it as if open) |
| 85 | `PLAYWRIGHT-LANE` | DEFERRED | `PS §6.3` |
| 86 | `PAID-RUNS-LANE` | DEFERRED | `PS §6.3` |
| 87 | `REQ-44-REASON-SWEEP` | ACTIVE_REMEDIATION | `PS §4.1` (passes vacuously outside the dict) |
| 88 | `M3-D370-SOLUTION-RUNG` | ACTIVE_IMPLEMENTATION | `PS §4.2`; the D-366 ⏸ / D-370 ✅ status contradiction → W-18 |
| 89 | `TEST-05-DESCRIPTIVE-REREAD` | ACTIVE_REMEDIATION | `PS §4.1` (the one entry with a shared engineering/documentation owner) |
| 90 | `TEST-24-429` | DEFERRED | `PS §6.3` (deliberately open) |
| 91 | `TEST-01-CRITERION1` | OBSERVATION_ONLY | Historical; the method rule lands in `AUTHORITY_MODEL` **§5.8** (gate verdicts are quoted with the reading that produced them) |
| 92 | `F4-CRITERION6` | PARKED_BY_DECISION | `PS §6.4` — reopen condition is live and currently unmonitored |
| 93 | `H3-ICS-WEBKIT` | OBSERVATION_ONLY | Historical |
| 94 | `TEST-21-HISTORICAL` | OBSERVATION_ONLY | Historical — unobservable by construction |
| 95 | `TRACEABILITY-ARITHMETIC` | DOCUMENTATION_ONLY | **W-11** → `TRACEABILITY.md` (+ archived ROADMAP, `reference/integration/INTEGRATION_PLAN.md`) |
| 96 | `AUDIT-COUNT-INSTRUMENT` | DOCUMENTATION_ONLY | **W-12** → `reference/audits/*`, after step 8 |
| 97 | `SUITE-COUNT-CITATIONS` | DOCUMENTATION_ONLY | **W-13** → archived PROGRESS + archived ledger |
| 98 | `DOC-TEST-CLAIM-WORDING` | DOCUMENTATION_ONLY | **W-14** → `TRACEABILITY.md` + `DECISIONS.md` |
| 99 | `DRIFT-58-E2E-ISOLATION` | RESOLVED at claim scope (+ DEFERRED residual) | Historical at claim scope; paid cross-spec residual carried in `PS §4.2`'s `WORK-13-FIXTURES` row (UD-2 whole-directory arm) |

### A.8 Integration and organization — the D-152 domain (entries 100–112)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 100 | `ORG-COMMS` | USER_DECISION_REQUIRED | `PS §5` — UD-8. **Permitted under the freeze (INT-28)**; live user work, not parked |
| 101 | `ARCH-35-ORG-TIME` | BLOCKED | `PS §6.2` (`ORG_TIME_CONFIRMED = false` deployed; D-153 §4 guard owed at a frozen session) |
| 102 | `INT-29-FAQ` | BLOCKED | `PS §6.2`; the draft itself → `reference/org-drafts/ENROLLMENT_FAQ_APPROVAL.md` |
| 103 | `D152-FREEZE` | PARKED_BY_DECISION | **`PS §6.1`** — the canonical freeze statement, verbatim, with its reopen condition |
| 104 | `S43-SCOPE` | PARKED_BY_DECISION | `PS §6.4`; scope detail → `reference/integration/ROADMAP_FROZEN_SESSIONS.md` |
| 105 | `AUTH-OPTION-O1B` | PARKED_BY_DECISION | `PS §6.4` (stays a recommendation until measured, right before S44) |
| 106 | `F2-ADAPTER-SHAPE` | DEFERRED | `PS §6.3` |
| 107 | `F3-DEVTOKEN-S44` | DEFERRED | `PS §6.3` |
| 108 | `SEC-34-ROLE-ALLOWLIST` | DEFERRED | `PS §6.3` (asserted in four documents, not yet designed) |
| 109 | `INT-ATTENDANCE-DERIVATION` | DEFERRED | `PS §6.3`; the fail-open trap itself stays in `reference/integration/INTEGRATION_PLAN.md` §8 |
| 110 | `COMMITTED-ORG-DRAFTS` | USER_DECISION_REQUIRED | `PS §5` — UD-12(f). **Key correction at step 9c**: the queue cites `RISK-R7.2`; this key is authoritative |
| 111 | `DRIFT-91-ORGTIME-IMPORT` | ACTIVE_REMEDIATION | `PS §4.1` — a seam-honesty defect, which is the one engineering obligation the freeze leaves open |
| 112 | `DRIFT-85-I7-ALLOWLIST` | BLOCKED | `PS §6.2` |

### A.9 Documentation and decision-log hygiene (entries 113–145)

| # | KEY | disposition | future destination |
|---|---|---|---|
| 113 | `AMENDMENT-SWEEP` | DOCUMENTATION_ONLY | **W-15** → `SPEC.md` (step 11 batch F) |
| 114 | `STATUS-TAG-CONVENTION` | DOCUMENTATION_ONLY | **W-16** → `DECISIONS.md` (also a design input, with a safe default) |
| 115 | `AUDIT-ID-NAMESPACE` | DOCUMENTATION_ONLY | **W-17** → `reference/audits/README.md`, created at step 8 |
| 116 | `DOC-DECISION-LOG-CORRECTIONS` | DOCUMENTATION_ONLY | **W-18** → `DECISIONS.md` |
| 117 | `DOC-PROGRESS-QUEUED-BLOCK` | DOCUMENTATION_ONLY | **W-19** → the four-row block retired at step 7d with `archive/PROGRESS.md`'s banner |
| 118 | `D192-PHANTOM` | UNKNOWN — irreducible by design | `PS §7` as a **permanent** unknown; the only action is one clarifying sentence |
| 119 | `RISK-GROUP-FREEZE` | DOCUMENTATION_ONLY | **W-20** → freeze banners at steps 7a/7c, ROADMAP half at step 3, `CLAUDE.md` link at step 14 |
| 120 | `RISK-GROUP-ARCH-AUTHORITY` | DOCUMENTATION_ONLY | **W-21** → extractions at steps 1–2, rename at step 7b, hierarchy at steps 10 and 14 |
| 121 | `RISK-R2.2-ACCEPTED-RISK-HOMES` | DOCUMENTATION_ONLY | **W-22** → expiry conditions single-homed in `PS §6.4` at step 10 |
| 122 | `RISK-GROUP-CURRENT-STATE` | DOCUMENTATION_ONLY | **W-23** → `PROJECT_STATE.md` + the ROADMAP/PROGRESS split (steps 3, 7d, 9). Largest block; **split shape to be ratified with the user** |
| 123 | `RISK-R1.4-SPEC-VINTAGE` | DOCUMENTATION_ONLY | **W-24** → `SPEC.md` + `CLAUDE.md` |
| 124 | `RISK-GROUP-DECISIONS-HYGIENE` | DOCUMENTATION_ONLY | **W-25** → `DECISIONS.md`; phantom ids annotated, never reconstructed |
| 125 | `RISK-GROUP-AUDIT-REGISTERS` | DOCUMENTATION_ONLY | **W-26** → `reference/audits/*` (early, after step 8) |
| 126 | `RISK-GROUP-NAMING` | DOCUMENTATION_ONLY | **W-27** → two renames at step 7; the rest re-described plus indexed |
| 127 | `RISK-GROUP-RESOLVED-LOOKS-OPEN` | DOCUMENTATION_ONLY | **W-28** → `CLAUDE.md` (step 14) + `reference/integration/S42_OPEN_QUESTIONS.md` (step 7c) + annotations on the archived `OPEN_DECISIONS.md` |
| 128 | `TRACKING-HOME-FOR-OPEN-ITEMS` | DOCUMENTATION_ONLY | **W-29** → `PS §5`/`§6`/`§7` + send-status line + `ARCHITECTURE.md` open-questions block |
| 129 | `RISK-GROUP-INDEX` | DOCUMENTATION_ONLY | **W-30** → `CLAUDE.md` at **step 14** (cheapest, highest priority) |
| 130 | `RISK-GROUP-DUPLICATE-CONTENT` | DOCUMENTATION_ONLY | **W-31** → the step-10 single-homing table |
| 131 | `RISK-GROUP-EXECUTED-PLANS` | DOCUMENTATION_ONLY (+ one engineering half) | **W-32** → `archive/plans/*` executed-as headers + brand data to `ARCHITECTURE.md` at step 4; `packages/ui-brand` promotion split out as engineering. **Fix the D-number line first** — engineering half tracked in W-32's row, not `PS §4.1` (the 27-count is by primary disposition) |
| 132 | `RISK-GROUP-OPS-DOC-STRATA` | DOCUMENTATION_ONLY | **W-33** → `ARCHITECTURE.md` + the five reference ops documents |
| 133 | `RISK-R7.3-DANGLING-REFS` | DOCUMENTATION_ONLY | **W-34** → pointer fixes at steps 9a/9b |
| 134 | `RISK-R6.4-SESSION-LABELS` | DOCUMENTATION_ONLY | **W-35** → `PROJECT_STATE` documentation map + per-file annotations (prerequisite for naming two owners) |
| 135 | `RISK-R6.5-SUPERSESSION-DIRECTION` | DOCUMENTATION_ONLY | **W-36** → `reference/integration/*` at step 7c, one pass per file with W-20 |
| 136 | `DOC-SNAPSHOT-BANNERS` | DOCUMENTATION_ONLY | **W-37** → as-of banners on the three snapshot documents |
| 137 | `DOC-VINTAGE-HEADERS` | DOCUMENTATION_ONLY | **W-38** → all four living documents; executed at **steps 0c and 14** (HC-6) |
| 138 | `DOC-LINE-CITATION-DRIFT` | DOCUMENTATION_ONLY | **W-39** → `TRACEABILITY.md` first, then the other two |
| 139 | `BATCH-LOW-CITATIONS` (9 members) | DOCUMENTATION_ONLY | **W-40** → `TRACEABILITY.md` + `ARCHITECTURE.md` + `reference/audits/AUDIT_FINDINGS.md` |
| 140 | `BATCH-LOW-STALE-STATUS` (10 members, 3 exceptions) | DOCUMENTATION_ONLY | **W-41** → `ARCHITECTURE.md` + W-08's U7 banner; DRIFT-81 recorded as a known limitation |
| 141 | `BATCH-LOW-OVERSTATEMENT` (11 members, 2 exceptions) | DOCUMENTATION_ONLY | **W-42** → `CLAUDE.md` + `SPEC.md` + `reference/INCIDENT_RESPONSE.md`; wording narrows, invariants do not |
| 142 | `BATCH-LOW-UNMARKED-SPEC` (5 members, 1 exception) | DOCUMENTATION_ONLY | **W-43** → `SPEC.md` + `reference/CONTENT_COVERAGE.md` + `TRACEABILITY.md` |
| 143 | `BATCH-LOW-UNSCHEDULED-CONTROLS` (6 members, 4 exceptions) | ACTIVE_REMEDIATION | `PS §4.1` — controls that exist but nothing schedules, invokes or rotates |
| 144 | `BATCH-LOW-NARROW-COVERAGE` (4 members, 1 exception) | ACTIVE_IMPLEMENTATION | `PS §4.2` — three small code gaps |
| 145 | `BATCH-LOW-CONFIG-VS-PLAN` (4 members, 2 exceptions) | DOCUMENTATION_ONLY | **W-44** → `ARCHITECTURE.md` (capacity plan; egress reframed as baseline-with-exception) |

### A.10 Audit-method observations and the resolved/superseded record (entries 146–166)

All 21 entries in this section are historical: no future destination, discoverable via
`docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`. Where a historical entry carries a
durable *method* lesson, the destination column names where that lesson lands.

| # | KEY | disposition | future destination |
|---|---|---|---|
| 146 | `LB-09-NULL-RESULT` | OBSERVATION_ONLY | Historical — a null result is evidence and is recorded as such |
| 147 | `LB-08-CORROBORATIONS` | OBSERVATION_ONLY | Historical; the 10.55-second latency anchor is quoted **only** with its build SHA and its pre-D-423 status (`PS §3`) |
| 148 | `JUDGE-HISTOGRAM-PROVENANCE` | OBSERVATION_ONLY | Historical — blocked by lane, not needed |
| 149 | `G7-SESSION-RENUMBER` | OBSERVATION_ONLY | Historical; the bound (old S17–S23 only) feeds **W-35** |
| 150 | `MAP-HORIZON` | OBSERVATION_ONLY | Historical — the supersession map stops at D-419 while the log runs to D-423; no finding is stale as a result |
| 151 | `F-17-STRENGTHENINGS` | RESOLVED | Historical — the evidence conversions that make the claim ledger trustworthy (562 tests executed) |
| 152 | `F-04-QUOTE-FLOOR-LOCATION` | RESOLVED | Historical; the corrected test location feeds **W-40** |
| 153 | `F-05-TOPIC-MAPPING` | RESOLVED | Historical; adopt its wording — **"declared and never used", not "absent"** (**W-43**) + **W-15** (the unamended thirteen-type list) |
| 154 | `F-07-ARCH01-SPLIT` | RESOLVED | Historical; its split feeds **W-21** — ARCHITECTURE is current on decisions, stale only on session provenance (32 of 48 tagged) |
| 155 | `LIVE-HALVES-SUPERSEDED` | SUPERSEDED | Historical — every live/deployed half outside 3A.5's scope was discharged by Phase 3B |
| 156 | `RUFF-DENOMINATOR` | OBSERVATION_ONLY | Historical; the method point (437 → 440 is not drift) feeds **W-19** |
| 157 | `WHOLE-SUITE-NOT-RUN` | OBSERVATION_ONLY | Historical; the wording discipline ("the suite is green" is not "everything run passed") feeds **W-13** and `AUTHORITY_MODEL` §5 |
| 158 | `NO-NEW-TEST-CODE` | OBSERVATION_ONLY | Historical; the consequence sentence lands in `PS §4.3`'s preamble (three defects established by code reading only) |
| 159 | `WORK-06-DEPLOY-EVENT` | RESOLVED | Historical — the post-deploy probe found what the green suite did not |
| 160 | `WORK-09-AGENT-TOOLING` | RESOLVED | Historical |
| 161 | `WORK-34-STUDY-RESERVE` | RESOLVED | Historical (D-325 option A) |
| 162 | `WORK-41-CVE-REPRODUCIBILITY` | RESOLVED (with limitation) | Historical — option B chosen because two measurements made option C impossible today; the limitation travels with the claim |
| 163 | `WORK-42-INTERSTITIAL-BYPASS` | RESOLVED (with limitation) | Historical — the YouTube interstitial ships with an **accepted** middle-click bypass; the acceptance is the record; **the accepted bypass → the launch-readiness accepted-residual-risk set via W-22** (primary users are minors) |
| 164 | `WORK-43-FRONTEND-TESTS` | RESOLVED (+ documentation count defect) | Historical; the wrong "two against recommendation" count → **W-13** |
| 165 | `D190-D191-PHANTOM` | RESOLVED | Historical — **the phantom trio's meta-note is the active record and must not be "completed"** |
| 166 | `ARCH-27-SSE-GAP` | RESOLVED | Historical — the single-instance SSE "known gap" was closed by D-334/D-335 |

### A.11 Appendix arithmetic

| destination | entries |
|---|---|
| `PS §4.1` + `§4.2` (active engineering) | 27 |
| `PS §5` (open user decisions — 11 carrying UD ids; UD-11 is sourced from the BLOCKED `LANGSMITH-RETENTION`) | 16 |
| `PS §6.1`/`§6.2`/`§6.3`/`§6.4` (blocked, deferred, parked) | 34 |
| `PS §7` (known unknowns) | 4 + `ARCH-34`'s residual half (counted under OBSERVATION_ONLY) = 5 substances |
| §4 worklist rows W-01 … W-44 | 44 |
| Historical, via the reference register | 41 |
| **Total** | **166** |

Cross-check against the register's own §12.1 counts: `USER_DECISION_REQUIRED` 16 ·
`ACTIVE_REMEDIATION` 16 · `ACTIVE_IMPLEMENTATION` 11 · `BLOCKED` 6 · `DEFERRED` 15 ·
`PARKED_BY_DECISION` 13 · `DOCUMENTATION_ONLY` 44 · `OBSERVATION_ONLY` 21 · `RESOLVED` 19 ·
`SUPERSEDED` 1 · `UNKNOWN` 4 = **166**. Entries belonging in `PROJECT_STATE`: **81**
(16 + 16 + 11 + 6 + 15 + 13 + 4), which is the sum of the first four rows above.

---

## Closing note — what this manifest deliberately does not do

- It answers **no** user decision. Twelve remain open, with their safe defaults.
- It resolves **no** UNKNOWN into a conclusion. Five substances remain unknown, with named next steps.
- It takes **no** D-152-frozen action and solicits no reopening.
- It changes **no** application code, terraform, or test. Twelve engineering halves are named and
  handed off rather than performed or hidden.
- It writes **no** decision on the six-schema split, the retention windows, the safety posture, the
  alerting endpoint, the RDS posture, the budget, or the deploy. It only makes sure that each of those
  questions is impossible to lose.
- It surfaces, rather than decides, one open design question: where per-session narration lives after
  `PROGRESS.md` archives (git commits only, or a non-authoritative `docs/log/`), and the matching
  `/end-session` reconciliation — §2.F.2. Executing this manifest requires the user's answer to that
  question, the approval of the target tree, and the migration-time sign-off points listed in W-15.

Nothing in this file has been executed. Executing it requires the user's approval of the target tree in
`DOCUMENT_MODEL.md` and of the split shapes flagged for ratification in W-23.
