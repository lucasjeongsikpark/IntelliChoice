# Open decisions — what needs a person, not more code

**Every decision in this file was answered on 2026-08-14 (D-322).** The execution plan is
ROADMAP.md's **Milestone 10 (Sessions U0–U7)**. This file is kept because the *reasoning* behind
each option is worth having when the work starts, and because two of the answers went against the
recommendation and that is worth being able to re-read.

**What is still genuinely open:**

1. **`YOUTUBE_YOUTUBE_API_KEY`** — U6 is blocked on a credential only the user can provide, into
   Secrets Manager. Nothing else about it is unresolved.
2. **The consolidation criteria for U7** — the *direction* is decided (consolidate into durable
   memory, then prune); *what in a finished session is worth remembering* is a design review, and
   the staging numbers have not been read yet.
3. **Depth generation timing** — decided in principle, parked in practice ("the near future").

Everything below is the record of how each was decided, marked with its outcome. Do not re-open one
without a reason that is new.

---

## 1. ✅ DECIDED — study re-serves the session's own exam questions → **re-render a different variant** (B)

**Status:** open since 2026-08-13 (D-314 amendment). Product decision, §5.9/§5.12.

A browser walk saw one question served **verbatim** as pre-exam Q1, as a study question, *and* as
post-exam Q1 of the same session.

**Why it matters more than it looks.** Pre and post sharing one fixed set is a defensible
learning-gain design — it is the same ruler twice. The **study** phase drawing the same variant is
not: the student practises the exact item they will be scored on, so the measured gain is inflated
by construction. That number is what the parent report is built on, and every other number on that
page borrows its credibility.

| option | consequence |
|---|---|
| **A. Exclude the session's exam items from study selection** | gain measures transfer rather than recall; study loses some of its best-matched items on thin topics |
| **B. Keep the item, re-render a different variant** | same skill, different numbers — the variant machinery already exists (D-189 mints per showing) |
| **C. Leave it, and stop claiming the gain number means learning** | cheapest, and makes the parent report's headline dishonest |

**Recommendation: B.** It preserves the study plan's targeting — the item was chosen because it is
the right practice — while removing the literal-recall path, and it uses machinery that already
exists rather than adding a constraint to the selector. A is the safer science but will starve
study on topics with thin banks, which is most of them today. C is not really an option once the
report is shown to a parent.

**Cost:** small change in study-item selection, plus one e2e assertion that no study item's
`question_variant_id` matches an exam item's. **Nothing else is blocked on it**, but every day it
stays open is a day of gain numbers nobody should quote.

---

## 2. ✅ DECIDED — no sink for client-side errors → **own authenticated endpoint** (A), not Sentry

**Status:** open since 2026-08-13 (D-315 stated it as a deliberate boundary).

Both ends now *log*: an `ErrorBoundary` turns a render crash into a recovery screen,
`window.onerror`/`unhandledrejection` cover what a boundary structurally cannot see, and
learning-api answers a `BedrockGatewayError` with a JSON 503 carrying a `trace_id`. **Nobody is
told about any of it.** A student's crash is recorded in a console nobody reads.

**Why it needs a decision rather than a default.** A sink means accepting arbitrary browser-supplied
text into infrastructure. That needs an authenticated endpoint, a rate limit, and a rule for stack
text — which can carry a question stem, and stems are student-facing content even if not PII.

| option | consequence |
|---|---|
| **A. Own endpoint** (`POST /client-errors`, authenticated, rate-limited, message+stack only) | no new vendor, no new data processor, fits the existing PII posture; one more thing to build and watch |
| **B. Sentry** | best tooling for the money, and it is a **new processor of minors' data** — a §5.32/§6.1 contractual question, not a library choice |
| **C. Stay as-is** | the recovery screen still works; nobody learns that it fired |

**Recommendation: A.** This product's whole PII posture is "no third party sees a minor's data
unless there is a reason", and a crash reporter is not a good enough reason to add a processor
before launch. Cap the body, drop anything that is not `message`/`stack`/`trace_id`, rate-limit per
token, and log it through the existing `PiiDenylistFilter`.

**Cost:** one thin route, one rate-limit rule, one test that a stack containing a question stem is
truncated. Half a session.

---

## 3. ✅ DECIDED — no URL routing → **`react-router`** (A)

**Status:** open since 2026-08-13 (audit item 3).

Any reload drops the student back into the session flow. The dashboard, results and sign-in are
unbookmarkable and the back button does nothing.

**Why it is not just polish.** It is a **prerequisite for §5.1.2's first-visit disclosures**, which
need a route-aware gate, and §5.1.2 is a launch gate. It also makes every future "send the parent a
link to the report" impossible.

| option | consequence |
|---|---|
| **A. `react-router` now** | boring, universal, ~1 session; unlocks §5.1.2 and shareable report links |
| **B. Hand-rolled `history` + a phase→path map** | no dependency, and re-implements a solved problem badly |
| **C. Defer to the §5.1.2 session** | the disclosure work then carries a routing rewrite inside it |

**Recommendation: A, and soon.** It is the one item on this list that *unblocks* another launch
gate rather than standing alone, and the longer the app grows at `/`, the more screens have to be
retrofitted.

---

## 4. ✅ DECIDED, and the answer improved on the question — **consolidate checkpoints into durable memory, then prune**

**Status:** open; **and the recorded framing of it is wrong** — corrected here.

PROGRESS carries a carry-over calling `question_variants` "the fastest-growing table in the
product". Measured on the local dev DB, 2026-08-14:

| table | rows | size |
|---|---|---|
| `checkpoint_writes` | **5,290,217** | **2557 MB** |
| `checkpoints` | **1,245,390** | **1872 MB** |
| `checkpoint_blobs` | — | 339 MB |
| `question_variants` | 352,198 | 127 MB |

The LangGraph checkpointer is **~4.8 GB across 6.5 M rows — roughly 37× `question_variants`**. The
shape is structural (one row per graph step per session, plus every write), so it will hold wherever
the graph runs; only the rate differs. **This is dev data after ~4 weeks including load tests, not a
staging measurement** — the staging number should be read before sizing anything.

**Why it matters.** RDS storage is the cheap part; the expensive parts are backup windows, restore
time during an incident, and vacuum behaviour on a table nobody prunes. Retention is also a
**privacy** control: SPEC's 90/90/365 windows are stated in the Privacy Notice, and a checkpoint
holds the session's working state.

| option | consequence |
|---|---|
| **A. Prune completed sessions' checkpoints after N days** | the largest win by far; a completed session's checkpoint has no resume value |
| **B. Prune `question_variants` runtime rows** | tidy, and worth ~2.5% of the problem |
| **C. Both, one scheduled job** | one job, one place to reason about retention |

**Recommendation: C, with A sized first.** Read the staging numbers before choosing N; align N with
the retention windows already promised in the Privacy Notice rather than inventing a second number.

**DECISION — option D, which was not on this list.** *"Consolidate the checkpoint into long-term
durable memory according to some criteria, then keep it there."* Every option above deletes; this
one **keeps what is worth keeping first**. It is strictly better and it is not a new mechanism:
`packages/memory` (S25) already consolidates learning memory and already has a scheduled entrypoint.
Pruning discards a finished session's only durable trace; consolidating keeps the part the student's
next session can use. The design question moves from "how long do we hold the working state" to
**"what in a finished session is worth remembering"** — a better question, and the one the memory
system exists to answer. Design review before code; staging numbers before sizing. ROADMAP U7.

**Cost:** one scheduled task next to the existing `retention-purge`, plus a staging measurement
first. **Not urgent at today's volumes; it becomes urgent the moment real students arrive**, which
is the wrong time to design it.

---

## 5. ✅ DECIDED — spend it, **but later** ("the near future"); parked, nothing blocked

**Status:** open since C1 close (D-313). Pure budget call, nothing blocked.

D-223's target is 5 items per occupied `(topic, tier)` cell. Standing at **84 of 153 cells**, short
**189 items** ≈ 315 candidates at the measured 60% acceptance ≈ **$13–16** and ~3.5 h of wall clock
at the account's measured ~1.5 candidates/min.

**Recommendation: spend it.** It is the last substantial item in C1, the estimate is measured rather
than guessed, every run sits behind a green preflight and an explicit `--run-budget-cents`, and
stopping part-way is safe (D-193's per-candidate commit). The alternative is carrying an
"incomplete" clause indefinitely for the price of two coffees.

---

## 6. ✅ DECIDED — **as soon as possible**, against the recommendation to wait for §5.1.2. ⛔ still blocked on the key

**Status:** open. The catalog holds **4 videos covering 4 of 112 skills and 1 of 33 topics**.

The no-video path is no longer a trap (D-314 fixed the dead end and the metrics miscount), so this
is now about coverage rather than correctness.

**Decision needed:** provision a real key and a quota budget, or accept that the video intervention
is effectively absent at launch and say so in the product copy.

**Recommendation: provision it, but after §5.1.2.** YouTube recommendations are one of the eleven
first-visit disclosures; shipping the feature before the disclosure that describes it is the wrong
order.

---

## 7. ✅ DECIDED — **edit the declarations to match the judge**

**Status:** open since D-313.

**106 items across 39 skills** carry a stored tier outside their skill's declared
`difficulty_tiers`, because D-302 stores the judge's rating and the judge may rate outside the
plan's range. Nothing breaks at runtime — `difficulty_tiers` is read by the taxonomy and the planner
only, never by serving code — but C1's "multi-tier where the skill spans" clause is measured against
a span the content no longer respects, and some skills read "single-tier" only because the judge
moved their items off the declared tiers.

**Recommendation: edit the declarations to match the judge.** The judge is the instrument the bank
is actually built with; a declaration that contradicts it is documentation of an intent nobody
enforces. This makes the multi-tier clause measurable against something true.

**Cost:** a taxonomy edit and a re-measure. No generation spend.

---

## 8. ⏸ UNCHANGED — not raised; D-310 stands until staging stops being synthetic

**Status:** declined once, with a reason (D-310, 2026-08-13).

The reasoning still holds: staging only, production is a separate frozen system, Postgres holds no
PII by design, and the residual risk is Bedrock spend which the gateway caps.

**What would change it:** staging serving anything real — a real student account, a real parent
email, a real document. **Recommendation: keep the decision, and re-open it the day staging stops
being synthetic.** If revisited: rotate at the source, then re-run `deploy-staging.yml`, because ECS
tasks read the value at container start.

---

## 9. ✅ DECIDED — **batch merge**. (There are **26**, not 7 — my count was a filter bug)

**Status:** 7 non-noise PRs open, the oldest from 2026-07-24.

They are accumulating because each one is individually not worth a decision.

**Recommendation: adopt a standing rule** — patch and minor bumps merge on green CI without review;
major bumps (`actions/checkout` 4→7, `python` 3.12→3.14, `@types/node` 24→26) get read
individually, and the Python major in particular is a runtime change that wants its own run. Then
clear the backlog in one pass.

---

## 10. ✅ ALL DECIDED — narrative header: yes (new API field) · ladder pause: investigate · `formatDateLabel`: **CDT** · `push` trigger: unchanged, stays manual · repeated context sentence: not raised

- **The narrative modal reuses "Why this is your next step" on a results context.** Fixing it needs
  a **new API field** — the snapshot carries the narrative *text*, not its stage. Small, but it is a
  wire-shape change, so it is a decision rather than a patch.
- **`clearInterventionIfPresent` misses the retry-ladder pause ~1 in 12 staging walks** (D-321).
  Classified as a harness race, not a product defect. The next step is a breadcrumb recording which
  locator won the wait; deciding to spend that hour is the only open part.
- **`formatDateLabel` shifts a *date-only* string back a day.** Harmless today because the API sends
  full timestamps. Fix now, or leave it armed for whoever first returns a date-only field.
- **`deploy-staging.yml`'s `push` trigger stays commented out.** The stated condition ("run and
  reviewed at least once") was met long ago; enabling it is a deploy-behaviour decision nobody has
  taken. **Recommendation: leave it manual** while the deploy still runs migrations and re-seeds.
- **15 of 92 items with a context block repeat its opening sentence in the stem**, so a student
  reads it twice. Cosmetic, concentrated in new content, and no gate checks for it. Decide whether
  it is worth a gate rule or a one-off content pass.

---

## Not decisions — already settled, listed to stop them being re-litigated

- **Auto-approval with no spot-check sampling** (D-289). A 20-item-per-wave sample was recommended
  and declined; both are on the record.
- **Follow the judge's tiers, accept an uneven distribution, fill the question count** (D-302).
- **Integration stays deferred until this codebase is finished and tested** (D-152). Do not measure
  reachability, finalize the §3.1 auth option, or rewrite the MySQL dev fake before then.
- **The difficulty rubric needs no re-anchoring** (D-300), measured and deliberately not acted on.
