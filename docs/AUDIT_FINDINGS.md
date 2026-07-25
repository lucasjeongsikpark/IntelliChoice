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
| **AUD-L-04** | **Minors / PII** | **P1** | **Decided** — fix before the gate | D-072 accepted "names in free text may survive" *because* that text lived in a 90-day-purged table; S25 then derived permanent, never-purged `semantic_memory.fact_text` from it, and those facts reach parent-visible reports |
| AUD-L-05 | Minors / PII | P2 | Open — Phase 0B | `MemoryConsolidationPayload` carries free text but was never added to the PII-floor allowlist test, contrary to D-072's own stated rule |
| AUD-L-06 | Minors | P3 | **Decided** — delete in Phase 0B | `tutor.generate_hint` is dead code that omits the leak check its live sibling applies — a trap for whoever wires it up |
| AUD-L-03 | Money | P2 | **Decided** — Phase 0B | `pre_intro` stage-narrative spend is never folded back into the session total, so the per-session ceiling is permanently one call short |
| **AUD-L-07** | **Authorization** | **P1** | Open — before the gate | D-086's known tutor/branch_manager scope gap now reaches further than when it was written: it covers the S28 dashboard and report surface, so a tutor token can read any student's data and generate reports about them |
| AUD-L-09 | Correctness | P2 | **Decided** — Phase 0B | Numeric grounding verifies a number's *provenance*, not its *attribution*, so a report can invert a real result ("fell from 6 to 4") and still pass |
| **AUD-L-10** | **Data integrity / scoring** | **P1** | Open — before the gate | The server marks an exam item `answered` and then accepts more answers for it; exam scores are computed over the *attempt* count, so one changed answer rescores a 10-item exam as 10/11 and silently removes the `not_applicable_pre_max` flag. Enforced client-side only |
| AUD-L-11 | Robustness / contracts | P2 | Open — Phase 0B | `UnknownQuestionVariantError` is raised at four sites and caught nowhere, so an answer POST with an unknown or not-currently-served variant returns an unhandled **500** instead of a 4xx |
| AUD-L-12 | SPEC conformance | P2 | Open — Phase 0B | `recommended_difficulty` is computed, stored and displayed but routes nothing; two docstrings claim it seeds `starting_difficulty` and it does not. Masked only by the 1:1 skill↔difficulty bank |
| AUD-L-13 | Minors / correctness | P2 | Open — Phase 0B | Memory consolidation verifies a fact's evidence provenance and cross-session repetition, never the claim against the measured mastery score in the same database — a `strength` fact coexists with `weighted_score = 0.0` for that skill |
| AUD-L-14 | Correctness / parent-visible | P2 | Open — Phase 0B | `time_spent_minutes` sums a client-populated telemetry column and ignores the always-populated `assessment_attempts.response_time_ms`, so a report shows `0.0` minutes beside `attempts_count: 26` — inside `verified_facts` |
| AUD-L-15 | Correctness / parent-visible | P2 | Open — Phase 0B | Mastery excludes the post-exam by construction while "skills to strengthen" is post-exam-derived, and both are shown together labeled `date_range_label: "all time"` — one skill reads mastery 1.000 *and* "needs work" |
| AUD-L-08 | Correctness | P3 | Open — Phase 0B | `normalized_gain` has no bound in either direction and derives its denominator from the pre *attempt count*. **Reachability corrected in the S36 continuation:** −200% reached on an ordinary journey, and >1 reachable via AUD-L-10's duplicate attempts |
| AUD-L-16 | Design integrity | P3 | Open — Phase 0B | Both policy snapshots (`assessment_sessions.policy`, `study_sessions.intervention_policy`) are written at creation and never read back; only `time_limit_seconds` governs behavior, via a separate column |
| AUD-L-17 | Test integrity | P3 | **Fixed in S36 continuation** | The default mock's own hint boilerplate (`Level 1`) tripped the runtime answer-leak check whenever the served answer was `"1"`, making a hint test fail 8 times in 60 runs; `hint_events.was_personalized` still records no reason code, so the real rate is unmeasurable |
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

**Disposition — DECIDED (user, S36 close-out; see D-098).** Add a retention job for
`semantic_memory`, and a line in the §6.1 privacy text. Rejected: stopping raw chat text reaching
consolidation (removes the risk at source but spends the consolidation quality D-074 deliberately
bought, and would partly supersede a settled decision); and accept-and-disclose (zero cost but
makes "we delete chat after 90 days" misleading for a product whose primary users are minors).

The chosen option restores exactly the boundary D-072 already reasoned about and approved, rather
than re-opening a settled trade-off. Phase 0B work, before the §2.6 gate:

1. `SemanticMemoryRepository.purge_older_than` + a `make memory-purge` CLI, mirroring
   `TutorChatMessageRepository.purge_older_than` / `make chat-purge` exactly.
2. Fold in the `stage_transitions` and `student_reports` retention jobs already on the standing
   carry-over list — same pattern, same session, so this is done once rather than three times.
3. The retention window must be **stated in the §6.1 privacy notice**, and the notice must not
   imply that deleting chat after 90 days removes everything derived from it.
4. All of these must run on a schedule, not by hand — the EventBridge item already seeded in
   §2.5 covers it. A retention promise that depends on someone running `make` is not a retention
   promise, which is the same reasoning §2.5 already applied to `chat-purge`.

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
reasonably call it and inherit an unguarded path.

**Disposition — DECIDED (user, S36 close-out; see D-098): delete it**, along with its three tests.
There is no caller to migrate, and the live path (`generate_personalized_hint`) already has every
check. If a non-personalized hint flow is ever wanted, writing it fresh with the checks in place is
easier and safer than remembering that this one lacked them. Rejected: keeping it and adding the
checks, which would preserve unreachable code and the false impression that it is exercised.

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
write-back is the remaining half.

**Disposition — DECIDED (user, S36 close-out; see D-098): fold out-of-band spend into the
checkpoint**, settling the question D-073 and D-075 each deliberately left open. Both `pre_intro`
(SSE connect) and chat's own spend get a path to write their cost back into `bedrock_spend_cents`,
so the per-session ceiling means what its name says and there is one authoritative number instead
of two partial ones.

The cost is understood and accepted: this means writing to the checkpoint from outside a graph
turn, which is exactly what those two decisions avoided. The reason to accept it now is AUD-L-02 —
this session has already produced one P0 from a ceiling that silently did not apply, so a ceiling
that is merely *approximately* right is no longer a comfortable place to leave things. Phase 0B;
the per-day ceilings remain the real bound on those surfaces in the meantime.

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

**Disposition — DECIDED (user, S36 close-out; see D-098).** Phase 0B, two partial mitigations,
with the incompleteness stated rather than papered over:

1. **A directional check.** When the evidence carries a known gain, reject narrative text that
   pairs those two numbers in the wrong order — this is what stops "your score fell from 6 to 4"
   for a student who went 4→6, which is the damaging class.
2. **Narrow the evidence dict per stage**, so each narrative is only given the fields it needs and
   there are fewer unrelated numbers available to misattribute at all.

Rejected: accept-and-rely-on-displayed-facts (defensible at current volumes, but it leaves
unverified LLM prose as parent-facing text about a child); and real semantic verification, which is
the only *complete* answer but is a project rather than a fix, adds a paid call per narrative, and
would itself need a cost ceiling given AUD-L-02. **Neither chosen mitigation makes the check
sound** — that limitation should be recorded in the code, not just here, so nobody later mistakes
the directional check for full verification.

### AUD-L-08 — `normalized_gain` is unbounded, and its denominator comes from the attempt count (P3)

- **Severity:** P3 — but see the reachability correction at the end of this entry; "not reachable
  today" was wrong in two ways.
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

**Reachability correction (S36 continuation).** The "not reachable today" claim above was wrong
in two independent ways, both found by driving real journeys through the real API rather than
calling the function with fabricated inputs:

1. **The negative direction is reachable right now, with no unusual setup.** A student driven
   8/10 → 4/10 through the ordinary flow was stored with
   `normalized_gain = -2.0` and `normalized_gain_status = NULL` — a −200% "normalized learning
   gain", flagged valid. The entry above only considered the `> 1` direction, so the *unbounded*
   framing was right and the *unreachable* framing was not.
2. **The `> 1` direction is reachable too, via AUD-L-10.** The reasoning above ("the post length
   always equals the pre length") is true of *item* counts, but this arithmetic uses **attempt**
   counts, and AUD-L-10 shows attempts are not one-for-one with items: a second answer to one
   post-exam item pushes `post_raw` above `max_score`. The stated invariant does not protect the
   quantity the code actually divides by.

Also worth recording, because it is the opposite of the expected failure: an extra *pre* attempt
takes the `pre_raw >= max_score` branch **off**, so a genuine 10/10 pre-exam stops reporting
`not_applicable_pre_max` and starts reporting a computed `normalized_gain` instead. The flag that
exists to mark this case unmeasurable disappears exactly when it applies.

**Bound on user exposure (checked, not assumed).** `normalized_gain` appears in
`apps/learning-web/src/types.ts` but is rendered by **no screen or component**, so −200% is not
displayed today. It *is* passed into `StageNarrativePayload` (`nodes.py:650`), so it can shape the
`post_outro` narrative text a student reads.

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

## S36 continuation — the four uncovered audit areas (2026-07-25)

The S36 session covered money, minors/PII, authorization and the data-integrity pattern sweep,
and ran out. This continuation covers the rest: §3.4's scoring / re-grade-consistency /
policy-snapshot remainder, §3.5's mastery + hint ladder + generation pipeline + memory work, and
all of §3.6 (independent recomputation). Method note: §3.6 could not be done against the existing
database because every learning table except `student_reports` and `stage_transitions` was empty,
so **four complete journeys were driven through the real local API first** — improving (3→9), flat
(6→6), regressing (8→4) and pre-max (10→9) — and every number below is recomputed from those raw
rows with SQL that never calls the code under audit.

### AUD-L-10 — The server marks an exam item `answered`, then accepts more answers for it; scores are attempt-counted (P1)

- **Severity:** P1 — fail-open on a data-integrity invariant the server already has the state to
  enforce. Not P0: there is no production traffic, and the shipped UI closes the common path.
- **Area:** data integrity / deterministic scoring (SPEC §5.9.2, §5.13.3)
- **Status:** open, fix before the gate

**What.** `_mark_item_answered` sets `assessment_items.status = "answered"` on every submission and
`GET /exam/overview` reports it, so the server knows an item is done. Nothing on the answer path
reads it. Idempotency is keyed `(assessment_session_id, question_variant_id, Idempotency-Key)`, so a
second submission for the same item under a *different* key grades and inserts a second attempt —
it does not replace the first, and both count.

**Reproduction (live, local API).**

```
answer item 0 wrong  (Idempotency-Key: change-1) -> 200
answer item 0 right  (Idempotency-Key: change-2) -> 200
attempt rows for that one item                   -> 2      (a,d,f / d,d,t)
answer the other 9 items once each, finalize     -> 200
pre-exam totals                                  -> 11 attempts / 10 correct   (10 items served)
```

and without any phase manipulation:

```
answer an item, confirm overview reports status=answered
answer it again with a new key -> 200, attempt rows = 2
```

Of every assessment session in the local database, exactly one has `attempts > items`, and it is
this probe — so this does not otherwise occur, it is simply unguarded.

**Why it corrupts scores.** `learning_gain.compute_learning_gain`:

```python
pre_raw   = count(correct pre attempts)
max_score = len(pre_graded)            # ATTEMPT count, not item count
normalized_gain = (post_raw - pre_raw) / (max_score - pre_raw)
```

One changed answer on a 10-item exam gives `pre_raw=10, max_score=11`: the exam scores 10/11, and
the `pre_raw >= max_score` branch stops firing, so `not_applicable_pre_max` is silently replaced by
a computed `normalized_gain`. A duplicate *post* attempt pushes `post_raw` above `max_score`,
producing AUD-L-08's `> 1` case. Changing an answer from wrong to right therefore *lowers* the
score, which is the opposite of what a student would expect.

**Why the shipped UI mostly hides it, and why that is not enough.**
`ExamScreen` gates on `isReadOnly = isExamPhase && currentOverviewItem?.status === "answered"` and
renders "You've already answered this question - it's locked in and can't be changed." But the
optional chaining makes the guard default to **permissive**: when `currentOverviewItem` is
undefined — overview not yet fetched, or its fetch failed — re-answering is allowed. And
`submitAnswer` mints `crypto.randomUUID()` per call, so SPEC §5.9.2's idempotency key can never
match a prior submission and is inert for the purpose the spec cites it for. `busy={false}` is
hardcoded at all six screen call sites in `App.tsx`, so there is no in-flight guard either;
double-click is prevented only incidentally, by `setSelected(null)` disabling the button on
re-render. Any non-browser client is unguarded entirely.

**Recommendation.** Reject (or treat as idempotent) an answer for an item already `answered`,
server-side, in the same place the status is written; and derive `max_score` from the declared item
count rather than the attempt count. The second half also closes AUD-L-08's reachable path.

### AUD-L-11 — `UnknownQuestionVariantError` is caught nowhere: unhandled 500 (P2)

- **Severity:** P2 · **Area:** robustness / API contracts · **Status:** open, Phase 0B

Raised at `flow.py` lines 295, 416, 422 and 697; `grep` finds no `except` for it in any router, in
the graph, or in `main.py`. Live: `POST /answers` with `question_variant_id="does-not-exist"` →
**500 Internal Server Error**. Also reached by answering a valid variant that is not the currently
served study item — a stale tab, or a retry landing after the phase advanced (observed while
probing AUD-L-10).

The correct pattern already exists one file away: `POST /sessions/{id}/chat` validates the same
thing and returns 400. 500s inflate error-rate metrics and can trip the CloudWatch alarms S34
added, so this is noise in exactly the signal S39 will rely on.

### AUD-L-12 — `recommended_difficulty` is computed, stored and displayed, but routes nothing (P2)

- **Severity:** P2 · **Area:** SPEC conformance (§5.11.2 rules 2–3) · **Status:** open, Phase 0B

`mastery_bootstrap.recommended_difficulty` implements the rule correctly (modal assessed tier,
nudged ±1 by accuracy, clamped 1–5) and `flow.py:233` stores it per skill. Two docstrings claim it
drives routing — `mastery_bootstrap.py:7` ("for difficulty routing (§5.11.2 rules 2-3)") and
`study_plan.py:5-7` ("`recommended_difficulty` (from bootstrap mastery) **seeds the session's
`starting_difficulty`**"). Neither is true: `build_study_plan` reads it into `recommended`
(line 133), packs it into the ranking tuple (138), and drops it — line 142 unpacks only `skill_id`.
`starting_difficulty` is assigned `first_item.difficulty` (line 169). Its only other readers are
display surfaces (`students.py:130`, `history.py:110`).

**Evidence.** `aud-student-regressing`'s weakest skill `linear_distribute` has
`weighted_score = 0.0` and `recommended_difficulty = 4` — stepped *down* from tier 5 because
accuracy was 0 — yet the study session was created with `starting_difficulty = 5`. The student was
served the tier they had just failed, with the model's step-down recommendation unused in the same
transaction.

Masked today because the bank is 1:1 skill↔difficulty (the D-060/A6 collinearity, which
`study_plan.py:7-8` acknowledges: "a skill *is* its difficulty tier"), so ranking by weakest skill
accidentally yields a defensible tier. It stops being accidental the moment real content has more
than one skill per tier. Either wire it up or delete it and correct both docstrings — a computed,
stored, displayed number that influences nothing is worse than an absent one.

### AUD-L-13 — Memory consolidation verifies provenance and repetition, never the claim against measured mastery (P2)

- **Severity:** P2 · **Area:** minors / correctness · **Status:** open, Phase 0B

`consolidation.py` verifies that a candidate fact's cited `evidence_event_ids` exist, demotes an
opposite-polarity fact to `contested` rather than replacing it, and requires ≥2 sessions of
evidence before promoting `provisional` → `active`. It never compares the fact against
`mastery.weighted_score` for the same skill, which is in the same database and the same transaction.

**Evidence.** `aud-student-regressing` has `mastery.weighted_score = 0.0` for `linear_distribute`
and an accepted `strength` fact for that same skill — *"Shows independent strength in this
skill."* — citing real events. Across all four journeys **all 20 facts are `strength` and zero
`weak_skill` facts exist**, including for the student who went 8→4 and whose own
`learning_gain.unresolved_skills` names `linear_distribute`.

**Bound, and it is a real bound.** `_resolve_relevant_fact` uses `top_fact_for_skill`, which
excludes `provisional`/`contested`/`superseded`/expired, so only `active` facts reach tutoring
payloads and parent-visible reports — and everything here is `provisional`. Nothing prevents it
after a second session, though, because the promotion criterion is repetition, not consistency.

Same class as AUD-L-09 (provenance verified, attribution not), one layer earlier in the pipeline,
and it concerns claims about a child's ability that AUD-L-04 already showed reach parents.
A deterministic floor — refuse a `strength` fact for a skill whose measured mastery is below
`WEAK_SKILL_THRESHOLD`, and vice versa — is cheap and does not depend on model quality.

### AUD-L-14 — `time_spent_minutes` reads best-effort client telemetry and ignores the always-populated server column (P2)

- **Severity:** P2 — a wrong parent-visible number, presented as a *verified fact*. Fails low.
- **Area:** correctness / reporting · **Status:** open, Phase 0B

`build_dashboard` computes `time_spent_minutes = total_time_ms / 60000`, where
`total_assessment_time_ms_in_range` sums `AssessmentItemState.time_spent_ms` — populated only by
S23's autosave tick (`POST /exam/items/{id}/time`), sent by the frontend. Meanwhile
`assessment_attempts.response_time_ms` is `NOT NULL` and written on every answer.

**Evidence.** The four journeys produced **140 `assessment_item_state` rows with
`sum(time_spent_ms) = 0`**, while the same students' attempts hold 41,250 ms per exam (≥82.5 s
each across both exams). `POST /students/{id}/report` accordingly returned, inside
`verified_facts`: `attempts_count: 26` and `time_spent_minutes: 0.0`. `verified_facts` is the
grounding set the narrative is checked against, so "0.0 minutes" is presented as verified.

The repository docstring claims item-state is "the only populated per-question timing source in
this schema". Half true: `study_attempts` genuinely has no response-time column, so study time
really is unavailable — but for exams an always-populated source exists and is ignored.

Frontend fragility compounds it: `ExamScreen` records time in a `useEffect` **cleanup** (fires on
item/phase change or unmount), gated on `currentOverviewItem?.assessment_item_id` being present,
and `useLearningSession.recordItemTime` swallows every failure with `.catch(() => {})`. A hard
refresh, a closed tab, a failed overview fetch, or any non-browser client yields 0.0.

### AUD-L-15 — Mastery and "skills to strengthen" use different windows and are shown together as "all time" (P2)

- **Severity:** P2 · **Area:** correctness / reporting · **Status:** open, Phase 0B

`_recompute_all_skill_mastery` accepts only `pre_assessment_session_id` and `study_session_id`;
the post-exam is **structurally excluded**, and its docstring says so ("every skill touched by the
pre-exam or study phase"). `unresolved_skills` / `weak_skill_names` come from `learning_gain`,
which is post-exam-derived. Both land in one report payload.

**Evidence** — `aud-student-premax` (10/10 pre, 9/10 post):

| skill | `mastery_by_skill` | listed in `unresolved_skills` |
|---|---|---|
| `linear_distribute` | **1.000** | **yes** |

The same report's `interpretation_text` reads *"Skills to strengthen: Solve linear equations
requiring distribution and combining like terms"* while `mastery_by_skill` gives that skill 1.0,
and `verified_facts.date_range_label` says **"all time"** — which misdescribes mastery, since
mastery never sees the post-exam. A parent sees 100% mastery and "needs work" for one skill in one
view, both labeled verified.

**The arithmetic is correct.** Recomputing mastery from raw rows restricted to the pre+study window
reproduces all five skills exactly (`linear_both_sides` 1.0000, `linear_distribute` 0.0000,
`linear_neg_frac_coeff` 1.0000, `linear_one_step` 1.0000, `linear_two_step` 1.0000). This is a
windowing and labeling defect, not a computation defect — the fix is to state each number's window,
and to decide deliberately whether mastery should include the post-exam.

### AUD-L-16 — Both policy snapshots are write-only (P3)

- **Severity:** P3 (no behavioral defect today) · **Area:** design integrity (SPEC §5.9/§5.13)
- **Status:** open, Phase 0B

`assessment_sessions.policy` and `study_sessions.intervention_policy` are written at creation and
**never read back anywhere**. The only consumers of `exam_policy` in either app are the two
`get_policy()` calls in `assessment_builder`, both at creation time. Only `time_limit_seconds`
governs runtime behavior, and it does so through its own denormalized column
(`flow.py:142-144`), not through the snapshot.

`hints_allowed`, `navigation` and `feedback_visibility` are enforced — where at all — by hardcoded
phase-string checks: chat returns 409 unless `phase == "study"` (its comment says it is "matching
`exam_policy`'s `hints_allowed=False`", i.e. the policy is documentation, not the mechanism), and
intervention interrupts are only ever created on the study path. Those checks agree with the
snapshot today, but a policy change would apply retroactively to in-flight sessions — the one thing
snapshotting exists to prevent. `intervention_policy` is a hardcoded `{"hints_enabled": True}`
literal at `study_plan.py:152`.

### AUD-L-17 — The default mock's hint boilerplate tripped the runtime leak check; `was_personalized` records no reason (P3, mock half fixed in-session)

- **Severity:** P3 · **Area:** test integrity + observability · **Status:** mock fixed; the
  observability half is open, Phase 0B

D-097's addendum recorded the long-standing
`test_hint_reflects_the_students_actual_wrong_option` flake as unseeded-RNG-driven at ~1 in 4 and
prescribed "seeding the fixture's RNG". The mechanism was RNG-driven; the attribution was wrong,
and no fixture RNG exists to seed — `_turn_context` constructs `random.Random()` per request
inside the route handler.

**Real cause.** `tutor.generate_personalized_hint` discards any hint in which
`answer_text_leaked` finds the served question's correct answer standing alone, substituting the
canonical ladder text. `MockBedrockProvider`'s personalization stand-in prefixed its output with
`Level {level} hint`, and `answer_text_leaked("Level 1 hint…", "1")` is `True` — a bare `1` with
non-alphanumerics on both sides. ~6% of this bank's variants have the answer `"1"`, and the
unseeded per-request RNG chooses the variant, so the test failed whenever that variant was served.
Measured **8 failures in 60 standalone runs** (13%), not 1 in 4; every failure returned the level-1
canonical text verbatim, confirming the fallback path.

**Fixed** by changing the marker to `Hint L{level}` — gluing the digit to a letter satisfies the
check's lookarounds — with the reason written into the docstring so it is not "tidied" back.
**60/60 passing** afterwards, against 52/60 before. Pinned by a new deterministic guard,
`packages/curriculum/tests/test_mock_hint_is_leak_clean.py`, which asserts the mock's output is
leak-clean for every reachable short answer at every level of every shape ladder, and that it still
names the misconception and varies by level.

**The half that is not fixed, and matters more.** `hint_events.was_personalized` is a single
boolean with no reason code, so *gateway failure*, *leaked answer*, *ladder monotonicity violation*
and *model set `answer_revealed`* are indistinguishable after the fact. `answer_text_leaked` is a
boundary-anchored substring match and roughly 54% of this bank's variants have a single-digit
answer, so any real model hint whose prose contains that digit standing alone ("Step 1", "try 2
more") is silently downgraded to the canonical hint. It fails safe — the student gets a generic
hint, never a leaked answer — but the rate is unmeasurable from what is stored, which means the
quality cost of a safety check cannot be observed in production.

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

### Areas audited with no finding — S36 continuation

**Scoring is deterministic, and stored rather than re-derived.** All 93 stored
`assessment_attempts` satisfy `is_correct == (selected_option == correct_option)` — zero
disagreements. `resolve_graded_attempts` uses `attempt.is_correct` for assessment attempts, so a
later edit to a variant cannot retroactively re-grade a past exam. Zero attempt rows disagree with
their variant's *current* `correct_option`, so no drift has occurred either. Every field SPEC §5.9.3
requires on an attempt is present, including `correct_option` frozen at submission time.

**Template edits cannot retroactively move historical analytics.** `skill_id` and
`difficulty_label` *are* read live from `question_templates` when grading attempts for mastery and
gain, which looked like a re-grade-consistency hole. It is not: templates are versioned by creating
new rows, and `supersede_template` only flips `validation_status` while keeping the prior row — so
the fields the analytics read are immutable per row.

**Unanswered items fail closed.** A skipped item and a never-visited item both received attempts
with `selected_option = NULL, is_correct = false` under a `finalize-unanswered-*` key; totals stayed
10 attempts / 8 correct on a 10-item exam. Unknown is not treated as correct.

**Exam assistance cannot leak in, matching `hints_allowed=False`.** During `pre_exam`: `/respond`
with `intervention_choice` → 409 "no interrupt is pending"; `/chat` → 409 "chat is only available
during study"; a wrong answer produces no interrupt and withholds correctness (`is_correct: null`,
matching `feedback_visibility=hidden_until_finalize`). The enforcement is structural rather than
policy-driven (AUD-L-16), but it holds.

**SPEC §5.9.1 exam composition is exact.** Every pre- and post-exam served 2 questions per
difficulty tier 1–5, total 10, verified by joining `assessment_items` through `question_variants` to
`question_templates.difficulty_label` for two students across four exams.

**SPEC §5.10.1's weights and formula are literal.** `DIFFICULTY_WEIGHTS = {1: 1.0, 2: 1.4, 3: 1.9,
4: 2.5, 5: 3.2}` matches the spec's example exactly, and `weighted_score` is exactly
`Σ(weight where correct) / Σ(weight)`.

**SPEC §5.11.1's `base_problem_count = 5` holds.** The 6 study items per journey are 5 base + 1
remediation; §5.11.1 says remediation is "tracked separately", so 6 is conformant, not off-by-one.

**The hint ladder is correct end-to-end, driven live.** Three levels served in order, all texts
distinct, `answer_revealed=False` throughout, none containing the question's real answer text, and a
fourth request closes the ladder with 409 rather than looping or re-serving. All three rounds landed
in `hint_events`.

**Question-bank integrity is clean** across 50 templates / 43k variants: zero duplicate option sets,
zero `correct_option` outside `a–d`, zero null option text, zero empty `rendered_question`, zero
difficulty outside 1–5, zero templates without variants.

**Dashboard and report numbers reconcile against independent SQL.** `overall_accuracy` recomputed
bit-identically (`0.9230769230769231`, 24/26); `accuracy_trend` matched (17/26 = 0.6538);
`mastery_by_skill` matched all five skills exactly once restricted to its real window;
`pre_post_by_skill` reconciled item-by-item against difficulty tiers. The only report numbers that
did **not** reconcile are AUD-L-14 and AUD-L-15.

**`starting_difficulty` is not inverted** — I suspected it was, since a 10/10 student got tier 1
while an 8/10 student got tier 5. That is §5.11.2 rule 1 (lowest mastery first) working: the 8/10
student's two misses were both tier 5, and a perfect scorer ties on every skill so the documented
curriculum-order tie-break decides. Recorded because it reads like a bug.

**My own first recomputation was wrong, not the API.** An initial independent mastery calculation
disagreed with the dashboard on two skills (0.6 vs 1.0) because it summed *all* attempts while
mastery covers pre+study only. Recorded so the next session does not repeat it — and it is what led
to AUD-L-15.

**Note, not a finding:** `accuracy_trend` and `overall_accuracy` count hint-assisted corrects as
correct, while mastery counts only `independent_correct`. Both appear on one dashboard. Defensible
(one is "accuracy", the other "independent mastery") but the labels do not say so.

_(Still **not** covered: the browser-driven adversarial runs — refresh mid-exam, concurrent tabs,
expired timers, dropped SSE — and the live-staging half of §2.3. See PROGRESS.md for the explicit
list, rather than leaving the absence to be inferred from this file. The API-level adversarial
probes that *were* run are the ones evidenced above and in AUD-L-10/11.)_
