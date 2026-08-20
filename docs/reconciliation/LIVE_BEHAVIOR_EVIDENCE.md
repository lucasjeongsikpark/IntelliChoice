> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase 3B-2 live-probe evidence — every probe command and its verbatim output from the 2026-08-20T03:30Z–05:00Z window against staging. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# LIVE_BEHAVIOR_EVIDENCE.md — Phase 3B-2 live behavioral verification

**Probe window:** 2026-08-20T03:30Z – 05:00Z.

**Entry points.** Only the two CloudFront distributions were addressed — learning
`https://d35dfnjzmgrm01.cloudfront.net`, chat `https://d222glidpp4azv.cloudfront.net` — reached
through the repository's own `make e2e-staging` tooling and plain HTTPS. **The ALB was never
probed directly**, so every observation below is of the same path a real client takes. Local-lane
probes ran against the dev stack (`localhost:8001/8002/5173/5174`, dev Postgres + MySQL) and the
repository at HEAD `344f0161eb6bbd927ba1f0f37fa52ce937c112ca`.

**Identities.** Synthetic fixtures only: `studentJourney` = `student-ext-10` and `studentResume` =
`student-ext-9` (`e2e/config.ts:128-189`), plus **one anonymous guest** chat session (no token; the
guest path is `localStorage["intellichoice.chat_guest"]="1"`, SPEC §18-C3). No real user, no PII
typed, no branch-manager or parent identity minted, and no student's weekly attendance gate consumed.

**Safety posture, verified rather than assumed.** The deployed task definitions
(`intellichoice-staging-learning-api:150`, `intellichoice-staging-chat-api:148`, both
`gha-44a12dfc9549`) carry **no email-provider and no calendar-provider environment variable of any
kind** — 21 env names enumerated on learning, 24 on chat, the only `*PROVIDER*` names being
`{LEARNING,CHAT}_BEDROCK_PROVIDER`. There is therefore **no lever by which a real transport could be
selected**: the fakes are unconditional in code (`apps/learning-api/src/learning_api/main.py:111`,
`apps/chat-api/src/chat_api/main.py:85-87`). Bedrock, by contrast, is **real** on both apps
(`LEARNING_BEDROCK_PROVIDER=bedrock`, `CHAT_BEDROCK_PROVIDER=bedrock` — the committed tfvars default
`"mock"` is overridden live), so staging arms genuinely spend. Spend was capped at **2 staging
learning walks + 1 guest RAG turn**, session-budget-capped and far below the `bedrock_spend_spike`
alarm window (200¢ / 3600 s). Zero AWS mutation, zero `get-secret-value` by hand, zero secret value
printed or written, zero repository modification (`git status --porcelain` before and after shows
only `?? docs/reconciliation/`), and `make fmt` was never run.

**Discipline notes.** Two rules governed what counts as evidence here. First, **a green e2e run
counts only where its assertions cover the claim** — assertion coverage was read per spec, in source,
before any run was treated as decisive (this is what makes `journey-student.spec.ts` a real
instrument for WORK-13 and what makes a bare count insufficient for TEST-21). Second, **non-vacuity
guards were checked**: `e2e/tests/` carries ~14 conditional `test.skip(!reached, …)` guards, any one
of which firing would have lifted the skip count above the documented 2; none fired locally, and the
staging run reported `skipped: 0`. Where a probe was declined, the file states whether that was a
blockage or an orchestrator ruling — the two are not the same and are not recorded the same way.

**Companion document.** The findings narrative — what each divergence means, its severity, and the
doc-side must-fix list — lives in `LIVE_BEHAVIOR_FINDINGS.md` as **LB-01 … LB-09**. This file carries
evidence and cross-references only; it makes no recommendations.

---

## 1. Per-claim records

### REQ-46

- **Claim ID**: REQ-46
- **Intended behavior**: against staging the access hint fired for **1 of 8** questions a role-gated document answers (recall) and **0 of 5** public questions produced a false hint (precision); the probe is biased toward silence, the feature "mostly is not doing the job SPEC gives it", and the threshold was **explicitly not tuned** — moving recall requires a separate measured offline rule sweep bounded by AUD-C-20 (`docs/DECISIONS.md:25124-25137`).
- **Prior evidence**: 3A — **not inspected**, deferral table only (`REPOSITORY_STATE_EVIDENCE.md:2222`); 3A.5 — nothing, `scripts/measure_*` named as paid and not invoked (`LOCAL_EXECUTION_FINDINGS.md:783-785`); 3B-1 — `DEPLOYED_INFRA_STATE_EVIDENCE.md:585`, "no control-plane call measures retrieval quality", nothing owed by AWS.
- **Probe performed**: Arm 1 (free) — `ls` of both `scripts/measure_*` instruments; full `git log` / `git log -p` of `packages/shared/src/intellichoice_shared/access_probe_policy.py`; `git log -p` over the four wider hint-path files since 2026-08-16 filtered to `ACCESS_PROBE|probe_access|access_hint|"log in as"`; `git diff --stat 44a12dfc9549..HEAD` on the policy file. Arm 2 (paid) — **one** guest turn: `POST /chat/sessions` then `POST /chat/sessions/<id>/messages`, mirroring `measure_access_hint_live.py:ask()`, question taken from the script's own `PUBLIC` list (`public/about`, "What is IntelliChoice?"), `escalate` never set. **The 13-turn paid re-measurement was NOT run — orchestrator ruling, not a blockage**: it re-derives nothing statistically at n=8/n=6 and spends real money, so the rate claim stands as-documented (and superseded).
- **Environment/endpoint**: chat CloudFront `https://d222glidpp4azv.cloudfront.net` (deployed build `gha-44a12dfc9549`) for the live turn; repository + git history at HEAD `344f016` for Arm 1.
- **Fixture/test identity**: **anonymous guest** — no token minted and none needed. Arm 1: n/a.
- **Observed behavior**: the rule is frozen — `access_probe_policy.py` has four commits, none after 2026-08-04, and the last constant change of any kind is `e1ab0ad` (D-177, 2026-08-04 19:09:49 -0500) `ACCESS_PROBE_RERANK_MIN_SCORE = 0.8` → `0.9`; `3b01837` (D-179) touched the file but changed no constant; the three post-D-371 hint-path commits (`b41efc7`, `e583cb9` = B4, `f6f84a2` = C8 ruff-format) match **nothing** under the filter; `git diff --stat 44a12dfc9549..HEAD` on the file is **empty**, so the deployed build carries the identical rule. Live constants: `ACCESS_PROBE_MAX_DISTANCE = 0.45` (documented fallback since D-168, not the live rule), `ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60`, `ACCESS_PROBE_RERANK_MIN_SCORE = 0.9`, `ACCESS_PROBE_TIER_MARGIN = 0.10`, `ACCESS_PROBE_CANDIDATE_LIMIT = 10`. Guest turn: `POST /chat/sessions` → **200** (0.25 s), message → **200**, latency **10.55 s**, `scope = "in_scope"`, `intent = "document_qa"`, **`access_hint = null`**, `escalation_recommended = false`, **1 citation**, answer length **1133** characters and grounded/org-specific. `scripts/measure_access_hint_live.py` exists (`BASE = "https://d222glidpp4azv.cloudfront.net"`, 8 gated + 5 public, `CONFIRM_PAID_RUN=1` guard), its docstring recording the D-351 baseline **recall 1/8, precision 5/5**.
- **Evidence**: `scratchpad/exec_staging_3b2.md` steps C.1–C.4 and D (command list, `git log -p` extract, response-key dump); `packages/shared/src/intellichoice_shared/access_probe_policy.py:37-40,103-109`; `docs/DECISIONS.md:25966-25972` (D-371's "recall 2/8, precision 5/5 … The denominator was never 8 … fired on 2 of the 6 it could reach") against `docs/DECISIONS.md:25129-25130` ("**1 of 8**" / "**0 of 5**"); `docs/DECISIONS.md:25953` (the "shipped ceiling of 0.40" wording); `apps/chat-api/src/chat_api/routers/sessions.py:130-136` (citation shape).
- **Timestamp**: Arm 1 2026-08-20T03:58:43Z; guest turn 2026-08-20T04:00:45Z → 04:00:56Z.
- **Limitations**: **one turn is not a rate.** Recall over the 8 gated questions and precision over all 5 public ones are undecided by a single public question; the recall **rate was not re-measured** and the claim's rate half rests on the documented figures. The turn also lands in `classify()`'s `ANSWERED` bucket, which by D-371's own argument never reaches the probe's precondition. Nothing here speaks to a build newer than `44a12dfc9549`.
- **Classification**: **LIVE_PARTIALLY_CONFIRMED**. Free arm confirmed ("threshold deliberately not tuned" holds live, on the identical deployed file); one precision cell of D-371 reproduced four days later; the rate half left as-documented and superseded. See LB-02, LB-03, LB-08.

### TEST-21

- **Claim ID**: TEST-21
- **Intended behavior**: the suite was green on build `gha-6841d9d9b169` (**88 passed / 7 skipped**) hours before the 2026-08-17 live audit found both P1s live in that same build; stated as a statement about **coverage**, not a suite failure, with the open list called "the more valuable half of this audit" (`docs/AUDIT_LIVE_2026_08_17.md:3-9,15-16`).
- **Prior evidence**: 3A — deferral table only (`REPOSITORY_STATE_EVIDENCE.md:2229`), "execute the suites and compare current counts"; 3A.5 — targeted pytest batches only (16 invocations, 562 unique tests, all green) and **zero Playwright**, the browser lane deferred by phase design (`LOCAL_EXECUTION_FINDINGS.md:770-780`); 3B-1 — `:586`, local execution not AWS, nothing owed. The past run is unfalsifiable by design and the ledger already dispositions it ("none for the past run").
- **Probe performed**: the single serialized local pass shared with TEST-28/WORK-05 — `uv run pytest -rs`, then (only after pytest exited) `cd e2e && npx playwright test` (= `make e2e`'s recipe, `Makefile:151-152`, `TARGET` defaulting to `local`). **No probe was manufactured for the historical 88/7**: it is unobservable by construction and the orchestrator ruled it recorded as context, not as a blocked item. Assertion coverage was then read for the five D-383 blind-spot specs and each was located in the run log.
- **Environment/endpoint**: local dev stack — dev Postgres (`alembic current` → `8509c0486d8d (head)`) + MySQL fake, both APIs and both vite servers started by Playwright's own `webServer`; no CloudFront, no AWS session, no secret.
- **Fixture/test identity**: n/a — the subject is the suite itself; the seeded fixture students are exercised by the specs, not selected by the probe.
- **Observed behavior**: pytest `============ 1735 passed, 2 skipped, 1 xfailed in 500.43s (0:08:20) ============`, `EXIT=0`, `collected 1738 items`. Playwright `Running 129 tests using 1 worker` → `2 skipped` / `127 passed (6.5m)`, `EXIT=0`, zero failures and zero "did not run". Measured **127 ≥ 88** and green with **fewer** skips (**2 < 7**). All five D-383 specs ran and passed: `journey-terminal.spec.ts`, `attendance-email-approved.spec.ts`, `escalation-approved.spec.ts`, `stream-disconnect-visible.spec.ts`, `exam-expiry.spec.ts` — and **none was skipped by a conditional non-vacuity guard**, so they passed **non-vacuously**. AUD-F-16's freshness gate passed on fresh servers (`learning-api booted=2026-08-20T04:06:35.101654+00:00 uptime=5.4s`, `chat-api booted=2026-08-20T04:06:37.206738+00:00 uptime=3.3s`).
- **Evidence**: `scratchpad/exec_local_3b2.md` steps 2, 3 and 5 (verbatim summary lines, skip listings, the ~14-guard enumeration); `docs/AUDIT_LIVE_2026_08_17.md:3-9,15-16`; `e2e/tests/security/deployed-authorization.spec.ts:36-38,188,191,218,219`; `e2e/artifacts/journeys.jsonl` (gitignored, truncated per run).
- **Timestamp**: pytest completed and Playwright began after it exited; Playwright server boot stamped 2026-08-20T04:06:35Z / 04:06:37Z.
- **Limitations**: **the historical half is unobservable by construction** — that build and that run are gone. And today's green run does not touch the 2026-08-17 lesson: a green suite still is not evidence of behavior nobody asserted, which remains the more valuable half of the claim. The counts describe HEAD `344f016`, not the deployed build.
- **Classification**: **LIVE_PARTIALLY_CONFIRMED**. The historical 88/7-era coexistence stays dispositioned as unobservable and recorded as context; the current half is live-confirmed, with all five blind-spot specs executing non-vacuously.

### TEST-28

- **Claim ID**: TEST-28
- **Intended behavior**: PROGRESS's current verification line states 0 typecheck errors, pytest **1735 passed / 2 skipped**, Playwright **127 passed / 2 skipped**, chat-web **49** unit tests, learning-web **26** — higher than the 88/7 recorded for the 2026-08-17 audit build (`docs/PROGRESS.md:35-38`). Candidate status was "CURRENT — doc-claimed, **not re-run**", confidence MEDIUM.
- **Prior evidence**: 3A — deferral table only (`:2230`), "**3A never ran a test**"; 3A.5 — converted `pyright` 0 errors, `ruff` clean, chat-web **49**, learning-web **26**, both builds clean, Alembic replay 37 migrations single head, but explicitly **not** the 1735/2 pytest total (562 unique tests in targeted batches) and **not** the 127/2 Playwright total (zero Playwright); 3B-1 — `:587`, same lane as TEST-21. Exactly two numbers were owed, both free.
- **Probe performed**: the shared serialized pass. `uv run pytest -rs` — `make test`'s recipe (`Makefile:117-118`) plus `-rs`, the one stated deviation: it adds the short-skip report only and changes nothing about selection or execution, and was needed because `pyproject.toml:52` sets no `-r` flag, so a bare `make test` prints the skips as bare `s` and the **skip identities** would have cost a second 8-minute run. Then `cd e2e && npx playwright test`, no flags, no `E2E_ARGS`, no target override. Pre-run hygiene checked, not assumed: `ps aux` showed no real `pytest` and no Playwright/vite process, ports 8001/8002/5173/5174 free, containers healthy.
- **Environment/endpoint**: local dev stack, as TEST-21. Static counting was ruled out in advance — 100 `test(` declarations cannot decide a 127, because two specs generate tests in loops and four tagged tests run on the `webkit`/`mobile` projects; and **127/2 is a *local* figure** whose skip set differs from a staging run's.
- **Fixture/test identity**: n/a.
- **Observed behavior**: **exact match on all four numbers.** pytest `1735 passed, 2 skipped, 1 xfailed in 500.43s`, collected **1738** (= 1735 + 2 + 1), `EXIT=0`, zero failures and zero errors. Skips named verbatim: `SKIPPED [1] apps/chat-api/tests/test_qa_coverage_eval_real_bedrock.py:128: set CHAT_EVAL_REAL_BEDROCK=1 (costs money)` and `SKIPPED [1] packages/evals/tests/test_llm_judge.py:85: set EVAL_REAL_BEDROCK=1 (costs money)` — both **paid-Bedrock opt-ins**. Playwright **127 passed / 2 skipped / 0 did-not-run**, and the 2 are the **predicted** two: `tests/security/deployed-authorization.spec.ts:188:3` (`/dev/token on the deployed stack refuses to mint without the shared secret`) and `:218:3` (`the CDN does not expose /metrics, /openapi.json or /docs`), both guarded `test.skip(TARGET !== "staging", STAGING_ONLY)`. The xfail is `test_identical_inputs_reproduce_identical_routing_and_scores` (`apps/learning-api/tests/test_learning_flow.py:1247`, `strict=False`, D-206/D-238). Paid exposure verified absent, not assumed: `bedrock_call` lines report `"duration_ms": 0.33` / `0.37` — sub-millisecond round trips are `MockBedrockProvider`.
- **Evidence**: `scratchpad/exec_local_3b2.md` steps 1b, 2, 3, 5 (the comparison table); `docs/PROGRESS.md:35-38`; `e2e/playwright.config.ts:34` (`workers: 1`); `e2e/artifacts/journeys.jsonl`.
- **Timestamp**: 2026-08-20T04:06:35Z (Playwright boot stamp); pytest ran to completion immediately before, wall clock 500.43 s.
- **Limitations**: the documented pair is structurally silent about the `1 xfailed` third bucket, whose value is **nondeterministic by design** (a rerun of the same tree can print `1 xpassed`). Both pytest skips being paid opt-ins means the free suite says nothing about real-Bedrock eval quality. And these counts describe **HEAD `344f016`, not the deployed build** — staging runs `gha-44a12dfc9549`, 10 commits behind.
- **Classification**: **LIVE_CONFIRMED**. Both documented totals reproduced **exactly** at HEAD `344f016` — so the WORK-11 upward-drift precedent was not even needed — and both skip identities matched the pre-registration verbatim, which the decision rule flagged as the decisive half. Confidence moves from MEDIUM/doc-claimed to **executed**. See LB-07.

### WORK-05

- **Claim ID**: WORK-05
- **Intended behavior**: on merged `main` at `6f107c1` — `ruff` clean, `ruff format --check` clean, `pyright` 0 errors, pytest **1735 passed / 2 skipped**, Playwright **127 passed / 2 skipped**, chat-web **49** unit tests, learning-web **26**, both builds clean (`docs/PROGRESS.md:35-38`; `docs/ROADMAP.md:3205-3207`, which defers the numbers to PROGRESS rather than repeating them).
- **Prior evidence**: WORK-05 is TEST-28's **superset** — the same PROGRESS lines plus the two lint gates and the two frontend builds. 3A — deferral table only (`:2232`); 3A.5 — converted everything **except** the two suite totals (`ruff check` + `ruff format --check` → `440 files already formatted`, `pyright` 0 errors, learning-web build 295 ms and chat-web 185 ms both clean, 49 + 26 frontend tests green), with F-row 6 pre-adjudicating the 437→440 delta as consistent growth, "not a contradiction"; 3B-1 — `:588`, local greps/counts, nothing owed by AWS.
- **Probe performed**: the identical shared pass, with HEAD's own SHA recorded alongside the counts — that being the difference between "the claim is wrong" and "the claim is dated". Tree identity captured **before** any run: `git rev-parse HEAD`, `git status --short`, `git rev-list 6f107c1..HEAD --count`; and again after both suites. `make fmt` was never run (`make lint` deliberately only checks, D-417/C8). The six figures 3A.5 already converted were **not** re-run.
- **Environment/endpoint**: local dev stack and the repository at HEAD; no CloudFront, no AWS, no secret.
- **Fixture/test identity**: n/a.
- **Observed behavior**: `git rev-parse HEAD` → `344f0161eb6bbd927ba1f0f37fa52ce937c112ca`; `git status --short` → `?? docs/reconciliation/` (this audit's own untracked output, not drift on HEAD); **`git rev-list 6f107c1..HEAD --count` → 1**. The extraction's "2 commits ahead" is corrected: **`6f107c1` IS #345**, so only `344f016` (#346, `docs: close Milestone 15…`) sits after the snapshot — **one docs-only commit**, meaning no Python or TypeScript exists between snapshot and measurement that could have moved a count. The two owed totals reproduced exactly: pytest **1735 passed / 2 skipped** (+1 xfailed), Playwright **127 passed / 2 skipped / 0 did-not-run**, zero failures in either suite. Post-run hygiene identical to pre-run: `git status --porcelain` → `?? docs/reconciliation/`, `git rev-parse HEAD` unchanged; **no repository file was modified**.
- **Evidence**: `scratchpad/exec_local_3b2.md` steps 1, 2, 3, and the Step-5 comparison table; `docs/PROGRESS.md:35-38`; `docs/ROADMAP.md:3207` (carries no numbers of its own — "see PROGRESS's session log for the numbers", confirming the ledger note).
- **Timestamp**: tree identity captured at lane start; suites completed by 2026-08-20T04:13Z (Playwright boot 04:06:35Z + 6.5 m).
- **Limitations**: only the **two suite totals** were re-executed here; the other six figures rest on 3A.5's conversion and were not repeated. Nothing lower and no gate red, but the reproduction is of **HEAD**, not of `6f107c1` itself, and not of the deployed build (10 commits behind).
- **Classification**: **LIVE_CONFIRMED (aged-by-SHA)**. Both suite totals reproduced and HEAD is stated: `344f016`, exactly **one docs-only commit** past the snapshot — the strongest available form of "the claim is dated, not wrong". No drift row from this lane.

### WORK-13

- **Claim ID**: WORK-13
- **Intended behavior**: against `E2E_TARGET=staging` the student journey spec is **not isolated** — measured across three runs, the two tests pass individually against build `4b847a8c5df4` but fail in combination (`answerWholeExam` returned **1 of 10**; the refresh test compared two different questions); the cause is stated as an inference, not a conclusion ("that is the next step, not a finished finding"), and the two named fixes are test-side: per-test fixture students, or clearing sessions in `beforeEach` (`docs/PROGRESS.md:16659-16690`, the file's physically last entry, 2026-08-07). Ledger status UNKNOWN.
- **Prior evidence**: 3A — **CONFIRMED_IN_REPOSITORY / DRIFT-58** (`REPOSITORY_STATE_EVIDENCE.md:1969-1980`): the per-test-fixture fix is present (`journey-student.spec.ts:117` signs in as `studentJourney`, `:427` as `studentResume`), **no `beforeEach` and no session-clearing hook appears** — the first named fix was applied, the second was not. 3A's own stated limitation is precisely this phase's job: "whether the isolation defect is actually resolved cannot be confirmed", tests were not executed. Also established: the staging e2e run is **not** a CI gate. 3A.5 — nothing (browser lane deferred). 3B-1 — `DEPLOYED_INFRA_DRIFT_REGISTER.md:381` asks for the behavioral confirmation "when the learning e2e walks run in combination".
- **Probe performed**: safety gate first (read-only `aws ecs list-clusters` / `list-services` / `describe-services` / `describe-task-definition`, env **names** and non-secret `name=value` pairs, secret **names** only), then scope (1) — the claim's literal wording: `make e2e-staging E2E_ARGS="tests/learning/journey-student.spec.ts"` with `AWS_PROFILE=jeongsik-staging-admin`, `AWS_DEFAULT_REGION=us-east-1`, `EXPECT_BUILD_SHA=44a12dfc9549`, `workers: 1`, `retries: 0`. Scope (2) (`E2E_ARGS="tests/learning"`, ~37 tests including four band walks) was **deliberately not run** — out of budget scope, **not** blocked by safety. No secret appeared on any command line (D-310 holds: `config.ts` fetched both in-process).
- **Environment/endpoint**: learning CloudFront `https://d35dfnjzmgrm01.cloudfront.net` (recipe also exported `CHAT_WEB_URL=https://d222glidpp4azv.cloudfront.net`), deployed build `gha-44a12dfc9549` = commit `44a12dfc95499fc40fc875681907951f5958ce5a` (2026-08-18, #336). `journey-student.spec.ts` is **byte-identical** between that build and HEAD, so the spec is a legitimate instrument for it.
- **Fixture/test identity**: `studentJourney` = **`student-ext-10`** (test 1) and `studentResume` = **`student-ext-9`** (test 2), minted out of band by `signInViaUi`'s staging branch. Both started clean.
- **Observed behavior**: `[build-identity] learning-api sha=44a12dfc9549` / `chat-api sha=44a12dfc9549`; `Running 2 tests using 1 worker`; **`2 passed (28.5s)`**, exit **0**; `results.json` stats **`{'expected': 2, 'skipped': 0, 'unexpected': 0, 'flaky': 0}`**, duration 28503 ms, 0 annotations, 0 errors. **None of the 2026-08-07 symptoms reproduced**: `pre-exam: answered 10 items` → **10/10** (was 1/10); **`refused=0`** on every one of the 12 study iterations, `POST …/answers` ×15 with statuses `{200}` only and `failedRequests: []` (was 7 refusals); refresh identity stable — `before refresh: Pre-exam Question 3 of 10 19:58` / `after refresh: Pre-exam Question 3 of 10 19:56`, same item and ordinal, only the countdown differing (was two different questions). Also decided in the same process: `study: answered 5 items`, `study verdicts: 5 graded, 4 wrong, 4 ladder pauses opened by the server`, reconciliation drift **5 − 5 = 0** (D-355; the 2026-08-14 failing run recorded 11 submitted / 1 graded), `ladderOffered` 4 and `interventions` 4, and `stems seen: 10 pre_exam, 5 study, 0 repeated` (D-325). **Neither `test.skip` non-vacuity guard fired**, so every assertion in the file executed — this is not the "partially observed" case the decision rule reserves. Criterion-3 capture over the whole run: `consoleErrorCount: 0`, `pageErrorCount: 0`, `serverErrorCount: 0`, `clientErrors: []`, `pageErrors: []`, `failedRequests: []`, **68 API calls (50 + 18) all 2xx**, no `audit.allow({…})` narrowing needed.
- **Evidence**: `scratchpad/exec_staging_3b2.md` steps A.1–A.3 and B.1–B.4; `e2e/artifacts/journeys.jsonl` (the `audit.note` lines quoted above) and `e2e/artifacts/results.json`, both gitignored and truncated per run; `e2e/tests/learning/journey-student.spec.ts:133,311-318,477-482`; `docs/PROGRESS.md:16659-16690`.
- **Timestamp**: safety gate 2026-08-20T03:56:38Z; run **START 2026-08-20T03:58:36Z → END 03:59:08Z**.
- **Limitations**: the original failure was a **whole-run** artifact — the walk then shared `studentPresent` with seventeen other specs — and this run reproduces the **two-test combination, not the cross-spec contention**. The register's broader wording (`DEPLOYED_INFRA_DRIFT_REGISTER.md:381`, whole `tests/learning`) was **deliberately not re-run**: one spec, by design, recorded here as a limitation and a residual, **not** as a block. The result is also attributable only to `44a12dfc9549` and says nothing about a newer build. The safety argument is re-derivable, not permanent: if `main.py:111` ever grows an env branch it expires. No attendance gate was encountered; no interrupt was approached.
- **Classification**: **LIVE_CONFIRMED (claim scope)**. Both tests passed in **one process, one file, first try** — exactly the "in combination" condition the claim says fails — so the per-test-fixture fix (D-365 §2 / D-367) is behaviorally sufficient and the second named fix (a `beforeEach` session clear, confirmed absent by 3A) is **unnecessary**. The ledger UNKNOWN closes. See LB-04, LB-05, LB-06, LB-08, LB-09.

### WORK-29

- **Claim ID**: WORK-29
- **Intended behavior**: §8's sequencing has steps 1–3 ticked (floor removed from the audit script, docstring corrected, instrument built as its own `BedrockTask` "wired to nothing") and **steps 4–7 unticked**: the hard-capped validation run (**the first paid step**), wiring the decision flow with check-3 sampling, check-4 routing plus check-5 monitoring, and measuring the unmeasured live rejection `_HINT_QUALITY_REJECT_BELOW` (`< 2`); §9 records four items explicitly out of scope (`docs/HINT_SOLUTION_REVIEW.md:519-541`). Ledger status **UNKNOWN**.
- **Prior evidence**: 3A — deferral table only (`:2234`); 3A.5 — nothing (paid lane); 3B-1 — `DEPLOYED_INFRA_DRIFT_REGISTER.md:382` carries the cost flag, "any arm that invokes generation is a **paid** run needing explicit user approval and exported model ids — never an audit-phase default". The ledger's two questions were: whether the validation run happened, and whether `_HINT_QUALITY_REJECT_BELOW` was ever measured.
- **Probe performed**: free documentary + source re-derivation — read D-254 and D-252 in `docs/DECISIONS.md` against `HINT_SOLUTION_REVIEW.md`'s §8 checklist and its three "never measured" lines; corroborated against today's HEAD in `ai_pipeline.py`; enumerated non-test callers of `run_review_loop` / `review_hints_and_solution`. **No paid arm**: D-254 *is* the validation run, and re-buying it at ~29¢ would replace the record rather than check it. The D-252-style histogram re-derivation over `question_validation_runs.stage_results->'judge'` needed the **dev Postgres, which this lane was forbidden to touch** — a lane restriction, not an environment blockage, and the documentary steps decided both ledger questions without it.
- **Environment/endpoint**: repository + git at HEAD `344f016`; `docs/DECISIONS.md`, `docs/HINT_SOLUTION_REVIEW.md`, `packages/curriculum/` source. No AWS, no staging, no database, no paid call.
- **Fixture/test identity**: n/a — offline content-pipeline claim with no browser surface and no `interrupt()` anywhere in its vicinity.
- **Observed behavior**: **step 4 was run.** `docs/DECISIONS.md:18463-18478` (D-254, accepted **2026-08-10**): "D-251 step 4, the first paid step. Pre-registration written before the script existed (`scratchpad/d254_preregistration.md`) … `scripts/measure_hint_solution_review.py`, **29.1¢**, 82 calls, Haiku 4.5 against the shipped authored bank", with all four pre-registered metrics surviving — **M1 verdict split 1 of 8** (disqualifies ≥ 3), **M2 blocking rate 10%** (≥ 30%), **M2r reject rate 2%** (≥ 10%), **M3 out-of-range defect index 0** (> 5%) — and the standing caveat "**That is not validation and the script prints so on every run**". **Step 7 was measured, and needed no paid run.** `docs/DECISIONS.md:18403-18405` (D-252): "**The floor has never fired.** 102 in-scale readings on generated candidates, plus D-249's 24 on the approved bank … — **126 readings, minimum observed 2, zero below it.** The floor sits below the distribution's observed support", from **331 runs, 110 with a judge verdict**, one `SELECT`. Corroborated on today's HEAD at `ai_pipeline.py:821-827` verbatim: "**D-252 measured it and it has never fired** … 126 readings, **minimum observed 2, zero below it** … Zero in 126 is a ~2% upper bound, not a proof that a 1 is impossible." Against that, `HINT_SOLUTION_REVIEW.md:527` and `:530` leave steps 4 and 7 **unticked**, and `:27` / `:452` / `:463` still say the `< 2` rejection "**has never been measured**" / "**stays until measured**". Two further staleness items in the same neighborhood: `:452` cites `ai_pipeline.py:1769` while the constant is at `:834` and its only gate at `:2005`; and the in-code "**Nothing calls this yet**" docstrings (`hint_solution_repair.py:3`, `review_panel.py:3-6`) are stale — `run_review_loop`'s only non-test caller is **`scripts/repair_authored_solutions.py:211`** (D-262), a script that "never writes to the bank", while `ai_pipeline.py` and `pipeline_cli.py` call neither.
- **Evidence**: `scratchpad/exec_staging_3b2.md` steps E.1–E.4; `docs/DECISIONS.md:18463-18478` and `:18376-18411`; `packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py:821-827,834,2005`; `docs/HINT_SOLUTION_REVIEW.md:27,452,463,520-530,536-541`; `docs/PROGRESS.md:2153,2806-2820`.
- **Timestamp**: 2026-08-20, within the 03:30Z–05:00Z window (documentary lane, no run stamp).
- **Limitations**: the histogram was **not independently re-derived** here, so the "minimum observed 2, zero below" figure rests on D-252's record plus the code comment rather than on a fresh `SELECT` — and D-252's own two guards (mock contamination by `MockBedrockProvider`'s constant `hint_quality_score: 5`; the eight pre-bound-era 8s/9s dated 2026-08-05 only) are the reason a careless re-derivation would be worse than none. Steps 5 and 6 remain genuinely open and were not probed beyond caller enumeration. Nothing here re-validates the instrument's *quality* — false acceptance is invisible to both checks by design.
- **Classification**: **LIVE_BEHAVIOR_DIFFERS** — and the divergence is **documentation-side: the system is ahead of its own doc.** Not a misbehaving system but a stale checklist, by ~8 days at authoring and nine days of decisions since. The parts of the claim that **hold** are recorded alongside: §9's four out-of-scope items are unchanged, and steps 5/6 are still real open work with no pipeline caller. See LB-01.

---

## 2. Classification totals

| Classification | Count | Claims |
|---|---|---|
| **LIVE_CONFIRMED** | **3** | TEST-28, WORK-05 *(aged-by-SHA)*, WORK-13 *(claim scope)* |
| **LIVE_PARTIALLY_CONFIRMED** | **2** | REQ-46, TEST-21 |
| **LIVE_BEHAVIOR_DIFFERS** | **1** | WORK-29 *(documentation-side; system ahead of doc)* |
| **BLOCKED_PAID_APPROVAL** | **0** | — |
| **BLOCKED_ENV_UNAVAILABLE** | **0** | — |
| **BLOCKED_NOT_OBSERVABLE** | **0** | — |
| Unverified at claim level | **0** | — |
| **Total** | **6** | REQ-46, TEST-21, TEST-28, WORK-05, WORK-13, WORK-29 |

**Zero claims are blocked or unverified at claim level.** Every one of the six was decided by a probe
that ran, by a documentary re-derivation, or by an explicit orchestrator ruling. The three items
below are **sub-arm residuals, not blocks** — each sits inside a claim that is already classified,
and none of them blocks the migration phase:

1. **The whole-directory staging contention re-run** (`E2E_ARGS="tests/learning"`, ~37 tests
   including four band walks) — the register's broader wording for WORK-13. Paid, optional; the
   claim as written was decided by the one-file scope.
2. **The recall-rate re-measurement** for REQ-46 — statistically weak at n=8 / n=6, which is why the
   13-turn paid run was ruled out rather than blocked; better served by the existing
   `scripts/measure_access_hint_live.py` whenever the user chooses to spend.
3. **The two real-Bedrock eval opt-ins** (`CHAT_EVAL_REAL_BEDROCK`, `EVAL_REAL_BEDROCK`) — the only
   two pytest skips, structurally silencing the free suite on real-Bedrock eval quality.

One further residual is recorded for completeness rather than as a gap: the D-252-style histogram
re-derivation for WORK-29 was declined on **lane** grounds (the dev Postgres belonged to the other
executor), and the claim was decided without it exactly as its decision rule permits.

**No new behavioral defect was discovered in any live walk** — 0 console errors, 0 pageerrors, 0 5xx
anywhere, across the local 127 and the staging 68-call journey run (LB-09).
