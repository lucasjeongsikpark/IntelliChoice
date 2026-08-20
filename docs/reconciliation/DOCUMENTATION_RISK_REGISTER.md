# Documentation Risk Register — Structural Risks

**Date:** 2026-08-19
**Companion:** [DOCUMENT_INVENTORY.md](DOCUMENT_INVENTORY.md) (per-document profiles and the
inspection-coverage ledger). This register records **structural** risks in the documentation
corpus — patterns that can mislead a reader or a future session — with concrete evidence. It does
not reconcile or compress anything; every item is a finding, not a fix.

Severity here means *how likely this is to cause a wrong action or wrong belief, weighted by who
reads it*: **HIGH** = a reader following the document as written would do something wrong or
forbidden, or believe a materially false project state; **MEDIUM** = a reader must already know
external context to read the document safely; **LOW** = confusing but self-correcting or low
consequence.

The register is organized by the six requested categories (§1–§6), followed by three additional
structural risk classes the audit surfaced (§7–§9). Each entry cites the evidence a reader can
verify. Line numbers are as of 2026-08-19.

---

## §1 — Current and historical state mixed together

### R1.1 · PROGRESS.md's "Current status" block is ~1,800 lines deep in strata — HIGH
The section meant to represent current state (PROGRESS.md:6 onward) is a newest-first stack of
"Next session" / "Previous —" / "Earlier —" summaries reaching back through Milestone 10, with the
boundary to the historical log marked only by a `---` and the prose "Prior state, still true"
(~L1862). Point-in-time numbers coexist at different depths: the video catalog is "4 of 112
skills" at one stratum (L1156), "102 of 112" at another (L89–95), with the correct current figure
(497 videos / 102 of 112, L3243-era) only at the top. The file's own recorded lesson: the
carry-over list "has now been wrong six times this milestone" (L385–388).
**Why it matters:** the top block is the project's actual sequencer (ROADMAP.md:713–714 delegates
to it); anything stale here directs the next session.
**Blocks:** any reconciliation step that wants a single trustworthy "current state" page.

### R1.2 · ROADMAP.md keeps ~470 lines of superseded gate standings inline — HIGH
Lines 969–1436: superseded standings interleaved with the live verdict (L958 "THE GATE IS
CLOSED"), each tagged `*(Superseded…)*` but fully readable as current when skimmed. Five different
criterion-6 dates coexist (L983, 1009, 1018, 1055, 1097). Multi-tier and depth clauses each carry
3–4 unreconciled numbers ("81 of 96" L2096, "83 of 96" L2262, "⛔ 76 of 91" L2210; depth
denominators 165→152→153 at L1942/1960/2097) where the later-in-file text is *earlier* in truth
order.
**Blocks:** deriving gate or coverage status from ROADMAP without reading DECISIONS.

### R1.3 · DECISIONS.md strata: entries are edited in place, referencing later decisions — MEDIUM
The log is not append-only: D-176 §4 records a paragraph edited after the fact ("this paragraph
originally ended 'inferred, not yet verified'"); D-110 §2 contains an embedded "> D-207 update"
block revising its own numbers by reference to a decision ~100 IDs later (L4963); D-401 carries a
correction dated 2026-08-18 inside a 2026-08-17 entry (L27513–27540). The mutability is honest
(corrections are loud) but means an entry's text cannot be dated by its heading.
**Blocks:** treating any single DECISIONS entry as a point-in-time record without scanning for
inline update blocks.

### R1.4 · SPEC.md embeds decision-log fragments in exactly two places, silently amended elsewhere — MEDIUM
§5.19.4/§5.19.5 (L1973–2008, D-351) and §5.35 (L3403–3405, D-092) are the only in-text amendment
markers in 4,210 lines; the D-111 MySQL sweep rewrote ~40 lines and four headings with no marker
at all (recorded only at DECISIONS.md:5170). The document is therefore *mixed-vintage with no
vintage marks*: a reader cannot distinguish never-amended text from silently-amended text.
**Blocks:** using SPEC text as current requirement without cross-checking DECISIONS.

### R1.5 · ARCHITECTURE.md contradicts itself on scheduler state — MEDIUM
L24–36 says the four schedules (incl. `memory-consolidate`, `chat-purge`, weekly youtube-sync
shipped disabled) exist and "do run unattended"; yet L1791–1792 ("manual trigger this session; a
weekly EventBridge schedule is later infra work"), L1850–1851, and L2068 ("no scheduler yet")
still describe the same jobs in the older posture. Also L644 calls a `/stream` issue "carry-over"
that L289–297 records as fixed (D-348/D-356).
**Blocks:** reading any single section of ARCHITECTURE.md as current without checking the top.

### R1.6 · QUESTION_GENERATION.md: four dated strata under one roof, live-voiced superseded text — MEDIUM
The "superseded" 2026-08-05 model-roster block (L280–309) contains present-tense imperatives ("The
shipped code default … is not invocable as written", "Solver A and B **must** be different model
ids. They currently are not") with no visual containment; §10 holds "Current, 2026-08-12" (696
items, L404) directly beside a superseded block (127 items, L413) separated only by bold prose;
the header's decision list stops at D-194 while the body cites D-342 (L3).
**Blocks:** trusting any state or roster claim in the file without checking its stratum date.

### R1.7 · Audit documents patched by blockquote strata, unevenly — MEDIUM
AUDIT_2026_08_16.md carries two status blockquotes (L7–37) that close the P1s and five
observability items, but its §3/§4 P2/P3 lists carry no status marks at all, and its "Still open"
lines (L20–22, L37) were overtaken by D-397→D-423 without further patching.
AUDIT_LIVE_2026_08_17.md is better maintained (✅ annotations through 08-18) but its residual
still-open tail is also partly overtaken (EDGE-CHAT-07 closed by D-408; AUD-L-09 by D-407;
AUD-L-10/L-11 by D-409/D-410) with no in-file marks.
**Blocks:** using either audit's open list as a work queue.

### R1.8 · docs/plans/2026-07-18-expansion-plan.md §1 is a present-tense snapshot inside executed history — MEDIUM
§1 (L13–155) asserts "**Does not exist**" (L90, L96), "already the 'next session'" (L110) about
features that shipped a month ago; the saving status line is 87 lines above at L3. §19's
"unresolved decisions" (L911–931) were all consumed and closed. The file still says **Mongo**
(L563, L649) — docs/plans/ was deliberately excluded from the MySQL sweep (DECISIONS.md:5174)
without being visibly marked historical.
**Blocks:** safe reading of the design reference ROADMAP still points into (ROADMAP.md:5, 326–331).

---

## §2 — Duplicate authority

### R2.1 · Two architecture documents, no ratified hierarchy — HIGH
ARCHITECTURE.md (2,180 lines, 2026-08-18) and FINAL_ARCHITECTURE.md (185 lines, 2026-07-28) both
describe system topology. The deference is stated only in the weaker file (FINAL_ARCHITECTURE.md:
3–6 "not a source of truth the way ARCHITECTURE.md is"); ARCHITECTURE.md never acknowledges
FINAL_ARCHITECTURE.md exists; **neither is in CLAUDE.md's index**, so a newcomer's only signal is
the filenames — which point the wrong way (see R3.1). The storage-split table has two owners:
ARCHITECTURE.md:2054–2073 holds it; FINAL_ARCHITECTURE.md:156–161 appends a row to it from
another file.
**Blocks:** any "which architecture doc wins" question; the extraction FINAL_ARCHITECTURE itself
prescribes (L183–185).

### R2.2 · The §7-R8/R9 accepted risks live in two places; only one carries the expiry — HIGH
INTEGRATION_PLAN.md §7 (L535–566) owns the two accepted P1 risks with their expiry conditions
("**This acceptance expires at first real traffic**", L548; the `learning_checkpoint_repairs_total`
tripwire, L565). ARCHITECTURE.md restates both at L486–494 and L601–609 **without the expiry
conditions** — and ARCHITECTURE.md is the file sessions are instructed to update (and therefore
read), while INTEGRATION_PLAN.md is unindexed.
**Why it matters:** an accepted risk whose expiry clause is invisible at the point of reading is
how "accepted for the pilot window" silently becomes "accepted for launch" — the exact failure
shape TRACEABILITY.md documents for D-072/AUD-L-04 ("an accepted residual risk whose mitigating
assumption had silently stopped holding").
**Blocks:** launch-readiness review of accepted risks.

### R2.3 · Session status has three homes; finding counts have two — MEDIUM
Session status: ROADMAP's ✅ glyphs, PROGRESS's log, and INTEGRATION_PLAN §5's table (no status
column at all, L455–473). Finding counts: AUDIT_FINDINGS.md's hand-maintained count line
(L159–169, "this line has now been wrong three times") vs ROADMAP's anchored-awk derivation
(ROADMAP.md:708/770) — the register itself instructs readers to trust the awk, not the sentence
(AUDIT_FINDINGS.md:166).
**Blocks:** any mechanical status roll-up.

### R2.4 · The four production security findings exist in four places — MEDIUM
S42_DISCOVERY.md:205–250, S42_OPEN_QUESTIONS.md:99–104, S42_SECURITY_REPORT.md:47–86/109–149, and
DECISIONS D-153 §5/§7. PROGRESS.md:7731–7732 already had to declare a winner once ("There is now
exactly one security document, and it is the right one") after deleting a fifth copy
(`docs/SECURITY_REPORT_TO_ORG.md`) — but CLAUDE.md's index points at DISCOVERY, not at the
declared winner, so the collision can recur.
**Blocks:** knowing which security text is send-authoritative.

### R2.5 · Numbers duplicated verbatim across three files with independent lifecycles — MEDIUM
The 189-item depth gap: QUESTION_GENERATION.md:12 and OPEN_DECISIONS.md:225. The
`difficulty_tiers`-are-authoring-targets rule: QUESTION_GENERATION.md:13–16, OPEN_DECISIONS.md
#7 (L283–296), and D-341 — OPEN_DECISIONS records the rule was re-derived "at least three times"
because copies drifted. Checkpoint sizing: OPEN_DECISIONS #4 (dev data, ~4.8 GB) vs
U7_CHECKPOINT_CONSOLIDATION §1.1 (staging, ~285 MB) — ~17× apart, same subject, no cross-link.
Taxonomy figures (245/34/194, 47/30/28/25) verbatim in CONTENT_COVERAGE.md, ROADMAP.md:1763–1772,
and DECISIONS.md:19722.
**Blocks:** trusting any coverage/size number without a date check.

### R2.6 · CLAUDE.md's condensed rules are the copy actually read — LOW
CLAUDE.md L86–109 is a lossy compression of SPEC §5.x that declares SPEC the winner, but it is the
always-loaded copy. Rule 8 (image deletion) compresses a *deferred feature's* requirement into a
flat imperative; only FIRST_VISIT_NOTICE.md:122–123 explains the feature does not exist.
**Blocks:** nothing today; a drift amplifier when SPEC changes.

---

## §3 — Misleading filenames and labels

### R3.1 · `FINAL_ARCHITECTURE.md` — HIGH (the exhibit)
"FINAL" reads as *latest* and *definitive*; the file is neither — it is a self-declared projection
("planned as of 2026-07-21", L10–11), 10× smaller and 3 weeks older than ARCHITECTURE.md, with
zero functional inbound references. The filename is the entirety of its authority signal and it
points the wrong way.

### R3.2 · `OPEN_DECISIONS.md` — HIGH
Line 1: "Open decisions — what needs a person, not more code." Line 8: "✅ **Nothing in this file
is awaiting a decision** (2026-08-18, D-417)." The filename invites treating a closed deliberation
record as a live queue — and CLAUDE.md L38–40 compounds it ("everything still open … ten
decisions … read before asking 'what should I work on next'"; the file has 14 items, all closed).
The file's own L292 articulates the hazard ("an annotated recommendation is still a recommendation
to whoever skims it") — the filename is the un-annotated recommendation.

### R3.3 · `S42_ORG_ASKS.md` — MEDIUM
The `S42_` prefix asserts a session the content predates: drafted at S36 close-out (2026-07-24,
L3), last amended 2026-07-31 — before S42 ran (2026-08-01) and before D-151/D-152/D-153 answered
or demoted most of its asks. `S42_SECURITY_REPORT.md` is also mislabeled by one session (drafted
S43, L4) but harmlessly.

### R3.4 · `AUDIT_FINDINGS.md` — MEDIUM
Undated, unscoped name for a register scoped to Phase 0A and frozen at 2026-08-05, sitting beside
two dated successor audits. A reader looking for "the audit findings" on 2026-08-19 lands on a
two-week-old register that mentions neither successor. Its content also outgrew its title (S40–S43
findings, criterion evidence, capacity pricing).

### R3.5 · `U7_CHECKPOINT_CONSOLIDATION.md` — MEDIUM
The filename names an action (§8.1 recommends **not** starting the deletion) and conveys nothing
of what the file is: a 2026-08-14 measurement snapshot plus four questions to the user, half
answered since. It is also unindexed, so the filename is its only signal.

### R3.6 · `docs/plans/` — MEDIUM
The directory name reads as "current plans"; both files inside are executed history, one still
labeled "planned, not started" (see R4.2). No archive convention or status suffix distinguishes
them.

### R3.7 · `ROADMAP.md` — LOW
~60% of the file is completed-work retrospective, including three "✅ CLOSED" milestone banners and
a closing retrospective; "Sessions 40–41 (elastic)" heads a 245-line audit-backlog ledger; a
"Dependency notes" heading is followed by an unrelated C1 amendment (L2166/2177).

### R3.8 · SPEC.md's H1 — LOW
Line 1 is `# 5. Very Detailed Version` — a section number from an absent parent document. Bare
`§2.x` citations elsewhere in the corpus (TRACEABILITY.md:1's "§2.6") resolve to
INTEGRATION_PLAN.md, not SPEC — an unstated section-namespace split. CLAUDE.md:13 also
under-describes the file by 38% ("~2,600 lines" vs 4,210).

---

## §4 — Old plans that can look active

### R4.1 · INTEGRATION_PLAN.md contains no trace of the D-152 freeze — HIGH (most consequential single finding)
`D-152` appears **zero times** in the file (verified by grep). Read standalone, the document
actively directs the four actions CLAUDE.md L54–72 forbids: measure AWS→icrest reachability and
latency (L464), make the Tier 1 org asks (L442–446, 464), finalize the §3.1 auth option
("Decision gate: finalized at S42 … before S44 implements", L281–283), and work the adapter
against production's schema (L311–316, 465). §5's session table (L455–473) lists S42–S51 with no
status column; §8 is headed "read before executing S42" (L579). The freeze is enforced entirely
by CLAUDE.md and ROADMAP:1440–1445, and CLAUDE.md's ⛔ section never names this file — **the guard
and the temptation are not linked in either direction**.
**Blocks:** safe standalone reading of the integration plan; this is the first banner any
reconciliation should add.

### R4.2 · branding-plan.md says "Status: planned, not started" for a session executed the same day — HIGH
docs/plans/2026-07-19-branding-plan.md:2–4 ("run via `/start-session S22.5`") vs ROADMAP.md:326
("✅ done 2026-07-19") and PROGRESS.md:15175–15177 ("executed as written"). No done/superseded
marker anywhere in the file. L44–45 instructs logging decisions "next free D-numbers — D-064 was
the last used" (the log is past D-423; following it would mint duplicates), and L73 says "trust
this, no need to re-derive" about a recon whose subject files the execution deleted.
**Why it matters:** an agent obeying the file re-runs a completed session against a stale recon.
It also holds a standing do-not-revert rule (BD3's deliberate WCAG deviation, L155–156) inside a
file marked not-started — the rule's home undermines the rule.

### R4.3 · S42_ORG_ASKS.md carries three "Send now" instructions for answered/demoted asks — HIGH
L12–14: Message A "Send now" (demoted to a courtesy question by D-153 §4), Message B "Send now"
(answered — DNS confirmed, org adds records at integration time, D-153 §6), Message C "Hold until
S42" (a release condition that can no longer arrive as written — S42 ran, then D-152 froze the
measurement). L389's deadline "Message A is due before S43 opens" expired 2026-08-02. Message D
prices a capacity purchase D-153 §3 withdrew. The file cites nothing newer than D-134 and never
mentions D-151/D-152/D-153 or any other S42 file.
**Blocks:** safe use of the outbound-drafts set; a reader with no D-152 context would send
answered asks to the org.

### R4.4 · S42_DISCOVERY.md §7–§9 read as live work; "D-152" appears nowhere in the file — HIGH
Header (L3–4): runtime half "still owed" (it is frozen, not owed). §7 (L270–292): Messages A/B/D
"still needed / unchanged" (answered or demoted). §9 (L324–342): "S43's real work list … Every row
below must be fixed" — urgency withdrawn (DECISIONS.md:8973) and the action now *prohibited* by
CLAUDE.md's "do not rewrite the MySQL dev fake." A reader obeying §9 violates CLAUDE.md. §2–§6
remain safe and valuable.

### R4.5 · ROADMAP's frozen sessions still read as build specs; S48–S51 carry no freeze at all — MEDIUM
S43–S47 (L1465–1512) are detailed imperative specs whose freeze exists only at L1440–1445 above
them; S48–S51 (L1514–1520) depend on the frozen sessions and have **no** freeze annotation.
S29's deferral (L465–471) is stated after its "Build (not started)" spec. SPEC §5.2.2's auth
option menu (L227–233) and §6's 24 phases similarly read as live.

### R4.6 · Stale imperative tails in ops docs — MEDIUM
QUESTION_GENERATION.md ends (L447–450) with an undated 2026-08-06 "**Next:**" instruction naming
Mistral Large 3 as the only viable generator — superseded by the 2026-08-11 re-measurement at
L269 (Sonnet 4.5) — as the last thing a reader sees. HINT_SOLUTION_REVIEW.md §8 (L519–531) lists
"4. Validation run … **First paid step**" unticked while §5 (L268–302) reports that run's results
— a reader following §8 would re-buy a completed measurement. U7_CHECKPOINT_CONSOLIDATION §8.2/
§9.2 (L269–270, 281–282) recommend and ask about building `learning_sessions`, which was built the
same day (migration `6538a95bc990_d331_learning_sessions.py`; PROGRESS.md:1084 "THE EXTRACTION
HALF IS BUILT, D-332") — and PROGRESS.md:1433 still gates U7 on "the four answers in §9".

### R4.7 · INCIDENT_RESPONSE.md describes shipped drills in future tense — LOW
L295–302: "S34 … is where failure drills … get built and exercised for real" — S34 shipped
2026-07-24 (ROADMAP.md:575–576). Correct pointer, wrong tense; a reader concludes no DR procedure
exists.

---

## §5 — Resolved decisions that still look open (and one inverse)

### R5.1 · CLAUDE.md's own index keeps OPEN_DECISIONS open — HIGH
CLAUDE.md:38–40 ("everything still open … ten decisions … the answer is often 'ask the user'") vs
OPEN_DECISIONS.md:3/8 (all 14 items answered/parked; "Nothing in this file is awaiting a
decision"). This is the resolved-looks-open pattern *in the one file every session loads*.

### R5.2 · FINAL_ARCHITECTURE.md presents four decided questions as live — HIGH
L33 "Status: decision-gated, not yet made" and L110 "D-004 is still 'proposed,' not 'accepted'" —
D-004 was accepted 2026-07-22 (DECISIONS.md:29), six days before this file's last edit. Questions
1–4 of L169–178 (ECS-vs-EKS, integration shape, single-vs-multi instance, RDS-vs-Aurora) are all
decided.
**Inverse risk, same section:** question 5 (SPEC §5.33.3's six-schema logical split, L179–180)
appears to be **genuinely undecided and recorded nowhere else** — OPEN_DECISIONS declares nothing
open, ARCHITECTURE.md never mentions a schema split. If FINAL_ARCHITECTURE is archived without
extracting it, an unmade decision disappears.

### R5.3 · S42_OPEN_QUESTIONS.md tables resolved items as open, one marked "cannot be deferred" — MEDIUM
C1/C2/C3/C8 remain full table rows (L74–76, 81) — C3 at 🔴 "미룰 수 없음" — after the same file's
resolution ledger (L17–21) declares them closed; L110 still instructs sending the answered C3 ask
as one of only two live actions.

### R5.4 · AUDIT_FINDINGS.md's residual open-looking strata — MEDIUM
The file documents this failure five times over (L114–116: five headings said "not fixed" after
fixes shipped; AUD-F-16 read `Open` for two weeks). Residuals verified: AUD-F-27's heading says
both "✅ fixed" and "not fixed" (L4521); "Status: open, Phase 0B" bullets survive inside closed
entries (L1804, 1985, 2345); "Fix shape (Phase 0B)" blocks — several known-wrong — retained
verbatim inside closed findings (L1439, 2759, 3032, 3090, 5415–5422).

### R5.5 · Stale "stay unapplied" lines against applied decisions — MEDIUM
OPEN_DECISIONS.md:15 "D-401 and D-406 stay unapplied until it exists" vs DECISIONS D-419
(2026-08-18): both applied. OPEN_DECISIONS.md:35 "staging numbers nobody has read" vs
U7_CHECKPOINT_CONSOLIDATION.md:38 (read 2026-08-14). OPEN_DECISIONS.md:3 "Every decision … answered
on 2026-08-14" vs items 11–14 decided 08-17/08-18 (L353, 403, 452, 545) — patched by the L8 banner
but never amended.

### R5.6 · HINT_SOLUTION_REVIEW.md's front page describes a pre-pilot world — MEDIUM
L3 "the loop around them is not built" vs L9–10 "`review_loop.py` implement[s] … the bounded loop"
(six lines apart); L378 reviewer C "measured" vs L440 "reviewer C does not yet exist"; the doc's
horizon ends at D-261 while D-262–D-269 (pilot, recall fix, repairs applied 44→0) are absent —
zero grep hits for any D-262+ ID.

### R5.7 · Genuinely open items that look closed or are tracked nowhere — MEDIUM (inverse class)
FIRST_VISIT_NOTICE.md:237's "the three gaps in §5 need a product decision before S45" is open and
recorded in no decision-tracking document. S42_SECURITY_REPORT.md has no send-status field —
unsent is indistinguishable from sent-and-unlogged, and nothing after 2026-08-02 tracks it.
S42_OPEN_QUESTIONS' A4/A5 are decisions awaiting a person, absent from OPEN_DECISIONS ("Nothing …
awaiting a decision"). The answer-cache decision (PROGRESS.md:31–33) lives only in the top-of-file
stack.

---

## §6 — Unclear decision supersession

### R6.1 · DECISIONS.md status tags are never updated; supersession lives only in body text — HIGH
The preamble declares `proposed | accepted | superseded` (L4); the tag is not maintained: D-004
(materially rewritten twice, still "accepted"), D-135 (premise proven false by D-138, still
"accepted"), D-121 §3 / D-129 §5 (claims refuted by D-122/D-132, uncorrected in place), D-344's
metadata still reading "Status: stopgap, **removed by D-349**" while its own correction says
"**D-349 therefore removes nothing**" (L24671 vs L24705–24707 — the stale clause deliberately
kept, corrected only in the body). Non-standard statuses appear without definition ("accepted as
launch-blocking carry-over", L2843; "measured, not acted on", L20916; "⏸ partial", L20679).
**Consequence:** a scan of headings by status finds zero supersessions; every one of the ~40
supersession/reversal chains the readers catalogued is discoverable only by full-text reading.
**Blocks:** any mechanical derivation of "which decisions are current."

### R6.2 · Phantom decision IDs: cited, never written — HIGH (verified directly)
**D-190, D-191, D-192** — cited 18× in code and 8× in docs, never written; the log itself records
the gap as a meta-note (DECISIONS.md:16101 "referenced everywhere, never written") without
reconstructing entries. **D-329** — referenced by D-330/D-334/D-335; exists only as a `####`
sub-heading inside D-330 (L23582), never as an entry. **D-363** — referenced at DECISIONS.md:
25728/25894 and PROGRESS.md:891/2214; no heading anywhere. Additionally, informal sub-entries
(`D-195 §5`, `D-206 addendum`, `D-210 disposition`, `D-212 addendum` embedded inside D-211's
entry) and one three-ID heading (`D-266/267/268`, L19182) make ID-grep unreliable — a failure
D-223 itself demonstrates (L16019: the log's author mis-grepped their own log).
**Blocks:** any citation-integrity pass; any tooling keyed on `## D-nnn` headings.

### R6.3 · The three audit registers have colliding ID namespaces and no supersession statement — HIGH (verified directly)
AUDIT_FINDINGS.md (frozen 2026-08-05) uses `AUD-L/C/X/F-nn`. AUDIT_LIVE_2026_08_17.md **reuses
the entire `AUD-L-01…AUD-L-19` range with unrelated meanings** (its AUD-L-01 = expired-token
dashboard loop, L16, vs the /dev/token finding at AUDIT_FINDINGS.md:44/663; its AUD-L-17 =
child-chooser-no-exit, L43, vs the finding renumbered to AUD-L-19 there *because of a previous
collision*, AUDIT_FINDINGS.md:182–201). AUDIT_2026_08_16.md uses a third scheme (`P1-1…P1-10`)
plus later `AUD-CHAT-nn`/`AEL-nn`/`EDGE-CHAT-nn` labels shared with AUDIT_LIVE. No document
states which register a bare `AUD-L-nn` in DECISIONS/PROGRESS refers to, and AUDIT_FINDINGS
mentions neither successor. The AUD-L-17→AUD-L-19 renumber was itself applied per-reference, with
ranges deliberately left ambiguous (AUDIT_FINDINGS.md:195–200).
**Blocks:** every cross-document finding lookup after 2026-08-16.

### R6.4 · Session-label collisions: C1, S43…S66, S45 — MEDIUM
**"C1"** names both the chat-content session (= S17; expansion-plan.md:714, ROADMAP.md:203) and
the 2026-08-11 full-taxonomy content-seeding session (ROADMAP.md:1718, CONTENT_COVERAGE.md:3).
**"S43"** is both ROADMAP's frozen IcProfileAdapter session and a self-applied label on the
D-115/D-116 work (flagged in-text, DECISIONS.md:5742–5744); PROGRESS's log also uses unnumbered
"S44"–"S66" labels for Phase 0B sessions (PROGRESS.md:12644–13695) that collide with ROADMAP's
S44–S47 frozen sessions — PROGRESS.md:13559's completed "S45 (unnumbered)" vs ROADMAP:1501's
unstarted consent-session S45, which FIRST_VISIT_NOTICE.md:235 names as its owner. **"§2.6"**
resolves to INTEGRATION_PLAN, not SPEC (R3.8).
**Blocks:** unambiguous session references in any reconciled index.

### R6.5 · Supersession direction runs opposite to citation direction in the S42 set — MEDIUM
S42_OPEN_QUESTIONS.md supersedes S42_DISCOVERY §7 on ask currency but cites DISCOVERY as its
evidence base (L3); DISCOVERY carries no forward pointer. S42_DISCOVERY corrects INTEGRATION_PLAN
twice (L130 "28 columns", L265–267 liveness endpoint) — INTEGRATION_PLAN.md:47/265/528 still
carries the uncorrected text; the correction lives only in the correcting document. Likewise
INTEGRATION_PLAN §8 patches §1/§5 by reference ("§5's S42 row shrinks accordingly", L615) without
editing them.

### R6.6 · Self-retirement instructions whose trigger fired without the act — LOW
FINAL_ARCHITECTURE.md:183–185 ("Once decided, update this file (or fold it back into
ARCHITECTURE.md and delete this one) rather than letting the two drift apart") — the decision was
made 2026-07-22; the fold never happened; the drift it predicted is R2.1/R5.2.
INTEGRATION_PLAN.md:3 supersedes "the two earlier drafts of this document" — drafts that no longer
exist, so the supersession is unverifiable.

---

## §7 — Additional class: discovery and index integrity (what CLAUDE.md makes invisible)

### R7.1 · Thirteen of twenty-five docs are absent from CLAUDE.md's index — HIGH
Verified list (inventory §1): ARCHITECTURE, FINAL_ARCHITECTURE, INTEGRATION_PLAN, AUDIT_FINDINGS,
AUDIT_2026_08_16, CONTENT_COVERAGE, ENROLLMENT_FAQ_APPROVAL, FIRST_VISIT_NOTICE, S42_ORG_ASKS,
S42_SECURITY_REPORT, U7_CHECKPOINT_CONSOLIDATION, and both docs/plans/ files (S42_OPEN_QUESTIONS
appears only outside the index, at L62). Consequences with teeth:
- **ARCHITECTURE.md** — the file every session must *update* (end-session skill) is not one any
  session is told to *read*; its ~70 invariants get re-derived by defect (its own recurring theme).
- **INTEGRATION_PLAN.md** — the document the D-152 freeze is *about* is undiscoverable from the
  file that states the freeze (pairs with R4.1).
- **ENROLLMENT_FAQ_APPROVAL.md** — claims to be "the only launch-checklist item gating the guest
  journey's canonical question" (L88–89) and is invisible at session start.
- **S42_SECURITY_REPORT.md** — the declared single security document; a session reading only the
  index would re-derive it from DISCOVERY §6.
- **U7_CHECKPOINT_CONSOLIDATION.md** — unindexed yet PROGRESS.md:1433 gates session U7 on its §9.
- **"The audit"** is ambiguous: three audit registers exist; the index names one.
**Blocks:** any reconciliation of authority — the index is the de-facto authority mechanism.

### R7.2 · Committed outbound drafts vs the stated no-committed-drafts rule — MEDIUM
INTEGRATION_PLAN.md:619: outbound communication drafts are kept "outside this repo (gitignored …
not committed)". Three committed drafts exist: S42_ORG_ASKS.md, S42_SECURITY_REPORT.md,
ENROLLMENT_FAQ_APPROVAL.md. Either the rule was silently superseded or the files violate it; no
document says which. The two org-facing S42 drafts also implement opposite policies on mentioning
the committed-credentials issue (S42_ORG_ASKS.md:366–371 excludes it from any sent message;
S42_SECURITY_REPORT.md:88–89/151–153 includes it as known context).

### R7.3 · Dangling and out-of-repo references — LOW
DECISIONS.md:3842 references `docs/codebase-analysis/` — no such directory exists in this repo
(verified); the intended referent is `../IntelliChoice-web/docs/codebase-analysis/`
(S42_DISCOVERY.md:8), i.e. an out-of-repo path cited as if local. ENROLLMENT_FAQ_APPROVAL.md:93–94
instructs syncing a `knowledge-content copy/` directory that no longer exists (deleted, D-253).
ROADMAP.md:5 and 326–331 point readers into docs/plans/ files without noting they are historical.

---

## §8 — Additional class: status-marker and summary-layer unreliability

### R8.1 · Summary lines contradicting their own tables — a documented, recurring pattern — HIGH
Four self-documented instances: TRACEABILITY.md's heading said "turns on one open discrepancy"
after T-02 was dispositioned (corrected 2026-08-17, L74–78); TRACEABILITY.md:641–645's "Open:
none" beside an open T-02 in the same commit; PROGRESS.md's summary block contradicting its own
session log (D-174-era "uncommitted" vs deployed, PROGRESS.md:12981–12984); AUDIT_FINDINGS.md's
count line "wrong three times" (L159–169). The corpus's own repeated lesson — "a summary that
agrees with the claim you want to make, above a table that contradicts it, is how a rubric passes
itself" (TRACEABILITY.md:645) — is a *structural* property of this documentation: summaries are
written by hand above machine-checkable detail, and they drift.
**Blocks:** trusting any headline/status line anywhere in the corpus without reading the table
under it. Any reconciliation should either generate summaries mechanically or date-stamp them.

### R8.2 · ROADMAP status glyphs are incomplete and internally denied — MEDIUM
18 session headings carry no glyph (S1–S16, S19, S33) while L2168–2169 asserts they are all done;
W5's ⚠️ is the only such glyph and is defined only in a milestone banner (L2773); "every skill
stocked" was reported met four times before it was true (ROADMAP.md:2106–2109, the file's own
admission).

### R8.3 · Verbatim duplicate headings/blocks — LOW (verified)
PROGRESS.md:15451/15453 — the `### S20` heading appears twice in a row verbatim. ROADMAP.md:
1667–1673 ≡ 1680–1686 (duplicated "Four defects" paragraph); two "Session C1" headings (L1718,
2084); two Phase 5 blocks (L1884, 2038). AUDIT_FINDINGS.md's Index is split into six table
fragments by stray blank lines (L74–101), breaking naive parsers, and rows end in dangling
"Original: |" cells (L42, 59, 60, 89).

---

## §9 — Additional class: freeze-coherence (D-152's visibility is inverted)

### R9.1 · The freeze is most visible where least needed, and absent where it binds — HIGH (summary risk)
Verified visibility of D-152 across the documents whose subject it governs:

| document | freeze visible in-file? | risk if read standalone |
|---|---|---|
| S42_OPEN_QUESTIONS.md | ✅ dedicated ⛔ banner + re-entry protocol (L9–13, 108–113) | low — the model citizen |
| CLAUDE.md | ✅ full ⛔ section (L54–72) | names S42_OPEN_QUESTIONS only; never names INTEGRATION_PLAN, S42_DISCOVERY, or S42_ORG_ASKS |
| ROADMAP.md | ✅ at L1440–1445 | S48–S51 unannotated below it |
| PROGRESS.md | ✅ reconfirmed banner (L65–71) | — |
| **INTEGRATION_PLAN.md** | ❌ zero mentions | directs all four forbidden actions (R4.1) |
| **S42_DISCOVERY.md** | ❌ zero mentions | §7–§9 read as live work (R4.4) |
| **S42_ORG_ASKS.md** | ❌ zero mentions (predates it) | three "Send now" markers (R4.3) |
| SPEC.md §5.2.2 | ❌ | auth-option menu reads live |
| S42_SECURITY_REPORT.md | (states the *production* freeze in its own words, L8–10) | none — its work item is the freeze's designed exception |

**Why this is one risk and not nine:** the freeze is the project's single most consequential
standing instruction, and its documentation is concentrated in the files a reader is *least*
likely to be inside when the freeze matters. The reconciliation cost is one banner per ❌ row.

---

## Category coverage statement

All six requested categories produced findings (§1–§6 above; none came back empty). Three
additional structural classes were found and registered (§7 index/discovery integrity, §8
summary-layer unreliability, §9 freeze-coherence). Every entry cites file:line evidence collected
by full-document readers or verified directly by this session; the highest-severity items
(R4.1, R6.2, R6.3, R2.2, R7.1, R9.1, R1.1, R6.1, R8.1, R5.1, R5.2's inverse, R4.2, R4.3) were each
confirmed against the primary source, not inferred from a single agent's report.

## What this register deliberately does not do

Per the audit's charter: no document was modified, no information reconciled or compressed, no
supersession banner added, no file renamed. The "Blocks:" lines name the future reconciliation
steps each risk gates; the candidate-role recommendations live in the inventory.
