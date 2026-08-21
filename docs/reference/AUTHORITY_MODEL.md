# AUTHORITY_MODEL.md — which document wins, and how conflicts are resolved

**Status: IN FORCE since 2026-08-20** — the documentation reconciliation migration executed that
day, promoted this file to `docs/reference/AUTHORITY_MODEL.md`, and summarised its precedence
ladders in `docs/PROJECT_STATE.md` §11.
**As-of:** 2026-08-20. **Last product-code commit at authoring:** `344f016`. **Deployed staging
build:** `gha-44a12dfc9549` (10 product commits behind).
**Creates no new architectural decisions and answers no open user decision.** Where a rule below
would need a judgement the user has not made, the rule says "ask", not "assume".

---

## 0. Why this document exists

The audit behind this proposal found 49 documentation risks, 18 of them HIGH (counts derived mechanically from `DOCUMENTATION_RISK_REGISTER.md`'s entry headings, 2026-08-20) — HIGH meaning *a reader
following the document as written would do something wrong or forbidden, or believe a materially
false project state*. Almost none were caused by a document being wrong when written; they were
caused by the corpus having no ratified answer to two questions: when two documents disagree, which
is authority; and when a document is silent about its own vintage, how should a reader treat it. This
file answers both. It holds no project facts, only rules for deciding which project facts to believe,
and every rule cites the observed failure that produced it.

---

## 1. The six semantic layers

Every statement in this corpus belongs to exactly one of six layers. They answer different questions
and are falsified by different evidence, so **they must never be flattened into a single "the docs
say" voice.** Flattening is the root cause of the R2.1/R2.2/R4.1/R5.2 family: a projection read as
as-built, an accepted risk read without its expiry, a frozen plan read as a work order.

| Layer | The question it answers | Falsified by |
|---|---|---|
| Normative truth | What is *required*? | An accepted decision that changes the requirement |
| Observed repository state | What is *in the code at this revision*? | Reading the code at that revision |
| Deployed state | What is *running in staging right now*? | Observing the deployed build |
| Historical state | What *was* true, and why we chose it | Nothing — history does not go stale, it only stops being current |
| Open work | What still needs *doing*? | Doing it (then the item is deleted, not archived in place) |
| User judgment | What has *not been decided*, and cannot be decided by engineering | The user deciding it |

A statement spanning two layers is split, not compressed. "The escalation email path is implemented"
is a repository-layer claim; "…is live" is a deployed-layer claim; on 2026-08-20 the first is true
and the second is false. One sentence meaning both misleads a reader without any individual word
being wrong.

---

## 2. Roles: who owns what

Each subsection states the **layer**, what the document is **authority for**, what it is
**explicitly not authority for**, and the **discipline** that keeps it trustworthy.

### 2.1 `docs/PROJECT_STATE.md` — the reconciled snapshot and navigation layer

- **Layer:** a derived, *reconciled view over* the observed-repo, deployed, open-work and
  user-judgment layers. **Authority for:** where to look, what is open, what is blocked and why, what
  is unknown. The canonical entry point — the first file an agent reads at session start.
- **NOT authority for:** anything. **PROJECT_STATE is never primary evidence.** It is a snapshot of
  primary evidence taken on a date; if it disagrees with the code, the code wins (§4.4). It also
  never restates a requirement — it links to SPEC.
- **As-of dating.** Every current-state claim carries the date it was verified and, for deployed
  claims, the build it was verified against. A dated claim can go stale; an undated claim lies.
- **Delete-on-resolve.** When a work item closes it is **deleted** from PROJECT_STATE; the resolution
  is recorded in DECISIONS.md and git, not accumulated here. Countermeasure to R1.1 — PROGRESS.md's
  "Current status" block became ~1,800 lines of strata in which the same metric read three different
  values at three depths, while being the project's actual sequencer.
- **No chronology.** No session log, no diary, no per-session narration. If it reads as history, it
  belongs in git commit messages or the archive.
- **Staleness rule (fail-closed).** If the snapshot date is **more than 14 days old**, or a
  **product-code commit has landed after the snapshot header's recorded last-product-code commit**
  (docs-only commits do not by themselves invalidate the snapshot — HEAD merely moving is not the
  trigger), **or the deployed staging image tag no longer matches the snapshot header** (a manual
  deploy moves neither HEAD nor the date), the current-state and known-drift sections
  are **unverified** and must be re-verified against primary evidence before being acted on. Do not
  silently trust them; do not silently delete them either.

### 2.2 `docs/SPEC.md` — normative truth

- **Layer:** normative. **Authority for:** what the system is required to do — the token claim set,
  the eleven first-visit disclosures, the §5.8.5 validation checks, the gain formula, retention
  windows, verbatim user-facing strings, the §5.29 failure matrix, the §5.30.1 Bedrock wire
  allowlist, the §5.33.4 SLO targets. Where SPEC and any other document disagree about a
  *requirement*, SPEC as amended wins.
- **NOT authority for:** what is built (ARCHITECTURE and the code), what is deployed, or work
  sequencing. **§6, the 24-phase implementation sequence, is historical** — superseded by actual
  delivery and by the roadmap freeze; read it as a record of an early plan, not as instructions.
- **Discipline — mandatory in-place dated amendment (the D-351 pattern).** SPEC's central failure
  (R1.4) is that ~220 decisions amended it from outside while only two amendment markers exist in
  4,210 lines. Going forward: **when an accepted decision changes a requirement, the SPEC text is
  edited in place, at the point of the requirement, with a dated marker naming the decision.** The
  decision keeps the rationale; SPEC keeps the requirement. An amendment living only in DECISIONS.md
  is a known defect, tracked as SPEC drift in PROJECT_STATE until folded back. Amending a SPEC §5
  requirement obliges **re-checking every TRACEABILITY row citing that section in the same change** —
  an orphaned row is a gap, not a pass (§4.8).

### 2.3 `docs/DECISIONS.md` — the append-only rationale system of record

- **Layer:** normative for accepted decisions, historical for the reasoning, the rejected options and
  the supersession trail. **Authority for:** *why* every non-obvious choice was made; supersession
  chains; correction trails; measured constants; incident post-mortems. It is the only record of what
  was rejected and why — what stops a session re-litigating a settled question.
- **NOT authority for:** open work. A decision records a judgment made; it is not a todo list, and
  anything still to be done lives in PROJECT_STATE. Nor is it authority for *current* state: an
  accepted decision proves intent at its date, not that the code matches (§4.2).
- **Append-only bodies, mutable status line.** Entry bodies are not rewritten in place. The one
  mutable field is the status line, with a fixed enum: `proposed` / `accepted` /
  `superseded-by D-xxx` (the declared vocabulary — see §5.4; extensions need a recorded convention
  decision). This exists because of R6.1 — the declared `proposed | accepted | superseded`
  vocabulary was never maintained, and a scan of headings by status found **zero** supersessions
  across roughly forty real chains, every one of which lived only in body prose.
- **Back-annotation on supersession.** The superseding entry edits the superseded entry's status line
  to point forward. Supersession discoverable only by reading the newer entry is not discoverable at
  all — readers arrive at the old ID.
- **Phantom IDs are annotated, never fabricated.** `D-190`, `D-191`, `D-192`, `D-329` and `D-363` are
  **cited but never written** (R6.2): D-190/191/192 are cited 18 times in source and 8 in docs, D-329
  exists only as a sub-heading inside D-330, D-363 is referenced four times with no heading anywhere.
  The index marks each `cited-never-written`. **Never invent content for a phantom ID.** If a citation
  to one is load-bearing, surface it as a finding and — if the user agrees — write a *new* entry
  stating what was done. Never backfill the phantom as though it had always existed.

### 2.4 `docs/ARCHITECTURE.md` — the single as-built authority

- **Layer:** observed repository state, curated. **Authority for:** what is and is not built; the
  cross-cutting invariants with their D-number provenance; the dataflow diagrams; the storage-split
  table; the egress/sink table; the measured capacity table with its extrapolation ban. There is
  exactly **one** architecture document; the second (`FINAL_ARCHITECTURE.md`, a 2026-07-21 projection
  whose filename made it read as definitive — R2.1/R3.1) is archived under a dated name.
- **NOT authority for:** which revision is deployed (snapshotted in PROJECT_STATE), what is required
  (SPEC), or what remains to be done (PROJECT_STATE).
- **Discipline:** ARCHITECTURE may carry one explicitly-marked block titled **"Open architecture
  questions (undecided — do not treat as designed)"**, holding questions genuinely unmade that would
  otherwise be lost when a projection document is archived. The SPEC §5.33.3 six-schema logical split
  is the founding entry, with "production schema design" as its reopen condition. **Content in that
  block is not design and must never be implemented from.** Each entry also gets a one-line row in
  PROJECT_STATE's deferred section. Creating such an entry is not creating a decision.

### 2.5 `docs/TRACEABILITY.md` — the living criterion-1 instrument

- **Layer:** observed repository state, as evidence about *coverage*. **Authority for:** whether each
  launch-scope SPEC §5 requirement is traced to implementation *and* to a falsifying test; the
  launch-scope determination and its exclusions; the four-verdict vocabulary; the T-01/T-02
  dispositions.
- **NOT authority for:** the requirements themselves (SPEC), the as-built design (ARCHITECTURE), or
  work scheduling. It is a fifth active file because evidence-of-coverage merges into none of the
  other four questions.
- **Discipline — its method rule is part of this authority model: "unverified counts as not
  traced."** A row without checked evidence is a gap, not an optimistic pass — the same fail-closed
  instinct the product's non-negotiables use for attendance (unknown ≠ present), applied to
  documentation. TRACEABILITY twice caught its own summary lines contradicting its own tables and
  kept both, annotated, as method — the origin of §5.2.

### 2.6 `docs/reference/` — durable, read-on-demand

- **Layer:** mixed; each file declares its own layer in its own banner. **Authority for:** whatever
  its own scope says, and only that. Reference content is true *regardless of which session is
  running* — an incident runbook, a pipeline design, a frozen audit register, the reconciliation
  provenance registers. Not read at session start; read when the task touches it.
- **Discipline:** every reference file whose content can go stale carries an **as-of banner**
  (measurement snapshots, coverage tables, audit registers). Files under `reference/integration/`
  additionally carry a line-1 D-152 freeze banner (§5.7). A reference file with no banner and no date
  is treated as unverified (§5.6), not as current.

### 2.7 `docs/archive/` — history

- **Layer:** historical. **Authority for:** provenance and forensics — what we believed, when, and
  why. History is genuinely authoritative *about the past*, which is a real use: it is how you
  reconstruct whether a rule was reasoned or accidental.
- **NOT authority for:** anything current. **Nothing under `archive/` is ever linked from SPEC,
  ARCHITECTURE, TRACEABILITY or CLAUDE.md as normative.** PROJECT_STATE may cite an archived file,
  but only as the *source* of a work item, never as a statement of current state.
- **Discipline:** every archived file gets a prepended banner naming the archive date, the reason and
  the superseding document, plus `archive/README.md` as the index. The banner is load-bearing:
  `FINAL_ARCHITECTURE.md` carried its own fold-back-and-delete instruction, the trigger fired
  2026-07-22, the act never happened, three HIGH risks grew out of the gap (R6.6). **A self-retirement
  instruction is not a mechanism.**

### 2.8 Implementation, tests and configuration — primary evidence for repository state

- **Layer:** observed repository state. **This is the primary evidence.** Code, tests, migrations,
  Terraform and config are what the repository *is*; every document about them is a description that
  can drift. A failing test is a fact; a migration that replays is a fact.
- **Qualification:** primary evidence is revision-scoped. "The code does X" means "the code at
  revision R does X" — and across a deploy gap the revision always matters, so name it.
- **Caveat:** a *green* suite is weaker evidence than a red one. The Playwright suite was green on the
  same build that carried two live P1 defects. Absence of a failing test is not evidence of correct
  behaviour.

### 2.9 Deployed and runtime evidence — primary evidence for deployed state

- **Layer:** deployed state; also primary evidence, for a different question. **Authority for:** what
  staging actually does right now — observed responses, CloudWatch data, the deployed image tag, live
  latency numbers, which tables exist in the staging database.
- **Discipline — LB-05, the revision-qualification rule: every live number carries the build SHA it
  was measured on.** Repo HEAD and staging are not the same revision. At authoring, staging runs
  `gha-44a12dfc9549` and HEAD is `344f016`, ten commits apart — so any live latency figure is a
  *pre*-D-423 number, a repo-side fix is inert until a deploy, and "the docs say X but staging does Y"
  may mean nothing worse than "X has not shipped". The reciprocal caution matters equally: **never
  credit staging with behaviour that exists only on HEAD.** And symmetrically: **never credit HEAD
  with behaviour that exists only on the deployed build** — a rollback, revert or branch deploy can
  put staging on a revision that is not an ancestor of HEAD.

### 2.10 Git history — provenance and forensics only

- **Layer:** historical. **Authority for:** when something changed, in what order, by which commit.
  It is the tiebreak for "which of these two dated claims is older", and the home for per-session
  narration once PROGRESS.md is archived.
- **NOT authority for current intent — ever.** A commit message states what its author believed at
  the moment of committing. It is not a decision record (that is DECISIONS.md), and a commit that
  contradicts an accepted decision is evidence of drift, not an amendment to the decision.

---

## 3. Precedence

There are **two** ladders, because there are two different questions. Using the wrong ladder is
itself a failure mode: SPEC does not tell you what is running, and staging does not tell you what is
required.

### 3.1 Ladder A — "what is required"

1. **SPEC.md as amended by accepted DECISIONS entries.**
2. Where an accepted decision is **newer** than the SPEC text it touches, **the decision wins** and
   the SPEC text is stale.
   - **(2a) A status line of `accepted` is not evidence.** Only 8 of ~120 supersession chains were
     back-annotated at migration (`STATUS-TAG-CONVENTION`: at least eleven stale `accepted`/
     `implemented` tags read as active); grep the topic for later entries before reasoning from any
     decision.
3. **Fold-back obligation.** A decision that has effectively amended SPEC is not a stable end state:
   the amendment is folded back into SPEC in place, dated, citing the D-number (§2.2), and until it
   is, the divergence is recorded as SPEC drift in PROJECT_STATE. The obligation falls on whoever
   accepts the decision, not on a later cleanup pass — that pass is what did not happen ~220 times.
4. Nothing else is normative: not a plan, not a roadmap "Done when", not a diagram, not a comment.

### 3.2 Ladder B — "what is true right now"

1. **Primary evidence** — code/tests/config for repository state (§2.8); runtime observation for
   deployed state (§2.9). Always revision-qualified.
2. **PROJECT_STATE.md's dated snapshot** — trusted only within its staleness window (§2.1).
3. **Any archived document** — never authority for current state; consulted for provenance only.

An accepted decision sits on Ladder A, not Ladder B: it tells you what *should* be true. Confusing
the two is §4.2, the subtlest conflict in this model.

### 3.3 The layers never flatten

No precedence rule may make one layer overwrite another. Ladder A settles requirement disputes;
Ladder B settles current-state disputes. Neither can promote a historical claim to current, demote a
requirement because the code differs, or merge repository and deployed state into one status. When a
fact differs between layers, **state both, each with its layer and its date** — a correct answer, not
an unresolved one.

---

## 4. Conflict protocols

Each protocol is **detect → do → record**. "Record" is never optional: an unrecorded resolution is a
resolution that will be re-litigated.

### 4.1 SPEC text vs an accepted decision

- **Detect:** SPEC states a requirement; a DECISIONS entry with status `accepted` and a later date
  states a different one. Live examples: §5.8.1, §5.33, §5.28.2, §5.17, §5.2.2, §5.32.1, §5.15.4,
  and §5.15.2 (retention windows — D-333 governs 30/90/180 plus a chat-checkpoint clock SPEC has no
  row for).
- **Do:** the **newer accepted decision wins**. Implement and reason from the decision; do not treat
  the SPEC text as a second opinion. Before applying this rule, verify the `accepted` label itself:
  check for later entries on the same topic (§3.1 item 2a) — supersession may live only in body prose.
- **Record:** flag the SPEC section for amendment and add a SPEC-drift row to PROJECT_STATE's
  known-drift section. If the fold-back is in scope for the current work, do it in place with a dated
  marker citing the D-number; if not, the drift row is the receipt that it is still owed.

### 4.2 A decision's intent vs the code

- **Detect:** an accepted decision says the system does X; the code at HEAD does Y.
- **Do:** **neither side automatically wins.** **Precondition: first check whether both sides are
  explicit user decisions.** If they are, this is not a drift case — no engineering rule (recency,
  code behaviour, supersession heuristics) can break the tie. Route to §4.6 and record it as an open
  user decision. Live example: D-322 §7 versus D-341 (`DIFFICULTY-TIERS-CONFLICT`, UD-12(a)).
  Three causes need three different actions: (a) the code
  drifted and should be fixed; (b) the decision was superseded and never back-annotated — check
  DECISIONS for a later entry on the same topic *before* concluding anything, since roughly forty
  supersession chains exist only in body prose (R6.1); (c) the divergence is genuine and unexplained.
- Case (c) is a **finding, not a task.** **Never silently "fix" working code to match an old
  decision.** The decision may be the thing that is wrong, and a silent conforming edit destroys the
  evidence that would have shown it.
- **Record:** a known-drift entry naming both sides, and surface it to the user. If the user rules,
  the ruling becomes a new DECISIONS entry that back-annotates the old one.

### 4.3 Repository code vs deployed staging

- **Detect:** HEAD and staging exhibit different behaviour **in either direction** — including a
  deployed build that is not an ancestor of HEAD (revert, rollback, branch deploy) — or a live
  measurement disagrees with a repo-derived expectation. At authoring, the whole B4 escalation series (D-420/421/422), C8
  and the D-423 docs are on HEAD and undeployed; `chat_escalation_sends` does not exist in staging.
- **Do:** **both statements are true in their own layer.** State both, revision-qualified:
  "implemented at `344f016`, not present on `gha-44a12dfc9549`". Do not average them; do not call
  either one wrong.
- **Never backport.** Do not edit repository documents to describe deployed behaviour as if it were
  the design, and do not describe HEAD behaviour as live. The deploy gap is a scheduling fact, not a
  documentation defect to be written away.
- **Record:** the dual status lives in PROJECT_STATE's repo-vs-deployed section, with both revisions
  in the snapshot header so downstream claims inherit them.

### 4.4 PROJECT_STATE vs primary evidence

- **Detect:** PROJECT_STATE says a thing is open, closed, present or absent; the code, the test run,
  or the live observation says otherwise.
- **Do:** **evidence wins, immediately and without deliberation.** PROJECT_STATE is a reconciled
  navigation layer, not primary truth (§2.1).
- **Record:** correct PROJECT_STATE in place — delete a resolved item, restate a changed one — and
  note *why* it was stale (snapshot predates the change, HEAD moved, a deploy landed). That note is
  the signal for whether the 14-day rule and the end-of-session ritual are working.

### 4.5 An archived document vs current state

- **Detect:** an archived plan, projection or audit describes the system, and it does not match.
- **Do:** **current state wins definitionally** — the archived document was true about its own date
  and makes no claim about today. No investigation, no correction to the file; its banner says so.
- **The one case needing action:** the archived document reveals a **forgotten obligation** — a
  standing rule, an accepted risk with an expiry condition, an unmade decision — that no active
  document carries. Two real instances: `FINAL_ARCHITECTURE.md`'s open question 5, and the branding
  plan's BD3 do-not-revert rule sitting inside a file labelled "planned, not started".
- **Record:** the obligation re-enters as a **PROJECT_STATE work item citing the archive as its
  source.** It does not re-enter by un-archiving the file, nor as a normative link into `archive/`. A
  standing rule is extracted to its proper active home *before* the source file is archived —
  extraction precedes archival, always.

### 4.6 An open user decision affects implementation

- **Detect:** progress requires an answer only the user can give — a product judgement, a spend
  authorisation, a deploy decision, a scope cut. Tracked as `UD-1` … `UD-12` in PROJECT_STATE's
  open-user-decisions table, with full analyses in `reference/reconciliation-2026-08/USER_DECISION_QUEUE.md`.
- **Do:** **do not infer the answer.** Do not pick the recommended option and do not treat a
  recommendation as an answer — the record contains three decisions the user made *against* their own
  written recommendation, which is precisely why inference is banned. Apply the **Phase-4 default
  safe action** if one is recorded (the option that preserves optionality and creates no irreversible
  state). If none exists, **stop and ask.**
- **Never convert a UD into a `D-xxx` without the user.** A UD is a question; a D-entry is a judgment
  that was made. Minting a decision ID for an unanswered question launders an assumption into the
  system of record, where the next session reads it as settled.
- **Record:** if the user answers, write the DECISIONS entry, remove the UD row, note the outcome. If
  the default safe action was applied instead, say so where the work is recorded — the UD stays open.

### 4.7 PROJECT_STATE vs the reconciliation registers

- **Detect:** `PROJECT_STATE` and `reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md` (or
  the queue) disagree about whether an item is open.
- **Do:** **PROJECT_STATE is authority for *whether* an item is still open; the register is authority
  for *why* it was opened and what the evidence was.** A register row with no `PROJECT_STATE` row is
  closed-or-stale, not open. The register is never the trigger for work.
- **Record:** nothing in the register (it is frozen provenance); if `PROJECT_STATE` looks wrong, §4.4
  applies — evidence wins.

### 4.8 TRACEABILITY vs an amended SPEC

- **Detect:** a TRACEABILITY row evidences a requirement whose SPEC text an accepted decision has
  amended away or changed.
- **Do:** SPEC as amended wins on the requirement; the row reverts to **not traced** until
  re-evidenced against the amended text. It is not "unverified" — it is verified against text that no
  longer exists, which is worse.
- **Record:** the row is re-marked in place, never silently deleted; the amendment's marker (§2.2)
  cites the affected rows.

---

## 5. Core rules

### 5.1 Consistency is not evidence of correctness.

Two documents agreeing proves only that someone copied. The corpus's worst failures were *internally
consistent*: three files carried the same `difficulty_tiers` rule that had to be re-derived from
source at least three times because the copies drifted together into being uniformly wrong, and four
documents carried the same production security findings with no authority statement among them. To
know whether something is true, go to primary evidence — never to a second document that agrees.

### 5.2 Summary lines are date-stamped or mechanically derived

A hand-written summary above machine-checkable detail will drift, and it drifts in the flattering
direction. The corpus documented this against itself four times and stated the lesson in its own
words: *a summary that agrees with the claim you want to make, above a table that contradicts it, is
how a rubric passes itself.* Therefore (R8.1): every summary line is either **derived mechanically**
from the table it summarises or **carries the date it was written**; **a table beats a summary that
contradicts it** — always, so correct the summary and keep the table; and any count that can be
computed is computed.

### 5.3 Single home for every volatile fact

Each volatile fact — a measurement, a count, a status, a threshold, an accepted risk's expiry
condition — has **exactly one authoritative location**, and every other file **links to it, never
restates it** (R2.5). Restatement is not redundancy; it is a second lifecycle. Demonstrated cost: an
accepted P1 risk restated in the file everyone reads *without* the expiry condition that made it
acceptable, while the expiry lived only in the file nobody had indexed (R2.2). If you are typing a
number that exists elsewhere, link instead.

### 5.4 Status vocabulary is a fixed enum

Prose statuses are not statuses. Two enums, and nothing else:

- **Work items** — the eleven Phase-4 dispositions: `USER_DECISION_REQUIRED`, `ACTIVE_REMEDIATION`,
  `ACTIVE_IMPLEMENTATION`, `BLOCKED`, `DEFERRED`, `PARKED_BY_DECISION`, `DOCUMENTATION_ONLY`,
  `OBSERVATION_ONLY`, `RESOLVED`, `SUPERSEDED`, `UNKNOWN`.
- **Decisions** — the declared vocabulary: `proposed` / `accepted` / `superseded-by D-xxx`. Any
  extension (e.g. a `reversed` state) is a convention change and requires a recorded `DECISIONS.md`
  entry before use — this model does not mint one.

`UNKNOWN` is a legitimate standing state — open, never quietly upgraded — and survives as `UNKNOWN` with a named resolution step; it
is never quietly upgraded to a guess to make a table look complete. And a status is a measurement
with an expiry date: `RESOLVED` means resolved *as of a date*, and a resolved item is deleted from
PROJECT_STATE rather than left standing as a claim about the present.

### 5.5 Citation rules

- Cite **decision IDs**, **stable section anchors** or **register keys**. **Never line numbers into
  mutable giant documents** — DECISIONS.md is 28,787 lines and PROGRESS.md 16,690; such a citation is
  wrong within a session, and a wrong line number is worse than none because it looks checkable.
- **Audit IDs are always source-qualified** as `<document>:<id>` (R6.3). `AUD-L-01` … `AUD-L-19`
  exist in **two** registers with unrelated meanings — including a reused ID that had itself been
  renumbered after an earlier collision — and a third register adds a `P1-n` scheme. A bare
  `AUD-L-14` is not a citation, it is a coin flip. Same discipline for ambiguous session labels: `C1`
  names two different sessions, and `§2.6` resolves to INTEGRATION_PLAN, not SPEC (R6.4).
- Cite a phantom decision ID only as a phantom (§2.3). Never write content for one.

### 5.6 Fail-closed reading

**A document with no as-of date and no status banner is treated as unverified — not as current.**

This mirrors the product's own fail-closed rules (unknown attendance is not presence; no RAG answer
without an approved, effective, citation-supported source). The corpus's most consequential single
finding (R4.1) is a plan that, read standing alone, directs all four actions the always-loaded
instruction file forbids — not because it says anything false about its own date, but because it says
nothing about it at all.

### 5.7 Two standing framings that must never be restated inconsistently

Both are single-homed under §5.3 and are quoted, never paraphrased:

- **The D-152 integration freeze is in force.** Integration is deliberately deferred: build and test
  against the dev fakes first, then integrate. Every document describing the integration world lives
  under `reference/integration/` behind a line-1 freeze banner carrying the reopen condition. The
  freeze's visibility was inverted — loudest where least needed, absent from the three files where it
  binds (R4.1/R4.4/R9.1) — so the banner is structural, not stylistic.
- **D-310 is resolved historical remediation.** The rotation was executed on 2026-08-20. It is a
  closed incident record, **never an active exposure**. Its named surviving residuals are tracked as
  their own work items; the D-310 entry itself is history. Any text implying a live credential
  exposure is stale and is corrected on sight.

### 5.8 Gate verdicts are quoted with the reading that produced them

§2.6 criterion 1 is MET on a **written reading**, not on a count. Any launch-readiness summary carries
that reading beside the verdict (`TEST-01-CRITERION1`); an unbuilt launch requirement does not satisfy
a criterion by being out of scope. Cross-reference `DISCLOSURES-LEGAL` / UD-10.

---

## 6. Session workflows

### 6.1 Standalone Claude Code

- **Session start:** read `PROJECT_STATE.md` (`CLAUDE.md` is auto-loaded). That is the whole required
  reading. Then pull the specific SPEC/ARCHITECTURE sections the task touches and the one or two
  `reference/` files it needs.
- **During:** cite decision IDs and anchors; go to primary evidence for any current-state claim;
  apply §4 when documents disagree.
- **Session end:** update PROJECT_STATE **in place** — refresh the snapshot header dates and
  revisions, delete resolved items, restate changed ones, add newly found drift. Append a DECISIONS
  entry, with a status line, for every judgment made. Narration goes in the git commit message. **No
  chronology in PROJECT_STATE.**
- **Explicitly not a workflow:** anything requiring a wholesale read of DECISIONS.md or archived
  PROGRESS (28,787 and 16,690 lines). A process assuming they are read is one that gets skipped
  silently. They are searched by ID and anchor, never read through.

### 6.2 Orca coordinator / executor

- **Coordinator:** PROJECT_STATE is the briefing document — what is open, blocked, unknown, awaiting
  the user. The coordinator owns the §4 protocols and is the only role that edits it.
- **Executors:** receive **task-scoped excerpts** plus the specific SPEC/ARCHITECTURE sections their
  task touches. **The archive is never handed to an executor** — historical text read out of context
  is exactly the R4.x failure mode, and an executor has no session memory with which to discount it.
- **Conflicts:** an executor finding a document that disagrees with evidence returns it as a
  **finding**, not an edit. Executors do not reconcile documentation, amend SPEC, or resolve a UD;
  findings route to the coordinator, which applies §4 and records the outcome once.

---

## 7. Quick reference

| Question | Go to | Never trust for this |
|---|---|---|
| What is required? | SPEC.md + accepted DECISIONS entries | plans, roadmaps, diagrams, code comments |
| Why was it chosen? | DECISIONS.md | narration, commit messages |
| What is built? | the code at a named revision; ARCHITECTURE.md as the curated map | SPEC, any projection |
| What is live? | runtime observation, build-SHA-qualified | repo HEAD, ARCHITECTURE, any repo doc |
| Is it tested? | TRACEABILITY.md (unverified = not traced) | a green suite as proof of correctness |
| What is open? | PROJECT_STATE.md, within its staleness window | DECISIONS.md, archive/, **or a reconciliation-register row by itself** (the register says why an item was opened; PROJECT_STATE says whether it still is — §4.7) |
| What can't engineering decide? | PROJECT_STATE's UD table + USER_DECISION_QUEUE | a recommendation; your own inference |

**If two sources disagree and this document does not cover the case:** state both claims with their
layer and date, do not pick, and surface it. A visible unresolved conflict is safe; one resolved by
guessing is not.
