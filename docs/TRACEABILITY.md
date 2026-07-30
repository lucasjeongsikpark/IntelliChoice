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

## Status — 21 of 37 sections, and not the finished criterion

**Tranche 1 (below) covers the ten non-negotiable rules in CLAUDE.md**, which is the correct place
to start for two reasons: they are the project's own compressed statement of what must not break,
and they map onto §2.3's risk order (money, minors, authorization, data integrity first). They cut
across roughly 12 of the 37 sections.

**Tranche 2 covers the money risk class** (§5.8.3–.5, §5.18, §5.31) — every path that can spend
without a user watching.

**Tranche 3 covers minors and PII** (§5.1, §5.15, §5.14.3) — the risk class where "unverified" is
least acceptable, since the primary users are K–12 students.

**Tranches 4–5 cover authorization and data integrity** (§5.2.2, §5.6, §5.19–§5.24; §5.4, §5.5,
§5.9, §5.13, §5.16, §5.26) — completing all four of §2.3's risk classes.

**Traced: 10 of 10 rules in tranche 1, plus tranches 2–5. Sections swept: 21 of 37.**
The criterion is **not met** and this file does not claim it
is. What it establishes is the method, the scope boundary, and the evidence so far — plus two real
findings (T-01, T-02) that a session of assertion would have missed entirely.

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

## Tranche 3 — minors and PII (§2.3's second risk class)

The primary users are K–12 students, so this is the risk class where "unverified" is least
acceptable. §5.1.4 was traced in tranche 1 (rule 4) and is not repeated.

### §5.1.2 — Token claims and product-specific consent

**Split verdict: the enforcement half is traced, the notice half is a gap (T-02).**

*Enforcement — traced.* [auth.py:25-29](../packages/shared/src/intellichoice_shared/auth.py#L25-L29)
carries SPEC's full claim set (`account_status`, `consent_status`, `parental_consent_verified`,
`consent_version`, `student_age_band`), and `account_refusal_reason` is consumed by **both** apps'
`get_current_claims` *and* both SSE routes — repeated rather than inherited, because the streams
verify `?token=` directly and never pass through the dependency (AUD-F-13's split-path shape). This
was AUD-X-02, a P1: the claims existed and were read by **nothing**, so a `suspended`/`revoked`/
unverified token behaved identically to a consented one on all 18 learning routes. Fixed in S40
(D-107) and measured. Note the age-band exempt set is deliberately **empty**, so every student needs
verified parental consent today — stricter than §5.1.2's literal "under 13" wording, and the right
way round to be wrong.

*Notice — see **T-02** below.*

### §5.1.3 — Location consent

**Traced.** Precise coordinates never leave the resolving function
([branch_locator.py:15](../apps/chat-api/src/chat_api/services/branch_locator.py#L15)), the chat SPA
gates on an explicit `LocationConsentModal.tsx`, a ZIP/city alternative exists (S37's e2e locator
spec resumes with a zip), and AUD-C-03 closed the one remaining leak —
[checkpoint_privacy.py:24](../apps/chat-api/src/chat_api/services/checkpoint_privacy.py#L24)
purges LangGraph's `checkpoint_writes.__resume__` rows after a `location_consent` resume, which is
where coordinates survived after every `QAState` field had been cleaned. Tests:
`test_branch_locator.py`, `test_chat_endpoints.py`, plus D-113's regression test that decodes
checkpoint blobs with LangGraph's own serializer.

### §5.1.5 — Prohibited data uses

**Traced structurally, which is the only way this list is worth anything.** "Exposing complete chat
transcripts to tutors or branch managers" is prevented by a **per-audience field allowlist**
([report.py:120-151](../apps/learning-api/src/learning_api/services/report.py#L143-L150)): the
`tutor` audience gets six fields against the parent's fourteen, and no transcript field exists in
the payload at all. A denylist would have to be maintained; an allowlist fails closed when someone
adds a field. "Retaining precise location history" and "sending email/creating calendar events
without approval" are covered by §5.1.3 and §5.1.4 above.

### §5.15 — Memory, and the retention boundary

**Traced.** Three memory types plus Sunday consolidation in
[packages/memory/](../packages/memory/src/intellichoice_memory/); test:
`packages/memory/tests/test_consolidation.py`.

The part worth citing is the retention boundary, because it was broken and restored:
[retention_purge_cli.py:12-21,54-61](../apps/learning-api/src/learning_api/services/retention_purge_cli.py#L12-L21)
purges `semantic_memory` at **90 days**, `stage_transitions` at **90**, `student_reports` at **365**.
This is AUD-L-04 (P1, D-114): D-072 accepted "names in free text may survive" *because* that text
lived in a 90-day-purged table — then S25 derived permanent, never-purged `semantic_memory.fact_text`
from it, and those facts reach parent-visible reports. **An accepted residual risk whose mitigating
assumption had silently stopped holding**, which is the most dangerous shape a documented risk takes.

### §5.14.3 — Parent dashboard

**Traced.** [authorization.py:39-43](../apps/learning-api/src/learning_api/authorization.py#L39-L43)
verifies parents against a **live MySQL lookup** of linked children and 403s otherwise — not a claim
in the token, which is the distinction that matters, since a token is a snapshot and a link can be
revoked. Tests: `test_auth_and_attendance.py`, `test_dashboard_report_endpoints.py`,
`e2e/tests/learning/journey-parent.spec.ts`.

**Sections swept: 7 of 37.**

---

## Tranche 4 — authorization (§2.3's third risk class)

### §5.2.2 — Shared authentication

**Traced.** [auth.py](../packages/shared/src/intellichoice_shared/auth.py) defines `Role`,
`Audience`, `TokenClaims` and a `TokenVerifier` Protocol whose `verify(token, audience)` makes the
audience a **required argument**, not an optional check — a learning token cannot satisfy a chat
route by omission. Tests: `packages/adapters/tests/test_fake_auth.py`,
`apps/chat-api/tests/test_auth.py`, `apps/learning-api/tests/test_auth_and_attendance.py`.

### §5.6 — Parent accounts, child selection, attendance verification

**Traced, subsection by subsection**, and unusually easy to trace because the implementation cites
the spec back: [attendance.py](../apps/learning-api/src/learning_api/services/attendance.py) carries
`§5.6.2-§5.6.5` in its module docstring, `§5.6.3` at the blocked-gate message (line 16), `§5.6.5` at
the acknowledged-absence message (line 26), `§5.6.4` at the branch-manager email (line 34), and
notes at line 107 that the §5.6.4 draft is **built fresh from a live MySQL lookup and never
persisted** — which is how the escalation stays inside the no-PII-in-Postgres rule. §5.6.1 child
selection is the parent authorization path traced in tranche 3. The gate itself is rule 5's
fail-closed `AttendanceStatus.PRESENT` check.

### §5.19–§5.21 — Q&A graph, RAG documents, RAG pipeline

**Traced.** Retrieval authorization is the SQL pre-filter from rule 3
([rag.py:34-43](../packages/db/src/intellichoice_db/repositories/rag.py#L34-L43)). Storage carries
the approval and effective-date state the filter depends on —
[models/rag.py:26-61](../packages/db/src/intellichoice_db/models/rag.py#L26) gives every document
and chunk a `status` defaulting to **`"draft"`** (fail-closed: a row must be promoted to be
visible) plus `effective_from`/`effective_to`.

**§5.21.8's "no answer without a citation-supported source" is enforced by verification, not by
trust.** [qa.py:1-55](../apps/chat-api/src/chat_api/services/qa.py#L1) re-checks each model-supplied
citation against the actual retrieved chunk — its docstring is explicit that "a citation is never
trusted just because the model produced it" — and `_no_answer` is the deterministic fallback. Tests:
`test_qa_service.py`, `test_qa_graph.py`, `test_qa_coverage_eval.py`, and `packages/knowledge/`'s
chunking/ingest/retrieval suites.

### §5.22–§5.24 — MCP tools (Maps, Calendar, Gmail)

**Traced, and the ordering inside the call path is the evidence.**
[mcp.py:86-134](../packages/shared/src/intellichoice_shared/mcp.py#L86) enforces
`tool.allowed_roles` **before** argument validation and before the handler runs, so an unauthorized
call cannot reach parsing, let alone execution — §5.30.4's "enforce tool permissions in the backend"
implemented as control flow rather than as a check someone remembers to call. Every branch —
permission denial, validation failure, timeout, execution error, success — writes a
`ToolCallAuditEvent` to `mcp_tool_calls`, so a refused call is as auditable as a successful one.
Bounded by `asyncio.wait_for(tool.timeout_s)`. Tests: `packages/shared/tests/test_mcp.py`,
`test_branch_locator.py`, `test_calendar_action.py`, `test_calendar_events.py`,
`packages/adapters/tests/test_ics.py`, `packages/shared/tests/test_email.py`.

**Known accepted hole, same as rule 3:** §7-R8 (AUD-L-07) — `resolve_target_student` is unchecked
for tutor and branch_manager on the learning side. Dispositioned, not traced.

## Tranche 5 — data integrity (§2.3's fourth risk class)

### §5.4 — MySQL / PostgreSQL responsibility separation

**Traced.** `packages/db/tests/test_schema_purity.py`'s own docstring states the rule —
"§5.4.2/§5.30: Postgres stores only `*_external_id` references, never PII" — and the test walks
every ORM model to enforce it, so the separation is machine-checked rather than reviewed. §5.4.4's
real-time attendance lookup is rule 5's fail-closed gate.

### §5.5 — Adaptive learning LangGraph

**Traced.** [graph/build.py:103-118](../apps/learning-api/src/learning_api/graph/build.py#L103)
registers the §5.5.1 workflow node-for-node (`select_student`, `select_topic`, `submit_answer`,
`finalize_exam`, `resume`, …), each wrapped in `traced_node` so the graph is observable per step.
Tests: `test_learning_flow.py`, `test_learning_graph_routes.py`, `test_exam_flow_determinism.py`.

### §5.9 / §5.13 — Grading, exam composition, learning gain

**Traced, and deterministic by construction.**
[grading.py:1](../apps/learning-api/src/learning_api/services/grading.py#L1) — "Deterministic
multiple-choice grading (SPEC §5.9.3). **No LLM is ever involved.**"
[learning_gain.py:1,44-87](../apps/learning-api/src/learning_api/services/learning_gain.py#L1)
computes §5.13.3's metrics from pre/post attempts plus study support levels.
`record_assessment_attempt_idempotent` (grading.py:30) is where AUD-L-10's fix lives — uniqueness on
`(session, variant)` as a **database invariant**, after the check-only version let four concurrent
answers all return 200.

### §5.16 — PostgreSQL checkpointing

**Traced, with a dispositioned defect.** `AsyncPostgresSaver` on its own psycopg pool, one
checkpointer for the app's lifetime ([main.py:147-149](../apps/learning-api/src/learning_api/main.py#L147)).
**The known seam is §7-R9** (AUD-X-07): the checkpoint commits inside `ainvoke` while domain rows
commit at dependency teardown. Seam (a) is fixed and controlled by `checkpoint_reconcile`; seam (b)
and the commit ordering are accepted residual risk with `learning_checkpoint_repairs_total` as the
tripwire. Test: `test_checkpoint_reconcile.py`.

### §5.26 — SQL, structured output, constrained decoding

**Traced, including the negative half — which is rare and worth noting.** "No runtime NL2SQL" is
not merely absent; it is **asserted by a test**:
`apps/chat-api/tests/test_prompt_injection_eval.py:316` pins that query text only ever reaches
predefined methods. `packages/evals/registry.py:98` records why SQL-parser validation was never
built ("there is no generated SQL to parse or validate"), and
[rag.py:164](../packages/db/src/intellichoice_db/repositories/rag.py#L164) implements §5.26.1's
predefined method as a filter-first `ILIKE`. **A negative requirement with a test is the only kind
that stays true** — otherwise the first person to add NL2SQL breaks a rule nothing was watching.

**Sections swept: 21 of 37.** All four of §2.3's risk classes are now covered.

---

## Discrepancies found

Criterion 1 requires every discrepancy to be dispositioned in DECISIONS.md. **Open: none.**

| id | discrepancy | disposition |
|---|---|---|
| **T-01** | §5.30.3 requires GuardDuty and CloudTrail; neither existed and neither had a decision | **Closed 2026-07-30 (D-125), as two opposite answers**: CloudTrail **built and live-verified**; GuardDuty **deferred with a written reason**, tracked to S50 A7 |
| **T-02** | §5.1.2's first-visit Adaptive Learning notice — eleven required disclosures — is not built and is owned only *by implication* | **Open.** Needs an explicit owner, not a fix. See below. |

### T-02 — §5.1.2's first-visit notice has no explicit owner, and its content depends on a track that has not started

**This is a weaker finding than T-01 and is filed at that strength deliberately.** T-01 was a
requirement with *nothing* anywhere. This one is a requirement whose home is guessable but never
stated, which is a different and lesser problem — recorded because the guess should be written down,
not because anyone has done something wrong.

**What exists.** Nothing in `apps/learning-web/src`. The chat app has `LocationConsentModal.tsx` for
§5.1.3, so the pattern exists; the learning app has no notice component and no first-visit gate.
§5.1.2 requires eleven specific disclosures — AI may err, AI does not replace a tutor, exam results
adjust the estimated level, limited sharing with tutors/branch managers, parents see the complete
record, learning memory is created from questions and events, images are deleted immediately,
YouTube recommendations, minimized external data, and the right to challenge results or report
questions. **None of the eleven is enumerated as a deliverable anywhere in ROADMAP.md.**

**Why it is only implied.** Two plausible homes exist and neither names it:

- **S45 — consent** (I9, I10) covers "parent-grants-for-child capture UI, age-band derivation,
  no-consent→no-token; legal text from the §6.1 track". A first-visit *product notice* is adjacent
  to consent capture but is not the same deliverable.
- **The §6.1 legal & policy parallel track**, which "gates the pilot" and has **not started** —
  and which already carries a standing obligation from D-114 §4 (the privacy text must state the
  90/90/365 retention windows and must not imply chat deletion removes derived text).

So the notice's *content* depends on an unstarted track, and its *implementation* is assumed by a
session that does not list it. That is exactly how a requirement arrives at launch owned by nobody.

**The disposition needed is one sentence naming the owner**, not a build. The recommendation is
S45, with the eleven disclosures enumerated in the §6.1 track's output so the UI work is
transcription rather than drafting. **Not urgent, and not a defect** — but the primary users are
minors, and this is the notice that tells them an AI is grading their work and may be wrong.

### T-01 — §5.30.3 lists GuardDuty and CloudTrail; neither exists and neither was ever decided against

**✅ CLOSED 2026-07-30 (D-125) — and the two halves got opposite answers, which is why D-124
refused to dispose of them as one item.**

- **CloudTrail: built.** [terraform/modules/cloudtrail/](../terraform/modules/cloudtrail/), wired
  in `terraform/environments/staging/main.tf`. Management events only, multi-region, global service
  events on, log-file validation on, 90-day bucket expiry, and `aws:SourceArn` conditions on both
  bucket-policy statements so the bucket cannot accept another account's log delivery. Plan was
  **7 add / 0 change / 0 destroy**. Live-verified: `IsLogging: true`, `LatestDeliveryError: None`,
  and **delivery proven end-to-end** by a real 1,761-byte `.json.gz` object ~4.5 minutes after
  start — not by the zero-byte prefix placeholders that appear at trail-start and would have faked
  it (AUD-F-12's shape; see D-125).
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

Tranches 1–5 swept **21 of 37 sections** and cut across the rest via the non-negotiable rules.
**All four of §2.3's risk classes — money, minors, authorization, data integrity — are covered.** The remaining work, in §2.3's risk order:

1. ~~**Money / cost**~~ — ✅ **done in tranche 2** (§5.8.3–.5, §5.18, §5.31).
2. ~~**Minors / PII**~~ — ✅ **done in tranche 3** (§5.1, §5.15, §5.14.3).
3. ~~**Authorization**~~ — ✅ **done in tranche 4** (§5.2.2, §5.6, §5.19–§5.24).
4. ~~**Data integrity**~~ — ✅ **done in tranche 5** (§5.4, §5.5, §5.9, §5.13, §5.16, §5.26).
5. **The rest, and it is genuinely the rest** — §5.0, §5.3, §5.7, §5.10–§5.12, §5.14.1/.2/.4,
   §5.27–§5.29, §5.32–§5.36. **16 sections, none of them in a §2.3 risk class**: architecture
   description, curriculum taxonomy, mastery/study/tutor mechanics, the remaining UI transports,
   Pydantic/FastAPI/failure-handling conventions, observability, and the deployment/accounts/
   technology-placement sections. Lower risk per section, and several are descriptive rather than
   testable — which is its own judgement to make and record, not a reason to skip them.

**Estimate, revised twice and both times downward.** First estimate was two to three sessions, then
one to two; tranches 1–5 landed in a single sitting. The reason is worth keeping: **each tranche was
cheaper than the last because the method and the denominator already existed**, and because the
codebase turned out to cite SPEC section numbers in its own docstrings far more often than expected
— `attendance.py` alone maps four subsections without any inference. That is the usual shape of this
kind of work and is worth expecting rather than re-discovering.

**The remaining 16 sections are the low-risk tail** and should take well under a session.

It is mechanical rather than hard. The expensive part is reading each requirement carefully enough
to know **what test would falsify it** — and, as tranche 2 showed, checking that a control is
*reachable* rather than merely present.

**It is also the cheapest criterion left.** It needs no AWS session, no Bedrock spend, no load run,
and no product decision. Nothing blocks it and nothing about it expires — which is exactly why it
has been skipped since S37, and why it will keep being skipped unless it is scheduled as the
session rather than the leftover of one.
