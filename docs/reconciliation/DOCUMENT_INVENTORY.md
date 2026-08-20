# Document Inventory — Documentation Reconciliation Audit

**Date:** 2026-08-19
**Scope:** the project `CLAUDE.md` plus every meaningful document under `docs/` — 26 documents, ~68,000 lines.
**Method:** every document was read in full. The two logs too large for one reading context
(`DECISIONS.md`, 28,787 lines; `PROGRESS.md`, 16,690 lines) were partitioned at heading boundaries
into 7 and 4 chunks respectively, each read line-by-line by a dedicated reader with ~30-line
overlaps at every seam; the coverage ledger below confirms 100% line coverage of both. All flagged
ambiguities (phantom decision IDs, stale headings, duplicate headings) were re-read directly and
verified against the source before being recorded here.
**This is an audit, not a rewrite.** No source file or existing document was modified. Companion
deliverable: [DOCUMENTATION_RISK_REGISTER.md](DOCUMENTATION_RISK_REGISTER.md).

**Field definitions.** *Type* uses the requested vocabulary: normative / decision / current-state /
planning / historical / audit / operational / reference. *Authority* is the document's likely
standing as a source of truth, judged from how it presents itself, what defers to it, and what it
defers to. *Candidate future role* is active / reference / archive / unknown — a recommendation
for the future reconciliation step, not an action taken here.

---

## Summary table

| # | Document | Lines | Dominant type | Stale risk | Contradiction risk | Candidate role |
|---|---|---|---|---|---|---|
| 1 | CLAUDE.md (project) | 118 | normative + reference index | MED-HIGH | MED-HIGH | active (top reconcile priority) |
| 2 | docs/SPEC.md | 4,210 | normative (+§6 planning) | HIGH | HIGH | active, needs amendment discipline |
| 3 | docs/ROADMAP.md | 3,328 | planning + historical | HIGH | HIGH | split: reference + archive |
| 4 | docs/PROGRESS.md | 16,690 | current-state + historical log | HIGH (by design) | HIGH | active (current status) + archive (log) |
| 5 | docs/DECISIONS.md | 28,787 | decision log | MED (bodies), HIGH (headings) | HIGH | active |
| 6 | docs/ARCHITECTURE.md | 2,180 | current-state + normative | MED | MED-HIGH | active (as-built authority) |
| 7 | docs/FINAL_ARCHITECTURE.md | 185 | planning (projection) | HIGH | HIGH | archive (after 2 extractions) |
| 8 | docs/INTEGRATION_PLAN.md | 626 | planning + normative + reference | HIGH | HIGH | active only with freeze banner |
| 9 | docs/AUDIT_FINDINGS.md | 5,822 | audit register | HIGH | HIGH | reference (frozen register) |
| 10 | docs/AUDIT_2026_08_16.md | 300 | audit | MED-HIGH | MED | reference |
| 11 | docs/AUDIT_LIVE_2026_08_17.md | 142 | audit + reference | MED | LOW-MED | reference |
| 12 | docs/TRACEABILITY.md | 791 | audit/evidence + reference | MED | LOW-MED | active |
| 13 | docs/OPEN_DECISIONS.md | 636 | decision (closed) + historical | LOW-MED (content), HIGH (name) | MED | reference, misleadingly named |
| 14 | docs/INCIDENT_RESPONSE.md | 310 | operational/normative runbook | MED | LOW-MED | active |
| 15 | docs/QUESTION_GENERATION.md | 450 | current-state + normative | MED-HIGH | MED-HIGH | active |
| 16 | docs/HINT_SOLUTION_REVIEW.md | 541 | planning + normative + audit | HIGH | HIGH | active, needs reconciliation first |
| 17 | docs/U7_CHECKPOINT_CONSOLIDATION.md | 297 | audit/measurement + decision-request | HIGH | MED-HIGH | reference + archive; mis-shelved |
| 18 | docs/CONTENT_COVERAGE.md | 180 | reference + current-state snapshot | HIGH | MED-HIGH | reference with as-of banner |
| 19 | docs/ENROLLMENT_FAQ_APPROVAL.md | 94 | operational (outbound draft) | LOW-MED | LOW | active until org answers |
| 20 | docs/FIRST_VISIT_NOTICE.md | 237 | normative + reference + audit | MED | LOW-MED | active (unconsumed S45 input) |
| 21 | docs/S42_DISCOVERY.md | 342 | current-state + audit + planning | HIGH (§7-§9) | HIGH | reference (§0-§6) + archive (§7-§9) |
| 22 | docs/S42_OPEN_QUESTIONS.md | 121 | planning (frozen) + decision | MED | MED | active (frozen by design) |
| 23 | docs/S42_ORG_ASKS.md | 406 | operational (outbound drafts) | HIGH (highest of S42 set) | HIGH | archive, preserve message text |
| 24 | docs/S42_SECURITY_REPORT.md | 170 | operational (outbound draft) | LOW-MED | LOW | active (survives the freeze) |
| 25 | docs/plans/2026-07-18-expansion-plan.md | 958 | planning (executed) + historical | HIGH | HIGH | archive with superseded header |
| 26 | docs/plans/2026-07-19-branding-plan.md | 164 | planning (executed) + reference data | HIGH (status), LOW (data) | HIGH (status) | archive plan, promote brand data |

---

## 1. CLAUDE.md (project root, 118 lines)

- **Purpose.** The always-loaded instruction file: product summary, the document-reading index
  ("read these instead of holding the spec in your head"), the production-system rules and
  credential prohibitions, the D-152 integration freeze, session workflow, stack, ten condensed
  non-negotiable rules, and conventions.
- **Type.** Normative (rules) + reference (doc index, stack) + operational (workflow, freeze).
- **Temporal scope.** Continuously maintained present tense; **no date or version marker
  anywhere**. Known to have drifted before: rule 1 said "MongoDB" for many sessions until the
  D-082/D-111 sweep corrected it (DECISIONS.md:5169).
- **Information it owns.** The doc-reading index with per-doc guidance; the two hard credential
  rules and the production-freeze rule (L47–52); the D-152 do/don't list (L54–72); the one
  production fact product work must honor now (`signups.attended = null` is routine, L70–72); the
  ten condensed rules (L86–109); conventions (L111–118).
- **Likely authority.** Highest *procedural* authority — auto-loaded, governs every session — but
  self-subordinating on content ("condensed from SPEC.md — the spec wins on detail", L86). Nothing
  references CLAUDE.md back, so drift here is unpoliced. Its index is the only mechanism by which
  a document becomes discoverable at session start; omission is de-facto invisibility.
- **Overlap.** Rules 1–10 are a lossy compression of SPEC §5.x; doc descriptions duplicate (and
  drift from) the described docs' own headers; the freeze section overlaps
  S42_OPEN_QUESTIONS.md / INTEGRATION_PLAN.md / ROADMAP.md's freeze text.
- **Stale risk — MEDIUM-HIGH**, concentrated in the doc *descriptions*: L38–40 describes
  OPEN_DECISIONS.md as "everything still open … ten decisions" while that file has 14 items and
  declares "Nothing in this file is awaiting a decision" (OPEN_DECISIONS.md:8); L13 calls SPEC.md
  "~2,600 lines" (it is 4,210); L29 calls HINT_SOLUTION_REVIEW.md "the **planned** design" though
  the panel/repair/loop modules exist.
- **Contradiction risk — MEDIUM-HIGH.** Direct contradiction with OPEN_DECISIONS.md:3/8 on whether
  anything awaits a decision; rule 8 (solution images deleted immediately) guards a feature that
  does not exist (D-078; FIRST_VISIT_NOTICE.md:122–123 is the only doc that explains this).
- **Index coverage fact (verified):** the Documents section names 11 files; **13 existing docs are
  omitted** (ARCHITECTURE, FINAL_ARCHITECTURE, INTEGRATION_PLAN, AUDIT_FINDINGS, AUDIT_2026_08_16,
  CONTENT_COVERAGE, ENROLLMENT_FAQ_APPROVAL, FIRST_VISIT_NOTICE, S42_ORG_ASKS,
  S42_SECURITY_REPORT, U7_CHECKPOINT_CONSOLIDATION, and both docs/plans/ files;
  S42_OPEN_QUESTIONS.md is mentioned only outside the index, at L62).
- **Candidate future role — ACTIVE**, and the highest-priority file to reconcile: fix the stale
  descriptions, decide explicitly which docs are unlisted and why, add a last-reviewed marker.

## 2. docs/SPEC.md (4,210 lines)

- **Purpose.** The full product/technical specification for both apps: legal/consent, DB ownership
  split, both LangGraph workflows, question pipeline rules, assessment math, RAG, MCP flows,
  Bedrock rules, failure matrix, PII/security, evaluation, observability, AWS deployment, plus a
  24-phase implementation sequence (§6).
- **Type.** ~95% normative (§5.0–§5.36); §6 is planning (explicitly demoted by TRACEABILITY.md to
  "implementation plans, not requirements"); small decision-record fragments embedded at
  §5.19.4/§5.19.5 (D-351) and §5.35 (D-092); reference tables (§5.29, §5.35, §5.36).
- **Temporal scope.** **No version header, no date, no changelog.** Exactly two in-text amendment
  markers in 4,210 lines ("Amended 2026-08-15 (D-351)" at L1973; a D-092 note at L3403). The
  D-111 MySQL sweep rewrote ~40 lines and four headings with *no* in-text marker. The file opens
  at "# 5. Very Detailed Version" — §1–§4 of the parent document are absent.
- **Information it owns.** The requirement baseline nowhere else in full: token claim set, the
  eleven first-visit disclosures, curriculum band tables, the 11 §5.8.5 validation checks,
  difficulty weights and gain formula, retention numbers, verbatim user-facing strings, the
  §5.19.5 TurnReason table, the §5.29 failure matrix, the §5.30.1 Bedrock wire allowlist, the
  accounts/secrets inventory, the §5.33.4 SLO targets.
- **Likely authority.** High for detail, low for currency — and it never says so itself. It
  contains no authority statement and **never references any other repo document by filename**
  (zero mentions of DECISIONS/ROADMAP/ARCHITECTURE in 4,210 lines); coupling is only via four
  decision-ID mentions. CLAUDE.md's "the spec wins on detail" is accurate about granularity but
  unsafe as a conflict-resolution rule: for §5.8.1, §5.11.2, §5.13.2, §5.28.2, §5.33, DECISIONS.md
  wins and the spec still reads as if it doesn't.
- **Overlap.** CLAUDE.md rules (deliberate compression); ARCHITECTURE.md (as-built complement);
  TRACEABILITY.md (indexes all 37 §5 sections); FINAL_ARCHITECTURE.md (contradicts §5.33–§5.34);
  ROADMAP.md (restates §6); DECISIONS.md (~220 SPEC references — effectively its amendment layer).
- **Stale risk — HIGH.** Amendments live almost entirely outside the file. Requirements that still
  read as live but were decided otherwise include: 100 templates/topic (§5.8.1 + §6.6, vs D-223's
  ~25–35), EKS/Karpenter/Aurora topology (§5.33, vs D-004's ECS/RDS), four dedicated chat
  endpoints (§5.28.2, vs D-044), whole §5.17 multimodal pipeline (deferred, D-078, unmarked),
  §5.2.2's live-looking auth-option menu (frozen by D-152), §5.32.1's "choose one" observability
  fork (decided, D-214/D-242), §5.15.4's Sunday EventBridge job (manual per ARCHITECTURE.md).
- **Contradiction risk — HIGH** — cross-document, load-bearing because CLAUDE.md tells sessions
  the spec wins: deployment topology vs FINAL_ARCHITECTURE/ARCHITECTURE; question volume vs
  ROADMAP/CONTENT_COVERAGE; post-exam variant reuse (§5.13.2 vs ROADMAP:1664); grade bands
  (12 declared vs 7 populated).
- **Candidate future role — ACTIVE**, with a mandatory amendment discipline (the D-351 pattern —
  amend in place with a dated marker — needs to become the rule), and §6 demoted to historical.

## 3. docs/ROADMAP.md (3,328 lines)

- **Purpose.** The session-by-session build plan: ~100 numbered work units (S0–S51, S22.5, C1,
  U0–U7, V1–V11, W1–W27 with no W13) across 16 milestones, each with Spec pointer, build list,
  and "Done when" criterion. In practice also the project's longest narrative record: "Actual
  scope"/"Outcome" blocks, a ~470-line gate-standings ledger, a content-track ledger, and three
  closed-milestone retrospectives.
- **Type.** Planning/normative (unbuilt sessions, "Done when" criteria) + historical/audit (the
  dominant mass) + decision-adjacent (carries D-152/D-341/D-342 instructions) + operational
  (runnable recount recipes).
- **Temporal scope.** 2026-07-13 → 2026-08-18; one renumbering event (D-049); milestones M0–M15;
  62 sessions marked ✅, 1 ⚠️, 18 headings unmarked (S1–S16, S19, S33) despite L2168–2169
  asserting all are done; S43–S47 frozen (D-152); S48–S51 untouched and carrying **no freeze
  annotation**.
- **Information it owns.** Per-session "Done when" acceptance criteria (its unique normative
  asset); the SPEC-section→session mapping; sequencing rationale and dependency spine;
  "decide at session start" gates; milestone scope for tracks with no other home (A6-C, C1).
- **Likely authority.** CLAUDE.md calls it "the source of truth for what to build next" — but the
  file's own L713–714 hands that role to PROGRESS.md's "Next session" pointer ("post-gate sessions
  run out of PROGRESS.md … rather than under a numbered block"), and then Milestones 10–15
  (L2216–3320) are numbered blocks anyway. Authoritative for "Done when" criteria and spec
  mapping; **not** authoritative for status, finding counts, or (post-gate) sequencing.
- **Overlap.** Heavy with PROGRESS.md (session outcomes, test counts), DECISIONS.md (the gate
  ledger is a D-number narrative), AUDIT_FINDINGS.md (counts, with a grep recipe it admits its own
  carried counts kept getting wrong), INTEGRATION_PLAN.md (gate criteria restated), OPEN_DECISIONS
  (#6–#14 dispositions).
- **Stale risk — HIGH.** Annotation-by-accretion: ~470 lines of superseded gate standings kept
  inline (five criterion-6 dates coexist); frozen S43–S47 still read as active build specs with
  the freeze stated only at L1440–1445; S29's deferral stated *after* its build spec; multi-tier
  and depth clauses carry three or four unreconciled numbers each; "the roadmap text was stale" is
  its own self-admission (L288).
- **Contradiction risk — HIGH.** L713–714 vs M10–M15's existence; L2168–2169 vs unmarked headings;
  the closing retrospective (L3322–3328) misattributes V1 to "V6–V11"; "Seven P1s remain" (L944)
  vs "criterion 2 is met" (L1343); D-418's phantom-blocker correction leaves earlier praise of the
  tfvars check standing.
- **Candidate future role — SPLIT: reference + archive.** The "Done when" criteria and spec
  mapping stay load-bearing reference; the gate ledger, C1/A6-C track logs, and M10–M15
  retrospectives are archive-shaped history that PROGRESS/DECISIONS already own.

## 4. docs/PROGRESS.md (16,690 lines)

- **Purpose.** "Current status, session log, carry-over items" (CLAUDE.md). Newest-first: a
  living "Current status" stack (L6–~1861), then the full historical session log back to S0
  (2026-07-13), ending (physically last) with a standalone 2026-08-07 carry-over note.
- **Type.** Current-state (top block, by intent) + historical log (the mass) + operational
  (carry-over lists, verification snapshots).
- **Temporal scope.** 2026-07-13 → 2026-08-18. The "Current status" block is itself a stratified
  stack of "Next session"/"Previous —"/"Earlier —" summaries reaching back through Milestone 10 —
  i.e. the *current* section contains ~1,800 lines of history. The boundary between current and
  log is informal (a `---` and "Prior state, still true" prose).
- **Information it owns.** The live "Next session" pointer (the project's actual sequencer
  post-gate, per ROADMAP:713–714); per-session verification transcripts and carry-over ledgers;
  the freshest open items (SNS PendingConfirmation, answer-cache decision, staging deploy gap);
  the standalone final carry-over (staging e2e isolation, 2026-08-07, explicitly "not a finished
  finding").
- **Likely authority.** High for current status by convention (ROADMAP defers to it; `/end-session`
  updates it) — but its own summary layer has been demonstrably wrong about its own log repeatedly:
  the carry-over list "has now been wrong six times this milestone" (L385–388, the file's own
  words); D-368 corrected PROGRESS's stale claim about D-364; D-386 corrected "a genuine HTTP 429
  has never rendered". The session log outranks the summaries; DECISIONS.md outranks both for
  decision content.
- **Overlap.** Near-total with DECISIONS.md (every session mirrors D-entries), heavy with ROADMAP
  (status), AUDIT_FINDINGS (finding status), OPEN_DECISIONS (#numbers).
- **Stale risk — HIGH by design** (append-only history with embedded present-tense claims):
  point-in-time numbers (video counts 4→72→102-of-112→497 across strata; ruff-format 116/415 →
  168/437) whose older values remain readable as current; "Superseded — pointer as of post-D-xxx"
  blocks stacked nine deep; duplicate session entries (a session appears once as a top teaser and
  once as the full log entry).
- **Contradiction risk — HIGH.** Documented self-contradictions: summary said "uncommitted" while
  the log said deployed (D-174 era); tfvars-rollback warning stated as fact across sessions then
  measured false (D-418); item counts (48 vs 41 approved items) corrected only by a later pointer.
  Duplicate verbatim `### S20` heading at L15451/15453 (verified). S32/S37/S40 were logged only in
  "Current status", never as session-log entries (L12553 — a self-flagged completeness gap).
- **Candidate future role — SPLIT: active (the "Current status"/"Next session" block, aggressively
  pruned) + archive (the session log, which is the project's history of record).**

## 5. docs/DECISIONS.md (28,787 lines, 443 D-entry headings)

- **Purpose.** "Lightweight ADRs. One entry per decision that a future session … might otherwise
  re-litigate" (L1–6). In practice the project's deepest record: decisions, measurements,
  corrections, incident narratives, and session results from D-001 (2026-07-13) to D-423
  (2026-08-18).
- **Type.** Decision log + audit/measurement record + historical narrative. Some entries are
  normative in effect (standing rules: expand/contract for NOT NULL, D-342's parking instruction).
- **Temporal scope.** 2026-07-13 → 2026-08-18, roughly chronological by creation with documented
  exceptions (D-013 after D-031; D-199 after D-201; D-217/218/219 in reverse order; D-351 after
  D-353 with an explanatory comment; D-099 interleaved mid-S36).
- **Information it owns.** The rationale layer for everything: supersession chains, correction
  trails, measured constants, incident post-mortems (D-084/D-085/D-310/D-400), user decisions with
  the options they rejected. It is the de-facto amendment layer for SPEC.md.
- **Likely authority.** The strongest content authority in the repo — other documents (PROGRESS,
  OPEN_DECISIONS, ROADMAP, audit docs) defer to it or get corrected against it. Direction of drift
  is consistently one-way: DECISIONS.md leads, mirrors lag.
- **Overlap.** Mirrored (lossily) by PROGRESS.md sessions; projected (curated) into
  ARCHITECTURE.md's invariants; outcome-duplicated in OPEN_DECISIONS.md and AUDIT_FINDINGS.md fix
  narratives; re-narrated in QUESTION_GENERATION/HINT_SOLUTION_REVIEW.
- **Stale risk — MEDIUM for bodies, HIGH for headings.** The declared status vocabulary
  (`proposed | accepted | superseded`, L4) is **never maintained**: entries later reversed,
  refuted, or corrected keep "(accepted)" in the heading (D-004, D-121, D-129 §5, D-135, D-344's
  "removed by D-349" clause standing beside its own correction "D-349 therefore removes nothing",
  L24671 vs L24705–24707 — verified). A scan by status alone misses every supersession; the truth
  lives only in body text and forward references.
- **Contradiction risk — HIGH**, but *documented*: the log's culture is to correct loudly in place
  (a strength) while never updating the corrected entry's heading (the risk). Verified anomalies:
  **phantom IDs** — D-190/D-191/D-192 "referenced everywhere, never written" (the log's own
  meta-note at L16101), **D-329** (referenced by D-330/D-334/D-335, exists only as a sub-heading
  inside D-330 at L23582), **D-363** (referenced 4× across both logs, never written anywhere);
  entries mutable after the fact (D-176 §4, D-110's embedded "D-207 update" block); heading format
  changes mid-file at D-274 (from `## D-xxx — title (status, date)` to `### D-xxx` + metadata
  lines, mostly without a status word); informal sub-entries (`D-195 §5`, "D-206 addendum",
  "D-210 disposition") that make ID-grep unreliable — a failure mode D-223 itself demonstrates.
- **Candidate future role — ACTIVE.** It is the system of record. The reconciliation opportunity
  is mechanical: status-tag hygiene, an ID index, and closure of the phantom-ID gap.

## 6. docs/ARCHITECTURE.md (2,180 lines)

- **Purpose.** The as-built map: what is/isn't built, ~70 cross-cutting invariants (each a defect
  post-mortem generalized to a rule, with D-number provenance), 10 mermaid flow diagrams, the
  storage-split table, and the network-egress/observability-sink section.
- **Type.** Current-state/reference (diagrams, tables) + normative-in-voice invariants sourced
  from decisions + small historical strata.
- **Temporal scope.** Living and actively maintained (last touched 2026-08-18; the `end-session`
  skill mandates updating it). Header scope sentence ("as built through S0–S34 plus …") is a
  rolling claim that already rotted once — the file itself narrates its 2026-07-30 rewrite after a
  stale "not yet built" list invalidated a gate criterion (L49–53).
- **Information it owns.** The only rendered dataflow diagrams; the measured capacity/pricing
  table with its extrapolation ban; the access-probe rule-history table; the storage-split table
  (per-table PII/retention/idempotency semantics); the egress/sink table ("LangSmith is the only
  egress that leaves AWS"); the two shipped plan-deviations (D-064, D-130).
- **Likely authority.** Presents itself as subordinate-but-canonical for as-built ("a map of what
  exists now … SPEC.md is the spec", L11–13). TRACEABILITY.md cites it as §5.3 evidence; the
  end-session skill mandates writing it. **CLAUDE.md's index omits it** — the file every session
  must *write* is not one any session is told to *read*. It never mentions FINAL_ARCHITECTURE.md
  or INTEGRATION_PLAN.md.
- **Overlap.** vs FINAL_ARCHITECTURE (which appends a row to *this* file's storage table); vs
  INTEGRATION_PLAN §7-R8/R9 (same accepted risks, two homes — and only INTEGRATION_PLAN carries
  the expiry conditions); vs SPEC (storage split, PII floor, refusal semantics); vs DECISIONS
  (largest-volume overlap: the invariants are a curated projection of it).
- **Stale risk — MEDIUM**, with three verified internal live/stale pairs: L24–36 says
  youtube-sync/memory-consolidate/chat-purge schedules are enabled and run unattended, while
  L1791, L1850–1851, and L2068 still describe the same jobs as "manual trigger this session /
  no scheduler yet"; L644 calls a fixed `/stream` issue "carry-over" (fixed per L289–297).
- **Contradiction risk — MEDIUM-HIGH.** Internal pairs above; refutes FINAL_ARCHITECTURE on
  SSE/replicas and INTEGRATION_PLAN §2.5's "still open" items; the deployed ECS/RDS reality never
  stated in one place, so the SPEC §5.33 contradiction is invisible from inside it.
- **Candidate future role — ACTIVE** (the single as-built authority). Needs: a CLAUDE.md index
  entry, and de-duplication of scheduling state so it lives once.

## 7. docs/FINAL_ARCHITECTURE.md (185 lines)

- **Purpose.** A projection (2026-07-21 vintage) of the system after the then-final sessions
  S32–S34, plus the five decisions S32 was expected to make and a target-topology diagram.
- **Type.** Planning/projection + decision-framing + one reference fragment; now effectively
  historical.
- **Temporal scope.** Self-dated snapshot ("treat every claim below as 'planned as of
  2026-07-21'"); patched once (D-082 MySQL note); last touched 2026-07-28 — *after* D-004 was
  accepted at S32 (2026-07-22), yet it still says the decision is unmade.
- **Information it owns.** The **only end-to-end deployed-topology diagram in the repo**
  (L46–105); the five S32 open questions as a set — of which **question 5 (SPEC §5.33.3's
  logical DB/schema split) appears to be the only one with no recorded closure anywhere**; its own
  retirement instruction (L183–185: fold back into ARCHITECTURE.md and delete "rather than letting
  the two drift apart" — the drift it warned about has happened).
- **Likely authority.** Self-demoting in text ("This is a projection, not an as-built record …
  not a source of truth the way ARCHITECTURE.md is", L3–6), maximally-claiming in filename.
  Inbound references: none functional — only as a MongoDB-cleanup target. Not in CLAUDE.md.
- **Overlap.** Duplicates ARCHITECTURE's built-state summary at lower fidelity; appends a row to
  ARCHITECTURE's storage table (one table, two owners); overlaps INTEGRATION_PLAN on integration
  shape and single-instance risk; contradicts SPEC §5.33 by proposing to defer it.
- **Stale risk — HIGH.** Nearly every status claim is false: "D-004 is still 'proposed'" (L110 —
  accepted 2026-07-22); "S33 … S34 — Status: not started" (both shipped); the single-process SSE
  gap "nothing schedules replacing it" (replaced, D-334/D-335/D-349); "no global rate limit
  exists" (exists); "integration shape still unconfirmed" (answered at S42).
- **Contradiction risk — HIGH** — and it loses every disagreement. Its one still-live item
  (question 5) sits beside four dead ones, indistinguishable from inside the file.
- **Candidate future role — ARCHIVE**, after two extractions: (a) the topology diagram, refreshed,
  into ARCHITECTURE.md; (b) open question 5 into an owned decision record. Rename on archive —
  "FINAL_ARCHITECTURE" is this audit's misleading-filename exhibit.

## 8. docs/INTEGRATION_PLAN.md (626 lines)

- **Purpose.** The full plan for connecting the new apps to the frozen production system: the
  immutability constraint and Tier 0/1/2 boundary, the Phase 0 audit and its nine §2.6 gate
  criteria, the auth option analysis (O1/O1b/O2–O4), the I1–I15 incompatibility catalog, the
  impossible-items table, session plan S35–S51, staged rollout, and the §7 residual-risk register
  (R1–R9, A1–A3).
- **Type.** Normative (constraint + tiers, echoed by CLAUDE.md) + planning + decision (auth
  matrix) + reference (risk register) + historical patches (§2.5 dispositions, §8 pre-discovery).
- **Temporal scope.** Rewritten 2026-07-24 (superseding two earlier drafts of itself); patched
  through 2026-07-30; **not updated since** — the gate closing, S42's discovery, and D-151/152/153
  are absent.
- **Information it owns.** The Tier 0/1/2 taxonomy (the only place "what counts as touching
  production" is drawn); the auth option matrix and coupling-surface reasoning; I1–I15 with
  per-item resolutions; the §4 accepted-reduced-scope table; §7's R8/R9 with their **expiry
  conditions** ("this acceptance expires at first real traffic") — cited as authoritative by
  ROADMAP, PROGRESS, and DECISIONS; the nine §2.6 gate criteria; §8's corrections including the
  `attendanceClaimed` fail-open trap.
- **Likely authority.** Highest inbound authority of the architecture set — ROADMAP:594 names it
  "the detailed source for this milestone"; AUDIT_FINDINGS derives from its §2.3; e2e/README
  cites §2.6. **Not in CLAUDE.md's index**, even though CLAUDE.md's ⛔ D-152 section is entirely
  about this document's subject matter and never names it.
- **Overlap.** §5's session table duplicates ROADMAP S35–S51 (ROADMAP carries the newer statuses);
  §7-R8/R9 duplicated in ARCHITECTURE (without expiry conditions there); §1 facts vs
  S42_DISCOVERY (which corrects two of them — "23 columns", "no health endpoint" — corrections
  that live only in the correcting file).
- **Stale risk — HIGH.** §2.5's "still open" items are closed; §3.1's "decision open until S42
  discovery" gate is neither open-as-written nor closed (frozen by D-152 instead); §1 is patched
  only by §8's reference, never edited; §5's table has no status column, so all of S35–S51 look
  equally pending.
- **Contradiction risk — HIGH, the most consequential in the repo.** `D-152` appears **zero
  times** in the file (verified by the profiler's grep). Read standalone, it actively directs the
  four actions CLAUDE.md L54–72 forbids: measure AWS→icrest reachability, make the Tier 1 org
  asks, finalize the §3.1 auth option, and work the adapter against production's schema. It also
  states outbound drafts are "kept outside this repo (gitignored)" (L619) while three such drafts
  are committed in docs/.
- **Candidate future role — ACTIVE only with a D-152 freeze banner at line 1**, plus: §2 marked
  historical (the gate ran and closed), §5 reduced to a pointer at ROADMAP, §1 folded with §8.

## 9. docs/AUDIT_FINDINGS.md (5,822 lines)

- **Purpose.** The findings register for the Phase 0A audit (S36–S39 + continuations): one row per
  finding with reproduction, evidence, disposition, and fix history, plus recorded
  areas-audited-with-no-finding, so §2.6 criteria 1–2 "can be evidenced rather than asserted".
- **Type.** Audit (primary), with layered current-state→historical strata per finding, embedded
  decisions, reference (the Index tables are the finding-ID ledger), and operational content
  (alarm thresholds, capacity pricing).
- **Temporal scope.** 2026-07-25 → **frozen 2026-08-05** (D-183 closure). Was aggressively living
  (statuses edited in place, correction markers inline); has been a snapshot for two weeks while
  two successor audits (2026-08-16, 2026-08-17) were filed elsewhere — this file mentions
  **neither**.
- **Information it owns.** Reproduction recipes and raw measurements per finding; negative results
  (the only record of what was checked and found correct); measurement-method corrections;
  measured constants and threshold sweeps; capacity curves; the AUD-L-17→AUD-L-19 ID-collision
  history (resolved per-reference across 33 citations in five documents, ranges deliberately left
  ambiguous); the register's own integrity failures (27 findings had a section but no row; five
  headings said "not fixed" after fixes shipped).
- **Likely authority.** The source of truth for Phase 0A finding status — ROADMAP derives the open
  count from it by anchored awk, and the file itself instructs "confirmed by running ROADMAP's
  anchored awk, not by counting this sentence." Its status column has been demonstrably wrong
  repeatedly and says so, capping trust in any single status without the body.
- **Overlap.** Heaviest with DECISIONS.md (fix rationale duplicated at length); ROADMAP
  (counts/criteria); PROGRESS (session narratives, mutual corrections); SPEC (verbatim requirement
  quotes plus recorded deliberate non-conformance the SPEC does not reflect); successor audits
  (subject overlap, **ID-namespace collision**: `AUD-L-01` here is a closed /dev/token finding,
  `AUD-L-01` in AUDIT_LIVE_2026_08_17.md is an unrelated P1 — nothing in either file flags this).
- **Stale risk — HIGH** — not open-finding rot (all closed) but: the "0 open / backlog empty"
  claim reads project-wide while two later audits filed 46+48 findings; accepted residual risks
  R8/R9 carry expiry conditions ("expires at first real traffic") that need re-checking; owed
  verifications whose named dates (2026-08-06/13) have passed; deploy identifiers, volumetrics,
  and capacity numbers pinned to 2026-08-05.
- **Contradiction risk — HIGH.** A self-contradictory heading (AUD-F-27: "✅ fixed … not fixed",
  L4521); severity relabels (P3→P1, P2→P3) other docs may not carry; "dispositioned" as a third
  status that naive counting mis-buckets; blank lines splitting the Index into six table
  fragments, breaking naive parses.
- **Candidate future role — REFERENCE** (frozen register with an archival core). The Index status
  column should stop being treated as authoritative; the relationship to the two successor audits
  needs one written sentence each.

## 10. docs/AUDIT_2026_08_16.md (300 lines) — read in full directly by this audit

- **Purpose.** Four independent sweeps run after C1 Phase 6 closed — learning-web UI/UX, chat-web
  UI/UX, timing/races, observability with live AWS reads: **46 findings, 44 new**. Its §1 is the
  audit's central product: "the finding behind the findings" — seven fixes shipped in one app and
  never ported to the sibling (a table of fix → shipped-in → never-ported-to → consequence), plus
  §6's process lesson ("a check that is correct and no longer checks").
- **Type.** Audit (point-in-time) with **status strata edited in on top**: a 2026-08-16 status
  blockquote (all 10 P1s closed, D-373→D-380) and a 2026-08-17 update blockquote (five
  observability items closed, D-393→D-396), plus one inline "✅ resolved" marker in §3 (L246).
- **Temporal scope.** Audit date 2026-08-16; patched 08-16 and 08-17; **not patched since**, while
  Milestones 13–15 (D-397→D-423) closed most of what its "Still open" lines list.
- **Information it owns.** The symmetry-drift table (§1); the ten P1 narratives with file:line
  evidence (P1-1…P1-10); the batch-ordered fix plan (§5); the §6 process lesson.
- **Likely authority.** Evidence document; severity follows AUDIT_FINDINGS.md's scale by reference
  (L39); every finding cross-checked against DECISIONS/ROADMAP/PROGRESS before "NEW" was claimed
  (L42–43). Defers to DECISIONS for dispositions. **Not listed in CLAUDE.md's index** (its 08-17
  sibling is).
- **ID namespace.** Uses its own third scheme — `P1-1`…`P1-10` for P1s and unnumbered prose for
  §3/§4 — distinct from both AUDIT_FINDINGS.md's `AUD-<area>-<n>` and AUDIT_LIVE's mixed scheme.
- **Overlap.** DECISIONS D-373→D-380/D-393→D-396 (the fix records); AUDIT_LIVE (next-day audit of
  the same build); PROGRESS/ROADMAP retellings.
- **Stale risk — MEDIUM-HIGH.** The two "Still open" lists (L20–22, L37) were themselves
  overtaken: chat's Stop-doesn't-stop-the-server (fixed, D-402/D-413), per-student spend
  attribution (D-400), the single-inbox alarm target (D-401/D-419), the approval-modal overflow
  and composer focus (fixed in the D-381 pass) — none marked here. §3/§4 items carry no status at
  all, so fixed and open are indistinguishable without cross-checking DECISIONS.
- **Contradiction risk — MEDIUM.** Its own 08-17 update corrects its own count ("The count was
  **22**, not the 15 stated above", L33); D-403 later recorded "the audit's own note was wrong
  about the reference implementation."
- **Candidate future role — REFERENCE** (the §1 symmetry finding and §6 lesson are durable; the
  status lines are not).

## 11. docs/AUDIT_LIVE_2026_08_17.md (142 lines) — read in full directly by this audit

- **Purpose.** What four `agent-browser` walks over the deployed build `gha-6841d9d9b169` found
  (D-381): 41 flows, 101 screenshots, **48 findings / 42 unique** (2 P1, 14 P2, 32 P3), organized
  as Fixed-in-this-pass / Not-acted-on / Still-open, plus the coverage-gap analysis CLAUDE.md
  points at ("the Playwright suite was green on this same build hours earlier with both P1s live
  in it — a statement about coverage").
- **Type.** Audit + reference (the coverage-blind-spot analysis, "the more valuable half").
- **Temporal scope.** Audit of 2026-08-17, then **maintained in place through 2026-08-18**: the
  Still-open list carries ✅ resolution annotations (D-411/D-412/D-413), and the coverage-gap
  section carries four dated blockquote updates (D-383/D-385/D-387/D-388/D-389) that close or
  narrow each gap. Not touched since 08-18.
- **Information it owns.** The live-walk finding catalogue; the green-suite-with-live-P1s coverage
  lesson; the three blind spots (nothing terminal ever completed; every approval declined never
  approved; every failure injected client-side) and their closure narratives; the reasoned
  non-actions (AEL-06's service-worker analysis, AUD-CHAT-05's unmet precondition).
- **Likely authority.** The only audit document in CLAUDE.md's index; defers to D-381 for root
  causes and to DECISIONS/OPEN_DECISIONS for outcomes.
- **ID namespace — the collision, verified directly.** It uses `AUD-CHAT-*`, `AUD-L-*`, `AEL-*`,
  and `EDGE-CHAT-*`. Its `AUD-L-01`…`AUD-L-19` range **reuses nineteen IDs that mean entirely
  different findings in AUDIT_FINDINGS.md** (e.g. `AUD-L-01` = expired-token dashboard loop here
  vs the /dev/token finding there; `AUD-L-17` = child-chooser-has-no-exit here vs the finding that
  was famously renumbered to AUD-L-19 there *because of* an earlier collision). Neither file
  states a namespace rule; any bare `AUD-L-nn` citation in DECISIONS/PROGRESS after 2026-08-17 is
  ambiguous between two registers.
- **Stale risk — MEDIUM.** Its residual still-open tail is partly overtaken (EDGE-CHAT-07 closed
  D-408; AUD-L-09 fixed D-407; AUD-L-10/L-11 addressed D-409/D-410; AUD-CHAT-14 measured and
  recommended for closure-as-accepted, D-412) with no in-file marks for those.
- **Contradiction risk — LOW-MEDIUM** (its own blockquotes correct its own over-broad phrasings —
  a discipline the 08-16 audit lacks).
- **Candidate future role — REFERENCE.**

## 12. docs/TRACEABILITY.md (791 lines) — read in full directly by this audit

- **Purpose.** The §2.6 criterion-1 evidence (the "§2.6" is **INTEGRATION_PLAN.md's** §2.6, not
  SPEC's — a namespace ambiguity worth knowing): every launch-scope SPEC §5 requirement mapped to
  implementation *and* a falsifying test, or carrying an explicit dispositioned / structural /
  descriptive verdict; discrepancies T-01/T-02 with dispositions; the criterion declared MET as of
  D-129 "on a reading that is written down rather than left to be inferred."
- **Type.** Audit/evidence + reference (the verdict vocabulary and method are quasi-normative:
  "the next person to want a fifth verdict should have to argue against this paragraph").
- **Temporal scope.** Created 2026-07-30 (D-124), swept in six tranches to 37/37 sections,
  actively maintained: rows updated for D-226's shape-apparatus deletion, D-294's cost-recording
  scope correction, D-393/D-394's logging fixes; the stale §Status heading corrected 2026-08-17
  (D-387). A living instrument, not a snapshot.
- **Information it owns.** The method rule ("unverified counts as not traced" — a row needs an
  implementation citation *and* a test that would fail); the four-verdict vocabulary with the
  fenced "structural" definition and the two sections honestly downgraded to "descriptive" (§5.3,
  §5.36); the launch-scope determination (exclusions: §5.17/§6.19 per D-078, EKS-only §5.30.3
  items per D-004, WAF per D-087); T-01 (CloudTrail built / GuardDuty deferred — "absent and
  deliberate rather than absent and unknown") and T-02 (first-visit notice: S45 builds, §6.1 track
  enumerates first, "scheduled, not shipped"); per-tranche traceability lessons (a criterion can
  be traced to real code and still be unenforced — read the floor, not just the check).
- **Likely authority.** High: CLAUDE.md indexes it with a read-the-method-first instruction;
  DECISIONS cites it as the criterion-1 instrument; AUDIT_FINDINGS defers to it.
- **Self-documented hazard.** Its summary lines have twice contradicted its own tables — the
  heading said "turns on one open discrepancy" after T-02 was dispositioned (corrected 08-17,
  L74–78), and "Open: none" sat above a table showing T-02 open in the same commit (L641–645).
  Both are kept, annotated, as warnings — the file treats its own near-misses as method.
- **Stale risk — MEDIUM.** Rows cite file:line and test names that move (it was already burned
  once: the §5.8.5 row was "evidence for a requirement satisfied by code no student could reach"
  until D-226 rewrote it); §7-R8's acceptance "expires at first real traffic"; T-02's owner "S45"
  inherits the S45 label ambiguity (ROADMAP's consent session vs PROGRESS's completed unnumbered
  "S45").
- **Contradiction risk — LOW-MEDIUM** (its discipline of correcting loudly in place is the
  strongest in the repo).
- **Candidate future role — ACTIVE** (the living criterion-1 instrument).

## 13. docs/OPEN_DECISIONS.md (636 lines)

- **Purpose (its own words).** Kept "because the *reasoning* behind each option is worth having
  when the work starts, and because two of the answers went against the recommendation" — a
  preserved deliberation record: options, consequences, recommendation, outcome, for 14 judgement
  calls, plus a "not decisions — already settled" trailer.
- **Type.** Decision + historical, with a thin current-state banner. Not a queue.
- **Temporal scope.** Densely dated; two global banners ("Every decision in this file was answered
  on 2026-08-14 (D-322)", L3; "✅ Nothing in this file is awaiting a decision (2026-08-18,
  D-417)", L8). Last touched 2026-08-18 — the freshest of the ops docs.
- **Information it owns.** The option space and recommendation-vs-outcome divergences for 14
  decisions — DECISIONS.md records what won; this records what else was on the table and why the
  recommendation lost (three items decided against their own recommendation). Also the meta-lesson
  ("a status line is a measurement with an expiry date", L27–28).
- **Likely authority.** Deliberately subordinate — every item defers to a D-id; drift is one-way
  (DECISIONS leads, this lags), and the file documents both times that lag mattered (#6's video
  figure wrong by two orders of magnitude; #7 recommending the opposite of settled D-341).
- **Overlap.** Near-total with DECISIONS on outcomes (never naming the file); ROADMAP (explicit
  hand-off: "the execution plan is ROADMAP.md's Milestone 10"); #4 is the parent of
  U7_CHECKPOINT_CONSOLIDATION.md — **neither links to the other**; #5/#7 duplicate
  QUESTION_GENERATION numbers.
- **Stale risk — LOW-MEDIUM in structure, HIGH in exposure.** Content is date-stamped and
  reconciled in place; but L3's "every decision … answered on 2026-08-14" is falsified by items
  11–14 (decided 08-17/08-18), and L15's "D-401 and D-406 stay unapplied" is contradicted by
  D-419 ("applied", 2026-08-18). CLAUDE.md's description ("ten decisions … still open") is the
  stalest thing about it.
- **Contradiction risk — MEDIUM.** Title vs banner ("Open decisions" / "Nothing … awaiting a
  decision"); blockquote-nested "Previously: ⏳ OPEN" former headings that outline renderers hoist
  to top level; #4's dev numbers vs U7's staging numbers (~17× apart, reconciled only by one line).
- **Candidate future role — REFERENCE (trending archive), and rename or re-describe.** The
  filename plus CLAUDE.md's description keep a closed record in the active read-path — exactly the
  misleading-active pattern its own L292 warns about.

## 14. docs/INCIDENT_RESPONSE.md (310 lines)

- **Purpose.** The practical runbook a solo maintainer follows during a real incident: severity
  tiers, a five-step general procedure, and five playbooks (leaked credential, auth bypass,
  unauthorized data access, cost anomaly, outage), each grounded in this project's own incidents
  (D-084, D-085, D-310, D-400).
- **Type.** Operational/normative runbook + historical worked examples + reference (executable
  CloudWatch/SQL queries, run against staging before being written down).
- **Temporal scope.** Framed as S33 (2026-07-23) but amended through 2026-08-16; **no date or
  version header** — a paragraph's vintage is inferable only from the D-number it cites.
- **Information it owns.** Nearly all of it is unique operational knowledge: the PII-boundary
  triage rule; rotation commands with the `-replace` scoping trap; the D-310
  "a safety claim in a comment is a hypothesis; measure it once" lesson; scanner cautions
  (~97% health-check dilution); the full D-400 cost-attribution procedure with measured baselines.
- **Likely authority.** Highest of the operational docs: in CLAUDE.md's index, cited by
  PROGRESS/ROADMAP for the `-target` apply form, queries verified live.
- **Overlap.** Least of its cluster; narrative counterpart to four DECISIONS entries; hands off to
  SPEC §6.23/S34.
- **Stale risk — MEDIUM.** L295–302 describes S34's failure drills in future tense — S34 shipped
  2026-07-24 (ROADMAP:575–576); the "pre-launch stage" framing will silently invert at launch;
  30-day cost baselines drift; the Terraform commands are version-sensitive and already carry one
  superseded-command warning.
- **Contradiction risk — LOW-MEDIUM.** Internally consistent; the S34-tense error is the one real
  conflict. Gap: the D-152 freeze is unmentioned, so the MySQL-adjacent severity tier reads as a
  live production attack surface when no production path exists yet.
- **Candidate future role — ACTIVE.** Needs a date header, the S34 tense fix, and one
  freeze-context line.

## 15. docs/QUESTION_GENERATION.md (450 lines)

- **Purpose.** Design-of-record for the offline question-generation pipeline — stages, the
  three-value difficulty model, run commands, preflight refusals, safety properties, deferrals —
  and a prohibition: the top banner parks all coverage-driven generation runs (D-342).
- **Type.** Current-state + normative, with historical strata (two superseded state blocks kept
  inline) and one operational section.
- **Temporal scope.** No "last updated" line; four dated strata coexist (2026-08-05 superseded
  roster, 2026-08-06 pilot, 2026-08-11 re-measurement, 2026-08-12 "Current" state block); header
  decision list stops at D-194 while the body cites D-342 — ~150 decisions of drift between header
  and body.
- **Information it owns.** The pipeline stage graph; the `requested/proposed/reviewed` difficulty
  model and D-239 re-tier rule; the repair-feedback filter table; preflight fail conditions
  (including the availability-vs-invocability distinction — "AVAILABLE is not a promise you can
  call the model"); run-metric definitions; D-223's per-topic volume rationale.
- **Likely authority.** Self-declared and CLAUDE.md-endorsed as "the as-built design"; gates
  changes to `packages/curriculum`. High for mechanism; weaker for state and model roster.
- **Overlap.** Re-narrates ~15 decisions; ROADMAP consumes its §6/§9 as conditions; OPEN_DECISIONS
  #5 duplicates its 189-item gap; adjacent to HINT_SOLUTION_REVIEW (they share the §5.8.5 judge
  and never mention each other).
- **Stale risk — MEDIUM-HIGH.** The "Current, 2026-08-12" state block (696 items) is a
  measurement with no expiry marker; the file **ends** with an undated 2026-08-06 "Next:"
  instruction naming Mistral Large 3 as the only viable generator — contradicted 180 lines earlier
  by the 2026-08-11 re-measurement naming Sonnet 4.5; the superseded 08-05 roster block still
  contains live-voiced imperatives.
- **Contradiction risk — MEDIUM-HIGH** (the "Next:" block vs §6; "implemented as described" vs
  the do-not-run banner reads as tension; two adjacent state blocks 696 vs 127 items).
- **Candidate future role — ACTIVE.** Needs the state block and trailing "Next:" dated-and-boxed
  or evicted, and the 08-05 roster moved to an appendix.

## 16. docs/HINT_SOLUTION_REVIEW.md (541 lines)

- **Purpose.** Design for the LLM hint/solution review instrument (`PASS`/`REPAIR`/`REJECT`), the
  two-reviewer unanimity panel, the five falsification checks gating it, cost model, sequencing —
  plus the prohibition "read this before adding any hint- or solution-quality scoring anywhere."
- **Type.** Planning + normative + embedded audit/measurement report.
- **Temporal scope.** Title says "design (D-251 → D-256)"; body reaches D-261; last touched
  **2026-08-10** — the oldest ops doc — while its subject moved on the same day (D-262…D-269:
  pilot run, recall fixed, repairs applied to 44 bank items). Zero mentions of any D-262+ decision
  (verified by the profiler's grep).
- **Information it owns.** The two-scorer diagnosis; the PASS/REPAIR/REJECT contract and why
  `run_llm_judge` cannot be reused; the deterministic-vs-LLM boundary; the five falsification
  checks with pre-registered disqualifiers and measured values; the "generator is not the
  repairer" measurement; the pre-registered stopping rule; the `hint_quality_score` disposition
  table.
- **Likely authority.** CLAUDE.md calls it "the **planned** design"; **seven source files and two
  scripts cite it as normative** — code treats as law a document CLAUDE.md calls unbuilt.
- **Overlap.** Effectively a synthesis of D-245→D-261 with an explicit split-authority arrangement
  (the log records, the doc designs); PROGRESS names it as "the design".
- **Stale risk — HIGH.** Its front page describes a world that ended 2026-08-10: header says "the
  loop around them is not built" six lines above "`review_loop.py` implement[s] … the bounded
  loop"; §8's step 4 ("Validation run … First paid step") is unticked while §5 reports that run's
  results; reviewer C is "measured" at L378 and "does not yet exist" at L440.
- **Contradiction risk — HIGH** (all of the above are internal contradictions; plus vs CLAUDE.md's
  "planned").
- **Candidate future role — ACTIVE, but requires reconciliation before being trusted** — it cannot
  be archived (its §3/§4.5b/§4.6/§6/§9 rules exist nowhere else) yet currently functions as a
  reference with a wrong front page. Highest reconciliation priority of the ops docs.

## 17. docs/U7_CHECKPOINT_CONSOLIDATION.md (297 lines)

- **Purpose.** The ROADMAP-mandated design review for session U7: measured checkpoint storage on
  staging, what transfers to durable homes, the trigger and delete-set proposal, falsification
  list, recommendations, and **four questions to the user** (§9).
- **Type.** Audit/measurement + planning + decision-request.
- **Temporal scope.** Single-dated (2026-08-14, measured same day); **never edited after the day
  it was written**; contains self-expiring claims ("nothing is eligible for at least another 8
  days") with no absolute dates.
- **Information it owns.** The only staging checkpoint sizing anywhere; the bytes-by-phase table
  (completed sessions are 1.7% of checkpoint storage, abandoned 77%, chat 19%); the five orphan
  `LearningState` fields; the shared-tables constraint (a `phase=='completed'` job silently skips
  every chat thread); two corrections of other docs (PROGRESS's "90/90/365" framing; the 27-vs-31
  field count).
- **Likely authority.** A proposal awaiting user answers — written in second person. **Not listed
  in CLAUDE.md**; reachable only via PROGRESS/DECISIONS pointers; yet PROGRESS:1433 gates U7 on
  its §9 — an unlisted, unmaintained snapshot is the stated blocker for a roadmap session.
- **Overlap.** D-331 names it as companion; PROGRESS duplicates its results near-verbatim and
  carries the update it lacks; OPEN_DECISIONS #4 is the parent (dev-data numbers ~17× apart from
  this file's staging numbers; no cross-link either way).
- **Stale risk — HIGH.** §9's question 2 ("Does `learning_sessions` get built now?") was answered
  the same day — the table exists (migration `6538a95bc990_d331_learning_sessions.py`; PROGRESS
  records "THE EXTRACTION HALF IS BUILT, D-332") — and the doc still asks it; §8.2 reads as a live
  imperative for done work; line 3's "Steps 1–2 of §8 are done" points at the wrong section (the
  Done items are §7's), an error D-331 repeats.
- **Contradiction risk — MEDIUM-HIGH** (the above; plus a title naming an action §8.1 recommends
  not starting).
- **Candidate future role — REFERENCE (measurements) + ARCHIVE (status/§8/§9); currently
  mis-shelved and invisible-but-load-bearing.**

## 18. docs/CONTENT_COVERAGE.md (180 lines)

- **Purpose.** The disposition record for the source math taxonomy: all 245 unique CSV rows either
  covered or explicitly deferred with a reason, plus the answer-model family analysis (A/B/C/D)
  and the grade-band-ordering trap.
- **Type.** Reference (durable taxonomy analysis) + current-state snapshot (dated measurements) +
  decision rationale. A Phase-0 deliverable of Session C1 (D-273).
- **Temporal scope.** Built and measured 2026-08-11; no revision marker since.
- **Information it owns.** The 246→245 denominator and duplicate triple; the books→topics /
  rows→skills mapping; the eight measured `derive_answer` outcomes; the family split 173/37/34/1;
  the band-order trap and its pinning test; D-223's volume target vs SPEC §5.8.1.
- **Likely authority.** Self-presents as reproducible and authoritative for dispositions; defers
  to TRACEABILITY's posture and SPEC/DECISIONS. Cited by ROADMAP as C1 Phase 0's artifact. Not in
  CLAUDE.md.
- **Overlap.** Heavy with ROADMAP's C1 block (same numbers restated) and D-273; machine twin in
  `curriculum/coverage/csv_row_dispositions.csv`.
- **Stale risk — HIGH.** Its status columns describe needs that were built the same day or since:
  "needs the Phase R router" (done 2026-08-11), "⛔ needs figure support (Phase 5 decision gate)"
  (built, D-279), `place_value_compare` 15/15 wrong-shape (re-authored to 0/15), "4 bands
  populated" (now 7), bank size long since superseded (47/30/28/25 → 958+).
- **Contradiction risk — MEDIUM-HIGH** (a reader would rebuild an existing router or re-author
  fixed items; "C1" in its status line collides with the other C1 = S17).
- **Candidate future role — REFERENCE with a mandatory as-of/superseded banner** (the taxonomy
  facts are worth keeping; the status columns are not).

## 19. docs/ENROLLMENT_FAQ_APPROVAL.md (94 lines)

- **Purpose.** A ready-to-send bilingual (KO/EN) approval request asking the org's content owner
  to confirm four claims in the synthetic `public-enrollment-faq` draft, plus the exact
  post-approval flip procedure (manifest `draft → approved`, re-run `make knowledge-load`).
- **Type.** Operational (outbound draft, launch-checklist item) + reference.
- **Temporal scope.** Drafted in the S43-era org-drafts work; open-ended — it describes a state
  that persists until the org replies. **Still pending: the manifest is still `draft`** (verified
  by the profiler against `knowledge-content/manifests/public.yaml`).
- **Information it owns.** The four claims and their exact ask; the flip procedure; the routing
  rule (do not bundle with the security report); the claim that this is **the only launch-checklist
  item gating the guest journey's canonical question**.
- **Likely authority.** Authoritative for its own procedure; defers content authority to the org
  and the manifest. Not in CLAUDE.md — invisible at session start despite its sole-gate claim.
- **Overlap.** The org-asks genre (S42_ORG_ASKS, deliberately separate audience); grade-band
  question overlaps CONTENT_COVERAGE/SPEC §5.7.3.
- **Stale risk — LOW-MEDIUM.** Core premise verified still true; two dead pointers (the manifest
  line number; an instruction referencing the deleted `knowledge-content copy/` directory).
- **Contradiction risk — LOW.**
- **Candidate future role — ACTIVE until the org answers, then archive with the outcome.**

## 20. docs/FIRST_VISIT_NOTICE.md (237 lines)

- **Purpose.** SPEC §5.1.2's eleven first-visit disclosures written as actual student-facing copy
  in two reading registers, each with "True because / Goes false if" evidence rows; reports that
  three of the eleven describe unbuilt behaviour and recommends shipping eight. The transcription
  source for the (unstarted, frozen-adjacent) S45 session — "S45 transcribes this; it does not
  draft it."
- **Type.** Normative/spec-derived + reference + audit finding (§5) + planning input.
- **Temporal scope.** Present-tense against the codebase at authoring (T-02/D-127 era, last
  touched 2026-08-15); forward-scoped to S45.
- **Information it owns.** The only written copy for all eleven disclosures; the register split
  rule; the retention table with per-clock columns; the no-implied-erasure rule; the
  ship-eight-not-eleven recommendation.
- **Likely authority.** The authoritative input to a build, not the build; explicitly not the
  Privacy Notice and not a substitute for counsel review (§6.1 launch gate). Not in CLAUDE.md.
- **Overlap.** SPEC §5.1.2 (the requirement list); retention windows triple-stated (here,
  D-114/D-333, purge CLIs); its §5 gaps are traceability-shaped.
- **Stale risk — MEDIUM.** Every "True because" row is a dated code measurement (the 102-of-112
  video figure is exactly the class of line OPEN_DECISIONS flags as having gone 100× stale
  before); "Owner: S45" is ambiguous — ROADMAP's S45 (consent session, not run) vs PROGRESS's
  completed "S45 (unnumbered)" of 2026-08-02.
- **Contradiction risk — LOW-MEDIUM.** Internally disciplined; the open product decision it names
  ("the three gaps need a product decision before S45") is tracked nowhere else — open but
  invisible.
- **Candidate future role — ACTIVE** (unconsumed input to unstarted work); re-verify the
  "True because" rows at S45 start.

## 21. docs/S42_DISCOVERY.md (342 lines)

- **Purpose.** The evidentiary record of S42: what `go.intellichoice.org` actually does, read from
  source — the signups and login contracts, schema verdicts, timezone split, production security
  findings (§6), outstanding org asks (§7), the auth recommendation (§8), and "S43's real work
  list" (§9).
- **Type.** Current-state (§2–§5) + audit (§6, plus the adversarial-verification method: 8
  CONFIRMED, 2 REFUTED-with-correction) + planning (§7–§9) + decision-input (§8 — "a
  recommendation, not a decision").
- **Temporal scope.** Pinned to the 2026-08-01 checkout ("Source ≠ deployment"), edited 08-02
  (D-153 citations) without the header moving; 18 days old against a database that ALTERs on every
  boot (its own finding).
- **Information it owns.** The largest block of production facts in the repo: exact API contracts,
  role facts, schema-drift mechanism, the three-way timezone split, §6's findings, the
  production-vs-dev-fake mismatch table.
- **Likely authority.** CLAUDE.md-indexed ("read this before assuming anything about
  production…"); honest about limits. **The D-152 freeze is invisible in this file** — "D-152"
  appears zero times; §7/§8/§9's authority has been silently superseded.
- **Overlap.** §6 restated in S42_SECURITY_REPORT (which names it as source) and
  S42_OPEN_QUESTIONS group E; §7 asks = OPEN_QUESTIONS groups (which mark several resolved while
  this file says "unchanged"); corrects INTEGRATION_PLAN twice (corrections that live only here).
- **Stale risk — HIGH (for §7–§9).** "Runtime half still owed" (frozen, not owed); Messages A/B/D
  "still needed/unchanged" (answered or demoted by D-153); §9's "every row below must be fixed"
  (urgency withdrawn by D-152/DECISIONS:8973 and now *prohibited* by CLAUDE.md's
  do-not-rewrite-the-fake rule).
- **Contradiction risk — HIGH.** §9 vs CLAUDE.md (a reader obeying §9 violates CLAUDE.md); vs
  S42_OPEN_QUESTIONS on ask currency; the omitted `attendanceClaimed` fail-open warning that
  INTEGRATION_PLAN §8 carries.
- **Candidate future role — REFERENCE (§0–§6) + ARCHIVE-with-supersession-note (§7–§9).**

## 22. docs/S42_OPEN_QUESTIONS.md (121 lines, Korean)

- **Purpose.** What source could *not* answer: five groups (A user / B measurable / C org / D
  live-DB / E report-only) with urgency-at-integration-start, a resolved-items ledger, and the
  D-152 re-entry protocol ("only C3-send and E-group notification are live; everything else
  reopens the day integration is declared").
- **Type.** Planning/tracking (frozen) + decision banner + one normative constraint (production
  role alone never grants privilege in the new stack).
- **Temporal scope.** 기준일 2026-08-01, amended 08-02; urgency labels explicitly relative to
  integration start, not now.
- **Information it owns.** The freeze rationale in operational form; the resolved ledger; the
  re-entry protocol; the warning that B2 (deployment-matches-source) must precede trusting
  S42_DISCOVERY.
- **Likely authority.** **The only S42 file where the D-152 freeze is visible in the file itself**
  — a dedicated ⛔ banner plus protocol. CLAUDE.md cites it (outside the index) as the thing not to
  treat as a blocker.
- **Overlap.** DISCOVERY §7 (same asks, different currency — supersession runs opposite to the
  citation direction); E-group duplicates §6/SECURITY_REPORT without linking the drafted report;
  the E2 correction is a third copy of D-153 §7.
- **Stale risk — MEDIUM, mostly self-declared.** Resolved items (C1/C2/C3/C8) remain as full
  table rows — C3 still marked 🔴 "cannot be deferred" — after being declared resolved at the top;
  line 110 still instructs sending the answered C3 ask.
- **Contradiction risk — MEDIUM** (internal resolved-vs-tabled; it is the *newer and correct* file
  against DISCOVERY, but DISCOVERY is the indexed one).
- **Candidate future role — ACTIVE (frozen by design).** Two cheap repairs: annotate the resolved
  rows in-table; point E-group at S42_SECURITY_REPORT.md.

## 23. docs/S42_ORG_ASKS.md (406 lines, bilingual)

- **Purpose.** Four ready-to-send outbound messages to the org (A timezone, B DNS, C DB
  hosting/API reliability, D peak concurrency), Korean and English, plus internal notes (the
  one-ask-per-message rule, deliberate exclusions, translation rationale).
- **Type.** Operational (outbound drafts) + planning (send-timing table) + historical notes.
- **Temporal scope.** **Predates S42 despite its filename**: drafted at S36 close-out
  (2026-07-24), cut down 07-25, last amended 07-31. Its newest citations are D-099/D-130/D-134;
  D-151/D-152/D-153 are entirely absent.
- **Information it owns.** The only send-ready outbound text for these asks, in Korean; the
  one-ask-per-message rule; the deliberate exclusion of the committed-credentials topic; the
  corrected DST arithmetic note.
- **Likely authority.** Overrules a PROGRESS pointer on message-splitting (and PROGRESS conceded).
  Not in CLAUDE.md; defers to nothing newer than D-134.
- **Overlap.** Messages A–D are the outbound form of OPEN_QUESTIONS groups and DISCOVERY §7 —
  three parallel forms with three different currencies and no statement of which is authoritative.
- **Stale risk — HIGH (highest of the S42 set).** "Send now" markers on Message B (answered,
  D-153 §6) and Message A (demoted to a courtesy question, D-153 §4); Message C's hold-until-S42
  release condition can no longer arrive as written; "Message A is due before S43 opens" — S43
  opened and closed 2026-08-02; Message D prices a purchase D-153 §3 withdrew.
- **Contradiction risk — HIGH.** Vs INTEGRATION_PLAN:619 ("outbound drafts are not committed" —
  this committed file *is* such a draft); vs OPEN_QUESTIONS/D-153 on ask status; vs
  SECURITY_REPORT on the credentials-mention policy (opposite implementations of one rule).
- **Candidate future role — ARCHIVE**, preserving the message text: stamp per-message D-153
  dispositions at the top and rename away from `S42_`.

## 24. docs/S42_SECURITY_REPORT.md (170 lines, bilingual)

- **Purpose.** One send-ready bilingual message to the production system's operator reporting four
  security findings (from DISCOVERY §6, dispositioned in D-153 §5/§7) with fixes, framing rules
  ("courtesy hand-off, not an audit finding or a demand"), and an explicit not-sent list.
- **Type.** Operational (outbound draft) + audit-derived report + a small normative tail (our
  stack's allowlist does not relax regardless of org-side fixes).
- **Temporal scope.** Drafted 2026-08-02 (S43); **apparently still unsent** — PROGRESS's last word
  is "drafted send-ready" and nothing since tracks it; the file has no send-status field, so
  unsent is indistinguishable from sent-and-unlogged.
- **Information it owns.** The only maintainer-addressed Korean form of the findings; the
  non-accusatory framing rules; the ported check-old-rows recommendation rescued from the deleted
  `docs/SECURITY_REPORT_TO_ORG.md`; the explicit rule never to quote the source-visible secret
  literals.
- **Likely authority.** High and well-scoped; PROGRESS once declared it "exactly one security
  document, and it is the right one". Not in CLAUDE.md's index — a session reading only the index
  would re-derive it from DISCOVERY §6.
- **Overlap.** Near-total with DISCOVERY §6.1–§6.4 and OPEN_QUESTIONS group E — the four findings
  exist in four places (those two, this, D-153 §5/§7).
- **Stale risk — LOW-MEDIUM** (findings describe frozen code; severity gates on still-unknown
  runtime facts; the operator may have changed things in 17 days — no re-verification step).
- **Contradiction risk — LOW.** It is the file that correctly states the production freeze in its
  own words, and its work item (notify the operator) is precisely the exception the freeze
  preserves.
- **Candidate future role — ACTIVE** — the only S42 work item that legitimately survives the
  freeze. Needs a send-status line and an index entry so it stops being untracked.

## 25. docs/plans/2026-07-18-expansion-plan.md (958 lines)

- **Purpose.** The full design reference behind the 2026-07-18 feature expansion (learning
  1.1–1.8, chat 2.1–2.5): verified current-state assessment (§1), ten architecture calls, schema/
  API/graph/LLM/frontend designs, 13 tasks with acceptance criteria (§18), and twelve risks/
  unresolved decisions (§19).
- **Type.** Planning + historical (merged and fully executed as S17–S28, all shipped
  2026-07-19/20) + decision rationale. §1 is a present-tense current-state snapshot of 2026-07-18
  inside an executed plan — its defining hazard.
- **Temporal scope.** Dated 2026-07-18; ~30 sessions of history sit on top of it; deliberately
  excluded from the Mongo→MySQL doc sweep (DECISIONS:5174 declares docs/plans/ "a historical
  record left deliberately untouched") — defensible only if visibly marked historical, which it
  is not.
- **Information it owns.** The task→session map and D-049 renumber; the ten architecture calls;
  design rationale no other doc restates in full — ROADMAP still tells readers to "read the plan
  rather than re-deriving" (a live pointer into a stale file).
- **Likely authority.** Explicitly subordinate ("ROADMAP.md is the source of truth … this file is
  the design reference").
- **Overlap.** Large: ROADMAP S17–S28, D-049, PROGRESS entries, QUESTION_GENERATION (planned vs
  as-built pipeline).
- **Stale risk — HIGH.** §1's "Does not exist" claims are all long since false; the
  `effective_from: 2026-08-01 (future)` premise inverted with the calendar; **still says Mongo**
  where the system is MySQL (L563, L649); §19's four "needs sign-off" items were consumed and
  closed by the sessions that shipped.
- **Contradiction risk — HIGH** for any reader who misses the status line at L3; also the `C1`
  label collision (chat-content session S17 here vs the 2026-08-11 content-seeding Session C1) and
  an internal authority tangle (L448/L848 claim to "supersede/replace ROADMAP S17" while L5 names
  ROADMAP its source of truth).
- **Candidate future role — ARCHIVE with an explicit superseded/as-of header, not delete**
  (deleting breaks ROADMAP's live pointer).

## 26. docs/plans/2026-07-19-branding-plan.md (164 lines)

- **Purpose.** The complete visual-identity plan: brand audit extracted from the live WordPress
  theme CSS, five BD-decisions (including a deliberate WCAG contrast deviation recorded so it is
  never "fixed" back), codebase recon, token mapping, four phases, risks.
- **Type.** Planning (executed) + reference (the brand-audit data is durable) + decision (BD1–BD5,
  logged as D-065–D-069).
- **Temporal scope.** 2026-07-19 — and executed the same day as Session 22.5 (ROADMAP:326;
  PROGRESS: "executed as written").
- **Information it owns.** The extracted brand table (fonts, colors, gradient, geometry); the logo
  asset warnings; the "site's dark CSS is Impreza defaults, not brand truth" ruling; BD3's exact
  contrast ratios and the standing do-not-revert rule.
- **Likely authority.** Stale as a status document, authoritative as a data document — ROADMAP:
  327–330 grants the brand data standing authority ("read it instead of re-deriving any of that").
- **Overlap.** ROADMAP S22.5; D-065–D-069 (BD rationale in both); the as-built
  `packages/ui-brand` tokens (with recorded deviations, e.g. favicon colors).
- **Stale risk — HIGH for status, LOW for data.** **L2–4 still reads "Status: planned, not
  started … run via `/start-session S22.5`"** for a session completed 2026-07-19 — no done/
  superseded marker anywhere; L44–45 tells the reader D-064 is the last-used decision number (the
  log is past D-423 — following it would mint duplicate decisions); L73's "trust this, no need to
  re-derive" recon describes files the execution deleted.
- **Contradiction risk — HIGH for status, LOW for data.**
- **Candidate future role — SPLIT: archive the plan** (with an "executed as S22.5; BD1–BD5 =
  D-065–D-069" header), **promote the data** — the brand table and BD3's do-not-revert rule belong
  somewhere active (`packages/ui-brand`), because a file marked "not started" is a weak home for a
  standing rule.

---

## Inspection coverage ledger

**DECISIONS.md (28,787 lines) — 100% line coverage**, 7 readers, cut at heading boundaries with
~30-line overlaps: 1–4296 · 4267–8467 · 8438–12638 · 12609–16815 · 16786–21037 · 21008–25216 ·
25187–28787. Every reader confirmed its exact range read with no gaps or truncation.

**PROGRESS.md (16,690 lines) — 100% line coverage**, 4 readers: 1–4202 · 4173–11282 ·
11253–15452 · 15423–16690. Same confirmation.

**All 24 other documents were read in full, every line** — 21 by their profilers (each stated an
explicit coverage line: SPEC 1–4210; ROADMAP 1–3328; AUDIT_FINDINGS 1–5822; ARCHITECTURE 1–2180;
FINAL_ARCHITECTURE 1–185; INTEGRATION_PLAN 1–626; and the fourteen small/medium documents and
CLAUDE.md in single full passes), and **three read in full directly by the auditing session
itself** (AUDIT_2026_08_16 1–300; AUDIT_LIVE_2026_08_17 1–142; TRACEABILITY 1–791) after the
delegated profiler for that cluster failed twice on a transient server-side 529 error.

**Direct verification pass (read by the auditing session itself, not delegated):** the phantom-ID
greps (D-190/191/192 meta-note at DECISIONS:16101; D-329 sub-heading-only at DECISIONS:23582;
D-363 referenced at DECISIONS:25728/25894 and PROGRESS:891/2214 with no heading anywhere);
D-344's stale status clause (DECISIONS:24671) against its own correction (DECISIONS:24704–24707);
the duplicate `### S20` heading (PROGRESS:15451/15453); the nonexistence of the referenced
`docs/codebase-analysis/` directory (DECISIONS:3842 refers to it; only `docs/` and `docs/plans/`
exist — the reference resolves to `../IntelliChoice-web/docs/codebase-analysis/`, an out-of-repo
path, per S42_DISCOVERY:8).

**Not inspected (out of scope by instruction):** `../IntelliChoice-web` (all of it, including its
`docs/codebase-analysis/`); the two forbidden credential files (never opened); `docs/.DS_Store`
(binary Finder artifact); source code and test files except the specific corroborating reads the
profilers listed (migration files, manifests, `grade_topic_mapping.yaml`, skill definitions).
One transient failure occurred and was fully recovered: the audit-cluster profiler died twice on
server-side 529 errors, so the auditing session read those three files (1,233 lines) itself in
full. No reader or profiler reported any unread line; nothing in scope was left uninspected.
