# Audit Findings — Phase 0A (S36–S39)

The findings register for the four audit sessions defined in
[INTEGRATION_PLAN.md §2.3](INTEGRATION_PLAN.md). One row per finding, with reproduction and
evidence, so §2.6's criteria 1 and 2 can be evidenced rather than asserted.

**Severity (§2.4).** P0 authorization bypass / PII leak / data corruption / child-safety
failure / uncontrolled spend — stops the line, fixed immediately with a regression test.
P1 a launch journey broken, fail-open behavior, cost or latency out of bounds — fixed and
re-verified before the gate. P2 degraded UX or quality with a workaround. P3 polish.

**Disposition rule.** Fixes land in Phase 0B (S40–S41), *not* mid-audit — except P0s. Every
finding needs a disposition here; "won't fix" needs a written reason.

**Areas audited with no finding are recorded too**, at the bottom of each session's section.
An audit whose output is only its defects can't be told apart from an audit that stopped
early, and traceability (criterion 1) needs the negative results as much as the positive
ones.

---

## Index

| ID | Area | Severity | Status | Summary |
|---|---|---|---|---|
| **AUD-L-02** | **Money** | **P0** | **Fixed in S36** | `POST /students/{id}/report` had no cost ceiling of any kind — it passed `session_spend_cents=0.0`, so the gateway's budget check could never fire, and one authenticated caller could drive unbounded Bedrock spend |
| **AUD-L-04** | **Minors / PII** | **P1** | Open — before the gate | D-072 accepted "names in free text may survive" *because* that text lived in a 90-day-purged table; S25 then derived permanent, never-purged `semantic_memory.fact_text` from it, and those facts reach parent-visible reports |
| AUD-L-05 | Minors / PII | P2 | Open — Phase 0B | `MemoryConsolidationPayload` carries free text but was never added to the PII-floor allowlist test, contrary to D-072's own stated rule |
| AUD-L-06 | Minors | P3 | Open — Phase 0B | `tutor.generate_hint` is dead code that omits the leak check its live sibling applies — a trap for whoever wires it up |
| AUD-L-03 | Money | P2 | Open — Phase 0B | `pre_intro` stage-narrative spend is never folded back into the session total, so the per-session ceiling is permanently one call short |
| **AUD-L-07** | **Authorization** | **P1** | Open — before the gate | D-086's known tutor/branch_manager scope gap now reaches further than when it was written: it covers the S28 dashboard and report surface, so a tutor token can read any student's data and generate reports about them |
| AUD-L-09 | Correctness | P2 | Open — Phase 0B | Numeric grounding verifies a number's *provenance*, not its *attribution*, so a report can invert a real result ("fell from 6 to 4") and still pass |
| AUD-L-08 | Correctness | P3 | Open — Phase 0B | `normalized_gain` has no upper bound and derives its denominator from the pre *attempt count*; unreachable today only because the post form is built one-for-one from the pre form |
| AUD-L-01 | Auth surface | P3 | Open — Phase 0B | A gated-off `/dev/token` still discloses that it exists, and the S35 deploy gate's stated rationale is wrong about why it 404s |

---

## S36 — AUD-L (learning product correctness)

### AUD-L-02 — `POST /students/{id}/report` had no cost ceiling at all (P0, fixed)

- **Severity:** P0 — §2.4 lists uncontrolled spend explicitly. Stopped the line and was
  fixed in-session with regression tests, per the audit's own rules.
- **Area:** money / Bedrock cost ceilings
- **Found by:** tracing every `session_spend_cents` argument to
  `BedrockGateway.generate_structured` back to its caller, rather than reading the gateway
  and concluding the ceiling exists
- **Status:** **fixed in S36**, live re-verification pending the Phase 1 deploy

**What.** The gateway is stateless about spend: it enforces the per-session budget against a
`session_spend_cents` value its *caller* supplies. Two callers supplied nothing, relying on a
`= 0.0` default — and one of them,
[routers/students.py](../apps/learning-api/src/learning_api/routers/students.py)'s
`POST /{student_id}/report`, is an on-demand endpoint with **no idempotency key**: one fresh
`student_reports` row and one fresh Bedrock call per click. So on every single call the check
evaluated `0.0 + worst_case > 50.0`, which is false, and the ceiling never applied. Not a
weakened ceiling — an absent one.

The only remaining limit was the global per-IP rate limiter, raised to 6,000 requests/60s in
S34 for a completely unrelated reason (real branches share an egress IP). A request cap is not
a spend cap.

**Reproduction.** Authenticate as any role permitted to reach a student's report (student-self,
linked parent, tutor, branch_manager) and repeat `POST /learning/students/{id}/report`. Every
request performs a real Bedrock `PARENT_REPORT` call. No counter, ledger, or ceiling is
consulted, and the response is not cached or deduplicated.

**Evidence.** Cost arithmetic from the gateway's own rate table, for the model actually
deployed (`us.anthropic.claude-haiku-4-5-20251001-v1:0`, 0.1/0.5 cents per 1K in/out) and the
report task's real `_MAX_OUTPUT_TOKENS = 500`: roughly **0.45 cents per call** (0.2 in + 0.25
out), doubling if the structured-output repair retry fires. At the per-IP limiter's ceiling
that is ~$27/minute, ~$1,600/hour, from one IP holding one valid token. Even at a rate a plain
browser script achieves without effort, it is hundreds of dollars a month of pure waste. The
only backstop was the AWS Budget alarm — a lagging notification, not an enforcement mechanism.

The bug class is already recognized in this codebase: S24 built
`tutor_chat.DAILY_COST_CEILING_CENTS` precisely because chat is a surface where one student can
trigger many separate LLM calls in a day. Report generation is the same shape and never got the
same control.

**Fix (in this session).** Mirrors the chat precedent rather than inventing a mechanism:

1. `StudentReportRepository.get_spend_cents_since` — sums `cost_cents` over a 24h window. No
   migration: `student_reports` already stores `cost_cents` and `created_at`.
2. `report.DAILY_REPORT_COST_CEILING_CENTS = 50.0`, checked *before* the Bedrock call. On
   exceed the endpoint degrades to the deterministic facts-only template that a gateway failure
   or a failed grounding check already produces — the caller still gets their real verified
   numbers, just without LLM prose. That reuses SPEC §5.25.3/§5.27's deterministic-fallback
   rule instead of erroring.
3. `session_spend_cents` is now **required** on both `generate_student_report` and
   `generate_stage_narrative`. A cost parameter with a permissive default *is* a fail-open
   default — the same class as D-096's `ecr:DescribeImages` check and D-085's environment-string
   gate. Removing the default immediately surfaced all five call sites that had been relying on
   it, which is the point.

**Regression tests** (3): the ceiling short-circuits *before* the gateway is called (an
`_ExplodingGateway` fails the test if Bedrock is reached at all); a call just below the
threshold still generates normally (a ceiling that blocks legitimate use is a different bug, so
the threshold is pinned from both sides); and the spend query counts only this student's reports
inside the window, so neither another student's spend nor last week's can deny a legitimate
report.

**Residual, deliberately not fixed here.** The endpoint is still not idempotent — the ceiling
bounds the *cost* of hammering it, not the hammering. Per-caller request-rate limiting on
LLM-calling endpoints specifically (as opposed to the global per-IP cap) is a Phase 0B item and
belongs with the same work for chat.

### AUD-L-04 — An accepted PII risk lost its mitigation when S25 made the text permanent (P1)

- **Severity:** P1 — a data-protection promise about minors that the code no longer keeps.
  Not P0: it needs a student to type a name, the model to copy it into a fact, and that fact to
  pass the pattern screen, and there are no real student users yet. But it must be closed before
  the §2.6 gate, not in the backlog.
- **Area:** minors / PII floor / retention
- **Found by:** following `relevant_learning_fact` — an *allowlisted* field on the tutoring
  payloads — backwards to where its text is authored, instead of stopping at the allowlist
- **Status:** open, before the gate

**What.** D-072 (S24) explicitly accepted that name detection in free text is unreliable and is
not attempted: `redact_free_text` removes emails, URLs and phone numbers only. So a student
typing "my mom Sarah said to skip this" leaves a name in `tutor_chat_messages.
redacted_student_message`. That was accepted as a bounded risk, and the boundary was real:
**that table is the only one in this codebase with a retention job** (`purge_older_than`,
`make chat-purge`, 90 days, SPEC §15).

S25 (D-074) then built memory consolidation on top of that same text, and the boundary quietly
disappeared:

1. `consolidation.py:185` reads `redacted_student_message` and folds it into
   `MemoryEventSummary.summary`.
2. That goes to Bedrock, which authors `MemoryFactCandidate.fact_text`.
3. `fact_text` is screened with `contains_pii_pattern` — the *same* email/URL/phone patterns,
   which by D-072's own admission do not catch names — and stored in `semantic_memory`.
4. `semantic_memory` has **no purge, no retention job, and no `make` target.** Verified: grepping
   `purge_older_than` across every repository in `packages/db` returns exactly one hit,
   `tutor_chat.py`.
5. `fact_text` then flows outward — into `relevant_learning_fact` on `BedrockTutorPayload` and
   `HintPersonalizationPayload`, and into `ReportInterpretationPayload.relevant_learning_facts`,
   which is rendered in **parent-visible reports**.

So a name a child typed can outlive the 90-day window indefinitely, in Postgres, and surface to a
different human than the one who typed it. Neither D-072 nor D-074 records this: D-072 reasoned
about a purged table, and D-074 reasoned about consolidation quality.

**Reproduction (structural, and that is the honest description).** The chain above is verifiable
by reading it, and every link is unconditional code. What cannot be reproduced deterministically
is step 2 — whether the model copies a name into a fact — because that depends on real model
behavior, and the dev fake does not attempt it. I did not manufacture a "leak" with a scripted
fake gateway, because that would only prove the fake does what I told it to; it would be evidence
about my test, not about the system.

**Evidence.** `consolidation.py:185` and `:250`/`:324` (the screen, using the same insufficient
pattern set); the single-hit `purge_older_than` grep; `report.py`'s `relevant_learning_facts`
reaching the parent audience in `build_report_facts`.

**Disposition — needs a decision, not just a fix.** Three options, and they are not equivalent:
add a retention job for `semantic_memory` (restores D-072's original boundary, cheapest, and
`stage_transitions`/`student_reports` need one anyway per the standing carry-over); stop feeding
raw chat text into consolidation and pass only the structured event fields (removes the risk at
the source, costs consolidation quality that D-074 deliberately bought); or accept and document
it explicitly, which at minimum requires saying so in the privacy notice the §6.1 track is
drafting, since "we delete chat after 90 days" would otherwise be misleading. Recommendation:
the retention job, plus a note in the §6.1 legal text — it restores the boundary that was
already reasoned about and approved rather than re-opening a settled quality trade-off.

### AUD-L-05 — `MemoryConsolidationPayload` was never added to the PII-floor allowlist (P2)

- **Severity:** P2 — no live leak today; a missing guard rail, not a broken one
- **Area:** minors / PII floor
- **Status:** open, Phase 0B

**What.** D-072's own "How to apply" clause states the rule: *"any future free-text-accepting
Bedrock task must run `redact_free_text` (or a stricter successor) before the wire and before
storage, **and its payload must appear in `test_bedrock_payload_pii_floor.py`'s allowlist set**."*
`MemoryConsolidationPayload` is a free-text-accepting payload (`MemoryEventSummary.summary`,
`MemoryExistingFact.fact_text`) added one session later, and it is not in that test.

**Reproduction / evidence.** The test covers exactly six payload types — `BedrockTutorPayload`,
`HintPersonalizationPayload`, `LearningChatIntentPayload`, `TutorChatPayload`,
`StageNarrativePayload`, `ReportInterpretationPayload` — confirmed by extracting every
`*Payload` symbol referenced in the file. `MemoryConsolidationPayload` is absent.

**Why it matters despite P2.** The payload's *current* fields are clean, so nothing leaks now.
The value of that test is that it fails when someone adds a field — it is the mechanism by which
the PII floor survives future sessions. An uncovered payload silently opts out of that
protection, and this one is the payload closest to real student free text.

**Disposition.** Phase 0B: add the allowlist case. Also worth checking the other uncovered
payloads in the same pass (`VideoClassificationPayload`, `LlmJudgePayload`, and the
curriculum-pipeline payloads); the chat-app payloads belong to AUD-C/S37.

### AUD-L-06 — `tutor.generate_hint` is unreachable and omits the leak check its sibling applies (P3)

- **Severity:** P3
- **Area:** minors / tutoring guardrails
- **Status:** open, Phase 0B

**What.** `tutor.generate_hint` performs a real Bedrock `TUTOR` call and returns
`result.value` directly — no `leak_phrase_present`, no `answer_text_leaked`, and it ignores
`HintResponse.answer_revealed` even though the field exists. Its live sibling
`generate_personalized_hint` applies all three checks plus a ladder-monotonicity check, and
`tutor_chat.generate_chat_reply` applies the leak checks too. `generate_solution` correctly has
none (revealing the answer is its job) but does cross-check the model's `final_answer` against
the real one.

**Reproduction / evidence.** `generate_hint` has **no caller in application code**: grepping the
whole repository finds it referenced only from `apps/learning-api/tests/test_tutor_service.py`
and one comment in `packages/evals`. The live hint path is `graph/nodes.py:788` →
`generate_personalized_hint`. So this is dead code, and there is no reachable defect today.

**Why log it at all.** It reads exactly like a supported entry point, it is covered by three
tests that assert it works, and it is the only LLM-output path in the learning app that trusts
the model unverified. A future session adding a "plain hint, no personalization" flow would
reasonably call it and inherit an unguarded path. Delete it, or add the checks — either resolves
it; leaving it as-is is the only bad option.

### AUD-L-03 — `pre_intro` spend is never folded back into the session total (P2)

- **Severity:** P2 — bounded, but it means the per-session ceiling is structurally wrong
- **Area:** money / cost accounting
- **Status:** open, Phase 0B

**What.** `routers/stream.py`'s `pre_intro` narrative fires on SSE connect, outside the graph.
S26/D-075 deliberately records its cost on the `stage_transitions` row rather than in the
checkpoint's `bedrock_spend_cents`, because that path never takes a graph turn. That choice was
recorded as an *accounting* decision; its consequence for *enforcement* was not: every later
call in that session evaluates the ceiling against a total that is permanently missing this
call's cost. The same is true of chat's out-of-band spend (S24/D-073 records that one).

**Reproduction / evidence.** Structural, and visible in the code: `_maybe_fire_pre_intro`
returns only `(narrative_text, evidence_summary)` — there is no cost in its return type, so no
caller could fold it in. Bounded by the stage-narrative idempotency check (one real Bedrock call
per session per stage), so the undercount is one call's worth per session, not unbounded.

**Fixed in this session only in part:** the call now passes the checkpoint's real running total
instead of the 0.0 default (as part of AUD-L-02's fix), so the ceiling at least applies. The
write-back is the remaining half and is Phase 0B work — it needs a cost channel out of the SSE
path and a decision about whether out-of-band spend belongs in the checkpoint at all, which is
exactly what D-073 and D-075 each declined to settle.

### AUD-L-07 — D-086's authorization gap has grown since it was recorded (P1)

- **Severity:** P1. Already known and already launch-blocking (D-086, S33); this finding is the
  *scope update*, not the discovery.
- **Area:** authorization
- **Status:** open, before the gate — same disposition D-086 already has

**What.** `authorization.resolve_target_student` verifies students against their own `sub` and
parents against a live linked-children lookup, then returns `requested_student_id` unchecked for
tutor and branch_manager. D-086 recorded this in S33. What is new is the *reach*: S28 added the
dashboard and report surface after D-086 was written, so the unchecked path now includes
`GET /students/{id}/dashboard`, `POST /students/{id}/report`, and `GET /students/{id}/reports` —
meaning a tutor token can read any student's mastery, accuracy and usage data and generate
LLM-written reports about a student they have no relationship to. D-086's text reasons about
session history, which was the surface that existed at the time.

Also stale: the code comment says the check "land[s] with Q&A authorization (Session 13)". S13
shipped without it. A pointer to work that already happened without doing the thing is worse than
no pointer.

**Reproduction.** Mint a tutor token for any `sub`, call
`GET /learning/students/<any-student-id>/dashboard`. No relationship is required or checked. Not
independently exploitable today — obtaining a tutor token requires the `/dev/token` path, which is
secret-gated as of this session — but that is a property of the current deployment, not of the
authorization code.

**Evidence.** [authorization.py:34-36](../apps/learning-api/src/learning_api/authorization.py#L34-L36)
is the whole check for these two roles. All 17 learning routes were enumerated and traced: every
route that names a student or a session does call `resolve_target_student`, so the gap is
uniformly *this function's* gap, not a per-route omission — which is the good news, since one fix
closes all of them.

**Disposition.** Unchanged from D-086: blocked on a tutor-assignment / branch_manager-branch data
model that `ProfileAdapter` does not have yet, which S42's discovery and S43's `IcProfileAdapter`
are what unblock. This finding adds two things to that record: the dashboard/report surface is in
scope, and the formal disposition is already scheduled for S46 (§5's "D-086 disposition
recorded"). Fix the stale comment whenever the file is next touched.

### AUD-L-09 — Numeric grounding checks provenance, not attribution (P2)

- **Severity:** P2 — degraded quality in parent-facing text, with a workaround (the facts-only
  template always shows the correct numbers)
- **Area:** correctness / stage-narrative and report grounding
- **Status:** open, Phase 0B

**What.** `numeric_grounding.is_grounded` returns False only if the narrative contains a number
that appears nowhere in the evidence dict. It does not check what the number is *claimed to mean*.
So for a student who improved from 4 to 6, the sentence "your score fell from 6 to 4" is fully
grounded — both numbers are in the evidence — and is accepted and shown. Same for swapped skills,
inverted gains, or a pre-exam figure presented as a post-exam one.

**Reproduction / evidence.** Structural, and visible in the nine-line function: it iterates
`extract_numbers(narrative_text)` and asks only whether each has *some* match anywhere in the
flattened evidence values. Direction, pairing, and field identity are never consulted.

**Why it matters more than P2 suggests, and why it is still P2.** This is the last check between
an LLM and a parent reading about their child's progress, and the product's whole framing is
growth-oriented language (SPEC §5.10.3) — a narrative that inverts a real gain is worse than no
narrative. But it is genuinely bounded: the deterministic fallback always contains the correct
figures, the numbers themselves can never be invented, and both parent-facing surfaces show
`verified_facts` alongside the prose, so a wrong claim sits next to the right data.

**Disposition.** Phase 0B, and the honest framing is that a *complete* fix needs semantic
verification, which is a different and much larger project. Two cheap partial mitigations worth
considering instead: check directional claims specifically (if the evidence has a positive gain,
reject narrative text pairing those two numbers in decreasing order), and narrow the evidence dict
per stage so fewer unrelated numbers are available to be misattributed in the first place. Neither
is complete; both remove the most damaging class.

### AUD-L-08 — `normalized_gain` is unbounded, and its denominator comes from the attempt count (P3)

- **Severity:** P3 — **not reachable today.** Recorded because it is a guard that does not exist
  in a number shown to parents, and the thing preventing it is incidental rather than intentional.
- **Area:** correctness / learning-gain math (SPEC §5.13.3)
- **Status:** open, Phase 0B

**What.** `learning_gain.compute_learning_gain` sets `max_score = float(len(pre_graded)) or 1.0` —
the *count of resolved pre attempts*, not the assessment's declared item count — and then computes
SPEC §5.13.3's `(post - pre) / (max - pre)` with no clamp on the result. If the post form ever
carries more items than the pre form, or pre attempts are ever missing while post attempts exist,
the quotient exceeds 1.0 and is stored and displayed as a normalized gain. The `or 1.0` guard
protects against ZeroDivisionError but converts a zero-pre-attempt case into a denominator of 1,
which is worse than an error: it produces a plausible-looking number.

**Reproduction (empirical).** Called the real function with a fake question repo:

| Case | `raw_gain` | `normalized_gain` | `status` |
|---|---|---|---|
| normal 10-item, pre 4 → post 6 | 2.00 | 0.333 | `None` |
| post form longer than pre (12 vs 10) | 8.00 | **1.333** | `None` |
| no pre attempts, post 6 correct | 6.00 | **6.0** | `None` |
| pre 1 item wrong, post 10 correct | 10.00 | **10.0** | `None` |

Note `status=None` in every row — a 1000% gain is not flagged as anomalous, it is reported as a
valid normalized gain. It would then pass the report's numeric-grounding check, because the number
*is* in the evidence; grounding verifies provenance, not plausibility.

**Why it is nevertheless P3.** I traced whether any of those inputs can occur:
`assessment_builder.build_post_exam` builds the post form by iterating `pre_items` and generating
one fresh variant per pre item, so the post length **always** equals the pre length; and
`build_pre_exam` is a fixed 5 difficulties × 2 questions with a hard `AssessmentBuildError` if any
difficulty lacks approved templates, so a zero-item pre exam cannot be created either. S22's
finalize grades every unanswered item incorrect, so the attempt count matches the item count. The
bad inputs are unreachable through the real flow.

**Why it is still worth fixing.** Nothing *states* that invariant where the arithmetic lives, and
nothing tests it. The protection is a property of a different module's loop shape. An adaptive or
variable-length post form — a plausible future change, and the kind of thing SPEC §5.13.2's
"parallel form" language does not forbid — would silently start producing >100% gains in
parent-facing reports, with no error and no flag. A one-line clamp plus a comment naming the
invariant costs nothing and converts a latent correctness bug into an impossible one.

### AUD-L-01 — A gated-off `/dev/token` discloses its own existence; the S35 gate's rationale is incorrect

- **Severity:** P3 (information disclosure only — no token can be minted)
- **Area:** auth surface / deploy-time security gate
- **Found by:** reading [.github/workflows/deploy-staging.yml](../.github/workflows/deploy-staging.yml)'s
  gate comment while extending it for S36/D-097, then probing the claim instead of trusting it
- **Status:** open, Phase 0B

**What.** The gate comment asserts: *"with the endpoint gated off, the route is never
registered on the app at all."* That is not how the code works. `@app.post("/dev/token")` is
registered unconditionally at module import; the 404 is raised from *inside* the handler after
FastAPI has already matched the route and validated the request body. So request shapes that
fail before the handler body runs return something other than 404, and reveal that the path
exists.

**Reproduction.** Both apps, settings in staging's real posture
(`environment="staging"`, `dev_token_endpoint_enabled=False`, no shared secret):

| Request | Actual | A genuinely absent route |
|---|---|---|
| `POST /dev/token` valid body | 404 | 404 |
| `POST /dev/token` `{"role": "not-a-role"}` | **422** | 404 |
| `POST /dev/token` `{}` | **422** | 404 |
| `GET /dev/token` | **405** | 404 |

**Evidence.** Probed directly against both apps' real ASGI app via `TestClient` with settings
monkeypatched to staging's posture; the table above is that run's output. `POST /dev/nonexistent`
returns 404 in the same run, which is the control that makes 422/405 a disclosure rather than
FastAPI's normal behavior for any unknown path.

**Why it matters.** Two distinct consequences, one small and one worth more than its severity:

1. The disclosure itself is minor. No token is issued, and an attacker learning that
   `/dev/token` exists on a FastAPI service learns very little — the endpoint's name is in a
   public-shaped codebase pattern anyway.
2. The gate is *load-bearing security infrastructure written in response to a P0*, and its
   stated reason for trusting a 404 is false. It happens to still work, because it probes with
   a valid body, which is exactly the shape that does reach the handler's gate. That is luck
   rather than design: nothing recorded anywhere says the probe body must stay valid for the
   gate to mean anything, so a later well-intentioned edit ("send an empty body, we only care
   about the status code") would silently turn the gate into decoration that always fails.
   This is the same class as D-096's `ecr:DescribeImages` finding — a check that appears to
   assert something stronger than it does.

**Disposition.** Phase 0B. Two changes, neither urgent: correct the comment to describe the
real mechanism and state that the probe body must remain valid; and register the route
conditionally rather than gating inside the handler, so a disabled endpoint is genuinely
absent for every request shape. The second is the real fix but touches how both apps'
`Settings` are read at import time, and the existing tests monkeypatch `get_settings` on the
module *after* import — so it needs a small test-approach change, which is Phase 0B work, not
mid-audit work.

### Areas audited with no finding

**Money — no Bedrock call bypasses the gateway.** Grepped every `raw_generate` / `raw_embed` /
`invoke_model` / `boto3` reference across `apps/` and `packages/`: the only hits outside
`adapters/bedrock/` are two comments. Every paid call in both apps really does go through
`ResilientBedrockGateway`, so the timeout, bounded retry, `_HARD_MAX_OUTPUT_TOKENS = 4000` cap,
circuit breaker, and cost accounting are unavoidable rather than conventional. This is the
premise AUD-L-02 depends on, so it was checked rather than assumed.

**Money — every other `session_spend_cents` call site passes a real accumulated value.** All 20+
call sites traced. The graph nodes thread `bedrock_spend_cents` (persisted in the checkpoint, so
it survives a process restart) and correctly pass `bedrock_spend_cents + cost` where several
calls happen inside one node; `video_catalog`, `tutor`, `tutor_chat`, and chat's own nodes all
receive a real total. The two defaults were the only two gaps, and both are now closed or logged.

**Money — bounded-by-design behaviors, noted but not findings.** The pre-flight budget check
estimates input at a hardcoded 2,000 tokens, so a call whose real payload is larger can overshoot
the ceiling by one call's worth; and a `generate_structured` call can make up to four provider
calls (three attempts plus one repair) while the budget is checked only once, at entry. Both are
bounded overshoots of a ceiling rather than absent ceilings, and the circuit breaker limits
sustained failure spend (verified with a real concurrency test in S34). Recording them so a
future session doesn't have to re-derive that they were considered.

**Money — no account-level enforcement exists**, only the AWS Budget *alarm*. This is
infrastructure rather than learning-product code, so it belongs to S39/AUD-F's operations audit
(§2.6 criterion 8 already requires proving alarms reach a human); noted here as a cross-reference
so it is not lost between the two sessions.

**Authorization — every learning route enforces the check; the coverage is uniform.** All 17
routes across `questions.py`, `sessions.py`, `stream.py` and `students.py` were enumerated and
each traced to its authorization call. Student-scoped routes call `resolve_target_student` with
the path's `student_id`; session-scoped routes call it with the *checkpoint's*
`student_external_id` rather than anything client-supplied, which is the right source. The four
`exam/items/...` routes share one helper, so they cannot drift apart. `POST /sessions` (create)
deliberately has no student yet and says so (`del claims  # authentication only`). No route was
found missing a check — the only authorization defect is AUD-L-07, which lives in the shared
function, not in any route.

**Authorization — the SSE `?token=` path verifies audience and ownership.** `stream.py` verifies
the token against `Audience.LEARNING` explicitly (a chat-audience token is rejected), then applies
`resolve_target_student`, and for a session that has no student selected yet falls back to
comparing `claims.sub` against the checkpoint's `user_external_id` — so a brand-new session cannot
be attached to by a different caller either. `/resume` has the same two-branch check. Deeper
SSE/thread-hijack work is AUD-X/S38's, but these two properties hold.

**Data integrity — the D-071 checkpoint-overwrite bug class does not recur in the learning app.**
Swept every explicit `": None"` channel write in both graphs. The learning app has exactly two,
and both are correct *because* they erase: `"last_items": None` when attendance blocks a start (a
stale question batch must not sit beside a blocked message) and `"last_message": None` when
entering the pre-exam with fresh items. Neither is the S23 shape, which was writing `None` to mean
"nothing new to report". The chat app has ~40, including 12 writes of `"access_hint": None` — not
audited here (AUD-C/S37 owns it) but flagged as a cross-reference, since `access_hint` is the field
in the known S22.5 blank-turn bug and that combination deserves a deliberate look.

**Data integrity — finalize is genuinely idempotent, at both layers.** `flow.finalize_exam`
returns `None` when the target `AssessmentSession` already has `finalized_at`, and the node then
returns `{}` — which under LangGraph's default merge preserves every channel, the same
"omit to preserve" convention D-071 established. The route additionally allows the `study` and
`completed` phases through on purpose, so a retry arriving after the phase has visibly moved still
re-serves the same result instead of 409ing, and it 409s explicitly when no student is selected
rather than relying on a downstream failure.

**Test signal — the known RNG flake is characterized more precisely than before, and it matters
for the gate.** `test_hint_reflects_the_students_actual_wrong_option` failed once in a full run and
once standalone this session, then passed three consecutive standalone runs and two full runs.
PROGRESS.md's prior sessions describe confirming it "via an immediate clean standalone rerun" — but
it reproduces standalone too (roughly 1 in 4 attempts here), so it is **purely unseeded-RNG driven,
not test-order dependent**. That is good news for whoever fixes it: seeding the RNG in the fixture
is sufficient, and no ordering investigation is needed. It is bad news for §2.6 criterion 4, which
requires three consecutive green full runs — at this failure rate that is a coin flip, so the
criterion would be met by luck rather than by signal. Fix the seed before attempting the gate.

**Question bank — what is actually `approved` and deliverable today, measured.** Queried the real
dev Postgres rather than reasoning from the seed scripts: **1 topic, 5 skills, 50 templates**, all
`validation_status=approved` and `active_status=active`, exactly 10 templates at each difficulty
1–5. `build_pre_exam` needs 2 per difficulty, so exam construction is satisfiable with 5× headroom
— the bank is *sufficient*, which is worth stating separately from being *broad*. It is not broad:
one topic, and **exactly one skill per difficulty level**, so skill and difficulty are perfectly
collinear in this data. Any "skill-level gain" is also a difficulty-level gain, and no test using
this bank can distinguish the two. That is the known A6/D-060 content gap (which gates the pilot,
not the build), now quantified.

**Two known carry-overs re-measured, both materially worse than last recorded** — numbers handed
to Phase 0B rather than left as "worsening": `question_variants` is at **42,023 rows across 50
templates**, with a worst single template at **1,559** (S23 recorded 610 on one template, so ~2.5×
growth in one session's worth of elapsed work); the `checkpoints` table is at **264,475 rows**
(S34 recorded 249,250). Both confirm the accumulation is ongoing rather than a one-off, which is
the assumption the seeded backlog items were written under.

**Correctness — the retry ladder matches SPEC §5.11.7 exactly, including the part that looked
wrong.** `study_outcomes.ladder_step` maps attempt counts to moves precisely as the spec's table
does (1st → retry, 2nd → retry with more explicit support, 3rd → easier prerequisite, 4th →
unresolved + tutor review), all six final outcome labels exist, and mastery is recomputed only
*after* the label is final so an assisted or unresolved answer can never inflate independent
mastery. There is also a sensible unspecified degradation: the prerequisite drop only happens if
the prerequisite actually has approved templates, otherwise it retries the same skill rather than
serving nothing.

I went in expecting a real bug here and did not find one. The escalation counts attempts on a
"line" filtered by the item's `target_skill_id`, so dropping to an easier prerequisite looked like
it would start a fresh line and make the 4th-attempt tutor-review escalation unreachable — a
student could fail forever without ever being flagged. It does not: `create_study_item` takes
`target_skill_id` (the base skill whose line the item belongs to) *separately* from `skill_id` (the
skill the question is drawn from), so a prerequisite question keeps the original line's identity
and the counter keeps climbing to the tutor-review threshold. Recording this as a negative result
specifically because the correct behavior depends on a two-parameter distinction that is easy to
misread as a bug, and the next person to look will otherwise re-derive the same false alarm.

**Correctness — the learning-gain formulas match SPEC §5.13.3 exactly.** `Raw Gain = Post − Pre`
and `Normalized Gain = (Post − Pre) / (Max − Pre)` are implemented literally, and the perfect-pre
case sets `normalized_gain_status = "not_applicable_pre_max"` with `normalized_gain = None` as the
spec requires (rather than emitting a division-by-zero or a misleading 0.0). All twelve fields
§5.13.3 says to store are present and populated: pre/post raw, raw gain, weighted gain, normalized
gain, skill-level gain, difficulty transition, independent-correct rate, hint dependency, solution
dependency, unresolved skills, and response-time change. AUD-L-08 is a missing bound on the result,
not a wrong formula.

_(The rest of phase 3.5, and phases 3.6–3.7, are **not** covered — see PROGRESS.md for the explicit list of
what remains, rather than leaving the absence to be inferred from this file.)_
