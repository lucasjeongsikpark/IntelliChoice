# Decision Supersession Map — Phase 2 of the Documentation Reconciliation Migration

**Date:** 2026-08-19

**Method.** Chains were hypothesised from Phase 1's full-read coverage of `docs/DECISIONS.md`,
`docs/PROGRESS.md` and the audit documents. Every material link was then **re-verified by direct
re-reads of the named DECISIONS.md entries**, with verbatim quotes and line numbers recorded.
Four rules governed the verification:

- Newer text was **never assumed** to supersede older text; the relation had to be stated somewhere.
- **Explicit user decisions outrank recommendations**, including a recommendation written later.
- Implementation was **not** treated as proof that a decision changed.
- **Contradictions are preserved, not resolved.** Where two entries conflict and no third entry
  reconciles them, this map says so and stops.

**Companion document:** `CLAIM_LEDGER.md` (same directory).

---

## How to read this map

- Every relation below is **quoted evidence, not inference**. Where the chain brief that seeded a
  verification asserted a link the text does not support, the refutation is recorded in that
  chain's *Ambiguities* block rather than being quietly dropped.
- **"Status tags updated?"** records whether the *earlier* entry's own heading was ever revised
  after a later entry superseded, corrected, or falsified it. The answer is almost always **no** —
  that is the single most consequential finding in this document.
- A **Candidate ACTIVE decision** is a *candidate*, pending Phase 3. It is what the corpus's own
  text supports as current; it is not an instruction to retag anything yet.
- Line numbers are for the file named in the chain. Unmarked line numbers are `docs/DECISIONS.md`.

---

## Summary of chains

| Chain | Theme | Candidate ACTIVE decision(s) | Confidence |
|---|---|---|---|
| F1 | Deployment footprint | **D-084 as amended by its 2026-07-23 addendum** (footprint); **D-092** (secret management); **D-093 as edited in D-137** (runbook) | HIGH on D-004→D-082/083→D-084; MEDIUM on D-092/D-093/D-137 |
| F2 | MongoDB→MySQL | **D-082 (the fact) + D-083 (dev fake) + D-111 §4 (docs)**, jointly | HIGH |
| F3 | Dev auth & `/dev/token` | **D-097 as amended by its addendum + D-167 + D-310** | HIGH on the D-006→D-310 sequence; MEDIUM on D-310→D-388 being a link at all |
| F4 | Criterion 6 date | **D-148 §2** (closed 2026-08-01 on a documented user reading), extended by **D-149** | HIGH on sequence and user attribution; MEDIUM on the D-141 §5 disposition |
| F5 | Capacity purchase | **D-153 §3** — no purchase; r = 5 withdrawn, not deferred; revisit at integration | HIGH |
| F6 | Retention assumption | **D-114 §1 (90/90/365) + D-153 §2 (365d `learning_events`) + D-333 (30/90/180 checkpoints, dry-run)** — three coexisting policy sets | HIGH on D-072→D-114→D-126; LOW on D-126→D-333 being one chain |
| G1 | Integration freeze | **D-152**, reconfirmed verbatim by **D-417 §A1** | HIGH |
| G2 | Branch locator privacy | **D-113 §1** — `purge_resume_writes` on `channel = '__resume__'` | HIGH |
| G3 | Tutor/manager read-scope (§7-R8) | **D-123 §1** — R8 accepted as a documented, *expiring* residual risk | HIGH on the three links; MEDIUM-HIGH on "no closure exists" |
| G4 | Secrets exposure & rotation | **D-310** — leak fixed at source; **rotation declined by the user** | HIGH |
| G5 | Org time convention | **D-130 mechanism + D-153 §4 disposition + D-324 §1–2 extension** | HIGH |
| G6 | Multi-child switcher | **D-184** — in-app switcher, reversing D-176's deliberate exclusion | HIGH |
| G7 | Session renumbering | **D-049** — still the live translation layer | HIGH |
| H1 | Access-probe rule evolution | **D-371** for the rule; **D-180** as the last entry that changed probe behaviour; **D-351** for the API surface | HIGH on every quoted link; LOW on D-180→D-220 and D-221→D-359 |
| H2 | AUD-C-23 oscillation | **D-177 §2** (floor 0.9 + pre-floor margin), verified live by **D-178**, with **D-179's** correction standing | HIGH |
| H3 | `.ics` / OPEN_DECISIONS #13 | **D-399** — DOM-contract spec; #13 closed | HIGH |
| H4 | Frontend unit tests / #14 | **D-405** (vitest + jsdom, both frontends, user's call) as extended by **D-413** (RTL); **D-414** closes the fourth assertion | HIGH on D-403→D-405→D-413→D-414; MEDIUM on "D-399 raises #14" |
| H5 | Chat turn lifecycle | **D-405** (40s stale timer) on **D-404** + **D-403** + **D-402** + **D-346**; extended to replayed turns by **D-413** | HIGH |
| K1 | Shape-pipeline retirement | **D-226** — shape apparatus deleted; authored-only is the sole path | HIGH on D-193→D-194→D-224→D-226; MEDIUM on the chain's start |
| K2 | Phantom trio D-190/D-191/D-192 | **The 2026-08-08 meta-note itself** is the active record for all three ids | HIGH on what the note says; irreducibly LOW on D-192's facts, by the note's own design |
| K3 | Volume / coverage / parking | **D-342** — all coverage/depth/tier-gap work parked as a standing user instruction; D-273's 5–7 per tier is the volume target of record when work resumes; D-289 for auto-approval | HIGH on D-185/D-341/D-342/D-417; MEDIUM on the D-223 target attribution and on where D-322 §7 sits |
| K4 | Difficulty judge / tiers | **D-302** — the judge's rating is the stored tier; uneven distribution accepted; D-232's per-topic anchors remain the rubric mechanism | HIGH on D-300→D-301→D-302→D-313; MEDIUM on D-233's role |
| K5 | Hint-quality instruments | **D-201's** single leak rule (per D-250), `hint_reveals_answer` as a flag (D-246), score out of triage (D-249), two-reviewer union with missing-verdict-blocks (D-256) inside D-251's falsification-only frame; content state of record **D-271** | HIGH on D-201→D-246→D-250 and D-269→D-271; MEDIUM on D-251→D-256 and D-264's state |
| M1 | SSE cross-replica delivery | **D-396** (telemetry) + **D-395** (concurrency contract); architecture-of-record **D-335 as amended by D-395** | HIGH |
| M2 | Deferred-narrative erasure family | **D-373** and **D-381 §`_initial_snapshot`** are the newest links; guard design of record **D-358 + D-369** | HIGH on links and tags; MEDIUM on whether the family is closed |
| M3 | Study-walk drift / C1 Phase 6 | **D-370** (clause closed); **D-365 + D-367** for the drift mechanism; **D-317 + addendum** for the exam-position defect | HIGH on links; MEDIUM on "D-288 fully resolved by D-317" |
| M4 | Video catalog | **D-337 + its verification** (sync guard); **D-305** (per-skill serving guard); **D-046** (classification/storage); **D-339** (U6 criterion) | HIGH |
| M5 | Alarm split / NAT / image floor | **D-419** (D-401 and D-406 applied and verified against AWS); **D-418** for the check itself | HIGH on links and applied state; MEDIUM on the instance-counter family |
| M6 | Phantom IDs D-329 and D-363 | n/a — both classified PHANTOM / MISSING ENTRY; see the phantom-ID section | HIGH (absence verified by exhaustive grep on both files) |

---

## Global findings (verified across all chains)

**1. The `superseded` status value is declared and never used.**
`docs/DECISIONS.md`'s own header (line 4) declares the convention
`Status: proposed | accepted | superseded.` Grep for `superseded` in any `## D-` / `### D-` heading
returns **nothing, file-wide**. The word occurs only in the header legend and in body prose. Across
all 29 chains — roughly 120 entries read in full — **zero** entries carry a `superseded` tag.

The **only heading-level supersession marker anywhere in the corpus** is D-342's metadata line:

> **Date:** 2026-08-15 · **Status:** standing instruction from the user · **Supersedes the "open" framing in** D-223, D-313, D-322 §5, D-341

(line 24569). That is one marker, in one entry, naming four antecedents — and, as recorded under
*Unresolved or ambiguous chains* below, its list is incomplete in a way that matters.

**2. Two heading conventions coexist, and neither is complete.**
Earlier entries use `## D-nnn — … (accepted, YYYY-MM-DD)`. Later entries use `### D-nnn — …`
followed by a free-prose metadata line such as `**Date:** 2026-08-15 · **Status:** implemented`, whose
values are *not* drawn from the declared enum (observed values include `implemented`, `fixed`,
`measured, deliberately not tuned`, `stopgap, removed by D-349`, `decided by the user`,
`standing instruction from the user`, `recorded`, `⛔ open — characterised, not fixed`,
`the clause stays ⏸`, `built, falsified, tested`, `leak fixed at the source; rotation declined by the user`).
Verification and addendum sub-entries **sometimes carry no status field at all** — confirmed at the
D-335 verification (line 24126) and the D-337 verification (line 24308), and at the D-165 and D-166
addenda. Two consequences, both verified: any table of contents or navigation generated by heading
level silently drops roughly half the corpus, and anything that indexes by status cannot see the
verification entries at all.

**3. In-place amendment is the file's actual supersession mechanism, used inconsistently.**
Where reconciliation happens at all in the *earlier* entry, it takes one of two forms. The model
cases are:

- **D-153 §5's pointer** — `⚠️ CORRECTED the same day — see §7, which supersedes that reading.`
  (line 9111). This is the only *backward* pointer found in the whole audit and is the convention
  worth reusing.
- **Dated correction blockquotes** inserted into the earlier entry's body: **D-004**
  (`**Correction (2026-07-22, see D-082/D-083):** …` and a companion
  `**Decided (2026-07-22, S32 — see D-084 …)**` paragraph, lines 39–52), **D-269**
  (`> **Correction (D-271).** …`, lines 19268–19274), **D-273** (§1 labelled
  `*Superseded by the § "Corrected by verification" block below; kept because the correction is the point.*`
  plus that block), and **D-401** (`> **Corrected 2026-08-18 by a terraform plan run for D-406:** …`,
  line 27533).

Adjacent, weaker variants observed: dated addenda appended without their own status tag (D-084,
D-097, D-165, D-166, D-211, D-212, D-225, D-326, D-335, D-337, D-317), an in-body
`✅ VERIFIED BY THE USER 2026-08-04` annotation (D-167), a self-warning non-standard heading tag
(D-086: `accepted as launch-blocking carry-over, not fixed`), and same-entry self-corrections
(D-141 §6 walking back §3, D-201's `### A correction to an earlier claim in this session`,
D-344's `#### ⚠️ Correction`).

**4. Actively-misleading stale tags and lines — each individually verified.**

| Entry | What it still says | Why that is wrong | Line |
|---|---|---|---|
| **D-135** | heading asserts *"Criterion 6 closes on 2026-08-02 for all three jobs"*; §5 still says *"2026-08-02 is a read-and-tick"* | D-138 proved the premise false — *"the 07-26 firing D-135 recorded is not a mis-read metric — it is an event with no possible cause."* **No annotation anywhere in D-135's body** (7608–7679 read in full). Highest-risk stale heading found. | 7608 |
| **D-344** | `**Status:** stopgap, **removed by D-349**` | its own correction section says *"the stopgap existed for the length of a code review and never once bounded the service"* and *"**D-349 therefore removes nothing**; that clause in its heading is inherited from this mistake"*. A heading and its own body in direct contradiction. | 24669 / 24696, 24705 |
| **D-356** | `**Status:** ⛔ **open — characterised, not fixed**` | D-358 carries `**Fixes:** D-356`. And `PROGRESS.md:834` says `**✅ D-356 IS FIXED…`. **This is a cross-document status conflict, not merely a stale tag** — the two documents disagree about the same decision. | 25322 |
| **D-300** | `**Status:** measured, 10.24¢; the remedy is a decision, not yet taken` | the remedy was taken, twice: D-301 (compromise) and D-302 (reversal). | 21480-area |
| **D-366** | `**Status:** the clause stays ⏸, with a tally rather than a claim` | D-370 closed the same clause `✅`, 140 lines later, with no cross-link back. | 25715 |
| **D-085** | reads as closed (`Reverted app_environment to "staging"`) | D-096 records that the change lived *"in `terraform.tfvars`, which is gitignored, in one machine's working tree, with the apply withheld … the decision log said 'closed' for two days while the hole was open."* D-167 restates it. Nothing in D-085 points forward. | 2795 |
| **D-072** | residual-risk acceptance stated with a bare 90-day-retention mitigation bullet | D-114 and D-126 both record that the mitigating premise broke — *"The acceptance did not change; **its mitigating assumption silently stopped holding**"*. Unannotated. | 1585 |
| **D-322 §7** | records the user choosing *"Edit `difficulty_tiers` to match the judge"* | D-341 records the user deciding the opposite; D-342's supersession list names **§5 but not §7**. See *Unresolved or ambiguous chains* (a). | 22918 |

Two further stale-but-less-dangerous cases worth naming: **D-405**'s explicit "no RTL" scope line,
intact after D-413 added RTL the same day; and **D-419**, which carries a live unresolved action
(`PendingConfirmation`) with no `⛔`/`⏸` marker of any kind — four informational alarms currently
route to a topic with no confirmed subscriber.

**5. The corpus is traversable newest→oldest only.**
Supersession pointers are written **forward, inside the superseding entry**. Of roughly 120 entries
read across the five verification passes, not one had a status tag edited *after* a later entry
superseded it. The only in-place status corrections are *self*-corrections inside the same entry.
The practical consequence, stated as measured: any reader who lands on an older entry by grep gets
the stale claim with no warning, and any consumer that reads status tags to determine what is
current will read at least eleven stale `accepted`/`implemented` entries as active.

**6. A likely typo is carried identically in two documents.**
`DECISIONS.md:27790` (inside D-406) and `PROGRESS.md:334` both cite **"D-137/D-141/D-356"** for the
CI-registers-then-terraform-re-registers image drift. D-356 is the deferred-narrative erasure
defect and has nothing to do with image floors. This almost certainly means **D-357**, which is the
entry that records exactly that drift. Two documents carry the same wrong id.

---

## Unresolved or ambiguous chains

These are not oversights in this map. Each is a place where the corpus contradicts itself or leaves
a question open, and where no document reconciles it. **Do not resolve them here.**

**(a) D-322 §7 versus D-341 — two USER decisions in direct conflict.**
D-322 §7 (2026-08-14) records, as a user decision and "as recommended":
*"**Edit `difficulty_tiers` to match the judge**"* (line 22918). D-341 (2026-08-15) records the user
deciding the opposite, in a quoted blockquote: *"Keep the existing `difficulty_tiers` declarations
unchanged. Do not modify the taxonomy solely because the current bank is thin"* (24523–24528).
D-342's supersession list names **"D-322 §5"** — **not §7** (line 24569). D-417 §D10 fixes only
`OPEN_DECISIONS` #7, not D-322 §7. So D-322 §7 stands unannotated and contradicts the later, active
decision. Both sides are explicit user decisions, so the ranking rule cannot break the tie.
**Unresolved.**

**(b) §7-R8's closure path is frozen while its acceptance expires.**
D-123 §1 accepted the tutor/manager read-scope gap as documented residual risk §7-R8, with
*"R8 expires at first real traffic."* (6497) and closure owned by *"S43/S46 for R8"* (6500). S43 is
frozen by D-152 and reconfirmed frozen by D-417 §A1. So the risk cannot be closed on its stated
path while integration stays frozen, and the acceptance expires on an event the freeze does not
prevent. **No document reconciles this**, and nothing read states who should.

**(c) D-401/D-406: "applied" versus "still unapplied".**
D-419 records *"**Applied** on the user's authorisation, immediately after D-418 removed the phantom
blocker"* (28465), with post-apply verification against AWS, and ROADMAP W25 carries the same. The
PROGRESS.md top block still reads that they are unapplied. **Contradiction preserved.** Note also
the related attribution trap recorded in M5: the sentence *"D-401 (alarm split) and D-406 … stay
unapplied"* is **not** inside D-406 — it is at 28296–28297 inside **D-417/A3**. D-406's own body says
only *"nothing applied"* (27792).

**(d) Whether the D-356 erasure family is fully closed.**
D-373 ports the guard to a third publisher; D-381 carries a sub-heading
`#### D-356's family, in the third place it lives` (26527) — **both claim to be the third place**.
No entry states how many publishers exist, and **no entry claims completeness**. D-373 says "seven
fixes have now gone one way only"; D-381 finds a further site. Whether a fifth exists is
unaddressed. **Open.**

**(e) Whether the NAT gateway currently exists.**
`ARCHITECTURE.md` describes one NAT gateway in the present tense. D-406/D-419 treat it as **absent
from the plan entirely**. Not reconciled anywhere read.

**(f) Chain-brief links refuted or weakened during verification.** Recorded honestly rather than
carried forward:

- **"D-138 supersedes D-135" is NOT literal.** The word *supersede* is absent from every entry
  discussing D-135. The actual relation is **premise-falsified**: *"The premise is false, and the
  date moves."* (7917) and *"D-135's per-job table was therefore an inference from the cron
  expressions dressed as a measurement"* (7960).
- **D-092 → D-084 is linked only via D-093.** D-092 never names D-084; it simply removes the
  resource D-084's remediation command used. The link is made explicit only downstream, in D-093
  (3180).
- **D-126 → D-333 crosses policy families.** D-114 is 90/90/365 on derived-text tables; D-333 is
  30/90/180 on LangGraph checkpoints. D-333 cites **neither** D-072, D-114 nor D-126 (it cites
  D-331/D-332). These are two policy families, **not one chain**.
- **"D-169 corrects D-168's carry-over" is real but off-thread.** The dated correction exists at
  10569 — but it concerns the `cryptography`/PyMySQL **dependency** note, not the access probe.
  D-169's own body (10580–10639) is AUD-L-12 `recommended_difficulty` and contains no access-probe
  content. If the expectation was "D-169 corrects D-168's *probe* carry-over" → **NOT FOUND**.
- **The quote "The number was never the variable", attributed to D-233, was NOT FOUND** in the
  window read (16724–16734). D-233's recorded framing there is the heading's *"the judge's prose
  expands to fill whatever it is given"* plus *"`str(asyncio.TimeoutError())` is `""`. The judge was
  hitting `bedrock_call_timeout_s = 20.0`."* Flagged rather than substituted; do not attribute it
  without a wider read.
- Two further links carry **no stated relation at all** and must not be read as supersession:
  **D-180 → D-220** (D-220's antecedent is D-219's carry-over; it never cites D-180, and the two are
  ~3,600 lines apart) and **D-221 → D-359** (D-359's stated antecedents are D-351 and
  AUD-C-21/AUD-C-16).
- **D-003 → D-193/D-224/D-226 is inference-only.** D-003 is cited exactly once in the whole file
  (line 1270, inside D-060). No entry supersedes or retires it.
- **D-176's role in the AUD-C-23 chain is weak/indirect** — it deploys D-175's *other* work and
  contains no AUD-C-23 fix, because D-175 deliberately did not fix it.

---

## Phantom / missing decision IDs

Five ids are cited across the corpus with **no entry of their own**. Recorded here per the phase
rules: every known reference, a classification, and an explicit split between what can and cannot
safely be inferred. **The missing decisions are not fabricated.**

### D-190, D-191, D-192 — recorded as absent, by the corpus itself

Unlike the others, this trio already has a meta-note. **Heading verbatim:**
`## D-190, D-191, D-192 — referenced everywhere, never written (recorded 2026-08-08, while closing D-223)`
— line 16101. Its status tag is `recorded`, **not** `accepted`; it is the only heading in the entire
audit that uses that word.

**What the note claims, quoted:**

- Existence of the gap: *"**These three ids have no entry.** The log jumps from D-189 straight to
  D-193, yet the ids are cited **18 times in code and 8 times in docs**"* (16103–16104). Named
  citation sites: *"`authored_validation.py`'s own docstrings, in `test_authored_bank.py`'s module
  docstring, and in D-223 above"* (16104–16105).
- What is wrong: *"Nothing is wrong with the *work*; what is missing is the record, so a reader
  following a citation lands on nothing."* (16105–16106)
- Reconstruction basis: *"What they refer to, reconstructed from the code and tests that cite them,
  and verifiable there"* (16108).
  - **D-190:** *"**approved authored content as a versioned file.** `curriculum/internal_math/authored/*.yaml`,
    written by `make question-export`… Pinned by `test_authored_bank.py`"* (16110–16114).
  - **D-191:** *"**the gate made independent, and the wording list made word-boundary.**
    `answer_expression` became a required *relation* so `derive_answer` solves the question…
    `_DISALLOWED_WORDING` moved from substring to boundary matching after it destroyed a question
    about rolling a **die**."* (16115–16119)
  - **D-192 — explicitly unreconstructable:** *"**the id nothing in the tree explains.** Cited in 4
    code files and 2 docs; unlike the other two, no citation states what it decided. **Left as a
    known unknown rather than guessed at.**"* (16120–16121)
- Refusal to backfill: *"**Not reconstructed into full entries here.** … writing three retrospective
  entries from inference would produce exactly the confident-looking, unverified prose this project
  keeps finding bugs inside. The citations now resolve to this note, which says what is known and
  what is not."* (16123–16126)
- Process framing: *"**Worth a habit, not a fix:** … `grep -c "^## D-$n" docs/DECISIONS.md` before
  citing an id costs nothing."* (16128–16130)

**Status tags updated?** N/A — there are no earlier entries to tag. The note *is* the record of
absence. **No back-annotation exists at D-189 or D-193 pointing forward to it.**

**Which decisions cite them** (verified by grep, DECISIONS.md only):

- **D-192:** D-193 (12950, 12990, 12992); 13756 (*"**This is not D-192 returning.**"*); 13836;
  D-199 (13908); the note (16101, 16120); 17304 (*"D-192's lesson applied to a new bucket"*).
- **D-191:** 13346; D-198 (13582); D-200 (13725); D-223 (16014, 16058); the note; D-225 (16222);
  16463 (as D-190); D-273 (19654, 19689–19690); 20243; 20422; 21832; 22114.
- **D-190:** 16110 (the note) and 16463 (*"D-187, D-190, and here"*).

**Candidate ACTIVE decision:** the note itself is the active record for all three ids. Its
substantive content is live-in-code for D-190 and D-191; **D-192's content remains unknown** and is
only *negatively* characterised (by D-193's reversal and 13756's "not D-192 returning").

**Historical-but-must-stay-discoverable:** the entire note — **it is the only resolution target for
~26 citations.** Deleting it or "completing" it would break every citation and reintroduce exactly
the inference the note refuses.

**Ambiguities:** the D-190/D-191 descriptions are reconstruction, self-labelled as such, and carry
no date for when the decisions were actually taken. D-192 is doubly odd: no entry, no citation
stating its content, yet D-193 claims to reverse its *direction* and describes it in detail (*"built
an inverted authoring mode: generate the equation from a registered shape first"*) — that
description exists **only in the reversing entry**. The note's "no citation states what it decided"
is therefore in mild tension with D-193's account, unless the note counted only *code* citations.
The counts ("18 times in code and 8 times in docs", "4 code files and 2 docs") were not re-verified;
only the DECISIONS.md side was. **Confidence:** HIGH on what the note says; the underlying facts
about D-192 are irreducibly LOW **by the note's own design**.

### D-210 — PHANTOM / MISSING ENTRY (discovered in Phase 2, not Phase 1)

`grep '^#\+.*D-210'` returns exactly one hit: **`## D-210 disposition`**. There is no `D-210` entry.
This has the same phantom shape as D-190/D-191/D-192 but **was never recorded as such** — no
meta-note covers it.

**What exists.** The disposition entry (`(accepted, 2026-08-06)`) reads *"D-210 was committed \"WIP\"
because removing shape templates left three thin cells"* (14535) and decides *"A shape-template
fallback (the \"option B\" considered here) is therefore **not built**"* (14554). That tells a reader
what was decided *about* D-210's residue, not what D-210 itself decided.

**What the citations establish.** D-210's substance — the `_servable()` / `authoring_mode == "authored"`
rule and the export `active_status` filter — is reachable **only** through citations in **D-224,
D-226, D-269 and D-271**. D-271 is the most load-bearing: *"`export_cli` filters on
`active_status == \"active\"` as well as approved — **D-210 added exactly that filter**"*
(19378–19384), which is what falsifies D-269's own precaution claim.

**What cannot be inferred:** D-210's own text, date, status tag, and what alternatives it weighed.
**Classification: PHANTOM / MISSING ENTRY.**

### D-329 — PHANTOM / MISSING ENTRY

**No `## D-329` or `### D-329` heading exists anywhere in either file.** Confirmed by
`grep -nE "^#{2,4} D-(329|363)"`; the only hit is line 26276, which is
`#### D-329's detection gap…` — a sub-heading *about* D-329 inside another entry.

**Every known reference** (whole-file grep, DECISIONS.md + PROGRESS.md):

- `#### Learning: personalized hints had never worked (D-329, fixed)` — **line 23582**, a level-4
  sub-heading **inside D-330** (`### D-330 — The learning/chat sweep…`, line 23576,
  `**Status:** learning bug fixed (`0deb31c`); chat measured, one residual recorded`).
- *"`background_hint_personalization_failed` × **117 in 48 hours**, and the *only* ERROR the learning
  API was emitting. **See D-329.**"* — 23584–23585.
- `**Follows:** D-329` — **line 23941** (D-334); and *"The carry-over from D-329 was 'still unproven:
  that a student sees the personalized hint'"* — 23943.
- *"the scheduler *swallowed the resulting `TypeError`* — the same silence D-329 was about"* — 24002.
- `### 5. A correction to D-329, recorded rather than quietly edited` — **24004**, retracting D-329's
  history claim: *"`test_background_gateway_registry.py` asserted that the bug 'ran in production for
  as long as the feature had existed'. **Measured, that is false.**… It was a regression, not an
  original defect."*
- *"the same class of error as D-329's 'never worked in production'"* — 24700 (D-344).
- *"the second time this session (the other: D-329's…)"* — 24997 (D-350).
- `#### D-329's detection gap, unchanged since the incident` — 26276.
- PROGRESS.md:1196, 1230, 1425, 1443, 12046 (12046 is a section heading:
  *"### Sweep — one dead feature in learning, and F-19's P1 resolved in chat (2026-08-14, D-329/D-330)"*).

**What the citations safely establish:** the subject — personalized hints
(`background_hint_personalization_failed`, the `BackgroundHintPersonalizationScheduler`) failing
silently; **117 errors in 48 hours**; fixed in commit **`0deb31c`** around **2026-08-14**; a
carry-over left open (*"still unproven: that a student sees the personalized hint"*); a docstring
claim about production history that **D-334 §5 measured as false** (regression, not original
defect); and a detection gap still open at D-381's date.

**What cannot be inferred:** the decision's own text and rationale, its exact date, its status tag
(it has none), whether it was ever `accepted`/`implemented`/`⏸`, what alternatives it weighed, and
anything beyond what its citers summarise. **D-334's `Follows: D-329` is a dangling reference.**

### D-363 — PHANTOM / MISSING ENTRY (weaker than D-329)

**No heading of any level for D-363 exists in either file.** Confirmed. **Exhaustive citation list —
only four in the corpus:**

- `| 5 | 1 | D-363 (the click never landed) and **D-364, a real 502 the app never logged** |` —
  **DECISIONS.md:25728**, inside D-366's attempt table.
- `| D-361, D-363 — the hint spec measuring the chooser; a click that never landed | harness |` —
  **DECISIONS.md:25894**, inside D-370's "what stopped it" table.
- `| 5 | 1 clean | D-363 (the click never landed) and **D-364, a real 502** |` — **PROGRESS.md:891**.
- `D-363, D-365); a repaired live instrument (D-359).` — **PROGRESS.md:2214**.

It has **no sub-heading, no `See D-363`, and no `Follows:`/`Fixes:` relation anywhere** — it exists
only as two table cells in DECISIONS.md and two lines in PROGRESS.md.

**What the citations safely establish:** a **harness** (not product) defect in which *"the click
never landed"*; it stopped accumulation attempt 5 of C1 Phase 6, alongside D-364; it is grouped with
D-361 as "the hint spec measuring the chooser". Approximate date **2026-08-16**, by neighbours
D-361–D-365.

**What cannot be inferred:** the exact decision content (which spec, which click, what the fix was),
its status, its date, whether it was fixed or merely recorded, and whether "the click never landed"
is the defect or the symptom.

**Ambiguity worth carrying:** the D-361/D-363 pairing at 25894 collapses two ids into one row with
two descriptions, and the mapping of description to id is recoverable **only** from 25728.

> **Phase 3 sweep item (from M6).** D-359, D-360, D-361, D-362 and D-364 all appear as cited ids in
> these same two tables, and for several of them that table is the only evidence. Phase 3 should
> confirm which of D-359–D-364 have real headings.

---

## Audit-ID namespace rule

Finding ids in this project are **only meaningful when qualified by their source document.** Three
independent, verified facts force this rule:

- **`AUDIT_FINDINGS.md`** (frozen 2026-08-05) and **`AUDIT_LIVE_2026_08_17.md`** both use the range
  **`AUD-L-01` … `AUD-L-19`**, for **unrelated findings**. The ranges are reused, not continued.
- **`AUDIT_2026_08_16.md`** uses its own **`P1-n`** scheme, plus later shared labels
  **`AUD-CHAT-*`**, **`AEL-*`** and **`EDGE-CHAT-*`** that appear across more than one document.
- Inside `AUDIT_FINDINGS.md`, the **`AUD-L-17` → `AUD-L-19` renumber was applied per-reference**,
  with ranges **deliberately left ambiguous** rather than rewritten wholesale.

**Rule: never treat a bare audit ID as uniquely identifying one finding.** Always cite it as
`<document>:<id>`. A cross-document search on a bare `AUD-L-nn` will return findings from two
different audits with different subjects, and a range like "AUD-L-15…19" cannot be resolved without
naming the document and the revision.

---

## The chains

### Theme F — Foundation & infrastructure (F1–F6)

#### CHAIN F1 — Deployment footprint

**Links**

- `D-004 --self-corrected-in-place--> (D-082/D-083)` | *"**Correction (2026-07-22, see D-082/D-083):**
  the "managed Mongo (Atlas)" clause above is stale on two axes and should not be acted on as
  written"* | line ~39
- `D-004 --decided/confirmed-in-place--> D-084` | *"**Decided (2026-07-22, S32 — see D-084 …):** the
  corrected recommendation above is confirmed as-is — ECS Fargate + RDS PostgreSQL w/ pgvector +
  RDS MySQL"* | line ~48
- `D-084 --confirms--> D-004 (as corrected)` | *"Confirms D-004 as corrected by D-082/D-083: ECS
  Fargate (not EKS) + RDS PostgreSQL w/ pgvector (not Aurora) + RDS MySQL"* | line ~2339
- `D-084 addendum --corrects--> D-084 body (Bedrock Mantle)` | *"**Addendum (2026-07-23): Bedrock
  Mantle abandoned account-wide** … That attribution is hereby corrected: Sonnet-5-on-Mantle has
  *two* independent blockers"* | lines ~2651, ~2667
- `D-092 --removes-the-resource-D-084's-remediation-used--> D-084` | *"Removed both modules'
  `random_password.master` resource and the manually-maintained combined-DSN
  `aws_secretsmanager_secret`/`_version` resources entirely"* | line ~3099. **D-092 never names
  D-084.** The supersession is made explicit only downstream, in D-093.
- `D-093 --records-D-084's-remediation-command-as-stale--> D-084 / D-092` | *"the old
  `terraform apply -replace=module.rds_mysql.random_password.master` remediation command S32 actually
  used no longer applies now that RDS-managed passwords replaced that resource"* | line ~3180
- `D-137 --fixes-runbook-again--> D-093` | *"`INCIDENT_RESPONSE.md`'s leaked-credential playbook told
  an operator to run a bare `terraform apply -replace=random_password.jwt_signing_secret_learning` …
  It now carries the `-target` form"* | line ~7881. **Different secret** (D-085's JWT signing secret,
  not the RDS master). Not a fix of the D-093 RDS rotation step.

**Status tags updated on superseded entries?**

- D-004: **NO** — `(accepted, decided at S32 2026-07-22, proposed 2026-07-13)`. Uniquely, it *does*
  carry two inline correction/decision paragraphs (lines 39–52), so its body was amended even though
  the tag was not.
- D-082: **NO** — `(accepted, 2026-07-21)`
- D-083: **NO** — `(accepted, 2026-07-22)`
- D-084: **NO** — `(accepted, 2026-07-22)`; body extended by a dated addendum heading (no status tag
  of its own).
- D-092: **NO** — `(accepted, 2026-07-23)`
- D-093: **NO** — `(accepted, 2026-07-23)`
- D-137: **NO** — `(accepted, 2026-07-31)`

**Candidate ACTIVE decision:** **D-084 as amended by its 2026-07-23 addendum** for the footprint
(ECS Fargate + RDS Postgres/pgvector + RDS MySQL, Claude Haiku 4.5 on classic `bedrock-runtime`);
**D-092** for secret management; **D-093 as edited in D-137** for the runbook.

**Historical-but-must-stay-discoverable:** D-004 (the only place the EKS/Aurora spec deviation and
its "Atlas" error are reasoned about); D-084's body (the Mantle wiring its own addendum abandons,
plus the real credential-leak incident that D-093's playbook cites); D-092 (the full DSN-component
change set every CLI still depends on).

**Ambiguities/uncertainty:** (1) D-092→D-084 supersession is an *inference the chain brief asserts*;
the text linking them lives only in D-093. (2) D-137's runbook fix concerns the JWT-secret
`-replace` command, not the RDS rotation command D-093 fixed — treating it as the next link in the
same chain conflates two different remediation commands. (3) The D-084 addendum corrects only the
Mantle/model attribution, **not** the footprint.

**Confidence:** HIGH on the D-004→D-082/083→D-084 half; MEDIUM on D-092/D-093/D-137.

#### CHAIN F2 — MongoDB→MySQL

**Links**

- `D-002 --corrected-by--> D-082` | *"Every prior doc (SPEC.md, ARCHITECTURE.md, D-002, and this
  project's own `MongoProfileAdapter`/`mongo:7` dev-fake) assumed … **This was wrong**"* | line ~2255
- `D-082 --partially-preserves--> D-002` | *"D-002's "swap is configuration, not rework" claim still
  holds either way, since it was never about the specific engine."* | line ~2269
- `D-083 --executes-dev-fake-half-of--> D-082` | *"Executes the dev-fake half of D-082's deferred work
  (docs are still not swept - see below)."* | line ~2284
- `D-111 §4 --executes-doc-half-of--> D-082` | *"**D-082's deferred doc sweep executed — the docs now
  say MySQL**"* | line ~5167
- Doc-sweep scope deliberately left: *"Historical records (PROGRESS.md, DECISIONS.md, docs/plans/)
  deliberately untouched: they accurately describe sessions in which Mongo was what existed."* |
  line ~5173

**Status tags updated on superseded entries?**

- D-002: **NO** — `(accepted, 2026-07-13)`, still reads "production MongoDB" and
  "`MongoProfileAdapter`" in its body.
- D-082: **NO** — `(accepted, 2026-07-21)`
- D-083: **NO** — `(accepted, 2026-07-22)`
- D-111: **NO** (nothing supersedes it) — `(accepted, 2026-07-28)`

**Candidate ACTIVE decision:** **D-082 (the fact) + D-083 (dev-fake implementation) + D-111 §4
(docs)** jointly. D-002's *pattern* (interfaces + dev fakes) remains active; only its engine claim
is dead.

**Historical-but-must-stay-discoverable:** D-002 (the interface/fake architecture rationale is still
the governing pattern and is cited by D-333, D-093 etc.); D-082 (the "still unconfirmed: direct
MySQL vs. HTTP API fronting it" open question survives all three later entries and is **not answered
anywhere in this chain**).

**Ambiguities/uncertainty:** D-111 §4 sweeps *docs* but explicitly excludes DECISIONS.md itself — so
D-002's stale MongoDB text is left standing **by design**, which means a reader of D-002 alone gets
a wrong fact with no in-entry pointer. Also unresolved: whether the real adapter is MySQL or HTTP
(D-082's own carve-out).

**Confidence:** HIGH.

#### CHAIN F3 — Dev auth & `/dev/token`

**Links**

- `D-006 --overtaken-by--> D-085` | *"`JwtTokenVerifier`/`FakeTokenIssuer` … default to a hardcoded,
  source-controlled constant (`DEV_JWT_SECRET`, D-006, judged safe at the time … - true for a
  local-only app, no longer true once S32 put a real ALB in front of it)"* | line ~2815
- `D-085 --recorded-executed-but-not-applied; corrected-by--> D-096` | *"S33/D-085 records this
  finding as executed, and it was — in `terraform.tfvars`, which is gitignored, in one machine's
  working tree, with the apply withheld. … the decision log said "closed" for two days while the hole
  was open"* | line ~3473
- `D-096 --leaves-open-question-decided-by--> D-097` | *"**1. The staging authentication question
  D-096 left open.** … the user chose a **staging-only token path gated on a real secret held in
  Secrets Manager**"* | line ~3604
- `D-097 --self-corrected-by-its-own-addendum` | *"### D-097 addendum — the staging token path
  shipped green and useless; live verification caught it"* and *"**Locally and in CI both sides are
  the dev constant**, so the two agreed by coincidence and all 509 tests passed."* | lines ~3730,
  ~3739
- `D-097 addendum --contradicts-prior-flake-characterization--> (D-091/D-095-era)` | *"which
  contradicts prior sessions' "confirmed via an immediate clean standalone rerun" characterization
  (that rerun just usually wins the coin flip)"* | line ~3770
- `D-167 --refines--> D-097` | *"D-097's secret gate is the only authenticated path to staging until
  S44 … **The user chose 1** [`sessionStorage` → `localStorage`] … The gate, the handler, terraform,
  and the deploy probe are all untouched."* | lines ~3644, ~10358, ~10380
- `D-167 --reaffirms-the-D-085-lesson--> D-085` | *"S33/D-085 "closed" this endpoint in a
  **gitignored** tfvars file on one machine and left both CloudFront distributions minting any-role
  tokens to the public internet **for two days**"* | line ~10373
- `D-310 --fixes-leak-in--> D-132 (Makefile comment), rotation DECLINED BY USER` | *"**Rotation: the
  user's decision was not to rotate**, on the exposure being bounded"* and *"the sentence asserting
  otherwise is why nobody checked in the ten sessions since D-132 wrote it"* | lines ~22219, ~22192
- `D-388 --verifies-deployed-config-of--> D-097/D-310` | *"If the task definition ever loses
  `STAGING_TOKEN_SECRET_*`, that endpoint becomes an unauthenticated token mint … Measured: **404 on
  both apps**"* | line ~26994. This is **verification, not supersession**.

**Status tags updated on superseded entries?**

- D-006: **NO** — `(accepted, 2026-07-15)`, still says *"**Revisit:** never for this fake issuer"*.
- D-085: **NO** — `(accepted, 2026-07-23)`; still reads as closed despite D-096 and D-167 both
  recording it as falsely closed for two days.
- D-096: **NO** — `(accepted, 2026-07-24)`
- D-097: **NO** — `(accepted, 2026-07-24)`; amended by an in-body addendum with no status tag.
- D-167: **NO** — `(accepted, 2026-08-03)`; carries an in-body `✅ VERIFIED BY THE USER 2026-08-04`
  annotation, heading untouched.
- D-310: heading has **no parenthetical tag**; a separate line reads
  `**Status:** leak fixed at the source; rotation declined by the user`.
- D-388: **NO** — `(accepted, 2026-08-17)`

**Candidate ACTIVE decision:** **D-097 (as amended by its addendum) + D-167 (localStorage
persistence) + D-310 (secret fetched in-process by `e2e/config.ts`)**, with D-085's second gate and
settings-driven JWT secret still in force. D-097 states the whole path is "Deleted at S44".

**Historical-but-must-stay-discoverable:** D-006 (the original hardcoded-constant rationale, quoted
by D-085 and D-097 as the thing that stopped being true); D-085 (the two independent gates and the
per-app random secrets are still live infrastructure, *and* it is the canonical worked example in
`INCIDENT_RESPONSE.md` per D-093); D-096 (the deploy-time 404 probe it created is still the tripwire
D-167 refused to remove); D-097's addendum (the "green deploys prove deployment, not function"
lesson).

**Ambiguities/uncertainty:** (1) D-085's tag still says accepted and its text still reads *"Reverted
`app_environment` to `"staging"`"* — which was true only in a gitignored file. A reader hitting D-085
without D-096 is misled; nothing in D-085 points forward. (2) D-310's status line is prose, not one
of the header's declared `proposed|accepted|superseded` values. (3) The rotation decision is an
**explicit user no-action** and must not be read as an open task. (4) D-388 is not a link in a
supersession chain; treating it as one overstates it.

**Confidence:** HIGH (D-006→D-085→D-096→D-097→D-167→D-310); MEDIUM on D-310→D-388 being a "link" at
all.

#### CHAIN F4 — Criterion 6 date

**Links**

- `D-135 --premise-falsified-by--> D-138` | *"D-135 closed criterion 6 down to a single date … **The
  premise is false, and the date moves.**"* and *"the 07-26 firing D-135 recorded is not a mis-read
  metric — it is an event with no possible cause."* | lines ~7917, ~7926
- Literal "supersedes D-135": **NOT FOUND.** D-138's heading says *"…and D-135 read a firing that
  could not have happened"*; the strongest in-body statements are *"The premise is false"* (~7917)
  and *"D-135's per-job table was therefore an inference from the cron expressions dressed as a
  measurement"* (~7960). **No entry in the file uses the word "supersede" about D-135.**
- `D-138 --leaves-reading-to-user--> (D-148)` | *"**The decision, which is the user's:** whether "≥1
  week unattended" for a weekly job requires the two firings D-135 committed to in writing (⇒
  **08-09**) or one successful firing … (⇒ **08-02**)"* | line ~7995
- `D-140 --invalidates-both-dates--> D-135/D-138` | *"`memory-consolidate` has never worked, fails
  silently, and criterion 6 would have been ticked on it"* and *"**So criterion 6 is now blocked on a
  code fix, not on the calendar**"* | lines ~8075, ~8145
- `D-140 --notes-strict-reading-did-not-help--> D-138` | *"**The strict reading chosen this session
  (two firings ⇒ 08-09) is not what saved this; the de-risking run is.**"* | line ~8141
- `D-141 §6 --self-reverses-D-141 §3-->` | *"**This walks back §3's own reasoning and it is worth
  saying why rather than quietly editing it.** §3 said lengthening the timeout would repeat
  AUD-F-34's mistake."* | line ~8282
- `D-141 §5 --supersedes-a-user-approved-action-->` | *"**Recommendation: do not trim, and this
  supersedes the approved action.**"* | line ~8251 (⛔ marked; the approved action was the user's, the
  reversal is a **recommendation**)
- `D-142 --near-revert-of-D-141's-fix-->` | *"the plan against the stale floor would have reverted
  AUD-F-34, for the third time in three days"* and *"the 2026-08-02 `memory-consolidate` firing would
  have run the **pre-fix** image"* | lines ~8350, ~8361
- `D-142 §3 --confirms-08-09-->` | *"**08-09 remains the date under either reading.**"* | line ~8406
- `D-148 --closes-early-BY-USER--> D-138/D-142` | user attribution: *"The user directed: "just bypass
  that blocker for once." The decision is theirs to make — D-138 §5 explicitly left the reading to
  the user"* | line ~8639; and *"**The §2.6 gate is closed as of 2026-08-01, on a documented user
  decision.**"* | line ~8679
- `D-149 --completes-the-one-gap-in--> D-148` | *"D-148 closed criterion 6 on a one-off `at()` firing
  and left one link unobserved: the *cron expression itself* evaluating to a firing at its own
  slot."* | line ~8691; residual: *"**The `SUN` enum value specifically.**"* | line ~8725
- `D-149 §4 --corrects-window-semantics-->` | *"the consolidation window is a **rolling
  `[now − 7d, now)` computed per run, deliberately not snapped to a calendar week**"* | line ~8733

**Status tags updated on superseded entries?**

- D-135: **NO** — `(accepted, 2026-07-31)`; carries **no** later annotation anywhere in its body
  (7608–7679 read in full). Its heading still asserts *"Criterion 6 closes on 2026-08-02 for all
  three jobs"* and §5 still says *"2026-08-02 is a read-and-tick"* — both known false since D-138.
- D-138: **NO** — `(accepted, 2026-07-31)`; heading still asserts the 08-09 date that D-148 bypassed.
- D-140: **NO** — `(accepted, 2026-07-31)`
- D-141: **NO** — `(accepted, 2026-07-31)`; §3 left standing and explicitly walked back in §6 of the
  same entry.
- D-142: **NO** — `(accepted, 2026-07-31)`
- D-148: **NO** — `(accepted, 2026-08-01)`
- D-149: **NO** — `(accepted, 2026-08-01)`

**Candidate ACTIVE decision:** **D-148 §2 (criterion 6 closed 2026-08-01 on a documented user
reading), extended by D-149 (cron path proven via a `SAT` clone).** D-148 §2's reopening condition is
live: *"a failure in any of those scheduled firings reopens criterion 6"*.

**Historical-but-must-stay-discoverable:** D-135 (the per-job reading of criterion 6 originates in
D-114 §3 and is quoted forward; also the bucket-offset instrument error); D-138 (the only place the
AWS/Scheduler no-per-schedule-dimension limitation and the bucket-minute attribution trick are
documented — `read_scheduler_evidence.py` depends on it); D-140 (AUD-F-34's diagnosis and the
"exit 0 defeats the failure notification" lesson); D-141 (the two wrong constants, and §8's
cohort-scaling numbers that D-153 §1 acts on); D-142 (the tfvars-floor checklist step, still the
standing pre-apply rule).

**Ambiguities/uncertainty:** (1) The chain's claimed literal "supersedes D-135" is **NOT FOUND** —
the relation is "premise falsified", asserted in D-138's heading and §1. (2) D-135's heading is now
flatly wrong and un-annotated; the highest-risk stale heading in this chain. (3) D-141 §5's
"supersedes the approved action" reverses a **user-approved** action but is phrased as a
*recommendation* — per the ranking rule, this is a recommendation against a prior explicit user
approval, and its final disposition is **not restated by a later user decision in this chain**.
(4) D-148's close depends on manufactured evidence plus a standing reopening condition, so "closed"
is conditional, not final. (5) The `SUN` enum remains unexercised as of D-149.

**Confidence:** HIGH on the sequence and the user attribution; MEDIUM on the D-141 §5 disposition.

#### CHAIN F5 — Capacity purchase

**Links**

- `D-133 --defers, user call-->` | *"**Decision (user call): defer the purchase; re-price after (a)
  and (b).**"* and *"**~$216 is a floor, not a total**"* | lines ~7430, ~7412
- `D-134 §7 --corrects-D-133-to-knife-edge--> D-133` | *"**D-133's ~$216 buys a knife-edge, not a
  pass.** … **Re-price against a target concurrency-per-task ratio, not a target task count.**"* |
  line ~7600
- `D-134 §2 --preserves-mechanism-of--> D-133 §3(b)` | *"**But the queueing is made of that work, so
  D-133 §3(b) survives in mechanism and shrinks in size.**"* | line ~7473
- `D-136 §5 --two corrections + r=5--> D-133` | *"**Two corrections to D-133's arithmetic, one in each
  direction.**"* (a) x86-vs-ARM64 rate ~20% high; (b) *"**`pool_size=10, max_overflow=10` is a
  per-task constant sized in S34** … **`db.t4g.micro`'s ~112 is sufficient and no RDS resize is
  required for the pilot at all**"* | lines ~7783–7793
- **Is D-136 §5 a recommendation or a decision? Both, explicitly:** *"**Decision: the purchase stays
  deferred, and the recommendation changes shape.** Not "defer until the org answers", but: **target
  r = 5, which at the pilot's 25 concurrent is 5 tasks and needs no database change**"* | line ~7800.
  The *deferral* is the decision; **r = 5 is the recommendation** ("the recommendation changes
  shape"), reinforced by D-139 §2's *"The recommendation does not change and gets cheaper"*.
  **Nothing in F5 records a user approving r = 5.**
- `D-139 §1 --confirms-D-136's-correction-(a)--> D-133` | *"D-133's $18.02 reproduces **exactly** from
  the x86 rates … The ARM figure is **80.0%** of it — D-136's "~20% high" was right to the tenth of a
  percent."* | line ~8032
- `D-139 §2 --re-prices-->` | *"**r = 5 for the pilot, +3 tasks, ~$43/month, no RDS resize**"* |
  line ~8045
- `D-139 §3 --reframes-every-price-in-the-chain--> D-133/D-136` | *"July's bill is **$72.12 of usage
  and −$72.12 of credit**, netting **$0** … So every price in this entry and in D-133/D-136 is
  **credit burn, not cash**"* | line ~8050
- `D-153 §3 --withdraws--> D-136/D-139` | exact quote: *"**the parked r = 5 capacity purchase (+3
  tasks, ~$43/month, D-139 §2) is withdrawn, not deferred.**"* | line ~9078. **Who withdrew:** the
  user — D-153 §3's heading reads *"(user: only 1 needed, record to raise at integration)"* and
  D-153's context says *"The user answered every item on the D-152 backlog."* The *reason* given is
  *"It was priced for a concurrency figure that was self-authored, never applied … so there is
  nothing to undo and nothing to buy. **Revisit at integration**."*
- `D-153 §3 --declines-a-reduction, by recommendation-->` | *"the recommendation is **don't**
  [learning-api 2 → 1] … **$14/month is not worth spending gate-evidence integrity on**"* | line ~9072

**Status tags updated on superseded entries?**

- D-133: **NO** — `(accepted, 2026-07-31)`; heading still carries "~$216/month" and "Criterion 8 is
  met at 4 of 4".
- D-134: **NO** — `(accepted, 2026-07-31)`
- D-136: **NO** — `(accepted, 2026-07-31)`
- D-139: **NO** — `(accepted, 2026-07-31)`
- D-153: **NO** — `(accepted, 2026-08-02)`

**Candidate ACTIVE decision:** **D-153 §3 — no capacity purchase; r = 5 withdrawn (not deferred);
learning-api stays at 2 tasks, chat-api at 1; revisit at integration when peak concurrency is
measured.**

**Historical-but-must-stay-discoverable:** D-133 (the $216 arithmetic and the connection-ceiling
table are the reference every later correction is stated against; also §3(a)'s *"150 has never been
validated as a requirement"*, still unresolved); D-134 (the queueing-vs-work measurement and the
r-ratio framing); D-136 §5 (the p95 ≈ 0.31 s × (r/2.5)^1.4 model, its ⚠️ non-extrapolability, and the
`db.t4g.small` Free-Tier rejection lead-time warning — a live prerequisite if 150 is ever pursued);
D-139 (the real ARM rates, and §3's credit-burn finding whose carry-over *"the date at which any of
it becomes payable is **unknown**"* is not closed in this chain).

**Ambiguities/uncertainty:** (1) D-136's r = 5 is a **recommendation**, not a user decision; the only
user decisions in the chain are D-133's "defer" and D-153 §3's "withdraw". (2) D-136's per-task price
($54/mo at D-133's figure) and D-139's ($43/mo) coexist; D-153 §3 quotes D-139's. (3) The
150-concurrent question (~$173–433/mo plus an RDS resize) is neither withdrawn nor approved — it is
parked behind an unsent org message. (4) D-139 §3's credit-exhaustion date remains unknown.

**Confidence:** HIGH.

#### CHAIN F6 — Retention assumption

**Links**

- `D-072 --accepted-risk-->` | *"**Explicitly NOT built, documented residual risk …:** name detection
  in free text is unreliable and not attempted - only email/URL/phone patterns are redacted."* |
  line ~1616. Its 90-day premise is a bare mitigation bullet: *"90-day retention
  (`TutorChatMessageRepository.purge_older_than`, `make chat-purge`)."* | line ~1614. **Note:** D-072
  itself does **not** say the acceptance is *conditional on* the 90 days — that causal reading is
  supplied later, by D-114 and D-126.
- `D-114 --restores-the-boundary--> D-072` | broken-assumption language: *"D-072 accepted "names in
  free text may survive" *because* that text lived in a 90-day-purged table, and S25's consolidation
  then derived permanent, never-purged `semantic_memory.fact_text` from it, reaching parent-visible
  reports."* | line ~5392
- `D-114 §1 --windows, user decision-->` | *"**1. Windows and keys (user, this session): 90 / 90 /
  365**"* | line ~5399
- `D-126 §2 --generalizes-the-lesson--> D-072/D-114` | *"**§5.15's retention boundary is the clearest
  example in the codebase of why accepted risks need re-reading.** … The acceptance did not change;
  **its mitigating assumption silently stopped holding**, which is the most dangerous shape a
  documented risk takes"* | lines ~6748–6752
- `D-333 --three-windows-implemented, dry-run default-->` | *"**Date:** 2026-08-15 · **Status:**
  implemented, **dry-run by default**"* and the three windows: *"completed learning **30 days**
  (SPEC's own number) | abandoned/pending learning **90 days** inactivity | chat **180 days**
  inactivity"* | lines ~23839, ~23857–23859. The user's rule quoted verbatim in-entry: *"Keep both
  chat and abandoned/pending checkpoints on a 90-day inactivity retention window. Before deleting any
  eligible checkpoint, run long-term memory consolidation first"* — with the chat window later revised
  to 180 days in the user's second quoted instruction.

**Status tags updated on superseded entries?**

- D-072: **NO** — `(accepted, 2026-07-20)`; the residual-risk paragraph is unannotated despite D-114
  and D-126 both recording that its mitigating premise broke.
- D-114: **NO** — `(accepted, 2026-07-29)`
- D-126: **NO** — `(accepted, 2026-07-30)`
- D-333: heading has **no parenthetical tag**; separate line reads
  `**Status:** implemented, **dry-run by default** · **Follows:** D-331, D-332`.

**Candidate ACTIVE decision:** **D-114 §1 (90/90/365 on
`semantic_memory`/`stage_transitions`/`student_reports`, one daily `retention-purge` job)** for
derived text, **plus D-153 §2 (365 days on `learning_events`)**, **plus D-333 (30/90/180 checkpoint
windows, dry-run by default)** for LangGraph checkpoints. These are **three distinct, coexisting
policy sets, not a single superseding line.**

**Historical-but-must-stay-discoverable:** D-072 (the wire-allowlist extension, `redact_free_text`,
the safety screen and the "how to apply" pattern are all still binding; only its 90-day-premise
reading is superseded); D-126 §2 (the "accepted risks need re-reading" lesson and the D-123
expiry-condition practice it motivates); D-114 §4 (the unfulfilled privacy-notice obligation — *"the
notice must state the 90-day chat window, the 90-day derived-fact window, the 365-day report
window"* — carried on PROGRESS.md and **not discharged** by anything in this chain, and now arguably
stale given D-153's 365-day `learning_events` window and D-333's 180-day chat checkpoints).

**Ambiguities/uncertainty:** (1) **D-333's "three windows" are not D-114's three windows.** D-114 =
90/90/365 on derived-text tables; D-333 = 30/90/180 on checkpoints. Presenting D-333 as the terminus
of D-114's chain conflates two policy families; **D-333 does not cite D-072, D-114 or D-126 at all**
(it cites D-331/D-332). (2) D-333 is **dry-run by default**, so it is a shipped-but-not-enforcing
policy — its windows are not yet deleting anything. (3) D-114's own §3 note that neither purge job
could delete a row until ~2026-10-20 (per D-135 §4) means the 90/90/365 windows were still
unexercised against real data at the time of these entries. (4) The privacy-notice obligation now
spans at least five windows across three entries with no single reconciled statement.

**Confidence:** HIGH on D-072→D-114→D-126; **LOW on D-126→D-333 being the same chain.**

#### Theme F consolidated tag table — every entry read, heading tag verbatim

| Entry | Line | Status tag exactly as written | Ever updated? |
|---|---|---|---|
| D-002 | 14 | `(accepted, 2026-07-13)` | no |
| D-004 | 29 | `(accepted, decided at S32 2026-07-22, proposed 2026-07-13)` | no tag change; body amended in place (lines 39–52) |
| D-006 | 60 | `(accepted, 2026-07-15)` | no |
| D-072 | 1585 | `(accepted, 2026-07-20)` | no |
| D-082 | 2254 | `(accepted, 2026-07-21)` | no |
| D-083 | 2283 | `(accepted, 2026-07-22)` | no |
| D-084 | 2338 | `(accepted, 2026-07-22)` | no tag change; dated addendum appended (2651) |
| D-085 | 2795 | `(accepted, 2026-07-23)` | no |
| D-092 | 3091 | `(accepted, 2026-07-23)` | no |
| D-093 | 3158 | `(accepted, 2026-07-23)` | no |
| D-096 | 3441 | `(accepted, 2026-07-24)` | no |
| D-097 | 3600 | `(accepted, 2026-07-24)` | no tag change; addendum appended (3730) |
| D-111 | 5112 | `(accepted, 2026-07-28)` | no |
| D-114 | 5389 | `(accepted, 2026-07-29)` | no |
| D-126 | 6709 | `(accepted, 2026-07-30)` | no |
| D-133 | 7376 | `(accepted, 2026-07-31)` | no |
| D-134 | 7434 | `(accepted, 2026-07-31)` | no |
| D-135 | 7608 | `(accepted, 2026-07-31)` | **no — and no in-body annotation either** |
| D-136 | 7681 | `(accepted, 2026-07-31)` | no |
| D-137 | 7807 | `(accepted, 2026-07-31)` | no |
| D-138 | 7910 | `(accepted, 2026-07-31)` | no |
| D-139 | 8014 | `(accepted, 2026-07-31)` | no |
| D-140 | 8075 | `(accepted, 2026-07-31)` | no |
| D-141 | 8163 | `(accepted, 2026-07-31)` | no |
| D-142 | 8350 | `(accepted, 2026-07-31)` | no |
| D-148 | 8635 | `(accepted, 2026-08-01)` | no |
| D-149 | 8689 | `(accepted, 2026-08-01)` | no |
| D-153 | 9020 | `(accepted, 2026-08-02)` | no; §5 self-corrects in place (`⚠️ CORRECTED the same day — see §7, which supersedes that reading`, line 9111) |
| D-167 | 10341 | `(accepted, 2026-08-03)` | no; in-body `✅ VERIFIED BY THE USER 2026-08-04` |
| D-310 | 22172 | `### D-310 — …` no parenthetical; `**Status:** leak fixed at the source; rotation declined by the user` | n/a |
| D-333 | 23837 | `### D-333 — …` no parenthetical; `**Status:** implemented, **dry-run by default** · **Follows:** D-331, D-332` | n/a |
| D-388 | 26980 | `(accepted, 2026-08-17)` | no |

### Theme G — Freeze & security (G1–G7)

*All seven chains verified by direct reads.*

#### CHAIN G1 — Integration freeze

**Links**

- `D-151 --superseded-in-posture-by--> D-152` | *"This supersedes the 'unblock S44 as soon as
  possible' posture that D-151's recommendations were written under."* | line ~8956
- `D-151 --urgency-withdrawn-by--> D-152` | *"Consequence: D-151's 'fix the dev fake' urgency is
  withdrawn."* | line ~8973
- `D-152 --backlog-answered-by--> D-153` | *"The user answered every item on the D-152 backlog."* |
  line ~9022
- `D-153 §5 --self-corrected-same-day-by--> D-153 §7` | *"⚠️ CORRECTED the same day — see §7, which
  supersedes that reading."* | line ~9111; and *"That supersedes §5's 'leaving client-supplied roles
  as-is'"* | line ~9132
- `D-152 --reconfirmed-by--> D-417 §A1` | *"D-152 is unchanged and is not 'nearly met' — it is closed
  until reopened."* | line ~28270

**Status tags updated on superseded entries?**

- D-151 heading verbatim: `## D-151 — S42 discovery answered from the production system's own source: O1b is feasible, the dev fake models a system that does not exist (accepted, 2026-08-01)`
  — **NOT updated**; no "superseded" marker despite §2's O1b recommendation and its dev-fake urgency
  being withdrawn. (D-417 §A1 explicitly re-states *"O1b stays a *recommendation* rather than a
  finding."*)
- D-152 heading: `## D-152 — sequencing: finish and test this codebase against the fakes first, integrate later (accepted, 2026-08-01)`
  — unchanged, **correctly so** (it is the active one).
- D-153 heading: `## D-153 — the parked decisions are answered: budget raised to the real cohort, `learning_events` gets a retention promise, capacity stays put, and the timezone question is closed by evidence (accepted, 2026-08-02)`
  — unchanged; the §5→§7 correction is marked **inline** at line 9111 with a ⚠️ pointer, which is the
  strongest in-file correction convention used anywhere in this chain.
- D-417 heading: `## D-417 — Twelve open items decided in one pass, and the video figure that was wrong by two orders of magnitude (accepted, 2026-08-18)`.

**Candidate ACTIVE decision:** **D-152**, reconfirmed verbatim by **D-417 §A1** (2026-08-18):
integration frozen until the user explicitly reopens it; D-152 §5's standing instruction (no
reachability measurement, no prod API URL, no test account, no auth finalization, no dev-fake
rewrite) is live.

**Historical-but-must-stay-discoverable:** D-151 (the only record of the production-source findings,
the six schema mismatches, KC2/KC3, and the O1b feasibility evidence — all still cited by later
entries); D-153 §5 (must stay readable next to §7 or §7's correction loses its subject); D-153 §7
(the standing S43/S44 role-allowlist constraint that survives any production-side fix).

**Ambiguities/uncertainty:** D-151's heading still reads plain `accepted` while two of its
load-bearing recommendations (fix-the-fake urgency; O1b as the pre-S44 decision) have been
withdrawn/demoted — a reader landing on D-151 alone gets a stale posture. D-153 §7's "supersedes"
applies to a *section*, not an entry, so entry-level tagging cannot express it.

**Confidence:** HIGH

#### CHAIN G2 — Branch locator privacy

**Links**

- `D-045 --caveat-upgraded-to-finding-by--> D-101 §4` | *"D-045's residual caveat is upgraded to a
  finding (AUD-C-03), and its 'not eliminable' is withdrawn."* | line ~4147
- `D-045 --two-claims-superseded-by--> D-113 §1` | *"This supersedes two claims in D-045."* |
  line ~5293 (the two: "briefly" → *"the unbounded lifetime of the thread"*; and "removal would mean
  disabling checkpointing for one specific node" → *"was wrong"*)
- D-045's original caveat verbatim: *"Residual caveat, not fully eliminable:"* … *"Removing this would
  mean disabling checkpointing for one specific node, which isn't supported without forking
  LangGraph's own architecture; not attempted this session."* | lines ~865–871

**Status tags updated on superseded entries?**

- D-045 heading verbatim: `## D-045 — Branch Locator: consent comes *before* any location is collected; the location itself travels only in the `interrupt()` resume value, never through `TurnContext`/`QAState` (accepted, 2026-07-18)`
  — **NOT updated**, and no inline note points forward to D-101/D-113. **This is the weakest link in
  the chain:** D-045's body still asserts "not fully eliminable" and "briefly", both of which were
  measured false.
- D-101 heading: `## D-101 — S37 (AUD-C, chat product correctness): the golden eval was measuring the mock, three P1s found, and the retrieval-quality categories are now measured rather than gated (accepted, 2026-07-25)`.
- D-113 heading: `## D-113 — AUD-C-03 and AUD-F-14: the coordinates purge, the scaling-signal swap, and the re-baseline that found the baseline gone (accepted, 2026-07-28)`.

**Candidate ACTIVE decision:** **D-113 §1** — `purge_resume_writes` deletes `checkpoint_writes` rows
with `channel = '__resume__'` after a `location_consent` resume, scoped deliberately to locator
resumes; checkpointing intact.

**Historical-but-must-stay-discoverable:** D-045 (the consent-before-collection architecture and the
SPEC §5.22 fallback behaviour are still the active design; only two claims inside it are dead) and
D-101 §4/§5 (the measurement method — decode msgpack, never a text cast — which D-113's regression
test depends on).

**Ambiguities/uncertainty:** D-113 §1 records *"Not yet on staging"* at the time of writing; nothing
read here confirms the post-deploy live probe was taken. A reader arriving at D-045 first has no
forward pointer at all.

**Confidence:** HIGH

#### CHAIN G3 — Tutor/manager read-scope (D-086 / §7-R8)

**Links**

- `D-086 --unfixed-carry-over--> (self)` | heading: *"(accepted as launch-blocking carry-over, not
  fixed, 2026-07-23)"* | line 2843; body: *"This is a launch blocker, not urgent, but must be resolved
  before real go.intellichoice.org tutor/branch_manager tokens are accepted"* | ~2876
- `D-086 --NOT fixed by--> D-107` | *"The read half needs the tutor-assignment/branch-roster model
  ProfileAdapter gains in S43 (D-086's accepted risk since S33, formal disposition at S46), so it is
  left with a pointer rather than half-guessed."* | line ~4654
- `D-086/AUD-L-07 --formally accepted as §7-R8 by--> D-123 §1` | *"AUD-L-07's read half and
  AUD-X-07's remaining halves are accepted as documented residual risks §7-R8 and §7-R9"* |
  line ~6483; expiry: *"R8 expires at first real traffic."* | line ~6497; closure owner: *"S43/S46 for
  R8"* | line ~6500

**What D-107 *did* fix:** AUD-X-01 (owner-rebind), AUD-X-05 (`access` required, 14 sites classified:
9 write / 5 read), AUD-X-02 (consent gate repeated on both SSE routes), AUD-C-01 + AUD-C-04
(ownership check on `/messages`, no owner-drop). Writes fail closed; **the read half was left open on
purpose** — *"A read-scope gap discloses data that already exists; the same fall-through on a *write*
fabricates data that does not"* (~4651).

**Status tags updated on superseded entries?**

- D-086 heading already carries an accurate **non-standard** tag:
  `(accepted as launch-blocking carry-over, not fixed, 2026-07-23)` — correct and self-warning; **no
  later amendment**, which is consistent since nothing closed it.
- D-107 heading: `## D-107 — S40: four authorization P1s, and the two tests that were weaker than they looked (accepted, 2026-07-27)`.
- D-123 heading: `## D-123 — Criterion 2's ordering call, made: two P1 halves accepted into §7 rather than fixed against the clock (accepted, 2026-07-30)`.

**Candidate ACTIVE decision:** **D-123 §1** — R8 accepted as a documented, *expiring* residual risk
(expires at first real traffic; fix owned by S43/S46). D-086 remains the substantive description of
the gap.

**Is there ANY later entry closing R8? NOT FOUND.** Targeted greps for `R8`, `D-086` and `AUD-L-07`
across the file return no closure. The last three references all treat it as open: line ~6753 (R8/R9
given expiry conditions rather than closure), line ~7041 (*"§7-R8's actual fix lives"* in S43, gated
on unsent org asks), and line ~15089 inside
`## D-216 — a code-level walk of the learning flow, and the fourteen things it found (accepted, 2026-08-07)`:
*"POST /students/{id}/report's access='read' is a written, reasoned disposition (D-086's read-scope
gap, owned by S43/S46) - not re-decided."* Since S43 integration is frozen by D-152/D-417 §A1, R8's
named closure path is itself blocked. **The question remains open.**

**Ambiguities/uncertainty:** R8's expiry trigger ("first real traffic") and its closure owner
(S43/S46) are in tension with the integration freeze — the risk cannot be closed on the stated path
while integration stays frozen, and **nothing read states who reconciles that.**

**Confidence:** HIGH for the three links; MEDIUM-HIGH on "no closure exists" (grep-based across the
whole file, but keyed on `R8`/`D-086`/`AUD-L-07` tokens only).

#### CHAIN G4 — Secrets exposure & rotation

**Links (single entry, no supersession chain)**

- Leak mechanism: *"Running pgrep -fl … printed the process's environment, which contained
  STAGING_TOKEN_SECRET_LEARNING and STAGING_TOKEN_SECRET_CHAT in plaintext into the session
  transcript."* | ~22177
- The defect the leak exposed: *"Measured on a live run: 4 process-table lines carried an expanded
  secret"* … *"any local process could read both secrets with ps"* | ~22188–22191; the Makefile
  comment (from D-132) asserted the opposite: *"never in argv, ps, or a shell history"* | ~22186
- Fix: `e2e/config.ts` fetches both secrets itself via
  `execFileSync("aws", ["secretsmanager","get-secret-value","--secret-id", ...])`; only the secret
  **id** is on any command line; verified `0` expanded-secret process lines post-fix (was 4) |
  ~22204–22217
- Rotation decision (user, verbatim): *"Rotation: the user's decision was not to rotate, on the
  exposure being bounded — staging only, production (go.intellichoice.org) is a separate frozen system
  these do not touch, Postgres holds no PII by design (rule 1)"* | ~22219
- Standing residual named in **this** entry: *"the residual risk is Bedrock spend through an
  authenticated staging consumer, which the gateway caps"* | ~22221; and *"One thing this does not fix:
  the secret is injected into the ECS task at start, so a future rotation still needs the tasks
  restarted before the new value takes effect. Re-running deploy-staging.yml does that."* | ~22226

**Status tags updated on superseded entries?** Heading verbatim:
`### D-310 — Two staging secrets in the process table, documented as safe, and my own disclosure`,
with a separate status line: `**Date:** 2026-08-13 · **Session:** C1 · **Status:** leak fixed at the source; rotation declined by the user`.
D-132's now-false Makefile comment is called out inside D-310 (*"the sentence asserting otherwise is
why nobody checked in the ten sessions since D-132 wrote it"*, ~22193) but **D-132's own entry was not
read here and no tag update on it is evidenced**.

**Candidate ACTIVE decision:** **D-310** — leak fixed at source (secrets fetched in-process by id);
**rotation declined by the user**, with the exposure-bounded rationale recorded as a deliberate
departure from the runbook default.

**Historical-but-must-stay-discoverable:** D-310's measurement-error paragraph (`grep` matching its
own command line; *"A canary test that does not reproduce a defect you have already seen is a broken
test, not an absolution."*) and the D-132 comment critique — both are the reusable lessons.

**Ambiguities/uncertainty:** **this** entry states **no** expiry or reopen condition on the no-rotate
decision beyond the bounded-exposure facts it lists. The "until staging stops being synthetic" style
condition is **NOT present in D-310** — if it exists it lives elsewhere (`OPEN_DECISIONS` #8), which
was not read per instruction. So per this entry alone the decline is unconditioned, though its stated
rationale depends on staging remaining synthetic/PII-free — an implicit, unwritten condition.

**Confidence:** HIGH

#### CHAIN G5 — Org time convention

**Links**

- `D-130 --provisional-default--> (self)` | *"Default: local_dst_aware + America/Chicago,
  unconfirmed."* | line ~7098; and *"ORG_TIME_CONFIRMED changes no behavior at all. It only lowers a
  startup log line from WARNING to INFO."* | ~7091
- `D-130 --question-closed-by-evidence-in--> D-153 §4` | *"The org runs neither window, so the
  conventions produce identical dates and identical weeks for every published session"* | line ~9089;
  Message A demoted: *"So Message A stops being a blocker of any kind and becomes a courtesy
  question."* | ~9094; the provisional default survives: *"The provisional default (America/Chicago,
  local_dst_aware) stands and ORG_TIME_CONFIRMED stays false, which is honest"* | ~9095
- `D-130 --extended-to-the-frontend-by--> D-324 §1` | *"The zone is now served —
  DashboardResponse.org_time_zone, from resolve_org_time()"* | line ~23057; and it explicitly refuses
  a client constant: *"org_time.py's own rule is one variable, both apps, no way to skew them, and a
  third copy in the frontend would silently keep Chicago the day ORG_TIMEZONE is confirmed to anything
  else."* | ~23059
- `D-324 §2 --fixes-UTC-bucketing-bug-->` | *"_accuracy_trend bucketed attempts on
  attempt.responded_at.date() — the UTC day. 02:00 UTC is 21:00 the previous evening in Central"* …
  *"Fixed to bucket on org_time.local_date_key()"* | lines ~23077–23080

**Status tags updated on superseded entries?**

- D-130 heading verbatim: `## D-130 — The org's time convention becomes a switch with a provisional default, because the answer is theirs and the code needed one anyway (accepted, 2026-07-30)`
  — **not amended, and correctly so**: D-153 §4 and D-324 *extend* rather than reverse it. The switch,
  the three env vars and the unconfirmed default all remain live.
- D-153 heading as quoted in G1 (unchanged). D-324:
  `### D-324 — The org's day, and a premise that a test refused`, status line
  `**Date:** 2026-08-14 · **Session:** U1 · **Status:** four items done, one deliberately left as an instrument, one narrowed on evidence`.

**Candidate ACTIVE decision:** **D-130 mechanism + D-153 §4 disposition + D-324 §1–2 extension** —
`local_dst_aware`/`America/Chicago` provisional, `ORG_TIME_CONFIRMED=false` (WARNING every startup),
convention known not to matter operationally, zone served to the client (client fallback `UTC`, never
Chicago), day-bucketing on `local_date_key()`.

**Historical-but-must-stay-discoverable:** D-130 §1 (the Sunday-evening/UTC week-key defect and why
it was invisible: fixture and query wrong together) and §4 (Message A was asking the wrong question —
display offset vs. week boundary); D-153 §4's stated limits (marketing-site evidence, hence the S43
guard: assert no session starts 00:00–01:00 local or Sunday evening and log loudly).

**Ambiguities/uncertainty:** D-153 §4's durable form is a **guard owed at S43** — and S43 is frozen
(D-152 / D-417 §A1), so that guard is presumptively unbuilt; **nothing read confirms it exists.**
`ORG_TIME_CONFIRMED` remains false across all three entries, so the *zone* is still inferred from
someone else's hard-coded −6. D-324 §1 also notes a `display_time_zone()`-vs-`timezone_name` trap
under `legacy_fixed_utc_minus_6` (POSIX sign inversion: `Etc/GMT+6` *is* UTC−6).

**Confidence:** HIGH

#### CHAIN G6 — Multi-child switcher

**Links**

- `D-176 §2 --deliberate-exclusion-->` | *"Known limitation, deliberate: a multi-child parent switches
  children by signing out and back in. A persistent switcher is new UI, which the decision explicitly
  excluded."* | line ~11631
- `D-176 --reversed-by--> D-184` | heading: *"a multi-child parent switches children in-app, reversing
  D-176's deliberate exclusion"*; body: *"That cost was carried as an open product question from D-176
  through D-183 and marked low stakes. The user resolved it this session: build the switcher."* |
  lines ~12397, ~12402

**User attribution: CONFIRMED explicitly** — *"The user resolved it this session: build the
switcher."* (~12403). Note D-176 §2 also records an earlier user choice on the adjacent question:
*"the user picked one before any code: at login (over 'at dashboard entry')"* (~11608). **So both the
exclusion and its reversal are user decisions, not recommendations.**

**Status tags updated on superseded entries?**

- D-176 heading verbatim: `## D-176 — the two decided findings implemented, and D-175 landed with its owed live rows measured (accepted, 2026-08-04)`
  — **not amended**; the reversal is discoverable only from D-184's heading pointing back. D-176 §2's
  "Known limitation, deliberate" bullet is now false and carries no correction marker.
- D-184 heading verbatim: `## D-184 — a multi-child parent switches children in-app, reversing D-176's deliberate exclusion (accepted, 2026-08-05)`.

**Candidate ACTIVE decision:** **D-184** — in-app switcher on the start screen only (no backend
change; `ChildSelectionScreen` reused with optional `title`/`onCancel`; Cancel leaves the current
child bound; `nodes.bind()`'s refusal to move a live session is respected by construction, not by a
runtime check).

**Historical-but-must-stay-discoverable:** D-176 §2 (login-time resolution,
`GET /learning/parents/me/children`, login-scoped binding via `forgetStudent`, and why the
`test.fail()` probe could not flip) — D-184 is only intelligible against it; also D-176 §1's
CloudFront `/dev/token` path-routing residual, unrelated to this chain but recorded nowhere else.

**Ambiguities/uncertainty:** only that D-176's stale bullet is untagged. A later mention (~12463)
notes something *"made D-176's accepted cost milder than it read"*, which was not opened — a possible
third, softer link in this chain.

**Confidence:** HIGH

#### CHAIN G7 — Session renumbering

**Links (structural, not supersession)**

- `D-049 --renumbers--> old S17–S23` | *"Renumbering map (old → new):"* table | lines ~964–974:
  S17 Memory system → **S25**; S18 Multimodal solution images → **S29**; S19 Evaluation platform →
  **S30**; S20 Observability → **S31**; S21 Deployment → **S32**; S22 Security hardening → **S33**;
  S23 Load testing → **S34**.
- Translation rule verbatim: *"every PROGRESS.md/DECISIONS.md reference written *before* 2026-07-18
  uses the old numbering (e.g. S13's 'revisit at S20 (observability)' now means S31 …). References
  from S17 onward use the new numbering. Do not renumber historical log entries - the map above is the
  translation layer."* | ~983–986
- New sessions inserted into the freed slots: S17 (test-debt + real org content, C1/X1), S18
  (structured events, C2), S19 (access-aware refusals + welcome/suggestions, C3), S20 (authored
  question bank, L1), S21 (personalized hint ladder, L2), S22 (assessment policy + exam backend, L3),
  S23 (exam frontend, L4), S24 (contextual learning chat, L5), S26 (stage narratives, L7), S27
  (YouTube hardening, L8), S28 (dashboard + report, L9).

**What a reader must know to interpret old session references:** **the same string "S20" means two
different sessions depending on the writing date.** Pre-2026-07-18 "S20" = Observability (now S31);
post-2026-07-18 "S20" = the authored question bank. Same collision for S17 (Memory → now S25, vs.
test-debt/org-content), S18, S19, S21, S22, S23. Historical entries were deliberately **not**
rewritten, so **any audit that pattern-matches session ids across the whole file without checking the
entry date will mis-resolve at least seven ids.** Also recorded here: three expansion decision gates
requiring sign-off at the named session's start (team-member names vs. schema-purity denylist at S17 —
see D-050; the §5.30.1 payload widening at S21, hard-blocking S24's chat; the exam grading-model/timing
choice at S22).

**Status tags updated on superseded entries?** Heading verbatim:
`## D-049 — Roadmap restructured after S16: expansion plan absorbed as S17–S28; former S17–S23 renumbered to S25/S29–S34 (accepted, 2026-07-18)`.
No earlier entry was retagged **by design** — the entry states the non-renumbering rule explicitly as
its "How to apply".

**Candidate ACTIVE decision:** **D-049** — still the live translation layer; nothing read supersedes
it, and D-086's own text ("S28/D-077", "Session 13") relies on it.

**Ambiguities/uncertainty:** the map covers old S17–S23 only; old references to sessions **above** S23
(if any pre-date the restructure) have no stated translation. S25 appears in the map's target set
(S17→S25) while S25 is not listed among "New sessions", which is consistent but easy to misread.

**Confidence:** HIGH

> **Theme G cross-chain observation.** The file's own header (line 4) declares
> `Status: proposed | accepted | superseded.` In practice **no** superseded entry in these seven
> chains had its heading retagged: D-151, D-045 and D-176 each retain a bare `(accepted, …)` tag while
> carrying claims later measured false or reversed by explicit user decision. Supersession is
> expressed only forward (in the superseding entry's prose) and never backward, so any reader who
> lands on the older entry by grep gets the stale claim with no warning. The one exception is
> **D-153 §5**, which carries an inline `⚠️ CORRECTED the same day — see §7` marker — the only backward
> pointer found, and the model worth reusing. **D-086** is the other well-behaved case, via a
> self-warning non-standard tag (`accepted as launch-blocking carry-over, not fixed`) rather than a
> retro-edit.

### Theme H — Access-probe & chat (H1–H5)

> Note on the log's own vocabulary (line 4): *"Status: proposed | accepted | superseded."* —
> `superseded` is an available tag. **It is used on zero headings in any of these five chains.** Every
> entry below retains its original status tag; supersession is expressed only in prose inside the
> *later* entry (and occasionally as a dated blockquote correction inserted into the earlier entry's
> body).

#### CHAIN H1 — Access-probe rule evolution

**Links** (all 15 named entries were read; depth notes at the end)

- `D-164 --wrong-for-a-measured-reason--> D-165` | *"What I recommended in D-164, and why it was wrong.
  Keyword coverage ≥2/3 measured 8/8 against the eight hand-written role-gated cases."* | line ~10084
- `D-165 --self-correcting addendum--> D-165-addendum` | *"Not verified live, and the measurement says
  why: access_probe_max_distance = 0.40 is too tight for human phrasing."* | line ~10157
- `D-165 --> D-166 (ceiling 0.40→0.45)` | *"Closes AUD-C-21 and retires the real-model
  role_gated >= 0.95 assertion that D-165 found unpassable."* | line ~10185
- `D-166 --> D-166-addendum (files AUD-C-22)` | *"And it names the wrong tier — filed as AUD-C-22."* …
  *"not fixable by widening the ceiling"* | line ~10308
- `D-166 --> D-168 (rejects AUD-C-22's own proposed fix)` | *"The finding's own proposed fix does not
  work, and that is the first result. AUD-C-22 proposed returning per-audience distances and picking
  the closest. Measured, nearest <=0.45 scores identically"* | line ~10416
- `D-168 --carry-over corrected in D-169's session--> D-169` | *"Correction (2026-08-03, D-169's
  session): that carry-over is wrong and is closed without a change."* | line ~10569 — **the corrected
  carry-over is the `cryptography`/PyMySQL dependency note, not anything about the access probe.**
  D-169's own body (10580–10639) is AUD-L-12 `recommended_difficulty` and contains no access-probe
  content. The chain's framing "corrects D-168's carry-over" is literally true but **off-thread** for
  the probe rule.
- `D-177 --floor, not margin--> supersedes D-168/D-175's fork framing` | *"AUD-C-23: the margin was
  never the knob — the floor was, and raising the floor alone would have resurrected AUD-C-22"* |
  line ~11693 (shipped: `ACCESS_PROBE_RERANK_MIN_SCORE` 0.8 → **0.9** + pre-floor margin)
- `D-177 --> D-178 (0/10 live, not a certification)` | *"The sample size adequate to detect a 60% rate
  is not adequate to certify a low one. … Nothing here licenses writing 'never'."* | line ~11772
- `D-178 --files AUD-C-25, corrects D-177-->` | *"So D-177 §2's '0 wrong tiers, 0 false hints, 0/40
  stability fires' is true of the harness's rule and does not cover production's composed path"* /
  *"This corrects a claim made earlier in this session"* | line ~11809
- `D-178 --> D-179 (--shipped replay; false hint found)` | *"So D-177's 'zero false hints on both
  negative classes in both arms' is wrong in exactly one cell, and right everywhere else."* |
  line ~11886; files AUD-C-26 (`probe-public-025` → `required_role: "parent"` for public content,
  ~11902)
- `D-179 --> D-180 (silence-on-ambiguity)` | *"The user chose (a) silence on ambiguity from four
  options that were measured before being chosen"* | line ~11930; severity: *"Severity is re-argued
  from P2 to P3 on the finding itself: a real gap in a stated rule … with no demonstrated user
  exposure."* | line ~12023
- `D-219 --carry-over premise refuted--> D-220` | *"D-219's carry-over ranked first in the
  next-session pointer: 'the access hint is built and still unreachable.' That premise is wrong"* |
  line ~15614; defect is rendering: *"A logged-out parent read … twice, stacked."* | ~15651; live 22/38
  (~15690)
- `D-220 --> D-221 (its two carried-over findings)` | *"34 of 38 was the ceiling D-220 measured; it is
  now 37 of 38."* | line ~15813; and *"D-219's fix was not merely imprecise, it was inert"* …
  *"unreachable through the graph from the day it shipped"* | ~15815/15826
- `D-351 --removed required_role, broke the instrument--> D-359` | *"D-351 removed that field on
  purpose … The script was not updated in the same change, so … a question that did produce a hint
  raised KeyError and was tallied as an error rather than a hit."* | line ~25505
- `D-359 --> D-371 (re-swept, item closes)` | *"D-359 recommended adding the eight live guest-probe
  questions to probe_eval.yaml and re-sweeping … Done."* | line ~25918; closing language: heading status
  **"measured, deliberately not tuned — the item closes"** (~25916) and *"This is not a tuning problem.
  The signal does not carry the distinction, and D-359's recommendation has now been carried out to the
  point where it says so with numbers."* | ~25961
- `D-351 --amends SPEC-->` | *"**Amends SPEC §5.19.4, adds §5.19.5**"* (heading metadata, ~25118) and
  *"SPEC was amended rather than deviated from. §5.19.4's response text and the new §5.19.5 reason table
  were written in the same change as the code"* | ~25214

**Status tags updated on superseded entries? None.** D-164 (accepted, 2026-08-03) — unchanged despite
D-165 declaring its rule wrong. D-165, D-166, D-168 — all still `(accepted, 2026-08-03)`; each carries
a self-authored addendum instead. D-177 still `(accepted, 2026-08-04)` although D-178 §4 and D-179 §2
correct its headline numbers. D-359 still "measured, deliberately not tuned" (unchanged after D-371
closed the item). D-351 "implemented" — unchanged after D-359 found it broke
`measure_access_hint_live.py`. **The only in-place edit found anywhere in this chain is the dated
blockquote inserted into D-168 (~10569) attributed to D-169's session, and it concerns dependencies,
not the probe.**

**Candidate ACTIVE decision:** **D-371** for the *rule* (re-swept fixture, shipped `probe_access` =
29/0/16/0/0, nothing beats it, "the item closes"), with **D-180** as the last entry that changed probe
behaviour (`_lexical_only` returns `{}` unless exactly one audience matched) and **D-351** as the
active *API-surface* decision (hint names no tier; SPEC §5.19.4/§5.19.5).

**Historical-but-must-stay-discoverable:** D-164 (keyword ≥2/3, the rejected rule + the user
disposition on escalation address/anonymous escalation), D-165 (0.40 ceiling, keyword-arm-kept
rationale for mock observability), D-166 (0.45, relative-margin negative control, four-site constant),
D-168 (rerank+margin design, HyDE and 0.9-floor negative results, the moved model boundary), D-177
(floor 0.9 + pre-floor margin, knife edges), D-178 (AUD-C-25, the certify-vs-detect rule), D-179
(`--shipped`, AUD-C-26), D-180 (P2→P3 re-argument, "measure the defect live before deploying its
fix"), D-220 (live 22/38 through routing; 11/38 is a sample), D-359 (KeyError,
fixture-easier-than-reality).

**Ambiguities/uncertainty**

- **D-168 → D-169 is mis-characterized in the chain brief.** The correction exists but is a dependency
  carry-over, not a probe carry-over. If the orchestrator expected "D-169 corrects D-168's probe
  carry-over" → **NOT FOUND**.
- **D-180 → D-220 has no stated relation.** D-220's antecedent is D-219's carry-over; it references
  AUD-C-23's rerank-quantization mechanism (~15695) but never cites D-180. The two entries are ~3,600
  lines and several sessions apart; entries D-181–D-219 were not read.
- **D-221 → D-359** likewise has no stated link; D-359's stated antecedents are D-351 and
  AUD-C-21/AUD-C-16.
- **Numbers across the chain are not comparable**: 25/43, 23/38, 29/38 (fixture, corpus vs human
  phrasing), 27/38 (post-floor-raise), 26 then 29 (D-359/D-371 on a re-composed 45-gated fixture),
  22/38 and 11/38 (live through routing), 2/8 then "2 of the 6 it could reach" (D-371's denominator
  correction). **Any reader treating these as one series will be wrong.**
- D-180's own live row is **vacuous by its own admission** (scope guard, not the probe, produced the
  null) — so AUD-C-26's user-exposure question is recorded as permanently unanswerable.

**Confidence:** **HIGH** on every link quoted above and on the "no status tags updated" finding;
**LOW** on any claim that D-180→D-220 or D-221→D-359 are supersession links (no evidence).

**Links not re-verified:** intervening entries D-181–D-219 and D-222–D-358 (not read, so an unnamed
intermediate probe decision could exist); D-219 itself (read only as quoted by D-220/D-221); the SPEC
file, `access_probe_policy.py` and AUDIT_FINDINGS rows (out of scope — DECISIONS.md only).

#### CHAIN H2 — AUD-C-23 oscillation

**Links**

- `D-172 --files AUD-C-23-->` | *"And the run failed on something else entirely, now filed as AUD-C-23
  — D-168's own recorded false-hint residual, observed live, against an eval assertion written to a
  stricter standard."* | line ~10895
- `D-172 --> D-173 ("does not reproduce", 3 probes)` | *"And AUD-C-23 does not reproduce on the
  deployed corpus — access_hint: null, three probes, against a control that can fail. Re-scoped in
  place"* | line ~11026
- `D-173 --> D-174 (corpus diff = no difference; corrects D-173's claim)` | *"AUD-C-23's fork had been
  re-scoped by D-173 to a prior question … The answer is that they do not disagree."* | ~11211 and
  *"the honest claim is 'not observed in 3 probes' — and AUD-C-23's own text, which said the deployed
  system 'does not exhibit' the finding, was overstated by its own evidence. Corrected in place."* |
  ~11257
- `D-174 --> D-175 (reverses two sessions; 6/10 live)` | *"This is the session's main result and it
  reverses two sessions of reasoning."* | ~11422 and *"6 returned
  access_hint: {"required_role": "branch_manager"} and 4 returned the correct null refusal."* | ~11437;
  D-175 explicitly **deliberately not fixed** (~11458)
- `D-175 --> D-176 (landed + live-verified)` | *"D-175 landed and deployed, and AUD-L-01's live rows now
  read 404"* | ~11588 — **caveat: D-176 lands D-175's *other* work (AUD-L-01 `/dev/token` 404,
  AUD-F-22, AUD-L-08). It contains no AUD-C-23 fix**, because D-175 deliberately did not fix it. The
  chain's "deployed+live-verified" applies to D-175's session, not to AUD-C-23.
- `D-176 --> D-177 (re-measured: the floor was the knob)` | *"The fork was recorded as 'tighten the
  margin vs. accept and name'. The re-measurement the user required before any tune is what caught the
  misnomer."* | ~11695
- `D-177 --> D-178 (re-baselined)` | *"correct_refusal_rate 97.3% (36/37) is the genuinely new number,
  and it re-baselines rather than proves a delta: the historical comparators (79.5% / 87.2% / 73.8%)
  come from different configs and eras."* | ~11794
- `D-178 --> D-179 (harness never matched production)`. **Which earlier numbers are cast into doubt —
  verbatim:** *"So D-177 §2's '0 wrong tiers, 0 false hints, 0/40 stability fires' is true of the
  harness's rule and does not cover production's composed path on the decisive question. This corrects
  a claim made earlier in this session ('the tables were measured with this exact code, so the numbers
  stand'): they were measured with a reimplementation of it."* (D-178 §4, ~11809–11812). D-179 then
  quantifies it: *"So D-177's 'zero false hints on both negative classes in both arms' is wrong in
  exactly one cell, and right everywhere else"* (~11886), and marks every non-`SHIPPED` row **`0+`** —
  *"a lower bound, since every row except SHIPPED is still a restatement that models no lexical arm"*
  (~11897). **Scope of doubt: every candidate row in the D-165/D-166/D-168/D-177 sweep tables'
  negative-class columns, not the live rows.** D-179 also names two of its own author's predictions as
  wrong (~11888).

**Status tags updated on superseded entries? None.** D-173 keeps `(accepted, 2026-08-04)` although its
central AUD-C-23 claim was withdrawn; the withdrawal is recorded in D-174 ("Corrected in place" refers
to the AUDIT_FINDINGS text, **not** to D-173's heading). D-174, D-175, D-176, D-177 all unchanged.

**Candidate ACTIVE decision:** **D-177 §2** as the shipped AUD-C-23 remedy (floor 0.9 + pre-floor
margin), **verified live by D-178** (0/10 target, 3/3 control), **with D-179's correction of its
measurement claims still standing.**

**Historical-but-must-stay-discoverable:** D-172 (the filing), D-173 (the withdrawn "does not
reproduce"), D-174 (corpus-identity evidence + "a corpus comparison must be made at the level the query
filter actually reads"), D-175 (the 6/10 measurement and the fixed-sample-size rule), D-178
(detect-vs-certify).

**Ambiguities/uncertainty:** D-176's role in this chain is **weak/indirect** — it deploys the session,
not the finding. The oscillation record is: filed (D-172) → "does not reproduce" (D-173) → corpus
eliminated, wording corrected (D-174) → reproduces 6/10 (D-175) → fork re-named, fixed (D-177) → live
0/10 but "not sufficient to certify" (D-178) → the instrument that chose the fix was not the fix
(D-179). Residual flip rate is bounded only at **<26%**; **nothing in the chain closes AUD-C-23 with a
"never".**

**Confidence:** **HIGH** (all eight links quoted from source; only the D-176 characterization is
softened).

#### CHAIN H3 — `.ics` / OPEN_DECISIONS #13

**Links**

- `D-352 --fix asserted-but-unverifiable--> D-392` | *"its own comment explains why nothing caught
  them: 'Chromium tolerates both, which is why the e2e suite (Chromium-only) has been asserting the
  button is visible and never that a download happens.'"* | ~27176 and *"both tests still pass. …
  D-352 remains unverified, and the reason is the suite's shape rather than the test's wording"* |
  ~27185; raises *"OPEN_DECISIONS #13"* (~27189)
- `D-392 --> D-397 (WebKit added, didn't catch it)` | *"Reverting downloadIcs to its pre-D-352 form and
  re-running: both specs pass on WebKit too."* | ~27361 and *"downloadIcs is still held by no browser in
  this suite, and #13 stays open in its residual form rather than being marked closed by the work that
  was supposed to close it."* | ~27377; also corrects its own author: *"#13's recommendation — which I
  wrote in D-392 — said WebKit 'is the strictest of the three…'"* | ~27358
- `D-397 --> D-399 (closes #13 by asserting the DOM contract)` | *"OPEN_DECISIONS #13 is closed by
  this, having survived two remedies that did not close it."* | ~27459; mechanism: *"No engine can be
  lenient about a call that was never made."* | ~27440

**Status tags updated on superseded entries? None.** D-352 still `**Status:** implemented` — never
annotated as unverified, even though D-392 states in terms that it *"remains unverified"* and D-399 is
the third attempt to hold it. D-392 and D-397 remain `(accepted, 2026-08-17)`; D-397's own text says it
keeps the WebKit project *"with every claim about it rewritten"* — that rewrite happened in D-397's
body, not in D-392's.

**Candidate ACTIVE decision:** **D-399** — `ics-download-dom-contract.spec.ts` patches
`HTMLAnchorElement.prototype.click`/`URL.revokeObjectURL` via `addInitScript` and asserts the code's DOM
contract; #13 closed.

**Historical-but-must-stay-discoverable:** D-352 (the actual product fix and the drifted
`calendar_event` fixture), D-392 (`calendar-branches.spec.ts` + the falsification-that-did-not-fail +
the corrected header claim), D-397 (WebKit project **retained** for iOS-engine coverage, positive
control `PROOF-THE-EDIT-IS-LIVE.ics`, the labelled guess that Playwright's download path may hide this
class from every engine, and the corrected CI-cost premise: `e2e-typecheck` never runs the suite).

**Ambiguities/uncertainty:** D-397's labelled guess (Playwright drives downloads via the automation
protocol) is explicitly *not measured* — so "no engine can catch this" remains a hypothesis. The WebKit
project outlives the reason it was bought, on a rationale (iPhone/iPad coverage) that was never the
decision the user made. **Whether D-352's *original* two bugs were ever user-visible in a real browser
is nowhere established.**

**Confidence:** **HIGH**.

#### CHAIN H4 — Frontend unit tests / OPEN_DECISIONS #14

**Links**

- `D-399 --raises the item (unnumbered)-->` | *"A frontend unit-test framework is still worth having,
  and is now recorded as its own item rather than smuggled in behind a one-line contract test."* |
  ~27456. **D-399 never writes "#14".** The number first appears in D-403. So "D-399 raises #14" is
  supported **by content, not by number** — preserve this ambiguity.
- `D-403 --third use case--> #14` | *"The property is real and belongs in a component unit test, which
  makes it OPEN_DECISIONS #14's third concrete use case after errors.ts's rules and downloadIcs's DOM
  contract."* | ~27663
- `D-404 --fourth use case--> #14` | *"Writing it needs either the frontend unit-test tooling of
  OPEN_DECISIONS #14 or a decision to ship it untested; that is the user's call, and this is now #14's
  fourth concrete use case."* | ~27710
- `D-405 --decides #14-->` | *"OPEN_DECISIONS #14 is decided: vitest + jsdom in both frontends."*
  **Went against a recommendation, and the decider is named:** *"The user chose both apps over my
  recommendation of one-first, on the D-347 argument — two independently deployed frontends drifting is
  this project's single most repeated defect shape, and starting asymmetric is starting with the bug.
  Fair, and the mirrored timer below is the immediate proof"* | ~27716–27719. D-405 also **explicitly
  excluded RTL**: *"Scope held deliberately: no @testing-library/react … it needs another dependency,
  and the rule here is two clear uses before an abstraction. It gets added when the first component test
  is written, not in advance."* | ~27757
- `D-405 --> D-413 (RTL adopted, closing D-405's own deferral)` | *"OPEN_DECISIONS #14 deliberately left
  it out until 'the first component test'; this session is that test, and the property being tested is a
  hook, which nothing else can drive. Added to both frontends per D-405's argument"* | ~28021; plus the
  harness defect: *"@testing-library/react registers its own afterEach(cleanup) only when the runner
  exposes globals, and this project's vitest config deliberately does not."* | ~28026
- `D-413 --> D-414 (last of the four assertions)` | *"The last of the four assertions OPEN_DECISIONS #14
  was raised for. D-403 wrote this one in a browser, measured it flaky (1 pass / 2 failures over three
  isolated runs) and deleted it"* | ~28084; counts: chat-web 6 → 36 (D-413, ~28080) → **42** (D-414,
  ~28124)

**Status tags updated on superseded entries? None.** D-405 remains `(accepted, 2026-08-18)` with its "no
RTL" scope line intact, even though D-413 adds RTL **the same day**; the reversal is recorded only in
D-413's body and is framed as *executing* D-405's stated condition rather than overturning it. D-403's
deferral and deleted test are likewise corrected only forward.

**Candidate ACTIVE decision:** **D-405** (vitest + jsdom in **both** frontends, user's call over the
recommendation) as extended by **D-413** (`@testing-library/react` in both, with `afterEach(cleanup)`
wired manually) — and **D-414** closes the fourth and last assertion #14 was raised for.

**Historical-but-must-stay-discoverable:** D-399's reason for *not* using jsdom that day; D-403's
flaky-and-deleted control test (the measurement 1 pass / 2 failures); D-404's `route.fulfill`
limitation; D-405's "two clear uses before an abstraction" rule and the two tooling mistakes the harness
caught within minutes; D-414's deliberate **non**-coverage of learning-web's banner and its stated
reason (*"Extracting the banner JSX into a component would move the markup and leave the condition
untested"*).

**Ambiguities/uncertainty:** whether #14 was formally raised by D-399 or only by D-403 **cannot be
settled from DECISIONS.md** (OPEN_DECISIONS.md not read). D-405's explicit "no RTL" and D-413's adoption
of RTL sit in the log **unreconciled at the heading level** — a reader landing on D-405 alone gets a
stale scope statement. D-414 records the learning-web asymmetry as carry-over, i.e. the D-347 defect
shape is **named, not closed**.

**Confidence:** **HIGH** on D-403→D-405→D-413→D-414; **MEDIUM** on `D-399 --raises--> #14` (content
match, no number).

#### CHAIN H5 — Chat turn lifecycle

**Links**

- `D-346 --deadline/lock/interrupt-disclosure-->` | *"Now asyncio.timeout(50), under CloudFront's 60s
  origin read timeout"* / *"pg_try_advisory_xact_lock(hashtext(...)) on the request's session"* |
  ~24791, ~24798. D-352 is the client half: *"the client times out at 55s, just above the server's own
  50s turn deadline (D-346)"* (~25056).
- `D-346 --> D-402 (Stop cancels server-side; corrects D-348's comment)` | *"client_turn_id already
  existed on the wire (D-348) and is already echoed on every snapshot, so no contract change was needed
  — but D-348's comment claimed it is 'never parsed, compared or stored anywhere else', and that is now
  false, so it was corrected rather than quietly violated."* | ~27596–27598. Mechanism measured:
  *"uvicorn does not cancel the ASGI task on disconnect, so nothing the browser does releases a
  transaction-scoped advisory lock"* (~27570). Also: *"Half of it was already fixed, which narrowed the
  work. D-381 stopped the abandoned turn's late snapshot from overwriting…"* (~27575), and a stale
  carry-over closed: *"the approval-modal P2 on the same list was already closed by D-381"* (~27628).
- `D-402 --> D-403 (reconnect banner; liveness timer deferred)` | *"Deferred, with the reason it cannot
  be done yet: the liveness timer. The keep-alive is an SSE comment (': keep-alive', 15s in both apps),
  and a comment fires no client event"* | ~27650; also corrects the audit's premise: *"learning-web has
  the reconnect control (D-216) and no liveness timer either"* (~27640).
- `D-403 --> D-404 (keep-alive becomes a named event)` | *"W11 shipped chat's reconnect control and
  deferred the liveness timer, because the timer could not be written correctly… This is the server
  change that makes the timer possible."* | ~27670–27674; *"A named event, not a data:-only frame.
  EventSource.onmessage receives only unnamed events"* | ~27679. D-404 **re-defers** the client half:
  *"Still deferred: the client timer."* (~27708).
- `D-404 --> D-405 (timer built and tested)`. **Closure of D-403's deferred item, verbatim:** heading
  *"D-405 — W12b: frontend unit tests, and the liveness timer they unblocked (accepted, 2026-08-18)"*;
  then *"**The timer.** 40s without a frame marks the stream stale and reports `error`, which is what
  raises the banner and its Reconnect button. 2.5× the server's 15s keepalive: tolerates one lost
  keepalive plus jitter, so a healthy-but-quiet stream is never reported — the failure mode that
  mattered"* (~27729–27731), and the item is listed among the four #14 was blocking: *"and this timer,
  whose 40s window cannot be shortened from a browser test and whose stream cannot be held open by
  `route.fulfill`"* (~27725). Falsification: *"Removing the timer entirely fails 2 of 6"* (~27747).
  Later confirmation of reach: D-415 (~28141) — *"W12b's timer was built for `EDGE-CHAT-02`'s silent
  partition and is what makes this bounded; that was not its design goal."*

**Status tags updated on superseded entries? None.** D-346 still `**Status:** implemented`;
D-402/D-403/D-404 all still `(accepted, 2026-08-18)`. **D-403's "Deferred" paragraph is left standing
with no forward pointer to D-404/D-405** — the closure is discoverable only by reading forward. The one
in-log correction in this chain is to **D-348's code comment** (in the source, per D-402), not to a
DECISIONS heading.

**Candidate ACTIVE decision:** **D-405** for client liveness (40s stale timer, armed at construction,
any inbound frame counts, cleared on teardown), on top of **D-404** (named `keepalive` event, both
APIs), **D-403** (reconnect banner, `error` only), **D-402** (`chat_turn_cancellations` table,
`astream`, `TurnReason.CANCELLED`, 202) and **D-346** (50s deadline + advisory lock). **D-413** then
extends the lifecycle to replayed turns (`REPLAYED_TURN_WAIT_MS = REQUEST_TIMEOUT_MS` = 55s,
`unresolved` as a fifth turn state, and the dead Stop button inside a replayed bubble).

**Historical-but-must-stay-discoverable:** D-346's stated limit on 404-before-403 enumeration; D-352's
55s-above-50s ordering rationale and the `cancelled ≠ failed` distinction; D-403's deleted flaky control
and the "comment fires no event" reason; D-404's `TestClient.stream()` seven-minute hang and the
unexplained-skip explanation.

**Ambiguities/uncertainty:** the chain is **additive, not supersessive** — no entry here revokes an
earlier one; the only reversal is D-348's comment. D-403's deferral text reads as open unless the reader
reaches D-405. Whether the 40s/15s ratio is right is **argued, not measured live.** `learning-web`
parity is asserted only structurally (D-415), and D-414 leaves its banner render condition untested by
deliberate choice.

**Confidence:** **HIGH**.

#### Theme H consolidated tag table — every entry read, heading status tag verbatim

| Entry | Line | Tag as written |
|---|---|---|
| D-164 | 9984 | `(accepted, 2026-08-03)` |
| D-165 | 10078 | `(accepted, 2026-08-03)` |
| D-165 addendum | 10142 | *(no status tag)* — `### D-165 addendum — deployed 2026-08-03, and the live verification found the threshold is too tight` |
| D-166 | 10183 | `(accepted, 2026-08-03)` |
| D-166 addendum | 10281 | *(no status tag)* — `### D-166 addendum — deployed 2026-08-03, and the verification found the *selector*, not the threshold` |
| D-168 | 10404 | `(accepted, 2026-08-03)` |
| D-169 | 10580 | `(accepted, 2026-08-03)` |
| D-170 | 10641 | `(accepted, 2026-08-03)` *(read incidentally)* |
| D-172 | 10741 | `(accepted, 2026-08-04)` |
| D-173 | 10908 | `(accepted, 2026-08-04)` |
| D-174 | 11137 | `(accepted, 2026-08-04)` |
| D-175 | 11411 | `(accepted, 2026-08-04)` |
| D-176 | 11581 | `(accepted, 2026-08-04)` |
| D-177 | 11667 | `(accepted, 2026-08-04)` |
| D-178 | 11742 | `(accepted, 2026-08-04)` |
| D-179 | 11843 | `(accepted, 2026-08-04)` |
| D-180 | 11927 | `(accepted, 2026-08-04)` |
| D-181 | 12036 | `(accepted, 2026-08-04)` *(read incidentally)* |
| D-220 | 15612 | `(accepted, 2026-08-08)` |
| D-221 | 15729 | `(accepted, 2026-08-08)` |
| D-346 | 24780 | `**Date:** 2026-08-15 · **Status:** implemented · **File:** apps/chat-api/src/chat_api/routers/sessions.py` |
| D-347 | 24817 | `**Date:** 2026-08-15 · **Status:** implemented` *(read incidentally)* |
| D-351 | 25116 | `**Date:** 2026-08-15 · **Status:** implemented · **Amends SPEC §5.19.4, adds §5.19.5**` |
| D-352 | 25047 | `**Date:** 2026-08-15 · **Status:** implemented` |
| D-353 | 25095 | `**Date:** 2026-08-15 · **Status:** implemented` *(read incidentally)* |
| D-354 | 25217 | `**Date:** 2026-08-16 · **Status:** fixed · **Found by:** the staging chat suite…` *(incidental)* |
| D-359 | 25479 | `**Date:** 2026-08-16 · **Status:** measured, deliberately not tuned · **Spend:** 15.61¢` |
| D-360 | 25549 | `**Date:** 2026-08-16 · **Status:** fixed` *(incidental)* |
| D-361 | 25570 | `**Date:** 2026-08-16 · **Status:** fixed` *(incidental)* |
| D-371 | 25914 | `**Date:** 2026-08-16 · **Status:** measured, deliberately not tuned — the item closes · **Spend:** ~90¢` |
| D-372 | 25979 | `**Date:** 2026-08-16 · **Status:** built, falsified, tested` *(incidental)* |
| D-392 | 27171 | `(accepted, 2026-08-17)` |
| D-393 | 27221 | `(accepted, 2026-08-17)` *(incidental)* |
| D-397 | 27351 | `(accepted, 2026-08-17)` |
| D-398 | 27390 | `(accepted, 2026-08-17)` *(incidental)* |
| D-399 | 27426 | `(accepted, 2026-08-17)` |
| D-400 | 27461 | `(accepted, 2026-08-17)` *(incidental)* |
| D-401 | 27513 | `(accepted, 2026-08-17)` — body carries an inline dated correction: `> **Corrected 2026-08-18 by a terraform plan run for D-406**` |
| D-402 | 27561 | `(accepted, 2026-08-18)` |
| D-403 | 27632 | `(accepted, 2026-08-18)` |
| D-404 | 27668 | `(accepted, 2026-08-18)` |
| D-405 | 27714 | `(accepted, 2026-08-18)` |
| D-406 | 27761 | `(accepted, 2026-08-18)` *(incidental)* |
| D-407 | 27798 | `(accepted, 2026-08-18)` *(incidental)* |
| D-413 | 27966 | `(accepted, 2026-08-18)` |
| D-414 | 28082 | `(accepted, 2026-08-18)` |
| D-415 | 28126 | `(accepted, 2026-08-18)` *(incidental)* |

> **Theme H cross-chain finding.** The log has two heading conventions (`(accepted, DATE)` for
> `## D-nnn`, and a `**Date:** · **Status:**` metadata line for `### D-nnn` entries), and in **all five
> chains not one superseded entry's tag was changed**. Supersession is carried entirely by (a) forward
> prose in the later entry and (b) occasional dated blockquote corrections inserted into the earlier
> entry's *body* (observed at D-168 ~10569, D-401 ~27533, and referenced at D-372 ~26006 for
> OPEN_DECISIONS). **Any consumer that reads status tags to determine what is current will read at
> least eleven stale "accepted"/"implemented" entries as active.**

### Theme K — Content pipeline (K1–K5)

#### CHAIN K1 — Shape-pipeline retirement

**Links**

- `D-003 --(no recorded relation)--> D-193/D-224/D-226` | **NOT FOUND** | D-003 heading line 23.
  D-003 is cited **exactly once** anywhere in the file (line 1270, inside D-060: *"the same … scope cut
  the S9 shape pipeline already made, D-003/D-016"*). Neither D-193, the D-210 disposition, D-224 nor
  D-226 mentions D-003. Its own text (*"The spec's '100 templates per topic' volume target is met later
  by the pipeline"*) is thematically upstream but **no entry supersedes or retires it.**
- `D-192 --reversed-in-direction-by--> D-193` | *"This reverses the direction of D-192, not its findings.
  Its commit is kept in history."* | line 12992. **D-192 has no entry** (only the phantom note at
  16101), so the superseded side of this link is unrecorded. D-193 also keeps parts of D-192 alive
  explicitly: *"The counters, `RejectionStage` and `--seed-offset` that D-192 also brought are
  mode-independent and stay."* (12989–12990).
- `D-193 --partially-reversed-and-corrected-by--> D-194` | *"This **reverses D-193's deliberate
  duplication**, where the preflight recomputed ids so a divergence could be caught."* | line 13105.
  Second quote, the explicit correction (D-194 §6, heading `### 6. A correction to D-193`, line 13138):
  *"D-193 claimed `_settle` contained duplicate-id damage. It did not, quite:
  `QuestionRepository.create_template` **flushes**…"* (13140–13142). **Note D-194 reverses only the
  duplication design + one factual claim; the equation-first retirement stands.**
- `D-210 --disposed-by--> D-210 disposition` | *"D-210 was committed \"WIP\" because removing shape
  templates left three thin cells"* | line 14535; the disposition's own decision: *"A shape-template
  fallback (the \"option B\" considered here) is therefore **not built**"* (line 14554).
- `D-210/D-223 --evidenced-unservable-by--> D-224` | *"**Servable templates that would take the
  generated rendering path: 0.**"* | line 16160. D-224 explicitly leaves the question open and to the
  user: *"Whether *any* of the shape apparatus should remain … is now a clean question with the evidence
  attached, and it is the user's call rather than a cleanup."* (16194–16195). D-224 also re-frames D-223:
  *"It was also **an efficiency improvement to a route whose every output is unservable**"*
  (16187–16188).
- `D-224 --decided-and-executed-by--> D-226` | *"The user's call, on D-224's evidence: **delete it.**
  About 2,000 lines removed"* | line 16311. D-226 also retires D-224's own guard: *"**D-224's
  `--mode shape` refusal is gone too**, along with its test."* (16364). TRACEABILITY rewrite confirmed:
  *"**A traceability row that was evidence for the wrong implementation.** … Rewritten against the
  authored route, with the reason left in place rather than quietly corrected."* (16335–16340), plus
  *"Two eval-registry rows pointing at shape tests … became `not_applicable` with a reason"*
  (16352–16354).

**Status tags updated on superseded entries? No, in every case.**

- D-003 — `(accepted, 2026-07-13)` — unchanged, no annotation.
- D-193 — `(accepted, 2026-08-05)` — unchanged despite D-194's reversal + correction; the "retired" word
  in its heading is about equation-first authoring, **not** about D-193's own status.
- D-194 — `(accepted, 2026-08-05)` — unchanged.
- D-210 disposition — `(accepted, 2026-08-06)` — unchanged.
- D-224 — `(accepted, 2026-08-08)` — unchanged even though D-226 deleted its subject and removed its
  `--mode shape` refusal.
- D-226 — `(accepted, 2026-08-08)`.

**Candidate ACTIVE decision:** **D-226** — the shape apparatus is deleted (bank, `SHAPES`, generators,
`generation.py`, `validation.py`, `hint_ladders.py`, pipeline shape route, CLI `--mode`, serving
branch); authored-only is the sole path.

**Historical-but-must-stay-discoverable:** D-003 (why a hand-authored bank existed first, and the
deferred 100/topic volume claim); D-193 (field-order/verdict-before-reasoning fix and the retirement
rationale — still live engineering, only its duplication design and `_settle` claim were revised); D-194
(blind judge, three-numbers/two-gates, `build_plan`); D-210 disposition (thin-cell repetition semantics,
`unused or matched`); D-224 (the measurement that justified deletion, and the 2.36%-inside-100% lesson);
D-226's residue note: *"**The 50 rows already in every database are left alone.** …
`authoring_mode='shape'`, 50 of them, safe to delete whenever someone wants to."* (16358–16362).

**Ambiguities/uncertainty**

- **D-210 itself has no entry** — `grep '^#\+.*D-210'` returns only `## D-210 disposition`. Same phantom
  shape as D-190/D-191/D-192 **but never recorded as such**; D-210's substance (the
  `_servable()`/`authoring_mode == "authored"` rule and the export `active_status` filter) is only
  reachable through citations in D-224, D-226, D-269, D-271. (See the phantom-ID section.)
- D-192's supersession is asserted by D-193 **against a non-existent entry**, so "reverses the direction,
  not the findings" cannot be checked against the original.
- D-003's chain membership is **inference-only**; there is no textual link.

**Confidence:** HIGH on D-193→D-194→D-224→D-226; MEDIUM on the chain's start (D-003 unlinked, D-210
missing).

#### CHAIN K2 — Phantom trio D-190 / D-191 / D-192

The full transcription of this chain — heading, every quote, the citation lists, and the
unreconstructability of D-192 — is in **Phantom / missing decision IDs → D-190, D-191, D-192** above,
because it is simultaneously a chain and the corpus's own record of absence. In summary:

- **Heading verbatim:**
  `## D-190, D-191, D-192 — referenced everywhere, never written (recorded 2026-08-08, while closing D-223)`
  (line 16101). Status tag `recorded` — the only heading in the audited chains using that word.
- **Candidate ACTIVE decision:** the note itself, for all three ids.
- **Historical-but-must-stay-discoverable:** the entire note — the only resolution target for ~26
  citations.
- **Confidence:** HIGH on what the note says; irreducibly LOW on D-192's underlying facts, by the note's
  own design.

#### CHAIN K3 — Volume / coverage / parking

**Links**

- `D-060 --re-scoped-and-partly-superseded-by--> D-185` | *"**D-060 said** authoring the other two topics
  is *"future content work, not a gap in this session's pipeline code."* That framing stands as an
  accurate statement about S20's pipeline and is now **superseded as a scheduling statement**"* |
  lines 12497–12499. The user decision behind it: *"The user's answer: **K-12 coverage is needed before
  launch.**"* (12476).
- `D-223 --depth-target-source--> (D-273, D-313, D-342)`. What D-223 *decided*: shared the wording list
  (`authored_validation.disallowed_wording_found`), fixed both gate copies, and authored 15 more
  `fraction_operations` items (15 → 30, *"0 of 15 failing the §5.8.5 gate on the first run"*, 16074). Its
  depth rationale, quoted: *"three items per tier is thin enough that a 10-item pre-exam shows a student
  two thirds of the bank and a second session repeats it"* (16072–16073). What it *found*: the two-copy
  pattern (*"*every* correction the authored half has received was made on the authored copy alone"*,
  16010–16011) and the flag-rate table (pipeline 2.36% → 0). **The "5–7 per tier" number is NOT stated as
  a user target in D-223** — D-223 shipped 5/6/7/6/6 per tier and gave the repetition reason; the *target*
  framing is attributed to D-223 **retroactively** by D-273 (*"**Volume target is D-223's measured 5–7 per
  occupied tier**"*, 19719) and by D-313/D-342 as *"D-223's target of 5 per occupied `(topic, tier)` cell"*
  (22359, 24579).
- `D-223 --volume-target-adopted-by--> D-273` | *"**Volume target is D-223's measured 5–7 per occupied
  tier** (~25–35/topic, ~1,000 items across 34 topics), **deliberately diverging from SPEC §5.8.1's
  100/topic**"* | lines 19719–19720 — recorded under *"**Two decisions taken by the user on these findings
  (2026-08-11)**"* (19711). D-273's embedded self-corrections: *"*Superseded by the § "Corrected by
  verification" block below; kept because the correction is the point.*"* (19596–19597); *"**c. The CSV is
  34 books / 245 unique rows, not "~40–50 topics / 246 rows"**"* (19666); *"**e. The mechanism — and my
  first account of it, written into this entry an hour earlier, was also wrong.**"* (19679–19680).
- `D-273 (Phase 3 auto-approval condition) --decided-by-user-in--> D-289` | *"**The decision, taken by the
  user: auto-approve, no sampling.** A 20-item-per-wave spot check was recommended here and declined"* |
  lines 20826–20827; the recorded consequence: *"the consequence is specific: prose defects now reach
  students unless someone reads the bank for another reason"* (20829–20830). Also *"Four waves had already
  shipped auto-approved on the user's instruction, so this is the evidence catching up with the practice
  rather than gating it."* (20796–20797).
- `D-313 --closed-against-recommendation-by--> D-341` | *"**The user declined, and the reasoning is
  recorded because it is the part that matters:**"* + blockquote *"Keep the existing `difficulty_tiers`
  declarations unchanged. Do not modify the taxonomy solely because the current bank is thin"* |
  lines 24523–24528; loop-stopping clause: *"The mismatch has now been re-derived at least three times
  (D-313, U1/D-324, here), each time as though it were a fresh defect. It is not a defect."* (24534–24536).
- `D-223 / D-313 / D-322 §5 / D-341 --superseded-in-framing-by--> D-342` | heading-line metadata verbatim:
  *"**Date:** 2026-08-15 · **Status:** standing instruction from the user · **Supersedes the "open" framing
  in** D-223, D-313, D-322 §5, D-341"* | line 24569. The standing instruction: *"every finding of the form
  "the bank is thin / a tier is unstocked / a skill does not span / a cell is under-filled" is parked, and
  stays parked until the user explicitly asks for new problems to be generated."* (24571–24573).
  Prohibitions: *"**Do not narrow declarations, targets or thresholds to make a gap disappear.**"* /
  *"**Do not open a session, spend, or generation run** … without the user asking first."* / *"**Do not
  re-derive it as a new finding.**"* (24602–24606). Scope includes *"**Depth** — D-223's
  5-per-occupied-(topic, tier) cell target. **84 of 153 cells, 189 items short, ≈ $13-16 and ~3.5 h.**"*
  (24579–24580).
- `D-342/D-341 --enforced-in-docs-by--> D-417 §B5 and §D10`. **B5:** *"**OPEN_DECISIONS #6 claimed *"4
  videos covering 4 of 112 skills and 1 of 33 topics"*. Measured on staging today: 497 videos, 363
  active-and-approved, and 102 of 112 skills servable.** The document was wrong by two orders of magnitude,
  and it was the basis for a recommendation to *"accept that the video intervention is effectively absent
  at launch…"*"* (28321–28324); parking restated: *"**Parked on the user's instruction:** no expansion of
  video coverage now"* (28342). **D10:** *"#7 recommended *"edit the declarations to match the judge"*.
  **D-341 records the opposite, decided by the user** … Rewritten to defer to D-341, with the recommending
  wording removed rather than merely annotated."* (28388–28393).

**Status tags updated on superseded entries?**

- D-060 — `(accepted, 2026-07-19)` — unchanged; **no in-place annotation** despite D-185's explicit
  "superseded as a scheduling statement".
- D-185 — `(accepted, 2026-08-05)` — unchanged.
- D-223 — `(accepted, 2026-08-08)` — unchanged; no marker that D-342 parked its depth target or that
  D-224 re-framed its value.
- D-273 — `(accepted, 2026-08-11)` — unchanged at the heading, but **this is the one entry with in-body
  supersession markers** (§1 labelled superseded, plus a dated "Corrected by verification" block).
- D-289 — `**Status:** decided by the user` (no in-place update afterwards).
- D-313 — `**Status:** measured; criterion restated, no code change` — unchanged after D-341/D-342 closed
  it.
- D-341 — `**Status:** decided by the user; recorded so audits stop reopening it` — unchanged, though
  D-342 lists it among the "open" framings it supersedes.
- D-342 — `**Status:** standing instruction from the user · **Supersedes the "open" framing in** D-223, D-313, D-322 §5, D-341`
  — **the only heading-level supersession tag found anywhere in this audit.**
- D-417 — `(accepted, 2026-08-18)`; sub-item tags: `### B5 … ✅ investigated`,
  `### D10 — OPEN_DECISIONS #7 reconciled to D-341` (no tag).
- D-322 (read for cross-check) — `**Status:** decided; execution plan in ROADMAP.md's "Sessions U1–U7" block`
  — unchanged.

**Candidate ACTIVE decision:** **D-342** — all question-bank coverage/depth/tier-gap work is parked as a
standing user instruction, with **D-341** supplying the reasoning and **D-417 §D10** the doc
reconciliation. Volume target of record when work resumes remains **D-273's 5–7 per occupied tier**
(diverging from SPEC §5.8.1's 100/topic); auto-approval-without-sampling remains **D-289**.

**Historical-but-must-stay-discoverable:** D-060 (accurate about S20's pipeline; only its scheduling
clause was superseded); D-185 (the measured 50-templates/one-band starting position and the
`grade_topic_candidates`-unread trap); D-223 (the one-rule-two-implementations pattern, the before/after
gate table, and the origin of the 5–7 reasoning); D-273 (plan of record + three self-falsifications, and
the 245-row/34-book denominator); D-289 (the declined 20-item spot check — the only record that prose
defects reach students unsampled); D-313 (the 106-items/39-skills measurement, reused by D-341/D-342 as
backlog); D-417/B5 (the 182-wrongly-inactivated-videos incident and its same-day recovery).

**Ambiguities/uncertainty**

- **Direct conflict on `difficulty_tiers`:** D-322 §7 (2026-08-14) records as a *user decision*, "as
  recommended": *"**Edit `difficulty_tiers` to match the judge**"* (22918). D-341 (2026-08-15) records the
  user deciding the opposite. D-342 names "D-322 §5" as superseded **but not §7**; D-417/D10 fixes only
  OPEN_DECISIONS #7, not D-322 §7. **So D-322 §7 stands unannotated and contradicts the later, active
  decision.**
- **"5–7 per tier" provenance is fuzzy:** D-223 never states it as a target or as a user target; D-273
  calls it "D-223's measured 5–7"; D-313/D-342 render it as "5 per occupied cell". **Three phrasings of one
  number.**
- D-342 lists D-341 as superseded-in-framing while simultaneously quoting D-341's user reasoning as its
  own basis — **D-341 is both source and superseded.**
- D-289's five criteria all pass while the entry itself says they "never named the failure"; whether the
  13% prose-defect class is now parked under D-342 is **not stated** (D-342 covers *quantity* findings
  only, and prose defects are quality).
- **Video figures:** D-314 (22375) still asserts *"the catalog holds 4 videos across 4 of 112 skills"* in
  the present tense, and D-322 §6 repeats *"4 videos across 112 skills"* (22941) — both left standing;
  D-417/B5 corrects OPEN_DECISIONS but **does not annotate these two entries.**

**Confidence:** HIGH on the D-185, D-341, D-342, D-417 links; MEDIUM on the D-223 target attribution and
on where D-322 §7 now sits.

#### CHAIN K4 — Difficulty judge / tiers

**Links**

- `D-231 --diagnosis-corrected-by--> D-232` | *"D-231 found the judge rating 20 of 21 `place_value` items
  \"2\" and concluded it rates absolute difficulty. **That diagnosis was incomplete, and the correction
  matters.**"* | lines 16659–16660. The correction's substance: *"The prompt already told the judge the
  scale is relative to the grade band — D-200 added that … What D-200 could not anticipate is that its fix
  was a *single global rubric*"* (16660–16663), and *"**The rubric became wrong the moment a second topic
  existed, and the three sessions that added topics never touched it.**"* (16675–16676). D-231's own words
  being corrected: *"**The judge answered \"2\" for 20 of 21 items.**"* (16627) and *"**Not fixed here.**
  The fix is a prompt that asks for a tier *relative to the named topic and grade band*"* (16638–16639) —
  i.e. D-232 both implements and re-diagnoses it.
- `D-232 --extended/corrected-by--> D-233` | *"D-232 made the judge discriminate. Running it over a whole
  topic then exposed that it could not finish: **7 of 25 calls failed with an empty error string.** This
  entry is the chain that followed, and it corrects two of this session's own fixes."* | lines 16726–16728.
  **The requested quote "The number was never the variable" was NOT FOUND** in D-233's opening 10 lines
  read (16724–16734); its recorded framing there is the heading's *"the judge's prose expands to fill
  whatever it is given"* plus *"`str(asyncio.TimeoutError())` is `\"\"`. The judge was hitting
  `bedrock_call_timeout_s = 20.0`."* (16732). **Flagging rather than substituting.**
- `D-292/D-296 --premise-falsified-by--> D-300` | *"**The baseline measurement says the rubric is not the
  problem, and D-292's central premise is false.**"* | lines 21480–21481; storage-by-design: *"**From the
  slot, for 10 of the 16.**"* (21504) and *"`flagged` is what a gap of exactly 1 produces
  (`_DIFFICULTY_FLAG_AT = 1`): the item is kept, a human is pointed at it, and the tier stays the slot's."*
  (21512–21514); remedy withheld: *"**Not acted on, because the three available remedies are opposed and
  the choice is the user's**"* (21538) — matching its status line "the remedy is a decision, not yet
  taken".
- `D-300 --decided-as-compromise-by--> D-301` | *"The user's instruction was to take a reasonable middle
  path, so: **change no stored tier, quantify the skew, and fix the metric that caused the confusion.**"* |
  lines 21560–21561. What was kept: *"**1. `difficulty_label` keeps meaning "the tier the plan asked
  for".** No content is rewritten."* (21563–21564) and *"**3. No re-anchoring.**"* (21587). D-301 also
  corrects D-300: *"**This corrects an overstatement I made from D-300's sample.** I wrote that the bank's
  labels sit "systematically about one tier above" … Bank-wide it is 27% above, 14% below, 59% agreeing"*
  (21580–21582).
- `D-300 + D-301 --reversed-by--> D-302` | *"The user's decision, given D-300/D-301: … Follow the judge's
  rating, accept an uneven and biased tier distribution, and optimise for item count."* | lines
  21615–21617, and mechanically: *"**`judge_difficulty` stores the judge's tier on `flagged`**, not only on
  `retiered`. A ±1 disagreement used to keep the slot's tier — the D-300/D-301 finding."* (21633–21635).
  **Yes, D-302 reverses D-301's option 2 in favour of D-300's option 1**, plus *"**330 existing items were
  re-tiered** to the judge's reading (214 down, 116 up)"* (21644–21645) and *"**`EXAM_QUESTION_COUNT`
  (= 2 × 5 = 10) replaces "two at every difficulty"**"* (21635–21636). **D-301's "keep the labels" is
  therefore dead as policy; its skew measurement survives.**
- `D-302 --relied-on-by--> D-313` | *"**It is not a defect, and the reason is worth being precise about.**
  D-302 decided the stored tier is the *judge's* reading. `generation_plan()` schedules only within a
  skill's declared tiers, but the judge is free to rate an item outside them, and on D-302's decision that
  rating is what gets stored."* | lines 22331–22334; the number: *"**106 items across 39 skills carry a
  stored `difficulty_label` that is not in their skill's declared `difficulty_tiers`.**"* (22328–22329);
  non-impact verified: *"`difficulty_tiers` is read by `content.py` and the planner **only** — no serving
  code reads it"* (22335–22336). **Note D-313's own recommendation** — *"where the judge disagrees with the
  declared span the honest fix is the **declaration**, not the content"* (22356) — **is the recommendation
  D-341 later had declined by the user.**

**Status tags updated on superseded entries?**

- D-231 — `(accepted, 2026-08-08)` — unchanged, despite D-232 calling its diagnosis incomplete.
- D-232 — `(accepted, 2026-08-09)` — unchanged.
- D-233 — `(accepted, 2026-08-09)`.
- D-300 — `**Status:** measured, 10.24¢; the remedy is a decision, not yet taken` — **still says "not yet
  taken"** although D-301 and D-302 both took it.
- D-301 — `**Status:** decided (user: "적당히 타협해도 좋아"), 19.94¢ total` — unchanged although D-302 (same
  day, same session) reversed its central clause.
- D-302 — `**Status:** decided by the user and implemented`.
- D-313 — `**Status:** measured; criterion restated, no code change` — unchanged after D-341/D-342.

**Candidate ACTIVE decision:** **D-302** — the judge's rating is the stored tier (including on `flagged`),
uneven/biased tier distribution accepted, `EXAM_QUESTION_COUNT` (10) replaces the per-tier floor; 330 items
backfilled. **D-232's per-topic `difficulty_anchors` in `topics.yaml` remains the active rubric mechanism.**

**Historical-but-must-stay-discoverable:** D-231 (the split token ceilings, the ≥80%-dominant-tier
dispersion control, and the "4 of 25 still failed at 3000" residual); D-232 (the before/after 24-item table
and why exact agreement is not the metric); D-233 (the three ceilings/timeout mechanism, and the bound on
`hint_quality_score` that D-249 later leans on); D-300 (provenance method — reading stored authoring
evidence rather than paying for calls); D-301 (the bank-wide 27/59/14 skew and the correction of D-300's
overstatement); D-313 (the 106-item measurement, now backlog per D-341/D-342).

**Ambiguities/uncertainty**

- Requested quote **"The number was never the variable" not located** in the D-233 window read; **do not
  attribute it** without a wider read of D-233 (16724–16850 unread beyond line 16734).
- **D-300's status line contradicts the two entries immediately following it** — a stale-status hazard
  exactly of the kind D-341's *"Two stale claims corrected"* section describes.
- **D-301 vs D-302:** same date (2026-08-13), same session, **opposite dispositions of the stored label.**
  Only D-302 says it supersedes; D-301 carries no annotation, so a reader landing on D-301 first gets the
  wrong active rule.
- D-313's *"the honest fix is the **declaration**"* is a recommendation later overridden by the user
  (D-341) and remains unannotated in place.

**Confidence:** HIGH on D-300→D-301→D-302→D-313; MEDIUM on D-233's role (partial read, missing quote).

#### CHAIN K5 — Hint-quality instruments

**Links**

- `D-201 --product-rule-established--> (the rule later duplicated)` | *"**Product decision (user,
  2026-08-06):** an item whose answer coincides with one of its given quantities is a normal item, not a
  defect."* | lines 13860–13861; mechanism: *"`answer_leaked_beyond_the_question` checks the hint against
  the answer *and* the answer against the stem+context, and only fails when the value is new."*
  (13864–13865); non-weakened part: *"`leak_phrase_present` still catches an explicit "the answer is 4"
  anywhere"* (13867–13868).
- `D-243 --measured-and-fix-failed-in--> D-245` | *"**It is neither, and the pre-registered fix failed.**
  Recorded in full because a plausible prompt clause that does not work is exactly the kind of thing a later
  session re-invents."* | lines 17883–17884; and *"**P3 fails outright**: the clause made splits *worse* and
  unstuck the one item that had been stable."* (17909–17910); the withheld fix: *"The obvious response is
  D-239's move — downgrade the rejection to a `pending` review flag … **It is not being made here.**"*
  (17935–17937).
- `D-245 --completed-by--> D-246` | *"D-245 established that `hint_reveals_answer` is unstable on approved
  content and that a skill-aware rubric clause made it worse. It could not license a change … This is the
  missing half"* | lines 17957–17960; negative control: *"**32/32 true positives, 8 of 8 unanimous, zero
  splits** … That is the profile of a flag, not a gate."* (17965–17969); the change: *"**Restore one
  deterministic check**, not the whole gate D-202 deleted."* (17989).
- `D-248 --condition-falsified-by--> D-249` | *"`hint_quality_score <= 3` does not say a candidate is weak;
  it says where this judge sits by default."* | lines 18193–18194; the two-population table: pending
  generated queue 45% vs *"unbiased hand-authored bank **46%**"* (18189); consequence: *"Removing it:
  **13/29 (45%) → 1/29 (3%)** … That is a rank that ranks."* (18206–18207); and the self-aware churn note
  *"D-246 added a condition, D-248 removed one, D-249 removed another."* (18216).
- `D-246 --duplicate-deleted-by--> D-250` | *"D-246 restored a deterministic hint-leak check and, in doing
  so, wrote a *second* implementation of a rule that had existed since D-201 … So the D-246 "finding" was a
  rediscovery and the **D-246 "fix" was a duplicate** — introduced in the same change that cited **D-223:
  one rule, one implementation**."* | lines 18235–18241; resolution: *"`ai_pipeline.py` now calls the D-201
  helper directly."* (18244). Also self-flagged process gap: *"Recorded after the fact: the change shipped
  as commit `6d591d9` (PR #211) without an entry here"* (18232–18233).
- `D-249 --method-adopted-by--> D-251` | *"the rejection was correct on grounds I should have reached
  myself — D-249, in this same session, falsified a judge with **no corpus and no new labels**."* |
  lines 18267–18268; both corrections attributed to the user: *"**The starting position was wrong twice, and
  both corrections came from the user**"* (18257); design rule: *"The five checks can only ever
  **disqualify** the instrument. Surviving all five means *not yet falsified*, never *validated*"*
  (18280–18281).
- `D-251/D-255 --claim-falsified-by--> D-256` | *"The plan asserted that unanimity makes the union **less**
  stable than either reviewer "by construction" … **Measured false.** B split on 1 of 8, C on 2, and the
  union on **1** — more stable than one of its own members."* | lines 18591–18593; new rule: *"**Rule added:
  a missing verdict counts as blocking** (HINT_SOLUTION_REVIEW.md §4.5b)."* (18613); honesty note: *"The
  disqualifier is 30%; the measured union blocks **more than one in five** human-approved items."* (18625).
- `D-269 --claims-corrected-by--> D-271`, **two distinct corrections:**
  - (a) of D-264: *"**This corrects D-264's diagnosis, which I had taken from the reviewers** … **Reading
    all eight says otherwise.** Hint 3 in *every one* already points at the difference … **The ladders are
    sound; only the solutions were incomplete.**"* (19364–19371);
  - (b) of D-269 itself: *"**And D-269's own claim was wrong too.** That entry said restricting the export
    avoided adding "21 uncommitted `linear_equations` items". `export_cli` filters on
    `active_status == "active"` as well as approved — **D-210 added exactly that filter** … The precaution
    was against nothing"* (19378–19384).
  - The correction was also applied **in place** inside D-269 as a blockquote: *"> **Correction (D-271).**
    This entry claimed a whole-bank export "would have added 21 uncommitted `linear_equations` items" …
    **That hazard does not exist.**"* (19268–19274).

**Status tags updated on superseded entries? No heading-level updates anywhere in this chain.**

- D-201 — `(accepted, 2026-08-06)` — unchanged (**correctly**: it was restored, not superseded).
- D-245 — `(accepted, 2026-08-10)` — unchanged.
- D-246 — `(accepted, 2026-08-10)` — unchanged even though D-250 deleted half of what it built and D-249
  removed its added condition.
- D-249 — `(accepted, 2026-08-10)`.
- D-250 — `(accepted, 2026-08-10)`.
- D-251 — `(accepted, 2026-08-10)` — unchanged after D-256 falsified one of its "by construction" claims.
- D-256 — `(accepted, 2026-08-10)`.
- D-269 — `(accepted, 2026-08-10)` heading unchanged, but **in-body dated correction blockquote added by
  D-271** (the strongest in-place reconciliation seen in this audit, alongside D-004 and D-273).
- D-271 — `(accepted, 2026-08-10)`.

**Candidate ACTIVE decision:** the active leak rule is **D-201's `answer_leaked_beyond_the_question`**
(single implementation, per **D-250**), with `hint_reveals_answer` **demoted to a flag per D-246** and
`hint_quality_score` **removed from triage ordering but still displayed per D-249**; the two-reviewer union
with "missing verdict = blocking" **per D-256** within **D-251's falsification-only validation frame**.
Content state of record: **D-271 — 0 of 130 unambiguous defects.**

**Historical-but-must-stay-discoverable:** D-245 (the failed skill-aware clause, preserved specifically so
it is not re-invented; `scripts/measure_hint_reveal_rule.py`); D-246 (the negative control 32/32 and the
D-202/`review_cli.approve` finding that no deterministic check reached generated content — that reasoning
survives even though its code was deduplicated); D-249 (the 45%/46% indistinguishability and the
three-revisions-in-one-session pattern); D-250 (the *"a rule that is *restored* is the highest-risk kind of
change"* lesson); D-251 (why a mutation corpus and distribution-similarity were both rejected, **by the
user**); D-256 (correlated-blocking mechanism; 0-based index schema failure); D-269 (the 44→15 numbers, the
0-of-52 `common_mistake` preservation loss, `carry_misconception_notes()`); D-271 (the
reviewer-explanation-vs-detection distinction).

**Ambiguities/uncertainty**

- **D-246 is now partly a record of a change that was reverted (D-250)** — its heading and text still read
  as the operative design; a reader must reach D-250 to learn the second implementation is gone.
- D-269's inline correction covers **only** the export claim; its *"15 items … no solution-step repair
  reaches that"* conclusion (19303–19305, inherited from D-264) is refuted by D-271 but **not** annotated in
  place at D-269 or at D-264. D-270 (19331–19334) independently notes one such repair *did* reach the class,
  adding a **third partly-overlapping account.**
- **D-264 was not read in this pass** (only quoted via D-269/D-271), so its own status tag and any in-place
  correction are unverified.
- D-245's "measured problem without a licensed fix" and D-246's licensed fix sit one entry apart **with no
  cross-annotation on D-245.**

**Confidence:** HIGH on D-201→D-246→D-250 and D-269→D-271; MEDIUM on the D-251→D-256 pairing (D-255 not
read) and on D-264's current annotation state.

> **Theme K cross-chain observation.** The file has **no status-tag supersession convention at the heading
> level**, with exactly one exception found in this theme: D-342's
> `**Supersedes the "open" framing in** D-223, D-313, D-322 §5, D-341`. Reconciliation is instead carried
> (a) forward-only in the superseding entry's prose, or (b) as dated in-place correction blocks inside the
> earlier entry — observed at D-004, D-269 (`> **Correction (D-271).**`), D-273 (§1 marked superseded + a
> "Corrected by verification" section), D-201 (`### A correction to an earlier claim in this session`), and
> the D-211/D-212/D-225 addenda. Two stale status lines deserve attention: **D-300**
> (`the remedy is a decision, not yet taken` — taken in D-301/D-302) and **D-322 §7** (records the user
> choosing to edit `difficulty_tiers`, the opposite of the active D-341/D-342/D-417-D10 position, and is
> the one artefact D-342's supersession list does not name).

### Theme M — Runtime, UX & operations (M1–M6)

*All line numbers are `docs/DECISIONS.md` unless marked PROGRESS.*

#### CHAIN M1 — SSE cross-replica delivery

**Links**

- `D-032 --predicts-own-obsolescence--> (no successor named)` | *"this bus is not durable and assumes one
  Uvicorn worker (true for this app); a future multi-worker deployment would need a real pub/sub"* |
  line ~521
- `D-334 --measures-defect-in--> D-032` | *"`SessionEventBus` is a plain
  `dict[str, list[asyncio.Queue]]` with no cross-process transport. `learning-api` runs **2 ECS tasks**."* |
  line ~23964; and *"the defect is reported, not fixed"* | line ~23941. **D-334 does not cite D-032
  anywhere** (`Follows: D-329` only).
- `D-335 --fixes--> D-334` | `**Status:** implemented · **Fixes:** D-334` | line ~24022
- `D-335 addendum --corrects--> D-335` | *"`a37e89d` deployed successfully… **The relay started on zero of
  two replicas.**"* | line ~24096
- `D-335 verification --proves--> D-335` | *"before D-335 | 6 | **3 (50%)** / after D-335 | 8 |
  **8 (100%)**"* | line ~24147
- `D-344 --stopgap-for--> D-335/D-349` | heading: *"**Status:** stopgap, **removed by D-349**"* | line ~24671
- `D-344 correction --retracts--> D-344 heading` | *"the stopgap existed for the length of a code review and
  never once bounded the service"* and *"**D-349 therefore removes nothing**; that clause in its heading is
  inherited from this mistake"* | lines ~24696, ~24705
- `D-349 --supersedes-reasoning-of--> D-335 §5` | *"The carry-over called this low value and gave a correct
  reason… It is not the client the fan-out serves."* | line ~24946
- `D-395 --fixes-regression-inside--> D-335/D-349` | *"a five-event burst published back-to-back produced
  four `InterfaceError`… one event of five reached the other replica. This is D-334's defect returning inside
  the mechanism built to fix D-334"* | line ~27307
- `D-396 --adds-telemetry-for--> D-395` | *"The 08-16 audit's line was *'SSE has no telemetry at all…'*, and
  D-395 is the bill for it."* | line ~27335

**Status tags updated on superseded entries?**

- D-032 (506): `(accepted, 2026-07-16)` — **NOT updated.** No supersession/partially-superseded marker
  despite D-335 replacing its bus and D-395/D-396 layering on it.
- D-334 (23939): `**Status:** measured; **the defect is reported, not fixed** · **Follows:** D-329` — **NOT
  updated** even though D-335 (same day) fixed it. A reader hitting D-334 alone sees an open architectural
  defect.
- D-335 (24020): `**Status:** implemented · **Fixes:** D-334` — not updated after its addendum found it dead
  on both replicas, nor after D-395 found it losing 4-in-5.
- D-335 addendum (24092): `**Status:** fixed before the fan-out was ever claimed to work`
- D-335 verification (24126): **no Status field at all** — only *"Deployed `daf323c`, both services on
  `gha-daf323c8a837`, rollout `COMPLETED`."*
- D-344 (24669): `**Status:** stopgap, **removed by D-349**` — **stale and self-documented as stale.
  Confirmed exhibit.**
- D-349 (24942): `**Status:** implemented` — not updated after D-395.
- D-395 (27303): `(accepted, 2026-08-17)`
- D-396 (27333): `(accepted, 2026-08-17)`

**Candidate ACTIVE decision:** **D-396** for telemetry + **D-395** for the relay's concurrency contract; the
architecture-of-record is **D-335 as amended by D-395** (Postgres LISTEN/NOTIFY, per-publish lock,
`_pending` strong refs, draining `stop()`). **No single entry states the current whole.**

**Historical-but-must-stay-discoverable:** D-032 (why `?token=`, why in-process, the dev token mint — items 2
and 3 are still live design), D-334 (the only measurement of the 2-of-4 rate and the "failure rate rises with
capacity" argument), D-335 §1 (the SQS-vs-SNS-vs-LISTEN/NOTIFY rejection rationale, requested by the user),
D-335 addendum (the `_dsn()` / vacuous-test lesson, re-cited by D-349), D-344 (both the ordering argument and
the stale-heading exhibit).

**Ambiguities/uncertainty**

- **D-344's heading and its own §correction are in direct contradiction inside one entry.** The correction is
  later and evidence-based (live `application-autoscaling` read), so the heading is wrong — but **nothing in
  D-349 acknowledges this**, so a reader arriving via D-349 gets no signal.
- Heading-level inconsistency: D-334/D-335/D-344/D-349 are `###`; D-395/D-396 are `##`. **The chain is not
  walkable by heading level.**
- D-032's `Consequence` paragraph is the closest thing to a supersession pointer and it **names no decision
  id.**
- D-335 §5 explicitly deferred chat-api; D-344 and D-349 both pick it up. Which of D-344/D-349 "owns" the
  chat scope is stated only in D-349.

**Confidence: HIGH**

#### CHAIN M2 — Deferred-narrative erasure family

**Links**

- `D-356 --characterises--> (defect)` | `**Status:** ⛔ **open — characterised, not fixed**` | line ~25324;
  mechanism: *"a deferred `study_step` narrative arriving ~1.5s after the choice erases the help panel"* |
  line ~25340
- `D-358 --fixes--> D-356` | `**Status:** fixed, deployed, verified · **Fixes:** D-356` | line ~25427
- `D-369 --completes--> D-358` | *"D-358 gave the guard the right *question*… The remaining defect is
  **when** it is evaluated."* | lines ~25821–25824
- `D-373 --ports-to-third-site--> D-356/D-358/D-369` | *"**That is D-356 exactly**… This publisher received
  neither D-358's `last_intervention_attempt_id` pairing nor D-369's publish-time re-read, and nobody opened
  it."* | lines ~26069–26071
- `D-381 --ports-to-fourth-site--> D-356 family` | sub-heading `#### D-356's family, in the third place it
  lives` | line ~26527 (**note:** D-381 calls itself the *third* place while D-373 already claimed the third
  publisher — an internal numbering conflict)

**Does D-356's own heading ever get updated to fixed? NO.** Re-read of 25322–25324 confirms the only
`### D-356` heading in the file still reads `**Status:** ⛔ **open — characterised, not fixed**`. A full-file
grep finds exactly one D-356 heading (line 25322) and 20 citations, **none of which edit it**.
**`PROGRESS.md:834` says `**✅ D-356 IS FIXED…`** — so the two documents disagree on the status of the same
decision.

**Status tags updated on superseded entries?**

- D-356 (25322): `**Status:** ⛔ **open — characterised, not fixed**` — **NOT updated. Highest-severity stale
  tag found in this chain.**
- D-358 (25425): `**Status:** fixed, deployed, verified · **Fixes:** D-356` — **NOT updated** after D-369
  showed the fix was incomplete and after D-373/D-381 showed two more sites unpatched. "verified" is the word
  D-369 explicitly deflates (*"4 of 4 is entirely consistent with a window that catches roughly one run in
  five"*).
- D-369 (25809): `**Status:** fixed, falsified, deployed` — not updated after D-373/D-381.
- D-373 (26047): `**Status:** fixed, falsified` (no "deployed").
- D-381 (26477): `**Status:** fixed`

**Candidate ACTIVE decision:** **D-373** (hint personalizer) and **D-381 §`_initial_snapshot`** (restore
path) are the newest links; the *guard design* of record is **D-358's `last_intervention_attempt_id` +
D-369's evaluate-immediately-before-publish**, applied at four call sites. **No entry consolidates the four.**

**Historical-but-must-stay-discoverable:** D-356 (the only place the three rejected fixes and their
worse-than-the-bug failure modes are written down; also the `helpOnScreen` client expression), D-358 (the
"first version of the test passed with the fix deleted" lesson and the anti-vacuity test placement on the
*solution* branch), D-369 (the "correct predicate, wrong evaluation point" generalisation).

**Ambiguities/uncertainty**

- D-356's ⛔ tag plus PROGRESS's ✅ means the status is genuinely **contested in the corpus**, not merely
  stale. **Preserving this ambiguity:** DECISIONS says open, PROGRESS says fixed, and D-358's `Fixes: D-356`
  is the tiebreaker in favour of fixed-for-the-narrative-scheduler-only.
- **"Fixed" is site-scoped throughout and no entry says how many publishers exist.** D-373 says *"seven fixes
  have now gone one way only"*; D-381 finds a further one. Whether a fifth site exists is unaddressed.
- **D-373 and D-381 both claim to be "the third place".**

**Confidence: HIGH** on links and tags; **MEDIUM** on whether the family is now closed (**no entry claims
completeness**).

#### CHAIN M3 — Study-walk drift / C1 Phase 6

**Links**

- `D-340 --ships-unproven-fix--> D-321` | `**Status:** fix shipped, **not proven**; instrument left in place`
  | line ~24449; *"Seven consecutive clean runs, and the two drifts both happened with the fix already live…
  **This is not claimed as fixed.**"* | line ~24476
- `D-355 --retracts-mechanism-of--> D-340` | *"That fix shipped as D-340 (`e73441a`) and **the drift survived
  it** — 2 of the 8 runs after"* and *"D-340 §2 had already retracted the mechanism in its own text"* |
  lines ~25266–25268
- `D-365 --names-the-cause--> D-340/D-355` | *"**N double-submits therefore produced exactly
  `answered - graded == N` with the phase never leaving `study`** — the signature D-340 measured, could not
  explain, and shipped a since-retracted fix against."* | line ~25686
- `D-366 --tallies-not-closes--> D-365` | `**Status:** the clause stays ⏸, with a tally rather than a claim` |
  line ~25717
- `D-367 --fixes-remaining-cause--> D-365 §2` | *"D-365 §2 left one named cause on C1 Phase 6:
  `journey-student` signed in as `studentPresent`… which **seventeen other spec files share**"* | line ~25747
- `D-370 --closes--> D-366` | `**Status:** ✅ the last engineering clause in the roadmap` | line ~25859
- `D-317 --resolves--> D-288` | heading itself: *"D-288 was never a failed restore: the exam answered before
  it knew where the student was"* | line ~22582; *"**1. The server was never wrong**… Every one of the four
  killed explanations… was looking behind the endpoint."* | lines ~22592–22604
- `D-317 addendum --downgrades--> D-317's own ✅` | *"I marked C1's `Phase 6: staging e2e green as a whole
  run` ✅ from a single 64 / 6 / 0 run. The next full run was **63 / 7 / 1**… **Downgraded to ⏸ with both
  numbers on the record rather than the flattering one.**"* | lines ~22668–22672

**Status tags updated on superseded entries?**

- D-340 (24447): `**Status:** fix shipped, **not proven**; instrument left in place` — **honest at write time
  and now understated-stale**: D-355 and D-365 retract its mechanism entirely, and the tag does not say so.
- D-355 (25258): `**Status:** fixed (harness)`
- D-365 (25670): `**Status:** fixed in isolation; a second cause remains (see below)` — **NOT updated** after
  D-367 fixed exactly that second cause.
- D-366 (25715): `**Status:** the clause stays ⏸, with a tally rather than a claim` — **NOT updated** after
  D-370 closed it ✅. **Two entries 140 lines apart give opposite verdicts on the same clause.**
- D-367 (25743): `**Status:** shipped`
- D-370 (25857): `**Status:** ✅ the last engineering clause in the roadmap`
- D-317 (22582): `**Status:** fixed, verified locally both directions; **not yet measured on staging, where
  the defect lives**` — **NOT updated** after its own addendum verified it on staging 10/10.
- D-317 addendum (22652): `**Status:** fix verified on staging; one correction; one new carry-over`
- D-288 (20679): `**Status:** ⏸ partial — band walks green, one product defect open` — **NOT updated.** D-317
  resolves the open product defect (reframing it as a client-side position race), but D-288's tag still reads
  open.

**Candidate ACTIVE decision:** **D-370** — C1 Phase 6 closed on five consecutive clean runs at
`gha-aaad6cfec153`. For the drift mechanism specifically: **D-365 + D-367** (wait for the screen to move;
`student-ext-10` isolation). For the exam-position defect: **D-317 + its addendum**.

**Historical-but-must-stay-discoverable:** D-288 (the four independent findings: SymPy in student text,
17-of-33 unopenable topics, the calculus 503 tie-break, the never-exercised ladder — all still substantive),
D-340 (the retracted-mechanism exhibit and the standing rule that a breadcrumb names the mechanism rather
than prompting a third guess), D-355 (three harness self-deceptions, and the recorded-not-changed note that
`Allowances.statuses` is never asserted), D-366 (the six-attempt table and the "stability criterion, not a
formality" argument), D-317 (the pre-registered decision rule and the `POSITION_WAIT_MS` reasoning, cited
five more times downstream at 27954/27974/28150/28152).

**Ambiguities/uncertainty**

- **D-366 (⏸) vs D-370 (✅) on the identical clause, with no cross-link from D-366 forward.**
- D-370's own body qualifies its ✅: *"Zero 5xx… is **not yet proof**"* (line ~25879) and
  `#### What did not close` — the solution terminal rung has no staging e2e coverage. **So ✅ is scoped
  narrower than the tag suggests.**
- D-317 §"What is not yet known" is contradicted by its own immediately-following addendum; a reader who
  stops at the section boundary gets the wrong state.
- D-288's "one product defect open" is **not named in the status line**, so confirming D-317 closes *that*
  one requires reading both bodies.

**Confidence: HIGH** on links; **MEDIUM** on "D-288 fully resolved by D-317" — D-317 reframes rather than
states closure, and D-288's tag was never touched.

#### CHAIN M4 — Video catalog

**Links**

- `D-046 --supersedes--> D-031` | *"This supersedes D-031's S10 stub catalog for the real video-selection
  *content*, though `video_catalog.FALLBACK_MESSAGE` (the exact SPEC §5.11.6 string) carries over
  unchanged."* | line ~896
- `D-305 --narrows-guard-of--> D-207` | *"Now `has_servable_video(skill_id)`"* | line ~21869 (**D-305 does not
  cite D-031/D-046**)
- `D-326 --reuses--> D-305` | *"`_pending_search_terms` asks the catalog which skills already have a servable
  video — reusing `has_servable_video`"* | line ~23393
- `D-326 addendum --self-corrects--> D-326` | *"**A defect D-326 itself introduced**… `mark_inactive_except`
  deactivates every catalog row the run did not encounter… **marked inactive | 62**"* | lines ~23455–23469
- `D-337 --fixes-the-fix--> D-326 addendum` | *"**The guard I wrote for D-326's addendum has the bug it was
  written to prevent**"* | line ~24264; *"182 marked inactive"* | line ~24250; fix:
  *"`covered == 0 and deferred == 0`"* | line ~24277
- `D-337 verification --proves--> D-337` | *"skills with a servable video | 72 | 76 | **102 of 112**"* |
  line ~24326
- `D-339 --meets-criterion-using--> D-337` | *"4 of 112 skills had a video when U6 was written; D-337's sync
  made it **102 of 112**"* | line ~24425

**Status tags updated on superseded entries?**

- D-031 (263): `(accepted, 2026-07-16)` — **NOT updated.** No "superseded by D-046" marker in the heading; the
  pointer exists only inside D-046's body, i.e. **forward-only**.
- D-046 (878): `(accepted, 2026-07-18)`
- D-305 (21837): `**Status:** fixed, both directions tested, free`
- D-326 (23366): `**Status:** done; code merged (`cc1b013`), staging sync pending the deploy` — **NOT
  updated** after its own addendum (84 lines later) recorded the defect it introduced, nor after D-337 broke
  its guard.
- D-326 addendum (23450): `**Status:** fixed (`6fd7d89`); the 5 affected skills heal on the next run by design`
  — **NOT updated** after D-337 proved this fix wrong.
- D-337 (24237): `**Status:** guard fixed; **staging catalog partially deactivated and recovering**` — **NOT
  updated** after its own verification recorded recovery to 102/112 and 3 skills residual.
- D-337 verification (24308): **no Status field**; *"Deployed `6e48084`; recovery run exit 0."*
- D-339 (24418): `**Status:** criterion met on staging`

**Candidate ACTIVE decision:** **D-337 + D-337 verification** for the sync/deactivation guard
(`saw_whole_channel = covered == 0 and deferred == 0`); **D-305** for the per-skill serving guard; **D-046**
for classification/storage; **D-339** for the closed U6 criterion.

**Historical-but-must-stay-discoverable:** D-031 (`FALLBACK_MESSAGE` and the "not every skill has an entry"
live path survive D-046 explicitly), D-326 (the quota arithmetic `check_search_quota`, the channel-id
refusal-to-hardcode, resumability rationale, and the non-converging pending list), D-326 addendum (the
"headline number improved while a subset regressed" lesson, quoted back by D-337 §4), D-337 §4 (the honest
*"I captured the before *count* but not the before *set*"* gap — **this limit is never retired by the
verification**).

**Ambiguities/uncertainty**

- **D-326's ordering in the file is odd:** the addendum sits at 23450, *after* D-327 (23416). Chronological
  read order breaks.
- **D-337 §4's gap (which of the 25 skills lost coverage in run 1) is never closed** — the verification
  reports recovery to 102/112 and "3 hold only inactive ones" but cannot retroactively answer §4.
- **Coverage numbers move across entries** (4 → 10 → 72 → 76 → 102 of 112), and D-305 quotes "4 videos
  covering 4 of 112 skills" while the D-326 addendum's before-state reads "10 → 72". **The 4-vs-10 baseline is
  not reconciled anywhere.**
- D-031 → D-046 is a *partial* supersession by D-046's own wording ("for the real video-selection *content*"),
  so **D-031 is not fully retired.**

**Confidence: HIGH**

#### CHAIN M5 — Alarm split / NAT / image floor

**Links**

- `D-143 §4 --origins--> AUD-X-16 tfvars family` | *"`.gitignore:40` matches `*.tfvars`, so the file whose
  comment block records three separate near-misses… **is untracked**… Filed as **AUD-X-16 (P2)**; the durable
  form is an executable check"* | lines ~8454–8459. Made executable at D-150 §2:
  *"AUD-X-16 — the checklist step is now a program: `make tfvars-floor-check`"* (line ~8783).
- `D-357 --exercises-check--> D-150/AUD-X-16` | *"the tfvars floor was `gha-70100623148d` while everything
  deployed was `gha-efea7d846d37`… **Fifth instance of this shape, and the first caught by the check instead of
  by a near-miss.**"* | lines ~25408–25413
- `D-401 --blocked-by-check--> same family` | *"**the check refused before any of it could be applied, which
  is the sixth instance of one shape.**"* | line ~27551
- `D-401 embedded correction --corrects--> D-401` | *"> **Corrected 2026-08-18 by a `terraform plan` run for
  D-406:** three qualify in the *configuration*, but only **two are deployed**."* | line ~27533
- `D-406 --supplies-the-correction--> D-401` | *"**A side finding the plan produced**, corrected above in
  D-401: `sessions_completed_floor` is not deployed (`count` gated on a variable that is 0)"* | line ~27794
- `D-418 --removes-blocker--> D-401 + D-406` | *"**So the defect was in the check, not the mechanism**"* |
  line ~28432; *"**A check that fails on an input nothing reads is worse than no check — it teaches its
  operator to bypass it**"* | line ~28437; *"renamed to `scripts/check_deployed_image_consistency.py` /
  `make image-check`"* | line ~28446; *"**D-401 and D-406 are unblocked.** Both remain unapplied"* | line ~28453
- `D-419 --applies--> D-401 + D-406` | *"**Applied** on the user's authorisation, immediately after D-418
  removed the phantom blocker."* | line ~28465; near-miss:
  *"`# module.cloudtrail.aws_s3_bucket.trail has been deleted` … **It had not been deleted.**"* |
  lines ~28495–28498; *"`aws sns list-subscriptions-by-topic` reports the new subscription as
  **`PendingConfirmation`**"* | line ~28484

**Correction carried forward from verification:** the quote *"D-401 (alarm split) and D-406 … stay
unapplied"* is **NOT inside D-406**. It is at lines 28296–28297, inside the **D-417/A3 "Decided; not yet
built"** section (`### A3 — The image floor is derived from ECS, not from a gitignored file`). D-406's own body
says only *"nothing applied"* (line ~27792). **Attributing that quote to D-406 would be wrong.**

**Status tags updated on superseded entries?**

- D-143 (8416): `(accepted, 2026-08-01)`
- D-357 (25390): `**Status:** applied and verified` — the "Fifth instance of this shape" claim **NOT updated**
  after D-418 showed the check was judging a value nothing reads.
- D-401 (27513): `(accepted, 2026-08-17)` — heading still reads *"**and the sixth stale image floor**"*, which
  D-418 reclassifies as a phantom blocker. **NOT updated.** Also **NOT updated** to "applied" after D-419
  applied it.
- D-406 (27761): `(accepted, 2026-08-18)` — **NOT updated** to applied after D-419.
- D-418 (28407): `(accepted, 2026-08-18)`
- D-419 (28463): `(accepted, 2026-08-18)` — **carries a live, unresolved action item (`PendingConfirmation`)
  with no status tag reflecting it.**

**Candidate ACTIVE decision:** **D-419** — D-401's alarm split and D-406's NAT consumer map are **applied and
verified against AWS** (alerts-info topic created, four alarms moved, task defs 151/149/144 all on
`gha-44a12dfc9549`, services undisturbed at :150/:148, post-apply plan `No changes`). **D-418** is active for
the check itself (`make image-check`, `scripts/check_deployed_image_consistency.py`; tfvars pins reported,
never judged; absent tfvars is fine).

**Historical-but-must-stay-discoverable:** D-143 §4 (the untracked-tfvars origin), D-150 §2 (the check
becoming a program), D-357 (the diff-as-sets discipline and read-back-from-AWS practice; also the nightly
job-ordering argument, which is independent and still live), D-401's admission rule for the quiet channel and
its non-vacuity control (`target_5xx`, `rds_free_storage`, `bedrock_circuit_open`, `bedrock_spend_spike` named
never-quiet), D-406's `local.private_egress_consumers` reasoning and the "verified by producing no diff"
method, D-418's *"a warning repeated often enough starts being cited instead of checked"*, D-419's two apply
rules (never apply an unread plan; a surprising plan means re-plan).

**Ambiguities/uncertainty**

- **D-401's blockquote is malformed markdown.** The `>` block starting at 27533 ends mid-sentence: line 27539
  reads *"Everything else stays"* inside the quote and line 27540 *"on the page channel…"* continues **outside**
  it. **The correction and the original text are visually fused.**
- **The "Nth instance of this shape" counter (D-357 fifth, D-401 sixth) is partially invalidated by D-418 and
  never renumbered.** Whether the earlier instances (D-137, D-141, D-244) were also phantom is not addressed —
  D-418 says *"**Two of its three original shapes are real and stay**"*, so the count is **neither wholly right
  nor wholly wrong.**
- **D-401 has a status split across three entries:** configured (D-401), corrected re. deployed count (D-401
  blockquote / D-406), applied (D-419). **No single entry states current alarm routing without the other two.**
- **D-419's `PendingConfirmation`** means the four informational alarms currently route to **a topic with no
  confirmed subscriber** — "a channel nobody receives". This is an open user action **with no ⛔/⏸ marker
  anywhere in the heading.**
- **Cross-reference error:** line 27790 (D-406) and `PROGRESS.md:334` both cite **"D-137/D-141/D-356"** for
  CI-registers-then-terraform-re-registers drift. D-356 is the video/narrative erasure defect. **Almost
  certainly meant D-357. Two documents carry the same wrong id.**

**Confidence: HIGH** on links and applied state; **MEDIUM** on the instance-counter family (D-418 partially
invalidates without renumbering).

#### CHAIN M6 — Phantom IDs D-329 and D-363

The full transcription — every citation with its line number, the classification, and the explicit
can/cannot-infer split for both ids — is in **Phantom / missing decision IDs → D-329** and **→ D-363** above.
In summary:

- **D-329:** **no `## D-329` or `### D-329` heading exists anywhere in either file** (confirmed by
  `grep -nE "^#{2,4} D-(329|363)"`; the only hit, line 26276, is `#### D-329's detection gap…`, a sub-heading
  *about* it). It exists as a `####` sub-heading inside **D-330** (line 23582) plus nine further citations.
  **Classification: PHANTOM / MISSING ENTRY.** D-334's `Follows: D-329` is a **dangling reference**.
- **D-363:** **no heading of any level in either file.** Four citations only — DECISIONS.md:25728, 25894;
  PROGRESS.md:891, 2214 — describing a **harness** defect ("the click never landed") around **2026-08-16**.
  Weaker than D-329: no sub-heading, no `See D-363`, no `Follows:`/`Fixes:` relation anywhere. **Classification:
  PHANTOM / MISSING ENTRY.**
- **Phase 3 sweep caveat (M6's own):** D-359, D-360, D-361, D-362 and D-364 all appear as cited ids in the same
  two tables, and for several of them that table is the only evidence. **Phase 3 should confirm which of
  D-359–D-364 have real headings.**

**Confidence: HIGH** (absence of headings verified by exhaustive grep on both files).

> **Theme M cross-chain notes.**
>
> 1. **Heading-level fracture.** The file mixes `## D-xxx` (D-031, D-032, D-046, D-143, D-395, D-396, D-401,
>    D-406, D-418, D-419) with `### D-xxx` (D-288, D-305, D-317, D-326, D-334–D-373, D-381). **Any TOC or nav
>    generated by heading level will silently drop half the corpus.**
> 2. **Systematic pattern: status tags are never revised backwards.** Of the 30 entries read in this theme,
>    **zero** had a status tag edited after a later entry superseded, fixed, or invalidated it. The only
>    in-place status corrections are *self*-corrections inside the same entry (D-344's `#### ⚠️ Correction`,
>    D-401's blockquote). **Every forward pointer is written in the *superseding* entry, so the corpus is only
>    traversable newest→oldest.**
> 3. **Three entries carry stale tags that actively mislead:** D-344 (`removed by D-349`, self-refuted in its
>    own body), D-356 (`⛔ open — characterised, not fixed`, fixed by D-358), D-366 (`the clause stays ⏸`,
>    closed by D-370).
> 4. **Two documents disagree on D-356** (DECISIONS ⛔ open vs `PROGRESS.md:834` ✅ FIXED).
> 5. **Verification/addendum entries carry no Status field at all** (D-335 verification 24126, D-337
>    verification 24308) — they are **unindexable by status**.
> 6. **`D-137/D-141/D-356`** at `DECISIONS.md:27790` and `PROGRESS.md:334` is very likely a typo for **D-357**.
> 7. **Live open action with no marker:** D-419's SNS `PendingConfirmation` — four informational alarms
>    currently reach nobody.

---

*End of the Phase 2 supersession map. Nothing in this document retags, edits, or reconciles any entry in
`docs/DECISIONS.md`; Phase 3 owns that, and the candidate-active column above is its input, not its output.*

