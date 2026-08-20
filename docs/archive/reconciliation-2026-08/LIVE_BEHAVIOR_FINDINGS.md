> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase 3B-2 material live findings (LB-01 … LB-08) — every number here is bound to its probe window and build SHA. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# LIVE_BEHAVIOR_FINDINGS.md — Phase 3B-2 material findings

**Date:** 2026-08-19 (probe window **2026-08-20T03:30Z – 05:00Z** UTC)
**Companion document:** [LIVE_BEHAVIOR_EVIDENCE.md](LIVE_BEHAVIOR_EVIDENCE.md) — that file is the
per-claim live-probe record (every command, its verbatim output, the identities used, and the claim
it settles). This file is the *material* residue: only what the live probes actually surfaced or
sharpened.

**What was probed.** Six behavioural claims — REQ-46, TEST-21, TEST-28, WORK-05, WORK-13, WORK-29 —
across three lanes: the local suites (free), the staging learning journey through
`d35dfnjzmgrm01.cloudfront.net` (paid), and the staging chat RAG path through
`d222glidpp4azv.cloudfront.net` (paid). Identities were synthetic fixtures only (`student-ext-10`,
`student-ext-9`, one anonymous guest chat session). Spend: 2 staging learning walks + 1 guest RAG
turn on real Bedrock, session-budget-capped. Zero AWS mutation, zero real external side effects,
zero repository modification.

**Categories.** Every finding below is tagged with one of the phase brief's five categories:

- **behavioral defect** — the deployed or local system misbehaves.
- **documentation drift** — a document disagrees with the system as it is.
- **stale completion claim** — a document's status (done / open / measured / unmeasured) is out of
  date relative to the system.
- **environment-only** — a property of the deployment or the environment, not of the code.
- **repo-tests-vs-deployed mismatch** — what the test suite asserts differs from what the deployed
  build is or covers.

**Scope.** This document records findings. It does not fix anything and it does not decide anything.
Every entry traces to an executed command in the companion evidence file or to a direct re-read of a
repository file, quoted verbatim. Severities are quoted from the Phase 3B-2 adjudication and are not
re-derived; where the adjudication assigned none, the entry says **"not assigned"** rather than
inventing one. Each finding closes with **not fixed — recorded**.

---

## 1. Headline

**No new behavioral defect was discovered in any live probe.** Across the staging journey run and the
guest RAG turn the capture teardown reported `consoleErrorCount: 0`, `pageErrorCount: 0`,
`serverErrorCount: 0` — zero console errors, zero page errors, zero 5xx, with 68 API calls in the
journey run all 2xx — and the three 2026-08-07 WORK-13 symptoms (1-of-10 exam acceptance, seven
refused submissions, two different questions across a refresh) did not reproduce even once.

**The material findings are therefore all documentation-side** — most notably a document that
*under-reports its own system's completed work* (LB-01: `HINT_SOLUTION_REVIEW.md` still lists two
steps as un-run and a threshold as "never measured" nine days after both were measured), and a
superseded metric still being quoted as current (LB-02: "recall 1 of 8", replaced by D-371's 2/8
restated as 2 of 6 reachable).

| Lane | Executed | Result |
|---|---|---|
| pytest, whole suite (local, HEAD `344f016`) | `collected 1738 items` | `1735 passed, 2 skipped, 1 xfailed in 500.43s`, EXIT=0 |
| Playwright, local target | `Running 129 tests using 1 worker` | `127 passed (6.5m)` / `2 skipped`, EXIT=0, 0 did-not-run |
| Playwright, staging (`journey-student.spec.ts`) | 2 tests, one process, `workers: 1`, `retries: 0` | `2 passed (28.5s)`, EXIT=0, `{expected: 2, skipped: 0, unexpected: 0, flaky: 0}` |
| Guest RAG turn, staging chat | `POST /chat/sessions` → 200; 1 message → 200 | `scope="in_scope"`, 1 citation, `access_hint = null`, **10.55 s — pre-D-423, build `gha-44a12dfc9549`** *(both labels added 2026-08-20, step 7d; see LB-08)* |
| Free source arms (REQ-46 rule history, WORK-29 doc-vs-decision) | git history + source re-read | rule frozen since 2026-08-04; two doc-side drifts found |

Claim-level outcome: **LIVE_CONFIRMED 3** (TEST-28, WORK-05, WORK-13) · **LIVE_PARTIALLY_CONFIRMED 2**
(REQ-46, TEST-21) · **LIVE_BEHAVIOR_DIFFERS 1** (WORK-29, and the divergence is documentation-side —
the system is *ahead* of its own doc) · blocked or unverified at claim level: **0**.

---

## 2. Findings

### LB-01 — `HINT_SOLUTION_REVIEW.md` under-reports its own completed work

- **Category:** documentation drift (stale-incompletion variant — the inverse of a stale completion
  claim: the doc claims *less* done than is done)
- **Severity:** **MEDIUM** (per the adjudication)
- **Related claims / decisions:** WORK-29 (`LIVE_BEHAVIOR_DIFFERS`); D-251 (the plan), D-252, D-254,
  D-262, D-249, D-240; extends Phase 3A's WORK-28 finding.

**What was found.** `docs/HINT_SOLUTION_REVIEW.md` §8 still leaves steps 4 and 7 unticked
(`:527`, `:530`, verbatim):

> 4. Validation run: checks 1 and 2, hard-capped. **First paid step.**
> 7. Measure `_HINT_QUALITY_REJECT_BELOW` (`< 2`) — the unmeasured live rejection.

and three separate lines still assert the threshold is unmeasured — `HINT_SOLUTION_REVIEW.md:27`:

> The `< 2` **rejection** (`_HINT_QUALITY_REJECT_BELOW`) is still live and **has never been measured**

`HINT_SOLUTION_REVIEW.md:452`:

> | `_HINT_QUALITY_REJECT_BELOW = 2` | `ai_pipeline.py:1769` | **live rejection** | **no** |

`HINT_SOLUTION_REVIEW.md:463-464`:

> - `_HINT_QUALITY_REJECT_BELOW` **stays until measured.** D-249 measured `<= 3`; it never
>   measured `< 2`.

Both steps were in fact completed on **2026-08-10**, nine days before the claim's own date.
Step 4 ran — `docs/DECISIONS.md:18463-18478`, verbatim:

> ## D-254 — the hint & solution instrument survived its falsification run, and found real defects doing it (accepted, 2026-08-10)
> D-251 step 4, the first paid step. Pre-registration written before the script existed
> (`scratchpad/d254_preregistration.md`): four predictions, four disqualifying thresholds, and one
> outcome pre-committed as *bad* news. `scripts/measure_hint_solution_review.py`, **29.1¢**, 82
> calls, Haiku 4.5 against the shipped authored bank.

with all four pre-registered metrics surviving (M1 verdict split **1 of 8**, disqualifying at ≥ 3;
M2 blocking rate **10%**, disqualifying at ≥ 30%; M2r reject rate **2%**, disqualifying at ≥ 10%;
M3 out-of-range defect index **0**). Step 7 was measured and needed no paid run —
`docs/DECISIONS.md:18376` and `:18403-18405`, verbatim:

> ## D-252 — the reject floor was already measured, in data we had already paid for (accepted, 2026-08-10)
> **The floor has never fired.** 102 in-scale readings on generated candidates, plus D-249's 24 on
> the approved bank (`d249_dump.json`, distribution `{2: 4, 3: 7, 4: 9, 5: 4}`) — **126 readings,
> minimum observed 2, zero below it.** The floor sits below the distribution's observed support.

The same conclusion is carried in code on today's HEAD,
`packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py:821-827`:

> `_HINT_QUALITY_REJECT_BELOW` **rejects** the candidate (see the gate below). **D-252
> measured it and it has never fired**: 102 in-scale judge readings on real generated
> candidates (`question_validation_runs.stage_results->'judge'`, 2026-08-06 -> 08-10) plus
> D-249's 24 readings on the approved bank - 126 readings, **minimum observed 2, zero below
> it**.

Two adjacent drifts sit in the same neighbourhood. First, `:452`'s line cite is stale: the constant
is at `ai_pipeline.py:834` (`_HINT_QUALITY_REJECT_BELOW = 2`) and its only gate at
`ai_pipeline.py:2005` (`if judge.hint_quality_score < _HINT_QUALITY_REJECT_BELOW:`), verified on
HEAD. Second, two module docstrings say "**Nothing calls this yet**"
(`hint_solution_repair.py:3`; `review_panel.py:3-6`) when `review_loop.py` exists and D-262 piloted
it — `run_review_loop`'s only non-test caller is `scripts/repair_authored_solutions.py:211`, a
script rather than a pipeline caller.

**What still holds.** Steps 5 and 6 are genuinely open: neither `ai_pipeline.py` nor
`pipeline_cli.py` calls the review loop, so "wired to nothing" is correct about the *pipeline*
(and only wrong about the *tree*, where the offline script drives it). §9's four out-of-scope items
(`:536-541`) are unchanged.

**Why it matters.** This is the most consequential finding of the phase precisely because it points
the wrong way. A doc that overstates completion invites false confidence; a doc that *understates*
it invites re-buying evidence already paid for. D-252's whole point was that carry-over #18's
"paid measurement" was answerable from data already on disk — and the doc as written invites
someone to spend ~29¢ and a session re-running D-254, or to treat a measured floor as an open risk
in a launch review.

**What a migration must address** (stated as a list of required doc changes, *not* as action taken
here):

1. Tick §8 step 4, citing D-254 (`DECISIONS.md:18463-18478`).
2. Tick §8 step 7, citing D-252 (`DECISIONS.md:18376-18411`).
3. Retract the three "never measured" / "stays until measured" statements at `:27`, `:452`, `:463`,
   each with a pointer to D-252.
4. Fix `:452`'s line cite from `ai_pipeline.py:1769` to the constant at `:834` and the gate at
   `:2005`.
5. Refresh the two "Nothing calls this yet" docstrings (`hint_solution_repair.py:3`,
   `review_panel.py:3-6`) to name `scripts/repair_authored_solutions.py:211` and D-262, while
   preserving the accurate statement that no *pipeline* caller exists.

**Not fixed — recorded.**

---

### LB-02 — the "recall 1 of 8" access-hint figure is superseded

- **Category:** documentation drift
- **Severity:** **MEDIUM** (per the adjudication)
- **Related claims / decisions:** REQ-46 (`LIVE_PARTIALLY_CONFIRMED`); D-351, D-359, **D-371**;
  weakens Phase-2 REQ-46 *as written*.

**What was found.** The ledger's Phase-2 REQ-46 re-quotes the older figure from its own source,
`docs/DECISIONS.md:25129-25130`, verbatim:

> | **Recall** | **1 of 8** questions a role-gated document answers produced a hint |
> | **Precision** | **0 of 5** public questions produced a false one |

D-371 (2026-08-16) already replaced it — `docs/DECISIONS.md:25966-25972`, verbatim:

> Live re-measure today: **recall 2/8, precision 5/5 (zero false hints)** — up from the 0–1 of 8
> D-359 recorded, with no rule change, because that figure was partly the `KeyError` D-359 repaired.
>
> **The denominator was never 8.** The probe's precondition is a no-source refusal, so a question
> that gets *answered* never reaches it. Today: 2 answered, 4 refused-without-hint, 2 hinted. The
> probe fired on **2 of the 6 it could reach**. Every future report of this number should say which
> denominator it means.

A second, smaller drift sits in the same pair: the two sources state **precision at opposite
polarity** — "**0 of 5** public questions produced a false one" against "**precision 5/5**". Same
fact, counted in opposite directions, so a reader comparing the two numbers sees `0` against `5`.

The live arm bears on one cell of this, not the rate: one guest turn on the deployed build
returned `access_hint = null` with 1 citation on a public question — no false hint, reproducing one
cell of D-371's `precision 5/5` four days later. The recall *rate* was not re-measured (see §5).

**Why it matters.** REQ-46 is a **precision-over-recall** claim (memory / D-221: score both
directions and treat the negative controls as first-class). Quoting a stale recall numerator with an
unnamed denominator understates the shipped behaviour by half and, worse, obscures D-371's actual
methodological correction — that the denominator was never 8 because answered questions never reach
the probe's precondition. Any restatement must name its denominator.

**Not fixed — recorded.**

---

### LB-03 — D-371's "shipped ceiling of 0.40" names no constant that exists

- **Category:** documentation drift
- **Severity:** **LOW-MEDIUM** (per the adjudication)
- **Related claims / decisions:** REQ-46; D-165, D-166, **D-168**, D-177, D-371.

**What was found.** `docs/DECISIONS.md:25953`, verbatim:

> against corpus-derived gated cases at mean **0.432** and a shipped ceiling of **0.40**. Only one

No constant equals 0.40. Read from source,
`packages/shared/src/intellichoice_shared/access_probe_policy.py:37-40`:

> \# **Since D-168 this is the *fallback* ceiling, not the live rule.** It is what a
> \# distance-only probe uses: the lexical/`MockBedrockProvider` path, and the degraded path
> \# when the reranker is unavailable. The live rule is the three constants below.
> `ACCESS_PROBE_MAX_DISTANCE = 0.45`

0.40 was D-165's value; 0.45 has been the *fallback* since D-166; and since D-168 the live rule is
not a single ceiling at all but three constants —
`ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60` (`:103`), `ACCESS_PROBE_RERANK_MIN_SCORE = 0.9`
(`:104`), `ACCESS_PROBE_TIER_MARGIN = 0.10` (`:105`).

**Why it matters.** The *argument* D-371 makes with the number is unaffected — gated and public
cases interleave on the distance axis, so the distance signal does not carry the distinction. Only
the label is wrong. But the label is the part a future reader would act on: someone tuning "the
shipped ceiling" would edit the fallback used by the degraded and mock paths, not the live reranked
rule, and the change would not appear in production behaviour at all.

**Corroborating free arm (not a drift).** The same lane confirmed REQ-46's "the threshold was
deliberately not tuned" from history: `access_probe_policy.py` has four commits, none after
2026-08-04, and the last constant change of any kind is `e1ab0ad` (D-177), which moved
`ACCESS_PROBE_RERANK_MIN_SCORE` from `0.8` to `0.9`. `3b01837` (D-179) touched the file but changed
no constant. `git diff --stat 44a12dfc9549..HEAD` over that file is empty, so the deployed build
carries the identical rule that D-371 measured. No B4 or C8 commit changed a hint-path line.

**Not fixed — recorded.**

---

### LB-04 — `PROGRESS.md` still carries the WORK-13 isolation defect as open

- **Category:** stale completion claim
- **Severity:** **LOW-MEDIUM** (per the adjudication)
- **Related claims / decisions:** WORK-13 (`LIVE_CONFIRMED`, claim scope); D-213, D-355, D-365 §2,
  D-367; `DEPLOYED_INFRA_DRIFT_REGISTER.md:381`.

**What was found.** `docs/PROGRESS.md:16659-16690` still presents the defect as current
carry-over — `:16659` and `:16673-16677`, verbatim:

> ## Carry-over — `journey-student.spec.ts` is not isolated against staging (2026-08-07)
>
> The symptoms are consistent with each test starting on a session a previous test left behind:
> `answerWholeExam` returned **1 of 10**, and the refresh test compared two entirely different
> questions.

and `:16689-16690`:

> **Fix when picked up:** give each test its own fixture student, or have the suite clear the
> student's sessions in `beforeEach`. Both are test-side; nothing in the application needs to change.

The live staging run reproduced **none** of the three symptoms. `make e2e-staging
E2E_ARGS="tests/learning/journey-student.spec.ts"` with `EXPECT_BUILD_SHA=44a12dfc9549`, exit 0:

> Running 2 tests using 1 worker
>
>   ✓  1 [chromium] › tests/learning/journey-student.spec.ts:45:1 › student walks sign-in → pre-exam → finalize → study (the ladder included) (16.5s)
>   ✓  2 [chromium] › tests/learning/journey-student.spec.ts:421:1 › a refresh mid-exam restores the exact position (SPEC Phase 11) (5.5s)
>
>   2 passed (28.5s)

Symptom by symptom, from `e2e/artifacts/journeys.jsonl`: `pre-exam: answered 10 items` → **10/10**
(was 1 of 10); `refused=0` on every one of the 12 study iterations, with `POST …/answers` ×15 all
`{200}` and `failedRequests: []` (was 7 refusals); and the refresh comparison passed on the `h1`
stem — `before refresh: Pre-exam Question 3 of 10 19:58` / `after refresh: Pre-exam Question 3 of 10
19:56`, the same item and ordinal with only the countdown differing (was two entirely different
questions). Both tests ran **in one file, in one process, `workers: 1`, `retries: 0`, first try** —
which is precisely the "in combination" condition the carry-over says fails.

Of the two fixes the carry-over proposes, only the first was applied (per-test fixture students,
D-365 §2 / D-367) and it is behaviourally sufficient; the second (`beforeEach` session clearing),
which Phase 3A confirmed is absent, is **not needed**.

**Why it matters.** A stale open-defect note in PROGRESS is read as live risk against the only path
that exercises real CloudFront → ALB → ECS with real Bedrock. Left as written, it argues for
re-doing a fix that already landed and casts doubt on a gate that currently passes.

**Recorded limitation, not a block.** The register's broader wording,
`DEPLOYED_INFRA_DRIFT_REGISTER.md:381` — "when the learning e2e walks run in **combination** against
staging" — was deliberately scoped to this one spec. The original failure was a whole-run artifact
(the walk then shared `studentPresent` with seventeen other specs), and the cross-spec contention
case was not re-run. See §5(a).

**Not fixed — recorded.**

---

### LB-05 — the deployed build is 10 commits behind local HEAD

- **Category:** environment-only (with a repo-tests-vs-deployed note)
- **Severity:** **not assigned** — the adjudication records this as an *environment note, not a
  defect*.
- **Related claims / decisions:** frames WORK-13, REQ-46, TEST-28, WORK-05; D-415, D-420, D-421,
  D-422, D-423.

**What was found.** Both ECS services run the same app image tag, `gha-44a12dfc9549`
(learning task definition `:150`, 2/2 running; chat `:148`, 1/1 running). That tag resolves in this
checkout to:

> `44a12dfc95499fc40fc875681907951f5958ce5a 2026-08-18 13:27:15 -0500 W21: W19 checked against the sibling app, and the wait with no exit (D-415) (#336)`

**The deployed build is 10 commits behind local HEAD `344f016`** — `f7c9d10`, `a6da941`, `f6f84a2`,
`899547f`, `2e301d6`, `e583cb9`, `b41efc7`, `5b324a0`, `6f107c1`, `344f016` are all undeployed.
Notably the whole **B4 escalation series** (D-420 / D-421 / D-422) and **C8** (`f6f84a2`, ruff
format) are not on staging, and neither is D-423's `scope_guard`/retrieval-overlap work (`6f107c1`).

**Repo-tests-vs-deployed note.** The instrument was checked against the build before it was trusted:
`git diff --stat 44a12dfc9549..HEAD -- e2e/` shows the only e2e change is
`e2e/tests/chat/response-shapes.spec.ts`, so **`e2e/tests/learning/journey-student.spec.ts` is
byte-identical between the deployed build and HEAD**. That is what makes the WORK-13 run a
legitimate instrument for this build rather than a newer spec run against older code.

**Why it matters.** This frames every "the docs describe HEAD, staging runs an older build"
comparison in the phase, in both directions. It is why LB-08's 10.55 s latency is a *pre*-D-423
number (the ~22% improvement is not in it), why the B4 escalation behaviour could not have been
observed live at all, and why any future live probe must state its build SHA before its numbers.

**Not fixed — recorded.**

---

### LB-06 — no email or calendar provider lever exists on either deployed task definition

- **Category:** environment-only (positive safety posture)
- **Severity:** **not assigned** — the adjudication records this as a positive finding *worth
  recording*.
- **Related claims / decisions:** the phase's own safety gate; D-002, D-097, SPEC §5.1.4, §5.24;
  closes `targets_3b2.md` §0.5 item 9 and a `DEPLOYED_INFRA_STATE_EVIDENCE.md` gap.

**What was found.** Full environment-variable *name* lists were enumerated from both active task
definitions (21 names on learning `:150`, 24 on chat `:148`; secret **names** only, 7 per app, no
value fetched, printed, or exported). **There is no email-provider or calendar-provider environment
variable of any kind on either task definition** — no name matching `EMAIL`, `GMAIL`, `SES`, `MAPS`,
or any `*_PROVIDER_*` transport selector. The only `*PROVIDER*` name on each app is
`{LEARNING,CHAT}_BEDROCK_PROVIDER`.

The transports are the dev fakes **by construction, not by env**, on the code that is deployed:
`apps/learning-api/src/learning_api/main.py:111` → `email_transport = FakeEmailTransport()` with no
env branch, and `apps/chat-api/src/chat_api/main.py:85-87` → `FakeEmailTransport()`,
`FakeCalendarTransport()`, `FakeMapsProvider()`, all unconditional. A tree-wide grep
(`grep -rn "EmailTransport" --include="*.py" apps packages | grep -v tests`) returns exactly those
two construction sites and no env-selected alternative anywhere.

**It also closes an open question.** Staging `BEDROCK_PROVIDER` is **`bedrock`** on both apps
(`LEARNING_BEDROCK_PROVIDER bedrock`, `CHAT_BEDROCK_PROVIDER bedrock`), overriding the committed
tfvars default `"mock"`. That resolves `targets_3b2.md` §0.5 item 9 and the
`DEPLOYED_INFRA_STATE_EVIDENCE.md` gap ("no `BEDROCK_PROVIDER` line anywhere"). Both apps also carry
`*_DEV_TOKEN_ENDPOINT_ENABLED=false`, confirming staging `/dev/token` is the D-097 shared-secret
path and the locally-open unauthenticated path is off.

**Why it matters, in both directions.** The *absence* of a provider variable is the confirming
evidence, not a gap: there is no lever by which a real transport could have been selected on this
deployment, which is what made the paid staging arms safe to run without approaching an
`interrupt()`. And because Bedrock is genuinely real, every staging number in this phase is a paid
measurement that means what it claims. What this does **not** prove: anything about production /
`go.intellichoice.org`, nor that a *future* task definition keeps the property — the safety argument
is re-derivable, not permanent.

**Not fixed — recorded** (nothing to fix; recorded so the argument can be re-derived).

---

### LB-07 — the quoted "1735 / 2" is structurally silent about two things

- **Category:** documentation drift, with a repo-tests-vs-deployed coverage note
- **Severity:** **LOW** (per the adjudication)
- **Related claims / decisions:** TEST-28 (`LIVE_CONFIRMED`), WORK-05, TEST-21; D-206, D-238.

**What was found.** `docs/PROGRESS.md:35-38` records, verbatim:

> **Verification on merged `main` (`6f107c1`):** `ruff` clean · `ruff format --check` clean · `pyright`
> 0 errors · pytest **1735 passed / 2 skipped** · Playwright **127 passed / 2 skipped** · chat-web **49**
> unit tests, learning-web **26** · both builds clean.

The whole suite at HEAD `344f016` reproduced both totals *exactly*:

> `============ 1735 passed, 2 skipped, 1 xfailed in 500.43s (0:08:20) ============`

Two silences, neither of them a contradiction.

**(a) The third bucket.** Collection was `collected 1738 items`, and 1735 + 2 + 1 xfailed = 1738 —
so the documented pair does not sum to the suite's own collection count. The missing item is
`test_identical_inputs_reproduce_identical_routing_and_scores`
(`apps/learning-api/tests/test_learning_flow.py:1247`), marked `@pytest.mark.xfail(..., strict=False)`
per D-206/D-238, whose own comment records that it "XPASSed once in a full run and xfailed on the
next, from the same tree, with no code between them". The bucket is **nondeterministic by design**:
another run of the same tree can legitimately print `1 xpassed`. That is a reason the two-number pair
is *more* stable than a three-number one, so if the line is ever made to sum it must say so.

**(b) Real-Bedrock eval coverage.** The only two skips are both paid opt-ins, named verbatim:

> `SKIPPED [1] apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py:128: set CHAT_EVAL_REAL_BEDROCK=1 (costs money)`
> `SKIPPED [1] packages/evals/tests/test_llm_judge.py:85: set EVAL_REAL_BEDROCK=1 (costs money)`

They skip on any machine that has not deliberately opted into spend, which is what makes "2 skipped"
reproducible rather than incidental — and which also means **the free local suite is structurally
silent about real-Bedrock eval quality**.

**Why it matters.** Whenever "1735 passed" is cited as coverage, the citation carries an unstated
exclusion: the two tests that would exercise the real model are the two that did not run. This is
the same shape as the D-383 lesson recorded in `AUDIT_LIVE_2026_08_17.md` — a green count is not
evidence about the paths it did not assert.

**The counterweight, in the claims' favour.** `e2e/tests/` contains ~14 conditional
`test.skip(!reached, …)` non-vacuity guards (in `video-intervention`, `pii-typed-into-tutor-chat`,
`hint-displacement`, `journey-student`, `journey-terminal`, `exam-expiry`, `exam-position-refresh`,
`narrative-race`, `assistance-panel-probe`, `dashboard-chart-labels`, `attendance-email-approved`,
`escalation-approved`, `response-shapes`). Any one firing would have pushed the skip count above 2.
**None fired** — so the local 127 is the *non-vacuous* 127, and the two skips are the *predicted*
two (`deployed-authorization.spec.ts:188` and `:218`, both guarded
`test.skip(TARGET !== "staging", STAGING_ONLY)`). All five D-383 blind-spot specs
(`journey-terminal`, `attendance-email-approved`, `escalation-approved`,
`stream-disconnect-visible`, `exam-expiry`) ran and passed non-vacuously.

**Not fixed — recorded.**

---

### LB-08 — three independent corroborations of existing measurements

- **Category:** not a drift — corroboration of documented behaviour
- **Severity:** **not assigned** (the adjudication records these as corroborations)
- **Related claims / decisions:** REQ-46, WORK-13; D-325, D-355, **D-423**.

**What was found.**

1. **Latency corroborates D-423.** The guest QA turn measured **10.55 s** (session creation 0.25 s)
   **— pre-D-423, on staging build `gha-44a12dfc9549` (build SHA label added 2026-08-20, step 7d:
   this number must never be quoted without both facts)** —
   against D-423's recorded `10.62 s` and "~10.6s p95 accepted for launch"
   (`docs/DECISIONS.md:28716`, `:28729-28730`; k6 `http_req_duration` p95 13.1 s). Because
   `6f107c1` is undeployed (LB-05), this number is from a build that **predates** D-423's
   `scope_guard`/retrieval overlap — so the ~22% improvement is *not* in it, and the match is with
   the pre-optimisation baseline.
2. **D-355 reconciliation drift is zero.** `expect(studyAnswers - studyVerdicts.length)
   .toBeLessThanOrEqual(1)` measured **5 − 5 = 0** (`study: answered 5 items`; `5 graded`). The
   2026-08-14 failing run recorded 11 submitted / 1 graded.
3. **D-325's no-re-served-stem rule holds.** `stems seen: 10 pre_exam, 5 study, 0 repeated` —
   **zero repeats** across 15 stems.

Also decided in the same process, none skipped: `expect(studyAnswers).toBeGreaterThan(0)` → 5;
`expect(ladderOffered).toBeGreaterThan(0)` → 4; `expect(interventions).toBeGreaterThan(0)` → 4;
4 of 5 study answers wrong, so the wrong-answer and ladder paths were genuinely reached.

**Why it matters.** These are the cheapest kind of audit result: three documented behaviours
independently re-observed on the deployed build, one of them (the latency) usefully anchored to the
*older* build so that D-423's improvement claim retains an untouched before-measurement.

**Not fixed — nothing to fix; recorded.**

---

### LB-09 — no new behavioral defect was discovered

- **Category:** behavioral defect — **none found** (the null result, stated as a finding)
- **Severity:** **not assigned** (a null result)
- **Related claims / decisions:** all six 3B-2 claims; `AUDIT_LIVE_2026_08_17.md` (D-381/D-383).

**What was found.** Across every live walk in this phase: **0 console errors, 0 pageerrors, 0 5xx
anywhere.** The staging journey capture teardown reported, for both tests, `consoleErrorCount: 0`,
`pageErrorCount: 0`, `serverErrorCount: 0`, `clientErrors: []`, `pageErrors: []`,
`failedRequests: []`, with 50 API calls in test 1 and 18 in test 2 and **zero non-2xx across all
68** — and no `audit.allow({…})` narrowing was needed to get there. The guest RAG turn returned 200
on both calls with a 1133-character grounded answer, 1 citation, `scope="in_scope"`,
`intent="document_qa"`, `access_hint=null`, `escalation_recommended=false`. Neither suite locally
hit a port conflict, a DB-down condition, or a missing-migration error; both collected non-zero and
exited 0 on the first attempt, with zero failures and zero errors.

**Why it matters, and its limit.** This is the phase's primary result and the reason every finding
above is a *sharpening* rather than a breakage. It is also exactly the result that
`AUDIT_LIVE_2026_08_17.md` warns not to over-read: on 2026-08-17 a green Playwright suite coexisted
with two live P1s. A green run still does not prove the absence of a class of defect nobody
asserted. What is *newly* true here is that the five specs D-383 added to close those blind spots
all ran and passed non-vacuously — the coverage lesson holds, and the coverage that made the gap
non-repeatable is executing.

**Nothing to fix — recorded.**

---

## 3. Category cross-index

| Category (phase brief) | Findings |
|---|---|
| **behavioral defect** | **none** — LB-09 is the explicit null result |
| **documentation drift** | LB-01, LB-02, LB-03 (LB-07 carries a drift half: the pair does not sum) |
| **stale completion claim** | LB-04; **LB-01 as its inverse** (the doc claims *less* complete than the system is) |
| **environment-only** | LB-05, LB-06 |
| **repo-tests-vs-deployed mismatch** | LB-05's byte-identical-spec note (the instrument was validated against the older deployed build); LB-07's real-Bedrock coverage silence |
| *(corroboration — not one of the five)* | LB-08 |

---

## 4. Earlier-phase claims weakened or refuted by 3B-2

| Earlier claim | What 3B-2 did to it | Finding |
|---|---|---|
| **REQ-46 as written** (Phase 2 / ledger: "recall 1 of 8") | **Weakened.** Superseded by D-371's "recall 2/8 … the probe fired on 2 of the 6 it could reach"; the two sources also state precision at opposite polarity. The *rule*-half of REQ-46 ("deliberately not tuned") is confirmed from history. | LB-02 |
| **WORK-29's "steps 4 and 7 not run"** | **Refuted.** Both steps were completed 2026-08-10 (D-254, D-252) and corroborated in code on HEAD. The claim classifies `LIVE_BEHAVIOR_DIFFERS`, but the divergence is documentation-side: the system is ahead of its doc. | LB-01 |
| **`PROGRESS.md`'s WORK-13-still-open framing** | **Refuted at claim scope.** The staging run reproduced none of the three 2026-08-07 symptoms, in the same process, first try. The second proposed fix is unnecessary. | LB-04 |
| **The extraction's "2 commits ahead of the snapshot"** | **Corrected (minor).** `6f107c1` **is** #345, so only #346 is after the snapshot: HEAD is **1 commit** ahead, and that commit is docs-only — so no Python or TypeScript sits between WORK-05's snapshot and this measurement. | recorded here; strengthens WORK-05's `aged-by-SHA` confirmation |

One earlier-phase item was neither weakened nor confirmed: **TEST-21's historical half** (a
`88 passed / 7 skipped` green run on build `gha-6841d9d9b169` coexisting with two live P1s) is
**unobservable by construction** — that build and that run are gone. No probe was manufactured for
it; it is recorded as context, and it remains the more valuable half of TEST-21.

---

## 5. Residuals — explicitly not blocks

Three items remain unmeasured. **None blocks the migration phase**, and none is a blocked *claim*:
each of the six claims reached a classification.

- **(a) The whole-directory staging e2e contention re-run.** `E2E_ARGS="tests/learning"` (~37 tests
  including four band walks) was deliberately not run — out of budget scope, **not** blocked by
  safety (the safety gate in LB-06 cleared it). So `DEPLOYED_INFRA_DRIFT_REGISTER.md:381`'s broader
  wording ("when the learning e2e walks run in combination") stays open at register level: today's
  run reproduces the two-test combination, not the seventeen-spec cross-spec contention that
  produced the original failure. **Paid, optional.**
- **(b) Access-hint recall-rate re-measurement.** The instrument exists and was confirmed:
  `scripts/measure_access_hint_live.py` (8 `GATED` + 5 `PUBLIC` questions, guest path,
  `BASE = "https://d222glidpp4azv.cloudfront.net"`, `CONFIRM_PAID_RUN=1` guard). A 13-turn paid
  re-measurement re-derives nothing statistically at n=8 / n=6 — this was an **orchestrator ruling,
  not a blockage**. The rate claim stands as documented (and superseded, per LB-02), with the free
  conclusion on record so the claim is not left blank. Re-measure via the existing script **when the
  user chooses to spend**.
- **(c) Real-Bedrock eval opt-ins.** `CHAT_EVAL_REAL_BEDROCK=1` and `EVAL_REAL_BEDROCK=1` were not
  set, so the two paid eval tests remain the suite's only skips (LB-07b). Intended, reproducible,
  and worth restating whenever the suite total is cited as coverage.

One lane-scope non-block, recorded for completeness: the D-252-style histogram re-derivation over
`question_validation_runs.stage_results->'judge'` needs the dev Postgres, which the staging lane was
forbidden to touch — **BLOCKED_BY_LANE, not by environment**. It was not needed: D-254 and D-252
decide both of WORK-29's questions from documents and source, and re-buying D-254 at ~29¢ would
replace the record rather than check it.
