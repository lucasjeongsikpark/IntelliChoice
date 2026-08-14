# U7 — Consolidating checkpoints into durable memory

**Status:** design review, awaiting your decision. No code written.
**Date:** 2026-08-14 · **Decision this feeds:** D-322 §4, the reframing from *pruning* to
*consolidation*.

---

## 0. What this document is for

ROADMAP U7 says **design review before any code**, and **read the staging numbers first** — because
"sizing a retention job from dev data that includes load tests is how you get the wrong N". This
document does both and then asks you four questions.

**Two things it corrects before proposing anything.**

1. **The retention policy already exists in SPEC and nobody implemented it.** SPEC's retention
   section (around line 1583) reads: raw chat messages 90 days, **completed checkpoints 30 days**,
   pending interrupted sessions up to 90 days, security/audit logs one year, solution images deleted
   immediately. So U7 is not inventing a policy — it is implementing a specified one, and your
   consolidation reframing is what makes the specified deletion non-destructive.
2. **PROGRESS has been calling these "the 90/90/365 windows". Completed checkpoints are 30 days, not
   90.** Repeated in my own notes several times. The number that matters for this design is the
   smaller one.

---

## 1. The measurement, staging first

**Staging Postgres — `db.t4g.micro`, 20 GB allocated:**

| date | used | free |
|---|---|---|
| 2026-08-07 | 3.23 GB | 16.77 GB |
| 2026-08-13 | 3.27 GB | 16.73 GB |

**~10 MB/day over the last week, 3.27 GB of 20 used.** On that trend alone the instance has years of
headroom, and **there is no urgency on staging today.** That is the honest headline, and it disagrees
with the impression the dev number gave.

**Dev Postgres, for the per-session cost only** (its absolute size is load-test noise, exactly as
suspected):

| | |
|---|---|
| `checkpoints` + `checkpoint_writes` + `checkpoint_blobs` | **4,860 MB** |
| distinct `thread_id` (sessions) | **49,244** |
| average per session | **0.10 MB**, 110 write rows |
| write rows per session — p50 / p90 / p99 / max | **37 / 246 / 431 / 628** |
| bytes per `checkpoint_writes` row | **507** |

**A full journey is a p90-ish session, so ~0.2–0.25 MB.** I originally guessed 24 MB per session from
dividing 4.8 GB by ~200 *product* sessions; that was wrong by two orders of magnitude, because there
are 49,244 threads and most are short test sessions. The corrected figure is what the projection below
uses.

**Projection at the stated target of 1,000+ MAU:**

| assumption | value |
|---|---|
| sessions per student per month | 4 |
| sessions per month | 4,000 |
| checkpoint bytes per session | 0.25 MB |
| growth | **~1 GB/month → ~12 GB/year** |
| staging headroom today | 16.7 GB → **~17 months** |

**So: not urgent, and not ignorable.** Nothing prunes today, so the curve only goes up, and it lands
inside a two-year horizon on the current instance class. That is the right framing — a capacity
question with a year of runway, not a fire.

---

## 2. What in a finished session is worth remembering

This is the question your reframing turned the design into, and it is the one I most want your
judgement on.

The machinery already exists. `packages/memory` (S25) consolidates `learning_events` into
`semantic_memory` facts, with a fixed vocabulary of **12 fact types**: `strength`, `weak_skill`,
`misconception`, `explanation_preference`, `scaffolding_level`, `vocabulary_difficulty`,
`guessing_pattern`, `hint_dependence`, `improvement`, `effective_intervention`, `open_question`,
`next_skill_recommendation`. It has a scheduled entrypoint, a stability bar, and a
`_contradicts_measured_mastery` check that refuses a fact disagreeing with measured mastery.

**The important structural fact: almost everything durable is already outside the checkpoint.**

| what a session produces | where it already lives durably |
|---|---|
| exam items, answers, scores | `assessment_items`, `assessment_attempts` |
| study items, attempts, outcome labels | `study_items`, `study_attempts` |
| mastery and recommended difficulty | `mastery` |
| learning gain | `learning_gain` |
| the narrative shown at each stage | `stage_transitions` |
| blocked attendance attempts | `blocked_sessions` |
| the semantic facts S25 derives | `semantic_memory` |

**So my recommendation is that the answer to "what is worth remembering" is: nothing new.** The
checkpoint is LangGraph's *working state* — the resumable position inside a graph turn. Once a session
is `completed` there is nothing left to resume, and every durable fact about it has already been
written elsewhere by design (that is CLAUDE.md's rule 1 doing its job: Postgres holds
`*_external_id` references and derived facts, not a transcript).

**What that makes U7:** not "extract the good bits then delete", but **"verify the good bits are
already extracted, then delete"** — with the verification being the part that earns the deletion. That
is a smaller and much safer job than the ROADMAP implies, and if you agree it is the single biggest
scope reduction available here.

**Where I could be wrong, and what I would check before believing myself:** the checkpoint may hold
`pending_study_narrative` markers, `last_message`, or interrupt state that never got written anywhere
durable. I would enumerate `LearningState`'s fields against the table list above and report any field
that exists *only* in the checkpoint. That enumeration is ~an hour and I would do it before writing
any deletion code.

---

## 3. The trigger

**Proposed:** a session is eligible when **both** hold.

1. `phase == "completed"` — the graph has nothing left to resume.
2. The last checkpoint write is older than an **age floor**, default **30 days**, matching SPEC.

Why both: `completed` alone would delete a session a parent might still be reading a report from, and
an age floor alone would delete a *pending* session that a student intends to return to — which SPEC
gives a *different*, longer window (90 days) precisely because abandoning a student's half-finished
exam is worse than keeping bytes.

**Pending sessions get the 90-day window and are handled separately, or not at all in this session.**
Mixing the two policies into one job is how the shorter window ends up applied to the longer case.

---

## 4. Where it lands

**Nowhere new.** Per §2, the durable record already exists across the tables listed there. If the
§2 enumeration finds a checkpoint-only field worth keeping, it lands in `semantic_memory` via the
existing S25 path — **one durable record, not two** — and only if it fits an existing `fact_type`.
Inventing a 13th fact type to hold a scrap of graph state would be the wrong trade.

---

## 5. What becomes safe to delete

For an eligible session: its rows in `checkpoints`, `checkpoint_writes`, `checkpoint_blobs`, keyed by
`thread_id`. Nothing else.

**Deletion order matters and should be one transaction per thread** — a partial delete leaves a
checkpoint LangGraph can load but not resume, which is worse than either extreme.

**What must not be deleted:** anything in the §2 table list. Those are the record; the checkpoint is
the scaffolding.

---

## 6. How this squares with the retention windows

| SPEC window | what U7 does |
|---|---|
| completed checkpoints, **30 days** | this job, and it is the first implementation of it |
| pending interrupted sessions, up to 90 days | **out of scope here**, different window, different risk |
| raw chat messages, 90 days | untouched — different subsystem (`tutor_chat_messages`) |
| structured learning events | untouched, and they are what `semantic_memory` is derived from |
| security/audit logs, one year | untouched |

**One tension to name:** SPEC says "Final retention requires legal and policy approval." Implementing
the 30-day window is implementing SPEC's own recommendation, not settling the policy — and it is
reversible in the only direction that matters, since a longer floor deletes strictly less.

---

## 7. What would falsify this design

Stated up front, because a retention job that is wrong deletes things quietly.

1. **A restore test.** Take a consolidated session, delete its checkpoint, and assert the student's
   *next* session still sees their mastery, their weak skills, and their memory facts. If anything is
   missing, §2's claim is false and the design changes.
2. **A field enumeration.** Every `LearningState` field mapped to the durable table that holds it, or
   flagged as checkpoint-only. Any unflagged field is an unproven assumption.
3. **A dry-run count.** How many threads the job *would* delete, and how many bytes, before it deletes
   anything — run against staging and reported, not inferred from dev.
4. **An idempotency check.** Running twice must delete nothing the second time.

---

## 8. What I recommend

**Do the enumeration and the dry run, and do not write the deletion yet.** Concretely:

1. Enumerate `LearningState` against the durable tables (~1 hour). Report any checkpoint-only field.
2. Add a **dry-run** mode that reports eligible threads and bytes on staging, deleting nothing.
3. Only then write the deletion, behind the 30-day floor, with the restore test as its gate.

**Why not just build it:** staging has ~17 months of headroom at the projected rate and 3.27 GB of 20
used today. There is no deadline pressure, and the failure mode of getting this wrong is silent data
loss for a K-12 student's learning history. The measurement says we can afford to be careful.

---

## 9. What I need from you

1. **Do you agree with §2's claim** — that nothing new needs remembering, because every durable fact
   is already outside the checkpoint? This is the biggest scope question. If you think there *is*
   something in a finished session worth keeping that the tables in §2 do not hold, say what and the
   design grows to include it.
2. **Age floor: 30 days as SPEC says, or longer?** SPEC's own number is 30. Longer is strictly safer
   and strictly less effective.
3. **Pending sessions (90-day window): in or out?** I recommend out — different window, different
   risk, and mixing them is how the wrong policy gets applied.
4. **Is the ~17-month runway acceptable for now?** If yes, my recommendation in §8 stands. If you want
   the headroom sooner, the alternative is raising the instance's storage, which is a smaller and
   fully reversible change than a deletion job.
