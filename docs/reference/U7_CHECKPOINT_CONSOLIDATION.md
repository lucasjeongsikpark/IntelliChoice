> **COMPLETED 2026-08-20 — the questions in this document are answered. The measurements stand.**
>
> **What still stands:** every measurement below, **as of 2026-08-14, on staging**, read via a
> read-only `ops-task`. This is the only staging checkpoint sizing that exists anywhere, and it is
> reference material, not an open question.
>
> **What is answered:** §8's recommendation and **all four of §9's questions** were decided by
> **D-333** (with **D-332** landing `learning_sessions` the same day). Read §8 and §9 as the record
> of what was *asked*, not as open work. Per-item annotations are inline below.
>
> **D-333's precondition, verbatim, because it gates any future retention change:**
>
> > Before deleting any eligible checkpoint, run long-term memory consolidation first.
>
> **Environment labelling — do not "reconcile" these numbers with anyone else's.** Every figure in
> this document is **staging** (checkpoint tables **~285 MB** total). `OPEN_DECISIONS` #4 quotes
> **development** (~4.8 GB). They are roughly 17× apart because they measure **different
> environments**, not because one is wrong. Picking one would destroy information.
>
> Pointer: **D-333** (deletion windows, consolidation gate), **D-332** (`learning_sessions`),
> **D-331** (records this measurement), **D-336** (closes §10).

# U7 — Consolidating checkpoints into durable memory

**Status:** design review, **measured**. Steps 1–2 of §8 are done; no deletion code written.
**Date:** 2026-08-14 (measured pass same day) · **Decision this feeds:** D-322 §4, the reframing
from *pruning* to *consolidation*, and D-331 which records this measurement.

---

## 0. What this document is for

ROADMAP U7 says **design review before any code**, and **read the staging numbers first** — because
"sizing a retention job from dev data that includes load tests is how you get the wrong N". This
document does both and then asks you what remains open.

**The user's design shape, and it is the one being built to** (2026-08-14): *extract the
permanently-needed domain state / learning memory from the execution checkpoint → store it
separately → delete the checkpoint.* This is **not** the same as §2's original recommendation
("verify it is already extracted, then delete"). Keeping extraction as a real step is what caught
the five fields in §2.3 that have no durable home anywhere. Had the design gone with "nothing new
needs remembering", those five would have been deleted silently.

**Three things it corrects before proposing anything.**

1. **The retention policy already exists in SPEC and nobody implemented it for checkpoints.** SPEC's
   retention section reads: raw chat messages 90 days, **completed checkpoints 30 days**, pending
   interrupted sessions up to 90 days, security/audit logs one year, solution images deleted
   immediately.
2. **PROGRESS has been calling these "the 90/90/365 windows". Completed checkpoints are 30 days.**
3. **`LearningState` has 31 fields, not 27.** An earlier count in this session was wrong; the
   enumeration in §2 covers all 31.

---

## 1. The measurement, staging first

### 1.1 What the checkpoint tables actually weigh

**Staging, read via a read-only `ops-task` `run-task`, 2026-08-14 23:05 UTC:**

| table | size | rows |
|---|---|---|
| `checkpoint_writes` | 153 MB | 324,444 |
| `checkpoints` | 114 MB | 74,706 |
| `checkpoint_blobs` | 18 MB | 30,369 |
| **total** | **~285 MB** | 429,519 |

**This corrects the framing the first draft of this document used.** It quoted "staging Postgres
3.27 GB of 20 GB used" and discussed checkpoint growth against it. The checkpoint tables are
**285 MB — about 8.7%** of that 3.27 GB. The rest is other tables, indexes and WAL. Checkpoints are
not what is filling staging.

### 1.2 Where the bytes are, by phase — the finding that should decide this session

**Environment: staging, 2026-08-14** (same read as §1.1). Every figure in this subsection is
staging; none of it is development.

| phase | threads | bytes | share | per thread |
|---|---|---|---|---|
| `pre_exam` (abandoned mid-exam) | 1,581 | 119.4 MB | **64.7%** | 75 KB |
| `(no-phase)` — **chat threads** | 2,178 | 35.6 MB | 19.3% | 16 KB |
| `study` (abandoned mid-study) | 184 | 22.9 MB | 12.4% | 124 KB |
| **`completed`** | **9** | **3.2 MB** | **1.7%** | 350 KB |
| `student_selected` | 331 | 1.7 MB | 0.9% | 5 KB |
| `blocked` | 78 | 1.3 MB | 0.7% | 17 KB |
| `post_exam` | 3 | 0.3 MB | 0.2% | 108 KB |
| `awaiting_child_selection` | 18 | 0.1 MB | 0.1% | 5 KB |

**U7 as scoped — completed sessions only — addresses 1.7% of checkpoint storage.** Abandoned
sessions are **77%** of it and chat is another 19%.

**And at a 30-day floor it addresses 0% today.** The oldest thread on staging is **22 days** old
(2026-07-23, when staging was first deployed). Nothing is eligible under any floor of 30 days or
more. The dry-run's honest answer today is **zero threads, zero bytes**.

### 1.3 The two numbers that do transfer to production, and the one that does not

**Transfers — per-session bytes:**

| | |
|---|---|
| a completed session | **350 KB** (staging, n=9) · 233 KB (dev, n=4,023) |
| an abandoned pre-exam session | **75 KB** (staging) |

**Does not transfer — the thread mix.** Staging's 4,382 threads are almost entirely e2e-harness
walks, which abandon at `pre_exam` constantly and complete rarely. A real student population has a
different mix. So `pre_exam` being 65% of staging's bytes is *not* a prediction that it will be 65%
of production's. What it does establish is that **abandoned sessions are the structurally
unbounded case**, because nothing deletes them and the current design does not propose to.

That matters more in this product than in most: D-152 §2 records that
`AttendanceStatus.UNKNOWN → blocked` is a **routine** production path, not a rare one.

### 1.4 Projection

**Built from the staging per-session bytes above** (0.35 MB/completed session, staging, n=9) against
staging's free space. Not a development measurement and not a production one.

| assumption | value |
|---|---|
| sessions per student per month | 4 |
| sessions per month at 1,000 MAU | 4,000 |
| bytes per completed session | 0.35 MB |
| completed-session growth | **~1.4 GB/month → ~17 GB/year** |
| staging free space today | 16.7 GB |

**~12 months of headroom on completed sessions alone**, before counting the abandoned sessions that
today are the larger share. The earlier "~17 months" figure used 0.25 MB/session; the measured
350 KB shortens it.

**Still not a fire, and no longer a comfortable margin either.** The right reading is: a capacity
question with about a year of runway, where the thing that will actually consume the runway is not
the thing this session was scoped to delete.

---

## 2. What in a finished session is worth remembering

### 2.1 The structural fact

Almost everything durable is already outside the checkpoint:

| what a session produces | where it already lives | retention |
|---|---|---|
| exam items, answers, scores | `assessment_items`, `assessment_attempts` | **permanent** |
| study items, attempts, outcome labels | `study_items`, `study_attempts` | **permanent** |
| mastery and recommended difficulty | `mastery` | **permanent** |
| learning gain | `learning_gain` | **permanent** |
| hint ladder levels served | `hint_events` | **permanent** |
| blocked attendance attempts | `blocked_sessions` | **permanent** |
| the narrative shown at each stage | `stage_transitions` | **90 days** |
| the semantic facts S25 derives | `semantic_memory` | **90 days** |
| the event stream those are derived from | `learning_events` | **365 days** |

**A trap this table exposes.** Three of the "durable" homes are themselves on a retention clock
(`retention_purge_cli.py`, D-114/D-153). **"Store it separately" must land in the permanent set**,
or consolidation only moves the deletion date closer.

### 2.2 Verified on real data, not asserted

For all **9** completed staging threads, every durable trace exists:

```
TRACE | thread | events | narratives | pre_att | post_att | study_att | gain | mastery | facts | hints
      |        | 30-68  |    4-9     |  10/10  |  10/10   |   2-16    |  1   |   39    |  20   |  238
```

**9 of 9, no gaps.** `learning_events.session_id` is the learning-session id — verified on dev at
**5,718 of 5,718 rows matching a live thread**, so the join is real and not a naming coincidence.

**Two caveats stated rather than buried:**

1. **All 9 sessions belong to one e2e student.** The per-session columns (events, narratives,
   attempts, gain) are 9 independent observations; the per-student columns (mastery 39, facts 20,
   hints 238) are **one observation repeated 9 times**.
2. **Dev disagreed, and the disagreement is explained.** On dev only **6 of 4,023** completed
   threads had events. Dev's completed threads come overwhelmingly from pytest runs against fakes
   that never emit; its event-bearing sessions sit in `pre_exam` (633 of 771). Reported because a
   6/4023 taken at face value would have falsified §2 on data that could not support the claim.

### 2.3 The five fields with no durable home — what the enumeration actually found

All 31 `LearningState` fields were mapped. **26 are either durable or transient-by-design.** These
five are neither:

| field | why it has no home | value for a *completed* session |
|---|---|---|
| `week_id` | only `blocked_sessions.week_id` exists; a non-blocked session's week is nowhere | **real** — "did this student do their weekly session?" is a product question and `learning_gain` has only `computed_at` |
| `parent_external_id` | no column in any model | **real, audit-shaped** — who drove the session, parent or student |
| `bedrock_spend_cents` | per-call costs are in `cost_reservations` and `stage_transitions.cost_cents` (90-day); the **session total** is nowhere | moderate — reconstructible from `cost_reservations` while those rows live |
| `attendance_status` | no column | low — a completed session was necessarily not blocked |
| `attendance_resolution` | SPEC §5.6.5 names it; `blocked_sessions` stores `blocked_reason` but **not** the resolution | low **for completed**, but a genuine gap for blocked sessions |

**`phase` itself** is a sixth, half-case: the sub-sessions carry their own `status`, but the
*learning session's* lifecycle state exists only in the checkpoint. For completed sessions the
existence of a `learning_gain` row implies it.

### 2.4 What this makes U7

**Not "verify then delete", and not "invent a memory format".** The extraction target for those
five fields is the table that never existed: a small **`learning_sessions`** summary row, one per
session. That is a plain additive migration, it lands in the permanent set as §2.1 requires, and it
incidentally fixes a real orphan — `stage_transitions.learning_session_id` and
`tutor_chat_messages.learning_session_id` are bare strings today with nothing to point at.

Inventing a 13th `semantic_memory` fact type to hold graph state would be the wrong trade, and
`semantic_memory` is 90-day anyway.

---

## 3. The constraint the first draft missed: the tables are shared with chat

`checkpoints` / `checkpoint_writes` / `checkpoint_blobs` hold **both** apps' graphs.
`learning_api` writes `LearningState`; `chat_api` writes `QAState` to the same tables, keyed by
`thread_id`, through its own `AsyncPostgresSaver` on the same Postgres.

Measured on dev: **31,416 learning-only threads, 12,638 chat-only, 0 overlap**, plus 5,547 that
wrote no distinguishing channel. On staging chat is **2,178 threads / 19.3% of the bytes**.

**Consequences for any deletion job:**

- A job keyed on `phase == 'completed'` **silently skips every chat thread**, because `QAState` has
  no `phase` channel. Chat checkpoints then grow forever.
- A job written as "delete old threads" would delete chat threads under a policy reasoned about for
  learning sessions. Chat's own window is 90 days (`tutor_chat_purge_cli`), and its messages are
  purged while its checkpoints are not.
- So the job must **classify thread kind explicitly** rather than infer it from a field's absence.

---

## 4. The trigger

**Proposed, unchanged:** eligible when **both** hold.

1. `phase == "completed"` — the graph has nothing left to resume.
2. The last checkpoint write is older than an **age floor**.

Why both: `completed` alone would delete a session a parent might still be reading a report from;
an age floor alone would delete a *pending* session a student intends to return to, which SPEC
gives a longer window precisely because abandoning a half-finished exam is worse than keeping bytes.

---

## 5. What becomes safe to delete

For an eligible session: its rows in `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, keyed
by `thread_id`. Nothing else. **One transaction per thread** — a partial delete leaves a checkpoint
LangGraph can load but not resume, which is worse than either extreme.

**What must not be deleted:** anything in §2.1. Those are the record; the checkpoint is scaffolding.

**Why the scaffolding is most of the weight**, measured on dev blob channels: `last_items` (73 MB)
and `__start__` (56 MB) are **93%** of blob bytes, and both are pure working state — the re-serve
payload and each turn's input.

---

## 6. How this squares with the retention windows

| SPEC window | what U7 does |
|---|---|
| completed checkpoints, **30 days** | this job — first implementation |
| pending interrupted sessions, up to 90 days | **out of scope** (your decision), and §1.2 shows this is where the bytes are |
| raw chat messages, 90 days | already implemented (`tutor_chat_purge_cli`) |
| **chat checkpoints** | **unaddressed by anything**, see §3 |
| structured learning events | 365 days, already implemented |
| security/audit logs, one year | untouched |

**One tension to name:** SPEC says "Final retention requires legal and policy approval."
Implementing the 30-day window implements SPEC's own recommendation; it does not settle the policy,
and it is reversible in the only direction that matters, since a longer floor deletes strictly less.

---

## 7. What would falsify this design

1. ~~**A field enumeration.**~~ **Done** — §2.3. It found five fields with no durable home, so the
   original §2 claim is *substantially* right and *not exactly* right.
2. ~~**A dry-run count.**~~ **Done** — §1.2. Answer today: **zero eligible threads**.
3. **A restore test.** Still owed. Delete a consolidated session's checkpoint and assert the
   student's next session still sees mastery, weak skills and memory facts. §2.2 is the read-only
   form of this and is not a substitute.
4. **An idempotency check.** Still owed. Running twice must delete nothing the second time.

---

## 8. What I recommend now

The enumeration and dry-run changed the recommendation. **The scoped job is no longer the highest-value
thing here.**

1. **Do not write the completed-session deletion yet.** It reclaims 1.7% of checkpoint bytes and
   zero bytes today. Nothing is eligible for at least another 8 days on staging, and there is no
   production data at all.

   > **[Annotation 2026-08-20 — absolute date supplied; recommendation superseded.]** "Another
   > 8 days" is measured from **2026-08-14**, so the 30-day floor's first eligibility on staging is
   > approximately **2026-08-22**. The claim was self-expiring as written and is now anchored;
   > re-measure rather than trusting either form. The recommendation itself was **superseded by
   > D-333**, which chose the windows and shipped the deletion **dry-run by default**.
2. **Add `learning_sessions` (§2.4) regardless of when deletion ships.** It is additive, it is the
   "store it separately" half of your design, and every day it does not exist is a day the five
   §2.3 fields are recorded nowhere. This is the piece with value independent of retention.
3. **Re-scope the deletion around what actually grows.** Abandoned sessions and chat threads are
   96% of the bytes. A 90-day floor on abandoned sessions is a bigger, more honest win than a
   30-day floor on completed ones — and it is the one that needs the most care, which is an
   argument for designing it deliberately, not for continuing to leave it unbounded.

---

## 9. What is still open

> **[Annotation 2026-08-20 — nothing in this section is still open. All four were answered by
> D-333, one of them (question 2) by D-332 on the same day this document was written.]** The
> questions are kept as the record of what was asked. Per-question answers are inline.

1. **Age floor** — not yet chosen. The dry-run reports **zero eligible at 30, 90 and 180 days**, so
   the choice costs nothing today and can be made on principle rather than on reclaim.

   > **ANSWERED — D-333.** Three windows were chosen, with consolidation as a gate: *"Before
   > deleting any eligible checkpoint, run long-term memory consolidation first."* Chat and
   > abandoned/pending checkpoints take a **90-day inactivity** window. The job ships **dry-run by
   > default**. Read D-333 for the windows and for the classifier hole it records against itself.

2. **Does `learning_sessions` get built now?** My recommendation is yes (§8.2), independent of the
   deletion job.

   > **ANSWERED — yes, and it is built.** Decided by **D-332**, the same day this document was
   > written. Verified in the repository on 2026-08-20:
   >
   > - **Migrated:** `packages/db/alembic/versions/6538a95bc990_d331_learning_sessions.py`.
   > - **Modelled:** `LearningSession` / `__tablename__ = "learning_sessions"` in
   >   `packages/db/src/intellichoice_db/models/learning_session.py`, with
   >   `LearningSessionRepository` in `packages/db/src/intellichoice_db/repositories/`.
   > - **Produced, on a schedule:** `session_consolidation_cli.py` in
   >   `apps/learning-api/src/learning_api/services/`, scheduled in
   >   `terraform/modules/scheduled-jobs/main.tf` ("Project completed learning threads into
   >   learning_sessions (U7/D-332)").
   > - **Consumed:** the retention job reads eligibility from it
   >   (`checkpoint_retention_cli.py`), which is what makes D-333's consolidation gate enforceable.
   >
   > Note for anyone reading migration history: an **earlier, unrelated** `learning_sessions` table
   > was dropped by `f3d82932ed10` as an S5 stand-in. The table described here is the new D-331/D-332
   > one, not that one revived.

3. **Chat checkpoints (§3)** — currently unbounded and addressed by no policy. In scope for a
   follow-up, or filed?

   > **ANSWERED — D-333.** Chat checkpoints are covered by the 90-day inactivity window, and D-333
   > records what it decided about consolidating a chat thread before deleting it (chat-api persists
   > nothing about its conversations, and a full chat-summary table was explicitly *not* built).
   > §3's structural warning still stands as a design constraint: a job keyed on
   > `phase == 'completed'` silently skips every chat thread, so thread kind must be classified
   > explicitly.

4. **Abandoned sessions (§8.3)** — you scoped them out, correctly, on the reasoning that mixing
   windows is how the wrong policy gets applied. §1.2 says they are also where the growth is. Worth
   revisiting as its own session?

   > **ANSWERED — D-333.** Abandoned/pending checkpoints were brought in scope under the same
   > 90-day inactivity window, which is the re-scoping §8.3 argued for.

---

## 10. Observation logged, not chased

One completed staging thread (`98abc0f0…`) has **two** `learning_gain` rows for a single
`pre_assessment_session_id`; the other eight have one. Either a re-finalize legitimately writes a
second row or gain is computed twice for one cycle. **Out of U7's scope** and recorded as a
carry-over rather than investigated here.

> **[Annotation 2026-08-20 — no longer a carry-over. CLOSED by D-336.]** The carry-over was picked
> up and closed: a cycle finalized twice showed a parent the same session twice. Of the two
> candidate explanations offered above, it was **gain computed twice for one cycle**, not a
> legitimate re-finalize. D-336 closes it on both halves — the cause cannot recur (a guard plus a
> database constraint), and the existing duplicate rows were cleaned up with the earliest row
> surviving. Do not re-investigate from this section; read D-336.
