> **ARCHIVED 2026-08-20. Historical record — do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase-7 adjudication record (MIGRATION_READY); the migration it cleared executed 2026-08-20.
> **Superseded by:** the executed tree; see `docs/archive/README.md`.

# REVIEW_RESOLUTION.md — Phase 7 adjudication of the adversarial review

**Status:** COMPLETE, 2026-08-20. Resolves all 64 findings of
`docs/reconciliation/review/ADVERSARIAL_REVIEW.md` and applies the accepted corrections to the four
files under `docs/reconciliation/proposal/` — **and nothing else**. No canonical project document,
source file, reconciliation evidence artifact, Phase-4 register/queue, `CLAUDE.md`, or
infrastructure was touched. The migration itself has **not** begun.

**Method.** Every finding was adjudicated individually against primary evidence, assuming neither
the proposal author nor the reviewer correct. All CRITICAL/HIGH findings were re-verified against
primary sources before correction (Phase-6 verification greps plus fresh Phase-7 re-reads of:
D-050's body at `DECISIONS.md:992-1002`; D-333's verbatim instruction at `DECISIONS.md:23843-23845`;
`USER_DECISION_QUEUE.md:470-472`; the `SEC-13-PURGE` durable-leak clauses at register `:318`/`:325`;
`REQ-32-SAFETY`'s no-escalation-destination clauses at register `:348-376`;
`INCIDENT_RESPONSE.md:22-25`; `DOCUMENTATION_RISK_REGISTER.md` heading counts 49/18;
`ROADMAP.md` "Done when" range grep = 0 hits in lines 525–1769; `.gitignore:67` + `git ls-files`;
`docs/plans/2026-07-19-branding-plan.md:64,:115` vs `DECISIONS.md:1479-1487` vs
`packages/ui-brand/tokens.css:37`; `apps/chat-api/tests/test_chat_endpoints.py:503-506,:560-562`).
Corrections were applied by four per-file edit executors with per-edit ledgers, followed by an
independent 15-point consistency verification and a residual-closure pass.

---

## 1. Summary

| Metric | Value |
|---|---|
| Findings adjudicated | **64 / 64** |
| ACCEPTED | **64** — 58 corrected exactly as the review specified; **6 with a modified remedy** (§4), reasons recorded |
| REJECTED_WITH_EVIDENCE | **0** |
| NEEDS_VERIFICATION | **0** |
| USER_DECISION_REQUIRED (findings) | **0** — no factual/mechanical correction was escalated; one genuine **design question** is surfaced (§6, DQ-1) |
| CRITICAL remaining | **0** |
| HIGH remaining | **0** |
| Technical migration blockers remaining | **0** |
| Status | **MIGRATION_READY** (§8 — execution still requires the user inputs listed there) |

Why zero rejections is the honest outcome, not deference: the Phase-6 review was itself built on
direct primary-evidence verification (every CRITICAL/HIGH was re-read against code, git state,
ROADMAP text, or the registers before it was filed, and 20 tested suspicions were rejected there).
Phase 7 re-tested the contested points independently — including the four safety-critical re-reads
above — and every finding held. Where the reviewer's *remedy* was wrong or over-reached, the remedy
was changed, not the finding (§4).

---

## 2. Disposition record — all 64 findings

Correction references: **PS** = `proposal/PROJECT_STATE.md`, **MM** = `proposal/MIGRATION_MANIFEST.md`,
**AM** = `proposal/AUTHORITY_MODEL.md`, **DM** = `proposal/DOCUMENT_MODEL.md`. "Blocker after" =
whether the finding still blocks migration after resolution.

| RF | Sev | Disposition | Primary evidence checked | Correction applied | Blocker after |
|---|---|---|---|---|---|
| 01 | CRIT | ACCEPTED | DM O1/§10.1/§10.2/§8.1 vs MM step order (5 conflicting statements, quoted) | MM: new **Phase 0** (0a promote+skeleton via `git mv`, 0b hazard grep, 0c vintage headers), **HC-8**, step 13 → summarize-only, step 9 create-clause removed, Phase-2 header + rule-1/rule-10 Phase-0 carve-outs; DM: O1/§10.1/§10.2/§8.1 name step 0a. DAG re-checked: O1–O20 + HC-0–8 all satisfiable | NO |
| 02 | CRIT | ACCEPTED | `grep "Done when" ROADMAP.md` lines 525–1769 = **0**; `ROADMAP.md:1436-1530` read (scope bullets + 5 embedded constraints) | DM §6.2/§11/§4-tree/O5; MM §2.C.4/§2.F.1/step 3/step-6 gate/§5.10/§5.45: extraction target = S42–S51 scope bullets + the 5 constraints (D-153 §5 role gate, 6 dev-fake mismatches, `BranchInfo` merge, D-153 §4 window assertion, D-167 `/dev/token` cascade incl. `sub`); "no Done-when exists — author none" stated at every site; line-1 freeze banner required | NO |
| 03 | HIGH | ACCEPTED | Queue option texts `:298-299,:368,:436,:615-617,:671-674,:834-836` are answer-shaped; PS:169 authorized applying them | PS §5: two-class preamble; UD-1/2/3/7/10/11 tagged `[agent may apply]`; UD-4/5/6/8/9/12(a) tagged `[USER ONLY — hold:]` with non-committal holds | NO |
| 04 | HIGH | ACCEPTED | Queue `:470-472` ("carry verbatim"); grep PS = 0 hits (pre-fix) | PS UD-7 cell: D-333 verbatim + verify-implemented-before-any-dry-run-flip; §6.4 `WORK-23` pointer | NO |
| 05 | HIGH | ACCEPTED | PS §6.4 had 13 rows, no R9; 4 places single-home it there | PS §6.4: **accepted-risk expiries block** (R8 pointer + R9 "any movement in `learning_checkpoint_repairs_total` voids the acceptance"; UD-5 sub-question); §4.1 ARCH-17 → pointer; MM §5.4 check extended. (Register 13-PARKED count preserved — block, not a 14th row) | NO |
| 06 | HIGH | ACCEPTED | PS §5 header had 4 cols; 4 UD keys 0 hits in file | PS §5: `Register key` column, all 12 populated; MM §2.G.1/§5.2 wording now true | NO |
| 07 | HIGH | ACCEPTED | MM `:746-750` "open design question for the user" vs PS §10's settled rule | PS §10 narration bullets marked **provisional pending §2.F.2**, `docs/log/` alternative named, `/end-session` reconciliation required; MM closing note surfaces the question (DQ-1, §6) | NO (DQ-1 surfaced) |
| 08 | HIGH | ACCEPTED | Plan `#d13a80` (:64,:115) vs D-067 (`4.16:1, a real fail`; `#c22f73`) vs `tokens.css:37` | DM §6.3: extraction sourced from **D-067 + tokens.css** (`#387e40`, `#c22f73`); `#d13a80` marked superseded; false "effectively deleted" justification replaced; §14 R4.2 row updated | NO |
| 09 | HIGH | ACCEPTED | `git check-ignore` → `.gitignore:67`; `git ls-files` → untracked; PROGRESS `:10137-10139` "deliberately never committed" | MM §2.F.5 + DM §8.4: `.gitignore:67` updated to the archive path in the same commit; file **stays untracked**; tracking is UD-12(f), not decided by a rename; §2.C.1's "rule falsified" claim softened to "partially honoured" | NO |
| 10 | HIGH | ACCEPTED | `test_chat_endpoints.py:503-506,:560-562` assert the purge's effect (success path) | PS §4.3 SEC-13: coverage claim corrected ("no test covers the cancel or exception path… the Phase-4 'zero tests' claim was a symbol-grep, corrected here"). **Upstream error recorded** (§5): register `SEC-13-PURGE` + `LOCAL_EXECUTION_FINDINGS.md` F-11's "would break no test" are wrong — artifacts left untouched per Phase-7 rules | NO |
| 11 | HIGH | ACCEPTED (modified remedy, §4) | Register `:348-376` (one screen, one test, no escalation destination); queue option D "independent of Guardrails" | PS §8: child-safety headline bullet; UD-9 hold names the three unowned engineering deliverables. **No new §4.2 row** — see §4 | NO |
| 12 | HIGH | ACCEPTED | `grep -cE '^### '` risk register = 49; HIGH headings = 18 | AM §0 → "49 … 18 … (counts derived mechanically …, 2026-08-20)" | NO |
| 13 | HIGH | ACCEPTED | Both triggers keyed to date/HEAD; deploy is MANUAL (PS:18); UD-1 is exactly that event | AM §2.1 + PS §1: third trigger (deployed image tag mismatch); PS §3 conditional on `gha-44a12dfc9549` | NO |
| 14 | HIGH | ACCEPTED | `INCIDENT_RESPONSE.md:22-25` ("don't under-react to a MySQL-adjacent incident"); committed prod credentials in local checkout (CLAUDE.md) | MM §2.B.1: scoped wording ("does **not** mean the tier is not a live exposure surface … triage severity unchanged"); forbidden phrase banned from the executed edit; DM §7.1's matching stale framing rewritten | NO |
| 15 | HIGH | ACCEPTED | D-050 body re-read (`DECISIONS.md:992-1002`): student/parent/guardian scope, 2 tables, `ALLOWED_PII_SHAPED_COLUMNS`, fails-loudly | MM W-42 + §5.9 rule-1 row carry the **exact required wording** (no subject-free carve-out); W-30 sole owner | NO |
| 16 | HIGH | ACCEPTED | Register `:4694-4705` ("at least eleven stale tags read as active"; `PROJECT_STATE? no`) | AM §3.1 item 2a + §4.1 verify-the-label clause; PS §8 residual bullet | NO |
| 17 | HIGH | ACCEPTED | Rule existed only at DM §9.1 (a file that archives); AM §2.6 read literally inverted it | AM **§4.7** (PROJECT_STATE = whether open; register = why opened; register never triggers work) + §7 never-trust cell; DM §9.1 banner spec carries the precedence sentence | NO |
| 18 | HIGH | ACCEPTED | ~18 rows carried non-11 steps vs step 11's blanket instruction; O12/O13/O16/O17 violated via batch order | MM: step 11 restated (rows-whose-step-is-11 + split-row list), §4 lead-in "Execution order across all steps", **step 7e** created (W-08/O13 + O14 items), W-35 → batch A, W-39 first in batch I, batch G = W-25→W-16→W-18, hazard grep → step 0b; HC-6 rewritten; DM O-table annotated | NO |
| 19 | HIGH | ACCEPTED | grep across 4 files: zero `git mv`/commit-granularity instructions | MM §0.2 **rule 10** (git mv; banner as separate commit; per-phase commits; `--follow` verification; pre-0a clean commit) + step-6 revert path + step 15 `git mv` | NO |
| 20 | MED | ACCEPTED | Register `:1212-1215` (X-Ray line "deserves its own sentence"); "X-Ray" absent from MM | MM W-01 + Appendix row 24: both residual lines, X-Ray as its own sentence | NO |
| 21 | MED | ACCEPTED | §1 enumerates 7; register compound dispositions confirm 7 | MM: "Seven entries (M1–M7)"; §5.1 check updated | NO |
| 22 | MED | ACCEPTED (modified remedy, §4) | PS §6.3 = exactly the 15 DEFERRED keys; register forbids flattening | MM §1 + row 99: residual carried **inside `WORK-13-FIXTURES`'s row** (named, with UD-2 reopen); PS WORK-13 row states it explicitly. No 16th §6.3 row — see §4 | NO |
| 23 | MED | ACCEPTED | Register `:6647` folds WORK-43's count into W-18; W-13 claimed it | MM W-13: routing override declared, at-least-four figure carried | NO |
| 24 | MED | ACCEPTED | Register `:6620-6623` and `:2944-2947` place both items in the residual-risk set; zero proposal hits | MM W-22 + rows 163/64: interstitial bypass + shared anonymous bucket land in the launch-readiness accepted-residual-risk set (minors-primary rationale carried) | NO |
| 25 | MED | ACCEPTED | AM §5 contained no criterion-1 reading rule (grep) | AM **§5.8** (gate verdicts quoted with the reading; TEST-01; UD-10 x-ref); MM row 91 retargeted | NO |
| 26 | MED | ACCEPTED | Register `:3618` "Do not flatten the two scopes"; LB evidence: fix applied+live | PS WORK-13 row rewritten (single-spec resolved on the SHA; 17-spec scope open; do-not-rerun) | NO |
| 27 | MED | ACCEPTED | `DEPLOYED_INFRA_STATE_EVIDENCE.md:603` (WORK-03 forbidden read; proxy circumstantial) | PS §3 "absent **by inference**… (`DB-CONTENT-VERIFY`, §6.2)" | NO |
| 28 | MED | ACCEPTED | `REMEDIATION_D310_ROTATION.md:44-46` (PutSecretValue = 2) | PS §9 rebuilt (RF-45) with correct CloudTrail wording, then detail single-homed out entirely; MM §2.G.3 states "zero Update/Delete/Restore; PutSecretValue = exactly 2 (creation writes)" | NO |
| 29 | MED | ACCEPTED | `REPOSITORY_DRIFT_REGISTER.md:686` (2 of 3 built, code-verified at HEAD); `formatDateLabel` names no symbol | PS WORK-40 row rewritten (2 confirmed built; third is not a build item; phantom symbol qualified) | NO |
| 30 | MED | ACCEPTED | Flag audit: 10 flagged; W-25/W-29 doc-only in register; W-04/W-40/W-42 name code targets | MM §4 intro → **thirteen** rows (list corrected both directions); inline flags added to W-04/W-40/W-42 | NO |
| 31 | MED | ACCEPTED | Appendix A: 16 entries → UD-1…10 + UD-12(a–f) = 11 ids; UD-11 from BLOCKED row 11 | MM §1, §5.2, A.11 §5 row: "11 carrying UD ids; UD-11 sourced from BLOCKED `LANGSMITH-RETENTION`" | NO |
| 32 | MED | ACCEPTED | Register `:4525` topic key `R7.2`; queue `:681/:748` bare `REQ-27` vs register's explicit disambiguation `:123-125` | MM step 9c extended to three corrections (queue key; register topic-key normalization; both `REQ-27` qualifications) + step 9d (markup deletion). Applied to the **moved copies at migration** — artifacts untouched now (§5) | NO |
| 33 | MED | ACCEPTED | Queue `:981` ("MUST be re-presented … launch-blocking at that point"); zero proposal hits | PS `R8-READ-SCOPE` reopen cell carries the duty verbatim; MM §5.4 check extended | NO |
| 34 | MED | ACCEPTED | `S42_ORG_ASKS.md:386-389` (A due before S43 opens; B before S48; no 08-02 date there) | MM §2.F.5 + DM §8.4: stamp reads "pending, re-arms at integration reopen", never "expired"; C's as-written release condition and D's withdrawal preserved | NO |
| 35 | MED | ACCEPTED | grep PS: both RESOLVED items 0 hits (row-less by design); step 6 said "stop" | DM §8.1 + MM step-6 gate: disposition-aware test (row **iff** open disposition; two RESOLVED items named as expected row-less) | NO |
| 36 | MED | ACCEPTED | Register §11(g) `:7076-7089` maps 7 live items; gate named 2 | MM §2.F.3 + step-6 row: the seven-item §11(g) subset, cited as authority | NO |
| 37 | MED | ACCEPTED | Drift register in-entry field below `:152` addendum still says "live and `AWSCURRENT`" | MM §2.G.2 third trap + DM §9.1: in-entry field annotated too; resolution stamp = entry's last line | NO |
| 38 | MED | ACCEPTED | Citation counts (DECISIONS 18+32, ARCH/TRACE/CLAUDE) — path changes break them regardless of rename | MM step **9a(ii)** (repath all inbound refs; mid-file-landing hazard accepted and recorded); DM §8.2 rationale restated on citation-**text** stability | NO |
| 39 | MED | ACCEPTED | `SPEC.md:3163-3187` still prescribes the split; `TRACEABILITY.md:612` §5.33 row section-granular | MM step 2 **Destination C** (TRACEABILITY sub-row: deferred — not traced, keyed `ARCH-21-SCHEMA-SPLIT`); HC-2 + §2.F.4 + DM §8.3 softened to "only record that it is **unmade**" | NO |
| 40 | MED | ACCEPTED | O20/§10.4 require results **recorded**; step 15 said run-then-move; 2 files banner-less | MM step 15: outcomes recorded inline with date+runner; failure blocks archival; §15.1 banner on both instruments; `git mv` | NO |
| 41 | MED | ACCEPTED | §15.4 freeze vs 9 rows editing archive/ post-step-9 vs W-04's quarantine | MM §0.2 **rule 11** (archive edits only at step 7); 7d executes the archive-halves of W-10/11/12/13/14/18/19/44 | NO |
| 42 | MED | ACCEPTED | 4 CLAUDE.md obligations (W-07/W-21/W-24/W-42) absent from step 14's list | MM step 14 extended (HINT description; hierarchy statement; "spec wins" → granularity rule; rule-1 wording) + closing grep check; HC-7 lists step 0a | NO |
| 43 | MED | ACCEPTED | AM §5.4 enum ≠ W-16's declared vocabulary; `reversed` undefined; AM header forbids minting conventions | AM §5.4 + §2.3: declared vocabulary (`proposed`/`accepted`/`superseded-by D-xxx`); extensions need a recorded DECISIONS entry — none minted | NO |
| 44 | MED | ACCEPTED | Banner counts stated 2/4/5; new file (imperative frozen-work specs) had per-block lines only; §15.1's own mid-file argument | MM §2.C.4 + step 3 + DM §6.2/§11: **line-1 D-152 banner above the H1** required; counts reconciled at 5 (DM §14 total + O11 enumeration; template phrase generalized) | NO |
| 45 | MED | ACCEPTED (modified remedy, §4) | Register `D310-ROTATION` = `PROJECT_STATE? no`; PS §10 forbids chronology; MM §2.G.3 prescribed the narrative; AM §5.7 requires quoted-not-paraphrased | PS §9 **kept as a section number but reduced to the quoted standing framing + pointers** (no timeline narrative; detail single-homed in the archived record + register); accepted no-rotation-mechanism residual moved into §4.3 `D310-RESIDUALS` (d); MM §2.G.3(a) + §5.6 updated to match | NO |
| 46 | MED | ACCEPTED | RD-01 in 8 locations/6 sections; 5 closures are semantic reversals | PS §10 **fan-out check** bullet (multi-section keys: reversed, not deleted) | NO |
| 47 | MED | ACCEPTED (modified remedy, §4) | §4.3 duplicates register mechanism (verbatim-compared); staleness rule named §3/§8 only; §5/§7 had no update owner; MM §5.3 sanctions §4.3's purpose | PS: staleness extended to §4.3; update protocol → §3–§8; "§7 closed by reading" rule; register-wins subordination sentence; both `file:line` cites symbol-qualified with as-of. **51→14 compression NOT applied** — see §4 | NO |
| 48 | MED | ACCEPTED | Register ARCH-34: families' latest `:151`/`:149` byte-identical; "that distinction is the finding" | PS §1 row: "one behind each family's latest, byte-identical no-ops; compare images, not revision numbers" | NO |
| 49 | MED | ACCEPTED | PS header declares post-migration paths; `FINAL_ARCHITECTURE.md:179-180` will not exist | PS §6.3 ARCH-21 row: post-migration archive name + "SPEC §5.33.3 still prescribes"; extraction-precedes-archival kept | NO |
| 50 | MED | ACCEPTED | Re-entry protocol at `S42_OPEN_QUESTIONS.md:112`; §6.1 had zero links | PS §6.1: re-entry-sequence link bullet ("do not improvise one") | NO |
| 51 | MED | ACCEPTED | Register `DIFFICULTY-TIERS-CONFLICT` ("both sides are explicit user decisions… ranking rule powerless") | AM §4.2 **precondition** (both-user-decisions → §4.6; UD-12(a) example) | NO |
| 52 | MED | ACCEPTED | W-39's §5.8.5/D-226 precedent; no protocol existed | AM §2.2 third obligation + **§4.8** (row reverts to not-traced; never silently deleted) | NO |
| 53 | MED | ACCEPTED | §5.9 was 15 authored rows; 5 corpus invariants absent (all verified surviving) | MM §5.9: generator sentence + 5 rows added (§5.1.3, §5.1.5, §5.15.2, §5.29 VLM, D-333 gate) | NO |
| 54 | MED | ACCEPTED | `SPEC.md:1581-1590` pre-D-333 windows; §5.15.2 on no amendment list | MM W-15 departure list + AM §4.1 live examples gain §5.15.2 (D-333: 30/90/180 + chat-checkpoint clock). PS §8 drift row deliberately **not** added — §8's own rule routes documentation drift to the register/worklist; W-15 is that worklist row | NO |
| 55 | MED | ACCEPTED | 3 rows × 2 steps edited rule 8 with no owner; deletion rule also at §5.15.2/§5.29 | MM W-30 = sole owner with final wording ("requirement unchanged… binds any future implementation"); W-15/W-42 cross-reference; §5.9 lists the extra homes with **do not mark parked** | NO |
| 56 | MED | ACCEPTED | Register `:318`/`:325` re-read (no retention job covers `__resume__`; green tests not coverage) | PS §4.3 SEC-13 tail: both clauses (durable leak → `RETENTION-CLUSTER`/UD-7; green-tests caveat) | NO |
| 57 | LOW | ACCEPTED | Cell-level checks per review | MM Appendix rows 40/153/88/16/158/131 amended; PS §4.3 preamble carries the code-reading-only sentence | NO |
| 58 | LOW | ACCEPTED | Evidence per review (same-AZ, 08-16/17, flap cycles, pre-D-377, COST-25 attribution, §7 count) | PS §8 five precision fixes + §7 heading count; MM A.11 §7 bridge; DM §10.1 "four + half" | NO |
| 59 | LOW | ACCEPTED | Structure items per review | PS: §3 ten-commit clause; §10 enum link; LB-08 why-clause; anchors note; BATCH-LOW depth; Blocks?-cells + sub-question re-home rule; §3/§8 sanctioned-carry rewordings; WORK-40-TZ shared prerequisite; TEST-05 criterion-1 clause | NO |
| 60 | LOW | ACCEPTED | Queue accounting `:998-999` (two labelled sub-questions); §12.3 crosswalk; E-5 `:973`; trailing markup `:1005-1006` | PS: four-items paragraph reworded + §12.3 cited; UD-12 six questions written out; WORK-01 acknowledgement clause; §7 DRIFT-49 note; UD-4 hold reworded (terraform mention dropped — documentation-only hold). MM step 9d deletes the queue markup **on the moved copy** | NO |
| 61 | LOW | ACCEPTED | Rotation record `:44-46`, `:117-118` | MM §2.G.3: PutSecretValue enumeration; fourth self-neutralising residual; DM §9.2 carve-out | NO |
| 62 | LOW | ACCEPTED | Instruction-hygiene items per review | MM: W-28 D-419 clauses → W-04 (counts fixed); step-9 create-clause removed; A.11 §7 bridge; "staging numbers" line → W-04; INTEGRATION_PLAN §5 dual pointer; HC-6 narrowed; CLAUDE.md vintage consolidated at 14; enrollment pointer single-owned by W-34 (W-39 cross-refs); DM O15 non-conflict sentence | NO |
| 63 | LOW | ACCEPTED | Register-fidelity items per review; W-13 phantom cell confirmed (no "commits ahead" in CLAIM_LEDGER) | PS: COST-06 D-342 parking; DRIFT-70 reword; D356 third action; DRIFT-91 factory half. MM: row 47 method-rule note; W-13 retargeted (provenance recorded, nothing edited in the ledger); W-18 twelfth item. DM §8.1 false-uniqueness struck | NO |
| 64 | LOW | ACCEPTED | AM §4.3 direction gap; W-44 framing-vs-reporting; branding leftovers re-read in plan | AM §4.3 either-direction detect + §2.9 symmetric caution; MM W-44 split (reframing rides W-15 sign-off + DECISIONS entry; reporting is doc-only); DM §6.3 gains the SVG org ask + source-of-truth rule | NO |

---

## 3. Rejected / needs-verification findings

**None.** Every finding survived independent re-verification. The six cases where the *remedy* was
changed are ACCEPTED findings with modified corrections (§4) — the defect was real in each.

---

## 4. Accepted with modified remedy — six findings, with reasoning

1. **RF-11 (child-safety visibility).** The reviewer's suggested new `PS §4.2` row was **not**
   added: it would mint a register-keyless engineering row (breaking the key discipline the file
   enforces) and would effectively pre-answer UD-9's option D by scheduling work the user has not
   ordered. Visibility is achieved instead by the §8 headline bullet plus the UD-9 hold text naming
   the three unowned deliverables. Nothing is hidden; nothing is decided.
2. **RF-22 (DRIFT-58 residual).** No 16th §6.3 row: §6.3 mirrors the register's 15 DEFERRED
   entries, and adding a non-entry row would break the section↔disposition symmetry that Phase-6
   itself verified as a strength. The residual is carried, named, inside `WORK-13-FIXTURES`'s row
   with its UD-2 reopen condition — the register's do-not-flatten instruction is satisfied by
   stating both scopes explicitly.
3. **RF-45 (PROJECT_STATE §9).** Resolved from the accepted documentation model rather than
   escalated: the register's `PROJECT_STATE? no`, the file's own no-chronology rule, and AM §5.7's
   quoted-not-paraphrased rule all point the same way, so the manifest's narrative prescription was
   the outlier and was corrected. §9 keeps its **section number** (dozens of "PS §9" cross-references
   survive) but is now the quoted standing framing with pointers — no timeline, no probe matrix,
   no CloudTrail detail (single-homed in the archived record and register entry).
4. **RF-47 (§4.3 scale).** The refresh-rule and citation corrections were applied in full. The
   51→14-line compression was **not**: MM §5.3 sanctions §4.3's act-on-alone purpose, and the five
   mechanisms were verified accurate. The second-lifecycle risk is closed a different way — a
   standing subordination rule ("if §4.3 and the register disagree, the register wins; rows are
   re-derived, never patched") plus the staleness-rule extension. Compression remains available as a
   post-migration editorial option; it is not required for safety.
5. **RF-54 (§5.15.2 SPEC drift).** W-15 and AM §4.1 gained the retention-windows entry as
   specified, but the suggested `PS §8` drift row was not added — §8's own closing rule routes
   documentation-layer drift to the register/worklist rather than into §8, and W-15 *is* that
   worklist row. Adding the §8 row would have re-created the routing self-contradiction RF-59g
   removed.
6. **RF-60f (DRIFT-49 queueing).** No UD-12(g) was minted — creating a new user-decision entry
   would alter Phase-4 queue semantics from Phase 7. The §7 row now states explicitly that the
   ask-the-user half is deliberately unqueued (it fires only if DECISIONS/git evidence fails) and
   that the placeholder-default fix needs no decision.

---

## 5. Upstream factual errors — recorded here, evidence artifacts left untouched

Per the Phase-7 correction principle, the proposal now represents the corrected reality; the
Phase-4/-6 artifacts are **not** rewritten. Errors discovered:

1. **`FINAL_OPEN_WORK_REGISTER.md` `SEC-13-PURGE` + `LOCAL_EXECUTION_FINDINGS.md:534-536` (F-11):**
   "no `tests/` path at all … a refactor deleting that line would break no test" is **false at
   HEAD** — `apps/chat-api/tests/test_chat_endpoints.py:503-506` and `:560-562` assert the purge's
   effect on the success path (with a vacuity control). The defect itself (cancel/exception paths
   untested, leak durable) is real and unchanged. The proposal states the corrected coverage.
2. **`CLAIM_LEDGER.md` WORK-05:** contains **no** "2 commits ahead" cell; the figure was already
   corrected at `LIVE_BEHAVIOR_FINDINGS.md:506` (HEAD is 1 ahead). W-13 now records provenance
   instead of instructing an impossible edit.
3. **`USER_DECISION_QUEUE.md`:** three defects — `:935` cites `RISK-R7.2` (no such register key);
   UD-10's bare `REQ-27` conflates two entries with different dispositions; the file ends in two
   lines of tool-call markup. All three are fixed **on the moved copies at migration** (steps
   9c/9d), never on the Phase-4 artifact.
4. **`FINAL_OPEN_WORK_REGISTER.md:4525`:** `COMMITTED-ORG-DRAFTS`' own topic-key field reads
   `R7.2`; normalized on the moved copy at step 9c.
5. **`ALERT-ENDPOINT` register entry:** internally ambiguous on whether "26 of 34" is a live or
   pre-D-377 count; the proposal carries the caveat and flags the ambiguity rather than resolving it.
6. **A3 inventory 16-vs-15 file count** — already recorded in DM §1; unchanged.
7. **Phase-6 review's own remedy errors** (the six §4 items) — recorded here as the review's
   errata; ADVERSARIAL_REVIEW.md is left as filed.

---

## 6. The four Phase-5 design questions — adjudication

| # | Question | Category | Outcome |
|---|---|---|---|
| DQ-1 | **Post-PROGRESS session-narrative location** (git commit messages only, or an append-only non-authoritative `docs/log/`) — and the matching `/end-session` skill reconciliation | **GENUINELY USER_DECISION_REQUIRED** | **Surfaced — the one question the user must answer before executing the migration.** The accepted model settles only the negative half (no chronology in PROJECT_STATE); it cannot choose between commits-only and a journal, and the choice rewrites the user's own session ritual. PS §10 is marked provisional; MM §2.F.2 + the closing note carry the question; step 15b reconciles the skill once answered. |
| DQ-2 | ROADMAP/PROGRESS split shape (W-23 "ratify with the user") | Resolvable from the accepted model | The split's shape is fully specified by DOCUMENT_MODEL §6.2/§8.1 as corrected; "ratification" collapses into the single existing gate the manifest already requires — **user approval of the target tree before execution**. Not a separate question. |
| DQ-3 | DECISIONS status-tag cleanup scope | Safely deferrable | The Phase-4 safe default stands (8 worst entries + forward convention; the ~120-chain sweep deliberately deferred), and the residual risk is now visible in the active tier (PS §8 bullet; AM §3.1-2a). Nothing forces a scope decision at migration time. |
| DQ-4 | CLAUDE.md rewrite approval | Mechanical, with named sign-off points | The rewrite content is fully specified (step 14 + W-30's exact rule-1/rule-8 wordings). The two safety-rule wordings, the "spec wins" rewording, and W-44's egress reframing are **migration-time sign-off points** listed in W-15 — presented to the user during execution, not a blocking pre-decision. |

**Also confirmed NOT silently answered:** all 12 UD queue entries survive as open questions with
register keys; the six answer-shaped defaults are now `[USER ONLY — hold:]`; AM §4.2's new
precondition closes the UD-12(a) inference path; UD-12(f) is untouched by the gitignore fix.

---

## 7. Post-correction consistency pass — 15 points

An independent verifier read all four corrected files in full and ran the checklist; 14/15 passed
outright. The single FAIL (point 1: W-38 still scheduled at step 11 in three places) and all eleven
listed residuals were then corrected and re-verified by sweep (all pre-correction phrases now return
zero hits):

1. **RF-01 ordering executable — PASS** (after W-38 closure). Phase 0 → 15 DAG satisfies O1–O20 and
   HC-0–HC-8; step-11 split-row list now matches every W-row cell (W-38 wholly at 0c/14; W-29
   send-status at 7e; W-19/23/26/28 halves labelled; W-27 at 7/14); rule 1, rule 10 and the Phase-2
   header carry the Phase-0 carve-outs; the clean-tree commit precedes step 0a.
2. **RF-02 — PASS.** Zero extraction claims for nonexistent criteria; five embedded constraints at
   all five required sites; freeze semantics preserved.
3. **No step answers a user decision — PASS.** 6 `[agent may apply]` + 6 `[USER ONLY — hold:]`;
   HC-0 intact; AM §4.2/§4.6 intact; DQ-1 surfaced, not decided.
4. **All 166 entries route — PASS.** Appendix A rows 1–166 gap-free; disposition tallies match §1
   and §12.1; A.11 closes with the §7 bridge.
5. **All 12 UDs discoverable and unanswered — PASS.** Register-key column populated; UD-12's six
   questions written out; no row states an answer.
6. **No safety/privacy/HITL invariant weakened — PASS.** §5.9 generator + 5 added rows; rule-1
   exact wording (student/parent/guardian, two tables, fails loudly); rule-8 sole-owner wording;
   incident-response line scoped the right way (and DM §7.1's stale framing rewritten).
7. **D-333 survives — PASS** (verbatim in PS UD-7; WORK-23; MM §2.B.4/§5.9/W-15).
8. **D-152 survives — PASS** (§6.1 + re-entry link; rule 5/HC-0; three line-1 freeze-banner sites).
9. **D-310 resolved-historical — PASS** (quoted framing only; residuals (a)–(d); "unmeasured, not
   cleared" ×4; no active-exposure text).
10. **LB-05 survives — PASS** (both SHAs + 10 commits ×2; §3 conditional; deployed-image staleness
    trigger in PS §1 and AM §2.1).
11. **Extractions precede archival — PASS** (HC-1; 7e before 9; O2/O5/O13 satisfied).
12. **Ignored/tracked behavior explicit — PASS** (both files: `.gitignore:67` repath, stays
    untracked, UD-12(f) untouched).
13. **Superseded facts not promoted — PASS** (BD3 from D-067/tokens.css; `#d13a80` only with its
    superseded label; 49/18 everywhere; zero hits for the old counts).
14. **PROJECT_STATE stays snapshot/navigation — PASS** (§9 non-narrative; fan-out check;
    provisional narration note; update protocol §3–§8; all section counts match headings).
15. **Every blocking finding corrected or justified — PASS.** All 47 blocking findings corrected;
    zero remain blocking. Twelve-phrase stale-text sweep: zero hits.

Minor cross-file notes closed in the same pass: PS §9's CloudTrail restatement single-homed out;
AM's "terminal state" wording for `UNKNOWN` aligned with the open/terminal split PS §10 uses;
DM §8.1 names step 0a.

---

## 8. Migration readiness

### **MIGRATION_READY**

- Every CRITICAL finding: resolved (2/2).
- Every HIGH finding: resolved (17/17); none rejected.
- No unresolved safety-related MEDIUM remains (all 37 MEDIUM resolved; the six modified remedies
  are visibility-preserving, not weakening).
- No migration-blocking NEEDS_VERIFICATION exists (none was raised).
- All genuine user decisions are surfaced rather than guessed.

**Execution still requires, from the user, before or during the migration (surfaced, not guessed):**

1. **DQ-1 (blocking, pre-execution):** after `PROGRESS.md` archives, does per-session narration go
   to **git commit messages only**, or to an **append-only, non-authoritative `docs/log/`**? The
   `/end-session` skill must be reconciled to the answer either way (manifest step 15b).
2. **Approval of the corrected target tree** (DOCUMENT_MODEL §4/§16) — the manifest's own standing
   gate for execution.
3. **Migration-time sign-off points** (during execution, listed in W-15): DRIFT-15's two unbuilt
   §5.29 mechanisms; REQ-49's unbuilt mechanisms; DRIFT-16's reading question; W-44's zero-egress
   reframing (with its DECISIONS entry); the two CLAUDE.md safety-rule wordings (rules 1 and 8).
4. The **12 UD queue entries remain open** and none blocks the migration itself (UD-1 partially
   blocks *live verification of B4*, not the documentation migration).

The migration does **not** begin as part of this phase.
