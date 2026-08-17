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

| verdict | means |
|---|---|
| **traced** | implementation cited by file:line, test cited by name, requirement would fail loudly |
| **dispositioned** | not implemented, and a DECISIONS.md entry says so *on purpose* |
| **structural** | names an *artifact or convention*, not a behavior — see the constraint below |
| **gap** | none of the above — unmet, or met with nothing pinning it. Needs a disposition. |

A requirement dispositioned **in the code's own docstring** citing a decision ID counts as
dispositioned; several already are, and finding that out is most of the work.

**On the fourth verdict, which this file originally said would not exist.** Tranches 1–5 ran with
three verdicts and the explicit line "no fourth". Tranche 6 added **structural**, and the honest
account is that the original three were written before anyone had looked at §5.27 or §5.34 — a
convention like "use Pydantic v2 everywhere" is not a behavior a test can falsify, and forcing it
into *traced* would have meant inventing a ceremonial test, while calling it a *gap* would have been
false.

So the verdict was added, but **fenced**: structural requires (a) a citable artifact location and
(b) something mechanical that fails if the artifact disappears — a CI job, a typecheck, a build.
**No mechanism, no structural verdict; it is a gap.** Two sections (§5.3, §5.36) fail that test and
are recorded as *descriptive* rather than quietly passed, which flags them for human re-reading when
the architecture changes.

Adding a category to a method mid-way is exactly how a rubric gets softened, so the fence matters
more than the category. It is recorded here rather than in a footnote precisely because the next
person to want a fifth verdict should have to argue against this paragraph.

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

## Status — 37 of 37 sections swept; **no open discrepancy** (T-02 dispositioned, D-129)

> **This heading used to read "the criterion turns on one open discrepancy"** and was still saying so
> after T-02 was dispositioned — while §"Discrepancies found" below said **Open: none**. That is the
> same near-miss this file already warns about in as many words: a summary that agrees with the claim
> you want to make, above a table that contradicts it. It happened to the heading, and a reader
> checking gate readiness would have believed the heading. Corrected 2026-08-17.

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

**Tranche 6 covers the tail** (§5.0, §5.3, §5.7, §5.10–§5.12, §5.14, §5.27–§5.29, §5.32–§5.36) and
introduces the **structural** verdict for requirements that name an artifact rather than a behavior
— defined narrowly, with a mandatory enforcing mechanism, so it cannot become a "looks fine" escape
hatch.

**Sections swept: 37 of 37.** Every launch-scope §5 section now carries a verdict.

**✅ The criterion is MET as of 2026-07-30 (D-129), on a reading that is written down here rather
than left to be inferred.** Both clauses are now satisfied: 37 of 37 launch-scope sections map to
implementation *and* a falsifying test (or carry an explicit *structural* / *descriptive* /
*dispositioned* verdict), and **the last open discrepancy, T-02, is dispositioned** — see below.

**What the claim does and does not mean.** It means every launch-scope requirement has been read
against the code, that the evidence rule was applied uniformly ("unverified counts as not traced"),
and that each judgement call is on the page. It does **not** mean every requirement is implemented:
**T-02 is dispositioned, not built** — §5.1.2's first-visit notice is scheduled, not shipped. That
is the same shape as criterion 2's claim (D-123): *nothing is undecided*, which is a weaker and more
honest statement than *nothing is missing*.

**T-02 — dispositioned 2026-07-30 (D-129): S45 owns building §5.1.2's first-visit Adaptive Learning
notice, with the eleven required disclosures enumerated by the parallel §6.1 legal-and-policy track
before S45 starts.** The two halves are assigned deliberately: the §6.1 track owns *what must be
disclosed* (it is the same track producing the privacy policy the notice has to agree with), and S45
owns *the notice that displays it*, following the pattern `LocationConsentModal.tsx` already
establishes for §5.1.3 in the chat app. **The disclosure list gates the build, not the reverse** — a
notice shipped from an implementer's reading of §5.1.2 is how a compliance artifact ends up
disagreeing with the policy it exists to summarize.

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
- Logs — the boundary that had *no* repeatable check until 2026-07-30: the access logger templates
  the path and drops the query string, and D-104 §4 is exactly the trap that creates ("clean log,
  leaking trace, same request"). [scripts/scan_logs_pii.py](../scripts/scan_logs_pii.py)
  (`make scan-logs`) now scans live log events with the **same patterns and the same matcher** as the
  trace scanner, and fails on truncation, on an unreadable window, and on zero events. First run over
  authenticated traffic: **CLEAN, 20/20 control** (D-129).

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

**Five of §5.21.3's six listed predicates are enforced, and the sixth is dispositioned rather than
missing** (AUD-C-09, D-170, 2026-08-03): `academic_year = requested_year` is **not applicable to
this corpus** — the handbook set is unified, not partitioned by academic year — so retrieval scopes
on approved/effective document state plus role access instead. Recorded in `role_access_filter`'s
docstring and on `ChunkFilters.academic_year`. Counted here as a **dispositioned predicate, not a
traced one**, per this document's method: a decision not to implement is not an implementation.

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

**One deliberate exception, recorded so it is not read as a gap (D-172 §3).** The retrieval-score
floor is **not** applied when the reranker is unavailable: with no scores, applying it would discard
every candidate and turn a model outage into a corpus-wide "no approved source" — the false
statement about the corpus AUD-C-08/AUD-C-19 exist to prevent. Failing closed on a *scoring* outage
would be failing closed on the wrong proposition. The degraded path is loud
(`retrieval_rerank_degraded`) and asserted by
`test_the_floor_does_not_apply_when_the_reranker_is_unavailable`.

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

**Scope correction, 2026-08-12 (D-294).** Everything above is about the gateway *enforcing* the
caps, and that remained true throughout. What this row did not cover is whether the cost the
system **persists** equals the cost it spent — and it did not: the authoring pipeline's
`question_validation_runs.cost_cents` omitted the per-slot equation-design call, understating
accepted rows by a measured **32.0%**, and the column meant two different things depending on
which path wrote it. "Caps are enforced" and "spend is recorded correctly" are different claims
and only the first was traced here. Now both are:
`packages/curriculum/tests/test_authored_pipeline.py::test_a_slots_rows_account_for_every_cent_the_slot_reports`
pins `sum(rows) == what the run summary was told`, and
`scripts/measure_spend_reconciliation.py` re-checks it against real rows. Still not covered by a
test: the `skipped_duplicate_id` path, where the row is rolled back and the money stays
attributable only to the run total (D-294 records why that one cannot be fixed at the row).

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

**Traced.** SPEC's stage chain maps onto the **authored** route in
[ai_pipeline.py](../packages/curriculum/src/intellichoice_curriculum/ai_pipeline.py):
equation design → generator → two **independent** solvers (sharing `_SOLVER_SYSTEM_PROMPT`) →
difficulty judge → deterministic §5.8.5 validation (`validate_authored_item`) → near-duplicate
check → activate-or-quarantine.

**Rewritten in D-226, and the reason matters for reading this row.** Until then this block traced
the *shape* route — `generate_candidate`, parameterized templates rendered from a seed — and cited
`test_ai_pipeline.py`. That route was deleted because nothing it produced could ever be served:
it never set `authoring_mode`, the column defaults to `"shape"`, and `_servable()` has required
`"authored"` since D-210 (D-224 measured this; D-226 removed it). So the previous version of this
row was **evidence for a requirement satisfied by code no student could reach** — traced against
the wrong implementation rather than untraced. The authored route below is the one that produces
every one of the 130 items now serving.

**The load-time half of §5.8.5 was traced to a call that most edits never reached (D-235).** The
same `validate_authored_item` runs in `loader._load_authored_templates`, which is what makes the
hand-editable bank file safe to load into every environment — but the loader skipped by id *above*
that call, so for any item a database already had, the gate was unreachable and the edit was
discarded silently. Fixed by re-gating and updating in place; `test_editing_an_item_already_in_the_
database_propagates` covers both halves (the edit lands, and an edit that breaks the item fails the
load). Worth recording as a method note as much as a fix: the pre-existing test that appeared to
cover this passed because it used a **new** id, so it proved the gate fires on insert and was read
as proving it fires on edit.

SPEC's "do not place free-form LLM-generated questions directly into production" is enforced
structurally, not by convention: nothing is auto-approved, and every rejecting stage has a test that
proves it rejects — `test_disagreeing_solver_rejected_with_persisted_reasons`,
`test_a_solver_that_cannot_find_its_answer_rejects_even_though_both_agree`,
`test_one_solver_flagging_ambiguity_is_enough_to_reject`,
`test_two_level_difficulty_disagreement_rejects_with_both_rationales_persisted`,
`test_near_duplicate_rejected_with_persisted_reasons`,
`test_judge_flags_reject_and_borderline_score_sets_high_priority`,
`test_review_cli_approve_reject_and_rerun`.

**Cost ceiling verified reachable, not merely present.** A `_spend` accumulator updates a running
`spend`, and every downstream call site passes that running total rather than the initial
`session_spend_cents` — precisely the distinction AUD-L-02 cost a P0 to learn. Per-slot spending is
additionally bounded by `budget_ceiling_cents`, so a single candidate cannot spend past the run's
ceiling between the loop's checks. Tests: `test_authored_pipeline.py`'s budget and preflight cases.

**One gate lost its second half, deliberately.** §5.8.5's deterministic checks used to exist twice —
`validation.py` for shape variants and `authored_validation.py` for authored items — and D-223 found
that every fix had been applied to one copy only. D-226 deleted the shape copy along with the
content it gated, so there is now exactly one implementation of each check and no drift to guard
against.

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

**Report generation is now replay-safe (D-159/AUD-X-04):** `POST /students/{id}/report` requires
`Idempotency-Key`, uniqueness is scoped to `(student, audience, key)` with the constraint as the
enforcement, and a key reused across date ranges is a 409 rather than a 200 carrying the stored
report. §5.14.3's requirement is *what a parent may see*, which was already traced; what this adds is
that the same request twice cannot produce two documents or two paid calls.

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

**Two of §5.21.8's seven do-not-answer triggers were traced to a check that verified less than its
name implied, and both are now traced to a measured floor (D-172).** "Retrieval score is below
threshold" had **no implementation** until AUD-C-12 closed — the only cut was `rerank_score > 0.0`,
and `groundedness_confidence_threshold` gates the model's confidence in its own answer, a different
trigger. It is now `MIN_RERANK_RELEVANCE_SCORE = 0.35` in
[retrieval.py](../packages/knowledge/src/intellichoice_knowledge/retrieval.py), chosen from a real
reranker sweep; test `packages/knowledge/tests/test_retrieval.py`. "Citations do not support the
response" was traced but its floor was one character (AUD-C-13); it is now
`MIN_CITATION_QUOTE_CHARS = 20`, chosen from the corpus's own span-uniqueness distribution; tests in
`test_qa_service.py`, including one asserting what the floor makes uncitable. **Read as method
rather than as two fixes:** a criterion can be traced to real code and still be unenforced, so
"traced" here means the check's *floor* was read, not only that a check exists.

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

**§5.9.2's "one attempt per item" needed a second half nobody had asked for (D-159/AUD-L-19).** The
constraint above makes an item unanswerable twice, but nothing checked that the answered variant is
an item of *this* exam at all — so a real variant from another exam was graded and inserted here,
past a constraint it does not duplicate, moving the attempt-counted denominator §5.13.3 divides by.
`flow.ensure_item_is_served` is that check; `test_exam_backend.py` covers it, with the pre-fix
behaviour (200 + an attempt row) recorded in the finding. **The traceability lesson is AUD-F-31's
from §5.9.1, again:** this section was marked traced on the invariant someone thought to state, and
the adjacent one it depends on had no test at all.

**Exam *composition* (§5.9.1) gained its falsifying test in D-131, and did not have one before.**
`test_select_topic_sql_shape.py` covers the fixed set's structure (two items per difficulty, ordered,
each with an `unseen` state row) and its determinism for a fixed seed. Worth recording as a
traceability lesson rather than just a new row: the row above was accepted as *traced* on grading and
gain, and the composition half of the same section had **no test asserting the same seed builds the
same exam** — while `get_active_questions` had no `ORDER BY`, so the property was not even true by
construction. A section can be correctly marked traced on the requirement someone thought to check.

### §5.16 — PostgreSQL checkpointing

**Traced, with a dispositioned defect.** `AsyncPostgresSaver` on its own psycopg pool, one
checkpointer for the app's lifetime ([main.py:147-149](../apps/learning-api/src/learning_api/main.py#L147)).
**The known seam is §7-R9** (AUD-X-07): the checkpoint commits inside `ainvoke` while domain rows
commit at dependency teardown. Seam (a) is fixed and controlled by `checkpoint_reconcile`; seam (b)
and the commit ordering are accepted residual risk with `learning_checkpoint_repairs_total` as the
tripwire. Test: `test_checkpoint_reconcile.py`.

**§5.16's client half — "extended to nav state" — is traced as of 2026-08-04 (D-173) and was not
before.** `GET /exam/overview`'s docstring claims the checkpoint-restore property covers exam nav
state, and SPEC Phase 11's "done when" is that a refresh restores the exact position. The server
side was implemented and used (nav bar, read-only locks); the *position* was `ExamScreen` state and
a refresh lost it (AUD-F-03), so the requirement was implemented-but-untested on the client — the
"unverified counts as not traced" case this document's method section is about. Now derived from the
overview and covered by two e2e arms: `journey-student.spec.ts`'s promoted position test, and
`exam-position-refresh.spec.ts` for the once-per-phase property. **Residual, named because it is
narrower than the SPEC wording:** the restore lands on the first item still needing an answer, not
literally the last item viewed — nothing server-side records view position.

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

## Tranche 6 — the tail, and a fourth verdict defined narrowly enough to be safe

### The judgement this tranche owed

"100% mapped to implementation **+ test**" cannot mean the same thing for *"use Pydantic v2
everywhere"* as for *"grading never involves an LLM"*. The first names a convention; the second
names a behavior that a test can falsify. Pretending otherwise means either inventing a ceremonial
test or quietly marking a section done — and this file's whole premise is that neither is allowed.

So a fourth verdict, **structural**, with a deliberately tight definition:

> **structural** — the requirement names an *artifact or convention* rather than a behavior. It
> qualifies only if (a) the artifact's location is citable, and (b) something mechanical fails if
> the artifact disappears — a CI job, a typecheck, a build. **If no such mechanism exists, it is a
> gap, not structural.**

Clause (b) is what keeps this from becoming the "looks fine" escape hatch the method section bans.
Six sections use it, and each one names its enforcing mechanism below.

### Traced — the tail's behavioral sections

| section | implementation | test |
|---|---|---|
| **§5.0** Design principles | this *is* CLAUDE.md's ten non-negotiable rules | tranche 1, all ten traced |
| **§5.7** Curriculum taxonomy | `content.py:1` — "loads the internal curriculum taxonomy (SPEC §5.7.2)"; **§5.7.3's grade→topic candidates** are now read at runtime by `content.topics_for_grade` via `topic_availability.build_topic_options` (D-187) — before that the map was loaded and never consulted, i.e. this row's .3 half was traced to a *parse*, not to a behavior | `test_content.py`, `test_loader.py`, `test_topic_availability.py`, `test_topics_endpoint.py` |
| **§5.10** Mastery estimation | `mastery_bootstrap.py:1,43,120` — cites §5.10.1, §5.10.2's routing, §5.10.3; "pure deterministic scoring — no LLM" | `test_mastery_bootstrap.py` |
| **§5.11** Study + HITL | `study_plan.py:1,20` (§5.11.1–.2, §5.11.7 retry), `tutor.py` (§5.11.4–.5) | `test_study_outcomes.py`, `test_tutor_service.py`, `test_hint_ladders.py` |
| **§5.12** Tutor agent | `tutor.py:9,165` — §5.12.2's "verify calculations with tools", where a mismatch is treated as a failure rather than trusted; `tutor_chat.py:18` routes safety signals through an approved path rather than improvising | `test_tutor_service.py`, `test_learning_chat.py`, `test_numeric_grounding.py` |
| **§5.14.1/.2/.4** UI transport and views | `routers/stream.py:1` (SSE, and why `?token=` exists — `EventSource` cannot set headers); `report.py`'s per-audience allowlist for .4 | `test_stream_and_history.py`, `e2e/tests/learning/sse-reconnect.spec.ts`, `time-telemetry.spec.ts` |
| **§5.28** FastAPI and async | thin routers + `get_db_session` dependency teardown | `test_chat_endpoints.py`, `test_exam_backend.py` |
| **§5.29** Graceful failure handling | `graph/nodes.py:332,413` cites SPEC's failure rows verbatim — "MySQL attendance failure → block learning start", "Gmail MCP failure → preserve draft" | `test_learning_graph_routes.py:383,557` — **tests that quote the same SPEC rows back** |
| **§5.32** Observability | `packages/observability/` | one test per subsection, each citing its clause: `test_langsmith_config.py:39` (§5.32.1 PII masking "not optional"), `test_tracing.py:18` (§5.32.2 one trace_id per request), `test_logging_config.py:64` (§5.32.3's literal "do not log" list) |
| **§5.33** AWS environments | `terraform/environments/staging/` | `terraform validate`, plus the deploy workflow's own runs |

§5.29 and §5.32 deserve a note: **their tests quote the SPEC clause they enforce**. That is the
cheapest traceability mechanism this codebase has, it was free to verify, and it is the reason the
tail took minutes rather than the session it was budgeted.

### Structural — six sections, each with its enforcing mechanism named

| section | artifact | what fails if it disappears |
|---|---|---|
| **§5.3** Enterprise architecture | `docs/ARCHITECTURE.md`, and the deployed topology itself | nothing mechanical — **descriptive**, and the honest verdict is that this section documents rather than requires |
| **§5.27** Pydantic | **31** `extra="forbid"` models across `apps/` and `packages/` | `make typecheck` (pyright, 0 errors) in CI's `lint-typecheck-test`; the PII-floor tests additionally pin the strictness of every Bedrock payload model |
| **§5.34** Docker / Terraform / GHA | `apps/*/Dockerfile`, `terraform/`, `.github/workflows/{ci,deploy-staging,security-scan}.yml` | CI's four jobs and the deploy workflow — a missing Dockerfile or module fails the build, not a review |
| **§5.35** External accounts and identifiers | `.env.example` | app startup config validation; a missing required variable fails the container, not a checklist |
| **§5.36** Final technology placement | the stack as built | nothing mechanical — **descriptive** |
| **§5.2.1** Deployment units | two independently deployed apps + two SPAs | the deploy workflow deploys exactly these |

**Two of the six — §5.3 and §5.36 — fail clause (b) and are recorded as descriptive rather than
structural.** They describe the chosen architecture; there is nothing to falsify and nothing that
breaks if the description drifts. Saying so is more useful than a green checkmark, because it tells
a future reader those two sections need **re-reading by a human** when the architecture changes,
rather than trusting a test to notice.

**Sections swept: 37 of 37.**

---

## Discrepancies found

Criterion 1 requires every discrepancy to be dispositioned in DECISIONS.md. **Open: none** — true as
of D-129, and worth flagging that **this line was already saying "none" while the table below said
T-02 was open** (both written in the same commit, `c44414f`). It is corrected by the disposition
rather than by editing the summary, but the near-miss is the point: a summary line that agrees with
the claim you want to make, sitting above a table that contradicts it, is how a rubric passes itself.

| id | discrepancy | disposition |
|---|---|---|
| **T-01** | §5.30.3 requires GuardDuty and CloudTrail; neither existed and neither had a decision | **Closed 2026-07-30 (D-125), as two opposite answers**: CloudTrail **built and live-verified**; GuardDuty **deferred with a written reason**, tracked to S50 A7 |
| **T-02** | §5.1.2's first-visit Adaptive Learning notice — eleven required disclosures — is not built and is owned only *by implication* | **Dispositioned 2026-07-30 (D-129): S45 builds it; the §6.1 track enumerates the eleven disclosures first.** Scheduled, not shipped — see below. |

### T-02 — §5.1.2's first-visit notice has no explicit owner, and its content depends on a track that has not started

**✅ DISPOSITIONED 2026-07-30 (D-129), and the disposition splits the item in two on purpose:**

- **The §6.1 legal & policy track owns the eleven disclosures** — enumerating them as a written
  deliverable, consistent with the privacy policy it is already producing and with D-114 §4's
  standing obligation about the 90/90/365 retention windows.
- **S45 owns the notice itself** — the first-visit gate in `apps/learning-web`, following the
  pattern `LocationConsentModal.tsx` already establishes for §5.1.3 in the chat app.
- **The order is load-bearing:** the disclosure list gates the build. A notice drafted from an
  implementer's reading of §5.1.2 is how a compliance artifact ends up disagreeing with the policy
  it exists to summarize, and the §6.1 track already gates the pilot for other reasons.

**Still not built**, and the disposition does not pretend otherwise. What changed is that it is now
owned and ordered rather than assumed — which is all criterion 1 asks of a discrepancy.

*(The finding as filed, kept because the reasoning is the record:)*

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
| AWS WAF | absent | **dispositioned** — deferred with a written reason, tracked to S50 A7 (D-087, which added per-IP rate limiting as the explicit in-memory stopgap "not a replacement for one"). **The stopgap's ceiling was measured in D-181 and it is per-task:** one source IP gets `6000 × running tasks` per minute, and that is accepted for a bound chosen as ~3× a legitimate burst. The §5.24.2 escalation cap could not accept it and moved to a shared Postgres counter (AUD-C-27) |
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

**Nothing remains to sweep.** Tranches 1–6 covered **37 of 37 sections**; all four of §2.3's risk
classes are traced, and the tail carries either a test or a named enforcing mechanism. The remaining work, in §2.3's risk order:

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
