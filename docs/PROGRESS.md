# Progress Tracker

Living state of the build. Every session updates this file before ending.
Newest entries first. Keep entries short — details belong in code, tests, and DECISIONS.md.

## Current status

- **✅ Both D-113 latency carry-overs diagnosed and closed 2026-07-29 (D-115) — and they were
  one defect, not two. Four findings filed and fixed: AUD-X-09 (P1), AUD-X-10 (P2), AUD-X-11
  (P2), AUD-X-12 (P1).** Local suite **587 passed / 2 skipped** (565 at session start, +22),
  lint and pyright clean. Three PRs, each merged, deployed and verified against its own merge
  SHA: **#41 `7889610`, #42 `b245833`, #43**.
  **Root cause: the reranker had never once succeeded against real Bedrock.** `retrieve()` asked
  for 30 UUID-keyed scores under a fixed `max_output_tokens=1024`; real Bedrock returns
  `stopReason=max_tokens` with a truncated-but-valid-JSON `toolUse` block, which nothing read →
  Pydantic fails → a full repair call under the same ceiling → truncates identically →
  `StructuredOutputError` → silent RRF fallback. **~21 s and ~3.2 cents burned per grounded turn
  on a discarded result**, and answers came from an *unfiltered* candidate list (D-052's
  `score > 0` cut never ran since D-112 gave staging a real corpus).
  **One X-Ray trace was the whole diagnosis** (`7ee8e72c…`): `hybrid_search` **38 ms** killed the
  pgvector hypothesis, and 20.93 s sat inside one call that logged nothing. The tracing had been
  deployed since D-104; nobody had opened it.
  **The 30–84 ms zero-Bedrock refusals were the same defect's second face** — not task churn as
  D-113 guessed. The bursts are **30 s apart = `circuit_cooldown_s`**; five concurrent rerank
  failures tripped the *shared* breaker, so `scope_and_intent` failed closed too. X-Ray named it:
  `CircuitOpenError` at `gateway.py:90` → `langgraph.refuse`.
  **Why it survived a week: the gateway logged successes only** — every failure exit returned or
  raised in silence, so a call failing 100% of the time produced zero log lines and the only
  symptom was a gap between two unrelated timestamps.
  **Live before/after, measured the same way (guest turns via CloudFront, fresh session each):**

  | | unloaded p50 | loaded p50 | loaded p95 | errors | sub-1 s refusals |
  |---|---|---|---|---|---|
  | pre-fix (D-113) | ~29 s | 28.8 s | 32.8 s | 0 | 9 of 114 |
  | pre-fix (re-measured this session) | 29.5 s | — | — | — | — |
  | **post-fix (74-turn clean run)** | — | **9.57 s** | **15.94 s** | **0** | **0 of 74** |

  Per-task, post-fix: `scope_and_intent` p50 1.89 s, `rerank` **p50 2.92 / p95 3.76 s with 0
  repairs** (the log line that did not exist before), `rag_answer` p50 4.16 / p95 10.62 s.
  **The new WARNING lines found AUD-X-12 within their first hour**: `rag_answer` had its own fixed
  cap of 1536 against measured output of **p50 662 / p95 1490 / max 1530**, so ~1 turn in 30
  truncated — and `qa.answer_question` cannot tell a truncated response from an ungrounded
  question, so **it told students there was no approved source for questions that had one.** Also
  fixed the citation shape: `LlmCitation`/`RagContextChunk` are keyed by `context_index`, because a
  garbled UUID is an unmatchable citation and an unmatchable citation is also a refusal.
  **⚠️ Self-correction, same session: AUD-X-12's first fix regressed the low-passage end.** The cap
  shipped as `768 + 192n` by analogy with the reranker, but an answer's length is a function of the
  *question* — only its citation list scales. Single-passage turns got **960, below the 1536 it
  replaced**, and the next clean run truncated 3 of 74 turns, all `context_chunk_count=1`. Corrected
  to `2048 + 96n` (PR #43) with a test asserting every passage count 1–30 clears the old flat cap,
  watched failing against the cap then live. **Confirmed on revision 32: zero `bedrock_call_failed`
  of any reason across a 64-turn load run** (was 3 `output_truncated`), app 64/64 turns 200,
  ALB 134 requests with zero 5xx/504/connection errors.
  **Criterion 7 reframed (D-115 §11):** "redo the S34 calibration" was wrong — `chat_qa.js`'s
  `p(95)<1000` is correct for what it measures (mock provider, deliberately non-matching "zqxv"
  queries, no model in the path) and should stay. Criterion 7 is *missing* a separate live-staging
  threshold, which cannot be under ~8 s because a grounded turn is four sequential model calls.
  **Proposed: p95 ≤ 20 s, errors < 1%, concurrency 5, ≥2 tasks.**
  **Carry-over minted here:** (i) **answer brevity is the highest-value follow-up** — `rag_answer`
  is p95 10.62 s of the 15.94 and it is generating prose (p50 501 output tokens ≈ 375 words, p90
  ~1050 words); a shorter answer would improve latency, cost *and* SPEC §5.10.3
  age-appropriateness at once, but a prompt change is product-visible and needs its own before/after
  measurement; (ii) **`report.py` and `consolidation.py` have the same fixed-cap shape** over inputs
  that grow with student history — unmeasured, and they will now log `output_truncated` when they
  hit it; (iii) a residual `rag_answer` `schema_invalid` rate of ~2–4% under load, now visible,
  cause undiagnosed — capturing the invalid text needs a PII decision first; ~~(iv) six client-side
  timeouts~~ **(iv) resolved, not a finding: the client-side `ReadTimeout`/`ReadError`s were pooled-
  connection races in the ad-hoc load driver, not a server or edge failure.** Across every run the
  ALB reported **zero** 5xx/504/`TargetConnectionErrorCount` and the app answered **100% 200**;
  disabling HTTP keep-alive in the driver removed them entirely (58 turns, 0 errors). Operationally
  worth knowing: a naive pooled client can see resets on 10–17 s requests through CloudFront where a
  browser or k6 retries — **so criterion 7's error-rate leg should be measured with k6 through the
  edge, not an ad-hoc client**; (v) D-112's retrieval-margin flake ("Who is on the leadership team?", no-source 1 in 3)
  is very likely explained — unfiltered retrieval — but needs re-measuring before it is closed.
- **✅ AUD-L-04 fixed 2026-07-29 (D-114) — two P1s remain (AUD-L-07 read half, AUD-X-07
  half), both with written dispositions: zero P1s remain without one.** Local suite
  **565 passed / 2 skipped** (561 + three purge-boundary tests + the guard test's new
  parametrized case), lint and pyright clean. `retention_purge_cli` (one CLI, one daily
  18:50 UTC schedule) purges `semantic_memory` **90d on `last_confirmed_at`** (a
  reconfirmed fact survives; superseded audit rows age out — plan §9's "never deleted"
  yields to the retention promise, D-114 §1), `stage_transitions` 90d, `student_reports`
  **365d** (parent-visible history, the deliberate exception). CLI uses bare
  `create_engine()` and is in the AUD-F-15 guard test's list. `make retention-purge`
  smoke-ran locally (0 rows, nothing is that old yet).
  **✅ All three AWS-login-blocked items cleared after re-login, same session:**
  (i) `terraform apply` ran clean (plan and apply: exactly 1 add, the
  `intellichoice-staging-retention-purge` schedule, confirmed ENABLED at
  `cron(50 18 * * ? *)` — first unattended run tonight); (ii) **AUD-C-03's post-deploy
  staging probe passed**: a real-coordinates locator turn against the `9467c78` deploy
  answered with distances, then an ops-task query found **0 `__resume__` rows** for the
  thread and the coordinates' raw float64 bytes absent from every surviving blob
  (625 bytes of checkpoints intact — the purge is surgical, not a checkpointing outage);
  (iii) chat-api `desiredCount=1, running=1` — F-14's scale-in completed its final
  2 → 1 step exactly as D-113 predicted. **Both PRs merged and verified: #38 (D-113's
  work, deployed to staging, deploy concluded success against the merge SHA) and #39
  (this session's AUD-L-04 work, `ddf4e6c`), each with all 9 checks green.**
  **Criterion 6 is read per-job (D-114 §3):** the original two jobs' unattended week
  still completes 2026-08-02; `retention-purge`'s own week completes **2026-08-05**.
  **New standing obligation (D-114 §4):** the §6.1 privacy text must state the
  90/90/365 windows and must not imply chat deletion removes derived text — carried
  here until the legal track has a draft to hold it.
- ~~Next session: the two latency carry-overs~~ **(✅ both done 2026-07-29, D-115 — one root
  cause; see the entry above.)**
- **Next session: pick up (a) the post-#43 `output_truncated` confirmation and the criterion-7
  threshold decision, then (b) the two learning-side staging e2e failures that are all that
  stand between criterion 3 and two clean runs** (the time-telemetry dwell with AUD-F-01's
  signature despite the fix being deployed — check the served-bundle identity, AUD-F-16's ask —
  and the post-finalize narrative stall). Answer brevity (carry-over (i) above) is the
  highest-value optimization but is a product change needing sign-off. The remaining P1 halves
  (AUD-L-07 read, AUD-X-07) are S43+ work with written dispositions.
  Standing date-bound checks: **2026-08-01** re-probe "How do I enroll a student?";
  **2026-08-02** criterion 6's earliest pass for the original two jobs (**2026-08-05**
  for retention-purge); **S42's discovery asks to the org are still unsent** (unchanged
  since D-110, external lead time — send before the next session).

- **✅ AUD-C-03 and AUD-F-14 closed 2026-07-28 (D-113) — three P1s remain (AUD-L-04,
  AUD-L-07 read half, AUD-X-07 half), and the last two have written dispositions.** Local
  suite **561 passed / 2 skipped** (560 + the new C-03 probe), lint and pyright clean.
  **C-03:** `purge_resume_writes` deletes the thread's `checkpoint_writes.__resume__` rows
  right after a `location_consent` resume completes — the finding's own targeted delete,
  supersedes D-045's "briefly" and "not eliminable". Regression test runs the real endpoints
  against the real saver and decodes blobs with LangGraph's own serializer (the audit's
  msgpack method note); watched failing pre-fix with exactly the audit's two rows. **The code
  is not on staging yet — it rides the next merge + dispatched deploy**; staging holds no
  coordinates meanwhile (S37, and the e2e locator spec resumes with a zip). Probe once
  post-deploy.
  **F-14:** chat-api now scales on ALB p95 latency (step out >3 s/2 min: +1, +2 past 10 s;
  step in <1 s *or missing data* /15 min: −1), **replacing** CPU tracking for that service —
  the CPU policy's scale-in would read the incident's ~5% CPU as idle and undo the scale-out,
  so they can't coexist. Terraform applied to staging (4 add/1 destroy, chat-api only;
  learning-api stays on CPU — no measurement says to move it). **Live-verified: ALARM in
  2 min, desiredCount 1 → 3 in one step** (p95 was in the +2 band), 114/114 turns 200 under
  sustained 5-concurrent load. **Scale-in verified through its first step:** the scale-in
  alarm entered ALARM once the 15-minute quiet window cleared (missing data treated as
  breaching, as designed) and the policy set **3 → 2 at 23:58:32**. The final 2 → 1 step was
  not observed — the AWS session expired at midnight mid-watch — but it is the same policy on
  the same in-ALARM alarm after one more 300 s cooldown, floored by `min_capacity=1`. **One
  `aws ecs describe-services` after re-login confirms it**; the cost of being wrong is one
  idle Fargate task.
  **⚠️ The re-baseline's headline is that the old baseline no longer exists: a single
  unloaded grounded chat turn now takes ~29 s** (audit: 1.6 s — measured against the
  pre-D-112 noise corpus, when turns refused early). Log timeline per turn: scope ~2 s,
  embedding instant, then a **consistent ~26 s gap to `rag_answer` with no `rerank`
  bedrock_call line at all** (local runs log one). Consequently load p95 32.8 s ≈ single-turn
  latency (queueing amplification is gone — and honestly, turns already ran ~29 s at
  concurrency 5 on one task pre-scale-out), and **criterion 7's 3 s threshold leg is
  unmeetable until the ~26 s gap is diagnosed or the threshold recalibrated**. Diagnose the
  gap first (start with one OTel-traced turn); it smells like one defect.
  **Carry-over minted here:** (i) the ~26 s embedding→answer gap / missing rerank log line —
  no ID, diagnose before filing; (ii) nine of 114 load turns returned 200 in 30–84 ms with
  zero Bedrock calls, in two bursts coinciding with new tasks entering the target group, not
  reproducible after (6/6 identical probes answered ~29 s grounded), no WARNING/ERROR logs —
  no ID, diagnose before filing.
- ~~Next session: AUD-L-04 (the last P1 without a disposition — semantic_memory retention),
  or the two new latency observations above~~ **(✅ AUD-L-04 done 2026-07-29, D-114 — see
  the entry above; the latency observations are now the next session.)** Original: or the
  two new latency observations above if the gate ordering prefers criterion 7
  unblocked first. AUD-X-07's other half and AUD-L-07's read half keep their written
  dispositions (D-110 §3; the gate's option (b) note). Standing date-bound checks unchanged:
  **2026-08-01** re-probe "How do I enroll a student?"; **2026-08-02** criterion 6's earliest
  pass. **S42's discovery asks to the org are still unsent** (unchanged since D-110). C-03's
  merge + deploy + post-deploy staging probe is routine but pending.

- **✅ The chat cluster shipped and live-verified 2026-07-28 (D-112): AUD-C-16 and AUD-F-19
  closed, AUD-C-02's verification leg closed — five P1s remain** (AUD-L-04, AUD-L-07 read half,
  AUD-C-03, AUD-X-07 half, AUD-F-14). Two PRs (#34 `7469ea8`, #36 `9fdc178`), each deployed and
  verified against its pinned SHA; local suite **560 passed / 2 skipped**, lint and pyright clean.
  **C-16:** provenance columns + idempotent `knowledge-reembed` + a deploy-step re-embed + a
  fail-closed `/readyz` corpus assertion (the ALB health check — a mis-embedded corpus now drains
  the service instead of answering with noise). Staging re-embedded: **0/159 mock-like by S38's
  own discriminator** (was 159/159), paraphrase probes **no-source → 9/9 grounded with
  citations**, and the next deploy's re-embed was a 0-chunk no-op.
  **The ordering discipline paid for itself:** with retrieval fixed, F-19's "three different
  products" collapsed to document_qa 3/3 *on its own* — the flip-flop was C-16's noise — while
  the scope misroutes survived, isolating what was actually a prompt defect. D-111's topic fix
  was **measured insufficient** ("What is IntelliChoice?" still 0/3 with it live); the closing
  fix defines each intent and pins the measured misroutes as examples. Post-fix, fresh session
  per call: "What is IntelliChoice?" **3/3 grounded**, "Saturday hours" **3/3 with a Branch
  Directory citation** (was 0/6), "people who run IntelliChoice" 3/3 document_qa (was 3/3
  admin_contact email flow).
  **Not a defect:** "How do I enroll a student?" routes document_qa 3/3 but answers no-source
  because `public-student-participation-guide` is `effective_from` **2026-08-01** — the date
  filter failing closed correctly. **Re-check on/after Aug 1** (carry-over).
  **Staging e2e re-run (pinned to `9fdc178`'s deploy): 47 passed / 2 failed / 4 skipped** —
  identical scoreboard to D-111's run; the 2 are the known learning-side staging observations
  below (time-telemetry dwell, post-finalize stall), still undiagnosed, untouched here. All
  chat specs green a second consecutive run, this time with a working semantic channel.
  **Carry-over minted here:** (i) `youtube_videos.embedding` and
  `question_variants.stem_embedding` have no provenance columns — C-16's class, no runtime
  impact today (staging youtube is 0 rows, sync disabled); (ii) a retrieval-margin flake, no ID:
  "Who is on the leadership team?" goes no-source **1 in 3** before *and* after the prompt fix —
  rerank/confidence-threshold territory, measure before filing; (iii) one refusal carried a
  non-empty citations list (cosmetic, unverified). **Mid-session, the user shipped PR #35**
  (staging UI login, AUD-F-18's other half) and deployed `85dd6ad`; no interaction with this
  work beyond validating the re-embed no-op.
- ~~Next session: the remaining P1s — AUD-C-03 first, then AUD-F-14~~ **(✅ done 2026-07-28,
  D-113 — see the entry above).** Original: **the remaining P1s — AUD-C-03 first (a targeted
  `checkpoint_writes.__resume__` delete after the locator node, per its own finding; cheap and
  it's minors' coordinates), then AUD-F-14's scaling-signal change.** AUD-X-07's other half and AUD-L-07's read half both have
  their disposition already written down (D-110 §3; the gate's option (b) note). Two standing
  date-bound checks: **2026-08-01** — re-probe "How do I enroll a student?" (should gain
  citations by itself) and note the wider content window opening; **2026-08-02** — criterion 6's
  earliest pass, schedules must have run the week untouched. **S42's discovery asks to the org
  are still unsent and have external lead time** (unchanged since D-110).

- **✅ D-111 deployed and verified live 2026-07-28: staging e2e went 40/10/3 → 47 passed /
  2 failed / 4 skipped.** PR #32 merged (all 9 checks green, including the first runs of the new
  `chat-web`/`e2e-typecheck` jobs), deploy run `30385498488` verified against the merge SHA
  (`40acf59`), and the new re-seed step ran and exited 0 on its first execution — **AUD-F-20 is
  verified end to end**, all five attendance-blocked learning journeys now pass.
  **Do not read the chat side as fixed:** all AUD-F-19 chat specs passed *this run*, but F-19 is
  non-determinism (three different answers on identical calls in S42) and the corpus is still mock
  vectors (C-16) — one green run is exactly what a non-deterministic defect produces sometimes.
  F-19 stays open; the chat cluster stays next.
  **The two survivors are new staging-only observations** — both specs had never actually
  executed against staging before (blocked at `/topics` until today), so this is first light, not
  regression: **(i)** `time-telemetry.spec.ts` — after 15 s on one question the longest reported
  dwell is **1,989 ms**, AUD-F-01's exact signature, despite the deployed `main` containing S41's
  fix; suspect a stale CloudFront asset or a staging-latency interaction — check the served bundle
  identity first (AUD-F-16's ask, still unshipped). **(ii)** the main student journey stalls
  post-finalize: a stage narrative holds the screen while the phase poll times out at 60 s —
  AUD-F-04/05's displacement family widening under staging latency (locally the narrative window
  is ~26 ms; on staging it is seconds). Neither has an ID minted — diagnose before filing.
  Note the harness discipline that made this readable: AUD-F-03/F-04's specs are `test.fail()`
  expected-failures, so "47 passed" already accounts for two known-open findings failing on cue.
- **✅ Backlog-cleanup mini-session shipped 2026-07-28 (D-111): AUD-F-08 and AUD-F-20 closed,
  AUD-C-02's code half done, D-082's Mongo→MySQL doc sweep finally executed.** lint clean, pyright
  clean, **554 passed / 2 skipped** (552 baseline + two new guard tests). This supersedes the
  count below: **seven P1s remain** — AUD-C-02 leaves the list as fix-shipped/verification-pending.
  What changed: (i) `ci.yml` now builds all four deployables plus an `e2e-typecheck` job —
  criterion 4 is met (neither frontend has a test script; typecheck rides inside `build`).
  (ii) The scope prompt was missing **two** §5.19.4 topics, not one — "IntelliChoice organization"
  *and* "Student participation" — now covered, guarded by a static string test
  (`test_scope_prompt_spec_coverage.py`) because the mock can never see this defect class, plus two
  `paraphrase` eval probes for the real-Bedrock runner. Verification stays with the chat cluster
  (C-16 first, unchanged). (iii) `deploy-staging.yml` re-seeds MySQL fixtures after migrations on
  every deploy (user decision, D-111 §3 — weekly schedule declined to protect criterion 6's quiet
  week); **effective on the next dispatched deploy**, staging stays `phase=blocked` until then.
  `mysql_fixtures.py` now stamps `week_key` at call time. (iv) The docs no longer claim MongoDB is
  the source of truth — CLAUDE.md rule 1, SPEC.md (41 edits, §5.4/§6.4 numbers preserved,
  `MONGODB_READONLY_URI` → the real `*_MYSQL_URL` vars), FINAL_ARCHITECTURE.md, ROADMAP.md's live
  sections; historical records untouched. Also corrected in passing: AUDIT_FINDINGS.md's stale
  F-06/F-07 index rows, INTEGRATION_PLAN.md §2.5's seven-resolved-items backlog, and
  deploy-staging.yml's overtaken trigger comment (push trigger still off — enabling it is a
  standing decision nobody has taken).
- ~~Next session: the chat cluster~~ **(✅ done 2026-07-28, D-112 — see the entry above).**
  Original: **Eight P1s remain** —
  AUD-L-10 and AUD-X-08 closed in S42, but AUD-F-19 is new: AUD-L-04, AUD-L-07 (read half),
  AUD-C-02, AUD-C-03, AUD-C-16 (P3 → P1), AUD-X-07 (**half fixed**), AUD-F-14, **AUD-F-19**.
  **Take C-16 → C-02 → F-19 in that order and as one piece.** S42's staging run showed they are
  one problem, not three: staging's corpus is entirely mock hash vectors (C-16), so retrieval is
  noise, so the graph falls to whichever ungrounded branch it reaches first — which is what F-19's
  three-different-answers-to-one-question looks like from the outside. Judging C-02's scope prompt
  or F-19's routing before C-16 is fixed means tuning a prompt against a retrieval channel that
  returns nothing.
  **Two still carry a required verification *shape*, not just a fix:** AUD-X-07's remaining half is
  seam (b), mid-interrupt, where recovery means *completing* a paused LangGraph node rather than
  editing channel values — detection alone is not shippable, and fix shape (1), the commit ordering
  itself, is untouched; and AUD-F-14's ≥2-task fix must change the scaling *signal*, since CPU
  target-tracking cannot fire on an I/O-bound workload (CPU peaked at 15% while p95 sat at 31 s).
  **Two cheap ones are worth taking first:** AUD-C-02 is a one-line prompt fix (its test must run
  against a real provider — the mock's keyword list contains `"intellichoice"`, which is why no test
  could see it), and AUD-F-08 is two CI jobs that finish criterion 4's other half.
- **⚠️ Corrected: merging to `main` does not deploy anything, and three sessions' notes said it
  did.** `deploy-staging.yml` is **`workflow_dispatch:` only** — the `push` trigger is commented
  out deliberately ("not something that should fire unattended on every push until it's been run
  and reviewed at least once", a comment now overtaken by six reviewed runs). Deploy with
  `gh workflow run deploy-staging.yml --ref main`. **The way this nearly went unnoticed is worth
  more than the fact:** a watcher built on
  `gh run list --workflow=deploy-staging.yml --branch=main --limit=1` reported
  `COMPLETED: success` within seconds of the merge — it had matched the *previous* run
  (`30233724547`, the `73396c1` deploy this file already records). Comparing the run's head SHA
  against the merge commit is what caught it. Any check for "did my deploy succeed" has to pin the
  run id or the SHA; "the latest run is green" is true almost all the time and means nothing.
- **⚠️ Criterion 3 is NOT met, and it is further away than the roadmap said — S42 ran the staging
  suite for the first time and it returned 40 passed / 10 failed / 3 skipped.** Getting there took
  fixing two harness defects that hid each other (AUD-F-17, AUD-F-18, both below). The ten
  survivors are two real findings:
  **AUD-F-19 (P1, new):** on real Bedrock, *"What are the Saturday hours?"* routes to
  `location_consent` **3 times out of 3** with `answer: null` — the guest launch journey's most
  obvious question is never answered and the bubble sits on "Thinking…" — and *"How do I enroll a
  student?"* returned a **scope refusal, a no-source refusal, and an `email_approval` interrupt**
  across three identical consecutive calls. **Latency is not the cause and was ruled out: a guest
  turn takes 1.4 s.** Say that plainly to the next session, because AUD-F-14 makes "chat is slow"
  the reflex explanation for anything chat-shaped on staging. Neither is visible locally — the mock's
  keyword routing is deterministic and does not misroute these, which is **AUD-C-02's lesson on a
  second surface**. The non-determinism is plausibly downstream of **AUD-C-16** (staging's corpus is
  all mock hash vectors, so retrieval is noise), which makes C-16 a *prerequisite* for judging C-02
  and F-19 rather than a parallel item.
  **AUD-F-20 (P2, new):** every learning journey fails because `POST /topics` returns
  `phase=blocked`. `mysql_fixtures.seed()` writes attendance for `current_week_key()` **at seed
  time**, and staging was seeded in an earlier week, so the "present this week" fixture no longer
  is. **The gate is correct** (SPEC §5.4.4 fail-closed) — the data aged out. So **criterion 3
  evidence on staging is only valid within the week the fixtures were seeded**, unless
  `deploy-staging.yml` re-seeds or a schedule does. Neither re-seeding staging nor AUD-F-19 was
  attempted: the first mutates the staging environment and needs its own decision, the second
  belongs with the C-02/C-16 chat cluster.
- **✅ S42 shipped 2026-07-27 (D-110): the integrity/concurrency cluster — AUD-L-10 and AUD-X-08
  fixed, AUD-X-07 half fixed.** lint clean, pyright clean, **552 passed / 2 skipped across three
  consecutive whole-suite runs**, from 537 at session start. Taken instead of S42's scheduled
  discovery work because the dependency spine puts the gate *before* discovery, S42's own asks are
  mostly external (org DB topology, DNS, a read-only account), and criterion 2 needs the P1s gone.
  **Four things worth carrying as method:**
  **(i) The mock provider was hiding the money bug, and the unfixed code measured as clean.**
  AUD-X-08's concurrent arm on the *unfixed* ceiling produced **1 of 10 generated, 1.0× the
  ceiling** — it looked already fixed. The race window is the length of the model call, and
  `MockBedrockProvider` returns in ~0 ms. Giving it a realistic 250 ms (against S39's measured p50
  of 26.9 s on real Bedrock) produced **10/10 and 10.0×**, worse than S38's 8×. After the fix, same
  probe, **1/10 and 1.0×**. A cost-race test built on the mock's speed would have certified this
  fixed while it was wide open — third instance of the D-101 §5 shape.
  **(ii) Two fixes were nearly deleted as unnecessary, and one measurement decided each way.**
  AUD-L-10's Python pre-flight changed no test outcome once the unique constraint existed, which by
  D-109 §(iii) is a line to cut — until measuring showed a refused duplicate that reaches
  `graph.ainvoke` leaves **+2 `checkpoints` / +4 `checkpoint_writes`** behind. It stays, and the
  assertion protecting it is now a checkpoint row count. Conversely a defensive denominator recount
  in `compute_learning_gain` was **not** added, because with the constraint no test could watch it
  matter.
  **(iii) A regression test passed for the wrong reason, twice, before it was right.** The
  route-level ledger test first used `STUDENT_UNLINKED`, whose report never generates at all, so
  `generated is False` proved nothing and it passed with the ceiling *disabled*. Fixing that, it
  still passed with the ceiling disabled — the gateway's 50-cent session budget was catching it
  instead. It is now confirmed to fail only when both ledger reads are bypassed, and its docstring
  says exactly what it can and cannot isolate.
  **(iv) The drift guard caught its own constants.** `test_cost_reservation_estimates.py` failed on
  the first reservation constants written (0.5 against real worst cases of 1.35 and 2.625), before
  anything shipped.
- **⚠️ AUD-F-17 (P2, new, fixed): `make e2e-staging` was never pointed at staging.** Found by
  running the criterion-3 verification the roadmap had called "one command away" for three
  sessions. `E2E_TARGET=staging` selects the *auth* path (out-of-band token minting, D-097) but
  does not retarget the browser — `config.ts` defaults the two web URLs to `localhost:5173`/`5174`
  regardless of target, and only `LEARNING_WEB_URL`/`CHAT_WEB_URL` move them, which the Makefile
  never set. Result against the deployed stack: **2 passed, everything else
  `net::ERR_CONNECTION_REFUSED at http://localhost:5173/`**, the 2 being the only specs that never
  open a page. Supplying the URLs takes the same smoke spec **0/4 → 4/4**. Fixed in the Makefile.
  **Why it survived:** the failure reads as "you forgot to start the dev servers", which is exactly
  what a staging target is supposed not to need. **Together with the merge-does-not-deploy
  correction above, that is two false premises about the same criterion, both recorded as
  working** — the same shape as D-107 §10's "lost" secrets. A step recorded as *the one thing left*
  should be executed once before it is believed.
- **⚠️ AUD-F-18 (P2, new, fixed): the staging auth path was written, documented, and never taken.**
  Fixing AUD-F-17 let the staging suite run for the first time: **34 passed, 18 failed**, and all 18
  were one cause. `fixtures/session.ts` has documented out-of-band token minting as *the* staging
  path since the harness was written — `/dev/token` is secret-gated there (D-097) and the frontend
  sends no header, so the dev-login screen renders **`Not Found`** under Sign in — but all ten
  journey specs called `signInViaUi`, which drives that screen. Fixed by delegating to
  `mintToken` + `seedSession` on the staging target; the one test whose subject *is* the login
  screen now skips there with a stated reason (it should disappear with S44).
  **The two harness defects hid each other:** AUD-F-17 meant the suite never reached staging, so
  AUD-F-18 could not be observed. Both sat inside a step three sessions described as one command
  away.
- **⚠️ One thing found in passing that is not fixed.** Adding `worst_case_cost_cents` to the
  `BedrockGateway` Protocol produced **70 typecheck errors across ~13 scripted test fakes** that
  would each need a pricing method they never call. The method stayed on the concrete gateway and
  the reservation estimates are constants guarded by a drift test instead. Worth knowing before
  anyone else tries to widen that Protocol: it is expensive to extend.
- **✅ S41 shipped 2026-07-27 (D-109): the criterion-3 cluster is done — AUD-F-01 (P1) and
  AUD-F-02 (P2) fixed, three harness races fixed, and the suite is green three runs running.**
  **52/1/0, 51/2/0, 52/1/0** (passed / skipped / failed) against **48 passed, 3 failed, 2 skipped**
  at session start. Python side unchanged: lint clean, pyright clean, 537 passed / 2 skipped.
  Four things worth carrying as *method*, because four separate hypotheses were wrong and a
  measurement caught each one:
  **(i) "Same root cause" was an assumption, and the middle measurement is what disproved it.**
  Fixing AUD-F-01 took the post-finalize burst from **35 × 409 to 1**, and 1 looks like noise —
  closing AUD-F-02 there would have been defensible and wrong. That survivor is a different defect
  (the view-time flush on unmount, where the unmount *is* the finalize), so criterion 3's zero-
  console-errors would still have failed, for a reason the closing note claimed was handled.
  **(ii) The AUD-F-02 fix is about *when*, and three readings of the component got it wrong.**
  A `finalizedRef` set after `await onFinalize(...)` changes nothing: `finalizeExam` calls
  `setSnapshot` **inside** the awaited request, so React unmounts the screen in a microtask that
  lands first. One temporary `console.warn` in the cleanup settled in a single run what deduction
  had failed at three times.
  **(iii) A change was reverted rather than shipped.** Scoping the flush to exam phases looked
  right and had a confident comment. A control run showed the test passes without it — so the
  explanation was wrong and no test covered the line. Every shipped line here was watched
  mattering, which is D-107 §1's bar for tests applied to product code.
  **(iv) The intermittency was three unrelated harness bugs, and each passed the run before it
  failed.** Only one is the shared-state story S39 recorded. Fixing the diagnosis would not have
  found the other two; running the suite again did.
- **⚠️ Two things found in passing that are not fixed.** **AUD-F-16 (P2, new):** the browser audit
  had been measuring **two-day-old API code** — `reuseExistingServer: true` plus `uvicorn`
  processes up since 2026-07-25 21:31, i.e. predating S40's four authorization fixes. Playwright
  restarts the *frontends* every run and reuses the *APIs*, which is the worst version, because
  nothing looks stale. Every S39/S40 `local` e2e result is of an unknown application version. **And
  a tracked directory, `knowledge-content copy/`, disappeared from the working tree mid-session**
  (33 files) and was restored with `git checkout`. Not pytest and not `make e2e` — both were
  re-run afterwards with the directory intact. Cause unknown; worth a glance at `git status` before
  trusting a clean tree. (It looks like an accidentally committed Finder duplicate of
  `knowledge-content/`; deleting it deliberately is a reasonable separate call.)
- **✅ S40 continuation shipped 2026-07-27 (D-106/D-107/D-108): four authorization P1s fixed and
  live-verified, the D-053 recurrence ended structurally, and 19 PRs merged.** Details in the
  session-log entry below. Three things worth carrying forward as *method*, each of which nearly
  produced a wrong result in this session:
  **(i) A regression test that has never been seen to fail is an assertion about nothing.** All 18
  new tests were run with their own fix disabled; **two passed**, and had to be rewritten. The
  AUD-C-04 test used two ordinary turns — an ordinary turn overwrites every field on its way
  through, so the stale read it was meant to catch was invisible. It needed a genuinely *paused*
  turn.
  **(ii) A live probe that cannot express the failure proves nothing.** AUD-X-02's first staging
  probe returned 200 for all three bad-claim tokens and nearly shipped as a pass. `DevTokenRequest`
  accepts only `role`/`sub`/`audience` and silently drops the rest, so staging minted a fully
  consented token every time. **`/dev/token` cannot express a non-consented account** — no probe
  built on it can ever test that gate. Real verification needed tokens signed with staging's own JWT
  secret. Same class as D-101 §5's positive-control lesson and D-105 §5's dead notification.
  **(iii) An existing test caught a defensible-looking fix that would have removed a product
  feature.** `POST /students/{id}/report` was classified as a write; the suite failed, because with
  no assignment model every student is "unlinked", so tutor report generation would have ended
  outright. AUD-L-07 files that under the read-scope gap S43/S46 own.
- **⚠️ CORRECTION: `STAGING_TOKEN_SECRET_LEARNING`/`_CHAT` were never missing, and three sessions
  scoped around a constraint that does not exist.** S38, S39 and S40 each recorded these as "the one
  thing to hand over" and "the binding constraint on three gate criteria". They are Terraform
  `random_password` resources in Secrets Manager (`terraform/environments/staging/main.tf`) — never
  handed to a human, so never losable. Recover without echoing:
  `aws secretsmanager get-secret-value --profile jeongsik-staging-admin --region us-east-1
  --secret-id intellichoice-staging/{learning,chat}-api/staging-token-shared-secret --query
  SecretString --output text`. Verified live 2026-07-27: both mint tokens, chat `/me` 200, and every
  S40 fix was re-verified on authenticated staging paths as a result. **The authenticated halves of
  criteria 7 and 8 are therefore reachable and no longer blocked** — they are simply not yet done.
  Staging's real JWT signing secret is at the same path with `jwt-signing-secret`, which is what
  lets a probe carry arbitrary claims. **Generalisable: before recording anything as blocked on a
  missing credential, check whether Terraform generated it.**
- **✅ Criterion 5's open judgement call is settled.** The prior entry left it on whether
  "consecutive" excludes a failed deployment in between, since the bad-image rollback drill sat
  chronologically between `bccc3ac` and `73396c1`. There are now **six consecutive successful
  `deploy-staging.yml` runs**, and `73396c1` → `c58d1fe` is a clean consecutive pair with **no
  failed deployment between them** on either reading. Combined with the demonstrated auto-rollback,
  **criterion 5 is met.**
- **Criterion 4 is half met.** Three consecutive green `make lint typecheck test` runs, repeatedly,
  and the D-106 fix removes the recurring source of baseline flake. **But CI on `main` still runs
  only `lint-typecheck-test` and `learning-web`** — `chat-web` and the `e2e/` harness have no build
  or test job, so "CI builds and tests every deployable" remains unmet (AUD-F-08). Both frontends
  were verified by hand this session, including TypeScript 7 on chat-web, which no CI job would have
  caught.
- **⚠️ Criterion 6's ≥1-week clock started 2026-07-26. The earliest possible gate pass is
  2026-08-02**, and only if the schedules run untouched. **Nothing in the S40 continuation went near
  the schedules.** **Two schedules are ENABLED**
  (`intellichoice-staging-chat-purge` daily 18:10 UTC, `intellichoice-staging-memory-consolidate`
  Sundays 18:30 UTC) and **`youtube-sync` is deliberately DISABLED** — see D-105 §4. What to check
  each day: the first `chat-purge` run is **18:10 UTC on 2026-07-27**, and any non-zero-exit
  ops-task run now emails the alerts topic, so **silence is the pass signal**. Do not disable or
  re-apply over these without noting it — an interruption restarts the week.
- **S40 opened 2026-07-26 (D-105): AUD-F-06 fixed, AUD-F-07's premise corrected, and one new P1
  (AUD-F-15) that only a scheduled run could have found.** `chat-purge` had **never once executed
  against the deployed database** — it read `LEARNING_`-prefixed settings that the ops task does not
  set, so it silently used its `localhost` default and the first scheduled run died on
  `127.0.0.1:5432`. So SPEC's 90-day retention promise had never actually been kept. Fixed, with a
  guard test over every standalone CLI (third instance of this shape), **and verified on the real
  path after deploying**: a one-shot Scheduler probe ran `startedBy chronos-schedule/…` on the
  rebuilt image, exit **0**, logging `purged 0 tutor_chat_messages row(s) older than 90 days`. **Also: the failure
  notification I added was itself dead on arrival** — the rule fired, `FailedInvocations = 1`, SNS
  delivered 0, because the topic policy did not allow `events.amazonaws.com`; CloudWatch *alarms*
  publish to the same topic fine on the default policy, which is what made it worth testing rather
  than reasoning about. Fixed and re-verified with two further deliberate failures.
  **AUD-F-07 was a false premise:** staging has **zero** `loadtest-` rows (`semantic_memory` empty
  entirely), so nothing was blocked on fixture cleanup — the 150 are local-only, per D-095's
  docker-compose load test. Cleaning the local dev DB is optional hygiene, still outstanding.
- **Criterion 5 may now be complete — one judgement call is yours.** Two consecutive
  workflow deploys went green end to end including migrations, the `/dev/token` security gate, the
  3-minute canary bake and the smoke test (`bccc3ac` run 30218489130, `73396c1` run 30233724547),
  and the deliberate auto-rollback drill is demonstrated. **The nuance:** the bad-image drill sits
  chronologically *between* those two deploys. It was an out-of-band `update-service`, not a
  pipeline deploy, so on the natural reading the two pipeline deploys are consecutive — but if
  "consecutive" is meant to exclude any failed deployment in between, one more workflow run settles
  it, and re-running on an unchanged commit is cheap now that S35's ECR-reuse fix exists.
- **AUD-F-10's CI hazard is cleared — the "DO THIS FIRST" that led this file is done.** The mirror
  is pushed (`aws-otel-collector:v0.43.3`, `linux/arm64` verified against `runtime_platform`),
  Terraform re-applied, and both services are deployed onto the sidecar. **Staging is healthy and
  tracing:** frontends 200, chat `/me` 401, `/dev/token` **404 for both a missing and a wrong
  secret** (S35's gate intact), both `otel-collector` containers RUNNING, both target groups
  healthy. One wrinkle worth keeping: `public.ecr.aws` rate-limits anonymous pulls
  (`toomanyrequests`) — `aws ecr-public get-login-password | docker login public.ecr.aws` first.
- **AWS sessions expire roughly hourly** and expired mid-`apply` twice now (S39 and this
  continuation). Re-auth with `aws login`, then `--profile jeongsik-staging-admin` for the CLI and
  `eval "$(aws configure export-credentials --profile jeongsik-staging-admin --format env)"` for
  Terraform *and* for `scripts/scan_xray_pii.py` — boto3 cannot read the CLI's token cache without
  `botocore[crt]`. **Plan operations work in sub-hour units** and re-check
  `aws sts get-caller-identity` before starting anything long.
- **~~⚠️ The one thing to hand over: `STAGING_TOKEN_SECRET_LEARNING` / `_CHAT` were never available
  to this session, and that is now the binding constraint on three gate criteria.~~** **The premise
  was false — see the CORRECTION item at the top of this block (2026-07-27).** The secrets were
  always retrievable from Secrets Manager. **What remains true, and is the useful part of this
  item:** every learning route requires `get_current_claims`, so there is no *unauthenticated* path
  that can produce a 5xx or a slow response — which is why the learning app's two alarms were
  induced on the `set-alarm-state` delivery leg only, the load run was guest-chat-only, and the
  criterion-9 trace scan covered **guest traffic only**, which is *not* where names and emails would
  enter a span. Those three remain **undone**, but they are no longer **blocked**: with a token in
  hand, S41 can induce the two learning alarms on their real condition, re-run the load test on the
  authenticated path, and re-scan traces over authenticated traffic.
- **S39 continuation shipped 2026-07-26 (D-104): items (a) done, (b)–(d) partial — 4 new findings,
  one P1 fixed in-session, and the tracing work found a credential leak.**
  **(a) Done, and it closes S38's unevidenced sub-item plus criterion 9's trace half.** Traces went
  from the recorded baseline of **0 over 6 hours** to **650**, then **1,925 traces / 9,614 segments
  / 749,155 strings scanned CLEAN**, re-confirmed afterwards over the load-run window (**1,286
  traces / 5,439 segments / 452,312 strings**, the richest content of the session) — with a positive
  control firing **20/20** every run *and* a coverage control proving the one request carrying
  precise coordinates was in the scanned set.
  Request bodies are not captured into spans. **Two defects had to be fixed to get there**
  (AUD-F-12, no `xray` VPC endpoint — the collector accepted and discarded every span with nothing
  detecting it; AUD-F-11, a stale Terraform image pin that made `apply` silently revert a security
  fix), **and the scan then found AUD-F-13, the P1:** a bearer JWT recorded in `http.url` on every
  SSE connection, because `EventSource` cannot set an `Authorization` header and
  `FastAPIInstrumentor` records the full URL. **The same request is sanitized in the access log and
  not in the trace** — which is exactly why S38's log scan was clean, and the reason a PII floor has
  to be re-established per store rather than inherited. Fixed at the export boundary
  (`RedactingSpanExporter`), with a regression test that drives the real instrumentation and was
  confirmed to fail with the fix disabled. Deployed via CI (`bccc3ac`).
  **AUD-F-09's fix is now verified on a real deploy**, not just by reading: revision 21 patched the
  app image and left `aws-otel-collector:v0.43.3` untouched, which is the two-container case the fix
  was written for and could not previously be tested against.
  **(c) Done — criterion 5's auto-rollback is demonstrated deliberately.** An unpullable tag on the
  *essential* container: 4 task attempts, each `CannotPullContainerError` retried 7×, `failedTasks`
  hit 3, and ECS rolled back on its own at 15:42:06 — **13 m 55 s** end to end, which is the floor
  on how long a bad deploy stays stuck. **Zero downtime measured, not assumed: 200 edge probes
  across the window, every one a 401 from the application, zero 5xx.** Revision 22 was then
  deregistered — leaving a poisoned revision as the family's *latest* is exactly AUD-F-10's trap.
  Combined with the green CI deploy above, criterion 5 needs **one more clean deploy** for its
  "2 consecutive".
  **(b) Partial — one alarm induced genuinely, three on the delivery leg only.**
  `chat-api-p95-latency` went `OK → ALARM` on its own evaluation from real 30-second latency, and
  **delivery is proven by SNS's own metrics rather than inferred**: 4 delivered / 0 failed across
  the four inductions, against a 3-hour baseline of zero — and **the maintainer confirmed all four
  emails arrived (2026-07-26)**, which is the half no AWS API can evidence, since `Delivered` means
  SNS handed off to SES rather than that the mail cleared spam filtering. **So criterion 8's
  "reaching a monitored inbox" half is met for all four alarms.** The other three have **no
  unauthenticated path to induce** (see the secrets item above), so what stays unproven is narrower
  than it was: their *detection* leg — that the metric and threshold fire on the real condition —
  not their delivery.
  **(d) Partial — and it produced a new P1, AUD-F-14.** 45 guest turns, all 200: **1.62 s unloaded
  → p50 26.92 s / p95 32.14 s at concurrency 5**, ~10× the 3 s threshold at a concurrency that is
  not a stress test. **Autoscaling cannot react**: it is CPU target-tracking at 70% and the workload
  waits on Bedrock, so CPU **peaked at 15.19%** while p95 sat at 31 s and `desiredCount` never left
  1 — so **criterion 7's "≥2 tasks under load" is unreachable as configured.** Guest-chat-only, so
  the authenticated path stays unmeasured. Spend ~$0.20 of the ~$5 cap.
  **Three sequencing facts worth keeping, each learned the hard way.**
  (i) `deploy-staging.yml`'s canary bake checks these exact four alarms and rolls back if any is in
  ALARM — **never induce an alarm while a deploy is in flight, and never leave one lit.**
  (ii) `set-alarm-state` is **transient**: the next real evaluation overrides it, so a manually
  cleared alarm can re-fire minutes later on trailing data. All four were left settled `OK`
  *naturally*.
  (iii) ALB metrics publish with ~1.5–2 min lag, so **an alarm fires minutes after the breach window
  closes** — do not extend a load run just because it has not tripped yet.
- **S39 shipped ⏸ partial, 2026-07-25 (D-103): AUD-F, 9 findings (AUD-F-01..09), one P1, one fixed
  in-session. Browser automation now exists** — a Playwright harness in [e2e/](../e2e/),
  `make e2e`, 46+ journeys with console/network capture.
  **⏸ because the four operations items above mutate staging.** Everything not requiring a staging
  mutation is done.
  **The browser-driven half of §2.3 is now closed for both apps** — the gap S36 and S37 each left.
  All **18** chat response shapes render correctly in a real browser (S37's fourteen, with the
  email/location outcomes split), **confirming S37's code-reading conclusion by rendering**, and
  AUD-C-04/AUD-C-10/AUD-C-11 are reproduced visually. A drift control runs one real un-stubbed turn
  and asserts the live field set matches the fixtures, so the suite cannot silently audit a payload
  the API no longer sends.
  **The P1 is AUD-F-01, and no API-level audit could have found it.** `App.tsx` passes
  `onFetchOverview` and `onRecordTime` as **inline arrows** into `ExamScreen` effect dependency
  arrays, so every render re-runs both effects. Measured with the student sitting on one question
  for 15 seconds touching nothing: **885 `POST /exam/items/{id}/time` (~59/s)**, each carrying the
  ~20 ms gap between two renders, and **76 `GET /exam/overview` for one 10-item exam at a median
  30 ms gap against the declared `OVERVIEW_POLL_MS = 20000`** — ~667×. Both hit the database on the
  main journey's hot path. **The fix is one line per callback; the re-verification must count
  requests**, because the screen has always worked and that is why three audits missed it.
  **It also corrects AUD-L-14's evidence.** The server *accumulates* item time, and the browser's
  885 reports total **15,591 ms for a 15,000 ms dwell** — approximately right. S36's "140 rows
  summing to 0 ms" is most consistent with its journeys being **API-driven with no browser in the
  loop**, which is how S36 had to drive them. AUD-L-14's substantive point stands (the report
  ignores `assessment_attempts.response_time_ms`); its headline number needs re-measuring.
  **Two more that block gate criteria directly.** **AUD-F-02:** after `finalize` returns 200 the
  client fires **35 × 409 in a 96 ms burst**, each a browser console error — so **criterion 3's
  "zero console errors" cannot be met until it is fixed**, independent of any visible symptom.
  **AUD-F-06:** `aws events list-rules` and `aws scheduler list-schedules` are **both empty** — no
  job is scheduled at all, so criterion 6's ≥1-week unattended clock **has not started**, and the
  earliest possible gate pass is **one week after the EventBridge schedules land**. Sequence them
  early in S40, and clean up first: **AUD-F-07**, `make memory-consolidate` reports 145.97 cents
  for 160 students of whom **150 are `loadtest-student-N` fixtures left by S34**.
  **AUD-F-10, found only by deploying:** the ECS tasks **cannot pull from `public.ecr.aws`** —
  private subnets, `ecr.dkr`/`ecr.api` endpoints, **no NAT** (D-084's cost posture), and no
  interface endpoint exists for public ECR. The sidecar deploy failed with
  `CannotPullContainerError ... i/o timeout`, retried 7×, and was rolled back. Note that
  `essential: false` did **not** save it: a non-essential container that *exits* leaves the task
  up, but one that cannot be *pulled* fails the task before it starts. Fixed by mirroring into
  private ECR (`scripts/mirror-otel-collector.sh`, arm64-pinned to match `runtime_platform`).
  **Also found:** **AUD-F-03** a refresh mid-exam drops the student from "Question 3 of 10" to
  "Question 1 of 10" (SPEC Phase 11's own "done when", cited verbatim in `useLearningSession`'s
  docstring); **AUD-F-04/05** stage narratives return after a reload and displace live screens (the
  topic list is interactive ~26 ms); **AUD-F-08** two of four deployables have no CI job.
  **AUD-F-09 fixed in-session** — a defect in *this session's own change*: `deploy-staging.yml`
  rewrote the image tag on every container, so adding the sidecar would have crash-looped every
  later deploy into a circuit-breaker rollback. Caught by reading the deploy path before applying.
  **Three plausible findings were killed by measuring them** (the failure mode of browser audits is
  over-reporting): the hint survives 14.7 s untouched; the SSE stream reopens **0** times in 20 s of
  idle (the 71 `ERR_ABORTED` entries are the hook's own cleanup); and the attendance gate is
  correct — it fires at `/topics`, not `/student`, verified at the API for both fixtures, so rule 5
  holds and the test was asserting at the wrong step.
  **Strong negative results, all in a real browser:** attendance fails closed for *both* absent and
  **unknown-attendance** students; the branch-manager email shows a draft with Send and Decline
  before anything is sent; a two-child parent is offered exactly both and the choice sticks while a
  **single-child parent is auto-selected** (S11's gap does not reproduce); chat answers render for
  guest and all four signed-in roles; the locator asks consent before collecting, honors declining,
  and returns an answer on a shared ZIP; transcript survives a refresh.
  **Not covered, and two harness carry-overs stated plainly.**
  **(i)** The study → post-exam → results segment of the student walk. A **harness limitation, not
  a product defect**: to stay deterministic the walk always picks the first option, so it answers
  wrong nearly every time and the study phase never reaches the mastery bar that ends it (measured:
  22 answers, 18 ladder responses in 6 minutes, still advancing, zero 5xx). Closing it needs the
  walk to read the answer off the ladder's "Show the solution" panel and then answer correctly — a
  real student path, left as carry-over rather than faked.
  **(ii) The e2e suite is not yet stable end-to-end.** Individually every finding above reproduces
  (several were re-measured in isolation with controls), but a *whole-suite* run lands at **49–50
  of 51 with 1–2 intermittent failures that move between runs**, concentrated in the longest
  journeys and in chat turn resolution. The cause is shared-state coupling — one student fixture
  reused by many journeys against a database that accumulates sessions — not the app. **This must
  be fixed before the gate**, because §2.6 criterion 3 asks for every journey to pass *twice
  consecutively*; treat it as a first-class S40 item rather than harness polish.
  **(iii)** `make webcontent-sync` **rewrites tracked `knowledge-content/` files** and asks for a
  human diff review; leaving its edits in the tree breaks
  `test_ingestion_creates_all_documents_then_is_idempotent_on_rerun` (found exactly that way here,
  reverted, 513 passed). So **only three of the four jobs are schedulable**, and §2.5's work item
  should be re-scoped — see AUD-F-06.
  **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **513 passed / 2
  skipped**, three consecutive runs. Test count unchanged — the browser harness is a separate suite
  (`make e2e`); per S37/S38's precedent the probes are not folded into the Python suite, and
  regression tests land with the Phase 0B fixes. Three confirmed defects are marked `test.fail()`
  so the suite stays green while they keep being measured; a Phase 0B fix makes them pass
  unexpectedly, which fails the run and is the signal to promote them.
- **Phase 0B (S40–41) now has four P1s queued from S38** on top of the six from S36/S37, and two
  of them are structural rather than local: **AUD-X-07** (checkpoint commits before the domain
  transaction — the fix that matters is replacing the `assert`s on checkpointed ids with a
  reconciliation path, not reordering the commits) and **AUD-X-08** (every per-day cost ceiling is
  a read-then-act race; **whatever lands must be re-verified with a concurrent arm**, because the
  sequential test passes today and would keep passing after a bad fix).
- **S38 shipped ⏸ partial, 2026-07-25 (D-102): AUD-X, 8 findings (AUD-X-01..08 plus AUD-C-16
  settled), five P1, one fixed in-session.**
  **⏸ not ✅ for one reason:** its roadmap line says "PII floor re-verified against live staging
  logs/**traces**/metrics/payloads", and `OTEL_ENABLED` is **false** on both staging services, so
  the traces half is unevidenced rather than passing. Logs, stored payloads and metrics are all
  clean *with positive controls*. Enabling OTEL is a deploy-time config change, left to S39 rather
  than done inside an audit.
  **AUD-C-16 is settled and upgraded P3 → P1: staging's semantic retrieval has never worked.**
  The corpus is **159/159 `MockBedrockProvider` hash vectors** while both deployed services query
  with real Titan v2. Measured: stored-mock vectors peak at cosine **+0.065–0.074**, which is the
  1/√1024 ≈ 0.031 chance floor, versus **+0.19–0.41** for the same chunks embedded with real Titan.
  Live, the seven `paraphrase` cases cite the expected document **1/7**. Both controls ran before
  the discriminator was trusted. What moves it off P3 is not the misconfiguration but that
  **nothing anywhere detects it** — so the fix that matters is a startup assertion that the
  configured embedding model matches the corpus, not the re-ingest.
  **The two P1s from the deferred areas, both reproduced with control arms.**
  **AUD-X-07:** the checkpoint commits inside `ainvoke` (its own psycopg connection, per superstep)
  while domain rows commit in FastAPI's dependency teardown *after the route returns*, so any
  failure between them keeps the graph's state and discards the database's. Mid-finalize leaves a
  scored exam `in_progress` with a dangling `study_session_id` — a reloading client is served a
  study question and then **500s forever**; mid-interrupt leaves a pending `intervention_choice`
  for an attempt row that does not exist, `/respond` **500s**, and the interrupt never clears. Both
  end states are unrecoverable through the API. **The trigger needs no bug: ECS drains tasks on
  every deploy.** The control arm passed — the ordinary answer path stays consistent across the
  same crash — which is what localises the defect to routes whose checkpoint carries a row id.
  84 `assert … is not None` statements (35 in `graph/nodes.py`) are load-bearing cross-store
  invariant checks written as a statement `-O` deletes.
  **AUD-X-08:** **10 concurrent reports → all 200, 8 generated, 8.0× the ceiling**, while the
  sequential control correctly degraded to the facts-only template. A correct check with no
  serialization around it, which weakens AUD-L-02's P0 fix; a single caller can drive it because
  AUD-X-04 leaves the route non-idempotent. Two more ceilings share the shape and were not
  separately measured.
  **The authorization findings.** **AUD-X-01** (P1, **reproduced end to end on live staging**):
  `POST /sessions/{id}/student` is the one learning route that *writes* `student_external_id` and
  the one that never checks the existing value — a different student claimed an in-progress
  session, the owner got **403 on their own exam**, and their row was orphaned. That is verbatim
  AUD-C-01's shape in the other app, found in consecutive sessions. **AUD-X-02** (P1): SPEC
  §5.1.2's `parental_consent_verified` check **does not exist** — that claim plus `account_status`
  and `consent_status` are read by nothing, and a `suspended`/`revoked`/`under_13` token behaved
  identically to a consented one on **all 18 routes**. It sits in the seam between S44 and S45;
  whichever lands second must add the consuming-side assertion, or §5.1.2 stays unmet with no test
  noticing. **AUD-X-05** (P1): AUD-L-07's tutor fall-through extends to **writes** — a tutor token
  answered and **finalized another student's exam**. **AUD-X-03/04** (P2/P3): `/topics` replayed
  builds a second exam and orphans the first; `/report` has no idempotency key.
  **AUD-X-06 fixed in-session** (a test defect that left the baseline intermittently red, so it
  blocked §2.6 criterion 4 independently of the audit): a hint test asserted a plain substring
  where the product's `answer_text_leaked` is boundary-aware, so it **demanded more than the
  product guarantees** and the mock's own `hint lN` prefix collided whenever the drawn answer was
  `"1"`–`"3"` — **17.9%** of the bank's 51,613 variants, measured at **15/70 (21%)**. Now asserts
  the two functions `tutor.py` itself calls: **0/40**. **The earlier diagnosis of this was wrong
  and the correction is the transferable part:** AUD-L-17 did **not** regress — it pinned a
  *different* test (still 0/20), so the "bank has grown" hypothesis was explaining a contradiction
  that never existed. What AUD-L-17 actually did was **unmask** this flake, by stopping the runtime
  leak check from firing so the mock's hint was served for the first time.
  **Strong negative results, all with positive controls** (D-101 §5's lesson, which recurred
  immediately — the first live log scan reported zero for strings that are demonstrably present,
  because `filter-log-events --max-items` paginates): the token layer held on **every** axis
  (anonymous, expired, bad-signature, `alg:none`, wrong-audience in all three directions → 401 on
  every authenticated route in both apps, 13 caller shapes × 24 routes); cross-caller isolation
  held on **all 18** learning routes wherever `resolve_target_student` is actually called, so the
  failures are missing calls, not a broken helper; the interrupt-resume path is **stricter** than
  the rest of the app and is the pattern to copy; SSE `?token=` is not a weak spot and the token
  never reaches logs; idempotency holds everywhere it was implemented; all **1,552
  `checkpoint_writes` + 181 `checkpoint_blobs`** staging rows deserialized and walked as objects
  showed zero PII, with local dev as a positive control reproducing AUD-C-03 by a different method.
  **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **513 passed / 2
  skipped**, run **three consecutive times** after the probes were removed. Test count unchanged —
  the audit's probes were deliberately not left behind as tests (S37's precedent).
- **S37 shipped ⏸ partial, 2026-07-25 (D-101): AUD-C, 16 findings (AUD-C-01..16), three P1.**
  **⏸ not ✅:** two sub-items of the roadmap line are not met as written — "every degraded/refusal/
  empty response shape **actually rendered**" was done by enumerating all 14 shapes against the
  render code (finding two broken ones) rather than by rendering a page, and "reconnects" was
  exercised programmatically rather than by dropping a real SSE connection. No browser automation
  exists in this environment. **This is the same gap S36 left**, so the browser-driven half of §2.3
  is now uncovered for both apps; fold it into S39 (AUD-F), which already owns scripted journeys
  with console/network capture.
  Traceability over SPEC §5.19–§5.24/§5.25.3/§5.29/§5.30.2/§5.30.4, defect-pattern sweeps,
  API-level adversarial runs, and a bounded **live-staging** pass. Retrieval quality measured
  **twice** — mock and real Bedrock (Haiku 4.5 + Titan v2, **76.7¢, 13m17s**). Test *count* is
  unchanged at **513 passed / 2 skipped** (was 513/1): the coverage eval is still one test, now
  scoring 61 fixture cases instead of 40, and the new paid runner is the second skip. The audit's
  own probes were deliberately not left behind as tests — they belong to the findings, and the
  regression tests for them land with the Phase 0B fixes.
  **The headline is that the golden Q&A eval was measuring the mock, and its 100% scores were hiding
  real defects.** Against a real model the same fixture scores `grounded` **11.1%** (was 100%) and
  `role_gated` **0%** (was 100%) — not because retrieval is bad, but because a real classifier
  correctly refuses 10 of those 14 cases *before retrieval runs*: they are keyword lists
  (`"Baton Rouge Carver Public Library Terrace Street Saturday hours"`) and nonsense markers
  (`"zqxveval1 handbook"`), written that way on purpose to survive the mock's word-overlap reranker.
  The newly added `no_answer` set inverts it — **0/8 mock, 8/8 real** — because the mock always
  answers from the first chunk with confidence 0.8, so it can never decline. The fixture now has
  `paraphrase`, `no_answer`, `adversarial` and `role_gated_question` categories, scoring moved to
  `packages/evals/qa_coverage.py` so both runners compute identically, and the quality categories are
  **measured, not gated** — no threshold was invented before the first measurement.
  **Three P1s.** **AUD-C-01:** `POST /messages` has no thread-ownership check *and* an anonymous turn
  rewrites `user_external_id` to `None`, disabling the checks `/respond` and `/stream` do perform —
  **verified live on staging**: an unauthenticated caller continued a tutor's thread, got the tutor's
  answer and citation back, and resolved its interrupt (all 200). Locally, tutor-audience text
  reached the anonymous response verbatim. Logged not fixed (§2.4 reserves mid-audit fixes for P0s);
  the P0 argument is in D-101, and its two halves must be fixed together with AUD-C-04.
  **AUD-C-02:** the `SCOPE_AND_INTENT` prompt omits SPEC §5.19.4's *first* supported topic
  ("IntelliChoice organization"), so live staging refuses **"What is IntelliChoice?"** as out of
  scope, 5/5 — invisible to every test because the mock's keyword tuple contains `"intellichoice"`.
  **AUD-C-03:** the locator's precise coordinates persist in `checkpoint_writes.__resume__` after the
  turn and after two more turns, with nothing purging them, against a consent notice that promises
  verbatim not to store them — D-045 called this "briefly" and called removal infeasible; both are
  wrong, and a targeted delete works.
  **Also found:** **AUD-C-06** §18-C3's access-aware refusal fires **0 times in 8** under a real model
  (its precondition is zero-row retrieval, which real hybrid search never produces); **AUD-C-04** a
  paused turn returns the *previous* turn's answer/citations and `ics_content` sticks forever;
  **AUD-C-07** an embedding failure or exhausted budget on the retrieval path is an unhandled 500;
  **AUD-C-08** a Bedrock outage answers every in-scope question with the out-of-scope refusal;
  **AUD-C-09** §5.21.3's `academic_year` predicate is never applied; **AUD-C-10** any API error leaves
  chat-web stuck on `Thinking…` forever (a §2.6 criterion-3 blank state); **AUD-C-11** the no-source
  refusal ships *with* citations attached.
  **The strongest negative result:** pre-retrieval role/branch/date filtering held for all five
  audiences against the **real** corpus, run twice — once as-is and once inside a rolled-back
  transaction with the 2026-08-01 date gate opened so the 19 gated real documents went live. No role
  ever retrieved outside `{public, its own tier}`; draft, future-dated, expired and other-branch
  chunks were each individually excluded. Only `academic_year` failed.
  **One method lesson (D-101 §5):** the first coordinate probe used `CAST(blob AS text) LIKE` and
  reported clean — checkpoint blobs are msgpack, so that check cannot see a float and would have
  certified a database full of coordinates. §2.6 criterion 9 is exactly the criterion a badly-shaped
  grep appears to satisfy.
  **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **513 passed /
  2 skipped**. **Not covered:** LLM-judge answer quality, multi-turn context (`standalone_query` is
  still always `query` — a pre-existing carry-over), and browser-driven runs — no browser automation
  exists here, so the frontend findings are code enumeration plus API evidence, not a rendered page.
  **Cost:** 76.7¢ for the full paid eval plus ~25¢ of targeted diagnostic re-runs.
- **Superseded next-session line (kept for the record): S37 (AUD-C, chat product correctness)** — or, if you want AUD-L fully closed
  first, the **browser-driven adversarial runs + the live-staging half of §2.3**, which are the
  only AUD-L areas still uncovered (list below). **AWS is authenticated** (IAM user
  `jeongsik-staging-admin`, re-authenticated 2026-07-25), so the live half is unblocked, not
  blocked. To obtain a staging token: fetch
  `intellichoice-staging/{learning,chat}-api/staging-token-shared-secret` from Secrets Manager
  into a shell variable — never echo it — and send it as `X-Staging-Token-Secret` on
  `POST /dev/token`. The two secrets are per-app and deliberately not interchangeable.
- **S36 continuation shipped, 2026-07-25 (D-100): the four uncovered AUD-L areas are now
  covered.** §3.4's scoring/re-grade/policy-snapshot remainder, §3.5's mastery + hint ladder +
  generation pipeline + memory work, and **all of §3.6**. Eight findings logged
  (**AUD-L-10..AUD-L-17**), AUD-L-08's reachability corrected, one fix applied, and a large
  negative-results section recorded. Tests **510 → 513**, all green.
  **The P1 worth reading is AUD-L-10: the server marks an exam item `answered` and then accepts
  more answers for it.** Idempotency is keyed on `(session, variant, Idempotency-Key)` and the
  frontend mints `crypto.randomUUID()` per submission, so SPEC §5.9.2's idempotency key can
  never match a prior submission and is **inert for the purpose the spec cites it for**. Two
  answers to one item produce two graded attempts — and scores are attempt-counted
  (`max_score = len(pre_graded)`), so one changed answer rescores a 10-item exam as **10/11**
  and silently removes the `not_applicable_pre_max` flag. Changing an answer from wrong to right
  *lowers* the score. The invariant is enforced only in `ExamScreen`, through
  `currentOverviewItem?.status === "answered"` — optional chaining that defaults **permissive**
  when the overview hasn't loaded — with `busy={false}` hardcoded at all six screen call sites so
  there's no in-flight guard either. Logged not fixed (§2.4 reserves mid-audit fixes for P0s);
  the P0 argument is recorded in D-100 since the only thing keeping it out of that bracket is the
  absence of users. **Fifth instance of this project's recurring class** — the first four
  (D-096, D-085, AUD-L-02, D-097) were fail-open *defaults*; this is a fail-open *location*.
  **§3.6 could not start against the existing database:** every learning table except
  `student_reports` and `stage_transitions` had **zero rows** (268,793 checkpoints, 43,375
  variants, not one assessment session). So four complete journeys were driven through the real
  local API — improving 3→9, flat 6→6, regressing 8→4, pre-max 10→9 — and every number was then
  recomputed with SQL that never calls the code under audit. **Two findings are only visible with
  real rows** (AUD-L-14/15), and one *contradicts* a prior conclusion reached from fabricated
  inputs: **AUD-L-08 is reachable.** −200% `normalized_gain` with `status = NULL` came out of an
  ordinary 8→4 journey, and the `> 1` case is reachable via AUD-L-10 because the "post length
  always equals pre length" invariant is true of *item* counts while the math divides by *attempt*
  counts.
  **Also found:** **AUD-L-12** `recommended_difficulty` is computed correctly, stored, displayed —
  and routes nothing; it's unpacked as `_` and dropped, while two docstrings claim it seeds
  `starting_difficulty` (a student whose weakest skill recommended tier 4 was served tier 5, the
  tier they'd just failed) — masked entirely by the D-060/A6 1:1 skill↔difficulty bank.
  **AUD-L-13** memory consolidation verifies evidence provenance and cross-session repetition but
  never the claim against the `mastery.weighted_score` in the same transaction: a `strength` fact
  coexists with measured mastery 0.0, and across four journeys **all 20 facts are `strength` with
  zero `weak_skill` facts** — including for the student who regressed 8→4. **AUD-L-14**
  `time_spent_minutes` sums client telemetry and ignores the always-populated
  `assessment_attempts.response_time_ms`: 140 item-state rows summing to **0 ms** against 41,250 ms
  of real response time per exam, shown as `0.0` beside `attempts_count: 26` **inside
  `verified_facts`**. **AUD-L-15** mastery excludes the post-exam by construction while "skills to
  strengthen" is post-exam-derived, and both appear in one payload labeled "all time" — one skill
  reads mastery **1.000** *and* "needs work". **AUD-L-11** an unhandled 500 from
  `UnknownQuestionVariantError`. **AUD-L-16** both policy snapshots are write-only.
  **D-097's flake diagnosis was wrong, and that's the transferable part.** It recorded the hint
  flake as ~1-in-4 and prescribed "seed the fixture's RNG" — but **no fixture RNG exists**
  (`_turn_context` builds `random.Random()` per request inside the handler) and the rate was
  **8/60 (13%)**, measured before touching anything. Real cause: `MockBedrockProvider` prefixed its
  hint with `Level {level}`, and the runtime leak check reads a bare `1` as the answer for the ~6%
  of variants whose answer is `"1"` — the mock's own boilerplate made the mock's own hint unusable.
  Fixed to `Hint L{level}` (**60/60** after, 52/60 before) and pinned by a new deterministic guard.
  Measuring first cost ~4 minutes and changed both diagnosis and remedy.
  **The stretch goal was not reached:** the browser-driven adversarial runs (refresh mid-exam,
  concurrent tabs, expired timers, dropped SSE) and the live-staging half of §2.3 are still
  uncovered. API-level adversarial probing *was* done and is what produced AUD-L-10 and AUD-L-11.
  **§2.6 criterion 1 is closer but not met** — and criterion 2 now has an open P1.
  **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors),
  **513 passed / 1 skipped**; the previously flaky test run 60× standalone with zero failures.
  **Carry-over:** five `aud-student-*` accounts + `aud-parent` were added to **local dev MySQL**
  (deliberately outside the seed fixture set, since `seed()` deletes only fixture students'
  attendance and would have reverted them mid-audit) — local-only and disposable.
  `question_variants` is now **43,375** (was 42,023) and `checkpoints` **268,793** (was 264,475).
- **Superseded status line for the S36 continuation (kept for the record)** — see D-097 + its addendum and the
  new [docs/AUDIT_FINDINGS.md](AUDIT_FINDINGS.md). **Phase 1 is now applied, deployed and
  live-verified**, so the continuation session starts directly on the uncovered audit phases
  (listed below) with a working authenticated path against live staging.
  **How to obtain a staging token** (the continuation session will need this): fetch
  `intellichoice-staging/{learning,chat}-api/staging-token-shared-secret` from Secrets
  Manager into a shell variable — never echo it — and send it as `X-Staging-Token-Secret` on
  `POST /dev/token`. The two secrets are per-app and deliberately not interchangeable.
  **Merged to `main`** (`1eb125a`, fast-forward, CI green). The running image is
  `gha-d1899a483d06`, one docs-only commit behind `main` — no code or Terraform drift, so a
  deploy from `main` now reproduces what staging is running.
- **Pre-discovery pass over the production repos (2026-07-25, D-099) answered four of the S42
  asks and cut the slowest one entirely.** The user pointed at `IntelliChoice-web/`; most questions
  turned out to be answerable from `icrest` plus its existing `docs/codebase-analysis/`.
  **The biggest result: I11 rung 1 (API-only) is confirmed viable**, because
  `GET /api/accounts/signups` really does return `attended` (the `Signup` include carries no
  `attributes` restriction; past sessions come back with `required: true`) and its background-check
  gate exempts exactly the `Student`/`Parent` roles we issue at launch. Per I11 that rung needs no
  ask at all, so **the read-only DB account and private network path are off the critical path** —
  still documented fallbacks, no longer requests.
  **Answered:** the four role strings (`Parent`/`Student`/`Tutor`/`Manager`, free text, no DB
  constraint); and the timezone convention, which upgraded from a question into a **decision for the
  org** — storage is UTC, but reports apply a *hardcoded fixed UTC−6* in three queries, i.e. US
  Central Standard Time, so for the ~8 months Central observes DST their reports render session
  times **one hour earlier than reality**. **Corrected same day:** I first wrote that this
  mis-dates late-evening sessions; checking the arithmetic against `America/Chicago` shows the date
  only breaks for sessions starting 00:00-00:59 local, which a K-12 org essentially never has — so
  the real symptom is a one-hour display discrepancy, and the severity is lower than first recorded.
  Still worth a decision (which convention our apps match), just not the alarm I first raised.
  **Two new traps for S43, both easy to get wrong:** `signups` has a *second* attendance column,
  `attendanceClaimed` (non-null, self-reported) alongside `attended` (nullable, manager-recorded) —
  the convenient one is the fail-open one, and only `attended === true` may gate an exam; and the
  signups response is **PII-bearing** (`firstName`, `lastName`, full `children`), so the adapter must
  project at the boundary before anything is returned, logged, traced or cached.
  **Still unknown:** where MySQL runs and whether AWS can reach it (confirmed *undocumented* — no
  CI, IaC, deploy script or host reference anywhere), API reliability (no metrics/error-tracking/
  uptime monitor exists, so no data exists to ask for), and DNS ownership.
  `db.config.js`, the Gmail service-account key, and `data.sql` were deliberately **not opened**
  (credentials, and a dump that may carry student PII).
- **S42's Tier 1 org asks are drafted** in a working file kept **outside this repo**
  (`docs/S42_ORG_ASKS.md`, gitignored — an outbound communication draft, deliberately never
  committed), ready for
  the user to review and send. Not sent — I can't, and two judgment calls are flagged in the
  file: whether to include the paragraph disclosing that write-capable DB credentials sit in the
  production repo (true and material, but it may land better in conversation than in a
  forwardable email), and whether to ask now for the possibly-unneeded read-only DB account
  (I11's ladder says descend only as far as discovery forces, but provisioning is where weeks
  disappear). Drafted early on purpose: these items are blocked on other people, so their clock
  runs whether or not anyone is at the keyboard, which is the one thing on this backlog that is
  true of.
- **All four open audit dispositions are decided (D-098), none implemented — Phase 0B owns
  them.** The Phase 0B backlog therefore has these concrete, already-decided items, on top of
  the seeded known-issues list: **AUD-L-04** a `semantic_memory` retention job + `make
  memory-purge`, folding in the `stage_transitions`/`student_reports` retention already on
  carry-over, all on the EventBridge schedule, plus a §6.1 privacy-notice line that doesn't
  imply deleting chat removes what was derived from it (before the gate); **AUD-L-03** fold
  out-of-band `pre_intro`/chat spend back into the checkpoint's `bedrock_spend_cents`, settling
  what D-073 and D-075 both left open — accepted knowingly, since AUD-L-02 showed what an
  approximately-right ceiling costs; **AUD-L-09** a directional grounding check plus a narrower
  per-stage evidence dict, with a code comment stating plainly that neither makes the check
  sound; **AUD-L-06** delete `tutor.generate_hint` and its three tests. AUD-L-05 and AUD-L-01
  stay open as mechanical one-fix items; AUD-L-07 keeps D-086's existing disposition (formal
  resolution at S46, blocked until S43's adapter exists).
- **Phase 1 shipped live, after one real defect that only the live run could find.** The
  first deploy (run `30126765810`) was **fully green on every step** — including the extended
  security gate, the canary bake, and the smoke test — and shipped a **working endpoint that
  issued unusable tokens**: `/dev/token` returned 200 while every authenticated route
  rejected the JWT with 401. Both handlers built a bare `FakeTokenIssuer()`, which signs with
  the public `DEV_JWT_SECRET` constant, while the verifier has been settings-driven since
  D-085 and uses the real per-app Secrets Manager secret. Locally and in CI both sides *are*
  the dev constant, so all 509 tests agreed by coincidence. Fixed (pass
  `settings.jwt_signing_secret` to the issuer in both apps) and pinned by a regression test
  that uses a non-default secret and asserts both directions — verifies under the configured
  secret, and does **not** verify under `DEV_JWT_SECRET`, since otherwise D-085's secret
  would be decorative. Redeployed and re-verified.
  **The generalizable lesson, recorded in D-097's addendum:** every gate this pipeline has —
  `/healthz`, `/readyz`, the security gate, the canary bake, the smoke test — is a liveness
  or negative check, and all of them passed while the feature was inert. **A green deploy
  proves deployment, not function.** Closing that is S39/AUD-F's scripted-journey work.
- **S36 (AUD-L, learning product correctness) is PARTIAL, 2026-07-24** — see D-097 for the
  full record. Four of seven planned phases completed; **one P0 found and fixed**, six other
  findings logged, and a deliberate set of negative results recorded.
  **Decisions taken at session start, both by the user:** D-096's open staging-auth question
  was answered with a **secret-gated staging token path** (a 64-char random secret in Secrets
  Manager, presented as `X-Staging-Token-Secret`, `hmac.compare_digest`, 404 on failure,
  empty by default so local dev/CI/tests and any future production deployment are
  unaffected) rather than pulling S44's real issuer forward (its architecture depends on S42
  discovery data that doesn't exist) or auditing locally with a weakened §2.6 criterion 3
  (which forfeits the premise §2.1 rests on). Audit breadth was set to full-breadth
  risk-ordered; that choice was right but the estimate was wrong — the session ran out after
  four areas.
  **P0, found and fixed in-session (AUD-L-02): `POST /students/{id}/report` had no cost
  ceiling of any kind.** The gateway enforces its per-session budget against a
  `session_spend_cents` value the *caller* supplies, and this caller supplied nothing,
  relying on a `= 0.0` default — so the check evaluated `0.0 + worst_case > 50.0` on every
  call and never fired. The endpoint has no idempotency key (one fresh Bedrock call per
  click), so the only remaining limit was the global per-IP request cap raised to 6,000/60s
  in S34 for an unrelated reason. At the deployed model's real rates that permits **~$27 a
  minute from one IP holding one valid token**, with the AWS Budget alarm — a lagging
  notification — as the only backstop. Fixed by mirroring S24's existing chat precedent: a
  `get_spend_cents_since` window query (no migration — `student_reports` already stores
  `cost_cents`/`created_at`), `DAILY_REPORT_COST_CEILING_CENTS = 50.0` checked before the
  call, and on exceed a degrade to the deterministic facts-only template the
  gateway-failure/failed-grounding paths already produce. **The generalizable half:**
  `session_spend_cents` is now *required* on both `generate_student_report` and
  `generate_stage_narrative` — a cost parameter with a permissive default is a fail-open
  default, this project's fourth instance of that class after D-096's `ecr:DescribeImages`
  check and D-085's environment-string gate. Removing it surfaced all five call sites that
  had silently depended on it.
  **The finding most worth reading is AUD-L-04 (P1):** D-072 accepted that names survive
  free-text redaction (only email/URL/phone are matched), and that acceptance was bounded by
  the text living in `tutor_chat_messages` — **the only table in this codebase with a
  retention job**. S25 then derived `semantic_memory.fact_text` from that same text, screened
  with the same insufficient patterns, into a table with **no purge**, and those facts flow
  outward into tutoring payloads and parent-visible reports. An accepted risk lost its
  mitigation without anyone deciding to remove it — D-072 reasoned about a purged table,
  D-074 about consolidation quality, and neither records this. Needs a decision, not just a
  fix; recommendation is a `semantic_memory` retention job plus a note in the §6.1 privacy
  text, since "we delete chat after 90 days" is otherwise misleading.
  **Also logged, not fixed** (the audit's own rule — Phase 0B owns fixes, P0s excepted):
  **AUD-L-07 (P1)** D-086's tutor/branch_manager scope gap is unchanged but reaches further
  than its record describes, since S28's dashboard/report routes arrived after it was written
  — a tutor token can read any student's data and generate reports about them (one shared
  function, so one fix closes all 17 routes); **AUD-L-05 (P2)**
  `MemoryConsolidationPayload` was never added to the PII-floor allowlist test, contrary to
  D-072's own "How to apply" clause; **AUD-L-03 (P2)** `pre_intro` spend is never folded back
  into the session total; **AUD-L-06 (P3)** `tutor.generate_hint` is dead code omitting the
  leak check its live sibling applies; **AUD-L-01 (P3)** a gated-off `/dev/token` still
  discloses its existence via 422/405, and the S35 gate's stated rationale for trusting a 404
  is factually wrong about the code — it works only because it happens to probe with a valid
  body, and nothing recorded says it must.
  **Negative results recorded deliberately** (an audit whose output is only its defects can't
  be told apart from one that stopped early): no Bedrock call anywhere bypasses the gateway;
  every other one of 20+ `session_spend_cents` call sites passes a real accumulated value;
  all 17 learning routes enforce authorization and session-scoped routes correctly key it off
  the *checkpoint's* student id, not anything client-supplied; the SSE `?token=` path verifies
  audience and ownership including for a student-less session; **the S23/D-071
  checkpoint-overwrite bug class does not recur in the learning app** (both explicit `None`
  writes are correct precisely because they erase); finalize is genuinely idempotent at both
  the flow and route layers.
  **Phase 3.5 (SPEC conformance) partially covered**, after the deploy freed up time:
  learning-gain math verified against §5.13.3 formula-by-formula (both formulas literal, all
  12 stored fields present, `not_applicable_pre_max` handled) with one finding, **AUD-L-08
  (P3)** — `normalized_gain` is unbounded and takes its denominator from the pre *attempt
  count*; measured 133%, 600% and 1000% outputs from the real function, all reported with
  `status=None`, and confirmed unreachable today only because `build_post_exam` iterates the
  pre items one-for-one. Retry ladder verified against §5.11.7 exactly, including the
  `target_skill_id`/`skill_id` distinction that makes the prerequisite drop keep the original
  line's attempt counter (I expected a bug here and there isn't one — recorded as a negative
  result because it reads like one). Outcome labels: all six §5.11.7 finals produced with
  most-revealing-first precedence. **AUD-L-09 (P2)** — numeric grounding verifies a number's
  provenance but not its attribution, so "your score fell from 6 to 4" passes for a student
  who went 4→6; bounded by the facts-only fallback and by `verified_facts` being displayed
  alongside, but this is the last check between an LLM and a parent.
  **Question bank measured, not assumed:** 1 topic, 5 skills, 50 templates, all
  approved/active, 10 per difficulty — sufficient for exam construction with 5× headroom, but
  exactly one skill per difficulty, so skill and difficulty are perfectly collinear and no
  test on this data can separate them (the known A6/D-060 gap, now quantified).
  **Two carry-overs re-measured and materially worse:** `question_variants` at **42,023 rows
  / 1,559 on the worst template** (S23 recorded 610); `checkpoints` at **264,475** (S34
  recorded 249,250).
  **Still not covered:** the rest of 3.5 (mastery bootstrap, the full hint ladder end-to-end,
  the generation/validation pipelines themselves, memory effects on tutoring payloads beyond
  the PII path); **all of 3.6** (independent recomputation of dashboard/report numbers from
  raw rows against what the API and UI show); and the **scoring/re-grade-consistency and
  policy-snapshot** parts of 3.4. **§2.6 criterion 1 is not met by this session.**
  **Tests (+12 net, 497→509, stable across 3 repeated `make test` runs):** 9 for the
  staging-token gate (4 learning incl. a 3-case parametrization and a no-secret-configured
  case, 4 chat, plus the positive paths), 3 for the report cost ceiling.
  **Tests are 510 after the auth fix's regression test** (497 -> 510 net).
  **Verification:** `make lint && make typecheck` clean, `terraform fmt`/`validate` clean,
  workflow YAML parse-checked, 510 passed / 1 skipped. **Live-verified against real staging**
  (not just the workflow's own report): both services on task-definition revision 16, 1/1;
  `POST /dev/token` -> 404 for both a no-credential and a wrong-credential probe on both
  CloudFront distributions; -> 200 with the correct per-app secret; **chat's secret rejected
  by learning-api** (404), so the two secrets really are not interchangeable; and a minted
  token now authenticates a real `GET /me` request. The Terraform apply was verified
  independently too: both secrets created, both task-definition families at revision 14 with
  the secret wired, all six ARNs present in the execution role's `ReadAppSecrets` policy, and
  the services untouched on revision 13 until the deploy moved them.
  **Carry-over beyond the audit phases:** [docs/INTEGRATION_PLAN.md](INTEGRATION_PLAN.md) is
  **untracked and not gitignored** despite ROADMAP/PROGRESS/CLAUDE.md all pointing at it, so a
  fresh clone loses Milestone 9's reasoning; `knowledge-content.zip` is also untracked and
  probably should not be committed at all.
- **Superseded context for S36 (kept for the record)** — the first of Phase 0A's
  four audit sessions, now scoped in `docs/ROADMAP.md`'s new **Milestone 9** (added this
  session from `docs/INTEGRATION_PLAN.md` §5, which is the detailed source for everything
  S35-S51). **One decision must be made at S36's session start, before any audit work:**
  closing the `/dev/token` P0 (below) leaves live staging with **no usable authentication
  path at all** - real auth doesn't exist until S44 - so S36-S39's adversarial end-to-end
  runs and §2.6's criterion 3 ("every launch journey passing twice consecutively against
  live staging") cannot be executed as written. Three options are laid out at the end of
  D-096; none was chosen, because it's a real trade-off between audit fidelity and
  re-opening auth surface on a public endpoint.
- **S35 (Restore the deploy pipeline) shipped, 2026-07-24** — see D-096 for
  the full diagnosis and every finding. **The ten-attempt Alembic blocker is fixed and the
  deploy is functionally restored:** both services run task-definition revision 12, 1/1,
  both ALB target groups `healthy` under the new `/readyz` check (which pings Postgres
  *and* MySQL, so healthy targets prove real connectivity to both from both apps), no
  errors in either app log. The real error, finally read, was
  `InvalidPasswordError: password authentication failed` - every S34 SSL fix had worked;
  applying D-092's `manage_master_user_password` had rotated the master password into RDS's
  managed secret while `ops-task` still injected the old, now-dead one. **S34's sequencing
  was inverted:** it withheld the apply until a deploy succeeded, but the apply is what
  rewires every consumer to the managed secret, so the deploy could never succeed first.
  The withheld Terraform is now applied (alarms, autoscaling, circuit breaker, per-app JWT
  secrets, old-secret cleanup).
  **P0, live for two days: `POST /dev/token` was reachable on both public CloudFront
  distributions** (returned 422, not 404 - the endpoint existed and was processing input,
  so anyone could mint a token for any role and any student). S33/D-085 records this as
  closed, and it was - in gitignored `terraform.tfvars`, in one working tree, with the
  apply withheld. Nothing tied config-level intent to deployed reality. Now closed
  (verified 404 through both distributions) **and** guarded by a new post-deploy step in
  `deploy-staging.yml` that asserts it live and fails the deploy otherwise.
  **Two hazards caught in the withheld plan before applying it**, either of which would
  have caused an outage: `terraform.tfvars` pinned a pre-`/readyz` image while the same
  apply flipped the health check *to* `/readyz` (bumped to `gha-6cc4a27430bd`); and
  `ignore_changes = [task_definition]` means the apply never moves the services, so
  **apply and deploy are one operation** - between them staging really did serve 503 with
  both targets unhealthy.
  **The deploy pipeline could never be re-run on an unchanged commit** (SHA-derived tag +
  immutable ECR tags), which made the normal repair loop structurally impossible; D-095
  hand-deleted tags to work around it and it recurred immediately. Fixed to reuse an
  existing image for the same commit. **A fail-open bug in that fix** was caught before it
  mattered: it used `ecr:DescribeImages`, an `implicitDeny` for the deploy role, with
  `2>/dev/null` - so a permission error and an absent image were indistinguishable and the
  step would have been decoration that appeared to succeed. Rewritten on `batch-get-image`
  (permitted) and to exit non-zero rather than assume.
  **Credential-exposure gap closed:** `*.tfstate` was gitignored but `*.tfplan` was not,
  and a plan file is a zip containing a full cleartext copy of state - one was sitting
  untracked and committable under `terraform/environments/staging`.
  **A third gate failure, worth recording:** the first run after the P0 fix ended red at the
  new security gate itself - `cloudfront:ListDistributions` isn't granted to the deploy
  role, so it couldn't resolve the domains to probe. It failed *closed* (an unresolvable
  domain is a failure, not a pass), which is exactly why this surfaced as a red run instead
  of a false green. Fixed by hardcoding both domains in the workflow's `env:`, matching the
  file's existing convention for infrastructure ids.
  **Fully green end-to-end, run `30121887429` from `cad4e54`: this project's first
  completely successful deploy** (13m22s, every step, `conclusion=success`), with CI green on
  the same push. Independently re-verified afterwards rather than trusting the workflow's own
  report: both services on task-definition revision 13 (1/1), both ALB target groups
  `healthy` under `/readyz`, all 4 CloudWatch alarms `OK`, `POST /dev/token` -> 404 and both
  frontends -> 200 through both CloudFront distributions. Migrations passed on **two
  consecutive runs**, so the fix is repeatable rather than a one-off. Newly exercised live for
  the first time ever: the `/dev/token` security gate (`OK` for both apps), S34's canary bake
  (`No alarms breached during the bake period`), the frontend build/S3-sync/CloudFront-
  invalidation steps, and the smoke test. The rewritten ECR check also behaved correctly
  against the deploy role's real permissions (`needs a build for gha-cad4e54ee885` for both,
  no permission error).
  **Carry-over:** the SNS alarm email subscription **was** `PendingConfirmation` and is now
  confirmed and active (`PendingConfirmation: false`), so alarms can reach the inbox. §2.6's
  criterion 8 is still open, though: a confirmed subscription is necessary but not
  sufficient - it needs an *induced* alarm proving end-to-end delivery, which is S39's
  operations-audit work. The
  applied `terraform.tfvars` values live only in a local working tree (gitignored by
  pre-existing convention; real state is in the S3 backend, so reality is recoverable, but
  a fresh clone would need them re-supplied). `AmazonBedrockMantleFullAccess` on the admin
  group is vestigial after D-084's addendum abandoned Mantle - small least-privilege
  cleanup. Real load testing against live staging (S34's carry-over) is now unblocked.
- **Roadmap past S34 is now scoped**: `docs/ROADMAP.md` gained **Milestone 9** (S35-S51:
  deploy restoration → four audit sessions → stabilization → the §2.6 gate → integration
  discovery/adapter/auth/consent → rollout), derived from `docs/INTEGRATION_PLAN.md`, which
  holds the detailed reasoning (immutability constraint, boundary tiers, incompatibility
  catalog I1-I15, auth options O1-O4, residual risks R1-R7). Milestone 8 (S32-S34) is
  otherwise all shipped. The other long-standing carry-overs (WAF, backup-restore test, ZAP
  scan, RBAC gap D-086) are folded into that plan's Phase 0B and A7 tracks.
- **S34 (Load testing and production readiness) shipped, 2026-07-24** — see D-095 for
  the full design, every real finding, and what's translated vs. built vs. deferred. User
  chose full scope (both the locally-runnable load-test half and the canary-pipeline/
  Terraform half) in one session at session start. **No live AWS access this session
  either** (same expired `intellichoice-staging` SSO session as all of S33) - every
  Terraform/CI change is written and `fmt`/`validate`-clean but not `apply`'d or actually
  run; real staging-scale load testing is a carry-over.
  **SPEC §6.23 targets the EKS/Aurora/HPA/SQS architecture this project never built**
  (D-004/D-082/D-084's ECS Fargate divergence) - translated rather than built literally:
  "MongoDB timeout" tested as a Postgres/MySQL connection-loss drill (both are behind
  the new `/readyz`), "queue backlog" is N/A (no SQS/queue anywhere in this codebase).
  **New `load-tests/`** (k6 scenarios for concurrent learning sessions + chat Q&A,
  `sse_load.py` for concurrent SSE connections since k6 has no native SSE support,
  `loadtest_fixtures.py` for disposable synthetic students so VUs are distinct students
  rather than one student under artificial contention) - see its own README for the
  full SPEC-target-to-test mapping.
  **Two real production bugs found by a corrected k6 run (150 concurrent, one realistic
  flow per VU, no scripting artifacts) and fixed this session:** (1) a genuinely
  realistic 150-concurrent-session burst from one shared IP (this app's actual
  deployment context - branches share egress IPs) tripped the existing global per-IP
  rate limiter's 1,000 req/60s default well before every session finished, rejecting
  ~1,100 legitimate requests - raised to 6,000 (~3x the measured real burst, math in the
  config comment) in both apps; separately, none of those 429s were visible in the
  access log or Prometheus metrics at all, because the rate-limit middleware was
  registered last (Starlette LIFO stack order made it outermost, short-circuiting before
  logging/metrics ever ran) - fixed by reordering middleware registration in both
  `main.py`s. (2) `/healthz` never checked database connectivity, and the ALB target
  group health-checked it anyway - a real DB outage would never have made the ALB stop
  routing to a broken task. Fixed with a new `/readyz` (`intellichoice_shared.db_ready`,
  pings Postgres+MySQL, 3s timeout) that staging's Terraform now uses for the ALB health
  check instead; `/healthz` and the Docker `HEALTHCHECK` stay liveness-only on purpose.
  **Live-verified** via a new `load-tests/drills/db_connection_loss.sh` against the real
  local docker-compose Postgres: `/healthz` stayed 200 throughout a real stop/restart,
  `/readyz` correctly flipped to 503 and recovered on its own ~6s after Postgres
  returned, no app restart needed.
  **A third finding, a capacity ceiling not a bug:** the same k6 run measured ~2.9s P95
  latency (SPEC targets ~1s). Bumping the SQLAlchemy pool from bare defaults (15) to an
  explicit 20 (`pool_size=10, max_overflow=10`, sized against staging RDS's real
  `db.t4g.micro` connection ceiling, not unlimited) barely moved it (2.93s -> 2.77s) -
  the real bottleneck is `desired_count=1` with one uvicorn worker serializing all
  concurrent request handling on one process, not the connection pool. `pool_pre_ping=
  True` was added alongside it for a different, drill-motivated reason (a connection
  gone stale during a DB outage should be detected and replaced by the pool, not handed
  out and fail on first use). The real fix for the P95 gap is the new autoscaling below.
  **Verified, not fixed, because it was already fine:** went in expecting a concurrency
  gap in `ResilientBedrockGateway`'s circuit breaker (unlocked instance attributes) -
  a real concurrency test disproved it: asyncio's cooperative scheduling means exactly
  `circuit_failure_threshold` calls reach the provider even under a 30-way concurrent
  failure burst, not the whole burst. Kept as a regression test, a genuine negative
  result.
  **Verified, not built, because it was already built:** the external-tool-outage drill
  (SPEC's "MCP outage") already had real coverage from S14/S18 (Gmail send failure /
  Google Calendar failure both already degrade gracefully with dedicated tests) - just
  re-confirmed both still pass.
  **New Terraform, all unapplied (no AWS access):** `deployment_circuit_breaker` on both
  ECS services (automatic rollback if a new revision never becomes healthy) - the
  deploy-time safety net; a new post-deploy **canary bake** in `deploy-staging.yml` (not
  a true weighted traffic-split canary - `desired_count=1` means there's no second task
  to shift traffic to gradually, a deliberate solo-maintainer simplification over SPEC
  §6.24's full canary-pipeline shape) - sleeps 3 minutes after both services report
  stable, then polls 4 new CloudWatch alarms (per-service ALB 5xx rate + P95 latency,
  new SNS topic reusing the budget alarm's email-notification posture) and rolls both
  services back to their captured pre-deploy revisions on any breach - the runtime
  safety net for a revision that's healthy but quietly wrong. New `aws_appautoscaling_
  target`/`policy` (CPU-utilization target-tracking, 70%, min/max 1/3) - Fargate's real
  equivalent of SPEC §5.33.4's HPA, absent entirely before this session
  (`desired_count` was a flat fixed number). The P95 alarm threshold is 3s, not SPEC's
  aspirational ~1s - alarming below what this architecture's current shape can already
  meet would just teach the one human who'd see it to ignore it; closing that gap is the
  new autoscaling's job.
  **Tests (+5 net, 492→497, stable across 4 repeated `make test` runs, one interleaved
  failure was the pre-existing S22.5-documented unseeded-`random.Random()` flake,
  confirmed via an immediate clean standalone rerun, not caused by this session):** 4
  `test_readyz.py` (2 per app), 1 Bedrock circuit-breaker concurrency test.
  **Verification:** `make lint && make typecheck && make test` clean, `terraform fmt`/
  `validate` clean across the whole tree. Left ~150 `loadtest-student-N` MySQL rows
  cleaned up after use (`loadtest_fixtures.py --cleanup`); ~16,400 assessment-table rows
  the k6 runs generated in the shared local dev Postgres were cleaned up via a targeted
  dependency-ordered DELETE (unlike most prior sessions' "small enough to leave"
  footprint, this one wasn't). Did **not** attempt to clean the shared dev Postgres's
  `checkpoints` table (249,250 rows found, pre-existing, spanning many prior sessions'
  never-cleaned-up runs per the same "Newly observed"/S12 pattern documented repeatedly
  below - out of scope for this session, a systemic test-hygiene gap, not something S34
  caused).
  **Carry-over:** real load testing against the live staging ALB once AWS access
  returns (this session's k6/SSE runs were all local-only); the WAF/backup-restore test/
  ZAP scan carry-overs from S33 are all still open for the same reason. The D-086 RBAC
  gap (tutor/branch_manager per-student scope) is still open, still launch-blocking.
  ALB-request-count-based autoscaling (would react faster to this app's actual
  I/O-bound concurrency bottleneck than CPU-based) if CPU-based scaling proves too slow
  once real traffic exists. The long-standing `checkpoints`-table test-hygiene gap noted
  above is worth a dedicated future cleanup pass given its now-confirmed real size.
- **S33 (Security hardening) shipped, 2026-07-23** — see D-085 through D-094 for full
  design/verification detail. No live AWS access existed for this entire session (the
  `intellichoice-staging` SSO profile's session was already expired at session start and
  stayed expired throughout) - every Terraform change is written and `validate`/`fmt`
  clean but **not yet `apply`'d**; the user chose to deploy on their own timeline rather
  than treat it as urgent (D-085). Code/CI/docs changes are otherwise complete and fully
  verified locally.
  **The most consequential finding wasn't in the original SPEC §6.22 checklist** -
  auditing auth for the RBAC-audit item found `POST /dev/token` (a dev-only auth
  stand-in, meant to 404 outside `environment=="dev"`) was reachable on the real live
  staging ALB, because `terraform.tfvars` had deliberately set `app_environment="dev"`
  mid-S32 for real-browser testing - a real, already-documented, user-approved S32
  trade-off (not an unknown bug), with its own comment naming the exact revert
  condition ("before this environment is treated as anything more than an internal
  testing target"). S33 executed that revert, plus a second, independent gate
  (`dev_token_endpoint_enabled`) so the same mistake can't reopen it alone next time
  (D-085). The JWT signing secret's own hardcoded-public-constant fallback (D-006, safe
  when written, no longer true once a real ALB existed) was fixed the same way -
  settings-driven, real per-app random secrets in Secrets Manager.
  **RBAC audit (D-086) also found a real, structural gap, left as a launch-blocking
  carry-over at the user's own direction**: tutor/branch_manager have zero per-student
  scope check in `learning_api.authorization.resolve_target_student` - a known,
  deliberately-tested design choice from an earlier session (not new), blocked on a
  tutor-assignment/branch_manager-branch data model that doesn't exist in `ProfileAdapter`
  yet. Not independently exploitable today (no way to obtain a tutor/branch_manager token
  without the now-closed `/dev/token`), but must be fixed before real
  go.intellichoice.org tutor/branch_manager auth goes live.
  **Rate limiting (D-087)** generalized beyond the existing admin-escalation-only
  limiter - a new global per-IP cap on both apps - and found the *existing* limiter was
  already broken in the live deployment: neither Dockerfile passed Uvicorn
  `--proxy-headers`, so every real caller collapsed onto the ALB's own IP behind
  `Request.client.host`. Fixed in both Dockerfiles.
  **Fargate hardening (D-088)**: security groups audited and already correct (no
  changes needed - ALB/RDS/VPC-endpoint ingress all already least-privilege, permissive
  egress rules neutralized by the VPC's own no-NAT route tables); `readonlyRootFilesystem`
  now defaults true on both API services (confirmed safe - neither app writes to local
  disk at runtime).
  **Dependency + container scanning (D-089)**: new `.github/dependabot.yml` +
  `.github/workflows/security-scan.yml` (`pip-audit`, `npm audit` x2, Trivy image scans
  x2) - every tool run for real against this project's actual dependencies/images before
  being wired as a hard gate, all 0 findings. `aquasecurity/trivy-action` pinned by
  commit SHA, not a version tag, after a web search surfaced a real 2026-03-19 supply-
  chain compromise of that exact Action. Found `chat-web` has no CI job in `ci.yml` at
  all (pre-existing, not fixed - out of scope, flagged as a carry-over).
  **Prompt-injection test suite (D-090)** - new
  `apps/chat-api/tests/test_prompt_injection_eval.py`, closing the item S14/S24/S30 each
  deferred (`packages/evals/.../registry.py`'s "Prompt injection" `EvalItem` now has real
  `test_refs`). Found a real false-failure while writing it (not a defense gap) -
  naturally-worded adversarial queries spuriously matched real seeded content via the
  mock reranker; fixed with the existing "zqxv" nonsense-marker convention.
  **Data-deletion testing (D-091)**: new CLI-level test for `make chat-purge` (only
  repository-level coverage existed before); found and fixed a real test-writing bug
  (missing `session.commit()`), not an app bug.
  **RDS auto-rotation (D-092)** - user-confirmed native `manage_master_user_password`
  over a custom rotation Lambda. The real cost, discovered while implementing (not
  upfront): RDS-managed secrets are JSON-shaped, not a ready DSN, so every real DSN
  consumer needed a change, not just the two apps' `Settings` classes as originally
  scoped - `packages/db/engine.py`'s `create_engine()` fallback (used by every
  standalone CLI), `alembic/env.py`, and `seed_mysql.py` all gained the same
  component-based DSN assembly. Both RDS Terraform modules' `random_password`+manual-
  secret resources removed entirely.
  **Incident-response runbook (D-093)**: new `docs/INCIDENT_RESPONSE.md`, grounded in
  this project's own two real incidents (S32's credential leak, this session's
  `/dev/token` finding) rather than generic boilerplate.
  **ZAP baseline scan (D-094)**: not run (no AWS access all session) - `make
  security-scan-staging` is ready to run once access is restored.
  **Deferred, documented, not built this session** (D-002/D-025-style "no real creds/
  infra yet" posture, consistent with every prior session): AWS WAF (real cost/infra,
  user chose to defer), the backup-restore test (real, reversible, but real AWS
  resource creation/teardown - deferred alongside WAF), CAPTCHA (no real reCAPTCHA/
  hCaptcha creds), OAuth scope review (no real Google OAuth exists yet), a real
  professional penetration-testing engagement (ZAP substitutes partially), image-
  deletion testing (N/A - S29 deferred, no image-upload feature exists to test).
  **Tests (+22 net, 470→492, stable across 3 repeated `make test` runs):** 2 dev-token-
  flag regression tests, 4 `packages/shared/tests/test_rate_limit.py`, 5
  `test_prompt_injection_eval.py`, 1 `test_tutor_chat_purge_cli.py`, 3
  `packages/db/tests/test_engine_component_dsn.py`, 4+3
  `test_config_component_dsn.py` (both apps).
  **Verification:** `make lint && make typecheck && make test` - 492 passed, 1 skipped,
  stable across 3 repeated runs (one interleaved failure during iteration,
  `test_hint_reflects_the_students_actual_wrong_option`, is the pre-existing
  S22.5-documented unseeded-`random.Random()` flake, confirmed by an immediate clean
  rerun, not caused by this session). `terraform validate`/`fmt` clean throughout - never
  `apply`'d (no AWS access). A real `alembic upgrade head`/`downgrade -1`/`upgrade head`
  round-trip against the local dev Postgres confirms `alembic/env.py`'s changed URL-
  resolution fallback chain still resolves correctly when no component env vars are set.
  `terraform.tfvars` is gitignored in this repo (pre-existing convention, not introduced
  this session) - the `app_environment` revert (D-085) and other tfvars edits exist only
  in the local working tree; make sure they're not lost before this environment is next
  applied.
- **S32 (Deployment architecture decision + first deploy) shipped, 2026-07-22** — see
  D-084 for the full design, every real bug found and fixed live against real AWS (not
  in review), and the live-verification results; D-004 amended to "decided," no longer
  "proposed." Confirmed ECS Fargate + RDS PostgreSQL/pgvector + RDS MySQL over EKS/
  Aurora/managed-Mongo, corrected per D-082/D-083. New `terraform/` (10 modules +
  `environments/staging`), two `Dockerfile`s. A real `intellichoice-staging` AWS
  environment is live: VPC (single-AZ VPC endpoints, no NAT), ALB, ECS cluster running
  both services, both RDS instances (migrated + seeded), both frontends on S3+CloudFront
  with same-origin `/learning/*`/`/chat/*` path routing to the API (no CORS, no domain
  needed), real AWS Bedrock wired in (EULA accepted, closes D-025's "never exercised
  against real AWS" caveat for both `AnthropicBedrockProvider` and
  `TitanEmbeddingProvider`), an AWS Budget alarm. **Real credential leak found and
  remediated live**: `seed_mysql.py` printed the real RDS MySQL master password into
  CloudWatch Logs (and the session transcript) - password rotated immediately, log
  stream deleted, source fixed to redact before printing. Also found and fixed: a
  missing `cryptography` dependency that would have broken both real services' MySQL
  connectivity (not just the seed script - caught via a pre-deploy dry run); an
  ALB/CloudFront timeout ceiling shorter than the Bedrock gateway's own worst-case
  retry latency (real 504s hit live); several other real AWS-constraint surprises
  (Free Tier restrictions, a nonexistent RDS engine version, a security-group
  description character limit, an ALB/target-group 32-char name limit, arm64 vs
  Fargate's x86_64 default). GitHub repo creation and CI wiring were blocked on
  `gh auth login` at the time - **since resolved 2026-07-23, see below.** Custom domain
  (registration guidance given separately). Continued troubleshooting after initial wrap-up found two
  more real bugs (a second Bedrock PrivateLink endpoint the app's SDK actually needs,
  `bedrock-mantle` - and a distinct IAM namespace for it). **Superseded by D-084's
  2026-07-23 addendum**: Bedrock Mantle was ultimately abandoned account-wide after a
  live investigation found every flagship model on it (Claude Sonnet 5, GPT-5.6
  Sol/Terra/Luna) blocked by an AWS-Sales-only access gate unrelated to quota or IAM
  (confirmed by testing with `AmazonBedrockFullAccess`/`AmazonBedrockMantleFullAccess`
  directly attached to the task role), and Gemma 4 (which does work on Mantle) hanging
  on the app's real nested response schemas. **Claude Haiku 4.5 via classic
  `bedrock-runtime`** (the same surface `TitanEmbeddingProvider` already used) is what's
  actually live now - real quota, real access, ~1.5s responses, verified via real
  `bedrock_call` log entries from both apps through the live browser.
  **MySQL dev-fake swap shipped (off-roadmap, 2026-07-22)** — see D-083 and the
  session-log entry below; `MongoProfileAdapter` → `MySQLProfileAdapter`, live-verified
  against a real `mysql:8.4` container, plus a second real instrumentation-ordering bug
  found and fixed in the same family as S31's Pymongo one.
  **S31 (Observability) shipped** — see D-081 for the full
  design and the S31 session-log entry below; found and fixed two real instrumentation-
  ordering bugs via live verification against a running Jaeger (FastAPI and Pymongo spans
  both silently dropped when instrumented from inside `lifespan`).
  **S29 (Multimodal solution images) was deferred, not built**
  — the user declined at that session's own start, before any file was touched; see
  D-078 for the full reasoning (a real photo of a minor's solution work raises a
  privacy/consent question the spec doesn't resolve, and every supporting dependency —
  malware scanner, S3 encryption — is still on the D-002 "no real creds yet" footing, so
  that session would only stack fakes on fakes without answering the actual open
  question). ROADMAP's S29 entry stays in place as a design reference, marked deferred.
  **S30 (Evaluation platform) shipped** — see D-080 for the full design and the S30
  session-log entry below; found and fixed a real bug in the existing hint-leak check
  (D-079).
  **Roadmap restructured 2026-07-18 (D-049):** the expansion plan
  ([plans/2026-07-18-expansion-plan.md](plans/2026-07-18-expansion-plan.md)) is now
  ROADMAP S17–S28; the *old* S17 (Memory system) is now **S25**, old S18–S23 are now
  S29–S34. Session references in the log below and in older DECISIONS entries use the
  old numbering — D-049 holds the translation map.
- **Resolved 2026-07-23**: `gh auth login` done, GitHub repo created
  (`lucasjeongsikpark/IntelliChoice`, private, first commit), `ci.yml` fixed (was never
  run against real GitHub Actions before - missing DB service containers and seed/content
  steps, both found live) and green, GitHub OIDC deploy role wired,
  `deploy-staging.yml` written (`workflow_dispatch` only until it's been run once). See
  D-084's 2026-07-23 addendum. No longer a carry-over item.
- **S31 additions:** Observability (SPEC §5.32, Phase 20/§6.21) shipped — see D-081 for
  the full design (LangSmith forced-mask wiring, alert-rules-without-Alertmanager scope
  cut, the two live-verified instrumentation-ordering bugs and their fix). New
  `packages/observability` (`intellichoice_observability`): `logging_config.py`
  (structured JSON logs + a `PiiDenylistFilter` enforcing SPEC §5.32.3's denylist),
  `tracing.py` (OpenTelemetry SDK + `traced_span`/`traced_node` manual-span helpers),
  `metrics.py` (every SPEC §5.32.4 KPI as `prometheus_client` counters/histograms + an
  HTTP timing middleware), `request_logging.py` (JSON access log), `langsmith_config.py`
  (env-gated, no real account exists — D-002 posture). Both apps' `main.py` wired at
  startup (structured logging, `/metrics`, real Bedrock/DB/Mongo spans); KPI-recording
  calls added at existing service call sites (session starts, attendance gate, hint/
  solution/video usage, retry ladder, tutor-review flags, problem reports/quarantine,
  RAG answer/no-answer, email escalation, maps/calendar success, out-of-scope refusal) —
  instrumentation only, no new business logic. `docker-compose.yml` gained
  `otel-collector`/`jaeger`/`prometheus`/`grafana`, config under `observability/`
  (alert rules, 3 provisioned Grafana dashboards). **Resolves the standing D-032 caveat**
  (SSE `?token=` bearer values in access logs) — the new access-log middleware logs the
  route template only, and uvicorn's own raw access logger is disabled.
  **Found and fixed two real bugs via this session's own live verification against a
  running Jaeger, neither visible from unit tests (D-081):** `FastAPIInstrumentor`/
  `PymongoInstrumentor` both silently produce zero spans when instrumented from inside
  `lifespan` (each has its own "must run before some object is constructed/receives its
  first call" hazard — Starlette caches its middleware stack on the first ASGI call,
  which is the lifespan startup call itself; `pymongo.MongoClient.__init__` snapshots the
  global listener list at construction time). Fixed by moving both to module level,
  before `app = FastAPI(...)` and before any Mongo client exists; two new regression
  tests (`test_instrumentation_ordering.py`) encode the ordering contract directly.
  **Tests (+16 net, 452→468, stable across 3 repeated `make test` runs):** logging
  denylist/formatter tests, tracing nested-span/trace-id tests, metrics/KPI tests, access-
  log query-string-redaction test, LangSmith env-gating tests, the two instrumentation-
  ordering regression tests.
  **Verification:** `make lint && make typecheck && make test` — 468 passed, 0 lint/type
  errors, stable across 3 repeated runs. Live-verified against the real running
  `learning-api` dev server + the real compose observability stack (not just unit tests):
  a real `create_session → select_student → select_topic` HTTP flow produced one trace
  with `POST .../topics` (FastAPI) as root, `langgraph.select_topic` as its child, and 48
  real Postgres spans as *its* children, all one `trace_id`; a separate attendance-check
  call produced a trace with a real Mongo `find` command span correctly nested under the
  FastAPI root. Prometheus's `learning-api` scrape target reported `up` with real KPI
  values populated; Grafana auto-provisioned all 3 dashboards + both datasources,
  confirmed via its own API. JSON access logs confirmed no `?token=`/raw query string
  anywhere. Left a handful of real `assessment_sessions`/checkpoint rows for
  `student-ext-4` in the shared dev Postgres from this session's own live-verification
  flows (never reached `finalize_exam`) — same "useful seed data, small bounded
  footprint" reasoning prior sessions gave, not cleaned up.
  **Carry-over:** CPU/memory/pod-count metrics aren't built — no deployed container
  runtime exists yet to scrape them from (S32's decision, D-004). Alerting is rules-only,
  no real Alertmanager notification channel (no Slack/email/PagerDuty creds — D-002
  posture). LangSmith is wired but entirely unexercised (no real account — D-025/D-035's
  same posture); §5.32.1's self-hosted-vs-cloud contractual-review decision is still open.
  `otel_enabled`/`CHAT_OTEL_ENABLED` default to `False` — a real dev/staging run needs to
  set them explicitly (documented in `config.py`'s own comments).
- **S28 additions:** Progress dashboard and student report (SPEC §5.14.2–5.14.4, plan
  §12/§18-L9) shipped — see D-077 for the full design (branch-manager reuses the tutor
  field set with cohort aggregation deferred, `PARENT_REPORT` task reused for every
  audience, `verified_facts` fixed-shape-payload convention, chart palette choice).
  **Decide-at-session-start (user-approved):** branch-manager gets the tutor field set
  as a single-student stand-in rather than building a real student→branch roster/cohort
  aggregate this session (D-077 #1). New `packages/db` `DashboardRepository`
  (date-range-filtered SQL: learning gains, study attempts+items, assessment
  attempts+sessions, assessment time) + `learning_api/services/dashboard.py`
  (`build_dashboard` — pure-Postgres DTOs: mastery by skill, pre/post accuracy by
  skill, gains over time, accuracy trend, difficulty progression, hint/solution/video
  usage; no LLM). New `StudentReport` model/repo (one Alembic migration) — not
  idempotency-keyed, a fresh row per on-demand "Generate report" call. New
  `ReportInterpretationPayload`/`Response` (`packages/shared/bedrock.py`, reuses the
  existing `BedrockTask.PARENT_REPORT` slot) + `learning_api/services/report.py`
  (`build_report_facts` audience-gates the payload server-side from the caller's role;
  `generate_student_report` mirrors S26's grounding-check/facts-only-fallback pattern).
  Two new routes on `routers/students.py`: `GET .../dashboard`, `POST .../report` +
  `GET .../reports` history. New learning-web `StudentDashboardScreen.tsx` (replaces
  `ParentDashboardScreen.tsx` — same component now serves both student-self and parent
  views per the existing `dashboardStudentId` wiring) with 6 Recharts chart types + a
  date-range preset control, and `ReportView.tsx` (Verified/Interpretation/
  Recommendations, visually distinct sections). Added `recharts`+`react-is`
  dependencies. Chart palette follows the `dataviz` skill's validated reference
  categorical/sequential slots (not the brand's raw hues, which failed dark-mode
  validation) as local `--viz-series-*` CSS custom properties.
  **Found via this session's own Playwright verification, not previously known:** the
  S11 carry-over (parent auto-select doesn't set `student_external_id` client-side)
  also blocks a single-child parent from reaching the *new* dashboard through the real
  UI (`StartScreen`'s button needs `studentId` already known); not fixed (same root
  cause as the existing gap), worked around in verification by seeding
  `sessionStorage` directly — see D-077's closing note.
  **Tests (+16 net, 425→441, stable across 3 repeated `make test` runs):** 2
  `apps/learning-api/tests/test_dashboard.py` (date-range filtering, no-range =
  everything), 7 `test_report.py` (audience-gating pure-function tests + scripted-
  gateway gateway-failure/ungrounded/grounded fallback tests), 4
  `test_dashboard_report_endpoints.py` (HTTP wiring, role-based `verified_facts`
  gating, cross-student 403), 3 new `test_bedrock_payload_pii_floor.py` cases.
  **Verification:** `make lint && make typecheck && make test` — 441 passed, 0 lint/
  type errors, stable across 3 repeated runs. Alembic `upgrade head`/`downgrade -1`/
  `upgrade head` round-tripped 3x. Both apps' `npm run build`/`npm run lint` clean
  (learning-web only — chat-web untouched). Live-verified via a scripted Playwright run
  (temp install in the scratch directory, D-034 convention) against the real running
  dev servers: drove a real pre→study(with a hint round)→post cycle over raw HTTP
  first (`student-ext-4`) so the dashboard had real data, then confirmed all 6 chart
  types render, the date-range presets are clickable and keyboard-focusable, report
  generation produces grounded text for a real gain, and a parent view (zero-activity
  student) correctly shows the facts-only fallback plus the `tutor_review_flagged`
  fact the student view never receives — 0 console errors across both role flows,
  screenshots confirmed clean. All 4 ROADMAP S28 "Done when" criteria hold. Left the
  real `student-ext-4` pre→study→post cycle plus a handful of `student_reports` rows
  in the shared dev Postgres — same "useful seed data" reasoning prior sessions gave.
  Carry-over: real cross-student cohort aggregation for branch-manager reports is not
  built (D-077 #1); `student_reports` has no retention/purge job yet (small, grows one
  row per manual "Generate report" click); the S11 parent-auto-select dashboard gap
  now also covers the new dashboard/report screens, not just session history.
- **S27 additions:** Khan Academy video bank hardening (SPEC §5.18, plan §18-L8)
  shipped — see D-076 for the full design (channel-pin-at-sync-layer, one combined
  `videos.list` call for verification+license+captions, deterministic
  `prerequisite_skill_ids`, enrichment-never-a-hard-filter). New `packages/adapters/
  youtube_data_api_provider.py` (real `YoutubeProvider`, httpx-based, mirrors
  `AnthropicBedrockProvider`'s thin-wrapper posture) — unexercised, no real YouTube
  Data API key exists yet (D-002); `FakeYoutubeProvider` stays the dev/test default,
  `YoutubeSyncSettings.youtube_provider="youtube"` is the env-selection switch.
  `FakeYoutubeProvider.list_uploaded_videos` no longer pre-filters by channel_id itself
  (S27's own hardening test needs the *sync layer's* pin check to be what's actually
  rejecting an off-channel item, not the fake). New `youtube_videos` columns (one
  Alembic migration, round-tripped 3x, every non-nullable addition carries a
  `server_default` since the shared dev Postgres already has real S15/S17 seed rows):
  `prerequisite_skill_ids`, `transcript_available`, `transcript_language`, `license`,
  `last_verified_at`, `suitability_status` (default `"approved"`),
  `verification_failures`. `catalog_sync.sync_channel` gained a verification pass
  (`YoutubeProvider.get_video_details`) after the classify/embed/upsert loop — gone/
  private flips `active_status`/increments `verification_failures`; a later passing
  check resets the failure count (reversible, same posture `mark_inactive_except`
  already had). `video_catalog.search_video` gained optional `misconception_tag`/
  `grade_band`/`mastery_state` params that only widen the embedding query text (never
  a hard filter); `search_catalog` gained an unconditional `suitability_status ==
  "approved"` gate. New `topic_resolver.resolve_mastery_state` helper (reuses the
  existing `WEAK_SKILL_THRESHOLD`, no new threshold invented). `graph/nodes.py::
  _video_intervention` now resolves and forwards all three enrichment values.
  **Tests (+5 net, 420→425, stable across 3 repeated `make test` runs):** 2
  `packages/db/tests/test_repositories.py` (reversible verification, suitability-status
  exclusion), 2 `packages/youtube/tests/test_catalog_sync.py` (off-channel rejection,
  verification-pass reversibility) plus a `prerequisite_skill_ids` assertion folded
  into the existing idempotency test, 1 `apps/learning-api/tests/test_video_catalog.py`
  (a `_CapturingGateway` proving the enriched query text reaches the embedding call).
  **Verification:** `make lint && make typecheck && make test` — 425 passed, 0 lint/
  type errors, stable across 3 repeated runs. Alembic round-tripped 3x. Live-verified
  against the real shared dev Postgres via `make youtube-sync` (fake provider, the
  only exercisable path): all 4 real videos re-synced with `prerequisite_skill_ids`
  correctly populated from their classified skills (e.g. `ka-two-step-eq` →
  `["linear_one_step"]`), `last_verified_at`/`suitability_status`/
  `verification_failures` populated as expected, `active_status` unaffected.
  All 4 ROADMAP S27 "Done when" criteria hold.
  Carry-over: `transcript_language` is an approximation (the video's own
  `RawVideoMetadata.language`, stored only when `transcript_available` is true) rather
  than a true per-caption-track language — a real per-track value needs a separate
  `captions.list` call per video, deliberately skipped this session (one more
  unexercisable real API call, same "no real creds yet" posture as everywhere else).
  `suitability_status` is schema-ready but nothing in this session ever sets it to
  anything other than `"approved"` — no human/automated content-review step exists yet;
  it's a content-policy gate ready for one, not yet load-bearing. The verification
  pass's `except Exception` swallows any real API outage silently (by design — a
  verification failure must never undo an otherwise-successful classify/embed/upsert
  pass) with no retry/alerting; fine at this catalog's small scale, worth revisiting if
  the channel grows or verification becomes safety-critical.
- **S26 additions:** Personalized stage narratives (SPEC §5.10.3/§5.13.3, plan §18-L7)
  shipped — see D-075 for the full design (inline-helper-not-node choice, exact
  `pre_intro`/`study_step` trigger definitions, shared `numeric_grounding` location).
  All 5 stages built (`pre_intro`/`pre_outro`/`study_step`/`study_outro`/`post_outro`),
  not just the 3 the ROADMAP entry's own build list named — user-approved scope
  expansion at session start. New `STAGE_NARRATIVE` Bedrock task + `StageNarrativePayload`
  (`packages/shared/bedrock.py`) and a new shared `intellichoice_shared.numeric_grounding`
  module (extract-numbers + exact/nearest-integer/one-decimal-rounded matching against a
  deterministic evidence dict — built shared-first since S28's report grounding plans to
  reuse it). New `packages/db` model/repo `StageTransition`/`StageTransitionRepository`
  (one Alembic migration, round-tripped 3x) — idempotency key is (session, stage[,
  skill]), checked before ever calling Bedrock. New `learning_api/services/
  stage_narrative.py`: gateway failure or a failed grounding check both fall back to a
  deterministic Python template built from the same evidence, so a fallback is grounded
  by construction. Wired inline (no new graph nodes/edges) from `graph/nodes.py::
  finalize_exam` (×2), a new shared `_fire_study_transition_narrative` helper
  (`submit_answer`/`intervention_choice`, triggered off a new `flow.AnswerResult.
  new_target_skill_id` field), and `routers/stream.py`'s SSE connect path (`pre_intro`,
  cost recorded on its own row, never the checkpoint). New learning-web
  `StageTransitionScreen` (narrative + collapsible "How we personalized this" evidence
  list + Continue) interposed in `App.tsx` ahead of the phase branches, dismissal tracked
  by the narrative text itself so a later, different narrative reappears correctly.
  **Found and fixed a real, pre-existing, cross-cutting bug via this session's own live
  Playwright verification (not previously known, not introduced this session):**
  `useLearningSession.ts`'s SSE-connect effect raced ahead of `/student` actually
  creating the LangGraph checkpoint, and — unlike a mid-stream drop — `EventSource` does
  not retry after a non-2xx response at all, so a brand-new session's tab permanently
  never received a single SSE push (invisible until now since every REST action updates
  `snapshot` directly regardless; `pre_intro` was the first SSE-only-dependent content
  in this codebase). Fixed with a new `checkpointReady` gate on the SSE-connect effect;
  live-reverified working (real 200 connect, `pre_intro` renders, screenshot-confirmed).
  **Tests (+17 net, 403→420, stable across 3 repeated `make test` runs):** 9
  `packages/shared/tests/test_numeric_grounding.py`, 5
  `apps/learning-api/tests/test_stage_narrative.py` (scripted fake gateway — gateway
  failure/ungrounded-response fallback, grounded-response trust, idempotency, per-skill
  `study_step` scoping), 3 new `test_bedrock_payload_pii_floor.py` cases, plus new S26
  assertions appended to `test_full_deterministic_learning_flow` (all 4 in-graph stages
  fire with real grounded content across one real cycle, including the `study_step`
  skill-transition rows the checkpoint's own `stage_narrative` channel had since
  overwritten by the time the test could observe them directly).
  **Verification:** `make lint && make typecheck && make test` — 420 passed, 0 lint/type
  errors, stable across 3 repeated runs. Alembic round-tripped 3x. Both apps' `npm run
  build`/`npm run lint` clean. Live-verified against the real running `learning-api`/
  `learning-web` dev servers: a scripted Python/`httpx` run (not `TestClient`) drove a
  full pre→study→post cycle over raw HTTP, producing 8 real `stage_transitions` rows
  (`pre_intro`, `pre_outro`, `study_step` ×4, `study_outro`, `post_outro`), every one
  `generated=True` with real skill names/scores, none invented; a Playwright pass
  confirmed `StageTransitionScreen` itself (narrative, evidence `<details>`, Continue
  dismissal, no console errors), including with real rich evidence content injected from
  a server-driven session. Dev Postgres swept clean afterward; `apps/learning-api/tests/
  conftest.py`'s own sweep extended to cover `stage_transitions`.
  Carry-over: `stage_transitions` has no retention/purge job yet (small, bounded — at
  most 5 rows per learning session, no PII). `_evidence_summary`'s
  `relevant_learning_facts` line is only ever populated for `post_outro` (the only stage
  that assembles per-skill memory facts across unresolved skills) — `pre_outro`/
  `study_step` don't surface memory facts in their evidence text even when a relevant
  fact exists, a thin-coverage choice made for scope, not a bug.
- **S25 additions:** Memory system (SPEC §5.15.4, plan §9) shipped — see D-074 for the
  full design (two consolidation entrypoints, first-contradiction-demotes/second-
  supersedes, PII-redacted chat text approved as consolidation input at session start).
  New `packages/memory` workspace package (`consolidation.py`, `events.py`,
  `consolidate_cli.py`, `make memory-consolidate`). Six episodic emission points wired
  into `graph/nodes.py` (`answer_submitted`, `intervention_chosen`, `study_outcome`,
  `chat_turn`, `exam_finalized`, `learning_gain_computed`) via a new
  `learning_api/services/memory_events.py`. `SemanticMemory` gained
  `superseded_by_id`/`contradicts_event_count` (one Alembic migration, round-tripped
  3x); `MemoryRepository` went from a stub (`upsert_fact` that only ever inserted) to a
  real implementation (`add_fact`/`reconfirm_fact`/`demote_to_contested`/
  `supersede_fact`/`expire_fact`/`top_fact_for_skill`/`find_live_fact`/
  `list_events_for_session`/`list_events_in_window`). Read paths wired: `tutor.py`'s
  `generate_hint`/`generate_solution`/`generate_personalized_hint` and `tutor_chat.py`'s
  `generate_chat_reply`/`explain_why_wrong` all now resolve and forward a real
  `relevant_learning_fact` (the `None,  # semantic memory doesn't exist until S25`
  breadcrumbs from S8/S21/S24 are gone); `study_plan.build_study_plan` breaks a
  `weighted_score` tie in favor of a skill with an active `weak_skill` fact.
  **Deliberately not touched** (despite ROADMAP's own S25 read-paths bullet mentioning
  "video search"): `video_catalog.search_video`'s misconception-tag/grade-band query
  enrichment is explicit S27 scope (`ROADMAP.md`'s own S27 build list) — wiring it here
  would collide with that session's planned work.
  **Tests (+11 net, 392→403, stable across 3 repeated `make test` runs):** new
  `packages/memory/tests/test_consolidation.py` (10 — evidence verification, provisional/
  active promotion, the two-stage contradiction/supersession sequence, idempotent rerun,
  `facts_to_update` reconfirmation, session-scoping, PII/enum screens, gateway-failure
  fallback) + `apps/learning-api/tests/test_tutor_service.py` (1, a `_CapturingGateway`
  proving `relevant_learning_fact` really reaches the wire payload) + new S25 assertions
  appended to `test_full_deterministic_learning_flow` (all six event types fire across
  one real pre->study->post cycle; the post-exam finalize's inline consolidation really
  produces `semantic_memory` rows, all correctly `provisional` since one session can
  never supply the >=2-session evidence bar alone) and to two `test_learning_chat.py`
  tests (`chat_turn` events carry only `intent`/`resolved`/`tutor_chat_message_id`, never
  the message text).
  **Verification:** `make lint && make typecheck && make test` — 403 passed, 0 lint/type
  errors, stable across 3 repeated runs. Alembic `upgrade head`/`downgrade -1`/`upgrade
  head` round-tripped 3x. Live-verified against the real running `learning-api` dev
  server (not just `TestClient` — a plain Python/`urllib` script, not Playwright, since
  this session touched no frontend code): a real pre-exam→study cycle through raw HTTP
  produced real `hint_events`/`learning_events` rows, confirmed via a direct `psql`
  query (4 distinct event types, 16 rows) against the shared dev Postgres; fixture rows
  swept clean afterward via the same dependency-ordered `DELETE` pattern prior sessions
  used. `make memory-consolidate` run against the shared dev DB exits cleanly (0
  students with recent activity, since test runs roll back/clean up their own events).
  **Found via this session's own `uv sync` troubleshooting (environment gotcha, not a
  design decision — full note in D-074):** `uv sync --reinstall-package <pkg>` (and,
  once in that state, even a bare `uv sync`) silently narrowed the shared venv down to
  just the root `dev` dependency group, breaking every `intellichoice_*` import
  workspace-wide until `uv sync --all-packages` restored it.
- **S24 additions:** Contextual learning chat (SPEC §5.12/§5.30.1) shipped, but **not** as
  the planned graph node/`entry_action` — see D-073: a scripted check this session found
  that both `graph.ainvoke` and `graph.aupdate_state` silently discard a pending
  `intervention_choice` interrupt (`/respond` 409'd "no interrupt is pending" right after
  one `aupdate_state` call), and that pause is exactly when the button-panel
  `AssistancePanel`/chat is shown. Fixed by making `graph/nodes.py::run_chat_turn` a plain
  service call invoked directly from `routers/sessions.py` (same "not a graph turn"
  precedent as S22/S23's skip/flag/time routes), read via a new `_peek_state_values`
  (identical to `_get_state_values` minus the pending-interrupt guard). Two narrow,
  documented consequences, neither fixed: chat's hint-ladder level comes from the durable
  `hint_events` table, not `LearningState.assistance_level_by_variant` (can drift from the
  button panel's own tracking only if a student mixes both channels for the same wrong
  attempt in the same pause); chat's own Bedrock spend isn't persisted back into the
  checkpoint's per-session budget total (the per-day cost ceiling, backed by the real
  `tutor_chat_messages` table, is chat's actual — and arguably stronger — cost control).
  **D-072:** user approved the free-text-to-Bedrock §5.30.1 extension at session start
  (the plan's "hard blocker"), with mandatory deterministic PII redaction
  (`intellichoice_shared.pii_redaction.redact_free_text` — email/URL/phone, the phone
  pattern deliberately requiring a 3-3-4 grouping so it doesn't redact ordinary math like
  "2024 - 1998 = 26") before the wire and before storage, plus a self-harm/abuse keyword
  screen (fixed response, `flagged_for_review=True`, never LLM-improvised) and a per-day
  cost ceiling. New `tutor_chat_messages` table + `make chat-purge` (90-day retention).
  9 new backend tests (intent dispatch incl. real `hint_events` recording, exam-phase
  refusal, cost ceiling, PII redaction on wire+storage, self-harm screen, purge job) — 371
  → 392 collected, stable across 3 repeated `make test` runs. Live-verified via a scripted
  Playwright run (temp install in the scratch directory, D-034 convention): reached a
  wrong study answer, chatted three times (hint/why_wrong/off_topic) while the
  `intervention_choice` pause was open, then confirmed the original "Show the solution"
  button still worked afterward — proving the pause survived chat's turns. Both apps'
  `npm run build`/`npm run lint` clean. No PII-floor/schema-purity regressions.
- **S23 additions:** `ExamScreen` fully rebuilt (`QuestionNavBar`/`ExamTimer`/
  `SubmitConfirmationModal` under `apps/learning-web/src/components/`) - `exam_overview`
  is fetched explicitly by the screen itself, not pushed over SSE (D-070, user-decided at
  session start against the ROADMAP bullet's literal wording). New `POST .../exam/items/
  {id}/time` route + `AssessmentRepository.add_item_time` finally populate
  `assessment_item_state.time_spent_ms` (unpopulated since S22). **Found and fixed a real
  cross-cutting checkpoint bug via this session's own Playwright verification, not
  previously known:** `graph/nodes.py`'s `submit_answer`/`finalize_exam` nodes wrote
  `"last_items": None` explicitly whenever there was nothing new to report - which is
  *every* pre/post-exam answer under free navigation (D-064) - silently erasing the
  checkpointed 10-question batch the instant the first such answer was submitted. A page
  refresh (or `/resume`) after even one exam answer showed "Loading the next question…"
  forever; the nav bar's own statuses were unaffected (a separate, unaffected read via
  `exam/overview`) which is why this hadn't surfaced before. Fixed by omitting the key
  instead of writing `None` (D-071) - LangGraph's default merge then leaves the channel
  holding its previous value, the same "omit to preserve" convention the `intervention_
  choice` node's hint-ladder branch already relied on. Regression test:
  `test_resume_after_an_exam_answer_still_returns_the_full_batch`. **Also found (same
  triage precedent as S9/S12/S14/S20/S22), not a regression from this session's own code
  but now materially worse:** `packages/curriculum/tests/test_ai_pipeline.py::
  test_passing_candidate_lands_pending_then_activates_to_active` failed - a
  deterministic-seed-generated candidate (`"Solve for x: 3x + 18 = 27"`) collided with an
  already-committed, unreferenced `question_variants` row. The colliding template
  (`linear_equations-d2-16`) had **610 accumulated variant rows** (up from the "14-16
  copies" S22 found) - confirms the still-open `question_variants`-cleanup carry-over
  (D-053) is actively worsening, not just theoretical; this session's own heavy exam-
  building verification (5-6 full `make test` runs + a live Playwright exam completion)
  plausibly added to it. Fixed this occurrence the same way as before (deleted the one
  offending row, verified unreferenced by any attempt/item/hint-event row first; confirmed
  371/371 stable across 3 repeated `make test` runs afterward) - the underlying unbounded
  accumulation is still not fixed. A future session should treat the `question_variants`
  cleanup/RNG-seeding carry-over as higher priority given this trend.
- **S22.5 additions:** brand tokens are now live in both apps (`packages/ui-brand/`,
  D-065–D-069) - S23's `ExamScreen` rebuild and any new component from here on should
  consume the existing tokens (`--accent`, `--radius-button`, etc.) and follow the
  uppercase-600-action-button pattern, not introduce new ad hoc styling.
  **Found via this session's own Playwright verification, not previously known, not
  fixed (out of branding scope):** `chat-web/src/screens/ChatScreen.tsx`'s assistant
  bubble is gated on `turn.response?.answer` being truthy, and `access_hint` is rendered
  *inside* that same bubble - so a real S19/D-056 role-gated response (`answer: null`,
  `access_hint` set) renders as a completely blank turn with no visible feedback at all,
  not the intended access-hint banner. Confirmed via a network-mocked Playwright run
  (`answer: null` + `access_hint` payload → empty assistant row, banner never appears).
  A future session should hoist the `access_hint` render out of the `turn.response
  ?.answer &&` block so it shows whether or not an answer is also present. Root
  `pyproject.toml`'s `[tool.uv.workspace]` needed `packages/ui-brand` added to
  `exclude` (D-065) - it broke `make lint`/`typecheck`/`test` for the whole monorepo
  until fixed, since `uv` expects every `packages/*` entry to be a Python package.
  **Also found, not fixed (backend/curriculum code, outside frontend-only scope):**
  `test_hint_reflects_the_students_actual_wrong_option` (S21) is genuinely flaky under
  `make test` - failed 2 of 3 full-suite runs this session (passed the 3rd), passed 3/3
  when run standalone. Traced to
  `routers/sessions.py:408`'s unseeded `random.Random()` per pre-exam build - the exact
  class of RNG-determinism gap S22's own carry-over already predicted would recur (there:
  duplicate `question_variants` rows; here: an occasionally answer-tag-less canonical
  hint). A future session should seed request-scoped RNGs in tests (or the request path
  itself for test-mode) rather than relying on `random.Random()`'s OS-entropy default.
- **S22 additions:** grade-on-submit was kept (not the plan's recommended save-then-
  finalize) and pre/post exams got a real default 1200s timer, both user-decided against
  the plan's own recommendation — see D-064 for the full reasoning and consequences
  (answered items are permanently locked, not just feedback-hidden; an explicit
  `POST .../exam/finalize` is now required even when every item was answered in order,
  since phase auto-advance was removed). `assessment_item_state.time_spent_ms` exists but
  nothing populates it yet — wired up once S23 builds a real autosave tick.
  `assessment_sessions.topic_id` is populated going forward only, not backfilled for
  pre-S22 rows. Timer enforcement is lazy (checked on the next request) — no background
  scheduler exists anywhere in this codebase yet, same "manual/on-demand only" posture as
  `youtube-sync`/`webcontent-sync`. **Found via this session's own verification, not
  previously known:** `question_variants` has no cleanup path at all in
  `apps/learning-api/tests/conftest.py`'s per-student sweep (D-053) — rows are keyed by
  template, not student, so every HTTP-committed exam-building test leaves generated
  variants behind permanently, unbounded, forever. This had already silently accumulated
  enough duplicate content (14–16 copies of several `linear_equations` phrasings found
  during triage) to collide with `packages/curriculum/tests/test_ai_pipeline.py`'s
  deliberately-chosen S17 anti-collision seed (700666), rejecting that test's pipeline
  candidate for "duplicate rendered_question" before it ever reached the check the test
  means to exercise — fixed this time by deleting the one specific orphaned variant row
  (verified unreferenced by any attempt/item/hint-event row first; confirmed 369/369
  stable across 3 repeated `make test` runs afterward), but the underlying accumulation is
  unbounded and not fixed — a future session should either seed the RNG in
  `apps/learning-api/tests/*`'s HTTP-committed tests or add a real `question_variants`
  cleanup/dedup pass before this recurs.
- **Carry-over items:** **Parent auto-select dashboard gap (S11):** when a parent has
  exactly one linked child, `resolve_student` auto-selects without an `interrupt()`, so
  the frontend never learns `student_external_id` (it isn't in `SessionSnapshotEvent`) and
  can't offer that parent a dashboard link until an explicit selection happens elsewhere —
  a small backend enrichment (or adding the field to the snapshot) would close this cleanly
  if it matters before launch. **Results-screen hint/solution/video counts are
  client-observed, not backend-authoritative** — they reset on a mid-session refresh; the
  parent dashboard (`GET /learning/students/{id}/sessions`) is the real source of truth for
  the same numbers, computed from `StudyAttempt` rows. **SSE is coarse state-push, not
  per-node LangGraph event streaming** (D-032) — sufficient for the refresh-restore
  "Done when" criterion, but if a future session wants live token-level tutor output, the
  Bedrock gateway itself would need a streaming method first (only `generate_structured`
  exists, D-022). The `?token=` query-string SSE auth (D-032) means access logs can carry
  live bearer tokens - revisit at S20 (observability) before real deployment. **Enterprise
  IRT/Bayesian mastery (§5.10.2) is still deferred** —
  it needs production response data that doesn't exist pre-launch; S10 keeps the bootstrap
  model and adds `recommended_difficulty` on top (D-029). **Genuine within-skill difficulty
  routing is limited by the 1:1 skill↔difficulty curriculum** — each `linear_equations`
  skill's templates all sit at one tier, so S10's real ±1 move is the ladder's prerequisite
  step (difficulty −1); true within-skill routing needs multi-difficulty-per-skill template
  banks (future content work, D-030). The §5.11.2 rule-6 prerequisite carry-over is **half
  retired**: the *retry ladder* now traverses `prerequisites.yaml` in-process (no Postgres
  table) for its easier-prerequisite step, but the *study-plan selector* still doesn't gate
  on prerequisites, and there's still no Postgres prerequisites table. The S9 AI-generation
  pipeline is still proven against `linear_equations` only — `fraction_operations`/
  `place_value` still have **no registered template shapes**, so `ai_pipeline.
  generate_candidate` raises `PipelineConfigError` for those topics by design (D-003/D-016);
  authoring shapes + bounds for them is a future content session. SPEC §5.8.4's
  production-data difficulty recalibration is **not** built (needs live usage data). The
  §5.11.6 video option's **hardcoded stub catalog (D-031) was replaced by S15's real
  Postgres+Bedrock catalog** - see the S15 section below. Still open from earlier sessions:
  `AnthropicBedrockProvider` never exercised against real AWS (D-025); real Bedrock
  Guardrails untouched (revisit S21+); `MockBedrockProvider`'s solver always returns option
  "a" (real candidate/tutor volume needs real Bedrock creds, D-025). **S12 additions:**
  `TitanEmbeddingProvider` (D-035) is likewise never exercised against real AWS - the
  ingestion pipeline has only run against `MockBedrockProvider`'s deterministic hash-based
  vectors. No automatic document-version chaining is built - a changed `source_sha256`
  under an existing `document_id` replaces that document's chunks in place and updates
  `version`/`status` from the manifest, but nothing auto-sets `supersedes_document_id` or
  retires the prior version; that's manifest-authoring discipline for now, not pipeline
  logic. `RagChunk.parent_chunk_id` only expresses one level of hierarchy (every non-root
  chunk's parent is its document's root/title chunk) - correct for all 22 placeholder docs
  (single H1 + flat H2 sections) but would need a real ancestor-stack for H3+ nesting.
  `search_vector`/`embedding` are now queried (S13's hybrid search) - see S13's own
  section below for what's still open there.
- **Newly observed (not S12-caused, worth knowing before the next pollution cleanup):**
  `apps/learning-api/tests/*` integration tests drive a real `TestClient(app)` against the
  live shared dev Postgres with no rollback wrapper (unlike `packages/db`/`packages/
  curriculum`/`packages/knowledge`'s `rollback_session` pattern), so every `make test` run
  commits real rows under the Mongo-fixture student ids. Confirmed live during S12: after
  this session's initial cleanup (below) and 3 more full-suite runs while iterating,
  `student-ext-4`/`student-ext-2` had already reaccumulated 154 `assessment_sessions`/22
  `blocked_sessions` rows with no manual "curl the dev server" step involved this time -
  the test suite itself is the source, not only prior sessions' manual verification as
  originally assumed. Currently harmless (only `test_repositories.py`'s broad "count every
  row for this student" assertions are sensitive to it, and those key off `student-ext-1`
  specifically, which these particular integration tests don't touch), but it's unbounded
  accumulation with no test-suite-level cleanup - a future session should wrap these tests
  in the same rollback pattern or add a teardown, rather than relying on periodic manual
  `DELETE`s the way this session did.
- **S13 additions:** `role_access_filter` only resolves a caller's `branch_external_id`
  for `Role.STUDENT` (the one role with an unambiguous single branch in S2's
  `ProfileAdapter`) - parents/tutors/branch_managers always retrieve as branch-unresolved
  (org-wide chunks only, never leaked into another branch's), which is safe but not fully
  spec-realized; a real "current branch" concept (tutor/branch_manager profiles, or a
  parent's selected-child branch) is future work, not built this session. `academic_year`
  is *not* part of `role_access_filter`'s query - SPEC's "academic_year = requested_year"
  implies parsing a year out of the question text, which would be exactly the "runtime
  NL2SQL" CLAUDE.md non-negotiable #2 forbids without a deterministic year-extraction
  design; all 22 seeded documents share one academic year regardless, so this doesn't
  currently under- or over-filter anything. No conversation-history contextualization -
  `QAState.standalone_query` is always identical to `query` (single-turn only); a future
  session wanting pronoun/reference resolution across turns needs to build that rewrite
  step. `MockBedrockProvider`'s reranker scores by query-word overlap only (no real
  semantic judgment) - fine for deterministic tests, but real reranking quality is
  unverified until a real Bedrock reranker model is wired (same "never exercised against
  real AWS" caveat as D-025/D-035). **All 22 `knowledge-content` documents carry
  `effective_from: 2026-08-01`** (next academic year) - confirmed live during this
  session's own verification that this makes every retrieval correctly return "no
  approved source" via the real dev server *today* (2026-07-17), since none of the
  seeded content is "effective" yet; this is the §5.21.3 date filter working exactly as
  designed, not a bug, but it means anyone manually curling the live dev server before
  2026-08-01 needs to pass a future `as_of` (or the manifests need their dates moved
  earlier) to see a populated happy-path answer - confirmed working via a direct
  service-layer call with `as_of=2026-09-01`, see this session's verification notes.
  Left the 22 documents/110 chunks re-seeded in the dev Postgres (they'd been cleaned
  since S12 ended) - same "useful seed data for the next session's retrieval work"
  reasoning S12 gave. `apps/chat-api/tests/test_chat_endpoints.py`'s few `TestClient(app)`
  HTTP tests write LangGraph checkpoint rows to the live dev Postgres under fresh random
  session ids (no RAG content is ever seeded through them) - same small, bounded
  footprint `apps/learning-api`'s own session-creation HTTP tests already have, not the
  unbounded-domain-row accumulation flagged above. **Any future test that calls
  `search_document_chunks`/`hybrid_search` with a generic English query and no `as_of`
  filter risks the same real-content collision** this session hit and fixed once (see
  the session-log entry below) - S13's own graph-level tests are naturally immune since
  `role_access_filter` always sets `as_of=now()`, which excludes all real seeded content
  (every `knowledge-content` document is dated `effective_from: 2026-08-01`, in the
  future relative to "now" through the current build), but any test that skips `as_of`
  entirely and uses a plausible real word is at risk; prefer a nonsense marker phrase
  (D-018's pattern) for those.
- **S14 additions:** CAPTCHA and ML-based abuse detection for anonymous
  `admin_escalation` calls are explicitly **not built** - SPEC §5.24.2 lists them, but no
  real CAPTCHA service exists yet (same D-002 "no real creds yet" posture as the rest of
  this project); the in-memory rate limiter + body-length cap + header-injection defense
  are the buildable subset. No dedicated prompt-injection filter on the admin-escalation
  email body either - it's a fixed template with the user's own query interpolated as
  inert text (never re-fed to an LLM or executed), judged low-risk enough to defer rather
  than build new filtering machinery for. **No real Google OAuth** - both Gmail and
  Google Calendar stay on fake transports in dev (`FakeEmailTransport`/
  `FakeCalendarTransport`), same posture as every other external dependency (D-002); real
  credential wiring is SPEC §5.35/Session 21+ territory. **No `.ics` file-download HTTP
  endpoint** - the generated RFC 5545 text is returned inline as a response field
  (`ics_content`) this session; a real download affordance is `chat-web`'s job (S16).
  Branch locator (`intent="branch_locator"`) routing to `unavailable_intent` was **S15
  scope, now built** - see the S15 section below. Left ~6 real `interrupt_approvals`/
  `mcp_tool_calls` rows in the
  shared dev Postgres from this session's own live-server verification (admin-escalation
  approve+send, calendar `.ics` generation) - small, bounded audit-table rows, not
  domain-row accumulation, so not cleaned up (same reasoning prior sessions gave for
  small verification footprints). **The S12 "Newly observed" `student-ext-1` pollution
  recurred** (still not fixed - same known cause: `apps/learning-api/tests/
  test_learning_flow.py`'s uncommitted-rollback `TestClient` runs), surfacing as two
  spurious `packages/db/tests/test_repositories.py` failures
  (`test_assessment_repository_round_trip`/`test_mastery_repository_round_trip`, exact
  `get_weak_skills`/session counts inflated) after repeated `make test` runs during this
  session's own iteration. Cleaned up via the same targeted, dependency-ordered `DELETE`
  S9/S12 used, scoped to `student-ext-1` only; confirmed back to the clean 244/245
  baseline across 3 repeated `make test` runs afterward. Still not a one-time fix -
  a future session should add the same `rollback_session` wrapper (or teardown) to
  `apps/learning-api/tests/*`'s HTTP-committed tests that `packages/db`/`packages/
  curriculum`/`packages/knowledge` already use.
- **S15 additions:** Real Google Maps and YouTube Data API credentials don't exist yet
  (same D-002 "no real creds yet" posture) - `FakeMapsProvider`/`FakeYoutubeProvider`
  are the only implementations; a real client behind either `MapsProvider`/
  `YoutubeProvider` Protocol is future work once credentials exist. **A residual,
  not-fully-eliminable caveat on the location-consent design (D-045):** the raw
  location is never assigned to a named `QAState` field (proven by a dedicated test
  asserting it's absent from the checkpointed state), but LangGraph's own
  `AsyncPostgresSaver` still persists the `interrupt()` resume value itself as part of
  its internal crash-safety bookkeeping - the same category of caveat D-032 already
  flagged for the `?token=` SSE query string; not eliminable without forking LangGraph's
  own checkpoint architecture. **No weekly EventBridge schedule** for `youtube-sync` -
  ROADMAP's own S15 scope note says "manual trigger in dev; schedule later," so
  `make youtube-sync` (a CLI, `packages/youtube/sync_cli.py`) is the only trigger this
  session; Phase 16's "runs automatically every week" completion criterion is
  deliberately deferred, not a gap. Left 4 real `youtube_videos` rows (the
  `FakeYoutubeProvider` stub catalog, correctly classified against the real curriculum
  registry) plus a couple of `interrupt_approvals`/`mcp_tool_calls` rows in the shared
  dev Postgres from this session's own live-server verification - same "useful seed
  data, small bounded audit rows" reasoning prior sessions gave, not cleaned up.
- **S16 additions:** the visible chat transcript is client-only (D-048) - `QAState` has
  no message-history field, so a cleared `sessionStorage` loses the conversation view
  (the backend's own turn-scoped checkpoint is unaffected; nothing server-side is
  lost). **All 22 `knowledge-content` documents are still `effective_from: 2026-08-01`**
  (S13's carry-over, unchanged) - as of this session's "today" (2026-07-18), every real
  document_qa/calendar query through the live graph correctly hits the fail-closed
  no-answer/no-event-found path rather than a grounded answer; confirmed live via the
  browser (a guest FAQ query and a calendar query both produced the documented graceful
  messages, not a bug). Because of this, the "found a dated event -> `.ics` choice ->
  download" path couldn't be exercised against real content this session - verified
  instead via a Playwright run with `/messages`/`/respond` network-mocked to return a
  real `calendar_event`/`ics_content` shape, proving `CalendarActionModal` and the
  client-side `.ics` Blob download (D-048) work correctly and byte-for-byte, decoupled
  from the date gate. This will self-resolve once real content passes 2026-08-01, or
  whenever a future session seeds a document with a nearer `effective_from` for this
  purpose. Dev-login fixture tutor/branch_manager ids (`tutor-ext-1`/
  `branch_manager-ext-1`) are arbitrary strings with no Mongo profile behind them,
  matching `role_access_filter`'s already-documented S13 gap (no branch resolution for
  those two roles) - fine for exercising the auth/role-gating wire-up, not tied to real
  seeded identities. No real Google OAuth still (S14/D-002's posture, unrelated to this
  session).
- **S17 additions:** the 2026-08-01 date gate is now retired for exactly 3 documents
  (`public-organization-overview`/`public-branch-directory`/`public-our-team`, all
  `effective_from: 2026-07-18`) - the other 19 `knowledge-content` documents (parent/
  student/tutor/branch_manager, plus the still-placeholder `academic-calendar`) remain
  `2026-08-01` until S18+ replaces them with real content the same way. **Real branch
  data (`org_branches`, 26 rows) is not unified with the branch-locator/geolocation flow**
  - `FakeMapsProvider`'s gazetteer and `mongo_fixtures.py`'s `BRANCH_MAIN`/`BRANCH_NORTH`
  dev-login fixtures deliberately stay on the old 2-branch synthetic Springfield data
  (user-confirmed scope cut at session start, ~5 dependent test files); a student's
  assigned branch and "find nearest branch" still resolve against the synthetic pair,
  while `document_qa`/the branch directory now answer from the real 26. Unifying these
  is future work if the locator itself needs real addresses. `org_team_members.
  branch_external_id` is always `null` - matching a scraped team member (e.g. a "NOC
  Branch Manager") to a specific `org_branches` row needs name/title parsing not built
  this session. The about page's real history section flattens WPBakery's accordion
  era-groupings (1993-2001, 2004-2005, ...) into one running list under whichever real
  `<h4>` milestone heading precedes them (only 2 real h4s exist on the page) - every
  milestone bullet is intact and citable, just not visually grouped by era the way the
  live site's collapsible widget presents it. `make webcontent-sync` always hits the
  real live site (D-051) - no scheduled refresh yet, manual trigger only (same "schedule
  later" posture as `youtube-sync`, S15). `packages/knowledge/retrieval.py`'s new
  score-`>0.0` rerank filter (D-052) is a real behavior change on the production
  retrieval path, not test-only - worth double-checking against real Bedrock reranker
  output once real credentials exist (same "never exercised against real AWS" caveat as
  D-025/D-035/D-046).
- **S18 additions:** the org's real event history (42 events synced via the Tribe
  Events Calendar REST API, D-054) is **entirely historical** - most recent
  2025-05-10 - so a live "what events are coming up?" query today correctly answers
  "There are no upcoming events currently scheduled," confirmed against the real dev
  server; upcoming/recurring/canceled classification is proven by
  `apps/chat-api/tests/test_calendar_events.py`'s synthetic-date unit tests instead
  (same posture as every other "not yet exercised against real X" caveat - D-025/
  D-035/D-046/etc.), self-resolving once the org posts a real future event.
  `OrgEvent.timezone` defaults to `"America/Chicago"` for every scraped event (the
  source API's own `timezone` field is a WordPress misconfiguration - D-054) - not
  exact for the one real branch outside Central time (Flagstaff, AZ), but no event row
  links to a branch to do better. `OrgEvent.recurrence_rule` is populated only in
  tests - this site's real events plugin tier doesn't expose true recurring-series
  metadata (weekly workshops are separate WP posts per week). No `mark_inactive_
  except`-style bookkeeping exists for events (D-055) - a real event going missing
  from the source has never happened and isn't handled if it does. Left 42 real
  `org_events` rows (plus 26 `org_branches`/50 `org_team_members`, re-synced with a
  fixed HTML-entity-unescaping bug found this session - D-054) in the shared dev
  Postgres, same "useful seed data" reasoning prior sessions gave.
- **S19 additions:** the plan's "different branch" generic access-hint message is
  **not built** (D-056) - only the role-gated case ships; see D-056 for the false-
  positive this avoided. The golden Q&A coverage eval's `grounded` subset only covers
  3 of the 4 real, already-effective documents (`public-organization-overview`/
  `public-branch-directory`/`public-our-team`) - `public-academic-calendar` is
  deliberately excluded since any calendar-shaped query routes to the `calendar`
  intent's structured `org_events` path, never `document_qa`/RAG citations, so it
  can't produce a RAG citation by design; that path's own correctness is already
  covered by S18's `test_calendar_events.py`/`test_events_endpoint.py`. The eval's
  `grounded` queries are hand-tuned around `MockBedrockProvider`'s crude keyword-
  overlap reranker (confirmed empirically this session - even "What is
  IntelliChoice?" alone didn't reliably retrieve real public content); real retrieval
  quality on these same queries is unverified until real Bedrock creds exist (same
  D-025 posture as everywhere else). `chat_suggestions` has no per-role coverage
  eval of its own - the ~14 seed prompts (`suggestions_seed.py`) are reviewed by hand,
  not tested for "does every role have at least N suggestions" the way a larger
  catalog might need. Left 14 real `chat_suggestions` rows (`make chat-suggestions-
  load`) in the shared dev Postgres - same "useful seed data" reasoning prior
  sessions gave (re-seeded once already this session after an `alembic downgrade -1`/
  `upgrade head` round-trip check dropped and recreated the table, as expected).
- **S20 additions:** authored generation is wired for `linear_equations` only
  (D-060, user-confirmed at session start) - `fraction_operations`/`place_value` still
  raise `PipelineConfigError`, same posture as the S9 shape pipeline's own gap
  (D-003/D-016). Near-duplicate cosine-distance threshold and `QUESTION_JUDGE`'s
  reject/borderline score cutoffs are placeholders never calibrated against real
  Bedrock/Titan output (D-059/D-061, same "unverified until real creds exist" posture as
  D-025/D-035/D-046). Hint-ladder monotonicity is checked as substring containment (a
  deterministic proxy for "an earlier hint already reveals a later one"), not a semantic
  check - real nuance is `QUESTION_JUDGE`'s `hint_quality_score` job. An authored
  template gets exactly **one** static `QuestionVariant` (plan §7) - unlike the shape
  bank, a repeated delivery of the same authored template never gets a fresh numeric
  variant (SPEC §5.8.6's "generate a new numerical variant instead" fallback doesn't
  apply to authored content by design). **Found via a live-verification incident this
  session, now fixed but worth flagging for future live runs:** `make
  question-gen-authored` + `make question-review` (approve) against the shared dev
  Postgres left one real `approved`+`active` `linear_equations` difficulty-1 template,
  which broke `packages/curriculum/tests/test_loader.py` and `apps/learning-api/tests/
  test_learning_flow.py`'s exact `len(active) == 10` assertions (they hard-code the S4
  hand-authored bank's per-difficulty count) - cleaned up via a targeted delete of the 5
  live rows this session's own verification created (dependency-ordered:
  `question_validation_runs` → `question_variants` → `question_templates`), confirmed
  back to 341/341 across 3 repeated `make test` runs. A future session live-verifying
  the authored pipeline against the shared dev DB should activate a topic/difficulty
  pair `test_loader.py`/`test_learning_flow.py` don't exact-count (or clean up
  afterward), not `linear_equations` difficulty 1. `review_cli.py` is CLI-only (`make
  question-review`) - no web/admin UI for human review this session, matching D-026's
  existing "pipeline can never self-approve" gate being satisfied by a human running a
  command, not a specific UI shape.
- **S21 additions:** the misconception-tag mapping (`topic_resolver.
  resolve_misconception_tag`) is a **coarse heuristic** - the student's wrong option's
  ordinal rank among the non-correct options, mapped to the same-index
  `common_error_tags` entry - not a true per-distractor-generator trace back to which
  specific error produced that option. Correct only if a template's `common_error_tags`
  are authored in the same order as its distractor generators (true for the S4
  hand-authored `linear_equations` bank's `["sign_error", "off_by_one",
  "magnitude_error"]`, unverified for any future topic's tags). An exact reconstruction
  would need to replay `generation.generate_variant`'s seeded RNG to recover which
  `distractor_generator_keys[i]` produced the student's actual selected option - future
  work if hint quality demands it, not built this session. **`HINT_PERSONALIZATION`
  reuses the same configured model as `TUTOR`** (`settings.bedrock_tutor_model_id`) -
  no new settings field, since this is a rewrite of the same tutoring task family, not
  a distinct capability; revisit if a different model proves better for rewriting vs.
  generating fresh content. The within-question ladder is capped at exactly 3 levels
  for both shape and authored templates (matching S20's existing
  `_REQUIRED_HINT_LEVELS = 3`) - the ROADMAP text's "before level 4" phrasing is stale
  from an earlier plan draft, not a decision this session revisited. `PendingInterruptResponse.
  question_variant_id` is `None` on any `/respond`-initiated resume (pre-existing gap,
  not introduced this session - `ctx.question_variant_id` was never guaranteed set on
  that call path; S21's second-and-later ladder rounds hit this same gap on every
  round, same as the original single-shot design already did on its one resume). Live-
  verified via a scripted Playwright run against the real dev server (`learning-api`
  :8001 + `learning-web` :5173, `MockBedrockProvider`): a full wrong-answer → hint ×3
  escalation showed "(hint 1 of 3)" → "(hint 2 of 3)" → "(hint 3 of 3)", three genuinely
  distinct hint texts each correctly embedding the resolved `misconception_tag`
  ("sign_error"), the "Get another hint"/"I'll try again now" buttons correctly
  disappearing at the final level in favor of "Got it — next question", and a fresh
  study question already loaded underneath - no console errors beyond one unrelated
  favicon 404. Screenshots + fixture-row sweep confirmed clean afterward (358/358
  stable across 3 repeated `make test` runs, 0 leftover `hint_events`/`study_attempts`
  rows for the fixture student used).

## Session log

_Note: this section holds S32, S37 and S40's continuation. S33–S36 recorded themselves in the
"Current status" block above instead, which is where this project's detailed log actually lives —
recorded here so the gap reads as drifted practice, not as unlogged work._

### Off-roadmap — the chat cluster: AUD-C-16 → C-02 → F-19 (2026-07-28) ✅
- **Scope: PROGRESS.md's own "Next session" pointer, not a numbered roadmap block** — the three
  chat P1s taken in the mandated order and as one piece. The ordering was the diagnostic: with
  retrieval fixed first, F-19(b)'s "three different products" collapsed to `document_qa` 3/3 on
  its own, while the scope misroutes survived it — one cluster, separated into two defects plus
  one correct behavior by a single ordering choice.
- **AUD-C-16 (P1) fixed and live-verified (D-112 §1, PR #34 `7469ea8`, deploy `30396987673`).**
  Provenance columns stamped at ingest (NULL = unknown = mismatch), idempotent
  `make knowledge-reembed`, a deploy-step re-embed after migrations and before rollouts, and a
  fail-closed `/readyz` corpus assertion on the ALB health-check path — the detection the finding
  called load-bearing. Staging: **159→0 mock-like by S38's own discriminator** (max cos 0.078),
  0.0224¢; the *next* deploy re-ran the step as a 0-chunk/0-cent no-op. Paraphrase probes:
  no-source refusals → **9/9 grounded with citations**. All three guards watched failing with
  their fix disabled.
- **AUD-C-02 (P1) closed, and D-111's fix was measured insufficient first (D-112 §2, PR #36
  `9fdc178`, deploy `30418370062`).** With the topic fix live on real Bedrock, "What is
  IntelliChoice?" was still refused/deflected 3/3, and "Tell me about the people who run
  IntelliChoice" routed to `admin_contact`'s email flow 3/3. The close was intent *definitions*
  plus pinned examples in the same prompt. Post-fix: 3/3 grounded on each, `Our Team`/`About
  IntelliChoice` citations. Static guard watched failing against the old prompt; behaviour lives
  in four real-Bedrock `paraphrase` eval cases.
- **AUD-F-19 (P1) closed (D-112 §3).** (a) "Saturday hours" 0/6 → **3/3 answered with a Branch
  Directory citation** via the same prompt fix. (b) was C-16's noise; its residual no-source is
  the effective-date filter working (`public-student-participation-guide` opens **2026-08-01** —
  re-check then).
- **Verification:** lint clean, pyright clean, **560 passed / 2 skipped** (554 → +5 C-16 guards,
  +1 prompt guard); migration `e18f4a6c2b90` round-trips; staging e2e re-run pinned to
  `9fdc178`'s deploy: **47/2/4**, same scoreboard as D-111's run, the 2 being the known
  learning-side observations (untouched here); all chat specs green a second consecutive run.
- **Carry-over:** youtube/question-variant embedding provenance (C-16's class, dormant); the
  1-in-3 no-source margin flake on one leadership question (no ID until measured); one refusal
  with a non-empty citations list (cosmetic, unverified); 2026-08-01 and 2026-08-02 date checks;
  S42 discovery asks still unsent. Mid-session the user shipped PR #35 (staging UI login) and
  deployed `85dd6ad` — no interaction beyond validating the re-embed no-op.

### S42 — Phase 0B: the integrity/concurrency cluster (2026-07-27) ⏸ partial
- **Scope note: this was not S42's roadmap scope.** S42 is "discovery, Tier 1 org asks, and the auth
  decision gate", and **none of that was done** — it remains fully outstanding. The dependency spine
  puts the gate *before* discovery, S42's own asks are mostly external (org DB topology, network
  path, read-only account, DNS, live role survey), and gate criterion 2 needs the P1s gone. So the
  session took the integrity/concurrency cluster instead. The session number is used for continuity;
  the discovery work is unstarted.
- **AUD-L-10 (P1) fixed with a unique constraint, not a check (D-110 §1).** Uniqueness on
  `assessment_attempts` tightened from `(session, variant, idempotency_key)` to `(session, variant)`.
  A status check in Python is the same read-then-act shape this cluster exists to remove: **with the
  constraint dropped, four concurrent answers all return 200 while the sequential test still
  passes.** The `flow` pre-flight is kept and was nearly cut — disabling it changed no test outcome,
  which by D-109 §(iii) is a line to delete, until measurement showed a refused duplicate that
  reaches `graph.ainvoke` leaves **+2 `checkpoints` / +4 `checkpoint_writes`** behind. It is now
  covered by a checkpoint row count. Conversely a defensive denominator recount in
  `compute_learning_gain` was **not** added, because with the constraint no test could watch it
  matter; the assumption is documented at the line instead.
- **AUD-X-08 (P1) fixed with a reserve-then-settle ledger (D-110 §2).** New `cost_reservations`
  table: the worst-case cost is reserved in its own immediately-committed transaction *before* the
  model call and settled with the real cost after, serialized by
  `pg_advisory_xact_lock(hashtext(scope||subject))`. `INSERT … SELECT` alone does not serialize under
  READ COMMITTED — **removing the lock grants 10 of 10 reservations against a ceiling of 3 while all
  three sequential tests pass.** Both ceilings converted (report, tutor chat); the two spend readers
  that *were* the defect are deleted rather than left for a future ceiling to wire itself to.
- **The AUD-X-08 reproduction had to be repaired before it could reproduce, and this is the most
  transferable thing in the session.** Ten genuinely concurrent reports (10 in flight, measured)
  against the **unfixed** ceiling produced **1 generated, 1.0× the ceiling** — it looked already
  fixed. The race window is the length of the model call and `MockBedrockProvider` returns in ~0 ms.
  At a realistic 250 ms: **10/10 and 10.0×**, worse than S38's 8×. After the fix, same probe:
  **1/10 and 1.0×**. A cost-race test built on the mock's speed would have certified this fixed while
  it was wide open.
- **Reservation estimates are constants, guarded by a drift test.** Adding `worst_case_cost_cents`
  to the `BedrockGateway` Protocol cost **70 typecheck errors across ~13 scripted test fakes**, so
  the method stayed on the concrete gateway. `test_cost_reservation_estimates.py` asserts each
  constant still bounds the real gateway's arithmetic for every model in the rate table — and
  **failed on the first constants written** (0.5 against real worst cases of 1.35 and 2.625).
- **AUD-X-07 (P1) half fixed; it stays open (D-110 §3).** `services/checkpoint_reconcile.py` rolls a
  checkpoint *backwards* to what the database supports when it names a row that does not exist,
  wired into `_get_state_values` and `/resume`, counted by `learning_checkpoint_repairs_total`.
  Seam (a) mid-finalize is fixed and S38's reproduction is now a test that fails
  `'study' == 'pre_exam'` with the fix disabled. **Seam (b) mid-interrupt is not fixed and no
  detection code for it shipped** — recovery means *completing* a paused LangGraph node, not editing
  channel values, and a detect-but-cannot-act branch is code no test can watch mattering. Fix
  shape (1), the commit ordering itself, is untouched.
- **Two false premises about criterion 3 corrected, and they had compounded (D-110 §4–5).**
  (i) **Merging to `main` does not deploy** — `deploy-staging.yml` is `workflow_dispatch:` only.
  A watcher built on `gh run list --limit=1` reported `COMPLETED: success` seconds after the merge
  because it matched the *previous* run; comparing head SHA caught it. (ii) **`make e2e-staging` did
  not point at staging** — `E2E_TARGET=staging` selects the auth path, not the browser target, so the
  suite ran against `localhost:5173`: **2 passed, everything else `ERR_CONNECTION_REFUSED`**
  (AUD-F-17). (iii) With that fixed, **all ten journey specs used a dev-login screen that is
  secret-gated on staging**: 34 passed / 18 failed, all 18 that (AUD-F-18). Each defect hid the next.
- **The first real staging run: 40 passed / 10 failed / 3 skipped. Criterion 3 is NOT met**, and the
  ten are two real findings, diagnosed against staging directly rather than through the browser
  (D-110 §6). **AUD-F-19 (P1, new):** *"What are the Saturday hours?"* → `location_consent` 3/3 with
  `answer: null`, and *"How do I enroll a student?"* returned a scope refusal, a no-source refusal and
  an `email_approval` interrupt across three identical calls. **Latency was the obvious hypothesis
  and it is wrong — a guest turn takes 1.4 s.** **AUD-F-20 (P2, new):** seeded attendance is written
  for `current_week_key()` at seed time, so the "present this week" fixture is now blocked and every
  learning journey fails; the gate is behaving correctly on stale data, and criterion 3 evidence on
  staging therefore has a **weekly expiry**.
- **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **552 passed / 2
  skipped across three consecutive whole-suite runs** (537 at session start). e2e harness typechecks
  clean. Both migrations **replay from empty** and survive a downgrade → re-upgrade cycle. PR #31
  merged with all 7 CI checks green and **deployed to staging, verified by head SHA** (`1d2436a`):
  migrations, `/dev/token` gate, canary bake and smoke test all green, rollback skipped.
- **Carry-over:** AUD-X-07 seam (b) and fix shape (1); AUD-F-19 and AUD-F-20 (neither attempted —
  re-seeding staging mutates the environment and needs its own decision, and F-19 belongs with the
  C-02/C-16 cluster); the per-session gateway budget, still stateless by design (D-072); enabling
  `deploy-staging.yml`'s `push` trigger now that the "run and review it once" comment is seven runs
  stale; **gate criterion 2 cannot be met on the current ordering** — AUD-L-07's remaining half needs
  S43's roster model, scheduled *after* the gate, so it needs either a fail-closed read refusal
  (which removes tutor report generation) or explicit §7 residual-risk acceptance.
- **New decisions:** **D-110**.

### S41 — Phase 0B: the criterion-3 cluster (2026-07-27) ⏸ partial
- **AUD-F-01 (P1) fixed and re-verified by counting requests, not by looking at the screen
  (D-109 §1).** `App.tsx` passed `onFetchOverview`/`onRecordTime` as inline arrows into two
  `ExamScreen` effect dependency arrays; it now destructures the hook's already-memoized functions
  by name. Same 15-second dwell on one question: **899 → 1 `POST .../time`** (longest report
  **68 ms → 15,009 ms**, i.e. the real dwell) and **903 → 2 `GET /exam/overview`**. The obvious
  version of this fix is a trap — a `useCallback` over `session.fetchExamOverview` makes
  `exhaustive-deps` demand `session`, which is a fresh object every render, so obeying the linter
  silently reinstates the defect.
- **AUD-F-02 (P2) fixed, and "same root cause as AUD-F-01" turned out to be wrong (D-109 §2–3).**
  The AUD-F-01 fix took the post-finalize burst from **35 × 409 to 1**, and that survivor is a
  different defect: the view-time flush on unmount, where the unmount *is* the finalize. The
  `finalizedRef` guard must be raised **before** awaiting `onFinalize` — `finalizeExam` calls
  `setSnapshot` inside the awaited request, so React unmounts the screen in a microtask that lands
  before the `await` resumes. **0 × 409, 0 console errors.**
- **Both probes promoted from `test.fail()` to regression tests**, each watched failing with its
  own fix reverted (D-107 §1). `time-telemetry` now asserts the request *counts* as well as the
  dwell value: a fix that made reports accurate while leaving the churn would still be a database
  write per render.
- **The e2e intermittency was three unrelated harness races, not one shared-state story
  (D-109 §5).** A parent journey asserting on three locators that a stage narrative matches none of
  (this one genuinely is shared state — narratives only exist once an account has history); a chat
  journey whose second turn is the branch-locator prompt verbatim, so it waits 90 s for an answer
  the product is correctly withholding; and two Playwright calls that **throw** where this
  harness's own convention is to degrade to a retry. **Each passed the run before it failed.**
- **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **537 passed / 2
  skipped** (unchanged — no backend change). **e2e green three consecutive whole-suite runs:
  52/1/0, 51/2/0, 52/1/0** (passed/skipped/failed), against **48 passed / 3 failed / 2 skipped** at
  session start. Both frontends and the e2e harness typecheck and lint clean.
- **One change reverted rather than shipped (D-109 §4):** scoping the view-time flush to exam
  phases looked right and had a confident comment; a control run showed the test passes without it,
  so the explanation was wrong and no test covered the line.
- **Carry-over:** criterion 3 needs the deploy (see Current status); **AUD-F-16 (new P2)** —
  `reuseExistingServer: true` had the audit measuring two-day-old API code, so every S39/S40
  `local` e2e result is of an unknown application version; two conditional `test.skip()`s that
  should stop being conditional; whether study-phase time is ever attributed to a stale exam item
  (the question left open by the reverted change); the unexplained disappearance of the tracked
  `knowledge-content copy/` directory, restored via `git checkout`.
- **New decisions:** **D-109**.

### S40 continuation — Phase 0B: the authorization cluster (2026-07-27) ⏸ partial
- **Unbroke the baseline structurally (D-106).** The session opened red:
  `test_solver_disagreement_rejects_without_persisting` failed 5/5, **the fourth recurrence of
  D-053**. `question_variants` held two populations under one table and SPEC §5.8.3's dedup compared
  against both, so a *content* question ("is this a new question?") was answered by a *usage* fact
  ("how much has the app been run?") — **60,906 rows against 50 templates, 93.5% referenced by
  nothing**. Fixed with an explicit `origin` column, an Alembic migration, and a two-armed
  regression test. S17/S22/S31 each deleted the offending row; **it is still in the database and the
  suite passes**, which is the evidence the fix is structural rather than postponed.
- **Four authorization P1s fixed, each live-verified with a before/after pair (D-107).**
  **AUD-X-01** — the one route that *writes* `student_external_id` never read it; live pre-fix, B
  seized A's session (200), A was locked out of their own exam (403), and a tutor rebound it to
  **`student-ext-77`, an id that does not exist** (200). **AUD-X-05** — the tutor fall-through
  extends to writes (a tutor answered and finalized another student's exam); `access` is now a
  **required** argument and writes fail closed, with the read half explicitly left to S43/S46.
  **AUD-X-02** — SPEC §5.1.2's consent claims were read by **nothing**; enforced in shared code
  across **four** call sites, because both SSE routes verify `?token=` directly and bypass
  `get_current_claims`. **AUD-C-01 + AUD-C-04** (together, per D-101) — `/messages` had no ownership
  check and an anonymous turn *erased* the owner; separately, a paused turn answered with the
  previous turn's answer, which is what made C-01 a disclosure rather than a missing check.
- **Merged 19 pending PRs and cleaned the branch list (D-108).** The repo had **24 open PRs and zero
  ever merged**. Every dependabot PR's CI was stale (2026-07-24, pre-S40), so they were verified as a
  *combination* in an integration branch, not on their own badges. Five held back with written
  reasons. `main` is now the only branch.
- **Verification:** `make lint` clean, `make typecheck` clean (pyright 0 errors), **537 passed / 2
  skipped, three consecutive runs** (519 → 537; 18 regression tests). **Every new test was confirmed
  to fail with its own fix disabled** — which is how two of them were found to be asserting nothing.
  Migration replays from empty. CI green on every PR; deployed via the pipeline (`c58d1fe`).
- **Carry-over:** the `question_variants` orphan sweep (56,938 rows) and the `checkpoints` sweep
  (325,606) — now optional hygiene rather than prerequisites; AUD-L-07's read half (S43/S46); the
  five held-back dependency PRs; e2e suite intermittency (49–50/51) still blocking criterion 3.
- **New decisions:** **D-106**, **D-107**, **D-108**.

### S37 — AUD-C, chat product correctness (2026-07-25) ⏸ partial
- **Audited the chat product against SPEC §5.19–§5.24, §5.25.3, §5.29, §5.30.2/.4**: traceability,
  defect-pattern sweeps, API-level adversarial runs, and a bounded live-staging pass. 16 findings
  (AUD-C-01..16), three P1, all logged in AUDIT_FINDINGS.md with reproductions; none fixed, per
  §2.4's rule that mid-audit fixes are reserved for P0s.
- **Extended the golden Q&A eval and measured it twice.** Fixture 40 → 61 cases with `paraphrase`,
  `no_answer`, `adversarial` and `role_gated_question`; scoring extracted to
  `packages/evals/qa_coverage.py` so both runners compute identically; new opt-in, spend-capped
  `test_qa_coverage_eval_real_bedrock.py`. The real run (Haiku 4.5 + Titan v2, 76.7¢) showed the
  suite's 100% scores were measuring `MockBedrockProvider`, not retrieval — `grounded` 11.1% and
  `role_gated` 0% real vs 100% mock, `no_answer` 8/8 real vs 0/8 mock.
- **Three P1s:** AUD-C-01 `/messages` has no ownership check and an anonymous turn erases the owner
  `/respond` and `/stream` check (verified live on staging, with tutor text reaching an anonymous
  response locally); AUD-C-02 the scope prompt omits SPEC §5.19.4's first topic so live staging
  refuses "What is IntelliChoice?" 5/5; AUD-C-03 precise coordinates persist in
  `checkpoint_writes.__resume__` against a consent notice promising otherwise.
- Verification: `make lint` clean, `make typecheck` clean (pyright 0 errors), **513 passed /
  2 skipped**. Dev DB verified intact afterwards (23 documents / 159 chunks, zero probe leftovers).
- Carry-over: browser-driven rendering and SSE-drop verification (the ⏸); whether staging's corpus
  holds real or mock embedding vectors (AUD-C-16) — first thing for S38's live pass.
- New decisions: **D-101**.

### Session 32 — Deployment architecture decision + first deploy (2026-07-22) ✅
- **Decision-gated session, decided at start**: confirmed D-004 as corrected by
  D-082/D-083 — ECS Fargate + RDS PostgreSQL/pgvector + RDS MySQL (IntelliChoice's own
  seeded fixture DB standing in for `go.intellichoice.org`'s shape, not a managed
  instance of the real external system), not EKS/Aurora/managed-Mongo. User also
  approved, beyond D-004's original minimal-smoke-test framing: real AWS credentials,
  real Bedrock (not kept mocked), both frontends deployed alongside both backends,
  "close to production posture" sized for <2,000 MAU. Full design, every real bug found
  and fixed live against real AWS, and live-verification results are in **D-084** — this
  entry summarizes.
- **What was built.** `terraform/modules/{vpc,ecr,iam,rds-postgres,rds-mysql,alb,
  ecs-service,ops-task,cloudfront-spa-api,observability}` + `terraform/environments/
  staging/`; `apps/{learning-api,chat-api}/Dockerfile` + root `.dockerignore`. Same-
  origin CloudFront design (frontend + path-routed API on one domain, matching
  `main.py`'s own long-standing comment about the intended real deployment shape) - zero
  CORS, no mixed-content problem, no registered domain needed (CloudFront's default
  `*.cloudfront.net` cert). VPC interface endpoints instead of a NAT Gateway (ECR,
  Logs, Secrets Manager, Bedrock runtime), single-AZ after finding live that 2-AZ
  endpoints cost *more* than a NAT Gateway would have. ARM64/Graviton Fargate (cheaper,
  matches building locally on Apple Silicon). A monthly AWS Budget alarm as the
  account-level Bedrock-spend backstop the existing per-session/per-day ceilings don't
  provide.
- **Real staging environment is live**: `intellichoice-staging` — VPC, ALB, ECS cluster
  running both services (healthy, real DB connectivity), both RDS instances (all 24
  Alembic migrations + MySQL schema/fixture seed applied), both frontends on S3+
  CloudFront, real AWS Bedrock wired in (Bedrock model-access EULA accepted via CLI,
  closing D-025's "never exercised against real AWS" caveat for both
  `AnthropicBedrockProvider` and `TitanEmbeddingProvider`).
- **Real credential leak found and remediated live, not caught in review**:
  `seed_mysql.py`'s own `print(...)` statement put the real RDS MySQL master password
  into CloudWatch Logs (and the session transcript, since the log was read back).
  Rotated the password immediately (`terraform apply -replace=...random_password.
  master`), deleted the log stream, fixed the source to redact before printing
  (`sqlalchemy...render_as_string(hide_password=True)`), re-verified clean. Root cause:
  the line was written when the only URL in play was the local dev placeholder
  (not a secret) and had never been pointed at a real credential before.
- **Also found and fixed live** (full list in D-084): a missing `cryptography`
  dependency that would have broken both real services' MySQL auth, not just the seed
  script (caught via a pre-deploy dry run, before either service was deployed); an
  ALB/CloudFront timeout ceiling shorter than the Bedrock gateway's own worst-case retry
  latency (real 504s reproduced live through the browser); a circular Terraform module
  dependency (RDS's "allow the ECS task SG" rule vs. the task's "needs the DB secret
  ARN" input) resolved by moving the shared SG to a plain root resource; a nonexistent
  RDS MySQL engine version, this AWS account's Free Tier restrictions rejecting the
  original instance class/backup-retention choices, a security-group description
  character-set rejection, an ALB/target-group 32-char name limit, and arm64-vs-Fargate
  x86_64-default needing an explicit `runtime_platform` block.
- **Verification**: `make lint && make typecheck && make test` stayed green throughout
  (470 passed, 1 skipped). All 24 Alembic migrations ran clean against real RDS
  Postgres. A real Playwright run against the live CloudFront URLs (not curl) confirmed
  both frontends load with 0 console/page errors and correct branding, and a guest
  chat-api query round-tripped through CloudFront→ALB→ECS→pgvector (empty - no
  `knowledge-content` ingested into this fresh staging DB) and correctly returned the
  fail-closed "no approved source" message (SPEC §5.29). A "real 200 response" from an
  early Bedrock call turned out, on closer inspection, to be the app's own fail-closed
  fallback (`OUT_OF_SCOPE_MESSAGE`, triggered by `except BedrockGatewayError`) - not
  genuine LLM content; corrected in D-084. The actual root cause was two more real bugs,
  found via continued live troubleshooting after this session's initial wrap-up: the
  `anthropic` SDK's `AnthropicBedrockMantle` client calls a **different PrivateLink
  service** (`bedrock-mantle.<region>.api.aws`) than the `bedrock-runtime` VPC endpoint
  already built covered, and once that was added, a second gap - `bedrock-mantle` uses
  its own distinct IAM action/resource namespace
  (`bedrock-mantle:CreateInference`/`ListModels` on a `project/default` ARN, not
  `bedrock:InvokeModel` on a model ARN). Both fixed. Also explored, at the user's
  direction, whether Claude Haiku 4.5 or GPT-5.6 Luna could substitute for Sonnet 5 on
  this specific code path - both correctly ruled out (Haiku 4.5 isn't offered on the
  Anthropic-compatible Mantle surface at all for this account; GPT-5.6 Luna needs its
  own undocumented-outside-its-model-card `/openai/v1/responses` path, and once called
  correctly, hit a real "not available for this account" gate with no CLI-discoverable
  grant flow) - confirming Sonnet 5 was the right model all along, now blocked purely by
  quota with every other layer fixed. Reverted the model config back to the code default.
- **Two more real bugs found via the user's own manual testing** (full detail in D-084):
  both `main.py`s register a few routes directly on `app`, outside any router's path
  prefix (`learning-api`'s `/dev/token`/`/students/{id}/attendance`, `chat-api`'s
  `/dev/token`/`/me`) - CloudFront only routed `/learning/*`/`/chat/*` to the ALB, so
  these fell through to the S3 default behavior, returning a non-JSON 404. That in turn
  hit a second, independent bug in both frontends' shared fetch error handler - reading
  a `Response` body twice (`res.json()` then `res.text()` in a catch block) throws
  `TypeError: ... body stream already read` instead of recovering, crashing the whole
  error path. Fixed both: added the missing paths to each CloudFront distribution's
  routed patterns, and fixed both `client.ts` files to read the body once and
  `JSON.parse` that string. Rebuilt, redeployed, invalidated caches, re-verified live -
  `learning-web` sign-in (still 404s in staging by design) now shows a clean inline
  error instead of crashing.
- **User then asked to enable dev sign-in on staging + a full holistic test** (new
  `app_environment` Terraform variable, `"dev"` in tfvars only after explicit
  approval - `/dev/token` is a documented "must never exist in a real deployment"
  backdoor, acceptable for non-customer-facing staging only). This unlocked a real
  authenticated pass that found five more genuine bugs (full detail in D-084): the
  earlier CloudFront routing fix was only half-done (ALB has its own separate listener
  rules that also needed the new paths); `/dev/token` is a real cross-app path
  collision on the one shared ALB, disambiguated via an `X-IntelliChoice-App` origin
  header + two header-matched listener rules; the `"[object Object]"` fix was also
  incomplete (FastAPI wraps errors as `{"detail": ...}`, and the fix stored the whole
  wrapper instead of unwrapping it); **neither Docker image ever included the
  repo-root `curriculum/`/`knowledge-content/` directories** (`.dockerignore` had
  explicitly excluded the latter) - every content-load attempt failed with
  `FileNotFoundError`, meaning no student could ever select a topic; and
  `intellichoice_db.engine.create_engine()`'s hardcoded `localhost` default had no env
  override at all (the same bug class `alembic/env.py` already had once this session),
  fixed once at the shared source rather than per-caller. Curriculum (3 topics, 50
  templates) and knowledge content (23 documents, 159 chunks) are now genuinely loaded
  into the real deployment. Rebuilt/redeployed twice more (v4, v5) - lint/typecheck/
  test and `terraform plan` stayed clean throughout. Full re-verification via real
  browser + real auth + real content: present and absent students both reach the app,
  and the absent student correctly hits a real, well-formatted attendance-gate block
  screen with SPEC §5.6.3's two choices when starting a session - the fail-closed
  design is confirmed working end-to-end in the real deployment. Zero console errors
  across every scenario tested.
- **GitHub repo creation and CI wiring - resolved 2026-07-23** (see D-084's addendum):
  `gh auth login` done, repo created (`lucasjeongsikpark/IntelliChoice`, private, first
  commit of all 484 files), `ci.yml` fixed (was never run against real GitHub Actions
  before - missing DB service containers, then missing seed/content-load steps once DB
  connectivity was fixed, both found live) and green, GitHub OIDC deploy role wired into
  `terraform/modules/iam` (narrowly scoped, `terraform plan` clean before/after),
  `deploy-staging.yml` written (`workflow_dispatch` only, not auto-triggering on push
  until it's been run once). No longer a carry-over item.
- **Carry-over**: Custom domain + ACM + Route53 (registration guidance
  given separately, not scripted this session). Production environment. Real hosted
  Prometheus/Grafana for the deployed environment - CloudWatch Container Insights
  (enabled) covers the immediate S31-carry-over gap (CPU/memory/task-count metrics with
  a real runtime to scrape) but isn't a dashboard replacement. Left the real staging AWS
  environment running (not torn down) - unlike prior sessions' "seed data" footprint,
  this is real ongoing infrastructure cost, tracked via the new Budget alarm.
- **Model-access follow-up, resolved (2026-07-23) - see D-084's addendum**: the "Bedrock
  Sonnet 5 Mantle quota pending" item above turned out to be only half the story - Sonnet
  5 is *also* blocked on Mantle by the same account-wide "not available for this account,
  contact AWS Sales" gate found later to block GPT-5.6 too, confirmed unaffected by
  broader IAM (`AmazonBedrockFullAccess`/`AmazonBedrockMantleFullAccess` tested directly
  on the task role, no change). Gemma 4 works on Mantle for simple schemas but hangs
  (150s+) on the app's real nested response schemas. **Bedrock Mantle abandoned
  entirely** - `AnthropicBedrockProvider` rewritten to use classic `bedrock-runtime`'s
  `converse()` API (plain `boto3`, same client `TitanEmbeddingProvider` already used;
  `anthropic` SDK dependency removed) calling **Claude Haiku 4.5**, which has real
  granted access and quota on this account today. Redeployed (`s32-haiku-v1`), live
  `bedrock_call` logs from both apps confirm real ~1.5s responses with correct structured
  output through the actual browser. The dead `bedrock-mantle` VPC interface endpoint and
  IAM statement were removed (~$7.30/mo saved).

### Off-roadmap — MySQL dev-fake swap, executing D-082/D-083 (2026-07-22) ✅
- **Not a numbered roadmap session** — triggered directly by the user correcting a wrong
  assumption (`go.intellichoice.org`'s real database is MySQL, not MongoDB, logged
  2026-07-21 as D-082) and asking for the dev-fake to actually be swapped, not just left
  as a documented TODO. No ROADMAP.md "Done when" criteria apply here; S32 remains the
  next numbered session.
- **What was built (D-083).** `MongoProfileAdapter` (`motor`) → `MySQLProfileAdapter`,
  built on SQLAlchemy Core (`create_async_engine` + `text()`) + `aiomysql`, not a raw
  driver — chosen because no OpenTelemetry instrumentor for `aiomysql` exists (verified
  via web search; open-telemetry/opentelemetry-python-contrib#1787 is an open,
  unresolved request), so this reuses `opentelemetry-instrumentation-sqlalchemy`
  (already a dependency) instead of adding a new one. `docker-compose.yml`'s `mongo:7`
  → `mysql:8.4`; schema created by a new `mysql-init/001-schema.sql` init script (4
  tables — `parent_child_links` is now a normalized junction table, not Mongo's array
  field). Seed scripts, both apps' `config.py`/`main.py`, and all 8 test files that held
  a live Mongo client were rewritten. `.env.example` updated too (required the user to
  widen their own `~/.claude/settings.json` `Read(./.env.*)` deny rule, which had been
  blocking `.env.example` along with real `.env` files).
- **Found and fixed a second real instrumentation-ordering bug, same family as D-081's
  Pymongo one.** `SQLAlchemyInstrumentor` is a process-wide singleton — instrumenting
  two engines via two separate `.instrument(engine=...)` calls silently drops the
  second engine's spans (open-telemetry/opentelemetry-python-contrib#1103, verified
  independently via web search + a local repro). Fixed by
  `tracing.instrument_sqlalchemy_engine` (singular) → `instrument_sqlalchemy_engines`
  (plural, one combined `.instrument(engines=[...])` call); both apps now pass their
  Postgres engine and `MySQLProfileAdapter.engine` together. Two new regression tests
  in `test_instrumentation_ordering.py`.
- **Found and fixed a real resource-cleanup bug live verification surfaced.**
  `aiomysql`'s `Connection.__del__` raises `RuntimeError: Event loop is closed` if a
  `MySQLProfileAdapter` is never disposed before its owning event loop tears down
  (Motor's client didn't have this failure mode) — surfaced as a
  `PytestUnraisableExceptionWarning` in `test_stream_and_history.py`'s two
  standalone-adapter helpers. Fixed with an explicit `await profile_adapter.close()`
  in both `finally` blocks.
- **Docs.** New D-083 decision entry; corrected this file's own "Current status" and
  `docs/ROADMAP.md`'s S32 section, both of which repeated D-004's stale "managed Mongo"
  recommendation — doubly wrong, since `go.intellichoice.org` is pre-existing external
  infrastructure IntelliChoice doesn't provision at all, not just the wrong engine
  name. `docs/ARCHITECTURE.md` updated (mermaid diagram node, PII-boundary table row,
  several inline mentions) since the dev-fake's actual database engine is real
  architecture, not just wording — this was **not** a full sweep of every remaining
  "MongoDB" mention repo-wide (SPEC.md's 41, FINAL_ARCHITECTURE.md's 4, CLAUDE.md's 3,
  and ROADMAP.md's other ~11 mentions are still outstanding, deferred to a dedicated
  docs session per D-083).
- **Verification.** `make lint && make typecheck && make test` all green — live against
  a real `mysql:8.4` container, not mocked or skipped: schema/seed verified row-by-row
  via direct `mysql` client queries, seed idempotency confirmed by re-running and
  diffing row counts, all 7 `MySQLProfileAdapter` tests passed live, full suite 470
  passed / 1 skipped (unrelated — needs real AWS creds) on 2 of 3 runs; one run hit
  `test_hint_reflects_the_students_actual_wrong_option`, a pre-existing cross-test-order
  flake (passes in isolation and on repeat runs — confirmed unrelated to this session's
  changes).
- **Carry-over:** SPEC.md/FINAL_ARCHITECTURE.md/CLAUDE.md/ROADMAP.md's remaining ~59
  combined "MongoDB" mentions need a wording sweep in a dedicated docs session. Whether
  the real `go.intellichoice.org` integration is direct MySQL access or an HTTP API
  fronting it is still unconfirmed — needed before building the real (non-dev-fake)
  adapter; ask before assuming either.
- **New decisions:** D-083 (plus a dated correction note appended to D-004 — its
  original 2026-07-13 text is left as historical record, not rewritten).

### S31 — Observability (2026-07-21) ✅
- **Design (D-081).** New `packages/observability` package (mirrors D-014/D-036's "pure
  logic, not persistence" split): `logging_config.py`, `tracing.py`, `metrics.py`,
  `request_logging.py`, `langsmith_config.py`. Both apps' `main.py` wired at startup;
  KPI-recording calls added at existing service call sites across both apps
  (instrumentation only, no new business logic). `packages/adapters` gained the
  package as a dependency for the Bedrock gateway span (every CLI worker gets tracing
  for free). `docker-compose.yml` gained `otel-collector`/`jaeger`/`prometheus`/
  `grafana`; `observability/` holds their config (alert rules, 3 provisioned Grafana
  dashboards covering every named SPEC §5.32.4 KPI except container-runtime metrics).
- **LangSmith forced-mask, not selective.** `LANGSMITH_HIDE_INPUTS`/
  `LANGSMITH_HIDE_OUTPUTS=true` whenever `LANGSMITH_API_KEY` is present — the only
  granularity `langgraph`'s env-var-driven default tracer actually supports, and this
  project has no contractual basis yet for judging any subset of a trace "safe" to send
  unmasked. No real LangSmith account exists (D-002 posture) — unexercised by design.
- **Alerting is rules-only.** Prometheus evaluates real alert rules (HTTP error rate,
  attendance-block rate, tutor-review-flag rate, Q&A no-answer rate, session-cost-vs-
  budget) visible in its own `/alerts` UI; no Alertmanager/real notification channel
  (no Slack/email/PagerDuty creds exist).
- **Found and fixed two real bugs via this session's own live verification against a
  running Jaeger, neither visible from unit tests (D-081).** `FastAPIInstrumentor`/
  `PymongoInstrumentor` both silently produced zero spans when instrumented from inside
  `lifespan`: Starlette caches its middleware stack on the very first ASGI call an app
  receives, and that first call is the `"lifespan"` startup message itself, so patching
  `build_middleware_stack` from inside the function that call triggers is always too
  late; separately, `pymongo.MongoClient.__init__` (wrapped by `motor`, used by
  `MongoProfileAdapter`) snapshots the global listener list at construction time, and
  `lifespan` constructs the Mongo adapter before instrumentation used to run. First
  symptom: a real trace's root span was `langgraph.select_topic` (a manual span), never
  the expected `POST .../topics` FastAPI span — DB/LangGraph spans existed and shared a
  trace_id among themselves, but nothing wrapped them. Fixed by moving both
  `configure_tracing_provider()`/`instrument_fastapi_app()` to module level, before
  `app = FastAPI(...)` and before any Mongo client is ever constructed; only
  `instrument_sqlalchemy_engine()` stays lifespan-scoped, since only there does the
  per-lifespan `Engine` instance exist. Two new regression tests
  (`packages/observability/tests/test_instrumentation_ordering.py`) encode the ordering
  contract directly, so a future "simplification" back into `lifespan` fails loudly.
- **Resolved the standing D-032 caveat** (SSE `?token=` bearer values leaking into
  access logs): the new access-log middleware logs the route *template* only (never
  `request.url`/the raw query string), and `configure_logging` disables uvicorn's own
  plain-text access logger, which did log the full raw request line.
- **Tests (+16 net, 452→468, stable across 3 repeated `make test` runs):** PII-denylist/
  JSON-formatter tests, nested-span/shared-trace_id tests, KPI counter/histogram tests,
  the query-string-redaction access-log test, LangSmith env-gating tests, and the two
  instrumentation-ordering regression tests.
- **Verification:** `make lint && make typecheck && make test` — 468 passed, 0 lint/
  type errors, stable across 3 repeated runs. Live-verified against the real running
  `learning-api` dev server plus the real compose observability stack (otel-collector,
  Jaeger, Prometheus, Grafana all actually started and queried, not assumed): a real
  `create_session → select_student → select_topic` HTTP flow produced one trace with
  `POST .../topics` (FastAPI) as root, `langgraph.select_topic` as its child, and 48 real
  Postgres `INSERT`/`SELECT` spans as *its* children, all one `trace_id` — satisfying the
  ROADMAP's literal "Done when" criterion; a separate attendance-check call produced a
  trace with a real Mongo `find` command span correctly nested under the FastAPI root.
  Prometheus's `learning-api` scrape target reported `up` with real KPI values populated
  after the same flow (`learning_session_starts_total 1`, a labeled
  `http_requests_total` per route). Grafana auto-provisioned all 3 dashboards + both
  datasources with zero manual clicks, confirmed via its own API. JSON access logs
  confirmed no `?token=`/raw query string anywhere across the whole flow. Left a handful
  of real `assessment_sessions`/checkpoint rows for `student-ext-4` in the shared dev
  Postgres from this session's own verification flows (never reached `finalize_exam`) —
  same "useful seed data, small bounded footprint" reasoning prior sessions gave.
- **Also found (same triage precedent as S9/S12/S14/S20/S22/S23), not a regression from
  this session's own code but tipped over by this session's own live-verification
  traffic:** `packages/curriculum/tests/test_ai_pipeline.py::
  test_solver_disagreement_rejects_without_persisting`'s deterministic-seed-generated
  candidate (`"Solve for x: x/6 + 7 = 4"`, seed 700666 — the test's own comment already
  documents this exact class of risk) collided with an already-committed, unreferenced
  `question_variants` row, rejecting for "duplicate rendered_question" before it ever
  reached the solver-disagreement check the test means to exercise. The colliding
  template (`linear_equations-d3-24`) had **1000+ accumulated variant rows** — this
  session's own `select_topic` pre-exam builds (driven against the real shared dev
  Postgres for live trace/metrics verification) plausibly tipped an already-fragile
  D-053 carry-over into an actual failure; the 3 clean `make test` runs earlier in this
  session (before that live-verification traffic) did not hit it. Fixed the same way
  prior sessions did: deleted the one specific offending row (verified unreferenced by
  any `study_attempts`/`assessment_items`/`hint_events`/`learning_events` row first),
  confirmed 468/468 stable across repeated runs afterward. The underlying unbounded
  `question_variants` accumulation is still not fixed (D-053) — now well past 1000
  copies for some templates, worse than every prior session's count; a future session
  should treat this as higher priority than the "someday" framing prior entries used.
- **Carry-over:** CPU/memory/pod-count metrics aren't built (no deployed container
  runtime yet to scrape from — S32's decision, D-004). `otel_enabled`/`CHAT_OTEL_ENABLED`
  default to `False` in both apps — a real dev/staging run must set them explicitly.

### S30 — Evaluation platform (2026-07-20) ✅
- **Scoping (D-080).** The S19/S20-era golden fixtures (`qa_coverage_eval.yaml`, the 5
  authored-pipeline bad-item tests) were registered, not rewritten into a generic
  YAML-driven runner — they're procedural (the near-duplicate case needs two sequential
  candidates), already pass, and already satisfy ROADMAP S20's own "Done when" wording;
  rewriting working, well-tested logic to fit a documentation goal would have been an
  unnecessary rewrite. New `packages/evals/src/intellichoice_evals/registry.py` instead
  maps every SPEC §5.31.1–§5.31.4 named item to the repo-relative test file(s) that
  already cover it (file-existence granularity), with an explicit
  `not_applicable_reason` for the few items with no matching feature (image deletion
  event — S29 deferred, D-078; SQL parser validation — no NL2SQL feature exists,
  CLAUDE.md non-negotiable #2; prompt injection — deferred to S33).
  `test_registry_coverage.py` is the actual regression gate for "did coverage silently
  drop."
- **Real LLM-as-judge wiring.** `BedrockTask.LLM_JUDGE` (reserved, uncalled since S8,
  D-022) gets its first real caller: new `LlmJudgePayload`/`RubricDimensionScore`/
  `LlmJudgeResponse` (`packages/shared/bedrock.py`), a `MockBedrockProvider` handler,
  and `intellichoice_evals.llm_judge.run_llm_judge` + the two SPEC §5.31.3 dimension
  lists (learning: 6, Q&A: 5) verbatim. New `EvalSettings.bedrock_judge_model_id`
  defaults to a different model (`anthropic.claude-haiku-4-5`) than either app's
  production answerer (`anthropic.claude-sonnet-5`) — satisfies "different model...when
  possible" architecturally, unverified against real creds (D-025 posture, same as
  everywhere else). A `pytest.mark.skipif`-gated test wires a real
  `AnthropicBedrockProvider`-backed gateway call — skips in this environment (no real
  AWS creds anywhere in this project's history) but proves the wiring is correct.
- **Found and fixed a real bug via the new hint-leak-detection golden fixture, not
  previously known (D-079).** `packages/evals/src/intellichoice_evals/leak_sample.py`
  reuses the existing `leak_phrase_present`/`answer_text_leaked` functions
  (`packages/curriculum/authored_validation.py`) against a fixture of answer/hint pairs
  varied by format (negative integers, fractions, decimals) rather than reimplementing
  detection logic. The negative-integer case failed: `answer_text_leaked`'s
  `\b`-anchored regex can never match an answer starting with a non-word character (a
  leading `-`), so a hint stating a negative correct answer outright ("The answer is
  -4...") was never caught by either the S20 pipeline gate or the S21/S24 runtime
  fallback check — a live gap in a safety-critical check, not theoretical (negative
  integer answers are real and reachable via `format_integer`'s `Fraction.numerator`).
  Fixed with lookaround assertions (`(?<![0-9A-Za-z])...(?![0-9A-Za-z])`) instead of
  `\b` — verified against the full existing suite (no regressions, strictly stricter)
  plus the new fixture's 9 cases.
- **Exam-flow determinism** landed as a pure-function evaluator in
  `apps/learning-api/tests/test_exam_flow_determinism.py` (`grade`/`weighted_score`/
  `support_dependency` called twice with identical inputs), not inside `packages/evals`
  — that package depends only on `intellichoice_shared`/`adapters`/`curriculum`, never
  an app (D-009/D-014's direction).
- **Verified the literal ROADMAP "Done when" bar, not just claimed it:** temporarily
  replaced `grading.grade`'s `==` with a hardcoded `True`, confirmed
  `test_exam_flow_determinism.py::test_grade_is_deterministic` failed immediately, then
  reverted.
- **Tests (+11 net, 441→452 collected, stable across 3 repeated `make test` runs):** 11
  new across `packages/evals/tests/` (`test_registry_coverage.py` ×3,
  `test_leak_sample.py` ×2, `test_llm_judge.py` ×4 incl. the skip-gated real-creds test)
  and `apps/learning-api/tests/test_exam_flow_determinism.py` (×3).
- **Verification:** `make lint && make typecheck && make test` — 452 passed, 1 skipped
  (the real-creds judge test), 0 lint/type errors, stable across 3 repeated runs. No
  schema change this session, so no Alembic round-trip needed. No frontend touched, so
  no Playwright pass needed — this session's surface is entirely backend test/eval
  infrastructure with no runtime behavior to click through.
- All 3 ROADMAP S30 "Done when" criteria hold: a deliberately broken grading rule fails
  the suite (verified directly, not assumed); the judge harness is correctly wired to
  run against staging creds (unexercisable here, D-025 posture, same as every other
  "never tested against real AWS" caveat); the plan-§13 suites (leak detection, judge,
  exam-flow determinism; memory/report grounding already existed and are now
  registered) are wired into the same `pytest`/CI gate.
- Carry-over: no dedicated prompt-injection fixture yet (deferred to S33); "SQL parser
  validation" has no feature to validate; the image-deletion-event evaluator is N/A
  until S29 is un-deferred.
- New decisions: D-079, D-080.

### S29 — Multimodal solution images (2026-07-20) — deferred, not built
- `/start-session` produced a plan (upload endpoint outside the graph; consent-to-analyze
  as a new `"image"` choice on the existing `intervention_choice` interrupt, resumed with
  only an opaque `image_key` — never image bytes — so nothing crosses the LangGraph
  checkpoint boundary; `BlobStore`+`Fernet` encryption; `MalwareScanner` fake; new
  `BedrockGateway.analyze_image`; a restricted-`ast` executable math validator for
  VLM-extracted steps), confirmed via `AskUserQuestion` against the one genuine
  architectural fork (interrupt-choice extension vs. a standalone plain-service flow like
  S24's chat).
- **User declined to build the session at all**, before any file was touched — see D-078.
  Reasoning: a real photo of a K-12 minor's solution work can incidentally capture a face,
  other homework, or a home background, a privacy question the spec's own §5.1.4/§5.17.2
  language doesn't resolve; and every supporting dependency (malware scanner, S3
  encryption-at-rest) is still on the D-002 "no real creds yet" footing, so this session
  would only stack fakes on fakes without answering the actual open question.
- **Nothing built, nothing changed in code.** ROADMAP's S29 entry stays as a design
  reference, marked deferred (not deleted). `docs/` (this file, ROADMAP.md, DECISIONS.md)
  are the only files this session touched.
- New decisions: D-078.

### S28 — Progress dashboard and student report (2026-07-20) ✅
- **Decide-at-session-start (user-approved):** branch-manager reuses the tutor field
  set as a single-student stand-in; real cross-student cohort aggregation deferred (no
  student→branch roster exists in the Learning API domain) — see D-077 #1.
- **Build:** `packages/db` `DashboardRepository` (date-range SQL filtering: learning
  gains, study attempts+items, assessment attempts+sessions, assessment time) +
  `learning_api/services/dashboard.py::build_dashboard` (pure-Postgres DTOs, no LLM) +
  new `student_reports` model/repo (one Alembic migration, not idempotency-keyed) +
  `learning_api/services/report.py` (audience-gated `ReportInterpretationPayload`
  reusing `BedrockTask.PARENT_REPORT`, numeric-grounding check, facts-only fallback —
  same pattern as S26's stage narratives). Two new routes on `routers/students.py`.
  New learning-web `StudentDashboardScreen.tsx` (replaces `ParentDashboardScreen.tsx`,
  6 Recharts chart types + date-range presets) + `ReportView.tsx`. Chart palette
  follows the `dataviz` skill's validated reference slots as local `--viz-series-*`
  tokens (brand hues failed dark-mode validation).
- **Found via this session's own Playwright verification, not previously known:** the
  S11 parent-auto-select gap also blocks a single-child parent from reaching the new
  dashboard through the real UI; not fixed (same root cause as the existing gap),
  worked around in verification by seeding `sessionStorage` directly.
- **Tests (+16 net, 425→441, stable across 3 repeated `make test` runs):** `test_
  dashboard.py` (2, date-range filtering), `test_report.py` (7, audience gating +
  scripted-gateway grounding/fallback), `test_dashboard_report_endpoints.py` (4, HTTP
  wiring + role-based gating + auth), 3 new `test_bedrock_payload_pii_floor.py` cases.
- **Verification:** `make lint && make typecheck && make test` — 441 passed, 0 lint/
  type errors, stable across 3 repeated runs. Alembic round-tripped 3x. Both apps'
  `npm run build`/`npm run lint` clean (learning-web only). Live-verified via a
  scripted Playwright run (temp install in the scratch directory, D-034 convention): a
  real pre→study(with a hint round)→post cycle over raw HTTP produced real dashboard
  data (6 chart types rendered, screenshots confirmed clean after fixing an initial
  Y-axis label-overlap issue), report generation produced grounded text for a real
  gain, and a parent view correctly showed the facts-only fallback plus the
  `tutor_review_flagged` fact the student view never receives — 0 console errors
  across both role flows.
- All 4 ROADMAP S28 "Done when" criteria hold: all listed visualizations render with
  range filtering; every number in a generated report traces to a stored fact; student
  and parent views differ per the authorization rules; the keyboard/Playwright pass is
  clean.
- Carry-over: real cross-student cohort aggregation for branch-manager reports not
  built; `student_reports` has no retention/purge job yet; the S11 parent-dashboard
  gap now also covers the new dashboard/report screens.
- New decisions: D-077.

### S27 — Khan Academy video bank hardening (2026-07-20) ✅
- **Build:** real `YoutubeProvider` (`packages/adapters/youtube_data_api_provider.py`,
  httpx-based) behind the existing Protocol - unexercised (no real YouTube Data API key,
  D-002), env-selected via `YoutubeSyncSettings.youtube_provider`. Channel pin enforced
  in `catalog_sync.sync_channel` itself (never trusts the provider's own filtering) -
  `FakeYoutubeProvider.list_uploaded_videos` no longer pre-filters by channel_id so the
  hardening test actually exercises the sync layer's own check. One combined
  `YoutubeProvider.get_video_details` call (`videos.list(part=status,contentDetails)`)
  covers the new verification pass, license, and caption-availability together - no
  separate `captions.list` call this session. New `youtube_videos` columns
  (`prerequisite_skill_ids`, `transcript_available`, `transcript_language`, `license`,
  `last_verified_at`, `suitability_status`, `verification_failures`; one Alembic
  migration). `prerequisite_skill_ids` is derived deterministically in
  `catalog_sync.py` from classified `skill_ids` via `CurriculumContent.
  prerequisite_for` - never an LLM output. `video_catalog.search_video` gained
  optional misconception-tag/grade-band/mastery-state query enrichment (widens the
  embedding query text only, never a hard filter); `search_catalog` gained an
  unconditional `suitability_status == "approved"` gate. New `topic_resolver.
  resolve_mastery_state` helper reuses the existing `WEAK_SKILL_THRESHOLD`.
  `graph/nodes.py::_video_intervention` now resolves and forwards all three
  enrichment values.
- **Tests (+5 net, 420→425, stable across 3 repeated `make test` runs):** off-channel
  rejection and verification-pass reversibility (`packages/youtube/tests/
  test_catalog_sync.py`), reversible verification and suitability-status exclusion
  (`packages/db/tests/test_repositories.py`), a `_CapturingGateway` proving the
  enriched query text reaches the embedding call
  (`apps/learning-api/tests/test_video_catalog.py`).
- **Verification:** `make lint && make typecheck && make test` — 425 passed, 0 lint/
  type errors, stable across 3 repeated runs. Alembic `upgrade head`/`downgrade -1`/
  `upgrade head` round-tripped 3x (every new non-nullable column carries a
  `server_default` since the shared dev Postgres already has real S15/S17 seed rows to
  replay against). Live-verified via `make youtube-sync` against the real shared dev
  Postgres (fake provider, the only exercisable path): all 4 real videos re-synced with
  `prerequisite_skill_ids` correctly populated (e.g. `ka-two-step-eq` →
  `["linear_one_step"]`), `last_verified_at`/`suitability_status`/
  `verification_failures` populated as expected, `active_status` unaffected.
- All 4 ROADMAP S27 "Done when" criteria hold: only official-channel rows enter the
  catalog; a removed video stops being recommended after one sync; recommendation
  input includes grade band + misconception when available; sync failure keeps the
  previous catalog (existing S15 property preserved).
- Carry-over: `transcript_language` is an approximation (the video's own language,
  stored only when captions are available) rather than a true per-track caption
  language - a real value needs a separate `captions.list` call per video, skipped
  this session (unexercisable without real creds anyway). `suitability_status` is
  schema-ready but nothing sets it to anything other than `"approved"` yet - no
  content-review step exists. The verification pass's `except Exception` swallows a
  real API outage silently by design (must not undo an already-successful sync); no
  retry/alerting exists, fine at this catalog's small scale.
- New decisions: D-076.

### S26 — Personalized stage introductions and transitions (2026-07-20) ✅
- **Decide-at-session-start (user-approved):** inline service calls instead of a real
  graph node (build all 5 stages from the plan's schema, not just the 3 ROADMAP's build
  list named, including newly-invented trigger definitions for `pre_intro`/`study_step`)
  — see D-075 #1-2 for the full reasoning.
- **Build:** new `STAGE_NARRATIVE` Bedrock task + `StageNarrativePayload`/
  `StageNarrativeResponse` (`packages/shared/bedrock.py`); new shared
  `intellichoice_shared.numeric_grounding` module (extract-numbers + exact/
  nearest-integer/one-decimal-rounded matching against a deterministic evidence dict —
  D-075 #3); new `packages/db` `StageTransition` model/`StageTransitionRepository` (one
  Alembic migration); new `learning_api/services/stage_narrative.py`
  (`generate_stage_narrative`: idempotency check → Bedrock call → grounding check →
  deterministic-template fallback on either failure → persist). Wired inline (zero new
  graph nodes/edges) from `graph/nodes.py::finalize_exam` (×2, `pre_outro`/`post_outro`)
  and a new shared `_fire_study_transition_narrative` helper (`submit_answer`/
  `intervention_choice`, `study_step`/`study_outro`, triggered off a new
  `flow.AnswerResult.new_target_skill_id` field that's set only on a genuine skill-line
  transition, never a same-skill retry); `routers/stream.py`'s SSE connect path fires
  `pre_intro` outside any graph turn. New learning-web `StageTransitionScreen`
  (narrative + collapsible "How we personalized this" evidence list + Continue),
  interposed in `App.tsx` ahead of the phase branches, dismissal keyed by the narrative
  text itself.
- **Found and fixed a real, pre-existing, cross-cutting bug via this session's own live
  Playwright verification, not previously known (D-075 #4):** `useLearningSession.ts`'s
  SSE-connect `useEffect` opened `EventSource` as soon as `sessionId` was set, racing
  ahead of `/student` (`resolve_student`) actually creating the checkpoint - a fresh
  session's first `/stream` connect always 404'd, and `EventSource` does not retry after
  a non-2xx response (confirmed empirically: 18s observed, zero reconnect attempts), so
  a brand-new session's tab permanently never got a single SSE push. Invisible until now
  because every REST action updates `snapshot` directly from its own response regardless
  of SSE health - `pre_intro` was the first SSE-only-dependent content in this codebase.
  Fixed with a new `checkpointReady` gate (`true` for a `sessionId` restored from
  `sessionStorage`, since a refresh always has an already-resolved checkpoint behind it;
  `false` on every fresh `startSession()`, flipped `true` once `chooseStudent`'s
  response confirms `resolve_student` ran) on the SSE-connect effect. Live-reverified:
  real 200 connect immediately once `checkpointReady` flips, `pre_intro` renders
  correctly (screenshot-confirmed), doesn't reappear after Continue.
- **Tests (+17 net, 403→420, stable across 3 repeated `make test` runs):** new
  `packages/shared/tests/test_numeric_grounding.py` (9), new
  `apps/learning-api/tests/test_stage_narrative.py` (5 — scripted fake gateway: gateway
  failure/ungrounded-response fallback, grounded-response trust, idempotency, per-skill
  `study_step` scoping), 3 new `test_bedrock_payload_pii_floor.py` cases for
  `StageNarrativePayload`, plus new S26 assertions appended to
  `test_full_deterministic_learning_flow` (all 4 in-graph stages fire with real grounded
  content across one real pre->study->post cycle, cross-checked against the durable
  `stage_transitions` table since the checkpoint's own `stage_narrative` channel only
  ever exposes the *latest* narrative).
- **Verification:** `make lint && make typecheck && make test` — 420 passed, 0 lint/type
  errors, stable across 3 repeated runs. Alembic `upgrade head`/`downgrade -1`/`upgrade
  head` round-tripped 3x. Both apps' `npm run build`/`npm run lint` clean. Live-verified
  against the real running `learning-api`/`learning-web` dev servers (not just
  `TestClient`): a scripted Python/`httpx` run drove a full pre->study->post cycle over
  raw HTTP, producing 8 real `stage_transitions` rows (`pre_intro`, `pre_outro`,
  `study_step` ×4, `study_outro`, `post_outro`), every one `generated=True` with real
  skill names/scores, none invented; a Playwright pass confirmed `StageTransitionScreen`
  itself (narrative, evidence `<details>` list, Continue dismissal, no console errors),
  including with real rich evidence content injected from a server-driven session
  (screenshots reviewed - brand tokens intact). Dev Postgres swept clean afterward;
  `apps/learning-api/tests/conftest.py`'s own sweep extended to cover
  `stage_transitions` (an independent table, no FK to anything else the sweep touches).
- All 3 ROADMAP S26 "Done when" criteria hold under the expanded (D-075) scope - see
  ROADMAP.md's own "Actual scope" note on the S26 entry.
- Carry-over: `stage_transitions` has no retention/purge job yet (small, bounded — at
  most 5 rows per learning session, no PII, unlike `tutor_chat_messages`' 90-day need).
  `_evidence_summary`'s `relevant_learning_facts` line is only ever populated for
  `post_outro` — `pre_outro`/`study_step` don't surface memory facts in their evidence
  text even when a relevant fact exists for that skill, a thin-coverage scope choice,
  not a bug. Pre-existing carry-overs (`question_variants` accumulation D-053,
  `ChatScreen.tsx` access-hint bug S22.5) are both untouched this session, unrelated to
  this session's own scope.
- New decisions: D-075.

### S25 — Memory system (2026-07-20) ✅
- **Decide-at-session-start (user-approved):** the `MEMORY_CONSOLIDATION` Bedrock call's
  chat-turn input includes PII-redacted (D-072) chat text, not just intent/resolution -
  the fuller of the two options offered, on top of plan §9's own "chat-derived snippets
  (PII-minimized)" wording. `learning_events.structured_payload` itself still never
  holds the text (only a `tutor_chat_message_id` reference) - only the consolidation
  renderer joins it in, and only for this one Bedrock call. See D-074 #5.
- **Build:** new `packages/memory` workspace package (D-009/D-014 precedent):
  `consolidation.py` (`consolidate_student_session`/`consolidate_student_window`
  sharing one `_consolidate_events` core - see D-074 #1), `events.py` (the emitter/
  renderer shared event-type vocabulary), `settings.py`, `consolidate_cli.py`
  (`make memory-consolidate`). `BedrockTask.MEMORY_CONSOLIDATION` +
  `MemoryConsolidationPayload`/`MemoryEventSummary`/`MemoryExistingFact`/
  `MemoryFactCandidate`/`MemoryFactUpdate`/`MemoryUpdateResponse` in
  `packages/shared/bedrock.py`, plus a deterministic `MockBedrockProvider` branch
  (`_memory_consolidation_json`, groups events by skill and keyword-matches their
  code-rendered summaries - good enough to exercise every add/update/contradiction path
  without a real model). `SemanticMemory` gained `superseded_by_id`/
  `contradicts_event_count` (migration `7e51132e191f`); `MemoryRepository` rewritten
  from a stub into a real implementation (see "S25 additions" above for the method
  list). Six emission points wired into `graph/nodes.py` via new
  `learning_api/services/memory_events.py` (`submit_answer`, `intervention_choice`,
  `finalize_exam`, `run_chat_turn`'s `_finish`) - `flow.py`'s `AnswerResult`/
  `FinalizeResult` dataclasses gained `outcome_label`/`target_skill_id` and
  `session_type`/`raw_score` fields respectively so the node layer can emit without a
  second DB read. `finalize_exam`'s post-exam branch calls
  `consolidate_student_session` inline (plan §9 trigger (a)); its cost is folded back
  into `bedrock_spend_cents` (unlike chat's own out-of-band spend, D-073's documented
  gap - this *is* a real graph-node turn, so it can update state normally).
- **Read paths:** see "S25 additions" above and D-074's own "Read paths wired this
  session" paragraph - `tutor.py`/`tutor_chat.py`'s four Bedrock call sites and
  `study_plan.build_study_plan`'s tie-break.
- **Tests/Verification:** see "S25 additions" above (392→403, stable ×3; Alembic
  round-tripped ×3; live-verified against the real dev server, not just `TestClient`).
- Carry-over: none new this session beyond D-074's own two notes (video-search
  enrichment deferred to S27 by design; the `uv sync --all-packages` environment
  gotcha). Pre-existing carry-overs (`question_variants` accumulation D-053,
  `ChatScreen.tsx` access-hint bug S22.5) untouched, unrelated to this session's scope.
- New decisions: D-074.

### S24 — Contextual learning chat (2026-07-20) ✅
- **Decide-at-session-start (user-approved, plan §19 #1's "hard blocker" — D-072):**
  widened SPEC §5.30.1's Bedrock wire allowlist to let the student's own free-text chat
  message cross the gateway for the first time (`redacted_message` on two new
  narrowest-necessary payloads, `LearningChatIntentPayload`/`TutorChatPayload`) — approved
  the plan's full option (redaction + payload extension), not its "deterministic-only
  chat" fallback. Mandatory `intellichoice_shared.pii_redaction.redact_free_text`
  (deterministic email/URL/phone regex — the phone pattern requires a 3-3-4 punctuated
  grouping, not a bare digit run, since this is a math-tutoring app where "2024 - 1998 =
  26" is normal student work) runs at the request boundary, before the message reaches
  `TurnContext`, the Bedrock wire, or the new `tutor_chat_messages` row.
- **Found via this session's own empirical testing, not previously known, changed the
  entire build approach (D-073):** the plan's design (a new `tutor_chat` graph node,
  `entry_action="chat_message"`) would have broken the moment a student chatted while the
  button-panel `AssistancePanel` was open — which is *every* time, since that panel only
  renders while the graph is paused at `intervention_choice`'s `interrupt()`. A scripted
  check confirmed both a fresh `graph.ainvoke` *and* `graph.aupdate_state` silently discard
  a pending interrupt (`/respond` 409'd "no interrupt is pending" immediately after one
  `aupdate_state` call in the check). Fixed by making `graph/nodes.py::run_chat_turn` a
  plain service call - never `ainvoke`/`aupdate_state` - invoked directly from
  `routers/sessions.py::send_chat_message`, which reads state via a new
  `_peek_state_values` (identical to `_get_state_values` minus the pending-interrupt 409
  guard, safe here only because this reader never invokes the graph). Two narrow,
  documented consequences of never touching the checkpoint (neither fixed this session):
  chat's hint-ladder level is read from the durable `hint_events` table instead of
  `LearningState.assistance_level_by_variant` (can drift from the button panel's own
  checkpoint-based tracking only if a student mixes both channels for the *same* wrong
  attempt in the *same* pause); chat's own Bedrock spend isn't persisted back into the
  checkpoint's per-session budget total (the per-day cost ceiling — backed by the real
  `tutor_chat_messages` table, not the checkpoint — is chat's actual, arguably stronger,
  cost control).
- **Build:** `BedrockTask.LEARNING_CHAT_INTENT`/`TUTOR_CHAT` + schemas
  (`packages/shared/bedrock.py`), both reusing `settings.bedrock_tutor_model_id` (same
  "same tutoring task family, no new settings field" posture D-062 established for
  `HINT_PERSONALIZATION`); `MockBedrockProvider` gained deterministic keyword-based
  branches for both. New `packages/db` model/repo `TutorChatMessage`/
  `TutorChatMessageRepository` (one Alembic migration, round-tripped 3x) +
  `StudyRepository.get_latest_attempt_for_variant`. New
  `learning_api/services/tutor_chat.py`: self-harm/abuse keyword screen (fixed response,
  `flagged_for_review=True`, never LLM-improvised — SPEC §5.12.2's "separately approved
  safety policy"), intent classification, and the two free-reply generators
  (`generate_chat_reply`/`explain_why_wrong`), both re-checked against the real question's
  real answer with the same leak-phrase/verbatim-answer rules `tutor.
  generate_personalized_hint` (S21) already uses. `run_chat_turn` gates
  `request_hint`/`request_solution`/`request_video`/`why_wrong` on a real, most-recently-
  *wrong* `StudyAttempt` for the current question (same precondition
  `intervention_choice` already enforces) — absent one, a fixed clarifying message, no
  Bedrock call. New `POST /learning/sessions/{id}/chat` route (phase-gated to `study`
  only, matching `exam_policy`'s existing `hints_allowed=False` for pre/post exam). New
  purge CLI (`learning_api/services/tutor_chat_purge_cli.py`, `make chat-purge`, 90-day
  retention) + `apps/learning-api/tests/conftest.py`'s cleanup sweep gained
  `tutor_chat_messages`.
- **Frontend:** new `apps/learning-web/src/components/TutorChatPanel.tsx` (collapsed
  "Chat with your tutor" toggle → inline transcript + input, client-only per-mount state -
  same D-048 "visible transcript is client-only" precedent `chat-web` already
  established) rendered as the 4th `AssistancePanel` option in both its chooser and
  ladder-open states; `useLearningSession`'s new `sendChatMessage` deliberately sits
  outside the shared `run()` busy gate (same reasoning as `fetchExamOverview`) since chat
  never touches `snapshot`.
- **Tests (+9 net, 383→392 collected — the 371 baseline also grew by 2 from the shared-
  package additions along the way — 392/392 stable across 3 repeated `make test` runs):**
  new `apps/learning-api/tests/test_learning_chat.py` (hint-ladder advance + real
  `hint_events` row; `why_wrong` reply doesn't leak the answer; no-wrong-attempt gets the
  clarifying message; refuses outside study phase; off_topic redirect without needing a
  wrong attempt; self-harm keyword flags + fixed response; PII redacted on the wire and in
  storage; cost ceiling short-circuits with zero spend; purge job deletes only >90-day
  rows) + `packages/shared/tests/test_pii_redaction.py` (5, incl. the math-vs-phone-number
  false-positive case) + extended `test_bedrock_payload_pii_floor.py` for both new
  payloads.
- **Verification:** `make lint && make typecheck && make test` — 392 passed, 0 lint/type
  errors, stable across 3 repeated runs. Alembic `upgrade head`/`downgrade -1`/`upgrade
  head` round-tripped 3x. Both apps: `npm run build`/`npm run lint` clean. Live-verified via
  a scripted Playwright run (temp install in the scratch directory, D-034 convention;
  `learning-api` :8001 + `learning-web` :5173, `MockBedrockProvider`, student fixture
  `student-ext-4`): reached a wrong study answer, opened the chat toggle, sent three
  messages (hint/why_wrong/off_topic) — the hint reply correctly advanced the real ladder
  ("hint 1 of 3", referencing the resolved misconception tag) — then clicked the
  *original* "Show the solution" button and confirmed it still worked (the exact case
  D-073's fix was built to prove), landing normally on a fresh study question with
  correctness/streak UI restored. Screenshots reviewed directly - chat bubbles render
  correctly with brand tokens, scrollable transcript. Dev Postgres swept clean afterward
  via the existing fixture-cleanup helper (confirmed 0 rows across every table this
  session touched).
- All five ROADMAP S24 "Done when" criteria hold under the adapted (D-073) architecture —
  see ROADMAP.md's own "Actual scope" note on the S24 entry.
- Carry-over: see "Current status" above (S24 additions section) — most notably D-073's
  two narrow, accepted drift risks (hint-ladder level, per-session spend tracking) if a
  student mixes chat and the button panel for the same wrong attempt. The pre-existing
  `question_variants` accumulation (D-053) and `ChatScreen.tsx` access-hint bug (S22.5,
  unrelated app) are both untouched this session, unrelated to this session's own scope.
- New decisions: D-072, D-073.

### S23 — Exam frontend: navigation, timers, accessibility (2026-07-20) ✅
- **`ExamScreen` rebuilt** (`apps/learning-web/src/screens/ExamScreen.tsx`) around three
  new components under a new `apps/learning-web/src/components/`: `QuestionNavBar`
  (roving-tabindex toolbar pattern, arrow/Home/End keyboard nav, status glyph + `aria-
  label` per chip so status is never color-only), `ExamTimer` (local per-second countdown
  seeded from `remaining_seconds`, resynced whenever the parent refetches - no backend
  push exists, matching `flow.is_exam_expired`'s existing "lazy check" posture), and
  `SubmitConfirmationModal` (lists unanswered/flagged items computed from the client-held
  overview, not by parsing the finalize endpoint's 422 body). App.tsx's old client-side
  `batch`/`batchIndex` state was removed entirely - `ExamScreen` now owns exam-phase
  batch caching, current-item tracking, and view-time tracking itself, keyed off a new
  `assessment_item_id`↔`display_order` join between the once-fetched question batch and
  the `exam/overview` endpoint's status list (which deliberately doesn't re-send question
  content).
- **Backend (small):** new `POST /learning/sessions/{id}/exam/items/{item_id}/time`
  route + `AssessmentRepository.add_item_time` (accumulates, never overwrites -
  `assessment_item_state.time_spent_ms` was unpopulated since S22) + `services/flow.py`'s
  `record_item_time`, same "plain repository write, not a graph turn" precedent as
  skip/flag. Backs the "autosave tick" via `ExamScreen`'s per-item view-start/cleanup
  effect (flushes elapsed time on nav-bar jump, submit-and-advance, or unmount).
- **D-070 (user-decided at session start):** `exam_overview` is fetched by `ExamScreen`
  itself (mount, after every skip/flag/answer, and a 20s poll for timer resync) rather
  than embedded in the SSE `SessionSnapshotEvent` - avoids an `AssessmentRepository`
  round-trip on every action response across every phase for a field only exam phases
  need. See D-070 for the full reasoning.
- **D-064 read-only design:** an *answered* item's nav chip is a real jump target (not
  disabled) - clicking it shows the question read-only (options disabled, a "locked in"
  note, no submit/skip/flag controls), matching the ROADMAP note's "read-only, never
  resubmittable" instruction literally rather than blocking navigation to it. The
  previously-chosen option is highlighted only if still held in the same browser
  session's in-memory `answeredSelections` map (lost on refresh by design - `exam/
  overview` doesn't expose `selected_option`, and showing "you picked X" isn't a
  correctness signal either way since no right/wrong indication is ever attached to it).
- **Keyboard/ARIA:** number keys 1-4 select an option, Enter submits (container-level
  `onKeyDown`, mirrors the existing select-then-submit two-step flow rather than
  auto-submitting on selection); one `aria-live="polite"` status region (visually
  hidden via a new `.sr-only` utility class) announces every action ("Answer submitted
  for question 3", "Question 2 skipped", "Jumped to question 5", ...). Correctness/streak
  UI was already effectively suppressed for exam phases by D-064's `is_correct` masking;
  this session made that suppression explicit in `ExamScreen` itself (`streak` only
  renders when `phase === "study"`) rather than relying on the masked value alone.
- **Found and fixed a real cross-cutting checkpoint bug via this session's own Playwright
  verification** (not previously known - no existing test submitted an exam answer and
  then resumed/refreshed before this session): `graph/nodes.py`'s `submit_answer`/
  `finalize_exam` nodes explicitly wrote `"last_items": None` whenever there was nothing
  new to report, which is *every* pre/post-exam answer under free navigation (D-064) -
  silently clearing the checkpointed 10-question batch the instant the first such answer
  was submitted. A mid-exam refresh (or `/resume`) then showed "Loading the next
  question…" forever, even though the nav bar's own statuses (a separate `exam/overview`
  read) restored correctly - which is why the gap hadn't surfaced in S22's own
  verification. Fixed by omitting the `last_items` key instead of writing `None` (D-071) -
  LangGraph's default `LastValue` merge then leaves the channel holding its previous
  value, generalizing a convention the `intervention_choice` node's hint-ladder branch
  already relied on for the same reason. New regression test:
  `test_resume_after_an_exam_answer_still_returns_the_full_batch`
  (`apps/learning-api/tests/test_learning_flow.py`).
- **Also found and fixed, same triage precedent as S9/S12/S14/S20/S22 (not a regression
  from this session's own code, but now materially worse than previously documented):**
  `test_ai_pipeline.py::test_passing_candidate_lands_pending_then_activates_to_active`
  failed on a fresh `make test` run - its deterministic seed's generated content
  (`"Solve for x: 3x + 18 = 27"`) collided with an already-committed `question_variants`
  row. The colliding template (`linear_equations-d2-16`) had accumulated **610** variant
  rows (S22 had found "14-16 copies" for a different template) - the unbounded
  `question_variants` accumulation carry-over (D-053) is worsening, not just a one-time
  fluke; this session's own heavy exam-building verification (5-6 full-suite runs plus a
  live Playwright exam completion) plausibly contributed. Fixed the same way prior
  sessions did (deleted the one specific offending row, verified unreferenced by any
  attempt/item/hint-event row first); confirmed 371/371 stable across 3 repeated `make
  test` runs afterward. Underlying accumulation still not fixed - see "Current status".
- **Verification:** `make lint && make typecheck && make test` - 371 passed (+2 net: the
  time-tracking test and the resume regression test), 0 lint/type errors, stable across 3
  repeated runs. `apps/learning-web`: `npm run build` (`tsc -b && vite build`) and `npm
  run lint` (oxlint) both clean. Live-verified via a scripted, keyboard-only Playwright
  run against the real dev server (temp install in the scratch directory, D-034
  convention; `learning-api` :8001 + `learning-web` :5173, `MockBedrockProvider`,
  student fixture `student-ext-4`): answered Q1 via `1`+`Enter`, skipped Q2 via keyboard
  focus+`Enter` on the Skip button, answered Q3-10 via keyboard, jumped back to the
  skipped Q2 via nav-bar arrow-key focus + `Enter` and answered it, confirmed Q1 renders
  read-only with no resubmit affordance when revisited, reloaded the page mid-exam and
  confirmed both the nav bar (all 10 chips showing answered) and the actual question
  content restored correctly (the exact case D-071's bug broke), opened the submit
  confirmation modal and finalized, landing correctly in the `study` phase with a fresh
  question and correctness/streak UI restored. A scripted body-text check after every
  answer confirmed no "correct"/"incorrect" string ever appeared during the exam.
  Screenshots reviewed directly - one visual false alarm chased down and ruled out (a
  solid-green `.option` background on a fresh study question turned out to be a leftover
  browser `:hover` state from Playwright's last automated click landing on the same
  screen coordinates, confirmed via computed style (`--accent-hover`) and `aria-
  pressed="false"`/no `.selected` class - not a real correctness leak).
- All four ROADMAP S23 "Done when" criteria hold: keyboard-only full exam completion incl.
  skip-and-return (live); no correctness signal during exams (live, scripted check); a
  mid-exam refresh restores both nav state and question content (live - the D-071 fix
  made this genuinely true, not just nav-bar-deep); `tsc`/oxlint clean (both apps).
- Carry-over: see "Current status" above (S23 additions section) - most notably the
  `question_variants` accumulation trend (D-053, now worse) and the still-open S22.5
  `ChatScreen.tsx` access-hint rendering bug (unrelated app, untouched this session).
- New decisions: D-070, D-071.

### S22.5 — Brand identity and design tokens (2026-07-19) ✅
- Executed [plans/2026-07-19-branding-plan.md](plans/2026-07-19-branding-plan.md) as
  written (user pre-approved 2026-07-19); logged its BD1–BD5 decisions as D-065–D-069.
  Frontend-only, no backend/DB/LangGraph/RAG/eval changes.
- **New `packages/ui-brand/`** (D-065): `tokens.css` (keeps the pre-existing semantic
  token names - `--text`, `--accent`, etc. - only values changed), `base.css` (element
  styles factored out of both apps' now-deleted twin `index.css`), `assets/logo.png`
  (downloaded from the live site, 512×115), `assets/favicon.svg` (three-dot mark redrawn
  as flat circles from colors sampled off the logo's own pixels - `#4CAF50`/`#03A9F4`/
  `#FF5722`, not the theme CSS brand colors), `check_contrast.py`, `README.md`. Both apps'
  `main.tsx` import `@fontsource/poppins`/`@fontsource/open-sans` (`latin`-subset entry
  points only - `600.css`/`400.css`/`700.css` would have pulled in every Unicode range,
  ~8 unneeded font files) then the two shared CSS files; both `vite.config.ts` gained
  `server.fs.allow: ["../.."]` for the dev server to read across the app boundary.
- **Two-tier color system (D-067):** raw brand colors (`--brand-green` `#5eb761`,
  `--brand-pink` `#e95095`, `--brand-purple` `#7049ba`) fail WCAG AA as text - kept for
  decorative/logo/gradient use only. A separate darkened "interactive" tier
  (`--accent` `#387e40`, `--pink-interactive` `#c22f73`) is used for all text-sized
  color. **The plan's own draft pink value (`#d13a80`) didn't actually clear 4.5:1** -
  it was checked only against `--panel-bg` (white); this app's `--bg` token is an
  off-white `#f5f5f5` that drops the same hex to 4.16:1, caught by `check_contrast.py`
  once it checked both surfaces - corrected to `#c22f73` (`--error` similarly darkened
  one step, `#dc2626` → `#d32020`, same reason).
- **Dark mode (D-068):** own brand-adapted palette (not the live site's own dark CSS,
  which is untouched Impreza theme defaults) - near-neutral dark surfaces, lightened
  green/pink/purple, new `--accent-contrast` token (dark text on the lightened green
  button background, since white-on-light-green fails contrast the same way raw
  green-on-white fails in light mode).
- **App chrome.** learning-web: `App.tsx`'s entire early-return if-chain wrapped in a
  `renderContent(): ReactNode` closure (renamed from the plan's suggested `view()` to
  avoid shadowing the existing `view`/`setView` dashboard-toggle state) inside a new
  `<div className="app-shell"><header/><main>{renderContent()}</main><footer/></div>` -
  header carries the logo + "Adaptive Learning"; footer is a dark bar ("© IntelliChoice
  Inc." + a link to intellichoice.org) using new `--footer-bg`/`--footer-text`/
  `--footer-link` tokens; `#root`'s old centering styles moved to `.app-main`. chat-web:
  logo placed inside the existing `.chat-header` only, per the plan's explicit
  "don't add a shell bar" call (the `calc(100svh - 48px)` height math would have broken).
  Both apps' `DevLoginScreen` gained a larger logo above the `<h1>`.
- **Component pass:** buttons uppercase/600/letter-spacing/`--radius-button`, with
  `text-transform: none` restored on the four content-bearing classes the plan flagged
  (`.option`, `.card`, `button.link`, `button.chip`); all hardcoded `border-radius`
  values replaced with the new `--radius-panel`/`--radius-control`/`--radius-button`
  scale; hardcoded `color: white` on solid-accent surfaces (button base, chat user
  bubble) replaced with `--accent-contrast` so dark mode's lightened-green buttons get
  dark text automatically; new `.gradient-bar` (a bare decorative strip, no text drawn
  on the gradient itself - keeps D-067's contrast rule intact) added to `ResultsScreen`
  as the plan's "sparse highlight" device.
- **Verification.** Both apps: `npm run build` + `npm run lint` (oxlint) clean.
  `check_contrast.py`: every checked text/background pair passes ≥4.5:1 in both schemes
  (15 pairs × 2 schemes). Playwright screenshot walk (network-mocked, no real backend
  needed - same pattern S16/S19/S21 used) covering 11 learning-web screens (DevLogin,
  Start, ChildSelection, Attendance ×2 variants, TopicSelect, Exam, Exam+hint,
  Exam+solution, Results, ParentDashboard) and 7 chat-web screens/states (DevLogin,
  Welcome, answer+citations, access-hint, EmailApproval/CalendarAction/LocationConsent
  modals), light + dark each - reviewed directly, no layout breakage, brand consistently
  applied. `make lint`/`make typecheck`: clean. `make test`: **but only after fixing a
  real regression this session caused** first - `packages/ui-brand/` (no
  `pyproject.toml`) broke `uv`'s workspace resolution for the whole monorepo until added
  to `pyproject.toml`'s existing `[tool.uv.workspace].exclude` list (see D-065's
  addendum). Once fixed, `make test` itself is **not stably 369/369** -
  `test_hint_reflects_the_students_actual_wrong_option` (S21) failed 2 of 3 full-suite
  runs during this session's own end-of-session verification (passed the 3rd) but
  passed 3/3 when run standalone; root cause traced (not fixed - backend/curriculum
  code, outside this session's frontend-only scope) to `routers/sessions.py:408`'s
  unseeded
  `random.Random()` per pre-exam build - `MockBedrockProvider`'s canonical hint text
  doesn't always embed the misconception tag for every randomly-sampled numeric variant,
  and this test's assertion isn't robust to that. This is the exact class of flakiness
  S22's own carry-over predicted would recur ("a future session should either seed the
  RNG in the HTTP-committed test files..."), just surfacing via a different symptom
  (hint-tag assertion) than S22's own duplicate-variant symptom. Confirmed via zero
  backend file changes this session and a live `docker compose ps` showing the shared
  dev Postgres has been running for 27+ hours (pre-existing state, not something this
  session's - entirely frontend/mocked-Playwright - verification touched).
- All four ROADMAP S22.5 "Done when" criteria hold: both apps build+lint clean; the
  screenshot walk shows the brand applied with no breakage; `check_contrast.py` passes
  in both schemes; student-facing wording is unchanged (only chrome/footer/alt-text
  added, no curriculum or growth-language copy touched).
- Carry-over: see "Current status" above (S22.5 additions section) - most notably a
  real, found-but-not-fixed `ChatScreen.tsx` bug (access_hint never renders when
  `answer` is null) that's outside this session's branding scope.
- New decisions: D-065, D-066, D-067, D-068, D-069.

### S22 — Assessment policy and exam backend (2026-07-20) ✅
- **Decide-at-session-start (user-decided, against the plan's own recommendation — D-064):**
  kept grade-on-submit (not save-then-finalize) and gave pre/post exams a real 1200s
  default timer (not untimed). See "Current status" S22 additions and D-064 for the full
  consequences this forced (answered items permanently locked; explicit finalize now
  required even on the all-answered-in-order path).
- **`AssessmentPolicy`** (new `apps/learning-api/src/learning_api/services/exam_policy.py`):
  pure, deterministic per-session-type config (`pre_exam`/`study`/`post_exam` →
  timing/navigation/hints_allowed/feedback_visibility). A JSON snapshot is stamped onto
  `assessment_sessions.policy` at creation so a later constant change can't retroactively
  alter an in-progress exam.
- **Schema** (one Alembic migration, round-tripped 3x). `assessment_sessions` gained
  `topic_id`/`policy`/`time_limit_seconds`/`finalized_at`; `assessment_attempts.
  selected_option` became nullable (a finalize-synthesized "unanswered" attempt has none);
  new `assessment_item_state` table (unseen/answered/skipped/flagged +
  `first_viewed_at`/`time_spent_ms`, one row per `AssessmentItem`, created alongside it in
  `assessment_builder.py`).
- **`flow.py`.** `_submit_pre_exam_answer`/`_submit_post_exam_answer` still grade
  immediately but no longer auto-transition the phase on the last answer; that tail
  (mastery upsert + study-plan build for pre-exam, learning-gain compute for post-exam) was
  extracted into `_complete_pre_exam`/`_complete_post_exam`, now only reachable via the new
  `finalize_exam`. New `mark_item_skipped`/`mark_item_flagged` (plain repository writes, no
  graph turn — same precedent as answer-saving itself). New `is_exam_expired` (lazy check,
  no scheduler). `finalize_exam` synthesizes an incorrect attempt
  (`selected_option=None`) per unanswered item once confirmed or expired, marks
  `finalized_at`, then runs the completion tail — idempotent by checking `finalized_at`
  fresh from the DB first and no-op-returning `None` if already set.
- **Graph.** New `finalize_exam` node (`graph/nodes.py`) + `entry_action` (`graph/
  build.py`), straight edge to `END` (no `interrupt()` — finalize is deterministic, no
  human approval involved). **Idempotency gotcha found and fixed while building this:**
  dispatching by `learning_session.phase` alone breaks for a retry that arrives after the
  phase already advanced to `"study"`/`"completed"` — fixed by accepting those two phases
  as valid dispatch targets too (structurally guaranteed already-finalized, so it always
  falls through to the no-op).
- **Routes (`routers/sessions.py`).** `POST .../answers`: unchanged shape, now masks
  `is_correct` to `None` for `phase in ("pre_exam", "post_exam")` (grade still computed and
  stored), and 409s once `flow.is_exam_expired`. New `POST .../exam/items/{id}/skip`,
  `POST .../exam/items/{id}/flag`, `GET .../exam/overview` (item statuses + difficulty +
  `remaining_seconds`), `POST .../exam/finalize` (`confirm_unanswered: bool`, 422 with
  `unanswered_item_ids` if needed and not given/expired).
- Tests (+11 net, 358→369 collected, 369/369 passing, stable across 3 repeated runs): new
  `test_exam_policy.py` (4, pure unit: the hints/timing/navigation/feedback matrix); new
  `test_exam_backend.py` (6: skip-then-answer grades normally, flag toggles and locks out
  once answered, finalize requires confirmation then grades unanswered items incorrect,
  finalize is idempotent with no duplicate attempts, an expired exam rejects new answers
  and finalizes without confirmation, resume+overview restore item statuses after a
  restart); `packages/db/tests/test_repositories.py` (+1: `AssessmentItemState` round-trip
  incl. the nullable-`selected_option` finalize path). Updated every existing
  `apps/learning-api/tests/*` test that walked a full pre/post-exam answer loop (9 files'
  worth of call sites) to call the new explicit finalize step and stop asserting a real
  `is_correct` during the exam phase. `apps/learning-api/tests/conftest.py`'s
  dependency-ordered sweep gained `assessment_item_state` (must clear before
  `assessment_items`, its FK parent).
- Verification: `make lint && make typecheck && make test` — 369 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head`/`downgrade -1`/`upgrade
  head` round-tripped cleanly 3x. Live-verified against the real dev server: full
  pre-exam answer → skip → flag → `GET exam/overview` (correct statuses + countdown) →
  `POST exam/finalize` without confirmation (422, correct `unanswered_item_ids`) → retry
  with `confirm_unanswered: true` (200, phase→`study`, unanswered items graded incorrect)
  → repeat the same finalize call (identical response, confirmed idempotent). All four
  ROADMAP S22 "Done when" criteria hold under the adapted (D-064) model — see ROADMAP.md's
  own "Actual scope" note on the S22 entry.
- Carry-over: see "Current status" above (S22 additions section) — most notably the
  newly-discovered unbounded `question_variants` accumulation (found and partially
  mitigated this session, not fully fixed).
- New decisions: D-064.

### S21 — Personalized hint ladder grounded in the bank (2026-07-19) ✅
- **Decide-at-session-start (user-approved):** widened the SPEC §5.30.1 Bedrock
  allowlist for a new `HINT_PERSONALIZATION` task only (D-062) - 4 non-identifying
  fields (`previous_hint_summaries`, `misconception_tag`, `attempt_count`,
  `hint_level`) plus `canonical_hint_text` (a necessary, explicitly-flagged addition
  beyond the named 4 - the model needs something concrete to rewrite). `TUTOR`'s own
  payload is untouched; this is a new, separate, narrowest-necessary payload model
  (D-023's rule applied, not loosened).
- **Schema (SPEC §5.11.4, plan §18-L2).** New `hint_events` table
  (`packages/db/models/hints.py`'s `HintEvent` + `repositories/hints.py`'s
  `HintEventRepository`) - one row per hint level served, `was_personalized=False`
  marking any fallback-to-canonical round. One Alembic migration, round-tripped 3x
  (same known-false-positive LangGraph-checkpoint/`rag_chunks`-index omissions every
  prior migration has documented). New `packages/curriculum/.../hint_ladders.py`:
  hand-authored, static, 3-level canonical hint ladders for all 11 registered
  `linear_equations` shapes (method-only, never referencing sampled numbers or a
  computed value - the roadmap's "10 shapes" was stale, `two_step_sub_b`/
  `both_sides_alt` bring the real count to 11). Authored templates reuse their S20-
  populated `hint_ladder` column unchanged.
- **Bedrock (`packages/shared/bedrock.py`).** New `BedrockTask.HINT_PERSONALIZATION` +
  `HintPersonalizationPayload`/`HintPersonalizationResponse` (D-062). The response type
  deliberately does *not* echo `hint_level`/`is_final_level` back from the model - the
  caller already knows both before the call, so trusting the model to restate them
  would duplicate code-owned state (same "model proposes content, code decides facts"
  split as this file's existing `LlmCitation`/`RerankResponse`). `MockBedrockProvider`
  gained a `HintPersonalizationResponse`-title branch that varies its text by the real
  `hint_level`/`misconception_tag` inputs, so default-mock-driven tests see genuinely
  different, misconception-aware text per level without a bespoke scripted gateway.
  `packages/curriculum/.../authored_validation.py`'s leak-phrase and monotonicity
  checks were generalized to plain-string/`list[str]` helpers
  (`leak_phrase_present`/`answer_text_leaked`/`hint_ladder_monotonicity_violations`) so
  S20's authored-item validation, S21's static shape ladders, and S21's runtime
  personalized-hint check all share one implementation - no wordlist forked three ways.
- **`tutor.generate_personalized_hint`** (`learning_api/services/tutor.py`) - rewrites
  the canonical text at a given level; on success, re-checks the model's own output
  against the *real* question's real answer (leak phrase + verbatim answer text +
  monotonicity against the canonical ladder's next level) before accepting it; any
  failure (gateway error or a failed check) falls back to the canonical text verbatim,
  never surfacing bad content - matches the existing `generate_hint`/`generate_solution`
  fallback posture exactly.
- **Misconception-tag lookup** (`topic_resolver.resolve_misconception_tag`) - maps the
  student's actual wrong option to a `common_error_tags` entry by ordinal rank among
  the non-correct options; deterministic and testable, a known-coarse heuristic (see
  carry-over above). `resolve_tutor_context`'s existing `common_error_tag` field now
  uses this instead of always taking `common_error_tags[0]`.
- **Graph control flow (D-063).** The central design question: how does a student get
  hint level 2 on the *same* question without the graph moving on, given
  `intervention_choice` previously always called `flow.advance_study` right after
  generating one piece of content? Verified first (not assumed) that `flow.
  advance_study` → `create_study_item` always generates a brand-new `QuestionVariant`
  on every retry (D-028) - so the ladder cannot piggyback on the cross-question retry
  ladder; it needed a genuinely new pause-and-resume loop. Rejected an intra-node
  `while` loop (D-021 gotcha #1: a resumed node replays its entire body from the top,
  so each escalation would redundantly re-run every earlier round's real Bedrock call
  and DB write - O(N²) side effects). Implemented instead as a **graph-level self-loop**:
  a new conditional edge in `graph/build.py` routes `intervention_choice` back to
  itself for a fresh superstep when a `"hint"` choice hasn't reached the ladder's final
  level, driven by a new transient `LearningState.hint_ladder_awaiting_choice` field
  (same category as the existing `entry_action`). `intervention_choice` itself stays
  single-`interrupt()`-per-invocation, unchanged in shape. `LearningState` also gained
  `assistance_level_by_variant: dict[str, int]`, persisting the current hint level per
  question variant across checkpoint restarts. `routers/sessions.py`'s `/respond`
  needed no core change - it already reads the next pending interrupt generically after
  every resume. `InterventionChoiceRequest.choice` gained a `"continue"` option (the
  "I'll try again now" action, ends the ladder without a further hint/solution/video).
  **Found and fixed a real correctness bug while designing this:**
  `StudyRepository.update_intervention_choice` used to overwrite
  `hint_used`/`video_used`/`solution_used` wholesale each call - a round-1 "hint" then
  round-2 "solution" would have silently cleared `hint_used`, corrupting `study_outcomes.
  correct_label`'s support-history precedence for an abandoned-without-solution case.
  Fixed to OR each round's flag into the attempt's already-persisted value.
- **Frontend (`apps/learning-web`).** `InterventionChooserScreen` + `InterventionPanel`
  merged into one `AssistancePanel` (`screens/InterventionScreen.tsx`, file kept,
  component renamed/rebuilt) - the two were never meaningfully separable once a single
  intervention_choice pause can carry both "already has content" and "still awaiting
  another choice" simultaneously (the graph self-loop means a `pending_interrupt` of
  type `intervention_choice` can now coexist with real `intervention` content, which
  the old two-component split couldn't represent). Renders ladder position ("hint 2 of
  3"), a "Get another hint" button (hidden at the final level), and "I'll try again
  now" while the ladder is open; falls back to the original plain "Got it — next
  question" dismiss once it closes. `App.tsx`'s render logic restructured to read
  `pending`/`snapshot.intervention` together inside the exam-phase block instead of a
  separate early-return chooser branch (removing the return meant the merged panel and
  the exam question can render together whenever there's content to show, matching the
  self-loop's actual state shape). `types.ts`/`api/client.ts` extended for
  `hint_level`/`max_hint_level` and the `"continue"` choice.
- Tests (+17 net: 341→358 collected, 358/358 passing, stable across 3 repeated runs):
  `packages/shared/tests/test_bedrock_payload_pii_floor.py` (+3: the new payload's
  allowlist/denylist/extra-field-rejected block); `packages/curriculum/tests/
  test_hint_ladders.py` (new, 6: all 11 shape ladders pass leak/monotonicity checks,
  exactly 3 distinct non-empty levels each - pure data validation, no DB/LLM);
  `apps/learning-api/tests/test_tutor_service.py` (+4: `generate_personalized_hint`
  success, gateway-error fallback, leak-triggered fallback, monotonicity-triggered
  fallback); `packages/db/tests/test_repositories.py` (+1: `HintEvent` round-trip incl.
  a `was_personalized=False` fallback row, 25th repository covered);
  `apps/learning-api/tests/test_learning_flow.py` (+3: a full 3-round hint escalation
  via real `/respond` calls asserting levels 1→2→3, three genuinely distinct texts,
  no leaked answer text, auto-advance only after the final level, `hint_used` staying
  `True` through the loop; a restart-mid-ladder test asserting `assistance_level_by_
  variant` survives a checkpoint reload - level 2 is requested correctly after a fresh
  `TestClient` block, not a repeat of level 1; a scripted-gateway-equivalent test tying
  a specific wrong option to `MockBedrockProvider`'s embedded misconception tag in the
  live hint text - the "Done when" misconception criterion). Existing
  `test_full_deterministic_learning_flow` updated for the new multi-round pause shape
  (a "hint" choice now re-pauses; the test drives an explicit "continue" to close the
  ladder before proceeding, matching the new UX). `apps/learning-api/tests/conftest.py`'s
  dependency-ordered fixture-cleanup sweep (D-053) gained `hint_events` (must clear
  before `study_attempts`, its FK parent).
- Verification: `make lint && make typecheck && make test` - 358 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-tripped cleanly for the `hint_events` migration.
  `apps/learning-web`: `npm run build` (`tsc -b && vite build`) and `npm run lint`
  (oxlint) both clean. Live-verified via a scripted Playwright run against the real
  dev server (see carry-over above for the full transcript of what was checked) -
  screenshots confirmed all three hint levels rendered with correct ladder position,
  distinct misconception-aware text, and the correct button set at each stage. All
  four ROADMAP S21 "Done when" criteria hold: three successive hints escalate and
  never reveal the answer before the final level (live + `test_hint_ladder_escalates_
  through_three_levels_without_leaking_answer`); a personalized hint addresses the
  mapped misconception (live + `test_hint_reflects_the_students_actual_wrong_option`);
  gateway failure serves the canonical hint (`test_generate_personalized_hint_falls_
  back_on_gateway_error`); the PII-floor test covers the widened payload
  (`test_hint_personalization_payload_*`).
- Carry-over: see "Current status" above (S21 additions section).
- New decisions: D-062, D-063.

### S20 — Authored question bank: generation and validation pipeline (2026-07-19) ✅

### S20 — Authored question bank: generation and validation pipeline (2026-07-19) ✅
- **Schema (SPEC §5.8.2, plan §7).** `QuestionTemplate` gains `authoring_mode`
  (`"shape"|"authored"`, default `"shape"` - existing rows unaffected) plus
  authored-content columns: `stem`/`context_block`/`answer_expression`/`hint_ladder`
  (JSON)/`canonical_solution` (JSON)/`stem_embedding` (pgvector, mirrors `RagChunk.
  embedding`)/`review_priority`. New append-only `question_validation_runs` table
  (`packages/db/models/questions.py`'s `QuestionValidationRun`) - one row per pipeline
  attempt, `question_template_id` deliberately **nullable** so a candidate rejected
  before a template ever exists still gets a persisted audit row (D-059). One Alembic
  migration, round-tripped 3x; the autogenerated diff's LangGraph-checkpoint-table and
  `rag_chunks`-index drops were omitted as the same known false positives
  `f6dcf62cdba4` already documented. `QuestionRepository` gained `create_validation_run`/
  `get_latest_validation_run`/`get_variant_for_template`/
  `get_pending_authored_by_priority`/`stem_near_duplicate_exists`/`reject_template`/
  `supersede_template`.
- **Bedrock schemas (`packages/shared/bedrock.py`).** Two new `BedrockTask`s
  (`AUTHORED_QUESTION_GENERATION`, `QUESTION_JUDGE`) + their payload/response schemas
  (`AuthoredGeneratorPayload`/`AuthoredGeneratedItemResponse`/`QuestionJudgePayload`/
  `QuestionJudgeResponse`, reusing the existing `SolutionResponse` shape for
  `canonical_solution`). Solver A/B reuse the existing `QUESTION_GENERATION`/
  `QUESTION_REVIEW` task slots instead of a third task (D-059, user-confirmed) - gets
  "different models" (§5.25.2) for free. `MockBedrockProvider` gained deterministic
  branches for both new response types.
- **New `authored_validation.py`** (`packages/curriculum`) - the SPEC §5.8.5
  deterministic gate for authored items, distinct from the S9 shape pipeline's
  `validation.py` (no registered shape/solver to recompute from): schema/markdown
  safety, SymPy independent solve (new `sympy>=1.13` dependency) with distractor
  cross-checks, exactly-one-correct, answer-leakage (explicit leak phrases + verbatim
  answer text in any hint level), hint-ladder monotonicity (substring-containment
  proxy), hint/solution/answer agreement, a wordlist + words-per-sentence readability
  heuristic. 11 pure unit tests, no DB.
- **`generate_authored_candidate`** (`ai_pipeline.py`) - generate → deterministic gate →
  exact-text dedup → embed-and-check near-duplicate (`stem_embedding`, cosine distance,
  D-061) → Solver A/B (reject on disagreement) → `QUESTION_JUDGE` (reject on flags/low
  score, `review_priority="high"` on borderline, D-059) → persist `pending` + one static
  variant + one `question_validation_runs` row. Reuses the S9 shape pipeline's
  `TOPIC_DIFFICULTY_SKILLS` map - `linear_equations` only this session (D-060,
  user-confirmed at session start).
- **CLIs.** `pipeline_cli.py` gained `--mode authored` (`make question-gen-authored`).
  New `review_cli.py` (`make question-review`) - lists `pending` sorted by
  `review_priority`, renders the item + its `question_validation_runs` evidence,
  approve (→ the existing `activate_template`, D-026 unchanged: the pipeline can never
  self-approve) / reject / edit-and-rerun (`supersede_template` + a fresh
  `generate_authored_candidate` call at `version + 1`, D-061).
- Tests (+26 net, 315→341 collected, 341/341 passing, stable across 3 repeated runs):
  `test_authored_validation.py` (new, 11: every deterministic-gate check, pure unit);
  `test_authored_pipeline.py` (new, 11: happy path incl. activation +
  `get_active_questions`/`get_active_questions_for_skill` selection, unregistered-topic
  `PipelineConfigError`, all 5 ROADMAP golden bad-item fixtures - two correct options,
  leaked answer, disagreeing solvers, off-grade wording, near-duplicate - each asserting
  a persisted `question_validation_runs` row, judge-reject + judge-borderline-priority,
  and `review_cli.py`'s render/approve/reject/edit-and-rerun); `packages/db/tests/
  test_repositories.py` (+2: `QuestionValidationRun` round-trip incl. the nullable-FK
  case, and the four new `QuestionRepository` authored helpers);
  `test_generation_payload_schemas.py` (+2: the two new payloads' `extra="forbid"`).
- **Live-verified**, then cleaned up (see carry-over above for why): `make
  question-gen-authored` against the real dev Postgres produced 5 pending candidates
  (one per difficulty); `make question-review` rendered real pipeline evidence and
  approved one; the approved item was confirmed selectable via the exact unchanged
  `get_active_questions` runtime query - then all 5 live rows were deleted once this
  broke two exact-count tests (see carry-over), re-confirmed 341/341 stable afterward.
- Verification: `make lint && make typecheck && make test` - 341 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-tripped cleanly. All three ROADMAP S20 "Done when" criteria hold:
  every golden bad-item fixture rejects with persisted reasons (test_authored_pipeline.
  py); nothing reaches students without human review (pending is never auto-approved,
  D-026, tested + live); an approved authored item appears in a real pre-exam via the
  unchanged selection query (tested + live-verified).
- Carry-over: see "Current status" above (S20 additions section).
- New decisions: D-059, D-060, D-061.

### S19 — Access-aware refusals, welcome message, and suggestions (2026-07-19) ✅
- **Access-aware refusal (SPEC §5.19.1/§5.21.3, plan §18-C3).** New `RagRepository.
  count_matching_by_audience(filters, query)` (`packages/db/repositories/rag.py`):
  one metadata-only probe (`GROUP BY audience` count, branch restriction lifted,
  keyword-only `websearch_to_tsquery` match, no embedding call) - counts only, chunk
  content never leaves the repository layer. `answer_document_qa` split into pure
  retrieval + new `synthesize_answer` (citation synthesis, unchanged logic) so an
  empty role-filtered retrieval routes to a new `explain_access` node instead of
  paying for an LLM synthesis call with no chunks. `chat_api.services.role_access`
  gained `build_access_hint` (fixed `ACCESS_HINT_MESSAGES` dict, priority order
  branch_manager > tutor > parent > student - the LLM never decides access,
  CLAUDE.md #3) and `AccessHint`. `QAState`/`MessageResponse`/`RespondResponse`/
  `SessionSnapshotEvent` gained `access_hint`.
- **Found and fixed one real design flaw via live verification (D-056).** The plan's
  second access-hint case (a match under the caller's own audience, elsewhere, for a
  different branch → generic "different branch" message) was built, then removed
  after curling the live dev server: "What is IntelliChoice?" anonymously returned a
  false "that's for a different branch" message for what was actually a legitimate
  no-answer (the real, fully public `public-organization-overview` chunk reranked to
  score 0 for that exact wording, D-052) - the probe has no `candidate_limit` and
  never reranks, so it's a much looser filter than the real retrieval pipeline and
  still "found" that same chunk once branch restriction was lifted. Kept only the
  role-gated case, re-verified live (anonymous + a synthetic tutor-only chunk →
  role-guidance message; tutor token → real answer) and via Playwright.
- **Welcome + suggestions (plan §2.2/§2.5-UX).** New `chat_suggestions` table
  (`packages/db/models/chat.py` + `repositories/chat.py`, one Alembic migration,
  round-tripped) - hand-authored reference data (not scraped), upserted by natural-
  key `id` via new `make chat-suggestions-load`
  (`chat_api.services.suggestions_seed[_cli]`, 14 seed rows). New `GET /chat/meta`
  (anonymous-OK): a deterministic 2-line welcome excerpt of `public-organization-
  overview`'s known "About Us" chunk (new `RagRepository.
  get_chunk_by_document_and_section` - `RagChunk` has no sequence column, so this is
  the only way to name a specific chunk without depending on undefined row order;
  `chat_api.services.welcome._first_two_sentences` does the excerpting, regex only,
  no LLM, static fallback if that content isn't loaded) plus role-aware suggested
  prompts (`chat_api.services.suggestions.suggestions_for_role`). Deterministic
  per-answer follow-up chips (`suggestions.followups_for_answer`, category-based:
  intent for branch_locator/calendar, else the top citation's document id) - new
  `suggested_followups` on the same three response DTOs (D-057).
- **Found and fixed a second real bug via live Playwright verification (D-058):** the
  SSE `/stream` endpoint's `_initial_snapshot` built its `SessionSnapshotEvent`
  straight from checkpointed state and never set `access_hint`/`suggested_followups` -
  since chat-web opens the stream right after a turn resolves (D-048), it silently
  reverted a correct `/messages` response to defaults moments after rendering.
  `access_hint` is real checkpointed state (one-line fix); `suggested_followups`
  isn't, so `_initial_snapshot` gained a `db: AsyncSession` parameter to recompute it
  via the same `_suggested_followups` helper `sessions.py` uses (now shared).
- **Frontend (`apps/chat-web`).** New `WelcomeCard` (welcome text + suggestion chips,
  shown while the transcript is empty) and `AccessHintBanner` (message + a "log in"
  shortcut back to `DevLoginScreen`) components; per-answer follow-up chips inline in
  `ChatScreen`. `App.tsx` fetches `/chat/meta` once past the dev-login gate,
  refetching on role change. `types.ts` gained `AccessHint`/`ChatMeta` and extended
  `TurnSnapshot`.
- **Golden Q&A coverage eval (plan §13, ~40 questions).** New versioned fixture
  `apps/chat-api/tests/fixtures/qa_coverage_eval.yaml` (9 `grounded` + 5 `role_gated`
  + 10 `out_of_scope` + 16 `no_source` cases) + `test_qa_coverage_eval.py`. Split
  threshold (user-confirmed at session start, given only 3 of 22 seeded documents are
  effective today): refusal-correctness and no-hallucination need ≥0.95 across the
  whole set (don't depend on real content); citation-grounding is measured only over
  the `grounded` subset targeting the 3 currently-effective real documents (org
  overview/branch directory/our-team - `academic-calendar` excluded on purpose, see
  carry-over), at ≥0.85 - currently hits 9/9 (100%), stable across repeated runs.
  `grounded`/`role_gated`/`no_source` query wording is hand-tuned around
  `MockBedrockProvider`'s crude keyword-overlap reranker and D-018's real-content-
  collision pattern (several iterations needed - documented in the fixture file's own
  comments).
- Tests (+23 net, 292→315 collected, 315/315 passing, stable across 3 repeated runs):
  `packages/db/tests/test_rag_search.py` (+2: probe returns counts only, ignores
  non-matching query text); `test_repositories.py` (+1: `ChatSuggestion` round-trip,
  24th repository covered); `apps/chat-api/tests/test_role_access.py` (+access-hint
  unit tests, replacing 2 removed branch-blocked-case tests per D-056);
  `test_qa_graph.py` (replaced the old "unanswerable in-scope query" test - its own
  premise is now the access-hint feature working as intended - with
  `test_anonymous_query_with_only_higher_role_content_yields_access_hint` +
  `test_genuinely_unanswerable_query_offers_escalation`); `test_meta.py` (new, 6
  tests: welcome-excerpt sentence-splitting logic, a real-content integration check
  against the live `public-organization-overview` document, role-aware suggestion
  filtering); `test_suggestions.py` (new, 7 tests: pure category-mapping/selection
  logic, no DB); `test_chat_endpoints.py` (+1 HTTP followups test; the 4 pre-existing
  `_initial_snapshot` direct-call tests updated for its new `db` parameter, using a
  fresh per-call engine rather than `app.state.db_session_factory` - that one is bound
  to `TestClient`'s own event loop, which a separate `asyncio.run()` can't share);
  `test_qa_coverage_eval.py` (new, the golden-set runner above).
- Verification: `make lint && make typecheck && make test` - 315 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-tripped cleanly for the `chat_suggestions` migration (re-ran
  `make chat-suggestions-load` afterward, since the round-trip drops and recreates the
  table). Live-verified against both real dev servers plus a scripted Playwright run:
  `GET /chat/meta` returned the real welcome excerpt + role-aware chips; an anonymous
  query against a synthetic tutor-only chunk returned the exact role-guidance message
  with no content, while a tutor-token query against the same chunk returned the real
  answer with a real citation; per-answer follow-up chips and the access-hint banner
  rendered correctly in the browser after the D-058 SSE fix; a genuinely unanswerable
  anonymous query ("What is IntelliChoice?", after the D-056 fix) correctly returned
  the honest no-source escalation message. All four S19 "Done when" criteria hold:
  anonymous tutor-procedure question → role-guidance message, never content (live +
  `test_qa_graph.py`); tutor token → real answer (live); the probe provably returns no
  content fields (its own return type, `dict[str, int]`, plus
  `test_rag_search.py`); welcome + suggestions render per role (live + `test_meta.py`);
  the coverage eval passes its agreed split threshold (`test_qa_coverage_eval.py`,
  100% on the `grounded` subset against an 0.85 floor).
- Carry-over: see "Current status" above (S19 additions section).
- New decisions: D-056, D-057, D-058.

### S18 — Structured events and calendar rewiring (2026-07-19) ✅
- **Real events via the Tribe Events Calendar REST API, not HTML scraping (D-054).**
  New `packages/webcontent/extractors/events.py` (`extract_events`, a pure function
  over the API's parsed JSON) - found live while probing `/events/` for a scrape
  target: the response headers advertised the plugin's own
  `/wp-json/tribe/events/v1/events` REST API, richer and more reliable than the HTML
  listing page (confirmed by fetching both). New `EventRecord`; `sync_cli.py`'s
  `_fetch_all_events` paginates from `start_date=2000-01-01` (the API defaults to
  "now," which would silently return zero events for this org's all-historical
  calendar) and writes `knowledge-content/structured/events.yaml` +
  `knowledge-content/documents/public/academic-calendar/content.md` (real
  `effective_from`, retiring that document's placeholder date gate). Two real
  data-quality bugs found and fixed via the live sync: HTML-entity-encoded titles
  (`&#8211;` etc., fixed with `html.unescape()`); the API's own `timezone` field
  reporting a bogus `"UTC+0"` (a WordPress misconfiguration, not a real IANA zone -
  overridden to `"America/Chicago"`, the org's Dallas home base).
- **New `org_events` table** (`packages/db/models/org.py`'s `OrgEvent` +
  `repositories/org.py`'s `OrgEventRepository`) + one Alembic migration (round-tripped
  3x). `status` stores only a source-declared override (`"canceled"`/`"changed"`, or a
  neutral `"scheduled"` default) - `upsert_event` never overwrites it on a
  content-changing update, so a re-sync fixing an unrelated field can't silently
  un-cancel a human-flagged event. No `mark_inactive_except` (unlike `OrgBranch`/
  `OrgTeamMember`) - see D-055 for why. `org_load.py`/`org_load_cli.py` extended for
  events (`make org-load`).
- **`calendar_extract` rewired (D-055, SPEC §5.23 for real content).** New
  `apps/chat-api/services/calendar_events.py` (`classify_event`/
  `list_upcoming_events`/`find_event_by_keywords`/`to_calendar_event`) - pure Python,
  no LLM, keyword-overlap matching, date-arithmetic classification that always
  recomputes upcoming/completed against `now` (a stored value is never trusted for
  those two states, so a past event can never be mislabeled). `calendar_extract` now
  tries `org_events` deterministically first; only falls back to the pre-S18 RAG+LLM
  chunk extraction (`services/calendar.py`, unchanged) when nothing structured
  matches; and - new - answers a generic "what's coming up" query directly from a
  real listing (new `calendar_event_listing` node, no `interrupt()`, SPEC §5.23.1's
  "information request") when no specific event matched either way but something is
  upcoming. `QAState` gained `event_listing`. New `GET /chat/events?window_days=`
  (public, anonymous-OK), sharing `list_upcoming_events` with the in-graph listing so
  the two can't disagree.
- Tests (+22 net, 270→292 collected, 292/292 passing): `packages/webcontent/tests/
  test_extractors.py` (+4: date/timezone-default extraction, venue-address handling,
  HTML-entity unescaping, determinism); `test_org_load.py` (+2: events natural-key
  upsert/unchanged, a content-changing re-sync never clears a manually-set status);
  `packages/db/tests/test_repositories.py` (+1: `OrgEvent` round-trip, 23rd repository
  covered); `apps/chat-api/tests/test_calendar_events.py` (+11, new file: pure-function
  classification/listing/keyword-match/conversion coverage using synthetic dates,
  since the real event data is entirely historical); `test_calendar_action.py` (+3:
  a structured match wins over a conflicting RAG-chunk date, a generic listing query
  answers without an interrupt, the no-upcoming-events message differs from the
  no-event-data-at-all message - plus the pre-existing no-dated-event test needed a
  scoped `DELETE FROM org_events` once real events landed in the shared dev Postgres,
  same D-052-style fix); `test_events_endpoint.py` (+2, new file: audience filtering,
  `window_days` bounding).
- Verification: `make lint && make typecheck && make test` - 292 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-tripped cleanly. Live-verified against the real dev server: an
  anonymous "What's coming up on the calendar?" correctly answered "There are no
  upcoming events currently scheduled" (honest, not a bug - see D-054); "Add the
  Scholarship Banquet to my calendar" found the real 2023 event via the structured
  path (`source_document_id: "org-event:scholarship-banquet"`, confirming the RAG/LLM
  path was skipped), paused for approval, and the `"ics"` choice produced valid,
  round-trippable RFC 5545 text; `GET /chat/events` correctly returned an empty list.
  All four ROADMAP S18 "Done when" criteria hold: upcoming/completed/canceled/
  recurring classification is correct (live for completed, unit-tested for the rest
  given real data's shape); a past event is never described as upcoming (live and
  tested); a canceled event says so (unit-tested - no real canceled event exists
  yet); `.ics` generation works from a structured event row (live).
- Carry-over: see "Current status" above (S18 additions section).
- New decisions: D-054, D-055.

### S17 — Test-debt cleanup + real org content: branches, team, about (2026-07-19) ✅
- **Test-debt (plan X1).** New `apps/learning-api/tests/conftest.py`: an autouse
  fixture runs a dependency-ordered `DELETE` (mirroring S9/S12/S14's manual recipe)
  for the 4 Mongo-fixture student ids before *and* after every test in the directory -
  self-healing, not just a one-time cleanup (D-053; a shared-connection transaction-
  rollback approach was prototyped and rejected first - see D-053 for why). Confirmed
  727 pre-existing `student-ext-4` rows and all other fixture-id rows cleared to 0 and
  staying at 0 across 3 repeated `make test` runs. Fixed the known-red S9 seed-collision
  test (`test_ai_pipeline.py::test_solver_disagreement_rejects_without_persisting`) by
  swapping its colliding `seed=424242` for a large distinctive seed (`700666`) whose
  generated `rendered_question` doesn't coincidentally match a hand-authored template.
- **Real org content (plan C1, 2.3/2.5-data).** New workspace member `packages/
  webcontent`: `fetch.py` (httpx, timeout + bounded retry, env-configurable base URL -
  D-051), `extractors/{about,branches,team}.py` (BeautifulSoup, targeting the real
  site's WordPress/WPBakery markup - confirmed by fetching and inspecting the actual
  live pages, not guessed), `render.py` (Markdown, no frontmatter, matches the existing
  `knowledge-content/documents` shape), `sync_cli.py` (`make webcontent-sync`: fetch →
  extract → write structured YAML + Markdown, never touches Postgres - human review of
  the diff is the publish gate, same posture as D-026's question gate), `org_load.py`
  + `org_load_cli.py` (`make org-load`: natural-key + `content_hash` upsert into new
  `org_branches`/`org_team_members` tables, mirrors `YoutubeRepository`'s S15
  upsert/inactive-mark shape - a record missing from the latest sync is marked
  inactive, never deleted). **The org (`intellichoice.org`) turned out to be a real,
  operating 501(c)(3) tutoring nonprofit, not a fictional placeholder** (D-051) - the
  user supplied the four real page URLs directly. Extractor unit tests use small,
  hand-trimmed golden-HTML fixtures (no network); the real sync ran live against the
  real site (26 branches, 50 team members across Administration/Branch Managers/Deputy
  Branch Managers/Chapter Leaders, a 5-section About narrative) and was reviewed before
  loading. Found and fixed one real extractor bug via that live run: WPBakery nests
  `vc_column_container` at more than one level for some layouts, double-matching 4 of
  50 team members - fixed by deduping on `(category, name, role_title)`.
- **Schema.** New `org_branches`/`org_team_members` tables + repos + one Alembic
  migration (round-tripped). `org_team_members.name`/`org_branches.address/phone/email`
  get an explicit, narrow, documented exemption in `test_schema_purity.py`'s denylist
  (D-050, the session's decide-at-start gate, plan §19 #2) - public staff bios and
  branch contact info the org already publishes, not student/parent PII.
- **Content.** Replaced the placeholder `branch-directory`/`organization-overview`
  documents with real content (same `document_id`s, `effective_from` moved to
  `2026-07-18` - today, retiring the 2026-08-01 date gate for these two); added a new
  `public-our-team` document/manifest entry. Re-ran `make knowledge-load`: 1 created, 2
  updated, 20 unchanged, confirmed idempotent on a second run (0/0/23).
- **Found and fixed one real pre-existing architecture gap via live verification**
  (D-052): once real content became genuinely retrievable "today" for the first time,
  `packages/knowledge/retrieval.py`'s reranker was found to only *sort* candidates, not
  filter them, and `MockBedrockProvider`'s mock synthesis unconditionally cites
  candidate #1 - so `hybrid_search`'s unconditional `ORDER BY distance LIMIT` semantic
  fallback could surface an irrelevant real chunk as a false-positive citation for an
  unrelated query. Fixed by dropping rerank-score-`0.0` candidates before synthesis (the
  rerank prompt's own scale already defines 0 as "irrelevant"). This is a real
  production-path fix, not a test-only one; several existing tests needed nonsense-
  marker query/chunk text (D-018's pattern) afterward since plausible English phrases
  now risk a weak real match against the new content.
- Tests (+12 net: 6 `packages/webcontent` new - 4 extractor golden-fixture, 2 org_load
  real-Postgres; 2 `packages/db` new - `org_branches`/`org_team_members` round-trips;
  4 pre-existing tests fixed in place, not net-new - `test_ai_pipeline.py`'s known-red
  seed, `test_ingest.py`'s draft-invisibility phrase, `test_qa_graph.py`'s 3
  no-source/happy-path/prompt-injection tests, `test_chat_endpoints.py`'s no-source
  test, and `test_calendar_action.py`'s provenance test - all switched to D-018-style
  nonsense-marker content or (for the last one) added literal keyword overlap with the
  fixed `CALENDAR_QUERY` constant): 258→270 collected, 270/270 passing, stable across 3
  repeated runs.
- Verification: `make lint && make typecheck && make test` - 270 passed, 0 lint/type
  errors, stable across 3 repeated runs. `alembic upgrade head` / `downgrade -1` /
  `upgrade head` round-tripped cleanly for the `org_branches`/`org_team_members`
  migration. Confirmed live against the real dev server: an anonymous `document_qa`
  query about a real branch ("What are the tutoring session times at the Carrollton
  Public Library?") answered with a real citation to `public-branch-directory` (version
  2); a second `make webcontent-sync` + `make org-load` + `make knowledge-load` cycle
  on unchanged real pages was a full no-op (0 created/0 updated throughout). All four
  Phase/S17 "Done when" criteria hold: a live document_qa query about a real branch
  answers today with a citation to the ingested page; re-running sync on unchanged
  pages is a no-op; extractor tests run against saved golden-HTML fixtures with no
  network; full suite green with no HTTP-test row accumulation across 3 repeated runs
  (confirmed 0 rows for all 4 fixture student ids before and after).
- Carry-over: see "Current status" above (S17 additions section).
- New decisions: D-050, D-051, D-052, D-053.

### S16 — Chat frontend (2026-07-18) ✅
- **`POST /dev/token` on `chat-api`** (`main.py`), mirroring `learning_api`'s dev-only
  endpoint (D-006) verbatim but defaulting to `Audience.CHAT` - `apps/chat-web` had no
  way to obtain an authenticated token otherwise. 404s outside `environment=="dev"`.
  2 new tests in `apps/chat-api/tests/test_auth.py` (issues a verifiable chat-audience
  token; 404s outside dev).
- **New `apps/chat-web`** (Vite + React + TS, same toolchain/design system as
  `apps/learning-web` - react 19, oxlint, `tsc -b && vite build`, no state library;
  excluded from the uv workspace alongside `learning-web`, D-034's pattern). `src/
  hooks/useChatSession.ts` drives session creation, `/messages`, `/respond`, and the
  SSE stream; unlike `learning-web`, the visible conversation is a client-built
  `ChatTurn[]` transcript, not read from checkpointed state (D-048 - `QAState` carries
  only the current turn, SPEC §5.19.3). `src/screens/`: `DevLoginScreen` (role picker +
  "continue as guest", since SPEC §5.19.1 makes anonymous access a first-class case
  unlike learning), `ChatScreen` (message bubbles, citation chips, an
  escalation-recommended banner, composer), and one modal per `pending_interrupt` type:
  `EmailApprovalModal` (admin-escalation preview/approve/decline), `CalendarActionModal`
  (google/`.ics`/cancel choice + the event preview), `LocationConsentModal` (the exact
  §5.1.3 notice, ZIP/city text fields, and an optional real
  `navigator.geolocation.getCurrentPosition()` button - the location itself is sent
  only in the one `/respond` call, matching `branch_locator_consent`'s own D-045
  design). `.ics` files download via a client-side `Blob`/`<a download>`, closing S14's
  "chat-web's job (S16)" carry-over - no new backend route needed since `ics_content`
  was already served inline (D-048).
- **Found and fixed one real bug via live Playwright verification** (not caught by
  `tsc`/oxlint): opening the SSE stream immediately after session creation raced the
  LangGraph checkpoint (nothing to read until the first `/messages` call completes),
  producing a transient 404 each session - harmless (`EventSource` auto-reconnects) but
  avoidable. Fixed by gating the stream-open effect on a `streamReady` flag set only
  after the first turn resolves (D-048). Confirmed via a before/after Playwright run:
  4 console errors per multi-scenario run before the fix, 0 after.
- `pyproject.toml`: `apps/chat-web` added to the uv workspace exclude list. `Makefile`:
  new `dev-chat-web` target.
- Tests: 2 new (`apps/chat-api/tests/test_auth.py`), full suite 261/262 passing (the 1
  failure is the pre-existing S9 test documented above, confirmed unrelated to this
  session's diff - `packages/curriculum` wasn't touched). `apps/chat-web`: `npm run
  build` (`tsc -b && vite build`) and `npm run lint` (oxlint) both clean.
- Verification: `make lint && make typecheck && make test` clean except the documented
  known-red test. Live-verified both dev servers together (`chat-api` on :8002,
  `chat-web` on :5173, matching the CORS origin already configured in `chat_api.main`)
  via a scripted Playwright session covering all four `Intent`s: an anonymous
  `document_qa` query correctly produced the fail-closed no-answer/escalation response
  (see the S16-additions carry-over on why - the date gate, not a bug); an anonymous
  `branch_locator` query paused with the exact §5.1.3 notice, and submitting a ZIP
  returned both branches correctly sorted nearest-first with real distance/duration; an
  anonymous `admin_contact` query previewed a real subject/body draft, and approving it
  returned the real "sent" confirmation; a `calendar` query correctly produced the
  graceful "no dated event found" message (same date-gate reasoning). Separately
  confirmed dev sign-in as `parent-ext-1` mints a real chat-audience JWT and attaches it
  as `Authorization: Bearer …` on every request (inspected via Playwright's request
  log) - the role-gating logic itself was already proven correct at the graph level by
  S13's own tests; this session's job was proving the frontend actually wires
  authentication through, which it does. `.ics` download verified via a network-mocked
  Playwright run (see S16-additions above) - downloaded bytes matched the served
  content exactly. Both stated "Done when" criteria hold: an anonymous user can do
  FAQ + locator + `.ics` end-to-end locally (FAQ/`.ics`'s "found" branches are
  currently only reachable via the documented date-gate workaround, not a gap in this
  session's code); a logged-in parent's request is genuinely role-gated end-to-end.
- Carry-over: see "Current status" above (S16 additions).
- New decisions: D-048.

### S15 — MCP tools II: Maps locator and YouTube catalog (2026-07-18) ✅
- **Branch Locator (SPEC §5.1.3, §5.22).** New `packages/shared/.../maps.py`
  (`GeocodeQuery`/`Coordinates`/`RouteQuery`/`RouteResult`/`MapsProvider`/
  `haversine_km`) + `packages/adapters/.../fake_maps.py` (`FakeMapsProvider` -
  deterministic gazetteer + real haversine distance/duration, `fail_geocode`/
  `fail_routes` toggles standing in for a Maps outage). `BranchInfo`/`ProfileAdapter`
  gained `address`/`latitude`/`longitude` + `list_branches()`; Mongo fixtures updated to
  match, every `ProfileAdapter` test double across both apps updated for the new method.
  New `chat_api.services.branch_locator.find_nearest_branches`: geocode -> per-branch
  route -> sort, implementing all three §5.22 fallbacks locally (Maps unavailable ->
  address list only; no/undeliverable location -> ask for ZIP/city; route-computation
  failure -> a `haversine_km`-based straight-line estimate, clearly flagged
  `is_estimate=True`).
- **Location-consent design (D-045).** New `branch_locator_consent` graph node pauses
  via `interrupt()` with the exact §5.1.3 notice *before* any location is collected
  (unlike `admin_escalation`/`calendar_action`'s D-021 "precompute then pause" split) -
  the caller's ZIP/city/address/precise coordinates travel only in the same `/respond`
  call as their approval (`LocationConsentChoice`), never through `TurnContext` or a
  checkpointed `QAState` field. A dedicated test proves the full location is absent
  from the checkpointed state after a real turn; the one residual, not-fully-fixable
  caveat (LangGraph's own resume-value bookkeeping) is documented in D-045 and
  PROGRESS's carry-over section. `maps.geocode`/`maps.compute_routes` registered in
  `chat_api.main`'s lifespan.
- **YouTube catalog + sync worker (SPEC §5.18, Phase 16/§6.17).** New `youtube_videos`
  Postgres table (§5.18.2 fields + pgvector `embedding`) + `YoutubeRepository`
  (metadata-filter-then-cosine-rank `search_catalog`, natural-key `upsert_video`,
  `mark_inactive_except` - never deletes, only flips `active_status`). One Alembic
  migration (round-tripped). New `packages/shared/.../youtube.py`
  (`YoutubeProvider`/`RawVideoMetadata`/`YoutubeCatalogSearchArgs`/`Result`) +
  `packages/adapters/.../fake_youtube.py` (4 deterministic stub videos covering the S10
  `linear_equations` skills, real credentials don't exist yet - D-002).
- **Real LLM video classification, re-validated (D-046).** New
  `BedrockTask.VIDEO_CLASSIFICATION` (`VideoClassificationPayload`/`Response`) - chosen
  over a deterministic keyword mapping since topic/skill assignment from free-text
  title/description is a genuine extraction task (mirrors `CALENDAR_EXTRACTION`'s
  reasoning, D-038), but every proposed name is re-validated against the *real*
  curriculum registry (`packages/curriculum.content.load_curriculum`) before becoming a
  stored `topic_id`/`skill_id` - an invented or misspelled name is silently dropped
  (D-038/D-026's "model proposes, code re-derives" pattern, applied to catalog labels).
  A Bedrock failure falls back to empty `topic_ids`/`skill_ids`, never a guess.
- **New workspace member `packages/youtube`.** `classify.py` (the re-validation above),
  `catalog_sync.py` (`sync_channel`: fetch -> classify -> embed -> upsert -> mark-
  missing-inactive; a fetch failure raises `YoutubeSyncError` *before* any write, so
  SPEC §6.17 "keeps the previous catalog on failure" holds), `settings.py`, `sync_cli.py`
  + `make youtube-sync` (manual trigger this session per ROADMAP's own scope note; a
  real weekly EventBridge schedule is later infra work, not a gap).
- **Learning-api video option (SPEC §5.18.3).** `_video_intervention` now calls the real
  `youtube_catalog.search` MCP tool instead of S10's hardcoded stub map (D-031,
  superseded). The tool is registered on a fresh, throwaway `McpToolRegistry` built
  inside `video_catalog.search_video` itself (D-047) rather than the shared
  `app.state` one every other tool uses - its handler closes over *this request's*
  `YoutubeRepository`/embedding, and mutating the shared long-lived registry per
  request would risk one request's registration racing another's. `TurnContext` gained
  `youtube_repo`; `learning_api.main`'s gateway gained an `embedding_provider` (mirrors
  `chat_api.main`'s S12 wiring) since the search tool needs `create_embedding`.
- Tests (+14 net, 245->259 collected, 258/259 passing - the 1 failure is the
  pre-existing S9 test documented above, confirmed unrelated to this session's diff;
  net count reflects both new tests added and S10's 2 now-obsolete stub-catalog tests
  removed):
  `apps/chat-api/tests/test_branch_locator.py` (+7: consent-notice pause, decline never
  calls Maps, approved-with-no-location asks for ZIP/city, ZIP resolves to a sorted
  nearest-first branch list, Maps-unavailable falls back to the address list,
  route-computation failure falls back to a labeled straight-line estimate, and a
  dedicated test proving precise coordinates never land in the checkpointed `QAState`);
  `test_chat_endpoints.py` (+1: full HTTP consent -> ZIP round trip against the real
  dev-server lifespan); `test_qa_graph.py` (branch_locator intent now pauses for
  consent instead of the old "not yet available" message);
  `packages/db/tests/test_repositories.py` (+1: `YoutubeVideo` natural-key upsert,
  inactive-marking, metadata-filtered + embedding-ranked search - 22nd repository
  covered); `packages/youtube/tests/test_classify.py` (+2: a name outside the real
  curriculum menu is dropped, not stored; a Bedrock failure falls back to
  safe/unclassified defaults); `test_catalog_sync.py` (+3: create-then-idempotent-
  re-sync with real classification landing on the seeded fixture skills, a removed
  video is marked inactive not deleted and drops out of search, a fetch failure raises
  and leaves the existing catalog untouched); `apps/learning-api/tests/
  test_video_catalog.py` (+2, new file, replacing S10's now-obsolete pure-function
  stub-catalog tests: a seeded catalog match is found and audited, no match falls back
  to the exact §5.11.6 message).
- Verification: `make lint && make typecheck && make test` - 258 passed (+14 net over
  S14's 244), 0 lint/type errors, stable across 3 repeated runs. `alembic upgrade head`
  / `downgrade -1` /
  `upgrade head` round-tripped cleanly for the `youtube_videos` migration.
  Live-verified: `make youtube-sync` against the real dev Postgres created 4 videos with
  real LLM-classified `topic_ids`/`skill_ids` matching the real curriculum registry
  (confirmed via direct query), then a second run was fully idempotent (0 created/4
  updated/0 marked inactive). Curled the live chat-api dev server end-to-end: a branch
  question paused with the exact §5.1.3 consent notice; approving with ZIP `62704`
  returned both branches correctly sorted nearest-first with real distance/duration,
  no precise coordinates anywhere in the response. Both Phase 16 (§6.17) "Done when"
  criteria that apply to a manual-trigger dev build hold: the learning flow makes zero
  external YouTube calls (proven by `test_video_catalog.py`/`test_catalog_sync.py`,
  and by inspection - `search_catalog` never touches `YoutubeProvider`); a sync failure
  keeps the previous catalog (proven by `test_catalog_sync.py`); consent tests pass
  (`test_branch_locator.py`, including the dedicated no-coordinates-in-checkpoint test).
- Carry-over: see "Current status" above (S15 additions section).
- New decisions: D-045, D-046, D-047.

### S14 — MCP tools I: Gmail, Calendar, .ics (2026-07-17) ✅
- **MCP tool registry (SPEC §5.22-§5.24, Phase 15/§6.16).** New
  `packages/shared/.../mcp.py`: `McpTool[ArgsT, ResultT]`/`McpToolRegistry` -
  `call()` validates `raw_args` via Pydantic *before* anything executes (the literal
  Phase 15 completion criterion), checks an optional `allowed_roles` set, runs the
  handler under a timeout, and records one `ToolCallAuditEvent` (tool name, caller
  external id or `None`, success/failure, exception *type* name only - never the raw
  message or payload) via an injected `AuditRepo`, regardless of outcome. Deliberately
  **no automatic retry** (D-042) - `gmail.send_email`/`calendar.create_event` are
  non-idempotent side effects with no idempotency-key support in their fake transports.
  New `packages/db/.../models/mcp.py` (`McpToolCall` table, no PII) +
  `repositories/mcp.py` (`McpToolCallRepository`, implements the registry's `AuditRepo`
  Protocol) back it.
- **Gmail (SPEC §5.24).** `EmailMessage` (`packages/shared/.../email.py`) gained a
  `field_validator` rejecting `\r`/`\n` in `recipient`/`subject` (header-injection
  defense, protects both apps from one place). `learning_api`'s S7 attendance email
  (`services/attendance.py`) now routes through the registry as the `gmail.send_email`
  tool instead of calling `EmailTransport.send` directly, and implements SPEC §5.29
  "Gmail MCP failure -> Preserve draft" (catches `McpToolError`, returns a new
  `EMAIL_FAILED_MESSAGE` instead of crashing; the *approval* is still recorded - only
  the *send* failed, a separate fact on the `mcp_tool_calls` audit row). `chat_api`
  gained a real `admin_contact` handler (`graph/nodes.py`'s `prepare_admin_escalation`
  -> `admin_escalation`): a deterministic draft (no LLM call,
  `services/admin_escalation.py`'s `build_escalation_draft`, mirrors
  `attendance.build_attendance_email_draft`'s shape), rate-limited
  (`services/rate_limit.py`'s `InMemoryRateLimiter`, SPEC §5.24.2), previewed via
  `interrupt()`, sent through the same `gmail.send_email` tool only on approval.
- **Calendar (SPEC §5.23).** New `CalendarEvent`/`CalendarTransport`
  (`packages/shared/.../calendar.py`) and `FakeCalendarTransport`
  (`packages/adapters/.../fake_calendar.py`). New `packages/adapters/.../ics.py`:
  `generate_ics` (RFC 5545 via the `icalendar` library - UID/DTSTAMP freshly generated
  per call, datetimes normalized to UTC rather than embedding a `VTIMEZONE` block) +
  `validate_event`/`validate_ics_text` (SPEC §5.23.4's rules as small pure `check_*`
  functions, mirroring `packages/curriculum/.../validation.py`'s shape). New
  `BedrockTask.CALENDAR_EXTRACTION` + `CalendarExtractionPayload/Response`
  (`packages/shared/.../bedrock.py`) - dates are free prose in source documents, a
  genuine structured-extraction task; `MockBedrockProvider` gained a deterministic
  regex-based date-finder stand-in. `chat_api`'s new `calendar` handler
  (`graph/nodes.py`'s `calendar_extract` -> `calendar_action`): reuses
  `intellichoice_knowledge.retrieval.retrieve` exactly as `answer_document_qa` does,
  then `services/calendar.py`'s `extract_calendar_event` - the model proposes which
  retrieved chunk supports an event and drafts its fields, but `source_document_id`/
  `source_page` are always re-derived from the *real* chunk/document row (D-038's
  "model proposes, code re-derives provenance" pattern, never the model's own claim);
  `found=False` or a failed `validate_event` means no event, no interrupt (SPEC §5.29
  "No RAG result -> do not guess"). Found -> `interrupt()` for a 3-way
  `"google"/"ics"/"cancel"` choice; `"google"` calls the `calendar.create_event` tool
  and falls back to `generate_ics` on `McpToolError` (SPEC §5.29 "Google Calendar
  failure -> Generate .ics", verbatim); `"ics"` generates directly; `"cancel"` takes no
  action. All three choices record the literal decision string to `interrupt_approvals`
  (no CHECK constraint on that column, so no lossy 3-to-2 mapping needed).
- **`interrupt_approvals` becomes app-agnostic (D-043).** Renamed
  `learning_session_id` -> `session_id`, added `source_app` ("learning"|"chat"), made
  `decided_by_external_id` nullable (chat-api allows anonymous callers, SPEC §5.19.1,
  with no external id to record) - one Alembic migration, round-tripped.
- **chat-api graph interrupts (D-044).** Two intents that previously fell through to
  `unavailable_intent` (`admin_contact`, `calendar`) now pause via real `interrupt()`s,
  the first ones this app has had (S13 shipped none). New `POST /chat/sessions/{id}
  /respond` mirrors `learning_api`'s shape (discriminated-union request body,
  `Command(resume=...)`, a `_reject_if_paused` 409-guard on `/messages` for D-021
  gotcha #2) but is simpler: `QAState.email_draft`/`calendar_event` are checkpointed
  directly (no D-020 indirection) since neither carries Mongo-sourced PII the way
  learning-api's attendance draft does - `email_draft` is deliberately typed as
  `EmailDraftState` (subject/body only, no recipient, so `QAState`'s own "no email
  addresses stored here" invariant still holds); `calendar_event`'s fields come from
  public organizational documents, not a person. Both new pausing nodes split their
  pre-interrupt work into a separate, already-completed prior node
  (`prepare_admin_escalation`, `calendar_extract`) rather than computing it inline
  before their own `interrupt()` call - one real bug was caught this way during manual
  verification (see below) and fixed before it shipped.
- **Found and fixed one real bug via live manual verification** (not caught by
  `pytest`/`pyright`): the first `admin_escalation` draft (built inline, right before
  its own `interrupt()`) was invisible to the `/respond` pending-interrupt preview,
  since a node that pauses never actually *returns* until resumed - nothing it computes
  before the pause reaches checkpointed state. Curling `/messages` for an
  `admin_contact` query showed `pending_interrupt.email_subject/email_body` as `null`.
  Fixed by splitting draft-building into `prepare_admin_escalation`, a node that
  completes normally *before* `admin_escalation`'s pause (mirrors
  `learning_api.resolve_student`/`await_child_selection`'s split, D-021) - the same
  fix `calendar_extract`/`calendar_action` already used for a different reason (never
  re-running a real Bedrock call on resume), applied here for this reason instead.
  Re-verified live end-to-end after the fix: anonymous admin-escalation preview -> approve
  -> real send recorded in both `interrupt_approvals` and `mcp_tool_calls`; calendar
  extraction against a live-seeded dated chunk -> `.ics` choice -> valid RFC 5545 text
  with correct line-folding, confirmed by round-tripping it back through `icalendar`.
- Tests (+35, 210->245 collected, 244/245 passing - the 1 failure is the pre-existing S9
  test documented above, confirmed unrelated to this session's diff):
  `packages/shared/tests/test_mcp.py` (the Phase 15 completion criterion itself: invalid
  args never reach the handler, unknown tool/disallowed role never call anything, a
  timeout raises without retry, audit events never carry the raw exception message);
  `test_email.py` (header-injection rejected in `recipient`/`subject`, body newlines
  allowed); `packages/adapters/tests/test_ics.py` (the §5.31.2 ".ics syntax" executable
  evaluator - round-trip validity, distinct UIDs per call, escaping/line-folding proof,
  invalid-timezone/bad-range rejection before any text is generated);
  `apps/learning-api/tests/test_learning_graph_routes.py` (+1: Gmail send failure
  preserves the draft and still records the approval); `apps/chat-api/tests/
  test_admin_escalation.py` (+4: approve-sends-and-records, decline-sends-nothing,
  send-failure-preserves-draft, rate-limit-blocks-repeated-anonymous-escalation);
  `test_calendar_action.py` (+6: real-chunk provenance re-derivation, `.ics` choice
  validity, Google choice creates event, Google failure falls back to `.ics`, cancel
  takes no action, no-dated-event-found is a graceful no-answer with no interrupt);
  `packages/db/tests/test_repositories.py` (+2: `InterruptApproval`/`McpToolCall`
  round-trips, 19th/20th repositories covered).
- Verification: `make lint && make typecheck && make test` - 244 passed (+35 over S13's
  210), 0 lint/type errors, stable across repeated runs. `alembic upgrade head` /
  `downgrade -1` x2 / `upgrade head` round-tripped cleanly for both new migrations.
  Live-verified against both real dev servers: anonymous admin-escalation end-to-end
  (preview with real subject/body -> approve -> `EMAIL_SENT_MESSAGE` -> a real
  `FakeEmailTransport.sent` entry -> `interrupt_approvals`/`mcp_tool_calls` rows);
  calendar extraction against a live-seeded dated document chunk -> `.ics` choice ->
  valid, round-trippable RFC 5545 text with correct escaping/line-folding. Both Phase
  15 (§6.16) "Done when" criteria hold: only Pydantic-validated tool arguments can
  execute (enforced in the registry itself, proven by `test_mcp.py`); every send has an
  approval + audit record (proven by both the graph-level tests and the live
  verification above).
- Carry-over: see "Current status" above (S14 additions section).
- New decisions: D-042, D-043, D-044.

### S13 — Advanced RAG and the Q&A graph (2026-07-17) ✅
- **Hybrid search (SPEC §5.21.3-5.21.6).** `packages/db/.../repositories/rag.py`:
  `ChunkFilters` gained `audiences`/`restrict_to_branch`/`as_of` (D-039); new
  `keyword_search_chunk_ids` (`websearch_to_tsquery` + `ts_rank` over the GIN-indexed
  `search_vector`), `semantic_search_chunk_ids` (pgvector cosine distance over the new
  HNSW `embedding` index), `reciprocal_rank_fusion` (pure function), and `hybrid_search`
  (fuses both, filter-first, never retrieve-then-hide). One Alembic migration adds the
  GIN/HNSW/composite-btree indexes (round-tripped).
- **Reranking + citation-grounded synthesis (§5.21.7-5.21.8, D-037/D-038).** New
  `packages/shared/.../bedrock.py` schemas: `ScopeAndIntentPayload/Response`,
  `RerankPayload/Response`, `RagAnswerPayload/Response` (raw, model-proposed
  `LlmCitation`s) and the backend-only `Citation`/`GroundedAnswer` (SPEC §5.21.8's own
  schema, never round-tripped from the model). New `packages/knowledge/retrieval.py`
  (`retrieve`: embed query -> `hybrid_search` -> LLM rerank, with a graceful RRF-order
  fallback on any `BedrockGatewayError`). New `apps/chat-api/.../services/qa.py`
  (`answer_question`: synthesizes via `BedrockTask.RAG_ANSWER`, then verifies every
  citation's quote is a real substring of its cited chunk before trusting it - a claim
  with no surviving citation, low confidence, or `sources_conflict=True` becomes a
  no-answer/escalation response instead). `MockBedrockProvider` gained deterministic
  branches for all three new response types.
- **QAState LangGraph (SPEC §5.19.2, D-041).** New `apps/chat-api/.../graph/` (`state.py`,
  `nodes.py`, `build.py`), mirroring `learning_api.graph`'s shape: `resolve_role` (claims
  -> role/branch, anonymous-safe) -> `scope_guard` (one combined
  `BedrockTask.SCOPE_AND_INTENT` call) -> `refuse` (§5.19.4 verbatim) /
  `unavailable_intent` (branch_locator/calendar/admin_contact - S14/S15 build the real
  tools) / `answer_document_qa` (role-filtered retrieval + synthesis + verification). No
  `interrupt()` yet - nothing this session needs external approval.
- **`role_access_filter` (D-039).** New `apps/chat-api/.../services/role_access.py`:
  resolves `(user_role, branch_external_id)` from `TokenClaims | None` (branch only for
  students, per S2's `ProfileAdapter` shape) and builds `ChunkFilters` entirely
  server-side - authorization never touches the query text (CLAUDE.md non-negotiable #3).
- **Anonymous access (D-040).** New `get_optional_claims` dependency (missing header ->
  anonymous; present-but-invalid -> still 401s). `POST /chat/sessions` and `POST
  .../messages` (SPEC §5.28.2 subset - `messages`/`stream` only, per this session's
  roadmap scope) both allow it; `GET /me` still requires real auth.
- **SSE stream.** New `apps/chat-api/.../routers/stream.py` + `services/session_events.py`
  (own `ChatSessionEventBus` copy, mirrors `learning_api`'s S11 pattern) - `?token=` is
  optional; a session with no resolved owner (`user_external_id is None`) is streamable
  by anyone holding the session id, matching how an anonymous chat naturally has no
  narrower access boundary than the id itself.
- Tests (+28, 182→210 collected, 209/210 passing - the 1 failure is the pre-existing S9
  test above, confirmed unrelated to this session's diff): `packages/db/tests/
  test_rag_search.py` (pure RRF unit tests, real-Postgres hybrid-search fusion, draft/
  expired-chunk exclusion, branch restriction); `apps/chat-api/tests/test_role_access.py`
  (pure role/branch resolution + filter construction); `test_qa_service.py` (real-Postgres
  citation verification: quote-matches, fabricated-quote-dropped, low-confidence refusal,
  conflict surfaced, gateway-error fallback - via a scripted `_FakeGateway`, mirroring
  `test_tutor_service.py`'s pattern); `test_qa_graph.py` (full graph `ainvoke` via
  `InMemorySaver` + real `MockBedrockProvider` + real rollback-isolated Postgres: the
  Phase 14 "Done when" role-filter test itself - a student query never retrieves the
  seeded tutor-audience chunk even though it's lexically the better keyword match - plus
  out-of-scope refusal, unavailable-intent, no-answer/escalation, grounded happy path,
  and prompt-injection-in-a-chunk not changing `scope`/`intent`); `test_chat_endpoints.py`
  (HTTP-level via `TestClient(app)`: anonymous session creation, out-of-scope/no-answer
  through real endpoints, `/stream`'s `_initial_snapshot` token-match/anonymous/404 cases
  - exercised directly rather than through a live SSE response, same D-033 reasoning
  `learning_api`'s own stream tests already established).
- **Found and fixed one real pre-existing-test fragility in-flight** (not new-code bug):
  `packages/db/tests/test_repositories.py::test_rag_repository_round_trip` asserted an
  exact `len(results) == 1` for a generic `query="attendance"` search - harmless while
  `rag_chunks` was empty between S12 sessions, but once this session's live verification
  re-ran `make knowledge-load` (leaving the real 22-document/110-chunk seed permanently
  in the shared dev Postgres, same as S12 left it), that generic word also matched the
  real `parent-attendance-policy` document's chunks, inflating the count to 6. Fixed by
  switching the test's chunk text/query to a nonsense marker phrase (D-018's throwaway-
  content pattern) - not this session's own diff, but blocked a clean baseline the same
  way S12's own pre-session cleanup did.
- Verification: `make lint && make typecheck && make test` - 209 passed (+28 new tests
  over S12's 181, all from this session's own diff), 0 lint/type errors, stable across 3
  repeated runs. `alembic upgrade head` / `downgrade -1` / `upgrade head` round-tripped
  cleanly for the new index migration. Live-verified against the real dev server after
  re-running `make knowledge-load` (the 22 docs/110 chunks from S12 had been cleaned):
  confirmed the role-filter Done-when criterion live (tutor token retrieves the tutor
  handbook chunk; the identical query from a student token does not, via a direct
  service-layer call bypassing the effective-date gap noted above), and confirmed live
  via HTTP that an out-of-scope query refuses with the exact §5.19.4 message and an
  in-scope query with no effective content correctly escalates rather than guessing. Both
  Phase 14 (§6.15) completion criteria hold: role-filter tests (and live verification)
  prove a student query never retrieves tutor/branch_manager chunks; unanswerable queries
  refuse with escalation instead of guessing. "Core claims have citations" holds via the
  quote-verification tests; "unauthorized documents are never retrieved" holds via both
  the metadata-filter-first SQL shape and the role-filter tests/live check.
- Updated `docs/ARCHITECTURE.md`: new invariants (filter-before-rank, citation
  verification, retrieved-content-is-data), `chat-api` node expanded (routers/services/
  graph), new diagram 5 (Q&A request flow), storage-split RAG row updated (indexes +
  hybrid_search).
- Carry-over: see "Current status" above (S13 additions section).
- New decisions: D-037, D-038, D-039, D-040, D-041.

### S12 — RAG content foundation and ingestion (2026-07-17) ✅
- **Pre-session cleanup (not S12 scope, but blocked a clean baseline):** the shared local
  dev Postgres had accumulated real rows under the Mongo-fixture student ids
  (`student-ext-1/2/4`) from six-plus past sessions' "curl the live dev server" manual
  verification steps (which commit for real, unlike the rollback-isolated repository
  tests) - up to 431 `assessment_sessions` rows for one id. This failed 2 previously-green
  `packages/db` round-trip tests. Cleaned up via targeted `DELETE`s (dependency order:
  `learning_gain`/`study_attempts`/`study_items` → `study_sessions`/`assessment_attempts`/
  `assessment_items` → `assessment_sessions` → `mastery`/`blocked_sessions`), confirmed by
  the user first. Baseline returned to the pre-existing 162/163 (documented known-red test
  only). **Root cause turned out to be broader than first diagnosed** - see "Newly
  observed" in "Current status" above: it's `apps/learning-api/tests/*`'s own uncommitted-
  rollback TestClient runs, not only past manual verification, so this will reaccumulate
  from ordinary `make test` runs and isn't a one-time fix.
- **`knowledge-content/` repo structure (SPEC §5.20.1-§5.20.3).** 5 manifests (`manifests/
  {public,parent,student,tutor,branch_manager}.yaml`), 2 JSON Schemas (`schemas/
  document_manifest.schema.json`, `schemas/metadata.schema.json`), and all 22 SPEC-listed
  placeholder documents (`documents/<audience>/<slug>/content.md`) - real prose with
  genuine Markdown structure (multiple headings, tables, lists), every one carrying the
  DRAFT banner, 3 deliberately `status: draft` (spread across audiences) so the
  draft-invisibility completion criterion has real fixtures.
- **Embedding capability on the Bedrock gateway (SPEC §5.21.1, D-035).** Amazon Titan Text
  Embeddings V2 (1024-dim) chosen as the real model; `packages/adapters/.../bedrock/
  provider.py` split into two Protocols (`BedrockProvider.raw_generate`,
  `EmbeddingProvider.raw_embed`) since Titan isn't served by the Anthropic Messages API
  surface `AnthropicBedrockProvider` uses. New `TitanEmbeddingProvider` (boto3-based, never
  exercised against real AWS this session, same footing as D-025);
  `MockBedrockProvider.raw_embed` returns a hash-seeded deterministic unit vector per text.
  `ResilientBedrockGateway` gained `create_embedding` (same timeout/retry/circuit-breaker/
  cost-budget machinery as `generate_structured`) and an optional `embedding_provider`
  constructor param. `EMBEDDING_DIM` 1536 → 1024 (`rag_chunks.embedding` was never written
  to, so this was a plain `alter_column` migration, no data to migrate).
- **New `packages/knowledge` workspace member (D-036).** `manifest.py` (JSON-Schema +
  Pydantic manifest validation), `content_store.py` (`ContentStore` Protocol +
  `LocalFilesystemContentStore`, standing in for S3 per D-002, bucket-relative keys so
  swapping to real S3 is a config change), `chunking.py` (LlamaIndex `MarkdownNodeParser`
  structural chunking - heading/table/list boundaries, not fixed character counts;
  `section_title` parsed directly off each node's own leading heading line rather than
  LlamaIndex's `header_path` metadata, which was found to lag by one heading transition),
  `ingest.py`/`ingest_cli.py` (the pipeline + `make knowledge-load`, mirroring
  `intellichoice_curriculum.loader`/`pipeline_cli`'s shape). Idempotency is keyed by
  `source_sha256` under each manifest entry's `document_id` (natural key, D-016's
  pattern): unchanged content is a no-op, changed content replaces that document's chunks
  in place (new `RagRepository.delete_chunks_for_document`/`refresh_search_vectors`/
  `get_document`).
- Tests (+20, 162→182 collected, 181 passing - the 1 failure is the pre-existing S9 test
  above): `packages/knowledge/tests/test_manifest.py` (all 5 real manifests validate, 22
  total entries, unique ids, at least one draft, 2 deliberately-broken fixtures fail
  schema validation); `test_chunking.py` (heading-bounded splits, table/list preservation,
  single-level parent hierarchy, determinism); `test_ingest.py` (real Postgres, skip-if-
  unreachable per D-008/D-013 style - full-manifest ingest then idempotent re-run with
  document/chunk counts asserted unchanged, a draft document's chunks proven unreachable
  via `search_document_chunks` while an approved document's are findable, and an
  in-place-update test via a `_DictContentStore` double proving changed content replaces
  rather than duplicates chunks); `packages/adapters/tests/test_bedrock_gateway.py`
  extended (`create_embedding` success/determinism/timeout-retry/cost-budget/missing-
  provider paths). Existing `_FakeGateway`/`_ScriptedGateway` test doubles in
  `test_tutor_service.py`/`test_ai_pipeline.py` gained a `create_embedding` stub to keep
  satisfying the widened `BedrockGateway` Protocol.
- Verification: `make lint && make typecheck && make test` — 181 passed (+20 net over
  S11's 162, some new, some pre-existing-test-fixup), 0 lint/type errors, stable across 3
  repeated runs. `alembic upgrade head` / `downgrade -1` / `upgrade head` round-tripped
  cleanly for the `EMBEDDING_DIM` migration. Live-ran `make knowledge-load` against the
  real dev Postgres twice: first run created 22 documents/110 chunks (all with non-null
  embeddings); second run reported 0 created/0 updated/22 unchanged/0 chunks (proving
  idempotency via `source_sha256`, not just the rollback-session test). Directly queried
  `search_document_chunks` for a phrase that only exists in a `status: draft` document (0
  results) versus a phrase from an approved document (1 result), confirming Phase 13's
  (§6.14) completion criterion live, not just in a test. Left the 22 real documents/110
  chunks in the dev Postgres (confirmed with the user) - not test pollution, exactly what
  `knowledge-load` is meant to produce, and useful seed data for S13's retrieval work.
- Updated `docs/ARCHITECTURE.md`: new `packages/knowledge` node, new offline-pipeline node
  (`make knowledge-load`), `knowledge-content/` store node, a 4th Mermaid diagram for the
  ingestion pipeline, and a storage-split table update.
- Carry-over: see "Current status" above (S12 additions section).
- New decisions: D-035, D-036.

### S11 — Learning frontend with SSE (2026-07-16) ✅
- **SSE progress stream (SPEC §5.14.1).** New `services/session_events.py` (in-process
  per-session pub/sub) and `routers/stream.py` (`GET /learning/sessions/{id}/stream`):
  every mutating action handler in `routers/sessions.py` now also publishes the
  turn's response as a `SessionSnapshotEvent`; `/stream` replays the live checkpoint
  snapshot on (re)connect before forwarding further pushes. Coarse state-push, not
  per-node LangGraph event streaming (D-032) - matches the one-`ainvoke`-per-action
  architecture (D-019), where there's nothing to stream mid-turn except the Bedrock
  hint/solution call.
- **Parent-dashboard history endpoint (SPEC §5.14.3).** New `GET /learning/students/
  {id}/sessions`: `services/history.py` reconstructs a student's session history from
  existing tables (`LearningGain` for completed cycles, `BlockedSession` for blocked
  weeks, `ProblemReport`, `Mastery`) since no `LearningSession` grouping table exists
  post-S6. One migration adds `learning_gain.study_session_id`/`.topic_id` (nullable)
  so hint/solution/video counts and the tutor-review flag can be pulled from the
  right `StudyAttempt` rows. Every skill reference is resolved to `Skill.name` before
  it reaches a response DTO - `skill_id` never crosses that boundary (CLAUDE.md
  non-negotiable #10). Weekly automated report + long-run trend charting stay out of
  scope (need a worker / more infra than one session).
- **Dev-only auth.** `POST /dev/token` (`main.py`, 404s outside `environment=="dev"`)
  wraps the existing `FakeTokenIssuer` so the frontend has something to call locally,
  standing in for `go.intellichoice.org`'s real auth (out of scope).
- **New `apps/learning-web`** (Vite + React + TS, no state library): `useLearningSession`
  hook drives the 9 REST actions + the SSE stream; screens for dev sign-in, child
  selection, attendance (blocked → ask-branch-manager/acknowledge → email preview),
  topic pick, exam (pre/study/post), intervention chooser + content panel, results, and
  the parent dashboard. `sessionStorage`-persisted session id is what makes a refresh
  restore exact position - `/stream`'s initial snapshot does the rest, no replay logic
  needed client-side.
- **Four real bugs found and fixed via Playwright-driven manual verification** (not
  caught by `tsc`/`oxlint`/pytest) - see D-034: a stale-closure bug that silently
  no-op'd `chooseStudent` after `startSession`; `/student` never being called for the
  parent role at all; the attendance "resolved" flag being computed from a state
  combination that's also true the instant the gate first blocks; and raw `skill_id`s
  being rendered directly to students/parents. Also found: adding `apps/learning-web`
  under `apps/*` broke `uv run` workspace-wide until excluded in `pyproject.toml`
  (D-034).
- Tests (+6, 157→163): `apps/learning-api/tests/test_stream_and_history.py` -
  dev-token issuance + dev-only 404 gating, a pure `SessionEventBus` pub/sub test,
  `/stream`'s connect-time snapshot and cross-student rejection (via
  `routers.stream._initial_snapshot` directly - `TestClient.stream()` hangs against
  an intentionally-never-ending SSE response, confirmed by killing a stuck process;
  see D-033), and the history endpoint reflecting a real completed session plus a
  cross-access 403.
- Verification: `make lint && make typecheck && make test` - all of S11's own code
  (163 tests, +6) passed repeatedly during the session; a final re-run during
  end-session found one *unrelated* pre-existing failure in `packages/curriculum`
  (162/163) - see "Known red test" in "Current status" above; root-caused and
  confirmed unconnected to any file this session touched. 0 lint/type errors across
  the whole repo. `apps/learning-web`: `npm run build` (tsc + vite build) and
  `npm run lint` (oxlint) both clean. Live verification: both
  dev servers run locally, driven end-to-end with a temporary Playwright install
  (no `chromium-cli` available in this environment) through dev sign-in → start →
  topic select → full pre-exam → study phase with a triggered hint → post-exam →
  results screen, confirmed via screenshots at each step; a mid-results-screen browser
  refresh restored the identical scores (Phase 11 §6.12 "Done when": refresh restores
  exact position); separately verified the attendance-blocked → ask-branch-manager →
  email-preview → send flow and the parent 2-child selection screen render correctly
  with real Mongo-sourced data. Both Phase 11 completion criteria hold.
- Carry-over: see "Current status" above.
- New decisions: D-032, D-033, D-034.

### S10 — Adaptive mastery and study planner (2026-07-16) ✅
- **Retry-ladder study flow (SPEC §5.11.7).** Reworked `apps/learning-api/.../services/
  flow.py` from S5's fixed 5-`StudyItem` batch to serving one question at a time with a
  per-skill escalation ladder: base question → 2 same-skill retries → an easier
  **prerequisite** problem → on the 4th unresolved attempt, `tutor_review_flagged` + continue
  (D-028). `advance_study` is the single labeling/mastery/routing point; study completes when
  every base target skill reaches a terminal outcome, not at a fixed count. One Alembic
  migration adds `StudyItem.target_skill_id/skill_id/difficulty/is_remediation` +
  `StudyAttempt.solution_used/tutor_review_flagged` (`server_default` so it applies to the
  populated dev DB; round-tripped).
- **Outcome labels + independent mastery (§5.11.5, §5.10.3).** New `study_outcomes.py` (pure)
  derives the six §5.11.7 labels; only `independent_correct` counts toward bootstrap mastery —
  `mastery_bootstrap.resolve_graded_attempts` now grades study attempts outcome-aware, so an
  assisted/unresolved correct never inflates mastery (D-029). `learning_gain.support_dependency`
  wires §5.13.3's independent/hint/solution rates from those labels (replacing S8's 0.0 stub).
- **Difficulty routing (§5.10, §5.11.2).** `mastery_bootstrap.recommended_difficulty`
  (deterministic step up/hold/down, clamped 1-5) stored per skill; study plan ranks skills
  weakest-first and seeds `starting_difficulty`. The concrete ±1 move is the ladder's
  prerequisite step via new `content.prerequisite_for` (in-process, no Postgres table),
  partly retiring the rule-6 carry-over (D-030).
- **Video stub catalog (§5.11.6).** New `video_catalog.py` — deterministic skill→approved
  Khan Academy video, no network, §5.11.6 fallback message when absent; wired into
  `intervention_choice`'s video branch, response gained `video_title/url/source` (D-031).
- **Bug fixed in-flight:** `_route_after_submit_answer` sent *any* incorrect study-phase
  answer to `intervention_choice`, but an incorrect *final pre-exam* answer transitions to
  "study" with no study attempt → assertion crash. Now also requires `last_study_attempt_id
  is not None`. Regression-tested; pre-S10 tests missed it (they answered the last pre-exam
  item correctly).
- Tests (+25, 132→157): `test_study_outcomes.py` (labels, ladder, independence, video
  catalog found/fallback, support-dependency, outcome-aware grading — all deterministic);
  `test_mastery_bootstrap.py` (recommended_difficulty cases); `test_content.py`
  (prerequisite_for); `test_learning_flow.py` reworked for one-at-a-time serving + new tests
  for the full ladder→unresolved+tutor-flag+prerequisite, the last-wrong-pre-exam regression,
  and **Phase 10's "identical inputs reproduce identical routing and scores"** (two runs →
  equal routing + gain); `test_repositories.py` updated for the new columns + `set_outcome`.
- Verification: `make lint && make typecheck && make test` — 157 passed (+25), 0 lint/type
  errors, stable across repeated runs. Live dev-server smoke (uvicorn + httpx): pre-exam →
  study serves one item at a time → wrong study answer pauses → `respond video` returns the
  stub catalog's Khan Academy video (title/url/source) → next remediation item served. Phase
  10 (§6.11) completion criterion holds: scores and routing are reproducible for identical
  inputs (deterministic evaluator test + pure-function determinism tests).
- Carry-over: see "Current status" above.
- New decisions: D-028, D-029, D-030, D-031.

### S9 — LLM question-generation and review pipeline (2026-07-16) ✅
- `packages/shared/.../bedrock.py`: generalized `BedrockGateway.generate_structured`'s
  `payload` param from the hardcoded `BedrockTutorPayload` (S8's only caller) to base
  `BaseModel`, plus 5 new task-specific `extra="forbid"` payloads and their responses
  (`GeneratorPayload`/`GeneratedTemplateResponse`, `SolverPayload`/`SolverResponse`, and
  Difficulty/Ambiguity/Alignment review pairs). Reused the existing 2-slot `BedrockTask`
  enum per §5.25.2's own table — no new registry entries (D-026).
- `packages/adapters/.../bedrock/`: `ResilientBedrockGateway`/`MockBedrockProvider` updated
  for the generic payload; mock gained 5 schema-aware branches so the pipeline runs
  end-to-end on the dev default provider.
- `packages/curriculum/.../ai_pipeline.py` (new): the §5.8.3 pipeline — Generator →
  Solver A/B → Difficulty/Ambiguity/Alignment reviewers → §5.8.5 executable validation →
  DB dedup → persist as `validation_status="pending"` (never auto-approved). Generator
  picks a shape *key* from a difficulty-scoped allowlist and never invents solve logic or
  parameter bounds (extends D-015 into the LLM pipeline, D-026); every model-proposed
  string is re-validated against the registry; solver agreement is checked as option
  letter vs. the deterministic `correct_option`. New `settings.py` (standalone Bedrock
  config, no `learning_api` import) and `pipeline_cli.py` + `make question-gen-run`.
- `packages/db/.../repositories/questions.py`: `activate_template` (promotes only a
  `pending` template to `approved`, refuses `rejected`), `set_active_status` (quarantine),
  `rendered_question_exists` (dedup). `repositories/reports.py`: `get_report` for the
  idempotent-per-student check.
- `apps/learning-api/.../services/question_reports.py` + `routers/questions.py` (new):
  `POST /learning/questions/{question_variant_id}/reports` — student-only, reporter id from
  `claims.sub` (never the request body), idempotent per student, 5-distinct-user quarantine
  flipping `active_status="quarantined"` only, leaving `validation_status`/rows intact
  (D-027). Wired into `main.py`.
- Tests (+28): `packages/curriculum/tests/test_ai_pipeline.py` (scripted-gateway pipeline —
  passing candidate → pending → activate → active/delivered, and reject paths for solver
  disagreement, each reviewer flag, far-off difficulty, unregistered shape key, dedup, plus
  `activate_template` refusing a non-pending template and `PipelineConfigError` for an
  unconfigured topic); `apps/learning-api/tests/test_question_reports.py` (single report,
  same-user-counts-once, 5th-reporter quarantine + delivery stops + history kept + 6th
  idempotent, non-student 403, unknown-variant 404, bad-type 400 — dedicated throwaway
  template with teardown, never quarantines real curriculum); `packages/shared/tests/
  test_generation_payload_schemas.py` (all 5 payloads `extra="forbid"`, solver never told
  the answer); `test_bedrock_gateway.py` extended (mock produces valid output for every
  generation response type); `test_tutor_service.py`'s `_FakeGateway` widened for the
  generalized payload.
- Verification: `make lint && make typecheck && make test` — 132 passed (+28), 0 lint/type
  errors, stable across repeated runs. Ran `make question-gen-run` against the mock provider
  + live Postgres: solver-agreement gate correctly rejected candidates the mock can't verify,
  one landed `pending`, cost accounting logged (0.99¢); confirmed via direct query the
  pending template is NOT returned by `get_active_questions` (proving "nothing reaches active
  without passing every check"), then cleaned up the verification rows. Both Phase 5 §6.6
  second-half "Done when" criteria hold: nothing reaches `active` without passing every
  automated check; quarantine stops delivery without deleting history.
- Carry-over: see "Current status" above.
- New decisions: D-026, D-027.

### S8 — Bedrock Gateway, Tutor Agent, structured outputs (2026-07-16) ✅
- `packages/shared/.../bedrock.py`: `BedrockGateway` Protocol (`generate_structured`
  only — D-022), `BedrockTask` enum (§5.25.2's task table, only `TUTOR` wired to a real
  model), `TutorContext` (§5.11.4), `BedrockTutorPayload` (§5.30.1's exact
  minimum-necessary field list, `extra="forbid"` — D-023), `HintResponse`/
  `SolutionResponse`/`SolutionStep` (§5.11.4-§5.11.5), and the gateway's typed
  exceptions (`BedrockTimeoutError`/`StructuredOutputError`/`CostBudgetExceededError`/
  `CircuitOpenError`, all carrying `cost_cents` for real-but-failed spend).
- `packages/adapters/.../bedrock/`: `ResilientBedrockGateway` (timeout, bounded
  retry+backoff, a hard max-output-tokens ceiling, per-session cost budget, an
  in-memory circuit breaker, and one repair retry on structured-output validation
  failure — SPEC §5.25.3's "Invalid → Limited retry → Deterministic fallback" diagram,
  minus the fallback itself, which is a caller concern); `MockBedrockProvider` (default
  in dev/tests, schema-aware for `HintResponse`/`SolutionResponse`); `AnthropicBedrock
  Provider` (real, `anthropic`'s `AnthropicBedrockMantle` client with a forced
  single-tool call for structured output — D-025). New `anthropic[bedrock]` dependency.
- `apps/learning-api/src/learning_api/services/`: `topic_resolver.py` (deterministic
  `TutorContext` builder from `question_variant_id`/`selected_option` — D-024, not an
  LLM classifier); `tutor.py` (`generate_hint`/`generate_solution`, each falling back to
  static, pre-verified content on any `BedrockGatewayError` — SPEC §6.10's "safe
  fallbacks work" — and `generate_solution` additionally cross-checking the model's
  `final_answer` against the question's real correct answer before accepting it, per
  §5.12.2 "verify calculations with tools").
- `graph/state.py`/`graph/nodes.py`: `LearningState` gains `last_intervention` (generated
  content, transient per-turn) and `bedrock_spend_cents` (persisted running total, so the
  per-session cost budget survives a restart); `intervention_choice` now actually
  generates hint/solution content or the §5.11.6 video-catalog-unavailable message,
  closing the gap S7 left open. `routers/sessions.py`'s `RespondResponse` gained a typed
  `intervention` field.
- Tests: `packages/adapters/tests/test_bedrock_gateway.py` (success, malformed-output
  repair-then-fallback, repair-recovers, timeout-after-bounded-retries, circuit-breaker
  opens and short-circuits further calls, cost-budget-exceeded before any provider
  call); `packages/shared/tests/test_bedrock_payload_pii_floor.py` (D-011-style exact
  field-set + denylist check); `apps/learning-api/tests/test_tutor_service.py`
  (hint/solution success and fallback, solution-verification rejects a wrong model
  answer); `test_learning_flow.py`/`test_learning_graph_routes.py` extended for all
  three intervention choices (hint content present, solution `final_answer` always
  equals the real correct answer regardless of which path produced it, video fallback
  message, and `bedrock_spend_cents` > 0 after a real call).
- Verification: `make lint && make typecheck && make test` — 104 passed (16 new), 0
  lint/type errors, stable across 3 repeated runs. Manually curled the live dev server
  through all three intervention choices end-to-end (hint, solution — including the
  verification/fallback path, since the mock provider can't actually solve equations and
  its guess was correctly discarded in favor of the verified answer — and video).
  Confirmed the `bedrock_call` structured log line fires with real cost/token fields when
  the app's log level is raised to INFO (uvicorn's default config doesn't surface app
  INFO logs - a S20 observability concern, not a gap in this session's code). All three
  Phase 9 (§6.10) completion criteria hold: intervention flow returns validated
  hints/solutions, unit tests prove fallback on malformed model output, and cost/token
  accounting is logged per call.
- Carry-over: see "Current status" above.
- New decisions: D-022, D-023, D-024, D-025.

### S7 — Human-in-the-loop interrupts (2026-07-16) ✅
- Replaced S6's exception-based `ChildSelectionRequiredError` placeholder with three
  real LangGraph `interrupt()` pauses (SPEC §5.1.4, §5.16): multi-child parent selection
  (§5.6.1), branch-manager attendance-email approval (§5.6.3-§5.6.4), and the
  hint/solution/video choice on an incorrect study answer (§5.11.3). Every pause is
  checkpointed by the existing `AsyncPostgresSaver` and survives a process restart.
- `apps/learning-api/src/learning_api/graph/`: new nodes `await_child_selection`,
  `resolve_attendance`, `intervention_choice`, wired into `build.py` via conditional
  edges off `select_student`/`submit_answer`. `flow.py`'s study-answer handling split
  into `_record_study_attempt` (grade + write, always runs) and `finish_study_turn` (the
  phase-completion tail), so the misconception attempt is recorded before the pause and
  the completion check runs identically whether the answer was immediately correct or
  resolved later via the interrupt.
- New `EmailTransport`/`FakeEmailTransport` (`packages/shared`, `packages/adapters`) as
  the Gmail MCP stand-in (the real gateway is still S14); new `interrupt_approvals`
  Postgres table + repository (one Alembic migration, round-tripped) as the Phase 8
  (§6.9) "no external action without approval" audit record — written for both approve
  and decline decisions.
- `routers/sessions.py`: every relevant response now carries an optional
  `pending_interrupt` (external-id-only interrupt payload enriched with a live Mongo
  lookup per request — see D-020); new `POST .../attendance-resolution` (the §5.6.3
  acknowledge-vs-ask-manager choice) and generic `POST .../respond` (Pydantic
  discriminated union per interrupt type, resumes via `Command(resume=...)`); a new 409
  guard rejects `/topics`, `/attendance-resolution`, `/answers` while an interrupt is
  still pending, since a fresh (non-`Command`) `ainvoke` would otherwise silently discard
  the paused task.
- Found and fixed two real LangGraph replay bugs in-flight (D-021): a resumed node
  replays every line *before* its `interrupt()` call, so `resolve_attendance` needed its
  pre-interrupt `ctx.attendance_choice` resupplied on resume, not just on the first call;
  and `resolve_student`'s original single-node design never committed
  `user_external_id` before pausing, so `/resume` on a still-paused child-selection
  session had nothing to authenticate against and always 403'd — fixed by splitting
  identity-commit (`resolve_student`) from the pause itself (`await_child_selection`).
- Tests: `test_learning_graph_routes.py` rewritten for interrupt-based child selection
  (pause, correct resume, rejected-unlinked-choice resume) plus new fast/no-DB tests for
  both `resolve_attendance` branches (acknowledge; ask-manager approved/declined, proving
  nothing sends before approval). `test_learning_flow.py` (live DB): the existing
  full-flow test now resolves its deliberate wrong answer via `/respond`; three new
  tests — intervention-choice pause + DB-verified `hint_used`/`video_used` + the 409
  skip-guard, attendance email end-to-end (preview → approve → sent → approval row),
  and restart-mid-child-selection (kill/rebuild `TestClient(app)`, `/resume` re-serves
  the identical pending interrupt, then `/respond` still resolves it).
- Verification: `make lint && make typecheck && make test` — 88 passed (13 new/changed),
  0 lint/type errors, stable across 3 repeated runs. Manually curled the live dev server
  through all three interrupt flows, including killing and restarting the process
  mid-child-selection and confirming `/resume` returned the identical pending interrupt.
  Both Phase 8 (§6.9) "Done when" criteria hold: no external action (the branch-manager
  email) fires without an approval record, and pending interrupts survive restart.
- Carry-over: see "Current status" above.
- New decisions: D-020, D-021.

### S6 — LangGraph workflow and PostgreSQL checkpointing (2026-07-15) ✅
- `apps/learning-api/src/learning_api/graph/`: `LearningState` (§5.5.3 Pydantic model,
  fields limited to what S5/S6 phases actually use — hint/video/interrupt fields deferred
  to S7/S8, not stubbed); a `StateGraph` (`build.py`) with one node per action
  (`select_student`/`select_topic`/`submit_answer`/`resume`), entered via a conditional
  edge keyed on a transient `entry_action` field, each running to `END` in one `ainvoke`
  call per HTTP request (`nodes.py`). Node bodies call the *existing* S5 service functions
  (`flow.py`, `attendance.py`, `assessment_builder.py`) unchanged in logic — `flow.py` was
  adapted to operate on a `SessionLike` Protocol instead of the old `LearningSession` ORM
  row, exactly as its own docstring anticipated.
- Role → child-selection routing (SPEC §5.6.1) as a real graph branch: student self-select,
  parent explicit linked child, parent auto-select when exactly one linked child, parent
  with 2+ children raises `ChildSelectionRequiredError` (candidate ids surfaced, no pause —
  see carry-over above), tutor/branch-manager pass-through.
- `AsyncPostgresSaver` checkpointing (SPEC §5.16), constructed once in `main.py`'s lifespan
  (D-007 pattern) and exposed via `app.state.learning_graph` / `get_graph`; `thread_id =
  learning_session_id`. New `POST /learning/sessions/{id}/resume` reloads the checkpoint
  and re-serves the last turn's pending question/message with no side effects.
- Retired the S5 `LearningSession` Postgres table/model/repository per PROGRESS.md's own
  carry-over note — one Alembic migration (round-tripped: `downgrade -1` / `upgrade head`)
  drops it; domain tables (assessment/study/mastery) remain the official record, checkpoints
  are resume state only (SPEC §5.16's own framing).
- §5.29 failure handling: a MongoDB attendance-lookup failure inside `select_topic` is
  caught and routed to an explicit `error` phase instead of crashing the request.
- Tests: `test_learning_graph_routes.py` (new, fast/no-DB) covers every role-resolution
  branch plus the attendance-failure error branch via `InMemorySaver`; `test_learning_flow.py`
  gained a restart/resume test that exits and re-enters `TestClient(app)` (tearing down and
  rebuilding the `AsyncPostgresSaver` connection against the same Postgres, standing in for a
  process restart) and asserts `/resume` returns the identical pending pre-exam question set.
- Verification: `make lint && make typecheck && make test` — 80 passed (9 new), 0 lint/type
  errors, stable across 5 repeated runs. Manually curled the live dev server: full
  student flow through `/resume` after a real process restart (identical items), parent
  single-child auto-select, and parent multi-child → HTTP 300 with candidate ids. Both
  Phase 7 (§6.8) "Done when" criteria hold.
- Found and fixed one real bug in-flight (not a pre-existing issue): passing a fully
  materialized `LearningState` instance as `ainvoke`'s `input` (done to satisfy pyright)
  silently reset every unset field to its schema default each turn, since LangGraph applies
  "last write wins" merge semantics per dict key, not per Pydantic-instance identity — every
  field on a full instance counts as "touched". Fixed by giving the graph a narrower
  `input_schema` (`EntryInput`, just `session_id`+`entry_action`) instead (D-019).
- Carry-over: see "Current status" above.
- New decisions: D-019.

### S5 — Deterministic learning vertical slice (2026-07-15) ✅
- New `LearningSession` model/repo (`packages/db`) orchestrating the multi-request flow
  (student → topic/attendance → pre-exam → study → post-exam → gain) since no LangGraph state
  exists until S6; new `StudyItem` model fixing the 5-question study plan the same way
  `assessment_items` fixes the pre/post-exam set. One new Alembic migration, reviewed by hand,
  round-tripped (`downgrade -1` / `upgrade head`).
- `apps/learning-api/src/learning_api/services/`: `attendance` (§5.6 gate — non-present
  attendance is treated as an immediately acknowledged absence per §5.6.5, since the "ask the
  branch manager" `interrupt()`+Gmail path is S7 scope), `assessment_builder` (fixed 10-question
  pre-exam and parallel-form post-exam via existing `generate_variant`), `grading` (deterministic
  §5.9.3 grading + idempotent attempt recording via the `Idempotency-Key` header),
  `mastery_bootstrap` (§5.10.1 weighted-score formula, weak-skill threshold D-017),
  `study_plan` (§5.11.2 priority selection — rules 1/2/4/5/7 implemented, rule 6 skipped per the
  existing prerequisite carry-over, rule 3 unneeded), `learning_gain` (§5.13.3 metrics incl.
  `not_applicable_pre_max`), and `flow` (phase-transition orchestration the routes call —
  written so S6 can lift it into LangGraph nodes without a rewrite).
- 4 of the 9 §5.28.1 endpoints (`POST /learning/sessions`, `.../student`, `.../topics`,
  `.../answers`) wired as thin FastAPI routes (`learning_api/routers/sessions.py`);
  `.../interventions`/`.../resume` need S7/S6, `.../stream` needs S11's SSE, and
  `/students/{id}/history|reports` aren't in this session's scope — none stubbed.
- Fixed a latent bug found while wiring this up: `MasteryRepository.upsert_mastery` only ever
  inserted, never updated in place, despite the name — harmless with one call, but wrong once
  mastery is recomputed repeatedly (D-017).
- Tests: repository round-trips extended for the new/changed methods; pure-function unit tests
  for `mastery_bootstrap`; an HTTP integration test (`test_learning_flow.py`) driving one
  present-attendance student through the entire pre-exam → study (incl. one deliberate wrong
  answer, proving it "just advances") → post-exam → learning-gain flow via `TestClient`, plus an
  in-phase idempotent-resubmission check and a separate blocked-attendance-branch test.
- Verification: `make lint && make typecheck && make test` — 72 passed (11 new), 0 lint/type
  errors, stable across repeated runs. Manually curled all 4 endpoints against the live dev
  server for both a present-attendance and an absent-attendance seeded student, confirming both
  Phase 6 (§6.7) completion criteria: the full flow completes via HTTP, and nothing in the path
  calls an LLM.
- Carry-over: none new (see "Current status" above for what's still open).
- New decisions: D-017, D-018.

### S4 — Curriculum taxonomy and hand-authored seed questions (2026-07-15) ✅
- `curriculum/internal_math/` YAML (SPEC §5.7.2 tree): 3 topics (linear_equations [6-7],
  fraction_operations [4-5], place_value [1-2]), 10 skills, prerequisite edges, grade→topic
  candidate mapping. `curriculum/kumon_us_reference/` public-progression-only reference folder
  per §5.7.1 (no worksheet content, `official_affiliation: false`).
- New `packages/curriculum` (`intellichoice_curriculum`) uv workspace member: a template "shape"
  registry (11 equation forms — one-step through distribute/combine-like-terms) where
  `solution_function`/`correct_option_generator`/`distractor_generators` are string keys resolved
  through the registry, never `eval`'d (D-015); deterministic seeded variant generation
  (parameters derived from a chosen integer answer, so every solution is exact); the §5.8.5
  automated validation suite (10 checks); 50 hand-authored `linear_equations` templates (10 per
  difficulty 1–5, D-003's seed-bank scope) built from a 5-skill difficulty ladder.
- Idempotent Postgres loader (`intellichoice_curriculum.loader`, `make curriculum-load`):
  natural-key ids for topics/skills/templates (D-016) so re-runs skip existing rows; refuses to
  insert any template that fails validation.
- Tests: taxonomy shape/reference checks, one unit test per §5.8.5 rule against a deliberately
  broken fixture, all-50-templates-pass-validation, seed-reproducibility, and a real-Postgres
  loader integration test (idempotency + validation-rejection, skip-if-unreachable per D-008/D-013
  style).
- Verification: `make lint && make typecheck && make test` — 61 passed (29 new), 0 lint/type
  errors. Ran `make curriculum-load` against the live local Postgres: 3 topics, 10 skills, 50
  templates, 50 sample variants persisted; re-ran and confirmed idempotent (0 created, 50
  skipped); spot-checked rendered questions/options via `psql`. Both Phase 5 (§6.6) "Done when"
  criteria hold: every loaded template passes §5.8.5; variant generation is seed-reproducible.
- Carry-over: none.
- New decisions: D-014, D-015, D-016.

### S3 — PostgreSQL domain schema and migrations (2026-07-15) ✅
- New `packages/db` (`intellichoice_db`) uv workspace member: 17 SQLAlchemy async models across
  8 domain files (curriculum, questions, assessment, mastery, reports, memory, rag, evaluation).
  Question templates/variants, episodic/semantic memory, chunking, and document versioning use
  SPEC's exact field lists (§5.8.2, §5.15.2–5.15.3, §5.21.2, §5.20.4); assessment sessions/items/
  attempts, blocked sessions, and base study plans match §5.9.2–5.9.3, §5.6.5, §5.11.1, §5.13.3.
  Every table keyed by `*_external_id` only — no PII columns.
- Async Alembic migration environment (`alembic init -t async`) wired to `Base.metadata`, one
  initial revision creating all 17 tables + indexes + the `vector` extension; pgvector `Vector`
  column on `rag_chunks.embedding` (placeholder dim=1536, pending S12's model choice) and a
  `TSVECTOR` `search_vector` column.
- Repository layer: 9 classes covering all 17 tables, including the four SPEC §5.26.1 named
  methods (`get_active_questions`, `get_student_assessment_summary`, `get_weak_skills`,
  `search_document_chunks`) as real parameterized queries — full ranking/scoring logic is
  deferred to S5/S10/S13 by design.
- Tests: a PII schema-purity test (exact-match column-name denylist, so `Topic.name` etc. don't
  false-positive) and one round-trip test per repository (17/17 tables exercised), isolated via
  per-test rollback transactions against the real Compose Postgres, skip-if-unreachable mirroring
  the existing Mongo test pattern.
- `Makefile`: `db-upgrade`, `db-downgrade`, `db-revision`.
- Verification: `make lint && make typecheck && make test` — 32 passed (10 new), 0 lint/type
  errors. `alembic upgrade head` proven reproducible from an empty DB twice (downgrade to base,
  re-upgrade). Both Phase 4 (§6.5) completion criteria hold.
- Carry-over: none.
- New decisions: D-009, D-010, D-011, D-012, D-013.

### S2 — Auth validation and MongoDB Profile Adapter (2026-07-15) ✅
- `packages/shared`: `TokenClaims`/`Role`/`Audience` (SPEC §5.1.2 claim set), `AttendanceStatus`
  and `StudentProfile`/`ParentProfile`/`BranchInfo` DTOs, plus the `TokenVerifier`/`ProfileAdapter`
  Protocols both apps depend on.
- `packages/adapters`: `FakeTokenIssuer` + `JwtTokenVerifier` (dev-only HS256, audience-checked),
  read-only `MongoProfileAdapter` (Motor), idempotent Mongo seed fixtures (2 parents — 1-child
  and 2-child cases — 4 students total incl. one unlinked, 2 branches, present/absent/unknown
  attendance) and a `make seed` script.
- `apps/learning-api`: `get_current_claims` (audience=`learning`), `resolve_target_student`
  (students verified against their own `sub`; parents verified against a live Mongo lookup of
  linked children, never the request), `GET /students/{id}/attendance` wired end-to-end via a
  lifespan-managed Mongo client on `app.state`.
- `apps/chat-api`: `get_current_claims` (audience=`chat`), `GET /me` proving audience separation.
- Verification: `make lint && make typecheck && make test` — 22 passed, 0 lint/type errors.
  Manually curled both live dev servers with `FakeTokenIssuer`-minted tokens: student self-access
  (200), student cross-access (403), parent linked-child access (200, correct absent/unknown +
  §5.4.4 blocked message), parent unlinked-student access (403), wrong-audience token against
  both apps (401). All four Phase 3 (§6.4) completion criteria hold; "no PII in Postgres" holds
  vacuously since no Postgres models exist yet (enforced for real in S3).
- Carry-over: none.
- New decisions: D-006, D-007, D-008.

### S1 — Repo scaffold and local dev environment (2026-07-14) ✅
- uv workspace monorepo: `apps/learning-api`, `apps/chat-api`, `packages/shared`,
  `packages/adapters`, each an independent workspace member (own `pyproject.toml`, src-layout).
- Both FastAPI apps boot with `/healthz` (pydantic-settings config, env-prefixed `LEARNING_`/`CHAT_`).
- `docker-compose.yml` (Postgres 16 + pgvector, Mongo 7) and `.env.example`.
- `Makefile` (`up`, `down`, `test`, `lint`, `typecheck`, `dev-learning`, `dev-chat`) and GitHub
  Actions CI (lint + typecheck + test via `uv sync --all-packages --all-groups`).
- Verification: `make lint && make typecheck && make test` all pass (ruff, pyright, pytest — 2
  passed). Both apps' `/healthz` confirmed live via `uv run uvicorn` + curl. `make up` confirmed
  live once Docker Desktop was started — `docker compose ps` shows both `postgres` and `mongo`
  as `healthy`. All 4 "Done when" conditions hold.
- Carry-over: none.
- New decisions: D-005 (use `httpx2`, not `httpx`, for FastAPI `TestClient` — this starlette
  version deprecates plain `httpx`).

### S0 — Planning setup (2026-07-13) ✅
- Moved full spec to docs/SPEC.md; slimmed CLAUDE.md to working rules + pointers.
- Created ROADMAP.md (24 sessions across 6 milestones), this tracker, DECISIONS.md.
- Added `/start-session` and `/end-session` skills; `git init` done (no commits yet — user commits).
- Decisions recorded: D-001..D-004.

## Entry template (copy for each session)

### S<n> — <title> (<date>) <✅ | ⏸ partial>
- What was built (1–4 bullets)
- Verification: <tests/typecheck/manual runs performed>
- Carry-over: <scope cut and deferred, or "none">
- New decisions: <D-xxx refs, or "none">
