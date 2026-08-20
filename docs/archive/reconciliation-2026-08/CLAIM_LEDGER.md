> **ARCHIVED 2026-08-20.** Point-in-time audit evidence (reconciliation, 2026-08-19/20) — **do not treat as current state.**
> **Current state:** `docs/PROJECT_STATE.md`
> **Reason:** Phase-2 claim ledger — the ~70 extracted claim rows with their sources, temporal notes and candidate statuses, as read on 2026-08-19. **Superseded by:** the 166-entry register at `docs/reference/reconciliation-2026-08/FINAL_OPEN_WORK_REGISTER.md`.

# Claim Ledger — Phase 2 of the Documentation Reconciliation Migration

**Date:** 2026-08-19
**Purpose:** extract the material project knowledge from the original documentation before any
compression or migration occurs. Every claim below was extracted from the **original documents as
primary evidence** by domain-focused readers and assembled/cross-checked by the orchestrating
session; Phase 1's inventory and risk register were used only as leads, and material Phase 1
assertions were re-verified against sources (see §10 of the companion
[DECISION_SUPERSESSION_MAP.md](DECISION_SUPERSESSION_MAP.md) and the closing report).

**How to read a claim.**
- *Type* distinguishes what kind of statement it is; per the phase rules, a recommendation is not
  a decision, a plan is not completed work, an audit observation is not automatically current
  state, and implementation mentioned in documentation is not verified implementation.
- *Candidate status* is this ledger's judgment of the claim's temporal standing:
  CURRENT / HISTORICAL / SUPERSEDED / DEFERRED / UNKNOWN. It is a candidate — Phase 3's
  observed-code verification may change it.
- *Evidence still required* names what Phase 3 must verify before the claim can be relied on as
  fact about the running system. Claims whose sources are documentation-of-implementation are
  systematically marked this way, however confident the prose.
- Audit finding IDs are **source-qualified** where ambiguous (`AUD-L-01 [AUDIT_FINDINGS]` vs
  `AUD-L-01 [AUDIT_LIVE_2026_08_17]`) — the two audit registers reuse the same ID range for
  unrelated findings, and a bare ID must never be treated as uniquely identifying one finding.

**Claim ID prefixes / sections:**
§1 REQ (requirements, LLM behavior, HITL, deterministic core, failure handling) ·
§2 ARCH (architecture, infrastructure, deployment, operational, egress) ·
§3 SEC (security, privacy, authorization, data boundaries, incidents) ·
§4 COST (cost controls, observability, alerting, spend accounting) ·
§5 TEST (testing, traceability, audit state, verification method) ·
§6 INT (integration, D-152 freeze, production facts, org communications) ·
§7 WORK (active work, open items, parked work, known limitations, user decisions) ·
§8 cross-cutting contradiction index · §9 Phase 3 verification queue · §10 counts.

**Do-not-merge note.** Deliberately-similar claims are kept separate where their type or temporal
standing differs (e.g. REQ-21 the image-deletion *requirement* vs REQ-22 the D-078 *deferral
decision* vs SEC-15 the traceability *disposition*; ARCH-04 the scheduled-jobs claim vs ARCH-06
the surviving contradicting "manual trigger" text). Cross-references between them are recorded in
each block and in §8.

---

## §1 — Requirements, LLM behavior, HITL, deterministic core, failure handling (REQ-01…REQ-52)

### REQ-01 — No PII in Postgres, logs, traces, or LLM payloads
- Domain: product requirements
- Claim: Postgres stores only `*_external_id` references and no PII (names, emails, roles, relationships, attendance) may appear in Postgres, logs, traces, or LLM payloads; the org's MySQL remains sole source of truth for that data.
- Type: invariant
- Sources: CLAUDE.md:88–90; docs/SPEC.md:23–24 (§5.0), SPEC.md:559 (§5.5.3 "Names and email addresses are not stored in graph state")
- Related IDs: SPEC §5.4, §5.30.1; D-104; D-129
- Temporal: SPEC-original; log-boundary check first clean run 2026-07-30 (D-129)
- Candidate status: CURRENT
- Intended vs observed: both (intended in SPEC/CLAUDE.md; claimed observed in TRACEABILITY)
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `packages/db/tests/test_schema_purity.py::test_no_model_has_a_pii_column_name`, `packages/shared/tests/test_bedrock_payload_pii_floor.py`, `packages/observability/tests/test_tracing.py:62`, and `scripts/scan_logs_pii.py` exist and pass.
- Confidence: HIGH — stated identically in two independent docs.

### REQ-02 — PII floor must be enforced at four separate boundaries, not one
- Domain: deterministic-core guarantees
- Claim: TRACEABILITY claims the PII floor is enforced at four distinct boundaries (Postgres schema, LLM payload models with `extra="forbid"`, a `RedactingSpanExporter` at trace export, and access-log templating plus a log scanner), each with its own test, because a floor at one store does not transfer to another (D-104).
- Type: observed-state
- Sources: docs/TRACEABILITY.md:126–153
- Related IDs: D-104, D-129
- Temporal: as of TRACEABILITY tranche-1 writing; log scan first clean run 2026-07-30
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm each named file/test exists, that `make scan-logs` runs, and that the trace test's negative arm and vacuity guard (lines 91/100) are real.
- Confidence: MEDIUM — documentation asserts implementation; not independently verified here.

### REQ-03 — Deterministic core: no LLM in grading, gating, authz, scoring, or SQL
- Domain: deterministic-core guarantees
- Claim: Attendance verification, authorization, score/gain calculation, multiple-choice grading, and SQL execution are performed deterministically and never by an LLM; LLMs are confined to language tasks (explanation, intent classification, summarization, template generation).
- Type: invariant
- Sources: CLAUDE.md:91–92; docs/SPEC.md:25–26 (§5.0); SPEC.md:531 (§5.5.2 "Do not turn every node into an agent…")
- Related IDs: SPEC §5.0, §5.26
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `grading.py`, `exam_policy.py`, `learning_gain.py`, `mastery_bootstrap.py`, `study_plan.py` under `apps/learning-api/src/learning_api/services/` contain no model call, and that `test_exam_flow_determinism.py` exists and passes.
- Confidence: HIGH — restated in three places.

### REQ-04 — Multiple-choice grading is a literal equality comparison
- Domain: deterministic-core guarantees
- Claim: Grading is `selected_option == correct_option` with no LLM involvement, and the stored record set is fixed (student_external_id, assessment_session_id, question_variant_id, selected_option, correct_option, is_correct, response_time_ms, submitted_at).
- Type: requirement
- Sources: docs/SPEC.md:1035–1056 (§5.9.3)
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the grading service implements exact comparison and persists exactly these fields.
- Confidence: HIGH — explicit SPEC text.

### REQ-05 — No runtime NL2SQL; structured output selects an approved repository function
- Domain: deterministic-core guarantees
- Claim: SQL must not be generated from ordinary user requests; a natural-language request becomes a `QueryIntent` Pydantic model that selects one of a fixed set of predefined repository methods, and the LLM never produces raw SQL.
- Type: requirement
- Sources: docs/SPEC.md:2597–2650 (§5.26.1–§5.26.2)
- Related IDs: CLAUDE.md:92
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm no NL2SQL code path exists at runtime and repository methods are parameterized with row-level authorization and query timeouts.
- Confidence: HIGH — explicit.

### REQ-06 — Internal NL2SQL is permitted only for dev/eval/analytics under twelve controls
- Domain: deterministic-core guarantees
- Claim: NL2SQL may be used for development, evaluation, and internal analytics only, gated by a plan→allowlist→parser→read-only-role→EXPLAIN→timeout→row-limit pipeline plus twelve controls (SELECT-only, table/column allowlists, PII-column prohibition, mandatory LIMIT, SQLGlot-class parser, full audit log); constrained decoding is explicitly stated not to enforce authorization or prevent leakage.
- Type: requirement
- Sources: docs/SPEC.md:2652–2690 (§5.26.3)
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: UNKNOWN — TRACEABILITY:161–164 states "No runtime NL2SQL exists to test for" and that ROADMAP S30's SQL-parser validation was not built because there is no NL2SQL feature; whether the internal variant is intended-later or abandoned is not stated.
- Intended vs observed: intended-state
- Contradicts/competes: docs/TRACEABILITY.md:161–164 (no NL2SQL feature exists) vs SPEC.md:2652 (prescribes an internal one).
- Evidence still required: Phase 3: determine whether internal NL2SQL is planned, dropped, or partially present; check ROADMAP/DECISIONS for a disposition.
- Confidence: MEDIUM — SPEC text clear, status ambiguous.

### REQ-07 — Authorization lives in the backend/query layer, never in prompts
- Domain: deterministic-core guarantees
- Claim: Parent-child links are verified server-side and role/branch filters are applied as query predicates *before* RAG retrieval, never as prompt instructions.
- Type: invariant
- Sources: CLAUDE.md:93–95; docs/TRACEABILITY.md:167–178
- Related IDs: SPEC §5.21.3, §5.30.2; AUD-C-09, D-170
- Temporal: rule SPEC-original; predicate disposition 2026-08-03 (D-170)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `packages/db/src/intellichoice_db/repositories/rag.py:34-43` applies status/audience/effective-window/branch predicates in SQL, and that `test_rag_search.py` / `test_role_access.py` pass.
- Confidence: HIGH — two sources agree.

### REQ-08 — Five of six §5.21.3 retrieval predicates enforced; `academic_year` dispositioned not implemented
- Domain: deterministic-core guarantees
- Claim: `academic_year = requested_year` is deliberately not implemented because the handbook corpus is unified rather than year-partitioned; it is counted as a dispositioned predicate, explicitly not a traced implementation.
- Type: decision
- Sources: docs/TRACEABILITY.md:174–179
- Related IDs: AUD-C-09, D-170
- Temporal: decided 2026-08-03
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: SPEC §5.21.3 lists six predicates — the SPEC text as written still requires it.
- Evidence still required: Phase 3: confirm the disposition is recorded in `role_access_filter`'s docstring and on `ChunkFilters.academic_year`, and read SPEC §5.21.3 to confirm the six-predicate list.
- Confidence: MEDIUM — asserted only by TRACEABILITY.

### REQ-09 — Open authorization hole: `resolve_target_student` unchecked for tutor and branch_manager
- Domain: failure handling
- Claim: `resolve_target_student` returns the requested student id unchecked for tutor and branch_manager roles; this is an accepted residual risk expiring at first real traffic, and §5.30.2's authorization matrix is therefore not fully enforced.
- Type: audit-finding
- Sources: docs/TRACEABILITY.md:180–185
- Related IDs: §7-R8, AUD-L-07 [AUDIT_FINDINGS], D-123
- Temporal: accepted as of D-123; expiry condition "first real traffic"
- Candidate status: CURRENT (open)
- Intended vs observed: observed-state
- Contradicts/competes: CLAUDE.md:93 states authorization is verified server-side as a non-negotiable — this is a live exception to rule 3. See SEC-09, INT-33.
- Evidence still required: Phase 3: locate `resolve_target_student`, confirm the hole is still present, and check whether real traffic has begun (which would make the acceptance expired).
- Confidence: HIGH — explicitly self-reported as a gap.

### REQ-10 — Every external action requires `interrupt()` approval; six enumerated actions
- Domain: HITL behavior
- Claim: Explicit human approval via LangGraph `interrupt()` is required before sending an attendance-verification email to a branch manager, sending a question to an administrator, creating a Google Calendar event, using the user's location, analyzing an uploaded solution image, or including potentially sensitive information in an email.
- Type: requirement
- Sources: docs/SPEC.md:126–137 (§5.1.4); CLAUDE.md:96–97
- Related IDs: SPEC §5.1.4
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: The image-analysis action cannot be exercised — the image feature does not exist (REQ-22/REQ-23). CLAUDE.md:96 lists four action classes vs SPEC's six items.
- Evidence still required: Phase 3: confirm `respond_to_interrupt` (`apps/learning-api/.../routers/sessions.py:1120`) and `_pending_task_interrupt` (line 414) exist, and that `test_learning_graph_routes.py`, `test_calendar_action.py`, `test_admin_escalation.py` pass; confirm the "sensitive info in email" case is actually gated.
- Confidence: HIGH — explicit in both.

### REQ-11 — Child selection and post-incorrect intervention are also interrupt points
- Domain: HITL behavior
- Claim: Beyond external actions, the learning graph interrupts for parent multi-child selection and after every incorrect answer to let the student choose hint / solution / video.
- Type: requirement
- Sources: docs/SPEC.md:456–460 (§5.5.1); SPEC.md:1183–1194 (§5.11.3)
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm both interrupts exist in the graph and are resumable through the same endpoint.
- Confidence: HIGH — explicit in the workflow diagram and flow.

### REQ-12 — Fail closed: unknown attendance is not present
- Domain: failure handling
- Claim: Attendance is read live from MySQL at session start and resolves to Present / Absent / Unknown; `present` must not be assumed when MySQL is unavailable, and the session cannot begin until attendance is confirmed.
- Type: invariant
- Sources: docs/SPEC.md:420–444 (§5.4.4); CLAUDE.md:98–99
- Related IDs: SPEC §5.4.4, §5.29; D-152 §2
- Temporal: SPEC-original; production-frequency note D-152 (CLAUDE.md:73–75)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `check_attendance_gate` (`services/attendance.py:71-80`) opens only on `AttendanceStatus.PRESENT` and `test_auth_and_attendance.py` passes.
- Confidence: HIGH — explicit.

### REQ-13 — `AttendanceStatus.UNKNOWN` → blocked is a routine production path, not an edge case
- Domain: product requirements
- Claim: In the existing production system `signups.attended = null` ("manager hasn't marked it yet") is common, so the UNKNOWN→blocked path is routine, not rare — this must inform product work now even though integration is deferred.
- Type: observed-state
- Sources: CLAUDE.md:73–75
- Related IDs: D-152 §2, D-151, docs/S42_DISCOVERY.md
- Temporal: read from production source per D-151/D-152
- Candidate status: CURRENT
- Intended vs observed: observed-state (of the external production system)
- Contradicts/competes: none found — but it materially raises the UX cost of REQ-12's hard block. See INT-23.
- Evidence still required: Phase 3: confirm the Attendance Resolution path is built and reachable, and that S42_DISCOVERY documents the `attended = null` finding.
- Confidence: HIGH — stated as the one production fact that must inform work now.

### REQ-14 — Fail closed in RAG: no answer without an approved, effective, citation-supported source
- Domain: failure handling
- Claim: The Q&A app must not answer from unapproved, out-of-effective-window, or uncited sources; no RAG result means "do not guess; offer escalation", and conflicting sources mean surface the conflict and offer escalation.
- Type: invariant
- Sources: CLAUDE.md:98–99; docs/SPEC.md:2795–2796 (§5.29 rows)
- Related IDs: SPEC §5.21.8, §5.29; AUD-C-08 [AUDIT_FINDINGS], AUD-C-19 [AUDIT_FINDINGS]
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `apps/chat-api/tests/test_qa_coverage_eval.py` covers the no-citation refusal.
- Confidence: HIGH — consistent across CLAUDE.md, SPEC §5.29, and §5.19.5 reason codes.

### REQ-15 — The one recorded fail-closed exception: retrieval-score floor is skipped when the reranker is down
- Domain: failure handling
- Claim: The retrieval-score floor is deliberately not applied when the reranker is unavailable, because with no scores the floor would discard every candidate and turn a model outage into a corpus-wide "no approved source" — a false statement about the corpus; the degraded path emits `retrieval_rerank_degraded`.
- Type: decision
- Sources: docs/TRACEABILITY.md:203–210
- Related IDs: D-172 §3, AUD-C-08 [AUDIT_FINDINGS], AUD-C-19 [AUDIT_FINDINGS]
- Temporal: decided 2026-08-04 (D-172)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: Reads as an exception to CLAUDE.md:98's blanket "fail closed"; TRACEABILITY frames it as failing closed on the right proposition rather than a violation.
- Evidence still required: Phase 3: confirm `test_the_floor_does_not_apply_when_the_reranker_is_unavailable` exists and passes, and that the degraded signal is actually emitted/alertable.
- Confidence: HIGH — explicitly recorded as the single exception.

### REQ-16 — Structured output → Pydantic → bounded repair → deterministic fallback
- Domain: LLM behavior
- Claim: All LLM output must be JSON-schema structured, validated by Pydantic; invalid output gets a limited retry then a deterministic fallback, and an invalid tool call is never executed.
- Type: invariant
- Sources: docs/SPEC.md:2570–2592 (§5.25.3); SPEC.md:2716 (§5.27); CLAUDE.md:100–101
- Related IDs: SPEC §5.25.3, §5.27
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `_validate_or_repair` in `packages/adapters/.../bedrock/gateway.py:270-285,419` bounds the repair and distinguishes `schema_invalid` from `output_truncated`; confirm `test_bedrock_gateway.py` passes.
- Confidence: HIGH — three sources agree.

### REQ-17 — Thirteen artifact types must use JSON Schema
- Domain: LLM behavior
- Claim: JSON Schema is required for intent, topic mapping, question template, hint, solution, tutor response, parent report, semantic-memory update, calendar event, email draft, RAG answer, citation, and evaluation result.
- Type: requirement
- Sources: docs/SPEC.md:2553–2568 (§5.25.3 list)
- Related IDs: SPEC §5.27 (Pydantic at every boundary, SPEC.md:2693–2705)
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm a Pydantic model exists per artifact type and that each is actually used at its boundary.
- Confidence: HIGH — enumerated list.

### REQ-18 — Measured ~2–4% `rag_answer` schema-invalid rate, invalid text not captured
- Domain: LLM behavior
- Claim: The `rag_answer` structured-output path has a measured ~2–4% `schema_invalid` rate; the invalid text is deliberately not captured pending a PII decision, so the failures cannot currently be diagnosed.
- Type: open-work
- Sources: docs/TRACEABILITY.md:218–220
- Related IDs: carried in docs/PROGRESS.md
- Temporal: as of TRACEABILITY tranche-1 writing
- Candidate status: CURRENT (open)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the rate in PROGRESS.md, whether a PII decision has since been made, and whether capture is now enabled.
- Confidence: MEDIUM — a single self-reported measurement with no cited instrument.

### REQ-19 — All paid model calls go through a gateway with timeouts, bounded retries, caps, cost accounting
- Domain: LLM behavior
- Claim: Every model/paid-API call must route through `BedrockGateway`, which provides timeouts, bounded retry, max-token ceiling, per-session cost budget, circuit breaker, PII redaction, guardrails, model versioning, and a pre-flight `worst_case_cost_cents` reservation.
- Type: invariant
- Sources: docs/SPEC.md:2515–2540 (§5.25.1); CLAUDE.md:102–103; docs/TRACEABILITY.md:221–232
- Related IDs: D-022, D-078, D-294
- Temporal: SPEC-original; four of six interface methods dispositioned in code
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: SPEC §5.25.1 lists six gateway methods; TRACEABILITY:225–228 says only `generate_structured` and `create_embedding` exist (`generate_stream`/`classify` no caller per D-022, `analyze_image` deferred per D-078, `judge` dispatched through `generate_structured`). SPEC's six-method interface as written = SUPERSEDED-in-part by D-022/D-078.
- Evidence still required: Phase 3: confirm which gateway methods exist, that the eval judge calls `generate_structured` (`packages/evals/.../llm_judge.py:64`), and that the cost-reservation tests pass.
- Confidence: HIGH — competing statements both explicit.

### REQ-20 — Recorded cost understated by 32.0%; "caps enforced" ≠ "spend recorded correctly"
- Domain: failure handling
- Claim: The authoring pipeline's `question_validation_runs.cost_cents` omitted the per-slot equation-design call, understating accepted rows by a measured 32.0%, and the column meant different things depending on the writing path; the `skipped_duplicate_id` path remains untested and unattributable at row level.
- Type: audit-finding
- Sources: docs/TRACEABILITY.md:238–249
- Related IDs: D-294
- Temporal: scope correction 2026-08-12
- Candidate status: CURRENT (partially remediated; one path still uncovered)
- Intended vs observed: observed-state
- Contradicts/competes: Competes with the earlier framing of rule 7 as fully "traced" — TRACEABILITY itself says only the caps half was traced. See COST-05/COST-06.
- Evidence still required: Phase 3: confirm `test_a_slots_rows_account_for_every_cent_the_slot_reports` and `scripts/measure_spend_reconciliation.py` exist and pass, and that the `skipped_duplicate_id` gap is still open.
- Confidence: HIGH — explicit, with a measured number.

### REQ-21 — Solution images deleted immediately, never in backups/traces/logs
- Domain: product requirements
- Claim: Uploaded solution images must be deleted immediately after analysis (success or failure), must not enter the long-term RAG bucket, versioned S3, backups, or LangSmith traces (including Base64), with filename/metadata logging minimized; a lifecycle rule is a final safeguard, not the primary deletion mechanism, and only extracted equations and error steps may be retained.
- Type: requirement
- Sources: docs/SPEC.md:1736–1754 (§5.17.2); SPEC.md:1727; SPEC.md:27; CLAUDE.md:104–105
- Related IDs: SPEC §5.17
- Temporal: SPEC-original
- Candidate status: DEFERRED — the requirement stands as written but has no subject; competing source is D-078 (docs/DECISIONS.md:2025) and docs/TRACEABILITY.md:250–253.
- Intended vs observed: intended-state
- Contradicts/competes: docs/TRACEABILITY.md:250–253 — "Dispositioned — the feature does not exist"; CLAUDE.md:104 states the rule as if active. See REQ-22, SEC-14/SEC-15.
- Evidence still required: Phase 3: confirm no image path exists anywhere (no `BlobStore`, `MalwareScanner`, `analyze_image`, upload router).
- Confidence: HIGH — requirement text is explicit.

### REQ-22 — Multimodal image feature deferred by user decision; nothing was built
- Domain: product requirements
- Claim: S29 (multimodal solution images) was declined by the user before any file was touched; a design was drafted but nothing exists — no `BlobStore`, `MalwareScanner`, `BedrockGateway.analyze_image`, upload router, executable math validator, or `"image"` intervention choice — and the rule 8 requirement re-opens the moment §5.17 is built.
- Type: decision
- Sources: docs/DECISIONS.md:2025–2041; docs/TRACEABILITY.md:250–253
- Related IDs: D-078, D-002, D-020
- Temporal: accepted 2026-07-20
- Candidate status: CURRENT (the deferral is current), feature DEFERRED
- Intended vs observed: observed-state
- Contradicts/competes: SPEC §5.17 and CLAUDE.md:104 present image handling as active product behavior; SPEC §5.1.4 lists image analysis as an interrupt-gated action.
- Evidence still required: Phase 3: grep for the five named absent artifacts to confirm none has since appeared; confirm ROADMAP S29 is marked deferred-not-deleted.
- Confidence: HIGH — decision text is unambiguous and enumerates absences.

### REQ-23 — Two unresolved preconditions gate any future image work
- Domain: product requirements
- Claim: Before §5.17 is built, two questions must be resolved first: (1) a K-12 minor's solution photo can incidentally capture a face, other homework, or a home background — a privacy question the consent language and storage policy assume away rather than answer, including whether parent-level opt-in is needed; (2) every supporting dependency (real malware scanner, real S3 encryption-at-rest) is still on D-002's "no real creds" footing.
- Type: open-work
- Sources: docs/DECISIONS.md:2032–2049
- Related IDs: D-078, D-002
- Temporal: recorded 2026-07-20
- Candidate status: CURRENT (open)
- Intended vs observed: intended-state
- Contradicts/competes: SPEC §5.1.2's disclosure "Uploaded solution images are deleted immediately after analysis" would be a promise about a feature whose privacy model is unresolved.
- Evidence still required: Phase 3: confirm no decision has since resolved the incidental-capture question (check OPEN_DECISIONS.md).
- Confidence: HIGH — explicit in D-078.

### REQ-24 — Image analysis never determines score
- Domain: deterministic-core guarantees
- Claim: Because assessment is multiple-choice, image analysis cannot affect the score; it may only identify the incorrect step, generate better hints, and extract misconception tags, while the selected multiple-choice option determines the score.
- Type: requirement
- Sources: docs/SPEC.md:1756–1770 (§5.17.3)
- Related IDs: D-078 (feature not built)
- Temporal: SPEC-original
- Candidate status: DEFERRED — depends on an unbuilt feature.
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: none while the feature is absent; re-check if §5.17 is built.
- Confidence: HIGH — explicit.

### REQ-25 — Eleven first-visit disclosures required on `learning.intellichoice.org`
- Domain: product requirements
- Claim: The first visit to the learning app must present a product-specific notice disclosing eleven items (AI analyzes answers/history; AI hints may err; AI does not replace a tutor; exam results adjust estimated level; limited sharing with tutors/branch managers; parents see the complete record; learning memory is created; uploaded solution images are deleted immediately after analysis; YouTube recommendations; external data minimized/de-identified; right to challenge results or report questions).
- Type: requirement
- Sources: docs/SPEC.md:96–110 (§5.1.2)
- Related IDs: T-02, D-129
- Temporal: SPEC-original
- Candidate status: CURRENT (unbuilt)
- Intended vs observed: intended-state
- Contradicts/competes: The image-deletion disclosure describes a feature that does not exist (D-078) — the notice as specified would state something untrue.
- Evidence still required: Phase 3: confirm no first-visit notice component exists in the learning frontend and that the disclosure list has not been amended.
- Confidence: HIGH — enumerated in SPEC.

### REQ-26 — First-visit notice is unbuilt: S45 owns the component, the §6.1 track owns the disclosure list
- Domain: product requirements
- Claim: T-02 is dispositioned, not traced: S45 will build the notice, but the §6.1 legal-and-policy track must first enumerate the required disclosures; the disclosure list gates the build and not the reverse, following the `LocationConsentModal.tsx` pattern already used for §5.1.3.
- Type: plan
- Sources: docs/TRACEABILITY.md:113–122
- Related IDs: T-02, D-129, SPEC §5.1.2, §6.1
- Temporal: dispositioned 2026-07-30
- Candidate status: CURRENT (planned, not done)
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm S45 has not run, that `LocationConsentModal.tsx` exists in the chat app, and that §6.1 has not yet produced the list.
- Confidence: HIGH — explicitly framed as a disposition, not an implementation.

### REQ-27 — A student notice is not a substitute for parental consent under 13
- Domain: product requirements
- Claim: The learning app must not use a student-facing notice in place of parental consent for users under 13; it must verify `parental_consent_verified=true` from the existing auth system and only then show an age-appropriate student notice. The auth token must carry at least sub, role, account_status, consent_status, parental_consent_verified, consent_version, student_age_band, issued_at, expires_at, audience.
- Type: requirement
- Sources: docs/SPEC.md:112–128 (§5.1.2)
- Related IDs: D-152, SPEC §3.1
- Temporal: SPEC-original
- Candidate status: UNKNOWN — the token contract depends on the frozen production system; CLAUDE.md:58–62 forbids finalizing the §3.1 auth option before S44.
- Intended vs observed: intended-state
- Contradicts/competes: CLAUDE.md:58–62 defers the auth contract; whether production actually issues these ten claims is unverified. Production's own token is `{id, iat, exp}` only (see INT-32) — the claim set must be minted by the new stack.
- Evidence still required: Phase 3: check S42_DISCOVERY.md for which claims production's JWT actually carries, and whether any gate reads `parental_consent_verified`.
- Confidence: MEDIUM — requirement explicit, satisfiability unverified.

### REQ-28 — Location consent: precise coordinates discarded, never stored
- Domain: product requirements
- Claim: Before the Branch Locator, a specific consent string must be shown; browser geolocation is requested only after explicit permission, precise coordinates are discarded after the Maps MCP request completes and must not be stored in PostgreSQL, MySQL, LangSmith, or application logs; ZIP/city/address entry must be offered and the raw manual address not retained by default.
- Type: requirement
- Sources: docs/SPEC.md:130–147 (§5.1.3)
- Related IDs: SPEC §5.1.4
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `LocationConsentModal.tsx` implements the copy and that `ephemeral_location` in `QAState` is not persisted or traced.
- Confidence: HIGH — explicit.

### REQ-29 — Seven prohibited data uses
- Domain: product requirements
- Claim: Prohibited: selling student data; behavioral advertising to students; using scores or weaknesses for marketing; unauthorized model training on student data; retaining images for facial recognition; retaining precise location history; sending email or creating calendar events without approval; exposing complete chat transcripts to tutors or branch managers.
- Type: invariant
- Sources: docs/SPEC.md:149–163 (§5.1.5)
- Related IDs: SPEC §5.1.4
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the tutor/manager summary path shares only scores and skill summaries and never transcripts.
- Confidence: HIGH — explicit prohibition list.

### REQ-30 — Legal review is a mandatory production release gate
- Domain: product requirements
- Claim: Because minors across the U.S. are the primary users, the org must evaluate COPPA (as amended by the FTC on 2025-04-22), FERPA, PPRA, state student-privacy and consumer-privacy laws, breach-notification laws, and school contractual obligations; the SPEC's legal sections are product requirements not legal advice, and review by U.S. education and child-privacy counsel is a mandatory production release gate.
- Type: requirement
- Sources: docs/SPEC.md:38–78 (§5.1.1)
- Related IDs: SPEC §6.1
- Temporal: SPEC-original; cites FTC COPPA amendment of 2025-04-22
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm no counsel review has occurred and that the gate is represented in the launch checklist.
- Confidence: HIGH — stated as mandatory.

### REQ-31 — Retry/intervention ladder: four escalating steps and six terminal outcomes
- Domain: HITL behavior
- Claim: On 1st incorrect attempt the student chooses hint/solution/video; 2nd → recommend more explicit support; 3rd → an easier prerequisite problem; 4th unresolved → mark for tutor review and continue. Final outcomes are exactly `independent_correct`, `correct_after_hint`, `correct_after_video`, `correct_after_solution`, `answer_revealed`, `unresolved`.
- Type: requirement
- Sources: docs/SPEC.md:1265–1290 (§5.11.7)
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the intervention router implements four steps and that the six outcome labels are the actual persisted enum.
- Confidence: HIGH — explicit ladder.

### REQ-32 — Hints must never reveal the answer; `answer_revealed = false` is part of the schema
- Domain: LLM behavior
- Claim: The `HintResponse` structured schema carries `answer_revealed = false` alongside hint_text, concept_reminder, next_step_prompt, and difficulty; the Tutor Agent must not reveal the answer immediately, must not fabricate sources or videos, must not reveal system prompts or student PII, must verify calculations with tools, and must route self-harm/abuse/safety signals through a separately approved safety policy.
- Type: requirement
- Sources: docs/SPEC.md:1213–1231 (§5.11.4); SPEC.md:1314–1330 (§5.12.2)
- Related IDs: Bedrock Guardrails (SPEC.md:1327–1329); docs/HINT_SOLUTION_REVIEW.md (D-251, planned)
- Temporal: SPEC-original
- Candidate status: CURRENT; the "separately approved safety policy" is UNKNOWN — SPEC names it without defining it
- Intended vs observed: intended-state
- Contradicts/competes: CLAUDE.md:31–35 says the LLM hint/solution review instrument (D-251) is **planned**, not built, and that two prior hint-quality scorers already failed.
- Evidence still required: Phase 3: confirm `HintResponse` exists with `answer_revealed`, whether Bedrock Guardrails are configured, and whether any approved safety policy for self-harm/abuse routing exists at all.
- Confidence: MEDIUM — guardrail list explicit but the safety-policy referent is undefined.

### REQ-33 — Correct-after-solution is not independent mastery
- Domain: deterministic-core guarantees
- Claim: A correct answer given after the student has seen the full solution must be recorded as `correct_after_solution` and must not count as independent mastery.
- Type: invariant
- Sources: docs/SPEC.md:1246–1252 (§5.11.5)
- Related IDs: SPEC §5.11.7 outcomes; §5.13.3 solution dependency
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the mastery service excludes `correct_after_solution` from independent-mastery updates.
- Confidence: HIGH — explicit.

### REQ-34 — Video is served from a local pre-synced catalog; never a real-time YouTube call
- Domain: failure handling
- Claim: YouTube must not be called in real time; the video intervention searches a local pre-synchronized catalog (metadata filter then semantic search) and returns only an approved Khan Academy video, with an explicit fallback message offering hint or solution when none exists; a sync failure keeps the last valid catalog.
- Type: requirement
- Sources: docs/SPEC.md:1254–1263 (§5.11.6); SPEC.md:2792–2793 (§5.29 rows)
- Related IDs: SPEC §5.18
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm no runtime YouTube call exists in the intervention path and that the providers are sync-time only.
- Confidence: HIGH — explicit prohibition.

### REQ-35 — Study plan is rule + statistical with a seven-rule selection priority
- Domain: deterministic-core guarantees
- Claim: Each topic gets exactly five base study questions (`base_problem_count = 5`) with remediation tracked separately; question selection follows a fixed seven-rule priority (lowest-mastery skill, difficulty matching estimated level, within ±1, template unused this session, same skill as recent error, prerequisite requirement, not quarantined) and the Study Planner is "Rule + statistical", not an LLM.
- Type: requirement
- Sources: docs/SPEC.md:1150–1181 (§5.11.1–§5.11.2); SPEC.md:521 (§5.5.2)
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: ROADMAP:2320 records "A departure from SPEC, recorded not buried" on the §5.11.2 priority order — Phase 3 must read which departure.
- Evidence still required: Phase 3: confirm `study_plan.py` implements the priorities and has no model call; read the recorded departure.
- Confidence: HIGH for the SPEC text; the as-built order is MEDIUM.

### REQ-36 — Learning gain is owned by a deterministic service with three named formulas
- Domain: deterministic-core guarantees
- Claim: The Learning Gain Service is deterministic and compares pre- and post-exam; `Raw Gain = Post Score − Pre Score`, `Normalized Gain = (Post − Pre) / (Maximum − Pre)`, and when the pre-exam is already perfect the result must be `normalized_gain_status = not_applicable_pre_max`; twelve gain metrics must be stored including hint dependency, solution dependency, unresolved skill, and change in average response time.
- Type: requirement
- Sources: docs/SPEC.md:1374–1411 (§5.13.3); SPEC.md:524 (§5.5.2)
- Related IDs: CLAUDE.md:91–92
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `learning_gain.py` implements both formulas, guards the pre-max case, and persists all twelve metrics.
- Confidence: HIGH — formulas and the edge case are explicit.

### REQ-37 — Post-exam must be a parallel form, never a reused variant
- Domain: product requirements
- Claim: The post-exam must match the pre-exam on topic, skill, difficulty, template family, required reasoning steps, and option construction, differing only in numeric parameters, option order, and random seed; the same question variant must not be reused, and composition is 2 questions at each of difficulties 1–5 per topic.
- Type: requirement
- Sources: docs/SPEC.md:1331–1372 (§5.13.1–§5.13.2)
- Related IDs: SPEC §5.9.1
- Temporal: SPEC-original
- Candidate status: CURRENT as written, with a recorded deviation: ROADMAP:1664 records post-exam "knowingly repeats an authored item" — a departure that lives outside SPEC.
- Intended vs observed: intended-state
- Contradicts/competes: ROADMAP:1664 (the authored-bank repeat, D-189-era) — the SPEC text carries no amendment marker.
- Evidence still required: Phase 3: read the deviation's decision record and the current `exam_policy.py` behavior.
- Confidence: HIGH for the SPEC text; the deviation is documented elsewhere.

### REQ-38 — Assessment set is fixed once created, with idempotent answer submission
- Domain: product requirements
- Claim: Once an assessment session's question set is created it is fixed; refreshes and retries must not generate a new set, and answer submission uses an `Idempotency-Key` header on `POST /learning/sessions/{session_id}/answers`.
- Type: requirement
- Sources: docs/SPEC.md:1010–1033 (§5.9.2)
- Related IDs: SPEC §5.29; AUD-L-10 [AUDIT_FINDINGS]
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm the answers endpoint honors `Idempotency-Key` and that set regeneration is impossible on refresh.
- Confidence: HIGH — explicit.

### REQ-39 — Ten questions are not an absolute ability measure; UI must say "Current estimated level"
- Domain: product requirements
- Claim: Mastery starts as a bootstrap model (weighted score with difficulty weights 1.0/1.4/1.9/2.5/3.2) and may later adopt IRT or Bayesian estimation; ten questions must not be treated as an absolute measure of ability and the UI must say "Current estimated level".
- Type: requirement
- Sources: docs/SPEC.md:1060–1122 (§5.10.1–§5.10.2)
- Related IDs: none
- Temporal: SPEC-original; IRT adoption conditioned on "after enough response data"
- Candidate status: CURRENT for the bootstrap model; the IRT/Bayesian upgrade is DEFERRED/UNKNOWN (no trigger threshold or owning session)
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm `mastery_bootstrap.py` uses these exact weights, that no IRT path exists, and that the frontend renders the wording.
- Confidence: HIGH for the bootstrap requirement.

### REQ-40 — Student-facing language rule: growth-oriented copy, internal skill IDs stay internal
- Domain: product requirements
- Claim: Student-facing copy must use growth-oriented phrasing and internal skill identifiers must never reach students; tutor-facing summaries may use exact internal skill IDs.
- Type: invariant
- Sources: docs/SPEC.md:1124–1147 (§5.10.3); CLAUDE.md:108–109
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: AUDIT_2026_08_16 §3 recorded 30 of 33 topics rendering raw internal ids on the dashboard — a violation later fixed (D-380 era); see the audit register.
- Evidence still required: Phase 3: confirm `test_leak_sample.py` and `test_mock_hint_is_leak_clean.py` exist and pass as leak assertions.
- Confidence: HIGH — explicit in both docs.

### REQ-41 — Twelve automated validation checks gate every multiple-choice item
- Domain: deterministic-core guarantees
- Claim: Every multiple-choice item must pass twelve automated checks before use (exactly one correct answer, unique options, correct option matches the executable solution, no division by zero, values in range, complete wording, no answer leakage, no duplicate, difficulty-rubric compliance, topic/skill alignment, age-appropriate wording) — implemented with Python, SymPy, or custom evaluators.
- Type: requirement
- Sources: docs/SPEC.md:926–944 (§5.8.5)
- Related IDs: docs/QUESTION_GENERATION.md (as-built pipeline)
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: QUESTION_GENERATION.md describes what preflight actually refuses — the as-built check set may be narrower.
- Evidence still required: Phase 3: enumerate the checks the curriculum pipeline actually runs and diff against these twelve.
- Confidence: MEDIUM — the list is explicit; implementation status asserted nowhere read.

### REQ-42 — Difficulty label from an LLM is a bootstrap label only
- Domain: LLM behavior
- Claim: An LLM-assigned difficulty label is only a bootstrap label, to be superseded by observed evidence (including success after hints).
- Type: requirement
- Sources: docs/SPEC.md:990–994
- Related IDs: docs/QUESTION_GENERATION.md §3 ("This is provisional")
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm difficulty is recalibrated from observed response data and that no gating decision depends on the LLM label alone.
- Confidence: MEDIUM.

### REQ-43 — TurnReason is a closed nine-value taxonomy and the client contract
- Domain: LLM behavior
- Claim: Every chat turn must carry a machine-readable `reason` from a closed enum of nine values (`answer`, `no_approved_source`, `sources_conflict`, `access_required`, `out_of_scope`, `human_action_required`, `policy_restricted`, `system_error`, `needs_clarification`); the reason is the contract and the wording is not, and clients must branch on the reason rather than infer cause.
- Type: decision
- Sources: docs/SPEC.md:1929–1955 (§5.19.5); docs/DECISIONS.md:25116, 25142–25152
- Related IDs: D-351, AUD-C-19 [AUDIT_FINDINGS], AUD-C-04 [AUDIT_FINDINGS]
- Temporal: added 2026-08-15 (D-351), status "implemented"
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: docs/DECISIONS.md:26570 notes part of an earlier statement "contradicts D-351".
- Evidence still required: Phase 3: confirm the closed enum in `chat_api/services/outcomes.py`, that every node writing `answer` writes `reason`, and that `chat-web/src/types.ts` exposes it.
- Confidence: HIGH — SPEC and DECISIONS agree, with a named implementation file.

### REQ-44 — Rule 1: no user-facing message may restate its own reason code
- Domain: LLM behavior
- Claim: No user-facing message may restate its own reason code, because an internal category is not a sentence to read at a visitor; the check is applied over the whole message set rather than the one message that was wrong.
- Type: invariant
- Sources: docs/SPEC.md:1957–1960 (§5.19.5 rule 1); docs/DECISIONS.md:25158–25161
- Related IDs: D-351
- Temporal: amended/added 2026-08-15
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm a test iterates the full message set and can fail for the right reason.
- Confidence: HIGH.

### REQ-45 — Rule 2: `access_required` names no role and no document
- Domain: LLM behavior
- Claim: An `access_required` response carries only generic copy; the matching tier is selected server-side, kept in graph state and logged, but never returned, because naming the tier disclosed to an unauthenticated caller that a restricted document mentioning their terms exists — measured wrong in the field (AUD-C-25/D-179). Reversing this requires an explicit decision, not an edit.
- Type: invariant
- Sources: docs/SPEC.md:1961–1968 (§5.19.5 rule 2); docs/DECISIONS.md:25185–25200
- Related IDs: D-351, D-179, AUD-C-25 [AUDIT_FINDINGS], AUD-C-20 [AUDIT_FINDINGS], D-221
- Temporal: amended 2026-08-15 (D-351)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: Supersedes the prior behavior of four role-specific sentences (docs/DECISIONS.md:25185–25190).
- Evidence still required: Phase 3: confirm the generic copy is the only returned string and the tier is still logged.
- Confidence: HIGH — explicit, with a measured field failure.

### REQ-46 — Access-hint recall is measured at 1 in 8, and the threshold was deliberately not tuned
- Domain: LLM behavior
- Claim: Against staging, the access hint fired for 1 of 8 questions a role-gated document answers (recall) and 0 of 5 public questions produced a false hint (precision); the probe is biased toward silence, the feature "mostly is not doing the job SPEC gives it", and the threshold was explicitly not tuned — moving recall requires a separate measured offline rule sweep bounded by AUD-C-20.
- Type: observed-state
- Sources: docs/DECISIONS.md:25124–25137
- Related IDs: D-351, D-343, AUD-C-20 [AUDIT_FINDINGS], D-221, D-359, D-371
- Temporal: measured for D-351, 2026-08-15; re-swept D-359/D-371 (2026-08-16) with the shipped rule kept
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: SPEC §5.19.5's `access_required` row implies the reason is reliably produced; the measurement says it fires 1 time in 8. D-371 closed the item with the shipped rule still best.
- Evidence still required: Phase 3: confirm `scripts/measure_access_hint_live.py` exists and whether recall has changed since D-371.
- Confidence: HIGH — numbers are explicit and self-critical.
- **Annotation 2026-08-20 (step 7d, W-10) — the rate above is SUPERSEDED and its denominator was
  never 8. The rule-half of this row stands.** This row re-quotes D-351's 2026-08-15 figures
  (`docs/DECISIONS.md:25129-25130`) verbatim; **D-371 replaced them on 2026-08-16**
  (`docs/DECISIONS.md:25966-25972`): **recall 2/8, precision 5/5 (zero false hints)**. D-371's own
  methodological correction is the part that must travel with the number — **the probe's
  precondition is a no-source refusal, so an *answered* question never reaches it**: of the 8, 2
  were answered, 4 refused without a hint, 2 hinted, so the probe **fired on 2 of the 6 it could
  reach**. Any restatement must say *which denominator it means* — **2/8** (all questions) or
  **2-of-6-reachable** (questions the probe could act on). Note also that this row states precision
  as "0 of 5 false hints" while D-371 states "precision 5/5" — the same fact at opposite polarity,
  so a reader comparing the two sees `0` against `5`. Cross-reference:
  `LIVE_BEHAVIOR_FINDINGS.md` LB-02, and one cell (`access_hint = null` on a public question,
  no false hint) re-confirmed live on 2026-08-20.
- **Annotation 2026-08-20 (step 7d, W-10) — D-371's "shipped ceiling of 0.40" label matches no
  constant that exists.** `docs/DECISIONS.md:25953` argues from "a shipped ceiling of **0.40**";
  read from source, `packages/shared/src/intellichoice_shared/access_probe_policy.py:37-40` says
  0.40 was D-165's value, **`ACCESS_PROBE_MAX_DISTANCE = 0.45` is the *fallback* ceiling since
  D-166/D-168** (used only by the distance-only paths: lexical/`MockBedrockProvider` and the
  degraded path when the reranker is unavailable), and **the live rule is three constants**:
  `ACCESS_PROBE_CANDIDATE_MAX_DISTANCE = 0.60` (`:103`), `ACCESS_PROBE_RERANK_MIN_SCORE = 0.9`
  (`:104`), `ACCESS_PROBE_TIER_MARGIN = 0.10` (`:105`). D-371's *argument* is unaffected (gated and
  public cases interleave on the distance axis), but the *label* is what a future reader would act
  on: "tuning the shipped ceiling" edits the fallback used by the degraded and mock paths and
  changes production behaviour not at all. Cross-reference: `LIVE_BEHAVIOR_FINDINGS.md` LB-03.

### REQ-47 — §5.19.4 out-of-scope wording amended; the supported-topic list is unchanged
- Domain: LLM behavior
- Claim: The out-of-scope refusal's final line changed from "I cannot answer unrelated general-purpose questions." to "For anything else, your branch can point you to the right person.", because a parent asking about a mistaken-donation refund was told their question was unrelated general-purpose — the classification was correct but the sentence described the asker's question with the classifier's own label. The eight supported topics are unchanged; donations remain deliberately out of scope.
- Type: decision
- Sources: docs/SPEC.md:1898–1927 (§5.19.4, amendment at 1920–1927)
- Related IDs: D-351
- Temporal: amended 2026-08-15
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: Supersedes the prior final line (marked inline — one of only two dated amendments in SPEC).
- Evidence still required: Phase 3: confirm the shipped string matches SPEC exactly.
- Confidence: HIGH — the amendment is dated and inline.

### REQ-48 — `system_error` must not be phrased as a statement about the question
- Domain: failure handling
- Claim: The `system_error` reason denotes a failure on our side and is explicitly not a statement about the question; its offered next step is retry.
- Type: invariant
- Sources: docs/SPEC.md:1952 (§5.19.5 table row)
- Related IDs: D-351, AUD-C-08 [AUDIT_FINDINGS], AUD-C-19 [AUDIT_FINDINGS]
- Temporal: 2026-08-15
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found — same failure-mode family as REQ-15.
- Evidence still required: Phase 3: confirm the `system_error` copy makes no claim about the corpus or the question.
- Confidence: HIGH.

### REQ-49 — §5.29 graceful-failure matrix: nineteen named failures with prescribed responses
- Domain: failure handling
- Claim: A nineteen-row failure matrix prescribes a specific response per failure (MySQL profile failure → disable authenticated functions but keep public Q&A up; MySQL attendance failure → block learning start; Postgres writer failure → stop answer submission; Bedrock timeout → bounded retry + smaller-model fallback; hint failure → verified static concept hint; VLM failure → delete image and request text input; LangSmith/Prometheus failure → continue serving). Common mechanisms: timeout, bounded retry, backoff, circuit breaker, idempotency, dead-letter queue, fallback, user-safe error message.
- Type: requirement
- Sources: docs/SPEC.md:2775–2809 (§5.29)
- Related IDs: SPEC §5.4.4, §5.21.8; CLAUDE.md:98–99
- Temporal: SPEC-original
- Candidate status: CURRENT, with the VLM row DEFERRED (D-078)
- Intended vs observed: intended-state
- Contradicts/competes: The "verified static concept hint" fallback and the dead-letter queue are prescribed but no evidence of either was found in the docs read.
- Evidence still required: Phase 3: verify each row has an implementation and a test — especially the static concept-hint fallback, the DLQ, and the smaller-model fallback.
- Confidence: HIGH that the matrix exists as written; LOW that all rows are implemented.

### REQ-50 — Scale, availability, and language targets for the initial release
- Domain: product requirements
- Claim: The initial production release supports English only, targets more than 1,000 students and more than 100 concurrent learning sessions, and carries a 99.9% monthly availability SLO.
- Type: requirement
- Sources: docs/SPEC.md:29–31 (§5.0)
- Related IDs: SPEC §5.33.4, §6.23; D-136 (capacity pricing); D-153 §1 (~1,000/week planning assumption)
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: ARCHITECTURE's measured capacity table prices 150 concurrent as expensive (ARCH-13); D-153 fixed the planning assumption at ~1,000 spread across a week with peak concurrency unmeasured.
- Evidence still required: Phase 3: confirm whether any SLO instrumentation exists and whether the 100-concurrent target has ever been demonstrated.
- Confidence: HIGH — explicit; MEDIUM that anything enforces it.

### REQ-51 — Multi-agent component table assigns node types, pinning which nodes may use a model
- Domain: deterministic-core guarantees
- Claim: The §5.5.2 table binds each of sixteen components to a type — Profile Resolver, Attendance Gate, Grading Node and Learning Gain Service are deterministic; Topic Resolver and Parent Report Agent are structured LLM; Mastery Estimator is a statistical service; Study Planner is rule + statistical; Tutor Agent is an LLM agent — and closes with "Do not turn every node into an agent."
- Type: requirement
- Sources: docs/SPEC.md:493–531 (§5.5.2)
- Related IDs: CLAUDE.md:91–92
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3: confirm each component's implementation matches its declared type.
- Confidence: HIGH — an explicit per-node allowance list.

### REQ-52 — LearningState is a fixed field list with names and emails excluded
- Domain: deterministic-core guarantees
- Claim: `LearningState` enumerates ~40 fields, all identity references being `*_external_id`; names and email addresses are never stored in graph state and email addresses are retrieved from MySQL only temporarily when needed. `QAState` likewise carries `ephemeral_location` rather than persisted coordinates.
- Type: invariant
- Sources: docs/SPEC.md:518–559 (§5.5.3); SPEC.md:1863–1896 (§5.19.3)
- Related IDs: REQ-01; D-020
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: U7_CHECKPOINT_CONSOLIDATION.md:29 corrects the field count ("`LearningState` has 31 fields, not 27") — counts drift; the no-PII property is the stable claim.
- Evidence still required: Phase 3: confirm the Pydantic state models contain no PII-shaped field and that LangGraph checkpoints are covered by the schema-purity posture.
- Confidence: HIGH — explicit closing sentence in §5.5.3.

---

## §2 — Architecture, infrastructure, deployment, operational, observability-egress (ARCH-01…ARCH-35)

### ARCH-01 — ARCHITECTURE.md's declared as-built scope
- Domain: architecture
- Claim: `docs/ARCHITECTURE.md` claims to document the system as built through S0–S34 plus the S36–S43 audit/stabilization work and the §2.6 launch gate, explicitly as a map of "what exists now" rather than the target design (SPEC.md is the spec).
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:3-13
- Related IDs: none
- Temporal: file states S32–S35 staging deployment as shipped; adjacent paragraph timestamped 2026-07-30
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: FINAL_ARCHITECTURE.md:6 says ARCHITECTURE.md documents "what exists now (through S31, S29 deferred)" — a stale scope statement about the same file
- Evidence still required: Phase 3 — confirm the code/infra actually covers the claimed session range
- Confidence: HIGH — direct self-description

### ARCH-02 — Production environment and go.intellichoice.org integration not built; staging is the only live environment
- Domain: deployment
- Claim: The production environment (S48) and the real integration with `go.intellichoice.org` (S42–S47), including `IcProfileAdapter`, are not built; staging is described as "live and real".
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:19-20; docs/DECISIONS.md:52
- Related IDs: D-004, S42–S48
- Temporal: staging live since S32 / 2026-07-22
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: SPEC.md:3118-3124 prescribes three accounts (dev/staging/production); FINAL_ARCHITECTURE.md:33-42 still treats the first deploy as not yet done
- Evidence still required: Phase 3 — enumerate `terraform/environments/` (expect staging only) and AWS account/env inventory
- Confidence: HIGH — stated in two independent docs

### ARCH-03 — No independent auth or consent capture; apps still issue dev tokens
- Domain: deployment
- Claim: Independent auth, consent capture, and §5.1.2's first-visit notice (S44/S45) are not built — the deployed apps still issue dev tokens, and `/dev/token` is the only authenticated path until S44.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:21-23, 435-437
- Related IDs: T-02, D-129, D-097, AUD-L-01 [AUDIT_FINDINGS], D-175
- Temporal: current as of ARCHITECTURE.md
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify `/dev/token` middleware gate and absence of a real auth provider in code/infra
- Confidence: HIGH

### ARCH-04 — Four enabled unattended schedules with a fixed nightly order
- Domain: operational
- Claim: Four EventBridge schedules run unattended — `session-consolidate`, `chat-purge`, `retention-purge`, `memory-consolidate` — in nightly order 18:00 / 18:10 / 18:50, with consolidation Sundays at 18:30.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:28-30
- Related IDs: D-357
- Temporal: current as of 2026-07-30 rewrite or later
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: directly contradicted by ARCHITECTURE.md:1850-1851 and :2068 — see ARCH-06
- Evidence still required: Phase 3 — read EventBridge rules in terraform/ and confirm four schedules, cron expressions, timezone
- Confidence: HIGH that the doc claims this; MEDIUM that it is true given the intra-doc conflict

### ARCH-05 — Schedule ordering is a correctness constraint, not tidiness
- Domain: operational
- Claim: The nightly order is a correctness constraint (D-357): `session-consolidate` projects finished threads into `learning_sessions`, and `checkpoint_retention_cli` both reads eligibility from that table and classifies a thread as chat by the absence of a row, so an unprojected learning thread is invisible to learning windows and looks like chat to the other branch.
- Type: invariant
- Sources: docs/ARCHITECTURE.md:30-36
- Related IDs: D-357
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: same paragraph's closing sentence says "That retention job stays unscheduled until this one has a record of firing" (L35-36) while L28 lists `retention-purge` among the four enabled schedules — the referent ("that retention job" = `checkpoint_retention_cli` vs `retention-purge`) is ambiguous in the text
- Evidence still required: Phase 3 — determine whether `checkpoint_retention_cli` has an EventBridge rule; resolve the referent
- Confidence: MEDIUM — invariant clear; the enabled/unscheduled status of the retention job is self-contradictory

### ARCH-06 — Two pipeline sections still assert "manual trigger" for jobs listed as scheduled
- Domain: operational
- Claim: Per-pipeline sections still record the older posture: `make memory-consolidate` is "manual trigger only this session" (L1850-1851) and `make chat-purge` has "no scheduler yet" (L2068).
- Type: audit-finding
- Sources: docs/ARCHITECTURE.md:1850-1851, 2068
- Related IDs: none
- Temporal: text dates to S24/S25 era; not updated after the schedules landed
- Candidate status: UNKNOWN — likely SUPERSEDED by L28-30 but recorded separately per phase rules
- Intended vs observed: observed-state (as of writing)
- Contradicts/competes: ARCHITECTURE.md:28-30 (ARCH-04)
- Evidence still required: Phase 3 — infra read decides which is true; whichever loses is a doc-rot finding
- Confidence: HIGH that both texts exist and conflict

### ARCH-07 — youtube-sync has a real weekly schedule that ships deliberately disabled
- Domain: operational
- Claim: `youtube-sync` now has a real weekly EventBridge schedule but ships deliberately disabled, because `youtube_provider` defaults to `fake` and an unattended run would write fabricated catalog rows on a schedule; `make webcontent-sync` remains manual for the same class of reason.
- Type: decision
- Sources: docs/ARCHITECTURE.md:24-28; docs/ARCHITECTURE.md:1791-1797 (older posture)
- Related IDs: D-105, D-002, D-076, D-326
- Temporal: current; L1791 text predates the schedule
- Candidate status: CURRENT (L24-28); L1791 HISTORICAL
- Intended vs observed: observed-state
- Contradicts/competes: ARCHITECTURE.md:1791-1792 states the weekly schedule is "later infra work"
- Evidence still required: Phase 3 — confirm the EventBridge rule exists with state DISABLED
- Confidence: HIGH

### ARCH-08 — Deployed footprint: ECS Fargate + RDS PostgreSQL with pgvector + RDS MySQL fixture (D-004, decided)
- Domain: deployment
- Claim: D-004 was accepted and decided at S32 on 2026-07-22 (proposed 2026-07-13): ECS Fargate + RDS PostgreSQL with pgvector + RDS MySQL (IntelliChoice's own seeded fixture DB standing in for `go.intellichoice.org`'s shape), Terraform IaC, env separation at VPC/prefix level rather than AWS Organizations, keeping Secrets Manager/TLS/WAF-class controls.
- Type: decision
- Sources: docs/DECISIONS.md:29-37, 48-52
- Related IDs: D-004, D-084, D-082, D-083
- Temporal: proposed 2026-07-13; corrected 2026-07-22; decided 2026-07-22
- Candidate status: CURRENT
- Intended vs observed: both (decision plus "a real staging environment is now live on this footprint")
- Contradicts/competes: SPEC.md:3116-3187 (EKS/Aurora/AWS Organizations) — see ARCH-23; FINAL_ARCHITECTURE.md:110 says "D-004 is still 'proposed,' not 'accepted'" (falsified by the decision text itself)
- Evidence still required: Phase 3 — read terraform/ + AWS state to confirm Fargate services, RDS Postgres 16, RDS MySQL fixture instance
- Confidence: HIGH — decision text is explicit and dated

### ARCH-09 — D-004's "managed Mongo (Atlas)" clause is stale and must not be acted on
- Domain: deployment
- Claim: D-004's original "managed Mongo (Atlas)" clause is corrected in place as stale on two axes: the real system runs MySQL not MongoDB, and `go.intellichoice.org` is pre-existing external infrastructure IntelliChoice does not own — the project needs network reachability and read credentials, not a managed DB instance.
- Type: decision
- Sources: docs/DECISIONS.md:39-46; docs/FINAL_ARCHITECTURE.md:25-29
- Related IDs: D-004, D-082, D-083
- Temporal: correction 2026-07-22
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: the un-annotated D-004 recommendation body it corrects (DECISIONS.md:33-36)
- Evidence still required: Phase 3 — confirm no Atlas/Mongo resource in terraform/
- Confidence: HIGH

### ARCH-10 — learning-api runs 2 ECS tasks; SSE crosses replicas via Postgres LISTEN/NOTIFY
- Domain: architecture
- Claim: `SessionEventBus` is an in-process `dict[str, list[asyncio.Queue]]` and `learning-api` runs 2 ECS tasks, so background-published SSE events reached nobody when publish and connection landed on different replicas; `SessionEventRelay` fans each publish over one dedicated `LISTEN` connection per process. Measured: personalized hints arrived in 2 of 4 staging runs before the relay, 8 of 8 after.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:610-624
- Related IDs: D-334, D-335, D-217, U7
- Temporal: measured on staging; current
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: FINAL_ARCHITECTURE.md:112-120 and 169-176 claim nothing schedules replacing the in-memory bus — a 2026-07-21 projection, overtaken
- Evidence still required: Phase 3 — confirm ECS desiredCount and the relay code path; confirm 8000-byte NOTIFY cap handling
- Confidence: HIGH

### ARCH-11 — chat-api has the same relay on its own channel; scales on ALB p95
- Domain: architecture
- Claim: `chat-api` has the same LISTEN/NOTIFY relay since D-349 on its own channel (`chat_session_events`) because both apps share one Postgres and NOTIFY is broadcast per channel; chat-api scales out on ALB p95 latency. An oversized event is dropped from the fan-out rather than truncated.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:623-631
- Related IDs: D-349, D-335
- Temporal: since D-349
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm chat-api autoscaling policy target metric and channel name
- Confidence: HIGH

### ARCH-12 — Capacity: one uvicorn worker per task, so the lever is task count
- Domain: infrastructure
- Claim: Each ECS task runs one uvicorn worker, so throughput is bounded by CPU per request — the lever is task count. Measured on staging at a pinned 2 tasks: throughput saturates near 5 concurrent requests per task, and added concurrency grows latency about `concurrency^1.55` (ALB p95 0.33 s at 2.5 concurrent/task vs 2.98 s at 12.5).
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:254-265
- Related IDs: D-134, D-132
- Temporal: measured on staging (D-134/D-136 era)
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: SPEC.md:3201-3207's HPA-signal model assumes Kubernetes-style pod autoscaling
- Evidence still required: Phase 3 — confirm one worker per task in the container command and task CPU sizing
- Confidence: HIGH

### ARCH-13 — Capacity/pricing table with an explicit extrapolation ban
- Domain: infrastructure
- Claim: A priced table interpolates `p95 ≈ 0.31 s × (r/2.5)^1.4` (exponent 1.37–1.45) giving tasks needed at 25 and at 150 concurrent, with an explicit prohibition: do not extrapolate outside r ∈ [2.5, 12.5], because two points cannot establish a functional form. Headline: at the pilot target of 25 concurrent a comfortable p95 costs three more tasks, not twenty-eight.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:266-283
- Related IDs: D-136, D-134, SPEC §6.23
- Temporal: as of D-136
- Candidate status: CURRENT
- Intended vs observed: observed-state (measured) with modelled projection
- Contradicts/competes: SPEC §6.23's 150-concurrent target is named as the expensive case
- Evidence still required: Phase 3 — verify current desiredCount matches the "today = 2 tasks" row
- Confidence: HIGH

### ARCH-14 — Connection-pool sizing rule and the db.t4g.micro ceiling
- Domain: infrastructure
- Claim: `create_engine`'s `pool_size=10, max_overflow=10` is a per-task constant sized in S34, so the demand rule is `pool_size ≈ target r` plus one psycopg connection per task for `AsyncPostgresSaver`. Under that rule 25 concurrent needs ~40 connections across both services and `db.t4g.micro`'s ~112 is sufficient; 150 concurrent needs ~180 and requires a resize.
- Type: invariant
- Sources: docs/ARCHITECTURE.md:284-299
- Related IDs: D-348, D-356, D-134
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm RDS instance class is `db.t4g.micro` and pool settings in code
- Confidence: HIGH

### ARCH-15 — A DB resize has lead time, not just cost: Free Tier rejected db.t4g.small
- Domain: infrastructure
- Claim: Scaling the database above `micro` is a prerequisite to check rather than a line item — this account's Free Tier restrictions rejected `db.t4g.small` outright with a real `CreateDBInstance` failure in S32/D-084.
- Type: historical-event
- Sources: docs/ARCHITECTURE.md:300-302
- Related IDs: D-084
- Temporal: S32 (2026-07-22 era)
- Candidate status: CURRENT (constraint), HISTORICAL (the failure)
- Intended vs observed: observed-state
- Contradicts/competes: SPEC.md:3163-3176's Aurora Multi-AZ + reader recommendation
- Evidence still required: Phase 3 — confirm current account/Free-Tier status before any capacity plan is priced
- Confidence: HIGH

### ARCH-16 — SSE connections must not hold pooled DB connections
- Domain: architecture
- Claim: A connection held for the life of an SSE connection breaks the pool rule (an SSE response never finishes, so each open tab pinned one pooled connection idle-in-transaction) — measured on chat as 20 concurrent streams exhausting 10+10 and blocking every other request on that replica. Both `/stream` routes now build the initial snapshot in a short-lived session.
- Type: invariant
- Sources: docs/ARCHITECTURE.md:289-296
- Related IDs: D-348, D-356
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read both `/stream` handlers to confirm no session held across the keep-alive loop
- Confidence: HIGH

### ARCH-17 — ECS drains tasks on every deploy, so the checkpoint/DB seam is entered without a bug
- Domain: operational
- Claim: The LangGraph saver commits per superstep on its own psycopg pool while domain rows commit at dependency teardown; anything failing between keeps the checkpoint and discards the rows, and a task stop enters that window with no bug required — ECS drains tasks on every deploy. `checkpoint_reconcile.py` rolls the checkpoint backwards only; `learning_checkpoint_repairs_total` counts it. Fix is partial — only the mid-finalize seam; the mid-interrupt seam and the commit ordering are still open.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:601-609
- Related IDs: AUD-X-07 [AUDIT_FINDINGS], S42, D-110 §3, §7-R9
- Temporal: current; remaining seams open
- Candidate status: CURRENT (partial), open remainder accepted per §7-R9
- Intended vs observed: observed-state
- Contradicts/competes: none found — but only INTEGRATION_PLAN carries R9's expiry condition (see SEC-10)
- Evidence still required: Phase 3 — confirm the reconcile module and metric exist and the two named seams remain unfixed
- Confidence: HIGH

### ARCH-18 — Accepted read-scope risk for tutor/branch_manager roles
- Domain: architecture
- Claim: Every learning route passes a required `access: "read" | "write"` to `resolve_target_student`, but tutor/branch_manager roles currently have no per-student scope check for reads — an accepted risk awaiting the assignment/branch-roster data `IcProfileAdapter` brings in S43; their writes fail closed.
- Type: decision
- Sources: docs/ARCHITECTURE.md:486-494
- Related IDs: D-086, D-107, AUD-C-01 [AUDIT_FINDINGS], AUD-X-01 [AUDIT_FINDINGS], AUD-X-05 [AUDIT_FINDINGS], S40, S43
- Temporal: accepted risk, current
- Candidate status: CURRENT (accepted risk), resolution DEFERRED to S43
- Intended vs observed: observed-state
- Contradicts/competes: ARCH-02 — the `IcProfileAdapter` is not built, so the resolution path is itself unbuilt (and S43 is frozen by D-152: the closure path is blocked; see the supersession map, chain G3)
- Evidence still required: Phase 3 — confirm the read-branch gap in `resolve_target_student`
- Confidence: HIGH

### ARCH-19 — Storage split table: MySQL 8.4 for PII, PostgreSQL 16 (+pgvector) for everything else, plus repo-local FS
- Domain: architecture
- Claim: ARCHITECTURE.md's storage-split table is the canonical as-built layout: MySQL 8.4 holds all names/emails/roles/parent-child links/attendance/branch contact data (read-only via `MySQLProfileAdapter`); PostgreSQL 16 holds curriculum, assessments, checkpoints, MCP audit trail, RAG+pgvector, YouTube catalog, org directory, cost reservations, rate-limit counters, chat/memory/report tables; `knowledge-content/` (repo, local FS) holds placeholder and extracted source content.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:2052-2073
- Related IDs: D-082, D-083, D-035, D-046, D-050, D-114, D-153, D-345, D-402, D-421, D-159
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: FINAL_ARCHITECTURE.md:154-161 appends/overrides the first row — see ARCH-20
- Evidence still required: Phase 3 — compare against actual migrations/models
- Confidence: HIGH

### ARCH-20 — FINAL_ARCHITECTURE appends one storage row: PII source becomes the real external MySQL, integration shape unconfirmed
- Domain: architecture
- Claim: FINAL_ARCHITECTURE.md "adds one row" to the storage-split table: in target state the PII row is the real `go.intellichoice.org` MySQL system, read-only via `ProfileAdapter`, and whether IntelliChoice connects directly to that MySQL instance or through an API it exposes is unconfirmed — to be resolved before writing the real adapter.
- Type: plan
- Sources: docs/FINAL_ARCHITECTURE.md:154-161, 169-174
- Related IDs: D-082, D-083, D-004, I11
- Temporal: planned as of 2026-07-21
- Candidate status: UNKNOWN — the row lives in a projection document; ARCHITECTURE.md lists a locally-provisioned MySQL fixture; the integration shape question was later refined by I11's ladder with rung 1 (API-only) confirmed viable (see INT-20)
- Intended vs observed: intended-state
- Contradicts/competes: ARCHITECTURE.md:2056; DECISIONS.md:48-52 (RDS MySQL fixture is what shipped)
- Evidence still required: Phase 3 — confirm no real-system connectivity or credential exists
- Confidence: MEDIUM — clear text, 2026-07-21 vintage

### ARCH-21 — Six-logical-DB / schema split is an explicitly undecided item (FINAL_ARCH open question 5)
- Domain: infrastructure
- Claim: Whether to adopt SPEC §5.33.3's six-schema split (`learning` / `rag` / `memory` / `checkpoint_learning` / `checkpoint_chat` / `evaluation`) now, later, or not at all is recorded as an open question S32 was to resolve and that no read document settles.
- Type: open-work
- Sources: docs/FINAL_ARCHITECTURE.md:163-167, 179-180, 182-185
- Related IDs: SPEC §5.33.3, D-004
- Temporal: open as of 2026-07-21; no later resolution located in ARCHITECTURE.md or D-004
- Candidate status: UNKNOWN — possibly genuinely undecided and recorded nowhere else
- Intended vs observed: intended-state
- Contradicts/competes: none found — notably, no decision entry resolving it was located
- Evidence still required: Phase 3 — grep DECISIONS/ROADMAP for any schema-split decision; inspect the actual Postgres schema list
- Confidence: MEDIUM — the unresolved status is inferred from absence

### ARCH-22 — Today's actual DB layout is one `intellichoice` Postgres database, stated only in FINAL_ARCHITECTURE
- Domain: infrastructure
- Claim: "Today's system is one `intellichoice` Postgres database" — the only place either architecture document states the actual database layout; ARCHITECTURE.md's storage table names stores and tables but never states how many logical databases or schemas exist.
- Type: observed-state
- Sources: docs/FINAL_ARCHITECTURE.md:165-166; absence in docs/ARCHITECTURE.md:2052-2073
- Related IDs: SPEC §5.33.3
- Temporal: stated as of 2026-07-21; unrefreshed since
- Candidate status: UNKNOWN — plausibly still true but asserted only in a stale projection document
- Intended vs observed: observed-state (as of writing)
- Contradicts/competes: SPEC.md:3178-3187 prescribes six logical DBs/schemas
- Evidence still required: Phase 3 — read migrations / terraform RDS config to confirm one database named `intellichoice`
- Confidence: MEDIUM — single stale source

### ARCH-23 — SPEC §5.33 prescribes AWS Organizations, EKS across 3 AZs, and Aurora PostgreSQL
- Domain: infrastructure
- Claim: SPEC §5.33 as written requires an AWS Organization with separate Dev/Staging/Production accounts, production EKS across three AZs with Karpenter/HPA/PDB/NetworkPolicy/IRSA, and Aurora PostgreSQL Multi-AZ with one writer plus at least one reader.
- Type: requirement
- Sources: docs/SPEC.md:3116-3187
- Related IDs: D-004 (defers this), SPEC §5.34
- Temporal: original spec text; carries no superseded marker
- Candidate status: SUPERSEDED (by D-004 for the deployment path) — but the spec text itself carries no such marker
- Intended vs observed: intended-state
- Contradicts/competes: DECISIONS.md:29-52 (D-004, accepted); ARCHITECTURE.md's ECS/RDS footprint; FINAL_ARCHITECTURE.md:33-42
- Evidence still required: Phase 3 — confirm no EKS resource exists in terraform/
- Confidence: HIGH — text unambiguous; the "superseded" judgment is inferential since SPEC carries no annotation

### ARCH-24 — SPEC §5.33.4 scaling targets and HPA/worker signals
- Domain: infrastructure
- Claim: SPEC targets are >1,000 students, >100 concurrent learning sessions, 99.9% monthly availability, API P95 near one second, LLM TTFT near three seconds; HPA signals are CPU/memory/active requests/SSE connections/P95, with worker scaling on SQS queue depth.
- Type: requirement
- Sources: docs/SPEC.md:3191-3213
- Related IDs: SPEC §6.23, D-136, D-134
- Temporal: original spec text
- Candidate status: UNKNOWN — numeric targets still cited while the HPA/SQS mechanisms assume EKS
- Intended vs observed: intended-state
- Contradicts/competes: ARCHITECTURE.md:266-283 prices 150 concurrent as expensive with an extrapolation ban; ARCHITECTURE.md:619-620 explicitly rejects SQS for the SSE fan-out
- Evidence still required: Phase 3 — confirm which autoscaling signals ECS services actually use
- Confidence: HIGH

### ARCH-25 — SPEC §5.36 technology-placement table still lists Kubernetes/EKS as the runtime
- Domain: infrastructure
- Claim: SPEC's "Final Technology Placement" table names Kubernetes → EKS runtime and lists EKS under the enterprise-level product row, alongside Terraform and GitHub Actions; LangFuse is marked "Not used" and YouTube API is placed as a "weekly API sync".
- Type: requirement
- Sources: docs/SPEC.md:3411-3462 (esp. 3415, 3442-3444, 3451, 3456)
- Related IDs: D-004, D-105
- Temporal: original spec text, uncorrected
- Candidate status: SUPERSEDED for the EKS/Kubernetes rows (D-004); CURRENT for Terraform/CI-CD
- Intended vs observed: intended-state
- Contradicts/competes: DECISIONS.md:29-52; ARCHITECTURE.md's ECS Fargate footprint
- Evidence still required: Phase 3 — none for the text
- Confidence: HIGH

### ARCH-26 — FINAL_ARCHITECTURE's own status claims are 2026-07-21 projections: S32 decision-gated, S33/S34 not started
- Domain: deployment
- Claim: FINAL_ARCHITECTURE.md self-labels as a projection and claims S32's deployment decision is "decision-gated, not yet made" with D-004 "still 'proposed,' not 'accepted'", and that S33 and S34 are "not started".
- Type: plan
- Sources: docs/FINAL_ARCHITECTURE.md:1-11, 33-42, 107-110, 122-124, 135-137
- Related IDs: D-004, D-064, D-078
- Temporal: explicitly "planned as of 2026-07-21"
- Candidate status: HISTORICAL for the status claims (D-004 accepted 2026-07-22; S33/S34 shipped), CURRENT only as a record of the plan's state at that date
- Intended vs observed: intended-state
- Contradicts/competes: DECISIONS.md:29, 48-52; ARCHITECTURE.md:3-13, 19-20. Both sides recorded; not resolved here
- Evidence still required: Phase 3 — determine whether S33/S34 deliverables (WAF-class controls, load tests, canary) shipped, since FINAL_ARCH was never regenerated as its own L183-185 instructs
- Confidence: HIGH that the doc says this; HIGH that it is stale

### ARCH-27 — FINAL_ARCHITECTURE's "known gap": single-instance SSE bus, unscheduled for replacement
- Domain: architecture
- Claim: FINAL_ARCHITECTURE claims the SSE bus assumes exactly one Uvicorn worker and that nothing in S32/S33/S34's scope schedules replacing it with real pub/sub (Redis or Postgres LISTEN/NOTIFY behind the same interface).
- Type: audit-finding
- Sources: docs/FINAL_ARCHITECTURE.md:112-120, 146-152, 175-176
- Related IDs: D-032, D-334, D-335
- Temporal: 2026-07-21
- Candidate status: HISTORICAL — the exact remedy it says nobody scheduled (Postgres LISTEN/NOTIFY behind `SessionEventBus`) is what D-334/D-335 shipped
- Intended vs observed: intended-state
- Contradicts/competes: ARCHITECTURE.md:610-631 (ARCH-10, ARCH-11) — the gap is closed for both apps
- Evidence still required: Phase 3 — none beyond ARCH-10's verification
- Confidence: HIGH

### ARCH-28 — VPC default posture is zero internet egress; all AWS dependencies via PrivateLink
- Domain: observability-egress
- Claim: The VPC's default posture is no internet egress at all: ECR, CloudWatch Logs, Secrets Manager, Bedrock, X-Ray and S3 reach the tasks over VPC endpoints (PrivateLink); the private subnets carried no `0.0.0.0/0` route and the account ran zero NAT gateways.
- Type: invariant
- Sources: docs/ARCHITECTURE.md:2149-2152
- Related IDs: D-084, S39
- Temporal: baseline posture; past tense relative to the LangSmith NAT
- Candidate status: CURRENT as the default posture
- Intended vs observed: both
- Contradicts/competes: ARCHITECTURE.md:2161-2169 asserts one NAT gateway now exists for LangSmith — tense shift is the only reconciliation offered
- Evidence still required: Phase 3 — read terraform/ VPC endpoints and route tables; count NAT gateways in AWS state
- Confidence: HIGH

### ARCH-29 — LangSmith is the only egress leaving AWS and the only reason a NAT gateway exists — with an unreconciled D-406/D-419 tension
- Domain: observability-egress
- Claim: LangSmith is the sole egress that leaves AWS and the sole reason a NAT gateway exists; one NAT in one AZ deliberately (telemetry, not function); both NAT and tracing gated on a single `langsmith_tracing_enabled` flag.
- Type: decision
- Sources: docs/ARCHITECTURE.md:2159, 2161-2174
- Related IDs: D-214, D-242, D-084, D-406, D-419
- Temporal: current per ARCHITECTURE.md
- Candidate status: UNKNOWN — DECISIONS D-419 (2026-08-18) records the NAT gateway as "absent from the plan entirely, which is D-406's verification"; whether a NAT currently exists and bills is not established by the documents alone
- Intended vs observed: both
- Contradicts/competes: D-406/D-419's absent-from-plan statements vs ARCHITECTURE.md's present-tense single-NAT description; PROGRESS also carried a "NAT ~$33/mo for nothing while tracing disabled" note (outside the re-verified ranges)
- Evidence still required: Phase 3 — read terraform NAT/route resources, the `langsmith_tracing_enabled` gate, and current AWS state; date the ~$33/mo note before using it
- Confidence: MEDIUM — the decision is clear; the current NAT count is not

### ARCH-30 — Observability sink table: system telemetry never leaves AWS, AI telemetry masked at source
- Domain: observability-egress
- Claim: Four sinks with asymmetric reach: CloudWatch Logs (VPC endpoint, structured JSON, external ids only); CloudWatch metrics via 4 metric filters per service (`BedrockCostCents`, `BedrockCallDurationMs`, `BedrockCallFailed`, `BedrockCircuitOpen`); X-Ray (per-task `otel-collector` sidecar); LangSmith (public internet via one NAT, node structure and timings only, inputs/outputs forced masked). D-242 corrected the row that used to claim prompt/response payloads leave AWS.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:2077-2093, 2154-2159, 2176-2180
- Related IDs: D-084, D-213, D-214, D-242, S39, SPEC §5.30, §5.32.1, §5.32.2
- Temporal: current; LangSmith row corrected by D-242
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: the superseded pre-D-242 version of the same row (self-noted)
- Evidence still required: Phase 3 — confirm the sidecar config, the metric filters, and the masking env vars in task definitions
- Confidence: HIGH

### ARCH-31 — The LangSmith leg was dark for its entire life until 2026-08-10
- Domain: observability-egress
- Claim: The LangSmith leg went live 2026-08-10 and had never worked before: 403 Forbidden on every flush since D-214 wired it, retrying forever at WARNING with zero runs delivered; cause was a missing `LANGSMITH_WORKSPACE_ID`. A new per-service metric filter, `LangSmithIngestFailed`, exists because four filters per service watched Bedrock and none watched telemetry delivery.
- Type: historical-event
- Sources: docs/ARCHITECTURE.md:2102-2111
- Related IDs: D-242, D-214, D-401
- Temporal: broken from D-214 until 2026-08-10
- Candidate status: CURRENT (fixed), HISTORICAL (the outage)
- Intended vs observed: observed-state
- Contradicts/competes: any doc dated between D-214 and 2026-08-10 that implies LangSmith tracing worked (e.g. FINAL_ARCHITECTURE.md:19 lists it among built observability)
- Evidence still required: Phase 3 — confirm `LANGSMITH_WORKSPACE_ID` and the `LangSmithIngestFailed` filter/alarm per service
- Confidence: HIGH

### ARCH-32 — Health endpoints emit no telemetry; the trace denominator is now real traffic
- Domain: observability-egress
- Claim: Health endpoints emit no telemetry at all, suppressed at the `/readyz` handler, so the trace corpus a PII scan walks is real traffic instead of ~97% ALB health checks. The fix took three attempts and the first made volume 3.4× worse (excluding a server span orphans its child spans into separate root traces).
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:249-253
- Related IDs: AUD-F-30 [AUDIT_FINDINGS], D-132, D-104 §4, D-129
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm suppression location in the `/readyz` handler
- Confidence: HIGH

### ARCH-33 — Deploy gate answers "is this commit serving?" from the ECS control plane, narrowed after a false failure
- Domain: deployment
- Claim: Because `/healthz` and `/metrics` are deliberately outside the CloudFront allowlist, the deploy asserts: exactly one `PRIMARY` deployment whose image tag is this run's, with `runningCount ≥ 1`; `rolloutState == COMPLETED` is bound-retried rather than required at an instant (healthy autoscaling once read as a bad deploy and skipped the rollback). A deterministic Vite content-hash comparison covers the S3/CloudFront half.
- Type: observed-state
- Sources: docs/ARCHITECTURE.md:429-458
- Related IDs: AUD-F-37 [AUDIT_FINDINGS], D-158, AUD-F-38 [AUDIT_FINDINGS], D-173 §6-§7, D-175
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read `.github/workflows/deploy-staging.yml` to confirm the assertions and retry bound
- Confidence: HIGH

### ARCH-34 — Image-floor / deploy-consistency checking (`make image-check`, D-418) is absent from ARCHITECTURE.md
- Domain: deployment
- Claim: The deploy-consistency control — `scripts/check_deployed_image_consistency.py` / `make image-check`, judging each service against its family's latest revision because deploys and un-pinned schedules resolve families by name — is recorded in DECISIONS/PROGRESS/ROADMAP but not in ARCHITECTURE.md, whose deploy-verification section stops at the ECS control-plane and frontend-hash checks. D-418 also records that Terraform adopts the deployed image (`adopt_deployed_image` default true, D-244), so tfvars pins are reported and never judged.
- Type: audit-finding
- Sources: docs/DECISIONS.md:28407-28419, 28441-28451, 28474-28480; docs/PROGRESS.md:139-153; docs/ROADMAP.md:2941-2943; absence verified in docs/ARCHITECTURE.md:429-458
- Related IDs: D-418, D-419, D-244, D-401, D-406, D-137
- Temporal: corrected 2026-08-18
- Candidate status: CURRENT (the control exists per DECISIONS), with an ARCHITECTURE.md coverage gap
- Intended vs observed: observed-state
- Contradicts/competes: the pre-2026-08-18 tfvars-floor warning D-418 retracts as a "phantom blocker", written into three documents
- Evidence still required: Phase 3 — read `Makefile`, the script, and `adopt_deployed_image` in terraform variables
- Confidence: HIGH — the control is documented; its absence from ARCHITECTURE.md verified by grep

### ARCH-35 — Grade-on-submit and ORG_TIMEZONE recorded as deviations from the plan's own recommendation
- Domain: operational
- Claim: Two shipped behaviors deviate from the plan such that reading the spec alone would mispredict the code: S22 kept grade-on-submit with a real default timer (user decision, D-064); and the org's local-time convention is a provisional default with an env switch (`ORG_TIMEZONE`/`ORG_TIME_CONVENTION`, D-130), known since D-153 §4 not to matter operationally for published sessions.
- Type: decision
- Sources: docs/ARCHITECTURE.md:38-47; docs/ARCHITECTURE.md:2057
- Related IDs: D-064, D-130, D-153 §4, S22, S43
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found (FINAL_ARCHITECTURE cites D-064 consistently)
- Evidence still required: Phase 3 — confirm the env vars in task definitions and the S43-owed property guard (which is frozen with S43)
- Confidence: HIGH

---

## §3 — Security, privacy, authorization, data boundaries, incidents (SEC-01…SEC-35)

### SEC-01 — MySQL is the PII source of truth; Postgres holds only external-id references
- Domain: data-boundary
- Claim: MySQL is the sole store for names, emails, roles, parent-child relationships, grade, branch, branch-manager email, attendance and account status; PostgreSQL may store only shared external identifiers (`student_external_id`, `parent_external_id`, `branch_external_id`, `user_external_id`) and must never replicate names, emails, phones, addresses or full MySQL rows.
- Type: requirement
- Sources: docs/SPEC.md:307-338; docs/INCIDENT_RESPONSE.md:16-26; CLAUDE.md non-negotiable #1
- Related IDs: D-082, D-083
- Temporal: standing; MySQL replaced MongoDB as the real store per D-082/D-083
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm no ORM model or migration in `packages/db` carries a PII column.
- Confidence: HIGH — stated identically in two independent docs.

### SEC-02 — No operational cross-database join; PII stays out of the operational Postgres
- Domain: data-boundary
- Claim: MySQL and Postgres results must be combined in the FastAPI service layer joined by external primary key (never a federated SQL join); large-scale analytics would require a separate de-identified warehouse rather than copying MySQL PII into operational Postgres.
- Type: requirement
- Sources: docs/SPEC.md:370-419
- Related IDs: none
- Temporal: standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify the service-layer join pattern and absence of a warehouse copy path.
- Confidence: HIGH — explicit spec prohibition.

### SEC-03 — Bedrock payloads limited to a minimum-necessary field set
- Domain: privacy
- Claim: Bedrock payloads may carry only grade, current_topic, skill, estimated_level, question, selected_answer and relevant_learning_fact; full_name, email, phone, home_address, precise_location, parent_contact and branch_manager_email must never be sent.
- Type: requirement
- Sources: docs/SPEC.md:2812-2836
- Related IDs: SPEC §5.30.1; D-023, D-072 (widenings by decision)
- Temporal: standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — diff the spec allowlist against the actual `extra="forbid"` payload models.
- Confidence: HIGH — verbatim spec lists.

### SEC-04 — Authorization matrix must be enforced in backend/query layer, not in prompts
- Domain: authorization
- Claim: The six-role access matrix (anonymous public Q&A; student own learning; parent linked children; tutor tutor-docs/summaries; branch manager manager-docs/branch summaries; admin approved functions) must be enforced in the backend and query layer, never via prompt instructions.
- Type: requirement
- Sources: docs/SPEC.md:2840-2851, 2883
- Related IDs: §7-R8; TRACEABILITY rule 3
- Temporal: standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: SEC-09 — TRACEABILITY:185 states "§5.30.2's matrix is not fully enforced".
- Evidence still required: Phase 3 — enumerate which matrix rows have backend enforcement.
- Confidence: HIGH — spec text unambiguous.

### SEC-05 — PII floor, Postgres boundary: schema-purity test over every ORM model
- Domain: data-boundary
- Claim: `test_schema_purity.py::test_no_model_has_a_pii_column_name` is documented as walking every ORM model against a denied-column-name list.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:133-134
- Related IDs: TRACEABILITY rule 1; D-011
- Temporal: as of TRACEABILITY tranche 1
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-asserted)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — open the test, confirm it walks all models and the denylist is non-trivial.
- Confidence: MEDIUM — doc-mentioned implementation.

### SEC-06 — PII floor, LLM-payload boundary: typed `extra="forbid"` payloads with 12+ tests
- Domain: privacy
- Claim: Every Bedrock payload is typed as an `extra="forbid"` model with an exact field list (`bedrock.py:15-20`), pinned by 12+ tests — three per payload type (exact allowlist match, no denylisted names, extra fields rejected).
- Type: observed-state
- Sources: docs/TRACEABILITY.md:135-138
- Related IDs: TRACEABILITY rule 1; §5.30.1
- Temporal: as of tranche 1
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-asserted)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm each payload type has all three test arms and the field lists match SPEC §5.30.1.
- Confidence: MEDIUM.

### SEC-07 — PII floor, trace boundary: RedactingSpanExporter at the export boundary
- Domain: privacy
- Claim: A `RedactingSpanExporter` redacts at the span-export boundary, pinned by `test_sse_token_query_string_is_redacted_before_export`, which drives real instrumentation and carries a negative arm and an explicit vacuity guard.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:139-147
- Related IDs: D-104; TRACEABILITY rule 1
- Temporal: post-D-104 (a bearer JWT previously sat in `http.url` on every SSE span)
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-asserted)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the negative arm and vacuity guard at the cited lines and that the exporter is wired in both apps.
- Confidence: MEDIUM.

### SEC-08 — PII floor, log boundary: live log scanner; D-104's transferability lesson
- Domain: privacy
- Claim: `scripts/scan_logs_pii.py` (`make scan-logs`) scans live log events with the same patterns/matcher as the trace scanner and fails on truncation, unreadable window, or zero events; first run over authenticated traffic was CLEAN with 20/20 control (D-129). D-104 is the stated reason for per-boundary enforcement: a clean log scan coexisted with a leaking trace on the same request.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:126-131, 148-153; docs/INCIDENT_RESPONSE.md:192-200
- Related IDs: D-104, D-129, AUD-F-30 [AUDIT_FINDINGS]
- Temporal: scanner added 2026-07-30
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the scanner exists; note a single clean run is not continuous assurance (INCIDENT_RESPONSE warns an idle-window scan is near-meaningless).
- Confidence: MEDIUM — one measured run; ongoing state unknown.

### SEC-09 — §7-R8: tutor and branch_manager can read any student (accepted, expires at first real traffic)
- Domain: authorization
- Claim: `resolve_target_student` verifies students against their own `sub` and parents against a live linked-children lookup but returns the requested id unchecked for tutor and branch_manager — a tutor token can read any student's dashboard, history and reports; accepted rather than fixed (D-123) because the real fix needs tutor-assignment/branch-roster data arriving at S43 (formal disposition S46). Mitigations recorded with the acceptance: the write half is closed (S40/D-107) and tutor tokens are only obtainable via secret-gated `/dev/token` (D-097). **The acceptance expires at first real traffic** — it covers the pilot's staging/no-user window, not launch.
- Type: decision
- Sources: docs/INTEGRATION_PLAN.md:535-550; docs/TRACEABILITY.md:183-185, 498-499
- Related IDs: §7-R8, AUD-L-07 [AUDIT_FINDINGS], D-123, D-107, D-097, D-086
- Temporal: accepted at D-123 (2026-07-30); expiry = first real traffic; closure named S43/S46
- Candidate status: CURRENT (accepted-open). Note: the named closure path (S43/S46) is frozen by D-152 — no document reconciles the acceptance's expiry with the freeze (verified, supersession map chain G3).
- Intended vs observed: observed-state
- Contradicts/competes: SEC-04 (§5.30.2 requirement) — explicitly acknowledged as "not fully enforced".
- Evidence still required: Phase 3 — confirm the read path is still unchecked and the write refusal present; confirm no real traffic has begun.
- Confidence: HIGH — stated consistently in two docs with the same expiry wording.

### SEC-10 — §7-R9: checkpoint→domain commit seam accepted for the pilot with a tripwire metric
- Domain: security
- Claim: The LangGraph checkpoint commits inside `ainvoke` while domain rows commit at dependency teardown, so a failure between them (including an ordinary ECS task stop during deploy) keeps graph state and discards DB state; seam (a) mid-finalize is fixed via `checkpoint_reconcile` (counted by `learning_checkpoint_repairs_total`); seam (b) mid-interrupt and the commit ordering remain accepted for the pilot. The evidence of non-occurrence is a **flat `learning_checkpoint_repairs_total`**; if that counter moves the acceptance is void. Re-read before launch.
- Type: decision
- Sources: docs/INTEGRATION_PLAN.md:551-566
- Related IDs: §7-R9, AUD-X-07 [AUDIT_FINDINGS], D-110, D-123
- Temporal: accepted D-123; expiry = counter movement or launch re-read
- Candidate status: CURRENT (accepted-open)
- Intended vs observed: observed-state
- Contradicts/competes: none found — but ARCHITECTURE.md restates the seam without the expiry condition (ARCH-17).
- Evidence still required: Phase 3 — confirm the metric exists and is observable, and whether anyone reads its value (an unread tripwire is not a tripwire).
- Confidence: HIGH.

### SEC-11 — Parent access verified by live MySQL linked-children lookup, not a token claim
- Domain: authorization
- Claim: `authorization.py:39-43` verifies parents against a live MySQL lookup of linked children and 403s otherwise, deliberately not trusting a token claim because a token is a snapshot and a link can be revoked.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:417-423; docs/INTEGRATION_PLAN.md:536-537
- Related IDs: §5.14.3, §5.6.1
- Temporal: as of tranche 3
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-asserted)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the live lookup is on every parent-scoped route, not just the dashboard.
- Confidence: MEDIUM.

### SEC-12 — Location consent requirement: coordinates discarded, never persisted, alternatives offered
- Domain: privacy
- Claim: Before Branch Locator use, a notice must state location is used only for nearby-branch computation and not permanently stored; precise coordinates must be discarded after the Maps MCP request and never stored in Postgres, MySQL, LangSmith or logs; a ZIP/city/address alternative must exist and raw manual addresses must not be retained by default.
- Type: requirement
- Sources: docs/SPEC.md:100-116 region (§5.1.3)
- Related IDs: §5.1.3, §5.1.4
- Temporal: standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify the "do not retain manually entered address" clause has an implementation (TRACEABILITY's §5.1.3 entry does not mention it).
- Confidence: HIGH.

### SEC-13 — Location consent traced, including the AUD-C-03 checkpoint-purge leak closure
- Domain: privacy
- Claim: Coordinates never leave the resolving function (`branch_locator.py:15`); the chat SPA gates on `LocationConsentModal.tsx`; AUD-C-03 closed the last leak — `checkpoint_privacy.py:24` purges LangGraph `checkpoint_writes.__resume__` rows after a `location_consent` resume, where coordinates survived after every `QAState` field had been cleaned; D-113 added a regression test decoding checkpoint blobs with LangGraph's own serializer.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:381-391
- Related IDs: AUD-C-03 [AUDIT_FINDINGS], D-113, D-101, D-045, §5.1.3
- Temporal: AUD-C-03 closure (D-113, 2026-07-28)
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-asserted)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the purge runs on failure/abandonment paths too, not only on a successful resume.
- Confidence: MEDIUM.

### SEC-14 — Solution-image handling requirement: immediate deletion, no backups, no traces
- Domain: privacy
- Claim: Uploaded solution images must be validated, malware-scanned, held in ephemeral encrypted storage, and deleted immediately after success or failure; never in the long-term RAG bucket, versioned S3, backups, or LangSmith traces; only extracted equations/error steps retained; the S3 lifecycle rule is explicitly a final safeguard, not the primary deletion mechanism.
- Type: requirement
- Sources: docs/SPEC.md:1710-1752 (§5.17)
- Related IDs: §5.17, D-078
- Temporal: standing (unbuilt)
- Candidate status: DEFERRED (requirement live, feature deferred — see SEC-15)
- Intended vs observed: intended-state
- Contradicts/competes: SEC-15
- Evidence still required: none for the requirement text; see SEC-15.
- Confidence: HIGH.

### SEC-15 — Image requirement is dispositioned-because-unbuilt (D-078), and re-opens on build
- Domain: privacy
- Claim: TRACEABILITY records rule 8 as dispositioned rather than traced because the feature does not exist — S29 deferred per D-078 — and states it "re-opens the moment §5.17 is built"; `analyze_image` is likewise an unimplemented gateway method deferred to S29.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:250-253, 230
- Related IDs: D-078, §5.17, S29
- Temporal: deferred 2026-07-20; unbuilt at tranche-1 writing
- Candidate status: DEFERRED
- Intended vs observed: observed-state
- Contradicts/competes: SEC-14; also T-02's disclosure list includes "images are deleted immediately" (TRACEABILITY:679) for a feature that does not exist — see WORK-32.
- Evidence still required: Phase 3 — confirm no image upload/VLM path exists anywhere.
- Confidence: HIGH.

### SEC-16 — T-01 half one: CloudTrail built and live-verified
- Domain: security
- Claim: CloudTrail was built (`terraform/modules/cloudtrail/`, wired into staging) with management events only, multi-region, log-file validation, 90-day bucket expiry and `aws:SourceArn` conditions; live-verified `IsLogging: true`, delivery proven by a real 1,761-byte `.json.gz` ~4.5 min after start rather than zero-byte placeholders.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:649, 705-714, 737
- Related IDs: T-01, D-125, AUD-F-12 [AUDIT_FINDINGS], §5.30.3
- Temporal: closed 2026-07-30 (D-125)
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found. Note D-419 (2026-08-18) records a near-miss where a transient refresh nearly replaced the healthy CloudTrail bucket during the apply.
- Evidence still required: Phase 3 — confirm the module is still wired in the staging environment.
- Confidence: HIGH — measured verification recorded.

### SEC-17 — T-01 half two: GuardDuty absent and deliberately deferred to S50 A7
- Domain: security
- Claim: GuardDuty, required by §5.30.3, remains absent; D-125 deferred it with a written reason (always-on paid service against a no-user staging account, same argument as WAF/D-087) and tracked it to S50 A7. The record changed, not the state.
- Type: decision
- Sources: docs/TRACEABILITY.md:649, 715-720, 736, 739-744
- Related IDs: T-01, D-125, D-087, S50 A7, §5.30.3
- Temporal: deferred 2026-07-30
- Candidate status: DEFERRED
- Intended vs observed: both
- Contradicts/competes: SPEC §5.30.3 (docs/SPEC.md:2868) still lists GuardDuty as required with no in-spec deferral marker.
- Evidence still required: Phase 3 — confirm ROADMAP S50 A7 carries GuardDuty.
- Confidence: HIGH.

### SEC-18 — WAF deferred; per-IP in-memory rate limiting is an explicitly-insufficient stopgap with a measured per-task ceiling
- Domain: security
- Claim: AWS WAF is absent and deferred with a written reason to S50 A7 (D-087), which added per-IP rate limiting as an in-memory stopgap "not a replacement for one"; D-181 measured the stopgap's ceiling as per-task — one source IP gets `6000 × running tasks` requests/minute — accepted as ~3× a legitimate burst.
- Type: decision
- Sources: docs/TRACEABILITY.md:734; docs/INCIDENT_RESPONSE.md:29-33, 209-213
- Related IDs: D-087, D-181, S50 A7, §5.30.3, D-002
- Temporal: deferred at S33; ceiling measured in D-181 (2026-08-04)
- Candidate status: DEFERRED
- Intended vs observed: both
- Contradicts/competes: SPEC §5.30.3 lists WAF among present controls.
- Evidence still required: Phase 3 — confirm the middleware is in-process and no WAF resource exists in terraform.
- Confidence: HIGH — consistent across two docs with a measured number.

### SEC-19 — Escalation cap moved from the in-memory limiter to a shared Postgres counter (AUD-C-27)
- Domain: security
- Claim: The §5.24.2 escalation cap could not accept the per-task ceiling of the in-memory rate limiter and was moved to a shared Postgres counter (AUD-C-27), the one limit enforced across tasks.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:734
- Related IDs: AUD-C-27 [AUDIT_FINDINGS], D-181, D-087, §5.24.2
- Temporal: after D-181's measurement
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — locate the counter table and confirm transactional safety under concurrency.
- Confidence: MEDIUM — single-sentence source.

### SEC-20 — T-02: the §5.1.2 first-visit notice is scheduled, not shipped
- Domain: privacy
- Claim: The first-visit notice with eleven required disclosures does not exist in `apps/learning-web/src`; D-129 dispositioned it as S45-builds / §6.1-track-enumerates-first, with the order load-bearing; the doc states plainly it is "still not built" — owned and ordered rather than assumed.
- Type: open-work
- Sources: docs/TRACEABILITY.md:650, 652-698
- Related IDs: T-02, D-129, D-114 §4, S45, §6.1 track, §5.1.2
- Temporal: dispositioned 2026-07-30; unbuilt as of that writing
- Candidate status: DEFERRED — and S45 sits inside the frozen S43–S47 block (see WORK-33)
- Intended vs observed: both
- Contradicts/competes: TRACEABILITY self-flags the near-miss where "Open: none" sat above a table listing T-02 open; SEC-15 (one disclosure describes an unbuilt feature).
- Evidence still required: Phase 3 — confirm no notice component exists today and whether the §6.1 track has started.
- Confidence: HIGH.

### SEC-21 — Two hard credential-file prohibitions and a no-quoting rule for production secrets
- Domain: security
- Claim: When reading the production checkout, two files must never be read — `icrest/app/config/db.config.js` and `intellichoice-sendmail-*.json` — and the source-visible JWT secret and password-HMAC key values must never be quoted anywhere; the S42 report restates this, naming them only as "a hard-coded literal".
- Type: invariant
- Sources: CLAUDE.md:47-52; docs/S42_SECURITY_REPORT.md:15-16
- Related IDs: D-151, D-153
- Temporal: standing since S42/D-151
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none (Phase 3 may grep docs/ for accidental violations, reporting the fact only).
- Confidence: HIGH.

### SEC-22 — Production is frozen: findings are reported to the user, never fixed here
- Domain: security
- Claim: The existing `go.intellichoice.org` system is the source of truth for its own behavior but frozen by constraint — findings about it get reported, never fixed in this project; D-152 additionally forbids reachability measurement, production API URL/test-account requests, and §3.1 auth finalization until the user starts integration.
- Type: invariant
- Sources: CLAUDE.md:45-72; docs/S42_SECURITY_REPORT.md:6-10
- Related IDs: D-151, D-152, D-153, D-417/A1
- Temporal: standing; reconfirmed 2026-08-18 (D-417 A1)
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none.
- Confidence: HIGH.

### SEC-23 — Secrets inventory exists by name only; secrets must not live in repos or images
- Domain: security
- Claim: SPEC §5.35 inventories required accounts and example secret names and requires that secrets never be stored in GitHub repositories or Docker images; staging stores MySQL connection parts as separate `MYSQL_DB_*` components per D-092; LangSmith needs a PII-masking policy, retention configuration and separate per-environment projects.
- Type: requirement
- Sources: docs/SPEC.md:3318-3407 (esp. 3366-3373, 3403-3407)
- Related IDs: D-092
- Temporal: standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: SEC-33 — the production system violates the same principle (its own repo history), though that system is out of scope.
- Evidence still required: Phase 3 — verify the LangSmith masking policy and per-environment projects exist as configuration, not just as required-account rows.
- Confidence: HIGH — names only; no values read or quoted.

### SEC-24 — Incident D-084: seed script printed a live RDS master password into CloudWatch and a transcript
- Domain: incident
- Claim: On 2026-07-22 (S32), `seed_mysql.py`'s own success print emitted the real RDS MySQL master password into CloudWatch Logs and the session transcript; found and fixed live (`render_as_string(hide_password=True)`). D-084 marks the point where real credentials began to exist.
- Type: historical-event
- Sources: docs/INCIDENT_RESPONSE.md:68-71, 27-28, 134-137
- Related IDs: D-084
- Temporal: 2026-07-22 (S32)
- Candidate status: HISTORICAL
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the hide_password pattern survives and no secret-adjacent print remains.
- Confidence: HIGH.

### SEC-25 — Incident D-085: `/dev/token` reachable on the real staging ALB
- Domain: incident
- Claim: On 2026-07-23 (S33), `/dev/token` was reachable on the real staging ALB because `terraform.tfvars` deliberately set `app_environment="dev"` mid-S32 for browser testing — a documented, user-approved trade-off; the fix added an independent second gate rather than flipping one flag. Later corrected by D-096: the fix was recorded as executed while the apply was withheld, so the endpoint stayed open two more days ("the decision log said 'closed' for two days while the hole was open").
- Type: historical-event
- Sources: docs/INCIDENT_RESPONSE.md:40-44, 150-173; docs/DECISIONS.md:3473 (D-096's correction)
- Related IDs: D-085, D-096, D-097
- Temporal: 2026-07-23 (S33); correction 2026-07-24
- Candidate status: HISTORICAL
- Intended vs observed: observed-state
- Contradicts/competes: D-085's own text still reads as closed with no caveat (verified — supersession map chain F3).
- Evidence still required: Phase 3 — confirm the second gate exists and `/dev/token` is currently secret-gated (D-097), since SEC-09's mitigation depends on it.
- Confidence: HIGH.

### SEC-26 — Incident D-310: process-table secret exposure; rotation deliberately declined by the user
- Domain: incident
- Claim: On 2026-08-13, `pgrep -fl` printed both `/dev/token` shared secrets into the session transcript; the exposure was undeletable; the Makefile comment asserting the secrets "never [reach] argv, ps, or a shell history" was measurably false (4 process-table lines carried an expanded secret). **Rotation was declined by the user** on bounded-exposure grounds (staging only; production frozen and untouched; Postgres holds no PII; residual risk is gateway-capped Bedrock spend). The fix went to the source: `e2e/config.ts` fetches secrets itself by id; 0 exposed lines after.
- Type: historical-event
- Sources: docs/INCIDENT_RESPONSE.md:73-96; docs/DECISIONS.md:22172-22230
- Related IDs: D-310, D-097, D-132, OPEN_DECISIONS #8
- Temporal: 2026-08-13
- Candidate status: HISTORICAL (with a standing condition)
- Intended vs observed: observed-state
- Contradicts/competes: departs from the runbook's own "rotate first" default — recorded as a documented departure. The standing condition ("until staging serves anything real") lives in OPEN_DECISIONS #8, not in D-310 itself (verified — chain G4); per D-310 alone the decline is unconditioned.
- Evidence still required: Phase 3 — whether the exposed secrets were ever rotated later; whether the bounded-exposure premises still hold.
- Confidence: HIGH — decision attributed to the user in the entry's own status line.

### SEC-27 — D-400: cost attribution was answerable without new code; `latest()` not `max()`
- Domain: incident
- Claim: The 08-16 audit's "never attributable per student or per session" was judged too strong: three queries answer it with no new code, each executed against staging before being documented; the recorded lesson is that `max(learning_session_id)` silently returned no field while looking like a working query — "a control that cannot succeed", caught only because the query was run.
- Type: historical-event
- Sources: docs/INCIDENT_RESPONSE.md:221-293
- Related IDs: D-400, D-393, AUD-F-30 [AUDIT_FINDINGS]
- Temporal: audit 2026-08-16; D-400 2026-08-17
- Candidate status: CURRENT (procedure) / HISTORICAL (the correction)
- Intended vs observed: both
- Contradicts/competes: the 08-16 audit's own finding (explicitly rebutted). See COST-11.
- Evidence still required: Phase 3 — the `cost_reservations` query is schema-verified only, "not row-verified against staging"; confirm both named trace-join tests exist.
- Confidence: HIGH — self-labelled verification levels.

### SEC-28 — Production finding 1: a single malformed request can terminate the icrest API process
- Domain: security
- Claim: In the frozen production system, the login handler is `async` with no try/catch and calls string methods on `req.body.email` with no type guard; with no rejection handlers and an unpinned Node version, Node ≥ 15 defaults to terminating the whole process. `POST /api/accounts/resendCode` has the same shape. Rated High; found by reading source, not probing.
- Type: observed-state
- Sources: docs/S42_SECURITY_REPORT.md:109-119, 6-9
- Related IDs: S42_DISCOVERY §6.1, D-153 §5/§7
- Temporal: read at the 2026-08-01 checkout; drafted 2026-08-02
- Candidate status: CURRENT (about production, unfixed by us by design)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: none from this repo — production is frozen; do not probe.
- Confidence: MEDIUM — source-read inference; deployed-runtime behavior unknown.

### SEC-29 — Production finding 2: role is self-assignable at registration, plus an unverified-account overwrite path
- Domain: authorization
- Claim: icrest's register endpoint persists `req.body.role` verbatim with no allowlist — the Parent/Student/Tutor restriction exists only in frontend radio buttons — so a direct API call can set any role including `Manager`; and re-registering an existing unverified email overwrites that account's password, role and code. Rated High; fixing the endpoint does not clean pre-fix rows (`SELECT DISTINCT role FROM accounts;` suggested).
- Type: observed-state
- Sources: docs/S42_SECURITY_REPORT.md:121-136
- Related IDs: S42_DISCOVERY §6.2, D-153 §5/§7, §7-R1
- Temporal: read at the 2026-08-01 checkout
- Candidate status: CURRENT (about production)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: none from this repo; the downstream obligation is SEC-34.
- Confidence: HIGH — two concrete code paths cited.

### SEC-30 — Production finding 3: credentials logged on every login attempt
- Domain: privacy
- Claim: icrest's login handler logs the email and stored password hash on every attempt, and the frontend logs the plaintext credentials object and token; severity depends entirely on where stdout goes — "an org-only fact" this project cannot know. Rated Medium.
- Type: observed-state
- Sources: docs/S42_SECURITY_REPORT.md:138-142
- Related IDs: S42_DISCOVERY §6.3, D-153 §5
- Temporal: read at the 2026-08-01 checkout
- Candidate status: CURRENT (about production)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: none — impact unresolvable without org operational information; record the uncertainty.
- Confidence: HIGH for the code fact, LOW for impact.

### SEC-31 — Production finding 4: the 6-digit code is weak, over-shared, non-expiring and unrate-limited
- Domain: security
- Claim: One `accounts.code` INTEGER column serves both email verification and password reset, generated with `Math.random`, with no server-side expiry (despite the email claiming 20 minutes), no rotation after use, and no rate limiting. Rated Medium in the outgoing report; the same weakness appears as permanent residual risk §7-R3 (an icrest takeover becomes a new-stack login as that user).
- Type: observed-state
- Sources: docs/S42_SECURITY_REPORT.md:144-149; docs/INTEGRATION_PLAN.md:518-520
- Related IDs: S42_DISCOVERY §6.4, §7-R3, D-153 §5
- Temporal: read at the 2026-08-01 checkout
- Candidate status: CURRENT (about production, permanent residual risk)
- Intended vs observed: observed-state
- Contradicts/competes: severity mismatch worth flagging — "Medium" in the outgoing message vs a permanent account-takeover residual risk in INTEGRATION_PLAN §7.
- Evidence still required: none.
- Confidence: HIGH — consistent across two documents.

### SEC-32 — The production security report is drafted and apparently unsent; no send-status field exists
- Domain: open-work
- Claim: S42_SECURITY_REPORT.md is a bilingual hand-off message drafted 2026-08-02, intended to be sent as one message to the production operator; the document records no send date, recipient or confirmation, and the recipient placeholders are still unfilled — so on the evidence, two High findings sit in an unread draft.
- Type: open-work
- Sources: docs/S42_SECURITY_REPORT.md:1-30 (esp. 4, 12, 38, 100)
- Related IDs: D-153 §5/§7, S42_DISCOVERY §6, E-group (S42_OPEN_QUESTIONS)
- Temporal: drafted 2026-08-02; send status unknown as of 2026-08-19
- Candidate status: UNKNOWN
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — search DECISIONS/PROGRESS for any send record; absent that, treat as unsent open work with real-world consequence.
- Confidence: MEDIUM — absence of a send-status field is strong but negative evidence.

### SEC-33 — §7-R1: production-repo compromise yields new-stack impersonation; committed credentials are permanent
- Domain: security
- Claim: The password-HMAC key and write-capable DB credentials live in the production repo (committed, permanently in its history), so an attacker with repo + network access could set a known password hash on any account and log into the new apps as that user; accepted as permanent, "to be signed off by the org at S42". Relatedly §7-R2: production's fast hashing stays crackable on a DB leak regardless of the auth option.
- Type: decision
- Sources: docs/INTEGRATION_PLAN.md:502-517; docs/S42_SECURITY_REPORT.md:151-153
- Related IDs: §7-R1, §7-R2, I14, D-153
- Temporal: permanent; the R1 org sign-off nominally "at S42"
- Candidate status: CURRENT (accepted permanent risk) — with an orphaned obligation: the sign-off's occasion (S42 org interaction) is frozen by D-152, and no completion is visible.
- Intended vs observed: observed-state
- Contradicts/competes: SEC-23 (our own no-secrets-in-repo rule) — boundary: this is the org's system.
- Evidence still required: Phase 3 — whether the org sign-off happened; whether I14's refresh check is built (it is impossible under I11 rung 1 — see INT-21).
- Confidence: HIGH.

### SEC-34 — Our stack gates Tutor/Manager behind an allowlist we control, independent of any org fix (D-153 §7)
- Domain: authorization
- Claim: Even if the org fixes the self-assignable-role finding, this stack still gates `Tutor`/`Manager` behind an allowlist we control — because pre-fix rows may already carry a self-assigned `Manager`, production is frozen and schema-drifting, and authorization is ours to decide (CLAUDE.md rule 3). Standing assumption A2: role strings match the four known values, unknowns fail closed with a metric (I7).
- Type: invariant
- Sources: docs/S42_SECURITY_REPORT.md:167-170; docs/INTEGRATION_PLAN.md:521-522, 572-573
- Related IDs: D-153 §7, §7-R4, A2, I7, I12, CLAUDE.md rule 3
- Temporal: standing since S43 drafting
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: SEC-09 — our own tutor/branch_manager read scope is currently unenforced, so "authorization is ours to decide" is asserted while one read path is knowingly open.
- Evidence still required: Phase 3 — locate the role allowlist design in S43-scoped material and the I7 unknown-role metric plan.
- Confidence: HIGH.

### SEC-35 — Staging secrets are Terraform-generated in Secrets Manager and were never actually missing
- Domain: security
- Claim: `STAGING_TOKEN_SECRET_LEARNING`/`_CHAT` were recorded across S38–S40 as a binding constraint on three gate criteria, but they are Terraform `random_password` resources in Secrets Manager — never handed to a human, so never losable; a single `get-secret-value` recovered both. Rotation paths documented: RDS via `manage_master_user_password` (D-092, AWS auto-rotates); JWT signing secrets via a scoped `-target`+`-replace` apply with the D-137 bare-apply trap documented.
- Type: observed-state
- Sources: docs/DECISIONS.md:4709-4714; docs/INCIDENT_RESPONSE.md:101-128
- Related IDs: D-092, D-137, D-085
- Temporal: recovery recorded post-S40 (2026-07-27 era)
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: supersedes three sessions' "blocked on missing credential" records.
- Evidence still required: Phase 3 — confirm the `random_password` resources exist in terraform.
- Confidence: MEDIUM — the recovery fact is explicit; whether older "blocked" statements were corrected in place is unchecked.

---

## §4 — Cost controls, observability, alerting, spend accounting (COST-01…COST-29)

### COST-01 — All paid calls funnel through BedrockGateway with cost controls
- Domain: cost-control
- Claim: SPEC requires a single `BedrockGateway` abstraction whose stated benefits include retry policy, timeouts, token accounting, cost control and circuit breaking — every paid model call inherits these rather than reimplementing them.
- Type: requirement
- Sources: docs/SPEC.md:2515-2537
- Related IDs: none
- Temporal: SPEC-original
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none (spec is authority for its own requirement)
- Confidence: HIGH.

### COST-02 — Only two of SPEC's six gateway methods exist; four dispositioned by name
- Domain: cost-control
- Claim: Of §5.25.1's six methods only `generate_structured` and `create_embedding` exist; `generate_stream`/`classify` have no caller (D-022), `analyze_image` is deferred with S29 (D-078), and `judge` dispatches through `generate_structured` — verified independently in `packages/evals`' judge rather than taken from a docstring.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:222-236
- Related IDs: D-022, D-078
- Temporal: tranche 1
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found (a documented disposition). See REQ-19.
- Evidence still required: Phase 3 — read `bedrock.py:4-13` and the gateway to confirm the method set.
- Confidence: MEDIUM.

### COST-03 — Gateway implements bounded retry, max-token ceiling, per-session budget, circuit breaker
- Domain: cost-control
- Claim: `gateway.py:58-110` is documented as implementing bounded retry, a max-token ceiling, a per-session cost budget and a circuit breaker, with three named test files.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:222-228
- Related IDs: none
- Temporal: undated
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-claimed)
- Contradicts/competes: COST-05 (this is the "caps enforced" half only)
- Evidence still required: Phase 3 — read gateway source and the three named test files.
- Confidence: MEDIUM.

### COST-04 — Worst-case cost pre-flight reservation in the gateway
- Domain: spend-accounting
- Claim: `worst_case_cost_cents` (gateway.py:158) is the pre-flight reservation bounding a call before it is made.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:224-225
- Related IDs: none
- Temporal: undated
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-claimed)
- Contradicts/competes: COST-09 (the Postgres `cost_reservations` path explicitly does not cover the per-session gateway budget)
- Evidence still required: Phase 3 — read the function and its call sites.
- Confidence: MEDIUM.

### COST-05 — "Caps are enforced" and "spend is recorded correctly" are different claims (D-294)
- Domain: spend-accounting
- Claim: A 2026-08-12 scope correction found `question_validation_runs.cost_cents` omitted the per-slot equation-design call, understating accepted rows by a measured 32.0%; both halves are now said to be traced, pinned by a named test and re-checked by `scripts/measure_spend_reconciliation.py`.
- Type: historical-event
- Sources: docs/TRACEABILITY.md:237-248
- Related IDs: D-294
- Temporal: 2026-08-12
- Candidate status: CURRENT (fix), HISTORICAL (defect)
- Intended vs observed: both
- Contradicts/competes: COST-03 (which covered enforcement only). See REQ-20.
- Evidence still required: Phase 3 — run/read the script and the named test.
- Confidence: HIGH — explicit, dated, measured.

### COST-06 — Residual untested spend path: `skipped_duplicate_id`
- Domain: spend-accounting
- Claim: The `skipped_duplicate_id` path is explicitly not covered by a test — the row is rolled back and the money stays attributable only to the run total; D-294 records why it cannot be fixed at the row.
- Type: open-work
- Sources: docs/TRACEABILITY.md:246-248
- Related IDs: D-294
- Temporal: recorded 2026-08-12
- Candidate status: UNKNOWN — an accepted limitation whose currency is unasserted
- Intended vs observed: observed-state
- Contradicts/competes: COST-05's "now both are traced"
- Evidence still required: Phase 3 — read D-294 and grep curriculum tests for the path.
- Confidence: MEDIUM.

### COST-07 — A ceiling that is accounted but not threaded is decoration (AUD-L-02)
- Domain: cost-control
- Claim: Tranche 2's governing rule: each money row is checked for reachability, not presence, because AUD-L-02 [AUDIT_FINDINGS] was a P0 where a cost ceiling existed but was passed `session_spend_cents=0.0` and could never fire.
- Type: invariant
- Sources: docs/TRACEABILITY.md:271-277
- Related IDs: AUD-L-02 [AUDIT_FINDINGS]
- Temporal: undated; AUD-L-02 prior
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: none for the rule.
- Confidence: HIGH.

### COST-08 — Authoring pipeline cost ceiling verified reachable, plus a per-slot ceiling
- Domain: cost-control
- Claim: A `_spend` accumulator maintains a running total that every downstream call site receives (not the initial value), and per-slot spending is additionally bounded by `budget_ceiling_cents`.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:319-325
- Related IDs: AUD-L-02 [AUDIT_FINDINGS]
- Temporal: undated
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-claimed)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read `ai_pipeline.py`'s `_spend` threading and the budget tests.
- Confidence: MEDIUM.

### COST-09 — Per-day paid-API ceilings reserve before they spend, on a separate connection
- Domain: spend-accounting
- Claim: Per-day ceilings were previously read-then-spend with the cost row committed after the response (ten concurrent reports cost 10× the ceiling — AUD-X-08/D-110 §2); callers now reserve worst-case cost in `cost_reservations` in an immediately-committed transaction before the model call, settle after, serialized by `pg_advisory_xact_lock`; unsettled reservations stay charged at estimate (over-counting is the safe direction). The per-session gateway budget is explicitly not covered and stays stateless by design (D-072).
- Type: decision
- Sources: docs/ARCHITECTURE.md:517-528
- Related IDs: AUD-X-08 [AUDIT_FINDINGS], D-110, D-072, S42
- Temporal: S42-era (D-110)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: COST-04 (two reservation mechanisms with a stated coverage gap between them)
- Evidence still required: Phase 3 — read `CostReservationRepository`, `settle()`, the advisory-lock call.
- Confidence: HIGH.

### COST-10 — A paid call needs an input bound sized against the timeout (D-141)
- Domain: cost-control
- Claim: The gateway bounded output tokens, timeouts, retries, circuit and per-session spend but nothing bounded input — `memory-consolidate` built a 215,355-token prompt; the input bound must be sized against the timeout, not the context window.
- Type: decision
- Sources: docs/ARCHITECTURE.md:529-532
- Related IDs: AUD-F-34 [AUDIT_FINDINGS], AUD-F-36 [AUDIT_FINDINGS], D-141
- Temporal: D-141 (2026-07-31)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: COST-01 (SPEC's benefit list names no input bound)
- Evidence still required: Phase 3 — confirm the input bound exists in gateway code.
- Confidence: MEDIUM — read window cut the source bullet mid-sentence.

### COST-11 — Bedrock spend attributable per student/session via a trace_id join, no new code (D-400)
- Domain: spend-accounting
- Claim: D-400 rejects the audit's "never per student or per session" as too strong: `bedrock_call` carries no session id but the formatter stamps `trace_id` on every line and the access line carries `learning_session_id` in the same log group, so the join happens in a Logs Insights `stats`; trace coverage measured 2209/2212 narrative and 297/299 personalization calls (~99.9% of the spend that matters).
- Type: decision
- Sources: docs/INCIDENT_RESPONSE.md:222-260
- Related IDs: D-400, D-393
- Temporal: 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state (queries executed against staging)
- Contradicts/competes: COST-23 (the audit's finding and its "still open" listing)
- Evidence still required: Phase 3 — confirm whether any doc still lists spend-attribution as open.
- Confidence: HIGH.

### COST-12 — `latest()` not `max()`: the query defect that only running it caught
- Domain: observability
- Claim: The first attribution query used `max(learning_session_id)`, which Logs Insights treats as numeric and silently returned no field while appearing to work — the document's recurring "a control that cannot succeed" class.
- Type: historical-event
- Sources: docs/INCIDENT_RESPONSE.md:224-225, 250-255
- Related IDs: D-400
- Temporal: D-400 authoring
- Candidate status: CURRENT (as a documented caveat)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: none.
- Confidence: HIGH.

### COST-13 — The two tests that keep the spend/session join working (D-393, D-400)
- Domain: observability
- Claim: `test_the_500_access_line_carries_a_trace_id` pins that the access line carries the server span's trace id under real instrumentation, and `test_a_detached_task_logs_the_trace_id_of_the_request_that_spawned_it` pins that a detached task inherits it after the span closed — without the second, attribution silently fails for ~80% of spend (deferred work).
- Type: observed-state
- Sources: docs/INCIDENT_RESPONSE.md:286-293
- Related IDs: D-393, D-400
- Temporal: 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state (doc-claimed)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — grep both test names and confirm assertions.
- Confidence: MEDIUM.

### COST-14 — Report spend deliberately unjoinable by trace; attributed in Postgres instead
- Domain: spend-accounting
- Claim: Spend on routes keyed by `student_id` cannot be joined via the access log because `student_id` is deliberately excluded from loggable path params; that spend is attributed per student per day from `cost_reservations` (`scope='student_report'`/`'tutor_chat'`) — and this SQL is schema-verified but **not row-verified against staging**, unlike the two log queries.
- Type: observed-state
- Sources: docs/INCIDENT_RESPONSE.md:262-278
- Related IDs: D-400
- Temporal: D-400
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: COST-11's ~99.9% is scoped to log-joinable spend only.
- Evidence still required: Phase 3 — run/read the query shape against the model.
- Confidence: HIGH — the doc itself flags the weaker verification level.

### COST-15 — Measured 30-day staging spend baseline, 80% in one task
- Domain: spend-accounting
- Claim: Over 30 days on staging, `stage_narrative` spent 404.5¢ across 2212 calls — 80% of learning-api Bedrock spend — with unit costs ~0.18¢/narrative and ~0.24¢/personalized hint, so a spike is either volume or a model change and dividing distinguishes them.
- Type: observed-state
- Sources: docs/INCIDENT_RESPONSE.md:239-247
- Related IDs: D-400
- Temporal: 30-day window ending ~2026-08-17
- Candidate status: HISTORICAL — a point-in-time baseline that ages
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — re-run if a current baseline is needed.
- Confidence: HIGH.

### COST-16 — Cost-anomaly playbook: existing controls and the response levers
- Domain: alerting
- Claim: The playbook names the AWS Budget alarm as the first real signal, plus the gateway's per-session cap and circuit breaker; notes these bound only a single session while the likelier anomaly is many normal sessions or an abuser against the D-087 stopgap limiter; prescribed levers are lowering `bedrock_session_budget_cents` or scaling `desired_count` to 0.
- Type: requirement
- Sources: docs/INCIDENT_RESPONSE.md:202-220
- Related IDs: D-087, S33
- Temporal: S33-era, pre-D-400 section
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the Budget alarm and circuit variables exist in terraform/settings.
- Confidence: MEDIUM — playbook asserts these are already built.

### COST-17 — P1-5 [AUDIT_2026_08_16]: the crash sink had no metric and no alarm
- Domain: alerting
- Claim: `client_errors.py` was built in both apps (D-328 learning, D-372 chat) so a student's blank screen reaches someone, and `$.event="client_error"` is directly metric-filterable — yet there was no filter, no alarm, no counter: the reporting half shipped, the noticing half did not.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:138-144, 280-282
- Related IDs: P1-5 [AUDIT_2026_08_16], D-328, D-372, D-377
- Temporal: found 2026-08-16; fixed per the in-file status block (batch B, D-377)
- Candidate status: SUPERSEDED (fixed) — D-419's routing inventory lists client errors on the page channel
- Intended vs observed: observed-state at 2026-08-16
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read alarms config for the `client_error` filter + alarm and its topic.
- Confidence: HIGH for the finding; fix corroborated by two sources.

### COST-18 — P1-6 [AUDIT_2026_08_16]: four nightly jobs report in unstructured print()
- Domain: observability
- Claim: Read live from staging: all four enabled schedules fired and emitted plain text; a structured-event query returned only the deploy-time loader. Example line — 0 facts added, 3,181 events dropped over the call cap, 14.11 cents spent — is a job succeeding at doing nothing; "has the 90-day purge deleted anything this month" was unanswerable from metrics.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:146-154, 280-282
- Related IDs: P1-6 [AUDIT_2026_08_16], D-377
- Temporal: observed 2026-08-16
- Candidate status: SUPERSEDED per the batch-level "all 10 P1s closed" status block — but the block does not itemize P1-6
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read the four job entrypoints for structured logging; confirm a structured query now returns job lines.
- Confidence: MEDIUM — closure asserted only at batch granularity.

### COST-19 — P1-7 [AUDIT_2026_08_16]: no dead-man's switch on any schedule
- Domain: alerting
- Claim: The existing alarm watched ECS task exit ≠ 0, so a job that never runs fires nothing; zero `AWS/Scheduler` alarms existed and the only instrument was manual. Prescribed fix: one alarm per job with `treat_missing_data="breaching"` — the inverse posture of every existing alarm, because here missing data is the incident.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:156-164, 280-282
- Related IDs: P1-7 [AUDIT_2026_08_16], D-377, D-419
- Temporal: 2026-08-16
- Candidate status: SUPERSEDED — D-419's routing table names "all four job heartbeats" on the page channel, implying heartbeat alarms exist
- Intended vs observed: both (finding observed; the breaching posture is a recommendation)
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read the four heartbeat alarms and confirm `treat_missing_data="breaching"`.
- Confidence: MEDIUM — existence inferred from D-419's inventory; posture unverified.

### COST-20 — P1-8 [AUDIT_2026_08_16]: a broken attendance gate goes silent instead of spiking
- Domain: observability
- Claim: `graph/nodes.py:379`'s except returned above `ATTENDANCE_CHECKS.inc()`, and the metric declares `"present"|"blocked"|"unknown"` while `"unknown"` is emitted nowhere — so the one metric separating "MySQL adapter down" from "quiet night" read flat in both cases while the ALB stayed 200. Two lines to fix; material because UNKNOWN→blocked is a routine production path (D-152 §2).
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:166-174, 282
- Related IDs: P1-8 [AUDIT_2026_08_16], D-152, D-377
- Temporal: 2026-08-16
- Candidate status: SUPERSEDED per "all 10 P1s closed"
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — read the attendance except block and grep for an `"unknown"` label emission.
- Confidence: MEDIUM — batch-level closure only.

### COST-21 — P1-10 [AUDIT_2026_08_16]: 22 product KPIs bridged to CloudWatch, zero alarms on any
- Domain: alerting
- Claim: Verified live: 21 metrics per service namespace against 26 alarms, none referencing a product KPI — while `alarms.tf` opens by criticising exactly that pattern. Suggested fix: low-watermark alarms on `learning_sessions_completed_total` and `qa_answers_total`.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:187-195
- Related IDs: P1-10 [AUDIT_2026_08_16], D-377, D-401
- Temporal: verified live 2026-08-16
- Candidate status: UNKNOWN — the status block claims all P1s closed with "four new application alarms reading OK", but PROGRESS records `sessions_completed_floor` **not deployed** (count gated on `daily_completed_sessions_floor` = 0), so at least one KPI alarm is configured-but-absent and no document states the variable was raised.
- Intended vs observed: both
- Contradicts/competes: COST-25 directly; the status block's own wording.
- Evidence still required: Phase 3 — enumerate deployed vs configured alarms; check `daily_completed_sessions_floor`.
- Confidence: MEDIUM — closure asserted, deployment contradicted downstream.

### COST-22 — `qa_service_degraded_total` cannot be alarmed on until its first outage
- Domain: alerting
- Claim: The counter is absent from the namespace because `prometheus_client` emits no series until `.labels()` is first called — so the metric built so a Bedrock outage stops reading as a surge of off-topic questions cannot be alarmed on until an outage creates it; fix is pre-initialising labels at import.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:191-195
- Related IDs: P1-10 [AUDIT_2026_08_16]
- Temporal: 2026-08-16
- Candidate status: UNKNOWN — not itemized in either status blockquote
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — grep for label pre-initialisation and an alarm on the metric.
- Confidence: HIGH for the finding and mechanism; status genuinely unresolved.

### COST-23 — All 26 alarms delivered to a single email address
- Domain: alerting
- Claim: The audit recorded all 26 alarms delivering to one email address (a 2am alarm and a parent's email arrive together at 8am), and Bedrock spend attributable per day/app but never per student/session.
- Type: audit-finding
- Sources: docs/AUDIT_2026_08_16.md:237-244, 20-22, 37
- Related IDs: D-400, D-401
- Temporal: 2026-08-16; still listed "open" in the file's own stale lines
- Candidate status: SUPERSEDED — single-inbox by D-401/D-419's two-topic split; attribution corrected by D-400 ("too strong")
- Intended vs observed: observed-state at 2026-08-16
- Contradicts/competes: COST-11, COST-24, COST-26 — the audit's own "still open" lines are stale relative to those.
- Evidence still required: Phase 3 — confirm the deployed alarm→topic mapping.
- Confidence: HIGH.

### COST-24 — D-401: split alarm severity across two SNS topics with a page-by-default rule
- Domain: alerting
- Claim: One permanently-firing informational alarm made every other alarm unreadable, so D-401 added a second SNS topic, moved three alarms on a narrow rule, made the page channel the default for anything new, and added a test failing on an unrouted alarm or a quietly-moved outage alarm. Recorded "Not applied — that is a deploy" at decision time.
- Type: decision
- Sources: docs/PROGRESS.md:260-264 region; docs/PROGRESS.md:15
- Related IDs: D-401, D-406, D-418, D-419
- Temporal: decided W9 (2026-08-17); applied by D-419 (2026-08-18)
- Candidate status: CURRENT (applied per D-419)
- Intended vs observed: intended-state at decision time
- Contradicts/competes: PROGRESS's top block still carries "still unapplied; yours to authorise" (see WORK-08 — an unresolved intra-corpus contradiction with ROADMAP W25/D-419).
- Evidence still required: Phase 3 — read D-401 and the unrouted-alarm test; terraform state.
- Confidence: HIGH.

### COST-25 — The configured alarm count and the deployed alarm count are not the same number
- Domain: alerting
- Claim: A correction to D-401: `sessions_completed_floor` is not deployed because its `count` is gated on `daily_completed_sessions_floor > 0` and that variable is 0 — of the three alarms routed to the quiet channel only two existed in staging.
- Type: audit-finding
- Sources: docs/PROGRESS.md:337-340
- Related IDs: D-401, D-406, D-419
- Temporal: recorded ≤2026-08-18
- Candidate status: UNKNOWN — D-419's applied table (four alarms moved) is consistent with the KPI floor alarm still not existing; no doc states the variable was raised
- Intended vs observed: observed-state
- Contradicts/competes: COST-21's closure claim.
- Evidence still required: Phase 3 — read `daily_completed_sessions_floor` and the alarm's count guard.
- Confidence: HIGH for the finding; MEDIUM that it still holds.

### COST-26 — D-419 applied the split, but the new SNS subscription is PendingConfirmation
- Domain: alerting
- Claim: D-419 created the `alerts-info` topic and moved four alarms to it while the page channel kept 5xx/p95/memory/bedrock/client-errors/databases/job-heartbeats; `aws sns list-subscriptions-by-topic` reports the new subscription as `PendingConfirmation`, so four informational alarms currently reach a topic with no confirmed subscriber — carried as next-session item 1, "one click, not optional".
- Type: observed-state
- Sources: docs/PROGRESS.md:29-31; docs/DECISIONS.md:28463-28490
- Related IDs: D-419, D-401, D-406, D-418
- Temporal: applied 2026-08-18
- Candidate status: CURRENT — an open defect at the top of PROGRESS
- Intended vs observed: both
- Contradicts/competes: COST-24's intent (the apply made those alarms quieter than intended).
- Evidence still required: Phase 3 — live SNS subscription state (user-side action).
- Confidence: HIGH — stated identically in two places.

### COST-27 — LangSmith cloud with PII masked at source, and a filter that watches the telemetry leg itself
- Domain: observability
- Claim: SPEC §5.32.1 requires LangSmith (not LangFuse) with either self-hosted Enterprise or Cloud plus complete PII masking; the implementation chose Cloud with `configure_langsmith()` forcing `LANGSMITH_HIDE_INPUTS/_OUTPUTS=true` (a test asserts it is not optional), so LangSmith receives node structure and timings only. D-242 corrected the earlier claim that prompt/response payloads leave AWS and added `LangSmithIngestFailed` per service because the leg 403'd silently since D-214 with zero runs delivered.
- Type: decision
- Sources: docs/SPEC.md:3006-3026; docs/ARCHITECTURE.md:2100-2115, 2156-2160
- Related IDs: D-214, D-242, D-084, D-213, S39
- Temporal: wired at D-214; live 2026-08-10 (D-242)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: SPEC §5.32.1's "choose one after contractual review" fork still reads open in SPEC — decided by D-214/D-242.
- Evidence still required: Phase 3 — read `configure_langsmith()` and its test; confirm the filter and alarm exist per service.
- Confidence: HIGH.

### COST-28 — LangSmith is the only egress leaving AWS; NAT existence carries a D-406/D-419 ambiguity
- Domain: cost-control
- Claim: The VPC default posture is zero internet egress (all AWS deps over PrivateLink); LangSmith SaaS is the sole exception, served by one NAT in one AZ, both NAT and tracing gated on `langsmith_tracing_enabled` so the gateway cannot be left billing after the feature is off.
- Type: decision
- Sources: docs/ARCHITECTURE.md:2148-2170
- Related IDs: D-084, D-214, D-406, D-419
- Temporal: D-084 posture; D-406 made the NAT follow its consumers
- Candidate status: UNKNOWN for the NAT's current existence — D-419 records the NAT "absent from the plan entirely, which is D-406's verification", and a "~$33/mo idle NAT" note exists in PROGRESS outside the re-verified ranges; the decision (NAT keyed to consumers) is CURRENT
- Intended vs observed: both — the ARCHITECTURE prose mixes past and present tense
- Contradicts/competes: see ARCH-29.
- Evidence still required: Phase 3 — terraform NAT/route resources + AWS state; date the $33/mo note before using it.
- Confidence: MEDIUM.

### COST-29 — Capacity is priced from measured points, and extrapolating past them is banned
- Domain: cost-control
- Claim: Throughput saturates near 5 concurrent requests/task; latency grows ~`concurrency^1.55`; D-136 prices `p95 ≈ 0.31 s × (r/2.5)^1.4` from r=12.5 (2 tasks) to r=2.5 (10 tasks) with the binding rule: do not extrapolate outside r ∈ [2.5, 12.5]. Headline: a comfortable p95 at the pilot's 25 concurrent costs three more tasks, not twenty-eight.
- Type: invariant
- Sources: docs/ARCHITECTURE.md:254-283
- Related IDs: D-132, D-134, D-136, SPEC §6.23; D-153 §3 (the purchase itself withdrawn)
- Temporal: measured at pinned 2 tasks (D-134/D-136 era)
- Candidate status: CURRENT (the measurement and rule); the r=5 purchase is WITHDRAWN per D-153 §3
- Intended vs observed: both
- Contradicts/competes: SPEC §6.23's 150-concurrent target is the named expensive case.
- Evidence still required: Phase 3 — only if reusing the table as current: confirm task size/count unchanged.
- Confidence: HIGH.

---

## §5 — Testing, traceability, audit state, verification method (TEST-01…TEST-28)

### TEST-01 — Criterion 1 declared MET on an explicitly written reading
- Domain: traceability
- Claim: §2.6 criterion 1 (100% of launch-scope SPEC requirements mapped to implementation + test, every discrepancy dispositioned) is recorded MET as of 2026-07-30 (D-129), on a reading stated in the file: it means *nothing is undecided*, not *nothing is missing* — the same shape as criterion 2's claim (D-123).
- Type: decision
- Sources: docs/TRACEABILITY.md:101-111
- Related IDs: D-129, D-123, T-02
- Temporal: met 2026-07-30; heading corrected 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: competes with the plain reading of the quoted criterion (TRACEABILITY.md:5-6), which T-02's unbuilt state does not satisfy.
- Evidence still required: Phase 3 — confirm D-129 states this reading; confirm no §5 section added since lacks a verdict.
- Confidence: HIGH — the reading is verbatim, not inferred.

### TEST-02 — "Unverified counts as not traced" is the binding evidence rule
- Domain: verification-method
- Claim: A row is traced only when it cites both an implementation location and a test that would fail if the requirement broke; anything else is unverified, and unverified counts as not traced.
- Type: invariant
- Sources: docs/TRACEABILITY.md:15-24, 108
- Related IDs: D-119, D-116, AUD-F-17 [AUDIT_FINDINGS]
- Temporal: method stated at file creation
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — sample rows and confirm each cites a test that exists.
- Confidence: HIGH.

### TEST-03 — Four-verdict vocabulary: traced / dispositioned / structural / gap
- Domain: verification-method
- Claim: Verdicts are traced (impl file:line + named failing test), dispositioned (not implemented, on purpose, with a DECISIONS entry), structural (artifact/convention, not behavior), gap (unmet or unpinned). A disposition in the code's own docstring citing a decision ID counts.
- Type: invariant
- Sources: docs/TRACEABILITY.md:26-34
- Related IDs: none
- Temporal: tranches 1–5 three verdicts; structural added in tranche 6
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: the file's own earlier "no fourth verdict" line, superseded openly (TRACEABILITY.md:36-41).
- Evidence still required: none.
- Confidence: HIGH.

### TEST-04 — The structural verdict is fenced: no enforcing mechanism, no structural verdict
- Domain: verification-method
- Claim: *structural* requires a citable artifact location and something mechanical that fails if the artifact disappears; with no mechanism it is a gap. The fence is recorded in the body because adding a category mid-method is how a rubric gets softened.
- Type: invariant
- Sources: docs/TRACEABILITY.md:36-51, 618-627
- Related IDs: none
- Temporal: tranche 6
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify the six structural sections' named mechanisms exist.
- Confidence: HIGH.

### TEST-05 — §5.3 and §5.36 are recorded as descriptive, requiring human re-read on architecture change
- Domain: traceability
- Claim: Two structural candidates fail the mechanism clause and are recorded as *descriptive*: §5.3 and §5.36 — flagged for human re-reading when the architecture changes, rather than trusting a test to notice.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:45-47, 622, 626, 629-633
- Related IDs: none
- Temporal: tranche 6
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: sits under the 37-of-37 claim while being neither traced nor structural.
- Evidence still required: Phase 3 — check whether any architecture change since triggered the owed re-read.
- Confidence: HIGH.

### TEST-06 — Launch-scope exclusions are enumerated with owning decisions
- Domain: traceability
- Claim: Launch scope is §5 minus four deliberate removals: §5.17 + §6.19 (D-078), §5.30.3's Pod Security/NetworkPolicy (D-004, EKS-only), and §5.30.3's WAF (D-087, tracked to S50 A7). §6's phases are traced through their §5 sections.
- Type: decision
- Sources: docs/TRACEABILITY.md:55-68
- Related IDs: D-078, D-004, D-087
- Temporal: predates D-129
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the three decisions say what the table attributes.
- Confidence: HIGH.

### TEST-07 — 37 of 37 launch-scope sections swept, no open discrepancy
- Domain: traceability
- Claim: All 37 launch-scope §5 sections carry a verdict across tranches 1–6, and the Discrepancies table reports Open: none, with T-02 dispositioned.
- Type: observed-state
- Sources: docs/TRACEABILITY.md:72, 99, 635, 641-650, 761-762
- Related IDs: T-01, T-02, D-129
- Temporal: as of D-129; heading corrected 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: the "What remains" tail (TRACEABILITY.md:768-773, 782) still lists 16 sections in present tense under a "nothing remains to sweep" banner — stale residue.
- Evidence still required: Phase 3 — count verdict-bearing sections to confirm 37.
- Confidence: MEDIUM — self-reported count; the tail was never rewritten.

### TEST-08 — The file self-reports a heading that contradicted its own table (instrument reliability)
- Domain: audit-state
- Claim: The Status heading read "the criterion turns on one open discrepancy" after T-02 was dispositioned, while the Discrepancies section said Open: none — and that "Open: none" line was itself written in the same commit (`c44414f`) as a table still showing T-02 open. Recorded as the near-miss the file warns about: a summary agreeing with the desired claim above a table contradicting it is how a rubric passes itself.
- Type: historical-event
- Sources: docs/TRACEABILITY.md:74-78, 641-645
- Related IDs: T-02, D-129
- Temporal: introduced in `c44414f`; corrected 2026-08-17
- Candidate status: HISTORICAL (defect), CURRENT (warning)
- Intended vs observed: observed-state
- Contradicts/competes: reason to discount headings in this file relative to tables.
- Evidence still required: Phase 3 — `git show c44414f`.
- Confidence: HIGH — self-reported with a commit hash.

### TEST-09 — T-01 closed with two opposite answers
- Domain: traceability
- Claim: T-01 closed 2026-07-30 (D-125) as two opposite answers — CloudTrail built and live-verified; GuardDuty deferred with a written reason, tracked to S50 A7. What changed is the record, not the state.
- Type: decision
- Sources: docs/TRACEABILITY.md:649, 700-720
- Related IDs: T-01, D-125, D-124, D-087, AUD-F-12 [AUDIT_FINDINGS]
- Temporal: closed 2026-07-30
- Candidate status: CURRENT (closure); DEFERRED (GuardDuty half)
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm `terraform/modules/cloudtrail/` wired in staging.
- Confidence: HIGH.

### TEST-10 — T-02 dispositioned as scheduled-not-shipped, with §6.1-track-before-S45 ordering
- Domain: traceability
- Claim: T-02 is dispositioned (D-129) and split: the §6.1 legal track enumerates the eleven disclosures as a written deliverable; S45 builds the notice; the order is load-bearing (the disclosure list gates the build); the item is explicitly still not built.
- Type: plan
- Sources: docs/TRACEABILITY.md:109-120, 650-698
- Related IDs: T-02, D-129, D-114 §4
- Temporal: dispositioned 2026-07-30; §6.1 track not started at writing
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found — the gap is stated openly.
- Evidence still required: Phase 3 — whether the §6.1 track has started; whether any notice component exists.
- Confidence: HIGH.
- **Annotation 2026-08-20 (step 7d, W-43): the temporal note above ("§6.1 track not started at
  writing") is SUPERSEDED.** The enumeration half of the §6.1 track shipped on **2026-08-15** as
  `docs/FIRST_VISIT_NOTICE.md` — "SPEC §5.1.2's eleven disclosures, enumerated (T-02)", all eleven
  written out as copy in a younger-reader and a standard form, each paired with the system fact it
  must stay true to (commit `da2549f`, 2026-08-15). So the deliverable this row calls the gate on
  S45 **exists**. Two things this does **not** change: the *build* half is still unbuilt (the file
  states "S45 transcribes this; it does not draft it" — the capture UI, age-band derivation and
  consent record are S45's), and **counsel review remains a launch gate** (§6.1). Read the row's
  `DEFERRED` status as applying to the build, not the enumeration. `docs/TRACEABILITY.md`'s T-02
  block carries the same stale assertion and is corrected separately (W-43, step 11 batch F); this
  annotation is **not** progress on `DISCLOSURES-LEGAL`.

### TEST-11 — Traced-to-deleted-code: D-226 rewrote the §5.8.3–.5 rows
- Domain: verification-method
- Claim: Until D-226, the §5.8.3/.4/.5 block traced SPEC's stage chain to the shape route — code that was deleted because nothing it produced could ever be served — so the previous row was "evidence for a requirement satisfied by code no student could reach": traced against the wrong implementation rather than untraced.
- Type: historical-event
- Sources: docs/TRACEABILITY.md:280-295, 323-327
- Related IDs: D-226, D-224, D-223, D-210 (phantom — no own entry), AUD-L-02 [AUDIT_FINDINGS]
- Temporal: measured D-224, removed D-226 (2026-08-08)
- Candidate status: CURRENT (corrected row); HISTORICAL (the mis-tracing)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the authored route and named rejection tests exist and pass.
- Confidence: HIGH.

### TEST-12 — A traced gate was traced to a call most edits never reached (D-235)
- Domain: verification-method
- Claim: §5.8.5's load-time half was traced to `validate_authored_item` inside the loader — but the loader skipped by id above that call, so for items already in a database the gate was unreachable and edits were discarded silently. The pre-existing test passed because it used a new id: it proved the gate fires on insert and was read as proving it fires on edit.
- Type: audit-finding
- Sources: docs/TRACEABILITY.md:297-305
- Related IDs: D-235
- Temporal: fixed at D-235 (2026-08-09)
- Candidate status: CURRENT (fixed; a method note)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — run/inspect the both-halves propagation test.
- Confidence: HIGH.

### TEST-13 — The floor-reading lesson (D-172): traced ≠ enforced
- Domain: verification-method
- Claim: Two of §5.21.8's seven do-not-answer triggers were traced to checks that verified less than their names implied ("retrieval score below threshold" had no implementation; the citation floor was one character). Both are now traced to measured floors (`MIN_RERANK_RELEVANCE_SCORE=0.35`, `MIN_CITATION_QUOTE_CHARS=20`). Read as method: "traced" means the check's floor was read, not only that a check exists.
- Type: invariant
- Sources: docs/TRACEABILITY.md:472-483
- Related IDs: D-172, AUD-C-12 [AUDIT_FINDINGS], AUD-C-13 [AUDIT_FINDINGS]
- Temporal: D-172 (2026-08-04)
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — inspect the constants and their band-asserting tests.
- Confidence: HIGH.

### TEST-14 — One floor is deliberately not applied on the reranker-degraded path
- Domain: testing
- Claim: The retrieval-score floor is deliberately not applied when the reranker is unavailable (D-172 §3); the degraded path is loud and pinned by `test_the_floor_does_not_apply_when_the_reranker_is_unavailable`. (Same substance as REQ-15, kept as the testing-side claim.)
- Type: decision
- Sources: docs/TRACEABILITY.md:203-209
- Related IDs: D-172 §3, AUD-C-08 [AUDIT_FINDINGS], AUD-C-19 [AUDIT_FINDINGS]
- Temporal: D-172
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found — recorded so it is not re-read as a gap.
- Evidence still required: Phase 3 — run/inspect the named test.
- Confidence: HIGH.

### TEST-15 — AUDIT_FINDINGS register: 0 open, with the arithmetic written out because the line was wrong three times
- Domain: audit-state
- Claim: AUDIT_FINDINGS.md reports open findings counted from both Index halves as 0 (D-174, recounted through D-183), with the arithmetic spelled out "because this line has now been wrong three times"; the Phase 0B backlog is called empty for the first time.
- Type: observed-state
- Sources: docs/AUDIT_FINDINGS.md:159-169
- Related IDs: D-174…D-183; AUD-F-32/AUD-C-09 [AUDIT_FINDINGS] (dispositioned, not open)
- Temporal: register frozen at 2026-08-05 (D-183)
- Candidate status: CURRENT as of 2026-08-05 — UNKNOWN as a project-wide statement (the 08-16 and 08-17 audits filed 46+48 findings in separate namespaces)
- Intended vs observed: observed-state
- Contradicts/competes: AUDIT_LIVE_2026_08_17.md's own open list is a different register — not the same count.
- Evidence still required: Phase 3 — re-run the anchored awk against current AUDIT_FINDINGS.md.
- Confidence: HIGH for the register's self-report; MEDIUM as current audit state overall.

### TEST-16 — The open count must be derived by ROADMAP's anchored awk, not read from any sentence
- Domain: verification-method
- Claim: The 0-open figure is "confirmed by running ROADMAP's anchored awk, not by counting this sentence"; ROADMAP records its own count line having been wrong twice before — the argument for deriving rather than reading, "this one included."
- Type: invariant
- Sources: docs/AUDIT_FINDINGS.md:166; docs/ROADMAP.md:706-712, 761-773, 783-784
- Related IDs: D-174, D-181, D-183
- Temporal: recipe corrected 2026-08-04
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found — the designated tiebreaker over prose counts.
- Evidence still required: Phase 3 — execute the awk and record actual output.
- Confidence: HIGH.

### TEST-17 — 27 findings had a detail section and no Index row; backfilled by D-174
- Domain: audit-state
- Claim: The Index stopped being maintained, so 27 findings had a section and no row (89 sections, 68 rows), breaking "one row per finding"; two open findings were invisible to every table-derived count and five headings still read "not fixed" after their fixes landed (all corrected the same day). The pre-D-174 count was "wrong in both directions."
- Type: historical-event
- Sources: docs/AUDIT_FINDINGS.md:103-123, 131-150, 179-180; docs/ROADMAP.md:734-747
- Related IDs: D-174; AUD-F-22/F-33/F-21/F-25/F-27/F-34/X-13/F-16 [all AUDIT_FINDINGS]
- Temporal: backfilled 2026-08-04
- Candidate status: HISTORICAL (breach); CURRENT (backfill + recount instruction)
- Intended vs observed: observed-state
- Contradicts/competes: invalidates the pre-D-174 count.
- Evidence still required: Phase 3 — verify every section now has a row.
- Confidence: HIGH.

### TEST-18 — The counting instrument itself has four recorded failure modes
- Domain: verification-method
- Claim: ROADMAP records four ways the finding count goes wrong: carrying it forward; table-derived counts missing row-less findings; naive `grep -i open` over-counting (rows carry their own history in the status cell); and a stray pipe shifting the positional field (four rows carry an extra pipe, checked, all still correct). The duplicate `### AUD-C-16` heading is one finding with two sections, owing no renumber.
- Type: invariant
- Sources: docs/ROADMAP.md:734-765, 749-753, 786-790
- Related IDs: D-174, D-178; AUD-C-14/C-15/L-16/F-16/C-16 [all AUDIT_FINDINGS]
- Temporal: warnings accreted 2026-08-04+
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm the four extra-pipe rows still keep status in field 5.
- Confidence: HIGH.

### TEST-19 — Diagnosis does not close a finding, and neither does shipping a fix whose verification is owed
- Domain: verification-method
- Claim: AUD-F-33 [AUDIT_FINDINGS] is the recorded case: D-182 found the mechanism and shipped the fix and the count did not move; only D-183's live read (Auto Scaling accepting the metric-math alarm, forced for $0) moved it to 0.
- Type: invariant
- Sources: docs/ROADMAP.md:726-732, 773-784; docs/AUDIT_FINDINGS.md:149, 166-169
- Related IDs: D-182, D-183, AUD-F-33 [AUDIT_FINDINGS]
- Temporal: 2026-08-04/05
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: none for the rule; the live rows are AWS-side.
- Confidence: HIGH.

### TEST-20 — AUD-L-17 → AUD-L-19 renumber applied per reference, with ranges deliberately left ambiguous
- Domain: audit-state
- Claim: One id named two findings; resolved (D-174) by renumbering D-159's P2 to `AUD-L-19` while the P3 keeps `AUD-L-17`. The id was ambiguous in 33 places across five documents; the renumber was applied per reference, not by global replace — ranges like `AUD-L-10..AUD-L-17` and P3 narrative passages were deliberately left, and pre-2026-08-04 documents still cite the P2 as `AUD-L-17`.
- Type: decision
- Sources: docs/AUDIT_FINDINGS.md:182-200, 35, 43; docs/ROADMAP.md:744-745
- Related IDs: AUD-L-17/AUD-L-19/AUD-L-11 [AUDIT_FINDINGS], D-174, D-159
- Temporal: 2026-08-04
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: collides with `AUD-L-17`/`AUD-L-19` in AUDIT_LIVE_2026_08_17.md:43,45 (child chooser; narrative replay) — a different namespace entirely; the file's own disambiguation heuristic does not work across documents.
- Evidence still required: Phase 3 — grep surviving `AUD-L-17` citations and classify each.
- Confidence: HIGH.

### TEST-21 — A green Playwright suite coexisted with two live P1s on the same build
- Domain: testing
- Claim: The suite was green on build `gha-6841d9d9b169` (88 passed / 7 skipped) hours before the 2026-08-17 live audit found both P1s live in that build; stated as a statement about coverage, not a suite failure, with the open list called "the more valuable half of this audit."
- Type: observed-state
- Sources: docs/AUDIT_LIVE_2026_08_17.md:3-9, 15-16
- Related IDs: D-381; AUD-CHAT-02 [AUDIT_LIVE_2026_08_17], AUD-L-01 [AUDIT_LIVE_2026_08_17]
- Temporal: 2026-08-17
- Candidate status: HISTORICAL (the run); CURRENT (the coverage lesson)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — none for the past run; compare current counts (PROGRESS: 127/2).
- Confidence: HIGH.

### TEST-22 — The 2026-08-17 audit's three coverage blind spots, all closed by D-383
- Domain: testing
- Claim: Three blind spots — nothing terminal ever completed; every approval gate declined, never approved; every failure injected client-side — all closed 2026-08-17 (D-383, Milestone 11), each producing a defect within minutes of being looked at.
- Type: audit-finding
- Sources: docs/AUDIT_LIVE_2026_08_17.md:78-103; docs/ROADMAP.md:2509-2588
- Related IDs: D-381, D-383, D-378, D-375
- Temporal: filed and closed 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — run/inspect the six named specs/tests created by the closures.
- Confidence: HIGH.

### TEST-23 — The approval-gap phrasing was corrected: API-level approvals had happened, UI approvals had not
- Domain: audit-state
- Claim: Blind spot 2's phrasing is explicitly corrected as broader than the truth: both approval gates were already approved at the API level (two named pytest tests assert the send, recipient, and `InterruptApproval` row); what had never happened is approving through the UI.
- Type: audit-finding
- Sources: docs/AUDIT_LIVE_2026_08_17.md:88-89; docs/ROADMAP.md:2537-2552
- Related IDs: D-383, CLAUDE.md rule 4
- Temporal: corrected 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: supersedes the uncorrected wording still present at AUDIT_LIVE_2026_08_17.md:97-99.
- Evidence still required: Phase 3 — confirm the two named tests exist.
- Confidence: HIGH.

### TEST-24 — One item from the error-vocabulary closure is deliberately still open (the real 429)
- Domain: open-work
- Claim: A genuine HTTP 429 has never rendered and remains deliberately open: reachable only through the message limiter (too expensive to drive) or the global middleware (a load test), while the escalation limiter is in-graph and returns 200 with `RATE_LIMITED_MESSAGE`, not a 429.
- Type: open-work
- Sources: docs/AUDIT_LIVE_2026_08_17.md:84-86; docs/ROADMAP.md:2580-2583
- Related IDs: D-383, AUD-C-27 [AUDIT_FINDINGS]
- Temporal: recorded open 2026-08-17
- Candidate status: CURRENT / DEFERRED
- Intended vs observed: observed-state
- Contradicts/competes: qualifies TEST-22's "all three closed".
- Evidence still required: none required to confirm openness.
- Confidence: HIGH.

### TEST-25 — What remains un-walked per AUDIT_LIVE's own successive narrowings
- Domain: open-work
- Claim: The never-exercised list was narrowed four times the same day (D-385 route-admission parity; D-387 PII-typed-by-a-visitor; D-388 deployed-authorization 6/6; D-389 ErrorBoundary loop, found broken); what the file states still remains un-walked: the exam timer, the calendar interrupt's `.ics` branch, and learning-web's tutor-chat browser leg.
- Type: open-work
- Sources: docs/AUDIT_LIVE_2026_08_17.md:105-142
- Related IDs: D-385, D-387, D-388, D-389, D-381
- Temporal: 2026-08-17 in-file
- Candidate status: PARTLY SUPERSEDED — later decisions outside this file closed two of the three: the exam timer (D-391, three defects fixed) and the `.ics` branch (D-392→D-397→D-399, closed via the DOM-contract spec; verified in the supersession map, chain H3). The tutor-chat browser leg was built by D-398. The file itself was never updated with these closures.
- Intended vs observed: observed-state
- Contradicts/competes: DECISIONS D-391/D-392/D-397/D-398/D-399 vs this file's still-open list.
- Evidence still required: Phase 3 — confirm the three specs exist.
- Confidence: HIGH — closure chain verified against DECISIONS directly.

### TEST-26 — The error-vocabulary clause was closed against a programmatic enumeration, not a feeling
- Domain: testing
- Claim: Closure counted the rules in both `errors.ts` tables programmatically (learning-web 10, chat-web 8), surfacing two chat 409s with no rendered evidence; final state 18 of 18 rendered, except learning-web's 401, excluded with a reason (D-375 signs the student out; a named spec owns that path).
- Type: observed-state
- Sources: docs/ROADMAP.md:2554-2587
- Related IDs: D-383, D-375, D-378
- Temporal: 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — re-run the enumeration against both `errors.ts` files.
- Confidence: HIGH.

### TEST-27 — The e2e harness enforces criterion 3 at teardown, so a journey cannot pass by never looking
- Domain: testing
- Claim: `e2e/` is the Playwright harness for §2.3's browser half and §2.6 criterion 3; `fixtures/capture.ts` attaches console+network capture to every page and enforces zero console errors, zero 5xx, zero blank/stuck states at teardown over the whole run, with error-path narrowing only via explicit `audit.allow({...})`; every run appends one JSON line per test to `artifacts/journeys.jsonl`.
- Type: invariant
- Sources: e2e/README.md:1-32
- Related IDs: D-097; AUD-F-02/F-16/F-17/F-18 [AUDIT_FINDINGS]
- Temporal: built S39
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — inspect `e2e/fixtures/capture.ts`.
- Confidence: HIGH.

### TEST-28 — Current suite counts as stated in PROGRESS
- Domain: testing
- Claim: PROGRESS's current verification line states 0 typecheck errors, pytest 1735 passed / 2 skipped, Playwright 127 passed / 2 skipped, chat-web 49 unit tests, learning-web 26 — higher than the 88/7 recorded for the 2026-08-17 audit build.
- Type: observed-state
- Sources: docs/PROGRESS.md:35-38
- Related IDs: D-381 (the 88/7 build), Milestone 15
- Temporal: on merged main `6f107c1` (2026-08-18)
- Candidate status: CURRENT — doc-claimed, not re-run
- Intended vs observed: observed-state
- Contradicts/competes: none found — supersedes the 88/7 figure chronologically.
- Evidence still required: Phase 3 — re-run and compare.
- Confidence: MEDIUM.

---

## §6 — Integration, the D-152 freeze, production facts, org communications (INT-01…INT-35)

### INT-01 — Production system is immutable (user-set scope constraint)
- Domain: integration
- Claim: The production system powering intellichoice.org and go.intellichoice.org (`icrest`/`icweb` + the `ic` MySQL database) is declared **immutable**: no changes to its frontend, backend, schema, auth logic, credentials, deployment, security posture, or operational processes may be *planned*, even to fix known weaknesses; all compatibility problems are resolved inside the new stack, and pre-existing production risks may only be recorded as assumptions or accepted residual risks.
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:3-13; CLAUDE.md:51-52
- Related IDs: none
- Temporal: constraint set 2026-07-24 (supersedes two earlier drafts of the plan); restated 2026-08-01
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found (the freeze of *our integration work*, D-152, is a separate and additional constraint)
- Evidence still required: none
- Confidence: HIGH — stated verbatim as a user-set constraint in the plan's opening block and echoed in CLAUDE.md.

### INT-02 — Tier 0/1/2 boundary; calling production's login API is Tier 2 usage, not a production change
- Domain: integration
- Claim: The plan defines Tier 0 (prohibited: any change to production app code, schema, auth implementation, or existing behavior), Tier 1 (additive integration support — read-only DB account, network path, schema snapshots, scheduled exports, new DNS records; each labeled and each with a fallback if refused), and Tier 2 (the new stack absorbs all compatibility logic). Explicitly: "Calling production's existing public endpoints as-is (e.g., its login API) is Tier 2 usage of existing behavior, not a production change."
- Type: invariant
- Sources: docs/INTEGRATION_PLAN.md:15-27; :442-446
- Related IDs: O1/O1b, I11 rung 1
- Temporal: clarified 2026-07-24
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — explicit definitional text.

### INT-03 — D-152: finish and test against the fakes first, integrate later
- Domain: freeze
- Claim: User decision (D-152): "The existing system is already deployed and will stay untouched, but **real integration happens much later**. Until then the plan is: keep assuming the existing system via the dev fakes, finish and test this codebase, and only then join the two." It states it "supersedes the 'unblock S44 as soon as possible' posture that D-151's recommendations were written under."
- Type: decision
- Sources: docs/DECISIONS.md:8952-8957
- Related IDs: D-151, D-152; S44
- Temporal: accepted 2026-08-01
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: outranks INTEGRATION_PLAN §3.1's "finalized at S42 … before S44 implements" gate (INT-06) and the §5 session table (INT-07), neither of which mentions D-152
- Evidence still required: none (explicit user decision)
- Confidence: HIGH — decision record's own wording, and it names what it supersedes.

### INT-04 — CLAUDE.md standing "do not unblock integration" instruction
- Domain: freeze
- Claim: Unless the user explicitly says integration is starting, no session may measure AWS→icrest reachability, request the production API URL or a test account, finalize the §3.1 auth option, or rewrite the MySQL dev fake to match production's schema; S44+ items and S42_OPEN_QUESTIONS groups A/B/C/D must not be treated as blockers — they are "frozen by choice, not stuck." The seam must still be kept honest: any app-level decision depending on the fake's *schema* rather than the Protocol is a real defect.
- Type: requirement
- Sources: CLAUDE.md:54-68; docs/DECISIONS.md:9012-9018
- Related IDs: D-152 §5; groups A/B/C/D; O1b
- Temporal: recorded 2026-08-01, standing
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: INTEGRATION_PLAN §5's S42 row still describes exactly these measurements as live work
- Evidence still required: none
- Confidence: HIGH — normative instruction in CLAUDE.md, mirrored by D-152 §5.

### INT-05 — O1b is a recommendation, not a decision, and stays one until measured
- Domain: integration
- Claim: S42_DISCOVERY §8 recommends **O1b** (server-side call to `POST /api/accounts/login`, transient header-borne legacy token for `GET /api/accounts` and `GET /api/accounts/signups`, then the new stack mints its own SPEC §5.1.2 token) with O2 (HMAC re-verification) as documented fallback — and says of itself "**This is a recommendation, not a decision.**" CLAUDE.md adds that O1b stays a recommendation until measured, "right before S44."
- Type: recommendation
- Sources: docs/S42_DISCOVERY.md:301-322; docs/S42_DISCOVERY.md:37-42; CLAUDE.md:59-61; docs/DECISIONS.md:8889-8891
- Related IDs: D-151 §2, O1/O1b/O2/O3/O4, A4, B1, I11 rung 1
- Temporal: recommended 2026-08-01; decision deferred to just before S44
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: S42_OPEN_QUESTIONS A4 labels the auth option "[결정]" (decision) pending from the user — same substance, different framing
- Evidence still required: at integration time — B1 (AWS→icrest reachability) and B2 (deployed build matches checkout) before the option is finalized
- Confidence: HIGH — the doc self-labels its status.

### INT-06 — §3.1 auth decision gate as written ("finalized at S42") vs frozen reality
- Domain: integration
- Claim: INTEGRATION_PLAN §3.1 reads as live: the decision is "open until S42 discovery," the earlier hash-re-verification pre-selection is "withdrawn," and the **Decision gate** is "finalized at S42 (discovery) from evidence (login-API response shape/latency/reachability from AWS, signups-response contents, icrest availability history), recorded in DECISIONS.md before S44 implements." The file contains **zero mentions of D-152/D-153**, so this gate text has not been reconciled with the freeze.
- Type: plan
- Sources: docs/INTEGRATION_PLAN.md:230-288 (gate at :281-288)
- Related IDs: O1/O1b/O2, D-152, A4, B1–B3
- Temporal: written 2026-07-24; unamended as of the audit
- Candidate status: SUPERSEDED (as to timing/urgency) — the option matrix itself remains CURRENT reference material
- Intended vs observed: intended-state
- Contradicts/competes: D-152 (INT-03) and CLAUDE.md L59-61 (INT-04) forbid finalizing the auth option or measuring reachability now; the plan's own §5 places this at S42, which has already passed
- Evidence still required: Phase 3 — confirm whether INTEGRATION_PLAN is intentionally left as a pre-freeze artifact or is stale-and-misleading
- Confidence: HIGH — verified absence of D-152/D-153 strings in the file; gate text quoted.

### INT-07 — INTEGRATION_PLAN §5 session table and dependency spine read as live
- Domain: integration
- Claim: §5 assigns S42 = discovery + org asks (Tier 1 only) + auth decision gate; S43 = `IcProfileAdapter`; S44 = independent auth; S45 = consent; S46 = role scoping/frontend; S47 = integration test pass; S48–S51 = rollout/pilot, with the dependency spine "§2.6 gate → discovery (S42) → adapter → auth → consent/scoping → integration testing." Numbering beyond S41 is self-described as "indicative."
- Type: plan
- Sources: docs/INTEGRATION_PLAN.md:450-478
- Related IDs: I1–I15, O1b, D-152
- Temporal: written 2026-07-24; S42 executed 2026-08-01 (partially, from source)
- Candidate status: SUPERSEDED in part — S42's discovery half was executed from source (D-151); its measurement half is frozen (D-152)
- Intended vs observed: intended-state
- Contradicts/competes: D-152; §8 (:615-621) already shrinks the S42 row itself
- Evidence still required: Phase 3 — reconcile the table against actual session history (S42 discovery done, S43 partly in progress per D-154)
- Confidence: HIGH — table read directly.

### INT-08 — D-153 §4: timezone question closed by evidence, not by asking
- Domain: production-fact
- Claim: The public site publishes sessions **Monday–Friday 10:00–12:00 and 18:00–20:00, with no Sunday sessions and nothing between midnight and 01:00**; since the two candidate conventions (DST-aware Central vs legacy fixed UTC−6) diverge only for 00:00–01:00 starts (date) and Sunday evenings (week), they yield identical dates and weeks for every published session. Message A therefore "stops being a blocker of any kind" and becomes a courtesy question; the provisional default `America/Chicago`/`local_dst_aware` stands and `ORG_TIME_CONFIRMED` stays false.
- Type: decision
- Sources: docs/DECISIONS.md:9084-9103; docs/S42_OPEN_QUESTIONS.md:18-20
- Related IDs: D-153 §4, C1, C2, Message A, D-151 §4
- Temporal: 2026-08-02 (evidence = marketing site, not the operational `calendars` table)
- Candidate status: CURRENT
- Intended vs observed: both — marketing-site observed state used to close an intended-state question
- Contradicts/competes: S42_ORG_ASKS:12 still marks Message A "**Send now**"; S42_ORG_ASKS:388-389 says Message A is "due before S43 opens"; S42_DISCOVERY §7 (:274-278) calls Message A "still needed, unchanged"
- Evidence still required: at S43 — the recorded guard: assert no ingested session starts 00:00–01:00 local or on a Sunday evening, and log loudly if one ever does (D-153 explicitly limits the marketing-site evidence)
- Confidence: HIGH — decision text is explicit about both the conclusion and its limits.

### INT-09 — DNS (Message B / C3) is answered: possible, org adds records at integration time
- Domain: org-comms
- Claim: DNS additions for `learning.`, `chat.`, and a mail subdomain are confirmed possible; the org will add the records **at integration time**, so Message B / C3 is "answered, not pending."
- Type: decision
- Sources: docs/DECISIONS.md:9124-9125; docs/S42_OPEN_QUESTIONS.md:17
- Related IDs: D-153 §6, C3, Message B, A3, I13
- Temporal: answered 2026-08-02; records to be created at integration time
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: S42_OPEN_QUESTIONS:76 still lists C3 as 🔴 "미룰 수 없음" (cannot be deferred) and :110 lists "C3(DNS) 발송" as one of only two live actions — see INT-28; S42_ORG_ASKS:13 marks B "Send now"; D-152 §4 (:9006-9007) says DNS "stays worth sending"
- Evidence still required: at-integration-time — the records actually created (A3 assumption otherwise falls back to CloudFront default domains)
- Confidence: HIGH — D-153 §6 is unambiguous; the residual issue is doc staleness elsewhere.

### INT-10 — Capacity: planning assumption fixed at ~1,000 students across a week; peak concurrency still unmeasured
- Domain: production-fact
- Claim: The user fixed the planning assumption at **~1,000 students spread across a week**, with peak concurrency explicitly still unmeasured. Consequently the parked r=5 capacity purchase (+3 tasks, ~$43/month, D-139 §2) is **withdrawn, not deferred**, learning-api stays at 2 tasks (criterion-7 parity beats ~$14.42/month), and peak concurrency gets revisited at integration "when it is a measurement instead of an assumption."
- Type: decision
- Sources: docs/DECISIONS.md:9022-9025; :9068-9082; docs/S42_OPEN_QUESTIONS.md:21
- Related IDs: D-153 §1/§3, C8, Message D, D-134, D-139 §2
- Temporal: 2026-08-02
- Candidate status: CURRENT (measurement DEFERRED to integration)
- Intended vs observed: intended-state (assumption), the ~25-simultaneous-user ceiling is observed (D-134)
- Contradicts/competes: S42_ORG_ASKS:355-364 argues Message D is "worth sending now rather than at purchase time" — the purchase it justified is now cancelled
- Evidence still required: at-integration-time — real peak-concurrency measurement
- Confidence: HIGH — explicit numbers and dispositions in D-153.

### INT-11 — D-153 §7 correction: `Manager` is intended admin-only; the API does not enforce it
- Domain: production-fact
- Claim: The user's policy is that Student, Parent and Tutor are self-selected while **`Manager` may be granted by an administrator only**; this supersedes D-153 §5's initial "leave client-supplied roles as-is" reading. The intent is real and half-implemented: the register form offers exactly three radios (`Parent`/`Student`/`Tutor`), but `icrest/app/controllers/account.controller.js:26,33` persists `req.body.role` verbatim with no allowlist/enum/validator, and there is no role-changing endpoint at all — so `Manager` is granted today only by direct database edit. A second, previously unrecorded path: `account.controller.js:56` overwrites an existing **unverified** account's `password`, `role` and `code` on `ER_DUP_ENTRY`, so anyone knowing the email can rewrite them.
- Type: observed-state
- Sources: docs/DECISIONS.md:9129-9154; docs/S42_DISCOVERY.md:216-236; docs/S42_OPEN_QUESTIONS.md:24-32
- Related IDs: D-153 §5/§7, D-151 §5 (KC3), E2, §6.2, D1
- Temporal: source read as of the 2026-08-01 checkout; correction recorded 2026-08-02
- Candidate status: CURRENT
- Intended vs observed: both — org intent vs source-observed enforcement gap
- Contradicts/competes: D-153 §5's own first recording ("left as-is"), explicitly marked corrected and superseded by §7
- Evidence still required: at-integration-time — `SELECT DISTINCT role` (D1) plus an audit to learn what roles live data actually holds
- Confidence: HIGH — cited to exact production source lines; independently re-verified per D-151's adversarial method.

### INT-12 — Our-side allowlist constraint does NOT relax if the org fixes role validation
- Domain: integration
- Claim: Production role must never by itself grant an elevated role in the new stack: Student/Parent may be mapped from production, but `Tutor`/`Manager` must additionally be confirmed against an allowlist the new stack controls. Three grounds keep this alive even after a production-side fix: (a) pre-fix rows may already carry a self-assigned `Manager`; (b) production is frozen and schema-drifting (`sync({alter:true})` every boot) so the fix cannot be asserted to persist; (c) authorization is not delegated to another system's input validation (CLAUDE.md rule 3).
- Type: requirement
- Sources: docs/DECISIONS.md:9115-9120; :9162-9170; docs/S42_DISCOVERY.md:238-241; docs/S42_OPEN_QUESTIONS.md:33-37
- Related IDs: D-153 §5/§7, I7, CLAUDE.md rule 3, S43/S44
- Temporal: recorded 2026-08-02; binds S43/S44
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found — explicitly framed as surviving §7's correction
- Evidence still required: Phase 3 — confirm the allowlist is actually designed into S43/S44 work when written
- Confidence: HIGH — stated three times across two docs with identical substance.

### INT-13 — §6.2 disposition moved from "accepted" to "to be fixed by the org"
- Domain: org-comms
- Claim: The client-supplied-role finding (§6.2) moved from *accepted* to *to be fixed by the org*, joining §6.1, §6.3 and §6.4 on the list the user will send. The prescribed fix is small and entirely inside the existing system: allowlist `Parent`/`Student`/`Tutor` at create with a 400 otherwise, and accept no role at all in the duplicate-unverified branch; `Manager` stays a database/admin operation.
- Type: decision
- Sources: docs/DECISIONS.md:9105-9109; :9156-9160; docs/S42_OPEN_QUESTIONS.md:22; :31-32
- Related IDs: D-153 §5/§7, E1–E4, §6.1–§6.4
- Temporal: 2026-08-02; send not yet confirmed as done
- Candidate status: CURRENT (open action on the user)
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — whether the E-group notification was actually sent
- Confidence: HIGH.

### INT-14 — `GET /api/accounts/signups` carries per-child, per-session `attended` (the O1/O1b decider)
- Domain: production-fact
- Claim: `getSignups` builds its response from `Calendar.findAll` with a nested `Signup` include and **no `attributes` restriction**, and `signup.model.js` declares `attended: BOOLEAN, allowNull: true`, so every signup column serializes — including `attended` — scoped to the caller, alongside `calendars.startTime`. This removes the direct-MySQL path from the critical path entirely. Its guard (`authBackgroundCheckNeeded`) passes `Student`/`Parent` unconditionally — the only roles issued at launch.
- Type: observed-state
- Sources: docs/S42_DISCOVERY.md:44-73; docs/DECISIONS.md:8882-8891; docs/INTEGRATION_PLAN.md:598-603
- Related IDs: D-151 §2, O1b, I11 rung 1, B4
- Temporal: observed state as of the **2026-08-01 checkout** of `../IntelliChoice-web`
- Candidate status: CURRENT (with drift risk)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: at-integration-time — B2 (deployed build matches checkout) and B4 (`attended` really arrives in live responses); noted also that `pastCalendars` has **no pagination** and grows unbounded per account
- Confidence: HIGH — hand-verified plus adversarially re-read per D-151's method; MEDIUM only for the deployed build matching.

### INT-15 — `attendanceClaimed` is a fail-open trap; the signups response is PII-bearing
- Domain: integration
- Claim: `signups` has **two** attendance columns — manager-recorded nullable `attended` and non-null self-reported `attendanceClaimed`. S43 must never gate an exam on `attendanceClaimed` ("it is the convenient field precisely because it is never null, which is what makes it a fail-open trap"); only `attended === true` means present. Separately, the signups response carries `firstName`, `lastName` and full `children`, so it must be projected to external ids at the adapter boundary before anything is returned, logged, traced, or cached.
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:586-588; :609-613
- Related IDs: D-099, I3–I5, S43
- Temporal: pre-discovery findings 2026-07-25; still binding on S43
- Candidate status: CURRENT
- Intended vs observed: intended-state (requirement) over observed-state (two columns)
- Contradicts/competes: INTEGRATION_PLAN §1 (:55-57) describes only one attendance column — self-corrected by §8
- Evidence still required: Phase 3 — verify no adapter/derivation code reads `attendanceClaimed` once S43 code exists
- Confidence: HIGH — explicit, with the fail-open reasoning spelled out.

### INT-16 — Id namespacing: `acct-<id>` / `child-<id>` over integer PKs
- Domain: integration
- Claim: Production uses integer auto-increment PKs with **no external ids anywhere**; the adapter mints prefix-namespaced ids — `acct-<id>` for account-holding students/parents/adults and `child-<id>` for parent-registered children — two disjoint populations that must not collide. "Non-registered" ad-hoc students have no account linkage and are out of integration scope.
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:318-323; docs/S42_DISCOVERY.md:152-157
- Related IDs: I3, I4, D-151 §6
- Temporal: plan 2026-07-24; production fact as of the 2026-08-01 checkout
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: dev fake uses opaque `VARCHAR(64)` external ids (must-fix per S42_DISCOVERY:335) — but fixing the fake is withdrawn by D-152
- Evidence still required: none
- Confidence: HIGH.

### INT-17 — Attendance derivation (I5) and its three fail-closed-able hazards
- Domain: integration
- Claim: The adapter derives "present this week" as a `signups` row with `attended = true` joined to a non-deleted `calendars` row whose `startTime` falls in the current org-local week; NULL/false/no row → absent/unknown → the existing fail-closed gate and `resolve_attendance` interrupt handle it. Three named hazards: `attended = null` means *never marked* (not absent) and must be treated as not-present per CLAUDE.md rule 5; the `children` include has **no `deleted: false` filter** so soft-deleted children come back and the adapter must filter them; and the week-boundary derivation is exactly where the timezone question bites.
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:325-331; docs/S42_DISCOVERY.md:75-82; docs/DECISIONS.md:8893-8895
- Related IDs: I5, D-151 §2, D-152 §2, D-153 §4
- Temporal: plan 2026-07-24; hazards confirmed against the 2026-08-01 checkout
- Candidate status: CURRENT (implementation DEFERRED to S43)
- Intended vs observed: both
- Contradicts/competes: the timezone hazard is materially reduced by D-153 §4 (no Sunday-evening or 00:00–01:00 sessions published) — reduced, not eliminated, per D-153's own stated limits
- Evidence still required: at-integration-time — live signups data; and the S43 loud-log guard from D-153 §4
- Confidence: HIGH.

### INT-18 — Role mapping must fail closed and must ignore `chapterRole` and `permissions`
- Domain: integration
- Claim: Production `role` is a free-text column, so the adapter uses a mapping table where **any unrecognized role string fails closed** (no token), with a metric emitted on unknown roles. Additionally, fail-closed mapping must treat `chapterRole` and the free-text comma-separated `permissions` override as inputs it does not understand, rather than assuming effective access follows from `role` alone.
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:344-346; :589-590; :605-607; docs/S42_DISCOVERY.md:143-148
- Related IDs: I7, A2, D-099, D-151 §5 (KC3), D-153 §5/§7, D1
- Temporal: plan 2026-07-24 + corrections 2026-07-25; role facts as of the 2026-08-01 checkout
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: §7-A2 assumes live role strings match the four known values — an assumption D1 exists to test
- Evidence still required: at-integration-time — `SELECT DISTINCT role` (D1) to learn how many accounts would be refused (fail-closed, so not a blocker per D1's own note)
- Confidence: HIGH.

### INT-19 — Consent ledger (I9): no consent row → no token
- Domain: integration
- Claim: Production stores no consent/COPPA data and its registration flow cannot be extended, so the new stack keeps a consent ledger in its own Postgres (`account_external_id`, version, timestamp, granting parent — external ids and enums only, no PII), with first-entry consent UI (parent grants for each child/student; adults self-consent) and fail-closed minting: no consent row → no token. Consent *text* comes from the §6.1 legal parallel track and is "a true pilot blocker."
- Type: requirement
- Sources: docs/INTEGRATION_PLAN.md:357-363; :437; :467
- Related IDs: I9, I10, S45, §6.1 legal track
- Temporal: plan 2026-07-24; implementation slated S45
- Candidate status: DEFERRED (behind D-152's freeze; the legal-text dependency is independent)
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — current status of the §6.1 legal parallel track
- Confidence: HIGH.

### INT-20 — I11's four-rung data-access ladder, with rung 1 confirmed viable
- Domain: integration
- Claim: Data access is a ladder descended only as far as discovery forces: (1) API-only (O1b) — no DB path, no new credentials, nothing to ask for; (2) hybrid API + read-only DB over a private path; (3) DB-only; (4) org-operated snapshot-sync replica with staleness as a first-class state. Rungs 2+ are Tier 1 asks; rung 1 needs no ask. §8 records that **rung 1 is confirmed viable** — signups returns `attended`, scoped to the caller, with the background-check gate exempting `Student`/`Parent` — so "the Tier 1 DB ask is no longer on the critical path"; rungs 2–4 remain documented fallbacks.
- Type: plan
- Sources: docs/INTEGRATION_PLAN.md:369-393; :598-603; docs/S42_DISCOVERY.md:39-42
- Related IDs: I11, O1b, O2, A1, C4, C9, R5
- Temporal: ladder 2026-07-24; rung 1 confirmed 2026-07-25 and re-confirmed 2026-08-01
- Candidate status: CURRENT (rung selection DEFERRED with the auth decision)
- Intended vs observed: both
- Contradicts/competes: rung 1 makes I14's password-hash-fingerprint revocation check impossible (INT-21) and makes I6's manager-email SQL lookup unavailable, forcing a new-stack-owned branch→manager-email config table
- Evidence still required: at-integration-time — B1 reachability; if it fails, immediate switch to O2/rung ≥ 2 and the C4/C9 DB asks start then
- Confidence: HIGH.

### INT-21 — §4: genuinely impossible without production changes (no SSO, no cross-system revocation)
- Domain: integration
- Claim: Seven requirements are recorded as impossible under the constraint, each with an accepted alternative — notably **seamless SSO from go.intellichoice.org** (no handoff mechanism, both frontends frozen, `sessionStorage` origin-locked → accept one explicit login per device on the new domains, with out-of-band discovery via org email/branch announcements/QR) and **server-side revocation across systems** (no production session store, logout is client-side only → short TTLs plus I14's hash-fingerprint refresh check, which itself is impossible under rung 1, compensated by capping total session length to ~24 h).
- Type: decision
- Sources: docs/INTEGRATION_PLAN.md:426-441; :304-309; :410-418; :222-228
- Related IDs: I1, I2, I13, I14, I8, R6, §7-A1
- Temporal: 2026-07-24
- Candidate status: CURRENT
- Intended vs observed: both — observed production limits driving intended reduced scope
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — table plus matching I-entries.

### INT-22 — The §2.6 gate closed 2026-08-01 (historical)
- Domain: integration
- Claim: INTEGRATION_PLAN §2.6 defines nine measurable exit criteria (traceability, zero open P0/P1, journeys twice consecutively, 3 green full runs, 2 clean deploys + bad-image rollback, ≥1 week of scheduled jobs, live load P95 ≤ 3 s at 150 concurrent, every alarm induced, zero PII) as the gate before integration discovery. That gate is recorded as **CLOSED as of 2026-08-01 (D-148), with criterion 6 closed early by documented user decision.**
- Type: historical-event
- Sources: docs/INTEGRATION_PLAN.md:192-214; docs/DECISIONS.md:8679; docs/PROGRESS.md:7744; :13721; :13755
- Related IDs: D-148, D-123 (R8/R9), §2.6 criteria 1–9
- Temporal: closed 2026-08-01
- Candidate status: HISTORICAL
- Intended vs observed: observed-state
- Contradicts/competes: criterion 2 ("zero open P0/P1") was claimable only because R8 and R9 were converted to time-boxed accepted risks by D-123 (INTEGRATION_PLAN:502-507) — record as a qualified closure, not an unqualified one
- Evidence still required: Phase 3 — the criterion-6 early-close rationale and whether R8/R9 expiry conditions are still tracked
- Confidence: HIGH for the closure; MEDIUM for its completeness given the R8/R9 carve-outs.

### INT-23 — `signups.attended = null` is routine, so UNKNOWN → blocked is a routine path
- Domain: production-fact
- Claim: In production, `signups.attended = null` means "a manager has not marked it yet" and is an ordinary, frequent state — so "blocked because attendance is unconfirmed" is a **routine** path in production, not a rare one. Fail-closed is already implemented correctly (SPEC §5.4.4); what needs attention is that the path is *often taken* — the blocked screen's wording, what the student does next, and how a late manager marking recovers — plus seeding an unmarked-session student so the UNKNOWN path is exercised by e2e, not only unit tests.
- Type: observed-state
- Sources: docs/DECISIONS.md:8978-8989; CLAUDE.md:70-72; docs/S42_DISCOVERY.md:76-78
- Related IDs: D-152 §2, D-154, I5, AttendanceStatus.UNKNOWN
- Temporal: observed as of the 2026-08-01 checkout; named as the one production fact that must inform product work **now**
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: dev fake returns UNKNOWN only when no row exists (`status ENUM('present','absent')`), so the fake understates the frequency — catalogued as "cosmetic — same intent" in S42_DISCOVERY:338
- Evidence still required: Phase 3 — whether the UNKNOWN-path UX work (D-154) actually landed
- Confidence: HIGH — carved out explicitly as the one non-frozen consequence.

### INT-24 — Production schema drift mechanism: `sync({alter: true})` on every boot
- Domain: production-fact
- Claim: `db.sequelize.sync({ alter: true, force: false })` runs on **every icrest boot**, issuing `ALTER TABLE` against the live production database with no migrations; a sync failure is only `console.log`ged and the process keeps serving. Collateral proof of real damage: `scripts/drop-indexes.sh` exists solely to delete the duplicate unique indexes (`email_1, email_2, …`) that `alter: true` recreates each boot, and it runs `sudo mariadb ic` — confirming MariaDB and database name `ic`. Consequence: I12's drift defense (contract tests against a schema snapshot + deploy-time read-only column probe + degraded `/readyz`) is justified, not over-engineering.
- Type: observed-state
- Sources: docs/S42_DISCOVERY.md:160-167; docs/INTEGRATION_PLAN.md:395-400; :523-524; docs/DECISIONS.md:8897-8904
- Related IDs: I12, R4, D-151 §3, D2, B2
- Temporal: observed as of the 2026-08-01 checkout; mechanism is ongoing (drift accrues continuously)
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: at-integration-time — D2 (`SHOW CREATE TABLE` ×5) as the drift baseline and B2 before trusting any documented schema
- Confidence: HIGH — this is the single strongest justification for the whole re-verification protocol.

### INT-25 — Production security findings exist and are catalogued elsewhere
- Domain: production-fact
- Claim: S42_DISCOVERY §6 catalogues six-plus production findings (severity High→Informational) as "the org's decisions, not this roadmap's work"; they are independent of this project's schedule because they affect a system serving real users today, and reporting them to the owner is the correct disposition — details are not re-extracted here (see the dedicated security-report artifact and D-153 §5/§7 dispositions).
- Type: audit-finding
- Sources: docs/S42_DISCOVERY.md:199-268; docs/DECISIONS.md:9000-9005; :8928-8931; docs/S42_OPEN_QUESTIONS.md:94-104
- Related IDs: E1–E4, §6.1–§6.7, D-152 §4, D-153 §5
- Temporal: found 2026-08-01; dispositioned 2026-08-02
- Candidate status: CURRENT (unfixed by design — production is frozen)
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — whether the notification to the org has actually been sent
- Confidence: HIGH.

### INT-26 — Message A/B/C/D dispositions: OPEN_QUESTIONS' ledger vs ORG_ASKS' stale "Send now"
- Domain: org-comms
- Claim: Per the current ledger, Message A (timezone) is downgraded to a courtesy question (D-153 §4), Message B (DNS) is **answered** (org adds records at integration time), and Messages C (topology/TLS/outages/log destination) and D (peak concurrency) wait for integration per D-152. But S42_ORG_ASKS' status table still marks **A = "Send now"** and **B = "Send now"** with C = "Hold until S42", and its internal notes still say Message A is "due before S43 opens" and B "before S48" — a direct, unreconciled contradiction with the post-D-152/D-153 state.
- Type: audit-finding
- Sources: docs/S42_ORG_ASKS.md:7-14; :388-389; docs/S42_OPEN_QUESTIONS.md:15-22; :108-113; docs/DECISIONS.md:9084-9097; :9122-9127
- Related IDs: Message A, B, C, D; C1–C3, C8; D-152, D-153, D-130, D-134, D-099
- Temporal: ORG_ASKS status written 2026-07-25 (Message D added 2026-07-31); superseded 2026-08-01/08-02
- Candidate status: SUPERSEDED (ORG_ASKS' status table); the message *drafts* themselves remain usable
- Intended vs observed: intended-state
- Contradicts/competes: INT-08, INT-09, INT-10 — this claim exists to name the contradiction, not resolve it
- Evidence still required: Phase 3 — decide whether S42_ORG_ASKS gets a freeze banner or is marked historical
- Confidence: HIGH — both texts read directly; the conflict is textual, not inferential.

### INT-27 — The re-entry protocol: what reopens, in what order
- Domain: freeze
- Claim: The frozen tracker specifies the re-entry order: on the day integration is declared, reopen the document and proceed **A1·A2·A3 → B1·B2 measurement → A4 (auth) finalized**, and not before ("the values go stale"). The re-read list is S42_DISCOVERY (contract/schema/roles/timezone, source-based, 2026-08-01) plus D-151 and D-152 — with the explicit warning that because `sync({alter:true})` can change the live schema every boot, **B2 (deployed build matches that checkout) must be verified before those documents are trusted**.
- Type: requirement
- Sources: docs/S42_OPEN_QUESTIONS.md:108-121; :42-43
- Related IDs: A1–A5, B1–B6, C1–C9, D1–D5, E1–E4, D-151, D-152
- Temporal: written 2026-08-01 (baseline date 2026-08-01), effective at integration start
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: INTEGRATION_PLAN §5's S42 row assigns the same measurements to a session that has already passed
- Evidence still required: at-integration-time — the whole protocol is a verification plan
- Confidence: HIGH — the ordering and the B2-first rule are both explicit.

### INT-28 — "Only two live actions" (C3 send + E-group notification) — but C3 is already answered
- Domain: org-comms
- Claim: The frozen tracker's "order now (post-D-152)" lists exactly two still-valid actions — **send C3 (DNS)** and **notify the org of the E group** — with everything else frozen; and its "still valid exception" section lists only the E-group notification. Yet the same document's D-153 resolved-ledger at the top states C3 is **already confirmed possible and no longer open**, and its C table still marks C3 🔴 "cannot be deferred." This is an internal contradiction inside one file.
- Type: audit-finding
- Sources: docs/S42_OPEN_QUESTIONS.md:108-113; :39-40; :17; :76
- Related IDs: C3, Message B, E1–E4, D-152 §4, D-153 §6
- Temporal: L108-113 written under D-152 (2026-08-01); the D-153 ledger added 2026-08-02 without updating L110 or L76
- Candidate status: SUPERSEDED (the C3 half of the action list); the E-group half remains CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: INT-09 (DNS answered) — recorded as a tension, not resolved
- Evidence still required: Phase 3 — reconcile L110/L76 with the 2026-08-02 ledger
- Confidence: HIGH — both statements are in the same 121-line file.

### INT-29 — Enrollment FAQ approval is the sole launch-checklist gate on the guest journey's canonical question
- Domain: org-comms
- Claim: The Q&A app's canonical guest question "How do I enroll a student?" **refuses to answer on purpose** (correct fail-closed behavior), because the only covering document `public-enrollment-faq` is synthetic draft content (`status: draft`, public manifest:78). Four draft claims need org sign-off (grades 1–7 in three bands that skip grade 3; enrollment via a branch manager; a single placement pre-exam; per-branch pricing kept out of the doc). On approval the action is editorial only — correct the four facts, drop the DRAFT banner, flip `status: draft → approved`, re-run `make knowledge-load`; `effective_from` (2026-08-01) is already past so it goes live immediately. Internal note: this is "the only launch-checklist item gating the guest journey's canonical question."
- Type: open-work
- Sources: docs/ENROLLMENT_FAQ_APPROVAL.md:1-28; :86-94
- Related IDs: D-146
- Temporal: `effective_from` 2026-08-01; approval outstanding as of the audit
- Candidate status: CURRENT (still draft)
- Intended vs observed: both — observed refusal, intended approval flow
- Contradicts/competes: none found; explicitly must **not** be bundled with the security report or the timezone/DNS asks (different audience: content owner vs system operator)
- Evidence still required: Phase 3 — confirm the manifest still reads `status: draft` and that no approval has landed
- Confidence: HIGH.

### INT-30 — Production roles: free-text, four values, no admin role, unvalidated user input
- Domain: production-fact
- Claim: `accounts.role` is free-text `STRING NOT NULL` with no enum, validator or allowlist; exactly four Title-case values appear across both repos (`Parent`, `Student`, `Tutor`, `Manager`); **there is no admin role** (case-insensitive `admin` grep over icrest returns zero) — elevated access comes from the separate free-text `permissions` column. A second unrelated free-text vocabulary, `chapterRole`, is hardcoded only in the frontend with typos preserved (`President`, `Vice President`, `Tresurer`, `Secretery`). Since role is client-supplied, only a live `SELECT DISTINCT role` reveals what is actually stored.
- Type: observed-state
- Sources: docs/S42_DISCOVERY.md:135-148; :294-296; docs/S42_OPEN_QUESTIONS.md:88
- Related IDs: I7, A2, D1, D-151 §5, D-153 §7
- Temporal: observed state as of the 2026-08-01 checkout
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: §7-A2's assumption that live role strings match the four known values is untested
- Evidence still required: at-integration-time — D1 (`SELECT DISTINCT role`)
- Confidence: HIGH.

### INT-31 — The login contract: minimal success body, an unverified-account trap, and zero rate limiting
- Domain: production-fact
- Claim: `POST /api/accounts/login` reads only `email` (lowercased server-side) and `password` (HMAC-SHA256-hashed before lookup); success 200 returns `{ token, profile, name, permissions }` and **nothing else — no account id, no email, no role**, so identity requires a follow-up `GET /api/accounts`. Wrong password and unknown email are indistinguishable 401s. Critically, `verifiedAt === null` yields a 400 "Verify your email" **only after the password matches** — so that 400 confirms correct credentials and triggers a verification email; the new stack must never surface this path to end users. There is **no rate limiting anywhere** in production, which is why the new stack's own per-account + per-IP limiter is mandatory rather than a nicety.
- Type: observed-state
- Sources: docs/S42_DISCOVERY.md:84-119; docs/INTEGRATION_PLAN.md:283-288; :623-626
- Related IDs: O1/O1b, I1, I15, R2, R3, D-151
- Temporal: observed state as of the 2026-08-01 checkout
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found; reinforced by the standing note that every `/api/accounts/*` route beyond login/register is reachable by any authenticated account regardless of role — the login API authenticates only, never authorizes
- Evidence still required: at-integration-time — B2 (contract matches deployed build) and B3 (login latency p50/p95)
- Confidence: HIGH.

### INT-32 — Token transport: our integration must use `x-access-token`, never `?token=`
- Domain: integration
- Claim: Production reads its token as `req.body.token || req.query.token || x-access-token` — no `Authorization: Bearer` — and because GETs have no body its frontend authenticates with `?token=`, landing JWTs in access logs, proxy logs, browser history and `Referer` headers. Tokens are HS256 `{id, iat, exp}`, 12 h, signed with a source-visible literal, with no revocation and no logout endpoint; expired/forged/malformed all return `403 Authentication failed`. Derived requirement: **our integration must call with the `x-access-token` header, never the query param.**
- Type: requirement
- Sources: docs/S42_DISCOVERY.md:256-263; docs/S42_DISCOVERY.md:303-309; docs/INTEGRATION_PLAN.md:295-302; :41-44
- Related IDs: I1, I14, O1b, §6.6, B5
- Temporal: observed 2026-08-01; requirement binds S44
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify the requirement is honored once the O1b client exists
- Confidence: HIGH.

### INT-33 — §7 residual risks and assumptions, including a sign-off nominally due "at S42"
- Domain: deferred-work
- Claim: §7 records R1–R7 and A1–A3 as **permanent** (properties of production or of the constraints, with no planned work behind them) — R1 production-repo compromise ⇒ new-stack impersonation, "accepted, to be signed off by the org at S42"; R2 weak hashing; R3 brute-forceable reset codes; R4 drift; R5 attendance freshness; R6 discoverability ceiling; R7 new-login availability coupled to icrest — while R8 and R9 are expressly different: open P1 findings accepted only for the gate and pilot, each with a named closure (S43/S46 for R8; the commit-ordering fix for R9) and a written expiry condition ("do not read them as settled"). Assumptions: A1 some lawful read path exists, A2 role strings match the four known values, A3 additive DNS permitted.
- Type: open-work
- Sources: docs/INTEGRATION_PLAN.md:500-575
- Related IDs: R1–R9, A1–A3, D-123, D-107, D-110 §3, D-097, AUD-L-07, AUD-X-07
- Temporal: 2026-07-24, amended by D-123; R1's org sign-off nominally "at S42"
- Candidate status: CURRENT for R1–R7/A1–A3; R8/R9 CURRENT-but-expiring (R8 "expires at first real traffic"; R9 void if `learning_checkpoint_repairs_total` moves)
- Intended vs observed: intended-state
- Contradicts/competes: R1's "signed off by the org at S42" has no visible completion, and D-152 freezes the org interaction it depends on — an orphaned sign-off obligation
- Evidence still required: Phase 3 — whether R1's org sign-off happened; whether R8/R9 expiry conditions are actively monitored
- Confidence: MEDIUM — the risk text is explicit, but the sign-off/expiry tracking status is not evidenced in the read range.

### INT-34 — Discovery's own stated limits: source ≠ deployment, runtime half still owed
- Domain: production-fact
- Claim: S42_DISCOVERY self-labels its status as "source half complete; runtime half still owed (§7)" and states its limits plainly: everything it describes is *this checkout*, whether the deployed build matches is unverified, and `sync({alter: true})` means even the schema is not pinned by source. Method was eight parallel source readers → synthesis → ten load-bearing claims re-read by adversarial verifiers instructed to refute them (**8 CONFIRMED, 2 REFUTED-with-correction, 0 unclear**, both corrections making the finding *more* severe). Credentials were excluded by construction and no secret value is ever quoted. Runtime facts remain org-only: AWS network reachability, TLS/proxy topology, outage history, DNS, and the timezone *decision*.
- Type: audit-finding
- Sources: docs/S42_DISCOVERY.md:1-36; :270-299; docs/DECISIONS.md:8862-8880
- Related IDs: D-151, B1–B6, C4–C9, D1–D5, KC2, KC3
- Temporal: 2026-08-01 checkout; the runtime half is unfilled as of the audit
- Candidate status: CURRENT — with the DNS/timezone items since answered by D-153
- Intended vs observed: observed-state
- Contradicts/competes: D-153 answered two of §7's asks (DNS, timezone decision) but §7's text still lists them as needed — mild staleness
- Evidence still required: at-integration-time — the whole B/C/D measurement set, B2 first
- Confidence: HIGH — the document is unusually explicit about its own epistemic status.

### INT-35 — The dev fake models a system that does not exist — but the "fix the fake" urgency was withdrawn
- Domain: deferred-work
- Claim: Six structural mismatches between the MySQL dev fake and production are catalogued as must-fix (branch metadata, role vocabulary/case, attendance shape, id convention, parent→child linkage, grade type), so "a green contract test against today's fake is evidence about a fiction," and S43 should build against **production-shaped fixtures captured from source**, not an extended fake. D-152 then **withdrew that urgency**: rewriting the fake now would be work performed months before first use against a schema `sync({alter:true})` can still move, and the mismatches provably stay behind the `ProfileAdapter` seam because `StudentProfile`/`BranchInfo`/`AttendanceStatus` are SPEC-derived, not fake-derived (verified case by case: grade, role/id/linkage, attendance derivation).
- Type: decision
- Sources: docs/S42_DISCOVERY.md:324-342; docs/DECISIONS.md:8933-8942; :8959-8976; CLAUDE.md:64-68
- Related IDs: D-151 §6, D-152 §1, I3, D-002 seam, S43
- Temporal: catalogued 2026-08-01 (D-151); urgency withdrawn same day (D-152)
- Candidate status: DEFERRED
- Intended vs observed: both
- Contradicts/competes: D-151 §6's "must-fix ×6" framing vs D-152 §1's explicit withdrawal — D-152 outranks it as the later, explicit user decision; note also D-152 §3's separate S43 fact that `IcProfileAdapter` merges two sources (`org_branches` for address/coords, `accounts` join for `manager_email`) and is not a single-source read
- Evidence still required: Phase 3 — confirm no app-level decision has since come to depend on the fake's schema (the "keep the seam honest" test)
- Confidence: HIGH.

---

## §7 — Active work, open items, parked work, known limitations, user decisions (WORK-01…WORK-44)

### WORK-01 — B6's `scope_guard`/retrieval overlap is specified, not built
- Domain: active-work
- Claim: The one piece of code left after Milestone 15 is running `scope_guard` concurrently with retrieval for ~22% off every grounded turn with no prompt change and therefore no quality delta; D-423 specifies it and verified three code constraints, and PROGRESS states "nothing about it needs re-deriving".
- Type: plan
- Sources: docs/PROGRESS.md:19-24; docs/ROADMAP.md:3303-3320
- Related IDs: D-423, W27, B6 (OPEN_DECISIONS decided-items table)
- Temporal: specified 2026-08-18; unbuilt as of that date
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — confirm no concurrent-`scope_guard` implementation exists in the graph code
- Confidence: HIGH — stated as the explicit next-session pointer in two documents

### WORK-02 — SNS email subscription is `PendingConfirmation`
- Domain: open-item
- Claim: The SNS email subscription is in `PendingConfirmation`, so four informational alarms currently publish to a topic with no confirmed subscriber; PROGRESS calls it "one click, not optional".
- Type: observed-state
- Sources: docs/PROGRESS.md:27-28
- Related IDs: D-401
- Temporal: as of 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — live SNS subscription state (user-side action, may be unverifiable from repo)
- Confidence: HIGH — explicit carry-over item

### WORK-03 — `chat_escalation_sends` migration is not on staging until the next deploy
- Domain: open-item
- Claim: The `chat_escalation_sends` table is not present on staging; the deploy pipeline runs migrations before switching services, so a deploy is the only action needed.
- Type: observed-state
- Sources: docs/PROGRESS.md:29-30
- Related IDs: D-420–D-422, W26, B4
- Temporal: as of 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — migration file exists in repo; staging schema state is external
- Confidence: HIGH — explicit carry-over item

### WORK-04 — An answer cache is still a decision, blocked on citation `effective_to`
- Domain: open-item
- Claim: An answer cache "remains a decision, not an optimisation" because citations carry `effective_to`, so a cached answer can outlive its sources' effective window (rule 5); the named fix is clamping each entry's TTL to its earliest citation expiry.
- Type: open-work
- Sources: docs/PROGRESS.md:31-33
- Related IDs: B6, D-423
- Temporal: raised/carried 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — verify citations carry `effective_to` and no answer cache exists
- Confidence: HIGH — stated as a decision, not a plan

### WORK-05 — Verification snapshot on merged `main` (`6f107c1`)
- Domain: content-state
- Claim: On merged `main` at `6f107c1`: `ruff` clean, `ruff format --check` clean, `pyright` 0 errors, pytest 1735 passed / 2 skipped, Playwright 127 passed / 2 skipped, chat-web 49 unit tests, learning-web 26, both builds clean.
- Type: observed-state
- Sources: docs/PROGRESS.md:35-38; docs/ROADMAP.md:3205-3207
- Related IDs: Milestone 15
- Temporal: 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — re-run counts on current HEAD; ROADMAP defers the numbers to PROGRESS rather than repeating them
- Confidence: HIGH — precise, single-source, dated

### WORK-06 — Staging is deployed and current (run 32171998780), and its own probe found a cancel-endpoint defect
- Domain: content-state
- Claim: Staging is deployed and current for the first time since Milestone 11 — `44a12df`, run 32171998780, both services on `gha-44a12dfc9549`, rollout COMPLETED, one additive migration applied before the switch, canary clean, having been 27 commits behind; the post-deploy probe then found `POST /chat/sessions/{invented}/turns/x/cancel` answering 202 to an anonymous caller (not an authz bypass) and it was fixed by unscoping the sweep inside `request()`.
- Type: historical-event
- Sources: docs/PROGRESS.md:118-137; docs/ROADMAP.md:3209-3224
- Related IDs: D-416, W22, W10
- Temporal: 2026-08-18
- Candidate status: CURRENT (deploy state) / HISTORICAL (the defect event)
- Intended vs observed: observed-state
- Contradicts/competes: WORK-03 (staging is current *except* for `chat_escalation_sends`, which post-dates the deploy)
- Evidence still required: Phase 3 — the unscoped sweep in the cancel path; staging image tag is external
- Confidence: HIGH — measured, two consistent sources

### WORK-07 — The tfvars-floor warning was a phantom blocker, corrected in place (D-418)
- Domain: known-limitation
- Claim: A self-authored warning that a fresh-checkout apply would "roll staging back past Milestone 13" was measured false — Terraform reads the image from the deployed container definition (`adopt_deployed_image` defaults true since D-244), so the check was refusing applies over the one input Terraform does not read; it was renamed `make image-check`, now judges only a service and its family's latest revision agreeing, reports the pin without failing on it, and no longer demands a gitignored file.
- Type: audit-finding
- Sources: docs/PROGRESS.md:139-153; docs/ROADMAP.md:3238-3248
- Related IDs: D-418, D-244, D-137, A3, W25
- Temporal: warning stood most of 2026-08-18; corrected same day
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: PROGRESS.md:85 (the decided-items table still lists A3 as ⏳ with "D-401 and D-406 stay unapplied until this exists"); OPEN_DECISIONS.md:15 states the same
- Evidence still required: Phase 3 — `make image-check` target and `adopt_deployed_image` default in terraform
- Confidence: HIGH — measured via `terraform plan`, recorded in three documents

### WORK-08 — D-401/D-406: "unblocked but unapplied" vs "applied in W25"
- Domain: open-item
- Claim: PROGRESS states D-401 (alarm split) and D-406 (NAT follows its consumers) are unblocked but "still unapplied; applying them is a deploy-shaped action and yours to authorise", while ROADMAP's W25 entry records both as applied (D-419) with three task definitions re-registered and a post-apply plan of `No changes`.
- Type: audit-finding
- Sources: docs/PROGRESS.md:155-156; docs/ROADMAP.md:3249-3254
- Related IDs: D-401, D-406, D-418, D-419, A3, W25
- Temporal: both dated 2026-08-18
- Candidate status: UNKNOWN — unresolved contradiction
- Intended vs observed: both
- Contradicts/competes: direct contradiction between the two sources; also competes with WORK-02 (the SNS topic D-401 created has no confirmed subscriber, which implies the apply did happen)
- Evidence still required: Phase 3 — DECISIONS.md D-419 text and terraform state; do not resolve from these two sources alone
- Confidence: MEDIUM — both statements are explicit; the PROGRESS line is likely the stale one but that is not established here

### WORK-09 — `.agents/skills/` and `skills-lock.json` untracked and not ignored
- Domain: open-item
- Claim: `.agents/skills/` and `skills-lock.json` are untracked and not gitignored, so they appear in every `git status`; they are Claude Code tooling artefacts and PROGRESS records that committing or ignoring them is a user preference that "was not chosen for you".
- Type: open-work
- Sources: docs/PROGRESS.md:158-160
- Related IDs: D10/D11 (PROGRESS.md:83 records "agent tooling committed" as done)
- Temporal: as of 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: PROGRESS.md:83's "agent tooling committed ✅ done" reads as tension with these paths still being untracked
- Evidence still required: Phase 3 — `git status` and `.gitignore`
- Confidence: HIGH — explicit, self-describing

### WORK-10 — Integration remains frozen; reconfirmed after the audit lists were empty
- Domain: deferred-work
- Claim: Integration with `go.intellichoice.org` is frozen: the user reconfirmed D-152 *after* being told the audit lists were empty and the suite green, so the "finish and test against the dev fakes first" condition is explicitly not treated as met, and integration reopens only on explicit say-so — no AWS→icrest reachability measurement, no production API URL, no test account, no finalising the §3.1 auth option, and O1b stays a recommendation rather than a finding.
- Type: decision
- Sources: docs/PROGRESS.md:65-71; docs/OPEN_DECISIONS.md:20,634-635
- Related IDs: D-152, D-417/A1, OPEN_DECISIONS #A1, S42–S47
- Temporal: original D-152; reconfirmed 2026-08-18
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — user decision, reconfirmed, stated identically in two files

### WORK-11 — C8 `ruff format` recorded as "⏳ next" (168 of 494) and as done (168 of 437) the same day
- Domain: open-item
- Claim: PROGRESS's decided-items table lists C8 as "⏳ next" — one isolated mechanical commit of 168 of 494 files, "not the 116/415 recorded", then enforce `--check` — while ROADMAP's W24 records it done with 168 of **437** Python files reformatted plus `ruff format --check` wired into CI as well as `make lint`, and Markdown scoped out (ruff 0.16.3 reformats Python inside `.md`).
- Type: audit-finding
- Sources: docs/PROGRESS.md:84; docs/ROADMAP.md:3226-3236
- Related IDs: C8, D-417/C8, W24
- Temporal: both 2026-08-18
- Candidate status: UNKNOWN — status and denominator both disagree
- Intended vs observed: both
- Contradicts/competes: the same PROGRESS table marks A3, B4 and B6 "⏳" although ROADMAP W25/W26/W27 record A3 and B4 done and B6 part 1 done — the whole four-row queued block appears superseded by the same milestone that produced it
- Evidence still required: Phase 3 — `ruff format --check` in CI config; count of Python files; git log for the mechanical commit
- Confidence: HIGH — both figures quoted verbatim; the discrepancy is on the page

### WORK-12 — learning-web's banner condition is untested and the cheap fix is a trap
- Domain: open-item
- Claim: learning-web's disconnect-banner render condition is untested and still open after W21; the banner plus an `error`-with-no-snapshot takeover screen both live inside `App.tsx`'s render logic, so testing it means mocking `useLearningSession`, and extracting the JSX would move the markup while leaving the condition untested ("coverage-shaped, worth nothing"). W21's one working extraction (`ConnectingPanel`) does not apply because its condition *is* its lifetime, whereas the banner's condition is data (`streamState === "error"`).
- Type: open-work
- Sources: docs/PROGRESS.md:107-117
- Related IDs: W20, W21, C7, D-343, D-414, OPEN_DECISIONS #14
- Temporal: raised W20, still open after W21 (2026-08-18)
- Candidate status: CURRENT
- Intended vs observed: observed-state
- Contradicts/competes: PROGRESS.md:81 records C7 ("banner condition stays browser-only") as done for chat-web, and PROGRESS.md:101-104 records the chat-side banner condition done in W20/D-414 — the learning-web half is the remainder
- Evidence still required: Phase 3 — absence of a learning-web test covering the banner condition
- Confidence: HIGH — stated at length as an open carry-over

### WORK-13 — `journey-student.spec.ts` is not isolated against staging (newest unresolved test-infra item)
- Domain: open-item
- Claim: Against `E2E_TARGET=staging` the student journey spec is not isolated — measured across three runs, the two tests pass individually against build `4b847a8c5df4` but fail in combination (`answerWholeExam` returned 1 of 10; the refresh test compared two different questions); the cause is stated as an inference, not a conclusion ("that is the next step, not a finished finding"), and the named fixes are test-side: give each test its own fixture student, or clear the student's sessions in `beforeEach`.
- Type: audit-finding
- Sources: docs/PROGRESS.md:16659-16690
- Related IDs: D-213, AUD-F-23
- Temporal: 2026-08-07 (the file's physically last entry)
- Candidate status: UNKNOWN — no later entry records resolution
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — whether `journey-student.spec.ts` now has per-test fixture students or a `beforeEach` cleanup; whether the staging e2e run is still a gate
- Confidence: MEDIUM — the finding is precise, but its status a year of entries later is unestablished

### WORK-14 — D-342 parks all question-bank coverage work until the user asks
- Domain: deferred-work
- Claim: Every question-bank coverage item is parked until the user explicitly asks for new problems to be generated — a standing instruction, not a per-session deferral — covering depth (84 of 153 cells, 189 items short, ≈$13–16, ~3.5 h), missing tiers (15 of 96 spanning skills at one tier), thin banks (5 skills at 1–3 items), and skills with no video (10 of 112 plus 3 holding only inactive). The test is "is the fix 'write more questions'?" — if yes, cite D-342 and stop.
- Type: decision
- Sources: docs/ROADMAP.md:2484-2507
- Related IDs: D-342, D-223, D-341, D-337, D-313, U1/D-324, C1
- Temporal: parking rule current; the four numbers are dated by their source decisions
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found — it explicitly supersedes any attempt to narrow a declaration, target or threshold to close a gap, and states the same finding has been re-derived at least four times
- Evidence still required: none
- Confidence: HIGH — standing user instruction, restated in QUESTION_GENERATION's banner

### WORK-15 — Anything not about content *quantity* stays a defect despite D-342
- Domain: known-limitation
- Claim: D-342's parking explicitly does not cover non-quantity problems — a wrong answer key, an item contradicting its own judge rating, an unservable path — and it depends on one tested behaviour (`_closest_to_recommended` never returns empty, so an unstocked tier stays servable); if that ever breaks it is a real defect D-342 does not cover.
- Type: invariant
- Sources: docs/ROADMAP.md:2503-2507
- Related IDs: D-342, D-341
- Temporal: current
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — the `_closest_to_recommended` non-empty test
- Confidence: HIGH — stated as the parking's precondition

### WORK-16 — S43–S47 frozen by choice; S48–S51 carry no freeze annotation
- Domain: deferred-work
- Claim: Sessions 42–47 are marked "⛔ DEFERRED BY USER DECISION (D-152)" and "frozen by choice, not blocked" with S42's source half done (D-151); the Sessions 48–51 rollout block (production environment, real credentials, A7 close-out, pilot) carries no such banner and is simply unstarted downstream work.
- Type: decision
- Sources: docs/ROADMAP.md:1438-1446,1512-1521
- Related IDs: D-152, D-151, D-153, D-167, D-086, D-129, S42–S51, I1–I15
- Temporal: D-152 original; S42 source half 2026-08-01
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — explicit banner and section text

### WORK-17 — S43's known scope: six MySQL dev-fake mismatches, do not rewrite the fake
- Domain: deferred-work
- Claim: S43's scope is known from D-151 but is to be handled only when S43 runs: the MySQL dev fake models a system that does not exist (six structural mismatches), `IcProfileAdapter` is to be built against production-shaped fixtures rather than by extending the fake, the mismatches stay behind the `ProfileAdapter` Protocol seam, and production `role` must never by itself grant an elevated role here (D-153 §5) because pre-fix rows may already carry a self-assigned `Manager`.
- Type: requirement
- Sources: docs/ROADMAP.md:1469-1497
- Related IDs: D-151, D-152, D-153, S42_DISCOVERY.md §9, I3–I7, I12, I15
- Temporal: recorded 2026-08-01/08-02; deferred indefinitely
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — explicit and detailed

### WORK-18 — W27 measured the latency split and left the fix specified rather than half-built
- Domain: known-limitation
- Claim: A grounded turn makes four sequential Bedrock round trips, written down nowhere until W27: `RAG_ANSWER` 4124 ms (~42%), retrieval 3411 ms (~35%), `scope_guard` 2129 ms (~22%), `create_embedding` 124 ms (~1.3%). The 1.3% figure cancelled an optimisation the author had proposed and the user had already approved (parallelising the embedding, at ~8 KB per checkpoint or a cancellation boundary), and the replacement was "left specified rather than half-built" with three code-verified constraints including that every non-`document_qa` turn would pay one wasted rerank.
- Type: historical-event
- Sources: docs/ROADMAP.md:3303-3320; docs/PROGRESS.md:12-24
- Related IDs: D-423, W27, B6
- Temporal: measured 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found — it supersedes the earlier 25% embedding-parallelisation estimate
- Evidence still required: Phase 3 — the three constraints in graph/state code
- Confidence: HIGH — measured on staging, recorded with the falsified prior

### WORK-19 — U7 §9.1: the retention age floor has not been chosen
- Domain: open-item
- Claim: The age floor for checkpoint deletion is not yet chosen; the dry-run reports zero eligible threads at 30, 90 and 180 days, so the choice costs nothing today and can be made on principle rather than on reclaim.
- Type: open-work
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:261-263
- Related IDs: U7 §9.1, D-322 §4, D-331, ROADMAP U7
- Temporal: 2026-08-14
- Candidate status: UNKNOWN — open as written; no later source read confirms a choice
- Intended vs observed: intended-state
- Contradicts/competes: SPEC's stated retention (completed checkpoints 30 days) already exists as policy per U7 §0.1
- Evidence still required: Phase 3 — whether any retention job or config now carries a floor
- Confidence: MEDIUM — clearly open in its own document, status elsewhere unread

### WORK-20 — U7 §9.2: "does `learning_sessions` get built now?" — asked open, possibly already built
- Domain: open-item
- Claim: U7 §9.2 asks the user whether `learning_sessions` (§2.4) gets built now, with the document's own recommendation being yes and independent of the deletion job, because every day it does not exist is a day the five §2.3 fields with no durable home are recorded nowhere.
- Type: open-work
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:265-267,272-276
- Related IDs: U7 §9.2, U7 §8.2, U7 §2.3, U7 §2.4, D-322 §4, OPEN_DECISIONS #4
- Temporal: asked 2026-08-14
- Candidate status: UNKNOWN
- Intended vs observed: intended-state
- Contradicts/competes: OPEN_DECISIONS #4 (lines 204-211) records the direction as already decided ("consolidate the checkpoint into long-term durable memory… then keep it there", ROADMAP U7) and notes `packages/memory` already consolidates learning memory with a scheduled entrypoint — i.e. the mechanism the question asks about may already exist or have been built since. **Both claims recorded; not resolved.**
- Evidence still required: Phase 3 — does a `learning_sessions` table/migration exist, and does DECISIONS.md answer §9.2
- Confidence: MEDIUM — the question is verbatim; whether it was answered is not established by the read sources

### WORK-21 — U7 §9.3: chat checkpoints are unbounded and addressed by no policy
- Domain: known-limitation
- Claim: Chat checkpoints (U7 §3) are currently unbounded and addressed by no retention policy; the document asks whether they are in scope for a follow-up or filed. Chat threads are 2,178 threads / 35.6 MB, 19.3% of checkpoint bytes.
- Type: open-work
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:268-269,52-63
- Related IDs: U7 §9.3, U7 §3, U7 §1.2
- Temporal: measured 2026-08-14
- Candidate status: UNKNOWN
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — any chat-checkpoint retention job
- Confidence: MEDIUM — clearly open in-document; later status unread

### WORK-22 — U7 §9.4: abandoned sessions are 77% of bytes and were scoped out
- Domain: open-item
- Claim: Abandoned sessions were scoped out by the user, correctly per the document, on the reasoning that mixing retention windows is how the wrong policy gets applied — but §1.2 measures them as where the growth is (`pre_exam` 64.7% + `study` 12.4%), so the document asks whether they are worth revisiting as their own session and recommends a 90-day floor on them as "a bigger, more honest win" than a 30-day floor on completed ones.
- Type: open-work
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:270-273,52-63,276-279
- Related IDs: U7 §9.4, U7 §8.3, U7 §1.2
- Temporal: 2026-08-14
- Candidate status: UNKNOWN
- Intended vs observed: both
- Contradicts/competes: the user's scoping decision competes with the document's own re-scope recommendation; recommendation ≠ decision
- Evidence still required: Phase 3 — whether a follow-up session for abandoned sessions was ever scheduled
- Confidence: MEDIUM — both the scoping and the counter-recommendation are explicit

### WORK-23 — U7 as scoped addresses 1.7% of checkpoint bytes and 0% today
- Domain: content-state
- Claim: Completed sessions are 9 threads / 3.2 MB = 1.7% of checkpoint storage, abandoned sessions 77% and chat 19%; at a 30-day floor the job addresses 0% today because the oldest staging thread is 22 days old, so the dry-run's honest answer is zero threads and zero bytes. The document therefore recommends *not* writing the completed-session deletion yet.
- Type: audit-finding
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:52-70,259-279
- Related IDs: U7 §1.2, U7 §8.1, D-331, D-322 §4
- Temporal: measured on staging 2026-08-14
- Candidate status: HISTORICAL (measurement) / CURRENT (recommendation, unless later overridden)
- Intended vs observed: observed-state
- Contradicts/competes: OPEN_DECISIONS #4's cost line ("one scheduled task next to the existing `retention-purge`") assumes the job gets written
- Evidence still required: Phase 3 — re-measure; check whether a completed-session deletion job now exists
- Confidence: HIGH — measured, tabulated, dated; "status line is a measurement with an expiry date" applies

### WORK-24 — U7 §10: one completed thread has two `learning_gain` rows — logged, not chased
- Domain: known-limitation
- Claim: One completed staging thread (`98abc0f0…`) has two `learning_gain` rows for a single `pre_assessment_session_id` while the other eight have one; either a re-finalize legitimately writes a second row or gain is computed twice for one cycle. Declared out of U7's scope and recorded as a carry-over rather than investigated.
- Type: observed-state
- Sources: docs/U7_CHECKPOINT_CONSOLIDATION.md:291-297
- Related IDs: U7 §10
- Temporal: 2026-08-14
- Candidate status: UNKNOWN — carry-over with no recorded resolution in the read sources
- Intended vs observed: observed-state
- Contradicts/competes: none found
- Evidence still required: Phase 3 — whether a later decision or session investigated the duplicate-gain path
- Confidence: MEDIUM — the observation is precise; its disposition is not

### WORK-25 — Running the generation pipeline is parked (D-342 banner in QUESTION_GENERATION)
- Domain: deferred-work
- Claim: QUESTION_GENERATION's status is "implemented as described" and scoped to one topic (`linear_equations`), multiple-choice only, but a banner forbids starting a generation run to close a coverage gap: depth (189 items short), missing tiers (15 spanning skills at one tier), thin banks and skills with no video are parked until the user explicitly asks, and no declaration or target may be narrowed to make a gap disappear.
- Type: decision
- Sources: docs/QUESTION_GENERATION.md:1-20
- Related IDs: D-342, D-223, D-026, D-186–D-194
- Temporal: current
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: the same file's §10 state block (line 403) reports 696 approved items across 33 topics, which sits oddly beside the header's "Scope right now: one topic"
- Evidence still required: none
- Confidence: HIGH — matches ROADMAP's D-342 table

### WORK-26 — QUESTION_GENERATION's trailing "Next:" is a superseded plan naming a non-Anthropic model
- Domain: known-limitation
- Claim: The file's last instruction still reads "Next: one identical four-candidate repeat… If it again yields 0 of 4, stop using Mistral Large 3 as Generator and obtain additional model access: it is the only accessible model that passes the generator contract", which is superseded — the model roster measured 2026-08-11 records an Anthropic-only gateway with Sonnet 4.5 as Generator and Haiku 4.5 as Solver A/Judge, and states a non-Anthropic provider would be a real integration, not a config change.
- Type: plan
- Sources: docs/QUESTION_GENERATION.md:446-450,243-309
- Related IDs: D-195, D-273 C1 Phase 0, D-243, D-231–D-240, D-194
- Temporal: "Next:" dated to D-195 (2026-08-06); roster re-measured 2026-08-11
- Candidate status: SUPERSEDED
- Intended vs observed: intended-state
- Contradicts/competes: directly contradicts the §243-309 roster in the same file
- Evidence still required: Phase 3 — confirm no Mistral configuration exists in the pipeline
- Confidence: HIGH — the contradiction is internal to one file

### WORK-27 — Only two Anthropic models are invocable, so Solver B shares the Generator's weights
- Domain: known-limitation
- Claim: Measured with 1-token invocations (account 320503430250, us-east-1, 2026-08-11), only Haiku 4-5 and Sonnet 4-5 are actually invocable — `claude-sonnet-5` reports AVAILABLE and denies the call, so `agreementAvailability.status = AVAILABLE` is not a promise you can call the model; with Generator, Solver A and Solver B all wanting independence, two of three must share, so Solver B runs the Generator's own model and the documented asymmetric diversity weakness stands. An open cost question remains: Sonnet 4.5 bills 3× Haiku, and whether a better Generator lowers cost per accepted item is a measurement C1's first wave was to take.
- Type: observed-state
- Sources: docs/QUESTION_GENERATION.md:243-282
- Related IDs: D-273 C1 Phase 0, D-243, D-194
- Temporal: measured 2026-08-11 (supersedes the 2026-08-05 availability read in the same file)
- Candidate status: CURRENT (with expiry — model access can change)
- Intended vs observed: observed-state
- Contradicts/competes: the file's own superseded 2026-08-05 block; WORK-26's Mistral line
- Evidence still required: Phase 3 — current model ids in config/`.env.example`; whether the cost measurement was ever taken
- Confidence: HIGH — invocation-measured, not inferred

### WORK-28 — HINT_SOLUTION_REVIEW: instrument built and measured, loop not built, no pipeline caller
- Domain: known-limitation
- Claim: The reviewer and panel exist and are measured (D-254, D-256, precision 6/6 blocks real, recall ~43% on the one class checkable for free), and `review_panel.py`, `hint_solution_repair.py` and `review_loop.py` are all named as implemented — yet the header states "the loop around them is not built" and "Still not built: any pipeline caller. Nothing in the generation pipeline runs §4, by choice."
- Type: observed-state
- Sources: docs/HINT_SOLUTION_REVIEW.md:1-18
- Related IDs: D-251–D-260, D-257, D-258
- Temporal: status undated in the header block
- Candidate status: UNKNOWN — the header contradicts itself between "the loop … is not built" and "`review_loop.py` … implement[s] … the bounded loop (D-259/D-260)"
- Intended vs observed: both
- Contradicts/competes: internal contradiction within lines 3-15 of the same file
- Evidence still required: Phase 3 — do `review_loop.py`/`hint_solution_repair.py` exist, and does any pipeline module call `HINT_SOLUTION_REVIEW`
- Confidence: HIGH — both statements are in the same 15 lines

### WORK-29 — HINT_SOLUTION_REVIEW sequencing: steps 1–3 ticked, 4–7 not; step 4 is the first paid step
- Domain: deferred-work
- Claim: §8's sequencing has steps 1–3 ticked (floor removed from the audit script, docstring corrected, instrument built as its own `BedrockTask` "wired to nothing") and steps 4–7 unticked: the hard-capped validation run (the first paid step), wiring the decision flow with check-3 sampling, check-4 routing plus check-5 monitoring, and measuring the unmeasured live rejection `_HINT_QUALITY_REJECT_BELOW` (`< 2`). §9 records four things explicitly out of scope: a mutation/golden corpus, growing `GOLDEN_DATASET_BAD_ITEMS`, deleting `hint_quality_score`, and pairwise comparison.
- Type: plan
- Sources: docs/HINT_SOLUTION_REVIEW.md:519-541
- Related IDs: D-249, D-251–D-260
- Temporal: undated within the file
- Candidate status: UNKNOWN — step 3's tick coexists with the header naming the loop built (WORK-28), so the tick state may lag
- Intended vs observed: intended-state
- Contradicts/competes: WORK-28 — an unticked "wire the decision flow" against a header that names `review_loop.py` as implementing the bounded loop
- Evidence still required: Phase 3 — whether the validation run happened; whether `_HINT_QUALITY_REJECT_BELOW` was ever measured
- Confidence: MEDIUM — the ticks are unambiguous but demonstrably out of step with the header

### WORK-30 — CONTENT_COVERAGE's family status column is superseded by work done the same day
- Domain: content-state
- Claim: CONTENT_COVERAGE (built 2026-08-11, "Phase 0 of ROADMAP Session C1") marks family B (37 rows) as "⚠️ needs the Phase R answer-model router" and routes `selection`/`multi_root`/`interval`/`tuple`/`symbolic` to **Phase R** in §5 — but ROADMAP records Phase R DONE 2026-08-11 (D-273), with those verifiers added behind `route_answer`, fail-closed and both-directions tested, and `place_value_compare` re-authored 15/15 → 0/15. The file also records only 4 of SPEC §5.7.3's 12 grade bands populated, with band order load-bearing (`topics_for_grade` returns the first match on endpoints).
- Type: audit-finding
- Sources: docs/CONTENT_COVERAGE.md:1-15,89-98,143-155,160-168; docs/ROADMAP.md:1778-1795
- Related IDs: D-273 (Phase R), D-187, C1 Phase 0/Phase 1/Phase 5
- Temporal: both dated 2026-08-11
- Candidate status: SUPERSEDED (the family-B status cell), CURRENT (family C/D and the band trap)
- Intended vs observed: both
- Contradicts/competes: CONTENT_COVERAGE.md:96 vs ROADMAP.md:1792-1795
- Evidence still required: Phase 3 — `route_answer` verifier coverage vs the 37 family-B rows; whether family C (34 figure rows) is still gated
- Confidence: HIGH — same-day supersession, both texts explicit

### WORK-31 — The volume target is the user's 5–7 items per occupied tier, chosen over SPEC §5.8.1
- Domain: user-decision
- Claim: The volume target is 5–7 items per occupied tier (~25–35 per topic, ~1,000 items across 34 topics) — D-223's measured figure, **chosen by the user** over SPEC §5.8.1's 100-per-topic (~3,400 items, 3× the spend and review burden), on the grounds that §5.8.1's number has never been met by any topic and nothing has measured it as necessary. Not every `(skill, tier)` cell needs filling; treating that as a target costs content quality.
- Type: decision
- Sources: docs/CONTENT_COVERAGE.md:169-181
- Related IDs: D-223, SPEC §5.8.1, D-342
- Temporal: D-223
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: SPEC §5.8.1's 100-per-topic requirement — a deliberate, recorded departure
- Evidence still required: Phase 3 — SPEC §5.8.1 text vs the D-223 record
- Confidence: HIGH — user named as the decider in the source text

### WORK-32 — Three of eleven first-visit disclosures describe behaviour that does not exist
- Domain: known-limitation
- Claim: Checking each §5.1.2 disclosure against the system found three that are NOT BUILT: §2.11's "challenge learning results" (the phrase appears once in the whole SPEC, with no section, endpoint or UI — the reporting half is real, the challenging half is a right the product does not provide), §2.8's solution images (S29 deferred and not started, D-078, so there is no upload path), and §2.5's tutor/branch-manager sharing (roles exist and gate the Q&A corpus, but learning-api has no tutor- or manager-facing view; the read half is deferred to integration, D-086/S43). A disclosure whose "True because" row says NOT BUILT must not ship as written.
- Type: audit-finding
- Sources: docs/FIRST_VISIT_NOTICE.md:33-35,201-218
- Related IDs: T-02, D-127 §3, D-078, D-086, S29, S43, S45, SPEC §5.1.2
- Temporal: undated in the read block; T-02 filed by D-127
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: none found
- Evidence still required: Phase 3 — absence of a challenge route, an image upload path, and a tutor/manager read view
- Confidence: HIGH — each gap is named with the code or decision that makes it a gap

### WORK-33 — Ship eight disclosures, not eleven — a product decision nobody has taken, owned by frozen S45
- Domain: open-item
- Claim: FIRST_VISIT_NOTICE **recommends** shipping eight of the eleven disclosures and attaching 2.5, 2.8 and 2.11 to the work that makes each true, and states that "the three gaps in §5 need a product decision before S45 starts, because they change how many disclosures there are". Owner is S45 per D-127 §3, with this file as the input S45 transcribes rather than drafts; counsel review of the resulting text stays a §6.1 launch gate.
- Type: recommendation
- Sources: docs/FIRST_VISIT_NOTICE.md:214-218,231-237,3-13
- Related IDs: T-02, D-127 §3, S45, SPEC §5.1.2, §6.1 legal track, OPEN_DECISIONS #3 (routing named a §5.1.2 prerequisite)
- Temporal: recommendation open as written
- Candidate status: CURRENT (as a pending decision) / DEFERRED (its owner S45 is inside the frozen S43–S47 block)
- Intended vs observed: intended-state
- Contradicts/competes: WORK-10/WORK-16 — S45 is frozen by D-152, so a launch-gate requirement is owned by a session that must not start; recommendation ≠ decision, and no user decision on eight-vs-eleven is recorded in the read sources
- Evidence still required: Phase 3 — whether DECISIONS.md contains a ruling on the eight-vs-eleven question
- Confidence: HIGH — the recommendation and its blocking status are both explicit

### WORK-34 — OPEN_DECISIONS #1: fixed by D-325 via option A, against the file's recommendation of B
- Domain: user-decision
- Claim: Study re-serving the exam's questions was fixed on 2026-08-14 by D-325 via **option A** (exclude the session's exam templates from study selection), while the entry recommended **B**; B is additionally recorded as unachievable on today's bank because since D-226 every servable template has exactly one rendering, so B would serve the same question with options shuffled — "B does not fix the defect; it disguises it". The genuinely open remnant is content, not code: re-rendering with different numerical parameters is the authoring work D-189 costed and the user rejected.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:43-98
- Related IDs: OPEN_DECISIONS #1, D-325, D-314, D-226, D-189, D-370, SPEC §5.9/§5.12
- Temporal: raised 2026-08-13, fixed 2026-08-14, verified by code read 2026-08-16
- Candidate status: CURRENT (decision) / SUPERSEDED (the recommendation of B)
- Intended vs observed: both
- Contradicts/competes: the entry's own recommendation; counts toward the against-recommendation set in WORK-40
- Evidence still required: Phase 3 — `flow._templates_to_avoid` and `journey-student.spec.ts:377`
- Confidence: HIGH — stale-entry box is explicit and code-verified

### WORK-35 — OPEN_DECISIONS #4: the user answered with an option that was not on the list (consolidate, then keep)
- Domain: user-decision
- Claim: Against three pruning options, the user chose **option D, not on the list**: "Consolidate the checkpoint into long-term durable memory according to some criteria, then keep it there." The decision reframes the design question from "how long do we hold the working state" to "what in a finished session is worth remembering", reuses `packages/memory` (S25) which already consolidates and already has a scheduled entrypoint, and requires design review before code and staging numbers before sizing (ROADMAP U7). The measurement behind it: LangGraph checkpointer ~4.8 GB across 6.5 M rows on the local dev DB, ~37× `question_variants`, and the recorded framing calling `question_variants` "the fastest-growing table" was wrong.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:171-215
- Related IDs: OPEN_DECISIONS #4, D-322 §4, D-331, S25, ROADMAP U7, U7 §8/§9
- Temporal: measured and decided 2026-08-14
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: WORK-23 (U7's later measurement says the scoped job addresses 1.7% and zero bytes today, so "not urgent at today's volumes" is confirmed while the job's shape is re-scoped)
- Evidence still required: Phase 3 — whether the consolidation job exists next to `retention-purge`
- Confidence: HIGH — user's words quoted, decision id given

### WORK-36 — OPEN_DECISIONS #5: spend the depth budget, but later — parked, nothing blocked
- Domain: deferred-work
- Claim: The depth-generation budget decision is "spend it, **but later** ('the near future'); parked, nothing blocked" — the gap being 84 of 153 cells, 189 items short, ≈315 candidates at a measured 60% acceptance, ≈$13–16 and ~3.5 h at ~1.5 candidates/min. The file's own recommendation was "spend it"; the outcome deferred it. The summary at the top adds that depth generation timing is "decided in principle, parked in practice".
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:219-231,36
- Related IDs: OPEN_DECISIONS #5, D-223, D-193, D-313, D-322, D-342
- Temporal: decided 2026-08-14; still parked as of 2026-08-18
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found — consistent with D-342 (WORK-14) and the QUESTION_GENERATION banner (WORK-25)
- Evidence still required: none
- Confidence: HIGH — consistent across three documents

### WORK-37 — OPEN_DECISIONS #6: video catalog parked on the user's instruction, and the item's figure was wrong by ~100×
- Domain: deferred-work
- Claim: Item #6 is parked 2026-08-18 (D-417) on the user's instruction — no expansion of coverage now, a further seeding run is the user's to schedule, and `YOUTUBE_YOUTUBE_API_KEY` remains theirs to provision (PROGRESS still lists #6 as "blocked on the YouTube key, which only you can supply"). The figure the item was argued from — "4 videos covering 4 of 112 skills" — was true on 2026-08-13 and superseded two days later; a live read measured 497 videos, 363 active-and-approved, 102 of 112 skills servable, last synced 2026-08-15 07:39 UTC, so the user's recollection of "roughly 100" was correct and a product decision (declaring video intervention absent at launch) was one step from being taken on a stale number. A real loss event occurred (182 rows wrongly deactivated by D-326's guard reading `saw_whole_channel = deferred == 0`) and was recovered the same day.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:23-28,32-33,234-269; docs/PROGRESS.md:89-98,105; docs/ROADMAP.md:3232-3237
- Related IDs: OPEN_DECISIONS #6, D-417/B5, D-337, D-326, D-314, D-342
- Temporal: figure written 2026-08-13, superseded 2026-08-15, corrected/parked 2026-08-18
- Candidate status: DEFERRED
- Intended vs observed: both
- Contradicts/competes: "parked, not blocking" (OPEN_DECISIONS:32-33) vs "still blocked on the YouTube key" (PROGRESS:105) — a wording tension worth flagging; 10 of 112 skills with no video remain a content question (D-337 established no further run changes them)
- Evidence still required: Phase 3 — the D-326 guard's current condition (`covered == 0 and deferred == 0`)
- Confidence: HIGH — measured live and cross-recorded in three documents

### WORK-38 — OPEN_DECISIONS #7: keep `difficulty_tiers` declarations unchanged (user's words, D-341)
- Domain: user-decision
- Claim: The user decided, in D-341 (2026-08-15): current single-tier coverage is temporary because more problems will be generated across missing tiers later; treat these as expected content gaps, not taxonomy/declaration errors; keep existing `difficulty_tiers` declarations unchanged; do not modify the taxonomy solely because the bank is thin or concentrated. So `difficulty_tiers` is an authoring target, not a description of the current bank, and narrowing a declaration would trade a visible gap for an invisible one.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:273-303
- Related IDs: OPEN_DECISIONS #7, D-341, D-313, U1/D-324, D-302, D-342, D-417/D10
- Temporal: decided 2026-08-15; entry reconciled 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: the entry previously recommended the **opposite** of D-341, making it "the artefact most likely to cause a fifth re-derivation"; the recommending wording was removed rather than annotated, because an annotated recommendation is still a recommendation to a skimmer
- Evidence still required: none
- Confidence: HIGH — user quoted verbatim, cross-referenced from PROGRESS and ROADMAP

### WORK-39 — OPEN_DECISIONS #8: D-310 stands until staging stops being synthetic
- Domain: deferred-work
- Claim: Item #8 is unchanged and was not re-raised: D-310 (2026-08-13, declined once with a reason) stands because staging only, production is a separate frozen system, Postgres holds no PII by design, and the residual risk is Bedrock spend which the gateway caps. What would change it is staging serving anything real — a real student account, parent email or document; if revisited, rotate at the source then re-run `deploy-staging.yml`, because ECS tasks read the value at container start.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:307-317; docs/PROGRESS.md:106
- Related IDs: OPEN_DECISIONS #8, D-310
- Temporal: 2026-08-13; reaffirmed 2026-08-18
- Candidate status: DEFERRED
- Intended vs observed: intended-state
- Contradicts/competes: none found
- Evidence still required: none
- Confidence: HIGH — restated identically in PROGRESS

### WORK-40 — OPEN_DECISIONS #10: five sub-items, all decided
- Domain: user-decision
- Claim: All five of item #10's sub-items are recorded decided: the narrative modal's reused "Why this is your next step" header needs a **new API field** (a wire-shape change, hence a decision not a patch); `clearInterventionIfPresent` missing the retry-ladder pause ~1 in 12 staging walks is classified a harness race, not a product defect, with a breadcrumb as the next step and only the hour's spend open; `formatDateLabel`'s date-only shift is settled as **CDT**; `deploy-staging.yml`'s `push` trigger stays commented out and deployment stays manual; and the "15 of 92 items repeat the context block's opening sentence in the stem" observation was not raised.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:334-349; docs/PROGRESS.md:82
- Related IDs: OPEN_DECISIONS #10, D-321, C9 (deployment stays manual)
- Temporal: decided 2026-08-14 / reaffirmed 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: intended-state
- Contradicts/competes: within the item, "ladder pause: investigate" and "`formatDateLabel`: fix now or leave it armed" read as work still unscheduled despite the header calling all five decided
- Evidence still required: Phase 3 — whether the narrative API field, the breadcrumb and the `formatDateLabel` fix were built
- Confidence: MEDIUM — the header asserts all decided; two sub-items still contain open sub-questions

### WORK-41 — OPEN_DECISIONS #11: option B chosen (D-384) because two measurements made C impossible today
- Domain: user-decision
- Claim: The container-scan gate failure was resolved by **option B** (install security updates in the runtime stage) on 2026-08-17 (D-384), against the entry's recommendation of **C** (pin-and-bump by digest): `python:3.12-slim` still shipped `util-linux 2.41-5` so there was no fixed digest to pin to, while `apt-cache policy` reported the fix already in the archive. Also corrected in place: it is **one** CVE (`CVE-2026-53615`) across nine binary packages from one source, not nine HIGH CVEs — Trivy's `Total: 9` counts rows.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:353-401
- Related IDs: OPEN_DECISIONS #11, D-384, PR #310
- Temporal: raised and decided 2026-08-17
- Candidate status: CURRENT — with the note that C "stays the better long-term shape" and nothing in B blocks adopting it when upstream republishes
- Intended vs observed: both
- Contradicts/competes: the entry's own recommendation; B knowingly makes image contents depend on when the build ran, the reproducibility property the pinned base tag exists to provide (an accepted cost, i.e. a live known limitation)
- Evidence still required: Phase 3 — the `apt-get` upgrade line in `apps/*/Dockerfile`
- Confidence: HIGH — outcome, reasoning and correction all explicit

### WORK-42 — OPEN_DECISIONS #12: the user chose the interstitial (D-390), not the recommended embed
- Domain: user-decision
- Claim: For `AUD-L-16` (video help sending a minor to youtube.com), the user chose **option B, the interstitial** (D-390), against the recommendation of a narrowly-scoped `youtube-nocookie` embed, preserving the property that the page loads nothing third-party. Implemented so the card stays a real anchor with a real `href` (click intercepted, element not replaced), so middle-click and open-in-new-tab still work and the existing spec's href assertion holds — and **a power user can still bypass the step with a middle-click, accepted rather than overlooked**.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:403-450
- Related IDs: OPEN_DECISIONS #12, AUD-L-16, D-390, `video-intervention.spec.ts`
- Temporal: raised and decided 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: the entry's own recommendation; the accepted middle-click bypass is a standing known limitation
- Evidence still required: Phase 3 — the interstitial in `InterventionScreen.tsx` / `VideoContent`
- Confidence: HIGH — decision, decider and accepted residual all named

### WORK-43 — OPEN_DECISIONS #14: vitest+jsdom in **both** frontends (D-405), against the recommendation of one-app-first
- Domain: user-decision
- Claim: The user chose **A, both frontends now** (D-405, 2026-08-18) against the recommendation of **B, one app first**, on the argument that two independently deployed frontends drifting is D-347, the most repeated defect shape in the project, so starting asymmetric is starting with the bug. Built: vitest + jsdom in both apps with config in each `vite.config.ts`, a `test` script and a `Test` CI step; `@testing-library/react` deliberately deferred until the first component test, which arrived with D-413 and required explicit `setupFiles` because RTL registers `afterEach(cleanup)` only when the runner exposes globals.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:545-584; docs/PROGRESS.md:53-60
- Related IDs: OPEN_DECISIONS #14, D-405, D-413, D-414, D-403, D-347, EDGE-CHAT-02
- Temporal: decided and built 2026-08-18
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: the file's header says "**two** of the answers went against the recommendation" (OPEN_DECISIONS.md:5-6), but at least four outcomes are labelled as going against or overturning the item's own recommendation (#1, #11, #12, #14, plus #13's WebKit sub-entry) — the count itself is a documentation defect. Residual limitation: `errors.ts`'s status-to-message rules remain carried by the browser suite alone, stated as a choice rather than a gap.
- Evidence still required: Phase 3 — `src/test/setup.ts` and the `Test` step in both CI jobs; reconcile the two-vs-four count
- Confidence: HIGH — decision explicit; the count discrepancy is arithmetic on the file's own labels

### WORK-44 — OPEN_DECISIONS #2, #3, #9, #13: four outcomes recorded as closed in line with their reasoning
- Domain: user-decision
- Claim: Four items closed without contradicting their own recommendation: **#2** the client-error sink was built on both apps via option A (learning D-328, chat D-372), with chat unable to have an authenticated endpoint (its primary caller is anonymous per SPEC §5.19.1) so the gate became a rate limit — per `sub` with a token and a **single shared app-wide bucket** for anonymous reports, whose weakness (two unrelated visitors competing for one allowance) is stated in the router docstring; **#3** URL routing decided as `react-router` (A), named a prerequisite for §5.1.2's first-visit disclosures; **#9** dependency PRs decided as a batch merge with a standing rule (patch/minor on green CI, majors read individually), the item's own count corrected from 7 to **26** ("my count was a filter bug"); **#13** the `downloadIcs` DOM contract closed by D-399 after two remedies that did not close it, via a Playwright spec asserting the code's contract with the DOM rather than a jsdom unit test, with the WebKit project from D-397 kept on narrower merits.
- Type: decision
- Sources: docs/OPEN_DECISIONS.md:102-144,148-167,321-330,452-543
- Related IDs: OPEN_DECISIONS #2/#3/#9/#13, D-328, D-372, D-315, D-352, D-397, D-399, D-391, SPEC §5.19.1, §5.1.2
- Temporal: #2 2026-08-16, #3 2026-08-13/14, #9 2026-08-14, #13 2026-08-17
- Candidate status: CURRENT
- Intended vs observed: both
- Contradicts/competes: #13's own WebKit sub-entry records the measurement overturning its recommendation (both specs pass on WebKit with `downloadIcs` reverted), which feeds the count discrepancy in WORK-43; #3 is a decision only — no source read confirms `react-router` was built
- Evidence still required: Phase 3 — is `react-router` actually installed and routing; do both `/client-errors` routes exist; was the 26-PR backlog cleared
- Confidence: MEDIUM — outcomes explicit, but "decided" is not "built" for #3 and #9

---

## §8 — Cross-cutting contradiction index

Twenty-one material contradictions, judged from the 258 claim blocks above. Each entry names
the claims involved and states **both sides**. None is resolved here — that is Phase 3's job,
and several are decisions only the user can take. An entry earns its place by being able to
mislead a future reader who consults only one of the two documents.

**1. SPEC-as-written vs decided reality, unmarked in SPEC — the amendment-layer problem**
Claims: ARCH-08, ARCH-23, ARCH-25, WORK-31, REQ-21, REQ-22, SEC-14, SEC-15, COST-27, INT-05,
INT-06, REQ-06, REQ-19, COST-02, REQ-35, REQ-37. The single largest class in this ledger is
structural rather than factual: SPEC.md is treated as the requirement source of truth, later
decisions are recorded in DECISIONS.md, and **SPEC carries no amendment marker at the point of
departure** — so every one of these reads as current requirement to anyone who opens SPEC alone.
Nine strands:
- *Deployment substrate.* SPEC §5.33/§5.36 prescribe AWS Organizations, EKS across three AZs and
  Aurora PostgreSQL (ARCH-23, ARCH-25); D-004 decided and shipped ECS Fargate + RDS Postgres 16
  with pgvector + an RDS MySQL fixture (ARCH-08). Neither SPEC section is marked superseded.
- *Question volume.* SPEC §5.8.1 requires ~100 templates per topic; the user's D-223 target is
  5–7 items per occupied tier (WORK-31) — recorded as a deliberate departure in DECISIONS/ROADMAP,
  not in SPEC.
- *Solution images.* SPEC §5.17 and CLAUDE.md rule 8 state immediate-deletion image handling as
  active product behavior, and §5.1.4 lists image analysis as an interrupt-gated action
  (REQ-21, SEC-14); D-078 deferred the whole feature and nothing was built, so TRACEABILITY
  dispositions the same requirement as "the feature does not exist" (REQ-22, SEC-15).
- *Observability.* SPEC §5.32.1 still reads as an open "choose one after contractual review" fork;
  D-214/D-242 chose LangSmith cloud with PII masked at source and built the telemetry-leg filter
  (COST-27).
- *Auth menu.* SPEC §5.2.2 and INTEGRATION_PLAN §3.1 read as live work to be finalized "at S42"
  (INT-06); D-152 and CLAUDE.md forbid finalizing the option or measuring reachability now, and
  O1b stays a recommendation until measured (INT-05).
- *NL2SQL.* SPEC §5.26.3 permits an internal dev/eval/analytics NL2SQL under twelve controls
  (REQ-06); TRACEABILITY states no NL2SQL exists to test for, and ROADMAP S30's SQL-parser
  validation was never built for that reason — whether the internal variant is planned-later or
  abandoned is stated nowhere.
- *Gateway surface.* SPEC §5.25.1 lists six gateway methods (REQ-19); only `generate_structured`
  and `create_embedding` exist, the other four dispositioned by name via D-022/D-078 (COST-02).
- *Study-plan priority order.* REQ-35 carries SPEC §5.11.2's seven-rule priority while ROADMAP
  records "a departure from SPEC, recorded not buried" on that very ordering — the departure's
  content lives outside SPEC.
- *Post-exam form.* SPEC §5.9.1 forbids reusing a variant (REQ-37); ROADMAP records post-exam
  "knowingly repeats an authored item" as an accepted departure, again with no SPEC marker.

**2. Two USER decisions in direct conflict — `difficulty_tiers`**
Claims: WORK-38 (with WORK-14, WORK-15; see DECISION_SUPERSESSION_MAP.md, Unresolved chains).
D-322 §7 instructed editing `difficulty_tiers` declarations to match the judge's observed
ratings, while D-341 decided the opposite — keep the declarations unchanged and treat single-tier
coverage as expected content gaps. D-342's supersession list names D-322 §5, **not §7**, so on
the documents' own terms both user instructions are live.

**3. D-401/D-406: applied or unapplied**
Claims: WORK-08, COST-24 (and COST-26, WORK-02). PROGRESS.md's top block still reads "still
unapplied; yours to authorise", while ROADMAP W25 and D-419 record both decisions applied with a
No-changes post-apply plan; the existence of the new SNS topic with an unconfirmed subscriber is
consistent only with the apply having happened.

**4. C8 `ruff format`: status and denominator both disagree**
Claim: WORK-11. PROGRESS records C8 as "⏳ next, 168 of 494"; ROADMAP W24 records it done at
168 of 437 — the same day, with neither the status nor the file count reconcilable, and the same
PROGRESS block marks A3/B4/B6 "⏳" against ROADMAP W25–W27 recording them done.

**5. D-356 status contested across documents**
Claims: DECISION_SUPERSESSION_MAP.md chain M2. DECISIONS.md heads D-356 "⛔ open — characterised,
not fixed"; PROGRESS.md states "✅ D-356 IS FIXED". No third document adjudicates, and the two
sentences are not reconcilable by reading order alone.

**6. U7 §9.2 asks whether to build a table that was built the same day**
Claim: WORK-20. U7 §9.2 poses "does `learning_sessions` get built now?" as an open question;
D-332 built the table, and OPEN_DECISIONS #4 records the direction as already decided with
`packages/memory` already consolidating on a schedule.

**7. HINT_SOLUTION_REVIEW contradicts itself within twelve lines**
Claims: WORK-28, WORK-29. The header says "the loop around them is not built" six lines above
naming `review_loop.py` as implementing the bounded loop (D-259/D-260); the sequencing section's
step-3 tick and unticked step 4 ("wire the decision flow") sit on the other side of the same
contradiction, so which state is current is undecidable from the file.

**8. QUESTION_GENERATION's trailing "Next:" names a model the same file rules out**
Claims: WORK-26, WORK-27. The trailing instruction names Mistral Large 3 as the only viable
generator; the same file's 2026-08-11 roster records only two invocable Anthropic models
(Sonnet 4.5 as generator, so Solver B shares the generator's weights) — a superseded plan left in
the imperative mood at the end of the document, where a reader looks for what to do next.

**9. CONTENT_COVERAGE's status column is superseded by work done the same day**
Claim: WORK-30. The family-B rows read "needs the Phase R router" (CONTENT_COVERAGE.md:96) while
ROADMAP:1792-1795 records Phase R done on that date; families C/D and the band trap are unaffected
and remain current.

**10. Freeze visibility inversion — the frozen work reads as the live work**
Claims: INT-06, INT-07, INT-26, INT-28 (and INT-05). INTEGRATION_PLAN's §3.1 decision gate, §5
session table and §8 header describe integration as in-flight with **zero** mentions of D-152,
S42_ORG_ASKS still carries "Send now" markers for messages D-153 already answered (INT-26), and
S42_OPEN_QUESTIONS' "only two live actions" list contradicts itself by including C3, which its own
ledger records as answered (INT-28). Whether these are deliberate pre-freeze artefacts or simply
stale is stated nowhere.

**11. An accepted risk whose expiry and whose closure path cannot both hold**
Claims: SEC-09, REQ-09, ARCH-18 (map chain G3). §7-R8 accepts tutor/`branch_manager` read scope
"until first real traffic", and CLAUDE.md rule 3 states server-side authorization as
non-negotiable; the only recorded closure path is S43/S46, which D-152 freezes — so the acceptance
expires on an event its own remedy is forbidden to reach.

**12. Configured alarms vs deployed alarms**
Claims: COST-21, COST-25, COST-26, WORK-02. The P1 status block claims all 22 product KPIs
alarmed and "all 10 P1s closed"; PROGRESS records `sessions_completed_floor` **not deployed**
because its count is gated on `daily_completed_sessions_floor` = 0, and no document records that
variable being raised — while D-419's applied two-topic split has an SNS subscription still in
`PendingConfirmation`, making the pages quieter than D-401 intended.

**13. Does a NAT gateway exist**
Claims: ARCH-29, COST-28. ARCHITECTURE.md describes a single NAT gateway in the present tense as
the egress path LangSmith requires; D-406/D-419 record the NAT as "absent from the plan entirely,
which is D-406's verification", and PROGRESS separately carried a "~$33/mo for nothing while
tracing is disabled" note whose date is outside the re-verified ranges.

**14. ARCHITECTURE.md contradicts itself about the scheduler**
Claims: ARCH-04, ARCH-05, ARCH-06, ARCH-07. Lines 24–36 list four enabled EventBridge schedules
with a fixed nightly order that is a correctness constraint (D-357), while :1850-1851, :2068 and
:1791-1792 still say the jobs are manually triggered and the weekly `youtube-sync` schedule is
"later infra work"; §5's closing sentence adds a third ambiguity — "that retention job stays
unscheduled" with two candidate referents.

**15. FINAL_ARCHITECTURE's status claims are 2026-07-21 projections read as current**
Claims: ARCH-26, ARCH-08, ARCH-27, ARCH-10. The document says D-004 is "still 'proposed,' not
'accepted'", S33/S34 "not started", and the single-worker SSE bus unscheduled for replacement;
D-004 was accepted the next day, and D-334/D-335 shipped exactly the Postgres LISTEN/NOTIFY
replacement the file says nobody scheduled. The file's own L183-185 instruction to regenerate it
was never carried out.

**16. Audit-ID namespace collisions across three registers**
Claims: TEST-20 (map, Audit-ID namespace rule). `AUD-L-17`/`AUD-L-19` exist in both
AUDIT_FINDINGS.md (renumbered per D-174, ranges deliberately left ambiguous) and
AUDIT_LIVE_2026_08_17.md:43,45 as entirely different findings; the disambiguation heuristic
written into one register does not work across documents, and P1-n/AUD-n IDs are cited without
their source register throughout.

**17. AUDIT_LIVE's still-open tail vs closures recorded only in DECISIONS**
Claim: TEST-25. AUDIT_LIVE_2026_08_17.md's narrowed open list still carries the exam timer, the
`.ics` branch and the tutor-chat browser leg; D-391, D-392→D-397→D-399 and D-398 record all three
closed. The audit file was never updated, so the two documents disagree about what remains
un-walked.

**18. OPEN_DECISIONS' own header count is arithmetically wrong**
Claim: WORK-43 (with WORK-44). The header states "two of the answers went against the
recommendation"; at least four items are labelled by the file itself as going against or
overturning their own recommendation (#1, #11, #12, #14), plus #13's WebKit sub-entry — a
documentation defect in the summary line of the document most likely to be skimmed.

**19. One attendance column or two — and a fail-open trap**
Claim: INT-15. INTEGRATION_PLAN §1 (:55-57) describes a single attendance column; §8 corrects
this to two, where `attendanceClaimed` is student-asserted and reading it as attendance would
**fail open** against CLAUDE rule 5 — and the same response is PII-bearing. The uncorrected §1 is
the part a reader meets first.

**20. Severity mismatch on the production 6-digit code**
Claim: SEC-31. The outgoing S42 report grades the weak, over-shared, non-expiring, unrate-limited
6-digit code "Medium"; INTEGRATION_PLAN §7-R3 carries the same fact as a **permanent
account-takeover residual risk** on the new stack, because production is frozen and cannot fix it.

**21. Retention-window sprawl — three coexisting policy families and one undischarged obligation**
Claims: ARCH-19, WORK-19, WORK-21, WORK-22, WORK-23, WORK-35, SEC-20, TEST-10 (with ARCH-04,
ARCH-05; map chain F6). Three retention families coexist without a document that reconciles them:
D-114's 90/90/365 derived-text windows, D-153's 365-day `learning_events`, and D-333's 30/90/180
checkpoint floors still in dry-run with the age floor unchosen (WORK-19) — while chat checkpoints
are covered by no policy at all (WORK-21) and abandoned sessions, 77% of bytes, were deliberately
scoped out (WORK-22). Spanning all of them, D-114 §4's privacy-notice obligation is still
undischarged: T-02's first-visit notice is scheduled-not-shipped (SEC-20, TEST-10), and the notice
text would have to state windows that three families define differently.

---

## §9 — Phase 3 verification queue

Derived mechanically from every claim whose `Evidence still required:` line is not "none" —
**231 of the 258 claims**. Membership was read off the Evidence lines themselves, not inferred
from the claim text. A claim appears in exactly one group; where its Evidence line spans two
kinds of work, it is filed under the kind that has to happen **first**.

### (a) code/test existence-and-pass checks — 129

Read the named module, or run the named test, and record whether it exists and passes.

- **REQ-01** — four PII-floor tests exist and pass
- **REQ-02** — scan-logs runs; trace negative arm real
- **REQ-03** — five learning services contain no model call
- **REQ-04** — grading exact comparison; persisted field set
- **REQ-05** — no runtime NL2SQL; parameterized authorized queries
- **REQ-07** — rag.py SQL predicates; role-access tests pass
- **REQ-08** — docstring disposition vs SPEC's six predicates
- **REQ-09** — resolve_target_student hole still present
- **REQ-10** — interrupt endpoint plus three HITL tests
- **REQ-11** — both graph interrupts resumable, same endpoint
- **REQ-12** — attendance gate opens only on PRESENT
- **REQ-13** — Attendance Resolution path built and reachable
- **REQ-14** — no-citation refusal covered by coverage eval
- **REQ-15** — reranker-unavailable floor test; degraded signal alertable
- **REQ-16** — repair bounded; schema_invalid vs output_truncated
- **REQ-17** — one Pydantic model per artifact boundary
- **REQ-19** — gateway method set; judge uses generate_structured
- **REQ-20** — spend-reconciliation test and script pass
- **REQ-21** — no image path, blob store, scanner
- **REQ-22** — five named image artifacts still absent
- **REQ-24** — re-check only if §5.17 gets built
- **REQ-25** — no first-visit notice component exists
- **REQ-26** — LocationConsentModal exists; S45 not run
- **REQ-27** — JWT claims; any parental_consent_verified gate
- **REQ-28** — consent copy; ephemeral_location never persisted
- **REQ-29** — summary path shares no transcripts
- **REQ-31** — intervention router four steps, six labels
- **REQ-32** — HintResponse, Guardrails, self-harm safety policy
- **REQ-33** — correct_after_solution excluded from mastery updates
- **REQ-34** — no runtime YouTube call in intervention
- **REQ-35** — study_plan priorities present, no model call
- **REQ-36** — both gain formulas, twelve metrics persisted
- **REQ-37** — exam_policy behavior vs recorded departure
- **REQ-38** — Idempotency-Key honored; no set regeneration
- **REQ-39** — bootstrap weights exact; no IRT path
- **REQ-40** — two leak-assertion tests exist and pass
- **REQ-41** — pipeline checks diffed against the twelve
- **REQ-42** — difficulty recalibrated from observed responses
- **REQ-43** — outcome enum closed; reason always written
- **REQ-44** — message-set test can fail correctly
- **REQ-45** — generic copy only; tier still logged
- **REQ-47** — shipped string matches SPEC exactly
- **REQ-48** — system_error copy claims nothing about corpus
- **REQ-49** — each fallback row implemented and tested
- **REQ-51** — each component matches its declared type
- **REQ-52** — graph state PII-free; checkpoints covered
- **ARCH-01** — code/infra covers the claimed session range
- **ARCH-03** — /dev/token gate; no real auth provider
- **ARCH-16** — no DB session across keep-alive loop
- **ARCH-17** — reconcile module, metric, two unfixed seams
- **ARCH-18** — read-branch gap in resolve_target_student
- **ARCH-19** — storage split vs actual migrations/models
- **ARCH-32** — suppression location in /readyz handler
- **SEC-01** — no PII column in models or migrations
- **SEC-02** — service-layer join; no warehouse copy
- **SEC-03** — spec allowlist vs extra=forbid payload models
- **SEC-04** — which matrix rows have backend enforcement
- **SEC-05** — purity test walks models; denylist non-trivial
- **SEC-06** — three test arms per payload type
- **SEC-07** — negative arm, vacuity guard, exporter wiring
- **SEC-08** — scanner exists (one run isn't assurance)
- **SEC-09** — read path still unchecked; write refusal present
- **SEC-10** — tripwire metric exists and is read
- **SEC-11** — live parent-link lookup on every route
- **SEC-12** — manually entered address not retained
- **SEC-13** — purge covers failure and abandonment paths
- **SEC-15** — no image upload or VLM path
- **SEC-19** — counter table transactionally safe under concurrency
- **SEC-20** — no notice component; §6.1 track status
- **SEC-24** — hide_password survives; no secret-adjacent print
- **SEC-25** — second gate exists; /dev/token secret-gated
- **COST-02** — gateway method set in bedrock.py
- **COST-03** — gateway source and three named tests
- **COST-04** — the function and its call sites
- **COST-05** — reconciliation script and named test
- **COST-06** — D-294 record and curriculum test path
- **COST-08** — _spend threading and the budget tests
- **COST-09** — reservation repo, settle(), advisory lock
- **COST-10** — input token bound in gateway code
- **COST-13** — two named tests and their assertions
- **COST-14** — per-student attribution query shape
- **COST-18** — four job entrypoints log structured
- **COST-20** — attendance except block; unknown label emission
- **COST-22** — label pre-initialisation and its alarm
- **COST-27** — configure_langsmith(), its test, filter, alarm
- **TEST-02** — sampled rows cite tests that exist
- **TEST-04** — six structural sections' mechanisms exist
- **TEST-08** — git show c44414f
- **TEST-10** — notice component absent; §6.1 track started
- **TEST-11** — authored route and rejection tests pass
- **TEST-12** — the both-halves propagation test
- **TEST-13** — band constants and their asserting tests
- **TEST-14** — run or inspect the named test
- **TEST-22** — six specs created by the closures
- **TEST-23** — the two named tests exist
- **TEST-25** — the three post-audit specs exist
- **TEST-26** — re-enumerate both errors.ts files
- **TEST-27** — inspect e2e/fixtures/capture.ts
- **INT-15** — no code reads attendanceClaimed
- **INT-23** — did D-154's UNKNOWN-path UX land
- **INT-29** — manifest still status: draft, unapproved
- **INT-32** — no O1b client exists to verify
- **INT-35** — no app decision depends on fake's schema
- **WORK-01** — no concurrent scope_guard in graph code
- **WORK-03** — migration in repo; staging schema external
- **WORK-04** — citations carry effective_to; no answer cache
- **WORK-06** — unscoped sweep in the cancel path
- **WORK-09** — git status and .gitignore
- **WORK-11** — format check in CI; file count; commit
- **WORK-12** — missing learning-web banner-condition test
- **WORK-13** — per-test fixture students; staging gate status
- **WORK-15** — _closest_to_recommended non-empty test
- **WORK-18** — three constraints in graph/state code
- **WORK-19** — any retention job now carrying a floor
- **WORK-20** — does a learning_sessions table exist
- **WORK-21** — any chat-checkpoint retention job
- **WORK-26** — no Mistral configuration in the pipeline
- **WORK-27** — current model ids in config
- **WORK-28** — review_loop.py exists; any pipeline caller
- **WORK-30** — route_answer coverage vs family-B rows
- **WORK-32** — no challenge route, upload, tutor view
- **WORK-34** — _templates_to_avoid and the spec line
- **WORK-35** — consolidation job beside retention-purge
- **WORK-37** — the D-326 guard's current condition
- **WORK-40** — narrative field, breadcrumb, date-label fix
- **WORK-41** — apt-get upgrade line in both Dockerfiles
- **WORK-42** — interstitial in InterventionScreen/VideoContent
- **WORK-43** — test setup and both CI Test steps
- **WORK-44** — react-router routing; both client-error routes

### (b) terraform/AWS-state reads — 42

Read `terraform/`, the CI workflow, or live AWS/CloudWatch/SNS state — configuration is not deployment.

- **ARCH-02** — enumerate terraform environments; account inventory
- **ARCH-04** — four EventBridge rules, crons, timezone
- **ARCH-05** — does checkpoint_retention_cli have a rule
- **ARCH-06** — infra read decides the scheduler doc-rot
- **ARCH-07** — youtube-sync rule exists, state DISABLED
- **ARCH-08** — Fargate services, RDS Postgres, MySQL fixture
- **ARCH-09** — no Atlas/Mongo resource in terraform
- **ARCH-10** — ECS desiredCount; NOTIFY 8000-byte cap
- **ARCH-11** — chat-api autoscaling target metric, channel
- **ARCH-12** — one worker per task; CPU sizing
- **ARCH-13** — current desiredCount matches two tasks
- **ARCH-14** — db.t4g.micro class and pool settings
- **ARCH-15** — account Free-Tier status before pricing
- **ARCH-20** — no real-system connectivity or credential
- **ARCH-21** — actual Postgres schema list; split decision
- **ARCH-22** — one database named intellichoice
- **ARCH-23** — no EKS resource exists in terraform
- **ARCH-24** — which autoscaling signals ECS actually uses
- **ARCH-28** — VPC endpoints, route tables, NAT count
- **ARCH-29** — NAT resources, tracing gate, date the note
- **ARCH-30** — sidecar, metric filters, masking env vars
- **ARCH-31** — workspace id; LangSmithIngestFailed per service
- **ARCH-33** — deploy-staging.yml assertions and retry bound
- **ARCH-34** — Makefile, script, adopt_deployed_image variable
- **ARCH-35** — task-definition env vars; frozen S43 guard
- **SEC-16** — module still wired in staging environment
- **SEC-18** — no WAF resource in terraform
- **SEC-23** — masking policy, per-environment projects configured
- **SEC-26** — whether exposed secrets were later rotated
- **SEC-35** — random_password resources exist in terraform
- **COST-16** — Budget alarm and circuit variables
- **COST-17** — client_error filter, alarm, and topic
- **COST-19** — four heartbeat alarms treat_missing_data breaching
- **COST-21** — deployed vs configured alarms; KPI floor
- **COST-23** — deployed alarm-to-topic mapping
- **COST-25** — floor variable and the alarm's count guard
- **COST-24** — D-401 text, unrouted-alarm test, state
- **COST-28** — NAT resources and state; date the note
- **COST-29** — task size and count unchanged
- **TEST-09** — cloudtrail module wired in staging
- **WORK-07** — image-check target; adopt_deployed_image default
- **WORK-08** — D-419 text plus terraform state

### (c) live/staging measurements or re-measurements — 14

Numbers that age: re-run or re-measure rather than re-quote.

- **REQ-18** — schema-invalid rate; is capture enabled now
- **REQ-46** — access-hint recall since D-371
- **REQ-50** — SLO instrumentation; 100-concurrent ever demonstrated
- **SEC-27** — cost_reservations rows unverified against staging
- **COST-15** — re-run only if a current baseline needed
- **COST-26** — live SNS subscription state (user-side)
- **TEST-15** — re-run anchored awk on AUDIT_FINDINGS
- **TEST-16** — execute the awk, record actual output
- **TEST-21** — compare current suite counts
- **TEST-28** — re-run the suites and compare
- **WORK-02** — live SNS subscription state (user-side)
- **WORK-05** — re-run counts on current HEAD
- **WORK-23** — re-measure; completed-session deletion job
- **WORK-29** — validation run and reject threshold measured

### (d) documentation-reconciliation decisions (no code) — 32

Resolve a wording, count, status marker, or disposition inside the docs; no source change needed to answer.

- **REQ-06** — internal NL2SQL disposition in ROADMAP/DECISIONS
- **REQ-23** — incidental-capture question in OPEN_DECISIONS
- **REQ-30** — counsel review; launch-checklist gate
- **ARCH-25** — SPEC placement table lacks amendment marker
- **ARCH-26** — did S33/S34 deliverables actually ship
- **ARCH-27** — none beyond ARCH-10's verification
- **SEC-17** — ROADMAP S50 A7 carries GuardDuty
- **SEC-32** — any send record for the report
- **SEC-33** — org sign-off; I14 refresh check
- **SEC-34** — role allowlist design in S43 material
- **COST-11** — any doc still lists attribution open
- **TEST-01** — D-129 reading; verdictless §5 sections
- **TEST-05** — architecture change triggering the owed re-read
- **TEST-06** — three decisions say what table attributes
- **TEST-07** — count verdict-bearing sections to confirm 37
- **TEST-17** — every section now has a row
- **TEST-18** — extra-pipe rows keep status in field five
- **TEST-20** — classify surviving AUD-L-17 citations
- **INT-06** — pre-freeze artifact or stale-and-misleading
- **INT-07** — session table vs actual session history
- **INT-12** — allowlist designed into S43/S44 work
- **INT-13** — was the E-group notification sent
- **INT-19** — §6.1 legal parallel track status
- **INT-22** — criterion-6 rationale; R8/R9 expiry tracking
- **INT-25** — was the org notification actually sent
- **INT-26** — freeze banner or mark historical
- **INT-28** — reconcile L110/L76 with the ledger
- **INT-33** — R1 sign-off; R8/R9 monitoring
- **WORK-22** — follow-up session ever scheduled
- **WORK-24** — later investigation of the duplicate gain
- **WORK-31** — SPEC §5.8.1 text vs the D-223 record
- **WORK-33** — eight-vs-eleven ruling in DECISIONS

### (e) at-integration-time only — OUT of Phase 3 scope (D-152 freeze) — 14

Listed so they are not mistaken for Phase 3 work: each needs the production system, which the freeze forbids touching.

- **INT-05** — B1 reachability, B2 build match
- **INT-08** — S43 ingestion-window guard and loud log
- **INT-09** — the DNS records actually created
- **INT-10** — real peak-concurrency measurement
- **INT-11** — SELECT DISTINCT role plus a role audit
- **INT-14** — B2, B4; pastCalendars has no pagination
- **INT-17** — live signups data; the loud-log guard
- **INT-18** — how many accounts would be refused
- **INT-20** — B1 reachability; rung-switch trigger
- **INT-24** — SHOW CREATE TABLE ×5 drift baseline
- **INT-27** — the whole protocol is a verification plan
- **INT-30** — SELECT DISTINCT role (D1)
- **INT-31** — B2 contract match; login latency
- **INT-34** — the whole B/C/D measurement set

### Group counts

- **(a)** code/test existence-and-pass checks — **129**
- **(b)** terraform/AWS-state reads — **42**
- **(c)** live/staging measurements or re-measurements — **14**
- **(d)** documentation-reconciliation decisions (no code) — **32**
- **(e)** at-integration-time only — OUT of Phase 3 scope (D-152 freeze) — **14**
- **Total** — **231** (= the 231 non-"none" Evidence lines; the remaining 27 claims need no further evidence)
- **Phase 3 in scope** — **217** (groups a–d). **Out of scope** — **14** (group e).

---

## §10 — Ledger statistics

Counted mechanically over the `### ` claim blocks and their `- Type:` / `- Candidate status:` /
`- Confidence:` / `- Contradicts/competes:` / `- Evidence still required:` fields. Where a field
carries a qualified value ("CURRENT (partial), open remainder accepted per §7-R9"), the
distribution below buckets it by its **leading** verdict and the qualification is counted
separately — the qualifications are the point, not noise.

### Totals

| Section | Range | Claims |
| --- | --- | --- |
| §1 Requirements, LLM behavior, HITL, deterministic core, failure handling | REQ-01…52 | 52 |
| §2 Architecture, infrastructure, deployment, operational, observability-egress | ARCH-01…35 | 35 |
| §3 Security, privacy, authorization, data boundaries, incidents | SEC-01…35 | 35 |
| §4 Cost controls, observability, alerting, spend accounting | COST-01…29 | 29 |
| §5 Testing, traceability, audit state, verification method | TEST-01…28 | 28 |
| §6 Integration, the D-152 freeze, production facts, org communications | INT-01…35 | 35 |
| §7 Active work, open items, parked work, known limitations, user decisions | WORK-01…44 | 44 |
| **Total** | | **258** |

### `Type:` distribution

| Type | Claims |
| --- | --- |
| observed-state | 57 |
| decision | 50 |
| requirement | 48 |
| invariant | 33 |
| audit-finding | 27 |
| open-work | 17 |
| historical-event | 14 |
| plan | 10 |
| recommendation | 2 |

### `Candidate status:` distribution

Bucketed by leading verdict:

| Status | Claims |
| --- | --- |
| CURRENT | 190 |
| UNKNOWN | 24 |
| DEFERRED | 19 |
| SUPERSEDED (incl. 1 PARTLY SUPERSEDED) | 14 |
| HISTORICAL | 11 |

**97 of the 258** statuses are qualified rather than a bare verdict, and **31** name two or more
verdicts at once ("CURRENT (fix), HISTORICAL (defect)", "CURRENT / DEFERRED",
"SUPERSEDED for the EKS rows; CURRENT for Terraform/CI-CD"). Counting keyword mentions anywhere in
the field rather than at its head: CURRENT 200, DEFERRED 29, UNKNOWN 27, HISTORICAL 18,
SUPERSEDED 16, WITHDRAWN 1. The 24 leading-UNKNOWNs are the ledger's honest core: claims where two
documents disagree and no third source adjudicates.

### `Confidence:` distribution

| Confidence | Claims |
| --- | --- |
| HIGH | 209 |
| MEDIUM | 49 |
| LOW | 0 |

No claim is LOW overall; two carry a LOW clause about a *part* of the claim — REQ-49 ("HIGH that
the matrix exists as written; LOW that all rows are implemented") and SEC-30 ("HIGH for the code
fact, LOW for impact"). Ten claims in total grade two things separately — the other eight split
HIGH from MEDIUM, almost always "HIGH that the document says this; MEDIUM that it is still true"
(REQ-35, REQ-50, ARCH-04, ARCH-26, COST-25, TEST-15, INT-14, INT-22). That split is why the
evidence queue in §9 (231) is much longer than the disagreement count below (142): a claim can be
HIGH-confidence *as a reading of the document* and still need verifying as a fact about the system.

### Contradiction and evidence load

| Measure | Claims |
| --- | --- |
| `Contradicts/competes:` not "none" | 142 of 258 (55%) |
| `Contradicts/competes:` "none found" | 116 of 258 |
| `Evidence still required:` not "none" | 231 of 258 (90%) |
| `Evidence still required:` "none" | 27 of 258 |

**Closing note.** This ledger's companion is
[DECISION_SUPERSESSION_MAP.md](DECISION_SUPERSESSION_MAP.md) — 29 decision chains, including six
phantom or missing decision IDs cited by other documents but with no entry of their own: **D-190,
D-191, D-192, D-210, D-329, D-363**. §8's entries reference its chain labels (G3, F6, H3, M2) where
a contradiction is chain-shaped rather than claim-shaped.

Phase 3 (the verification queue in §9) **must not start automatically.** It runs code, reads AWS
state, and in several places would re-measure paid or live systems; group (e) is out of scope
entirely under the D-152 freeze; and several group (d) items are documentation *decisions* that
belong to the user, not to a verifier. Phase 3 begins when the user says so.
