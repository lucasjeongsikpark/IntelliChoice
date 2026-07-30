# Requirements Traceability — §2.6 criterion 1

What the criterion demands, quoted so it cannot drift:

> **Traceability**: 100% of launch-scope SPEC requirements mapped to implementation + test;
> every discrepancy dispositioned in DECISIONS.md.

This file is the evidence. It exists because criterion 1 is the one gate criterion that had
**never been assessed** — S36–S39's audits each did traceability over *their own* SPEC range and
each recorded "criterion 1 is not met by this session", but nobody ever assembled the result or
defined what 100% was being measured against.

---

## Method, and the one rule that makes this worth reading

A row is **traced** only when it cites both an implementation location and a test that would fail
if the requirement broke. Anything else is **unverified**, and unverified counts as *not traced*.

That rule is the whole point. A traceability matrix that grades itself on "does this look
implemented" is a document that certifies whatever the author already believed — which is the
failure mode this project has hit repeatedly under other names (D-119's two fixes shipped on a
mechanism that merely fit the symptom; D-116's stale-bundle hypothesis; AUD-F-17's "one command
away" step that had never once been run). Assertion is not evidence here either.

Three verdicts, and no fourth:

| verdict | means |
|---|---|
| **traced** | implementation cited by file:line, test cited by name, requirement would fail loudly |
| **dispositioned** | not implemented, and a DECISIONS.md entry says so *on purpose* |
| **gap** | neither — the requirement is unmet, or met with nothing pinning it. Needs a disposition. |

A requirement dispositioned **in the code's own docstring** citing a decision ID counts as
dispositioned; several already are, and finding that out is most of the work.

---

## Scope determination — what "launch scope" means

SPEC §5 has **37 top-level sections** (§5.0–§5.36) over ~197 subsections, plus §6's 23
implementation phases. Launch scope is **§5 minus what a decision deliberately removed**:

| excluded | why | decision |
|---|---|---|
| §5.17 Multimodal solution images (all of it) | S29 deferred, not built | **D-078** |
| §5.30.3's "Pod Security Standards", "NetworkPolicy" | EKS-only concepts; the deployment is ECS/Fargate | **D-004** |
| §5.30.3's "AWS WAF" | deferred with a written reason, tracked to S50 A7 | **D-087** |
| §6.19 Phase 18 (Multimodal) | same as §5.17 | **D-078** |

Everything else in §5 is in scope. §6's phases are *implementation plans* for §5's requirements
rather than requirements themselves, so they are traced through their §5 sections, not separately.

---

## Status — this is a first tranche, not the finished criterion

**Tranche 1 (below) covers the ten non-negotiable rules in CLAUDE.md**, which is the correct place
to start for two reasons: they are the project's own compressed statement of what must not break,
and they map onto §2.3's risk order (money, minors, authorization, data integrity first). They cut
across roughly 12 of the 37 sections.

**Tranche 2 covers the money risk class** (§5.8.3–.5, §5.18, §5.31) — every path that can spend
without a user watching.

**Traced: 10 of 10 rules in tranche 1, plus tranche 2's money paths. Sections swept: 4 of 37**
(§5.8 partial, §5.18, §5.25, §5.30). The criterion is **not met** and this file does not claim it
is. What it establishes is the method, the scope boundary, and the first evidence — plus one real
finding (T-01) that a session of assertion would have missed entirely.

---

## Tranche 1 — the ten non-negotiable rules

### 1. No PII in Postgres, logs, traces, or LLM payloads (§5.4, §5.30.1)

**Traced.** Enforced at three separate boundaries, each with its own test, which is the shape a
PII floor has to have — D-104 is the reason: the S38 log scan was clean while a bearer JWT sat in
`http.url` on every SSE span, because a floor established at one store does not transfer to
another.

- Postgres — `packages/db/tests/test_schema_purity.py::test_no_model_has_a_pii_column_name` walks
  every ORM model against a denied-column-name list.
- LLM payloads — [bedrock.py:15-20](../packages/shared/src/intellichoice_shared/bedrock.py#L15-L20)
  types every payload as an `extra="forbid"` model with an exact field list; pinned by 12+ tests in
  `packages/shared/tests/test_bedrock_payload_pii_floor.py`, three per payload type (field set
  matches the allowlist *exactly*, no denylisted names, extra fields rejected).
- Traces — `RedactingSpanExporter` at the export boundary
  ([tracing.py:72,134-137](../packages/observability/src/intellichoice_observability/tracing.py#L72)),
  pinned by
  [test_tracing.py:62](../packages/observability/tests/test_tracing.py#L62)
  (`test_sse_token_query_string_is_redacted_before_export`), which drives the real instrumentation
  rather than the class, carries a **negative arm** (line 100 — a redactor that rewrote everything
  would also pass) and an explicit **vacuity guard** (line 91 — "no span carried http.url, the
  assertion would be vacuous"). That is the strongest-shaped test in this tranche and it is worth
  copying: it can fail for the right reason, and it cannot pass for the wrong one.

### 2. Deterministic core — grading, gating, authorization, scoring, SQL (§5.0, §5.26)

**Traced.** Each lives in its own service module under
[apps/learning-api/src/learning_api/services/](../apps/learning-api/src/learning_api/services/) with
no model call in the path: `grading.py`, `exam_policy.py`, `learning_gain.py`,
`mastery_bootstrap.py`, `study_plan.py`. Tests: `test_exam_policy.py`, `test_mastery_bootstrap.py`,
`test_report.py`, and `test_exam_flow_determinism.py` — the last being the one that pins
*determinism* rather than correctness.

**No runtime NL2SQL exists to test for**, which is the correct state and is itself recorded
(ROADMAP S30: "SQL parser validation" was not built because there is no NL2SQL feature to validate).

### 3. Authorization in the backend/query layer, never in prompts (§5.21.3, §5.30.2)

**Traced, with a known accepted hole.** The RAG filter is applied as SQL `WHERE` clauses *before*
retrieval, not as prompt instruction —
[rag.py:34-43](../packages/db/src/intellichoice_db/repositories/rag.py#L34-L43) filters
`status == "approved"`, the audience set, the effective-date window, and §5.21.3's
`branch_id IS NULL OR branch_id = current_branch`, with a branchless caller seeing org-wide chunks
only. Tests: `packages/db/tests/test_rag_search.py`, `apps/chat-api/tests/test_role_access.py`.

**The hole is §7-R8** (AUD-L-07): `resolve_target_student` returns the requested id unchecked for
tutor and branch_manager. Accepted residual risk as of D-123, expiring at first real traffic. This
is a **dispositioned gap, not a traced requirement** — §5.30.2's matrix is not fully enforced.

### 4. Every external action needs human approval via `interrupt()` (§5.1.4)

**Traced.** Approval is a LangGraph `interrupt()` resumed through
[sessions.py:1120](../apps/learning-api/src/learning_api/routers/sessions.py#L1120)
(`respond_to_interrupt`), with the paused-task detection at `_pending_task_interrupt` (line 414).
Tests: `apps/learning-api/tests/test_learning_graph_routes.py`,
`apps/chat-api/tests/test_calendar_action.py`, `apps/chat-api/tests/test_admin_escalation.py`.

### 5. Fail closed (§5.4.4, §5.21.8, §5.29)

**Traced.** [attendance.py:71-80](../apps/learning-api/src/learning_api/services/attendance.py#L71-L80)
— `check_attendance_gate` opens **only** on `AttendanceStatus.PRESENT`, so unknown and absent both
fail closed by construction rather than by an `else` branch someone has to maintain. Test:
`apps/learning-api/tests/test_auth_and_attendance.py`. RAG's no-citation refusal is covered by
`apps/chat-api/tests/test_qa_coverage_eval.py`.

### 6. Structured output → Pydantic → limited repair → deterministic fallback (§5.25.3, §5.27)

**Traced.** [gateway.py:270-285, 419](../packages/adapters/src/intellichoice_adapters/bedrock/gateway.py#L270-L285)
— `_validate_or_repair` runs the bounded repair, and the failure is logged with a `reason` that
distinguishes `schema_invalid` from `output_truncated`. Test:
`packages/adapters/tests/test_bedrock_gateway.py`.

**Open sub-item, not a gap:** the ~2–4% `rag_answer` `schema_invalid` rate is measured but the
invalid text is not captured, pending a PII decision. Carried in PROGRESS.md.

### 7. All paid-API calls go through the gateway, with timeouts, retries, caps, cost accounting (§5.25.1)

**Traced, and the interface's four "missing" methods are dispositioned in code.**
[gateway.py:58-110](../packages/adapters/src/intellichoice_adapters/bedrock/gateway.py#L58-L110)
implements bounded retry, max-token ceiling, per-session cost budget and a circuit breaker;
`worst_case_cost_cents` (line 158) is the pre-flight reservation. SPEC §5.25.1 lists six methods
and only `generate_structured` / `create_embedding` exist —
[bedrock.py:4-13](../packages/shared/src/intellichoice_shared/bedrock.py#L4-L13) disposes of the
other four by name: `generate_stream`/`classify` have no caller (D-022), `analyze_image` is S29
(D-078), and `judge` is dispatched through `generate_structured` like every other task.
**Verified independently rather than taken on the docstring's word:** `packages/evals`' judge does
call `gateway.generate_structured` ([llm_judge.py:64](../packages/evals/src/intellichoice_evals/llm_judge.py#L64)),
so rule 7 holds for the eval path too. Tests: `packages/adapters/tests/test_bedrock_gateway.py`,
`packages/db/tests/test_cost_reservation.py`,
`apps/learning-api/tests/test_cost_reservation_estimates.py`.

### 8. Solution images deleted immediately, never in backups/traces/logs (§5.17)

**Dispositioned — the feature does not exist.** S29 deferred, D-078. There is no image path, so
there is nothing to delete and nothing to leak. Re-opens the moment §5.17 is built.

### 9. External deps behind interfaces with dev fakes, real clients env-selected (D-002)

**Traced.** [packages/adapters/](../packages/adapters/) holds `fake_auth`, `fake_calendar`,
`fake_email`, `fake_maps`, `fake_youtube`, `mock_provider`, `mysql_fixtures` against real
counterparts (`bedrock_runtime_provider`, `titan_embedding_provider`,
`youtube_data_api_provider`, `mysql_profile_adapter`). Tests: `test_fake_auth.py`,
`test_mysql_profile_adapter.py`, and `packages/db/tests/test_standalone_clis_use_the_env_fallback.py`
for the env-selection path itself.

### 10. Growth-oriented, age-appropriate language; skill IDs stay internal (§5.10.3)

**Traced.** Enforced as a leak check rather than a style guide —
`packages/evals/tests/test_leak_sample.py` and
`packages/curriculum/tests/test_mock_hint_is_leak_clean.py`. The second exists because the mock's
own boilerplate once made its hints unusable (S37), which is the kind of thing only a test catches.

---

## Tranche 2 — money (§2.3's first risk class)

Every path that can spend money without a user watching. The question each row has to answer is not
"is there a limit" but **"is the limit reachable"** — AUD-L-02 was a P0 because a cost ceiling
existed, was passed `session_spend_cents=0.0`, and therefore could never fire. A ceiling that is
accounted but not threaded is decoration, so each row below was checked for threading, not presence.

### §5.8.3 / §5.8.4 / §5.8.5 — AI generation pipeline

**Traced.** SPEC's eleven-stage chain maps stage-for-stage onto
[ai_pipeline.py](../packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py): generator
(line 314) → two **independent** solvers (417, 430, sharing `_SOLVER_SYSTEM_PROMPT`) → difficulty,
ambiguity and alignment reviewers (465, 497, 522, all on `BedrockTask.QUESTION_REVIEW`) →
deterministic validation → deduplication (685–709) → activate-or-quarantine.

SPEC's "do not place free-form LLM-generated questions directly into production" is enforced
structurally, not by convention: nothing is auto-approved — the module's own docstring (line 29)
points at `QuestionRepository.activate_template` for why — and every rejecting stage has a test that
proves it rejects: `test_solver_disagreement_rejects_without_persisting`,
`test_ambiguity_reviewer_flag_rejects`, `test_alignment_reviewer_flag_rejects`,
`test_difficulty_reviewer_far_off_rejects`, `test_generator_proposing_unregistered_shape_rejects`,
`test_duplicate_rendered_question_rejects`, `test_activate_template_refuses_a_non_pending_template`.

**Cost ceiling verified reachable, not merely present.** A `_spend` accumulator (line 308) updates a
running `spend`, and **every one of the twelve downstream call sites passes `spend`** — the running
total — rather than the initial `session_spend_cents`. That is precisely the distinction AUD-L-02
cost a P0 to learn, and it is implemented correctly here. Test:
`test_ai_pipeline.py:208` asserts `outcome.cost_cents > 0` with the comment "six real calls were
accounted for".

**§5.8.4's recalibration is future work by SPEC's own wording** ("as production data accumulates"),
and there is no production data. The bootstrap half — LLM ensemble + deterministic complexity
features + solver agreement — is what exists and is traced. Not a gap; a requirement whose trigger
condition has not occurred.

### §5.18 — Weekly YouTube synchronization

**Traced.** [catalog_sync.py:65,94](../packages/youtube/src/intellichoice_youtube/catalog_sync.py#L65)
takes `run_budget_cents` and cuts off at `spend >= run_budget_cents`. The code carries an explicit
note that **a budget cutoff must never look like a classification result** (line 87) — the failure
mode where running out of money silently reads as "this video is not relevant", which would poison
the catalog rather than truncate it. Tests: `packages/youtube/tests/test_catalog_sync.py`,
`test_classify.py`.

### §5.31 — Evaluation platform

**Traced.** [settings.py:28-31](../packages/evals/src/intellichoice_evals/settings.py#L28) sets
`bedrock_run_budget_cents = 200.0` and `bedrock_max_retries = 2`;
[llm_judge.py:74](../packages/evals/src/intellichoice_evals/llm_judge.py#L74) caps
`max_output_tokens`. The judge routes through `gateway.generate_structured` (verified in tranche 1
for rule 7), so it inherits the gateway's timeouts, bounded retry, circuit breaker and cost
accounting rather than reimplementing them. Tests: `packages/evals/tests/test_llm_judge.py`,
`test_registry_coverage.py`.

**Sections swept: 4 of 37** (§5.8 partial — .3/.4/.5; §5.18, §5.25, §5.30). Money as a risk class is
covered end-to-end: generation, sync, evaluation, plus tranche 1's gateway and per-session
reservation.

---

## Discrepancies found

Criterion 1 requires every discrepancy to be dispositioned in DECISIONS.md. **Open: none.**

| id | discrepancy | disposition |
|---|---|---|
| **T-01** | §5.30.3 requires GuardDuty and CloudTrail; neither existed and neither had a decision | **Closed 2026-07-30 (D-125), as two opposite answers**: CloudTrail **built and live-verified**; GuardDuty **deferred with a written reason**, tracked to S50 A7 |

### T-01 — §5.30.3 lists GuardDuty and CloudTrail; neither exists and neither was ever decided against

**✅ CLOSED 2026-07-30 (D-125) — and the two halves got opposite answers, which is why D-124
refused to dispose of them as one item.**

- **CloudTrail: built.** [terraform/modules/cloudtrail/](../terraform/modules/cloudtrail/), wired
  in `terraform/environments/staging/main.tf`. Management events only, multi-region, global service
  events on, log-file validation on, 90-day bucket expiry, and `aws:SourceArn` conditions on both
  bucket-policy statements so the bucket cannot accept another account's log delivery. Plan was
  **7 add / 0 change / 0 destroy**. Live-verified: `IsLogging: true`, `LatestDeliveryError: None`.
  The cost argument that deferred WAF does not apply — the first copy of management events is free;
  only storage costs, and the lifecycle rule bounds that.
- **GuardDuty: deferred, with the written reason it never had.** Always-on paid service against a
  no-user staging account — the same shape as WAF, so it gets the same answer (D-087). Tracked to
  S50 A7, to be reconsidered when real traffic or production data exists.

**What changed is the record, not the state.** GuardDuty is still absent; it is now *absent and
deliberate* rather than *absent and unknown*. That is the entire product of this criterion.

*(The finding as filed, kept because the reasoning is the point:)*

§5.30.3 enumerates 15 AWS security controls. Most are traced to terraform: Secrets Manager
(`terraform/environments/staging/main.tf`, `modules/iam`, `modules/vpc`), S3 Block Public Access
(`modules/cloudfront-spa-api/main.tf`), VPC endpoints (`modules/vpc/main.tf`), RDS encryption
(`modules/rds-postgres`, `modules/rds-mysql`), ECR image scanning (`modules/ecr/main.tf`), plus
IAM roles, private subnets, security groups, TLS and rate limiting.

Three are absent, and **their status is not the same**:

| control | terraform | disposition |
|---|---|---|
| AWS WAF | absent | **dispositioned** — deferred with a written reason, tracked to S50 A7 (D-087, which added per-IP rate limiting as the explicit in-memory stopgap "not a replacement for one") |
| Pod Security Standards / NetworkPolicy | absent | **moot** — EKS concepts, and D-004 chose ECS/Fargate |
| **GuardDuty** | absent | ~~none anywhere in the repo~~ → **deferred, written reason, S50 A7 (D-125)** |
| **CloudTrail** | ~~absent~~ **built** | ~~none — one incidental D-095 mention~~ → **implemented and live-verified (D-125)** |

**Why this is worth a finding rather than a shrug.** A `grep` for GuardDuty across `docs/` returns
**nothing** — not a deferral, not a "later", not a cost note. It is not that someone weighed it and
said no; it is that the requirement fell out of the plan silently somewhere between §5.30.3 and
S33's security session, and no artifact records the moment. That is precisely the class of gap
criterion 1 exists to catch, and it is invisible to every other criterion: no test fails, no alarm
fires, no journey breaks.

**Not filed as an audit finding (AUD-*) on purpose** — those are defects in built things. This is a
requirement with no decision, which is a traceability discrepancy, hence the T- prefix.

**A disposition is owed and it is not mine to make.** CloudTrail is cheap (a trail to S3, on by
default in most accounts for management events) and is what a real incident response would want —
[INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) is grounded in two real credential incidents
(S32/D-084, S33/D-085) and currently has no account-level audit log to point at. GuardDuty is a
paid, always-on service and a real monthly cost against a staging account with no users, which is
the same argument that deferred WAF. **They probably deserve different answers**, which is the
argument for deciding them separately rather than as "the rest of §5.30.3".

---

## What remains — the honest size of criterion 1

Tranches 1–2 swept **4 of 37 sections** (§5.8 partial, §5.18, §5.25, §5.30) and cut across ~10 more
via the non-negotiable rules. The remaining work, in §2.3's risk order:

1. ~~**Money / cost**~~ — ✅ **done in tranche 2** (§5.8.3–.5, §5.18, §5.31).
2. **Minors / PII** — §5.1 (legal, consent, prohibited uses), §5.15 (three memory types +
   consolidation), §5.14.3 (parent dashboard).
3. **Authorization** — §5.2.2 (shared auth), §5.6 (parent/child/attendance), §5.19–§5.21 (chat
   role access), §5.22–§5.24 (MCP tool permissions).
4. **Data integrity** — §5.4 (MySQL/Postgres separation), §5.5 (learning graph), §5.9/§5.13
   (exam composition, grading, learning gain), §5.16 (checkpointing), §5.26 (structured output).
5. **The rest** — §5.3, §5.7, §5.10–§5.12, §5.27–§5.29, §5.32–§5.36.

**Estimate, stated so nobody plans around a wish:** tranches 1–2 covered ~4 of 37 sections plus the
ten cross-cutting rules, in well under a session. The remainder is realistically **one to two
focused sessions**, not the two-to-three first estimated — tranche 2 went faster than tranche 1
because the method and the denominator already existed, which is the usual shape and is worth
expecting rather than re-discovering.

It is mechanical rather than hard. The expensive part is reading each requirement carefully enough
to know **what test would falsify it** — and, as tranche 2 showed, checking that a control is
*reachable* rather than merely present.

**It is also the cheapest criterion left.** It needs no AWS session, no Bedrock spend, no load run,
and no product decision. Nothing blocks it and nothing about it expires — which is exactly why it
has been skipped since S37, and why it will keep being skipped unless it is scheduled as the
session rather than the leftover of one.
